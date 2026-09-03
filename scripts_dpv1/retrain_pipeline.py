"""Phase 6E piece 4: weekly retrain pipeline.

    python scripts_dpv1/retrain_pipeline.py            # dry run (default)
    python scripts_dpv1/retrain_pipeline.py --execute  # actually do it

Loads any result charts that are on disk but not in the database, rebuilds
features, trains a candidate model to a dated artifact, evaluates it against
the current one, and prints a recommendation.

**It never promotes.** The last thing it prints is the copy command for a human
to run, and that is the whole point: the comparison below is evidence, not a
decision.

Ordering is not negotiable
--------------------------
Three orderings here were each established by a bug that cost real work, and
the pipeline enforces all three.

1. **Purge before load.** ``entries`` carries ``UNIQUE(race_id, program_num)``
   and ``db_loader`` inserts with ``INSERT OR IGNORE``, while
   ``ingest_race_day``/``ingest_race`` return the *existing* row when the day
   is already present. Loading a chart onto a day already loaded as an upcoming
   card therefore silently drops every result row and reports success.

2. **Rebuild features after loading.** Purging a card cascades to
   ``entry_features_dpv1`` and ``computed_speed_figures_dpv1`` — they key on
   ``entry_id``. Skip the rebuild and ``card_picks.py`` refuses the reloaded
   cards with "no rows in entry_features_dpv1", and the trainer sees a corpus
   with holes in it.

3. **Deduplicate by content, not by filename.** The backlog loader was caught
   about to purge and reload CT 2026-08-01 because that day's chart exists
   twice on disk — ``...standard.pdf`` and ``...standard (1).pdf``, byte
   identical. Once the canonical copy is in ``parsed_files`` the twin no longer
   groups with it and reads as a fresh chart. Every candidate here is checked
   against ``parsed_files.file_sha256``.

What the comparison can and cannot tell you
-------------------------------------------
The spec asks for ``model_health.py --model <new>`` against the current model.
That cannot work as written, and the reason matters: ``model_health`` reads
*scored live predictions*, and a model trained ninety seconds ago has never
made a pick. Its live sample is zero by construction, and it stays zero until
the candidate has been run on real cards for weeks.

So the primary comparison here is **cross-validated fold predictions** — the
out-of-sample predictions ``train_dpv1.py final`` produces for every race in
the corpus, on the same year-fold splits for both models, restricted to the
races both models actually scored. That is a genuine held-out comparison with
five figures of sample behind it.

The live comparison is still printed, because it is the number that eventually
matters, but it is reported with its true ``n`` rather than dressed up. For a
fresh candidate that ``n`` is 0 and the report says so.

Sample-size gate
----------------
No recommendation to promote is issued below ``MIN_RACES_FOR_RECOMMENDATION``
fold races. The live baseline at the time of writing was 29-40 races and was
carried by a single 8-for-8 card, which is not evidence; the fold comparison
has far more, but the gate stays because a corpus can shrink.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
REPO = DPV1_DIR.parent
LOG_DIR = DPV1_DIR / "logs"
sys.path.insert(0, str(DPV1_DIR))
sys.path.insert(0, str(REPO / "scripts"))

from dpv1_runtime import DEFAULT_DB, DEFAULT_MODEL, load_model, to_utc  # noqa: E402

HISTORY_FILE = LOG_DIR / "retrain_history.jsonl"
SCORED_FILE = LOG_DIR / "scored_predictions.jsonl"

# Result-chart directories, keyed by track code. Only the four training tracks
# are loaded by default: the repo also carries charts for Delta Downs,
# Evangeline, Fair Grounds and Fairmount Park, and pulling those in would
# expand the corpus into tracks the model does not train on. That is a decision
# for a human, so --all-tracks exists and the default reports what it skipped.
TRACK_DIRS = {
    "CT": "CharlesTown",
    "ELP": "Ellis",
    "GP": "Gulfstream Park",
    "MNR": "Mountaineer",
}
EXTRA_TRACK_DIRS = {
    "DD": "Delta Downs",
    "EVD": "Evangeline Downs",
    "FG": "Fair Grounds",
    "FP": "Fairmount Park",
}

KEEP_MODEL_VERSIONS = 5
MIN_RACES_FOR_RECOMMENDATION = 500
# A metric has to move by more than this to count as a real change rather than
# fold noise. Applied to ITM and win rate, which are proportions.
MATERIAL_PP = 0.5

log = logging.getLogger("retrain_pipeline")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rule(title: str) -> None:
    print("\n" + "=" * 74)
    print(f" {title}")
    print("=" * 74)


# ---------------------------------------------------------------------------
# Phase 1 - discover charts that are on disk but not in the database
# ---------------------------------------------------------------------------

def discover_charts(conn: sqlite3.Connection, all_tracks: bool = False) -> dict:
    """Result charts present on disk and absent from ``parsed_files``.

    Matched three ways -- repo-relative path, bare filename, and sha256 -- and
    the hash is the one that matters. See ordering note 3 in the module
    docstring.
    """
    rows = conn.execute(
        "SELECT source_pdf, file_sha256 FROM parsed_files WHERE success = 1"
    ).fetchall()
    known = {r[0].replace("\\", "/").lower() for r in rows}
    known_names = {Path(k).name for k in known}
    known_shas = {r[1] for r in rows if r[1]}

    dirs = dict(TRACK_DIRS)
    if all_tracks:
        dirs.update(EXTRA_TRACK_DIRS)

    pending: dict[str, list[Path]] = {}
    dupes: list[tuple[Path, str]] = []
    for code, folder in sorted(dirs.items()):
        found = []
        for pdf in sorted((REPO / folder).glob("*-results-*/*.pdf")):
            rel = str(pdf.relative_to(REPO)).replace("\\", "/").lower()
            if rel in known or pdf.name.lower() in known_names:
                continue
            if _sha(pdf) in known_shas:
                dupes.append((pdf, "content already loaded under another name"))
                continue
            found.append(pdf)
        if found:
            pending[code] = found

    skipped = {}
    if not all_tracks:
        for code, folder in sorted(EXTRA_TRACK_DIRS.items()):
            n = sum(1 for _ in (REPO / folder).glob("*-results-*/*.pdf"))
            if n:
                skipped[code] = n
    return {"pending": pending, "dupes": dupes, "skipped_tracks": skipped}


# ---------------------------------------------------------------------------
# Phase 2 - loaded upcoming cards
# ---------------------------------------------------------------------------

def loaded_upcoming_cards(conn: sqlite3.Connection) -> list[tuple[str, str, int, int]]:
    """Cards with entries but no finishers -- the NaN-as-False hazard.

    ``y_true = (finish_pos <= 3)`` evaluates NaN to False, so an unrun card in
    ``entries`` is a race in which every horse is labelled as having missed the
    board. The test is zero *finishers in the race*, not a null finish on an
    entry: a scratch is a null finish in a race that did run, and those are
    legitimate.
    """
    return [tuple(r) for r in conn.execute("""
        SELECT t.code, rd.race_date,
               COUNT(DISTINCT rc.id), COUNT(e.id)
        FROM races rc
        JOIN race_days rd ON rd.id = rc.race_day_id
        JOIN tracks t     ON t.id  = rd.track_id
        JOIN entries e    ON e.race_id = rc.id
        GROUP BY t.code, rd.race_date
        HAVING SUM(CASE WHEN e.finish_status = 'finished' THEN 1 ELSE 0 END) = 0
        ORDER BY rd.race_date
    """)]


def verify_label_guard(db: str, tracks: list[str]) -> dict:
    """Confirm no unrun race survives into the training labels.

    The spec says to refuse the retrain if loaded upcoming cards are found.
    Taken literally that would block every retrain in normal operation, because
    a card loaded for tonight's picks is an upcoming card and is *supposed* to
    be there. ``prepare_training_dpv1.drop_unrun_races`` already removes them,
    and has since Phase 6C.

    So this checks the thing that actually matters rather than the proxy: build
    the training frame and assert that no race in it has zero finishers. If one
    survives, the guard failed and the caller refuses.
    """
    import prepare_training_dpv1 as prep

    df = prep.load_full_frame(db, tracks=tuple(tracks))
    finishers = df.groupby("race_id")["finish_pos"].transform("count")
    bad = df[finishers == 0]
    return {"n_rows": int(len(df)), "n_races": int(df["race_id"].nunique()),
            "unrun_rows": int(len(bad)),
            "unrun_races": int(bad["race_id"].nunique()) if len(bad) else 0,
            "ok": len(bad) == 0}


# ---------------------------------------------------------------------------
# Phase 3 - load
# ---------------------------------------------------------------------------

def purge_card(conn: sqlite3.Connection, track: str, date: str) -> dict:
    """Remove one loaded card entirely: derived rows, entries, races, day."""
    DERIVED = ["entry_features_dpv1", "entry_features_v1", "entry_pp_features",
               "computed_speed_figures", "computed_speed_figures_dpv1",
               "entry_v10_flags"]
    entry_ids = [r[0] for r in conn.execute(
        """SELECT e.id FROM entries e
           JOIN races r      ON r.id  = e.race_id
           JOIN race_days rd ON rd.id = r.race_day_id
           JOIN tracks t     ON t.id  = rd.track_id
           WHERE t.code = ? AND rd.race_date = ?""", (track, date))]
    race_ids = [r[0] for r in conn.execute(
        """SELECT r.id FROM races r
           JOIN race_days rd ON rd.id = r.race_day_id
           JOIN tracks t     ON t.id  = rd.track_id
           WHERE t.code = ? AND rd.race_date = ?""", (track, date))]
    day_ids = [r[0] for r in conn.execute(
        """SELECT rd.id FROM race_days rd JOIN tracks t ON t.id = rd.track_id
           WHERE t.code = ? AND rd.race_date = ?""", (track, date))]

    counts = {"entries": len(entry_ids), "races": len(race_ids),
              "derived": 0, "exotics": 0}
    if entry_ids:
        q = ",".join("?" * len(entry_ids))
        for tbl in DERIVED:
            try:
                counts["derived"] += conn.execute(
                    f"DELETE FROM {tbl} WHERE entry_id IN ({q})", entry_ids).rowcount
            except sqlite3.OperationalError:
                pass
        conn.execute(f"DELETE FROM entries WHERE id IN ({q})", entry_ids)
    if race_ids:
        q = ",".join("?" * len(race_ids))
        counts["exotics"] = conn.execute(
            f"DELETE FROM exotic_payouts WHERE race_id IN ({q})", race_ids).rowcount
        conn.execute(f"DELETE FROM races WHERE id IN ({q})", race_ids)
    if day_ids:
        q = ",".join("?" * len(day_ids))
        conn.execute(f"DELETE FROM race_days WHERE id IN ({q})", day_ids)
    return counts


def load_charts(conn: sqlite3.Connection, pdfs: list[Path],
                cache: Path) -> dict:
    """Parse and ingest charts, purging any day that is already populated."""
    import db_loader
    import equibase_pdf_parser as parser

    cache.mkdir(parents=True, exist_ok=True)
    totals = {"races": 0, "entries": 0, "exotics": 0, "purged_entries": 0,
              "cards": 0, "errors": 0}
    detail = []
    for pdf in pdfs:
        try:
            cached = cache / (pdf.stem + ".json")
            parsed = None
            if cached.exists():
                try:
                    cand = json.loads(cached.read_text(encoding="utf-8"))
                    if cand.get("file_sha256") == _sha(pdf):
                        parsed = cand
                except (json.JSONDecodeError, OSError):
                    parsed = None
            if parsed is None:
                parsed = parser.parse_pdf(pdf)
                cached.write_text(json.dumps(parsed, indent=2), encoding="utf-8")

            track, date = parsed.get("track_code"), parsed.get("race_date")
            if not track or not date or not parsed.get("race_count"):
                log.warning("%s is not a result chart, skipped", pdf.name)
                continue
            parsed["source_pdf"] = str(pdf.relative_to(REPO)).replace("/", "\\")

            existing = conn.execute(
                """SELECT COUNT(*) FROM entries e
                   JOIN races r      ON r.id  = e.race_id
                   JOIN race_days rd ON rd.id = r.race_day_id
                   JOIN tracks t     ON t.id  = rd.track_id
                   WHERE t.code = ? AND rd.race_date = ?""",
                (track, date)).fetchone()[0]

            with conn:
                purged = purge_card(conn, track, date) if existing else None
                counts = db_loader.ingest_parsed_pdf(conn, parsed)
                warnings = [w for r in parsed["races"]
                            for w in (r.get("warnings") or [])]
                db_loader.record_parsed_file(
                    conn, source_pdf=parsed["source_pdf"],
                    sha256=parsed.get("file_sha256", ""),
                    races_found=parsed.get("race_count", 0),
                    races_loaded=counts["races"], success=True,
                    error_message=None,
                    warnings_json=json.dumps(warnings) if warnings else None)
            for k in ("races", "entries", "exotics"):
                totals[k] += counts[k]
            totals["cards"] += 1
            if purged:
                totals["purged_entries"] += purged["entries"]
            detail.append({"pdf": pdf.name, "track": track, "date": date,
                           "races": counts["races"], "entries": counts["entries"],
                           "purged": purged["entries"] if purged else 0})
            print(f"  {pdf.name:<45} {track} {date}  "
                  f"+{counts['races']}r {counts['entries']}e"
                  + (f"  (purged {purged['entries']} first)" if purged else ""))
        except Exception as exc:  # noqa: BLE001 - one bad chart must not abort
            totals["errors"] += 1
            log.warning("%s failed to load: %s", pdf.name, exc)
    return {"totals": totals, "detail": detail}


# ---------------------------------------------------------------------------
# Phase 4/5 - rebuild + train
# ---------------------------------------------------------------------------

def run(cmd: list[str], label: str) -> None:
    print(f"  $ {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    if res.returncode != 0:
        tail = (res.stderr or res.stdout or "").strip().splitlines()[-15:]
        raise SystemExit(f"{label} failed (exit {res.returncode}):\n"
                         + "\n".join(tail))
    for line in (res.stderr or "").strip().splitlines()[-4:]:
        print(f"    {line}")


def bump_version(current: str) -> str:
    """dpv1.2.0-4track -> dpv1.2.1-4track.

    The candidate must carry a version string distinct from the current one:
    Piece 3 filters the scored log by ``model_version``, so two models sharing
    a version are indistinguishable in every health report afterwards.
    """
    head, _, suffix = current.partition("-")
    parts = head.split(".")
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].isdigit():
            parts[i] = str(int(parts[i]) + 1)
            break
    else:
        return f"{current}-r{datetime.now():%Y%m%d}"
    return ".".join(parts) + (f"-{suffix}" if suffix else "")


# ---------------------------------------------------------------------------
# Phase 6 - evaluation
# ---------------------------------------------------------------------------

def fold_metrics(path: Path, race_ids: set | None = None) -> dict:
    """Top-pick metrics from a fold-prediction file.

    Ranks by ``p_fund`` because that is what ``card_picks.py`` ranks by --
    the fundamental side alone, with no market input. Ranking by the blended
    ``y_pred`` would measure a model nobody uses to pick horses.
    """
    df = pd.read_csv(path)
    if race_ids is not None:
        df = df[df["race_id"].isin(race_ids)]
    if df.empty:
        return {"n_races": 0}
    pf = df["p_fund"].clip(1e-9, 1 - 1e-9)
    df = df.sort_values(["race_id", "p_fund"], ascending=[True, False])
    top = df.groupby("race_id").head(1)
    # A race with no recorded winner (disqualification) cannot be a win; it is
    # still a valid ITM denominator because the board is well defined.
    has_winner = df.groupby("race_id")["finish_pos"].apply(
        lambda s: (s == 1).any())
    top = top.assign(_win_ok=top["race_id"].map(has_winner))
    itm = top["y_true"].astype(bool)
    win = (top["finish_pos"] == 1)
    win_pool = top[top["_win_ok"].fillna(False)]
    return {
        "n_races": int(len(top)),
        "itm_n": int(itm.sum()), "itm_d": int(len(top)),
        "itm": float(itm.mean()),
        "win_n": int((win_pool["finish_pos"] == 1).sum()),
        "win_d": int(len(win_pool)),
        "win": float((win_pool["finish_pos"] == 1).mean()) if len(win_pool) else float("nan"),
        "logloss_fund": float(-(
            df["y_true"] * np.log(pf) + (1 - df["y_true"]) * np.log(1 - pf)
        ).mean()),
    }


def live_metrics(version: str) -> dict:
    """Top-pick metrics from the live scored log, filtered by model_version.

    By version string, never by ``model_pkl``: back-filled rows carry a version
    read off the picks-file header but no artifact filename, so filtering on
    the filename silently drops legitimate baseline races.
    """
    if not SCORED_FILE.exists():
        return {"n_races": 0}
    from score_predictions import latest_run_only
    rows = [json.loads(l) for l in
            SCORED_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in latest_run_only(rows) if r.get("model_version") == version]
    races = defaultdict(list)
    for r in rows:
        races[(r["track"], r["race_date"], r["race_num"])].append(r)
    itm_n = itm_d = win_n = win_d = 0
    stake = ret = 0.0
    for g in races.values():
        top = [x for x in g if x.get("was_top_pick")]
        if not top or g[0].get("top_pick_scratched"):
            continue
        t = top[0]
        itm_d += 1
        itm_n += bool(t["hit_itm"])
        stake += 2.0
        ret += t.get("show_payoff") or 0.0
        if any(x.get("actual_finish") == 1 for x in g):
            win_d += 1
            win_n += bool(t["hit_win"])
    return {"n_races": itm_d, "itm_n": itm_n, "itm_d": itm_d,
            "itm": itm_n / itm_d if itm_d else float("nan"),
            "win_n": win_n, "win_d": win_d,
            "win": win_n / win_d if win_d else float("nan"),
            "roi": (ret - stake) / stake if stake else float("nan"),
            "stake": stake, "ret": ret}


def _fmt_pct(v) -> str:
    return "   --" if v is None or v != v else f"{100 * v:5.1f}%"


def print_comparison(cur_name: str, cur_ver: str, cand_name: str, cand_ver: str,
                     cur_fold: dict, cand_fold: dict,
                     cur_live: dict, cand_live: dict) -> list[str]:
    _rule("CANDIDATE vs CURRENT")
    print(f" CANDIDATE:  {cand_name}  ({cand_ver})")
    print(f" CURRENT:    {cur_name}  ({cur_ver})")

    print(f"\n--- Cross-validated fold predictions "
          f"({cur_fold.get('n_races', 0)} shared races) ---")
    print(f" {'Metric':<22}{'Current':>10}{'Candidate':>12}{'Delta':>12}")
    verdicts = []
    for label, key in (("ITM (top pick)", "itm"), ("Win (top pick)", "win")):
        c, k = cur_fold.get(key), cand_fold.get(key)
        if c is None or k is None or c != c or k != k:
            continue
        d = 100 * (k - c)
        mark = "better" if d > MATERIAL_PP else "worse" if d < -MATERIAL_PP else "flat"
        verdicts.append((label, d, mark))
        print(f" {label:<22}{_fmt_pct(c):>10}{_fmt_pct(k):>12}"
              f"{d:>+9.1f}pp  {mark}")

    print(f"\n--- Live scored picks (by model_version) ---")
    for who, m, ver in (("Current", cur_live, cur_ver), ("Candidate", cand_live, cand_ver)):
        if m.get("n_races"):
            print(f" {who:<10} {ver:<22} ITM {m['itm_n']}/{m['itm_d']} = "
                  f"{_fmt_pct(m['itm'])}   ROI {100 * m['roi']:+.1f}%")
        else:
            print(f" {who:<10} {ver:<22} no scored races")
    if not cand_live.get("n_races"):
        print("\n A model trained minutes ago has never made a live pick, so its")
        print(" live sample is zero by construction. It stays zero until the")
        print(" candidate has been run on real cards. Nothing can be concluded")
        print(" from the live block at retrain time -- it is printed so the")
        print(" current model's live record is visible beside the fold numbers.")
    return verdicts


def recommend(verdicts: list[tuple], n_races: int) -> str:
    _rule("RECOMMENDATION")
    if n_races < MIN_RACES_FOR_RECOMMENDATION:
        print(f" INSUFFICIENT EVIDENCE -- {n_races} shared fold races is below the")
        print(f" {MIN_RACES_FOR_RECOMMENDATION}-race floor this pipeline requires before it will")
        print(" argue either way. Do not promote on these numbers.")
        return "insufficient_evidence"
    better = [v for v in verdicts if v[2] == "better"]
    worse = [v for v in verdicts if v[2] == "worse"]
    if worse:
        print(" DO NOT PROMOTE -- candidate is worse on: "
              + ", ".join(f"{l} ({d:+.1f}pp)" for l, d, _ in worse))
        return "do_not_promote"
    if not better:
        print(" NO MATERIAL CHANGE -- every metric moved less than "
              f"{MATERIAL_PP}pp. The candidate is trained on more data, which is")
        print(" a reason to promote on principle, but this comparison is not")
        print(" evidence for it. Your call.")
        return "no_material_change"
    print(" CANDIDATE OUTPERFORMS on: "
          + ", ".join(f"{l} ({d:+.1f}pp)" for l, d, _ in better))
    if len(better) < len(verdicts):
        print(" (other metrics unchanged)")
    return "candidate_better"


# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

def is_pipeline_candidate(path: Path) -> bool:
    """True for artifacts this pipeline produced, and only those.

    Two accepted shapes:

    * ``dpv1_YYYYMMDD.pkl`` — the original, kept for backward compatibility
      with artifacts already on disk.
    * ``dpv1_YYYYMMDD_HHMMSS.pkl`` — the current form, collision-free by
      construction.

    Deliberately excluded: anything with a non-numeric suffix, such as
    ``dpv1_20260831_corpus_only.pkl`` or ``dpv1_20260831_interact.pkl``. Those
    are one-off research artifacts kept as controls for later comparisons, not
    production candidates, and the pruner must never reap them. The shipped
    ``dpv1.pkl`` and the named ``dpv1_3track.pkl`` fail the prefix test and are
    likewise untouchable.
    """
    stem = path.stem
    if not stem.startswith("dpv1_"):
        return False
    parts = stem[len("dpv1_"):].split("_")
    if not all(p.isdigit() for p in parts):
        return False
    return (len(parts) == 1 and len(parts[0]) == 8) or \
           (len(parts) == 2 and len(parts[0]) == 8 and len(parts[1]) == 6)


def prune_models(keep: int = KEEP_MODEL_VERSIONS, execute: bool = False) -> list[str]:
    """Keep the newest ``keep`` pipeline artifacts; delete older ones.

    Sorting is lexicographic on the stem, which is chronological for both
    accepted shapes because the timestamp is zero-padded and fixed-width.
    ``dpv1_20260831`` sorts before ``dpv1_20260831_120000``, which is the
    correct order: a date-only artifact predates any same-day timestamped one.
    """
    dated = sorted((p for p in DPV1_DIR.glob("dpv1_*.pkl")
                    if is_pipeline_candidate(p)),
                   key=lambda p: p.stem)
    doomed = dated[:-keep] if len(dated) > keep else []
    for p in doomed:
        print(f"  {'deleting' if execute else 'would delete'} {p.name}")
        if execute:
            p.unlink()
    return [p.name for p in doomed]


def append_history(event: dict) -> None:
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            print(json.dumps(event, ensure_ascii=False), file=f)
    except OSError as exc:
        log.warning("retrain history not written: %s", exc)


# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(
        description="DPv1 weekly retrain pipeline (Phase 6E piece 4).")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True,
                   help="report what would happen, touch nothing (default)")
    g.add_argument("--execute", action="store_true",
                   help="load, rebuild, train and evaluate for real")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--model", default=str(DEFAULT_MODEL),
                   help="current model, the comparison baseline")
    p.add_argument("--all-tracks", action="store_true",
                   help="also load charts for tracks outside the training set")
    p.add_argument("--skip-load", action="store_true",
                   help="skip chart loading; retrain on the corpus as it is")
    p.add_argument("--version", default=None,
                   help="candidate version string (default: bump the current)")
    p.add_argument("--keep", type=int, default=KEEP_MODEL_VERSIONS)
    args = p.parse_args()
    execute = args.execute

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    started = datetime.now(timezone.utc)

    current = load_model(args.model)
    tracks = list(current.hyperparameters.get("tracks", ["GP", "CT", "MNR", "ELP"]))
    cand_version = args.version or bump_version(current.version)
    # Second resolution, not date: two retrains in one day used to collide on
    # dpv1_YYYYMMDD.pkl and the second silently overwrote the first. That bit
    # on 2026-08-31, when a feature-set retrain would have destroyed the
    # corpus-only control being held deliberately for comparison.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cand_path = DPV1_DIR / f"dpv1_{stamp}.pkl"
    cand_folds = DPV1_DIR / f"dpv1_fold_predictions_{stamp}.csv"

    _rule(f"DPv1 RETRAIN PIPELINE -- {'EXECUTE' if execute else 'DRY RUN'}")
    print(f" current model:   {Path(args.model).name}  ({current.version})")
    print(f"   trained at:    {to_utc(current.trained_at)}")
    age = started - to_utc(current.trained_at)
    print(f"   age:           {age.days}d {age.seconds // 3600}h")
    print(f" candidate:       {cand_path.name}  ({cand_version})")
    print(f" training tracks: {', '.join(tracks)}")

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        # --- Phase 1: discover -------------------------------------------
        _rule("1. NEW RESULT CHARTS")
        disc = discover_charts(conn, all_tracks=args.all_tracks)
        pending = [p for v in disc["pending"].values() for p in v]
        for pdf, why in disc["dupes"]:
            print(f"  SKIP  {pdf.name}  ({why})")
        if pending:
            for code, files in sorted(disc["pending"].items()):
                print(f"  {code}: {len(files)} chart(s)")
                for f in files[:20]:
                    print(f"       {f.name}")
                if len(files) > 20:
                    print(f"       ... and {len(files) - 20} more")
        else:
            print("  none -- the database is current with what is on disk")
        if disc["skipped_tracks"]:
            print("\n  not loaded (outside the training tracks; --all-tracks to include):")
            for code, n in disc["skipped_tracks"].items():
                print(f"       {code}: {n} chart(s) on disk")

        # --- Phase 2: upcoming cards -------------------------------------
        _rule("2. LOADED UPCOMING CARDS (NaN-as-False hazard)")
        upcoming = loaded_upcoming_cards(conn)
        if upcoming:
            for code, date, nr, ne in upcoming:
                print(f"  {code} {date}: {nr} races, {ne} entries, no results")
            print("\n  Any of these with a chart on disk are purged and reloaded")
            print("  below. Any without are genuinely upcoming and are dropped")
            print("  from the training labels by drop_unrun_races.")
        else:
            print("  none")

        # --- Phase 3: load ------------------------------------------------
        _rule("3. LOAD")
        loaded = {"totals": {"cards": 0, "races": 0, "entries": 0,
                             "purged_entries": 0, "errors": 0}, "detail": []}
        if args.skip_load:
            print("  --skip-load: not loading anything")
        elif not pending:
            print("  nothing to load")
        elif not execute:
            print(f"  would load {len(pending)} chart(s), purging first where a")
            print("  day is already populated")
        else:
            loaded = load_charts(conn, pending, REPO / "scripts" / "ct_cache")
            t = loaded["totals"]
            print(f"\n  loaded {t['cards']} card(s): +{t['races']} races, "
                  f"+{t['entries']} entries, {t['errors']} error(s)")
            if t["purged_entries"]:
                print(f"  purged {t['purged_entries']} stale entries first")
    finally:
        conn.close()

    # --- Phase 4: feature rebuild ----------------------------------------
    _rule("4. FEATURE REBUILD")
    did_rebuild = False
    if not execute:
        print("  would run speed_figures_dpv1.py compute")
        print("  would run feature_builder_dpv1.py build")
        print("  (mandatory after a purge: purging cascades to "
              "entry_features_dpv1)")
    elif loaded["totals"]["cards"] == 0 and not args.skip_load:
        print("  skipped -- nothing was loaded, so features are current")
    else:
        run([sys.executable, "scripts_dpv1/speed_figures_dpv1.py", "compute",
             "--db", args.db], "speed figures")
        run([sys.executable, "scripts_dpv1/feature_builder_dpv1.py", "build",
             "--db", args.db], "feature build")
        did_rebuild = True

    # --- Phase 5: label guard --------------------------------------------
    _rule("5. LABEL GUARD (NaN-as-False)")
    guard = verify_label_guard(args.db, tracks)
    print(f"  training frame: {guard['n_rows']} rows, {guard['n_races']} races")
    if guard["ok"]:
        print("  no unrun race survives into the labels -- guard PASSED")
    else:
        print(f"  {guard['unrun_races']} unrun races ({guard['unrun_rows']} rows) "
              f"reached the label set")
        print("\n  REFUSING TO RETRAIN. Every horse in an unrun race would be")
        print("  labelled as having missed the board. Load those charts or")
        print("  purge those cards, then run again.")
        return 2

    # --- Phase 6: train ---------------------------------------------------
    _rule("6. TRAIN CANDIDATE")
    if not execute:
        print(f"  would run train_dpv1.py final")
        print(f"       --model-out  {cand_path.name}")
        print(f"       --fold-preds {cand_folds.name}")
        print(f"       --version    {cand_version}")
        print(f"       --tracks     {','.join(tracks)}")
        print(f"  (never overwrites {Path(args.model).name})")
    else:
        run([sys.executable, "scripts_dpv1/train_dpv1.py", "final",
             "--db", args.db, "--model-out", str(cand_path),
             "--fold-preds", str(cand_folds), "--version", cand_version,
             "--tracks", ",".join(tracks)], "training")
        print(f"  wrote {cand_path.name}")

    # --- Phase 7: compare -------------------------------------------------
    cur_folds = DPV1_DIR / "dpv1_fold_predictions.csv"
    outcome = "dry_run"
    verdicts: list = []
    shared = 0
    if execute and cand_path.exists() and cur_folds.exists():
        a = pd.read_csv(cur_folds, usecols=["race_id"])["race_id"].unique()
        b = pd.read_csv(cand_folds, usecols=["race_id"])["race_id"].unique()
        shared_ids = set(a) & set(b)
        shared = len(shared_ids)
        cur_fold = fold_metrics(cur_folds, shared_ids)
        cand_fold = fold_metrics(cand_folds, shared_ids)
        verdicts = print_comparison(
            Path(args.model).name, current.version, cand_path.name, cand_version,
            cur_fold, cand_fold,
            live_metrics(current.version), live_metrics(cand_version))
        outcome = recommend(verdicts, shared)
        _rule("TO PROMOTE (run this yourself after reviewing the above)")
        print(f"  copy \"{cand_path}\" \"{Path(args.model)}\"")
        print("\n  This pipeline does not promote. Nothing above is a decision.")
    elif not execute:
        _rule("7. COMPARE")
        print("  would compare candidate vs current on shared cross-validated")
        print("  fold races, then print a recommendation and a promote command.")
        print("  Nothing is promoted automatically in either mode.")

    # --- Phase 8: housekeeping -------------------------------------------
    _rule("8. HOUSEKEEPING")
    pruned = prune_models(args.keep, execute=execute)
    if not pruned:
        print(f"  nothing to prune (keeping newest {args.keep})")

    finished = datetime.now(timezone.utc)
    event = {
        "started_at": started.isoformat(), "finished_at": finished.isoformat(),
        "duration_sec": round((finished - started).total_seconds(), 1),
        "mode": "execute" if execute else "dry_run",
        "current_model": Path(args.model).name,
        "current_version": current.version,
        "candidate_model": cand_path.name if execute else None,
        "candidate_version": cand_version if execute else None,
        "charts_pending": len(pending),
        "charts_loaded": loaded["totals"]["cards"],
        "races_added": loaded["totals"]["races"],
        "entries_added": loaded["totals"]["entries"],
        "entries_purged": loaded["totals"]["purged_entries"],
        "load_errors": loaded["totals"]["errors"],
        "features_rebuilt": did_rebuild,
        "training_rows": guard["n_rows"], "training_races": guard["n_races"],
        "label_guard_ok": guard["ok"],
        "shared_fold_races": shared,
        "outcome": outcome,
        "promoted": False,
        "pruned_models": pruned,
    }
    if execute:
        append_history(event)
        print(f"\n  logged to {HISTORY_FILE}")
    print(f"\n  elapsed {event['duration_sec']:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
