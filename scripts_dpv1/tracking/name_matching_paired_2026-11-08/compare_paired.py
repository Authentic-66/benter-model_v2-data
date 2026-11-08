"""Paired name-matching check, DED 11/05-11/07: score the off/on arms.

usage: python compare_paired.py   (writes compare_output.txt, compare_horses.csv here)

Read-only on the live DB and logs. Same scoring as
tracking/name_matching_2026-11-04/compare.py: #1 = highest P(ITM) among the
horses that ran (nightly re-rank method), ITM = official finish 1-3, log loss
and Brier on P(ITM) over the starters. Races are identical in both arms (same
chart, same starters).

Second part: why the ON cards' log loss rose 0.622 -> 0.631 -> 0.643. Two
yardsticks that do not depend on name matching:
  * the OFF arm on the same cards (if OFF rises the same way, it is the races);
  * a market benchmark: P(ITM) from final odds (win probs = 1/(odds+1),
    normalised, Harville to top 3). If the market also did worse on these
    cards, the results were surprising, not the inputs.
The logged 1.3.2 cards 10/23-11/07 are scored the same way for context.
"""
import itertools, json, sys, sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
DPV1 = REPO / "scripts_dpv1"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "scripts"))
from equibase_pdf_parser import normalize_name  # noqa: E402

DATES = ["2026-11-05", "2026-11-06", "2026-11-07"]
c = sqlite3.connect(f"file:{REPO}/scripts/racing_full.db?mode=ro", uri=True)
lines = []
P = lambda *a: lines.append(" ".join(str(x) for x in a))


def results(d):
    res = pd.read_sql_query(
        """SELECT r.race_num AS race, h.name, e.official_finish_pos AS fin, e.finish_status
           FROM entries e JOIN horses h ON h.id=e.horse_id JOIN races r ON r.id=e.race_id
           JOIN race_days rd ON rd.id=r.race_day_id JOIN tracks t ON t.id=rd.track_id
           WHERE t.code='DED' AND rd.race_date=? AND rd.source_pdf NOT LIKE 'PP-SCHEDULED%'""",
        c, params=(d,))
    res["key"] = [normalize_name(h) for h in res.name]
    return res


# Logged record runs (scored log): final odds for every starter, and the
# logged P(ITM) for the meet context table.
SC = pd.DataFrame([json.loads(l) for l in open(DPV1 / "logs/scored_predictions.jsonl", encoding="utf-8")
                   if '"DED"' in l])
SC = SC[(SC.track == "DED") & (SC.model_version == "dpv1.3.2-5track-stretch")]
# record run = latest run per card before results (one generated_at per card in the scored log)
SC["pgm"] = SC.pgm.astype(str)

frames = []
for d in DATES:
    m = d[5:7] + d[8:10]
    a = pd.read_csv(HERE / f"card_{m}_off.csv", dtype={"pgm": str})
    b = pd.read_csv(HERE / f"card_{m}_on.csv", dtype={"pgm": str})
    x = a.merge(b, on=["date", "race", "pgm"], suffixes=("_off", "_on"))
    assert len(x) == len(a) == len(b), d
    x["key"] = [normalize_name(h) for h in x.horse_off]
    res = results(d)
    x = x.merge(res[["race", "key", "fin", "finish_status"]], on=["race", "key"], how="left")
    x["ran"] = x.finish_status.notna()
    x["itm"] = (x.fin <= 3).astype(float)
    od = SC[SC.race_date == d][["race_num", "pgm", "final_odds"]].rename(columns={"race_num": "race"})
    x = x.merge(od, on=["race", "pgm"], how="left")
    frames.append(x)
X = pd.concat(frames, ignore_index=True)


def harville_itm(pw):
    """P(top 3) per horse from win probabilities (exact Harville)."""
    n = len(pw)
    out = np.zeros(n)
    for i, j, k in itertools.permutations(range(n), 3):
        p = pw[i] * pw[j] / (1 - pw[i]) * pw[k] / (1 - pw[i] - pw[j])
        out[i] += p; out[j] += p; out[k] += p
    return out


def add_market(S):
    S = S.copy()
    S["p_mkt"] = np.nan
    for _, g in S.groupby(["date", "race"]):
        if g.final_odds.isna().any() or len(g) < 3:
            continue
        w = 1.0 / (g.final_odds.values + 1.0)
        S.loc[g.index, "p_mkt"] = harville_itm(w / w.sum())
    return S


