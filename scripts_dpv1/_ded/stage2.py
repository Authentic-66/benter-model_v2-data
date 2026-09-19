"""Stage 2 diagnostics: DED vs existing tracks, feature NULL rates and distributions (2022+)."""
import sys, sqlite3, json
import numpy as np, pandas as pd
sys.path.insert(0, '.')
from dpv1_runtime import load_model
LIVE = set(load_model('dpv1.pkl').fund_cols)
cfg = json.load(open('dpv1_feature_config.json', encoding='utf-8'))
ACTIVE = {k for k, v in cfg['features'].items() if v.get('active')}
c = sqlite3.connect('_ded/racing_ded.db')
f = pd.read_sql("""select f.*, t.code track from entry_features_dpv1 f join entries e on e.id=f.entry_id join races r on r.id=e.race_id
                   join race_days rd on rd.id=r.race_day_id join tracks t on t.id=rd.track_id
                   where rd.race_date >= '2022-01-01' and e.finish_status='finished'""", c)
ID = {'entry_id','race_id','horse_id','trainer_id','jockey_id','race_date','track_id','track'}
feats = [x for x in f.columns if x not in ID]
ded, oth = f[f.track=='DED'], f[f.track!='DED']
print(f"rows 2022+ finished: DED {len(ded):,}  existing {len(oth):,}  | features {len(feats)} (live model uses {len(LIVE)})")

# ---- NULL rates
nr = pd.DataFrame({t: g[feats].isna().mean()*100 for t, g in f.groupby('track')})
nr['existing_avg'] = nr[['CT','ELP','GP','MNR']].mean(axis=1)
nr['DED_minus_avg_pp'] = nr['DED'] - nr['existing_avg']
nr['live'] = [x in LIVE for x in nr.index]
flag = nr[nr.DED_minus_avg_pp > 20].sort_values('DED_minus_avg_pp', ascending=False)
print("\nNULL RATE: features with DED > existing-avg + 20pp")
print(flag.round(1).to_string() if len(flag) else "  none")
mid = nr[(nr.DED_minus_avg_pp > 5) & (nr.DED_minus_avg_pp <= 20)].sort_values('DED_minus_avg_pp', ascending=False)
print("\nNULL RATE: DED 5-20pp higher (watch list)")
print(mid.round(1).to_string() if len(mid) else "  none")
low = nr[nr.DED_minus_avg_pp < -20].sort_values('DED_minus_avg_pp')
print("\nNULL RATE: DED >20pp LOWER than existing avg")
print(low.round(1).to_string() if len(low) else "  none")

# ---- distributions
num = [x for x in feats if pd.api.types.is_numeric_dtype(f[x])]
cat = [x for x in feats if x not in num]
rows = []
for x in num:
    a, b = ded[x].dropna().astype(float), oth[x].dropna().astype(float)
    if len(a) < 50 or len(b) < 50: continue
    sd = np.sqrt((a.var() + b.var()) / 2) or np.nan
    rows.append(dict(feature=x, live=x in LIVE, ded_mean=a.mean(), oth_mean=b.mean(), smd=(a.mean()-b.mean())/sd if sd else np.nan,
                     var_ratio=a.var()/b.var() if b.var() else np.nan,
                     ded_q=f"{a.quantile(.1):.3g}/{a.median():.3g}/{a.quantile(.9):.3g}", oth_q=f"{b.quantile(.1):.3g}/{b.median():.3g}/{b.quantile(.9):.3g}"))
D = pd.DataFrame(rows)
D['flag'] = (D.smd.abs() > 0.5) | (D.var_ratio > 2) | (D.var_ratio < 0.5)
print(f"\nNUMERIC DISTRIBUTIONS: {int(D.flag.sum())} of {len(D)} flagged (|SMD|>0.5 or variance ratio outside 0.5-2)")
print(D[D.flag].sort_values('smd', key=abs, ascending=False).round(3).to_string(index=False))
crow = []
for x in cat:
    p = ded[x].fillna('NULL').value_counts(normalize=True); q = oth[x].fillna('NULL').value_counts(normalize=True)
    k = p.index.union(q.index); tvd = 0.5*(p.reindex(k, fill_value=0) - q.reindex(k, fill_value=0)).abs().sum()
    top = ", ".join(f"{i}:{100*p.get(i,0):.0f}/{100*q.get(i,0):.0f}" for i in (p.reindex(k,fill_value=0)-q.reindex(k,fill_value=0)).abs().sort_values(ascending=False).index[:3])
    crow.append(dict(feature=x, live=x in LIVE, TVD=tvd, biggest_shifts_DED_vs_existing_pct=top))
C = pd.DataFrame(crow).sort_values('TVD', ascending=False)
print("\nCATEGORICAL DISTRIBUTIONS (total variation distance; >0.25 notable)")
print(C.round(3).to_string(index=False))
