"""Stretch-run features: one definition for charts (training) and PP lines (live).

Doug's idea (2026-10-21): did the horse finish fast last time? Measured as
lengths gained or lost from the stretch call to the finish in its previous
race. The stretch call is usually the eighth pole, so this is roughly the
final furlong.

Beaten lengths at a call
------------------------
* Chart (Equibase): each call token is ``<position><margin>``, and the margin
  is lengths ahead of the NEXT horse (the same quantity as
  ``entries.beaten_lengths``). A horse's lengths behind the leader at a call =
  the sum of the margins of every horse ahead of it. Needs the whole field.
* PP line (Brisnet): each call is ``<position><superscript>``; the superscript
  is lengths behind the leader (the leader's is its lead, so 0 behind). Read
  straight off the horse's own line.

Both give "lengths behind the leader at that call", so

    gain = BL(stretch call) - BL(finish)     (positive = closed ground)

is the same number from either source, up to chart rounding (checked in
``diagnostics/stretch_run/pp_vs_chart.py``).

Features (values from the horse's previous race in the corpus, the same
"previous race" as every other last_race_* feature)
---------------------------------------------------------------------------
* ``last_str_gain``           gain, clipped to +-15 lengths.        chart, PP
* ``last_str_gain_rank_pct``  rank of gain in that field, 0 = best,
                              1 = worst, (rank-1)/(n-1), ties min.  chart only
* ``last_str_gain_padj``      gain - E[gain | BL at stretch call bucket,
                              early-pace bucket], clipped +-15.      chart, PP*
* ``last_str_gain_padj_rank_pct``  rank of padj in that field.      chart only

E[gain | ...] is fitted on races before 2023-01-01 only (ahead of the first
validation fold). Early pace = leader's time at the race's second
fractional time (first if only two), as a z-score against the median and
spread of the same (track, distance, surface) before 2023; cells with fewer
than 20 races, or races without fractions, use the pooled expectation for
their stretch-call bucket. *A PP line's race is usually at a track with no
par here, so its padj uses the pooled expectation.

A PP line can never give a rank: it shows one horse.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

GAIN_CLIP = 15.0
PADJ_FIT_BEFORE = "2023-01-01"
PAR_MIN_RACES = 20
BL_STR_EDGES = [-np.inf, 1e-9, 2.0, 5.0, 10.0, np.inf]      # 0 | (0,2] | (2,5] | (5,10] | >10
PACE_Z_EDGES = [-np.inf, -1.0, -0.33, 0.33, 1.0, np.inf]   # fast .. slow early pace

FEATURES = ["last_str_gain", "last_str_gain_rank_pct",
            "last_str_gain_padj", "last_str_gain_padj_rank_pct"]

# ---------------------------------------------------------------------------
# Chart side
# ---------------------------------------------------------------------------

_FIXED = {"head": 0.1, "neck": 0.25, "nose": 0.05}


def margin_lengths(s: str | None) -> float | None:
    """Chart margin text -> lengths ('11/2' after the position = 1.5)."""
    if not s:
        return None
    low = s.lower()
    if low in _FIXED:
        return _FIXED[low]
    m = re.match(r"^(\d+?)?(\d/\d)?$", s)
    if m and (m.group(1) or m.group(2)):
        whole = int(m.group(1) or 0)
        frac = 0.0
        if m.group(2):
            a, b = m.group(2).split("/")
            frac = int(a) / int(b)
        return whole + frac
    return None


def _token_candidates(tok: str, n: int) -> list[tuple[int, float | None]]:
    out = []
    for k in (1, 2):
        if len(tok) < k or not tok[:k].isdigit():
            continue
        pos, rest = int(tok[:k]), tok[k:]
        if pos < 1 or pos > n or (k == 2 and pos < 10):
            continue
        ml = margin_lengths(rest) if rest else None
        if rest and ml is None:
            continue
        out.append((pos, ml))
    return out


def call_beaten_lengths(tokens: dict, n: int) -> dict | None:
    """{key: chart token} for one call of one race -> {key: lengths behind the
    leader}, or None when the call cannot be read for the whole field.

    Positions must form 1..n; a token like '11/2' is position 1 + margin 1/2
    or position 11 + margin /2 only by elimination against the rest of the
    field.
    """
    cands = {k: _token_candidates(t, n) for k, t in tokens.items()}
    if any(not v for v in cands.values()):
        return None
    pos: dict = {}
    taken: set = set()
    changed = True
    while changed:
        changed = False
        for k, v in cands.items():
            if k in pos:
                continue
            free = [x for x in v if x[0] not in taken]
            if len(free) == 1:
                pos[k] = free[0]
                taken.add(free[0][0])
                changed = True
    if len(pos) != len(cands):
        return None
    order = sorted(pos.items(), key=lambda kv: kv[1][0])
    if [p for _, (p, _) in order] != list(range(1, len(order) + 1)):
        return None
    out, acc = {}, 0.0
    for i, (k, (_, ml)) in enumerate(order):
        out[k] = acc
        if i < len(order) - 1:
            if ml is None:
                return None
            acc += ml
    return out


def _seconds(s) -> float | None:
    if not isinstance(s, str) or not s.strip():
        return None
    s = s.strip().lstrip(":")
    try:
        if ":" in s:
            m, sec = s.split(":")
            return int(m) * 60 + float(sec)
        return float(s)
    except ValueError:
        return None


def early_fraction(fractional_times) -> float | None:
    """Leader's time at the second fractional time (first if only two)."""
    try:
        fr = json.loads(fractional_times) if isinstance(fractional_times, str) else None
    except json.JSONDecodeError:
        return None
    if not fr or len(fr) < 2:
        return None
    return _seconds(fr[1] if len(fr) >= 3 else fr[0])


