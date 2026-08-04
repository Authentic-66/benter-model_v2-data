# Phase 4C — DPv1 Model Training (Multi-Track, ITM Target)

> ### ⚠️ RETRACTED by Phase 4D — read `PHASE_4D_RANK1_CIRCUIT.md` §3 first
>
> This report's headline finding — that DPv1 beats the market by ~1% on CT/MNR
> against ~0.5% on GP, consistently in 4 of 4 folds, indicating a less
> efficient bullring market — **does not survive a calibrated market
> baseline**.
>
> Platt-rescaling the Harville market estimate (two parameters, no features)
> reproduces 87-94% of the measured edge on every track. Against a calibrated
> market the GP-vs-CT/MNR gap collapses from **+0.461pp to +0.004pp**, and
> Doug's features add a uniform **+0.07%** everywhere.
>
> The fold consistency reported below was real; the interpretation was not. A
> systematic miscalibration reproduces in every fold. CT and MNR did not have a
> softer market — the Harville reduction is simply worse calibrated on their
> smaller fields.
>
> Everything else in this report stands: the per-track machinery, the rank-1
> equivalence result, the interaction test, and the two mis-specified ship
> criteria it identified.

**Date:** 2026-07-31 · **Model:** `dpv1.1.0` · **Artifact:** `scripts_dpv1/dpv1.pkl`
**Corpus:** `racing_full.db`, 2022+ — 140,188 entries / 18,904 races across GP + CT + MNR
**Scored on:** 108,386 out-of-sample validation entries across 14,543 races (4 rolling-origin year folds)

---

## 1. TL;DR

**The critical success question — does DPv1 perform differently on GP than on
the CT/MNR bullring circuit? — answers YES, and the pattern is consistent in
4 of 4 folds.**

| Track | Log-loss vs market | Blend corr(p_f, p_m) |
|---|---:|---:|
| GP (efficient) | **+0.58%** | 0.615 |
| CT | **+1.05%** | 0.678 |
| MNR | **+0.91%** | 0.551 |
| **CT+MNR (edge zone)** | **+1.00%** | 0.618 |
| ALL | +0.80% | 0.616 |

CT+MNR beats GP by ~0.42 percentage points of log-loss improvement, in every
fold, never reversing. That is the edge-zone hypothesis surviving its first
real test.

**But the edge does not convert into money.** Trifecta box ROI on CT+MNR is
**−24.6%**, essentially identical to betting the market's own top three
(−25.4%). A ~1% log-loss improvement is roughly a fortieth of what the
takeout removes.

**Three findings matter more than the headline:**

1. **Doug's 19 rank-1 features alone match the full 95-feature model** —
   same log-loss to four decimals — while being *much* less market-correlated
   (CT+MNR corr **0.54** vs 0.62). The rank-1-only variant is the only
   configuration that passes the correlation ship criterion. The other 76
   features add market redundancy, not edge.
2. **Doug's interaction insight is real but already captured.** The model
   reproduces his won-last-out × class-up penalty to within 1pp *without* an
   explicit term; adding one changes nothing.
3. **Two of the four ship criteria are mis-specified** and cannot mean what
   they were intended to mean. Details in §8 — this is not a quibble, one of
   them would have been scored as a PASS for a filter that performs *worse
   than random*.

**Recommendation: do not ship. Proceed to a narrowed Phase 4D on the rank-1
feature set and the CT/MNR circuit** — that is where both the edge and the
low market-correlation live.

---

## 2. A correction to Phase 4B before anything else

Phase 4B activated 108 features. **Eight of them had to be removed here**,
because their missingness encodes the future.

The Phase 3A loader fills `horses.sex / foaled_date / sire_id / dam_id` only
when a horse first appears as a **race winner**. Phase 3E caught this for the
horse-immutable bucket and predicted the leak would fade once the corpus went
multi-track. Re-measured on all 207,976 entries of `entry_features_dpv1`:

