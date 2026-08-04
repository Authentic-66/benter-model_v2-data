# Phase 4B.1 — Feature-Builder Bug Fix: Impact on v2 / v2a / v10

**Date:** 2026-07-31
**Fixes:** `scripts/feature_builder.py` row-order contract
**Rebuilt:** `entry_features_v1` (GP-only, 116,311 entries), `entry_v10_flags`
**Retrained:** `benter_v2_rebuilt.pkl`, `benter_v2_v10_rebuilt.pkl`, `benter_v2a_rebuilt.pkl`
**Originals preserved:** `benter_v2_phase3e.pkl`, `benter_v2_v10.pkl`, `benter_v2a.pkl`, `benter_v2.pkl`

---

## TL;DR

The bug was **real and severe at the feature level** — 26 features were
effectively randomised, with a median old/new correlation of **−0.01**. It was
**almost irrelevant at the model level**: v2's log-loss moved by 0.0001 and
v2a's trifecta ROI by 0.06pp.

That combination is not a contradiction, and the reason matters more than
either number. A direct test (§5) shows the corrected features made the
fundamental model **a better standalone predictor** (log-loss 1.9224 → 1.8653)
while making it **much more collinear with the market** (corr 0.537 → 0.697).
The features the bug destroyed — trainer and jockey strike rates, career
records, at-track form — are precisely the ones the betting crowd already
prices. Fixing them made the model agree with the tote board more, not beat it.

**Phase 3E's "market is efficient / α ≈ 0" conclusion survives, and is
strengthened.** Phase 3F's "v10 marginally helps" conclusion **does not
survive** — on corrected features v10 is neutral-to-slightly-negative and α
turns negative. Phase 3G's ITM model is essentially unchanged and its shipping
verdict is unaffected.

No shipping decision changes. One published conclusion is retracted.

---

## 1. The fix

`_prior_by_entity_expanding`, `_prior_by_entity_windowed`, `_prior_last_value`
and `_prior_days_to_event` sorted internally by `(entity, race_date, entry_id)`
and **returned rows in that sorted order**. Several call sites assigned the
result straight onto an entry-ordered frame:

```python
rolled = _prior_by_entity_expanding(df_w, "horse_id", ["one"], "horse")
out["career_starts"] = rolled["horse_one"]      # positional, not keyed
```

The fix restores the caller's row order before returning, in one shared helper
(`_restore_input_order`) applied to all four functions. This was chosen over
patching the five call sites individually because it makes **both** access
patterns correct — callers that merge on `entry_id` are unaffected, callers
that assign positionally now get the right answer — and it cannot be
reintroduced by a new call site written in the old style.

### Verification against SQL ground truth

`career_starts` compared to a correlated-subquery count of prior starts:

| | Match rate |
|---|---:|
| Before fix | **9.8%** |
| After fix | **100.0%** |

9.8% is chance. Test: `scripts/test_feature_builder_alignment.py`.

### Regression test

`test_feature_builder_alignment.py` — 10 checks, all passing:

* the exact broken pattern (positional assignment) now lands on the right entries
* returned `entry_id` order equals input order, for all four helpers
* merge-on-`entry_id` and positional access agree
* results are invariant to the caller's row order (shuffled-input test)
* correct when the caller passes a non-default DataFrame index
* SQL ground-truth check (opt-in via `--db`)

One test **documents a separate defect rather than fixing it**:
`_prior_last_value` inspects only the immediately-preceding row, so a horse
with two entries on the *same date* gets NULL instead of falling back to its
last strictly-earlier start. Measured frequency: **0 of 116,311 entries in
`gp_full.db` and 0 of 207,976 in `racing_full.db`** — it never fires. Changing
it would have altered feature values beyond the alignment fix and contaminated
this report's before/after measurement, so the current behaviour is pinned by a
test instead.

---

## 2. Feature-level impact

`entry_features_v1` rebuilt on `scripts/gp_full.db`; the pre-fix table was
snapshotted to `entry_features_v1_prefix` and diffed row by row on `entry_id`.
Tool: `scripts/diff_prefix_postfix.py`.

