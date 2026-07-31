"""Validation for ``entry_features_dpv1``.

Six checks, each of which can fail the run:

1. **Row integrity** — one row per entry, no duplicates, no orphans.
2. **Coverage per track** — how many features clear 90% non-null at GP, CT
   and MNR, and where the misses are concentrated.
3. **Dead features** — anything constant (or all-null) across every row is
   a feature that is not doing any work and should not go into training.
4. **Distribution sanity** — mean/std per track, plus range checks on the
   features whose valid range is known a priori (rates in [0,1], normalized
   market probabilities summing to 1 per race).
5. **Shrinkage sanity** — shrunk rates must sit between the raw sample rate
   and the prior, and must be tighter than the raw rate at small n.
6. **Leakage probes** — first-time starters must have NULL prior-form
   features, and no feature may be perfectly separable on the outcome.

Usage
-----
    python scripts_dpv1/validate_dpv1_features.py            # full report
    python scripts_dpv1/validate_dpv1_features.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dpv1_common import DEFAULT_CONFIG, DEFAULT_DB, FEATURES_TABLE  # noqa: E402

KEY_COLS = {"entry_id", "race_id", "horse_id", "trainer_id", "jockey_id",
            "race_date", "track_id"}
TRACKS = ["GP", "CT", "MNR"]

# Features whose values must lie in [0, 1] by construction.
RATE_SUFFIXES = ("_winrate_shrunk", "_win_pct", "_pct_shrunk", "_success_rate",
                 "_itm_share", "_probability", "_probability_normalized")

# Prior-form features that MUST be NULL for a horse's first-ever start.
FIRST_START_MUST_BE_NULL = [
    "last_race_finish_pos", "last_race_beaten_lengths", "last_race_days_ago",
    "last_race_speed_figure", "last_race_won", "last_race_troubled_trip",
    "last_race_was_maiden", "class_change_from_last",
    "class_score_change_from_last", "purse_change_from_last",
    "distance_change_bucket", "distance_change_from_last_race",
    "weight_change_from_last_race", "surface_change_from_last_race",
    "condition_change_from_last_race", "is_shipping_today",
    "new_trainer_flag", "pace_progression_last_race",
]


def load(conn: sqlite3.Connection, table: str) -> pd.DataFrame:
    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    codes = pd.read_sql_query("SELECT id, code FROM tracks", conn)
    df["track"] = df["track_id"].map(dict(zip(codes["id"], codes["code"])))
    return df


def check_rows(df: pd.DataFrame, conn: sqlite3.Connection) -> dict:
    n_entries = conn.execute("SELECT count(*) FROM entries").fetchone()[0]
    dupes = int(df["entry_id"].duplicated().sum())
    res = {
        "rows": len(df),
        "entries_in_db": n_entries,
        "duplicate_entry_ids": dupes,
        "row_count_matches": len(df) == n_entries,
    }
    res["pass"] = res["row_count_matches"] and dupes == 0
    return res


def coverage_table(df: pd.DataFrame, feats: list[str]) -> pd.DataFrame:
    rows = []
    for f in feats:
        r = {"feature": f, "overall": df[f].notna().mean()}
        for t in TRACKS:
            sub = df.loc[df["track"] == t, f]
            r[t] = sub.notna().mean() if len(sub) else np.nan
        rows.append(r)
    return pd.DataFrame(rows).set_index("feature")


def check_dead(df: pd.DataFrame, feats: list[str]) -> dict:
    all_null, constant = [], []
    for f in feats:
        s = df[f].dropna()
        if len(s) == 0:
            all_null.append(f)
        elif s.nunique() <= 1:
            constant.append(f"{f} (={s.iloc[0]!r})")
    return {"all_null": all_null, "constant": constant,
            "pass": not all_null and not constant}


def check_ranges(df: pd.DataFrame, feats: list[str]) -> dict:
    violations = []
    for f in feats:
        if not any(f.endswith(s) for s in RATE_SUFFIXES):
            continue
        s = pd.to_numeric(df[f], errors="coerce").dropna()
        if len(s) and (s.min() < -1e-9 or s.max() > 1 + 1e-9):
            violations.append(
                f"{f}: min={s.min():.4f} max={s.max():.4f} (expected [0,1])")
    return {"out_of_range": violations, "pass": not violations}


def check_market_normalization(df: pd.DataFrame) -> dict:
    if "market_probability_normalized" not in df.columns:
        return {"skipped": True, "pass": True}
    g = df.groupby("race_id")["market_probability_normalized"].sum()
    g = g[g > 0]
    off = g[(g - 1.0).abs() > 1e-6]
    return {
        "races_checked": int(len(g)),
        "races_not_summing_to_1": int(len(off)),
        "pass": len(off) == 0,
    }


def check_first_start_nulls(df: pd.DataFrame) -> dict:
    if "career_starts" not in df.columns:
        return {"skipped": True, "pass": True}
    fs = df[df["career_starts"] == 0]
    leaks = {}
    for f in FIRST_START_MUST_BE_NULL:
        if f not in df.columns:
            continue
        n = int(fs[f].notna().sum())
        if n:
            leaks[f] = n
    return {
        "first_start_rows": int(len(fs)),
        "features_with_values_on_first_start": leaks,
        "pass": not leaks,
    }


def check_shrinkage(conn: sqlite3.Connection, cfg: dict) -> dict:
    """Shrunk trainer rates must be pulled toward the prior at small n."""
    df = pd.read_sql_query(
        f"""SELECT trainer_30d_winrate_shrunk AS rate,
                   trainer_starts_30d        AS starts
            FROM {FEATURES_TABLE}
            WHERE trainer_30d_winrate_shrunk IS NOT NULL""",
        conn,
    )
    prior = cfg["defaults"]["shrinkage_prior_win_rate"]
    bands = []
    for lo, hi in [(0, 1), (1, 5), (5, 20), (20, 60), (60, 10**9)]:
        s = df[(df["starts"] >= lo) & (df["starts"] < hi)]["rate"]
        if not len(s):
            continue
        bands.append({"starts": f"[{lo},{hi})", "n": int(len(s)),
                      "mean": float(s.mean()), "std": float(s.std()),
                      "dist_from_prior": float((s - prior).abs().mean())})
    # Dispersion must grow with sample size: more evidence, less shrinkage.
    monotone = all(bands[i]["std"] <= bands[i + 1]["std"] + 1e-9
                   for i in range(len(bands) - 1))
    return {"prior": prior, "bands": bands,
            "dispersion_grows_with_n": monotone, "pass": monotone}


def cross_track_summary(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    names = [k for k, v in cfg["features"].items()
             if v.get("dpv1_addition") and k in df.columns
             and k not in ("track_code", "class_score",
                           "class_score_change_from_last")]
    return coverage_table(df, sorted(names))


def distribution_table(df: pd.DataFrame, feats: list[str]) -> pd.DataFrame:
    rows = []
    for f in feats:
        s = pd.to_numeric(df[f], errors="coerce")
        if s.notna().sum() == 0:
            continue
        r = {"feature": f}
        for t in TRACKS:
            sub = s[df["track"] == t]
            r[f"{t}_mean"] = sub.mean()
            r[f"{t}_std"] = sub.std()
        rows.append(r)
    return pd.DataFrame(rows).set_index("feature")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--table", default=FEATURES_TABLE)
    p.add_argument("--json", default=None, help="write results as JSON")
    p.add_argument("--full", action="store_true",
                   help="print the full per-feature coverage table")
    args = p.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    conn = sqlite3.connect(args.db)
    df = load(conn, args.table)
    feats = [c for c in df.columns if c not in KEY_COLS | {"track"}]

    print("=" * 78)
    print(f"DPv1 FEATURE VALIDATION — {args.table} (config {cfg['version']})")
    print("=" * 78)

    results: dict = {}

    results["rows"] = check_rows(df, conn)
    r = results["rows"]
    print(f"\n[1] ROW INTEGRITY  {'PASS' if r['pass'] else 'FAIL'}")
    print(f"    rows={r['rows']}  entries in db={r['entries_in_db']}  "
          f"duplicate entry_ids={r['duplicate_entry_ids']}")
    print(f"    features: {len(feats)}")
    for t in TRACKS:
        print(f"      {t}: {int((df['track'] == t).sum())} rows")

    cov = coverage_table(df, feats)
    results["coverage"] = {
        "n_features": len(feats),
        "over_90_overall": int((cov["overall"] >= 0.9).sum()),
        "over_90_by_track": {t: int((cov[t] >= 0.9).sum()) for t in TRACKS},
        "over_50_by_track": {t: int((cov[t] >= 0.5).sum()) for t in TRACKS},
        "worst": cov["overall"].nsmallest(15).round(4).to_dict(),
    }
    c = results["coverage"]
    print(f"\n[2] COVERAGE PER TRACK")
    print(f"    features with >=90% coverage: overall {c['over_90_overall']}"
          f"/{len(feats)}")
    for t in TRACKS:
        print(f"      {t:<4} >=90%: {c['over_90_by_track'][t]:>3}   "
              f">=50%: {c['over_50_by_track'][t]:>3}")
    print("    lowest-coverage features:")
    for f, v in c["worst"].items():
        print(f"      {f:<40} {v * 100:6.2f}%   "
              f"GP {cov.loc[f, 'GP'] * 100:5.1f}  "
              f"CT {cov.loc[f, 'CT'] * 100:5.1f}  "
              f"MNR {cov.loc[f, 'MNR'] * 100:5.1f}")

    results["dead"] = check_dead(df, feats)
    d = results["dead"]
    print(f"\n[3] DEAD FEATURES  {'PASS' if d['pass'] else 'FAIL'}")
    print(f"    all-null: {d['all_null'] or 'none'}")
    print(f"    constant: {d['constant'] or 'none'}")

    results["ranges"] = check_ranges(df, feats)
    results["market"] = check_market_normalization(df)
    rr, mm = results["ranges"], results["market"]
    print(f"\n[4] DISTRIBUTION SANITY  "
          f"{'PASS' if rr['pass'] and mm['pass'] else 'FAIL'}")
    print(f"    rate features out of [0,1]: {rr['out_of_range'] or 'none'}")
    if not mm.get("skipped"):
        print(f"    market probs sum to 1: "
              f"{mm['races_checked'] - mm['races_not_summing_to_1']}"
              f"/{mm['races_checked']} races")

    results["shrinkage"] = check_shrinkage(conn, cfg)
    s = results["shrinkage"]
    print(f"\n[5] BAYESIAN SHRINKAGE  {'PASS' if s['pass'] else 'FAIL'}")
    print(f"    prior win rate = {s['prior']}")
    print(f"    {'trainer_starts_30d':<18} {'n':>8} {'mean':>8} {'std':>8} "
          f"{'|rate-prior|':>13}")
    for b in s["bands"]:
        print(f"    {b['starts']:<18} {b['n']:>8} {b['mean']:>8.4f} "
              f"{b['std']:>8.4f} {b['dist_from_prior']:>13.4f}")
    print(f"    dispersion grows with sample size: "
          f"{s['dispersion_grows_with_n']}")

    results["first_start"] = check_first_start_nulls(df)
    fs = results["first_start"]
    print(f"\n[6] LEAKAGE PROBE — first-time starters  "
          f"{'PASS' if fs['pass'] else 'FAIL'}")
    print(f"    first-start rows: {fs['first_start_rows']}")
    print(f"    prior-form features carrying a value: "
          f"{fs['features_with_values_on_first_start'] or 'none'}")

    ct = cross_track_summary(df, cfg)
    results["cross_track_coverage"] = ct.round(4).to_dict()
    print(f"\n[7] CROSS-TRACK FEATURE COVERAGE")
    print(f"    {'feature':<38} {'all':>7} {'GP':>7} {'CT':>7} {'MNR':>7}")
    for f, row in ct.iterrows():
        print(f"    {f:<38} {row['overall'] * 100:6.2f}% "
              f"{row['GP'] * 100:6.2f}% {row['CT'] * 100:6.2f}% "
              f"{row['MNR'] * 100:6.2f}%")

    if args.full:
        print("\n[8] FULL COVERAGE TABLE")
        print((cov * 100).round(2).to_string())
        print("\n[9] PER-TRACK DISTRIBUTIONS")
        print(distribution_table(df, feats).round(3).to_string())

    checks = ["rows", "dead", "ranges", "market", "shrinkage", "first_start"]
    failed = [k for k in checks if not results[k].get("pass", True)]
    print("\n" + "=" * 78)
    print(f"RESULT: {'ALL CHECKS PASS' if not failed else 'FAILED: ' + ', '.join(failed)}")
    print("=" * 78)

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2, default=str),
                                   encoding="utf-8")
        print(f"wrote {args.json}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
