"""Read-only: horses on DED 11/04-11/06 whose most recent PP race was not in the DB
when the card was run. Outcome vs model expectation, and where the missing races are."""
import sys, json, re, sqlite3
from collections import defaultdict, Counter
from datetime import date
ROOT = r"D:\Benter Model_v2 Data\benter-model_v2-data"
sys.path.insert(0, ROOT + r"\scripts_dpv1"); sys.path.insert(0, ROOT + r"\scripts")
sys.stdout.reconfigure(encoding="utf-8")
import brisnet_pp_parser as bp

CAP = []
_o = bp.last_finish_and_margin
def cap(b, p=None):
    CAP.append(b); return _o(b, p)
bp.last_finish_and_margin = cap

db = sqlite3.connect(f"file:{ROOT}/scripts/racing_full.db?mode=ro", uri=True)
corpus = {r[0] for r in db.execute("select code from tracks")}
# when was each chart (track, date) loaded
loaded = {}
for src, at in db.execute("select source_pdf, parsed_at from parsed_files where success=1"):
    m = re.search(r"([A-Z]{2,3})(\d{2})(\d{2})(\d{2})USA", src or "")
    m2 = re.search(r"(\d{4})(\d{2})(\d{2})-usa-([a-z]{2,3})-", src or "", re.I)
    k = None
    if m:
        k = (m.group(1), f"20{m.group(4)}-{m.group(2)}-{m.group(3)}")
    elif m2:
        k = (m2.group(4).upper(), f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}")
    if k:
        loaded[k] = min(loaded.get(k, at), at)
from datetime import datetime, timedelta
def utc(g):  # generated_at is local Central: CDT (UTC-5) before 11/01, CST (UTC-6) after
    return (datetime.fromisoformat(g) + timedelta(hours=6 if g >= "2026-11-01T02" else 5)).strftime("%Y-%m-%d %H:%M:%S")

# record-run predictions + scores
gen, pred = {}, {}
for l in open(ROOT + r"\scripts_dpv1\logs\predictions.jsonl", encoding="utf-8"):
    r = json.loads(l)
    if r["track"] == "DED" and r["race_date"] in ("2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-11", "2026-11-12", "2026-11-13"):
        k = (r["race_date"], r["race_num"])
        if k not in gen or r["generated_at"] > gen[k]:
            gen[k] = r["generated_at"]
sc = {}
for l in open(ROOT + r"\scripts_dpv1\logs\scored_predictions.jsonl", encoding="utf-8"):
    r = json.loads(l)
    k = (r["race_date"], r["race_num"])
    if r["track"] == "DED" and k in gen and r["generated_at"] == gen[k]:
        sc[(r["race_date"], r["race_num"], r["pgm"])] = r

rows = []
for d in ("2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-11", "2026-11-12", "2026-11-13"):
    f = ROOT + rf"\Delta Downs\ded-pps-files\ded{d[5:7]}{d[8:10]}y.pdf"
    CAP.clear()
    out = bp.parse_pp_file(f)
    # map horse name -> (race, pgm) from the parsed file
    for race in out["races"]:
        rn = race.get("race_num")
        for h in race.get("horses", []):
            pgm = str(h.get("program_num") or h.get("pgm"))
            name = h.get("horse_name") or h.get("name")
            blk = next((b for b in CAP if b and re.match(r"^\s*" + re.escape(pgm) + r"\s+" + re.escape(name) + r"(?![A-Za-z])", b[0])), None)
            if blk is None:
                rows.append(dict(date=d, rn=rn, pgm=pgm, horse=name, status="no block")); continue
            dated = [(bp._pp_line_date(l), l) for l in blk if bp._pp_line_date(l)]
            if not dated:
                continue  # first-time starter
            ld, line = max(dated, key=lambda x: x[0])
            trk = re.match(r"^\s*\d{1,2}[A-Za-z]{3}\d{2}([A-Za-z]+)", line).group(1).upper()
            # card entry -> horse_id
            hid = db.execute("""select e.horse_id from entries e join races r on r.id=e.race_id join race_days rd on rd.id=r.race_day_id
                 join tracks t on t.id=rd.track_id where t.code='DED' and rd.race_date=? and r.race_num=? and e.program_num=?""", (d, rn, pgm)).fetchone()
            in_db_now = False
            if hid:
                in_db_now = db.execute("""select count(*) from entries e join races r on r.id=e.race_id join race_days rd on rd.id=r.race_day_id
                    where e.horse_id=? and rd.race_date=?""", (hid[0], ld.isoformat())).fetchone()[0] > 0
            g = gen.get((d, rn))
            la = loaded.get((trk, ld.isoformat()))
            gu = utc(g)
            if trk not in corpus:
                why = "track not in corpus"
            elif la is None:
                why = "chart not loaded"
            elif la > gu:
                why = f"chart loaded after run ({la[:10]})"
            elif not in_db_now:
                why = "chart loaded, horse not matched"
            else:
                why = "in DB"
            s = sc.get((d, rn, pgm))
            rows.append(dict(date=d, rn=rn, pgm=pgm, horse=name, last_trk=trk, last_date=ld.isoformat(), why=why,
                             flagged=why != "in DB", s=s))

