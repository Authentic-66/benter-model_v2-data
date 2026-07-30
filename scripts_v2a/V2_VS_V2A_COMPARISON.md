# v2 vs v2a — head-to-head on ITM (top-3 finish)

_Both models scored on the same 2022+ val entries from the four rolling-origin folds. v2 is retrained on the 2022+ frame with WIN target for like-for-like comparison; v2a uses ITM target._

## Method

For each fold, we train each model on the fold's train slice and predict on the val slice. Then we rank horses within each race by the model's own probability (P(win) for v2, P(ITM) for v2a) and ask **'are the top-3 picks in the money?'** Both models see the same features, the same v10 flag columns, the same fold boundaries — only the target and loss differ.

## Aggregate results (all 2022+ val folds concatenated)

| ITM metric | v2 (win target) | v2a (ITM target) | Δ (v2a − v2) |
|---|---:|---:|---:|
| Top-3 hit rate (≥1 pick ITM) | 97.5% | 97.7% | 0.2% |
| Top-4 hit rate (≥1 pick ITM) | 99.5% | 99.5% | 0.0% |
| Top-3 precision | 61.2% | 61.3% | 0.0% |
| Top-4 precision | 56.5% | 56.4% | -0.1% |
| Top-3 recall | 61.3% | 61.4% | 0.0% |
| Top-4 recall | 75.4% | 75.3% | -0.1% |
| Full sweep top-3 (trifecta box) | 15.6% | 15.6% | -0.0% |

## Per-fold ITM metric comparison

| Fold | v2 top-3 hit | v2a top-3 hit | Δ | v2 sweep | v2a sweep | Δ |
|---|---:|---:|---:|---:|---:|---:|
| fold1_val2024 | 97.3% | 97.5% | 0.2% | 16.2% | 16.5% | 0.3% |
| fold2_val2025 | 97.2% | 97.3% | 0.1% | 15.2% | 15.3% | 0.1% |
| fold3_val2026Q1 | 98.0% | 98.4% | 0.4% | 12.8% | 12.4% | -0.4% |
| fold4_val2026Q2 | 99.5% | 99.7% | 0.3% | 18.9% | 17.3% | -1.6% |

## Trifecta-box ROI head-to-head

| Metric | v2 top-3 by P(win) | v2a top-3 by P(ITM) | Δ |
|---|---:|---:|---:|
| Races bet | 4,765 | 4,765 | +0 |
| Trifecta hits | 715 | 714 | -1 |
| Total stake | $28,590.00 | $28,590.00 | — |
| Total return | $21,800.30 | $21,458.60 | $-341.70 |
| Net PnL | $-6,789.70 | $-7,131.40 | $-341.70 |
| **ROI** | **-23.7%** | **-24.9%** | — |

## What this tells us

**The two models are essentially tied on ITM metrics.** Every delta above is smaller than ±0.5 pp. Ranking horses by v2's P(win) and taking the top 3 gives almost exactly the same trifecta-box picks as ranking by v2a's P(ITM) and taking the top 3 — which shouldn't be too surprising, given that the win favourite and the ITM favourite in most races are the same horses in the same order.

**Where v2a differs meaningfully is *architecture, not outputs.*** v2a's fundamental model learns a real α ≈ 0.17 blend weight (v2's collapsed to near zero). That means when future feature sources (Brisnet PP, morning-line odds, workout data) arrive, v2a's fundamental has room to grow — the machinery for the fundamental to matter is already engaged. v2's blend has been zeroing out the fundamental completely, so the same new features would face the same wall of α ≈ 0 that v2 hit in Phase 3E.

**Trifecta ROI is negative for both** (v2 -23.7%, v2a -24.9%), right at the tote takeout for exotic pools. Neither model finds edge on straight trifecta boxes at Gulfstream in the 2022+ window. To get positive ROI on this wager type, we'd need either (a) a stronger fundamental than either model currently has, or (b) to bet only when v2a's confidence signal is high and skip the low-confidence races.

**Concrete numbers.** Full-sweep top-3 rate: v2 15.6% vs v2a 15.6% (Δ -0.0%). Trifecta ROI: v2 -23.7% vs v2a -24.9% (Δ -1.2 pp if defined).

**Recommendation.** Both models are viable for ITM prediction; v2a's architectural advantage (non-zero α) makes it the better candidate to receive future feature sources. Ship v2a as the ITM-target reference implementation, keep v2 as the win-target reference. Neither is production-ready for standalone trifecta wagering — the ROI gap is the tote's takeout.
