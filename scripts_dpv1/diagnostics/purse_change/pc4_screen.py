import numpy as np, pandas as pd
from scipy.optimize import minimize
from pathlib import Path
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
df = pd.read_pickle(OUT / "pc_df.pkl")
x = df["purse_change_from_last"]
miss = x.isna().astype(float)
xf = x.fillna(0)
lr = np.log1p(xf)
cand = {
  "raw (refit slope only)": np.column_stack([xf]),
  "A: log ratio clipped ±ln(4)": np.column_stack([lr.clip(-np.log(4), np.log(4))]),
  "A2: log ratio clipped + >3x flag": np.column_stack([lr.clip(-np.log(4), np.log(4)), (xf > 3).astype(float)]),
  "B: pct capped [-60%,+100%]": np.column_stack([xf.clip(-.6, 1.0)]),
  "C: tier move (class_tier today - last)": None,
  "bins (upper bound, 10 one-hots)": None,
}
tier_d = (df["tier"] - df["prev_tier"]).fillna(0)
cand["C: tier move (class_tier today - last)"] = np.column_stack([tier_d.clip(-3, 3), lr.clip(-np.log(4), np.log(4))])
bins = [-np.inf, -0.5, -0.3, -0.1, -1e-9, 1e-9, 0.1, 0.3, 0.6, 1.0, 3.0, np.inf]
b = pd.cut(xf, bins, labels=False)
cand["bins (upper bound, 10 one-hots)"] = np.column_stack([(b == i).astype(float) for i in range(11) if i != 4])
off = np.log(df["p_fund"] / (1 - df["p_fund"])).to_numpy()
y = df["y_true"].to_numpy(); yr = df["race_date"].str[:4]
tr = yr.isin(["2023", "2024"]).to_numpy(); te = ~tr
def fit(X):
    X1 = np.column_stack([np.ones(len(X)), X, miss])
    def nll(w):
        z = off[tr] + X1[tr] @ w; return np.sum(np.logaddexp(0, z) - y[tr] * z) + 1e-3 * w @ w
    w = minimize(nll, np.zeros(X1.shape[1]), method="L-BFGS-B").x
    return X1 @ w
def topitm(p, mask):
    d = df[mask].assign(p=p[mask]); top = d.loc[d.groupby("race_id")["p"].idxmax()]; return top["y_true"].mean(), top.index
base_ll = np.mean(np.logaddexp(0, off[te]) - y[te] * off[te])
base_top, base_idx = topitm(off, te)
print(f"held-out 2025-26: n {te.sum():,}, races {df[te].race_id.nunique():,}; base log-loss {base_ll:.5f}, base top-pick ITM {base_top:.4f}")
for name, X in cand.items():
    z = off + fit(X)
    ll = np.mean(np.logaddexp(0, z[te]) - y[te] * z[te])
    t, idx = topitm(z, te)
    # paired: races where the top pick changed
    d = df[te].assign(p=z[te]); new = d.loc[d.groupby("race_id")["p"].idxmax()].set_index("race_id")["y_true"]
    old = df[te].assign(p=off[te]); old = old.loc[old.groupby("race_id")["p"].idxmax()].set_index("race_id")["y_true"]
    b_, c_ = ((new == 1) & (old == 0)).sum(), ((new == 0) & (old == 1)).sum()
    print(f"  {name:42s} dLL {1e4*(ll-base_ll):+7.2f}e-4   top-pick ITM {100*(t-base_top):+.2f}pp  (discordant {b_} up / {c_} down)")