flag = [r for r in rows if r.get("flagged")]
print("rows", len(rows), "no block", sum(1 for r in rows if r.get("status") == "no block"), "flagged", len(flag))
# runner rank
def rank_among_runners(r):
    s = r["s"]
    if not s: return None, None
    k = (r["date"], r["rn"])
    ran = [x for kk, x in sc.items() if (kk[0], kk[1]) == k and x["finish_status"] != "scratched" and x.get("actual_finish") is not None or ((kk[0], kk[1]) == k and x["finish_status"] == "dnf")]
    ran = [x for kk, x in sc.items() if (kk[0], kk[1]) == k and x["finish_status"] in ("finished", "dnf", "DNF")]
    order = sorted(ran, key=lambda x: -x["p_itm"])
    pgms = [x["pgm"] for x in order]
    return (pgms.index(r["pgm"]) + 1 if r["pgm"] in pgms else None), len(pgms)

print("\nfinish_status values:", Counter(x["finish_status"] for x in sc.values()))
starters = []
for r in flag:
    s = r["s"]
    st = s["finish_status"] if s else "unscored"
    rk, n = rank_among_runners(r) if s and st in ("finished", "dnf", "DNF") else (None, None)
    r.update(st=st, rk=rk, n=n)
    print(f"{r['date'][5:]} R{r['rn']} #{r['pgm']:<3} {r['horse'][:22]:<22} last {r['last_trk']} {r['last_date']} ({r['why']}) | "
          + (f"fin {s.get('actual_finish')} odds {s.get('final_odds')} rank {rk}/{n} P(ITM) {s['p_itm']:.3f} P(win) {s['p_win']:.3f}" if st in ("finished", "dnf", "DNF") else st))
    if st in ("finished", "dnf", "DNF"):
        starters.append(r)

def summ(lbl, rs):
    n = len(rs)
    if not n: return
    w = sum(1 for r in rs if r["s"].get("actual_finish") == 1)
    i = sum(1 for r in rs if (r["s"].get("actual_finish") or 99) <= 3)
    ew = sum(r["s"]["p_win"] for r in rs); ei = sum(r["s"]["p_itm"] for r in rs)
    ow = sum(1 / (1 + r["s"]["final_odds"]) for r in rs if r["s"].get("final_odds") is not None)
    roi = sum(r["s"].get("win_payoff") or 0 for r in rs)
    print(f"{lbl:<34} n={n:>3}  wins {w} (model exp {ew:.1f}, odds-implied {ow:.1f})  ITM {i} (model exp {ei:.1f})")
print()
summ("flagged starters, all 4 cards", starters)
for d in ("2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-11", "2026-11-12", "2026-11-13"):
    summ(f"  {d}", [r for r in starters if r["date"] == d])
others = []
for (d, rn, pgm), s in sc.items():
    if s["finish_status"] in ("finished", "dnf", "DNF") and not any(r["date"] == d and r["rn"] == rn and r["pgm"] == pgm for r in flag):
        others.append(dict(s=s, date=d))
summ("all other starters, same cards", others)
print("\nmissing-race tracks (all flagged entries incl. scratched):")
c = Counter((r["last_trk"], r["why"]) for r in flag)
for k, v in sorted(c.items(), key=lambda x: -x[1]): print("  ", k, v)
print("dates by track:")
dd = defaultdict(list)
for r in flag: dd[r["last_trk"]].append(r["last_date"])
for k, v in dd.items(): print("  ", k, sorted(set(v)))
json.dump([{k: v for k, v in r.items() if k != "s"} | ({"fin": r["s"].get("actual_finish"), "odds": r["s"].get("final_odds"), "p_itm": r["s"]["p_itm"], "p_win": r["s"]["p_win"]} if r.get("s") else {}) for r in flag],
          open(r"C:\Users\bornr\AppData\Local\Temp\claude\4f22c0db0d78fb97\2391090e-bb4b-4290-98e2-f711d9d62c28\scratchpad\s1114\missing_last.json", "w"), indent=1)
