"""Phase 6E piece 2: score logged predictions against what actually happened.

    python scripts_dpv1/score_predictions.py --track CT --date 2026-08-28

Piece 1 made ``card_picks.py --save`` leave a machine-readable trail in
``logs/predictions.jsonl`` — one row per horse, written before the race ran.
This reads that trail back, joins it to the finishing positions in
``racing_full.db``, and writes ``logs/scored_predictions.jsonl``: the same rows
plus what happened. Piece 3 aggregates that file into a health dashboard; this
script deliberately does no aggregating of its own beyond a summary it prints
so a card can be eyeballed straight after it is scored.

The join is on ``(track, race_date, race_num, pgm)`` with ``pgm`` compared as
text, because program numbers are not integers — coupled entries are ``1A``.

What counts as a result
-----------------------
The database distinguishes three states and they are not interchangeable:

* ``finish_status = 'finished'`` — a real position in ``finish_pos``.
* ``finish_status = 'DNF'`` — the horse ran and did not finish. ``finish_pos``
  is NULL, but this is an outcome, not a missing value: it did not hit the
  board. Scored, with ``actual_finish`` NULL and ``hit_itm`` false.
* ``finish_status IS NULL`` — the card is in the database but its results are
  not. Never scored.

A scratched horse is usually not an ``entries`` row at all once results load;
it lives in ``races.scratched_horses``. Either way it has no outcome, so it
gets no scored row, and its name is reported as scratched rather than as a
failed join.

Why a scratched top pick is NULL and not False
----------------------------------------------
``top_pick_hit_itm`` is the number the whole exercise turns on, and the
tempting shortcut — a scratched top pick "didn't hit" — silently biases the
model's headline metric downward by however often the top pick scratches. When
rank 1 has no outcome the race carries ``top_pick_hit_itm = null`` and
``top_pick_scratched = true``, and Piece 3 must drop those races from the
denominator rather than counting them as misses.

Idempotency
-----------
Re-scoring a card rewrites that card's rows rather than appending a second
copy: every row for the ``(track, race_date)`` being scored is dropped from
``scored_predictions.jsonl`` and replaced. Other cards in the file are carried
through untouched, and the rewrite goes via a temp file so an interrupted run
cannot truncate the history.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DPV1_DIR = Path(__file__).resolve().parent
LOG_DIR = DPV1_DIR / "logs"
sys.path.insert(0, str(DPV1_DIR))

from dpv1_runtime import DEFAULT_DB  # noqa: E402

PRED_FILE = LOG_DIR / "predictions.jsonl"
SCORED_FILE = LOG_DIR / "scored_predictions.jsonl"

log = logging.getLogger("score_predictions")


def _norm_pgm(v) -> str:
    """Program numbers join as text: '4', '1A'. Normalise case and padding."""
    return str(v).strip().upper() if v is not None else ""


def _norm_name(v) -> str:
    """Loose horse-name key, used for matching scratch lists only."""
    return "".join(ch for ch in str(v).upper() if ch.isalnum())


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

def load_predictions(path: Path, track: str | None = None,
                     date: str | None = None) -> list[dict]:
    """Read predictions.jsonl, optionally filtered to one card.

    A malformed line is skipped with a warning rather than killing the run.
    The log is append-only and a half-written final line is a real possibility
    if a pick run was interrupted.
    """
    if not path.exists():
        raise SystemExit(
            f"no prediction log at {path} -- run card_picks.py --save first")
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            log.warning("%s line %d is not valid JSON, skipped (%s)",
                        path.name, i, exc)
            continue
        if track and str(row.get("track", "")).upper() != track.upper():
            continue
        if date and row.get("race_date") != date:
            continue
        rows.append(row)
    return rows


def fetch_results(db: str, track: str, date: str) -> dict:
    """Pull one card's outcomes out of racing_full.db.

    Returns ``entries`` keyed by ``(race_num, normalised pgm)``, the set of
    races that actually have results, per-race scratch name sets, and per-race
    starter counts.
    """
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT r.race_num, e.program_num, h.name, e.finish_pos,
                   e.finish_status, e.show_payout, e.final_odds
            FROM entries e
            JOIN races r      ON r.id  = e.race_id
            JOIN horses h     ON h.id  = e.horse_id
            JOIN race_days rd ON rd.id = r.race_day_id
            JOIN tracks t     ON t.id  = rd.track_id
            WHERE t.code = ? AND rd.race_date = ?
            """, (track.upper(), date)).fetchall()
        scratch_rows = conn.execute(
            """
            SELECT r.race_num, r.scratched_horses
            FROM races r
            JOIN race_days rd ON rd.id = r.race_day_id
            JOIN tracks t     ON t.id  = rd.track_id
            WHERE t.code = ? AND rd.race_date = ?
            """, (track.upper(), date)).fetchall()
    finally:
        conn.close()

    entries: dict[tuple[int, str], dict] = {}
    have_results: set[int] = set()
    starters: dict[int, int] = defaultdict(int)
    for race_num, pgm, name, finish_pos, status, show_payout, final_odds in rows:
        entries[(int(race_num), _norm_pgm(pgm))] = {
            "horse_name": name,
            "finish_pos": finish_pos,
            "finish_status": status,
            "show_payout": show_payout,
            "final_odds": final_odds,
        }
        if status is not None:
            have_results.add(int(race_num))
            starters[int(race_num)] += 1

    scratched: dict[int, set[str]] = defaultdict(set)
    for race_num, raw in scratch_rows:
        if not raw:
            continue
        try:
            for s in json.loads(raw):
                nm = s.get("name") if isinstance(s, dict) else s
                if nm:
                    scratched[int(race_num)].add(_norm_name(nm))
        except (json.JSONDecodeError, TypeError, AttributeError):
            log.warning("R%s: could not parse scratched_horses", race_num)

    return {"entries": entries, "have_results": have_results,
            "scratched": scratched, "starters": dict(starters)}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_card(preds: list[dict], results: dict) -> tuple[list[dict], dict]:
    """Join one card's predictions to its outcomes.

    Grouping is by ``(generated_at, model_pkl, race_num)``, not by race alone:
    a card can be run more than once -- a different model, or a re-run after a
    scratch -- and each run is its own opinion with its own rank 1.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for p in preds:
        groups[(p.get("generated_at"), p.get("model_pkl"),
                int(p["race_num"]))].append(p)

    scored: list[dict] = []
    stats = {"races_scored": set(), "races_skipped": set(), "runs": len(groups),
             "predictions": len(preds), "no_result": 0, "scratched": 0,
             "unmatched": 0, "no_record": 0, "dnf": 0}
    scored_at = datetime.now().isoformat(timespec="seconds")

    for key, rows in sorted(groups.items(),
                            key=lambda kv: (kv[0][2], kv[0][0] or "")):
        race_num = key[2]
        if race_num not in results["have_results"]:
            stats["races_skipped"].add(race_num)
            continue

        # Resolve every horse's outcome first: the top pick's fate decides a
        # race-level field that every row in the group has to carry.
        scratch_names = results["scratched"].get(race_num, set())
        outcomes: dict[str, dict | None] = {}
        for p in rows:
            e = results["entries"].get((race_num, _norm_pgm(p.get("pgm"))))
            if e is not None and e.get("finish_status") is not None:
                outcomes[p["prediction_id"]] = e
                continue
            # Three different ways to have no outcome, and they mean different
            # things. Keep them apart: only the last one is a data problem.
            if _norm_name(p.get("horse_name")) in scratch_names:
                stats["scratched"] += 1
            elif e is None:
                log.warning("R%s: no entry for pgm %s (%s) -- not scored",
                            race_num, p.get("pgm"), p.get("horse_name"))
                stats["unmatched"] += 1
            else:
                # An entry row exists but carries no finishing position. In
                # this corpus that is normally a disqualification: the loader
                # renames the horse 'DQ-<name>' and leaves finish_pos NULL, so
                # the race has no recorded winner at all. 0.6% of loaded races.
                log.warning("R%s: pgm %s (%s) has an entry but no recorded "
                            "result (disqualification?) -- not scored",
                            race_num, p.get("pgm"), p.get("horse_name"))
                stats["no_record"] += 1
            stats["no_result"] += 1
            outcomes[p["prediction_id"]] = None

        top = next((p for p in rows if p.get("rank") == 1), None)
        top_out = outcomes.get(top["prediction_id"]) if top else None
        top_pick_scratched = top_out is None
        if top_pick_scratched:
            top_pick_hit_itm = None
        else:
            fp = top_out["finish_pos"]
            top_pick_hit_itm = bool(fp is not None and fp <= 3)

        for p in rows:
            e = outcomes[p["prediction_id"]]
            if e is None:
                continue  # scratched or no result: nothing to score
            fp = e["finish_pos"]
            if fp is None:
                stats["dnf"] += 1
            row = dict(p)
            row.update({
                "actual_finish": int(fp) if fp is not None else None,
                "finish_status": e["finish_status"],
                "hit_itm": bool(fp is not None and fp <= 3),
                "hit_win": bool(fp is not None and fp == 1),
                "was_top_pick": bool(p.get("rank") == 1),
                "top_pick_hit_itm": top_pick_hit_itm,
                "top_pick_scratched": top_pick_scratched,
                "show_payoff": (float(e["show_payout"])
                                if e["show_payout"] is not None else None),
                "final_odds": (float(e["final_odds"])
                               if e["final_odds"] is not None else None),
                "n_starters": results["starters"].get(race_num),
                "scored_at": scored_at,
            })
            scored.append(row)
        stats["races_scored"].add(race_num)

    return scored, stats


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_scored(rows: list[dict], cards: set[tuple[str, str]],
                 path: Path = SCORED_FILE) -> int:
    """Replace every scored row for ``cards``, keep the rest, write atomically.

    ``cards`` is passed in rather than derived from ``rows`` so that re-scoring
    a card that produced nothing this time still clears its stale rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                log.warning("dropping unparseable line from %s", path.name)
                continue
            if (str(r.get("track", "")).upper(), r.get("race_date")) in cards:
                continue
            kept.append(line)

    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for line in kept:
            print(line, file=f)
        for row in rows:
            print(json.dumps(row, ensure_ascii=False), file=f)
    os.replace(tmp, path)
    return len(kept) + len(rows)