| Feature | Doug's rank | P(ever won \| known) | P(ever won \| null) |
|---|---:|---:|---:|
| `horse_sex` | 2 | **100.00%** | **0.00%** |
| `sire_at_distance_winrate_shrunk` | 2 | 100.00% | 3.46% |
| `sire_at_surface_winrate_shrunk` | 2 | 100.00% | 4.02% |
| `sire_dirt_win_pct` | 2 | 100.00% | 44.63% |
| `sire_sprint_win_pct` | 2 | 100.00% | 52.21% |
| `sire_route_win_pct` | 2 | 100.00% | 56.71% |

It did not fade. `horse_sex` is a **perfect** predictor of whether a horse
ever wins, independently on all three tracks. ITM rate is 46.9% where it is
known and 22.6% where it is null. Since the preprocessor emits a
`{col}__missing` flag for every nullable column, these leak through the flag
even when the value itself is sound.

Excluded: `horse_sex`, `is_florida_bred` (its `1` implies a known foaling
place, hence a winner), and the six `sire_*` progeny rates. All eight are
Doug rank-2. **Doug's entire pedigree bucket is unusable until the loader is
changed to populate pedigree for every horse rather than only for winners.**

**Not excluded** — and this distinction is the whole point — features that are
null for *first-time starters* (`career_*`, `last_race_*`, the specialist
flags, `gate_break_avg_last_3`). Their missingness also correlates with "ever
won", but "this horse has no past performances" is knowable at post time. The
test is the mechanism, not the correlation size.

Final feature accounting:

```
108 active (Phase 4B)
  −  8 leaky (future-derived missingness)
  −  5 market (held out of the fundamental by design)
  = 95 fundamental features   (19 rank-1, 62 rank-2, 14 DPv1 cross-track additions)
```

---

## 3. Architecture and setup

```
fundamental : binary logistic per entry, 95 features → 213 encoded columns
market      : Harville P(ITM) from per-race-normalised tote win odds
blend       : sigmoid(α·logit p_f + β·logit p_m + γ), fit per fold on validation
```

Rolling-origin CV **by calendar year** — train on everything before year Y,
validate on Y:

| Fold | Train | Validate | Val entries |
|---|---|---|---:|
| fold_val2023 | 2022 | 2023 | 31,345 |
| fold_val2024 | 2022-23 | 2024 | 31,169 |
| fold_val2025 | 2022-24 | 2025 | 30,848 |
| fold_val2026 | 2022-25 | 2026 (partial) | 15,024 |

Fold 1 trains on a single year and is the weakest; it is reported per fold
rather than buried in a mean.

**Grid:** 4 half-lives × 4 L2 × 4 folds = 64 fits. Winner: **half-life 2.0y,
L2 0.01** — but as in every previous phase, hyperparameters barely matter
(the whole grid spans 0.0001 of log-loss).

**Blend weights per fold:**

| Fold | α (fundamental) | β (market) | γ |
|---|---:|---:|---:|
| fold_val2023 | 0.097 | 0.804 | −0.040 |
| fold_val2024 | 0.137 | 0.766 | −0.035 |
| fold_val2025 | 0.060 | 0.791 | −0.050 |
| fold_val2026 | 0.075 | 0.736 | −0.059 |
| **final refit** | **0.106** | **0.772** | **−0.041** |

α ≈ 0.11 is small but consistently positive — unlike v2's win-target models,
where Phase 4B.1 found α turning negative. The ITM fundamental does contribute
something. β ≈ 0.77 < 1 means the blend also *shrinks* the market, correcting
Harville's known favourite bias (see the ECE numbers in §4).

---

## 4. Per-track results — the core of the phase

All figures are pooled over the four validation folds (out-of-sample).