**26 of 77 columns changed. 51 were identical.**

| Feature | Rows changed | corr(old, new) | MAD / σ |
|---|---:|---:|---:|
| `jockey_at_track_winrate_shrunk` | 99.98% | −0.004 | 1.130 |
| `jockey_at_distance_winrate_shrunk` | 99.98% | −0.011 | 1.130 |
| `jockey_365d_winrate_shrunk` | 99.96% | −0.017 | 1.138 |
| `trainer_at_track_winrate_shrunk` | 99.96% | −0.011 | 1.133 |
| `jockey_90d_winrate_shrunk` | 99.93% | −0.003 | 1.131 |
| `trainer_at_distance_winrate_shrunk` | 99.92% | −0.003 | 1.122 |
| `jockey_at_surface_winrate_shrunk` | 99.91% | −0.001 | 1.126 |
| `trainer_365d_winrate_shrunk` | 99.89% | −0.013 | 1.136 |
| `jockey_30d_winrate_shrunk` | 99.81% | −0.004 | 1.126 |
| `trainer_at_surface_winrate_shrunk` | 99.69% | −0.014 | 1.120 |
| `trainer_90d_winrate_shrunk` | 99.58% | −0.008 | 1.104 |
| `trainer_recent_form_trend` | 99.26% | −0.005 | 1.101 |
| `jockey_starts_30d` | 99.18% | +0.024 | 1.120 |
| `trainer_30d_winrate_shrunk` | 98.39% | −0.005 | 1.076 |
| `trainer_jockey_combo_winrate_shrunk` | 97.05% | −0.013 | 1.051 |
| `trainer_starts_30d` | 96.67% | −0.019 | 0.994 |
| `trainer_jockey_combo_starts` | 96.46% | −0.039 | 0.571 |
| `career_itm_pct_shrunk` | 94.32% | +0.001 | 1.114 |
| `career_win_pct_shrunk` | 93.08% | +0.003 | 1.052 |
| **`career_starts`** (rank 1) | 90.81% | −0.013 | 0.979 |
| **`starts_at_track`** (rank 1) | 90.81% | −0.013 | 0.979 |
| `historical_surface_winrate_shrunk` | 86.96% | −0.004 | 1.035 |
| `historical_condition_winrate_shrunk` | 85.93% | −0.001 | 1.042 |
| **`career_wins`** (rank 1) | 58.83% | −0.012 | 0.874 |
| **`wins_at_track`** (rank 1) | 58.83% | −0.012 | 0.874 |
| `is_first_time_combo` | 23.62% | −0.022 | 0.695 |

**Median old/new correlation: −0.0095.** The pre-fix values were not
*approximately* right — they carried no information about the correct values at
all. Mean absolute error was larger than each feature's own standard deviation
(MAD/σ ≈ 1.1), which is what you get from randomly permuting a column.

Unchanged, as predicted: everything derived via `_prior_last_value` in a
merge-on-`entry_id` call site (all `last_race_*`, weight and distance deltas,
gate break), all row-local features, all market features, and the track-bias
features.

> **Correction to an earlier count.** My Phase 4B report estimated "~24
> features". The measured figure is 26. An initial run of the diff also
> reported 30, but four of those (`horse_sex`, `horse_country_origin`,
> `pace_type_last_race`, `race_type`) were an artifact of comparing NULLs as
> strings — each showed a "change" exactly equal to its null rate. The diff
> tool now treats NULL == NULL as unchanged.

---

## 3. Model-level impact

All three models retrained with the **same grids** Phase 3E/3F/3G used
(5 half-lives × 4 L2 values × 4 rolling-origin folds = 80 fits each), selected
by the same rule (best mean log-loss across folds). Tool:
`scripts/compare_grids.py`.

### 3.1 v2 — win target, no v10 (vs Phase 3E)

