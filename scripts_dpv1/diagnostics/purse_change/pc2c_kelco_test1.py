import numpy as np, pandas as pd
from pathlib import Path
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
df = pd.read_pickle(OUT / "pc_df.pkl")
x = df["purse_change_from_last"]
df["lr"] = np.log1p(x)
cc_mask = (df["rt"] == "CLAIMING") & (df["prev_rt"] == "CLAIMING") & df["race_tag"].gt(0) & df["prev_race_tag"].gt(0) & x.notna()
df["ltag"] = np.where(cc_mask, np.log10(df["race_tag"] / df["prev_race_tag"]), np.nan)
df["lp"] = np.where(cc_mask, np.log10(1 + x), np.nan)
c = df[cc_mask]; A = np.column_stack([np.ones(len(c)), c["ltag"]]); b, *_ = np.linalg.lstsq(A, c["lp"], rcond=None)
print("lp on ltag: intercept %.4f slope %.3f, R2 %.3f" % (b[0], b[1], 1 - ((c["lp"] - A @ b) ** 2).sum() / ((c["lp"] - c["lp"].mean()) ** 2).sum()))
df["d2"] = df["lp"] - (b[0] + b[1] * df["ltag"])
# Test 1 recipe: residual level-stripped in 20 p_fund bins; quantity demeaned within the race over rows that have it
def run(sub, cols, label, restrip=True):
    d = sub.dropna(subset=cols).copy()
    pb = pd.qcut(d["p_fund"], 20, labels=False, duplicates="drop")
    r = d["y_true"] - d["p_fund"]
    if restrip: r = r - r.groupby(pb).transform("mean")
    X = np.column_stack([(d[c] - d.groupby("race_id")[c].transform("mean")) for c in cols])
    X = X / X.std(axis=0)
    X1 = np.column_stack([np.ones(len(d)), X])
    bb, *_ = np.linalg.lstsq(X1, r.to_numpy(), rcond=None); e = r.to_numpy() - X1 @ bb
    XtXi = np.linalg.inv(X1.T @ X1); G = pd.DataFrame(X1 * e[:, None]).groupby(d["race_id"].to_numpy()).sum().to_numpy()
    se = np.sqrt(np.diag(XtXi @ (G.T @ G) @ XtXi))
    print(f"  {label:50s} n {len(d):6,} " + "  ".join(f"{cn} {100*v:+.2f}pp/sd (z {v/s:+.1f})" for cn, v, s in zip(cols, bb[1:], se[1:])))
same = df[cc_mask & (df["prev_track"] == df["track"])]
print("-- same-track claiming->claiming (Test 1 recipe)")
run(same, ["d2"], "d2")
run(same, ["d2", "purse_change_from_last"], "d2 + raw pct")
run(same, ["d2", "class_score_change_from_last"], "d2 + class_score change")
run(same, ["lr"], "log purse ratio alone")
run(same, ["purse_change_from_last"], "raw pct alone")
run(same, ["ltag"], "log tag ratio alone")
