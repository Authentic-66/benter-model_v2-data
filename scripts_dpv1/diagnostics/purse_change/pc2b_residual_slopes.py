import numpy as np, pandas as pd
from pathlib import Path
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
df = pd.read_pickle(OUT / "pc_df.pkl")
x = df["purse_change_from_last"]
df["lr"] = np.log1p(x)
df["cap"] = x.clip(-0.6, 1.0)
df["cs_d"] = df["class_score_change_from_last"]
def dm(col, d):  # within-race demean, then per-sd
    v = d[col] - d.groupby("race_id")[col].transform("mean")
    return v / v.std()
def slope(d, cols, label):
    d = d.dropna(subset=cols)
    d = d[d.groupby("race_id")["race_id"].transform("size") > 1]
    r = d["y_true"] - d["p_fund"]; r = r - r.groupby(d["pbin"]).transform("mean")
    r = r - r.groupby(d["race_id"]).transform("mean")
    X = np.column_stack([dm(c, d) for c in cols])
    b, *_ = np.linalg.lstsq(X, r.to_numpy(), rcond=None)
    e = r.to_numpy() - X @ b
    # race-clustered sandwich
    XtXi = np.linalg.inv(X.T @ X)
    G = pd.DataFrame(X * e[:, None]).groupby(d["race_id"].to_numpy()).sum().to_numpy()
    V = XtXi @ (G.T @ G) @ XtXi
    z = b / np.sqrt(np.diag(V))
    print(f"  {label:58s} n {len(d):7,}  " + "  ".join(f"{c}: {100*bb:+.2f}pp/sd (z {zz:+.1f})" for c, bb, zz in zip(cols, b, z)))
has = df[x.notna()]
print("== residual slopes vs the live model (OOF, level-stripped, within-race demeaned; +ve = model under-credits a HIGHER value)")
print("-- all rows with a last race")
slope(has, ["purse_change_from_last"], "raw pct (what the model has)")
slope(has, ["lr"], "log ratio")
slope(has, ["cap"], "pct capped [-60%, +100%]")
slope(has, ["purse_change_from_last", "lr"], "raw + log jointly")
print("-- core range |x| <= 1 (excludes the stakes tail)")
core = has[has["purse_change_from_last"].between(-1, 1)]
slope(core, ["purse_change_from_last"], "raw pct"); slope(core, ["lr"], "log ratio")
print("-- by year, log ratio")
for y in ("2023", "2024", "2025", "2026"):
    slope(has[has["race_date"].str[:4] == y], ["lr"], y)
print("-- by track, log ratio")
for t in ("GP", "CT", "MNR", "ELP", "DED"):
    slope(has[has["track"] == t], ["lr"], t)
# Kel-Co Test 1 subset: same-track claiming -> claiming; d2 = log purse move not explained by log tag move
cc = has[(has["rt"] == "CLAIMING") & (has["prev_rt"] == "CLAIMING") & has["race_tag"].gt(0) & has["prev_race_tag"].gt(0)].copy()
cc["ltag"] = np.log10(cc["race_tag"] / cc["prev_race_tag"]); cc["lp"] = np.log10(1 + cc["purse_change_from_last"])
A = np.column_stack([np.ones(len(cc)), cc["ltag"]]); bb, *_ = np.linalg.lstsq(A, cc["lp"], rcond=None)
cc["d2"] = cc["lp"] - A @ bb
same = cc[cc["prev_track"] == cc["track"]]; ship = cc[cc["prev_track"] != cc["track"]]
print(f"-- Kel-Co Test 1 open lead: claiming->claiming, d2 = log purse move beyond the tag move (R2(purse|tag) fit on {len(cc):,})")
slope(same, ["d2"], "same-track d2 (Test 1 reported -2.06, z -10.6)")
slope(same, ["d2", "purse_change_from_last"], "same-track d2, partial on raw pct")
slope(same, ["d2", "cs_d"], "same-track d2, partial on class_score change")
slope(ship, ["d2"], "cross-track d2 (Test 1 reported -1.61)")
print("   same-track d2 sd (log10):", round(same["d2"].std(), 4), " raw pct sd in that subset:", round(same["purse_change_from_last"].std(), 4))
print("   share of same-track C->C rows whose raw pct is exactly 0:", round((same["purse_change_from_last"] == 0).mean(), 3))
