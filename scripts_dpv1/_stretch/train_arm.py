"""Train one arm of the stretch-run ablation. See RULES.md.

    PYTHONHASHSEED=0 python _stretch/train_arm.py <c0|s1|s2> <db> <model_out> <fold_csv>

Live dpv1.pkl's 94 fundamental features, pinned, plus the arm's two columns.
Everything else is train_dpv1.cmd_final unchanged (five tracks, grid
half-life/L2). The version string is the live one for c0 (so Gate 0 can
compare its folds byte-for-byte) and a research tag for s1/s2.
"""
import argparse, logging, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import train_dpv1
from dpv1_runtime import load_model

arm, db, model_out, fold_csv = sys.argv[1:5]
EXTRA = {"c0": [],
         "s1": ["last_str_gain", "last_str_gain_rank_pct"],
         "s2": ["last_str_gain_padj", "last_str_gain_padj_rank_pct"]}[arm]
live = load_model(HERE / "dpv1.pkl")
assert live.version == "dpv1.3.1-5track-clean", live.version
BASE = list(load_model(HERE / "dpv1_20260919_040326_retired.pkl").fund_cols)
assert len(BASE) == 94 and sorted(BASE) == sorted(live.fund_cols)
COLS = BASE + EXTRA
VERSION = live.version if arm == "c0" else f"dpv1.3.1-stretch-{arm}"
_orig = train_dpv1.split_feature_columns
def pinned(cols):
    fund, market = _orig(cols)
    missing = sorted(set(COLS) - set(fund))
    if missing:
        raise RuntimeError(f"pinned features absent from table: {missing}")
    return list(COLS), market
train_dpv1.split_feature_columns = pinned
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.info("arm %s (%s): %d features on %s", arm, VERSION, len(COLS), db)
T = "GP,CT,MNR,ELP,DED"
sys.exit(train_dpv1.cmd_final(argparse.Namespace(
    db=db, grid=str(train_dpv1.GRID_OUT), model_out=model_out, fold_preds=fold_csv,
    max_iter=400, version=VERSION, with_interaction=False, tracks=T, train_tracks=T)))
