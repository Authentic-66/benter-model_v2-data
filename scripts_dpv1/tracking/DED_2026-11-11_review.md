# DED 2026-11-11 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Eleventh card
on 1.3.2, **fourth with name matching ON**. One logged run, the record:
`generated_at = 2026-11-11T11:17:16`, pre-race, bridged, 71 rows (full
fields), commit `85f95cc` (`picks/DED_2026-11-11_20261111-1117.*`).

Read-only on the live model: no changes to 1.3.2, the rerankers or the
Piece 1–4 code.

## Pre-race

* **Picks logged before post:** model 11:17 CST (`85f95cc`), Don received
  11:20 (`e1f4b3a`), Doug (`0b15ff6`). The high-confidence qualifier (R6 #5)
  was logged with the card.
* **Scratches (Doug's list, all confirmed by the chart):** R3 #10 Kissesfor
  Cooper (trainer), R4 #9 Three Echoes (gate), R6 #2 Call Me Susan (vet).
  **No others.**
* **Late jockey changes (Doug's list; no others on the chart):** Javier
  Antonio Hernandez came off **all four** of his mounts, each losing the
  apprentice allowance: R1 #5 Make Mea Deal (Kelvin Arana), R3 #5 Princess
  Peach (Colby Hernandez), R4 #5 Backfire (Jose Nava-Marin), R6 #1 Two Jet
  (Alex Birzer). **Flagged as a possible ongoing absence, like Thornton and
  Melancon**: check his mounts on each new card.

### Consensus (post-scratch rule, Doug 11/05)

| R | model | Don | Doug | consensus |
|---|---|---|---|---|
| 1 | 7 | 7 | 4 | no |
| 2 | 6 | 8 | 7 | no |
| 3 | 7 | 5 | 5 | no |
| 4 | 3 | 8 | 8 | no |
| 5 | 5 | 9 | 6 | no |
| 6 | 5 | 5 | 5 (#2 scratched was his 2nd) | **#5 Snazzy Gal** |
| 7 | 2 | 2 | 2 | **#2 Ironinthe Fire** |
| 8 | 6 | 6 | 8 | no |

## Load (2026-11-12 morning)

* **First live use of `scripts_dpv1/load_chart.py`.** Chart
  `Delta Downs/ded-results-2026/DED111126USA.pdf`. Output: `backup verified:
  racing_full.db.pre-ded1111res.bak`, `+8r 68e (purged 71 first) [replaced a
  pre-race card]`, `"errors": 0`, `loaded: DED 2026-11-11 8 races, 68
  entries, 67 with a finish; replaced a pre-race card of 71 entries`. 71 − 68
  = the 3 scratches.
* Spot checks: **R1 official 4-7-5-6 and R6 5-1-3-6, as expected.**
* **No DQs, no dead heats, no non-betting starters.** One non-finisher: **R7
  #7 San Juan Hill** (10.2-1, model 5th of 7) "pulled up down the backside
  and was transported by equine ambulance".
* Speed figures and features were not rebuilt here (the 11/12 card build does
  that).
* Pick payouts (per $0.50):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 4-8-7 | 64.30 |
  | Pick 3 | R2–R4 | 8-7-2 | 153.90 |
  | Pick 3 | R3–R5 | 7-2-5 | 69.75 |
  | Pick 4 (early) | R2–R5 | 8-7-2-5 | **534.80** |
  | Pick 5 (early) | R1–R5 | 4-8-7-2-5 | 1,947.95 |
  | Pick 3 | R4–R6 | 2-5-5 | 41.15 |
  | Pick 3 | R5–R7 | 5-5-1 | 64.70 |
  | Pick 3 | R6–R8 | 5-1-6 | 68.85 |
  | Pick 4 (late) | R5–R8 | 5-2/5-1-6 | **178.60** |
  | Pick 5 (late) | R4–R8 | 2-5-2/5-1-6 | 983.85 |

  The late pools' R6 leg reads `2/5`: the scratched #2 was replaced by the
  favourite #5.
* `score_predictions.py --track DED --date 2026-11-11`: top pick ITM **7 of
  8**, won 4 of 8; top-pick show ROI +8.1%; all horses ITM 24 of 68. 68 rows
  scored (2,497 total). No logged #1 scratched.

### Late jockey changes (`tracking/late_jockey_changes.csv`)

| R | horse | PP rider → rode | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 1 | #5 Make Mea Deal | J. A. Hernandez → Kelvin Arana | 4 of 9 | 35.2 | **3rd** | 9.5 |
| 3 | #5 Princess Peach | J. A. Hernandez → Colby Hernandez | 3 of 10 | 37.2 | **2nd** | 1.2 (fav) |
| 4 | #5 Backfire | J. A. Hernandez → Jose Nava-Marin | 7 of 8 | 20.4 | 8th | 44.2 |
| 6 | #1 Two Jet | J. A. Hernandez → Alex Birzer | 5 of 6 | 33.7 | **2nd** | 4.4 |

Four horses, summed P(ITM) 1.27, **ITM 3**. Across 11/05–11/11 the list has
19 rows (summed P(ITM) 7.15, ITM 11). The model priced these horses with
Hernandez's history and the PP weight; it did not see the change.

## Per race (re-ranked among horses that ran)

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 7-1-4-5 | 4-7-5-6 | **2nd** (fav) | 3 of 9 (2.6-1) | 2/3 | miss | miss (3 of 4) | 7-1 miss | 47.99 |
| 2 | 6-7-1-3 | 8-6-1-3 | **2nd** (fav) | **9 of 10** (7.1-1) | 2/3 | miss | miss (3 of 4) | 6-7 miss | 26.85 |
| 3 | 7-8-5-2 | 7-5-1-4 | **1st** | 1 of 10 (3.0-1) | 2/3 | miss | miss (2 of 4) | 7-8 miss | 218.07 |
| 4 | 3-8-2-1 | 2-1-7-4 | 7th | 3 of 8 (6.2-1) | 1/3 | miss | miss (2 of 4) | 3-8 miss | 233.67 |
| 5 | 5-6-3-4 | 5-3-9-1 | **1st** (fav) | 1 of 9 (1.9-1) | 2/3 | miss | miss (2 of 4) | 5-6 miss | 32.88 |
| 6 | 5-7-3-6 | 5-1-3-6 | **1st** (fav) | 1 of 6 (2.1-1) | 2/3 | miss | miss (3 of 4) | 5-7 miss | 9.06 |
| 7 | 2-5-4-3 | 1-4-2-6 | **3rd** (fav) | **7 of 7** (5.1-1) | 2/3 | miss | miss (2 of 4) | 2-5 miss | 59.25 |
| 8 | 6-2-8-9 | 6-8-4-2 | **1st** (fav) | 1 of 9 (1.0-1) | 2/3 | miss | miss (3 of 4) | 6-2 miss | 4.29 |

**Model:** #1 **won 4 of 8** (R3 Marriedfor Money $8.00, R5 Alakazam $5.80,
R6 Snazzy Gal $6.20, R8 Sassi Royal $4.00) and was **ITM in 7 of 8**, the
best card on 1.3.2. $2 win on the #1: $24.00 on $16 (+50.0%). Top-3 overlap
15 of 24, but **no exotic hit**: in every race one of its top three missed
the board.

* The model's #1 was the favourite in six races; five of those hit the board.
* **R2:** #8 Traitour (7.1-1, model 9th of 10, P(ITM) 18.0) "made a late bid
  and drove clear"; the model's #1 Wannabeeloved (0.8-1) 2nd. Don had
  Traitour #1.
* **R4:** the model's #1 #3 Guns (4.6-1) "always raced near the back ... showed
  little" (7th). #2 Field Study (6.2-1, model 3rd) won; #8 Mucino (1.6-1 fav,
  model 2nd) 5th.
* **R7:** #1 Yockey's Drivethru (5.1-1, model **last of 7**, P(ITM) 28.6)
  "rallied four wide and got up late". Consensus #2 Ironinthe Fire (1.7-1)
  3rd after setting the pace.

### Reranker

**No #1 changes**, pre-race or among runners (R4 was closest: base #3 48.7
vs #2 48.4). In R3 it moved #5 Princess Peach (2nd) into the top three in
place of #2 RT's Cajun Star (7th): top-3 overlap 15 vs base 14.

**Reranker review rule:** still **4 of 40** qualifying races (11/05 R4,
11/06 R4, 11/07 R6, R9): reranked #1 2 W / 3 ITM, base #1 0 W / 0 ITM.

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #1 Daat | 49.4 → 58.2 (+8.8) | 2 → 2 | 9th (7.0-1) |
| 1 | #3 Stormcatholic Spot | 28.3 → 22.9 (−5.3) | 5 → 6 | 8th |
| 1 | #2 Red Power | 28.0 → 22.8 (−5.1) | 7 → 7 | 7th |
| 1 | #6 Heath's Soldier | 20.8 → 13.4 (−7.4) | 9 → 9 | 4th (36.1-1) |
| 2 | #9 Little Warrior | 14.5 → 19.9 (+5.4) | 9 → 8 | 8th (78.7-1) |
| 3 | #2 RT's Cajun Star | 36.9 → 31.4 (−5.4) | 3 → 4 | 7th |
| 3 | #3 Dreamchaser Jewels | 20.8 → 28.2 (+7.4) | 7 → 5 | 6th |
| 3 | #9 She's by My Side | 29.6 → 22.7 (−6.9) | 5 → 7 | 8th |
| 4 | #7 Zavala | 25.8 → 31.5 (+5.7) | 6 → 5 | **3rd** (5.8-1) |
| 5 | #2 Prollydid | 30.5 → 24.7 (−5.8) | 5 → 6 | 9th (90.6-1) |

7 of 10 went the right way (the six cuts and Zavala). The biggest move,
Daat +8.8 to a near-tie for #1 in R1, ran 9th.

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 11/11 | 8 | 0 | 4 / 7 / $24.00 (+50.0%) | 4 / 7 / $24.00 (+50.0%) |
| 1.3.2 (10/22–11/11) | 93 | 14 | 22 / 56 / $124.80 (−32.9%) | 21 / 53 / $125.80 (−32.4%) |
| **Meet** | 145 | 19 | 39 / 85 / $235.60 (−18.8%) | 38 / 84 / $274.00 (−5.5%) |

`model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
scratches excluded): **with-reranker 52/84 vs base-only 49/84** (+3, as
before). Top pick ITM 61.9%, win 23.8%; show ROI −20.2%. No alerts.

## High-confidence #1 forward test (`tracking/high_conf_top1.csv`)

One qualifier: R6 #5 Snazzy Gal, P(ITM) 67.2; the R6 scratch (#2) left her
the post-scratch #1. **Won** at 2.1-1 (fav): $6.20 win, $5.00 place.

**6 of 40** qualifying races so far: **1 W, 2 placed**. $2 win $6.20 on $12,
$2 place $8.40 on $12. Over-4-1 subset: still 1 race (11/06 Vineaux, 4th).
No reading until 40.

## Name matching ON: 11/05–11/11 vs the earlier 1.3.2 cards

Same basis as before (record run, among starters, logged P(ITM) not
renormalised; #1 re-ranked among runners).

| card | name matching | races | starters | #1 W | #1 ITM | sum P(ITM) | ITM | P(ITM) LL | Brier | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.3.2 off (7 cards, 10/22–11/04) | off | 59 | 505 | 12 | 32 (54%) | 158.82 | 177 | 0.609 | 0.210 | $67.80 (−42.5%) |
| 11/05 | on | 8 | 61 | 3 | 7 | 21.82 | 24 | 0.622 | 0.218 | $19.20 |
| 11/06 | on | 9 | 77 | 2 | 5 | 24.27 | 27 | 0.631 | 0.218 | $8.60 |
| 11/07 | on | 9 | 75 | 1 | 5 | 23.12 | 27 | 0.643 | 0.227 | $5.20 |
| **11/11** | **on** | 8 | 68 | 4 | 7 | 23.15 | 24 | **0.580** | **0.199** | $24.00 |
| 1.3.2 on (4 cards) | on | 34 | 281 | 10 | 24 (71%) | 92.35 | 102 | 0.620 | 0.216 | $57.00 (−16.2%) |

**The rise in ON log loss stopped**: 11/11 is the best ON card (0.580) and
better than five of the seven OFF cards (11/04 by 0.0001). ON is now 0.620 vs OFF 0.609 on
log loss, with better ranking (#1 ITM 71% vs 54%). Still the read-only
paired OFF/ON check (from the `-run.bak` files) that decides this, not
these card totals.

## Data issues on the model's top picks (`tracking/top_pick_data_issues.csv`)

**None.** All eight post-scratch #1s had their last race in the DB (PP days
off = DB days, 11–75 days), and jockey and trainer history (at least 222 prior
starts each).

## Missing-last-race horses (read-only, running tally)

**Tonight: no flagged starters.** The three flagged horses all scratched (R3
#10 last ran EVD 8/29, R4 #9 SWF 9/19 (not in the corpus), R6 #2 DED 10/15).
The tally is unchanged: **11/04–11/11, 42 starters, ITM 18 vs 12.6
expected, W 4 vs 4.1.** All other 11/11 starters: W 8 vs 7.6 expected, ITM
24 vs 22.8.

## First-time starters in tonight's maidens

| R | first-time starters | finishes | model ranks | winner |
|---|---|---|---|---|
| 1 (MCL) | #2, #3 | 7th, 8th | 7th, 6th | #4 He's Readyto Win (raced), model 3rd |
| 5 (MCL) | #3, #7, #8, #9 | **2nd, 3rd**, 6th, 7th | 3rd, 7th, 9th, 8th | #5 Alakazam (raced), the model's #1 |

R3 and R8 (maidens) had no first-time starters. **The pattern from 11/06 R3
and 11/07 R3/R9 (a first-time starter won each time) did not repeat**: raced
horses won both maidens with first-time starters. Tally for the queued check:
5 maidens, first-time starter won 3.

## Low-coverage (<65%) horses

The same six first-time starters at 53–54%: R1 #2, #3; R5 #3 My Sweet
Caroline (**2nd**, model 3rd), #7, #8, #9 Shirley Our Joy (**3rd**, Don's
POD).

## Benchmarks: Don and Doug

* All three were logged before post.
* Scratches: **Don** lost nothing (no alts given). **Doug** lost his R4 4th
  (#9) and R6 2nd (#2).
* Doug's picks were all regular picks (no passes, no best guesses).

| R | Don | Don #1 fin | Don overlap | Doug | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 7-4-9-8 | **2nd** | 2/3 | 4-7-1-3 | **1st** | 2/3 | **2nd** | 2/3 |
| 2 | 8-6-7-1 | **1st** | 2/3 | 7-6-1-8 | 7th | 2/3 | **2nd** | 2/3 |
| 3 | 5-7-8-9 | **2nd** | 2/3 | 5-7-9-11 | **2nd** | 2/3 | **1st** | 2/3 |
| 4 | 8-3-7-4 | 5th | 1/3 | 8-2-3 | 5th | 1/3 | 7th | 1/3 |
| 5 | 9-5-6-7 | **3rd** | 2/3 | 6-5-8-7 | 5th | 1/3 | **1st** | 2/3 |
| 6 | 5-6-1-3 | **1st** | 2/3 | 5-6-3 | **1st** | 2/3 | **1st** | 2/3 |
| 7 | 2-1-3-4 | **3rd** | 2/3 | 2-4-5-1 | **3rd** | 2/3 | **3rd** | 2/3 |
| 8 | 6-4-8-2 | **1st** | 3/3 | 8-6-9-2 | **2nd** | 2/3 | **1st** | 2/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | **4** | **7/8** | 15/24 | 0 | 0 | 0 | $24.00 on $16 (+50.0%) |
| Don | 3 | **7/8** | **16/24** | 1 (R8 $4.29) | **2 (R6 $9.06, R8 $4.29)** | **3 (R1 $8.00, R2 $22.00, R3 $11.50)** | **$26.40 on $16 (+65.0%)** |
| Doug | 2 | 5/8 | 14/24 | 0 | 0 | 3 (R1 $8.00, R3 $11.50, R8 $6.60) | $13.40 on $16 (−16.2%) |

* A strong night for the model and Don. The model had the most winners (4);
  Don's #1 Traitour (R2, $16.20) was the night's best-priced #1 winner.
* Doug's top two hit three exactas; his #1 #4 He's Readyto Win won R1.

### Consensus #1s (`tracking/consensus_top1.csv`)

* **R6 #5 Snazzy Gal** (2.1-1 fav): **won**, $6.20 / $5.00 / $3.60. Also the
  high-confidence qualifier, and the top of Doug's winning superfecta.
* **R7 #2 Ironinthe Fire** (1.7-1 fav): **3rd**, show $2.40; set the pace
  and was outfinished by the top two.

So far: **7 W, 14 ITM from 19**. $2 win on all nineteen: $32.20 on $38
(−15.3%); $2 show $34.50 on $38 (−9.2%).

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **11/05–11/11** (name matching ON) | Model | 34 | 10 | 24 (71%) | 53/102 | −16.2% |
| | Don | 34 | 12 | 24 (71%) | 58/102 | +16.2% |
| | Doug | 34 | 8 | 17 (50%) | 50/102 | −17.9% |
| **1.3.2** (10/22–11/11) | Model | 93 | 22 | 56 (60%) | 143/279 | −32.9% |
| | Don | 93 | 31 | 60 (65%) | 158/279 | −3.0% |
| | Doug | 91 | 27 | 53 (58%) | 140/273 | −13.8% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.7% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (17 cards) | Model | 145 | 39 | 85 (59%) | 220/435 | −18.8% |
| | Don | 136 | 46 | 86 (63%) | 225/408 | −1.8% |
| | Doug | 99 | 30 | 56 (57%) | 150/297 | −11.2% |
| | Doug, without best guesses | 96 | 28 | 54 (56%) | 144/288 | −15.6% |

The meet $2 win lines ($235.60 model, $267.00 Don, $175.80 Doug) match the
ticket replay.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R5 #9 Shirley Our Joy (ML 12-1) | | **3rd** at 12.7-1 (show $4.80) | — | — |
| EP4 (R2–R5) | 6-7-8 / 5 / 3-8 / 5-6-9 (18 combos) | $9 | miss, **dead in R3** | 2/4 (R2 #8, R5 #5) | 8-7-2-5 paid 534.80 |
| LP4 (R5–R8) | 5-6-9 / 1-5-6 / 1-2-3 / 4-6 (54 combos) | $27 | **HIT** | **4/4** | 5-5-1-6 paid **178.60** |

* EP4: his single in R3, #5 Princess Peach (1.2-1, Hernandez off), ran 2nd
  to #7 Marriedfor Money, the model's #1.
* **LP4 hit: $178.60 back on $27 (+$151.60).** R5 #5 Alakazam, R6 #5 Snazzy
  Gal, R7 #1 Yockey's Drivethru (5.1-1; the model had him last) and R8 #6
  Sassi Royal. His second LP4 hit of the meet (10/29, $150.15).
* Don's day: **$36 wagered, $178.60 back (+$142.60).**

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 6 | superfecta wheel, $0.10 | 5 / 1,3,6,7 / 1,3,6,7 / ALL (36 combos) | $3.60 | **won: 5-1-3-6 paid $9.06** |
| IND | 10 | superfecta part wheel, $0.10 (Quarter Horse) | 1,10 / 1,10 / 4,9 / ALL (20 combos) | $2.00 | lost (10-9-6-5) |

Night total: **$5.60 wagered, $9.06 returned, +$3.46.** DED wagering $3.60,
**qualifies for the DED PP rebate** (+$3.85 to log when it lands). IND is a
personal bet, kept out of DED scoring and the ticket replay.

**Bankroll** (`tracking/bankroll.csv`): $67.57 after the IND stake, −$3.60,
+$9.06 = **$73.03 computed vs $73.00 reported** by TwinSpires (before the
rebate). The $0.03 difference is logged as a reconciliation row: **ask Doug**
(a rounding or a fee somewhere?).

## Watch list

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 3 | #7 Marriedfor Money | T Ronnie Ward | **1 of 10** | 42.4 | **1st** ($8.00) | 3.0 |
| 3 | #11 Rockaby Baby | T Ronnie Ward | 10 of 10 | 13.5 | 9th | 26.2 |
| 5 | #2 Prollydid | J Devin Magnon | 6 of 9 | 24.7 | 9th | 90.6 |
| 8 | #4 Catalina Classic | J Devin Magnon | 6 of 9 | 33.1 | **3rd** | 2.7 |

Catalina Classic was not on Doug's list but is in the tally (Devin Magnon
rode). Meet tally after 11/11 (`watch_people_tally.csv`; logged record runs
only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 32 | 3 | 13 | 9.34 | 13 | **+3.66** (was +3.22) |
| J Devin H. Magnon | 29 | 4 | 9 | 9.30 | 9 | −0.30 (was −0.72) |
| T Rylee Magnon | 9 | 1 | 2 | 3.12 | 2 | −1.12 (no starter) |
| T W.B. Calhoun | 19 | 4 | 9 | 6.24 | 9 | +2.76 (no starter) |

## Things that look off

1. **Javier Antonio Hernandez came off all four mounts**; three of the four
   hit the board for other riders. Possible ongoing absence: check his mounts
   on the next cards, as for Thornton and Melancon.
2. **Bankroll is $0.03 short** of the computed balance. Ask Doug.
3. **The model's top three never hit an exotic** on a 4-winner, 7-ITM night:
   in every race at least one of its 2nd and 3rd picks missed the board.
4. R7 #7 San Juan Hill was pulled up and vanned off (DNF).

## Queued (not started)

* Next session (read-only): paired name-matching OFF/ON check, now on
  11/05–11/11, from the `-run.bak` files.
* PP-date recency fix (top of the queue; needs the OFF/ON validation first).
* First-time-starter maiden check (5 maidens with first-time starters;
  first-time starter won 3).
* MNR 10/05 chart: retry after 11/21. Non-corpus tracks decision.
