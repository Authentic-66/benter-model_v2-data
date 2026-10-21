"""Step 2: winners vs all starters by last race's stretch-run rank, and the
live model's out-of-fold P(ITM) gap. Reads out/stretch.pkl.

    python scripts_dpv1/diagnostics/stretch_run/s2_winners.py
"""
import pandas as pd, numpy as np, json, sys
from pathlib import Path
OUT = Path(__file__).resolve().parent / "out"
d = pd.read_pickle(OUT / "stretch.pkl")
# check: horse order by computed finish BL == official order
ok = d[d.bl_fin.notna() & d.fin.notna()].copy()
ok["r"] = ok.groupby("race_id").bl_fin.rank(method="min")
print(f"computed finish order == official finish: {(ok.r == ok.fin).mean():.1%} of {len(ok):,} horses")
d = d.sort_values(["horse_id", "race_date", "race_num"])
for col in ["str_gain", "str_gain_rank", "turn_gain_rank", "bl_str", "bl_fin", "fin", "race_date", "track", "n_call", "race_id"]:
    d["last_" + col] = d.groupby("horse_id")[col].shift(1)
d["days"] = (pd.to_datetime(d.race_date) - pd.to_datetime(d.last_race_date)).dt.days
d = d[(d.race_date >= "2022-01-01") & d.fin.notna()]
has = d[d.last_str_gain_rank.notna() & (d.days <= 365)].copy()
has["won"] = (has.fin == 1).astype(int); has["itm"] = (has.fin <= 3).astype(int)
has["fast1"] = has.last_str_gain_rank == 1
has["fast3"] = has.last_str_gain_rank <= 3
has["turn1"] = has.last_turn_gain_rank == 1
print(f"\nstarters 2022+ with a charted last race (<=365d): {len(has):,}; races {has.race_id.nunique():,}")
W = has[has.won == 1]
print(f"winners: {len(W):,}")
for f, lab in [("fast1", "fastest stretch run in field last time"), ("fast3", "top-3 stretch run last time"), ("turn1", "fastest move into the stretch last time")]:
    pw, pa = W[f].mean(), has[f].mean()
    wr_y, wr_n = has[has[f]].won.mean(), has[~has[f]].won.mean()
    it_y, it_n = has[has[f]].itm.mean(), has[~has[f]].itm.mean()
    print(f"\n{lab}:\n  share of winners {pw:.1%}  vs share of all starters {pa:.1%}  (lift {pw/pa:.2f}x)"
          f"\n  win% if yes {wr_y:.1%} vs no {wr_n:.1%};  ITM% yes {it_y:.1%} vs no {it_n:.1%}")
# separate the 'already won last time' effect
has["lastwon"] = has.last_fin == 1
print("\nwin% by (fastest stretch last time) x (won last time):")
print(has.groupby(["lastwon", "fast1"]).won.agg(["mean", "size"]).round(3).to_string())
print("\nwin% by last-race stretch-run rank (non-winners last time only):")
nl = has[~has.lastwon]
print(nl.groupby(nl.last_str_gain_rank.clip(upper=8)).won.agg(["mean", "size"]).round(3).to_string())
# model check: out-of-fold P(ITM) from the live model's folds
fp = pd.read_csv(r"D:\Benter Model_v2 Data\benter-model_v2-data\scripts_dpv1\dpv1_fold_predictions.csv", usecols=["entry_id", "y_true", "p_fund", "y_pred"])
m = has.merge(fp, on="entry_id")
print(f"\nmodel check on {len(m):,} out-of-fold starters (ITM actual - model P(ITM), fundamental):")
for f in ["fast1", "fast3", "turn1"]:
    for val in (True, False):
        g = m[m[f] == val]; r = g.y_true - g.p_fund
        print(f"  {f}={val!s:5}  n={len(g):6,}  actual {g.y_true.mean():.3f}  model {g.p_fund.mean():.3f}  gap {r.mean()*100:+.2f}pp  (z {r.mean()/(r.std()/np.sqrt(len(g))):+.1f})")
g = m[(m.fast1) & (m.last_fin > 1)]; r = g.y_true - g.p_fund
print(f"  fastest stretch but did NOT win last time: n={len(g):,} actual {g.y_true.mean():.3f} model {g.p_fund.mean():.3f} gap {r.mean()*100:+.2f}pp z {r.mean()/(r.std()/np.sqrt(len(g))):+.1f}")
for trk in ["DED", "GP", "CT", "MNR", "ELP"]:
    g = m[(m.track == trk) & m.fast1]; r = g.y_true - g.p_fund
    if len(g) > 50: print(f"    {trk}: n={len(g):,} gap {r.mean()*100:+.2f}pp z {r.mean()/(r.std()/np.sqrt(len(g))):+.1f}")
has.to_pickle(OUT / "has.pkl")
