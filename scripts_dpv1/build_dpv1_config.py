"""Generate ``dpv1_feature_config.json`` from Doug's ranking spreadsheet.

The config is *derived*, not hand-maintained: re-run this whenever Doug
updates ``DPv1_Feature_Ranking.xlsx`` and the activation set follows his
ranks automatically.

Activation policy (Phase 4B)
---------------------------
    Rank 1-2  -> active, provided the DPv1 builder can actually compute it
    Rank 3    -> implemented where cheap, but ``active: false``
    Rank 4-5  -> skipped entirely; not computed, not written
    unranked  -> inherits from a ranked companion feature, flagged

A Rank 1-2 feature that the corpus cannot support is NOT silently dropped —
it is written with ``active: false`` and an explicit ``blocked_reason`` so
the gap is visible in the config itself and in the Phase 4B report.

Usage
-----
    python scripts_dpv1/build_dpv1_config.py
"""
from __future__ import annotations

import collections
import json
from datetime import date
from pathlib import Path

import openpyxl

DPV1_DIR = Path(__file__).resolve().parent
REPO_ROOT = DPV1_DIR.parent
XLSX = REPO_ROOT / "DPv1_Feature_Ranking.xlsx"
OUT = DPV1_DIR / "dpv1_feature_config.json"

CONFIG_VERSION = "dpv1.2.0"   # Phase 4D: pedigree bucket marked unavailable
SHEET = "Doug Parks v1 Feature Ranking"


# ---------------------------------------------------------------------------
# What the DPv1 builder can and cannot compute from the Equibase result-chart
# corpus. Anything not listed as blocked/deferred and carrying rank 1-2 is
# expected to be produced by feature_builder_dpv1.py.
# ---------------------------------------------------------------------------

# No source data anywhere in the corpus. Equibase result charts do not carry
# workouts, morning lines, or track-maintenance logs.
BLOCKED: dict[str, str] = {
    "days_since_last_workout":
        "No workout data in Equibase result charts. Needs Brisnet/DRF PP feed.",
    "recent_bullet_workout":
        "No workout data in Equibase result charts. Needs Brisnet/DRF PP feed. "
        "Doug ranked this 2 — highest-value gap that a PP feed would close.",
    "workout_frequency_30d":
        "No workout data in Equibase result charts. Needs Brisnet/DRF PP feed.",
    "trainer_workout_pattern":
        "No workout data in Equibase result charts. Needs Brisnet/DRF PP feed.",
    "morning_line_odds":
        "Result charts carry final tote odds only, never the morning line.",
    "odds_drop_from_morning_line":
        "Requires morning_line_odds, which the result charts do not carry.",
    "track_maintenance_change":
        "No track-maintenance log in the corpus.",
    "weather_last_3_days":
        "Only per-race weather is charted; no multi-day weather series.",
}

# Buildable, but deliberately out of Phase 4B scope. The v10 workbook signals
# are Phase 4D per the DPv1 plan ("No v10 signal re-integration yet").
DEFERRED: dict[str, str] = {
    "pedigree_index":
        "Composite from Doug's v10 workbook — Phase 4D v10 re-integration.",
    "sire_dirt_index_v10":
        "v10 workbook signal — Phase 4D v10 re-integration.",
    "sire_turf_index_v10":
        "v10 workbook signal — Phase 4D v10 re-integration.",
    "sire_wet_index_v10":
        "v10 workbook signal — Phase 4D v10 re-integration.",
    "sire_first_time_turf_flag":
        "Doug-curated sire list in the v10 workbook — Phase 4D.",
}

# ---------------------------------------------------------------------------
# PERMANENTLY UNAVAILABLE in a results-only data regime (Phase 4D decision)
# ---------------------------------------------------------------------------
# Equibase result charts publish breeding on exactly one line per race — the
# `Winner:` line. So horses.sex / foaled_date / sire_id / dam_id exist for
# precisely the horses that win at least once, and for nobody else:
#
#     horses with pedigree           13,636
#     horses that ever won a race    13,636
#     pedigree but never won              0
#
# Applied globally, "has pedigree" therefore means "will win at some point" —
# future information (Phase 4C measured P(ever won | horse_sex known) = 100%,
# P(ever won | null) = 0%, on all three tracks independently).
#
# This is a DATA SOURCE limitation, not a parser or loader bug: a 9-runner
# chart contains one sex token, and the per-entry parser output carries no
# breeding fields at all. There is nothing to fix at the loader level.
#
# Backfilling from a horse's own winning appearances was considered and
# REJECTED (Doug, Phase 4D): gating pedigree to "the horse had already won
# before today" removes the future component, but what remains is so close to
# a restatement of `career_wins` that it adds no information while keeping
# leak risk. These features are marked unavailable rather than reconstructed.
#
# Unblocking requires a different source (Brisnet/DRF past-performance feed),
# which carries breeding for every starter.
PEDIGREE_UNAVAILABLE_REASON = (
    "Results-only data regime: Equibase charts publish breeding solely on the "
    "`Winner:` line, so pedigree exists only for horses that win. Using it is "
    "future information; backfilling from own wins was rejected as adding "
    "nothing beyond career_wins. Needs a PP feed (Brisnet/DRF)."
)

