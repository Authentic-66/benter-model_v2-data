"""Score the off/on arms against results. Read-only on the live DB.

usage: python compare.py   (writes compare_output.txt and compare_horses.csv here)

#1 = highest P(ITM) among the horses that ran (the nightly re-rank method,
full pre-race field as logged). ITM = official finish 1-3. Log loss and Brier
are on P(ITM) over the starters. 11/04 has no results yet: history gains only.
"""
import sys, sqlite3, json
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "scripts"))
from equibase_pdf_parser import normalize_name  # noqa: E402

DATES = ["2026-10-23", "2026-10-24", "2026-10-28", "2026-10-29", "2026-10-30", "2026-11-04"]
c = sqlite3.connect(f"file:{REPO}/scripts/racing_full.db?mode=ro", uri=True)
lines = []
P = lambda *a: lines.append(" ".join(str(x) for x in a))

frames = []
for d in DATES:
    m = d[5:7] + d[8:10]
    a = pd.read_csv(HERE / f"card_{m}_off.csv", dtype={"pgm": str})
    b = pd.read_csv(HERE / f"card_{m}_on.csv", dtype={"pgm": str})
    x = a.merge(b, on=["date", "race", "pgm"], suffixes=("_off", "_on"))
    assert len(x) == len(a) == len(b), d
    x["key"] = [normalize_name(h) for h in x.horse_off]
    res = pd.read_sql_query(
        """SELECT r.race_num AS race, h.name, e.official_finish_pos AS fin, e.finish_status
           FROM entries e JOIN horses h ON h.id=e.horse_id JOIN races r ON r.id=e.race_id
           JOIN race_days rd ON rd.id=r.race_day_id JOIN tracks t ON t.id=rd.track_id
           WHERE t.code='DED' AND rd.race_date=? AND rd.source_pdf NOT LIKE 'PP-SCHEDULED%'""",
        c, params=(d,))
    res["key"] = [normalize_name(h) for h in res.name]
    x = x.merge(res[["race", "key", "fin", "finish_status"]], on=["race", "key"], how="left")
    x["ran"] = x.finish_status.notna() if len(res) else False
    x["itm"] = (x.fin <= 3).astype(float)
    frames.append(x)
X = pd.concat(frames, ignore_index=True)
X.to_csv(HERE / "compare_horses.csv", index=False)

P("History gains (PP entries whose jockey / trainer has a charted start before the card)")
P(f"{'card':10s} {'horses':>6s}  {'jky off':>7s} {'jky on':>6s}  {'trn off':>7s} {'trn on':>6s}  {'either gained':>13s}  {'#1 changed (full field)':>23s}")
tot = np.zeros(6, int)
for d, g in X.groupby("date"):
    gained = ((g.jockey_hist_on > g.jockey_hist_off) | (g.trainer_hist_on > g.trainer_hist_off)).sum()
    top_off = g.loc[g.groupby("race").p_itm_off.idxmax(), ["race", "pgm"]]
    top_on = g.loc[g.groupby("race").p_itm_on.idxmax(), ["race", "pgm"]]
    ch = int((top_off.pgm.values != top_on.pgm.values).sum())
    row = [len(g), g.jockey_hist_off.sum(), g.jockey_hist_on.sum(), g.trainer_hist_off.sum(),
           g.trainer_hist_on.sum(), gained]
    tot += np.array(row)
    P(f"{d:10s} {row[0]:6d}  {row[1]:7d} {row[2]:6d}  {row[3]:7d} {row[4]:6d}  {row[5]:13d}  {ch:>3d} of {g.race.nunique()}")
P(f"{'all':10s} {tot[0]:6d}  {tot[1]:7d} {tot[2]:6d}  {tot[3]:7d} {tot[4]:6d}  {tot[5]:13d}")
P(f"\nmean |P(ITM) on - off| = {np.abs(X.p_itm_on - X.p_itm_off).mean()*100:.2f}pp, "
  f"max {np.abs(X.p_itm_on - X.p_itm_off).max()*100:.1f}pp; base model only: "
  f"{np.abs(X.base_itm_on - X.base_itm_off).mean()*100:.2f}pp")


def card_metrics(g, arm):
    s = g[g.ran]
    p = s[f"p_itm_{arm}"].clip(1e-6, 1 - 1e-6)
    y = s.itm
    ll = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).sum())
    br = float(((p - y) ** 2).sum())
    tops = s.loc[s.groupby("race")[f"p_itm_{arm}"].idxmax()]
    return {"races": s.race.nunique(), "starters": len(s), "w": int((tops.fin == 1).sum()),
            "itm": int((tops.fin <= 3).sum()), "ll": ll, "br": br}


