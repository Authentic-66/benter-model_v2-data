"""Option C (2026-09-18): retrain live's exact 95-feature set on a given DB.

Pins train_dpv1's feature list to dpv1.pkl's fund_cols so the only thing that
differs between the control (buggy table) and candidate (fixed table) is the
trailing-window fix. No code under scripts/ or scripts_dpv1/ is modified.

    PYTHONHASHSEED=0 python _gap4fix/train_c95.py <db> <model_out> <fold_csv> <version>
"""
import sys, argparse, logging
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import train_dpv1
from dpv1_runtime import load_model

LIVE = load_model(HERE / "dpv1.pkl")
_orig = train_dpv1.split_feature_columns

def pinned(cols):
    fund, market = _orig(cols)
    missing = sorted(set(LIVE.fund_cols) - set(fund))
    if missing:
        raise RuntimeError(f"live features absent from table: {missing}")
    return list(LIVE.fund_cols), market

train_dpv1.split_feature_columns = pinned

db, model_out, fold_csv, version = sys.argv[1:5]
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
args = argparse.Namespace(db=db, grid=str(train_dpv1.GRID_OUT), model_out=model_out,
                          fold_preds=fold_csv, max_iter=400, version=version,
                          with_interaction=False, tracks=None, train_tracks=None)
sys.exit(train_dpv1.cmd_final(args))