S = add_market(X[X.ran])
X = X.merge(S[["date", "race", "pgm", "p_mkt"]], on=["date", "race", "pgm"], how="left")
X.to_csv(HERE / "compare_horses.csv", index=False)

P("History gains (PP entries whose jockey / trainer has a charted start before the card)")
P(f"{'card':10s} {'horses':>6s}  {'jky off':>7s} {'jky on':>6s}  {'trn off':>7s} {'trn on':>6s}  {'either gained':>13s}  {'#1 changed (full field)':>23s}")
for d, g in X.groupby("date"):
    gained = ((g.jockey_hist_on > g.jockey_hist_off) | (g.trainer_hist_on > g.trainer_hist_off)).sum()
    top_off = g.loc[g.groupby("race").p_itm_off.idxmax(), ["race", "pgm"]]
    top_on = g.loc[g.groupby("race").p_itm_on.idxmax(), ["race", "pgm"]]
    ch = int((top_off.pgm.values != top_on.pgm.values).sum())
    P(f"{d:10s} {len(g):6d}  {g.jockey_hist_off.sum():7d} {g.jockey_hist_on.sum():6d}  "
      f"{g.trainer_hist_off.sum():7d} {g.trainer_hist_on.sum():6d}  {gained:13d}  {ch:>3d} of {g.race.nunique()}")
P(f"\nmean |P(ITM) on - off| = {np.abs(X.p_itm_on - X.p_itm_off).mean()*100:.2f}pp, "
  f"max {np.abs(X.p_itm_on - X.p_itm_off).max()*100:.1f}pp; base model only: "
  f"{np.abs(X.base_itm_on - X.base_itm_off).mean()*100:.2f}pp")


def ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


for arm in ("off", "on", "mkt"):
    col = "p_mkt" if arm == "mkt" else f"p_itm_{arm}"
    S[f"ll_{arm}"] = ll(S[col], S.itm)
    S[f"br_{arm}"] = (S[col] - S.itm) ** 2


def tops(g, col):
    return g.loc[g.groupby(["date", "race"])[col].idxmax()]


P("\nScored against results (starters only; #1 re-ranked among runners; identical races in both arms)")
P(f"{'card':10s} {'races':>5s} {'start':>5s} | {'#1 W off/on':>11s} {'#1 ITM off/on':>13s} | "
  f"{'LL/start off':>12s} {'on':>7s} {'on-off':>7s} | {'Brier off':>9s} {'on':>7s} {'on-off':>7s}")
for d, g in list(S.groupby("date")) + [("all", S)]:
    to, tn = tops(g, "p_itm_off"), tops(g, "p_itm_on")
    n = len(g)
    P(f"{d:10s} {g.groupby(['date','race']).ngroups:5d} {n:5d} | {int((to.fin==1).sum()):5d}/{int((tn.fin==1).sum()):<5d} "
      f"{int((to.fin<=3).sum()):7d}/{int((tn.fin<=3).sum()):<5d} | {g.ll_off.mean():12.4f} {g.ll_on.mean():7.4f} "
      f"{g.ll_on.mean()-g.ll_off.mean():+7.4f} | {g.br_off.mean():9.4f} {g.br_on.mean():7.4f} {g.br_on.mean()-g.br_off.mean():+7.4f}")

R = S.groupby(["date", "race"]).agg(on=("ll_on", "sum"), off=("ll_off", "sum"),
                                     bon=("br_on", "sum"), boff=("br_off", "sum"), n=("itm", "size"))
rng = np.random.default_rng(6001)
idx = rng.integers(0, len(R), size=(10000, len(R)))
nst = R.n.sum()
for a, b, lab in (("on", "off", "log loss"), ("bon", "boff", "Brier")):
    v = (R[a] - R[b]).values
    bs = v[idx].sum(1) / nst
    P(f"{lab}: on - off = {v.sum()/nst:+.4f} per starter, 95% race-bootstrap CI "
      f"[{np.percentile(bs, 2.5):+.4f}, {np.percentile(bs, 97.5):+.4f}], "
      f"races better/worse/tied = {(v < -1e-12).sum()}/{(v > 1e-12).sum()}/{(abs(v) <= 1e-12).sum()}")

