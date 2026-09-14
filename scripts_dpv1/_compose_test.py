"""Session 1: reranker composition test.

Config X = base dpv1.pkl alone
Config Y = base + pp-reranker-1.0          (current shipped state)
Config Z = base + pp-reranker-1.0 + classctx-reranker-0.1

Shipped artifacts, unmodified. The live application path is replicated: the PP
reranker fires ONLY on horses with a PP row; the class-context reranker fires
on the whole field (class context is near-universal), stacked on Y's logit.
"""
import sys, math
from math import comb
import numpy as np, pandas as pd
REPO='D:/Benter Model_v2 Data/benter-model_v2-data/'
sys.path.insert(0, REPO+'scripts_dpv1')
import dpv1_pp_reranker_train as PP
import dpv1_classctx_reranker_train as CC

pp_rr = PP.load_reranker()
cc_rr = CC.load_reranker()
print('pp  reranker: %s  mode=%s  %d features' % (pp_rr.version, pp_rr.mode, len(pp_rr.feature_names)))
print('cc  reranker: %s  mode=%s  %d features' % (cc_rr.version, cc_rr.mode, len(cc_rr.feature_names)))

pp_ds = PP.load_dataset()                      # PP-covered rows only
print('\nPP-covered rows %d, races %d' % (len(pp_ds), pp_ds.race_id.nunique()))
cc_ds = CC.load_dataset()                      # every row with base folds + class block
races = set(pp_ds.race_id.unique())
full = cc_ds[cc_ds.race_id.isin(races)].copy()
print('full fields of those races: %d rows, %d races' % (len(full), full.race_id.nunique()))
print('PP coverage within those races: %.1f%% of runners' % (100*len(pp_ds)/len(full)))

# ---- Config X ----
full['logit_X'] = full['base_logit']

# ---- Config Y: pp reranker on PP-covered horses only ----
Xpp, pp_names = PP.build_features(pp_ds, pp_rr.mode,
                                  pp_rr.training_notes.get('style_spec','explicit-na'),
                                  pp_rr.training_notes.get('impute'))
assert list(pp_names)==list(pp_rr.feature_names), (pp_names, pp_rr.feature_names)
pp_adj = pp_rr.adjust_logit(pp_ds['base_logit'].to_numpy(), Xpp.to_numpy())
pp_delta = pd.Series(pp_adj - pp_ds['base_logit'].to_numpy(), index=pp_ds.entry_id.to_numpy())
full['logit_Y'] = full['logit_X'] + full.entry_id.map(pp_delta).fillna(0.0)
print('\npp reranker applied to %d of %d runners; mean |delta| %.4f' % (
      full.entry_id.isin(pp_delta.index).sum(), len(full), pp_delta.abs().mean()))

# ---- Config Z: classctx reranker stacked on Y ----
fZ = full.copy(); fZ['base_logit'] = fZ['logit_Y']
Xcc, cc_names, _ = CC.build_features(fZ, cc_rr.mode, cc_rr.impute)
assert list(cc_names)==list(cc_rr.feature_names), (cc_names, cc_rr.feature_names)
full['logit_Z'] = cc_rr.adjust_logit(fZ['base_logit'].to_numpy(), Xcc.to_numpy())
# also: classctx on the RAW base, no pp reranker (isolates the two)
fW = full.copy(); fW['base_logit']=fW['logit_X']
Xw,_,_ = CC.build_features(fW, cc_rr.mode, cc_rr.impute)
full['logit_W'] = cc_rr.adjust_logit(fW['base_logit'].to_numpy(), Xw.to_numpy())
cc_d = full['logit_Z']-full['logit_Y']
print('cc reranker applied to %d runners; mean |delta| %.4f' % (len(full), cc_d.abs().mean()))

print('\nclass-context availability on these races:')
print('  class_context_missing=1: %.1f%% of runners (corpus-wide 39.6%%)' % (100*full.class_context_missing.mean()))
print('  ... among PP-covered runners: %.1f%%' % (100*full[full.entry_id.isin(pp_delta.index)].class_context_missing.mean()))

for c in ('X','Y','Z','W'):
    full['p_'+c] = 1/(1+np.exp(-full['logit_'+c]))

