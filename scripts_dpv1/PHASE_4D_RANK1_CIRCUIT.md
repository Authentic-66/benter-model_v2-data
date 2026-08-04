# Phase 4D — Rank-1 Features, CT/MNR Circuit: The Decisive Test

**Date:** 2026-07-31 · **Config:** `dpv1.2.0` · **Scope:** CT + MNR, 2022+, Doug's 19 rank-1 fundamental features
**Scored on:** 57,809 out-of-sample entries across 7,930 races (4 rolling-origin year folds)

---

## 1. Verdict

```
PHASE 4D SHIP CRITERIA — rank-1 features, CT+MNR
==================================================================
  FAIL  log-loss edge vs market >= 1.5%     =  0.9832 %
  PASS  corr(logit p_f, logit p_m) < 0.55   =  0.5483
  FAIL  longshot lift > 1.15x base ITM      =  0.3725
  FAIL  positive ROI on any exotic          = -0.1497   [exacta box, top 2]
------------------------------------------------------------------
  VERDICT: FAILED  (1 of 4, and that one is marginal)
==================================================================
```

**The project has reached its honest natural conclusion.** Recommendation:
**pause**. Details and the reasoning are below, but the single result that
matters is in §3 and it is not the criteria table.

---

## 2. Task 1 — pedigree: no fix exists, bucket marked unavailable

Confirmed before doing anything else, and Doug's mid-phase call to remove
rather than reconstruct is recorded here as the decision it was.

Equibase result charts publish breeding on exactly one line per race — the
`Winner:` line. The correspondence is exact:

| | Count |
|---|---:|
| Horses with pedigree in `horses` | 13,636 |
| Horses that ever won a race | 13,636 |
| Have pedigree but never won | **0** |
| Ever won but no pedigree | **0** |

A 9-runner chart contains one sex token — the winner's — and the per-entry
parser output has no breeding fields at all. **This is a data-source
limitation, not a parser or loader bug. There is nothing to patch in
`db_loader.py`.**

An as-of backfill (gate pedigree to "the horse had already won before today")
was built, measured, and then **removed on Doug's instruction**. It would have
cut the leak from a 1.000 to a 0.559 gap, but what survives is so close to a
restatement of `career_wins` that it adds no information while keeping leak
risk. The right call.

**Decision: 26 catalog features are marked `unavailable_permanent`** in
`dpv1_feature_config.json` (12 of them Doug rank 1-2), covering the whole of
Doug's pedigree bucket plus the four v10 sire signals that depend on sire
identity. Active features drop 108 → 100.

`scripts/test_pedigree_population.py` (4/4 passing) pins this: it asserts the
data limit, asserts the config marks the bucket unavailable, and asserts no
pedigree column reaches the built feature table. If a PP feed ever lands, the
first assertion fails — which is the signal to revisit.

**This could not have changed the Phase 4D result: none of the 26 are rank-1.**
Doug's rank-1 set contains no pedigree feature.

---

## 3. The finding that matters: the edge was never information

Phase 4C's headline was that DPv1 beat the market by ~1% on CT/MNR against
~0.5% on GP, consistently in 4 of 4 folds, and read that as a less-efficient
bullring market. Phase 4D's corrected exacta trigger required calibrating the
market first — and that calibration answers a different, larger question.

**Platt-rescaling the Harville market estimate — two parameters, no features —
reproduces almost the entire edge.**

| Slice | n | Raw market | **Calibrated market** | DPv1 | Edge vs raw | **Edge vs calibrated** | From calibration |
|---|---:|---:|---:|---:|---:|---:|---:|
| GP | 50,577 | 0.56041 | 0.55779 | 0.55741 | +0.535% | **+0.069%** | 87.3% |
| CT | 34,507 | 0.55659 | 0.55109 | 0.55073 | +1.053% | **+0.066%** | 93.8% |
| MNR | 23,302 | 0.55842 | 0.55378 | 0.55333 | +0.913% | **+0.081%** | 91.1% |
| **CT+MNR** | 57,809 | 0.55733 | 0.55217 | 0.55178 | +0.997% | **+0.072%** | 92.8% |
| ALL | 108,386 | 0.55877 | 0.55479 | 0.55440 | +0.781% | **+0.070%** | 91.0% |

