# Paired name-matching check, DED 11/05–11/07 (2026-11-08)

Read-only. Nothing about the live model (`dpv1.pkl`, 33bfb329…a918), the
reranker (`dpv1_pp_reranker.pkl`, cd4a5c79…29ea), the code or the live DB
changed; both pickle hashes were checked on every run, and the live DB was
unchanged after every run. Harness and outputs:
`tracking/name_matching_paired_2026-11-08/` (`nm_card.py`, `compare_paired.py`,
`compare_output.txt`, `compare_horses.csv`, per-arm `card_MMDD_{on,off}.csv`).

## TL;DR

* **The ON arm reproduces the logged record runs exactly** on all three cards
  (69 / 89 / 87 rows, max |dP(ITM)| 1.1e-16, 0 rank changes), so the
  comparison is against what actually ran.
* **Paired on identical races (26 races, 213 starters), ON is a hair better
  than OFF, within noise:** P(ITM) log loss 0.6350 → 0.6327 per starter
  (−0.0023, 95% race-bootstrap CI −0.0119 to +0.0084), Brier 0.2218 → 0.2211;
  #1 in the money 14 → 17 of 26, #1 wins 5 → 6. 17 races better, 9 worse.
  This is the same direction and size as the 10/23–11/04 validation (−0.0022).
* **The rising log loss (0.622 → 0.631 → 0.643) is not name matching.** The OFF
  arm rises the same way on the same races (0.625 → 0.632 → 0.646), and ON is
  lower than OFF on every one of the three cards.
* **It is not a run of long-priced winners either.** Horses at 10-1 or more hit
  the board *less* often than on the earlier cards (14.7% vs 18.0%), and on
  11/05–11/06 the market (final odds) did unusually *well* (log loss 0.499,
  its best cards of the meet). The extra loss comes from **mid-priced horses
  (3-1 to 9-1) finishing in the money 53% of the time, against 41% on
  10/22–11/04**, while the model gave them about 36% either way. That is a
  three-card run of results, the kind of thing a 213-starter sample produces.
  The OFF-card range of the model's gap to the market (−0.006 to +0.136 per
  starter) already covers the ON cards' +0.035 to +0.133.

## Method

For each card, one arm per process (`nm_card.py`):