def top(d,c):
    t=d.sort_values(['race_id',c],ascending=[True,False]).groupby('race_id').head(1)
    return dict(zip(t.race_id,t.y_true.astype(bool)))
def mc(a,b):
    ids=sorted(set(a)&set(b)); g=sum(1 for r in ids if not a[r] and b[r]); l=sum(1 for r in ids if a[r] and not b[r])
    n=g+l;k=min(g,l)
    return g,l,(min(1.0,2*sum(comb(n,i) for i in range(k+1))/2**n) if n else 1.0)
def ll(y,p):
    p=np.clip(p,1e-9,1-1e-9); return -(y*np.log(p)+(1-y)*np.log(1-p))

maps={c:top(full,'p_'+c) for c in ('X','Y','Z','W')}
n=full.race_id.nunique()
print('\n=== TOP-PICK ITM on %d PP-eligible races ===' % n)
for c,lab in (('X','X  base alone'),('Y','Y  base + pp'),('Z','Z  base + pp + classctx'),('W','W  base + classctx only')):
    print('  %-28s %.3f%%  (%d/%d)' % (lab, 100*np.mean(list(maps[c].values())), sum(maps[c].values()), n))
print()
for a,b,lab in (('X','Y','Y vs X   (pp alone)'),('X','Z','Z vs X   (both)'),
                ('Y','Z','Z vs Y   (adding classctx)'),('X','W','W vs X   (classctx alone)'),
                ('W','Z','Z vs W   (adding pp)')):
    g,l,p=mc(maps[a],maps[b])
    d=100*(np.mean(list(maps[b].values()))-np.mean(list(maps[a].values())))
    print('  %-30s %+.3fpp   %d vs %d   McNemar p=%.4f' % (lab,d,g,l,p))

print('\n=== LOG-LOSS (all runners in those races, n=%d) ===' % len(full))
y=full.y_true.to_numpy()
base_ll=ll(y,full.p_X.to_numpy()).mean()
for c,lab in (('X','X  base alone'),('Y','Y  base + pp'),('Z','Z  base + pp + classctx'),('W','W  base + classctx only')):
    v=ll(y,full['p_'+c].to_numpy()).mean()
    print('  %-28s %.5f   delta vs X %+.5f' % (lab,v,v-base_ll))
def zdiff(a,b):
    d=ll(y,full['p_'+b].to_numpy())-ll(y,full['p_'+a].to_numpy())
    s=pd.Series(d).groupby(full.race_id.to_numpy()).sum()
    se=math.sqrt((s**2).sum())/len(full)
    return d.mean(), d.mean()/se if se else float('nan')
for a,b in (('X','Y'),('Y','Z'),('X','W'),('W','Z')):
    m_,z_=zdiff(a,b); print('  %s -> %s  log-loss delta %+.5f (z %+.2f)' % (a,b,m_,z_))

print('\n=== SUBSET CHECK: does adding classctx degrade the PP-covered horses? ===')
ppm = full.entry_id.isin(pp_delta.index)
for lab,sub in (('PP-covered runners', full[ppm]), ('non-PP runners in same races', full[~ppm])):
    yy=sub.y_true.to_numpy()
    print('  %-30s n %5d   X %.5f   Y %.5f   Z %.5f' % (
        lab,len(sub),ll(yy,sub.p_X).mean(),ll(yy,sub.p_Y).mean(),ll(yy,sub.p_Z).mean()))
    print('      residual pp:  X %+5.2f   Y %+5.2f   Z %+5.2f' % (
        100*(sub.y_true-sub.p_X).mean(),100*(sub.y_true-sub.p_Y).mean(),100*(sub.y_true-sub.p_Z).mean()))

print('\n=== do the two deltas correlate? (overlap diagnostic, PP-covered rows) ===')
sub=full[ppm]
d_pp=sub.entry_id.map(pp_delta).to_numpy()
d_cc=(sub.logit_Z-sub.logit_Y).to_numpy()
print('  corr(pp delta, classctx delta) = %+.3f  over %d rows' % (np.corrcoef(d_pp,d_cc)[0,1], len(sub)))
print('  mean pp delta %+.4f, mean classctx delta %+.4f' % (d_pp.mean(), d_cc.mean()))
print('  same-sign %.1f%%' % (100*np.mean(np.sign(d_pp)==np.sign(d_cc))))