def race_stretch_table(conn) -> pd.DataFrame:
    """One row per charted entry: bl_str, bl_fin, gain, gain rank in field,
    and the race's early-pace inputs. Only races whose Str and Fin calls are
    readable for every starter."""
    df = pd.read_sql("""
        SELECT e.id entry_id, e.race_id, e.pace_calls_json pj, r.call_labels,
               r.fractional_times, r.distance_yards, r.surface, rd.track_id,
               rd.race_date
        FROM entries e JOIN races r ON r.id = e.race_id
        JOIN race_days rd ON rd.id = r.race_day_id
        WHERE e.pace_calls_json IS NOT NULL""", conn)
    rows = []
    for rid, g in df.groupby("race_id", sort=False):
        labs = g.call_labels.iloc[0]
        if not isinstance(labs, str):
            continue
        try:
            labs = json.loads(labs)
        except json.JSONDecodeError:
            continue
        if "Str" not in labs or "Fin" not in labs:
            continue
        calls = {}
        try:
            calls = {e: json.loads(p) for e, p in zip(g.entry_id, g.pj)}
        except (json.JSONDecodeError, TypeError):
            continue
        res = {}
        for lab in ("Str", "Fin"):
            toks = {e: d.get(lab) if isinstance(d, dict) else None for e, d in calls.items()}
            if any(not isinstance(t, str) or not t or t == "---" for t in toks.values()):
                res = None
                break
            res[lab] = call_beaten_lengths(toks, len(g))
            if res[lab] is None:
                res = None
                break
        if res is None:
            continue
        for e in g.entry_id:
            rows.append((e, rid, res["Str"][e], res["Fin"][e]))
    s = pd.DataFrame(rows, columns=["entry_id", "race_id", "bl_str", "bl_fin"])
    s["gain"] = s.bl_str - s.bl_fin
    races = df.drop_duplicates("race_id")[["race_id", "fractional_times", "distance_yards",
                                           "surface", "track_id", "race_date"]]
    races = races.assign(early=races.fractional_times.map(early_fraction)).drop(columns="fractional_times")
    return s.merge(races, on="race_id", how="left")


def rank_pct(s: pd.DataFrame, col: str) -> pd.Series:
    r = s.groupby("race_id")[col].rank(ascending=False, method="min")
    n = s.groupby("race_id")[col].transform("count")
    return ((r - 1) / (n - 1)).where(n > 1)


def fit_padj(s: pd.DataFrame) -> dict:
    """Par cells and expected-gain table, from races before PADJ_FIT_BEFORE."""
    pre = s[s.race_date < PADJ_FIT_BEFORE]
    rr = pre.drop_duplicates("race_id").dropna(subset=["early"])
    cell = rr.groupby(["track_id", "distance_yards", "surface"]).early
    par = pd.DataFrame({"med": cell.median(), "sd": cell.std(), "n": cell.size()})
    par = par[(par.n >= PAR_MIN_RACES) & (par.sd > 0)]
    pre = add_pace_bucket(pre, par)
    pre = pre.assign(blb=pd.cut(pre.bl_str, BL_STR_EDGES, labels=False))
    exp_cell = pre.dropna(subset=["paceb"]).groupby(["blb", "paceb"]).gain.mean()
    exp_pool = pre.groupby("blb").gain.mean()
    return {"par": par, "exp_cell": exp_cell, "exp_pool": exp_pool}


def add_pace_bucket(s: pd.DataFrame, par: pd.DataFrame) -> pd.DataFrame:
    k = s.set_index(["track_id", "distance_yards", "surface"]).index
    med = par.med.reindex(k).to_numpy()
    sd = par.sd.reindex(k).to_numpy()
    z = (s.early.to_numpy() - med) / sd
    return s.assign(pace_z=z, paceb=pd.cut(z, PACE_Z_EDGES, labels=False))