# Bucket 2 features sourced from the winner-only pedigree block.
_PEDIGREE_BUCKET2 = {
    "horse_sex", "horse_age", "horse_country_origin", "is_florida_bred",
    "horse_color", "days_since_foaled",
}

# Bucket 5 is entirely sire/dam-derived EXCEPT these two, which Doug's catalog
# files under pedigree but which are actually read off entries.equipment.
_BUCKET5_NOT_PEDIGREE = {"is_first_time_blinkers", "is_first_time_lasix"}

# Rank-3 features the builder implements anyway, so flipping "active" to true
# later needs no code change. (Rank-3 features NOT listed here are catalogued
# but have no implementation yet.)
RANK3_IMPLEMENTED = {
    "day_of_week", "is_stakes", "log_purse", "month_of_year", "purse",
    "horse_age", "horse_country_origin",
    "career_avg_speed_figure", "last_race_beaten_favorite",
    "is_first_time_combo", "jockey_dirt_win_pct", "jockey_turf_win_pct",
    "jockey_won_last_race", "new_jockey_flag", "trainer_won_last_race",
    "trainer_jockey_combo_starts", "trainer_jockey_combo_winrate_shrunk",
    "trainer_jockey_bond_strength",
    "broodmare_sire_dirt_win_pct", "broodmare_sire_turf_win_pct",
    "damsire_at_surface_winrate", "sire_id", "sire_off_track_win_pct",
    "sire_overall_win_pct", "sire_turf_win_pct",
    "is_inside_post", "is_outside_post", "post_rank_in_field",
    "post_position_win_pct_at_track", "start_pos_last_race",
    "weight_vs_field_avg",
    "odds_rank_in_field", "odds_ratio_to_favorite",
    "rail_setting_feet", "time_of_year_bias", "track_speed_yield_90d",
    "track_variant_today",
}

# Doug left starts_at_track unranked. It is the denominator companion of
# wins_at_track (rank 1) and is meaningless without it, so it inherits rank 1.
RANK_INHERITED = {"starts_at_track": ("wins_at_track", 1)}

# Same concept charted under two names in Doug's catalog. We compute one
# column and alias the other so both names stay resolvable.
ALIASES = {"lasix_first_time": "is_first_time_lasix"}

# Cross-track features the 3-track corpus makes possible for the first time.
# Not in Doug's 154 — added by Phase 4B and flagged as such.
DPV1_ADDITIONS: dict[str, dict] = {
    "trainer_at_other_tracks_winrate": dict(
        bucket=8, type="numeric",
        description="Trainer's shrunk win rate at tracks OTHER than today's, "
                    "prior races only. Separates a barn that wins everywhere "
                    "from one that only wins at home.",
    ),
    "trainer_at_other_tracks_starts": dict(
        bucket=8, type="numeric",
        description="Sample size behind trainer_at_other_tracks_winrate.",
    ),
    "jockey_at_other_tracks_winrate": dict(
        bucket=8, type="numeric",
        description="Jockey's shrunk win rate at tracks OTHER than today's, "
                    "prior races only.",
    ),
    "jockey_at_other_tracks_starts": dict(
        bucket=8, type="numeric",
        description="Sample size behind jockey_at_other_tracks_winrate.",
    ),
    "horse_shipping_success_rate": dict(
        bucket=8, type="numeric",
        description="Horse's shrunk ITM rate on prior starts that were a SHIP "
                    "(track differed from its own previous start). NULL for "
                    "horses that have never shipped.",
    ),
    "horse_shipping_starts": dict(
        bucket=8, type="numeric",
        description="Number of prior shipping starts — sample size behind "
                    "horse_shipping_success_rate.",
    ),
    "is_shipping_today": dict(
        bucket=8, type="boolean",
        description="Today's track differs from the horse's last-start track. "
                    "NULL for first-time starters.",
    ),
    "trainer_home_track": dict(
        bucket=8, type="categorical",
        description="Track the trainer has started the most horses at, prior "
                    "races only. NULL until the trainer has a prior start.",
    ),
    "is_at_trainer_home_track": dict(
        bucket=8, type="boolean",
        description="Today's track == trainer_home_track. The modelling-ready "
                    "form of trainer_home_track.",
    ),
    "jockey_home_track": dict(
        bucket=8, type="categorical",
        description="Track the jockey has ridden the most at, prior races only.",
    ),
    "is_at_jockey_home_track": dict(
        bucket=8, type="boolean",
        description="Today's track == jockey_home_track.",
    ),
    "class_score": dict(
        bucket=3, type="numeric",
        description="Derived class ladder position (tier*10 + within-tier "
                    "offset). races.class_level is NULL corpus-wide, so this "
                    "is the substrate class_change_from_last is computed from.",
    ),
    "class_score_change_from_last": dict(
        bucket=3, type="numeric",
        description="Signed magnitude of the class move. Doug: 'A significant "
                    "change in class, up or down, is a big factor' — the "
                    "categorical alone loses the magnitude.",
    ),
    "track_code": dict(
        bucket=1, type="categorical",
        description="GP / CT / MNR. Grouping key for per-track validation and "
                    "for track fixed effects in Phase 4C.",
    ),
}


