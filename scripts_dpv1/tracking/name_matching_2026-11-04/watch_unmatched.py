"""usage: python watch_unmatched.py <snapshot_dir>

Watch-list people on every DED PP card this meet: was the switch-OFF
loader able to link them to a charted person? Read-only."""
import sys, json, sqlite3, collections, re
from pathlib import Path
REPO = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
sys.path.insert(0, str(REPO / "scripts_dpv1")); sys.path.insert(0, str(REPO / "scripts_dpv1/tracking"))
from check_watch_list import load_watch_list, person_matches
S = Path(sys.argv[1])  # folder with snap_off/ and snap_on/ (parse_pp_file JSON per PDF)
key = lambda n: re.sub(r"[^a-z0-9]+", "", (n or "").lower())
c = sqlite3.connect(f"file:{REPO}/scripts/racing_full.db?mode=ro", uri=True)
def charted(table, col, before):
    return {r[0] for r in c.execute(f"""SELECT DISTINCT x.normalized_name FROM {table} x JOIN entries e ON e.{col}=x.id
        JOIN races r ON r.id=e.race_id JOIN race_days d ON d.id=r.race_day_id
        WHERE e.finish_pos IS NOT NULL AND d.source_pdf NOT LIKE 'PP-SCHEDULED%' AND d.race_date<?""", (before,))}
watch = [w for w in load_watch_list() if w["type"] in ("trainer", "jockey")]
tab = collections.defaultdict(lambda: collections.Counter())
rows = []
for f in sorted(S.glob("snap_off/ded*y.pdf.json")):
    off = json.loads(f.read_text(encoding="utf-8")); on = json.loads((S / "snap_on" / f.name).read_text(encoding="utf-8"))
    md = f.name[3:7]; date = f"2026-{md[:2]}-{md[2:]}"
    ck = {"trainer": charted("trainers", "trainer_id", date), "jockey": charted("jockeys", "jockey_id", date)}
    for ro, rn in zip(off["races"], on["races"]):
        for ho, hn in zip(ro["horses"], rn["horses"]):
            for w in watch:
                t = w["type"]
                if person_matches(w, hn.get(t)) or person_matches(w, ho.get(t)):
                    nm_off = ho.get(t)
                    ok = key(nm_off) in ck[t]
                    cause = "matched" if ok else ("jockey '?' (parse)" if nm_off in (None, "", "?") else f"spelling '{nm_off}'")
                    tab[(w["name"], t)][(date, cause)] += 1
                    rows.append((date, ro["race_num"], ho.get("program_num"), ho.get("horse_name"), t, w["name"], nm_off, hn.get(t), cause))
for (n, t), cnt in tab.items():
    tot = sum(cnt.values()); um = sum(v for (d, cs), v in cnt.items() if cs != "matched")
    print(f"\n{t} {n}: {tot} PP entries this meet, unmatched with switch OFF {um}")
    for d in sorted({d for d, _ in cnt}):
        print("  ", d, {cs: v for (dd, cs), v in cnt.items() if dd == d})
json.dump(rows, open(Path(__file__).parent / "watch_unmatched_rows.json", "w"), indent=0)