| Metric | GP | CT | MNR | CT+MNR | ALL |
|---|---:|---:|---:|---:|---:|
| Val entries | 50,577 | 34,507 | 23,302 | 57,809 | 108,386 |
| Val races | 6,613 | 4,609 | 3,321 | 7,930 | 14,543 |
| ITM base rate | 39.2% | 40.0% | 42.7% | 41.1% | 40.2% |
| **Log-loss (DPv1)** | 0.5574 | 0.5507 | 0.5533 | **0.5518** | 0.5544 |
| Log-loss (market) | 0.5607 | 0.5566 | 0.5584 | 0.5573 | 0.5589 |
| **vs market** | **+0.58%** | **+1.05%** | **+0.91%** | **+1.00%** | +0.80% |
| **corr(logit p_f, logit p_m)** | 0.615 | **0.678** | **0.551** | 0.618 | 0.616 |
| Brier | 0.1889 | 0.1865 | 0.1877 | 0.1870 | 0.1879 |
| ECE (DPv1) | 0.0079 | 0.0135 | 0.0159 | 0.0133 | 0.0107 |
| ECE (market) | 0.0282 | 0.0386 | 0.0364 | 0.0377 | 0.0333 |
| ITM hit top-3 | 97.5% | 98.3% | 98.1% | 98.2% | 97.9% |
| ITM precision top-3 | 61.3% | 62.9% | 64.8% | 63.7% | 62.6% |
| Full sweep top-3 | 15.7% | 16.6% | 19.6% | 17.9% | 16.9% |

### Is the GP/bullring gap real, or one lucky fold?

Log-loss improvement over market, **per fold**:

| Fold | GP | CT | MNR | CT+MNR |
|---|---:|---:|---:|---:|
| fold_val2023 | +0.27% | +0.82% | +0.87% | **+0.84%** |
| fold_val2024 | +0.60% | +1.05% | +1.03% | **+1.04%** |
| fold_val2025 | +0.65% | +1.04% | +0.69% | **+0.90%** |
| fold_val2026 | +1.02% | +1.54% | +1.22% | **+1.42%** |
| **mean** | **+0.63%** | **+1.11%** | **+0.95%** | **+1.05%** |
| std | 0.31 | 0.30 | 0.22 | 0.26 |

**CT+MNR > GP in 4 of 4 folds**, by 0.40-0.57pp, never reversing. Under a
sign test that alone is only p ≈ 0.06, but the gap is also stable in
magnitude, which a coin flip would not produce. Treat it as a real effect of
modest size, not as established beyond doubt.

Two honest caveats:

* **The improvement grows monotonically over time** (+0.84% → +1.42%). Later
  folds have more training data, so part of this is sample size rather than a
  market becoming less efficient. The GP/bullring *gap* is present in every
  fold regardless.
* **Pooled vs mean-of-folds disagree at the ship threshold.** Pooling all
  CT+MNR entries gives **+0.997%**; averaging the four folds gives **+1.050%**.
  The ship criterion is "≥1%". It fails one way and passes the other. Reported
  both ways rather than picking the flattering one.

**Calibration is where DPv1 clearly wins:** ECE 0.0107 vs the market's 0.0333,
a 3× improvement, consistent across all three tracks. The raw Harville market
estimate is materially overconfident and DPv1 fixes that. This is real, but
calibration is not edge — see §6.

---

## 5. Variants and baselines

All at the winning hyperparameters, scored on identical folds.

| Variant | ALL log-loss | CT+MNR vs market | CT+MNR corr | ALL top-3 hit | CT+MNR trifecta ROI |
|---|---:|---:|---:|---:|---:|
| **full** (95 feats) | 0.5544 | +0.997% | 0.618 | 97.90% | −24.6% |
| **rank1_only** (19 feats) | **0.5544** | +0.985% | **0.543** | **97.98%** | −24.7% |
| **+interaction** (97 feats) | 0.5544 | +0.995% | 0.618 | 97.88% | −24.9% |
| market (chalk) | 0.5589 | 0.000% | 1.000 | 98.00% | −25.4% |
| random | 1.0021 | −79.2% | 0.000 | 85.35% | −43.9% |

### The rank-1-only result is the most interesting thing in this phase

**19 of Doug's rank-1 features reproduce the full model's log-loss to four
decimal places** — and do it with a fundamental that is far less
market-correlated: **0.543 on CT+MNR versus 0.618**. It is the only variant
that satisfies the `corr < 0.60` criterion.

