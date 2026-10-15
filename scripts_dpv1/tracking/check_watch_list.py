"""Flag watch-list horses entered on a loaded PP card.

Run after ``load_pp_card.py load``: it reads the card's staged rows in
``pp_entries_raw`` and prints any horse on ``tracking/watch_list.csv`` (status
``active``) that is entered. Read-only; it writes nothing.

    python scripts_dpv1/tracking/check_watch_list.py --track DED --date 2026-10-17

Without ``--date`` it checks every staged card dated today or later.

Names are compared with case, spacing and punctuation removed, because the PP
and the chart spell the same horse differently ("C C Short Drive" on the PP,
"CC Short Drive" on the chart).
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from dpv1_runtime import DEFAULT_DB  # noqa: E402

WATCH_LIST = HERE / "watch_list.csv"


def norm(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def load_watch_list(path: Path = WATCH_LIST) -> dict[str, dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return {norm(r["horse"]): r for r in csv.DictReader(fh)
                if r.get("status", "active").strip().lower() == "active"}


def check(db: str | Path, track: str | None, race_date: str | None) -> list[tuple]:
    watch = load_watch_list()
    sql = ("SELECT track, race_date, race_num, program_num, horse_name, "
           "pp_ml_text FROM pp_entries_raw WHERE 1=1")
    args: list = []
    if track:
        sql += " AND track = ?"
        args.append(track)
    if race_date:
        sql += " AND race_date = ?"
        args.append(race_date)
    else:
        sql += " AND race_date >= ?"
        args.append(date.today().isoformat())
    with sqlite3.connect(db) as conn:
        rows = conn.execute(sql + " ORDER BY race_date, track, race_num", args).fetchall()
    hits = [(r, watch[norm(r[4])]) for r in rows if norm(r[4]) in watch]
    return rows, hits


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--track")
    p.add_argument("--date", help="YYYY-MM-DD; default: every card dated today or later")
    p.add_argument("--db", default=str(DEFAULT_DB))
    a = p.parse_args()
    rows, hits = check(a.db, a.track, a.date)
    cards = sorted({(r[0], r[1]) for r in rows})
    print(f"checked {len(rows)} entries on {len(cards)} card(s): "
          + (", ".join(f"{t} {d}" for t, d in cards) or "none staged"))
    if not hits:
        print("no watch-list horses entered")
        return 0
    for (trk, d, rn, pgm, name, ml), w in hits:
        print(f"  WATCH  {trk} {d} R{rn} #{pgm} {name}  ML {ml or '?'}  "
              f"-- {w['reason']} (added {w['added']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
