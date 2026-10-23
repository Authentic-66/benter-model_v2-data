"""Compare re-parsed payout rows with exotic_payouts; optionally insert Pick 3/4/5 rows.

  python backfill_compare.py reparse_all.jsonl            # report only
  python backfill_compare.py reparse_all.jsonl --insert   # add-only insert
"""
import json, sqlite3, sys
from collections import Counter, defaultdict

REPO = "D:/Benter Model_v2 Data/benter-model_v2-data"
src, do_insert = sys.argv[1], "--insert" in sys.argv
PICKS = {"Pick3", "Pick4", "Pick5"}

db = sqlite3.connect(f"{REPO}/scripts/racing_full.db")
race_ids = {(t, d, rn): rid for rid, t, d, rn in db.execute("""
    select r.id, t.code, rd.race_date, r.race_num from races r
    join race_days rd on rd.id=r.race_day_id join tracks t on t.id=rd.track_id
    where t.code in ('DED','CT','GP')""")}
dbrows = defaultdict(list)
for rid, w, n, q, pay, pool in db.execute(
        "select race_id, wager_type, winning_numbers, qualifier, payoff, pool from exotic_payouts"):
    dbrows[rid].append((w, n, q, pay, pool))

errors, seen_cards = [], set()
stat = Counter()
add = []                      # (track, rid, row)
other_missing = Counter()     # wager_name -> n (non-Pick rows missing from DB)
odd_pick_missing = []         # missing Pick rows with no '/' (unexpected)
changed, db_only = [], []
for line in open(src, encoding="utf-8"):
    c = json.loads(line)
    if "error" in c:
        errors.append(c); continue
    t, d = c["track"], c["date"]
    if (t, d) in seen_cards:
        stat["duplicate card skipped"] += 1; continue
    seen_cards.add((t, d)); stat[f"cards {t}"] += 1
    for r in c["races"]:
        rid = race_ids.get((t, d, r["race_num"]))
        if rid is None:
            stat["race not in DB"] += 1; continue
        have = Counter((w, pay, pool) for w, n, q, pay, pool in dbrows[rid])
        have_full = {(w, pay, pool): (n, q) for w, n, q, pay, pool in dbrows[rid]}
        parsed = Counter()
        for x in r["exotics"]:
            k = (x["wager_type"], x["payoff"], x["pool"])
            parsed[k] += 1
            if parsed[k] <= have[k]:
                if have_full[k] != (x["winning_numbers"], x["qualifier"]):
                    changed.append((t, d, r["race_num"], k, have_full[k], (x["winning_numbers"], x["qualifier"])))
                continue
            if x["wager_name"] in PICKS:
                if "/" in x["winning_numbers"]:
                    add.append((t, rid, x))
                else:
                    odd_pick_missing.append((t, d, r["race_num"], x["wager_type"], x["winning_numbers"], x["qualifier"], x["payoff"]))
            else:
                other_missing[(t, x["wager_name"])] += 1
        for k, n in have.items():
            if parsed[k] < n:
                db_only.append((t, d, r["race_num"], k))

print(dict(stat))
print("parse errors:", len(errors), [e["file"].split("/")[-1] + " " + e["error"][:80] for e in errors[:10]])
print("Pick 3/4/5 rows to add, by track:", Counter((t, x["wager_name"]) for t, _, x in add), " total", len(add))
print("missing Pick rows WITHOUT '/' (not added):", len(odd_pick_missing))
for o in odd_pick_missing[:15]: print("   ", o)
print("other missing rows (not added):", dict(other_missing))
print("existing rows whose numbers/qualifier differ from the new parse (left as is):", len(changed))
for o in changed[:15]: print("   ", o)
print("DB rows with no match in the new parse:", len(db_only))
for o in db_only[:15]: print("   ", o)

if do_insert:
    import hashlib
    def fingerprint(max_id):
        h = hashlib.sha256()
        for row in db.execute("select * from exotic_payouts where id <= ? order by id", (max_id,)):
            h.update(repr(row).encode())
        return h.hexdigest()
    before = db.execute("select count(*) from exotic_payouts").fetchone()[0]
    max_id = db.execute("select max(id) from exotic_payouts").fetchone()[0]
    fp_before = fingerprint(max_id)
    with db:
        for t, rid, x in add:
            db.execute("""insert into exotic_payouts (race_id, wager_type, base_amount, wager_name,
                          winning_numbers, qualifier, payoff, pool, carryover) values (?,?,?,?,?,?,?,?,?)""",
                       (rid, x["wager_type"], x["base_amount"], x["wager_name"], x["winning_numbers"],
                        x["qualifier"], x["payoff"], x["pool"], x["carryover"]))
    after = db.execute("select count(*) from exotic_payouts").fetchone()[0]
    print("inserted", after - before, "rows;", before, "->", after,
          "integrity", db.execute("PRAGMA integrity_check").fetchone()[0])
    print("existing rows unchanged:", fingerprint(max_id) == fp_before, fp_before[:12])