1. copy `scripts/racing_full.db.dedMMDD-run.bak` (the DB just before that
   card's PP load) to scratch;
2. rebuild the card there with today's code: `load_pp_card load`,
   `speed_figures_dpv1 compute`, `feature_builder_dpv1 build`, with
   `BENTER_NAME_MATCH=1` (ON) or `=0` (OFF) for the loader and the PP bridge
   parse;
3. score 1.3.2 + pp-reranker-1.0 on the full pre-race field (seed 6001,
   10,000 iterations), as logged;
4. **ON arm:** compare to the logged record run (11/05 09:31, 11/06 08:55,
   11/07 09:54) and stop if it differs. (The 11/04 check reproduced the OFF arm,
   because those cards ran OFF; these ran ON.)

Today's loader maps "Alw 5000s" to STARTERALLOWANCE (`bb5b1a5`), which is what
the hand relabel of 11/06 R4 did before its run, so 11/06 reproduces without
a manual step. Scoring (`compare_paired.py`): #1 = highest P(ITM) among the
horses that ran (the nightly re-rank method); ITM = official finish 1–3; log
loss and Brier on P(ITM) over the starters. Races and starters are identical
in both arms (same chart).

The 11/07 OFF arm was first stopped by Claude Code for low memory (machine-
wide, while idle) and rerun in the foreground; the five arms already done
were committed first (`fe07676`).

## Results

### History gains

| card | horses | jockey with history OFF → ON | trainer OFF → ON | either gained | #1 changed (full field) |
|---|---|---|---|---|---|
| 11/05 | 69 | 41 → 69 | 38 → 68 | 46 | 2 of 8 |
| 11/06 | 89 | 50 → 89 | 59 → 88 | 53 | 1 of 9 |
| 11/07 | 87 | 51 → 87 | 55 → 87 | 51 | 5 of 9 |

Mean |P(ITM) ON − OFF| = 2.2pp per horse (max 12.8pp). Match logs: 11/05
exact 86 / core 51 / new 1; 11/06 exact 115 / core 62 / new 1; 11/07 exact 107
/ core 66 / alias 1; no ambiguous.

### Scored (starters only)

| card | races | starters | #1 W OFF/ON | #1 ITM OFF/ON | log loss OFF | ON | ON − OFF | Brier OFF | ON |
|---|---|---|---|---|---|---|---|---|---|
| 11/05 | 8 | 61 | 2 / 3 | 5 / 7 | 0.6252 | 0.6217 | −0.0035 | 0.2193 | 0.2179 |
| 11/06 | 9 | 77 | 2 / 2 | 4 / 5 | 0.6318 | 0.6313 | −0.0005 | 0.2183 | 0.2183 |
| 11/07 | 9 | 75 | 1 / 1 | 5 / 5 | 0.6462 | 0.6430 | −0.0032 | 0.2275 | 0.2265 |
| **all** | **26** | **213** | **5 / 6** | **14 / 17** | **0.6350** | **0.6327** | **−0.0023** | **0.2218** | **0.2211** |

Paired race bootstrap (10,000 draws): log loss ON − OFF −0.0023 [−0.0119,
+0.0084]; Brier −0.0008 [−0.0050, +0.0040]. Races better / worse: 17 / 9.

### Races where the #1 among runners differs (OFF → ON)

| race | OFF #1 (P(ITM), finish, odds) | ON #1 (P(ITM), finish, odds) |
|---|---|---|
| 11/05 R2 | #1 Life's Ride (48.6, 6th, 20-1) | #2 Gomarkgo (46.1, 2nd, 1-2) |
| 11/05 R4 | #8 Cheyenne Moon (55.1, 6th, 1.9-1) | #6 Memory Maker (57.1, **won**, 2.3-1) |
| 11/06 R4 | #6 Call My Banker (62.6, 5th, 3.4-1) | #7 Mahoney Road (65.5, 2nd, 1.9-1) |
| 11/07 R1 | #5 Paradise Ridge (40.6, 2nd, 4.7-1) | #6 Double L's Army (42.4, 4th, 3.8-1) |
| 11/07 R8 | #10 Cool Guitar (39.3, 4th, 4.1-1) | #3 Inchhighatahundred (45.5, 2nd, 3.0-1) |

ON's #1 did better in 4 of the 5 and worse in 1 (11/07 R1). Five races is far
too few to read anything into.

## Why the ON cards' log loss rose

Two yardsticks that do not depend on name matching: the OFF arm on the same
races, and a **market benchmark**, P(ITM) from final odds (win probability
1/(odds+1), normalised, Harville to the top three). The market uses
post-time information the model never sees, so it is only a measure of how
surprising each card's results were, not a target.

| card | LL ON | LL OFF | LL market | ITM finishers' median odds | ITM at 10-1+ | winners at 10-1+ |
|---|---|---|---|---|---|---|
| 11/05 | 0.6217 | 0.6252 | 0.4988 | 5.0 | 4 of 24 | 0 of 8 |
| 11/06 | 0.6313 | 0.6318 | 0.4982 | 4.3 | 5 of 27 | 2 of 9 |
| 11/07 | 0.6430 | 0.6462 | 0.6080 | 5.5 | 6 of 27 | 2 of 9 |

Context, all logged 1.3.2 cards (record runs, logged P(ITM), same scoring):

| | cards | starters | LL model | LL market | model − market |
|---|---|---|---|---|---|
| 10/22–11/04, NM OFF | 7 | 505 | 0.6090 | 0.5516 | +0.057 (per card −0.006 to +0.136) |
| 11/05–11/07, NM ON | 3 | 213 | 0.6327 | 0.5370 | +0.096 (per card +0.035 to +0.133) |

By final-odds band:

| group | band | starters | ITM % | model mean P(ITM) | LL model | LL market |
|---|---|---|---|---|---|---|
| 10/22–11/04 OFF | under 3-1 | 90 | 68.9 | 0.448 | 0.796 | 0.619 |
| | 3-1 to 9-1 | 176 | 40.9 | 0.351 | 0.691 | 0.638 |
| | 10-1 up | 239 | 18.0 | 0.237 | 0.478 | 0.462 |
| 11/05–11/07 ON | under 3-1 | 38 | 63.2 | 0.476 | 0.707 | 0.649 |
| | 3-1 to 9-1 | 73 | **53.4** | 0.361 | **0.847** | 0.724 |
| | 10-1 up | 102 | 14.7 | 0.243 | 0.452 | 0.362 |

Reading it:

1. **Name matching is ruled out as the cause.** On identical races the OFF arm
   has the same high, rising log loss, and ON is lower on all three cards.
2. **Long shots are ruled out.** Fewer 10-1+ horses hit the board than before,
   and the model's loss on them went *down* (0.478 → 0.452).
3. **The loss is in the middle of the board.** 3-1 to 9-1 horses ran in the
   money 53% of the time against 41% before, and the model (about 0.36 for
   them in both periods) gave up 0.15 per starter there. The market also had a
   harder time in that band (0.638 → 0.724), so these were surprising results,
   not something the market saw and the model missed. On 11/05–11/06 the market
   had its best cards of the meet mostly because its short-priced horses ran
   to form (11/05: 8 of 10 under 3-1 ITM).
4. **Nothing here is outside the earlier spread.** The model's per-card gap to
   the market on the ON cards (+0.035 to +0.133) falls inside the range seen on
   OFF cards (−0.006 to +0.136; 10/23 was +0.136).

## Caveats

* Three cards, 26 races, 213 starters. Every interval crosses zero; the result
  is "no sign of harm", the same as the 10/23–11/04 validation.
* The market benchmark uses final odds and the Harville top-three formula,
  which is known to over-rate favourites for place and show. It is used only
  to compare cards with each other, never as a model target.
* The arms are rebuilt with today's code. The ON arm's exact reproduction of
  the three record runs shows that nothing else changed the inputs.

## Decision basis for Doug

No action suggested. Name matching stays ON. The rising log loss looks like
three nights of mid-priced horses running well; keep watching it in the
nightly reviews (with OFF/market yardsticks if it keeps rising), and judge it
again at the reranker-review and high-confidence-test checkpoints, which
already split NM ON/OFF.