It also flags meaningfully more longshots at better precision (CT+MNR: 50
flags at 18.0% vs 34 at 14.7%; GP: 45 at 28.9% vs 17 at 35.3%), which on
sample-size grounds alone makes it the more trustworthy detector.

Reading: the 76 rank-2 and cross-track features are not adding independent
information. They are adding *market-shaped* information — exactly the failure
mode Phase 4B.1's correlation diagnostic was introduced to catch. Doug's own
top-priority list is the better feature set, and it is 5× smaller.

---

## 6. Wagering — no strategy is profitable

Box wagers over the model's top-k picks, priced from `exotic_payouts`.
Payoffs are normalised per $1 staked (base differs by track: trifecta is $1 at
CT/MNR, $0.50 at GP). Dead heats produce multiple winning combinations for one
race (23% of trifecta races carry two rows); ROI is reported on the mean
payoff across combinations, and min/max variants were computed as a
sensitivity check — no conclusion changes.

| Strategy | GP | CT | MNR | CT+MNR | ALL |
|---|---:|---:|---:|---:|---:|
| Trifecta box, top 3 | −22.7% | −24.2% | −25.2% | **−24.6%** | −23.8% |
| Trifecta box, top 4 | −24.4% | −24.8% | −27.6% | −26.0% | −25.2% |
| Superfecta box, top 4 | −30.9% | −30.5% | −31.9% | −30.9% | −30.9% |
| *market chalk, trifecta top 3* | *−21.3%* | *−24.0%* | *−27.3%* | *−25.4%* | *−23.6%* |

DPv1 beats chalk on CT+MNR by 0.8pp and loses to it on GP by 1.4pp — the same
directional pattern as the log-loss result, at a scale that is irrelevant next
to a ~20% takeout.

**The exacta-at-edge-threshold test could not run**, and why is informative.
The rule was "bet where the model's top pick beats market P(ITM) by ≥5pp".
Across 14,543 races the model's top-pick edge is:

```
median  −0.0497      races with edge ≥ 1pp:   7 / 14,543
99th pct −0.0095     races with edge ≥ 5pp:   0 / 14,543
max      +0.0481
```

The model is *systematically less confident than the market on its own
favourite*. That is partly genuine market-tiedness and partly structural: the
blend's weights sum to ~0.88, which compresses extreme probabilities, and
much of that compression is DPv1 correctly undoing Harville's favourite bias
(market ECE 0.033 → DPv1 0.011). So "edge vs market" measured against an
*uncalibrated* market baseline is the wrong yardstick for a wagering trigger.
**The criterion cannot fire as written** and needs redefining against a
calibrated market before it can test anything.

---

## 7. Doug's handicapping insights

### Class change — the model learns it cleanly

| Class move | n | Actual ITM | DPv1 predicted | Fundamental only |
|---|---:|---:|---:|---:|
| DOWN | 14,674 | 45.68% | 46.97% | 45.80% |
| SAME | 66,138 | 40.47% | 39.69% | 40.79% |
| UP | 13,564 | 35.87% | 35.99% | 36.04% |

Monotone DOWN > SAME > UP, matching Phase 4B's raw marginals, and predicted to
within ~1.3pp in every cell. The derived class ladder (built because
`races.class_level` is NULL corpus-wide) is measuring something real and the
model uses it correctly.

### Doug's interaction — real, and already captured

| Won last out | Class move | n | Actual ITM | DPv1 predicted |
|---|---|---:|---:|---:|
| Yes | DOWN | 792 | 58.71% | 60.05% |
| Yes | SAME | 6,069 | 54.36% | 55.46% |
| Yes | **UP** | 6,400 | **42.25%** | **42.55%** |
| No | DOWN | 13,810 | 45.00% | 46.23% |
| No | SAME | 59,858 | 39.10% | 38.11% |
| No | UP | 7,131 | 30.16% | 30.10% |

Doug's note on `last_race_won`: *"winning multiple races in a row is
difficult, unless the horse really is that good, and especially if/as it moves
up in class."*

