"""Decomposition: blend's ITM gain = model information, or just the beta<1 reshaping of the tote?
'tote reshaped' = the blend with the model term held at its race average (alpha*mean logit is
constant in the race, so normalising to sum 3 absorbs it): expit(beta*logit(m_itm)+c), normalised."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"D:\Benter Model_v2 Data\benter-model_v2-data"); sys.path.insert(0, str(ROOT / "scripts_dpv1"))
import logging; logging.disable(logging.WARNING)
from dpv1_runtime import load_model, normalise_itm, invert_harville
HERE = Path(sys.argv[1])  # scratch work dir with scored_rerun.csv (from analyse.py)
b = load_model(ROOT / "scripts_dpv1" / "dpv1.pkl").blend
d = pd.read_csv(HERE / "scored_rerun.csv")
lg = lambda p: np.log(np.clip(p, 1e-9, 1 - 1e-9) / (1 - np.clip(p, 1e-9, 1 - 1e-9)))
rows = []
for rid, g in d.groupby("race_id", sort=False):
    g = g.copy()
    zb = b.alpha_ * lg(g.p_fund) + b.beta_ * lg(g.m_itm) + b.gamma_
    zr = b.beta_ * lg(g.m_itm) + b.gamma_ + b.alpha_ * lg(g.p_fund).mean()
    g["b_itm"] = normalise_itm(1 / (1 + np.exp(-zb))); g["r_itm"] = normalise_itm(1 / (1 + np.exp(-zr)))
    g["b_win"] = invert_harville(g.b_itm.to_numpy())[0]; g["r_win"] = invert_harville(g.r_itm.to_numpy())[0]
    rows.append(g)
d = pd.concat(rows); d["yw"] = (d.off == 1) * 1.0; d["yi"] = (d.off <= 3) * 1.0
ll = lambda p, y: -(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1)))
for c, y in (("b_itm", "yi"), ("r_itm", "yi"), ("m_itm", "yi"), ("b_win", "yw"), ("r_win", "yw"), ("m_win", "yw")):
    d["ll_" + c] = ll(d[c], d[y])
rng = np.random.default_rng(7)
def ci(a, b_):
    r = d.groupby("race_id").agg(n=("yi", "size"), a=("ll_" + a, "sum"), b=("ll_" + b_, "sum")).to_numpy(); n = len(r)
    t = r.sum(0); bs = []
    for _ in range(5000):
        s = r[rng.integers(0, n, n)].sum(0); bs.append((s[1] - s[2]) / s[0])
    return round(t[1] / t[0], 5), round(t[2] / t[0], 5), round((t[1] - t[2]) / t[0], 5), np.round(np.percentile(bs, [5, 95]), 5)
print("ITM blend vs reshaped tote", ci("b_itm", "r_itm"))
print("ITM reshaped tote vs tote ", ci("r_itm", "m_itm"))
print("WIN blend vs reshaped tote", ci("b_win", "r_win"))
print("WIN reshaped tote vs tote ", ci("r_win", "m_win"))
