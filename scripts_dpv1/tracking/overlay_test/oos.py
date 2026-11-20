import sqlite3, sys, os
os.chdir(sys.argv[1])  # scratch work dir
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
S=r"D:\Benter Model_v2 Data\benter-model_v2-data\scripts_dpv1\_stretch\racing_s.db"
L=r"D:\Benter Model_v2 Data\benter-model_v2-data\scripts\racing_full.db"
Q="""select t.code, rd.race_date, r.race_num, r.id from races r join race_days rd on rd.id=r.race_day_id join tracks t on t.id=rd.track_id
   where exists(select 1 from entries e where e.race_id=r.id and e.official_finish_pos is not null)"""
s={(a,b,c) for a,b,c,_ in sqlite3.connect(f"file:{S}?mode=ro",uri=True).execute(Q)}
L_=sqlite3.connect(f"file:{L}?mode=ro",uri=True)
live=list(L_.execute(Q))
oos=[x for x in live if x[:3] not in s]
by=defaultdict(list)
for t,d,n,i in oos: by[t].append(d)
for t,v in sorted(by.items()):
    dd=Counter(v); print(t, len(v), "races", len(dd), "days", min(v), max(v))
    # month summary
    print("   ", sorted(Counter(x[:7] for x in v).items()))
# feature rows present?
ids=[i for *_,i in oos]
have=set(r[0] for r in L_.execute(f"select distinct e.race_id from entries e join entry_features_dpv1 f on f.entry_id=e.id where e.race_id in ({','.join(map(str,ids))})"))
print("feature rows present for", len(have), "of", len(ids))
# training-snapshot races missing from live? 
print("in snapshot not in live:", len(s-{x[:3] for x in live}))
import json; json.dump(oos, open("oos.json","w"))
print("tracks table:", [r for r in L_.execute("select code from tracks")])
