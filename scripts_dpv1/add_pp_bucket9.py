"""Phase 5A: register the Brisnet PP features in ``dpv1_feature_config.json``.

Adds **Bucket 9 — "PP Data"**: the features that only a past-performance feed
can supply, each carrying its measured coverage from ``entry_pp_features``.

Design rules this script enforces
---------------------------------
* Every PP feature ships ``"active": false`` and ``"availability":
  "PP_AVAILABLE"``. They are candidates, not part of the trained model — the
  PP catalogue covers 220 of 28,105 races, so activating them in the main
  pipeline would null out 99% of the corpus. Phase 5B flips them on if and
  when the catalogue is large enough.
* ``pp_ml_decimal`` is bucket 9, not bucket 7 (Market Signals), and is marked
  ``"anchor": false``. This is deliberate. The v1 model made ``log_ml`` its
  largest coefficient — roughly 40% of the prediction — and that is the
  structural flaw the v2 rebuild exists to remove. The morning line is a
  bookmaker's opinion published before any money is bet; it belongs with the
  other PP-sourced opinions (Prime Power, Brisnet angles), not with the
  post-time tote signal the Benter blend treats as its market term.
* Features the config already listed as blocked on a PP feed get an
  ``unblocked_by`` pointer to the bucket-9 feature that now supplies them, so
  the blocked list stays honest rather than going stale.

Usage
-----
    python scripts_dpv1/add_pp_bucket9.py            # writes the config
    python scripts_dpv1/add_pp_bucket9.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from brisnet_pp_parser import PP_FEATURE_COLUMNS  # noqa: E402

DPV1_DIR = Path(__file__).resolve().parent
REPO = DPV1_DIR.parent
CONFIG = DPV1_DIR / "dpv1_feature_config.json"
DB = REPO / "scripts" / "racing_full.db"

BUCKET = 9
BUCKET_NAME = "PP Data"

# name -> (type, doug_rank, description). doug_rank is inherited from the
# nearest concept in Doug's ranking sheet where one exists, else null.
SPEC: dict[str, tuple[str, int | None, str]] = {
    "pp_ml_decimal": ("numeric", 3, "Brisnet morning-line odds as decimal (fraction + 1). A FEATURE, never an anchor — see module docstring."),
    "pp_prime_power": ("numeric", None, "Brisnet Prime Power composite rating."),
    "pp_prime_power_rank": ("numeric", None, "Rank of Prime Power within today's field (1 = highest)."),
    "pp_best_speed": ("numeric", 1, "Best Brisnet speed figure in the horse's PP lines."),
    "pp_best_speed_turf": ("numeric", 2, "Best Brisnet speed figure on turf."),
    "pp_best_speed_aw": ("numeric", 2, "Best Brisnet speed figure on all-weather."),
    "pp_last_speed": ("numeric", 1, "Brisnet speed figure in the most recent start."),
    "pp_avg_speed_last3": ("numeric", 1, "Mean Brisnet speed figure over the last three starts."),
    "pp_speed_improving": ("binary", 2, "Last three speed figures strictly increasing."),
    "pp_best_e1": ("numeric", 2, "Best Brisnet E1 (first-call) pace figure."),
    "pp_best_e2": ("numeric", 2, "Best Brisnet E2 (second-call) pace figure."),
    "pp_best_late": ("numeric", 2, "Best Brisnet late-pace figure."),
    "pp_speed_fig_slope": ("numeric", 2, "OLS slope of speed figures over recent starts — form trajectory."),
    "pp_beaten_lengths_slope": ("numeric", 2, "OLS slope of beaten lengths over recent starts."),
    "pp_class_drop_count": ("numeric", 1, "Count of class drops across the horse's PP lines."),
    "pp_figure_high_recent": ("binary", 2, "Most recent speed figure is the horse's career high."),
    "pp_races_in_60d": ("numeric", 2, "Starts in the 60 days before today."),
    "pp_workout_count_60d": ("numeric", 3, "Workouts in the last 60 days."),
    "pp_bullet_count_60d": ("numeric", 2, "Bullet (fastest-of-day) workouts in the last 60 days."),
    "pp_has_recent_bullet": ("binary", 2, "Any bullet workout in the last 60 days. Unblocks recent_bullet_workout."),
    "pp_days_since_last_workout": ("numeric", 3, "Days between the most recent workout and today."),
    "pp_workout_avg_pace": ("numeric", 3, "Mean workout pace (seconds per furlong)."),
    "pp_blinkers_added_today": ("binary", 2, "Blinkers on for the first time today."),
    "pp_blinkers_removed_today": ("binary", 2, "Blinkers off today."),
    "pp_first_time_lasix": ("binary", 1, "First-time Lasix today."),
    "pp_weight_change": ("numeric", 3, "Assigned weight minus last race's weight."),
    "pp_equipment_change": ("binary", 2, "Any equipment change flagged for today."),
    "pp_career_starts": ("numeric", 1, "Career starts per the PP header."),
    "pp_dist_starts": ("numeric", 2, "Career starts at today's distance."),
    "pp_dist_wins": ("numeric", 2, "Career wins at today's distance."),
    "pp_surface_starts": ("numeric", 2, "Career starts on today's surface."),
    "pp_surface_wins": ("numeric", 2, "Career wins on today's surface."),
    "pp_surface_winpct": ("numeric", 2, "Career win rate on today's surface."),
    "pp_combo_starts": ("numeric", 2, "Career starts at today's distance AND surface."),
    "pp_combo_wins": ("numeric", 2, "Career wins at today's distance AND surface."),
    "pp_jockey_change": ("binary", 2, "Today's jockey differs from the last start's."),
    "pp_jockey_first_time": ("binary", 2, "Today's jockey has never ridden this horse in its PP lines."),
    "pp_jt_winpct": ("numeric", 2, "Jockey/trainer combo win rate, last 60 days."),
    "pp_hot_jt_combo": ("binary", 2, "Brisnet 'hot J/T combo' angle present."),
    "pp_jt_zero": ("binary", 3, "Jockey/trainer combo win rate is 0%."),
    "pp_trainer_angle_winpct": ("numeric", 2, "Brisnet trainer-angle win rate for the angle matching today's conditions."),
    "pp_trainer_angle_starts": ("numeric", 2, "Sample size behind pp_trainer_angle_winpct."),
    "pp_has_strong_trainer_angle": ("binary", 2, "A trainer angle matching today clears Brisnet's strong threshold."),
    "pp_positive_trainer_angles": ("numeric", 2, "Count of positive trainer angles applying today."),
    "pp_jky_angle_winpct": ("numeric", 2, "Brisnet jockey-angle win rate for the angle matching today's conditions."),
    "pp_jky_angle_starts": ("numeric", 2, "Sample size behind pp_jky_angle_winpct."),
    "pp_has_strong_jky_angle": ("binary", 2, "A jockey angle matching today clears Brisnet's strong threshold."),
    "pp_positive_jky_angles": ("numeric", 2, "Count of positive jockey angles applying today."),
    "pp_days_off": ("numeric", 1, "Days since the last start, from the PP race lines."),
    "pp_beaten_len_last": ("numeric", 2, "Beaten lengths in the most recent start."),
    "pp_last_class": ("numeric", 1, "Class money of the last start."),
    "pp_last_dist": ("numeric", 2, "Distance of the last start, in furlongs."),
    "pp_class_delta": ("numeric", 1, "Today's class money minus the last start's."),
    "pp_distance_delta": ("numeric", 2, "Today's distance minus the last start's, in furlongs."),
    "pp_running_style": ("categorical", 2, "Brisnet running style (E / E/P / P / S)."),
    "pp_pos_angle_count": ("numeric", 3, "Count of positive Brisnet QuickPlay angles."),
    "pp_neg_angle_count": ("numeric", 3, "Count of negative Brisnet QuickPlay angles."),
}

# Existing config entries this feed unblocks.
UNBLOCKS = {
    "recent_bullet_workout": "pp_has_recent_bullet",
    "days_since_last_workout": "pp_days_since_last_workout",
    "workout_frequency_30d": "pp_workout_count_60d",
    "morning_line_odds": "pp_ml_decimal",
}

# Coverage below this is reported but the feature stays a candidate; see the
# Phase 5A report for the per-feature diagnosis.
LOW_COVERAGE = 50.0


def measure_coverage() -> tuple[dict[str, float], int]:
    conn = sqlite3.connect(DB)
    cur = conn.execute(
        f"SELECT COUNT(*) FROM entry_pp_features")
    n = cur.fetchone()[0]
    if n == 0:
        return {}, 0
    sel = ", ".join(
        f'SUM(CASE WHEN "{c}" IS NOT NULL THEN 1 ELSE 0 END)'
        for c in PP_FEATURE_COLUMNS)
    row = conn.execute(f"SELECT {sel} FROM entry_pp_features").fetchone()
    conn.close()
    return {c: round(v / n * 100, 1)
            for c, v in zip(PP_FEATURE_COLUMNS, row)}, n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cov, n_entries = measure_coverage()

    missing = [c for c in PP_FEATURE_COLUMNS if c not in SPEC]
    if missing:
        raise SystemExit(f"SPEC is missing: {missing}")

    added = 0
    for name in PP_FEATURE_COLUMNS:
        ftype, rank, desc = SPEC[name]
        entry = {
            "active": False,
            "bucket": BUCKET,
            "bucket_name": BUCKET_NAME,
            "type": ftype,
            "description": desc,
            "doug_rank": rank,
            "doug_notes": None,
            "phase3c_status": "NOT_IN_CATALOG",
            "v2_active": "NO",
            "implemented": True,
            "source": "brisnet_pp",
            "availability": "PP_AVAILABLE",
            "pp_coverage_pct": cov.get(name),
            "activation_blocked_reason": (
                "PP catalogue covers 220 of 28,105 races (Phase 5A). Activate "
                "in the main pipeline only when PP coverage is broad enough "
                "that the column is not null for most of the corpus."),
        }
        if name == "pp_ml_decimal":
            entry["anchor"] = False
            entry["anchor_note"] = (
                "Morning line is a FEATURE. The v1 model used log_ml as its "
                "largest coefficient (~40% of the prediction); that anchor "
                "architecture is not ported. Kept out of bucket 7 so it is "
                "never mistaken for the post-time market term in the blend.")
        if cov.get(name) is not None and cov[name] < LOW_COVERAGE:
            entry["low_coverage_flag"] = True
        cfg["features"][name] = entry
        added += 1

    for blocked, supplier in UNBLOCKS.items():
        spec = cfg["features"].get(blocked)
        if spec:
            spec["unblocked_by"] = supplier
            spec["unblocked_phase"] = "5A"

    cfg["version"] = "dpv1.3.0"
    cfg["generated"] = "2026-08-03"
    cfg["generated_by"] = (cfg["generated_by"]
                           + " + scripts_dpv1/add_pp_bucket9.py")
    cfg["notes"].extend([
        "Phase 5A adds bucket 9 ('PP Data') from the Brisnet PP feed.",
        "Every bucket-9 feature is active=false / availability=PP_AVAILABLE:",
        "  they are candidates for Phase 5B, not part of the trained DPv1.",
        "pp_ml_decimal is bucket 9, not bucket 7, and anchor=false. The v1",
        "  model's log_ml anchor (~40% of the prediction) is NOT ported.",
    ])
    cfg["counts"]["pp_features_bucket9"] = added
    cfg["counts"]["pp_matched_entries"] = n_entries
    cfg["counts"]["pp_low_coverage"] = sorted(
        c for c in PP_FEATURE_COLUMNS
        if cov.get(c) is not None and cov[c] < LOW_COVERAGE)

    print(f"bucket 9: {added} features, measured on {n_entries} matched entries")
    print(f"low coverage (<{LOW_COVERAGE:.0f}%): "
          f"{cfg['counts']['pp_low_coverage']}")
    print(f"unblocked existing features: {list(UNBLOCKS)}")
    if args.dry_run:
        print("(dry run — config not written)")
        return 0
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(f"wrote {CONFIG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
