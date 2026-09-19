"""Stage 4 arms (2026-09-19): live's 94 fundamental features, pinned, on _ded/racing_ded.db.

    PYTHONHASHSEED=0 python _ded/train_arm.py <model_out> <fold_csv> <version> <tracks> <train_tracks>

<tracks> is the corpus loaded and validated; <train_tracks> restricts only what is
fit (Phase 6C design). Identical validation rows follow from identical <tracks>.
No code under scripts/ or scripts_dpv1/ is modified.
"""
import sys, argparse, logging
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import train_dpv1
from dpv1_runtime import load_model

model_out, fold_csv, version, tracks, train_tracks = sys.argv[1:6]
COLS = list(load_model(HERE / "dpv1.pkl").fund_cols)
_orig = train_dpv1.split_feature_columns
def pinned(cols):
    fund, market = _orig(cols)
    missing = sorted(set(COLS) - set(fund))
    if missing:
        raise RuntimeError(f"pinned features absent from table: {missing}")
    return list(COLS), market
train_dpv1.split_feature_columns = pinned
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.info("arm %s: %d features, tracks=%s train_tracks=%s", version, len(COLS), tracks, train_tracks)
sys.exit(train_dpv1.cmd_final(argparse.Namespace(
    db=str(HERE / "_ded" / "racing_ded.db"), grid=str(train_dpv1.GRID_OUT), model_out=model_out,
    fold_preds=fold_csv, max_iter=400, version=version, with_interaction=False,
    tracks=tracks, train_tracks=train_tracks)))
