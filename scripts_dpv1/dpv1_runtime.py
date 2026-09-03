"""Phase 6A runtime: turn the trained DPv1 artifact into a live race scorer.

Everything before this phase was *measurement* — train, cross-validate, score
folds. Nothing ever asked ``dpv1.pkl`` about a race that had not already
happened. This module is the missing half: loading the artifact, assembling a
feature row per horse, and converting the model's output into the shape the
simulator and the ticket calculator need.

Three things here are load-bearing and are worth reading before trusting a
number that comes out the other end.

1. The pickle is a ``__main__`` pickle
-------------------------------------
``train_dpv1.py`` was run as a script, so ``DPv1Model`` was pickled with the
qualified name ``__main__.DPv1Model``. Unpickling from anywhere else raises
``AttributeError: Can't get attribute 'DPv1Model' on <module '__main__'>``.
``load_model`` installs the class into ``__main__`` first. This is a property
of the artifact, not a choice — re-running ``train_dpv1.py final`` would
reproduce it.

2. Missing features are not free
--------------------------------
The preprocessor emits a ``{col}__missing`` indicator for every numeric column
that had a NULL anywhere in training, and the fundamental model has a fitted
coefficient on each one. So a hand-entered horse with 60 blank fields is not
"scored on the 35 fields you gave" — it is scored as *a horse with 60 blank
fields*, which in the training corpus overwhelmingly means a first-time starter
or a layoff. That is a real signal the model learned, and it will drag the
prediction toward the base rate for such horses.

``coverage_report`` exists so this is visible rather than silent. The honest
operating range is: full DB features (what the model was trained on), or a
hand-entered card where you accept that sparse rows read as "unraced".

3. P(ITM) is not P(win)
-----------------------
DPv1's target is ``finish_pos <= 3``. A Plackett-Luce simulator needs per-horse
*win* strengths. ``invert_harville`` recovers them: it finds the win-probability
vector whose Harville top-3 marginals reproduce the model's P(ITM).

This is exact, not a heuristic, and the choice of Harville is forced rather
than free: ``market_model_v2a`` used Harville to build the market P(ITM) the
model was *trained against*, and Harville's top-k marginals are precisely the
Plackett-Luce ones. So the win probabilities recovered here, the simulator that
samples from them, and the target the model was fit to are all the same object
viewed from three sides.

The one preliminary step is a normalisation. Exactly three horses finish in the
money, so the true P(ITM) over a field must sum to 3. DPv1's raw per-entry
estimates do not — they are fit as independent binary logistics with no
per-race constraint, and typically sum to somewhere between 2.5 and 3.5.
``normalise_itm`` rescales in log-odds space before inversion. Both the raw and
the normalised values are carried through so the adjustment is auditable.
"""
from __future__ import annotations

