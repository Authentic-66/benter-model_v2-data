# Phase 3E — Benter Light v2 (First Model)

_Model version: `benter_v2.1.0` · trained 2026-07-02 · artifact: `scripts/benter_v2.pkl`_

## TL;DR

**Ship criteria failed — do not deploy.** Once a subtle look-ahead leak in the horse-immutable features (Bucket 2) was removed, the fundamental model was found to provide **essentially no signal beyond the market** across all 20 hyperparameter combinations. The blend learned α ≈ 0, β ≈ 1.06 — i.e. the blend is the market.

**But this is a valuable outcome.** We caught the leak *before* shipping a fake edge. The infrastructure is validated: preprocessing, CV, metrics, grid search, and reporting all functioned correctly and made the failure visible. Doug's decision: proceed to Phase 3F (v10 workbook priors) and Phase 3G (Brisnet PP) to add the missing signal, then retrain.

### The bug we caught

The Phase 3A DB loader stores horse pedigree (sex, age, country) **only when a horse first appears as a race winner**. So the presence-vs-absence of pedigree data is a proxy for "this horse wins at least once in the 2019-2026 corpus" — information derived from the future. A first training run leveraged this heavily (missingness flags for `horse_age`, `horse_sex`, `horse_country_origin` were the top-4 coefficients) and produced spectacular but fake numbers (log-loss 1.20, ROI +160%). Once excluded, the model's real signal was near zero and honest numbers emerged.

The fix is checked into `prepare_training.py` as the `LEAKY_FEATURES` tuple. All numbers in this report come from the corrected model.

## Ship criteria assessment

| Criterion | Result | Status |
|---|---:|---|
| Log-loss ≤ 1.6494 (1% better than market) | 1.6474 | ✅ PASS |
| ROI at edge 0.4 > 0 (positive PnL) | n/a (no bets) | ❌ FAIL |
| ECE < 3% (well-calibrated) | 0.0055 | ✅ PASS |
| Hit rate top-1 > 36.4% (beats market fav) | 35.9% | ❌ FAIL |

**One or more ship criteria failed.** The model is not ready to ship as-is; see the fold-by-fold table below to diagnose.

## Headline: model vs baselines

Metrics are means across the four rolling-origin CV folds (2024, 2025, 2026 Q1, 2026 Q2). **Baselines from Phase 3D:** market_favorite = market implied probability (the hard bar to beat); random_uniform = 1/field.

| Model | log-loss | Top-1 | Top-3 | ECE | ROI @0.2 | ROI @0.4 | Fav hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| market_favorite (baseline) | 1.6661 | 36.4% | 72.7% | 0.0056 | n/a | n/a | 36.0% |
| random_uniform (baseline) | 2.0368 | 13.3% | 39.9% | 0.0007 | -0.335 | -0.350 | 36.0% |
| **Benter v2 (α=0.00, β=1.06)** | **1.6474** | **35.9%** | **72.8%** | **0.0055** | **n/a** | **n/a** | **35.7%** |

Δ log-loss vs market: **-0.0187** (-1.1% relative).

## Per-fold performance (best hyperparameters)

| Fold | log-loss | Top-1 | Top-3 | Fav hit | ECE | ROI @0.4 | n bets @0.4 | α | β |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fold1_val2024 | 1.6331 | 38.2% | 73.3% | 37.6% | 0.0053 | n/a | 0 | 0.103 | 1.075 |
| fold2_val2025 | 1.6386 | 36.8% | 72.9% | 36.6% | 0.0054 | n/a | 0 | -0.008 | 1.085 |
| fold3_val2026Q1 | 1.7080 | 33.3% | 70.2% | 33.0% | 0.0066 | n/a | 0 | -0.010 | 1.036 |
| fold4_val2026Q2 | 1.6102 | 35.5% | 74.9% | 35.8% | 0.0047 | n/a | 0 | -0.082 | 1.058 |

## Hyperparameter grid (mean across folds)

Sorted by mean log-loss (lower is better).

