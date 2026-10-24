"""Ticket replay over logged DED cards: model, Don, Doug.

Usage: python scripts_dpv1/tracking/ticket_replay.py [out.csv]

Picks are re-ranked among horses that ran (non-betting starters excluded).
Graded on official finish (win) and the chart's payout rows (exotics, Picks).
Each ticket is bought at the chart's minimum base: $2 win, $1 exacta,
$0.50 trifecta, $0.10 superfecta, $0.50 Pick 3/4/5.
"""
import csv, json, sqlite3, sys
from collections import defaultdict
from itertools import permutations, product

from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{ROOT}/scripts_dpv1/tracking/ticket_replay.csv"

db = sqlite3.connect(f"file:{ROOT}/scripts/racing_full.db?mode=ro", uri=True)
# Every logged DED card whose results are loaded.
_logged = {json.loads(l)["race_date"] for l in open(f"{ROOT}/scripts_dpv1/logs/predictions.jsonl", encoding="utf-8")
           if '"track": "DED"' in l}
CARDS = sorted(d for d in _logged if db.execute("""
    select count(*) from entries e join races r on r.id=e.race_id join race_days rd on rd.id=r.race_day_id
    join tracks t on t.id=rd.track_id where t.code='DED' and rd.race_date=? and e.official_finish_pos=1""", (d,)).fetchone()[0])

# --- results --------------------------------------------------------------
runners = defaultdict(list)          # (date, race) -> [pgm] that ran and could be bet
win_pay = {}                          # (date, race, pgm) -> $2 win payout
fin = {}
for d, rn, pgm, off, wp, nb in db.execute("""
    select rd.race_date, r.race_num, e.program_num, e.official_finish_pos, e.win_payout, e.non_betting
    from entries e join races r on r.id=e.race_id join race_days rd on rd.id=r.race_day_id
    join tracks t on t.id=rd.track_id where t.code='DED' and rd.race_date in (%s)""" % ",".join("?" * len(CARDS)), CARDS):
    if nb:
        continue
    runners[(d, rn)].append(str(pgm))
    fin[(d, rn, str(pgm))] = off
    if off == 1 and wp:
        win_pay[(d, rn, str(pgm))] = wp
pays = defaultdict(list)              # (date, race, wager) -> [(slots, qualifierN, payoff, base)]
for d, rn, w, nums, q, pay, base in db.execute("""
    select rd.race_date, r.race_num, x.wager_name, x.winning_numbers, x.qualifier, x.payoff, x.base_amount
    from exotic_payouts x join races r on r.id=x.race_id join race_days rd on rd.id=r.race_day_id
    join tracks t on t.id=rd.track_id where t.code='DED' and rd.race_date in (%s)
    and x.wager_name in ('Exacta','Trifecta','Superfecta','Pick3','Pick4','Pick5')""" % ",".join("?" * len(CARDS)), CARDS):
    slots = [set(s.split("/")) for s in nums.split("-")]
    qn = int(q.replace("correct", "")) if q else len(slots)
    pays[(d, rn, w)].append((slots, qn, pay, base))
nraces = {d: max(rn for (dd, rn) in runners if dd == d) for d in CARDS}

