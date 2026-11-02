# DED paired comparison — 1.3.0 vs 1.3.2, with and without the reranker (2026-11-01)

The question: keep `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` as it is,
turn the reranker off, or roll back to `dpv1.3.0-5track`.

This is a read-only comparison. Nothing changed in the live DB, the models,
the rerankers or protected code, and nothing is changed because of it.

**Short answer: keep 1.3.2 as it is.** There is no case for a rollback. The
reranker evidence is mixed, and the sample is far too small to act on in
either direction. Details and caveats below.

## What was run

* **Cards:** the five DED cards scored on 1.3.2 and its reranker: 10/23,
  10/24, 10/28, 10/29, 10/30. That is **43 races and 370 starters.** All five
  are out of sample for both models (1.3.0 was trained 9/19 and 1.3.2 on
  10/21).
* **Arms**, all run on the same entries:

  | arm | model | reranker |
  |---|---|---|
  | **A** | 1.3.0 (`dpv1_20260919_040326_retired.pkl`, sha 70b529db…7ff1) | pp-reranker-1.0 |
  | **A0** | 1.3.0 | off |
  | **B** (live) | 1.3.2 (`dpv1.pkl`, sha 33bfb329…a918) | pp-reranker-1.0 |
  | **C** | 1.3.2 | off |

  The reranker is `dpv1_pp_reranker.pkl` (sha cd4a5c79…29ea). Classctx stayed
  off, as it is live. Every run used the PP bridge (`--pp-file`), seed 6001
  and 10,000 simulations, the same as the nightly runs.
* **Pre-race DBs.** Each card's `scripts/racing_full.db.dedMMDD-run.bak` turned
  out to be the DB from **just before** that card's PP load, so none of them
  contains its own card. For each card the backup was copied to the
  scratchpad (the live DB was never opened for writing), and the nightly
  steps were re-run on the copy: `load_pp_card.py load ded<MMDD>y.pdf`,
  `speed_figures_dpv1.py compute`, `feature_builder_dpv1.py build`. Then the
  copy was deleted.
* **Reproduction check, passed on every card.** On the rebuilt copy, 1.3.2
  with the reranker, run on the full pre-race field, reproduced the logged
  record run row for row: P(ITM), P(win), base P(ITM) and rank. The largest
  difference was 1e-16, with 0 rank mismatches.

  | card | backup (sha256) | rebuilt feature rows | record run | rows reproduced |
  |---|---|---|---|---|
  | 10/23 | `ded1023-run.bak` (452684120cb4…) | 318,934 | 10/23 09:29:50 | 82/82 |
  | 10/24 | `ded1024-run.bak` (311a8078c27a…) | 319,006 | 10/23 22:30:26 | 79/79 |
  | 10/28 | `ded1028-run.bak` (bd038ec0c092…) | 319,080 | 10/28 14:33:40 | 82/82 |
  | 10/29 | `ded1029-run.bak` (101d5aa471bd…) | 319,144 | 10/29 15:06:13 | 75/75 |
  | 10/30 | `ded1030-run.bak` (7b6e165f0d7d…) | 319,236 | 10/30 14:47:18 | 100/100 |

* **Two ways of handling scratches**, both graded on `official_finish_pos`
  from the loaded charts:
  * **Drop:** the scratched horses (48 across the five cards) are removed from
    each card *before* scoring, so the model simulates the field that
    actually ran. P(win) and P(ITM) are then proper probabilities over the
    runners. The field-relative features keep their pre-race values; they
    are not rebuilt for the smaller field.
  * **Re-rank:** the model is scored on the pre-race field and its order is
    re-ranked among the horses that ran. This is the nightly review method.
    For calibration, P(win) is renormalised to sum to 1 over the runners and
    P(ITM) is scaled to sum to 3, capped at 0.999. That is an approximation.
  * Check: the re-rank method for arm B gives **7 wins, 22 ITM and 2
    exacta-box hits**, which is exactly the sum of the five nightly reviews.
* **Metrics.** "#1" is the top P(ITM) pick. ROI is from the chart's $2 win
  and $2 show payoffs. "Top-3 overlap" counts model top-3 horses that
  finished in the top 3, out of 3 per race. The exacta box is the model's
  top two by P(ITM), at $1 per combination ($2 per race), paid from the
  chart's $1 exacta. Log loss (LL) and Brier score are per starter for the
  binary events win and ITM; lower is better. Paired differences use a
  bootstrap over races (20,000 resamples). #1 hit differences use an exact
  McNemar test on the discordant races.