def load_catalog() -> list[dict]:
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    ws = wb[SHEET]
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[3]
    recs = [dict(zip(hdr, r)) for r in rows[4:] if r[2] is not None]
    return recs


def build_config() -> dict:
    recs = load_catalog()
    seen: dict[str, dict] = {}
    duplicates: list[str] = []

    for r in recs:
        name = str(r["Feature Name"]).strip()
        rank = r["Doug's Rank (1-5)"]
        rank = int(rank) if rank is not None else None
        if name in seen:
            # Doug's catalog lists is_first_time_lasix twice. Keep the
            # stronger (lower) rank and remember that it was duplicated.
            duplicates.append(name)
            prev = seen[name]["doug_rank"]
            if rank is not None and (prev is None or rank < prev):
                seen[name]["doug_rank"] = rank
            continue

        inherited = RANK_INHERITED.get(name)
        entry = {
            "active": False,
            "bucket": int(r["Bucket"]),
            "bucket_name": r["Bucket Name"],
            "type": r["Type"],
            "description": r["Description"],
            "doug_rank": rank if inherited is None else inherited[1],
            "doug_notes": r["Doug's Notes"],
            "phase3c_status": r["Status"],
            "v2_active": r["v2 Active"],
            "implemented": False,
        }
        if inherited is not None:
            entry["rank_inherited_from"] = inherited[0]
            entry["rank_inherited_note"] = (
                "Doug left this unranked; it is the denominator companion of "
                f"{inherited[0]} (rank {inherited[1]}) and inherits its rank."
            )
        if name in ALIASES:
            entry["alias_of"] = ALIASES[name]
        seen[name] = entry

    # Resolve activation.
    for name, e in seen.items():
        rank = e["doug_rank"]
        is_pedigree = (name in _PEDIGREE_BUCKET2
                       or (e["bucket"] == 5 and name not in _BUCKET5_NOT_PEDIGREE))
        if is_pedigree:
            e["implemented"] = False
            e["active"] = False
            e["unavailable_reason"] = PEDIGREE_UNAVAILABLE_REASON
            e["unavailable_permanent"] = True
            continue
        if name in BLOCKED:
            e["implemented"] = False
            e["active"] = False
            e["blocked_reason"] = BLOCKED[name]
        elif name in DEFERRED:
            e["implemented"] = False
            e["active"] = False
            e["deferred_reason"] = DEFERRED[name]
        elif rank in (1, 2):
            e["implemented"] = True
            e["active"] = True
        elif rank == 3:
            e["implemented"] = name in RANK3_IMPLEMENTED
            e["active"] = False
            e["inactive_reason"] = (
                "Rank 3 — built but held inactive; flip 'active' to include."
                if e["implemented"] else
                "Rank 3 — catalogued only; no DPv1 implementation yet."
            )
        else:
            e["implemented"] = False
            e["active"] = False
            e["skipped_reason"] = f"Rank {rank} — skipped per Doug's ranking."

    # DPv1 cross-track additions.
    for name, spec in DPV1_ADDITIONS.items():
        seen[name] = {
            "active": True,
            "bucket": spec["bucket"],
            "bucket_name": {1: "Race-Level Context", 3: "Recent Form",
                            8: "Track-Specific Dynamics"}[spec["bucket"]],
            "type": spec["type"],
            "description": spec["description"],
            "doug_rank": None,
            "doug_notes": None,
            "phase3c_status": "DPV1_NEW",
            "v2_active": "N/A",
            "implemented": True,
            "dpv1_addition": True,
        }

    features = dict(sorted(seen.items(), key=lambda kv: (kv[1]["bucket"], kv[0])))
    ranks = collections.Counter(
        e["doug_rank"] for e in features.values() if not e.get("dpv1_addition")
    )
    n_active = sum(1 for e in features.values() if e["active"])

    return {
        "version": CONFIG_VERSION,
        "generated": date.today().isoformat(),
        "generated_by": "scripts_dpv1/build_dpv1_config.py",
        "source_ranking": "DPv1_Feature_Ranking.xlsx",
        "target": "ITM",
        "tracks": ["GP", "CT", "MNR"],
        "notes": [
            "Activation is driven by Doug's ranks, NOT by the Phase 3C defaults.",
            "Rank 1-2 -> active. Rank 3 -> built where cheap but inactive.",
            "Rank 4-5 -> skipped entirely.",
            "A rank 1-2 feature the corpus cannot support carries an explicit",
            "  'blocked_reason' (no source data) or 'deferred_reason' (later phase)",
            "  rather than being dropped silently.",
            "Features with 'dpv1_addition': true are cross-track features added",
            "  in Phase 4B; they are not part of Doug's original 154.",
            "Doug's handicapping notes are preserved verbatim in 'doug_notes'.",
        ],
        "activation_policy": {
            "rank_1": "active",
            "rank_2": "active",
            "rank_3": "implemented where cheap, active=false",
            "rank_4": "skipped",
            "rank_5": "skipped",
            "unranked": "inherits rank from a companion feature (flagged)",
        },
        "counts": {
            "catalog_features": len(recs),
            "unique_catalog_features": len(recs) - len(duplicates),
            "duplicate_names_in_catalog": duplicates,
            "by_doug_rank": {str(k): v for k, v in sorted(
                ranks.items(), key=lambda kv: (kv[0] is None, kv[0]))},
            "dpv1_additions": len(DPV1_ADDITIONS),
            "active_total": n_active,
            "blocked_rank_1_2": sorted(
                n for n, e in features.items()
                if e.get("blocked_reason") and e["doug_rank"] in (1, 2)),
            "deferred_rank_1_2": sorted(
                n for n, e in features.items()
                if e.get("deferred_reason") and e["doug_rank"] in (1, 2)),
            "permanently_unavailable": sorted(
                n for n, e in features.items()
                if e.get("unavailable_permanent")),
            "permanently_unavailable_rank_1_2": sorted(
                n for n, e in features.items()
                if e.get("unavailable_permanent") and e["doug_rank"] in (1, 2)),
        },
        "defaults": {
            "shrinkage_prior_win_rate": 0.12,
            "shrinkage_prior_itm_rate": 0.35,
            "shrinkage_k_defaults": {
                "trainer_overall": 20,
                "trainer_at_track": 30,
                "trainer_at_surface": 25,
                "trainer_at_distance": 30,
                "trainer_at_other_tracks": 30,
                "trainer_context": 25,
                "trainer_jockey_combo": 25,
                "jockey_overall": 20,
                "jockey_at_track": 30,
                "jockey_at_surface": 25,
                "jockey_at_distance": 30,
                "jockey_at_other_tracks": 30,
                "horse_career": 15,
                "horse_shipping": 8,
                "sire_progeny": 40,
                "damsire_progeny": 40,
                "post_at_track": 40,
                "speed_par_time": 50,
            },
            "half_life_days": {
                "training_loss": 730,
                "aggregate_stats": 730,
            },
            "cross_track_priors": True,
            "class_ladder": {
                "source": "derived — races.class_level is NULL corpus-wide",
                "score": "tier * 10 + within-tier offset (0-9)",
                "claiming_offset_breaks": [2500, 4000, 5000, 7500, 10000,
                                           16000, 25000, 40000, 62500],
                "purse_offset_log10_range": [3.7, 5.3],
                "class_change_threshold": 3.0,
            },
            "sprint_route_cutoff_yards": 1540,
            "layoff_days": 60,
            "bias_window_days": 90,
        },
        "features": features,
    }


def main() -> int:
    cfg = build_config()
    OUT.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    c = cfg["counts"]
    print(f"wrote {OUT}")
    print(f"  catalog rows        : {c['catalog_features']}")
    print(f"  unique features     : {c['unique_catalog_features']}")
    print(f"  duplicates          : {c['duplicate_names_in_catalog']}")
    print(f"  by Doug's rank      : {c['by_doug_rank']}")
    print(f"  DPv1 additions      : {c['dpv1_additions']}")
    print(f"  ACTIVE total        : {c['active_total']}")
    print(f"  blocked rank 1-2    : {c['blocked_rank_1_2']}")
    print(f"  deferred rank 1-2   : {c['deferred_rank_1_2']}")
    print(f"  permanently unavail : {len(c['permanently_unavailable'])} "
          f"({len(c['permanently_unavailable_rank_1_2'])} of them rank 1-2)")
    print(f"    {c['permanently_unavailable_rank_1_2']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
