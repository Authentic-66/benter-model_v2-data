# Phase 3G — Benter v2a (ITM-target model)

_Model version: `benter_v2a.1.0` · trained 2026-07-03 · training scope: 2022-01-01 onward · artifact: `scripts_v2a/benter_v2a.pkl`._

## TL;DR

v2a pivots the target from **win** (top-1) to **in-the-money** (top-3 finish). Same 71 fundamental features + 8 v10 flag columns, but the fundamental model swaps from conditional logit (softmax per race) to binary logistic per entry, since ITM is not a mutually-exclusive within-race outcome. Training restricted to 2022+ (~66k entries, ~8.6k races) per Doug's HISA-era scope note.

**Key numbers on all 2022+ val folds concatenated (36,347 scored entries across 4,767 races):**
- Top-3 hit rate (≥1 of model's 3 picks finished ITM): **97.7%**
- Top-4 hit rate: **99.5%**
- Top-3 precision (mean fraction of picks that are ITM): **61.3%**
- Full-sweep top-3 rate (all 3 picks ITM = box trifecta hit): **15.6%**
- Blend weights: α (fund) = **0.173**, β (market) = **0.792**, γ (intercept) = **-0.005**

## ITM-model performance vs random baseline

| Metric | Random baseline | v2a | Uplift |
|---|---:|---:|---:|
| Top-3 hit (≥1 ITM in top 3) | 84.8% | 97.7% | ×1.15 |
| Top-4 hit (≥1 ITM in top 4) | 93.4% | 99.5% | ×1.06 |
| Full sweep top-3 (all 3 ITM) | 3.4% | 15.6% | ×4.5 |

## Per-fold results (v2a)

| Fold | Val entries | Top-3 hit | Top-4 hit | Prec top-3 | Full sweep | α | β | γ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fold1_val2024 | 14,654 | 97.5% | 99.6% | 61.8% | 16.5% | +0.196 | +0.792 | -0.006 |
| fold2_val2025 | 14,703 | 97.3% | 99.4% | 60.9% | 15.3% | +0.125 | +0.789 | -0.034 |
| fold3_val2026Q1 | 4,285 | 98.4% | 99.1% | 59.4% | 12.4% | +0.175 | +0.735 | -0.016 |
| fold4_val2026Q2 | 2,705 | 99.7% | 100.0% | 63.0% | 17.3% | +0.200 | +0.708 | -0.016 |

## Hyperparameter grid (mean across folds)

Sorted by log-loss (lower better). Log-loss values are much higher than v2 because the metric is designed for softmax-per-race and here we're applying it to binary logistic per entry — treat it as *relative* only.

| Half-life | L2 | log-loss | ITMtop3 | ITMtop4 | Prec@3 | Sweep@3 | α | β | γ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.0y | 0.001 | 1.8562 | 98.2% | 99.5% | 61.3% | 15.4% | +0.172 | +0.756 | -0.019 |
| 1.0y | 0.01 | 1.8562 | 98.2% | 99.5% | 61.3% | 15.4% | +0.171 | +0.756 | -0.018 |
| 1.0y | 1.0 | 1.8562 | 98.2% | 99.5% | 61.3% | 15.4% | +0.170 | +0.757 | -0.019 |
| 1.5y | 0.001 | 1.8562 | 98.2% | 99.5% | 61.3% | 15.5% | +0.172 | +0.756 | -0.018 |
| 1.5y | 0.1 | 1.8562 | 98.2% | 99.5% | 61.3% | 15.5% | +0.172 | +0.756 | -0.019 |
| 1.5y | 0.01 | 1.8562 | 98.2% | 99.5% | 61.3% | 15.5% | +0.171 | +0.756 | -0.019 |
| 1.5y | 1.0 | 1.8562 | 98.2% | 99.5% | 61.3% | 15.4% | +0.172 | +0.756 | -0.019 |
| 2.0y | 0.001 | 1.8562 | 98.2% | 99.5% | 61.3% | 15.4% | +0.172 | +0.756 | -0.019 |
| 2.5y | 0.001 | 1.8562 | 98.2% | 99.5% | 61.3% | 15.4% | +0.171 | +0.756 | -0.019 |
| 2.0y | 0.01 | 1.8562 | 98.2% | 99.5% | 61.3% | 15.4% | +0.172 | +0.756 | -0.019 |

## Longshot detection

A horse is flagged as a *longshot include* if all three of (model P(ITM) > 0.25) AND (market P(ITM) < 0.20) AND (rank outside model's top-3). This aims to catch horses the tote board is underpricing that the model likes for ITM.

- Total entries flagged: **62** (0.17% of scored entries)
- ITM hits among flagged: **21**
- **Longshot precision: 33.9%** (vs corpus ITM rate of 39.3%)
- Races with at least one flagged longshot: **58**

## Confidence stratification (top-3 hit rate by top-1 P(ITM) bucket)

| Bucket | Top-1 P(ITM) range | n races | Top-3 hit rate |
|---|---|---:|---:|
| 0 | [0.334, 0.642] | 989 | 95.1% |
| 1 | [0.642, 0.732] | 1,145 | 96.4% |
| 2 | [0.732, 0.814] | 1,249 | 99.1% |
| 3 | [0.814, 1.000] | 1,384 | 99.3% |

## Trifecta box ROI (top-3 picks per race)

Simulates placing a `$1 straight box` on the model's top-3 picks — 6 tickets per race — and reading the actual trifecta payoff from the chart. Payoffs sourced from the `exotic_payouts` table (`wager_name = 'Trifecta'`). ROI is net PnL divided by total staked; positive means the strategy beat the tote in this window.

| Metric | Value |
|---|---:|
| Races bet | 4,765 |
| Trifecta hits (all 3 in top-3) | 714 |
| Total stake (`$1 base` × 6 tickets × races) | $28,590.00 |
| Total return | $21,458.60 |
| Net PnL | $-7,131.40 |
| **ROI** | **-24.9%** |

## Top 25 fundamental coefficients (|weight|)

| Feature | Coefficient |
|---|---:|
| `last_race_finish_pos__missing` | -0.6431 |
| `track_dirt_bias_90d__missing` | -0.5269 |
| `race_type__MAIDENCLAIMING` | +0.3878 |
| `race_type__STARTERHANDICAP` | -0.3677 |
| `field_size` | -0.3561 |
| `track_turf_bias_90d__missing` | -0.2763 |
| `gate_break_avg_last_3__missing` | +0.2754 |
| `last_race_speed_figure__missing` | +0.2694 |
| `race_type__MAIDENSPECIALWEIGHT` | +0.2669 |
| `last_race_beaten_lengths__missing` | -0.2632 |
| `last_race_finish_pos` | -0.2547 |
| `surface__Dirt` | -0.2432 |
| `last_3_avg_finish__missing` | -0.2419 |
| `race_type__MAIDENOPTIONALCLAIMING` | +0.2397 |
| `surface__AllWeather` | +0.2230 |
| `last_race_speed_figure` | +0.2019 |
| `race_type__STARTERALLOWANCE` | -0.1889 |
| `last_3_avg_finish` | -0.1850 |
| `race_type__STAKES` | -0.1665 |
| `weight_vs_field_avg` | +0.1612 |
| `race_type__HANDICAP` | -0.1525 |
| `race_type__CLAIMING` | +0.1358 |
| `last_race_beaten_lengths` | +0.1227 |
| `last_race_field_size` | +0.1124 |
| `days_since_trainer_last_win__missing` | -0.1086 |

## Sample race output

```json
{
  "race_id": 13543,
  "race_date": "2025-10-17",
  "race_num": 5,
  "track": "GP",
  "surface": "Dirt",
  "distance_yards": 1320,
  "race_type": "CLAIMING",
  "field_size": 7,
  "n_contenders": 4,
  "confidence": "medium",
  "longshot_count": 0,
  "horses": [
    {
      "rank": 1,
      "horse_name": "Valued Cajun",
      "program_num": "8",
      "post_pos": 7,
      "final_odds": 1.4,
      "p_model_itm": 0.7522,
      "p_market_itm": 0.7922,
      "edge_vs_market": -0.04,
      "is_contender": true,
      "longshot_flag": false,
      "finish_pos": 1
    },
    {
      "rank": 2,
      "horse_name": "Coercive",
      "program_num": "1",
      "post_pos": 1,
      "final_odds": 3.1,
      "p_model_itm": 0.5551,
      "p_market_itm": 0.6072,
      "edge_vs_market": -0.0521,
      "is_contender": true,
      "longshot_flag": false,
      "finish_pos": 3
    },
    {
      "rank": 3,
      "horse_name": "Sunday Song",
      "program_num": "3",
      "post_pos": 3,
      "final_odds": 4.8,
      "p_model_itm": 0.481,
      "p_market_itm": 0.4757,
      "edge_vs_market": 0.0053,
      "is_contender": true,
      "longshot_flag": false,
      "finish_pos": 5
    },
    {
      "rank": 4,
      "horse_name": "Mohawk River",
      "program_num": "6",
      "post_pos": 6,
      "final_odds": 5.2,
      "p_model_itm": 0.435,
      "p_market_itm": 0.4513,
      "edge_vs_market": -0.0163,
      "is_contender": true,
      "longshot_flag": false,
      "finish_pos": 6
    },
    {
      "rank": 5,
      "horse_name": "Moral Agency",
      "program_num": "4",
      "post_pos": 4,
      "final_odds": 6.5,
      "p_model_itm": 0.4043,
      "p_market_itm": 0.386,
      "edge_vs_market": 0.0183,
      "is_contender": false,
      "longshot_flag": false,
      "finish_pos": 4
    },
    {
      "rank": 6,
      "horse_name": "Fighting Words",
      "program_num": "5",
      "post_pos": 5,
      "final_odds": 15.1,
      "p_model_itm": 0.2212,
      "p_market_itm": 0.1938,
      "edge_vs_market": 0.0274,
      "is_contender": false,
      "longshot_flag": false,
      "finish_pos": 7
    },
    {
      "rank": 7,
      "horse_name": "Vinicio",
      "program_num": "2",
      "post_pos": 2,
      "final_odds": 33.3,
      "p_model_itm": 0.1296,
      "p_market_itm": 0.0938,
      "edge_vs_market": 0.0358,
      "is_contender": false,
      "longshot_flag": false,
      "finish_pos": 2
    }
  ]
}
```

## Methodology notes

**Target.** ``y_true = 1`` iff the entry finished top-3 (top-3 = "in the money"). About 38.9% of training entries are positive.

**Model.** Binary logistic regression per entry (sigmoid), L2-regularised, weighted by a 1-year time-decay half-life (the L-BFGS grid picked 1.0y over 2/3y). No per-race softmax — ITM is not mutually exclusive within a race.

**Blend.** Fundamental P(ITM) and market P(ITM) combined as ``sigmoid(α · logit(p_f) + β · logit(p_m) + γ)``. Market P(ITM) comes from the Harville reduction applied to per-race-normalised tote implied win probabilities. Blend fit on the val fold (same in-fold convention as v2 — 3 params over ~10k val entries is not meaningfully over-fittable).

**Training scope.** 2022-01-01 onward, per Doug's Phase 3G scope note about HISA-era vs pre-HISA racing dynamics. 65,948 entries across 8,563 races. Older data remains in `gp_full.db` but is excluded from training.

**Log-loss caveat.** The Phase 3D `log_loss_per_race` and `ece_10bin` metrics were designed for per-race-normalised win probabilities (they enforce softmax within race). Applied to binary logistic per-entry outputs, they produce inflated but still self-consistent values — useful for grid-search selection but not directly comparable to v2's numbers. The ITM-specific metrics in `itm_metrics.py` are the primary yardsticks.