## Overall results

**Drop method** (scratches removed before scoring):

| arm | #1 W | #1 ITM | $2 win ROI | $2 show ROI | top-3 overlap | exacta box hits | $1 exacta ROI | LL win | Brier win | LL ITM | Brier ITM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A 1.3.0 + rr | 7 | 21 | −58.1% | −34.2% | 64/129 | 2 | −66.4% | 0.3478 | 0.1006 | 0.5976 | 0.2062 |
| A0 1.3.0, no rr | 9 | 22 | −29.8% | −27.0% | 62/129 | 3 | −52.8% | 0.3476 | 0.1004 | 0.6020 | 0.2077 |
| **B 1.3.2 + rr (live)** | 8 | **23** | −44.7% | −25.8% | **66/129** | 2 | −66.4% | 0.3472 | 0.1004 | **0.5951** | **0.2052** |
| C 1.3.2, no rr | 8 | 22 | −33.7% | **−24.0%** | 64/129 | 3 | −52.8% | **0.3471** | **0.1003** | 0.5997 | 0.2067 |

**Re-rank method** (nightly method):

| arm | #1 W | #1 ITM | $2 win ROI | $2 show ROI | top-3 overlap | exacta box hits | $1 exacta ROI | LL win | Brier win | LL ITM | Brier ITM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A 1.3.0 + rr | 6 | 21 | −65.1% | −33.7% | 62/129 | 2 | −66.4% | 0.3473 | 0.1006 | 0.5997 | 0.2072 |
| A0 1.3.0, no rr | 8 | 22 | −36.7% | −26.5% | 64/129 | 3 | −52.8% | 0.3471 | 0.1003 | 0.6033 | 0.2083 |
| **B 1.3.2 + rr (live)** | 7 | 22 | −51.6% | −30.0% | **66/129** | 2 | −66.4% | 0.3468 | 0.1004 | **0.5968** | **0.2060** |
| C 1.3.2, no rr | 8 | 22 | −36.7% | −26.5% | 65/129 | 3 | −52.8% | **0.3466** | **0.1002** | 0.6007 | 0.2072 |

**For reference, the market**, on the same 43 races: the post-time favourite
won 16 and was in the money in 32, at −7.0% $2 win ROI and −4.0% $2 show ROI.
P(win) from the final odds has LL win 0.3006 and Brier win 0.0886. Every arm
is far behind the market on P(win). That is expected, since the model never
sees odds. It is the same for all four arms and doesn't separate them.

**How uncertain the ROI figures are** (95% bootstrap interval, drop method):
B win −45% [−79%, −3%] and show −26% [−47%, −4%]; C win −34% [−76%, +18%]
and show −24% [−47%, 0%]. A gap of 10–20 points between arms sits well
inside these intervals.

## Per card (drop method; re-rank #1 W/ITM shown alongside)

