"""Preprocess ``entry_features_dpv1`` for DPv1 training (ITM, multi-track).

Differences from ``scripts_v2a/prepare_training_v2a.py``
--------------------------------------------------------
* **Three tracks.** GP + CT + MNR from ``racing_full.db``, with ``track_code``
  carried through so every metric can be sliced per track — the core question
  of Phase 4C.
* **Doug's feature set.** 108 active features from ``dpv1_feature_config.json``
  rather than the Phase 3C defaults.
* **Wider categorical list.** DPv1 adds ten categoricals the v2 preprocessor
  never saw (class_change_from_last, distance_change_bucket, the pace/bias
  shapes, the home-track columns, track_code).
* **Its own leak list** — see below. This is the significant change.

The horses.* missingness leak, re-measured on the 3-track corpus
---------------------------------------------------------------
Phase 3E excluded four "horse immutable" features because the Phase 3A loader
fills ``horses.sex / foaled_date / sire_id / dam_id`` **only when a horse first
appears as a race winner**. Presence-vs-absence of those fields is therefore
derived from future results. Phase 3E's note said the leak should become
negligible once the corpus expanded to multiple tracks.

It did not. Measured on ``entry_features_dpv1`` (207,976 entries, all three
tracks), where "ever won" means the horse wins at least once anywhere in the
corpus:

    feature                          P(ever won | known)   P(ever won | null)
    horse_sex                              100.00%               0.00%
    sire_at_distance_winrate_shrunk        100.00%               3.46%
    sire_at_surface_winrate_shrunk         100.00%               4.02%
    sire_dirt_win_pct                      100.00%              44.63%
    sire_sprint_win_pct                    100.00%              52.21%
    sire_route_win_pct                     100.00%              56.71%

``horse_sex`` is a *perfect* predictor of whether the horse ever wins, on all
three tracks independently. ITM rate is 46.9% where it is known and 22.6%
where it is null. The ``Preprocessor`` emits a ``{col}__missing`` flag for
every nullable column, so these features leak through the flag even when the
value itself is sound.

So DPv1 excludes eight features: ``horse_sex``, ``is_florida_bred`` (whose
``1`` value likewise implies a known foaling place, hence a winner), and the
six ``sire_*`` progeny rates. Doug ranked all eight a 2; they are not
recoverable until the loader is changed to populate pedigree for every horse
rather than only for winners.

**Not** excluded: features that are null for *first-time starters*
(``career_*``, ``last_race_*``, the specialist flags, ``gate_break_avg_last_3``).
Their missingness also correlates with "ever won" — a horse with no prior
starts has had fewer chances to win — but "this horse has no past performances"
is knowable at post time and is exactly the kind of thing a handicapper
conditions on. The test is the mechanism, not the correlation.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
REPO = DPV1_DIR.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts_v2a"))

from prepare_training import Preprocessor, time_decay_weights  # noqa: E402,F401

log = logging.getLogger("prepare_training_dpv1")

DEFAULT_DB = REPO / "scripts" / "racing_full.db"
DEFAULT_CONFIG = DPV1_DIR / "dpv1_feature_config.json"
TRAIN_DATE_MIN = "2022-01-01"   # HISA era, Doug's scope decision

# Phase 4C-5A trained on these three. Phase 6C tests adding ELP.
TRACKS_3 = ("GP", "CT", "MNR")
TRACKS_4 = ("GP", "CT", "MNR", "ELP")

# Market-side features — held out of the fundamental model so the blend is a
# genuine two-source combination rather than the market predicting itself.
DPV1_MARKET_FEATURES: tuple[str, ...] = (
    "final_odds",
    "log_final_odds",
    "implied_probability",
    "is_favorite",
    "market_probability_normalized",
    "odds_rank_in_field",
    "odds_ratio_to_favorite",
)

# Future-derived missingness — see module docstring.
DPV1_LEAKY_FEATURES: tuple[str, ...] = (
    "horse_sex",
    "is_florida_bred",
    "sire_at_distance_winrate_shrunk",
    "sire_at_surface_winrate_shrunk",
    "sire_dirt_win_pct",
    "sire_first_time_starter_win_pct",
    "sire_route_win_pct",
    "sire_sprint_win_pct",
)

DPV1_CATEGORICAL_FEATURES: tuple[str, ...] = (
    "surface", "track_condition", "race_type", "pace_type_last_race",
    "class_change_from_last", "distance_change_bucket", "track_code",
    "trainer_home_track", "jockey_home_track", "running_style_last_3",
    "early_pace_position_projected", "pace_pressure_in_race",
    "expected_pace_shape", "track_bias_running_style",
)

NON_FEATURE_COLS: tuple[str, ...] = (
    "entry_id", "race_id", "horse_id", "trainer_id", "jockey_id",
    "track_id", "race_date", "finish_pos", "y_true", "track", "program_num",
    "field_size_actual",
)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_full_frame(db_path: str | Path = DEFAULT_DB,
                    date_min: str = TRAIN_DATE_MIN,
                    tracks: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Entry-grain DPv1 frame with the ITM label, 2022+.

    ``tracks`` restricts the corpus (``None`` = every track in the DB). Phase 4C
    ran on the three tracks that were loaded at the time; Phase 6C added ELP, so
    the track list is now explicit rather than implied by what happens to be in
    ``racing_full.db``.

    Unrun races are dropped — see ``drop_unrun_races``.
    """
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query(
        """
        -- f.* already carries race_date (written by feature_builder_dpv1),
        -- so we must not select rd.race_date again.
        SELECT f.*, e.finish_pos, e.program_num, t.code AS track
        FROM entry_features_dpv1 f
        JOIN entries e    ON e.id = f.entry_id
        JOIN races r      ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        JOIN tracks t     ON t.id = rd.track_id
        WHERE rd.race_date >= ?
        """,
        conn, params=(date_min,),
    )
    conn.close()
    if tracks is not None:
        df = df[df["track"].isin(tracks)]
    df["race_date"] = pd.to_datetime(df["race_date"])
    df = drop_unrun_races(df)
    df["y_true"] = (df["finish_pos"] <= 3).astype(int)
    df = df.sort_values(["race_date", "race_id", "entry_id"]).reset_index(drop=True)
    return df


