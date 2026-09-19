"""Stage 4 evaluation: arms A (4-track train), B (5-track train), C (DED-only), identical validation rows.

    python _ded/eval_stage4.py   (run from scripts_dpv1/)
"""
import sqlite3
import numpy as np
import pandas as pd
from scipy.stats import binomtest
from sklearn.metrics import roc_auc_score

PRIMARY = {"GP", "CT", "MNR", "DED"}
ORDER = ["GP", "CT", "MNR", "ELP", "DED"]
INC = ["GP", "CT", "MNR", "ELP"]


def lab(t):
    return f"{t} ({'primary' if t in PRIMARY else 'secondary'})"


def load(p):
    d = pd.read_csv(p)
    return d[d.finish_pos.notna()].copy()


A, B, C = load("_ded/folds_armA.csv"), load("_ded/folds_armB.csv"), load("_ded/folds_armC.csv")
assert (A.entry_id.values == B.entry_id.values).all(), "A/B rows differ"
f = pd.read_sql("select entry_id, class_direction, race_type from entry_features_dpv1",
                sqlite3.connect("_ded/racing_ded.db"))
d = A[["entry_id", "race_id", "track", "race_date", "fold", "y_true", "p_fund", "y_pred"]].rename(
    columns={"p_fund": "pA", "y_pred": "bA"})
d = d.merge(B[["entry_id", "p_fund", "y_pred"]].rename(columns={"p_fund": "pB", "y_pred": "bB"}), on="entry_id")
d = d.merge(C[["entry_id", "p_fund", "y_pred"]].rename(columns={"p_fund": "pC", "y_pred": "bC"}),
            on="entry_id", how="left")
d = d.merge(f, on="entry_id", how="left")
d["yr"] = d.race_date.astype(str).str[:4]
ded = d[d.track == "DED"]
assert ded.pC.notna().all() and len(ded) == len(C), "C's DED rows != A/B DED rows"
print(f"validation: {len(d):,} scored rows, {d.race_id.nunique():,} races "
      f"(A,B identical; C = the {ded.race_id.nunique():,} DED races, identical rows)")


def tops(df, col):
    return df.loc[df.groupby("race_id")[col].idxmax(),
                  ["race_id", "track", "yr", "y_true", "entry_id"]].set_index("race_id")


T = {"A": tops(d, "pA"), "B": tops(d, "pB"), "C": tops(ded, "pC")}


def mc(x, y, idx):
    a, b = T[x].loc[idx, "y_true"], T[y].loc[idx, "y_true"]
    b01 = int(((a == 0) & (b == 1)).sum())
    b10 = int(((a == 1) & (b == 0)).sum())
    p = binomtest(b01, b01 + b10).pvalue if b01 + b10 else 1.0
    return len(idx), 100 * a.mean(), 100 * b.mean(), 100 * (b.mean() - a.mean()), b01, b10, p


def row(label, r):
    disc = f"{r[4]}/{r[5]}"
    print(f"  {label:<30}{r[0]:>6}{r[1]:>9.2f}%{r[2]:>9.2f}%{r[3]:>+8.2f}{disc:>10}{r[6]:>8.3f}")


HDR = f"  {'population':<30}{'races':>6}{'first':>10}{'second':>10}{'delta':>8}{'b01/b10':>10}{'p':>8}"
ti = T["A"]
YEARS = sorted(ti.yr.unique())

print("\n=== TOP-PICK ITM, B (5-track) vs A (4-track control); first=A second=B ===")
print(HDR)
for t in ORDER:
    row(lab(t), mc("A", "B", ti.index[ti.track == t]))
inc_idx = ti.index[ti.track.isin(INC)]
R_inc = mc("A", "B", inc_idx)
row("POOLED incumbents (4)", R_inc)
row("POOLED primary incumbents (3)", mc("A", "B", ti.index[ti.track.isin(["GP", "CT", "MNR"])]))
row("ALL 5 tracks", mc("A", "B", ti.index))
print("\n  incumbents by validation year:")
YR_INC = {}
for y in YEARS:
    YR_INC[y] = mc("A", "B", ti.index[ti.track.isin(INC) & (ti.yr == y)])
    row(f"incumbents {y}", YR_INC[y])
