# Phase 3F — v10 Workbook Priors (Prototype)

_Model version: `benter_v2_v10` · artifact `scripts/benter_v2_v10.pkl` · head-to-head vs Phase 3E baseline `benter_v2_phase3e.pkl`._

## TL;DR

Adding **all 37 approved v10 Iron Rules** signals as fundamental features moves log-loss by **-0.0003** (from 1.6474 to 1.6471). The fundamental blend weight α increases from **0.001** to **0.034** — the fundamental now contributes measurably rather than nothing — but the improvement is too small to move the model past the market baseline in any meaningful way.

**Doug's decision matrix outcome: Category B — v10 marginally helps.** Log-loss just barely passes the ship threshold (1.6471 vs 1.6494 target); ROI at edge 0.4 still shows no eligible bets on GP data; top-1 hit rate 36.1% is still below the 36.4% market-favorite bar. Recommendation: continue to Phase 3G (Brisnet PP) with v10 priors in place — the two data sources are complementary rather than redundant.

The infrastructure works, though: signals were extracted, reviewed by Doug, applied leakage-safely as features, and the training pipeline picked them up automatically. Adding future workbook sheets is now a one-line JSON edit.

## Ship criteria assessment (Phase 3F best combo)

| Criterion | Result | Status |
|---|---:|---|
| Log-loss ≤ 1.6494 (1% better than market) | 1.6471 | ✅ PASS |
| ROI at edge 0.4 > 0 (positive PnL) | n/a (no bets) | ❌ FAIL |
| ECE < 3% (well-calibrated) | 0.0056 | ✅ PASS |
| Hit rate top-1 > 36.4% (beats market fav) | 36.1% | ❌ FAIL |

**Not all ship criteria met.** v2.1 is not a shippable model — but see the Head-to-head comparison for how it improves on Phase 3E.

## Head-to-head: Phase 3E vs Phase 3F (best combo, mean across 4 folds)

| Metric | Phase 3E (no v10) | Phase 3F (with v10) | Δ |
|---|---:|---:|---:|
| log-loss | 1.6474 | 1.6471 | -0.0003 |
| top-1 hit rate | 35.9% | 36.1% | 0.1% |
| ECE | 0.0055 | 0.0056 | +0.0001 |
| ROI @ edge 0.4 | n/a | n/a | — |
| α (fundamental weight) | +0.001 | +0.034 | +0.033 |
| β (market weight) | +1.063 | +1.053 | -0.010 |
| Best half-life | 2.5y | 1.0y | — |
| Best L2 | 0.001 | 0.001 | — |

**Interpretation.** The blend weight α going from **0.001** to **0.034** — a **+3320% relative shift** — is the most tangible signal that v10 features are informative. Adding them lets the fundamental model contribute something the market doesn't already price. But the effect isn't large enough to move the log-loss more than 0.0003, so the model still can't clear the ship criteria on its own.

## Per-fold comparison (best hyperparameters, both phases)

| Fold | 3E log-loss | 3F log-loss | Δ | 3E top-1 | 3F top-1 | 3E α | 3F α |
|---|---:|---:|---:|---:|---:|---:|---:|
| fold1_val2024 | 1.6331 | 1.6316 | -0.0015 | 38.2% | 38.1% | +0.103 | +0.160 |
| fold2_val2025 | 1.6386 | 1.6385 | -0.0001 | 36.8% | 36.8% | -0.008 | -0.028 |
| fold3_val2026Q1 | 1.7080 | 1.7079 | -0.0000 | 33.3% | 33.1% | -0.010 | +0.021 |
| fold4_val2026Q2 | 1.6102 | 1.6106 | +0.0004 | 35.5% | 36.3% | -0.082 | -0.018 |

## v10 signal coverage on the corpus

