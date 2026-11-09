"""Card input snapshots: what the model scored on a saved card run, exactly.

Written by ``card_picks.py --save`` next to the prediction log
(``logs/card_snapshots/<TRACK>_<date>_<stamp>.json.gz``, about 0.1 MB a
card), and by the backfill harness for older cards. One file per run:

* ``meta``: run stamp (``generated_at``), track, date, iters, seed, flags,
  picks file, name-matching state, and version tags: model version + sha256,
  PP reranker and class-context reranker versions + sha256, feature config
  version + sha256, speed-figure par version, git commit (and whether the
  tree was dirty).
* ``races``: per race, the card frame **before** the PP bridge (the stored
  feature row) and **after** it (the vector the model scored), the race
  conditions, the pre-bridge coverage (shipper detection), the shipper flags,
  the PP-reranker input rows (``pp_entries_raw``) and the morning-line
  display values.

``rescore`` rebuilds each race from the snapshot alone (no database) and
runs it through ``card_picks.score_race``, the same function the live run
uses, then rebuilds the logged rows with ``card_picks.prediction_rows``.
Re-scoring a record run's snapshot must reproduce its logged rows exactly;
that is the standing reproducibility check (PHASE_7_SCALING_PLAN section 3).

    python scripts_dpv1/card_snapshot.py rescore logs/card_snapshots/DED_2026-11-07_20261107-095415.json.gz
    python scripts_dpv1/card_snapshot.py show <snapshot>
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

DPV1_DIR = Path(__file__).resolve().parent
SNAPSHOT_DIR = DPV1_DIR / "logs" / "card_snapshots"
FORMAT = 1


# ---------------------------------------------------------------------------
# Exact frame <-> JSON
# ---------------------------------------------------------------------------

def _py(v):
    """JSON-safe Python scalar; floats keep their exact repr (incl. NaN)."""
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (pd.Timestamp, datetime)):
        return {"__ts__": v.isoformat()}
    if isinstance(v, (list, tuple)):
        return [_py(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _py(x) for k, x in v.items()}
    return v


def frame_to_json(df: pd.DataFrame) -> dict:
    return {"columns": [str(c) for c in df.columns],
            "dtypes": [str(t) for t in df.dtypes],
            "index": [_py(i) for i in df.index],
            "data": {str(c): [_py(v) for v in df[c].tolist()] for c in df.columns}}


def frame_from_json(obj: dict) -> pd.DataFrame:
    cols = {}
    for c, t in zip(obj["columns"], obj["dtypes"]):
        vals = obj["data"][c]
        if t == "object":
            cols[c] = pd.Series(vals, dtype=object)
        elif t.startswith("float"):
            cols[c] = pd.Series([np.nan if v is None else v for v in vals], dtype=t)
        else:
            cols[c] = pd.Series(pd.array(vals, dtype=t))
    df = pd.DataFrame(cols, columns=obj["columns"])
    df.index = pd.Index(obj["index"])
    return df


# ---------------------------------------------------------------------------
# Version tags
# ---------------------------------------------------------------------------

def sha256(path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        return h.hexdigest()
    except OSError:
        return None


def _git(*args) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=str(DPV1_DIR), capture_output=True,
                              text=True, timeout=20).stdout.strip() or None
    except Exception:  # noqa: BLE001 -- tags are best effort
        return None


def version_tags(model, model_path, db=None) -> dict:
    import card_picks as cp
    tags = {"model_version": getattr(model, "version", None),
            "model_pkl": Path(model_path).name,
            "model_file": Path(model_path).name,
            "model_sha256": sha256(model_path)}
    rr = cp.get_reranker()
    tags["pp_reranker_version"] = getattr(rr, "version", None)
    tags["pp_reranker_sha256"] = sha256(DPV1_DIR / "dpv1_pp_reranker.pkl") if rr else None
    cc = cp.get_classctx_reranker()
    tags["classctx_version"] = getattr(cc, "version", None)
    tags["classctx_sha256"] = sha256(DPV1_DIR / "dpv1_classctx_reranker.pkl") if cc else None
    cfg = DPV1_DIR / "dpv1_feature_config.json"
    try:
        tags["feature_config_version"] = json.load(open(cfg, encoding="utf-8")).get("version")
    except (OSError, ValueError):
        tags["feature_config_version"] = None
    tags["feature_config_sha256"] = sha256(cfg)
    try:
        tags["par_version"] = json.load(open(DPV1_DIR / "speed_par_config.json",
                                             encoding="utf-8")).get("par_version")
    except (OSError, ValueError):
        tags["par_version"] = None   # before 2026-11-08: whole-DB medians
    tags["git_commit"] = _git("rev-parse", "HEAD")
    tags["git_dirty"] = bool(_git("status", "--porcelain", "--untracked-files=no"))
    return tags


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def race_snapshot(card, frame_pre, frame_post, base_cov, pp_rows, shipper,
                  ml_map) -> dict:
    """One race's inputs, from the objects ``card_picks.one_race`` holds."""
    from equibase_pdf_parser import normalize_name
    ml = {}
    for nm in card.names():
        k = (int(card.race_num), normalize_name(nm))
        if k in ml_map:
            ml[normalize_name(nm)] = _py(list(ml_map[k]))
    return {"race_num": int(card.race_num), "track": card.track,
            "race_date": card.race_date, "source": card.source,
            "conditions": _py(dict(card.conditions)),
            "frame_pre_bridge": frame_to_json(frame_pre),
            "frame": frame_to_json(frame_post),
            "base_cov": _py(list(base_cov)),
            "pp_rows": None if pp_rows is None else {k: _py(v) for k, v in pp_rows.items()},
            "shipper": _py(list(shipper)),
            "ml": ml}