The penalty is real — **12.1pp** from won-and-same-level (54.4%) to
won-and-stepping-up (42.3%) — and the model predicts it to within **0.3pp**
**without any explicit interaction term**.

Adding `won_last_class_up_flag` explicitly changed nothing (ALL log-loss
identical to four decimals; CT+MNR +0.995% vs +0.997%). The reason: additive
main effects *on the logit scale* already generate this pattern on the
probability scale. A 12pp swing at these base rates needs no interaction term
to express.

**Verdict:** Doug's insight is validated as handicapping, and requires no
feature-engineering change. That is a useful negative result — it closes off
"add more of Doug's interactions" as a Phase 4D direction unless a candidate
demonstrably breaks logit-additivity.

### Feature importance

Mean |coefficient| by Doug's rank (standardised features, final refit):

| Group | Encoded columns | Mean \|coef\| | Max \|coef\| |
|---|---:|---:|---:|
| DPv1 cross-track additions | 30 | **0.093** | 0.484 |
| Doug rank 1 | 54 | 0.079 | 0.344 |
| Doug rank 2 | 125 | 0.039 | 0.477 |

**Doug's rank-1 features carry roughly twice the average weight of his
rank-2s** — his prioritisation is validated by the model, independently of his
reasons for it.

Top 12 coefficients:

| # | Group | Feature | Coef |
|---:|---|---|---:|
| 1 | NEW | `track_code__GP` | −0.484 |
| 2 | R2 | `track_dirt_bias_90d__missing` | −0.477 |
| 3 | NEW | `track_code__MNR` | +0.475 |
| 4 | R1 | `field_size` | −0.344 |
| 5 | NEW | `trainer_home_track__MNR` | −0.329 |
| 6 | R1 | `last_race_finish_pos` | −0.306 |
| 7 | NEW | `jockey_home_track__GP` | +0.271 |
| 8 | R1 | `surface__Dirt` | −0.268 |
| 9 | R1 | `last_race_finish_pos__missing` | −0.249 |
| 10 | NEW | `trainer_home_track__GP` | +0.241 |
| 11 | R1 | `race_type__STAKES` | +0.239 |
| 12 | NEW | `jockey_home_track__MNR` | −0.238 |

**Be careful reading this.** The three largest weights are *structural*, not
handicapping: `track_code` and `field_size` encode base-rate differences
(MNR's ITM rate is 42.7% vs GP's 39.2%, driven largely by field size — 7.2 vs
8.1 runners). The model spends its largest coefficients learning "which track,
how many horses", which is arithmetic, not insight.

Of the genuine cross-track features, **`trainer_home_track` and
`jockey_home_track` do carry real weight** (ranks 5, 7, 10, 12) — the
connection-circuit features earn their place. `horse_shipping_success_rate` is
negligible (|coef| 0.056), consistent with its 10% coverage.

---

## 8. Ship criteria — assessed, with two rejected as mis-specified

> Model must beat market baseline on **at least one** of four criteria.

| # | Criterion | Result | Verdict |
|---|---|---|---|
| 1 | Log-loss on CT+MNR ≥1% better | +0.997% pooled / +1.050% mean-of-folds | **AMBIGUOUS** |
| 2 | Longshot precision > 30% on any track | GP 35.3% (n=17) | **MIS-SPECIFIED — see below** |
| 3 | Positive trifecta ROI at edge threshold on CT+MNR | −24.6% | **FAIL** |
| 4 | corr(p_f, p_m) < 0.60 on CT+MNR | 0.618 (full) / **0.543 (rank1_only)** | **FAIL for full, PASS for rank-1-only** |

### Criterion 2 is broken and would have produced a false pass

Longshot precision must be read against the **ITM base rate of ~40%**, because
a "longshot" here is a horse we predict will hit the board — and 40% of all
horses do.

