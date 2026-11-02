"""Combine paired-comparison checkpoints. usage: python analyze2.py <out.txt>"""
import json, sys
from math import comb
from pathlib import Path
import numpy as np
import pandas as pd

CK = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data/scripts_dpv1/tracking/paired_2026-11-01")
CARDS = ["1023", "1024", "1028", "1029", "1030"]
ARMS = {"A": ("1.3.0", True), "A0": ("1.3.0", False), "B": ("1.3.2", True), "C": ("1.3.2", False)}
LABEL = {"A": "1.3.0 + reranker", "A0": "1.3.0, no reranker",
         "B": "1.3.2 + reranker (live)", "C": "1.3.2, no reranker"}
METHODS = {"drop": "drop scratches, then score", "rerank": "re-rank pre-race order"}
EPS = 1e-6
rng = np.random.default_rng(20261101)
L = []; P = L.append

arms = pd.concat([pd.read_csv(CK / f"card_{c}.csv", dtype={"pgm": str, "program_num": str}) for c in CARDS])
metas = {c: json.loads((CK / f"card_{c}_meta.json").read_text()) for c in CARDS}
EX = {(metas[c]["date"], int(r)): v for c in CARDS for r, v in metas[c]["exacta"].items()}
arms["y_win"] = (arms.official_finish_pos == 1).astype(int)
arms["y_itm"] = (arms.official_finish_pos <= 3).astype(int)


def field_probs(g, method):
    """Return a frame of runners with p_win / p_itm used for calibration."""
    g = g.copy()
    if method == "rerank":
        g = g[~g.scratched]
        n = len(g)
        g["p_win"] = g.p_win / g.p_win.sum()
        k = min(3, n)
        g["p_itm"] = (g.p_itm * k / g.p_itm.sum()).clip(upper=0.999)
    return g


def race_rows(sub, method):
    out = []
    for (d, rn), g in sub.groupby(["date", "race"]):
        g = field_probs(g, method).sort_values(["p_itm", "p_win"], ascending=False)
        top = g.iloc[0]; top2 = set(g.pgm.iloc[:2])
        ex = EX.get((d, rn))
        ex_hit = bool(ex) and set(ex["numbers"].split("-")) == top2
        pw = g.p_win.clip(EPS, 1 - EPS); pi = g.p_itm.clip(EPS, 1 - EPS)
        out.append({"date": d, "race": rn, "n": len(g), "pick": top.pgm, "horse": top.horse,
                    "fin": top.official_finish_pos, "odds": top.final_odds,
                    "win": int(top.y_win), "itm": int(top.y_itm),
                    "win_ret": float(top.win_payout) if top.y_win else 0.0,
                    "show_ret": float(top.show_payout) if top.y_itm and pd.notna(top.show_payout) else 0.0,
                    "overlap": int(g.iloc[:3].y_itm.sum()), "ex_hit": int(ex_hit),
                    "ex_ret": ex["per_dollar"] if ex_hit else 0.0,
                    "ll_win": float(-(g.y_win * np.log(pw) + (1 - g.y_win) * np.log(1 - pw)).sum()),
                    "br_win": float(((g.p_win - g.y_win) ** 2).sum()),
                    "ll_itm": float(-(g.y_itm * np.log(pi) + (1 - g.y_itm) * np.log(1 - pi)).sum()),
                    "br_itm": float(((g.p_itm - g.y_itm) ** 2).sum()),
                    "ll_winner": float(-np.log(max(g.loc[g.y_win == 1, "p_win"].sum(), EPS)))})
    return pd.DataFrame(out)


def summ(df, nh):
    n = len(df)
    return {"races": n, "#1 W": int(df.win.sum()), "#1 ITM": int(df.itm.sum()),
            "$2 win ROI": f"{(df.win_ret.sum() - 2*n) / (2*n):+.1%}",
            "$2 show ROI": f"{(df.show_ret.sum() - 2*n) / (2*n):+.1%}",
            "top-3 overlap": f"{int(df.overlap.sum())}/{3*n}",
            "exacta box hits": int(df.ex_hit.sum()),
            "$1 exacta box ROI": f"{(df.ex_ret.sum() - 2*n) / (2*n):+.1%}",
            "LL win": round(df.ll_win.sum() / nh, 4), "Brier win": round(df.br_win.sum() / nh, 4),
            "LL ITM": round(df.ll_itm.sum() / nh, 4), "Brier ITM": round(df.br_itm.sum() / nh, 4),
            "winner -log p": round(df.ll_winner.mean(), 3)}