*(Phase 4C model, out-of-sample folds; the market calibration is fitted
out-of-fold so it never sees the rows it is scored on.)*

### Phase 4C's edge-zone finding is retracted

| Measured against | GP | CT+MNR | Gap |
|---|---:|---:|---:|
| Raw Harville market (Phase 4C) | +0.535% | +0.997% | **+0.461pp** |
| Calibrated market (Phase 4D) | +0.069% | +0.072% | **+0.004pp** |

The gap does not shrink — it vanishes. CT and MNR did not have a softer
betting market. **The Harville reduction is simply worse calibrated on those
tracks** (smaller fields, 7.2-7.7 runners vs GP's 8.1, so its favourite bias
bites harder), and recalibrating buys correspondingly more there. That is a
property of *our market model*, not of the betting public.

I reported that differential in Phase 4C as "the edge-zone hypothesis
surviving its first real test", on the strength of 4-of-4 fold consistency.
The fold consistency was real; the interpretation was wrong. A systematic
miscalibration is exactly the kind of thing that reproduces in every fold.

**Across all three tracks, Doug's features add a uniform +0.07% over a
properly calibrated market.** Phase 4C's stated alternative outcome — "if
uniform mediocrity → truly no edge from public data" — is what actually
happened; it was hidden behind an uncalibrated baseline.

---

## 4. The decisive test in detail

19 rank-1 fundamental features, trained on CT+MNR only, 2022+, same grid
(4 half-lives × 4 L2) and year folds as Phase 4C.

**Hyperparameters were completely inert** — all 16 combinations returned
log-loss 0.55185 and edge +0.983% to five decimal places. Best nominal:
half-life 1.0y, L2 0.001.

### Criterion 1 — log-loss edge ≥ 1.5%: **FAIL (0.983%)**

| Fold | n | Log-loss | Edge vs raw market | corr |
|---|---:|---:|---:|---:|
| fold_val2023 | 17,115 | 0.5496 | +0.842% | 0.549 |
| fold_val2024 | 16,515 | 0.5513 | +0.992% | 0.539 |
| fold_val2025 | 16,145 | 0.5481 | +0.895% | 0.560 |
| fold_val2026 | 8,034 | 0.5652 | +1.427% | 0.543 |
| **pooled** | 57,809 | 0.5519 | **+0.983%** | **0.548** |

Consistent, and consistently short of 1.5%. Against a calibrated market it is
+0.060%.

### Criterion 2 — corr < 0.55: **PASS (0.548), marginally**

The only criterion that clears, and it clears by 0.002. One fold
(fold_val2025) is **0.5596**, above the line. Treat this as a coin-flip pass,
not a result.

For contrast, the full-feature model on the same data scores 0.609 — so the
rank-1 restriction does genuinely reduce market-shadowing, as Phase 4C
predicted. It just doesn't buy any edge with the freedom.

### Criterion 3 — longshot lift > 1.15×: **FAIL (0.373)**

Phase 4D's rule (`p_model > 1.15 × p_market`) fires on 19,119 entries (33.1%
of the field) and genuinely does select longshots — median odds 30.9 vs 4.5
for unflagged. They hit ITM 15.3% against a 41.1% base rate.

| Ratio | n | % of field | ITM rate | **Lift** |
|---:|---:|---:|---:|---:|
| 1.05 | 26,719 | 46.2% | 20.3% | 0.495 |
| **1.15** | 19,119 | 33.1% | 15.3% | **0.373** |
| 1.25 | 13,661 | 23.6% | 12.1% | 0.295 |
| 1.50 | 4,114 | 7.1% | 5.9% | 0.143 |

Lift falls monotonically as the threshold tightens: **the more strongly the
model prefers a longshot over the market, the worse that horse does.**

A fairness note, because lift-against-the-base-rate is the same shape of error
this project has already made twice: any rule selecting long prices will show
lift < 1 by construction. The fair test is whether flagged horses beat *their
own price*:

