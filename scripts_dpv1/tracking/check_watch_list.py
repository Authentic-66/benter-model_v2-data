"""Flag races on a loaded PP card that have a watch-list horse, trainer or jockey.

Run after ``load_pp_card.py load``: it reads the card's staged rows in
``pp_entries_raw`` and prints every race with an entry whose horse, trainer
or jockey is on ``tracking/watch_list.csv`` (status ``active``). Read-only; it
writes nothing.

    python scripts_dpv1/tracking/check_watch_list.py --track DED --date 2026-10-17

Without ``--date`` it checks every staged card dated today or later.

Matching
--------
* **Horses** are compared with case, spacing and punctuation removed, because
  the PP and the chart spell the same horse differently ("C C Short Drive" on
  the PP, "CC Short Drive" on the chart).
* **People** are matched on last name + first name, and on the middle initial
  only when both sides have one. The same trainer is "Ward, Ronnie" on a
  chart and "Ward Ronnie P" on a PP, while "Ward Wesley A" is someone else.
  Watch-list rows give ``last``, ``first`` and ``middle`` explicitly.
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from dpv1_runtime import DEFAULT_DB  # noqa: E402

WATCH_LIST = HERE / "watch_list.csv"
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def parse_person(raw: str | None) -> tuple[str, str, str] | None:
    """``(last, first, middle initial)`` from "Last, First M" or "Last First M"."""
    if not raw:
        return None
    if "," in raw:
        last, rest = raw.split(",", 1)
        last_toks = [norm(t) for t in last.split()]
        rest_toks = [norm(t) for t in rest.split()]
    else:
        toks = [norm(t) for t in raw.split()]
        last_toks, rest_toks = toks[:1], toks[1:]
    last_toks = [t for t in last_toks if t and t not in _SUFFIXES]
    rest_toks = [t for t in rest_toks if t and t not in _SUFFIXES]
    if not last_toks or not rest_toks:
        return None
    middle = rest_toks[1][:1] if len(rest_toks) > 1 else ""
    return last_toks[0], rest_toks[0], middle


def person_matches(watch: dict, raw: str | None) -> bool:
    p = parse_person(raw)
    if p is None:
        return False
    last, first, middle = p
    w_mid = norm(watch.get("middle", ""))[:1]
    return (last == norm(watch["last"]) and first == norm(watch["first"])
            and (not middle or not w_mid or middle == w_mid))


def load_watch_list(path: Path = WATCH_LIST) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh)
                if r.get("status", "active").strip().lower() == "active"]


def entry_hits(watch: list[dict], horse: str, trainer: str | None,
               jockey: str | None) -> list[dict]:
    hits = []
    for w in watch:
        t = w["type"].strip().lower()
        if t == "horse" and norm(horse) == norm(w["name"]):
            hits.append(w)
        elif t == "trainer" and person_matches(w, trainer):
            hits.append(w)
        elif t == "jockey" and person_matches(w, jockey):
            hits.append(w)
    return hits


def check(db: str | Path, track: str | None, race_date: str | None):
    watch = load_watch_list()
    sql = ("SELECT track, race_date, race_num, program_num, horse_name, "
           "pp_trainer, pp_jockey, pp_ml_text FROM pp_entries_raw WHERE 1=1")
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
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        rows = conn.execute(sql + " ORDER BY race_date, track, race_num", args).fetchall()
    hits = [(r, h) for r in rows for h in [entry_hits(watch, r[4], r[5], r[6])] if h]
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
        print("no watch-list horse, trainer or jockey entered")
        return 0
    by_race = defaultdict(list)
    for r, h in hits:
        by_race[(r[0], r[1], r[2])].append((r, h))
    print(f"{len(by_race)} race(s) with a watch-list entry:")
    for (trk, d, rn), items in sorted(by_race.items()):
        print(f"  WATCH  {trk} {d} R{rn}")
        for (_, _, _, pgm, name, trainer, jockey, ml), h in items:
            why = "; ".join(f"{w['type']} {w['name']}" for w in h)
            print(f"         #{pgm} {name}  ML {ml or '?'}  (T: {trainer or '?'}, "
                  f"J: {jockey or '?'})  <- {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