P("\nScored against results (starters only; #1 re-ranked among runners)")
P(f"{'card':10s} {'races':>5s} {'start':>5s} | {'#1 W off/on':>11s} {'#1 ITM off/on':>13s} | {'LL/horse off':>12s} {'on':>7s} | {'Brier/horse off':>15s} {'on':>7s}")
agg = {"off": dict(races=0, starters=0, w=0, itm=0, ll=0.0, br=0.0), "on": dict(races=0, starters=0, w=0, itm=0, ll=0.0, br=0.0)}
for d, g in X[X.ran].groupby("date"):
    mo, mn = card_metrics(g, "off"), card_metrics(g, "on")
    for k in agg["off"]:
        agg["off"][k] += mo[k]; agg["on"][k] += mn[k]
    P(f"{d:10s} {mo['races']:5d} {mo['starters']:5d} | {mo['w']:5d}/{mn['w']:<5d} {mo['itm']:7d}/{mn['itm']:<5d} | "
      f"{mo['ll']/mo['starters']:12.4f} {mn['ll']/mn['starters']:7.4f} | {mo['br']/mo['starters']:15.4f} {mn['br']/mn['starters']:7.4f}")
o, n = agg["off"], agg["on"]
P(f"{'all':10s} {o['races']:5d} {o['starters']:5d} | {o['w']:5d}/{n['w']:<5d} {o['itm']:7d}/{n['itm']:<5d} | "
  f"{o['ll']/o['starters']:12.4f} {n['ll']/n['starters']:7.4f} | {o['br']/o['starters']:15.4f} {n['br']/n['starters']:7.4f}")

# Paired race-level bootstrap of the log-loss and Brier differences (on - off)
S = X[X.ran].copy()
for arm in ("off", "on"):
    p = S[f"p_itm_{arm}"].clip(1e-6, 1 - 1e-6)
    S[f"ll_{arm}"] = -(S.itm * np.log(p) + (1 - S.itm) * np.log(1 - p))
    S[f"br_{arm}"] = (p - S.itm) ** 2
R = S.groupby(["date", "race"]).agg(dll=("ll_on", "sum"), dll0=("ll_off", "sum"),
                                     dbr=("br_on", "sum"), dbr0=("br_off", "sum"), n=("itm", "size"))
R["dll"] -= R.dll0; R["dbr"] -= R.dbr0
rng = np.random.default_rng(6001)
idx = rng.integers(0, len(R), size=(10000, len(R)))
nst = R.n.sum()
for col, lab in (("dll", "log loss"), ("dbr", "Brier")):
    v = R[col].values
    bs = v[idx].sum(1) / nst
    P(f"{lab}: on - off = {v.sum()/nst:+.4f} per starter, 95% race-bootstrap CI "
      f"[{np.percentile(bs, 2.5):+.4f}, {np.percentile(bs, 97.5):+.4f}], "
      f"races better/worse/tied = {(v < -1e-12).sum()}/{(v > 1e-12).sum()}/{(abs(v) <= 1e-12).sum()}")

# Races where the re-ranked #1 differs between arms
P("\nRaces where the #1 among runners differs (off -> on): finish of each")
for (d, rn), g in S.groupby(["date", "race"]):
    to, tn = g.loc[g.p_itm_off.idxmax()], g.loc[g.p_itm_on.idxmax()]
    if to.pgm != tn.pgm:
        P(f"  {d} R{rn}: off #{to.pgm} {to.horse_off} ({to.p_itm_off*100:.1f}, fin {to.fin:.0f}) -> "
          f"on #{tn.pgm} {tn.horse_off} ({tn.p_itm_on*100:.1f}, fin {tn.fin:.0f})")
g = X[X.date == "2026-11-04"]
P("\n11/04 (no results yet): races where #1 differs, full field")
for rn, h in g.groupby("race"):
    to, tn = h.loc[h.p_itm_off.idxmax()], h.loc[h.p_itm_on.idxmax()]
    if to.pgm != tn.pgm:
        P(f"  R{rn}: off #{to.pgm} {to.horse_off} {to.p_itm_off*100:.1f} -> on #{tn.pgm} {tn.horse_off} {tn.p_itm_on*100:.1f}")

out = "\n".join(lines)
(HERE / "compare_output.txt").write_text(out + "\n", encoding="utf-8")
print(out)