print("\n  delta by track x year (pp):")
for t in ORDER:
    cells = "  ".join(f"{y}: {mc('A', 'B', ti.index[(ti.track == t) & (ti.yr == y)])[3]:+.2f}" for y in YEARS)
    print(f"  {lab(t):<22}{cells}")
print("\n  DED by year:")
R_ded_y = {}
for y in YEARS:
    R_ded_y[y] = mc("A", "B", ti.index[(ti.track == "DED") & (ti.yr == y)])
    row(f"DED {y}", R_ded_y[y])
R_ded = mc("A", "B", ti.index[ti.track == "DED"])
fam = ded.groupby("race_id").race_type.first().str.extract(
    r"^(MAIDENCLAIMING|MAIDENSPECIALWEIGHT|CLAIMING|ALLOWANCE|STAKES|STARTER)")[0].fillna("OTHER")
print("\n  DED by race family:")
for k in ["CLAIMING", "MAIDENCLAIMING", "ALLOWANCE", "MAIDENSPECIALWEIGHT", "STARTER", "STAKES"]:
    idx = fam.index[fam == k]
    if len(idx):
        row(f"DED {k}", mc("A", "B", idx))


def ll(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def lld(df, c1, c2):
    dl = ll(df.y_true, df[c2]) - ll(df.y_true, df[c1])
    g = dl.groupby(df.race_id).sum()
    se = np.sqrt(len(g)) * g.std() / len(dl)
    return dl.mean(), (dl.mean() / se if se else 0.0)


print("\n=== LOG-LOSS delta B - A (race-clustered z; negative = B better) ===")
print(f"  {'population':<30}{'n':>9}{'fund d':>11}{'z':>7}{'blend d':>11}{'z':>7}{'AUC A':>8}{'AUC B':>8}")


def llrow(label, s):
    x = d[s]
    f1, b1 = lld(x, "pA", "pB"), lld(x, "bA", "bB")
    print(f"  {label:<30}{len(x):>9,}{f1[0]:>+11.5f}{f1[1]:>+7.2f}{b1[0]:>+11.5f}{b1[1]:>+7.2f}"
          f"{roc_auc_score(x.y_true, x.pA):>8.4f}{roc_auc_score(x.y_true, x.pB):>8.4f}")
    return f1


LL = {t: llrow(lab(t), d.track == t) for t in ORDER}
LL_inc = llrow("POOLED incumbents", d.track != "DED")
for y in YEARS:
    llrow(f"incumbents {y}", (d.track != "DED") & (d.yr == y))
for y in YEARS:
    llrow(f"DED {y}", (d.track == "DED") & (d.yr == y))

print("\n=== C (DED-only specialist) vs B (5-track) on DED; first=B second=C ===")
print(HDR)
cidx = T["C"].index
R_cb = mc("B", "C", cidx)
row("DED all", R_cb)
R_cb_y = {}
for y in sorted(T["C"].yr.unique()):
    R_cb_y[y] = mc("B", "C", cidx[T["C"].yr == y])
    row(f"DED {y}", R_cb_y[y])
rca = mc("A", "C", cidx)
print(f"  C vs A on DED: delta {rca[3]:+.2f}pp p={rca[6]:.3f}")
f1 = lld(ded, "pB", "pC")
print(f"  log-loss C - B on DED: fund {f1[0]:+.5f} (z {f1[1]:+.2f}) | "
      f"AUC A {roc_auc_score(ded.y_true, ded.pA):.4f}  B {roc_auc_score(ded.y_true, ded.pB):.4f}  "
      f"C {roc_auc_score(ded.y_true, ded.pC):.4f}")

print("\n=== GAP #11 class-direction residual (within-race demeaned y - p_fund, pp) ===")
for k in "AB":
    r = d.y_true - d["p" + k]
    d["rw" + k] = r - r.groupby(d.race_id).transform("mean")
for pop, s in (("incumbents", d.track != "DED"), ("DED", d.track == "DED")):
    sub = d[s]
    for cd, g in sub.groupby(sub.class_direction.fillna("NULL")):
        if len(g) > 100:
            print(f"  {pop:<11}{cd:<12} n={len(g):>7,}  A {100 * g.rwA.mean():+.2f}  B {100 * g.rwB.mean():+.2f}")

print("\n=== GAP #8 calibration: weighted mean |cal error| pp (own deciles / fixed 0.1 bins) ===")


def cal(x, col, how):
    q = (pd.qcut(x[col], 10, labels=False, duplicates="drop") if how == "dec"
         else np.minimum((x[col] * 10).astype(int), 9))
    t = x.assign(q=q).groupby("q").agg(n=("y_true", "size"), y=("y_true", "mean"), p=(col, "mean"))
    return 100 * (t.n * (t.y - t.p).abs()).sum() / t.n.sum()


for t in ORDER + ["ALL"]:
    x = d if t == "ALL" else d[d.track == t]
    extra = f"   C {cal(x, 'pC', 'dec'):.3f}/{cal(x, 'pC', 'fix'):.3f}" if t == "DED" else ""
    print(f"  {t:<5} A {cal(x, 'pA', 'dec'):.3f}/{cal(x, 'pA', 'fix'):.3f}   "
          f"B {cal(x, 'pB', 'dec'):.3f}/{cal(x, 'pB', 'fix'):.3f}{extra}   "
          f"mean pred-actual A {100 * (x.pA.mean() - x.y_true.mean()):+.2f} B {100 * (x.pB.mean() - x.y_true.mean()):+.2f}")

print("\n=== RULES ===")
per = {t: mc("A", "B", ti.index[ti.track == t])[3] for t in ORDER}
r1a = all(per[t] >= -0.5 for t in ["GP", "CT", "MNR"])
r1b = all(per[t] >= -2.0 for t in INC)
r1c = not (R_inc[3] < 0 and R_inc[6] < 0.05)
print(f"Rule 1 (revised): primary >= -0.5pp: {r1a} {[(t, round(per[t], 2)) for t in ['GP', 'CT', 'MNR']]}")
print(f"   every incumbent incl. ELP >= -2pp: {r1b} (ELP {per['ELP']:+.2f})")
print(f"   pooled incumbents not significantly negative: {r1c} ({R_inc[3]:+.3f}pp, p={R_inc[6]:.3f})")
print(f"   (context) incumbent deltas by year: {[(y, round(r[3], 2)) for y, r in YR_INC.items()]}; "
      f"incumbent fund log-loss z {LL_inc[1]:+.2f}")
print(f"   RULE 1 {'PASS' if (r1a and r1b and r1c) else 'FAIL'}")
pos = sum(r[3] > 0 for r in R_ded_y.values())
below2 = [y for y, r in R_ded_y.items() if r[3] < -2]
r2 = (R_ded[3] >= 0) and (pos >= 3) and (LL["DED"][0] < 0)
print(f"Rule 2: DED delta {R_ded[3]:+.3f}pp (p={R_ded[6]:.3f}) | positive years {pos}/{len(R_ded_y)} "
      f"{[(y, round(r[3], 2)) for y, r in R_ded_y.items()]} | DED fund log-loss {LL['DED'][0]:+.5f} "
      f"(z {LL['DED'][1]:+.2f}) | DED years below A by >2pp: {below2 or 'none'}")
print(f"   RULE 2 {'PASS' if r2 else 'FAIL'}")
cons = sum(r[3] > 0 for r in R_cb_y.values())
r3 = R_cb[3] > 1 and R_cb[6] < 0.05 and cons >= 3
print(f"Rule 3: C - B on DED {R_cb[3]:+.3f}pp (p={R_cb[6]:.3f}), C ahead in {cons}/{len(R_cb_y)} years -> "
      f"{'REOPEN specialist' if r3 else 'generalist stands'}")
