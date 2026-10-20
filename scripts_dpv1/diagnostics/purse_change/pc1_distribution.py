import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import numpy as np, pandas as pd
from pc_load import load
from pathlib import Path
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
ent, df = load()
x = ent["purse_change_from_last"]
print("== 1. build check: stored feature vs reconstructed (purse-prev)/prev")
both = x.notna() & ent["recon_pct"].notna()
print(f"rows {len(ent):,}; feature non-null {x.notna().mean():.1%}; recon agrees (|d|<1e-9) on {np.isclose(x[both], ent['recon_pct'][both]).mean():.4%} of {both.sum():,}")
print(f"feature null but recon present {(x.isna() & ent['recon_pct'].notna()).sum()}, feature present but recon null {(x.notna() & ent['recon_pct'].isna()).sum()}")
tr = ent[(ent["race_date"] >= "2022-01-01") & ent["track"].isin(["GP","CT","MNR","ELP","DED"])]
xt = tr["purse_change_from_last"]
print(f"\n== distribution, training scope (2022+, 5 tracks): n {len(tr):,}, null {xt.isna().mean():.1%}")
q = [0, .001, .01, .05, .1, .25, .5, .75, .9, .95, .99, .999, 1]
print(pd.Series(xt.quantile(q).values, index=q).round(3).to_string())
print(f"mean {xt.mean():.3f}  sd {xt.std():.3f}  skew {xt.skew():.1f}  kurt {xt.kurt():.0f}")
print(f"exactly 0: {(xt==0).mean():.1%};  |x|<=0.10: {(xt.abs()<=.1).mean():.1%};  x>=+1 (doubled+): {(xt>=1).mean():.2%};  x>=+3: {(xt>=3).mean():.2%};  x<=-0.5: {(xt<=-.5).mean():.2%}")
sd = xt.std()
print(f"in standardised units (sd {sd:.3f}): a -30% drop = {-.3/sd:.2f} sd, a +30% rise = {.3/sd:+.2f} sd, a doubling = {1/sd:+.2f} sd, max = {xt.max()/sd:+.1f} sd")
print("\n-- top tail (x>=+3): today's race type / last race type")
big = tr[xt >= 3]
print(big["rt"].value_counts().head(6).to_string()); print(big["prev_rt"].value_counts().head(6).to_string())
print("-- top tail: share where today is a stakes race", (big["rt"].fillna("").str.contains("STAKES")).mean().round(3))
print("\n-- bottom tail (x<=-0.5): today's / last race type")
low = tr[xt <= -.5]
print(low["rt"].value_counts().head(6).to_string()); print(low["prev_rt"].value_counts().head(6).to_string())
print("-- bottom tail: last race at a different track", (low["prev_track"] != low["track"]).mean().round(3), " vs all rows", (tr["prev_track"] != tr["track"])[xt.notna()].mean().round(3))
print("\n-- 10 largest rises (training scope)")
print(tr.loc[xt.nlargest(10).index, ["track","race_date","rt","purse","prev_track","prev_rt","prev_purse","purse_change_from_last","finish_pos"]].to_string())
print("\n-- 10 largest drops")
print(tr.loc[xt.nsmallest(10).index, ["track","race_date","rt","purse","prev_track","prev_rt","prev_purse","purse_change_from_last","finish_pos"]].to_string())
df.to_pickle(OUT / "pc_df.pkl")