| Reference market | Flagged ITM | Implied | Actual / implied |
|---|---:|---:|---:|
| vs **raw** Harville | 15.3% | 12.4% | **1.235** |
| vs **calibrated** market | 15.3% | 16.4% | **0.933** |

Against the raw market the longshot signal looks real. Against a calibrated
one it is *negative*. The apparent skill was Harville's favourite-longshot
bias, again. **The model has no longshot-detection ability.**

### Criterion 4 — positive ROI on any exotic: **FAIL**

| Ticket | DPv1 (rank-1, CT+MNR) | Market chalk |
|---|---:|---:|
| Exacta box, top 2 | **−14.97%** | **−12.47%** |
| Exacta box, top 3 | −19.15% | −18.39% |
| Trifecta box, top 3 | −25.72% | −25.39% |
| Superfecta box, top 4 | −29.96% | −28.97% |
| Exacta at ≥2pp calibrated edge | −17.21% (154 races, 1.9% trigger) | −12.76% |

Every structure loses, and **the market's own top picks beat the model on
every one of them.** The calibrated edge trigger now fires (154 races vs zero
in Phase 4C, so that fix worked) and loses more than betting chalk.

---

## 5. Head-to-head

All scored on the identical 57,809 CT+MNR validation entries.

| Variant | Edge vs raw | Edge vs calibrated | corr | Top-3 hit | Trifecta ROI |
|---|---:|---:|---:|---:|---:|
| **rank1_ctmnr** (the test) | +0.983% | +0.060% | **0.548** | 98.23% | −25.7% |
| full_ctmnr (all 100 features) | +1.019% | +0.096% | 0.609 | 98.20% | −24.6% |
| rank1_pooled (trained incl. GP) | +0.996% | +0.072% | 0.542 | 98.28% | −25.4% |
| market chalk | — | −0.932% | 1.000 | 98.30% | −25.4% |

Three readings:

* **Dropping GP from training changed nothing** (+0.983% vs +0.996% pooled).
  The bullring circuit does not need its own model.
* **Restricting to rank-1 changed nothing on edge** (+0.983% vs +1.019%) but
  did cut correlation 0.609 → 0.548. Phase 4C's read was right about the
  mechanism and irrelevant to the outcome.
* **The market chalk has the best top-3 hit rate of all four.** DPv1's
  selection is not better than reading the tote board top-down.

---

## 6. Feature importance — Doug's handicapping is sound

With GP removed, the `track_code` and structural terms that dominated Phase
4C's fit are gone, and what remains is a recognisable handicapping model:

| # | Feature | Coef |
|---:|---|---:|
| 1 | `class_change_from_last__UP` | −0.478 |
| 2 | `last_race_finish_pos` | −0.379 |
| 3 | `field_size` | −0.355 |
| 4 | `class_change_from_last__DOWN` | +0.335 |
| 5 | `career_itm_pct_shrunk` | +0.247 |
| 6 | `starts_at_track` | −0.242 |
| 7 | `race_type__MAIDENCLAIMING` | +0.223 |
| 8 | `last_race_finish_pos__missing` | −0.214 |
| 9 | `last_race_won__missing` | −0.214 |
| 10 | `last_race_speed_figure__missing` | −0.209 |

**Doug's rank-1 #1 feature — class change — is the model's single strongest
signal in both directions**, UP negative and DOWN positive, symmetric and
correctly signed. Last-race finish, field size and career ITM follow. This is
a defensible handicapping model.

It is worth separating the two conclusions cleanly, because they are not the
same conclusion:

* **Doug's feature ranking is validated.** The features he ranked 1 carry the
  weight, in the directions he said, and they alone match a 100-feature model.
* **The market already knows all of it.** That validation is exactly why there
  is no edge — these are the first things any handicapper looks at, so they are
  the first things priced in.

---

## 7. What Phase 4D corrected in its own measurements

Two more measurement bugs surfaced, continuing the pattern from 4B.1 and 4C.
Both are fixed here.

1. **`int(1.15 * 100)` is 114.** The first Phase 4D run reported longshot lift
   as `nan` — not because no entries flagged (19,119 did) but because the
   metric was stored under `ls114_lift` and read as `ls115_lift`. Binary
   floating point. Fixed with `round()`; the real value is 0.373, a decisive
   fail rather than a missing number.
