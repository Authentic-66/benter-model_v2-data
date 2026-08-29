"""One-off: back-fill predictions.jsonl from picks CSVs written before Piece 1.

ELP 2026-08-22 and 2026-08-23 were predicted before ``card_picks.py`` learned to
log, so they exist only as ``picks/*.csv``. Piece 3 cannot report on a card that
is not in the log, and re-predicting them today would not reproduce them: the
charts have since been loaded, so the field is now the post-scratch starter list
rather than what was on the board pre-race, and the Harville inversion would
renormalise over a different set of horses. The CSV is the actual pre-race
opinion, so the CSV is what gets back-filled.

    python scripts_dpv1/_backfill_picks_csv.py --dry-run
    python scripts_dpv1/_backfill_picks_csv.py --execute

Model provenance
----------------
The CSV carries no model version, but the ``.txt`` written beside it does: the
runner's header line reads ``DPv1 <version> -- <TRACK> <date>``. That is the
authoritative record of which model actually produced the picks, so it is
parsed out and written to ``model_version``, with
``backfill_attribution = "picks_file_header"`` recording where the attribution
came from.

Both back-filled cards resolve to ``dpv1.2.0-4track``. The timeline is tight
and worth stating, because the naive reading of it is wrong: ``dpv1.pkl`` has
``trained_at = 2026-08-22T14:20:19Z``, and local time here is UTC-5, so the
4-track model finished training at **09:20 local** and these cards were
generated at 09:24 and 09:44 local -- minutes later, on the freshly trained
model. Comparing those local clock times against the UTC timestamp without
converting makes it look like the picks predate the model. They do not.

The *earlier* runs of both cards -- ELP 8/22 at 08:13 and ELP 8/23 the previous
night at 23:30 -- carry ``dpv1.1.0`` in their headers, which is why the runs
back-filled here are the 09:24/09:44 pair and not simply the first file found.

``model_pkl`` stays null: the header records a version, not an artifact
filename, and inventing one would be a guess dressed as a record.
``race_coverage`` is reconstructed as the mean of the per-horse ``cov`` column,
which is close to but not identical with the runner's own race-level figure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DPV1_DIR))

from card_picks import LOG_DIR, append_predictions, _jsonable, _round  # noqa: E402

# The original pre-race picks. Explicit, not globbed: the directory also holds
# later re-runs of the same cards, and picking "the newest" would silently
# choose the wrong opinion.
SOURCES = [
    ("ELP", "2026-08-22", "ELP_2026-08-22_20260822-0944.csv"),
    ("ELP", "2026-08-23", "ELP_2026-08-23_20260822-0924.csv"),
]


def stamp_from_name(name: str) -> tuple[str, datetime]:
    """'ELP_2026-08-23_20260822-0924.csv' -> ('20260822-0924', datetime)."""
    stamp = Path(name).stem.rsplit("_", 1)[1]
    return stamp, datetime.strptime(stamp, "%Y%m%d-%H%M")


def version_from_txt(csv_name: str) -> tuple[str | None, str | None]:
    """Read the model version out of the picks .txt header.

    The runner writes ``  DPv1 <version> -- <TRACK> <date>`` as its second
    line. Returns (version, attribution) so callers can record *how* the
    attribution was established rather than just asserting it.
    """
    txt = DPV1_DIR / "picks" / (Path(csv_name).stem + ".txt")
    if not txt.exists():
        return None, None
    for line in txt.read_text(encoding="utf-8").splitlines()[:6]:
        line = line.strip()
        if line.startswith("DPv1 "):
            version = line.split()[1]
            return version, "picks_file_header"
    return None, None


def rows_from_csv(track: str, date: str, csv_name: str) -> list[dict]:
    path = DPV1_DIR / "picks" / csv_name
    df = pd.read_csv(path)
    stamp, generated_at = stamp_from_name(csv_name)
    picks_file = f"picks/{Path(csv_name).stem}.txt"
    version, attribution = version_from_txt(csv_name)

    rows: list[dict] = []
    for race_num, grp in df.groupby("race_num", sort=True):
        race_cov = _round(grp["cov"].mean(), 4)
        for _, h in grp.iterrows():
            pgm = _jsonable(h.get("pgm"))
            pgm = str(pgm) if pgm is not None else None
            rows.append({
                "prediction_id": (f"{track}_{date}_R{int(race_num)}"
                                  f"_pgm{pgm}_{stamp}"),
                "generated_at": generated_at.isoformat(timespec="seconds"),
                "track": track,
                "race_date": date,
                "race_num": int(race_num),
                "pgm": pgm,
                "horse_name": _jsonable(h.get("horse")),
                "p_itm": _round(h.get("P(ITM)"), 4),
                "p_win": _round(h.get("P(win)"), 4),
                "coverage": _round(h.get("cov"), 4),
                "race_coverage": race_cov,
                "ml_odds": _jsonable(h.get("ML")),
                "prime_power": _jsonable(h.get("PrimePwr")),
                "model_version": version,
                "model_pkl": None,   # the header records a version, not a filename
                "backfill_attribution": attribution,
                "rank": _jsonable(h.get("rank")),
                "n_horses_in_race": int(len(grp)),
                "picks_file": picks_file,
                "backfilled": True,
            })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Back-fill predictions.jsonl from picks CSVs.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--execute", action="store_true")
    ap.add_argument("--log-file", default=str(LOG_DIR / "predictions.jsonl"))
    ap.add_argument("--replace", action="store_true",
                    help="rewrite previously back-filled rows for these cards "
                         "instead of skipping them as duplicates -- use when "
                         "the attribution or the source CSV has changed")
    args = ap.parse_args()

    log_path = Path(args.log_file)
    existing = set()
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing.add(json.loads(line)["prediction_id"])

    all_rows: list[dict] = []
    for track, date, csv_name in SOURCES:
        rows = rows_from_csv(track, date, csv_name)
        version = rows[0].get("model_version") if rows else None
        attribution = rows[0].get("backfill_attribution") if rows else None
        dupes = [r for r in rows if r["prediction_id"] in existing]
        fresh = rows if args.replace else [
            r for r in rows if r["prediction_id"] not in existing]
        races = sorted({r["race_num"] for r in rows})
        print(f"{track} {date}: {len(rows)} rows over {len(races)} races "
              f"from {csv_name}")
        print(f"   model_version={version!r} via {attribution!r}")
        if dupes:
            print(f"   {len(dupes)} already in log -- "
                  f"{'REPLACING' if args.replace else 'skipped'}")
        all_rows.extend(fresh)

    if not args.execute:
        print(f"\ndry run: {len(all_rows)} rows not written")
        return 0

    if args.replace:
        # Drop every prior row for these cards, then re-append. Same
        # rewrite-via-temp discipline the scorer uses: the log is append-only
        # in normal operation, and this is the one sanctioned exception.
        cards = {(t, d) for t, d, _ in SOURCES}
        kept = [l for l in log_path.read_text(encoding="utf-8").splitlines()
                if l.strip() and (lambda r: (r.get("track"), r.get("race_date"))
                                  not in cards)(json.loads(l))]
        tmp = log_path.with_suffix(log_path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for line in kept:
                print(line, file=f)
        os.replace(tmp, log_path)
        print(f"\ndropped prior rows for {sorted(cards)}; kept {len(kept)}")

    n = append_predictions(all_rows, log_path)
    print(f"appended {n} rows to {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
