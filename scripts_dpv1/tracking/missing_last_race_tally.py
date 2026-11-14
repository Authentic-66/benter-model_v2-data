"""Missing-last-race tally for scored DED cards (read-only).

A starter is flagged when its most recent PP race line (date + track) was
not in the DB **when the card was run**. "When the card was run" is the
card's own backup, ``scripts/racing_full.db.dedMMDD-run.bak`` (taken right
before that night's PP load), so charts loaded or re-downloaded later do not
hide a gap (11/06 R9 Dat Hint, EVD 6/11 truncated chart). Outcomes and
P(ITM)/P(win) come from the record run in ``logs/scored_predictions.jsonl``.

Two groups, always reported separately (Doug, 2026-11-14):

* **data tracks**: the last race was at a track the DB had (EVD, LAD, MNR,
  ...): a chart loaded late, a truncated chart, or a chart not loaded.
  Fixable by loading charts.
* **no-data tracks**: the last race was at a track with no data in the DB
  (shippers from PRM, ARP, GIL, LS, ...). Not fixable by a chart load: needs
  feeder tracks (1.4 item 4).

usage: python missing_last_race_tally.py [--from 2026-11-04] [--to YYYY-MM-DD]
                                         [--json out.json]
"""
import argparse, json, re, sqlite3, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts_dpv1")); sys.path.insert(0, str(ROOT / "scripts"))
import brisnet_pp_parser as bp        # noqa: E402
import equibase_pdf_parser as ep      # noqa: E402

RAN = ("finished", "dnf", "DNF")

# The PP parser hands each horse's raw block to last_finish_and_margin;
# capture the blocks to read the dated running lines.
CAP = []
_orig = bp.last_finish_and_margin
def _cap(b, p=None):
    CAP.append(b); return _orig(b, p)
bp.last_finish_and_margin = _cap


def ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def load_logs(d0, d1):
    gen = {}
    for l in open(ROOT / "scripts_dpv1/logs/predictions.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r["track"] == "DED" and d0 <= r["race_date"] <= d1:
            k = (r["race_date"], r["race_num"])
            if k not in gen or r["generated_at"] > gen[k]:
                gen[k] = r["generated_at"]      # record run = latest logged run
    sc = {}
    for l in open(ROOT / "scripts_dpv1/logs/scored_predictions.jsonl", encoding="utf-8"):
        r = json.loads(l)
        k = (r["race_date"], r["race_num"])
        if r["track"] == "DED" and gen.get(k) == r["generated_at"]:
            sc[(r["race_date"], r["race_num"], str(r["pgm"]))] = r
    return sc


def chart_loaded_at(db):
    """(track, date) -> first parsed_at of a chart file for that day."""
    out = {}
    for src, at in db.execute("select source_pdf, parsed_at from parsed_files where success=1"):
        m = re.search(r"([A-Z]{2,3})(\d{2})(\d{2})(\d{2})USA", src or "")
        m2 = re.search(r"(\d{4})(\d{2})(\d{2})-usa-([a-z]{2,3})-", src or "", re.I)
        k = ((m.group(1), f"20{m.group(4)}-{m.group(2)}-{m.group(3)}") if m else
             (m2.group(4).upper(), f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}") if m2 else None)
        if k:
            out[k] = min(out.get(k, at), at)
    return out


def card_rows(d, bak, loaded):
    CAP.clear()
    out = bp.parse_pp_file(str(ROOT / "Delta Downs/ded-pps-files" / f"ded{d[5:7]}{d[8:10]}y.pdf"))
    corpus = {r[0] for r in bak.execute("select code from tracks")}
    rows = []
    for race in out["races"]:
        rn = race.get("race_num")
        for h in race.get("horses", []):
            pgm = str(h.get("program_num") or h.get("pgm"))
            name = h.get("horse_name") or h.get("name")
            # full name, not a prefix (11/04 R7 Daddy's Code vs R3 Daddy's Last Sweet)
            blk = next((b for b in CAP if b and re.match(
                r"^\s*" + re.escape(pgm) + r"\s+" + re.escape(name) + r"(?![A-Za-z])", b[0])), None)
            if blk is None:
                rows.append(dict(date=d, rn=rn, pgm=pgm, horse=name, why="no PP block")); continue
            dated = [(bp._pp_line_date(l), l) for l in blk if bp._pp_line_date(l)]
            if not dated:
                continue                                    # first-time starter
            ld, line = max(dated, key=lambda x: x[0])
            trk = re.match(r"^\s*\d{1,2}[A-Za-z]{3}\d{2}([A-Za-z]+)", line).group(1).upper()
            ld = ld.isoformat()
            if trk not in corpus:
                why = "no data for track"
            elif bak.execute("""select count(*) from entries e join horses h on h.id=e.horse_id
                     join races r on r.id=e.race_id join race_days rd on rd.id=r.race_day_id
                     where h.normalized_name=? and rd.race_date=?""", (ep.normalize_name(name), ld)).fetchone()[0]:
                continue                                    # in the DB at run time
            elif bak.execute("""select count(*) from race_days rd join tracks t on t.id=rd.track_id
                     where t.code=? and rd.race_date=?""", (trk, ld)).fetchone()[0]:
                why = "chart incomplete at run"
            elif (trk, ld) in loaded:
                why = f"chart loaded after run ({loaded[(trk, ld)][:10]})"
            else:
                why = "chart not loaded"
            rows.append(dict(date=d, rn=rn, pgm=pgm, horse=name, last_trk=trk, last_date=ld, why=why,
                             group="no-data tracks" if why == "no data for track" else "data tracks"))
    return rows


def summ(rs):
    n = len(rs)
    itm = sum(1 for r in rs if (r["fin"] or 99) <= 3)
    w = sum(1 for r in rs if r["fin"] == 1)
    return (f"{n:>3} | {itm:>3} | {sum(r['p_itm'] for r in rs):5.1f} | "
            f"{w:>2} | {sum(r['p_win'] for r in rs):4.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="d0", default="2026-11-04")
    ap.add_argument("--to", dest="d1", default="9999-12-31")
    ap.add_argument("--json")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sc = load_logs(a.d0, a.d1)
    cards = sorted({k[0] for k in sc if any(v["finish_status"] in RAN for kk, v in sc.items() if kk[0] == k[0])})
    cards = [d for d in cards if (ROOT / f"scripts/racing_full.db.ded{d[5:7]}{d[8:10]}-run.bak").exists()]
    loaded = chart_loaded_at(ro(ROOT / "scripts/racing_full.db"))
    flagged = []
    for d in cards:
        bak = ro(ROOT / f"scripts/racing_full.db.ded{d[5:7]}{d[8:10]}-run.bak")
        flagged += card_rows(d, bak, loaded)
        bak.close()
    starters = []
    for r in flagged:
        s = sc.get((r["date"], r["rn"], r["pgm"]))
        if s and s["finish_status"] in RAN:
            r.update(fin=s.get("actual_finish"), odds=s.get("final_odds"), p_itm=s["p_itm"], p_win=s["p_win"])
            starters.append(r)
    print(f"cards: {', '.join(c[5:] for c in cards)}  (scratched horses left out)\n")
    print("| card | R | horse | last race | why | group | P(ITM) | odds | fin |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in starters:
        print(f"| {r['date'][5:]} | {r['rn']} | #{r['pgm']} {r['horse']} | {r.get('last_trk')} {r.get('last_date', '')[5:]} | "
              f"{r['why']} | {r['group']} | {r['p_itm']:.3f} | {r['odds']} | {r['fin']} |")
    print("\n| span | group | starters | ITM | exp ITM | W | exp W |")
    print("|---|---|---|---|---|---|---|")
    for d in cards + ["all"]:
        rs = [r for r in starters if d == "all" or r["date"] == d]
        for g in ("data tracks", "no-data tracks"):
            print(f"| {d if d == 'all' else d[5:]} | {g} | " + summ([r for r in rs if r["group"] == g]) + " |")
        print(f"| {d if d == 'all' else d[5:]} | **both** | " + summ(rs) + " |")
    other = [dict(fin=v.get("actual_finish"), p_itm=v["p_itm"], p_win=v["p_win"]) for k, v in sc.items()
             if k[0] in cards and v["finish_status"] in RAN
             and not any((r["date"], r["rn"], r["pgm"]) == k for r in starters)]
    print(f"| all | all other starters | " + summ(other) + " |")
    print("\nlast-race tracks, no-data group:",
          dict(Counter(r["last_trk"] for r in starters if r["group"] == "no-data tracks").most_common()))
    print("other flagged rows (no PP block):", [f"{r['date'][5:]} R{r['rn']} #{r['pgm']}" for r in flagged if r["why"] == "no PP block"])
    if a.json:
        Path(a.json).write_text(json.dumps(starters, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