2. **The calibrated exacta trigger works.** Phase 4C's trigger fired 0 times in
   14,543 races; measured against a calibrated market it fires on 154 races
   (1.9%). The fix was correct — the strategy still loses.

Three phases in a row have produced a headline number that a measurement error
had distorted. That is worth stating plainly: the infrastructure for catching
these (per-track slicing, the correlation diagnostic, calibrated baselines) is
now good, and it is what turned a "qualified yes" into a clean negative.

---

## 8. Recommendation: pause the project

Against the stated decision rule — *"if 0 criteria clear → honest project
pause"* — the count is 1 of 4, and that one passes by 0.002 with a fold above
the line. On the substance the answer is cleaner than the count: **once the
market baseline is calibrated, Doug's features add 0.07% and no wagering
structure is profitable.**

**What has been established, and is worth keeping:**

* Doug's ranked feature catalog is sound; his rank-1s carry the model and his
  class-change intuition is its strongest signal.
* The pipeline is correct and well-tested — leakage probes, alignment
  regression tests, pedigree availability tests, per-track slicing, a
  correlation diagnostic and calibrated baselines.
* A 3-track, 28,105-race corpus with 100 validated features exists and is clean.
* The v2/v2a baselines are honest after the Phase 4B.1 fix.

**What has been ruled out:**

* Public Equibase **result charts** cannot beat the tote board on GP, CT or
  MNR — not on log-loss against a calibrated market, not on longshot
  selection, and not on any exotic ticket.
* The CT/MNR "edge zone" was a calibration artifact.
* More features do not help: 100 features and 19 features perform identically.
* More tracks do not help: pooled and circuit-only training perform identically.

**If the project resumes, only one thing changes the odds:** a
past-performance feed (Brisnet/DRF). It is the only source that supplies what
this corpus structurally cannot — workouts (Doug rank 2, blocked since 4B),
breeding for non-winners (26 features, unavailable), and morning-line odds. It
would also give a second, independent probability estimate to blend against.
Adding anything else derived from result charts is re-arranging what the market
has already priced.

**Do not** resume with: more chart-derived features, more tracks, different
model families on the same inputs, or a wagering strategy on the current edge.

### One honest caveat on the negative

This tested a **linear** blend of a **logistic** fundamental on **ITM**. A
gradient-boosted model on the same features would likely add a little, and
it was never tried. But the ceiling is visible: the fundamental alone scores
0.633 against a calibrated market's 0.552, and its whole marginal contribution
is +0.07%. A better function class would have to find something in these
inputs that a well-specified linear model on 19 strong features could not —
possible, but not where I would spend the next phase.

---

## 9. Files

**New in Phase 4D**
```
scripts/test_pedigree_population.py     data-limit + unavailability regression test (4/4)
scripts_dpv1/run_phase4d.py             the decisive test driver
scripts_dpv1/decompose_edge.py          calibration-vs-information decomposition
```

**Changed**
```
scripts_dpv1/build_dpv1_config.py       pedigree bucket -> unavailable_permanent
scripts_dpv1/dpv1_feature_config.json   dpv1.2.0 — 100 active, 26 unavailable
scripts_dpv1/dpv1_metrics.py            lift-based longshots, Platt calibration,
                                        calibrated exacta trigger, ls-key rounding fix
scripts_dpv1/train_dpv1.py              per-fold market calibration in run_fold
racing_full.db : entry_features_dpv1    rebuilt, 107 cols (100 active + 7 keys)
```

**Artifacts**
```
scripts_dpv1/phase4d_results.json           all variants, criteria, coefficients
scripts_dpv1/phase4d_grid.csv               16-combo grid
scripts_dpv1/phase4d_fold_predictions.csv   57,809 out-of-sample CT+MNR predictions
```

**Reproducing**
```bash
python scripts/test_pedigree_population.py --db scripts/racing_full.db
python scripts_dpv1/build_dpv1_config.py
python scripts_dpv1/feature_builder_dpv1.py build
python scripts_dpv1/run_phase4d.py
python scripts_dpv1/decompose_edge.py
```
