import json, re, pickle, sys
import pandas as pd, numpy as np
from pathlib import Path
D = Path(r"D:\Benter Model_v2 Data\benter-model_v2-data\scripts_dpv1")
sys.path[:0] = [str(D), str(D.parent / "scripts"), str(D.parent / "scripts_v2a")]
from pathlib import Path
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
m = pickle.load(open(D / "dpv1_20260919_040326_retired.pkl", "rb")); k = "purse_change_from_last"
coef, mu, sd = m.coefficients[k], m.preprocessor.means[k], m.preprocessor.stds[k]
sc = [json.loads(l) for l in open(D / "logs/scored_predictions.jsonl")]
sc = [r for r in sc if r["track"] == "DED" and r["model_version"] == "dpv1.3.0-5track"]
files = sorted({r["picks_file"] for r in sc})
byk = {(r["race_date"], int(r["race_num"]), str(r["pgm"])): r for r in sc}
rows, allh = [], 0
for f in files:
    txt = (D / f).read_text(encoding="utf-8")
    date = re.search(r"DED_(\d{4}-\d{2}-\d{2})", f).group(1)
    race = horse = None; reasons = {}
    for ln in txt.splitlines():
        mr = re.match(r"--- Race (\d+)", ln)
        if mr: race = int(mr.group(1)); continue
        mh = re.match(r"\s+(\d+)\s+(\S+)\s+(.+?)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+)\s", ln)
        if mh and race:
            horse = (date, race, mh.group(2)); reasons[horse] = []; continue
        ma = re.match(r"\s+([↑↓])\s+(.+?)\s+([+-]\d+\.\d+)\s*$", ln)
        if ma and horse:
            reasons[horse].append((ma.group(2).strip(), float(ma.group(3))))
    for h, rs in reasons.items():
        r = byk.get(h)
        if r is None: continue          # not in the scored record run (scratched, other run)
        allh += 1
        neg = [x for x in rs if x[1] < 0]
        if neg and min(neg, key=lambda x: x[1])[0] == "purse change vs last":
            c = min(neg, key=lambda x: x[1])[1]
            rows.append(dict(date=h[0], R=h[1], pgm=h[2], horse=r["horse_name"], rank=r["rank"], n=r["n_horses_in_race"],
                             p_itm=r["final_p_itm"], base=r["base_p_itm"], contrib=c,                              fin=r["actual_finish"], itm=r["hit_itm"], odds=r.get("final_odds")))
# a card with two logged runs (DED 10/10) lists each horse twice: keep one row per horse
t = pd.DataFrame(rows).sort_values(["date", "R"]).drop_duplicates(["date", "R", "pgm"])
pd.set_option("display.width", 220)
print(f"DED record runs scored: {len(files)} cards, {allh} scored horses; purse change is the largest negative reason for {len(t)}")
print(t.to_string(index=False))
print(f"\nITM {t.itm.sum()}/{len(t)} = {t.itm.mean():.3f}; mean P(ITM) {t.p_itm.mean():.3f}; mean base {t.base.mean():.3f}; diff {100*(t.itm.mean()-t.p_itm.mean()):+.1f}pp")
print("wins", (t.fin == 1).sum()); import math; p = t.p_itm.values; print("z (independent Bernoulli)", round((t.itm.sum() - p.sum()) / math.sqrt((p * (1 - p)).sum()), 2))
sc_df = pd.DataFrame(sc).drop_duplicates(["race_date", "race_num", "pgm"]); print("all DED scored horses: ITM", round(sc_df.hit_itm.mean(), 3), "mean P(ITM)", round(sc_df.final_p_itm.mean(), 3))
t.to_csv(OUT / "ded_purse_neg.csv", index=False)