def mcnemar(a, b):
    n = a + b
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(min(a, b) + 1)) / 2 ** n)


def boot(x, B=20000):
    x = np.asarray(x, float)
    s = x[rng.integers(0, len(x), (B, len(x)))].mean(1)
    return np.percentile(s, [2.5, 97.5])


starters = arms[(arms.field == "post")].drop_duplicates(["date", "race", "pgm"])
NH = len(starters)
R = {}
for meth in METHODS:
    fld = "post" if meth == "drop" else "full"
    for a, (mo, rr) in ARMS.items():
        R[(meth, a)] = race_rows(arms[(arms.field == fld) & (arms.model == mo) & (arms.reranker == rr)], meth)

# market reference
mk = starters.copy()
mk["q"] = 1 / (mk.final_odds + 1); mk["q"] = mk.q / mk.groupby(["date", "race"]).q.transform("sum")
mk_ll = float(-(mk.y_win * np.log(mk.q) + (1 - mk.y_win) * np.log(1 - mk.q)).sum() / NH)
mk_br = float(((mk.q - mk.y_win) ** 2).sum() / NH)
mk_w = float(-np.log(mk.loc[mk.y_win == 1].q).mean())
fav = starters.sort_values("final_odds").groupby(["date", "race"]).first()
P(f"SAMPLE: {len(fav)} races, {NH} starters, 5 cards")
P(f"MARKET: P(win) from final odds: LL win {mk_ll:.4f}, Brier win {mk_br:.4f}, winner -log p {mk_w:.3f}; "
  f"post-time favourite {int(fav.y_win.sum())}W {int(fav.y_itm.sum())}ITM, "
  f"$2 win ROI {(fav.win_payout.fillna(0)[fav.y_win==1].sum() - 2*len(fav)) / (2*len(fav)):+.1%}, "
  f"$2 show ROI {(fav.show_payout.fillna(0)[fav.y_itm==1].sum() - 2*len(fav)) / (2*len(fav)):+.1%}")

for meth, mlab in METHODS.items():
    P(f"\n=== OVERALL, method: {mlab}")
    P(pd.DataFrame({LABEL[a]: summ(R[(meth, a)], NH) for a in ARMS}).T.to_string())

P("\n=== PER CARD (drop method; re-rank method in brackets for #1 W/ITM)")
for c in CARDS:
    d = metas[c]["date"]; nh = int((starters.date == d).sum())
    t = {}
    for a in ARMS:
        s = summ(R[("drop", a)][R[("drop", a)].date == d], nh)
        rr_ = R[("rerank", a)][R[("rerank", a)].date == d]
        s["re-rank W/ITM"] = f"{int(rr_.win.sum())}/{int(rr_.itm.sum())}"
        t[LABEL[a]] = s
    P(f"\n--- {d} ({metas[c]['races']} races, {nh} starters)")
    P(pd.DataFrame(t).T[["#1 W", "#1 ITM", "re-rank W/ITM", "$2 win ROI", "$2 show ROI", "top-3 overlap",
                         "exacta box hits", "LL win", "Brier win", "LL ITM", "Brier ITM"]].to_string())

PAIRS = [("B", "C", "reranker on 1.3.2"), ("B", "A", "1.3.2 vs 1.3.0, both with reranker"),
         ("C", "A", "1.3.2 no reranker vs 1.3.0 with reranker"), ("A", "A0", "reranker on 1.3.0"),
         ("C", "A0", "1.3.2 vs 1.3.0, both without reranker")]
