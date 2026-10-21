# Stretch-run retrain ablation: results (2026-10-21)

Rules committed first (`a62eabe`, `RULES.md`); nothing trained before it.
Snapshot `racing_s.db` = live DB sha256 `3ad2c089…f881` + 4 columns
(`db_hashes.txt`). Full output: `eval_gate0.txt`, `eval_C1.txt`,
`eval_C2.txt`, `eval_C3.txt`, `reranker_check.txt`, arm logs.

**Nothing is promoted. `dpv1.pkl` and the rerankers are untouched.**

## Gate 0: PASS

`folds_c0.csv` is byte-identical to `_purse15/folds_a.csv` (md5
`e5678d35…`), the installed `dpv1.3.1-5track-clean`'s folds. The control
is the live model.

## Verdicts

| | comparison | top-pick ITM | McNemar | years + | fund log-loss | stretch-bucket error | verdict |
|---|---|---|---|---|---|---|---|
| **C1** | live -> s1 (raw) | **+0.49pp** (64.72 -> 65.20) | 501/411, **p 0.003** | **4/4** | -0.00065, **z -6.18** | 1.058 -> **0.441pp** | **PASS** |
| **C2** | live -> s2 (pace-adj) | +0.12pp | 321/298, p 0.38 | 3/4 (2024 = 0.00) | -0.00020, z -3.03 | 1.058 -> 0.552pp | PASS (marginal) |
| C3 | s1 -> s2 | -0.36pp | 248/315, p 0.005 | | +0.00046, z +6.37 | 0.441 -> 0.552 | s1 better |

Pre-registered tie-break: both pass, s2 does not beat s1 (it loses by
p 0.005), so **s1 is the candidate**.

## C1 (live -> s1) detail

* By track: GP +0.78 (p 0.004), CT +0.31, MNR +0.18, ELP 0.00, DED +0.61.
  Nothing negative. Fundamental log-loss better on GP (z -4.10), CT (-3.04),
  DED (-4.58), MNR (-1.39); ELP +0.00018 (z +0.53, n.s.).
* By year: +0.52, +0.48, +0.55, +0.34; log-loss better every year (z -2.1 to
  -4.3). Blended log-loss z -5.90. AUC 0.6953 -> 0.6962.
* The calibration error the investigation found is mostly gone: horses with
  last race's fastest stretch run were under-predicted by +3.08pp (z +8.8);
  under s1 +0.82pp (z +2.3). The slowest quarter goes from -1.30pp to +0.33.
* Overall calibration is mixed: own-decile error 0.483 -> 0.547pp (worse),
  fixed-bin 0.528 -> 0.525 (same); DED improves (0.703/0.515 ->
  0.651/0.387); GP, CT and MNR a little worse on both measures. Mean
  predicted minus actual barely moves (+0.13 -> +0.12pp).
* Coefficients (standardised): `last_str_gain` +0.065,
  `last_str_gain_rank_pct` -0.063 (0 = fastest, so both say "closed
  well = better"); the two missing indicators split -0.033 each.

## Why s2 is weaker

s2 subtracts the gain expected for a horse that far back at the stretch call
in a race with that early pace. That removes the stretch-call position
itself, which carries signal (being close at the eighth pole is good). The
early-pace part of the adjustment is small (across pace buckets the
expected-gain table moves ~1.5L for horses 10L+ back at the stretch call,
under 0.7L for everyone else).

## Reranker check (not a gate)

* pp-reranker-1.0 on top of s1: +5.2pp on 329 PP races (27/10, p 0.008) vs
  +5.5pp on top of live (26/8, p 0.003); log-loss -0.0046 vs -0.0048 (both
  z ~ -2.8). 259 of those races are its own training period. CV refit +2.1pp
  (p 0.25) vs +3.6pp (p 0.05).
* classctx-reranker-0.1 (shadow) on top of s1: +0.6pp (p 0.001), log-loss z
  -10.55, same as on live; DED +0.1pp vs +0.5pp (both n.s.).

## Feature parity (charts vs PP lines)

See `../diagnostics/stretch_run/pp_vs_chart.txt` (21 PP files: DED 10/10-10/17,
CT x6, GP x6, EVD x3, ELP x2).

| level | n | exact | within 0.25L | median diff | corr |
|---|---|---|---|---|---|
| line: BL at stretch call | 6,990 races, 1,295 horses | 57.1% | 95.8% | 0.00 | 0.9996 |
| line: BL at finish | 6,990 | 66.5% | 85.6% | 0.00 | 0.9997 |
| line: gain | 6,990 | 46.9% | 85.7% | 0.05 | 0.9991 |
| **feature: `last_str_gain`** (today's value, PP most recent line vs charts) | 677 | 50.5% | 87.9% | 0.00 | **0.9989** |
| feature: `last_str_gain_padj` (PP uses pooled pace by design) | 677 | 5.8% | 75.6% | 0.09 | 0.9925 |

The differences are rounding: Brisnet prints lengths behind as whole lengths
beyond ~10L and to the quarter below, while the chart sum keeps heads and
necks (e.g. 12.0 vs 12.75). Nearly every pair is within 1L; the one
outlier (Honor the Bull, CT 2026-05-09: stretch call 14 vs 10.1L) looks like
a chart/PP disagreement in that race, not a formula difference. Ranks
cannot be computed from a PP line (one horse).

## Before s1 could go live (needs Doug)

1. **Approve or not.** The evidence is a ranking gain (+0.49pp, p 0.003,
   4/4 years) with better log-loss, plus a large fix to the bucket error,
   at the cost of slightly worse overall own-decile calibration.
2. **Live path, not built yet:** the feature builder computing the two s1
   columns (output must equal `racing_s.db` on every row), and the bridge.
3. **Bridge decision** (RULES "open live-path decision"): a PP line gives the
   gain but never the rank, and in training both are missing together (the
   model split their missing-indicator weight evenly). Options: bridge
   neither for PP-only horses (exact training semantics), or bridge the gain
   and fill the rank from a fitted gain -> rank map.
4. Promotion would restart the live record window (`model_health --model`).
