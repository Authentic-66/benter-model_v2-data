"""Overlay test, step 2a: score every out-of-sample race with live dpv1.3.2 + pp-reranker-1.0
on a SCRATCH copy of the DB. Writes one row per starter to rerun_rows.csv.

Point-in-time fix (scratch only): days_since_jockey_last_win / days_since_trainer_last_win
are replaced by their start-of-day values (last win on a date strictly before the race
date), the 1.4 item 5 rule. Every other jockey/trainer feature already matches a
start-of-day recompute (same_day_audit_2026-11-09).
"""
import json, re, sqlite3, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"D:\Benter Model_v2 Data\benter-model_v2-data")
sys.path.insert(0, str(ROOT / "scripts_dpv1")); sys.path.insert(0, str(ROOT / "scripts"))
import logging; logging.disable(logging.WARNING)
from dpv1_runtime import load_model, load_race_from_db, normalise_itm, invert_harville, harville_itm
from card_picks import rerank_probabilities

HERE = Path(sys.argv[1])  # scratch work dir (holds racing_scratch.db = byte copy of the live DB)
DB = HERE / "racing_scratch.db"
model = load_model(ROOT / "scripts_dpv1" / "dpv1.pkl")
assert model.version == "dpv1.3.2-5track-stretch", model.version
oos = json.load(open(HERE / "oos.json"))

# ---- start-of-day values for the two same-day features (whole DB history) ----
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
raw = pd.read_sql_query("""SELECT e.id AS entry_id, e.race_id, e.jockey_id, e.trainer_id, e.finish_pos, rd.race_date
    FROM entries e JOIN races r ON r.id=e.race_id JOIN race_days rd ON rd.id=r.race_day_id""", c)
raw["date"] = pd.to_datetime(raw["race_date"]); raw["is_win"] = (raw["finish_pos"] == 1).astype(float)
SOD = {}
for role in ("jockey", "trainer"):
    key = f"{role}_id"
    g = raw.groupby([key, "date"])["is_win"].sum().reset_index().sort_values([key, "date"])
    g["win_day"] = g["date"].where(g["is_win"] > 0)
    g["lw"] = g.groupby(key)["win_day"].transform(lambda s: s.shift(1).ffill())
    m = raw[["entry_id", key, "date"]].merge(g[[key, "date", "lw"]], on=[key, "date"], how="left")
    SOD[f"days_since_{role}_last_win"] = dict(zip(m["entry_id"], (m["date"] - m["lw"]).dt.days.astype(float)))

ent = pd.read_sql_query(f"""SELECT e.id AS entry_id, e.race_id, e.program_num, e.trainer_id, e.official_finish_pos AS off,
       e.final_odds, e.non_betting, e.win_payout, e.place_payout, e.show_payout, e.last_raced_raw, h.name AS horse
    FROM entries e LEFT JOIN horses h ON h.id=e.horse_id WHERE e.race_id IN ({','.join(str(x[3]) for x in oos)})""", c)
rinfo = {r[0]: r[1:] for r in c.execute(f"SELECT id, race_type, field_size FROM races WHERE id IN ({','.join(str(x[3]) for x in oos)})")}
DBTRACKS = {r[0] for r in c.execute("SELECT code FROM tracks")}
c.close()
LR = re.compile(r"^(\d{1,2})([A-Z][a-z]{2})(\d{2})(\d{1,2})([A-Z]+)")

rows, pit = [], {"rows": 0, "jockey_changed": 0, "trainer_changed": 0, "trainer_same_race_leak": 0}
for track, date, rn, rid in oos:
    card = load_race_from_db(model, DB, race_id=rid)
    f = card.frame
    e = ent[ent.race_id == rid].set_index("entry_id")
    # same-race stablemate leak in the stored value: NULL stored, start-of-day value exists,
    # and a stablemate (same trainer) won THIS race
    winners_tr = set(e.loc[e["off"] == 1, "trainer_id"])
    for col in SOD:
        new = f["entry_id"].map(SOD[col]).astype(float)
        old = f[col].astype(float)
        ch = ~((old.isna() & new.isna()) | np.isclose(old.fillna(-9), new.fillna(-9)))
        pit[col.split("_")[2] + "_changed"] += int(ch.sum())
        if col.endswith("trainer_last_win"):
            pit["trainer_same_race_leak"] += int((ch & old.isna() & f["entry_id"].map(e["trainer_id"]).isin(winners_tr)
                                                  & (f["entry_id"].map(e["off"]) != 1)).sum())
        f[col] = new.to_numpy()
    pit["rows"] += len(f)
    X = model.preprocessor.transform(f)
    p_f = np.asarray(model.fundamental.predict_probabilities(X), dtype=float)
    rr = rerank_probabilities(card, p_f, str(DB), track, date, rn)
    p = np.asarray(rr.p_adjusted, dtype=float)
    pn = normalise_itm(p)
    pw, _ = invert_harville(pn)
    for i, eid in enumerate(f["entry_id"]):
        x = e.loc[eid]
        m = LR.match(x.last_raced_raw or "")
        lr_track = m.group(5) if m else ("FTS" if (x.last_raced_raw or "").strip().startswith("---") else "UNK")
        rows.append(dict(track=track, race_date=date, race_num=rn, race_id=rid, entry_id=int(eid), pgm=str(x.program_num),
                         horse=x.horse, race_type=rinfo[rid][0], field=len(f), p_fund=p_f[i], p_itm=p[i], p_itm_norm=pn[i],
                         p_win=pw[i], n_pp=rr[4], odds=x.final_odds, non_betting=x.non_betting, off=x["off"],
                         win_pay=x.win_payout, place_pay=x.place_payout, show_pay=x.show_payout,
                         lr_track=lr_track, no_data_shipper=int(m is not None and lr_track not in DBTRACKS)))
df = pd.DataFrame(rows)
df.to_csv(HERE / "rerun_rows.csv", index=False)
json.dump(pit, open(HERE / "pit.json", "w"), indent=1)
print(pit, len(df), df.race_id.nunique())
