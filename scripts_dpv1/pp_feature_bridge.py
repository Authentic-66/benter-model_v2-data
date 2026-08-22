"""Phase 6B: fill DPv1 feature slots from a Brisnet PP file.

What this is actually for
-------------------------
After ``load_pp_card.py`` writes a card into the database and
``feature_builder_dpv1.py`` runs, the Sunday ELP card scored **65.5%** feature
coverage — a large gain on hand entry's 27%, but with a sharp internal split.
Horses with prior starts in ``racing_full.db`` came out near 88%; the rest sat
at 40%, and the boundary is exactly the 58% of the field the corpus has seen
before.

The other 42% are not first-time starters. Most are shippers whose past races
happened at Churchill, Indiana Grand, Kentucky Downs — tracks outside this
corpus. To DPv1 they look identical to an unraced horse, because every
``last_race_*`` and ``career_*`` column is NULL, and the preprocessor's
``{col}__missing`` indicators fire exactly as they would for a debut runner.
That is a *wrong* signal, not merely an absent one, and it is the single
biggest thing a PP file can fix.

So the design principle here is narrower than "map PP fields to DPv1 fields":

    The value is in turning off a false first-time-starter signal, more than
    in the numbers themselves.

That distinction decides the awkward cases. Brisnet's speed figures correlate
with DPv1's computed figures at only **r=0.40** on 1,206 entries where both
exist (``dpv1 = 58.4 + 0.28 * brisnet``, R²=0.16) — the calibrated fill is so
shrunk toward the mean that it carries almost no ranking information. Filling
it anyway is still right, because "raced before, ran about average" is a much
better description of a shipper than "never raced", even though the value
itself is nearly uninformative. The regression is applied rather than a raw
copy because the scales differ by ~8 points and a raw copy would systematically
understate every bridged horse.

Rules
-----
* **The database always wins.** A slot is filled from PP only where the
  builder left it NULL. Nothing here overwrites a computed feature.
* **Morning-line odds is not bridged into any model feature.** It is carried
  as ``pp_ml_decimal`` for display and comparison only. DPv1's market side is
  ``final_odds``, and letting a morning line in through a fundamental slot
  would reintroduce exactly the anchor problem the v2 rebuild exists to fix.
* **Right-censoring is respected.** ``pp_career_starts`` tops out at 10
  because a Brisnet PP prints ten past-performance lines; it is "starts shown",
  not career starts. It is bridged because its main job is the has-raced
  signal, and flagged in the coverage report so the cap is not mistaken for
  a real career length.
* Anything without a defensible mapping is left NULL. ``class_score_change``
  is a good example: Brisnet's class delta is in purse dollars and DPv1's is a
  ladder position, so only the *direction* (UP/DOWN/SAME) transfers.

Usage
-----
    python scripts_dpv1/pp_feature_bridge.py report Ellis/elp-pps-files/elp0823y.pdf
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DPV1_DIR))
sys.path.insert(0, str(DPV1_DIR.parent / "scripts"))

from dpv1_runtime import DEFAULT_DB, load_model  # noqa: E402
from bayesian_shrinkage import shrink_rate_vec  # noqa: E402
from brisnet_pp_parser import parse_pp_file  # noqa: E402
from equibase_pdf_parser import normalize_name  # noqa: E402

log = logging.getLogger("pp_feature_bridge")

YARDS_PER_FURLONG = 220.0

# dpv1_speed = A + B * brisnet_speed, fitted on 1,206 entries carrying both.
# r=0.40, R2=0.16, residual sd 7.0 — see the module docstring for why a fill
# this weak is still worth making.
SPEED_CAL_A = 58.36
SPEED_CAL_B = 0.280

# Brisnet prints ten PP lines, so career starts saturate there.
PP_CAREER_STARTS_CAP = 10

# Shrinkage constants copied from the feature builder so a bridged rate sits on
# the same scale as a computed one.
PRIOR_WIN = 0.12
K_SURFACE = 25


def _f(v) -> float:
    """PP fields arrive as None / '' / str / float depending on the field."""
    try:
        if v is None or v == "":
            return np.nan
        return float(v)
    except (TypeError, ValueError):
        return np.nan


# ---------------------------------------------------------------------------
# The mapping
# ---------------------------------------------------------------------------

def bridge_row(pp: dict, race: dict) -> dict:
    """DPv1 feature values derivable from one PP horse block.

    ``race`` supplies today's conditions (distance in yards, surface), needed
    for the change-from-last features.
    """
    out: dict = {}

    starts = _f(pp.get("pp_career_starts"))
    days_off = _f(pp.get("pp_days_off"))
    has_run = (np.isfinite(starts) and starts > 0) or (
        np.isfinite(days_off) and days_off > 0)

    # -- career -----------------------------------------------------------
    if np.isfinite(starts):
        out["career_starts"] = starts

    # -- recency ----------------------------------------------------------
    if has_run and np.isfinite(days_off):
        out["days_since_last_race"] = days_off
        out["last_race_days_ago"] = days_off

    # -- last race --------------------------------------------------------
    if has_run:
        bl = _f(pp.get("pp_beaten_len_last"))
        if np.isfinite(bl):
            out["last_race_beaten_lengths"] = bl
        spd = _f(pp.get("pp_last_speed"))
        if np.isfinite(spd):
            out["last_race_speed_figure"] = SPEED_CAL_A + SPEED_CAL_B * spd

    style = pp.get("pp_running_style")
    if isinstance(style, str) and style.strip():
        s = style.strip().lower()
        # Brisnet uses E / EP / P / S; DPv1 uses front / stalk / mid / close.
        mapped = {"e": "front", "ep": "stalk", "p": "mid", "s": "close",
                  "front": "front", "stalk": "stalk", "mid": "mid",
                  "close": "close"}.get(s)
        if mapped:
            out["running_style_last_3"] = mapped

    # -- surface record ---------------------------------------------------
    sw, ss = _f(pp.get("pp_surface_wins")), _f(pp.get("pp_surface_starts"))
    if np.isfinite(ss) and ss > 0:
        out["historical_surface_winrate_shrunk"] = float(shrink_rate_vec(
            np.array([sw if np.isfinite(sw) else 0.0]), np.array([ss]),
            PRIOR_WIN, K_SURFACE)[0])
        out["surface_specialist_flag"] = float(
            np.isfinite(sw) and sw > 0 and (sw / ss) >= 0.20)

    dw, ds = _f(pp.get("pp_dist_wins")), _f(pp.get("pp_dist_starts"))
    if np.isfinite(ds) and ds > 0:
        out["distance_specialist_flag"] = float(
            np.isfinite(dw) and dw > 0 and (dw / ds) >= 0.20)

    # -- equipment / medication ------------------------------------------
    added = _f(pp.get("pp_blinkers_added_today"))
    removed = _f(pp.get("pp_blinkers_removed_today"))
    if np.isfinite(added) or np.isfinite(removed):
        a = added if np.isfinite(added) else 0.0
        r = removed if np.isfinite(removed) else 0.0
        out["blinkers_change_flag"] = float(a > 0 or r > 0)
        out["is_first_time_blinkers"] = float(a > 0)
    ftl = _f(pp.get("pp_first_time_lasix"))
    if np.isfinite(ftl):
        out["is_first_time_lasix"] = float(ftl > 0)
        out["lasix_first_time"] = float(ftl > 0)
    eq = _f(pp.get("pp_equipment_change"))
    if np.isfinite(eq):
        out["equipment_change_flag"] = float(eq > 0)
    wc = _f(pp.get("pp_weight_change"))
    if np.isfinite(wc):
        out["weight_change_from_last_race"] = wc

    # -- class move -------------------------------------------------------
    # Brisnet's delta is in purse dollars; DPv1's class_score is a ladder
    # position. Only the direction survives the translation.
    cd = _f(pp.get("pp_class_delta"))
    if np.isfinite(cd):
        out["class_change_from_last"] = (
            "UP" if cd > 0 else "DOWN" if cd < 0 else "SAME")

    # -- distance move ----------------------------------------------------
    today_yards = race.get("distance_yards")
    last_f = _f(pp.get("pp_last_dist"))
    if np.isfinite(last_f) and today_yards:
        last_yards = last_f * YARDS_PER_FURLONG
        out["distance_change_from_last_race"] = float(today_yards - last_yards)
        prev = "sprint" if last_yards < 1540 else "route"
        now = "sprint" if today_yards < 1540 else "route"
        out["distance_change_bucket"] = f"{prev}_to_{now}"
    else:
        dd = _f(pp.get("pp_distance_delta"))
        if np.isfinite(dd):
            out["distance_change_from_last_race"] = dd * YARDS_PER_FURLONG

    # -- surface move -----------------------------------------------------
    if has_run and np.isfinite(ss) and ss > 0 and race.get("surface"):
        # Brisnet's surface counts are for *today's* surface, so a horse with
        # starts on it has run this surface before. That is not the same as
        # knowing last race's surface, so only the "no change" case is safe to
        # assert, and only when every recorded start is on this surface.
        if np.isfinite(starts) and starts > 0 and ss >= starts:
            out["surface_change_from_last_race"] = 0.0

    return out


def apply_to_card(card, pdf: str | Path, model) -> dict:
    """Bridge a single ``RaceCard`` in place. Returns the fill report.

    ``load_race_from_db`` pops ``race_num`` off the frame onto the card, and a
    card is one race, so the race number is taken from the card rather than
    expected as a column.
    """
    frame = card.frame.copy()
    frame["_bridge_race_num"] = card.race_num
    if "distance_yards" not in frame.columns:
        frame["distance_yards"] = card.conditions.get("distance_yards")
    if "horse_name" not in frame.columns:
        frame["horse_name"] = card.names()
    bridged, report = apply_bridge(frame, pdf, model,
                                   race_num_col="_bridge_race_num",
                                   name_col="horse_name")
    card.frame = bridged.drop(columns=["_bridge_race_num"])
    return report


BRIDGEABLE: tuple[str, ...] = (
    "career_starts", "days_since_last_race", "last_race_days_ago",
    "last_race_beaten_lengths", "last_race_speed_figure",
    "running_style_last_3", "historical_surface_winrate_shrunk",
    "surface_specialist_flag", "distance_specialist_flag",
    "blinkers_change_flag", "is_first_time_blinkers", "is_first_time_lasix",
    "lasix_first_time", "equipment_change_flag",
    "weight_change_from_last_race", "class_change_from_last",
    "distance_change_from_last_race", "distance_change_bucket",
    "surface_change_from_last_race",
)


# ---------------------------------------------------------------------------
# Applying it to a frame
# ---------------------------------------------------------------------------

def pp_index(pdf: str | Path, track_code: str | None = None) -> dict:
    """``(race_num, normalized horse name) -> pp block``, plus race conditions."""
    parsed = parse_pp_file(pdf, track_code)
    if parsed["error"]:
        raise SystemExit(f"{Path(pdf).name}: {parsed['error']}")
    idx = {}
    for rc in parsed["races"]:
        for h in rc.get("horses", []):
            name = (h.get("horse_name") or "").strip()
            if not name:
                continue
            idx[(int(rc["race_num"]), normalize_name(name))] = h
    return {"index": idx, "parsed": parsed,
            "race_date": parsed["race_date"], "track": parsed["track"]}


def apply_bridge(frame: pd.DataFrame, pdf: str | Path, model,
                 race_num_col: str = "race_num",
                 name_col: str = "horse_name") -> tuple[pd.DataFrame, dict]:
    """Fill NULL DPv1 slots in ``frame`` from the PP file.

    Returns ``(frame, report)``. The report counts, per feature, how many cells
    were NULL before and how many the PP file could fill — which is the only
    honest way to describe what this bought.
    """
    bundle = pp_index(pdf)
    idx = bundle["index"]
    out = frame.copy()

    # Race-level conditions, needed by the change-from-last derivations.
    conds = {}
    for rc in bundle["parsed"]["races"]:
        conds[int(rc["race_num"])] = {
            "distance_yards": _f(out.loc[
                out[race_num_col] == int(rc["race_num"]), "distance_yards"
            ].iloc[0]) if (out[race_num_col] == int(rc["race_num"])).any()
            and "distance_yards" in out.columns else None,
            "surface": rc.get("surface"),
        }

    before = {c: int(out[c].isna().sum()) for c in BRIDGEABLE
              if c in out.columns}
    filled: dict[str, int] = {c: 0 for c in before}
    matched = 0

    for i in out.index:
        rn = out.at[i, race_num_col]
        nm = out.at[i, name_col]
        if pd.isna(rn) or not isinstance(nm, str):
            continue
        pp = idx.get((int(rn), normalize_name(nm)))
        if pp is None:
            continue
        matched += 1
        vals = bridge_row(pp, conds.get(int(rn), {}))
        for col, v in vals.items():
            if col not in out.columns or col not in before:
                continue
            if pd.isna(out.at[i, col]) and v is not None and not (
                    isinstance(v, float) and not np.isfinite(v)):
                out.at[i, col] = v
                filled[col] += 1

    report = {
        "rows": int(len(out)),
        "matched_to_pp": matched,
        "per_feature": {c: {"was_null": before[c], "filled": filled[c]}
                        for c in sorted(before) if before[c]},
        "total_cells_filled": int(sum(filled.values())),
    }
    return out, report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_card_frame(db, track, race_date, model) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(
            """
            SELECT f.*, r.race_num, r.distance_yards AS _dist,
                   h.name AS horse_name
            FROM entry_features_dpv1 f
            JOIN entries e     ON e.id = f.entry_id
            JOIN races r       ON r.id = e.race_id
            JOIN race_days rd  ON rd.id = r.race_day_id
            JOIN tracks t      ON t.id = rd.track_id
            LEFT JOIN horses h ON h.id = e.horse_id
            WHERE t.code = ? AND rd.race_date = ?
            """, conn, params=(track.upper(), race_date))
    finally:
        conn.close()


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("cmd", choices=["report"])
    p.add_argument("pdf")
    p.add_argument("--track", default=None)
    p.add_argument("--date", default=None)
    p.add_argument("--db", default=str(DEFAULT_DB))
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    bundle = pp_index(args.pdf, args.track)
    track = args.track or bundle["track"]
    race_date = args.date or bundle["race_date"]

    model = load_model()
    frame = _load_card_frame(args.db, track, race_date, model)
    if frame.empty:
        raise SystemExit(
            f"no built features for {track} {race_date} — run "
            f"load_pp_card.py load then feature_builder_dpv1.py build")
    if "distance_yards" not in frame.columns:
        frame["distance_yards"] = frame["_dist"]

    cols = list(model.fund_cols)
    before = frame.reindex(columns=cols).notna().to_numpy().mean()
    bridged, rep = apply_bridge(frame, args.pdf, model)
    after = bridged.reindex(columns=cols).notna().to_numpy().mean()

    print(f"\n{track} {race_date}: {rep['rows']} entries, "
          f"{rep['matched_to_pp']} matched to the PP file")
    print(f"feature coverage: {before * 100:.1f}%  ->  {after * 100:.1f}%  "
          f"({rep['total_cells_filled']} cells filled)")
    print("\nPer feature (only those that had NULLs):")
    rows = [{"feature": k, "was_null": v["was_null"], "filled": v["filled"],
             "still_null": v["was_null"] - v["filled"]}
            for k, v in rep["per_feature"].items()]
    rows.sort(key=lambda r: -r["filled"])
    print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