def drop_unrun_races(df: pd.DataFrame) -> pd.DataFrame:
    """Remove races that have not been run yet.

    ``y_true = (finish_pos <= 3)`` evaluates NaN to False, so a race loaded
    ahead of time is silently labelled *every horse missed the board*. Phase 6A's
    prediction runner loads upcoming cards into the same ``entries`` table the
    trainer reads, so as of Phase 6C ``racing_full.db`` carries the ELP cards for
    2026-08-22 and 2026-08-23 — 18 races, 206 entries, all fabricated negatives,
    and all inside the 2026 validation fold.

    The test is *zero* recorded finishers in the race, not a null ``finish_pos``
    on the entry. A scratch is a null finish in a race that did run; those have
    always been carried (0.6% of the 3-track corpus) and are left alone here so
    the Phase 6C before/after comparison isolates one change.
    """
    finishers = df.groupby("race_id")["finish_pos"].transform("count")
    unrun = finishers == 0
    if unrun.any():
        log.info("dropping %d entries in %d unrun races: %s",
                 int(unrun.sum()), df.loc[unrun, "race_id"].nunique(),
                 sorted(df.loc[unrun, "race_date"].dt.date.unique().tolist()))
    return df[~unrun]


def split_feature_columns(all_columns) -> tuple[list[str], list[str]]:
    """Return ``(fundamental_cols, market_cols)`` for DPv1.

    Excludes identifiers, the label, the market block, and the eight
    future-derived features documented at the top of this module.
    """
    cols = set(all_columns)
    market = [c for c in DPV1_MARKET_FEATURES if c in cols]
    exclusions = (set(NON_FEATURE_COLS) | set(DPV1_MARKET_FEATURES)
                  | set(DPV1_LEAKY_FEATURES))
    fundamental = sorted(c for c in cols if c not in exclusions)
    return fundamental, market


