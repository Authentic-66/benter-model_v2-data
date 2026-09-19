import sqlite3, pandas as pd, numpy as np, re, sys
from datetime import datetime
sys.path.insert(0,'.')
from dpv1_runtime import load_model
LIVE=load_model('dpv1.pkl').fund_cols
new=sqlite3.connect('_ded/racing_ded.db'); old=sqlite3.connect('_ded/racing_ded_pre_la.db')
Q="""select f.*, t.code trk, e.last_raced_raw lr, e.horse_id hid, e.finish_status fs from entry_features_dpv1 f join entries e on e.id=f.entry_id
     join tracks t on t.id=f.track_id"""
A=pd.read_sql(Q,new).set_index('entry_id'); B=pd.read_sql(Q,old).set_index('entry_id')
B=B.loc[B.index.intersection(A.index)]; A2=A.loc[B.index]
# which DED rows had their previous start filled by the load
starts_old=pd.read_sql("select e.horse_id, rd.race_date, t.code from entries e join races r on r.id=e.race_id join race_days rd on rd.id=r.race_day_id join tracks t on t.id=rd.track_id", old)
starts_new=pd.read_sql("select e.horse_id, rd.race_date, t.code from entries e join races r on r.id=e.race_id join race_days rd on rd.id=r.race_day_id join tracks t on t.id=rd.track_id", new)
ko=set(map(tuple,starts_old.values)); kn=set(map(tuple,starts_new.values))
m=A2.lr.fillna('').str.extract(r'^(\d{1,2})([A-Za-z]{3})(\d{2})\d{1,2}([A-Z]{2,4})')
def dt(r):
    try: return datetime.strptime(f"{r[0]}{r[1]}{r[2]}","%d%b%y").strftime("%Y-%m-%d")
    except Exception: return None
pk=[(h,dt(r),r[3]) if isinstance(r[0],str) else None for h,r in zip(A2.hid,m.values)]
A2=A2.assign(filled=[k is not None and k not in ko and k in kn for k in pk], had=[k is not None and k in ko for k in pk])
sel=(A2.trk=='DED')&(A2.race_date>='2022-01-01')&(A2.fs=='finished')
groups={'DED prev start FILLED by load':sel&A2.filled,'DED prev start already in corpus':sel&A2.had}
print({k:int(v.sum()) for k,v in groups.items()})
KEY=['career_starts','career_wins','last_race_finish_pos','last_race_speed_figure','last_race_days_ago','days_since_last_race','last_3_avg_finish',
     'class_change_from_last','class_score_change_from_last','running_style_last_3','early_pace_position_projected','is_shipping_today','horse_shipping_starts',
     'trainer_365d_winrate_shrunk','jockey_365d_winrate_shrunk','trainer_home_track','jockey_home_track']
for name,s in groups.items():
    print(f"\n== {name} (n={int(s.sum()):,})")
    print(f"   {'feature':<34}{'null% before':>13}{'null% after':>12}{'mean before':>13}{'mean after':>12}")
    for c in KEY:
        b,a=B.loc[s[s].index,c],A2.loc[s,c]
        num=pd.api.types.is_numeric_dtype(a)
        mb=f"{pd.to_numeric(b,errors='coerce').mean():.3f}" if num else "-"; ma=f"{pd.to_numeric(a,errors='coerce').mean():.3f}" if num else "-"
        print(f"   {c:<34}{100*b.isna().mean():>12.1f}%{100*a.isna().mean():>11.1f}%{mb:>13}{ma:>12}")
# existing-track rows: how much moved
ex=A2.trk.isin(['GP','CT','MNR','ELP'])
ch={}
for c in LIVE:
    x,y=B.loc[ex[ex].index,c],A2.loc[ex,c]
    same=(x==y)|(x.isna()&y.isna())
    if pd.api.types.is_numeric_dtype(x): same=same|np.isclose(pd.to_numeric(x,errors='coerce'),pd.to_numeric(y,errors='coerce'),equal_nan=True)
    n=int((~same).sum())
    if n: ch[c]=n
print(f"\nEXISTING-TRACK rows ({int(ex.sum()):,}): live features changed by adding EVD/FG/LAD: {len(ch)} of {len(LIVE)}; top:")
for k,v in sorted(ch.items(),key=lambda kv:-kv[1])[:10]: print(f"   {k:<38}{v:>7,} ({100*v/ex.sum():.2f}%)")
print("\nno garbage: numeric |value|>1e12 in new table:", [c for c in A.columns if pd.api.types.is_numeric_dtype(A[c]) and (A[c].abs()>1e12).any()] or "none")