| card | arm | #1 W | #1 ITM | re-rank W/ITM | $2 win ROI | $2 show ROI | top-3 overlap | exacta box hits | LL win | LL ITM |
|---|---|---|---|---|---|---|---|---|---|---|
| 10/23 (9 r, 75 st) | A | 0 | 2 | 0/2 | −100% | −65.6% | 12/27 | 0 | 0.3621 | 0.6612 |
| | A0 | 0 | 2 | 0/2 | −100% | −65.6% | 13/27 | 1 | 0.3600 | 0.6596 |
| | B | 0 | 2 | 0/2 | −100% | −65.6% | 12/27 | 0 | 0.3610 | 0.6571 |
| | C | 0 | 2 | 0/2 | −100% | −65.6% | 13/27 | 1 | 0.3588 | 0.6560 |
| 10/24 (9 r, 71 st) | A | 1 | 5 | 1/5 | −74.4% | −29.4% | 14/27 | 1 | 0.3702 | 0.5681 |
| | A0 | 1 | 6 | 1/6 | −22.2% | −0.6% | 14/27 | 1 | 0.3703 | 0.5707 |
| | B | 1 | 6 | 1/5 | −74.4% | −7.2% | 16/27 | 1 | 0.3688 | 0.5622 |
| | C | 1 | 6 | 1/6 | −22.2% | −0.6% | 15/27 | 1 | 0.3686 | 0.5645 |
| 10/28 (8 r, 71 st) | A | 3 | 4 | 3/4 | −8.7% | −32.5% | 11/24 | 1 | 0.3172 | 0.5851 |
| | A0 | 4 | 4 | 4/4 | +12.5% | −33.8% | 11/24 | 1 | 0.3143 | 0.5952 |
| | B | 3 | 4 | 3/4 | −8.7% | −32.5% | 12/24 | 1 | 0.3164 | 0.5811 |
| | C | 3 | 3 | 4/4 | −8.7% | −48.8% | 12/24 | 1 | 0.3141 | 0.5919 |
| 10/29 (8 r, 67 st) | A | 1 | 4 | 0/4 | −62.5% | −30.0% | 14/24 | 0 | 0.3391 | 0.5679 |
| | A0 | 2 | 5 | 1/5 | +10.0% | −8.8% | 13/24 | 0 | 0.3439 | 0.5704 |
| | B | 2 | 5 | 1/5 | +10.0% | −10.0% | 14/24 | 0 | 0.3382 | 0.5677 |
| | C | 2 | 6 | 1/5 | +10.0% | +22.5% | 14/24 | 0 | 0.3432 | 0.5698 |
| 10/30 (9 r, 86 st) | A | 2 | 6 | 2/6 | −40.0% | −12.8% | 13/27 | 0 | 0.3487 | 0.5999 |
| | A0 | 2 | 5 | 2/5 | −40.0% | −25.0% | 11/27 | 0 | 0.3484 | 0.6079 |
| | B | 2 | 6 | 2/6 | −40.0% | −12.8% | 12/27 | 0 | 0.3497 | 0.6013 |
| | C | 2 | 5 | 2/5 | −40.0% | −25.0% | 10/27 | 0 | 0.3496 | 0.6093 |

Brier columns are in `paired_2026-11-01/analysis_output.txt`; they rank the
arms the same way as LL. Each card has 8–9 races, so a single card can't
tell the arms apart. 10/23 is identical for all four arms on #1 results.

## Paired differences (first arm minus second; 95% CI over the 43 races)

| comparison | method | #1 ITM (only first / only second, p) | #1 win | $2 win return per race | $2 show return per race | LL ITM per starter | LL win per starter |
|---|---|---|---|---|---|---|---|
| **B − C** (reranker on 1.3.2) | drop | 2 / 1, p 1.00 | 1 / 1 | −0.22 [−0.98, +0.32] | −0.04 [−0.35, +0.21] | −0.0046 [−0.0124, +0.0031] | +0.0000 [−0.0045, +0.0044] |
| | re-rank | 2 / 2, p 1.00 | 1 / 2 | −0.30 [−1.06, +0.21] | −0.07 [−0.35, +0.18] | −0.0039 [−0.0123, +0.0042] | +0.0002 [−0.0044, +0.0048] |
| **B − A** (1.3.2 vs 1.3.0, both with rr) | drop | 2 / 0, p 0.50 | 1 / 0 | +0.27 [0.00, +0.81] | +0.17 [−0.01, +0.43] | −0.0024 [−0.0058, +0.0010] | −0.0006 [−0.0030, +0.0018] |
| | re-rank | 1 / 0, p 1.00 | 1 / 0 | +0.27 [0.00, +0.81] | +0.07 [−0.01, +0.24] | −0.0030 [−0.0068, +0.0009] | −0.0005 [−0.0029, +0.0019] |
| **C − A** (1.3.2 no rr vs 1.3.0 with rr) | drop | 3 / 2, p 1.00 | 2 / 1 | +0.49 [−0.21, +1.41] | +0.20 [−0.12, +0.59] | +0.0021 [−0.0073, +0.0114] | −0.0006 [−0.0058, +0.0048] |
| | re-rank | 3 / 2, p 1.00 | 3 / 1, p 0.62 | +0.57 [−0.13, +1.52] | +0.14 [−0.15, +0.47] | +0.0009 [−0.0092, +0.0112] | −0.0007 [−0.0061, +0.0050] |
| A − A0 (reranker on 1.3.0) | drop | 2 / 3, p 1.00 | 1 / 3, p 0.62 | −0.57 [−1.51, +0.13] | −0.14 [−0.47, +0.15] | −0.0044 [−0.0125, +0.0034] | +0.0002 [−0.0044, +0.0046] |
| C − A0 (1.3.2 vs 1.3.0, both no rr) | drop | 1 / 1, p 1.00 | 0 / 1 | −0.08 [−0.24, 0.00] | +0.06 [−0.17, +0.35] | −0.0023 [−0.0055, +0.0009] | −0.0005 [−0.0029, +0.0020] |

