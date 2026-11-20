"""Stablemate entries at the DED meet: read-only tally (Doug, 2026-11-20).

When one trainer has two or more runners in a race, log each runner with its
morning line, final odds and official finish, and ask whether the more
heavily backed stablemate (lower final odds) usually beats the other.

    python scripts_dpv1/tracking/stablemate_tally.py [--to YYYY-MM-DD]

Read-only on the DB. Rewrites ``tracking/stablemate_entries.csv`` (one row
per runner) and prints the summary.

* Trainer = the chart's trainer (``entries.trainer_id``), owner from the chart.
* ML = ``pp_entries_raw.pp_ml_text`` matched on race and program number
  (blank for the 10/09 and 10/31 cards, which have no PP file).
* Non-betting starters and scratches are left out; a horse that did not
  finish (DNF) counts as finishing behind every finisher.
* Graded on ``official_finish_pos``.
* Baseline: every other pair of runners in the same meet races (not from the
  same trainer) with different final odds: how often the shorter price
  finished ahead. A stablemate result is only interesting if it differs
  from that.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DB = ROOT / "scripts" / "racing_full.db"
OUT = HERE / "stablemate_entries.csv"
MEET_START = "2026-10-09"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", default="9999-12-31")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = db.execute(
        """select rd.race_date, r.race_num, r.race_type, e.program_num, h.name, t.name, e.trainer_id, o.name,
                  e.final_odds, e.official_finish_pos, e.finish_status, e.win_payout
           from entries e join races r on r.id=e.race_id join race_days rd on rd.id=r.race_day_id
           join tracks k on k.id=rd.track_id join horses h on h.id=e.horse_id
           left join trainers t on t.id=e.trainer_id left join owners o on o.id=e.owner_id
           where k.code='DED' and rd.race_date between ? and ? and coalesce(e.non_betting,0)=0
             and (e.official_finish_pos is not null or e.finish_status is not null)""",
        (MEET_START, a.to)).fetchall()
    ml = {(d, rn, str(p)): m for d, rn, p, m in db.execute(
        "select race_date, race_num, program_num, pp_ml_text from pp_entries_raw where track='DED' and race_date between ? and ?",
        (MEET_START, a.to))}
    races = defaultdict(list)
    for d, rn, rt, pgm, horse, tr, tid, own, odds, off, st, wp in rows:
        races[(d, rn)].append(dict(race_date=d, race_num=rn, race_type=rt, pgm=str(pgm), horse=horse, trainer=tr or "", tid=tid,
                                   owner=own or "", ml=ml.get((d, rn, str(pgm)), "") or "", final_odds=odds,
                                   finish=off, status=st or "", win=wp))

    def pos(x):  # DNF behind every finisher
        return x["finish"] if x["finish"] else 99

    out, groups = [], []
    base_n = base_short = 0
    for k in sorted(races):
        rs = races[k]; n = len(rs)
        by = defaultdict(list)
        for x in rs:
            if x["tid"] is not None: by[x["tid"]].append(x)
        stable_pairs = set()
        for tid, xs in by.items():
            if len(xs) < 2: continue
            xs = sorted(xs, key=lambda x: (x["final_odds"] if x["final_odds"] is not None else 999))
            groups.append(dict(key=k, runners=xs, field=n))
            for i, x in enumerate(xs):
                out.append(dict(race_date=k[0], race_num=k[1], race_type=x["race_type"], field_size=n, trainer=x["trainer"],
                                stable_runners=len(xs), backing_rank=i + 1, pgm=x["pgm"], horse=x["horse"], owner=x["owner"],
                                ml=x["ml"], final_odds=x["final_odds"], finish=x["finish"] if x["finish"] else "DNF",
                                win_payout=x["win"] or ""))
            for p, q in itertools.combinations(xs, 2): stable_pairs.add(frozenset((p["pgm"], q["pgm"])))
        for p, q in itertools.combinations(rs, 2):
            if frozenset((p["pgm"], q["pgm"])) in stable_pairs: continue
            if p["final_odds"] is None or q["final_odds"] is None or p["final_odds"] == q["final_odds"]: continue
            s, l = (p, q) if p["final_odds"] < q["final_odds"] else (q, p)
            base_n += 1; base_short += pos(s) < pos(l)

    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]) if out else ["race_date"], lineterminator="\n")
        w.writeheader(); w.writerows(out)

    print(f"DED {MEET_START} .. {max(k[0] for k in races)}: {len(races)} races, {len(groups)} with a trainer running 2+\n")
    print("| date | R | trainer | runners (ML -> final odds, finish) | backed one ahead? |")
    print("|---|---|---|---|---|")
    pairs = ahead = tie = 0; bW = oW = bI = oI = 0; bWin = oWin = 0.0; nb = no = 0
    for g in groups:
        xs = g["runners"]; b = xs[0]; others = xs[1:]
        if b["final_odds"] == others[0]["final_odds"]:
            res = "same odds (coupled?)"; tie += 1
        else:
            pairs += 1; ok = all(pos(b) < pos(o) for o in others); ahead += ok
            res = "yes" if ok else "no"
            nb += 1; bW += b["finish"] == 1; bI += pos(b) <= 3; bWin += b["win"] or 0
            for o in others: no += 1; oW += o["finish"] == 1; oI += pos(o) <= 3; oWin += o["win"] or 0
        desc = "; ".join(f"#{x['pgm']} {x['horse']} ({x['ml'] or '-'} -> {x['final_odds']}, {x['finish'] or 'DNF'})" for x in xs)
        print(f"| {g['key'][0][5:]} | {g['key'][1]} | {b['trainer']} | {desc} | {res} |")
    print(f"\nraces with different odds: {pairs}; the more heavily backed stablemate finished ahead of the other(s) in {ahead} "
          f"({ahead / pairs:.0%})" if pairs else "\nno stablemate races")
    if tie: print(f"same final odds (left out): {tie}")
    if nb:
        print(f"backed one:  {nb} runners, W {bW}, ITM {bI}, $2 win {bWin:.2f} on {2 * nb:.2f}")
        print(f"other(s):    {no} runners, W {oW}, ITM {oI}, $2 win {oWin:.2f} on {2 * no:.2f}")
    print(f"baseline, all other same-race pairs with different odds: shorter price ahead in {base_short} of {base_n} ({base_short / base_n:.0%})")
    print(f"\nwrote {OUT} ({len(out)} rows)")


if __name__ == "__main__":
    main()
