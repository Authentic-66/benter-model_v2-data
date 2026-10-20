"""Grade one comparison of the purse-change ablation against RULES.md.

    python _purse15/eval_purse15.py <control_folds> <candidate_folds> <label> [--snapshot DB]
    python _purse15/eval_purse15.py --determinism folds_a.csv folds_a2.csv

Rows: entries in live's dpv1_fold_predictions.csv AND both fold files, with a
finish in the snapshot. Labels: snapshot finish_pos <= 3 for every arm.
"""
import hashlib, sqlite3, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import binomtest
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
LIVE_FOLDS = HERE.parent / "dpv1_fold_predictions.csv"
TRACKS = ["GP", "CT", "MNR", "ELP", "DED"]
BINS = [-np.inf, -0.5, -0.3, -0.1, -1e-9, 1e-9, 0.1, 0.3, 0.6, 1.0, 3.0, np.inf]
BLAB = ["<=-50%", "-50..-30", "-30..-10", "-10..0", "0", "0..+10", "+10..+30", "+30..+60",
        "+60..+100", "+1x..+3x", ">+3x"]

if sys.argv[1] == "--determinism":
    md5 = [hashlib.md5(Path(p).read_bytes()).hexdigest() for p in sys.argv[2:4]]
    print(f"GATE 0 determinism: {sys.argv[2]} {md5[0]}\n                    {sys.argv[3]} {md5[1]}")
    print("GATE 0", "PASS (byte-identical)" if md5[0] == md5[1] else "FAIL: STOP, read nothing")
    sys.exit(0 if md5[0] == md5[1] else 1)

ctl_path, cand_path, label = sys.argv[1:4]
snap = sys.argv[sys.argv.index("--snapshot") + 1] if "--snapshot" in sys.argv else str(HERE / "racing_a.db")
con = sqlite3.connect(f"file:{snap}?mode=ro", uri=True)
lab = pd.read_sql("""SELECT e.id entry_id, e.finish_pos, f.purse_change_from_last pc
                     FROM entries e JOIN entry_features_dpv1 f ON f.entry_id = e.id""", con)
lab = lab[lab.finish_pos.notna()]
live_ids = set(pd.read_csv(LIVE_FOLDS, usecols=["entry_id"]).entry_id)
cols = ["entry_id", "race_id", "track", "race_date", "p_fund", "y_pred"]
X = pd.read_csv(ctl_path, usecols=cols).rename(columns={"p_fund": "p1", "y_pred": "b1"})
Y = pd.read_csv(cand_path, usecols=["entry_id", "p_fund", "y_pred"]).rename(columns={"p_fund": "p2", "y_pred": "b2"})
d = X.merge(Y, on="entry_id").merge(lab, on="entry_id")
d = d[d.entry_id.isin(live_ids)].copy()
d["y"] = (d.finish_pos <= 3).astype(int)
d["yr"] = d.race_date.astype(str).str[:4]
print(f"=== {label}: control {Path(ctl_path).name} -> candidate {Path(cand_path).name}")
print(f"rows {len(d):,}, races {d.race_id.nunique():,}; labels from {Path(snap).name}")

def tops(col):
    return d.loc[d.groupby("race_id")[col].idxmax(), ["race_id", "track", "yr", "y"]].set_index("race_id")
T1, T2 = tops("p1"), tops("p2")

def mc(idx):
    a, b = T1.loc[idx, "y"], T2.loc[idx, "y"]
    up, dn = int(((a == 0) & (b == 1)).sum()), int(((a == 1) & (b == 0)).sum())
    p = binomtest(up, up + dn).pvalue if up + dn else 1.0
    return dict(n=len(idx), c=100 * a.mean(), k=100 * b.mean(), d=100 * (b.mean() - a.mean()), up=up, dn=dn, p=p)

def pr(name, r):
    print(f"  {name:<22}{r['n']:>6}{r['c']:>9.2f}%{r['k']:>9.2f}%{r['d']:>+8.2f}{r['up']:>6}/{r['dn']:<5}{r['p']:>7.3f}")

print("\n-- top-pick ITM (control, candidate, delta pp, discordant up/down, McNemar p)")
per = {}
for t in TRACKS:
    per[t] = mc(T1.index[T1.track == t]); pr(t, per[t])
allr = mc(T1.index); pr("ALL five tracks", allr)
yrs = {}
for y in sorted(T1.yr.unique()):
    yrs[y] = mc(T1.index[T1.yr == y]); pr(f"year {y}", yrs[y])
print("  track x year delta:")
for t in TRACKS:
    print("   ", t, "  ".join(f"{y} {mc(T1.index[(T1.track == t) & (T1.yr == y)])['d']:+.2f}" for y in sorted(yrs)))