| Metric | Phase 3E (buggy) | Phase 4B.1 (fixed) | Δ |
|---|---:|---:|---:|
| log-loss | 1.6474 | **1.6473** | −0.0001 |
| top-1 hit rate | 35.94% | **36.28%** | +0.34pp |
| top-3 hit rate | 72.84% | 73.02% | +0.18pp |
| ECE | 0.0055 | 0.0066 | +0.0011 |
| α (fundamental) | −0.0003 | **−0.0339** | −0.0336 |
| β (market) | 1.0636 | 1.0799 | +0.0164 |
| Best half-life / L2 | 3.0y / 0.01 | 3.0y / 0.1 | — |

Ship criteria, re-assessed on corrected features:

| Criterion | Phase 3E | Phase 4B.1 | Status |
|---|---:|---:|---|
| Log-loss ≤ 1.6494 | 1.6474 | 1.6473 | ✅ PASS (unchanged) |
| ROI @ edge 0.4 > 0 | n/a — no bets | n/a — no bets | ❌ FAIL (unchanged) |
| ECE < 3% | 0.0055 | 0.0066 | ✅ PASS (unchanged) |
| Top-1 > 36.4% | 35.9% | 36.3% | ❌ FAIL (closer, still short) |

**Verdict: Phase 3E's conclusions hold.** Top-1 improved by a third of a point
and now sits 0.12pp under the market-favourite bar instead of 0.46pp under —
a real but immaterial improvement that does not change the recommendation. α
moved *further from* zero in the negative direction, which strengthens rather
than weakens the "no independent signal" reading.

### 3.2 v2 + v10 priors (vs Phase 3F)

| Metric | Phase 3F (buggy) | Phase 4B.1 (fixed) | Δ |
|---|---:|---:|---:|
| log-loss | 1.6471 | 1.6475 | +0.0003 |
| top-1 hit rate | 36.03% | 36.29% | +0.26pp |
| ECE | 0.0053 | 0.0065 | +0.0012 |
| **α (fundamental)** | **+0.0291** | **−0.0256** | **−0.0547** |
| β (market) | 1.0547 | 1.0761 | +0.0214 |

And the question Phase 3F actually asked — *does adding v10 help?* — re-run on
corrected features:

| Metric | 4B.1 without v10 | 4B.1 with v10 | Δ |
|---|---:|---:|---:|
| log-loss | **1.6473** | 1.6475 | **+0.0002 (worse)** |
| top-1 hit rate | 36.28% | 36.29% | +0.01pp |
| top-3 hit rate | 73.02% | 72.91% | −0.11pp |
| α | −0.0339 | −0.0256 | +0.0082 |

**Verdict: Phase 3F's headline conclusion does not survive the fix.**

Phase 3F's central claim was that α rising from 0.001 to 0.034 — "a +3320%
relative shift" — was "the most tangible signal that v10 features are
informative". On corrected features α is **negative** both with and without
v10, and adding v10 makes log-loss marginally *worse*. The α movement Phase 3F
measured was an artifact of the blend reallocating weight in the presence of
scrambled inputs, not evidence that v10 carries signal.

The honest restatement: **v10 priors are neutral.** Doug's decision matrix
outcome moves from *Category B (marginally helps)* to *Category A/C (no
measurable help)*.

### 3.3 v2a — ITM target, 2022+ (vs Phase 3G)

Grid metrics (mean across folds, each at its own best combo):

| Metric | Phase 3G (buggy) | Phase 4B.1 (fixed) | Δ |
|---|---:|---:|---:|
| log-loss | 1.8562 | 1.8569 | +0.0007 |
| ITM hit rate top-3 | 98.22% | 98.01% | −0.21pp |
| ITM hit rate top-4 | 99.53% | 99.54% | +0.01pp |
| ITM precision top-3 | 61.26% | 61.37% | +0.10pp |
| **α (fundamental)** | **+0.1715** | **+0.0729** | **−0.0986** |
| β (market) | 0.7563 | 0.7742 | +0.0178 |
| γ (intercept) | −0.0188 | −0.0492 | −0.0305 |