P("\nRaces where the #1 among runners differs (off -> on): finish and final odds of each")
for (d, rn), g in S.groupby(["date", "race"]):
    to, tn = g.loc[g.p_itm_off.idxmax()], g.loc[g.p_itm_on.idxmax()]
    if to.pgm != tn.pgm:
        P(f"  {d} R{rn}: off #{to.pgm} {to.horse_off} ({to.p_itm_off*100:.1f}, fin {to.fin:.0f}, {to.final_odds:.1f}-1) -> "
          f"on #{tn.pgm} {tn.horse_off} ({tn.p_itm_on*100:.1f}, fin {tn.fin:.0f}, {tn.final_odds:.1f}-1)")

# ---- Why did ON log loss rise? ----
P("\nWhy the ON cards' log loss rose: the same cards under OFF and under the market")
P(f"{'card':10s} {'LL on':>7s} {'LL off':>7s} {'LL mkt':>7s} | {'ITM fin. median odds':>20s} {'ITM at 10-1+':>12s} {'winners 10-1+':>13s} {'P(ITM) on of ITM fin.':>22s}")
for d, g in S.groupby("date"):
    it = g[g.itm == 1]
    w = g[g.fin == 1]
    P(f"{d:10s} {g.ll_on.mean():7.4f} {g.ll_off.mean():7.4f} {g.ll_mkt.mean():7.4f} | "
      f"{it.final_odds.median():20.1f} {int((it.final_odds >= 10).sum()):5d} of {len(it):<4d} "
      f"{int((w.final_odds >= 10).sum()):6d} of {len(w):<4d} {it.p_itm_on.mean():22.3f}")

# Context: every logged 1.3.2 DED card, scored the same way (logged P(ITM)).
L = SC[SC.finish_status.notna()].copy()   # starters (finished or DNF; DNF = not ITM)
L["itm"] = (L.actual_finish <= 3).astype(float)
L["date"], L["race"] = L.race_date, L.race_num
L = add_market(L.assign(fin=L.actual_finish))
L["ll"] = ll(L.final_p_itm, L.itm)
L["llm"] = ll(L.p_mkt, L.itm)
P("\nContext: logged 1.3.2 DED cards (record runs, logged P(ITM)), same scoring")
P(f"{'card':10s} {'NM':>3s} {'start':>5s} {'LL model':>8s} {'LL mkt':>7s} {'model-mkt':>9s} {'ITM 10-1+':>9s}")
for d, g in L.groupby("date"):
    nm = (g.name_matching.fillna("off").iloc[0])
    it = g[g.itm == 1]
    P(f"{d:10s} {nm:>3s} {len(g):5d} {g.ll.mean():8.4f} {g.llm.mean():7.4f} {g.ll.mean()-g.llm.mean():+9.4f} "
      f"{int((it.final_odds >= 10).sum()):4d} of {len(it)}")
for nm, g in L.groupby(L.name_matching.fillna("off")):
    P(f"  pooled NM {nm}: {g.date.nunique()} cards, {len(g)} starters, LL model {g.ll.mean():.4f}, "
      f"LL mkt {g.llm.mean():.4f}, model-mkt {g.ll.mean()-g.llm.mean():+.4f}")

# Where the extra loss sits: by final-odds band (logged record runs).
L["band"] = pd.cut(L.final_odds, [-1, 2.999, 9.999, 1e9], labels=["under 3-1", "3-1 to 9-1", "10-1 up"])
L["grp"] = np.where(L.name_matching.fillna("off") == "on", "11/05-11/07 ON", "10/22-11/04 OFF")
P("\nLog loss per starter by final-odds band (logged record runs; model vs market)")
P(f"{'group':15s} {'band':11s} {'start':>5s} {'ITM%':>6s} {'mean P(ITM)':>11s} {'LL model':>8s} {'LL mkt':>7s}")
for (g, b), x in L.groupby(["grp", "band"], observed=True):
    P(f"{g:15s} {str(b):11s} {len(x):5d} {x.itm.mean()*100:6.1f} {x.final_p_itm.mean():11.3f} "
      f"{x.ll.mean():8.4f} {x.llm.mean():7.4f}")
for d, x in L[L.grp == "11/05-11/07 ON"].groupby("date"):
    f = x[x.band == "under 3-1"]
    P(f"  {d}: under-3-1 starters {len(f)}, ITM {int(f.itm.sum())} ({f.itm.mean()*100:.0f}%), "
      f"model mean P(ITM) {f.final_p_itm.mean():.3f}, LL {f.ll.mean():.4f} vs market {f.llm.mean():.4f}")

out = "\n".join(lines)
(HERE / "compare_output.txt").write_text(out + "\n", encoding="utf-8")
print(out)