def ll(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
def lld(x, a, b):
    dl = ll(x.y, x[b]) - ll(x.y, x[a]); g = dl.groupby(x.race_id).sum()
    se = np.sqrt(len(g)) * g.std() / len(dl); return dl.mean(), dl.mean() / se if se else 0.0
print("\n-- log-loss delta candidate - control (negative = candidate better), race-clustered z; AUC")
LLall = None
for name, s in [(t, d.track == t) for t in TRACKS] + [(f"year {y}", d.yr == y) for y in sorted(yrs)] + [("ALL", d.track.notna())]:
    x = d[s]; f, b = lld(x, "p1", "p2"), lld(x, "b1", "b2")
    if name == "ALL": LLall = f
    print(f"  {name:<12}n {len(x):>7,}  fund {f[0]:+.5f} (z {f[1]:+6.2f})  blend {b[0]:+.5f} (z {b[1]:+6.2f})"
          f"  AUC {roc_auc_score(x.y, x.p1):.4f} -> {roc_auc_score(x.y, x.p2):.4f}")

def cal(x, col, how):
    q = pd.qcut(x[col], 10, labels=False, duplicates="drop") if how == "dec" else np.minimum((x[col] * 10).astype(int), 9)
    t = x.assign(q=q).groupby("q").agg(n=("y", "size"), y=("y", "mean"), p=(col, "mean"))
    return 100 * (t.n * (t.y - t.p).abs()).sum() / t.n.sum()
print("\n-- calibration: weighted mean |error| pp, own deciles / fixed 0.1 bins; mean pred - actual (p_fund)")
for t in TRACKS + ["ALL"]:
    x = d if t == "ALL" else d[d.track == t]
    print(f"  {t:<4} control {cal(x, 'p1', 'dec'):.3f}/{cal(x, 'p1', 'fix'):.3f}  candidate {cal(x, 'p2', 'dec'):.3f}/{cal(x, 'p2', 'fix'):.3f}"
          f"   mean pred-actual {100 * (x.p1.mean() - x.y.mean()):+.2f} -> {100 * (x.p2.mean() - x.y.mean()):+.2f}")

print("\n-- purse-change bucket table (actual - predicted p_fund, pp; z race-clustered)")
d["bk"] = pd.cut(d.pc, BINS, labels=BLAB).cat.add_categories("NULL").fillna("NULL")
mae = {}
for col in ("p1", "p2"):
    rows, tot = [], 0.0
    for k, g in d.groupby("bk", observed=True):
        r = g.y - g[col]; rs = r.groupby(g.race_id).sum()
        se = np.sqrt((rs ** 2).sum()) / len(g)
        rows.append((k, len(g), g.y.mean(), g[col].mean(), 100 * r.mean(), r.mean() / se))
        tot += len(g) * abs(r.mean())
    mae[col] = 100 * tot / len(d)
    if col == "p1": base = rows
    else: cand = rows
print(f"  {'bucket':<10}{'n':>7}{'actual':>8}  {'ctl pred':>8}{'ctl diff':>9}{'z':>6}  {'cand pred':>9}{'cand diff':>10}{'z':>6}")
for a, b in zip(base, cand):
    print(f"  {a[0]:<10}{a[1]:>7}{a[2]:>8.3f}  {a[3]:>8.3f}{a[4]:>+9.2f}{a[5]:>+6.1f}  {b[3]:>9.3f}{b[4]:>+10.2f}{b[5]:>+6.1f}")
print(f"  weighted mean |bucket error|: control {mae['p1']:.3f}pp -> candidate {mae['p2']:.3f}pp")

print("\n-- RULES (RULES.md)")
r1a = all(per[t]["d"] >= -0.5 for t in ("GP", "CT", "MNR"))
r1b = all(per[t]["d"] >= -2.0 for t in TRACKS)
r1c = not (allr["d"] < 0 and allr["p"] < 0.05)
print(f"  Rule 1: GP/CT/MNR >= -0.5pp {r1a} {[(t, round(float(per[t]['d']), 2)) for t in ('GP', 'CT', 'MNR')]}; "
      f"every track >= -2pp {r1b} {[(t, round(float(per[t]['d']), 2)) for t in ('ELP', 'DED')]}; "
      f"pooled not sig. negative {r1c} ({allr['d']:+.3f}pp p={allr['p']:.3f})  -> {'PASS' if r1a and r1b and r1c else 'FAIL'}")
pos = sum(r["d"] > 0 for r in yrs.values())
r2 = allr["d"] >= 0 and pos >= 3 and LLall[0] < 0
print(f"  Rule 2: pooled {allr['d']:+.3f}pp (>=0: {allr['d'] >= 0}); positive years {pos}/{len(yrs)} "
      f"{[(y, round(float(r['d']), 2)) for y, r in yrs.items()]}; fund log-loss {LLall[0]:+.5f} (z {LLall[1]:+.2f})  -> {'PASS' if r2 else 'FAIL'}")
verdict = "PASS" if (r1a and r1b and r1c and r2) else "FAIL"
calib = (not r2) and LLall[1] <= -2 and mae["p2"] < mae["p1"]
print(f"  {label}: {verdict}" + ("   (Rule 2 failed but calibration improved: goes to Doug as a calibration-vs-ranking call)" if calib else ""))
