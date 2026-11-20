"""Overlay test, step 2b: pre-registered rules A and B on rerun_rows.csv (and on the logged DED
pre-race predictions as a cross-check). Final tote odds + chart payouts only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"D:\Benter Model_v2 Data\benter-model_v2-data")
sys.path.insert(0, str(ROOT / "scripts_dpv1"))
import logging; logging.disable(logging.WARNING)
from dpv1_runtime import harville_itm, normalise_itm, invert_harville
HERE = Path(sys.argv[1])  # scratch work dir (holds racing_scratch.db = byte copy of the live DB)
RNG = np.random.default_rng(20261120); NB = 5000


def market(df):
    out = []
    for rid, g in df.groupby("race_id", sort=False):
        g = g.copy()
        ok = (g.non_betting == 0) & g.odds.notna() & (g.odds > 0)
        raw = np.where(ok, 1.0 / (g.odds.fillna(0) + 1.0), 0.0)
        w = raw / raw[ok].sum()
        g["m_win"] = np.where(ok, w, np.nan)
        mi = np.full(len(g), np.nan); mi[ok.to_numpy()] = harville_itm(w[ok.to_numpy()])
        g["m_itm"] = mi
        g["bettable"] = ok
        g["model_rank"] = g.p_itm.rank(ascending=False, method="first")
        itm = g[g.off.notna() & (g.off <= 3)]
        g["show_ok"] = bool(len(itm)) and itm.show_pay.notna().all()
        win = g[g.off == 1]
        g["win_ok"] = bool(len(win)) and win.win_pay.notna().all()
        out.append(g)
    return pd.concat(out)


def stats(b, pay_col, label):
    """b: bet rows (one $2 bet each). Cluster bootstrap by race."""
    n = len(b)
    if n == 0:
        return dict(label=label, bets=0)
    ret = b[pay_col].fillna(0).to_numpy()
    hit = (ret > 0)
    staked = 2.0 * n; returned = ret.sum()
    races = b.race_id.to_numpy(); u, inv = np.unique(races, return_inverse=True)
    rs = np.bincount(inv, weights=ret); rn = np.bincount(inv)
    roi = []
    for _ in range(NB):
        k = RNG.integers(0, len(u), len(u))
        roi.append(rs[k].sum() / (2.0 * rn[k].sum()) - 1)
    lo, hi = np.percentile(roi, [5, 95])
    return dict(label=label, bets=n, races=len(u), hits=int(hit.sum()), hit_rate=hit.mean(), staked=staked,
                returned=round(returned, 2), roi=returned / staked - 1, lo=lo, hi=hi,
                exp_hits=None)


def run(df, tag):
    df = market(df)
    df["shipper"] = np.where(df.no_data_shipper == 1, "no-data shipper", "rest")
    df["maiden"] = np.where(df.race_type.fillna("").str.upper().str.startswith("MAIDEN"), "maiden", "non-maiden")
    S = df[df.bettable & df.show_ok]          # show universe
    W = df[df.bettable & df.win_ok]           # win universe
    A = S[(S.p_itm > 0.25) & (S.m_itm < 0.20)]
    A3 = A[A.model_rank >= 4]
    B = W[(W.p_win >= 1.2 * W.m_win) & (W.p_win >= 0.10)]
    res = {"tag": tag, "universe": dict(races=int(df.race_id.nunique()), starters=len(df),
           show_races=int(S.race_id.nunique()), win_races=int(W.race_id.nunique()),
           excluded_show=sorted(set(map(tuple, df.loc[~df.show_ok, ["track", "race_date", "race_num"]].drop_duplicates().values.tolist())))[:0],
           n_excl_show=int(df.loc[~df.show_ok, "race_id"].nunique()), n_excl_win=int(df.loc[~df.win_ok, "race_id"].nunique()))}
    lines = {}
    def block(name, bets, pay, base, extra=None):
        out = {"all": stats(bets, pay, "all"), "base_all": stats(base, pay, "all")}
        # model / market expectation for hits
        pcol, mcol = ("p_itm_norm", "m_itm") if pay == "show_pay" else ("p_win", "m_win")
        out["all"]["exp_model"] = float(bets[pcol].sum()); out["all"]["exp_market"] = float(bets[mcol].sum())
        for col in ("track", "maiden", "shipper"):
            for k in sorted(df[col].unique()):
                out[f"{col}:{k}"] = stats(bets[bets[col] == k], pay, k)
                out[f"base_{col}:{k}"] = stats(base[base[col] == k], pay, k)
        lines[name] = out
    block("A", A, "show_pay", S)
    block("A_rank4plus", A3, "show_pay", S)
    block("B", B, "win_pay", W)
    res["lines"] = lines
    # who qualifies: odds profile
    res["A_odds"] = A.odds.describe().round(2).to_dict(); res["B_odds"] = B.odds.describe().round(2).to_dict()
    res["A_list_tracks"] = A.track.value_counts().to_dict(); res["B_list_tracks"] = B.track.value_counts().to_dict()
    # calibration of the model vs market among bets
    res["B_mean_pwin_model"] = float(B.p_win.mean()) if len(B) else None
    res["B_mean_pwin_market"] = float(B.m_win.mean()) if len(B) else None
    res["A_mean_pitm_model_norm"] = float(A.p_itm_norm.mean()) if len(A) else None
    res["A_mean_pitm_market"] = float(A.m_itm.mean()) if len(A) else None
    # whole-universe log-loss of win prob: model vs market (sanity: does model beat the tote at all?)
    w = W.copy(); y = (w.off == 1).astype(float)
    for c in ("p_win", "m_win"):
        p = w[c].clip(1e-6, 1 - 1e-6); res[f"win_logloss_{c}"] = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    s = S.copy(); y = (s.off <= 3).astype(float)
    for c in ("p_itm_norm", "m_itm"):
        p = s[c].clip(1e-6, 1 - 1e-6); res[f"itm_logloss_{c}"] = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    df.to_csv(HERE / f"scored_{tag}.csv", index=False)
    return res


rr = pd.read_csv(HERE / "rerun_rows.csv")
R = {"rerun": run(rr, "rerun")}

# ---- cross-check: logged pre-race DED predictions on 1.3.2 (record run per race) ----
best = {}
for l in open(ROOT / "scripts_dpv1/logs/predictions.jsonl", encoding="utf-8"):
    r = json.loads(l)
    if r["track"] != "DED" or not r["model_version"].startswith("dpv1.3.2"): continue
    k = (r["race_date"], r["race_num"])
    if k not in best or r["generated_at"] > best[k][0]: best[k] = (r["generated_at"], {})
    if r["generated_at"] == best[k][0]: best[k][1][str(r["pgm"])] = r["p_itm"]
ded = rr[rr.track == "DED"].copy()
ded["key"] = list(zip(ded.race_date, ded.race_num))
ded = ded[ded.key.isin(best)].copy()
ded["p_itm"] = [best[k][1].get(p, np.nan) for k, p in zip(ded.key, ded.pgm.astype(str))]
miss = int(ded.p_itm.isna().sum())
ded = ded[ded.race_id.isin(ded.groupby("race_id").p_itm.apply(lambda s: s.notna().all()).pipe(lambda s: s[s].index))]
out = []
for rid, g in ded.groupby("race_id"):
    g = g.copy(); pn = normalise_itm(g.p_itm.to_numpy()); pw, _ = invert_harville(pn)
    g["p_itm_norm"] = pn; g["p_win"] = pw; out.append(g)
ded = pd.concat(out)
R["logged_ded"] = run(ded.drop(columns="key"), "logged_ded")
R["logged_ded"]["runners_without_logged_p"] = miss
# agreement rerun vs logged on DED
a = rr.merge(ded[["entry_id", "p_itm"]], on="entry_id", suffixes=("", "_logged"))
R["ded_agreement"] = dict(rows=len(a), corr=float(np.corrcoef(a.p_itm, a.p_itm_logged)[0, 1]),
                          mean_abs_diff=float((a.p_itm - a.p_itm_logged).abs().mean()),
                          top1_same=float(a.groupby("race_id").apply(lambda g: g.p_itm.idxmax() == g.p_itm_logged.idxmax()).mean()))
json.dump(R, open(HERE / "results.json", "w"), indent=1, default=float)


def show(res):
    print("=====", res["tag"], res["universe"])
    for ln, out in res["lines"].items():
        print("--", ln)
        for k, v in out.items():
            if v.get("bets"):
                print(f"  {k:28s} bets {v['bets']:5d} hits {v['hits']:5d} ({v['hit_rate']:.1%}) ${v['staked']:.0f} -> ${v['returned']:.2f} "
                      f"ROI {v['roi']:+.1%} [{v['lo']:+.1%}, {v['hi']:+.1%}]" + (f" exp model {v['exp_model']:.1f} market {v['exp_market']:.1f}" if 'exp_model' in v else ""))
            else:
                print(f"  {k:28s} none")
    for k in res:
        if k not in ("lines", "universe", "tag"): print(" ", k, res[k])


for k in ("rerun", "logged_ded"): show(R[k])
print(R["ded_agreement"])
