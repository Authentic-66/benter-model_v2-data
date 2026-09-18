"""Paired evaluation: pace-duplicate fix candidate vs control (2026-09-18).

    python _pacefix/eval_pace.py _pacefix/folds_pace_ctrl.csv _pacefix/folds_pace_cand.csv
"""
import sys, sqlite3
import numpy as np, pandas as pd
from scipy.stats import binomtest

ctrl_csv, cand_csv = sys.argv[1:3]
f = pd.read_sql("select entry_id, class_direction, pace_pressure_in_race pace "
                "from entry_features_dpv1", sqlite3.connect("_pacefix/racing_ctrl.db"))

def load(p):
    d = pd.read_csv(p); return d[d.finish_pos.notna()]
a, b = load(ctrl_csv), load(cand_csv)
assert (a.entry_id.values == b.entry_id.values).all(), "row sets differ"
d = a[["entry_id", "race_id", "track", "y_true", "p_fund", "y_pred"]].merge(
    b[["entry_id", "p_fund", "y_pred"]], on="entry_id", suffixes=("_c", "_f")).merge(f, on="entry_id", how="left")
print(f"scored rows {len(d):,}  races {d.race_id.nunique():,}")
dp = np.abs(d.p_fund_f - d.p_fund_c)
print(f"|dp_fund| mean {dp.mean():.5f}  p99 {dp.quantile(.99):.5f}  max {dp.max():.5f}")

tc = d.loc[d.groupby("race_id").p_fund_c.idxmax(), ["race_id", "track", "entry_id", "y_true"]].set_index("race_id")
tf = d.loc[d.groupby("race_id").p_fund_f.idxmax(), ["race_id", "entry_id", "y_true"]].set_index("race_id")
print(f"top pick changed in {100*(tc.entry_id != tf.entry_id).mean():.2f}% of races")
print("\nTOP-PICK ITM (p_fund), exact McNemar")
print(f"{'population':<12}{'races':>7}{'ctrl':>10}{'cand':>10}{'delta':>9}{'b01/b10':>10}{'p':>8}")
def mc(label, idx):
    x, y = tc.loc[idx, "y_true"], tf.loc[idx, "y_true"]
    b01 = int(((x == 0) & (y == 1)).sum()); b10 = int(((x == 1) & (y == 0)).sum())
    p = binomtest(b01, b01 + b10, 0.5).pvalue if b01 + b10 else 1.0
    print(f"{label:<12}{len(idx):>7}{100*x.mean():>9.3f}%{100*y.mean():>9.3f}%"
          f"{100*(y.mean()-x.mean()):>+9.3f}{f'{b01}/{b10}':>10}{p:>8.3f}")
mc("all races", tc.index)
for t in ["GP", "CT", "MNR", "ELP"]:
    mc(t, tc.index[tc.track == t])

def ll(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12); return -(y*np.log(p) + (1-y)*np.log(1-p))
print("\nLOG-LOSS delta (cand - ctrl), race-clustered z; negative = better")
print(f"{'population':<22}{'n':>9}{'fund d':>11}{'z':>7}{'blend d':>11}{'z':>7}")
def lrow(label, s):
    y = d.y_true[s]; out = f"{label:<22}{s.sum():>9,}"
    for c in ("p_fund", "y_pred"):
        dl = ll(y, d[c + "_f"][s]) - ll(y, d[c + "_c"][s])
        g = dl.groupby(d.race_id[s]).sum(); se = np.sqrt(len(g)) * g.std() / len(dl)
        out += f"{dl.mean():>+11.5f}{dl.mean()/se if se else 0:>+7.2f}"
    print(out)
lrow("ALL", pd.Series(True, index=d.index))
for t in ["GP", "CT", "MNR", "ELP"]:
    lrow(t, d.track == t)
for v in ["hot", "moderate", "slow"]:
    lrow(f"pace = {v}", d.pace == v)
lrow("pace = NULL", d.pace.isna())

print("\nGAP #11 CLASS-DIRECTION RESIDUAL (within-race demeaned y - p_fund, pp)")
for sfx in ("_c", "_f"):
    r = d.y_true - d["p_fund" + sfx]; d["rw" + sfx] = r - r.groupby(d.race_id).transform("mean")
for cd, g in d.groupby(d.class_direction.fillna("NULL")):
    print(f"  {cd:<12} n={len(g):>7,}  ctrl {100*g.rw_c.mean():+.2f}  cand {100*g.rw_f.mean():+.2f}  shift {100*(g.rw_f.mean()-g.rw_c.mean()):+.2f}")

print("\nGAP #8 CALIBRATION: weighted mean |cal error| (pp)")
def cal(s, col, how):
    g = d[s].copy()
    g["q"] = (pd.qcut(g[col], 10, labels=False, duplicates="drop") if how == "dec"
              else np.minimum((g[col] * 10).astype(int), 9))
    t = g.groupby("q").agg(n=("y_true", "size"), y=("y_true", "mean"), p=(col, "mean"))
    return 100 * (t.n * (t.y - t.p).abs()).sum() / t.n.sum()
for how, hl in (("dec", "own deciles"), ("fix", "fixed 0.1 bins")):
    s = pd.Series(True, index=d.index)
    print(f"  ALL {hl:<16} ctrl {cal(s,'p_fund_c',how):.3f}  cand {cal(s,'p_fund_f',how):.3f}")
print("  per pace shape, own deciles:")
for v in ["hot", "moderate", "slow"]:
    s = d.pace == v
    print(f"    {v:<9} ctrl {cal(s,'p_fund_c','dec'):.3f}  cand {cal(s,'p_fund_f','dec'):.3f}  "
          f"(mean pred-actual: ctrl {100*(d.p_fund_c[s].mean()-d.y_true[s].mean()):+.2f}  cand {100*(d.p_fund_f[s].mean()-d.y_true[s].mean()):+.2f})")
