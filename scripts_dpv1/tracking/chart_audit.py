# Read-only chart audit: races in DB per chart date vs races referenced by later charts' "Last Raced".
import sys, re, sqlite3, glob, os, datetime as dt, collections
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
REPO = r'D:/Benter Model_v2 Data/benter-model_v2-data'
OUT = sys.argv[1]
c = sqlite3.connect(f'file:{REPO}/scripts/racing_full.db?mode=ro', uri=True)
BS = chr(92)

files = [f for f in glob.glob(REPO + '/*/*/*.pdf') if re.search(r'results', os.path.dirname(f), re.I)]
MON = {m: i for i, m in enumerate(['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'], 1)}

def file_key(f):
    b = os.path.basename(f)
    m = re.match(r'([A-Z]{2,3})(\d{2})(\d{2})(\d{2})USA', b, re.I)
    if m: return m.group(1).upper(), f'20{m.group(4)}-{m.group(2)}-{m.group(3)}'
    m = re.match(r'(\d{4})(\d{2})(\d{2})-usa-([a-z]{2,3})-', b, re.I)
    if m: return m.group(4).upper(), f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    m = re.match(r'(\d{2})\.(\d{2})\.(\d{2}) ([A-Z]{2,3}) Results', b)
    if m: return m.group(4), f'20{m.group(3)}-{m.group(1)}-{m.group(2)}'
    m = re.match(r'([A-Z]{2,3}?)(\d{2})(\d{2})(\d{2})\.pdf$', b)
    if m: return m.group(1), f'20{m.group(4)}-{m.group(2)}-{m.group(3)}'
    return None, None

F = pd.DataFrame([(f, os.path.basename(f), *file_key(f)) for f in files], columns=['path', 'file', 'track', 'date'])
print('chart files on disk', len(F), 'unrecognised names', F.track.isna().sum())
for x in F[F.track.isna()].file: print('  unrecognised:', x)

pf = pd.read_sql('select id, source_pdf, races_found, races_loaded, success, error_message from parsed_files', c)
pf['file'] = pf.source_pdf.str.replace(BS, '/').map(os.path.basename)
pf = pf.sort_values('id').groupby('file').tail(1)
F = F.merge(pf[['file', 'races_found', 'races_loaded', 'success', 'error_message']], on='file', how='left')

R = pd.read_sql("select t.code track, d.race_date date, r.race_num, d.source_pdf from races r join race_days d on r.race_day_id=d.id join tracks t on d.track_id=t.id", c)
g = R.groupby(['track', 'date'])
D = pd.DataFrame({'db_races': g.race_num.nunique(), 'db_max': g.race_num.max(),
                  'db_nums': g.race_num.apply(lambda s: sorted(set(s)))}).reset_index()
src = g.source_pdf.first().reset_index()
src['src_file'] = src.source_pdf.str.replace(BS, '/').map(os.path.basename)
D = D.merge(src[['track', 'date', 'src_file']], on=['track', 'date'])

E = pd.read_sql("select last_raced_raw from entries where last_raced_raw is not null", c)
ref = collections.defaultdict(collections.Counter)
pat = re.compile(r'^(\d{1,2})([A-Za-z]{3})(\d{2})(\d{1,2})([A-Za-z]{2,4}?)(\d*)$')
for s in E.last_raced_raw:
    m = pat.match(s.strip())
    if not m or m.group(2).upper() not in MON: continue
    try: d = dt.date(2000 + int(m.group(3)), MON[m.group(2).upper()], int(m.group(1))).isoformat()
    except ValueError: continue
    ref[(m.group(5).upper(), d)][int(m.group(4))] += 1
Rf = pd.DataFrame([(k[0], k[1], max(v), dict(sorted(v.items()))) for k, v in ref.items()],
                  columns=['track', 'date', 'ref_max', 'ref_counts'])

A = F.merge(D, on=['track', 'date'], how='left').merge(Rf, on=['track', 'date'], how='left')
def missing(r):
    if not isinstance(r.ref_counts, dict): return {}
    have = set(r.db_nums) if isinstance(r.db_nums, list) else set()
    return {n: k for n, k in r.ref_counts.items() if n not in have}
A['ref_missing'] = A.apply(missing, axis=1)
A['flag_ref'] = A.ref_missing.map(len) > 0
A['flag_found'] = A.races_found.notna() & (A.races_found != A.races_loaded)
A['flag_nodb'] = A.db_races.isna()
A['flag_fail'] = A.success.fillna(-1) != 1

LOADED = {'CT', 'DED', 'ELP', 'EVD', 'FG', 'GP', 'LAD', 'MNR'}
A['loaded_track'] = A.track.isin(LOADED)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60); pd.set_option('display.max_rows', 500)
L = A[A.loaded_track]
print('\nfiles on loaded tracks', len(L), ' other tracks', (~A.loaded_track).sum(),
      A[~A.loaded_track].groupby('track').size().to_dict())

print('\n== A. Loaded, but later charts name races missing from the DB  (race: # later references) ==')
x = L[L.flag_ref & L.db_races.notna()].copy()
x['after_last'] = x.apply(lambda r: {n: k for n, k in r.ref_missing.items() if n > r.db_max}, axis=1)
x['inside_gap'] = x.apply(lambda r: {n: k for n, k in r.ref_missing.items() if n <= r.db_max}, axis=1)
x['db_nums_s'] = x.db_nums.map(lambda l: ','.join(map(str, l)))
print(x[['track', 'date', 'file', 'races_found', 'db_races', 'db_nums_s', 'ref_max', 'after_last', 'inside_gap']]
      .sort_values(['track', 'date']).to_string(index=False))

print('\n== B. Loaded tracks: file failed to parse / never parsed / no DB day ==')
y = L[(L.flag_fail | L.flag_nodb)]
print(y[['track', 'date', 'file', 'races_found', 'success', 'error_message', 'ref_max']].sort_values(['track', 'date']).to_string(index=False))

print('\n== C. races_found != races_loaded ==')
print(L[L.flag_found][['track', 'date', 'file', 'races_found', 'races_loaded', 'db_races']].to_string(index=False))

dup = F[F.track.isin(LOADED)].groupby(['track', 'date']).file.apply(list)
dup = dup[dup.map(len) > 1]
print('\n== D. same track/date has 2+ files on disk ==', len(dup)); print(dup.to_string())

mm = L[L.src_file.notna() & (L.src_file != L.file)]
print('\n== E. DB day loaded from a different file ==', len(mm))
print(mm[['track', 'date', 'file', 'src_file']].to_string(index=False))

# other tracks: summary only
O = A[~A.loaded_track & A.track.notna()]
print('\n== F. tracks never loaded: files / parsed rows ==')
print(O.groupby('track').agg(files=('file', 'size'), parsed=('success', lambda s: s.notna().sum())).to_string())
A.to_csv(OUT + '/chart_audit_all.csv', index=False)