def make_preprocessor() -> Preprocessor:
    """Preprocessor with DPv1's categorical list patched in.

    ``Preprocessor`` reads the module-level ``CATEGORICAL_FEATURES`` from
    ``scripts/prepare_training``; DPv1 has ten categoricals that module has
    never seen. Rather than modify ``scripts/`` (Phase 4B design rule), we
    swap the module constant for the lifetime of the fit.
    """
    import prepare_training as pt
    pt.CATEGORICAL_FEATURES = DPV1_CATEGORICAL_FEATURES
    return Preprocessor()


# ---------------------------------------------------------------------------
# Doug's interaction term
# ---------------------------------------------------------------------------

def add_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
    """Doug's rank-1 insight as an explicit feature.

    Phase 4B measured it on raw marginals: a horse that won last out and
    steps UP in class goes 42.4% ITM, versus 55.1% staying at the same level —
    a 12.7pp penalty, and within a point of a horse that did NOT win last out
    and stays level. Doug predicted exactly this in his note on
    ``last_race_won``:

        "winning multiple races in a row is difficult, unless the horse really
         is that good, and especially if/as it moves up in class"

    A linear model cannot represent that interaction from the two main effects
    alone, so Phase 4C tests it as an explicit term.
    """
    out = df.copy()
    won = out["last_race_won"].fillna(0).astype(float) == 1.0
    known = out["last_race_won"].notna() & out["class_change_from_last"].notna()
    up = out["class_change_from_last"] == "UP"
    down = out["class_change_from_last"] == "DOWN"
    out["won_last_class_up_flag"] = np.where(known, (won & up).astype(float), np.nan)
    out["won_last_class_down_flag"] = np.where(known, (won & down).astype(float), np.nan)
    return out


INTERACTION_FEATURES = ("won_last_class_up_flag", "won_last_class_down_flag")


# ---------------------------------------------------------------------------
# Rolling-origin CV by year
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class YearFoldSplitter:
    """Train on everything before year Y, validate on year Y.

    Phase 4C validates on 2023, 2024, 2025 and 2026. 2022 is training-only
    because it is the first year in scope and has nothing before it. Fold 1
    therefore trains on a single year — its numbers are the weakest of the
    four and are reported per fold rather than hidden in the mean.
    """

    val_years: tuple[int, ...] = (2023, 2024, 2025, 2026)

    def split(self, df: pd.DataFrame):
        years = df["race_date"].dt.year
        for y in self.val_years:
            tr = np.flatnonzero((years < y).to_numpy())
            vl = np.flatnonzero((years == y).to_numpy())
            if len(tr) == 0 or len(vl) == 0:
                continue
            yield f"fold_val{y}", tr, vl


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rank_of(cfg: dict, feature: str) -> int | None:
    spec = cfg["features"].get(feature)
    return spec.get("doug_rank") if spec else None


def rank1_features(cfg: dict, available: list[str]) -> list[str]:
    """Doug's rank-1 features, for the subset baseline in the metrics suite."""
    return [c for c in available if rank_of(cfg, c) == 1]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    df = load_full_frame()
    df = add_interaction_features(df)
    fund, market = split_feature_columns(df.columns)
    log.info("rows=%d races=%d  ITM rate=%.4f",
             len(df), df["race_id"].nunique(), df["y_true"].mean())
    log.info("by track: %s", df["track"].value_counts().to_dict())
    log.info("fundamental features: %d", len(fund))
    log.info("market features: %d  %s", len(market), market)
    log.info("excluded as leaky: %s", list(DPV1_LEAKY_FEATURES))
    for name, tr, vl in YearFoldSplitter().split(df):
        log.info("  %s: train=%d val=%d", name, len(tr), len(vl))
    pre = make_preprocessor().fit(df, fund)
    log.info("design matrix: %s", pre.transform(df).shape)
