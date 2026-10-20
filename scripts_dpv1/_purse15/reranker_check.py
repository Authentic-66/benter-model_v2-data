"""Pre-promotion check: do the shipped rerankers still help on top of arm (a)?

    python _purse15/reranker_check.py      (from scripts_dpv1/)

For each base (live dpv1.3.0 folds, arm (a) folds) on identical rows, with
labels from the cleaned snapshot:
* PP reranker (live, applied): shipped pp-reranker-1.0 vs base alone, on
  PP-joinable races; split by whether the reranker trained on that period
  (its rows: 2026-05-08..2026-08-29). Also its documented 5-fold
  race-grouped CV (offset mode), re-fitted on each base.
* classctx-reranker-0.1 (shadow): shipped artifact vs base alone, all rows
  and DED (never in its 4-track training rows).
Top-pick ITM with exact McNemar; mean log-loss with race-clustered z.
"""
import sqlite3, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import binomtest
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parent.parent / "scripts"), str(HERE.parent.parent / "scripts_v2a")]
import dpv1_pp_reranker_train as PP
import dpv1_classctx_reranker_train as CC

SNAP = str(HERE / "racing_a.db")
BASES = {"live dpv1.3.0": HERE.parent / "dpv1_fold_predictions_dpv1.3.0.csv", "arm (a)": HERE / "folds_a.csv"}
PP_TRAIN_END = "2026-08-29"
sig = lambda z: 1 / (1 + np.exp(-z))

con = sqlite3.connect(f"file:{SNAP}?mode=ro", uri=True)
lab = pd.read_sql("SELECT id entry_id, finish_pos FROM entries WHERE finish_pos IS NOT NULL", con)

def with_labels(df):
    df = df.drop(columns=[c for c in ("y_true", "finish_pos") if c in df]).merge(lab, on="entry_id")
    df["y_true"] = (df.finish_pos <= 3).astype(int)
    return df

def compare(df, s_base, s_new, title):
    t = lambda c: df.loc[df.groupby("race_id")[c].idxmax()].set_index("race_id")["y_true"]
    a, b = t(s_base), t(s_new)
    up, dn = int(((a == 0) & (b == 1)).sum()), int(((a == 1) & (b == 0)).sum())
    p = binomtest(up, up + dn).pvalue if up + dn else 1.0
    y = df.y_true.to_numpy()
    ll = lambda z: -(y * np.log(sig(z)) + (1 - y) * np.log(1 - sig(z)))
    dl = pd.Series(ll(df[s_new].to_numpy()) - ll(df[s_base].to_numpy()))
    g = dl.groupby(df.race_id.to_numpy()).sum(); se = np.sqrt(len(g)) * g.std() / len(dl)
    print(f"  {title:<44} races {len(a):>5}  base {100*a.mean():5.1f}%  reranked {100*b.mean():5.1f}%  "
          f"{100*(b.mean()-a.mean()):+5.1f}pp  ({up}/{dn}, p {p:.3f})  log-loss {dl.mean():+.5f} (z {dl.mean()/se if se else 0:+.2f})")

# ---- PP reranker -------------------------------------------------------------
ppr = PP.load_reranker(HERE.parent / "dpv1_pp_reranker.pkl")
data = {k: with_labels(PP.load_dataset(SNAP, v)) for k, v in BASES.items()}
common = set(data["live dpv1.3.0"].entry_id) & set(data["arm (a)"].entry_id)
print("=== PP reranker (live, applied) on PP-joinable held-out rows ===")
for k, df in data.items():
    df = df[df.entry_id.isin(common)].reset_index(drop=True)
    X, _ = PP.build_features(df, "offset", ppr.training_notes["style_spec"], ppr.training_notes["impute"])
    df["rr"] = ppr.adjust_logit(df.base_logit, X[ppr.feature_names])
    print(f" base = {k}  ({len(df):,} rows)")
    compare(df, "base_logit", "rr", "shipped, all common rows")
    compare(df[df.race_date <= PP_TRAIN_END].reset_index(drop=True), "base_logit", "rr", "shipped, its training period (in-sample)")
    compare(df[df.race_date > PP_TRAIN_END].reset_index(drop=True), "base_logit", "rr", "shipped, after its training (out-of-sample)")
    for mode in ("offset",):
        adj, _ = PP.cross_val_predict(df, mode, 1.0, 5)
        df["cv"] = adj
        compare(df, "base_logit", "cv", f"5-fold race-grouped CV refit ({mode})")
dfa = data["arm (a)"]
extra = dfa[~dfa.entry_id.isin(common)].reset_index(drop=True)
X, _ = PP.build_features(extra, "offset", ppr.training_notes["style_spec"], ppr.training_notes["impute"])
extra["rr"] = ppr.adjust_logit(extra.base_logit, X[ppr.feature_names])
print(f" base = arm (a), rows beyond live's fold window (after 2026-09-18; both out of sample): {len(extra):,} rows,"
      f" tracks {sorted(extra.track.unique())}")
compare(extra, "base_logit", "rr", "shipped, post-9/18 PP cards")
for t in sorted(extra.track.unique()):
    compare(extra[extra.track == t].reset_index(drop=True), "base_logit", "rr", f"   {t}")

# ---- classctx (shadow) ---------------------------------------------------------
ccr = CC.load_reranker(HERE.parent / "dpv1_classctx_reranker.pkl")
print("\n=== classctx-reranker-0.1 (shadow, not applied live) ===")
cdat = {k: with_labels(CC.load_dataset(SNAP, v)) for k, v in BASES.items()}
ccom = set(cdat["live dpv1.3.0"].entry_id) & set(cdat["arm (a)"].entry_id)
for k, df in cdat.items():
    df = df[df.entry_id.isin(ccom)].reset_index(drop=True)
    X, _, _ = CC.build_features(df, "offset", ccr.impute)
    df["rr"] = ccr.adjust_logit(df.base_logit, X[ccr.feature_names])
    print(f" base = {k}  ({len(df):,} rows)")
    compare(df, "base_logit", "rr", "shipped, all rows (non-DED in its training)")
    compare(df[df.track == "DED"].reset_index(drop=True), "base_logit", "rr", "shipped, DED (out-of-sample)")
    compare(df[df.track != "DED"].reset_index(drop=True), "base_logit", "rr", "shipped, non-DED")
