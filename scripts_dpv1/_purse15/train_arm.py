"""Train one arm of the purse-change ablation. See RULES.md.

    PYTHONHASHSEED=0 python _purse15/train_arm.py <db> <model_out> <fold_csv> <version> [--p1]

Live dpv1.pkl's 94 fundamental features, pinned; --p1 swaps
purse_change_from_last for purse_logratio_clipped. Everything else is
train_dpv1.cmd_final unchanged (five tracks, grid half-life/L2).
"""
import argparse, logging, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import train_dpv1
from dpv1_runtime import load_model

db, model_out, fold_csv, version = sys.argv[1:5]
p1 = "--p1" in sys.argv[5:]
# dpv1.3.0 (live when the arms trained) defines the 94 pinned features
COLS = list(load_model(HERE / "dpv1_20260919_040326_retired.pkl").fund_cols)
assert len(COLS) == 94 and "purse_change_from_last" in COLS
if p1:
    COLS = ["purse_logratio_clipped" if c == "purse_change_from_last" else c for c in COLS]
_orig = train_dpv1.split_feature_columns
def pinned(cols):
    fund, market = _orig(cols)
    missing = sorted(set(COLS) - set(fund))
    if missing:
        raise RuntimeError(f"pinned features absent from table: {missing}")
    return list(COLS), market
train_dpv1.split_feature_columns = pinned
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.info("arm %s: %d features (p1=%s) on %s", version, len(COLS), p1, db)
T = "GP,CT,MNR,ELP,DED"
sys.exit(train_dpv1.cmd_final(argparse.Namespace(
    db=db, grid=str(train_dpv1.GRID_OUT), model_out=model_out, fold_preds=fold_csv,
    max_iter=400, version=version, with_interaction=False, tracks=T, train_tracks=T)))
