"""Step 3: DED meet winners (from 2026-10-09) with their previous race's
stretch-run rank. Reads out/stretch.pkl; writes ded_winners_stretch.csv here.

    python scripts_dpv1/diagnostics/stretch_run/s3_ded_winners.py
"""
import sqlite3
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent
d = pd.read_pickle(HERE / "out" / "stretch.pkl").sort_values(["horse_id", "race_date", "race_num"])
for col in ["str_gain", "str_gain_rank", "fin", "race_date", "track", "n_call"]:
    d["last_" + col] = d.groupby("horse_id")[col].shift(1)
c = sqlite3.connect(HERE.parents[2] / "scripts" / "racing_full.db")
names = pd.read_sql("select e.id entry_id, h.name from entries e join horses h on h.id=e.horse_id", c)
w = d[(d.track == "DED") & (d.race_date >= "2026-10-09") & (d.fin == 1)].merge(names, on="entry_id")
w = w.sort_values(["race_date", "race_num"])
cols = ["race_date", "race_num", "name", "final_odds", "last_track", "last_race_date",
        "last_str_gain", "last_str_gain_rank", "last_n_call", "last_fin"]
w[cols].to_csv(HERE / "ded_winners_stretch.csv", index=False)
k = w[w.last_str_gain_rank.notna()]
print(f"DED winners {len(w)}, with charted last race {len(k)}: fastest stretch "
      f"{int((k.last_str_gain_rank == 1).sum())}, top-3 {int((k.last_str_gain_rank <= 3).sum())}")