Negative LL is better for the first arm. **Every confidence interval above
includes zero**, and no McNemar p-value is below 0.5.

## Head-to-head where the #1 picks differ (drop method)

**B vs C, reranker on/off on 1.3.2: 9 of 43 races.**

| card | R | B (with reranker) | C (without) |
|---|---|---|---|
| 10/24 | 4 | #10 Millie's Stardust 1.3-1, 2nd | **#5 Crusin Likea Cat 6.0-1, 1st** |
| 10/24 | 5 | **#5 Polar Wolf 1.3-1, 1st** | #1 Not Behavin 2.7-1, 3rd |
| 10/24 | 8 | #2 La Foret 9.7-1, 4th | #3 Kaydences Calamity 3.3-1, 5th |
| 10/28 | 1 | #10 Ripple's Rocket 2.1-1, 2nd | #9 That's Apriority 13.3-1, 7th |
| 10/28 | 4 | #9 All West 6.2-1, 5th | #3 Z's Guitar 23.5-1, 7th |
| 10/28 | 5 | #4 Alyse Parker 5.0-1, 4th | #1 Exploding Circle 2.0-1, 6th |
| 10/29 | 2 | #9 Tensas Camp Road 14.6-1, 8th | #8 Breaking Star 4.4-1, 3rd |
| 10/29 | 7 | #7 Tortuga Coast 2.1-1, 3rd | #4 Jewlz 3.5-1, 2nd |
| 10/30 | 1 | #6 The Get Out 2.3-1, 3rd | #3 Mediator 39.8-1, 9th |

B: 1 win, 5 ITM; $2 win returned $4.60 and $2 show $12.60 on $18 each.
C: 1 win, 4 ITM; $2 win returned $14.00 and $2 show $14.20.
ITM head-to-head: B only 2, C only 1, both 3, neither 3. Under the re-rank
method the reranker also changes 9 #1s (10/24 R6 and 10/28 R8 come in, 10/28
R4 and 10/29 R2 drop out): B 1W/5ITM ($4.60 / $12.60) vs C 2W/5ITM ($17.40 /
$15.60). C's extra win is 10/28 R8 Marks Legacy at 0.7-1.

**The win-ROI gap between B and C (drop) is the net of two races:** in 10/24
R4 the reranker moved off the 6-1 winner, Crusin Likea Cat ($14.00), onto the
1.3-1 favourite, which ran 2nd. In 10/24 R5 it moved onto the 1.3-1 winner,
Polar Wolf ($4.60). On ITM the reranker is +1 race (drop) or level (re-rank).

**B vs A, 1.3.2 vs 1.3.0, both with the reranker: 3 of 43 races** (drop).

| card | R | B 1.3.2 | A 1.3.0 |
|---|---|---|---|
| 10/24 | 6 | #2 Robbiesstormangel 3.8-1, 3rd | #9 Our Majestic 6.8-1, 4th |
| 10/29 | 5 | **#7 Highstakes Hustler 4.8-1, 1st** | #3 Hedge 1.8-1, 5th |
| 10/29 | 7 | #7 Tortuga Coast 2.1-1, 3rd | #4 Jewlz 3.5-1, 2nd |

B: 1W/3ITM ($11.60 win, $10.20 show on $6). A: 0W/1ITM ($0 / $3.00). Under the
re-rank method they differ in 4 races: B 1W/2ITM vs A 0W/1ITM.

**C vs A0, both base models without the reranker: 2 of 43 races** (drop:
10/28 R8, 10/29 R2; 1 ITM each, A0's Marks Legacy won). They are **identical
in all 43 races** under the re-rank method. On these cards 1.3.2's base model
picks the same #1 as 1.3.0's almost every time. Whatever 1.3.2's stretch
features add shows up in calibration, not in the #1 pick.

**C vs A** (keeping 1.3.2 and dropping the reranker, vs rolling back to 1.3.0
as it ran): 10 of 43 races. C 2W/5ITM ($25.60 / $18.60) vs A 1W/4ITM ($4.60 /
$9.80). These are mostly the same races as B vs C, because the reranker
moves both base models the same way.

## The two scratch methods

They agree on the #1 pick in 39–42 of 43 races per arm. Where they differ (for
example 10/23 R3 and 10/29 R3), it's because dropping a scratched rival
changes who has the higher P(ITM) among close contenders. Neither method
changes any conclusion: every comparison points the same way under both, and
the sizes are similar.