| Track | Flags | Precision | Base ITM rate | Lift |
|---|---:|---:|---:|---:|
| GP | 17 | 35.3% | 39.2% | **0.90×** |
| CT | 23 | 17.4% | 40.0% | 0.44× |
| MNR | 11 | 9.1% | 42.7% | 0.21× |
| CT+MNR | 34 | 14.7% | 41.1% | 0.36× |
| ALL | 51 | 21.6% | 40.2% | 0.54× |

**Every longshot bucket performs worse than picking a horse at random**, GP
included. Its 35.3% would have been scored a PASS against a ">30%" bar while
being 0.90× the base rate — a losing filter. The criterion should be
*lift > 1.0×*, and on that basis the longshot detector **fails everywhere**.
(Also: n=17 at GP is far too small to conclude anything from either way.)

### Criterion 3's threshold test cannot fire

As shown in §6, zero of 14,543 races produce a top-pick edge ≥5pp because the
blend systematically prices its own favourite below the market. The criterion
needs redefining against a calibrated market baseline.

### Honest overall verdict

**Do not ship.** Of four criteria, one is ambiguous at the third decimal, two
are unusable as written, and the one that is both well-specified and decisive
(wagering ROI) fails by ~24 percentage points. The single clean pass —
correlation below 0.60 — belongs to the *rank-1-only* variant, not the model
as built.

---

## 9. Head-to-head vs Phase 3G v2a

