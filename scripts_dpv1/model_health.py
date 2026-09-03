"""Phase 6E piece 3: rolling health dashboard for DPv1's live picks.

    python scripts_dpv1/model_health.py                     # rolling summary
    python scripts_dpv1/model_health.py --track CT
    python scripts_dpv1/model_health.py --model dpv1.pkl
    python scripts_dpv1/model_health.py --last-n 100
    python scripts_dpv1/model_health.py --since 2026-08-01
    python scripts_dpv1/model_health.py --out-of-corpus     # true performance

Reads ``logs/scored_predictions.jsonl`` (Piece 2) and aggregates it. Diagnostic
only: it prints, it does not notify, and it never writes to the log or the
database.

The unit of measurement is a race, not a prediction
---------------------------------------------------
Every rate here has a race in the denominator. Three things follow from that,
and all three are easy to get wrong:

* **Only the latest run of a race counts.** A card can be predicted more than
  once -- a re-run after a scratch, a second model -- and every run is kept in
  the scored log because the audit trail is the point. Counting them all would
  weight a race by how many times it happened to be re-predicted. Piece 2
  exports ``latest_run_only`` for exactly this and it is applied before
  anything else here.

* **A race whose top pick scratched has no top pick.** It leaves the ITM and
  WIN denominators entirely. Scoring it as a miss would bias the headline
  number down by however often the top pick scratches -- which is often: 12 of
  113 on CT 2026-08-28 alone.

* **A race with no recorded winner cannot be a win.** Disqualifications land in
  this corpus as a horse renamed ``DQ-<name>`` with a NULL ``finish_pos``, so
  the race has no ``finish_pos = 1`` at all (168 of 29,020 loaded races, 0.58%).
  Those races leave the WIN denominator but stay in the ITM denominator, where
  the board is still well defined.

In-corpus versus out-of-corpus
------------------------------
A race the model trained on tells you the code works. Only a race it has never
seen tells you the model works. The two must never share a headline, so this
splits them and labels the split loudly.

Membership is decided from data, not from a date: a card is in-corpus if its
result chart was loaded into the database *before* the reference model was
trained (``parsed_files.parsed_at`` against the pickle's ``trained_at``). The
obvious shortcut -- comparing ``race_date`` to a cutoff -- gets this wrong in
the case that matters most. ELP 2026-08-22 ran on the cutoff date but its chart
was not loaded until 2026-08-29, a week after ``dpv1.pkl`` was trained, so it is
genuinely out-of-sample despite its date. ``--training-cutoff`` forces the date
rule when that is what you want.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DPV1_DIR = Path(__file__).resolve().parent
LOG_DIR = DPV1_DIR / "logs"
sys.path.insert(0, str(DPV1_DIR))

from dpv1_runtime import DEFAULT_DB, DEFAULT_MODEL  # noqa: E402
from score_predictions import latest_run_only  # noqa: E402

SCORED_FILE = LOG_DIR / "scored_predictions.jsonl"

log = logging.getLogger("model_health")

# Spec thresholds. Below MIN_N a bucket is reported as thin rather than
# alerted on: these bands were written for ~100-race windows, and firing them
# on a handful of races manufactures alarms out of noise.
ITM_TARGET = (0.55, 0.57)
WIN_BASELINE = 0.15
ALERT_ITM_LOW, ALERT_ITM_HIGH = 0.45, 0.68
ALERT_HIGHCOV_ITM_LOW = 0.40
ALERT_ROI_LOW = -0.25
ALERT_TRACK_DIVERGENCE = 0.15
MIN_N = 20


# ---------------------------------------------------------------------------
# Load and shape
# ---------------------------------------------------------------------------

def load_scored(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(
            f"no scored log at {path} -- run score_predictions.py first")
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            log.warning("%s line %d is not valid JSON, skipped (%s)",
                        path.name, i, exc)
    return rows


def race_metadata(db: str, cards: set[tuple[str, str]]) -> dict:
    """Per-race ``race_type`` / winner presence, and per-card chart load time."""
    meta: dict[tuple[str, str, int], dict] = {}
    loaded_at: dict[tuple[str, str], str | None] = {}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for track, date in sorted(cards):
            for race_num, race_type, has_winner in conn.execute(
                """
                SELECT r.race_num, r.race_type,
                       EXISTS (SELECT 1 FROM entries e
                               WHERE e.race_id = r.id AND e.finish_pos = 1)
                FROM races r
                JOIN race_days rd ON rd.id = r.race_day_id
                JOIN tracks t     ON t.id  = rd.track_id
                WHERE t.code = ? AND rd.race_date = ?
                """, (track, date)):
                meta[(track, date, int(race_num))] = {
                    "race_type": race_type,
                    "has_winner": bool(has_winner),
                }
            row = conn.execute(
                """
                SELECT pf.parsed_at
                FROM race_days rd
                JOIN tracks t ON t.id = rd.track_id
                LEFT JOIN parsed_files pf ON pf.source_pdf = rd.source_pdf
                WHERE t.code = ? AND rd.race_date = ?
                """, (track, date)).fetchone()
            loaded_at[(track, date)] = row[0] if row else None
    finally:
        conn.close()
    return {"races": meta, "loaded_at": loaded_at}


def model_trained_at(model_path: str) -> datetime | None:
    """``trained_at`` off the pickle, for the corpus split. None if unreadable."""
    try:
        from dpv1_runtime import load_model
        raw = load_model(model_path).trained_at
    except Exception as exc:  # noqa: BLE001 - a missing pickle is not fatal here
        log.warning("could not read trained_at from %s (%s); "
                    "corpus split needs --training-cutoff", model_path, exc)
        return None
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


RACE_TYPE_BUCKETS = (
    # Order matters: a maiden claimer is a maiden race first.
    ("Maiden", ("MAIDEN",)),
    ("Stakes", ("STAKES", "HANDICAP")),
    ("Allowance", ("ALLOWANCE",)),
    ("Claiming", ("CLAIMING",)),
)


def bucket_race_type(raw: str | None) -> str:
    if not raw:
        return "Unknown"
    up = "".join(ch for ch in raw.upper() if ch.isalnum())
    for label, needles in RACE_TYPE_BUCKETS:
        if any(n in up for n in needles):
            return label
    return "Other"


def bucket_coverage(cov: float | None) -> str:
    if cov is None:
        return "unknown"
    if cov >= 0.90:
        return "90-100% cov"
    if cov >= 0.80:
        return "80-89% cov"
    return "<80% cov"


def build_races(scored: list[dict], meta: dict, trained_at: datetime | None,
                cutoff: str | None) -> list[dict]:
    """Collapse scored rows into one record per race."""
    by_race: dict[tuple, list[dict]] = defaultdict(list)
    for r in scored:
        by_race[(r["track"], r["race_date"], r["race_num"])].append(r)

    races = []
    for key, rows in by_race.items():
        track, date, race_num = key
        info = meta["races"].get(key, {})
        top = next((r for r in rows if r.get("was_top_pick")), None)
        scratched = bool(rows[0].get("top_pick_scratched"))

        # Top-4 board coverage: of the four highest-ranked horses, how many hit
        # the board. Capped at 3 because a race only has three ITM slots.
        top4 = sorted((r for r in rows if r.get("rank") is not None),
                      key=lambda r: r["rank"])[:4]
        top4_hits = min(3, sum(1 for r in top4 if r.get("hit_itm")))

        if cutoff is not None:
            in_corpus = date < cutoff
        else:
            loaded = meta["loaded_at"].get((track, date))
            if loaded is None or trained_at is None:
                in_corpus = None
            else:
                dt = datetime.fromisoformat(loaded)
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
                in_corpus = dt < trained_at

        races.append({
            "track": track, "race_date": date, "race_num": race_num,
            "top_pick_scratched": scratched,
            "hit_itm": bool(top["hit_itm"]) if top and not scratched else None,
            "hit_win": bool(top["hit_win"]) if top and not scratched else None,
            "show_payoff": (top or {}).get("show_payoff") if not scratched else None,
            "final_odds": (top or {}).get("final_odds") if not scratched else None,
            "race_coverage": rows[0].get("race_coverage"),
            "race_type": bucket_race_type(info.get("race_type")),
            "has_winner": info.get("has_winner", True),
            "n_starters": rows[0].get("n_starters"),
            "top4_hits": top4_hits,
            "model_pkl": rows[0].get("model_pkl"),
            "model_version": rows[0].get("model_version"),
            "backfilled": bool(rows[0].get("backfilled")),
            "backfill_attribution": rows[0].get("backfill_attribution"),
            "in_corpus": in_corpus,
        })
    races.sort(key=lambda r: (r["race_date"], r["track"], r["race_num"]))
    return races


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def itm_rate(races: list[dict]) -> tuple[int, int]:
    live = [r for r in races if not r["top_pick_scratched"] and r["hit_itm"] is not None]
    return sum(1 for r in live if r["hit_itm"]), len(live)


def win_rate(races: list[dict]) -> tuple[int, int]:
    """Win rate excludes races with no recorded winner (disqualifications)."""
    live = [r for r in races
            if not r["top_pick_scratched"] and r["hit_win"] is not None
            and r["has_winner"]]
    return sum(1 for r in live if r["hit_win"]), len(live)


def show_roi(races: list[dict]) -> tuple[float, float]:
    live = [r for r in races if not r["top_pick_scratched"] and r["hit_itm"] is not None]
    stake = 2.0 * len(live)
    ret = sum(r["show_payoff"] or 0.0 for r in live)
    return ret, stake


def _pct(n: int, d: int) -> str:
    return f"{100.0 * n / d:5.1f}%" if d else "    --"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(races: list[dict], label: str, window: str) -> list[str]:
    print("=" * 72)
    print(f" DPv1 Model Health -- {label}")
    print(f" {window}")
    print("=" * 72)
    if not races:
        print("\n no races match this filter")
        return []

    itm_n, itm_d = itm_rate(races)
    win_n, win_d = win_rate(races)
    scratched = sum(1 for r in races if r["top_pick_scratched"])
    no_winner = sum(1 for r in races if not r["has_winner"])

    print("\n=== Overall ===")
    lo, hi = ITM_TARGET
    if itm_d:
        rate = itm_n / itm_d
        flag = ("on target" if lo <= rate <= hi
                else "above target" if rate > hi else "below target")
        print(f"Top pick ITM:        {itm_n} / {itm_d} = {_pct(itm_n, itm_d)}"
              f"   (target {lo:.0%}-{hi:.0%})   {flag}")
    if win_d:
        rate = win_n / win_d
        flag = "above baseline" if rate > WIN_BASELINE else "below baseline"
        print(f"Top pick WIN:        {win_n} / {win_d} = {_pct(win_n, win_d)}"
              f"   (baseline {WIN_BASELINE:.0%})   {flag}")
    cap = sum(r["top4_hits"] for r in races) / len(races)
    print(f"Top-4 avg ITM cap:   {cap:.2f} / 3.00")
    print(f"Races in window:     {len(races)}"
          f"   (top pick scratched: {scratched}, no recorded winner: {no_winner})")
    if scratched:
        print(f"                     {scratched} race(s) have no top pick and are "
              f"excluded from the rates above")
    if no_winner:
        print(f"                     {no_winner} race(s) have no recorded winner "
              f"(DQ) and are excluded from WIN only")

    def group_block(title: str, keyfn, order=None, note=None):
        print(f"\n=== {title} ===")
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in races:
            groups[keyfn(r)].append(r)
        keys = [k for k in (order or sorted(groups)) if k in groups]
        width = max((len(k) for k in keys), default=0)
        for k in keys:
            g = groups[k]
            i_n, i_d = itm_rate(g)
            w_n, w_d = win_rate(g)
            thin = "  (thin)" if i_d < MIN_N else ""
            print(f"{k:<{width}}  ITM {_pct(i_n, i_d)} (n={i_d:>3})"
                  f"   Win {_pct(w_n, w_d)} (n={w_d:>3}){thin}")
        if note:
            print(note)

    group_block("By Track", lambda r: r["track"])
    group_block("By Feature Coverage", lambda r: bucket_coverage(r["race_coverage"]),
                order=["90-100% cov", "80-89% cov", "<80% cov", "unknown"])
    group_block("By Race Type", lambda r: r["race_type"])
    # Grouped by version, not by pickle filename: the version is the model's
    # identity, and an attributed back-fill has a version but no filename.
    group_block("By Model",
                lambda r: (r["model_version"] or "unrecorded")
                + (" (attributed)" if r.get("backfill_attribution") else ""))

    ret, stake = show_roi(races)
    print("\n=== Show ROI on Top Pick ===")
    print(f"Total stake:      ${stake:,.2f}   ($2 to show, every live top pick)")
    print(f"Total return:     ${ret:,.2f}")
    print(f"Net:              ${ret - stake:+,.2f}")
    if stake:
        print(f"ROI:              {100 * (ret - stake) / stake:+.1f}%")

    return alerts(races)


def alerts(races: list[dict]) -> list[str]:
    out: list[str] = []

    last30 = races[-30:]
    n, d = itm_rate(last30)
    if d >= MIN_N:
        rate = n / d
        if rate < ALERT_ITM_LOW:
            out.append(f"top pick ITM over last {d} races is {rate:.1%}, "
                       f"below the {ALERT_ITM_LOW:.0%} floor")
        elif rate > ALERT_ITM_HIGH:
            out.append(f"top pick ITM over last {d} races is {rate:.1%}, "
                       f"above the {ALERT_ITM_HIGH:.0%} ceiling -- check for "
                       f"leakage or an in-corpus window")

    high = [r for r in races if bucket_coverage(r["race_coverage"]) == "90-100% cov"]
    n, d = itm_rate(high)
    if d >= MIN_N and n / d < ALERT_HIGHCOV_ITM_LOW:
        out.append(f"high-coverage ITM is {n / d:.1%} over {d} races, below "
                   f"{ALERT_HIGHCOV_ITM_LOW:.0%} -- the model is weak where it "
                   f"has the most to work with")

    last60 = races[-60:]
    ret, stake = show_roi(last60)
    if stake and len([r for r in last60 if not r["top_pick_scratched"]]) >= MIN_N:
        roi = (ret - stake) / stake
        if roi < ALERT_ROI_LOW:
            out.append(f"show ROI over last {len(last60)} races is {roi:+.1%}, "
                       f"below {ALERT_ROI_LOW:+.0%}")

    overall_n, overall_d = itm_rate(races)
    if overall_d >= MIN_N:
        overall = overall_n / overall_d
        by_track: dict[str, list[dict]] = defaultdict(list)
        for r in races:
            by_track[r["track"]].append(r)
        for track, g in sorted(by_track.items()):
            n, d = itm_rate(g)
            if d >= MIN_N and abs(n / d - overall) > ALERT_TRACK_DIVERGENCE:
                out.append(f"{track} ITM is {n / d:.1%} against {overall:.1%} "
                           f"overall, a {100 * (n / d - overall):+.0f}pp divergence")

    print("\n=== Alerts ===")
    if out:
        for a in out:
            print(f"[!] {a}")
    else:
        thin = itm_rate(races)[1] < MIN_N
        print(f"[none]  ({'window too thin to alert on' if thin else 'all metrics within expected bands'})")
    return out


def print_reranker_split(scored: list[dict]) -> None:
    """Live base-only vs with-reranker top-pick ITM, on reranked races only.

    Both arms are recomputed from the same scored rows: the reranked arm takes
    the horse with the highest ``final_p_itm``, the base arm the highest
    ``base_p_itm``. That is a genuine paired comparison on identical races and
    identical outcomes -- the only thing that differs is which horse the
    ranking selected.

    It reads 0/0 until reranked cards have been run *and* scored, which is the
    honest state until roughly 50-100 races accumulate.
    """
    rows = [r for r in scored if r.get("reranker_version")
            and r.get("base_p_itm") is not None
            and r.get("final_p_itm") is not None]
    print("\n=== Reranker: base-only vs with-reranker (live) ===")
    if not rows:
        print("No scored races carry reranker output yet.")
        print("Picks made before the reranker shipped have no base_p_itm, and")
        print("cards run since then are not scored until their charts load.")
        return

    by_race: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by_race[(r["track"], r["race_date"], r["race_num"])].append(r)

    arms = {"base only": "base_p_itm", "with reranker": "final_p_itm"}
    hits = {k: 0 for k in arms}
    n = changed = 0
    for g in by_race.values():
        if g[0].get("top_pick_scratched"):
            continue
        n += 1
        picks = {}
        for label, key in arms.items():
            top = max(g, key=lambda r: r[key])
            picks[label] = top
            hits[label] += bool(top["hit_itm"])
        changed += (picks["base only"]["prediction_id"]
                    != picks["with reranker"]["prediction_id"])

    if not n:
        print("No scorable reranked races yet.")
        return
    versions = sorted({r["reranker_version"] for r in rows})
    print(f"reranker {', '.join(versions)}   {n} scored race(s), "
          f"top pick differs in {changed}")
    for label in arms:
        print(f"  {label:<16} {hits[label]}/{n} = {_pct(hits[label], n)}")
    d = hits["with reranker"] - hits["base only"]
    print(f"  difference       {d:+d} race(s)")
    if n < 50:
        print(f"\n  {n} races is far below the ~50-100 needed to read this as")
        print("  evidence. The standalone cross-validated estimate was +3.9pp")
        print("  (p=0.064); this line exists to accumulate the live check.")


def print_corpus_split(races: list[dict]) -> None:
    ins = [r for r in races if r["in_corpus"] is True]
    outs = [r for r in races if r["in_corpus"] is False]
    unknown = [r for r in races if r["in_corpus"] is None]
    print("\n=== Corpus Split ===")
    for name, g in (("in-corpus (trained on)", ins),
                    ("OUT-OF-CORPUS (real)", outs),
                    ("unknown", unknown)):
        if not g:
            continue
        n, d = itm_rate(g)
        cards = sorted({(r["track"], r["race_date"]) for r in g})
        print(f"{name:<24} {len(g):>3} races   ITM {_pct(n, d)} (n={d})")
        print(f"{'':<24} {', '.join(f'{t} {d_}' for t, d_ in cards)}")
    if ins:
        print("\nIn-corpus races were in the training data. Their rates measure "
              "code correctness,\nnot model performance -- read the "
              "OUT-OF-CORPUS line as the real number.")


# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(
        description="DPv1 rolling health dashboard (Phase 6E piece 3).")
    p.add_argument("--track", help="filter to one track code")
    p.add_argument("--model", help="filter by model_pkl or model_version substring")
    p.add_argument("--last-n", type=int, help="most recent N races")
    p.add_argument("--since", help="races on or after this date (YYYY-MM-DD)")
    p.add_argument("--until", help="races on or before this date (YYYY-MM-DD)")
    p.add_argument("--in-corpus", action="store_true",
                   help="only races the reference model trained on")
    p.add_argument("--out-of-corpus", action="store_true",
                   help="only races the reference model has never seen")
    p.add_argument("--training-cutoff", metavar="DATE",
                   help="force the date rule for the corpus split: races before "
                        "DATE count as in-corpus. Default is data-driven "
                        "(chart load time vs the model's trained_at)")
    p.add_argument("--model-file", default=str(DEFAULT_MODEL),
                   help="reference model for the corpus split")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--scored-file", default=str(SCORED_FILE))
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    if args.in_corpus and args.out_of_corpus:
        raise SystemExit("--in-corpus and --out-of-corpus are mutually exclusive")

    scored = load_scored(Path(args.scored_file))
    if not scored:
        raise SystemExit("scored log is empty")

    # Rule one: collapse re-runs before anything is counted.
    scored = latest_run_only(scored)

    cards = {(r["track"], r["race_date"]) for r in scored}
    meta = race_metadata(args.db, cards)
    trained = None if args.training_cutoff else model_trained_at(args.model_file)
    races = build_races(scored, meta, trained, args.training_cutoff)

    bits = []
    if args.track:
        races = [r for r in races if r["track"] == args.track.upper()]
        bits.append(f"track={args.track.upper()}")
    if args.model:
        needle = args.model.lower()
        races = [r for r in races
                 if needle in str(r["model_pkl"]).lower()
                 or needle in str(r["model_version"]).lower()]
        bits.append(f"model~{args.model}")
    if args.since:
        races = [r for r in races if r["race_date"] >= args.since]
        bits.append(f"since {args.since}")
    if args.until:
        races = [r for r in races if r["race_date"] <= args.until]
        bits.append(f"until {args.until}")
    if args.in_corpus:
        races = [r for r in races if r["in_corpus"] is True]
        bits.append("in-corpus only")
    if args.out_of_corpus:
        races = [r for r in races if r["in_corpus"] is False]
        bits.append("OUT-OF-CORPUS only")
    if args.last_n:
        races = races[-args.last_n:]
        bits.append(f"last {args.last_n} races")

    # A window is mixed when it spans more than one model version, or when some
    # race carries no version at all. An *attributed* back-fill is neither:
    # its version was read off the picks-file header the runner wrote, so it is
    # a recorded fact about a known model, not a gap. Those races count as the
    # version they name and raise no banner when it matches the rest.
    versions = sorted({r["model_version"] for r in races if r["model_version"]})
    unattributed = [r for r in races if not r["model_version"]]
    attributed = [r for r in races if r.get("backfill_attribution")]
    label = ", ".join(versions) if versions else "unrecorded"
    if len(versions) > 1 or unattributed:
        label += " (MIXED -- rates below span more than one model)"
    if races:
        window = (f"{len(races)} races ({races[0]['race_date']} to "
                  f"{races[-1]['race_date']})")
    else:
        window = "no races"
    if bits:
        window += "   [" + "; ".join(bits) + "]"

    print_report(races, label, window)
    print_reranker_split(scored)
    if attributed:
        by_src: dict[str, set[str]] = defaultdict(set)
        for r in attributed:
            by_src[r["backfill_attribution"]].add(r["model_version"] or "?")
        print("\n=== Provenance ===")
        for src, vs in sorted(by_src.items()):
            n = sum(1 for r in attributed if r["backfill_attribution"] == src)
            print(f"{n} of {len(races)} races attributed to "
                  f"{', '.join(sorted(vs))} via {src}")
        print("Attributed races were logged before the runner recorded a model "
              "version;\ntheir version comes from the picks-file header, not "
              "from the log row.")
    if not (args.in_corpus or args.out_of_corpus):
        print_corpus_split(races)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