Downstream / shipping-relevant metrics, both models re-scored over identical
val folds (`scripts_v2a/compare_v2a_downstream.py`):

| Metric | Pre-fix model | Post-fix model | Δ |
|---|---:|---:|---:|
| ITM hit rate top-3 | 97.57% | 97.55% | −0.02pp |
| ITM precision top-3 | 61.25% | 61.24% | −0.01pp |
| Full sweep top-3 | 15.73% | 15.71% | −0.02pp |
| Longshots flagged | 23 | 25 | +2 |
| Longshot precision | 26.09% | 24.00% | −2.09pp |
| Trifecta box ROI | −23.61% | −23.67% | −0.06pp |

**Verdict: Phase 3G is unaffected in every respect that matters.** The ITM
model's selection quality, its trifecta economics, and its "do not ship on
trifecta ROI" verdict are all unchanged. The one substantive movement is α,
which more than halved — same pattern as v2.

Longshot precision moved 2pp, but on 23→25 flagged entries; that is one
horse's worth of noise and should not be read as a change.

---

## 4. v10 flag rebuild

`apply_v10_priors.py` derives its *leading jockey* proxy from
`entry_features_v1.jockey_starts_30d` — one of the scrambled columns (99.18% of
rows wrong). So the v10 flags were affected too, and were regenerated.

| Flag | Pre-fix entries | Post-fix entries | Δ |
|---|---:|---:|---:|
| `v10_sire_bet` | 810 | 810 | 0 |
| `v10_sire_fade` | 0 | 0 | 0 |
| `v10_trainer_bet` | 4,415 | 4,415 | 0 |
| `v10_trainer_fade` | 1,840 | 1,840 | 0 |
| `v10_jockey_bet` | 0 | 0 | 0 |
| `v10_jockey_fade` | 1,187 | 1,187 | 0 |
| **`v10_universal_fade`** | **6,725** | **10,907** | **+4,182** |
| any signal fired | 14,467 (12.4%) | 18,054 (15.5%) | +3,587 |

Only `universal_fade` moved — it is the only category that consumes the
leading-jockey proxy. `v10_signal_score` changed on 16,398 entries.
**The coverage table published in Phase 3F is wrong for that row.**

Signal quality, recomputed with Phase 3F's own bucket thresholds:

| Bucket | n (3F) | win rate (3F) | avg implied (3F) | n (4B.1) | win rate (4B.1) | avg implied (4B.1) |
|---|---:|---:|---:|---:|---:|---:|
| `strong_bet` | 19 | 21.05% | 34.95% | 15 | 26.67% | 39.40% |
| `weak_bet` | 4,889 | 23.42% | 25.92% | 4,352 | 23.09% | 25.08% |
| `neutral` | 101,844 | 12.17% | 14.99% | 97,698 | 11.63% | 14.30% |
| `weak_fade` | 3,117 | 14.24% | 17.44% | 3,535 | 15.62% | 19.32% |
| `strong_fade` | 6,442 | 10.62% | 14.51% | 10,033 | 17.42% | 21.66% |

`strong_fade`'s absolute win rate jumps from 10.6% to 17.4%, which looks at
first like the fade signal inverting. It hasn't — the bucket's *population*
changed. It now includes ~4,000 additional leading-jockey mounts, which are
better horses (market-implied 21.7% vs 14.5% before). Measured the way that
matters, against the price rather than against zero, the fade is intact and
marginally stronger: **−3.9pp vs the market before, −4.2pp after.**

Phase 3F's qualitative reading — "the market has already priced most of the
signal" — still stands and is in fact the same story §5 tells.

---

## 5. Why did α *fall* when the features were corrected?

This is the counterintuitive result in the whole phase: on every model, fixing
the features **reduced** the fundamental's blend weight. v2a's α more than
halved. Correct inputs should be worth more, not less.

Two explanations make opposite, testable predictions:

* **(A)** the corrected features are simply worse predictors
* **(B)** they are *better* predictors of exactly what the market already
  prices, so the fundamental becomes collinear with the market and the blend
  can reach the same fit with less weight on it

Tested directly (`scripts/diagnose_alpha_shift.py`), training on pre-2025 and
validating on 2025+ (21,693 val entries), same hyperparameters both sides:

| Quantity | Pre-fix | Post-fix | Δ |
|---|---:|---:|---:|
| Fundamental standalone log-loss | 1.9224 | **1.8653** | **−0.0571 (better)** |
| corr(logit p_fundamental, logit p_market) | 0.5371 | **0.6966** | **+0.1594** |
| α | −0.0242 | −0.0666 | −0.0425 |
| β | 1.0738 | 1.1004 | +0.0266 |
| *(market log-loss, reference)* | 1.6493 | — | — |

**Explanation (B), unambiguously.** The corrected fundamental is a
substantially better standalone predictor — 0.057 of log-loss, far larger than
any blended-model movement in §3 — and it moved decisively toward the market.

The interpretation matters for Phase 4C. Trainer strike rate, jockey strike
rate, career record, at-track form: these are the first things a handicapper
looks at, which means they are the first things the crowd bets on, which means
they are already in the price. Repairing them made the model a better
*handicapper* and no better a *bettor*.

This is the strongest evidence the project has produced for the Phase 3E
thesis. Phase 3E concluded the feature set "collectively duplicates what the
market already knows" — but it reached that conclusion with features that were
mostly noise, so the conclusion was right for the wrong reason. It now rests
on a correct measurement.

---

## 6. Did anything get better?

Honest accounting of what the fix bought:

**Real gains**
* The fundamental model is genuinely better in isolation (−0.057 log-loss).
* v2 top-1 hit rate +0.34pp; v2a top-3 precision +0.10pp.
* `entry_features_v1` is now correct, so any future model built on it —
  including anything reusing this pipeline — starts from honest inputs.
* One published conclusion (Phase 3F) has been corrected rather than carried
  forward into Phase 4C as a false premise.

**No change**
* Every ship criterion, on all three models, has the same pass/fail status.
* v2a's trifecta ROI, the most decision-relevant number in the project, moved
  0.06pp.
* Hyperparameters remain almost irrelevant — the whole grid still lands within
  0.0002 log-loss.

**Got worse (or was revealed as never having been there)**
* Phase 3F's "v10 marginally helps" finding is withdrawn.
* α is now negative on the win-target models, i.e. the blend would prefer a
  *small negative* weight on the fundamental — consistent with "no signal", not
  with "some signal".

**Why the model-level movement is so small.** The 26 broken features were
scrambled, so the fundamental model correctly learned to put near-zero weight
on them; the ~45 correct features (last-race form, odds, post, weight) carried
the model in both versions. A model that has correctly ignored its bad inputs
does not change much when those inputs are repaired — it just stops ignoring
them, and then discovers they say what the market already said.

---

## 7. What this does and does not license

**Does:**
* Phase 4C can use v2/v2a as an honest baseline. Use `*_rebuilt.pkl` for any
  DPv1 comparison; the originals are kept only for reproducing the historical
  reports.
* DPv1's Phase 4B numbers stand — `aggregate_features.py` was written
  independently with merge-on-`entry_id` throughout and never had this bug.

**Does not:**
* This does not revive v2 or v2a as shippable. Nothing crossed a ship
  criterion.
* This does not validate v10 priors. They should be treated as unproven going
  into Phase 4D, not as a known-positive.

---

## 8. Recommendations

1. **Update the project conclusion on v10.** Phase 3F's Category B verdict is
   withdrawn; treat v10 priors as unproven. This matters for Phase 4D, which
   was scoped on the premise that v10 adds signal.
2. **Do not chase the win target further.** Two independent measurements now
   say the fundamental feature set is market-redundant, and the second one was
   taken with correct features. DPv1's ITM focus is the right call.
