"""Scratch, read-only: frame for the purse-change investigation.
entry grain: feature value, today's race context, reconstructed last-race context, live OOF p_fund."""
import sqlite3, sys
import numpy as np, pandas as pd
from pathlib import Path
REPO = Path(r"D:\Benter Model_v2 Data\benter-model_v2-data")
sys.path.insert(0, str(REPO / "scripts_dpv1"))
from dpv1_common import normalize_race_type, class_tier

def load():
    c = sqlite3.connect(f"file:{REPO/'scripts/racing_full.db'}?mode=ro", uri=True)
    ent = pd.read_sql_query("""
        SELECT e.id entry_id, e.race_id, e.horse_id, rd.race_date, t.code track, r.purse, r.race_type,
               r.claiming_price race_tag, e.claiming_price tag, e.finish_pos, r.field_size
        FROM entries e JOIN races r ON r.id=e.race_id JOIN race_days rd ON rd.id=r.race_day_id
        JOIN tracks t ON t.id=rd.track_id""", c)
    f = pd.read_sql_query("""SELECT entry_id, purse_change_from_last, class_score, class_score_change_from_last,
                                   class_change_from_last FROM entry_features_dpv1""", c)
    ent = ent.merge(f, on="entry_id", how="left")
    ent = ent.sort_values(["horse_id", "race_date", "entry_id"])
    g = ent.groupby("horse_id")
    for col in ("race_date", "purse", "race_type", "track", "race_tag", "class_score"):
        ent["prev_" + col] = g[col].shift(1)
    # strictly-earlier date only (the builder's rule); a same-day duplicate would break it
    same = ent["prev_race_date"] == ent["race_date"]
    ent.loc[same, [c for c in ent.columns if c.startswith("prev_")]] = np.nan
    ent["rt"] = ent["race_type"].map(normalize_race_type)
    ent["prev_rt"] = ent["prev_race_type"].map(normalize_race_type)
    ent["tier"] = ent["race_type"].map(class_tier)
    ent["prev_tier"] = ent["prev_race_type"].map(class_tier)
    ent["recon_pct"] = (ent["purse"] - ent["prev_purse"]) / ent["prev_purse"]
    oof = pd.read_csv(REPO / "scripts_dpv1/dpv1_fold_predictions.csv",
                      usecols=["entry_id", "y_true", "p_fund", "y_pred", "fold"])
    df = oof.merge(ent, on="entry_id", how="left")
    # card-style P(ITM): p_fund normalised to sum min(3, n) per race
    s = df.groupby("race_id")["p_fund"].transform("sum"); n = df.groupby("race_id")["p_fund"].transform("size")
    df["p_norm"] = (df["p_fund"] * np.minimum(3, n) / s).clip(upper=0.999)
    return ent, df
