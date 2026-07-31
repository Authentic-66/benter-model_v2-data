"""DPv1 multi-track feature pipeline.

Reads ``dpv1_feature_config.json`` (generated from Doug's ranking
spreadsheet), computes every feature marked ``active``, and writes one wide
row per entry into ``entry_features_dpv1`` in ``scripts/racing_full.db``.

What is different from the Phase 3C builder
-------------------------------------------
* **Three tracks, one corpus.** GP + CT + MNR, 207,976 entries.
* **Doug's ranks drive activation**, not the Phase 3C defaults. Rank 1-2 are
  on, rank 3 is built but off, rank 4-5 are never computed.
* **Cross-track priors.** Connection and pedigree rates pool across all three
  tracks, which is what makes small-sample cells estimable; the at-this-track
  and at-other-tracks splits are then carried as separate features so the
  model can tell "wins everywhere" from "wins at home".
* **Track-aware speed figures** from ``computed_speed_figures_dpv1`` — the
  v1 table covers GP only and pools par times across tracks.
* **2-year half-life** on aggregate stats, per the Phase 4B spec (Phase 3C
  used 180 days for aggregates).

Everything the Phase 3C builder already did correctly is reused by importing
``scripts/feature_builder.py`` rather than copying it. ``scripts/`` and
``scripts_v2a/`` are not modified.

Leakage discipline is inherited and preserved: every historical statistic is
computed over races with a *strictly earlier* date, so same-day races on the
card being scored are never visible.

Usage
-----
    python scripts_dpv1/feature_builder_dpv1.py build
    python scripts_dpv1/feature_builder_dpv1.py summarize
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "new_features"))

from dpv1_common import (  # noqa: E402
    DEFAULT_CONFIG, DEFAULT_DB, FEATURES_TABLE, SPEED_TABLE, TRACK_CODES,
    class_score_vec, dist_bucket_vec, distance_change_bucket_vec,
    early_pace_position, pace_progression, style_from_position,
    _prior_last_value, _prior_by_entity_expanding,
)
import feature_builder as v1  # noqa: E402

from new_features import (  # noqa: E402
    aggregate_features, class_change_features, cross_track_features,
    equipment_features, pace_bias_features, pedigree_features,
    recent_form_features, troubled_trip_detector,
)

log = logging.getLogger("feature_builder_dpv1")


# ---------------------------------------------------------------------------
# Raw load
# ---------------------------------------------------------------------------

def load_raw(conn: sqlite3.Connection) -> pd.DataFrame:
    """Entry-grain frame across all three tracks."""
    log.info("Loading entries across GP + CT + MNR…")
    df = pd.read_sql_query(
        f"""
        SELECT
            e.id                  AS entry_id,
            e.race_id             AS race_id,
            e.horse_id            AS horse_id,
            e.trainer_id          AS trainer_id,
            e.jockey_id           AS jockey_id,
            e.program_num         AS program_num,
            e.post_pos            AS post_pos,
            e.start_pos           AS start_pos,
            e.weight_lbs          AS weight_lbs,
            e.equipment           AS equipment,
            e.has_lasix           AS has_lasix,
            e.has_blinkers        AS has_blinkers,
            e.finish_pos          AS finish_pos,
            e.beaten_lengths      AS beaten_lengths,
            e.final_odds          AS final_odds,
            e.is_favorite         AS is_favorite,
            e.pace_calls_json     AS pace_calls_json,
            e.trip_comment        AS trip_comment,
            r.race_num            AS race_num,
            r.race_type           AS race_type,
            r.distance_yards      AS distance_yards,
            r.surface             AS surface,
            r.track_condition     AS track_condition,
            r.purse               AS purse,
            r.claiming_price      AS claiming_price,
            r.field_size          AS field_size,
            r.temporary_rail_feet AS temporary_rail_feet,
            r.temperature_f       AS temperature_f,
            rd.race_date          AS race_date,
            rd.track_id           AS track_id,
            h.sex                 AS horse_sex,
            h.color               AS horse_color,
            h.country             AS horse_country,
            h.foaled_date         AS foaled_date,
            h.foaled_place        AS foaled_place,
            h.sire_id             AS sire_id,
            h.dam_id              AS dam_id,
            dm.dam_sire_id        AS damsire_id,
            sf.speed_figure       AS speed_figure_own,
            sf.par_time_sec       AS par_time_sec_own
        FROM entries e
        JOIN races r      ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        LEFT JOIN horses h ON h.id = e.horse_id
        LEFT JOIN dams dm  ON dm.id = h.dam_id
        LEFT JOIN {SPEED_TABLE} sf ON sf.entry_id = e.id
        """,
        conn,
    )
    df["race_date_dt"] = pd.to_datetime(df["race_date"])
    df["is_win"] = (df["finish_pos"] == 1).astype("float64")
    df["is_itm"] = (df["finish_pos"].fillna(999) <= 3).astype("float64")
    df["track_code"] = df["track_id"].map(TRACK_CODES)
    log.info("  %d entries; by track: %s", len(df),
             df["track_code"].value_counts().to_dict())
    return df


def derive_row_local(raw: pd.DataFrame) -> pd.DataFrame:
    """Columns computable from a single row (or a single race) up front.

    These become inputs to the prior-lookups, so they must exist before any
    historical aggregation runs.
    """
    log.info("Deriving row-local columns…")
    raw["class_score"] = class_score_vec(
        raw["race_type"], raw["claiming_price"], raw["purse"])
    raw["dist_bucket"] = dist_bucket_vec(raw["distance_yards"])
    raw["is_maiden"] = class_change_features.is_maiden_race(raw["race_type"])

    raw["own_early_pos"] = raw["pace_calls_json"].map(early_pace_position)
    raw["own_style"] = raw["own_early_pos"].map(style_from_position)
    raw["pace_progression_own"] = raw["pace_calls_json"].map(pace_progression)

    log.info("  detecting trouble in trip comments…")
    raw["troubled"] = raw["trip_comment"].map(troubled_trip_detector.is_troubled)

    # Did this horse finish ahead of the post-time favourite in this race?
    fav_finish = (
        raw.loc[raw["is_favorite"] == 1, ["race_id", "finish_pos"]]
        .groupby("race_id")["finish_pos"].min()
    )
    raw["_fav_finish"] = raw["race_id"].map(fav_finish)
    raw["beat_favorite"] = (
        (raw["finish_pos"] < raw["_fav_finish"]) & (raw["is_favorite"] != 1)
    ).where(raw["_fav_finish"].notna() & raw["finish_pos"].notna())
    return raw


# ---------------------------------------------------------------------------
# Shared prior context
# ---------------------------------------------------------------------------

PREV_COLS = [
    "finish_pos", "purse", "class_score", "is_maiden", "track_id", "troubled",
    "beat_favorite", "start_pos", "own_style", "pace_progression_own",
    "equipment", "has_lasix", "has_blinkers", "distance_yards",
    "beaten_lengths", "field_size", "speed_figure_own", "track_condition",
    "surface",
]


def build_context(raw: pd.DataFrame) -> dict:
    """Prior-race lookup and career counts, shared by every module."""
    log.info("Building prior-race context…")
    t0 = time.perf_counter()
    prev = _prior_last_value(
        raw, entity_col="horse_id", value_cols=PREV_COLS,
        date_col="race_date", prefix="prev",
    )
    prev = raw[["entry_id", "race_date_dt"]].merge(prev, on="entry_id", how="left")
    prev["prev_race_date_dt"] = pd.to_datetime(prev["prev_race_date"],
                                               errors="coerce")
    prev["prev_days_ago"] = (
        prev["race_date_dt"] - prev["prev_race_date_dt"]).dt.days
    prev["prev_pace_progression"] = prev["prev_pace_progression_own"]
    prev.index = raw.index

    # The gap BEFORE the previous start — identifies "second race back off a
    # layoff", which is the bounce pattern Doug asked for.
    gap = raw[["entry_id", "horse_id", "race_date_dt", "race_date"]].copy()
    gap["days_since_last_race"] = prev["prev_days_ago"].to_numpy()
    prev_gap = _prior_last_value(
        gap, entity_col="horse_id", value_cols=["days_since_last_race"],
        date_col="race_date", prefix="pg",
    )
    prev_gap = raw[["entry_id"]].merge(prev_gap, on="entry_id", how="left")
    prev["prev_prev_days_ago"] = prev_gap["pg_days_since_last_race"].to_numpy()

    log.info("  prior-race lookup in %.1fs", time.perf_counter() - t0)

    log.info("Building career counts…")
    cw = raw[["entry_id", "horse_id", "race_date_dt", "is_win", "is_itm"]].copy()
    cw["one"] = 1.0
    rolled = _prior_by_entity_expanding(
        cw, entity_col="horse_id", value_cols=["is_win", "is_itm", "one"],
        prefix="c",
    )
    rolled = raw[["entry_id"]].merge(rolled, on="entry_id", how="left")
    career = pd.DataFrame({
        "entry_id": raw["entry_id"].to_numpy(),
        "career_starts": rolled["c_one"].to_numpy(),
        "career_wins": rolled["c_is_win"].to_numpy(),
        "career_itm": rolled["c_is_itm"].to_numpy(),
    }, index=raw.index)

    return {"prev": prev, "career": career}


# ---------------------------------------------------------------------------
# Features with no home in a dedicated module
# ---------------------------------------------------------------------------

def compute_dpv1_extras(raw: pd.DataFrame, ctx: dict, cfg: dict,
                        active: set[str]) -> pd.DataFrame:
    out = pd.DataFrame({"entry_id": raw["entry_id"]})

    if "track_code" in active:
        out["track_code"] = raw["track_code"]

    if "distance_change_bucket" in active:
        out["distance_change_bucket"] = distance_change_bucket_vec(
            raw["distance_yards"], ctx["prev"]["prev_distance_yards"])

    if "is_stakes" in active:
        out["is_stakes"] = (
            raw["race_type"].fillna("").str.upper().str.contains("STAKES")
            .astype("Int8"))

    if "market_probability_normalized" in active:
        # Raw implied probabilities over-round; normalising to sum to 1 within
        # the race removes the takeout/overround and makes the market
        # comparable across field sizes — Benter's anchor in usable form.
        implied = 1.0 / (raw["final_odds"].astype("float64") + 1.0)
        total = implied.groupby(raw["race_id"]).transform("sum")
        out["market_probability_normalized"] = implied / total.replace(0, np.nan)

    if "new_trainer_flag" in active:
        prev_tr = _prior_last_value(
            raw, entity_col="horse_id", value_cols=["trainer_id"],
            date_col="race_date", prefix="pt",
        )
        prev_tr = raw[["entry_id", "trainer_id"]].merge(
            prev_tr, on="entry_id", how="left")
        out["new_trainer_flag"] = (
            (prev_tr["trainer_id"] != prev_tr["pt_trainer_id"])
            .where(prev_tr["pt_trainer_id"].notna())
            .astype("boolean").astype("Int8"))

    if "new_jockey_flag" in active:
        prev_jk = _prior_last_value(
            raw, entity_col="horse_id", value_cols=["jockey_id"],
            date_col="race_date", prefix="pj",
        )
        prev_jk = raw[["entry_id", "jockey_id"]].merge(
            prev_jk, on="entry_id", how="left")
        out["new_jockey_flag"] = (
            (prev_jk["jockey_id"] != prev_jk["pj_jockey_id"])
            .where(prev_jk["pj_jockey_id"].notna())
            .astype("boolean").astype("Int8"))

    for role in ("trainer", "jockey"):
        name = f"{role}_won_last_race"
        if name not in active:
            continue
        prev_role = _prior_last_value(
            raw, entity_col=f"{role}_id", value_cols=["is_win"],
            date_col="race_date", prefix="pr",
        )
        prev_role = raw[["entry_id"]].merge(prev_role, on="entry_id", how="left")
        out[name] = (prev_role["pr_is_win"] == 1).where(
            prev_role["pr_is_win"].notna()).astype("boolean").astype("Int8")

    for role, surf in (("jockey", "Dirt"), ("jockey", "Turf")):
        name = f"{role}_{surf.lower()}_win_pct"
        if name not in active:
            continue
        from dpv1_common import grouped_prior_rate
        d = cfg["defaults"]
        local = raw[["entry_id", "race_date_dt", "is_win", f"{role}_id"]].copy()
        local["_sub"] = (raw["surface"] == surf).astype(int)
        rate, starts = grouped_prior_rate(
            local, [f"{role}_id", "_sub"], d["shrinkage_prior_win_rate"],
            d["shrinkage_k_defaults"][f"{role}_at_surface"])
        out[name] = np.where(
            (raw["surface"] == surf).to_numpy() & (starts > 0), rate, np.nan)

    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

# Only the Phase 3C builders that join their results on entry_id are reused.
# Buckets 3, 4 and 8 assign horse-sorted arrays onto entry-ordered frames and
# are superseded by new_features/aggregate_features.py — see that module's
# docstring for the measurement.
V1_BUCKETS = {
    1: v1.compute_bucket1_race_context,
    2: v1.compute_bucket2_horse_immutable,
    6: v1.compute_bucket6_race_dynamics,
    7: v1.compute_bucket7_market,
}

DPV1_MODULES = [
    ("aggregates", aggregate_features.compute),
    ("class_change", class_change_features.compute),
    ("class_change/trainer", class_change_features.compute_trainer_class_rates),
    ("recent_form", recent_form_features.compute),
    ("cross_track", cross_track_features.compute),
    ("pace_bias", pace_bias_features.compute),
    ("pedigree", pedigree_features.compute),
    ("equipment", equipment_features.compute),
    ("extras", compute_dpv1_extras),
]


def build_features(conn: sqlite3.Connection, cfg: dict) -> pd.DataFrame:
    raw = derive_row_local(load_raw(conn))
    active = {k for k, v in cfg["features"].items() if v.get("active")}
    log.info("Config %s — %d active features", cfg["version"], len(active))

    ctx = build_context(raw)

    frames = [raw[["entry_id", "race_id", "horse_id", "trainer_id",
                   "jockey_id", "race_date", "track_id"]].copy()]

    # DPv1 modules run FIRST so that where a feature exists in both DPv1 and
    # Phase 3C, the DPv1 implementation is the one that survives the merge.
    for name, fn in DPV1_MODULES:
        t0 = time.perf_counter()
        result = fn(raw, ctx, cfg, active)
        log.info("  [dpv1 %s] %d cols in %.1fs", name,
                 len(result.columns) - 1, time.perf_counter() - t0)
        if len(result.columns) > 1:
            frames.append(result)

    # Phase 3C builders, gated by the DPv1 config's "active" flags.
    for b, fn in V1_BUCKETS.items():
        if not any(cfg["features"][k]["bucket"] == b for k in active
                   if k in cfg["features"]):
            continue
        t0 = time.perf_counter()
        result = fn(raw, cfg)
        log.info("  [v1 bucket %d] %d cols in %.1fs", b,
                 len(result.columns) - 1, time.perf_counter() - t0)
        frames.append(result)

    log.info("Merging %d frames…", len(frames))
    out = frames[0]
    for f in frames[1:]:
        dupes = (set(f.columns) & set(out.columns)) - {"entry_id"}
        if dupes:
            log.info("    superseded by an earlier frame: %s", sorted(dupes))
            f = f.drop(columns=list(dupes))
        out = out.merge(f, on="entry_id", how="left")

    # Fail loudly rather than shipping a table that silently omits a feature
    # Doug ranked 1 or 2.
    produced = set(out.columns)
    missing = sorted(active - produced)
    if missing:
        detail = ", ".join(
            f"{m} (rank {cfg['features'][m]['doug_rank']})" for m in missing)
        raise RuntimeError(
            f"{len(missing)} active feature(s) were not produced: {detail}")

    extra = sorted(produced - active - {
        "entry_id", "race_id", "horse_id", "trainer_id", "jockey_id",
        "race_date", "track_id"})
    if extra:
        log.warning("dropping %d non-active columns: %s", len(extra), extra)
        out = out.drop(columns=extra)

    log.info("Final frame: %d rows x %d columns", len(out), len(out.columns))
    return out


def write_table(conn: sqlite3.Connection, df: pd.DataFrame,
                table: str = FEATURES_TABLE) -> int:
    log.info("Writing %s (drop-and-replace)…", table)
    df.to_sql(table, conn, if_exists="replace", index=False)
    for col in ("race_id", "horse_id", "track_id"):
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON {table}({col})")
    conn.commit()
    return len(df)


def cmd_build(args: argparse.Namespace) -> int:
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    conn = sqlite3.connect(args.db)
    t0 = time.perf_counter()
    df = build_features(conn, cfg)
    write_table(conn, df, args.table)
    log.info("done — %d rows to %s in %.1fs", len(df), args.table,
             time.perf_counter() - t0)
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    df = pd.read_sql_query(f"SELECT * FROM {args.table}", conn)
    print(f"Rows: {len(df)}   Columns: {len(df.columns)}")
    cov = df.notna().mean().sort_values()
    print("\nNon-null coverage per column:")
    for col, pct in cov.items():
        print(f"  {col:<45} {pct * 100:6.2f}%")
    return 0


def _cli() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build")
    pb.add_argument("--db", default=str(DEFAULT_DB))
    pb.add_argument("--config", default=str(DEFAULT_CONFIG))
    pb.add_argument("--table", default=FEATURES_TABLE)
    pb.set_defaults(func=cmd_build)
    ps = sub.add_parser("summarize")
    ps.add_argument("--db", default=str(DEFAULT_DB))
    ps.add_argument("--table", default=FEATURES_TABLE)
    ps.set_defaults(func=cmd_summarize)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(_cli())