## What the sample can and cannot say

* **Too small to trust:** every #1 hit, ROI and exacta comparison. The arms
  differ in 2–10 races out of 43, and the largest #1 ITM gap is 2 races (p ≥
  0.5). All win-ROI gaps come down to one or two winners, and the ROI
  intervals per arm are about ±40 points wide. Exacta boxes hit 2–3 times in
  43 races for every arm, so there is nothing to compare there. Top-3
  overlap ranges over 62–66 of 129, which is noise.
* **Most consistent signal, still not significant:** the reranker lowers
  P(ITM) log loss by about 0.004 per starter on **both** base models (B−C
  −0.0046, A−A0 −0.0044), and it never changes P(win) calibration. 1.3.2 is
  slightly better calibrated than 1.3.0 on ITM, with and without the
  reranker (−0.0023 to −0.0030). Every interval still crosses zero.
* **Consistent with the meet-long reranker tally** in the nightly reviews
  (15 changed races through 10/30: base 4W/10ITM vs reranked 3W/8ITM). These
  five cards are part of that tally, so this is the same evidence measured
  again, not an independent confirmation. The direction on wins is mildly
  against the reranker; on ITM it is level here.
* **Not tested here:** what 1.3.0 would have done on the 10/14–10/22 cards
  where it or 1.3.1 ran live; races where Thornton or Hernandez came off
  mounts (all arms were scored with the pre-race jockeys, as logged); and
  rebuilding field-relative features after scratches.

## Recommendation (no change made)

1. **Don't roll back to 1.3.0.** Its base #1 picks match 1.3.2's in 41–43 of
   43 races. 1.3.2 is a little better calibrated on ITM, and A (1.3.0 as it
   ran live) is the worst arm on #1 wins, ITM and ROI under both methods.
   Nothing here favours 1.3.0.
2. **Keep the reranker on for now.** Its effect on these 43 races is +1/−1
   ITM, one winner either way, and a slight, consistent improvement in P(ITM)
   calibration. Its money deficit comes down mainly to one 6-1 winner it
   moved off (10/24 R4). That is not enough
   to justify a change, and switching on evidence this thin would just be
   chasing noise. The base P(ITM) is already logged on every run, so arm C
   keeps accumulating at no cost whichever way it's set.
3. **If Doug wants a decision rule,** write it down before the next cards
   so the result can't be read after the fact: for example, review again once
   the reranker has changed the #1 in about 40 scored races (it changes about
   one race in five, so roughly 200 races), and judge on #1 ITM plus P(ITM)
   log loss rather than win ROI.

## Files

* `tracking/paired_2026-11-01/card_MMDD.csv`: per-card checkpoint, one row
  per horse × arm × field (`full` = pre-race field, `post` = scratches
  dropped), with the chart outcome joined. `card_MMDD_meta.json` holds the
  backup sha, rebuilt row count, reproduction stats, scratches and exacta
  payoff.
* `races_<method>_<arm>.csv`: per-race results. `analysis_output.txt`: the
  full printed output, including Brier and every paired test.
* `run_card.py` (shared setup), `stages.py` (per-card stages: rebuild →
  repro → 1.3.0 → 1.3.2 → final), `analyze2.py` (combine). In-process only,
  the harness caches the PP PDF parse that the bridge otherwise redoes for
  every race. A cached run on 10/24 was checked byte-identical to an uncached
  one.
* **Harness bug found and fixed during the run:** the first pass reset
  `card_picks._RERANKER` between arms. Because `get_reranker` caches behind
  `_RERANKER_TRIED`, the reranker then silently returned None on every later
  pass in the same process. All five cards were redone with the reset
  removed, plus a guard that aborts any "+reranker" pass where the reranker
  never fires (and any no-reranker pass where it does). Only the corrected
  runs are reported or committed. `card_picks.py` itself is unchanged and
  behaves correctly in normal one-run-per-process use.