# --- picks ----------------------------------------------------------------
def model_picks():
    best = {}
    for l in open(f"{ROOT}/scripts_dpv1/logs/predictions.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r["track"] != "DED" or r["race_date"] not in CARDS:
            continue
        k = (r["race_date"], r["race_num"])
        g = r["generated_at"]
        if k not in best or g > best[k][0]:
            best[k] = (g, {})
        if g == best[k][0]:
            best[k][1][r["pgm"]] = (r["p_itm"], r["p_win"])
    out, unranked = {}, 0
    for k, (g, ps) in best.items():
        ran = runners.get(k, [])
        ranked = sorted([p for p in ran if p in ps], key=lambda p: -ps[p][0])
        unranked += len([p for p in ran if p not in ps])
        out[k] = ranked
        # Win bet on the most likely winner among horses that ran (ties: P(ITM) order).
        if ranked:
            TOP_PWIN[k] = max(ranked, key=lambda p: ps[p][1])
    return out, unranked, {k: v[0] for k, v in best.items()}

def csv_picks(path, use_alt):
    out = {}
    for r in csv.DictReader(open(path)):
        if r["track"] != "DED" or r["race_date"] not in CARDS:
            continue
        if (r.get("pass_flag") or "0").strip() == "1":   # source passed the race: no tickets
            continue
        k = (r["race_date"], int(r["race_num"]))
        ran = set(runners.get(k, []))
        picks = [r[f"pick{i}"].strip() for i in range(1, 5) if r[f"pick{i}"].strip()]
        n = len(picks)
        keep = [p for p in picks if p in ran]
        alt = (r.get("alt") or "").strip()
        if use_alt and alt and alt in ran and alt not in keep and len(keep) < n:
            keep.append(alt)
        out[k] = keep
    return out

TOP_PWIN = {}   # (date, race) -> model's top-P(win) pgm
mp, unranked, runs = model_picks()
SOURCES = {"Model": mp,
           "Don": csv_picks(f"{ROOT}/scripts_dpv1/tracking/don_picks.csv", True),
           "Doug": csv_picks(f"{ROOT}/scripts_dpv1/tracking/doug_picks.csv", False)}

# --- grading --------------------------------------------------------------
def grade_ordered(d, rn, w, combos):
    """combos: list of tuples. Returns (offered, return)."""
    rows = pays.get((d, rn, w))
    if not rows:
        return False, 0.0
    ret = 0.0
    for c in combos:
        for slots, _, pay, _ in rows:
            if len(slots) == len(c) and all(h in s or "ALL" in s for h, s in zip(c, slots)):
                ret += pay
    return True, ret

def grade_pick(d, last, k, legs):
    rows = pays.get((d, last, f"Pick{k}"))
    if not rows:
        return False, 0.0, 0
    ret, hits = 0.0, 0
    for combo in product(*legs):
        best = None
        for slots, qn, pay, _ in rows:
            ok = sum(1 for h, s in zip(combo, slots) if h in s or "ALL" in s)
            if ok >= qn and (best is None or qn > best[0]):
                best = (qn, pay)
        if best:
            ret += best[1]; hits += 1
    return True, ret, hits

BASE = {"Win": 2.0, "Exacta box 2": 1.0, "Trifecta box 3": 0.5, "Superfecta box 4": 0.1,
        "Super wheel 3/3/3/ALL": 0.1}
rows = []   # source, date, bet, tickets, hits, cost, ret
skipped = defaultdict(int)
for src, P in SOURCES.items():
    for d in CARDS:
        races = [rn for rn in range(1, nraces[d] + 1) if (d, rn) in P]
        if not races:
            continue
        acc = defaultdict(lambda: [0, 0, 0.0, 0.0])
        for rn in races:
            top = P[(d, rn)]
            ran = runners[(d, rn)]
            if top:
                a = acc["Win"]; a[0] += 1; a[2] += 2.0
                wp = win_pay.get((d, rn, top[0]), 0.0)
                a[1] += wp > 0; a[3] += wp
            if src == "Model" and (d, rn) in TOP_PWIN:
                a = acc["Win (top P(win))"]; a[0] += 1; a[2] += 2.0
                wp = win_pay.get((d, rn, TOP_PWIN[(d, rn)]), 0.0)
                a[1] += wp > 0; a[3] += wp
            for name, n, w in (("Exacta box 2", 2, "Exacta"), ("Trifecta box 3", 3, "Trifecta"), ("Superfecta box 4", 4, "Superfecta")):
                if len(top) < n or len(ran) < n:
                    skipped[(src, name)] += 1; continue
                combos = list(permutations(top[:n]))
                offered, ret = grade_ordered(d, rn, w, combos)
                if not offered:
                    skipped[(src, name, "no pool")] += 1; continue
                a = acc[name]; a[0] += 1; a[1] += ret > 0; a[2] += len(combos) * BASE[name]; a[3] += ret
            if len(top) >= 3 and len(ran) >= 4:
                rest = [p for p in ran if p not in top[:3]]
                combos = [c + (x,) for c in permutations(top[:3]) for x in rest]
                offered, ret = grade_ordered(d, rn, "Superfecta", combos)
                if offered:
                    a = acc["Super wheel 3/3/3/ALL"]; a[0] += 1; a[1] += ret > 0; a[2] += len(combos) * 0.1; a[3] += ret
            else:
                skipped[(src, "Super wheel 3/3/3/ALL")] += 1
        for k in (3, 4, 5):
            for last in races:
                legs_r = list(range(last - k + 1, last + 1))
                if (d, last, f"Pick{k}") not in pays:
                    continue
                if any((d, r) not in P or not P[(d, r)] for r in legs_r):
                    skipped[(src, f"Pick{k}")] += 1; continue
                for lab, width in (("(a) top 1", 1), ("(b) top 2", 2)):
                    legs = [P[(d, r)][:width] for r in legs_r]
                    offered, ret, hits = grade_pick(d, last, k, legs)
                    ncomb = 1
                    for l in legs: ncomb *= len(l)
                    a = acc[f"Pick {k} {lab}"]; a[0] += 1; a[1] += ret > 0; a[2] += ncomb * 0.5; a[3] += ret
        for bet, (t, h, c, r) in acc.items():
            rows.append(dict(source=src, date=d, bet=bet, tickets=t, hits=h, cost=round(c, 2), ret=round(r, 2)))

with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["source", "date", "bet", "tickets", "hits", "cost", "ret"])
    w.writeheader(); w.writerows(rows)
print("cards:", CARDS)
print("record runs:", {k: v for k, v in sorted(runs.items()) if k[1] == 1})
print("runners not in the model's log (ranked last, excluded):", unranked)
print("skipped tickets:", dict(skipped))
diff = sorted(k for k in TOP_PWIN if mp.get(k) and TOP_PWIN[k] != mp[k][0])
print(f"model races where top P(win) != top P(ITM): {len(diff)}/{len(TOP_PWIN)}", diff)