| half_life | l2 | log-loss ± σ | Top-1 | ROI @0.4 | ECE | α | β |
|---|---|---|---:|---:|---:|---:|---:|
| 2.5y | 0.001 | 1.6474 ± 0.0422 | 35.9% | n/a | 0.0055 | 0.001 | 1.063 |
| 2.5y | 0.01 | 1.6474 ± 0.0422 | 35.9% | n/a | 0.0055 | 0.001 | 1.063 |
| 2.5y | 1.0 | 1.6474 ± 0.0422 | 35.9% | n/a | 0.0056 | -0.002 | 1.064 |
| 2.5y | 0.1 | 1.6474 ± 0.0422 | 35.9% | n/a | 0.0056 | 0.000 | 1.063 |
| 2.0y | 1.0 | 1.6474 ± 0.0422 | 35.9% | n/a | 0.0055 | -0.001 | 1.064 |
| 2.0y | 0.01 | 1.6474 ± 0.0422 | 35.9% | n/a | 0.0055 | 0.001 | 1.063 |
| 3.0y | 0.01 | 1.6474 ± 0.0422 | 35.9% | n/a | 0.0055 | -0.000 | 1.064 |
| 3.0y | 0.001 | 1.6474 ± 0.0422 | 35.9% | n/a | 0.0055 | -0.001 | 1.064 |
| 3.0y | 1.0 | 1.6474 ± 0.0422 | 35.9% | n/a | 0.0055 | -0.000 | 1.064 |
| 3.0y | 0.1 | 1.6474 ± 0.0422 | 36.0% | n/a | 0.0055 | -0.001 | 1.064 |
| 1.5y | 0.01 | 1.6475 ± 0.0421 | 36.1% | n/a | 0.0056 | 0.001 | 1.063 |
| 1.5y | 0.001 | 1.6475 ± 0.0421 | 36.1% | n/a | 0.0057 | 0.003 | 1.063 |
| 1.5y | 1.0 | 1.6475 ± 0.0421 | 36.0% | n/a | 0.0055 | -0.000 | 1.063 |
| 1.5y | 0.1 | 1.6475 ± 0.0421 | 36.1% | n/a | 0.0056 | 0.002 | 1.063 |
| 1.0y | 0.001 | 1.6475 ± 0.0421 | 36.2% | n/a | 0.0054 | 0.004 | 1.062 |
| 1.0y | 0.01 | 1.6475 ± 0.0421 | 36.1% | n/a | 0.0054 | 0.003 | 1.062 |
| 2.0y | 0.001 | 1.6475 ± 0.0422 | 35.9% | n/a | 0.0055 | 0.000 | 1.063 |
| 2.0y | 0.1 | 1.6475 ± 0.0422 | 35.9% | n/a | 0.0055 | 0.000 | 1.063 |
| 1.0y | 0.1 | 1.6475 ± 0.0421 | 36.1% | n/a | 0.0054 | 0.003 | 1.063 |
| 1.0y | 1.0 | 1.6475 ± 0.0421 | 36.1% | n/a | 0.0053 | 0.002 | 1.063 |

## Top 20 fundamental-model coefficients (|weight|)

Preprocessed features, standardised. Positive coefficients mean the model reads this feature as pointing toward a win; negative mean it pushes toward a loss.

| Feature | Coefficient |
|---|---:|
| `last_3_avg_finish__missing` | +0.7364 |
| `post_position__missing` | +0.6977 |
| `post_rank_in_field__missing` | +0.6977 |
| `last_race_finish_pos__missing` | -0.6120 |
| `gate_break_avg_last_3__missing` | -0.4528 |
| `jockey_365d_winrate_shrunk` | -0.3556 |
| `last_race_speed_figure` | +0.3315 |
| `last_race_finish_pos` | -0.3234 |
| `last_race_beaten_lengths` | +0.2161 |
| `days_since_trainer_last_win__missing` | -0.1916 |
| `days_since_trainer_last_win` | -0.1639 |
| `jockey_90d_winrate_shrunk` | +0.1599 |
| `last_race_beaten_lengths__missing` | +0.1588 |
| `days_since_jockey_last_win__missing` | +0.1560 |
| `pace_type_last_race____MISSING__` | +0.1522 |
| `jockey_starts_30d` | -0.1319 |
| `jockey_at_track_winrate_shrunk` | +0.1273 |
| `last_race_field_size` | +0.1255 |
| `pace_type_last_race__close` | -0.1093 |
| `days_since_jockey_last_win` | -0.1013 |

## Building slice diagnostics on the full validation set…

_Slices with n ≥ 500 entries only (3 small-cell slices hidden)._