def latest_run_only(scored: list[dict]) -> list[dict]:
    """Keep one opinion per race: the most recently generated run.

    A card is often run more than once -- a re-run after a scratch, a second
    model -- and every run is kept in the scored file because the audit trail
    is the point. Rates are a different question: counting a race twice
    because it was predicted twice silently weights whichever races happened
    to get re-run. For a headline rate, the latest run per race wins.

    Piece 3 must do the same before aggregating, or a card that was re-run
    will pull the rolling average toward its own result.
    """
    latest: dict[tuple, dict] = {}
    for r in scored:
        key = (r["track"], r["race_date"], r["race_num"])
        cur = latest.get(key)
        if cur is None or (r.get("generated_at") or "") > (cur.get("generated_at") or ""):
            latest[key] = r
    keep = {(k, v.get("generated_at")) for k, v in latest.items()}
    return [r for r in scored
            if ((r["track"], r["race_date"], r["race_num"]),
                r.get("generated_at")) in keep]


def print_summary(track: str, date: str, scored: list[dict], stats: dict) -> None:
    ns = len(stats["races_scored"])
    nk = len(stats["races_skipped"])
    print(f"\n{track.upper()} {date}")
    print(f"  races scored:         {ns}"
          + (f"   (skipped {nk}, results not loaded: "
             f"{sorted(stats['races_skipped'])})" if nk else ""))
    print(f"  predictions read:     {stats['predictions']}"
          f"   ({stats['runs']} race-runs)")
    print(f"  scored rows:          {len(scored)}")
    if stats["no_result"]:
        print(f"  no outcome:           {stats['no_result']}"
              f"   (scratched {stats['scratched']}, "
              f"no result recorded {stats['no_record']}, "
              f"unmatched {stats['unmatched']})")
    if stats["dnf"]:
        print(f"  DNF (ran, no pos):    {stats['dnf']}")
    if not scored:
        return

    # Rates are per race, not per prediction run -- see latest_run_only.
    current = latest_run_only(scored)
    superseded = len(scored) - len(current)
    if superseded:
        print(f"  superseded rows:      {superseded}"
              f"   (earlier runs of a re-run race, excluded from rates below)")

    tops = [r for r in current if r["was_top_pick"]]
    live = [r for r in tops if not r["top_pick_scratched"]]
    if live:
        itm = sum(1 for r in live if r["hit_itm"])
        win = sum(1 for r in live if r["hit_win"])
        print(f"  top pick ITM:         {itm} / {len(live)} = "
              f"{100 * itm / len(live):.1f}%")
        print(f"  top pick WIN:         {win} / {len(live)} = "
              f"{100 * win / len(live):.1f}%")
        stake = 2.0 * len(live)
        ret = sum(r["show_payoff"] or 0.0 for r in live)
        print(f"  top pick show ROI:    ${ret:.2f} back on ${stake:.2f} = "
              f"{100 * (ret - stake) / stake:+.1f}%")
    dead = len(tops) - len(live)
    if dead:
        print(f"  top picks w/o result: {dead}"
              f"   (excluded from the rates above)")
    all_itm = sum(1 for r in current if r["hit_itm"])
    print(f"  all horses ITM:       {all_itm} / {len(current)} = "
          f"{100 * all_itm / len(current):.1f}%")


# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(
        description="Score logged DPv1 predictions against actual results "
                    "(Phase 6E piece 2).")
    p.add_argument("--track", help="track code, e.g. CT")
    p.add_argument("--date", help="race date, YYYY-MM-DD")
    p.add_argument("--all", action="store_true",
                   help="score every card present in predictions.jsonl "
                        "(retro-scoring); --track narrows it to one track")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--pred-file", default=str(PRED_FILE))
    p.add_argument("--out-file", default=str(SCORED_FILE))
    p.add_argument("--dry-run", action="store_true",
                   help="score and summarise but do not write the output file")
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    if not args.all and not (args.track and args.date):
        raise SystemExit("give --track and --date, or --all")

    pred_path = Path(args.pred_file)
    if args.all:
        every = load_predictions(pred_path, track=args.track)
        cards = sorted({(str(r["track"]).upper(), r["race_date"])
                        for r in every})
        if not cards:
            raise SystemExit(f"no predictions in {pred_path}")
    else:
        cards = [(args.track.upper(), args.date)]

    all_scored: list[dict] = []
    scored_cards: set[tuple[str, str]] = set()
    for track, date in cards:
        preds = load_predictions(pred_path, track=track, date=date)
        if not preds:
            log.warning("no predictions logged for %s %s", track, date)
            print(f"\n{track} {date}")
            print("  no predictions logged -- nothing to score")
            continue
        results = fetch_results(args.db, track, date)
        if not results["entries"]:
            log.warning("%s %s is not in the database at all", track, date)
        scored, stats = score_card(preds, results)
        print_summary(track, date, scored, stats)
        if not results["have_results"]:
            print("  ** results not loaded for this card -- nothing scored **")
        all_scored.extend(scored)
        scored_cards.add((track, date))

    if args.dry_run:
        print(f"\ndry run: {len(all_scored)} rows not written")
        return 0

    total = write_scored(all_scored, scored_cards, Path(args.out_file))
    print(f"\nwrote {len(all_scored)} scored rows "
          f"({total} total in {Path(args.out_file)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
