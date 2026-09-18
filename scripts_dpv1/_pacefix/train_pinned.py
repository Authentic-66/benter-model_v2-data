"""Pace-duplicate fix (2026-09-18): retrain live's feature list, optionally minus columns.

Pins train_dpv1's feature list to dpv1.pkl's fund_cols (minus --drop), so the
control and candidate differ only by the removed duplicate. No code under
scripts/ or scripts_dpv1/ is modified.

    PYTHONHASHSEED=0 python _pacefix/train_pinned.py <db> <model_out> <fold_csv> <version> [--drop col ...]
"""
import sys, argparse, logging
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import train_dpv1
from dpv1_runtime import load_model

ap = argparse.ArgumentParser()
ap.add_argument("db"); ap.add_argument("model_out"); ap.add_argument("fold_csv"); ap.add_argument("version")
ap.add_argument("--drop", nargs="*", default=[])
a = ap.parse_args()

LIVE = load_model(HERE / "dpv1.pkl")
COLS = [c for c in LIVE.fund_cols if c not in set(a.drop)]
assert len(COLS) == len(LIVE.fund_cols) - len(a.drop), "a --drop column is not in live's list"
_orig = train_dpv1.split_feature_columns

def pinned(cols):
    fund, market = _orig(cols)
    missing = sorted(set(COLS) - set(fund))
    if missing:
        raise RuntimeError(f"pinned features absent from table: {missing}")
    return list(COLS), market

train_dpv1.split_feature_columns = pinned
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.info("pinned %d fundamental features (dropped %s)", len(COLS), a.drop)
sys.exit(train_dpv1.cmd_final(argparse.Namespace(
    db=a.db, grid=str(train_dpv1.GRID_OUT), model_out=a.model_out, fold_preds=a.fold_csv,
    max_iter=400, version=a.version, with_interaction=False, tracks=None, train_tracks=None)))