def write_snapshot(path, meta: dict, races: list[dict]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"format": FORMAT, "meta": _py(meta), "races": races}
    raw = json.dumps(doc, ensure_ascii=False, allow_nan=True).encode("utf-8")
    with gzip.open(path, "wb", compresslevel=9) as f:
        f.write(raw)
    return path


def load_snapshot(path) -> dict:
    with gzip.open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Re-scoring
# ---------------------------------------------------------------------------

def rescore(snap: dict, model_path=None) -> tuple[list[dict], list[dict]]:
    """``(results, rows)``: card_picks race results and the logged rows,
    rebuilt from the snapshot alone."""
    import card_picks as cp
    from dpv1_runtime import RaceCard, load_model
    meta = snap["meta"]
    mp = (Path(model_path) if model_path
          else DPV1_DIR / (meta.get("model_file") or meta["model_pkl"]))
    if meta.get("model_sha256") and sha256(mp) != meta["model_sha256"]:
        raise SystemExit(f"{mp.name}: sha256 differs from the snapshot's model")
    rr_path = DPV1_DIR / "dpv1_pp_reranker.pkl"
    if meta.get("pp_reranker_sha256") and sha256(rr_path) != meta["pp_reranker_sha256"]:
        raise SystemExit("dpv1_pp_reranker.pkl: sha256 differs from the snapshot's")
    cc_path = DPV1_DIR / "dpv1_classctx_reranker.pkl"
    if meta.get("classctx_sha256") and sha256(cc_path) != meta["classctx_sha256"]:
        raise SystemExit("dpv1_classctx_reranker.pkl: sha256 differs from the snapshot's")
    model = load_model(str(mp))
    results = []
    for rs in snap["races"]:
        card = RaceCard(frame=frame_from_json(rs["frame"]), track=rs["track"],
                        race_date=rs["race_date"], race_num=rs["race_num"],
                        source=rs["source"], conditions=rs["conditions"])
        ml_map = {(rs["race_num"], k): tuple(v) for k, v in rs["ml"].items()}
        r = cp.score_race(card, model, race_num=rs["race_num"],
                          base_cov=np.asarray(rs["base_cov"], dtype=float),
                          pp_rows=rs["pp_rows"], shipper=rs["shipper"],
                          ml_map=ml_map, iters=meta["iters"], seed=meta["seed"],
                          use_classctx=meta["use_classctx"])
        results.append(r)
    gen = datetime.fromisoformat(meta["generated_at"])
    rows = cp.prediction_rows(results, track=meta["track"], race_date=meta["race_date"],
                              model=model, model_pkl=meta["model_pkl"],
                              picks_file=meta["picks_file"], generated_at=gen,
                              stamp=meta["stamp"], name_matching=meta.get("name_matching"))
    return results, rows


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def compare_to_log(rows: list[dict], log_path, generated_at: str, track: str,
                   race_date: str) -> dict:
    logged = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            if generated_at not in line:
                continue
            r = json.loads(line)
            if (r.get("generated_at") == generated_at and r.get("track") == track
                    and r.get("race_date") == race_date):
                logged.append(r)
    key = lambda r: r["prediction_id"]
    L = {key(r): r for r in logged}
    N = {key(r): r for r in rows}
    diffs = []
    for k in sorted(set(L) | set(N)):
        if k not in L or k not in N:
            diffs.append(f"{k}: only in {'log' if k in L else 'rescore'}")
            continue
        a, b = L[k], N[k]
        for f in sorted(set(a) | set(b)):
            if not _same(a.get(f), b.get(f)):
                diffs.append(f"{k} {f}: logged {a.get(f)!r} rescored {b.get(f)!r}")
    return {"logged_rows": len(logged), "rescored_rows": len(rows),
            "differences": len(diffs), "first": diffs[:15],
            "identical": bool(logged) and not diffs}


def _cli() -> int:
    sys.path.insert(0, str(DPV1_DIR))
    sys.path.insert(0, str(DPV1_DIR.parent / "scripts"))
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rescore")
    r.add_argument("snapshot")
    r.add_argument("--log", default=str(DPV1_DIR / "logs" / "predictions.jsonl"))
    r.add_argument("--model", default=None)
    s = sub.add_parser("show")
    s.add_argument("snapshot")
    a = p.parse_args()
    snap = load_snapshot(a.snapshot)
    if a.cmd == "show":
        print(json.dumps(snap["meta"], indent=1))
        print(f"{len(snap['races'])} races, "
              f"{sum(len(x['frame']['index']) for x in snap['races'])} horses")
        return 0
    _, rows = rescore(snap, a.model)
    m = snap["meta"]
    res = compare_to_log(rows, a.log, m["generated_at"], m["track"], m["race_date"])
    print(json.dumps(res, indent=1))
    return 0 if res["identical"] else 2


if __name__ == "__main__":
    raise SystemExit(_cli())