import logging
import pickle
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
REPO = DPV1_DIR.parent
for _p in (DPV1_DIR, REPO / "scripts", REPO / "scripts_v2a"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

log = logging.getLogger("dpv1_runtime")

DEFAULT_MODEL = DPV1_DIR / "dpv1.pkl"
DEFAULT_DB = REPO / "scripts" / "racing_full.db"


def to_utc(value) -> datetime | None:
    """Coerce any timestamp in this project to an aware UTC ``datetime``.

    Three clocks meet in this codebase and they do not agree:

    * ``parsed_files.parsed_at`` is a naive UTC string written by the loader.
    * ``DPv1Model.trained_at`` is ISO 8601 *with* a ``+00:00`` offset.
    * Picks-file stamps and filesystem mtimes are naive **local** time.

    Comparing across them unconverted is not hypothetical: on 2026-08-29 the
    model's ``trained_at`` of ``14:20:19Z`` was read against local picks stamps
    of ``09:24``, concluding those picks predated the model. Local is UTC-5, so
    training had finished at 09:20 local and the picks came *after* it. The
    wrong conclusion reached a project document before it was caught.

    A naive value is assumed to be UTC, which is right for the database columns
    and wrong for a local mtime — so convert local values at their source
    (``datetime.fromtimestamp(ts, tz=timezone.utc)``) rather than handing a
    naive local timestamp to this function.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            dt = pd.to_datetime(text, utc=True).to_pydatetime()
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)

EPS = 1e-12


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def load_model(path: str | Path = DEFAULT_MODEL):
    """Unpickle ``dpv1.pkl``, installing the ``__main__`` shim it needs.

    See point 1 of the module docstring. ``train_dpv1`` imports the v2a model
    classes at module scope, so importing it also makes
    ``FundamentalModelITM`` / ``BenterBlendITM`` / ``Preprocessor`` resolvable
    for the nested objects inside the artifact.
    """
    import __main__

    import train_dpv1  # noqa: F401  (side effect: registers dependencies)

    if not hasattr(__main__, "DPv1Model"):
        __main__.DPv1Model = train_dpv1.DPv1Model

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"model artifact not found: {path}\n"
            f"Rebuild it with:  python scripts_dpv1/train_dpv1.py final"
        )
    with open(path, "rb") as f:
        model = pickle.load(f)
    log.debug("loaded %s (%s, trained %s, %d fundamental features)",
              path.name, model.version, model.trained_at, len(model.fund_cols))
    return model


# ---------------------------------------------------------------------------
# Race container
# ---------------------------------------------------------------------------

@dataclass
class RaceCard:
    """One race, ready to score.

    ``frame`` is entry-grain and carries at minimum every column in
    ``model.fund_cols`` (NaN where unknown). ``odds`` is decimal-to-1 tote win
    odds — the same scale as ``entries.final_odds`` — or None when the race is
    being scored without a market, which is the normal case before post time.
    """

    frame: pd.DataFrame
    track: str = "?"
    race_date: str = "?"
    race_num: int | None = None
    source: str = "?"
    conditions: dict = field(default_factory=dict)
    # Set by pp_feature_bridge.apply_to_card when a PP file was supplied.
    pp_report: dict | None = None

    @property
    def n(self) -> int:
        return len(self.frame)

    @property
    def odds(self) -> np.ndarray | None:
        if "final_odds" not in self.frame.columns:
            return None
        o = pd.to_numeric(self.frame["final_odds"], errors="coerce").to_numpy(float)
        return o if np.isfinite(o).all() and (o > 0).all() else None

    def label(self) -> str:
        rn = f"R{self.race_num}" if self.race_num is not None else "R?"
        return f"{self.track} {self.race_date} {rn}"

    def names(self) -> list[str]:
        if "horse_name" in self.frame.columns:
            return [str(x) for x in self.frame["horse_name"]]
        return [f"#{p}" for p in self.programs()]

    def programs(self) -> list[str]:
        if "program_num" in self.frame.columns:
            return [str(x) for x in self.frame["program_num"]]
        return [str(i + 1) for i in range(self.n)]


# ---------------------------------------------------------------------------
# Loading a race out of the database
# ---------------------------------------------------------------------------

# The race-condition columns are aliased with a ``_c_`` prefix rather than
# selected bare: ``feature_builder_dpv1`` already writes distance_yards,
# surface, track_condition and race_type into ``entry_features_dpv1``, so
# ``f.*`` plus ``r.distance_yards`` would produce two columns of the same name
# and every later ``df[col]`` would return a DataFrame instead of a Series.
_RACE_SQL = """
    SELECT f.*,
           e.finish_pos, e.program_num, e.final_odds AS _odds,
           h.name AS horse_name,
           t.code AS _track, rd.race_date AS _race_date, r.race_num AS _race_num,
           r.distance_yards   AS _c_distance_yards,
           r.surface          AS _c_surface,
           r.track_condition  AS _c_track_condition,
           r.race_type        AS _c_race_type,
           r.purse            AS _c_purse
    FROM entry_features_dpv1 f
    JOIN entries e     ON e.id = f.entry_id
    JOIN races r       ON r.id = e.race_id
    JOIN race_days rd  ON rd.id = r.race_day_id
    JOIN tracks t      ON t.id = rd.track_id
    LEFT JOIN horses h ON h.id = e.horse_id
    WHERE r.id = ?
    ORDER BY CAST(e.program_num AS INTEGER), e.program_num
"""


def resolve_race_id(db: str | Path, track: str, race_date: str,
                    race_num: int) -> int:
    """Look up ``races.id`` from the way a human names a race."""
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            """
            SELECT r.id FROM races r
            JOIN race_days rd ON rd.id = r.race_day_id
            JOIN tracks t     ON t.id = rd.track_id
            WHERE t.code = ? AND rd.race_date = ? AND r.race_num = ?
            """,
            (track.upper(), race_date, int(race_num)),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise LookupError(
            f"no race found for {track.upper()} {race_date} R{race_num}")
    return int(row[0])


def load_race_from_db(model, db: str | Path = DEFAULT_DB, *,
                      race_id: int | None = None, track: str | None = None,
                      race_date: str | None = None,
                      race_num: int | None = None) -> RaceCard:
    """Pull a race's already-built DPv1 features straight out of the corpus.

    This is the highest-fidelity path and the only one that reproduces exactly
    what the model saw in training. Its limitation is equally exact: a race has
    features in ``entry_features_dpv1`` only after its result chart has been
    loaded, so this path scores *past* races. It is what Phase 6A validates
    against, and what a future PP-parser path would have to match.
    """
    if race_id is None:
        if not (track and race_date and race_num):
            raise ValueError("need race_id, or track + race_date + race_num")
        race_id = resolve_race_id(db, track, race_date, race_num)

    conn = sqlite3.connect(str(db))
    try:
        df = pd.read_sql_query(_RACE_SQL, conn, params=(int(race_id),))
    finally:
        conn.close()
    if df.empty:
        raise LookupError(
            f"race_id={race_id} has no rows in entry_features_dpv1 "
            "(chart not loaded, or features not built for it)")

    df["final_odds"] = pd.to_numeric(df.pop("_odds"), errors="coerce")
    race_date_val = str(df.pop("_race_date").iloc[0])
    track_val = str(df.pop("_track").iloc[0])
    race_num_val = int(df.pop("_race_num").iloc[0])
    conditions = {c[3:]: _scalar(df.pop(c))
                  for c in [c for c in df.columns if c.startswith("_c_")]}
    df = _ensure_columns(df, model)

    return RaceCard(
        frame=df.reset_index(drop=True),
        track=track_val,
        race_date=race_date_val,
        race_num=race_num_val,
        source=f"racing_full.db race_id={race_id}",
        conditions=conditions,
    )


def _scalar(series: pd.Series):
    if series.isna().all():
        return None
    v = series.iloc[0]
    return v.item() if hasattr(v, "item") else v


# ---------------------------------------------------------------------------
# Loading a hand-entered / file-supplied race
# ---------------------------------------------------------------------------

def _ensure_columns(df: pd.DataFrame, model) -> pd.DataFrame:
    """Add every model feature the frame lacks, as NaN.

    ``Preprocessor.transform`` indexes ``df[col]`` directly and raises KeyError
    on an absent column, so this has to happen before scoring. NaN is the right
    filler: it triggers the same median-impute-plus-missing-flag path the model
    was trained with. See point 2 of the module docstring for why that is not
    the same as "ignored".
    """
    out = df.copy()
    missing = [c for c in model.fund_cols if c not in out.columns]
    for c in missing:
        out[c] = np.nan
    return out


def load_race_from_file(model, path: str | Path) -> RaceCard:
    """Read a hand-built race from CSV or JSON.

    CSV: one row per horse, one column per feature. JSON: either a bare list of
    per-horse objects, or ``{"track":..., "race_date":..., "race_num":...,
    "conditions": {...}, "horses": [ ... ]}``. Any column named in
    ``model.fund_cols`` is used as a feature; ``horse_name``, ``program_num``
    and ``final_odds`` are recognised for display and for the market blend.
    Unrecognised columns are carried but ignored by the model.
    """
    import json

    path = Path(path)
    meta: dict = {}
    if path.suffix.lower() == ".json":
        blob = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(blob, list):
            rows = blob
        else:
            rows = blob.get("horses") or blob.get("entries") or []
            meta = {k: v for k, v in blob.items()
                    if k not in ("horses", "entries")}
        if not rows:
            raise ValueError(f"{path.name}: no horses found")
        df = pd.DataFrame(rows)
    else:
        df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"{path.name}: no rows")

    conditions = dict(meta.get("conditions") or {})
    # Race-level conditions are also features (surface, distance, ...), so
    # broadcast anything the model knows about down onto every horse row.
    for k, v in conditions.items():
        if k in model.fund_cols and k not in df.columns:
            df[k] = v
    if "final_odds" in df.columns:
        df["final_odds"] = pd.to_numeric(df["final_odds"], errors="coerce")

    df = _ensure_columns(df, model)
    return RaceCard(
        frame=df.reset_index(drop=True),
        track=str(meta.get("track", "?")),
        race_date=str(meta.get("race_date", "?")),
        race_num=meta.get("race_num"),
        source=str(path),
        conditions=conditions,
    )


def load_race_from_records(model, horses: list[dict], *, track: str = "?",
                           race_date: str = "?", race_num: int | None = None,
                           conditions: dict | None = None,
                           source: str = "interactive") -> RaceCard:
    """Build a card from in-memory dicts. Backs the interactive entry mode."""
    df = pd.DataFrame(horses)
    conditions = dict(conditions or {})
    for k, v in conditions.items():
        if k in model.fund_cols and k not in df.columns:
            df[k] = v
    if "final_odds" in df.columns:
        df["final_odds"] = pd.to_numeric(df["final_odds"], errors="coerce")
    df = _ensure_columns(df, model)
    return RaceCard(frame=df.reset_index(drop=True), track=track,
                    race_date=race_date, race_num=race_num, source=source,
                    conditions=conditions)


# ---------------------------------------------------------------------------
# Feature coverage
# ---------------------------------------------------------------------------

def coverage_report(card: RaceCard, model) -> dict:
    """How much of the model's feature set this card actually supplies.

    ``supplied`` counts non-NaN cells across the whole field. ``per_horse``
    gives the same per row, because one first-time starter in an otherwise
    complete field is normal, whereas an entire field at 30% coverage means the
    numbers below are describing a field of imaginary unraced horses.
    """
    cols = list(model.fund_cols)
    sub = card.frame.reindex(columns=cols)
    filled = sub.notna()
    per_col = filled.mean(axis=0)
    return {
        "n_features": len(cols),
        "n_horses": card.n,
        "overall": float(filled.to_numpy().mean()) if len(cols) else 1.0,
        "per_horse": [float(x) for x in filled.mean(axis=1)],
        "fully_missing": sorted(per_col.index[per_col == 0.0].tolist()),
        "fully_present": int((per_col == 1.0).sum()),
    }


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    return np.log(p) - np.log(1 - p)


def _expit(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(z, dtype=float)))


def market_itm_from_odds(odds: np.ndarray) -> np.ndarray:
    """Tote win odds -> Harville P(ITM), matching ``train_dpv1.market_p_itm``.

    The normalisation by the sum removes the track's takeout ("breakage") from
    the implied probabilities, so the result is the public's opinion rather
    than the public's opinion plus a house edge.
    """
    o = np.asarray(odds, dtype=float)
    raw = np.where((o > 0) & np.isfinite(o), 1.0 / (o + 1.0), np.nan)
    if not np.isfinite(raw).all():
        return np.full(len(o), np.nan)
    return harville_itm(raw / raw.sum())


@dataclass
class Prediction:
    """Model output for one race, in every form downstream code needs."""

    card: RaceCard
    p_fund: np.ndarray            # fundamental-only P(ITM), per entry
    p_market: np.ndarray | None   # Harville P(ITM) from tote odds
    p_blend: np.ndarray | None    # alpha*logit(p_f) + beta*logit(p_m) + gamma
    p_used: np.ndarray            # whichever of the above drives the sim
    used_name: str
    p_itm_normalised: np.ndarray  # p_used rescaled to sum to 3
    p_win: np.ndarray             # Harville inversion of p_itm_normalised
    inversion: dict               # convergence diagnostics

    @property
    def strength_logits(self) -> np.ndarray:
        """log P(win), i.e. the Plackett-Luce strengths up to a constant."""
        return np.log(np.clip(self.p_win, EPS, 1.0))

    def to_frame(self) -> pd.DataFrame:
        d = pd.DataFrame({
            "program": self.card.programs(),
            "horse": self.card.names(),
            "p_itm_fund": self.p_fund,
        })
        if self.p_market is not None:
            d["p_itm_market"] = self.p_market
        if self.p_blend is not None:
            d["p_itm_blend"] = self.p_blend
        d["p_itm"] = self.p_used
        d["p_itm_norm"] = self.p_itm_normalised
        d["p_win"] = self.p_win
        d["log_p_win"] = self.strength_logits
        if "final_odds" in self.card.frame.columns:
            d["odds"] = self.card.frame["final_odds"].to_numpy()
        if "finish_pos" in self.card.frame.columns:
            d["actual"] = self.card.frame["finish_pos"].to_numpy()
        return d


def predict_card(card: RaceCard, model, *, use: str = "auto") -> Prediction:
    """Score a card.

    ``use`` selects which probability drives the simulation:

    ``fundamental``
        The horse-and-race model alone. This is the only estimate that is
        independent of the tote, so it is the only one that can disagree with
        the market — and therefore the only one that can find a price wrong.

    ``blend``
        The shipped two-stage blend. Be aware of what its fitted weights say:
        alpha=0.106 on the fundamental logit against beta=0.772 on the market
        logit. The blend is, by a wide margin, a slightly-adjusted tote board.
        It is the more *accurate* estimate and the near-useless one for finding
        value, because exotic payouts are themselves priced off the tote.

    ``auto`` (default)
        blend when odds are present, fundamental when they are not.
    """
    X = model.preprocessor.transform(card.frame)
    p_f = np.asarray(model.fundamental.predict_probabilities(X), dtype=float)

    odds = card.odds
    p_m = market_itm_from_odds(odds) if odds is not None else None
    if p_m is not None and not np.isfinite(p_m).all():
        p_m = None

    p_b = None
    if p_m is not None:
        p_b = _expit(model.blend.alpha_ * _logit(p_f)
                     + model.blend.beta_ * _logit(p_m)
                     + model.blend.gamma_)

    if use == "auto":
        use = "blend" if p_b is not None else "fundamental"
    if use == "blend" and p_b is None:
        raise ValueError("blend requested but this card has no usable odds")
    if use not in ("blend", "fundamental", "market"):
        raise ValueError(f"unknown probability source: {use!r}")
    if use == "market" and p_m is None:
        raise ValueError("market requested but this card has no usable odds")

    p_used = {"blend": p_b, "fundamental": p_f, "market": p_m}[use]
    p_norm = normalise_itm(p_used)
    p_win, info = invert_harville(p_norm)

    return Prediction(card=card, p_fund=p_f, p_market=p_m, p_blend=p_b,
                      p_used=np.asarray(p_used, dtype=float), used_name=use,
                      p_itm_normalised=p_norm, p_win=p_win, inversion=info)


# ---------------------------------------------------------------------------
# Harville: win probabilities <-> P(ITM)
# ---------------------------------------------------------------------------

def harville_itm(w: np.ndarray) -> np.ndarray:
    """P(top 3) for each horse, given win probabilities ``w`` summing to 1.

    Single-race form of ``market_model_v2a.MarketModelITM.predict_p_itm``; the
    two agree to floating-point tolerance (asserted in the self-test at the
    bottom of this file). Kept separate because the simulator needs to call it
    hundreds of times inside the inversion loop with a bare vector, not a
    frame plus race_ids.
    """
    w = np.asarray(w, dtype=float)
    n = len(w)
    if n <= 3:
        return np.ones(n)
    p = np.clip(w, 1e-12, 1 - 1e-12)

    # 1st
    itm = p.copy()

    # 2nd: P(i 2nd) = p_i * sum_{j!=i} p_j/(1-p_j)
    base = p / (1.0 - p)
    itm = itm + p * (base.sum() - base)

    # 3rd: P(i 3rd) = sum_{j!=i} p_j * sum_{k!=i,j} p_k/(1-p_j) * p_i/(1-p_j-p_k)
    third = np.zeros(n)
    for j in range(n):
        rem_j = 1.0 - p[j]
        denom = rem_j - p                      # 1 - p_j - p_k, over k
        ratio = np.where(denom > 1e-12, p / denom, 0.0)
        ratio[j] = 0.0
        # For horse i: sum over k != i, j  of  (p_k/rem_j) * (p_i/(1-p_j-p_k))
        # The k-sum excludes k == i, so subtract i's own term.
        s = ratio.sum() - ratio
        contrib = p[j] * (p / rem_j) * s
        contrib[j] = 0.0
        third += contrib
    return itm + third


def normalise_itm(p_itm: np.ndarray, target_sum: float | None = None,
                  tol: float = 1e-10, max_iter: int = 200) -> np.ndarray:
    """Rescale per-entry P(ITM) so the field sums to 3.

    Exactly three horses hit the board, so ``sum_i P(ITM_i) = 3`` is an
    identity, not a modelling preference. DPv1 fits each entry independently
    and so does not respect it. The correction is a single shift in log-odds
    space — ``p_i -> sigmoid(logit(p_i) + delta)`` — solved for ``delta`` by
    bisection. A shift preserves the model's *ordering* and its relative
    log-odds spacing, changing only the overall level, which is the part the
    constraint actually pins down.

    Fields of three or fewer are all-ITM by definition and are returned as ones.
    """
    p = np.asarray(p_itm, dtype=float)
    n = len(p)
    if n <= 3:
        return np.ones(n)
    if target_sum is None:
        target_sum = 3.0

    z = _logit(p)
    lo, hi = -40.0, 40.0
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        s = _expit(z + mid).sum()
        if abs(s - target_sum) < tol:
            break
        if s < target_sum:
            lo = mid
        else:
            hi = mid
    return _expit(z + 0.5 * (lo + hi))


def _softmax(z: np.ndarray) -> np.ndarray:
    e = np.exp(np.asarray(z, dtype=float) - np.max(z))
    return e / e.sum()


def invert_harville(p_itm: np.ndarray) -> tuple[np.ndarray, dict]:
    """Find win probabilities whose Harville top-3 marginals equal ``p_itm``.

    Solved as least squares over log-strengths: parametrise
    ``w = softmax(z)`` — which enforces positivity and the sum-to-one
    constraint for free — and drive ``harville_itm(softmax(z)) - target`` to
    zero with Levenberg-Marquardt, warm-started from ``z = log(target)``.

    A note on why it is done this way, since the obvious alternative looks
    simpler. Iterative proportional fitting (multiply each ``w_i`` by
    ``target_i / current_i``, renormalise, repeat) is the textbook approach and
    does converge, but slowly and unevenly: measured over random Dirichlet
    fields it left errors around 1e-4 after 500 iterations in four- and
    six-horse fields, while reaching 1e-10 in twelve-horse fields. That pattern
    is easy to misread as the inversion being ill-posed in small fields — the
    thought being that when only one horse misses the board, P(ITM) carries
    little information about who *wins*. It is not ill-posed. The least-squares
    solver recovers the generating win vector to around 1e-14 at every field
    size from 4 to 12, small fields included. IPF was simply a bad solver for
    this residual surface.

    Returns ``(w, info)``; ``info["max_abs_error"]`` is the achieved residual
    in P(ITM) space, so a caller can refuse to simulate from a vector that did
    not solve rather than doing it silently.
    """
    from scipy.optimize import least_squares

    target = np.asarray(p_itm, dtype=float)
    n = len(target)
    if n <= 3:
        w = np.full(n, 1.0 / max(n, 1))
        return w, {"converged": True, "max_abs_error": 0.0, "n_eval": 0,
                   "note": "field of 3 or fewer: all horses ITM by definition"}

    def residual(z: np.ndarray) -> np.ndarray:
        return harville_itm(_softmax(z)) - target

    z0 = np.log(np.clip(target, 1e-6, None))
    z0 = z0 - z0.mean()
    sol = least_squares(residual, z0, xtol=1e-14, ftol=1e-14, gtol=1e-14,
                        max_nfev=2000)

    w = _softmax(sol.x)
    err = float(np.max(np.abs(harville_itm(w) - target)))
    info = {"converged": bool(err < 1e-8), "max_abs_error": err,
            "n_eval": int(sol.nfev)}
    if not info["converged"]:
        log.warning("Harville inversion did not converge: max|err|=%.2e", err)
    return w, info


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    """Check the Harville implementation and its inverse against each other."""
    from market_model_v2a import MarketModelITM

    rng = np.random.default_rng(6001)
    ok = True

    for n in (4, 6, 8, 12):
        for _ in range(25):
            w = rng.dirichlet(np.full(n, 0.7))

            mine = harville_itm(w)
            theirs = MarketModelITM().predict_p_itm(w, np.zeros(n, dtype=int))
            d = float(np.max(np.abs(mine - theirs)))
            if d > 1e-9:
                print(f"  FAIL n={n}: harville_itm vs MarketModelITM {d:.3e}")
                ok = False

            back, info = invert_harville(mine)
            d2 = float(np.max(np.abs(back - w)))
            if not info["converged"] or d2 > 1e-6:
                print(f"  FAIL n={n}: inversion recovered w to {d2:.3e}, "
                      f"ITM residual {info['max_abs_error']:.3e}")
                ok = False

    # Normalisation must hit the constraint exactly and preserve order.
    for n in (5, 9, 14):
        p = rng.uniform(0.05, 0.9, n)
        q = normalise_itm(p)
        if abs(q.sum() - 3.0) > 1e-6:
            print(f"  FAIL n={n}: normalised sum {q.sum():.6f} != 3")
            ok = False
        if not np.array_equal(np.argsort(p), np.argsort(q)):
            print(f"  FAIL n={n}: normalisation changed the ordering")
            ok = False

    print("dpv1_runtime self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    raise SystemExit(_self_test())
