"""Compare the base / line / full arms for one card (read-only)."""
import json, math, sqlite3, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
REPO = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
D, M = "2026-11-04", "1104"
T = [t for t in json.load(open(HERE / "targets.json")) if t["date"] == D and t["horse"] != "Daddy's Code"]
TK = {(t["race"], str(t["pgm"])) for t in T}

c = sqlite3.connect(f"file:{REPO}/scripts/racing_full.db?mode=ro", uri=True)
res = pd.read_sql_query("""select r.race_num race, e.program_num pgm, e.official_finish_pos fin, e.finish_status st, e.final_odds odds
  from entries e join races r on r.id=e.race_id join race_days d on d.id=r.race_day_id join tracks t on t.id=d.track_id
  where t.code='DED' and d.race_date=?""", c, params=(D,))
res["pgm"] = res.pgm.astype(str)
res["itm"] = res.fin.fillna(99) <= 3

S = {a: pd.read_csv(HERE / f"arm_{M}_{a}_scores.csv", dtype={"pgm": str}) for a in ("base", "line", "full")}
F = {a: pd.read_csv(HERE / f"arm_{M}_{a}_features.csv", dtype={"pgm": str}, low_memory=False) for a in ("base", "line", "full")}

# logged record run, for reference
lg = [json.loads(l) for l in open(REPO / "scripts_dpv1/logs/predictions.jsonl", encoding="utf-8") if '"DED"' in l and D in l]
lg = pd.DataFrame([r for r in lg if r["race_date"] == D and r["generated_at"] == "2026-11-04T10:14:46"])
lg["pgm"] = lg.pgm.astype(str)
b = S["base"].merge(lg, left_on=["race", "pgm"], right_on=["race_num", "pgm"])
print(f"base arm vs logged record run: {len(b)} rows, max |dP(ITM)| {np.abs(b.p_itm_x - b.p_itm_y).max():.4f}, "
      f"#1 differs in {sum(1 for r, g in b.groupby('race') if g.p_itm_x.idxmax() != g.p_itm_y.idxmax())} races (pars frozen in the arms; the logged run recomputed them)")

def score(df, label, keys=None):
    x = df.merge(res, on=["race", "pgm"])
    x = x[x.st.isin(["finished", "DNF"])]
    if keys is not None:
        x = x[[(r, p) in keys for r, p in zip(x.race, x.pgm)]]
    eps = 1e-6
    ll = -np.mean([math.log(max(eps, p)) if y else math.log(max(eps, 1 - p)) for p, y in zip(x.p_itm, x.itm)])
    br = np.mean([(p - y) ** 2 for p, y in zip(x.p_itm, x.itm)])
    return dict(arm=label, n=len(x), sumP=round(x.p_itm.sum(), 2), itm=int(x.itm.sum()), ll=round(ll, 4), brier=round(br, 4))

print("\n== the 20 tested starters (+ all starters on the card)")
for a in S:
    print(score(S[a], a, TK), "| card:", score(S[a], a))
print("\n== #1 among runners per race")
for a in S:
    x = S[a].merge(res, on=["race", "pgm"]); x = x[x.st.isin(["finished", "DNF"])]
    tops = x.loc[x.groupby("race").p_itm.idxmax()]
    print(a, "W", int((tops.fin == 1).sum()), "ITM", int(tops.itm.sum()), "of", len(tops), "| #1s:", " ".join(f"R{r}#{p}" for r, p in zip(tops.race, tops.pgm)))

print("\n== per tested horse: P(ITM) base -> line -> full, coverage, finish")
m = S["base"].merge(S["line"], on=["race", "pgm", "horse"], suffixes=("_b", "_l")).merge(S["full"].rename(columns={"p_itm": "p_itm_f", "cov": "cov_f", "p_win": "p_win_f", "base_itm": "base_itm_f"}), on=["race", "pgm", "horse"])
m = m.merge(res, on=["race", "pgm"])
for _, r in m.iterrows():
    if (r.race, r.pgm) in TK:
        print(f"R{r.race} #{r.pgm:<3} {r.horse[:20]:<20} {r.p_itm_b:.3f} -> {r.p_itm_l:.3f} -> {r.p_itm_f:.3f}  cov {r.cov_b:.0f}->{r.cov_l:.0f}->{r.cov_f:.0f}  fin {r.fin} ({r.st}) odds {r.odds}")
others = m[[(r, p) not in TK for r, p in zip(m.race, m.pgm)]]
print("other starters: max |dP| line-base", round(float((others.p_itm_l - others.p_itm_b).abs().max()), 4),
      "full-base", round(float((others.p_itm_f - others.p_itm_b).abs().max()), 4))

print("\n== feature cells that changed vs base")
cols = [c for c in F["base"].columns if c not in ("race", "pgm", "horse")]
def diff(a):
    x = F["base"].merge(F[a], on=["race", "pgm", "horse"], suffixes=("_b", "_x"))
    out = []
    for col in cols:
        p, q = x[col + "_b"], x[col + "_x"]
        try:
            ch = ~((p.isna() & q.isna()) | np.isclose(pd.to_numeric(p, errors="coerce"), pd.to_numeric(q, errors="coerce"), atol=1e-9, equal_nan=False) | (p.astype(str) == q.astype(str)))
        except Exception:
            ch = p.astype(str) != q.astype(str)
        for i in np.where(ch)[0]:
            r = x.iloc[i]
            out.append(dict(race=r.race, pgm=r.pgm, horse=r.horse, target=(r.race, r.pgm) in TK, col=col, base=r[col + "_b"], new=r[col + "_x"]))
    return pd.DataFrame(out)
for a in ("line", "full"):
    d = diff(a)
    d.to_csv(HERE / f"featdiff_{M}_{a}.csv", index=False)
    print(f"\n-- {a}: {len(d)} changed cells; target horses {d[d.target].pgm.nunique() if len(d) else 0} rows / other starters {d[~d.target][['race','pgm']].drop_duplicates().shape[0] if len(d) else 0} rows")
    if len(d):
        print("   columns changed on targets:", d[d.target].col.value_counts().to_dict())
        print("   columns changed on OTHER starters:", d[~d.target].col.value_counts().to_dict())
        # still blank on targets after the fetch
        tg = F[a][[(r, p) in TK for r, p in zip(F[a].race, F[a].pgm)]]
        blank = tg[cols].isna().sum()
        print("   still-blank columns on targets (count of 20):", {k: int(v) for k, v in blank[blank > 0].sort_values(ascending=False).items()})
# line vs full on the targets
x = F["line"].merge(F["full"], on=["race", "pgm", "horse"], suffixes=("_l", "_f"))
x = x[[(r, p) in TK for r, p in zip(x.race, x.pgm)]]
lf = {}
for col in cols:
    p, q = x[col + "_l"], x[col + "_f"]
    ch = ~((p.isna() & q.isna()) | (p.astype(str) == q.astype(str)) | np.isclose(pd.to_numeric(p, errors="coerce"), pd.to_numeric(q, errors="coerce"), atol=1e-9))
    if ch.sum(): lf[col] = int(ch.sum())
print("\n== line vs full on the 20 targets: columns that differ:", lf)
