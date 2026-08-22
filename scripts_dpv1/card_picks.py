"""Phase 6B: top-4 ITM rankings for a whole card, in a form usable at a track.

    python scripts_dpv1/card_picks.py --track ELP --date 2026-08-23 \
        --pp-file Ellis/elp-pps-files/elp0823y.pdf --save

This is the Phase 6B deliverable and it is deliberately the plainest thing in
the toolkit: a ranked list per race, the model's P(ITM), and the morning line
next to it. No tickets, no EV, no bet sizing. Phase 6A backtested the EV path
over 14,517 races and found that tickets it labelled +EV returned -34% against
-28.6% for betting indiscriminately, so pricing tickets is not something this
toolkit should be doing. Ranking horses is.

How to read it
--------------
``P(ITM)`` is the model's probability the horse finishes in the top three,
formed from the horses alone — DPv1's fundamental side, with no odds input.
That independence is the whole point: it is a second opinion formed without
looking at the board, so where it disagrees with the morning line, the
disagreement is real information about the model rather than an echo of the
price.

``ML`` is the Brisnet morning line, carried purely for comparison. It is not
an input to any prediction here. The v1 model gave morning-line odds its single
largest coefficient and that anchoring is the specific flaw the v2/DPv1 rebuild
exists to correct, so it is shown beside the model's opinion and never inside
it.

``cov`` is the fraction of DPv1's 95 features that were available for that
horse. It is the most important column on the page and the easiest to skip.
A horse at 45% is one the corpus has never seen — a shipper or a first-time
starter — and its probability is closer to a field-average prior than to a
real assessment. Phase 6A measured what low coverage does: at 27% coverage the
ranking retains rho=0.61 against a full-feature score and the top pick changes
in 56% of races. Weight the rankings by ``cov`` when you read them.

What the model does not know
----------------------------
As of Phase 6C, DPv1 is trained on GP, CT, MNR **and ELP**, so an Ellis Park
row now scores with a real ``track_code`` coefficient rather than an all-zero
block. Measured on held-out folds, that moved the ELP fundamental model from
AUC 0.627 to 0.659 against 0.696 on the home tracks — better, still worse.
Scoring any *other* track remains extrapolation and the runner says so.

The binding limitation is no longer the track list, it is the corpus. ELP is a
~30-day boutique meet and most of its runners ship in from Churchill, Indiana
Grand and Kentucky Downs, none of which are loaded. 38% of ELP starters in
*non-maiden* races have no prior start in ``racing_full.db`` — against 5-7% at
GP/CT/MNR — so their history-derived features are blank and their ``cov`` is
low. That is what the ``cov`` column is measuring here, and it is why it is the
most important column on the page.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DPV1_DIR))

from dpv1_runtime import (  # noqa: E402
    DEFAULT_DB, DEFAULT_MODEL, coverage_report, load_model,
    load_race_from_db, predict_card, resolve_race_id,
)
from pp_feature_bridge import apply_to_card, pp_index  # noqa: E402
from simulate_race import simulate_prediction  # noqa: E402

log = logging.getLogger("card_picks")

TOP_N = 4


def race_numbers(db, track: str, date: str) -> list[int]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return [int(r[0]) for r in conn.execute(
            """
            SELECT r.race_num FROM races r
            JOIN race_days rd ON rd.id = r.race_day_id
            JOIN tracks t     ON t.id = rd.track_id
            WHERE t.code = ? AND rd.race_date = ?
            ORDER BY r.race_num
            """, (track.upper(), date))]
    finally:
        conn.close()


def ml_lookup(pdf, track: str | None) -> dict:
    """``(race_num, normalized name) -> morning line`` for display only."""
    from equibase_pdf_parser import normalize_name
    bundle = pp_index(pdf, track)
    out = {}
    for (rn, nm), h in bundle["index"].items():
        out[(rn, nm)] = (h.get("ml"), h.get("pp_ml_decimal"),
                         h.get("pp_prime_power"))
    return out


def one_race(track: str, date: str, race_num: int, model, db, pp_file,
             ml_map: dict, iters: int, seed: int) -> dict | None:
    from equibase_pdf_parser import normalize_name

    try:
        card = load_race_from_db(model, db, track=track, race_date=date,
                                 race_num=race_num)
    except LookupError as exc:
        log.warning("R%s: %s", race_num, exc)
        return None
    if card.n < 2:
        return None

    if pp_file:
        try:
            apply_to_card(card, pp_file, model)
        except SystemExit as exc:
            log.warning("R%s: PP bridge failed (%s)", race_num, exc)

    pred = predict_card(card, model, use="fundamental")
    sim = simulate_prediction(pred, n_iter=iters, seed=seed)
    cov = coverage_report(card, model)

    names = card.names()
    d = pd.DataFrame({
        "pgm": card.programs(),
        "horse": names,
        "P(ITM)": sim.p_itm(),
        "P(win)": sim.position_matrix()[:, 0],
        "cov": cov["per_horse"],
    })
    mls, pps = [], []
    for nm in names:
        v = ml_map.get((race_num, normalize_name(nm)), (None, None, None))
        mls.append(v[0] if v[0] and v[0] != "?" else "")
        pps.append(v[2])
    d["ML"] = mls
    d["PrimePwr"] = pps
    if "finish_pos" in card.frame.columns and card.frame["finish_pos"].notna().any():
        d["actual"] = card.frame["finish_pos"].to_numpy()

    d = d.sort_values("P(ITM)", ascending=False).reset_index(drop=True)
    d.insert(0, "rank", np.arange(1, len(d) + 1))

    return {"race_num": race_num, "n": card.n,
            "conditions": card.conditions, "coverage": cov["overall"],
            "table": d}


def print_race(r: dict) -> None:
    c = r["conditions"]
    bits = []
    for k in ("race_type", "distance_yards", "surface", "purse"):
        if c.get(k) is not None:
            bits.append(f"{c[k]}" if k != "purse" else f"${c[k]:,}")
    print(f"\n--- Race {r['race_num']}  ({r['n']} horses)  "
          f"{'  '.join(str(b) for b in bits)}")
    print(f"    feature coverage {r['coverage'] * 100:.0f}%")

    d = r["table"].copy()
    d["P(ITM)"] = (d["P(ITM)"] * 100).round(1)
    d["P(win)"] = (d["P(win)"] * 100).round(1)
    d["cov"] = (d["cov"] * 100).round(0).astype(int)
    if "PrimePwr" in d.columns:
        d["PrimePwr"] = d["PrimePwr"].astype(object).where(
            d["PrimePwr"].notna(), "")
    top = d.head(TOP_N)
    rest = d.tail(max(0, len(d) - TOP_N))
    print(top.to_string(index=False))
    if len(rest):
        print("    ...")
        print(rest.to_string(index=False, header=False))


def _cli() -> int:
    p = argparse.ArgumentParser(
        description="Top-4 ITM rankings for a card (Phase 6B deliverable).")
    p.add_argument("--track", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--race", type=int, help="one race only")
    p.add_argument("--pp-file", help="Brisnet PP PDF for this card")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--model", default=str(DEFAULT_MODEL))
    p.add_argument("--iters", type=int, default=10000)
    p.add_argument("--seed", type=int, default=6001)
    p.add_argument("--save", action="store_true",
                   help="write a timestamped copy of this output")
    p.add_argument("--outdir", default=str(DPV1_DIR / "picks"))
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    model = load_model(args.model)
    ml_map = ml_lookup(args.pp_file, args.track) if args.pp_file else {}
    nums = [args.race] if args.race else race_numbers(args.db, args.track,
                                                      args.date)
    if not nums:
        raise SystemExit(f"no races for {args.track.upper()} {args.date}")

    import io
    buf = io.StringIO()

    class Tee:
        def write(self, s):
            sys.__stdout__.write(s)
            buf.write(s)

        def flush(self):
            sys.__stdout__.flush()

    sys.stdout = Tee()
    try:
        print("=" * 72)
        print(f" DPv1 {model.version} — {args.track.upper()} {args.date}")
        print(f" generated {datetime.now():%Y-%m-%d %H:%M}")
        print("=" * 72)
        print(" P(ITM) is the model's own opinion, formed without odds.")
        print(" ML is the morning line, shown for comparison only — it is not "
              "a model input.")
        print(" cov is how much of the 95-feature set was available; low cov "
              "means a")
        print(" near-prior guess, not a real assessment.")
        trained = tuple(model.hyperparameters.get("tracks", ("GP", "CT", "MNR")))
        if args.track.upper() not in trained:
            print(f" NOTE: this model was trained on {'/'.join(trained)}. "
                  f"{args.track.upper()} is outside that set, so the model")
            print("       carries no track coefficient or track-bias figures "
                  "for it.")

        results = []
        for rn in nums:
            r = one_race(args.track, args.date, rn, model, args.db,
                         args.pp_file, ml_map, args.iters, args.seed)
            if r:
                print_race(r)
                results.append(r)

        if len(results) > 1:
            print("\n" + "=" * 72)
            print(" CARD SUMMARY — top pick per race")
            print("=" * 72)
            rows = []
            for r in results:
                t = r["table"].iloc[0]
                rows.append({
                    "R": r["race_num"],
                    "top pick": f"#{t['pgm']} {t['horse'][:20]}",
                    "P(ITM)%": round(t["P(ITM)"] * 100, 1),
                    "ML": t.get("ML", ""),
                    "cov%": round(r["coverage"] * 100),
                })
            print(pd.DataFrame(rows).to_string(index=False))
            lo = [r["race_num"] for r in results if r["coverage"] < 0.6]
            if lo:
                print(f"\n Races with under 60% feature coverage: {lo}. "
                      f"Treat those rankings as weak.")
    finally:
        sys.stdout = sys.__stdout__

    if args.save:
        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        base = outdir / f"{args.track.upper()}_{args.date}_{stamp}"
        base.with_suffix(".txt").write_text(buf.getvalue(), encoding="utf-8")
        frames = []
        for r in results:
            t = r["table"].copy()
            t.insert(0, "race_num", r["race_num"])
            frames.append(t)
        if frames:
            pd.concat(frames).to_csv(base.with_suffix(".csv"), index=False)
        print(f"\nsaved {base.with_suffix('.txt')}")
        print(f"saved {base.with_suffix('.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
