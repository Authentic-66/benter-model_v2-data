"""Step 1 of the stretch-run investigation (2026-10-21): every charted horse's
beaten lengths at the stretch call and finish, lengths gained between them,
and rank in the field. Writes out/stretch.pkl.

    python scripts_dpv1/diagnostics/stretch_run/s1_build.py
"""
import sqlite3, json, re, sys
from pathlib import Path
OUT = Path(__file__).resolve().parent / "out"; OUT.mkdir(exist_ok=True)
import pandas as pd, numpy as np
DB = r"D:\Benter Model_v2 Data\benter-model_v2-data\scripts\racing_full.db"
c = sqlite3.connect(DB)
df = pd.read_sql("""
 select e.id entry_id, e.race_id, e.horse_id, e.pace_calls_json pj, e.official_finish_pos fin, e.beaten_lengths bl_chart,
        e.final_odds, r.call_labels, r.field_size, r.distance_yards, r.surface, rd.race_date, t.code track, r.race_num
 from entries e join races r on r.id=e.race_id join race_days rd on rd.id=r.race_day_id join tracks t on t.id=rd.track_id
 where (r.breed is null or r.breed='Thoroughbred')""", c)
df = df[df.fin.notna() | df.pj.notna()]

FIX = {"head": .1, "neck": .25, "nose": .05, "hd": .1, "nk": .25, "no": .05}
def mlen(s):
    if s is None or s == "": return None
    if s.lower() in FIX: return FIX[s.lower()]
    m = re.match(r"^(\d+?)?(\d/\d)?$", s)
    if not m or (m.group(1) is None and m.group(2) is None):
        m2 = re.match(r"^(\d+)$", s)
        return float(m2.group(1)) if m2 else None
    w = int(m.group(1) or 0); f = 0.0
    if m.group(2): a, b = m.group(2).split("/"); f = int(a)/int(b)
    return w + f
def cands(tok, n):
    out = []
    for k in (1, 2):
        if len(tok) < k or not tok[:k].isdigit(): continue
        p = int(tok[:k]); rest = tok[k:]
        if p < 1 or p > n or (k == 2 and p < 10): continue
        ml = mlen(rest) if rest else None
        if rest and ml is None: continue
        out.append((p, ml, rest))
    return out
def call_bl(toks, n):
    """toks: {entry_id: token}. Returns {entry_id: beaten lengths} or None."""
    cs = {e: cands(t, n) for e, t in toks.items()}
    if any(not v for v in cs.values()): return None
    pos = {}; taken = set(); changed = True
    while changed:
        changed = False
        for e, v in cs.items():
            if e in pos: continue
            v2 = [x for x in v if x[0] not in taken]
            if len(v2) == 1:
                pos[e] = v2[0]; taken.add(v2[0][0]); changed = True
    if len(pos) != len(cs): return None
    order = sorted(pos.items(), key=lambda kv: kv[1][0])
    if [x[1][0] for x in order] != list(range(1, len(order)+1)): return None
    out = {}; acc = 0.0
    for i, (e, (p, ml, rest)) in enumerate(order):
        out[e] = acc
        if i < len(order)-1:
            if ml is None: return None
            acc += ml
    return out

rows = []
for rid, g in df.groupby("race_id"):
    labs = g.call_labels.iloc[0]
    if not isinstance(labs, str): continue
    labs = json.loads(labs)
    if "Str" not in labs or "Fin" not in labs: continue
    i = labs.index("Str"); prev = labs[i-1] if i-1 >= 0 and labs[i-1] != "Start" else None
    pjs = {}
    for e, pj in zip(g.entry_id, g.pj):
        try: pjs[e] = json.loads(pj) if isinstance(pj, str) else None
        except Exception: pjs[e] = None
    if any(v is None for v in pjs.values()): continue
    n = len(g)
    res = {}
    for lab in [x for x in (prev, "Str", "Fin") if x]:
        toks = {e: d.get(lab) for e, d in pjs.items()}
        if any(not isinstance(t, str) or not t or t == "---" for t in toks.values()): res[lab] = None; continue
        res[lab] = call_bl(toks, n)
    if res.get("Str") is None or res.get("Fin") is None: continue
    for e in g.entry_id:
        rows.append(dict(entry_id=e, race_id=rid, bl_prev=(res[prev][e] if prev and res.get(prev) else np.nan),
                         bl_str=res["Str"][e], bl_fin=res["Fin"][e], n_call=n))
S = pd.DataFrame(rows)
d = df.merge(S, on=["entry_id", "race_id"], how="left")
# entries.beaten_lengths is each horse's margin over the NEXT horse (same as the
# call token), so it cannot check cumulative lengths; s2 checks finish order instead.
print(f"races with stretch data: {S.race_id.nunique():,} of {df.race_id.nunique():,}")
d["str_gain"] = d.bl_str - d.bl_fin          # lengths gained, stretch call -> finish
d["turn_gain"] = d.bl_prev - d.bl_str        # lengths gained, call before stretch -> stretch call
for col in ("str_gain", "turn_gain"):
    d[col + "_rank"] = d.groupby("race_id")[col].rank(ascending=False, method="min")
d.to_pickle(OUT / "stretch.pkl")
