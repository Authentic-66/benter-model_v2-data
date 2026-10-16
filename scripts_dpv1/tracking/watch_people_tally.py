"""Running DED tally for watch-list trainers and jockeys.

Read-only on the DB. Run after each results load; it prints the tally and
rewrites ``tracking/watch_people_tally.csv``.

    python scripts_dpv1/tracking/watch_people_tally.py

For each active trainer/jockey on ``watch_list.csv`` and each window (this
meet, and every DED result in the DB):

* starts, wins, in-the-money (1st-3rd), win% and ITM%;
* $2 win ROI: (sum of $2 win payouts on their winners - $2 x starts)
  / ($2 x starts);
* against the model: their starters that appear in a logged record run (the
  live model's latest pre-race run per race, the ``score_predictions``
  rule), with the summed P(ITM) the model gave them vs. the ITM they actually
  got. ITM well above the summed P(ITM) means the model under-rated their
  horses; ITM near it means they stand out on form the model already sees.

Only logged runs are used for the model comparison: they are out of sample
and are the record. Older DED charts were in the training data, so a
re-score of them would flatter the model. That sample is small for now
(DED is logged from 2026-10-10) and grows with each card.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from dpv1_runtime import DEFAULT_DB  # noqa: E402
from check_watch_list import load_watch_list, person_matches  # noqa: E402

LOG = HERE.parent / "logs" / "predictions.jsonl"
OUT = HERE / "watch_people_tally.csv"
TRACK = "DED"
MEET_START = "2026-10-09"
LIVE_MODEL = "dpv1.3.0-5track"


def record_runs(path: Path = LOG) -> dict:
    """``(date, race, pgm) -> logged row`` for the live model's latest run."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("track") == TRACK and r.get("model_version") == LIVE_MODEL:
                rows.append(r)
    latest: dict = {}
    for r in rows:
        k = (r["race_date"], int(r["race_num"]))
        if k not in latest or r["generated_at"] > latest[k]:
            latest[k] = r["generated_at"]
    return {(r["race_date"], int(r["race_num"]), str(r["pgm"]).strip().upper()): r
            for r in rows
            if r["generated_at"] == latest[(r["race_date"], int(r["race_num"]))]}


def tally(db: str | Path) -> list[dict]:
    watch = [w for w in load_watch_list() if w["type"] in ("trainer", "jockey")]
    logged = record_runs()
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        rows = conn.execute("""
            SELECT d.race_date, r.race_num, e.program_num, e.finish_pos,
                   e.finish_status, e.win_payout, tr.name, j.name
            FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN race_days d ON d.id = r.race_day_id
            JOIN tracks t ON t.id = d.track_id
            LEFT JOIN trainers tr ON tr.id = e.trainer_id
            LEFT JOIN jockeys j ON j.id = e.jockey_id
            WHERE t.code = ? AND e.finish_status IS NOT NULL""", (TRACK,)).fetchall()
    out = []
    for w in watch:
        col = 6 if w["type"] == "trainer" else 7
        mine = [r for r in rows if person_matches(w, r[col])]
        for label, lo in (("2026 meet", MEET_START), ("all DED in DB", "0000")):
            sel = [r for r in mine if r[0] >= lo]
            st = len(sel)
            wins = sum(1 for r in sel if r[3] == 1)
            itm = sum(1 for r in sel if r[3] is not None and r[3] <= 3)
            paid = sum((r[5] or 0.0) for r in sel if r[3] == 1)
            lg = [(logged[(r[0], int(r[1]), str(r[2]).strip().upper())], r) for r in sel
                  if (r[0], int(r[1]), str(r[2]).strip().upper()) in logged]
            exp = sum(x["final_p_itm"] for x, _ in lg)
            act = sum(1 for _, r in lg if r[3] is not None and r[3] <= 3)
            out.append({
                "type": w["type"], "name": w["name"], "window": label,
                "first_date": min((r[0] for r in sel), default=""),
                "starts": st, "wins": wins, "itm": itm,
                "win_pct": round(wins / st, 3) if st else None,
                "itm_pct": round(itm / st, 3) if st else None,
                "roi_2_win": round((paid - 2 * st) / (2 * st), 3) if st else None,
                "logged_starts": len(lg),
                "model_sum_p_itm": round(exp, 2),
                "logged_actual_itm": act,
                "itm_minus_model": round(act - exp, 2),
            })
    return out


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--no-write", action="store_true", help="print only")
    a = p.parse_args()
    res = tally(a.db)
    print(f"{'who':26s} {'window':14s} {'starts':>6s} {'W':>4s} {'ITM':>4s} {'win%':>6s} "
          f"{'ITM%':>6s} {'$2 ROI':>7s} | {'logged':>6s} {'sum P':>8s} {'actual':>6s} {'diff':>6s}")
    for r in res:
        f = lambda v: "-" if v is None else f"{v:.1%}"
        roi = "-" if r["roi_2_win"] is None else f"{r['roi_2_win']:+.1%}"
        print(f"{r['type'][0].upper()} {r['name']:24s} {r['window']:14s} {r['starts']:6d} "
              f"{r['wins']:4d} {r['itm']:4d} {f(r['win_pct']):>6s} {f(r['itm_pct']):>6s} {roi:>7s} | "
              f"{r['logged_starts']:6d} {r['model_sum_p_itm']:8.2f} {r['logged_actual_itm']:6d} "
              f"{r['itm_minus_model']:+6.2f}")
    if not a.no_write:
        with open(OUT, "w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(res[0]))
            wr.writeheader()
            wr.writerows(res)
        print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