def expected_gain(bl_str, paceb, fit: dict) -> np.ndarray:
    blb = pd.cut(pd.Series(bl_str, dtype="float64"), BL_STR_EDGES, labels=False).to_numpy()
    out = np.full(len(blb), np.nan)
    for i, (b, p) in enumerate(zip(blb, paceb)):
        if np.isnan(b):
            continue
        v = fit["exp_cell"].get((b, p), np.nan) if not (p is None or np.isnan(p)) else np.nan
        if np.isnan(v):
            v = fit["exp_pool"].get(b, np.nan)
        out[i] = v
    return out


def chart_entry_values(conn) -> tuple[pd.DataFrame, dict]:
    """In-race values for every charted entry (the race itself, not 'last')."""
    s = race_stretch_table(conn)
    fit = fit_padj(s)
    s = add_pace_bucket(s, fit["par"])
    s["gain_rank_pct"] = rank_pct(s, "gain")
    s["padj"] = s.gain - expected_gain(s.bl_str.to_numpy(), s.paceb.to_numpy(), fit)
    s["padj_rank_pct"] = rank_pct(s, "padj")
    return s, fit


def last_race_features(conn) -> pd.DataFrame:
    """The four features for every entry in the DB, from the horse's previous
    race (strictly earlier date; same lookup as the feature builder)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from feature_builder import _prior_last_value  # the builder's own lookup
    s, _ = chart_entry_values(conn)
    ent = pd.read_sql("""SELECT e.id entry_id, e.horse_id, rd.race_date
                         FROM entries e JOIN races r ON r.id = e.race_id
                         JOIN race_days rd ON rd.id = r.race_day_id""", conn)
    ent = ent.merge(s[["entry_id", "gain", "gain_rank_pct", "padj", "padj_rank_pct"]],
                    on="entry_id", how="left")
    ent["race_date_dt"] = pd.to_datetime(ent.race_date)
    prev = _prior_last_value(ent, entity_col="horse_id",
                             value_cols=["gain", "gain_rank_pct", "padj", "padj_rank_pct"],
                             date_col="race_date", prefix="p")
    out = ent[["entry_id"]].merge(prev, on="entry_id", how="left")
    f = pd.DataFrame({"entry_id": out.entry_id})
    f["last_str_gain"] = pd.to_numeric(out.p_gain, errors="coerce").clip(-GAIN_CLIP, GAIN_CLIP)
    f["last_str_gain_rank_pct"] = pd.to_numeric(out.p_gain_rank_pct, errors="coerce")
    f["last_str_gain_padj"] = pd.to_numeric(out.p_padj, errors="coerce").clip(-GAIN_CLIP, GAIN_CLIP)
    f["last_str_gain_padj_rank_pct"] = pd.to_numeric(out.p_padj_rank_pct, errors="coerce")
    return f


# ---------------------------------------------------------------------------
# PP side
# ---------------------------------------------------------------------------

def pp_line_stretch(full_line: str) -> dict | None:
    """Stretch call and finish from one whole-width Brisnet PP race line.

    The FIN call is the token right before the jockey (brisnet_pp_parser's
    _PP_FIN_RE); the stretch call is the token right before FIN. Each is
    position digits + superscript lengths behind the leader; position 1 is
    0 behind. Neck is 0.3 on a PP and 0.25 in the corpus; mapped to 0.25.
    """
    from brisnet_pp_parser import _PP_FIN_RE, _SUP_CHARS, _sup_to_lengths
    m = _PP_FIN_RE.search(full_line)
    if not m:
        return None
    before = full_line[:m.start()]
    sm = re.search(r"(\d{1,2})([" + _SUP_CHARS + r"]+)\s*$", before)
    if not sm:
        return None

    def bl(pos, sup):
        if pos == 1:
            return 0.0
        return _sup_to_lengths(sup) - (0.05 if "\xb3" in sup else 0.0)

    str_pos, fin_pos = int(sm.group(1)), int(m.group(1))
    b_str, b_fin = bl(str_pos, sm.group(2)), bl(fin_pos, m.group(2))
    return {"str_pos": str_pos, "bl_str": b_str, "fin_pos": fin_pos,
            "bl_fin": b_fin, "gain": b_str - b_fin}


def pp_features(full_line: str, fit: dict) -> dict:
    """Bridgeable values from a horse's most recent PP line (ranks: never)."""
    r = pp_line_stretch(full_line)
    if r is None:
        return {"last_str_gain": None, "last_str_gain_padj": None}
    e = expected_gain(np.array([r["bl_str"]]), np.array([np.nan]), fit)[0]
    clip = lambda v: float(max(-GAIN_CLIP, min(GAIN_CLIP, v)))
    return {"last_str_gain": clip(r["gain"]),
            "last_str_gain_padj": None if np.isnan(e) else clip(r["gain"] - e)}
