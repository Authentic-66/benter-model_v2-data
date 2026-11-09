"""Hand edits for the Step 6 adversarial tests (scratch copies only).

usage: adv_edit.py <db> <stash dir> <test>
  scratch    remove one 11/07 card entry (R5, highest program number) and its
             derived rows; saved to <stash>/scratch.json
  restore    put that entry back (an "also-eligible" added to the card)
  attrs      change one horse's sire and foaled date (horse with the most
             DED starts in October); old values saved
  relabel    change the race_type of DED 2026-10-10 R5 CLAIMING -> STARTERALLOWANCE
Prints what it changed.
"""
import json
import sqlite3
import sys
from pathlib import Path

db, stash, test = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
stash.mkdir(parents=True, exist_ok=True)
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
c.execute("PRAGMA foreign_keys = ON")
DAY = """FROM entries e JOIN races r ON r.id = e.race_id
         JOIN race_days rd ON rd.id = r.race_day_id
         JOIN tracks t ON t.id = rd.track_id"""
# Derived first (foreign keys), entries last.
TABLES = ["computed_speed_figures", "computed_speed_figures_dpv1",
          "entry_v10_flags", "entry_pp_features", "pp_entries_raw",
          "entry_features_v1"]


def rows(table, where, args):
    try:
        return [dict(r) for r in c.execute(f"SELECT * FROM {table} WHERE {where}", args)]
    except sqlite3.OperationalError:
        return []


if test == "scratch":
    eid = c.execute(f"""SELECT e.id {DAY} WHERE t.code='DED' AND rd.race_date='2026-11-07'
                        AND r.race_num=5 ORDER BY CAST(e.program_num AS INT) DESC,
                        e.program_num DESC LIMIT 1""").fetchone()[0]
    saved = {t: rows(t, "entry_id = ?", (eid,)) for t in TABLES}
    saved["entries"] = rows("entries", "id = ?", (eid,))
    (stash / "scratch.json").write_text(json.dumps(saved, default=str), encoding="utf-8")
    with c:
        for t in TABLES:
            if saved[t]:
                c.execute(f"DELETE FROM {t} WHERE entry_id = ?", (eid,))
        c.execute("DELETE FROM entries WHERE id = ?", (eid,))
    print("scratched entry", eid, {t: len(v) for t, v in saved.items()})

elif test == "restore":
    saved = json.loads((stash / "scratch.json").read_text(encoding="utf-8"))
    with c:
        for t in ["entries"] + TABLES:
            for r in saved[t]:
                cols = list(r)
                c.execute(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                          [r[k] for k in cols])
    print("restored entry", saved["entries"][0]["id"])

elif test == "attrs":
    hid = c.execute(f"""SELECT e.horse_id {DAY} WHERE t.code='DED'
                        AND rd.race_date BETWEEN '2026-10-01' AND '2026-10-31'
                        GROUP BY e.horse_id ORDER BY COUNT(*) DESC, e.horse_id LIMIT 1""").fetchone()[0]
    old = dict(c.execute("SELECT id, sire_id, foaled_date FROM horses WHERE id=?", (hid,)).fetchone())
    new_sire = c.execute("SELECT id FROM sires WHERE id <> ? ORDER BY id LIMIT 1",
                         (old["sire_id"] or -1,)).fetchone()[0]
    new_foaled = "2019-01-01" if old["foaled_date"] != "2019-01-01" else "2020-01-01"
    with c:
        c.execute("UPDATE horses SET sire_id=?, foaled_date=? WHERE id=?", (new_sire, new_foaled, hid))
    n = c.execute("SELECT COUNT(*) FROM entries WHERE horse_id=?", (hid,)).fetchone()[0]
    print("horse", hid, "entries", n, "old", old, "new sire", new_sire, "foaled", new_foaled)

elif test == "relabel":
    r = dict(c.execute("""SELECT r.id, r.race_type, r.race_num FROM races r
                          JOIN race_days rd ON rd.id = r.race_day_id JOIN tracks t ON t.id = rd.track_id
                          WHERE t.code='DED' AND rd.race_date='2026-10-10' AND r.race_num=5""").fetchone())
    new = "STARTERALLOWANCE"   # the kind of hand relabel done on 11/06 R4
    with c:
        c.execute("UPDATE races SET race_type=? WHERE id=?", (new, r["id"]))
    n = c.execute("SELECT COUNT(*) FROM entries WHERE race_id=?", (r["id"],)).fetchone()[0]
    print("race", r, "->", new, "entries", n)
else:
    sys.exit(f"unknown test {test}")