3. **Judge DPv1 features by what the market *doesn't* price.** The features
   that repaid the fix least were the crowd-visible ones. The DPv1 additions
   most likely to carry independent signal on that logic are the cross-track
   features (§9 of the Phase 4B report), which no tote board at GP/CT/MNR
   prices directly, and the trip/trouble taxonomy.
4. **Add `corr(logit p_f, logit p_m)` to the standard Phase 4C metric bundle.**
   It diagnosed in one number what log-loss could not show at all, and it is
   the right early-warning metric for "this feature set is just re-deriving the
   price".
5. **Run `test_feature_builder_alignment.py` in CI**, or at least before any
   future feature rebuild. This bug survived a full validation phase, two model
   builds and three reports without being caught, because every downstream
   check was self-consistent.

---

## 9. Files

**Modified**
```
scripts/feature_builder.py          row-order contract + _restore_input_order
scripts/PHASE_3C_FEATURES.md        regenerated on corrected features
```

**Added**
```
scripts/test_feature_builder_alignment.py   10-check regression suite
scripts/diff_prefix_postfix.py              per-feature before/after diff
scripts/compare_grids.py                    grid-search head-to-head
scripts/diagnose_alpha_shift.py             the (A)-vs-(B) test in §5
scripts/phase4b1_feature_diff.csv           machine-readable feature diff
scripts/PHASE_4B1_BUG_FIX_IMPACT.md         this report
scripts_v2a/compare_v2a_downstream.py       ITM/trifecta/longshot comparison
```

**New artifacts** (originals untouched)
```
scripts/benter_v2_rebuilt.pkl               v2, no v10   — vs Phase 3E
scripts/benter_v2_grid_rebuilt.csv
scripts/benter_v2_v10_rebuilt.pkl           v2 + v10     — vs Phase 3F
scripts/benter_v2_grid_v10_rebuilt.csv
scripts_v2a/benter_v2a_rebuilt.pkl          v2a ITM      — vs Phase 3G
scripts_v2a/benter_v2a_grid_rebuilt.csv
```

**Preserved for reference**
```
scripts/benter_v2.pkl, benter_v2_phase3e.pkl, benter_v2_v10.pkl
scripts_v2a/benter_v2a.pkl
scripts/PHASE_3C_FEATURES_prefix.md         pre-fix version of the 3C report
gp_full.db : entry_features_v1_prefix       pre-fix feature snapshot
gp_full.db : entry_v10_flags_prefix         pre-fix v10 flag snapshot
```

**Working file:** `scripts/gp_full_no_v10.db` — a copy of `gp_full.db` with
`entry_v10_flags` dropped. `prepare_training.load_full_frame` auto-joins that
table when it exists, so replicating the Phase 3E (no-v10) baseline required a
database where it does not. Safe to delete once Phase 4C is done.

---

## 10. Reproducing

```bash
python scripts/test_feature_builder_alignment.py --db scripts/gp_full.db
python scripts/feature_builder.py build --db scripts/gp_full.db --config scripts/feature_config.json
python scripts/diff_prefix_postfix.py --db scripts/gp_full.db
python scripts/apply_v10_priors.py --db scripts/gp_full.db --signals scripts/v10_iron_rules_extracted.json
python scripts/train_benter_v2.py  --db scripts/gp_full_no_v10.db --model-out scripts/benter_v2_rebuilt.pkl     --results-out scripts/benter_v2_grid_rebuilt.csv
python scripts/train_benter_v2.py  --db scripts/gp_full.db        --model-out scripts/benter_v2_v10_rebuilt.pkl --results-out scripts/benter_v2_grid_v10_rebuilt.csv
python scripts_v2a/train_benter_v2a.py --db scripts/gp_full.db    --model-out scripts_v2a/benter_v2a_rebuilt.pkl --results-out scripts_v2a/benter_v2a_grid_rebuilt.csv
python scripts/diagnose_alpha_shift.py --db scripts/gp_full.db
python scripts_v2a/compare_v2a_downstream.py
```
