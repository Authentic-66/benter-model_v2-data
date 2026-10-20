import pickle, sys
import numpy as np, pandas as pd
sys.path[:0] = [r"D:\Benter Model_v2 Data\benter-model_v2-data\scripts_dpv1", r"D:\Benter Model_v2 Data\benter-model_v2-data\scripts", r"D:\Benter Model_v2 Data\benter-model_v2-data\scripts_v2a"]
from pathlib import Path
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
pd.set_option("display.width", 220)
df = pd.read_pickle(OUT / "pc_df.pkl")
m = pickle.load(open(r"D:\Benter Model_v2 Data\benter-model_v2-data\scripts_dpv1\dpv1.pkl", "rb"))
pre = m.preprocessor
names = m.fundamental.feature_names_ if hasattr(m.fundamental, "feature_names_") else None
co = m.coefficients
k = "purse_change_from_last"
print(f"live coef {k}: {co.get(k):+.4f} per sd;  __missing: {co.get(k + '__missing')};  train median {pre.medians[k]:.4f} mean {pre.means[k]:.4f} sd {pre.stds[k]:.4f}")
rank = sorted(co, key=lambda c: -abs(co[c])).index(k) + 1
print(f"|coef| rank {rank} of {len(co)}")
for v in (-0.5, -0.3, -0.1, 0.3, 1, 3, 10, 50):
    print(f"   x={v:+5}: logit contribution {co[k] * (v - pre.means[k]) / pre.stds[k]:+.3f}")
x = df[k]
bins = [-np.inf, -0.5, -0.3, -0.1, -1e-9, 1e-9, 0.1, 0.3, 0.6, 1.0, 3.0, np.inf]
lab = ["<=-50%", "-50..-30", "-30..-10", "-10..0", "0", "0..+10", "+10..+30", "+30..+60", "+60..+100", "+1x..+3x", ">+3x"]
df["b"] = pd.cut(x, bins, labels=lab)
df["b"] = df["b"].cat.add_categories("missing").fillna("missing")
# level-stripped residual: y - p within 20 p_fund bins (removes miscalibration of the overall level)
df["pbin"] = pd.qcut(df["p_fund"], 20, labels=False, duplicates="drop")
def tab(d, p):
    r = d["y_true"] - d[p]
    g = d.assign(r=r).groupby("b", observed=True)
    out = pd.DataFrame({"n": g.size(), "actual": g["y_true"].mean(), "pred": g[p].mean(), "diff_pp": 100 * g["r"].mean()})
    # race-clustered SE
    se = []
    for b, gg in d.assign(r=r).groupby("b", observed=True):
        rs = gg.groupby("race_id")["r"].sum(); se.append(100 * np.sqrt((rs ** 2).sum()) / len(gg))
    out["z"] = out["diff_pp"] / np.array(se)
    return out.round(3)
print("\n== calibration by purse-change bucket, live dpv1.3.0-5track out-of-fold (2023-2026, 5 tracks)")
print("-- raw p_fund"); print(tab(df, "p_fund").to_string())
print("-- card-style P(ITM) (p_fund normalised to 3 per race)"); print(tab(df, "p_norm").to_string())
print("-- blended y_pred (with market)"); print(tab(df, "y_pred").to_string())
# ranking-relevant: within-race demeaned residual after level-strip
df["r_ls"] = df["y_true"] - df["p_fund"]; df["r_ls"] -= df.groupby("pbin")["r_ls"].transform("mean")
g = df.groupby("b", observed=True)["r_ls"]
print("\n-- level-stripped residual (20 p_fund bins), pp:", (100 * g.mean()).round(2).to_dict())
by = df.assign(yr=df["race_date"].str[:4]).groupby(["b", "yr"], observed=True).apply(lambda d: 100 * (d.y_true - d.p_fund).mean()).unstack().round(1)
print("\n-- raw p_fund diff (pp) by year"); print(by.to_string())
bt = df.groupby(["b", "track"], observed=True).apply(lambda d: 100 * (d.y_true - d.p_fund).mean()).unstack().round(1)
print("\n-- raw p_fund diff (pp) by track"); print(bt.to_string())
df.to_pickle(OUT / "pc_df.pkl")
