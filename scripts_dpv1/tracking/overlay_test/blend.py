"""Overlay test part 2: shipped blend vs tote-only, same 1,055 OOS races (scored_rerun.csv)."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"D:\Benter Model_v2 Data\benter-model_v2-data")
sys.path.insert(0, str(ROOT / "scripts_dpv1"))
import logging; logging.disable(logging.WARNING)
from dpv1_runtime import load_model, normalise_itm, invert_harville
HERE = Path(sys.argv[1])  # scratch work dir with scored_rerun.csv (from analyse.py)
m = load_model(ROOT / "scripts_dpv1" / "dpv1.pkl"); b = m.blend
print("blend", b.alpha_, b.beta_, b.gamma_)
d = pd.read_csv(HERE / "scored_rerun.csv")
lg = lambda p: np.log(np.clip(p, 1e-9, 1 - 1e-9) / (1 - np.clip(p, 1e-9, 1 - 1e-9)))
d["b_itm_raw"] = 1 / (1 + np.exp(-(b.alpha_ * lg(d.p_fund) + b.beta_ * lg(d.m_itm) + b.gamma_)))
out = []
for rid, g in d.groupby("race_id", sort=False):
    g = g.copy(); pn = normalise_itm(g.b_itm_raw.to_numpy()); pw, _ = invert_harville(pn)
    g["b_itm"] = pn; g["b_win"] = pw; out.append(g)
d = pd.concat(out)
d["y_win"] = (d.off == 1).astype(float); d["y_itm"] = (d.off <= 3).astype(float)
def ll(p, y): p = np.clip(p, 1e-9, 1 - 1e-9); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
for t in ("win", "itm"):
    d[f"llb_{t}"] = ll(d[f"b_{t}"], d[f"y_{t}"]); d[f"llm_{t}"] = ll(d[f"m_{t}"], d[f"y_{t}"])
d["llbr_itm"] = ll(d.b_itm_raw, d.y_itm)
rng = np.random.default_rng(20261120); NB = 5000
def boot(g):
    r = g.groupby("race_id").agg(n=("y_win", "size"), bw=("llb_win", "sum"), mw=("llm_win", "sum"), bi=("llb_itm", "sum"), mi=("llm_itm", "sum"))
    a = r.to_numpy(); n = len(a); res = {}
    tot = a.sum(0)
    res["races"] = n; res["starters"] = int(tot[0])
    for k, (ib, im) in {"win": (1, 2), "itm": (3, 4)}.items():
        diffs = []
        for _ in range(NB):
            s = a[rng.integers(0, n, n)].sum(0); diffs.append((s[ib] - s[im]) / s[0])
        res[k] = dict(blend=tot[ib] / tot[0], tote=tot[im] / tot[0], diff=(tot[ib] - tot[im]) / tot[0],
                      lo=float(np.percentile(diffs, 5)), hi=float(np.percentile(diffs, 95)),
                      share_better=float(np.mean(np.array(diffs) < 0)))
    return res
R = {"all": boot(d)}
for t in sorted(d.track.unique()): R[t] = boot(d[d.track == t])
R["itm_raw_blend_ll"] = float(d.llbr_itm.mean())
for k, v in R.items():
    if isinstance(v, dict):
        print(k, v["races"], {t: {x: round(y, 5) for x, y in v[t].items()} for t in ("win", "itm")})
print("raw blend itm ll", R["itm_raw_blend_ll"], "normalised", d.llb_itm.mean(), "tote", d.llm_itm.mean())
# Rules with blend probabilities
def stats(bt, pay):
    n = len(bt); ret = bt[pay].fillna(0).to_numpy(); u, inv = np.unique(bt.race_id, return_inverse=True)
    rs = np.bincount(inv, weights=ret); rn = np.bincount(inv); roi = []
    for _ in range(NB):
        k = rng.integers(0, len(u), len(u)); roi.append(rs[k].sum() / (2 * rn[k].sum()) - 1)
    return dict(bets=n, races=len(u), hits=int((ret > 0).sum()), staked=2 * n, returned=round(float(ret.sum()), 2),
                roi=float(ret.sum() / (2 * n) - 1), lo=float(np.percentile(roi, 5)), hi=float(np.percentile(roi, 95)))
S = d[d.bettable & d.show_ok]; W = d[d.bettable & d.win_ok]
A = S[(S.b_itm_raw > .25) & (S.m_itm < .20)]; A3 = A[A.b_itm_raw.groupby(A.race_id).rank(ascending=False) >= 0]  # placeholder
S2 = S.assign(br=S.groupby("race_id").b_itm_raw.rank(ascending=False, method="first")); A3 = S2[(S2.b_itm_raw > .25) & (S2.m_itm < .20) & (S2.br >= 4)]
B = W[(W.b_win >= 1.2 * W.m_win) & (W.b_win >= .10)]
R["rules"] = {"A": stats(A, "show_pay") | dict(exp_blend=float(A.b_itm.sum()), exp_tote=float(A.m_itm.sum())),
              "A_rank4": stats(A3, "show_pay") if len(A3) else dict(bets=0),
              "B": stats(B, "win_pay") | dict(exp_blend=float(B.b_win.sum()), exp_tote=float(B.m_win.sum())),
              "B_track": {t: stats(B[B.track == t], "win_pay") for t in sorted(B.track.unique())},
              "A_track": {t: stats(A[A.track == t], "show_pay") for t in sorted(A.track.unique())},
              "A_odds": A.odds.describe().round(1).to_dict(), "B_odds": B.odds.describe().round(1).to_dict(),
              "B_ratio_med": float((B.b_win / B.m_win).median()) if len(B) else None,
              "max_blend_over_tote_win": float((W.b_win / W.m_win).max())}
print(json.dumps(R["rules"], indent=1, default=float))
json.dump(R, open(HERE / "blend_results.json", "w"), indent=1, default=float)