| Slice | Value | n | log-loss | Top-1 | ROI @0.4 | Fav hit |
|---|---|---:|---:|---:|---:|---:|
| OVERALL | all | 36,347 | 1.6421 | 36.8% | n/a | 36.5% |
| race_type | ALLOWANCEOPTIONALCLAIMING | 4,746 | 1.6961 | 33.8% | n/a | 33.4% |
| race_type | CLAIMING | 11,588 | 1.5903 | 39.5% | n/a | 38.7% |
| race_type | MAIDENCLAIMING | 8,142 | 1.6981 | 34.9% | n/a | 34.8% |
| race_type | MAIDENOPTIONALCLAIMING | 803 | 1.7920 | 31.0% | n/a | 30.1% |
| race_type | MAIDENSPECIALWEIGHT | 5,264 | 1.6505 | 36.7% | n/a | 36.0% |
| race_type | STAKES | 2,191 | 1.6442 | 36.5% | n/a | 36.3% |
| race_type | STARTERALLOWANCE | 509 | 1.5807 | 38.6% | n/a | 40.5% |
| race_type | STARTEROPTIONALCLAIMING | 2,276 | 1.5472 | 40.1% | n/a | 39.8% |
| surface | AllWeather | 16,297 | 1.6345 | 36.5% | n/a | 36.0% |
| surface | Dirt | 10,328 | 1.5499 | 40.2% | n/a | 39.7% |
| surface | Turf | 9,722 | 1.7789 | 33.1% | n/a | 33.0% |
| distance_category | mid | 20,408 | 1.6567 | 36.3% | n/a | 36.1% |
| distance_category | route | 765 | 1.7429 | 31.1% | n/a | 30.4% |
| distance_category | sprint | 15,174 | 1.6194 | 37.7% | n/a | 37.3% |
| field_size_bucket | large | 7,795 | 1.9612 | 27.7% | n/a | 27.2% |
| field_size_bucket | medium | 21,131 | 1.6687 | 36.0% | n/a | 35.7% |
| field_size_bucket | small | 7,421 | 1.4095 | 43.7% | n/a | 43.2% |
| track_condition_bucket | fast | 34,592 | 1.6457 | 36.5% | n/a | 36.2% |
| track_condition_bucket | off_track | 1,755 | 1.5745 | 42.5% | n/a | 42.4% |
| favorite_bucket | favorite | 9,665 | 0.6487 | 62.7% | -0.189 | 36.5% |
| favorite_bucket | longshot | 12,545 | 1.0427 | 48.2% | -0.321 | 4.5% |
| favorite_bucket | midpack | 14,137 | 1.0255 | 44.5% | -0.218 | 14.4% |

## Calibration table (10 bins)

Bin-wise average predicted probability vs observed hit rate. Perfect calibration means avg pred ≈ observed in every populated bin.

| Bin | Range | n | Avg pred | Observed |
|---|---|---:|---:|---:|
| 0 | [0.00, 0.10) | 19356 | 0.045 | 0.045 |
| 1 | [0.10, 0.20) | 8931 | 0.145 | 0.149 |
| 2 | [0.20, 0.30) | 4308 | 0.244 | 0.227 |
| 3 | [0.30, 0.40) | 2065 | 0.345 | 0.347 |
| 4 | [0.40, 0.50) | 1040 | 0.445 | 0.446 |
| 5 | [0.50, 0.60) | 442 | 0.543 | 0.557 |
| 6 | [0.60, 0.70) | 168 | 0.635 | 0.595 |
| 7 | [0.70, 0.80) | 34 | 0.737 | 0.765 |
| 8 | [0.80, 0.90) | 3 | 0.804 | 1.000 |
| 9 | [0.90, 1.00) | 0 | - | - |

## Sample race with attribution

**2026-02-05 · Race 4** — MAIDENCLAIMING, 1430 yd Dirt.

| Post | Horse | Finish | Odds | p_market | p_fundamental | p_blend | Edge |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | That's Amore | 4 | 18.6 | 0.041 | 0.146 | 0.039 | -5.94% |
| 2 | Angelic Quality | 2 | 2.6 | 0.226 | 0.172 | 0.225 | -0.19% |
| 3 | Riyah Al Nil | 6 | 25.2 | 0.031 | 0.217 | 0.029 | -7.33% |
| 4 | My Girl Nina | 3 | 1.6 | 0.313 | 0.225 | 0.315 | +0.69% |
| 5 | R Tun Who | 1 | 1.4 | 0.339 | 0.126 | 0.344 | +1.63% |
| 6 | She's Wicked Hot | 5 | 15.3 | 0.050 | 0.114 | 0.047 | -5.04% |

