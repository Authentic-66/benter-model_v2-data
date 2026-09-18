"""Paired evaluation of a control/candidate fold-prediction pair (Gap #4 fix).

    python _gap4fix/eval_pair.py <ctrl_folds.csv> <cand_folds.csv>
"""
import sys, sqlite3
import numpy as np, pandas as pd
from scipy.stats import binomtest

G = "_gap4fix/"
ctrl_csv, cand_csv = sys.argv[1:3]

# --- affected rows: either windowed column differs between the two tables ---
def feats(db):
    c = sqlite3.connect(G + db)
    f = pd.read_sql("select entry_id, last_3_avg_finish l3, gate_break_avg_last_3 gb, "
                    "class_direction from entry_features_dpv1", c)
    return f, c
fc, conn = feats("racing_ctrl.db"); ff, _ = feats("racing_cand.db")
m = fc.merge(ff[["entry_id", "l3", "gb"]], on="entry_id", suffixes=("_c", "_f"))
def diff(a, b): return ~((m[a] == m[b]) | (m[a].isna() & m[b].isna()))
m["affected"] = diff("l3_c", "l3_f") | diff("gb_c", "gb_f")
# corpus-start ordinal per horse, within the feature table (the 2026-09-17
# definition: 17,799 ord-0 / 13,143 ord-1 scored rows, 10,222 races)
o = pd.read_sql("select entry_id, horse_id, race_date from entry_features_dpv1", conn)
o = o.sort_values(["horse_id", "race_date", "entry_id"])
o["ord"] = o.groupby("horse_id").cumcount()
m = m.merge(o[["entry_id", "ord"]], on="entry_id", how="left")
m = m.rename(columns={"affected": "value_changed"})
m["affected"] = m["ord"] <= 1   # 1st/2nd corpus start: the fix's target population

def load(p):
    d = pd.read_csv(p)
    return d[d.finish_pos.notna()]
a, b = load(ctrl_csv), load(cand_csv)
assert (a.entry_id.values == b.entry_id.values).all(), "row sets differ"
d = a[["entry_id", "race_id", "track", "y_true", "p_fund", "y_pred"]].merge(
    b[["entry_id", "p_fund", "y_pred"]], on="entry_id", suffixes=("_c", "_f"))
d = d.merge(m[["entry_id", "affected", "value_changed", "ord", "class_direction"]], on="entry_id", how="left")
d["affected"] = d["affected"].fillna(False).astype(bool)
print(f"scored rows {len(d):,}  races {d.race_id.nunique():,}  "
      f"affected rows {d.affected.sum():,} ({100*d.affected.mean():.1f}%)")
aff_races = set(d.loc[d.affected, "race_id"])
print(f"races with an affected horse {len(aff_races):,}")
print(f"rows whose windowed value actually changed {d.value_changed.fillna(False).sum():,}")
print(f"max|dp_fund| on unaffected rows {np.abs(d.p_fund_f - d.p_fund_c)[~d.affected].max():.5f}")

# --- top-pick ITM, exact McNemar ---
def top(col):
    t = d.loc[d.groupby("race_id")[col].idxmax(), ["race_id", "track", "y_true"]]
    return t.set_index("race_id")
tc, tf = top("p_fund_c"), top("p_fund_f")
print("\nTOP-PICK ITM (p_fund)")
print(f"{'population':<28}{'races':>7}{'ctrl':>9}{'cand':>9}{'delta':>9}{'b01/b10':>10}{'p':>8}")
def mc(label, idx):
    x, y = tc.loc[idx, "y_true"], tf.loc[idx, "y_true"]
    b01 = int(((x == 0) & (y == 1)).sum()); b10 = int(((x == 1) & (y == 0)).sum())
    p = binomtest(b01, b01 + b10, 0.5).pvalue if b01 + b10 else 1.0
    print(f"{label:<28}{len(idx):>7}{100*x.mean():>8.3f}%{100*y.mean():>8.3f}%"
          f"{100*(y.mean()-x.mean()):>+8.3f}{f'{b01}/{b10}':>10}{p:>8.3f}")
mc("all races", tc.index)
mc("races w/ affected horse", tc.index[tc.index.isin(aff_races)])
mc("races w/o affected horse", tc.index[~tc.index.isin(aff_races)])
for t in ["GP", "CT", "MNR", "ELP"]:
    mc(t, tc.index[tc.track == t])
print(f"top pick changed in {(top('p_fund_c').index == top('p_fund_f').index).all() and ((d.loc[d.groupby('race_id')['p_fund_c'].idxmax(),'entry_id'].values != d.loc[d.groupby('race_id')['p_fund_f'].idxmax(),'entry_id'].values).mean()*100):.2f}% of races")

# --- log-loss ---
def ll(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12); return -(y*np.log(p) + (1-y)*np.log(1-p))
print("\nLOG-LOSS delta (cand - ctrl); negative = better")
print(f"{'population':<30}{'n':>8}{'fund d':>11}{'z':>7}{'blend d':>11}{'z':>7}")
def lrow(label, s):
    y = d.y_true[s]
    out = f"{label:<30}{s.sum():>8,}"
    for c in ("p_fund", "y_pred"):
        dl = ll(y, d[c + "_f"][s]) - ll(y, d[c + "_c"][s])
        # race-clustered SE
        g = dl.groupby(d.race_id[s]).sum(); n = len(dl)
        se = np.sqrt(len(g)) * g.std() / n
        out += f"{dl.mean():>+11.5f}{dl.mean()/se if se else 0:>+7.2f}"
    print(out)
allm = pd.Series(True, index=d.index)
lrow("ALL", allm)
lrow("AFFECTED (1st/2nd start)", d.affected)
lrow("  ord 0", d.affected & (d.ord == 0))
lrow("  ord 1", d.affected & (d.ord == 1))
lrow("UNAFFECTED ROWS", ~d.affected)
lrow("ALL ROWS IN AFFECTED RACES", d.race_id.isin(aff_races))

# --- Gap #11 class-direction residual table ---
print("\nGAP #11 CLASS-DIRECTION RESIDUAL (within-race demeaned y - p_fund, pp)")
for sfx in ("_c", "_f"):
    r = d.y_true - d["p_fund" + sfx]
    d["rw" + sfx] = r - r.groupby(d.race_id).transform("mean")
for cd, g in d.groupby(d.class_direction.fillna("NULL")):
    rc, rf = g.rw_c.mean()*100, g.rw_f.mean()*100
    print(f"  {cd:<12} n={len(g):>7,}  ctrl {rc:+.2f}  cand {rf:+.2f}  shift {rf-rc:+.2f}")

# --- Gap #8 calibration recheck ---
# The affected-subgroup figure is bin-definition sensitive (0.40-0.62pp for
# one arm across four definitions), so two are reported.
print("\nGAP #8 CALIBRATION: weighted mean |cal error| (pp)")
def cal(s, col, how):
    g = d[s].copy()
    g["q"] = (pd.qcut(g[col], 10, labels=False, duplicates="drop") if how == "dec"
              else np.minimum((g[col] * 10).astype(int), 9))
    t = g.groupby("q").agg(n=("y_true", "size"), y=("y_true", "mean"), p=(col, "mean"))
    return 100 * (t.n * (t.y - t.p).abs()).sum() / t.n.sum()
for lab, s in [("ALL", allm), ("AFFECTED", d.affected)]:
    for how, hl in (("dec", "own deciles"), ("fix", "fixed 0.1 bins")):
        print(f"  {lab:<9}{hl:<16} ctrl {cal(s,'p_fund_c',how):.3f}  cand {cal(s,'p_fund_f',how):.3f}")
