"""Read-only audit: which features see results from earlier races the same day.

For every jockey / trainer feature in dpv1.3.2 this recomputes the value
"as of the start of the race day" (only races on earlier dates count) with
code independent of the feature builder, and compares it with the stored
entry_features_dpv1 value.

    python scripts_dpv1/tracking/same_day_audit_2026-11-09.py [--db PATH]

Prints JSON. Opens the DB read-only. Training rows = the 1.3.2 training
frame: 2022-01-01 on, GP/CT/MNR/ELP/DED, races that have been run.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from dpv1_common import DEFAULT_DB, DEFAULT_CONFIG, shrink_rate_vec  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--db", default=str(DEFAULT_DB))
a = ap.parse_args()
cfg = json.loads(Path(DEFAULT_CONFIG).read_text(encoding="utf-8"))
d = cfg["defaults"]
TRACKS = ["GP", "CT", "MNR", "ELP", "DED"]

c = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
raw = pd.read_sql_query("""
    SELECT e.id AS entry_id, e.race_id, e.jockey_id, e.trainer_id, e.finish_pos,
           r.race_num, rd.race_date, rd.track_id, t.code AS track
    FROM entries e JOIN races r ON r.id = e.race_id
    JOIN race_days rd ON rd.id = r.race_day_id JOIN tracks t ON t.id = rd.track_id""", c)
roles = ["jockey", "trainer"]
feat_cols = [f"days_since_{r}_last_win" for r in roles] + \
    [f"{r}_{w}d_winrate_shrunk" for r in roles for w in (30, 90, 365)] + \
    [f"{r}_starts_30d" for r in roles] + [f"{r}_at_track_winrate_shrunk" for r in roles]
f = pd.read_sql_query(f"SELECT entry_id, {', '.join(feat_cols)} FROM entry_features_dpv1", c)
c.close()
df = raw.merge(f, on="entry_id", how="inner")
df["is_win"] = (df["finish_pos"] == 1).astype(float)
df["date"] = pd.to_datetime(df["race_date"])
run = df.groupby("race_id")["finish_pos"].transform(lambda s: s.notna().any())
df["train"] = (df["race_date"] >= "2022-01-01") & df["track"].isin(TRACKS) & run


def by_day(role, extra=()):
    """Per (role id, *extra, date): wins and starts on that day."""
    keys = [f"{role}_id", *extra]
    g = df.groupby(keys + ["date"])["is_win"].agg(["sum", "count"]).reset_index()
    return g.sort_values(keys + ["date"]), keys


def window_prior(role, days=None, extra=()):
    """wins, starts over [date - days, date) (or all earlier dates)."""
    g, keys = by_day(role, extra)
    g["cw"] = g.groupby(keys)["sum"].cumsum() - g["sum"]      # strictly earlier days
    g["cs"] = g.groupby(keys)["count"].cumsum() - g["count"]
    if days is not None:
        # subtract what is older than the window: cumulative through date - days - 1
        g2 = g[keys + ["date", "sum", "count"]].copy()
        g2["tw"] = g2.groupby(keys)["sum"].cumsum()
        g2["ts"] = g2.groupby(keys)["count"].cumsum()
        g["cut"] = g["date"] - pd.Timedelta(days=days)
        old_w = np.zeros(len(g)); old_s = np.zeros(len(g))
        for k, idx in g.groupby(keys).indices.items():
            dates = g2["date"].to_numpy()[idx]
            pos = np.searchsorted(dates, g["cut"].to_numpy()[idx], side="left")  # days < cut
            tw = np.concatenate([[0], g2["tw"].to_numpy()[idx]])
            ts = np.concatenate([[0], g2["ts"].to_numpy()[idx]])
            old_w[idx] = tw[pos]; old_s[idx] = ts[pos]
        g["cw"] -= old_w; g["cs"] -= old_s
    m = df[keys + ["date"]].merge(g[keys + ["date", "cw", "cs"]], on=keys + ["date"], how="left")
    return m["cw"].to_numpy(), m["cs"].to_numpy()


def cmp(stored, recomputed):
    s = pd.Series(stored, dtype="float64"); r = pd.Series(recomputed, dtype="float64")
    diff = ~((s.isna() & r.isna()) | (np.isclose(s, r, rtol=0, atol=1e-9)))
    out = {}
    for name, mask in (("all_rows", np.ones(len(df), bool)), ("training_rows", df["train"].to_numpy())):
        dm = diff.to_numpy() & mask
        out[name] = {"rows": int(mask.sum()), "differ": int(dm.sum()),
                     "differ_pct": round(100 * dm.sum() / max(mask.sum(), 1), 3)}
    return out, diff.to_numpy()


report = {"db": a.db, "rates_and_counts": {}, "days_since_last_win": {}}
prior = d["shrinkage_prior_win_rate"]; ks = d["shrinkage_k_defaults"]

for role in roles:
    for w in (30, 90, 365):
        wins, starts = window_prior(role, w)
        rate = shrink_rate_vec(wins, starts, prior, ks[f"{role}_overall"])
        report["rates_and_counts"][f"{role}_{w}d_winrate_shrunk"], _ = cmp(df[f"{role}_{w}d_winrate_shrunk"], rate)
        if w == 30:
            report["rates_and_counts"][f"{role}_starts_30d"], _ = cmp(df[f"{role}_starts_30d"], starts)
    wins, starts = window_prior(role, None, ("track_id",))
    rate = shrink_rate_vec(wins, starts, prior, ks[f"{role}_at_track"])
    report["rates_and_counts"][f"{role}_at_track_winrate_shrunk"], _ = cmp(df[f"{role}_at_track_winrate_shrunk"], rate)

# days since last win, as of the start of the day: last win strictly before today
for role in roles:
    key = f"{role}_id"
    g, _ = by_day(role)
    g["win_day"] = g["date"].where(g["sum"] > 0)
    g["last_win_before"] = g.groupby(key)["win_day"].transform(lambda s: s.shift(1).ffill())
    m = df[[key, "date"]].merge(g[[key, "date", "last_win_before"]], on=[key, "date"], how="left")
    sod = (m["date"] - m["last_win_before"]).dt.days.to_numpy().astype(float)
    name = f"days_since_{role}_last_win"
    st = df[name].to_numpy(dtype=float)
    res, diff = cmp(st, sod)
    tr = df["train"].to_numpy()
    both = diff & tr
    became_null = both & np.isnan(st) & ~np.isnan(sod)
    other = both & ~np.isnan(st)
    res["training_rows_detail"] = {
        "stored_null_sod_has_value": int(became_null.sum()),
        "other_differences": int(other.sum()),
        "stored_null_total": int((np.isnan(st) & tr).sum()),
        "sod_value_on_affected_rows": {
            "median_days": float(np.nanmedian(sod[became_null])) if became_null.any() else None,
            "p25": float(np.nanpercentile(sod[became_null], 25)) if became_null.any() else None,
            "p75": float(np.nanpercentile(sod[became_null], 75)) if became_null.any() else None,
            "share_le_7_days": round(float(np.mean(sod[became_null] <= 7)), 3) if became_null.any() else None,
        },
        "itm_rate_affected_rows": round(float((df.loc[became_null, "finish_pos"] <= 3).mean()), 4) if became_null.any() else None,
        "itm_rate_other_stored_null_rows": round(float((df.loc[np.isnan(st) & tr & ~became_null, "finish_pos"] <= 3).mean()), 4),
        "itm_rate_all_training_rows": round(float((df.loc[tr, "finish_pos"] <= 3).mean()), 4),
        "by_year": {str(y): int(n) for y, n in pd.Series(df.loc[became_null, "date"].dt.year).value_counts().sort_index().items()},
    }
    report["days_since_last_win"][name] = res

print(json.dumps(report, indent=2))