for meth, mlab in METHODS.items():
    P(f"\n=== PAIRED DIFFERENCES, method: {mlab} (first minus second; 95% bootstrap CI over races)")
    for a, b, lab in PAIRS:
        x = R[(meth, a)].set_index(["date", "race"]); y = R[(meth, b)].set_index(["date", "race"])
        P(f"\n{a} - {b}  ({lab})")
        for col, nm in [("itm", "#1 ITM"), ("win", "#1 win")]:
            aw = int(((x[col] == 1) & (y[col] == 0)).sum()); bw = int(((x[col] == 0) & (y[col] == 1)).sum())
            P(f"  {nm}: {a} only {aw}, {b} only {bw}  (exact McNemar p={mcnemar(aw, bw):.2f})")
        for col, nm in [("win_ret", "$2 win return per race"), ("show_ret", "$2 show return per race"),
                        ("ex_ret", "$1 exacta box return per race")]:
            dd = (x[col] - y[col]).to_numpy(); lo, hi = boot(dd)
            P(f"  {nm}: {dd.mean():+.2f}  [{lo:+.2f}, {hi:+.2f}]")
        for col, nm in [("ll_win", "LL win"), ("br_win", "Brier win"), ("ll_itm", "LL ITM"), ("br_itm", "Brier ITM")]:
            dd = (x[col] - y[col]).to_numpy() * len(x) / NH; lo, hi = boot(dd * 1.0)
            # per-starter mean difference: scale race sums by races/starters
            P(f"  {nm} per starter: {dd.mean():+.4f}  [{lo:+.4f}, {hi:+.4f}]  (negative = {a} better)")

P("\n=== #1 DISAGREEMENTS, drop method")
for a, b, lab in PAIRS[:4]:
    x = R[("drop", a)].set_index(["date", "race"]); y = R[("drop", b)].set_index(["date", "race"])
    dis = x.index[x.pick != y.pick]
    P(f"\n{a} vs {b} ({lab}): {len(dis)} of {len(x)} races")
    f = lambda s, k: f"#{s.loc[k,'pick']} {str(s.loc[k,'horse'])[:18]} {s.loc[k,'odds']:.1f}-1 fin {int(s.loc[k,'fin']) if pd.notna(s.loc[k,'fin']) else 'DNF'}"
    for k in dis:
        P(f"  {k[0][5:]} R{k[1]}: {a} {f(x, k)} | {b} {f(y, k)}")
    if len(dis):
        n = len(dis); xs, ys = x.loc[dis], y.loc[dis]
        for nm, s in ((a, xs), (b, ys)):
            P(f"  {nm}: {int(s.win.sum())}W {int(s.itm.sum())}ITM, $2 win returned ${s.win_ret.sum():.2f}, "
              f"$2 show returned ${s.show_ret.sum():.2f} (staked ${2*n} each)")
        aw = int(((xs.itm == 1) & (ys.itm == 0)).sum()); bw = int(((xs.itm == 0) & (ys.itm == 1)).sum())
        P(f"  ITM head-to-head: {a} only {aw}, {b} only {bw}, both {int(((xs.itm==1)&(ys.itm==1)).sum())}, neither {int(((xs.itm==0)&(ys.itm==0)).sum())}")

P("\n=== METHOD AGREEMENT: #1 under drop vs re-rank")
for a in ARMS:
    x = R[("drop", a)].set_index(["date", "race"]).pick; y = R[("rerank", a)].set_index(["date", "race"]).pick
    dif = list(x.index[x != y])
    P(f"  {a}: same #1 in {int((x == y).sum())}/{len(x)}; differ {[f'{k[0][5:]} R{k[1]}' for k in dif]}")

P("\n=== REPRODUCTION")
for c in CARDS:
    m = metas[c]
    P(f"  {m['date']}: {m['backup']} sha {m['backup_sha256'][:12]}, PP {m['pp_file']}, rebuilt {m['rebuilt_feature_rows']} rows, "
      f"record {m['record_run']}: {m['reproduction']}, live DB unchanged {m['live_db_sha_unchanged']}")

for k, v in R.items():
    v.to_csv(CK.parent / "paired_2026-11-01" / f"races_{k[0]}_{k[1]}.csv", index=False)
Path(sys.argv[1]).write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