Scored on the **identical 36,347 GP entries / 4,767 races** both models held
out (matched on race date + race number + program number, since the two
databases don't share entry ids). v2a is the Phase 4B.1-rebuilt artifact.

| Metric | DPv1 | v2a | Δ |
|---|---:|---:|---:|
| Log-loss | 0.5590 | 0.5590 | −0.0000 |
| vs market | +0.702% | +0.693% | +0.009pp |
| Brier | 0.1894 | 0.1895 | −0.0001 |
| ECE | 0.0117 | 0.0107 | +0.0009 |
| corr(p_f, p_m) | 0.620 | 0.627 | −0.007 |
| ITM hit top-3 | 97.52% | 97.55% | −0.02pp |
| ITM precision top-3 | 61.30% | 61.24% | +0.06pp |
| Full sweep top-3 | 15.63% | 15.71% | −0.08pp |
| Trifecta box ROI | −23.27% | −22.78% | −0.49pp |
| Superfecta box ROI | −31.02% | −32.65% | +1.63pp |

**A dead tie.** On Gulfstream, DPv1's 95 ranked features, three-track priors,
class ladder, trouble taxonomy and cross-track additions buy **nothing** over
v2a's 73 Phase 3C features.

This is the cleanest statement of where DPv1's value actually is: not in the
richer feature set, but in **covering CT and MNR at all** — tracks v2a never
saw, and where the same machinery finds nearly twice the edge.

---

## 10. Sample race

**CT, 2026-07-25, $claiming, 6f dirt, 7 starters** (`dpv1_predictions_sample.json`
also carries a GP and an MNR race).

| Rank | Odds | P(ITM) model | fundamental | market | Edge | Finish | ITM |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.4 | 0.734 | 0.507 | 0.811 | −0.077 | 2 | ✓ |
| 2 | 1.9 | 0.679 | 0.441 | 0.754 | −0.075 | 4 | |
| 3 | 4.5 | 0.478 | 0.251 | 0.519 | −0.040 | 3 | ✓ |
| 4 | 7.0 | 0.380 | 0.264 | 0.382 | −0.002 | 7 | |
| 5 | 9.3 | 0.325 | 0.293 | 0.305 | +0.020 | 5 | |
| 6 | 21.8 | 0.192 | 0.276 | 0.145 | +0.047 | — | |
| 7 | 39.1 | 0.122 | 0.119 | 0.084 | +0.038 | 6 | |

Two of the model's top three hit the board. The shape is the whole phase in
one race: DPv1 shades every short price **down** and every long price **up**
relative to the tote — a calibration correction — while barely reordering
anything. The fundamental disagrees more (it likes the 21.8-1 at 0.276), but
at α ≈ 0.11 it moves the blend by only ~5pp.

---

## 11. Recommendations for Phase 4D

**Highest value**

1. **Rebuild on the rank-1 feature set.** Same accuracy, 5× fewer features,
   materially lower market correlation (0.543 vs 0.618 on CT+MNR), and the
   only configuration passing a well-specified ship criterion. Everything
   below should be tested on that base, not on the 95-feature model.
2. **Fix the pedigree loader.** Populating `horses.*` for every horse rather
   than only winners would (a) remove the leak, (b) return eight rank-2
   features including Doug's whole pedigree bucket, and (c) make Phase 4D's
   sire work possible at all. This is a data-side fix in `db_loader.py`, not
   a modelling change.
3. **Concentrate on CT/MNR.** The edge is ~1.7× larger there and GP shows
   nothing v2a didn't already have. A CT/MNR-only model also removes the
   `track_code` coefficients that currently dominate the fit.

**Methodology**

4. **Redefine ship criteria 2 and 3.** Longshot precision must be measured as
   *lift over the base ITM rate*, not an absolute percentage. Wagering edge
   must be measured against a *calibrated* market, not raw Harville, or the
   threshold can never fire.
5. **Keep the correlation diagnostic front and centre.** It is the metric
   that distinguished the rank-1 model from the full one when log-loss could
   not tell them apart — the second time in two phases it has earned its place.

**Do not pursue**

6. **More of Doug's interactions.** §7 shows the logit-additive model already
   reproduces his flagship interaction to 0.3pp. Only pursue a candidate
   interaction if there is evidence it breaks additivity.
7. **Wagering strategies on the current edge.** A 1% log-loss improvement
   against a ~20% takeout is not a betting proposition, and every box strategy
   tested lost 23-31%.

---

## 12. Files

**New**
```
scripts_dpv1/prepare_training_dpv1.py   loading, leak exclusions, year folds
scripts_dpv1/dpv1_metrics.py            per-track metrics + corr diagnostic + wagering
scripts_dpv1/train_dpv1.py              grid search, final fit, fold predictions
scripts_dpv1/evaluate_dpv1.py           variants, baselines, importance, interaction
scripts_dpv1/compare_dpv1_vs_v2a.py     GP head-to-head on matched entries
scripts_dpv1/PHASE_4C_DPV1_TRAINING.md  this report
```

**Artifacts**
```
scripts_dpv1/dpv1.pkl                       trained model (dpv1.1.0)
scripts_dpv1/dpv1_grid_results.csv          64-fit grid, per-track metrics per fold
scripts_dpv1/dpv1_fold_predictions.csv      108,386 out-of-sample predictions
scripts_dpv1/dpv1_eval.json                 all variants x all track slices
scripts_dpv1/dpv1_vs_v2a.json               head-to-head detail
scripts_dpv1/dpv1_predictions_sample.json   sample races, one per track
```

**Reproducing**
```bash
python scripts_dpv1/train_dpv1.py grid
python scripts_dpv1/train_dpv1.py final
python scripts_dpv1/evaluate_dpv1.py
python scripts_dpv1/compare_dpv1_vs_v2a.py
```

---

## 13. Decision point

Against the three options set out for this phase:

* **"If edge found on CT/MNR → refine, add cross-track features."** An edge
  differential *was* found and it is consistent across folds — but it is ~1%
  of log-loss and does not survive takeout. Refining is justified; expecting
  it to become profitable from public chart data is not.
* **"If uniform market-tie → honest project conclusion, pause."** Not uniform.
  GP is a tie with v2a; CT/MNR is measurably better. The bullring hypothesis
  earned a qualified yes.
* **"If a specific insight drives edge → Phase 4D on interaction discovery."**
  Doug's interaction is real but already modelled. This route is closed.

**Recommended: a narrowed Phase 4D** — rank-1 features, CT/MNR only, pedigree
loader fixed first, ship criteria re-specified. If that does not produce a
better-than-1.5% edge with correlation below 0.55, the honest conclusion is
that public Equibase chart data cannot beat the tote board on these circuits,
and the project should pause rather than add more features.