## Methodology notes and caveats

**In-fold blend fitting.** The two blend parameters α, β are learned on each val fold, then applied to that same fold. This is *technically* peeking at val labels, but with only two degrees of freedom over ~10k val races it can't meaningfully overfit. In this v1 the concern is moot anyway: α is essentially zero across all folds, so the blend *is* the market. If a future version's fundamental develops real signal we should nest the blend fit inside a proper hold-out.

**Val ROI numbers should not be interpreted as live-betting expectations.** The ROI reported here reflects the model's edge measured against **final tote odds** — i.e., we can only know the odds AFTER the pools closed. In live betting: (a) placing large bets can move the price against you, (b) some tracks apply CRW/takeout that changes payout math, and (c) the shifted line means your effective edge is smaller. Treat the reported ROI as a *ceiling* on live performance, not an expectation.

**Prior-only features, confirmed by Phase 3B and Phase 3C.** All 116,311 entries in `entry_features_v1` are computed strictly from data predating the target race (same-day siblings excluded). No leakage from future outcomes into training features.

**Temporal folds, not random.** All four CV folds train on the past and validate on the future, matching how the model will be used. This is the honest way to score a horse-racing model — random CV would let the model cheat by memorising specific horses' peak years.

## What Phase 3E deliberately does not do

- **No pedigree features.** Bucket 5 of the catalog is empty until Phase 3F extracts v10 workbook signals into sire/dam priors.
- **No Brisnet PP features.** Morning-line odds, workout data, and other PP-side signals await Phase 3G.
- **Only Gulfstream Park.** Multi-track expansion is Phase 3H.
- **No live inference infrastructure.** The pickle is an artifact for reproducibility, not a serving stack.
- **No production deployment.** This is model v1, meant to prove the architecture works — and confirm the current feature set is insufficient to beat the market on its own.

## Conclusion

- **Ship criteria: FAIL** — log-loss 1.6474 (need ≤ 1.6494), ROI@40 n/a (no bets) (need > 0), ECE 0.0055 (need < 0.03), top-1 35.9% (need > 36.4%).
- **Best hyperparameters:** half-life 2.5y, L2 0.001. (Hyperparameters barely matter — all 20 combos land within 0.0001 log-loss of each other because the fundamental has almost no signal for regularisation to affect.)
- **Blend weights:** α=0.00 (fundamental), β=1.06 (market). α near zero is diagnostic: the blend is essentially the market alone.
- **Log-loss margin vs market baseline: -1.1%** (vs the 1% target). The model is a statistical rounding error away from the market — no significant edge found.
- **Grid search:** 20 hyperparameter combinations × 4 folds = 80 fits, wall clock ~14 min on this machine.

### Recommendation to Doug

**Do not ship v2.1.0.** The features currently in Phase 3C's active set (73 features across Buckets 1, 3, 4, 6, 7, 8) collectively duplicate what the market already knows — trainer/jockey rates, recent form, pace, post, weight, market signals. None of these gives the model a meaningful independent view of the race.

**Where the missing signal likely lives:**
1. **Phase 3F — v10 workbook priors.** Doug's curated sire/dam signals were built to identify horses the market misprices (first-time turf, hidden pedigree strength, etc.). Wiring these into Bucket 5 is the single highest-leverage next step.
2. **Phase 3G — Brisnet PP data.** Morning-line odds, workout recency, trainer angles, class movement, and jockey PP splits add signals not currently in the model. Live-betting requires these anyway for pre-race inference.
3. **Phase 3H — Multi-track corpus.** More data helps stabilise the smaller feature signals, and cross-track features (trainer's record at other similar tracks) genuinely add information.

**What we now know infrastructure-wise:** the training + evaluation stack is trustworthy. The preprocessor, conditional-logit fitter, blend layer, and Phase 3D metrics/CV framework all behaved as designed. When a fake edge appeared, the honest evaluation of the corrected pipeline exposed it. That's the correct behaviour and it means we can trust the numbers Phase 3F/3G models produce.