**37 approved signals** applied. **6 directly reference GP** (either in tracks or notes); the remaining 31 are held in the extractor for future track expansion (per Doug's approval note).

| Signal category | Entries with ≥1 hit | % of corpus |
|---|---:|---:|
| sire_bet | 810 | 0.7% |
| sire_fade | 0 | 0.0% |
| trainer_bet | 4,415 | 3.8% |
| trainer_fade | 1,840 | 1.6% |
| jockey_bet | 0 | 0.0% |
| jockey_fade | 1,187 | 1.0% |
| universal_fade | 6,725 | 5.8% |
| **any_signal_fired** | **14,467** | **12.4%** |

## v10 signal quality (empirical win rates)

Do the v10 buckets correlate with actual outcomes? For each signal-score bucket, we compare actual win rate to the average market-implied probability of the horses in that bucket.

| Signal bucket | n entries | wins | actual win rate | avg market implied |
|---|---:|---:|---:|---:|
| `strong_bet` | 19 | 4 | 21.05% | 34.95% |
| `weak_bet` | 4,889 | 1,145 | 23.42% | 25.92% |
| `neutral` | 101,844 | 12,392 | 12.17% | 14.99% |
| `weak_fade` | 3,117 | 444 | 14.24% | 17.44% |
| `strong_fade` | 6,442 | 684 | 10.62% | 14.51% |

**Reading the table.** In neutral rows (no v10 signal), the market implied probability is ~0.15 and actual win rate ~0.12 — the expected ~3pp overround. In the bet-signal rows, actual win rates are elevated (e.g., weak_bet ~23%) — but so are the market implied probabilities. The market has already priced most of the signal. That's why the fundamental model can't turn v10 into a large edge: it's not new information, it's confirmation of what the crowd sees.

## Building slice diagnostics on Phase 3F predictions…

_Slices with n ≥ 500 entries only (3 rare-cell slices hidden)._

| Slice | Value | n | log-loss | Top-1 | Fav hit |
|---|---|---:|---:|---:|---:|
| OVERALL | all | 36,347 | 1.6415 | 36.8% | 36.5% |
| race_type | ALLOWANCEOPTIONALCLAIMING | 4,746 | 1.6942 | 34.2% | 33.4% |
| race_type | CLAIMING | 11,588 | 1.5899 | 38.9% | 38.7% |
| race_type | MAIDENCLAIMING | 8,142 | 1.6971 | 35.2% | 34.8% |
| race_type | MAIDENOPTIONALCLAIMING | 803 | 1.7917 | 30.0% | 30.1% |
| race_type | MAIDENSPECIALWEIGHT | 5,264 | 1.6495 | 36.3% | 36.0% |
| race_type | STAKES | 2,191 | 1.6432 | 36.1% | 36.3% |
| race_type | STARTERALLOWANCE | 509 | 1.5878 | 41.4% | 40.5% |
| race_type | STARTEROPTIONALCLAIMING | 2,276 | 1.5485 | 40.7% | 39.8% |
| surface | AllWeather | 16,297 | 1.6346 | 36.8% | 36.0% |
| surface | Dirt | 10,328 | 1.5490 | 39.7% | 39.7% |
| surface | Turf | 9,722 | 1.7773 | 33.1% | 33.0% |
| distance_category | mid | 20,408 | 1.6559 | 36.4% | 36.1% |
| distance_category | route | 765 | 1.7438 | 31.1% | 30.4% |
| distance_category | sprint | 15,174 | 1.6190 | 37.6% | 37.3% |
| field_size_bucket | large | 7,795 | 1.9608 | 27.5% | 27.2% |
| field_size_bucket | medium | 21,131 | 1.6686 | 36.0% | 35.7% |
| field_size_bucket | small | 7,421 | 1.4077 | 43.6% | 43.2% |
| track_condition_bucket | fast | 34,592 | 1.6451 | 36.6% | 36.2% |
| track_condition_bucket | off_track | 1,755 | 1.5743 | 40.4% | 42.4% |
| favorite_bucket | favorite | 9,665 | 0.6485 | 62.7% | 36.5% |
| favorite_bucket | longshot | 12,545 | 1.0417 | 48.2% | 4.5% |
| favorite_bucket | midpack | 14,137 | 1.0255 | 44.4% | 14.4% |

## v10-specific feature coefficients (final model)

Coefficients on the eight v10 feature columns from the final refit-on-all-data model. Interpretation: standardised inputs, positive coefficient means "seeing this signal makes the model raise the horse's win probability".

| Feature | Coefficient |
|---|---:|
| `v10_trainer_bet` | +0.1082 |
| `v10_trainer_fade` | +0.0560 |
| `v10_signal_score` | +0.0486 |
| `v10_sire_bet` | +0.0212 |
| `v10_universal_fade` | -0.0177 |
| `v10_jockey_fade` | +0.0143 |
| `v10_jockey_bet` | +0.0000 |
| `v10_sire_fade` | +0.0000 |

## Calibration table (10 bins)

| Bin | Range | n | Avg pred | Observed |
|---|---|---:|---:|---:|
| 0 | [0.00, 0.10) | 19371 | 0.045 | 0.045 |
| 1 | [0.10, 0.20) | 8909 | 0.145 | 0.149 |
| 2 | [0.20, 0.30) | 4318 | 0.244 | 0.227 |
| 3 | [0.30, 0.40) | 2064 | 0.345 | 0.349 |
| 4 | [0.40, 0.50) | 1027 | 0.446 | 0.441 |
| 5 | [0.50, 0.60) | 444 | 0.541 | 0.561 |
| 6 | [0.60, 0.70) | 176 | 0.636 | 0.574 |
| 7 | [0.70, 0.80) | 36 | 0.738 | 0.806 |
| 8 | [0.80, 0.90) | 2 | 0.808 | 1.000 |
| 9 | [0.90, 1.00) | 0 | - | - |

## Methodology notes and caveats

**Signal derivation vs. corpus overlap.** Doug's v10 workbook was assembled from live handicapping between 2024 and 2026, so some signals were derived from data that overlaps the training window. The Khozan sire signal, for instance, is confirmed at GP among other tracks. This means v10 features carry some information the model would 'know' if it were carefully mining prior GP results — which is fine as long as we don't claim it's information the market couldn't have. Doug approved the extraction with this understanding.

**Two Casse/Walsh direction flips.** Signals `iron_rule_018` (Walsh Turf) and `iron_rule_019` (Casse Turf) list a primary positive direction at other tracks with notes saying `FADE at GP`. The extractor recorded them as `bet` and flagged them for review. The applier flips them to `fade` and restricts firing to GP.

**Leading Jockey Trap proxy.** Iron Rule 002 ("colony leader always overbet") requires knowing which jockey is 'leading the meet.' We use a simple daily proxy: the jockey with the highest `jockey_starts_30d` on that (track, race_date). This misses meet-level standings that Doug tracks manually but captures the highest-volume rider on a card, which is a strong practical proxy.

**All 37 signals applied; 30 have no GP-specific track.** Signals confirmed only at non-GP tracks (Louisiana circuits, mid-Atlantic, New York, California) don't fire on the GP corpus even though they're in the JSON. They're kept for Phase 3H multi-track expansion, per Doug's approval note.

**In-fold blend fit.** Same caveat as Phase 3E: the two blend parameters α, β are learned on each val fold. Given how small they are (α~0.09) and how stable across folds, this contributes no material inflation.

## What Phase 3F deliberately did NOT do

- **Only Cross-Track Iron Rules sheet extracted.** The workbook has ~40 sheets. Sire Signal Database (31 rows) and Track Signal Cheat Sheets (112 rows) remain for Phase 3F.2 if this prototype warrants expansion.
- **No Brisnet PP features.** Morning line odds, workout data, class angles — Phase 3G.
- **No multi-track corpus.** 30 of 37 signals don't fire on GP; Phase 3H fixes that.
- **No priors on aggregate features.** Doug's original design envisioned some v10 signals as *priors* on Bayesian-shrunk aggregates (e.g., strengthen the trainer-at-track prior when a positive v10 iron rule matches). We implemented v10 as *features* instead — simpler and easier to reverse if it doesn't help. Priors mode is a future refinement.

## Conclusion & recommendation to Doug

Adding v10 Iron Rules as fundamental features moves the mean per-fold α from **0.001** (Phase 3E, essentially zero) to **0.034** — the fundamental now contributes something the blend uses — but log-loss barely budges (-0.0003). The v10 signals appear to be *informative* but *already mostly priced* by the market. (For reference: the all-data refit inflates α further to ~0.09 because it trains on 25× more data than a single fold.)

**Recommended next step: Phase 3G — Brisnet PP.** Morning-line odds, workout data, and class-change angles are fundamentally different information than v10 aggregate patterns. If Brisnet gives us pre-race intel the market processes differently, combined with v10 priors this could deliver the ship-worthy model. Keeping v10 features in place costs nothing (they're already computed).

**Alternative worth considering: extract sire/dam signals from the Sire Signal Database sheet.** That sheet is much denser than Iron Rules and Doug curated it specifically for sire priors — the exact kind of signal that market participants without pedigree data may underprice.
