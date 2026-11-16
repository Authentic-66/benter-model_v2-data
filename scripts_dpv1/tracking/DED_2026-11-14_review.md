# DED 2026-11-14 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Fourteenth
card on 1.3.2, **eighth with name matching ON**. One logged run, the record:
`generated_at = 2026-11-14T08:36:33`, pre-race, bridged, 92 rows (full
fields), commit `560dc83` (`picks/DED_2026-11-14_20261114-0836.*`). Doug ran
runbook B himself; verified after the fact.

Read-only on the live model: no changes to 1.3.2, the rerankers or the
Piece 1–4 code.

## Pre-race

* **Picks:** model logged 08:36 CST (`560dc83`). The four high-confidence
  qualifiers (R1, R4, R7, R9) and the two reranker #1 changes (R1, R7) were
  logged with the card.
* **Don:** picks, POD, EP4 and LP4 logged 11/14 morning, before post
  (`e48e4af`). **Both his 11/13 (9 races, `9a022f8`) and 11/14 (11 races)
  picks are logged.**
* **Doug:** picks sent **4:29 PM CST, before the 4:40 first post** (chart R1
  off 4:43). **Valid** (Doug, 11/15); logged pre-race (`cecb0cc`).
* **Consensus (post-scratch three-way #1s), logged 4:32 PM before R1:** R1
  #1 Footprint, R5 #8 Easy Like Breezy, R9 #5 Romeo Spikes, R11 #2 C Note
  Gia.
* **Scratches (Doug's list, all confirmed by the chart):** R2 #3 Cairo Dancer
  (vet), R7 #1 Watering (vet), R9 #2 Banquet Chef (vet). **No others.**
  Watering was the model's base #1 in R7 and Don's R7 #1 (Don has three
  picks there, no alt). Nobody else lost a pick.
* **Late jockey changes** (every chart rider compared with
  `pp_entries_raw.pp_jockey`; the comparison found no others):
  * **R4 #3 Takethe Hint: Carlos Lozada for Javier Antonio Hernandez, the
    fourth night running.** Apprentice allowance dropped: the chart has him
    at 115 (110 on the PP). The model's 2nd; he ran 3rd.
  * **R8 #1 Sic'em Now Now: Isaac Castillo for Rey Williams.** First-time
    starter, the model's 2nd of 6; he **won** ($13.60).

## Load (2026-11-15)

* `load_chart.py` on `Delta Downs/ded-results-2026/DED111426USA.pdf`:
  `backup verified: racing_full.db.pre-ded1114res.bak`, `+11r 89e (purged 92
  first) [replaced a pre-race card]`, `"errors": 0`, `loaded: DED 2026-11-14
  11 races, 89 entries, 85 with a finish; replaced a pre-race card of 92
  entries`. 92 − 89 = the 3 scratches.
* Spot checks: **R5 official 3-5-8-9 with #3 First Class Harlow paying $54.80
  to win, and R7 6-5-3-2, as expected.** **R8 4th: #3 Heza Buckaroo**, as
  Doug had it (official 1-4-5-3-2).
* **Four non-finishers** (stored `finish_status = 'DNF'`, no finish
  position; scored as starters that missed the board):

  | R | horse | odds | model rank (runners) | chart |
  |---|---|---|---|---|
  | 1 | #2 It's Miles | 30.8 | 8 of 8 | "dropped back and was eased to the wire" |
  | 8 | #6 B.G.'s Song | 5.0 | 3 of 6 | "sprinted to the front, drove clear ... dropped back and was distanced" (first-time starter, T Ronnie Ward) |
  | 11 | #5 Dixie | 78.3 | 10 of 10 | "lost contact with the field and was distanced" |
  | 11 | #1 Please Hold | 8.7 | 5 of 10 | "dwelt, pulled up and walked off" (first-time starter) |

* **No DQs, no dead heats, no non-betting starters.**
* Pick payouts (per $0.50):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 3-4-9 | 542.35 |
  | Pick 3 | R2–R4 | 4-9-4 | 163.55 |
  | Pick 3 | R3–R5 | 9-4-3 | 405.45 |
  | Pick 4 (early) | R2–R5 | 4-9-4-3 | **4,672.65** |
  | Pick 5 (early) | R1–R5 | 3-4-9-4-3 | 2,056.15 (4 correct) |
  | Pick 3 | R4–R6 | 4-3-4 | 231.80 |
  | Pick 3 | R5–R7 | 3-4-6 | 237.50 |
  | Pick 3 | R6–R8 | 4-6-1 | 66.75 |
  | Pick 3 | R7–R9 | 6-1-1 | 236.10 |
  | Pick 3 | R8–R10 | 1-1-6 | 829.00 |
  | Pick 3 | R9–R11 | 1-6-3 | 432.60 |
  | Pick 4 (late) | R8–R11 | 1-1-6-3 | **11,383.55** |
  | Pick 5 (late) | R7–R11 | 6-1-1-6-3 | 376.35 (4 correct) |

  Both Pick 5 pools paid on four correct (the chart's qualifier).
* `score_predictions.py --track DED --date 2026-11-14`: top pick ITM **7 of
  11**, won 2 of 11; top-pick show ROI +6.4%; all horses ITM 33 of 89. 89
  rows scored (2,718 total), 3 scratched, 4 DNF. No post-scratch #1 was
  scratched (R7's base #1 was, see Reranker).

### Late jockey changes (`tracking/late_jockey_changes.csv`)

| R | horse | PP rider → rode | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 4 | #3 Takethe Hint | J. A. Hernandez → Carlos Lozada | 2 of 9 | 55.3 | **3rd** | 2.4 |
| 8 | #1 Sic'em Now Now | Rey Williams → Isaac Castillo | 2 of 6 | 54.0 | **1st** | 5.8 |

Two horses, summed P(ITM) 1.09, **ITM 2**. Across 11/05–11/14 the list has
30 rows (summed P(ITM) 11.78, ITM 16). **J. A. Hernandez alone: 11 mounts
over four nights (11/11–11/14), summed P(ITM) 3.71, ITM 6.**

## Per race (re-ranked among horses that ran)

Non-finishers count as runners (they started).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1-4-3-6 | 3-4-6-1 | 4th (fav) | 3 of 8 (8.1-1) | 2/3 | miss | **hit** (4 of 4) | 1-4 miss | **101.43** |
| 2 | 5-2-7-4 | 4-5-9-2 | **2nd** | 4 of 8 (10.4-1) | 1/3 | miss | miss (3 of 4) | 5-2 miss | 224.03 |
| 3 | 4-3-7-8 | 9-3-6-2 | 5th | 6 of 9 (7.8-1) | 1/3 | miss | miss (1 of 4) | 4-3 miss | 385.41 |
| 4 | 4-3-9-2 | 4-1-3-5 | **1st** (fav) | 1 of 9 (1.0-1) | 2/3 | miss | miss (2 of 4) | 4-3 miss | 28.59 |
| 5 | 8-2-9-7 | 3-5-8-9 | **3rd** (fav) | 6 of 10 (26.4-1) | 1/3 | miss | miss (2 of 4) | 8-2 miss | 1,075.98 |
| 6 | 3-2-8-7 | 4-3-8-7 | **2nd** | 6 of 8 (5.4-1) | 2/3 | miss | miss (3 of 4) | 3-2 miss | 98.46 |
| 7 | 4-6-5-3 | 6-5-3-2 | 5th | 2 of 6 (2.9-1) | 2/3 | miss | miss (3 of 4) | 4-6 miss | 11.16 |
| 8 | 5-1-6-2 | 1-4-5-3 | **3rd** | 2 of 6 (5.8-1) | 2/3 | miss | miss (2 of 4) | 5-1 miss | 13.90 |
| 9 | 5-3-8-1 | 1-6-3-4 | 5th (fav) | 4 of 7 (13.7-1) | 1/3 | miss | miss (2 of 4) | 5-3 miss | 283.15 |
| 10 | 6-1-4-3 | 6-4-5-2 | **1st** | 1 of 8 (2.9-1) | 2/3 | miss | miss (2 of 4) | 6-1 miss | 20.44 |
| 11 | 2-7-3-4 | 3-2-9-7 | **2nd** | 3 of 10 (8.6-1) | 2/3 | miss | miss (3 of 4) | 2-7 miss | 241.62 |

**Model:** #1 **won 2 of 11** (R4 Bearcat $4.00, R10 Dromas $7.80) and was
**ITM in 7 of 11**. $2 win on the #1: $11.80 on $22 (−46.4%). Top-3 overlap
18 of 33. **Its top four hit the R1 superfecta box ($101.43 for $0.10).**

* **The model's #1 was the favourite in four races:** R4 won, R5 ran 3rd, R1
  (1.3-1) 4th and R9 (0.5-1) 5th. **Only one favourite won all night (R4
  Bearcat)**; four ran 2nd (R3, R7, R8, R10) and two 3rd (R5, R6).
* **R9:** #5 Romeo Spikes (0.5-1, P(ITM) 68.3, everyone's #1) "raced evenly
  near the middle ... never a factor" and ran 5th. #1 Mr. Brad's Cowboy
  (13.7-1, model 4th) won; #6 Dixie's Astro (20.0-1) ran 2nd after the
  reranker's biggest lift of the night (29.1 → 40.4).
* **R5:** #3 First Class Harlow (26.4-1, model 6th of 10) "wide rally, best
  late" and #5 Ruiz Junior (15.3-1, model 7th, a no-data shipper) ran 1-2;
  the $1 exacta paid $323.70 and the $0.10 super $1,075.98.
* **R3:** #9 Maximum Return (7.8-1, model 6th) won; the #1 #4 Angel's Anthem
  "drove clear around the final turn and faded".
* **R6:** the #1 #3 Hap Hot (6.0-1), a no-data shipper (last race OP 2/19),
  "bothered at the start ... closed fast" for 2nd.

### Reranker

Two #1 changes logged pre-race. **Only R1 is a change among runners:**

| R | base #1 | finished | reranked #1 | finished | race P(ITM) log loss, base → reranked |
|---|---|---|---|---|---|
| 1 | #4 Mazing Mark (3.5-1) | **2nd** | #1 Footprint (1.3-1 fav) | 4th | 4.698 → 4.884 (worse) |
| 7 | #1 Watering — **scratched** | – | #4 Rose Darling (5.5-1) | 5th | 3.766 → 3.737 |

**R7 is not a qualifying race, and `reranker_changes.csv` handles it that
way:** with Watering out, the highest base P(ITM) among the six runners was
Rose Darling's own (58.2), so the base #1 and the reranked #1 among starters
are the same horse. The row has `base1_finish = scratched`, `rr1_finish = 5`,
`both_ran = 0` and the note "NOT a qualifying race for the review rule", the
same handling as 11/07 R2 (where the reranked #1 was the scratch). The review
count reads `both_ran = 1` only.

On the card the reranker cost one ITM (R1) and no wins. Card log loss
0.5966 (base) → 0.5940 (reranked) per starter.

**Reranker review rule: 11 of 40** qualifying races (11/05 R4, 11/06 R4,
11/07 R6, R9, 11/12 R2, R5, R7, 11/13 R1, R4, R6, 11/14 R1). Reranked #1
**2 W / 8 ITM**, base #1 **3 W / 4 ITM**. The rule judges ITM and log loss at
40, not wins; no reading until then.

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #1 Footprint | 54.5 → 60.9 (+6.4) | 2 → 1 | 4th (1.3-1 fav) |
| 4 | #8 Baby's Last Dance | 17.2 → 12.0 (−5.2) | 9 → 9 | 7th (16.4-1) |
| 5 | #9 Ambiguous | 32.1 → 38.0 (+5.8) | 4 → 3 | 4th (4.4-1) |
| 6 | #2 Margot's Boy | 42.7 → 50.9 (+8.2) | 4 → 2 | 7th (5.3-1) |
| 9 | #6 Dixie's Astro | 29.1 → 40.4 (+11.3) | 6 → 5 | **2nd** (20.0-1) |
| 10 | #1 Unaffiliated | 44.6 → 49.7 (+5.0) | 2 → 2 | 7th (25.1-1) |
| 10 | #8 Chamois' Splendor | 34.7 → 28.9 (−5.8) | 5 → 7 | 8th (38.2-1) |
| 11 | #2 C Note Gia | 54.4 → 59.8 (+5.4) | 1 → 1 | **2nd** |
| 11 | #4 Woodall Pass | 25.0 → 35.7 (+10.7) | 8 → 4 | 5th (4.4-1) |
| 11 | #8 Soxy Girl | 29.8 → 23.7 (−6.1) | 5 → 8 | 7th (32.4-1) |

5 of 10 went the right way (Footprint, Ambiguous, Margot's Boy, Unaffiliated
and Woodall Pass did not). Top-3 overlap 18 reranked vs 19 base: the base
top three held R3 #6 Money Train (3rd) and R9 #1 Mr. Brad's Cowboy (won),
the reranked top three R10 #4 Channelfortynine (2nd).

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 11/14 | 11 | 1 | 2 / 7 / $11.80 (−46.4%) | 2 / 8 / $11.80 (−46.4%) |
| 1.3.2 (10/22–11/14) | 121 | 21 | 29 / 77 / $158.60 (−34.5%) | 31 / 73 / $174.40 (−27.9%) |
| **Meet** | 173 | 26 | 46 / 106 / $269.40 (−22.1%) | 48 / 104 / $322.60 (−6.8%) |

`model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
scratches excluded): **with-reranker 73/112 vs base-only 69/112** (+4, was
+5). Top pick ITM 65.2%, win 24.1%; show ROI −12.7%. **Alert:** "top pick
ITM over last 30 races is 76.7%, above the 68% ceiling", the same hot-run
check as 11/05–11/13 (pre-race record runs on out-of-corpus cards).

## High-confidence #1 forward test (`tracking/high_conf_top1.csv`)

Four qualifiers, all still the post-scratch #1 (R7 lost its base #1, not
Rose Darling; R9's scratch was not in the top four):

| R | horse | P(ITM) | ML | final odds | finished | $2 win | $2 place |
|---|---|---|---|---|---|---|---|
| 1 | #1 Footprint | 60.9 | 7/2 | 1.3 (fav) | 4th | 0 | 0 |
| 4 | #4 Bearcat | 60.7 | 2/1 | 1.0 (fav) | **1st** | 4.00 | 4.00 |
| 7 | #4 Rose Darling | 60.6 | 6/1 | 5.5 | 5th | 0 | 0 |
| 9 | #5 Romeo Spikes | 68.3 | 5/2 | 0.5 (fav) | 5th | 0 | 0 |

**17 of 40** qualifying races so far: **4 W, 9 in the first two**. $2 win
$18.40 on $34, $2 place $32.10 on $34. Largest payouts: win $6.20 (11/11
Snazzy Gal), $5.20 (11/12 CF Spunie Style); place $6.40 (11/13 Cajun
Coaster), $5.00 (11/11 Snazzy Gal).

### Over-4-1 subset: ML or final odds?

**The pre-registration uses final odds** (PHASE_6D_ROADMAP, `fabee7c`:
"Report the **over-4-1 subset** (final odds) separately"; `top1_roi.py`
splits at 2-1, 4-1 inclusive and over 4-1). Both ways so far, "over 4-1"
meaning odds above 4.0:

| basis | races | horses | finishes | $2 win | $2 place |
|---|---|---|---|---|---|
| **Final odds (as registered)** | 3 | 11/06 Vineaux (4.1), 11/13 Cajun Coaster (9.6), 11/14 Rose Darling (5.5) | 4th, **2nd**, 5th | $0 on $6 | $6.40 on $6 |
| Morning line | 3 | 11/06 Mahoney Road (6/1, went 1.9), 11/13 Cajun Coaster (9/2), 11/14 Rose Darling (6/1) | **2nd**, **2nd**, 5th | $0 on $6 | $9.80 on $6 |

Two of the three overlap. Vineaux (3/1 ML) drifted over 4-1 and Mahoney Road
(6/1 ML) was bet down to 1.9. 11/06 The Red Wicked One (4/1 ML, 3.8) is
exactly 4-1 on the line, so "over" leaves it out either way. Rose Darling
(6/1 ML, 5.5 final) is over on both. The ML is known before the bet and
final odds are not, so the choice matters if the subset ever becomes a bet
rule; the definition is Doug's to fix before race 40.

## Name matching ON: 11/05–11/14 vs the earlier 1.3.2 cards

Same basis as before (record run, among starters, logged P(ITM) not
renormalised; #1 re-ranked among runners; DNFs count as starters that
missed the board).

| card | name matching | races | starters | #1 W | #1 ITM | sum P(ITM) | ITM | P(ITM) LL | Brier | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.3.2 off (7 cards, 10/22–11/04) | off | 59 | 505 | 12 | 32 (54%) | 158.82 | 177 | 0.609 | 0.210 | $67.80 (−42.5%) |
| 11/05 | on | 8 | 61 | 3 | 7 | 21.82 | 24 | 0.622 | 0.218 | $19.20 |
| 11/06 | on | 9 | 77 | 2 | 5 | 24.27 | 27 | 0.631 | 0.218 | $8.60 |
| 11/07 | on | 9 | 75 | 1 | 5 | 23.12 | 27 | 0.643 | 0.227 | $5.20 |
| 11/11 | on | 8 | 68 | 4 | 7 | 23.15 | 24 | 0.580 | 0.199 | $24.00 |
| 11/12 | on | 8 | 60 | 3 | 7 | 23.02 | 24 | 0.5275 | 0.176 | $12.20 |
| 11/13 | on | 9 | 72 | 2 | 7 | 25.56 | 27 | 0.5965 | 0.205 | $9.80 |
| **11/14** | **on** | 11 | 89 | 2 | 7 | 32.17 | 33 | **0.5940** | **0.206** | $11.80 |
| 1.3.2 on (7 cards) | on | 62 | 502 | 17 | 45 (73%) | 173.10 | 186 | **0.6010** | **0.208** | $90.80 (−26.8%) |

ON stays just below OFF on log loss (0.6010 vs 0.609) and Brier (0.208 vs
0.210); calibration on the card was close (sum P(ITM) 32.17 vs 33 ITM). Still
too close to call; the read-only paired OFF/ON check from the `-run.bak`
files decides it.

## Data issues on the model's top picks (`tracking/top_pick_data_issues.csv`)

* **R6 #3 Hap Hot (2nd at 6.0-1): stale last race.** PP last race OP
  2026-02-19 (268 days, track not in the corpus); DB last race DED
  2025-11-14 (365 days).
* **R8 #5 Luck of the Tide (3rd): first-time starter with a new trainer.**
  Randy Nunley has no DB history (flagged new at the card load; genuinely
  new, not a name miss). R8 was six first-time starters, race coverage about
  50%.
* The other nine #1s had their last race in the DB (PP days off = DB days,
  15–75) and jockey and trainer history. Also noted in the rows: R1's
  reranker change, R4's #2 late jockey change, R7's base #1 scratch, and the
  R2 and R9 scratches (none in the top four).

## Missing-last-race horses (`missing_last_race_tally.py --to 2026-11-14`)

Five flagged starters tonight, **all no-data tracks** (R9 #2 Banquet Chef,
LAD 2021, was scratched and is not counted):

| R | horse | last race | model rank | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 1 | #6 Jinxzi | KEE 10/21 | 4 of 8 | 33.6 | **3rd** | 5.5 |
| 5 | #5 Ruiz Junior | ARP 8/07 | 7 of 10 | 23.6 | **2nd** | 15.3 |
| 6 | #3 Hap Hot | OP 2/19 | **1 of 8** | 53.5 | **2nd** | 6.0 |
| 6 | #6 Topofthe Rock | SWF 9/25 | 8 of 8 | 17.1 | 6th | 62.8 |
| 6 | #8 Double Edge Sword | DEL 9/30 | 3 of 8 | 47.8 | **3rd** | 1.7 (fav) |

Tonight: **no-data tracks 5 starters, ITM 4 vs 1.8 expected, W 0 vs 0.6**;
data tracks 0.

| group (11/04–11/14) | starters | ITM | exp ITM | W | exp W |
|---|---|---|---|---|---|
| data tracks | 21 | 7 | 6.5 | 1 | 2.1 |
| no-data tracks | 35 | **18** | **11.1** | 3 | 3.6 |
| both | 56 | 25 | 17.6 | 4 | 5.7 |
| all other starters | 515 | 185 | 177.2 | 66 | 59.3 |

The no-data group keeps beating its P(ITM) (18 vs 11.1); the data-track group
is on expectation.

## First-time starters

| R | first-time starters | finishes | model ranks | winner |
|---|---|---|---|---|
| 3 (MSW) | #1 Midnight Rayne, #2 Little Miss Mo | 8th (6.0-1), 4th (31.2-1) | 8th, 9th of 9 | #9 Maximum Return (not a first-timer) |
| 11 (MCL) | #1 Please Hold | DNF (pulled up, 8.7-1) | 5th of 10 | #3 Ariceli Aces (not a first-timer) |
| 8 (2yo Alw 30000nc) | all six | 1-2-3-4-5, B.G.'s Song DNF | – | #1 Sic'em Now Now |

R8 is an allowance, not a maiden, so it stays out of the queued maiden
check. Tally: **10 maidens with first-time starters, a first-time starter won
4** (R3 and R11 added, neither won).

## Low-coverage (<65%) horses

R3 #1 Midnight Rayne (53%, 8th), #2 Little Miss Mo (51%, 4th at 31.2-1);
R8 all six (48–52%; #5 Luck of the Tide, the #1, 3rd); R11 #1 Please Hold
(54%, DNF).

## Benchmarks: Don and Doug

* All three sent picks before post. Doug's picks were all regular picks (no
  passes, no best guesses); he lost none to scratches. Don lost his R7 #1
  (#1 Watering).
* Doug's #1 = the model's #1 in R1, R5, R9, R11 (the four consensus races).
  Don's #1 = the model's in R1, R2, R5, R9, R11, and = Doug's in R1, R5, R9,
  R10, R11.

| R | Don | Don #1 fin | Don overlap | Doug | Doug #1 fin | Doug overlap | model | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1-5-4-7 | 4th | 1/3 | 1-4-6-8 | 4th | 2/3 | 1-4-3-6 | 4th | 2/3 |
| 2 | 5-2-7-1 | **2nd** | 1/3 | 7-2-5-8 | 7th | 1/3 | 5-2-7-4 | **2nd** | 1/3 |
| 3 | 3-4-7-8 | **2nd** | 1/3 | 1-4-3-7 | 8th | 1/3 | 4-3-7-8 | 5th | 1/3 |
| 4 | 3-4-9-2 | **3rd** | 2/3 | 9-4-3-2 | 5th | 2/3 | 4-3-9-2 | **1st** | 2/3 |
| 5 | 8-5-1-9 | **3rd** | 2/3 | 8-7-5-1 | **3rd** | 2/3 | 8-2-9-7 | **3rd** | 1/3 |
| 6 | 8-2-3-7 | **3rd** | 2/3 | 2-3-8-4 | 7th | 2/3 | 3-2-8-7 | **2nd** | 2/3 |
| 7 | 6-2-5 | **1st** | 2/3 | 5-6-4-3 | **2nd** | 2/3 | 4-6-5-3 | 5th | 2/3 |
| 8 | 3-4-5-6 | 4th | 2/3 | 4-1-2-6 | **2nd** | 2/3 | 5-1-6-2 | **3rd** | 2/3 |
| 9 | 5-3-8-1 | 5th | 1/3 | 5-3-8-1 | 5th | 1/3 | 5-3-8-1 | 5th | 1/3 |
| 10 | 3-4-5-6 | 6th | 2/3 | 3-6-4-7 | 6th | 2/3 | 6-1-4-3 | **1st** | 2/3 |
| 11 | 2-3-7-6 | **2nd** | 2/3 | 2-7-6-4 | **2nd** | 1/3 | 2-7-3-4 | **2nd** | 2/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | **2** | **7/11** | 18/33 | 0 | **1 (R1 $101.43)** | 0 | $11.80 on $22 (−46.4%) |
| Don | 1 | **7/11** | 18/33 | 0 | 0 | 1 (R11 $31.20) | $7.80 on $22 (−64.5%) |
| Doug | 0 | 4/11 | 18/33 | 0 | 0 | **2 (R7 $9.80, R8 $26.10)** | $0 on $22 |

* **Don's #1 won R7** (#6 Madison Rae, $7.80, his #1 after Watering
  scratched). R9 had the same top four (5-3-8-1) for all three sources.
* **Doug's #1 won none**; his R7 and R8 top two were the exactas.

### Consensus #1s (`tracking/consensus_top1.csv`)

| R | horse | odds | finished |
|---|---|---|---|
| 1 | #1 Footprint | 1.3 (fav) | 4th |
| 5 | #8 Easy Like Breezy | 1.0 (fav) | **3rd** ($2.60 show) |
| 9 | #5 Romeo Spikes | 0.5 (fav) | 5th |
| 11 | #2 C Note Gia | 3.0 | **2nd** ($5.00 / $4.00) |

No winners. Doug's R1 superfecta wheel used Footprint. File now **8 W, 18
ITM from 26**.

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **11/05–11/14** (name matching ON) | Model | 62 | 17 | 45 (73%) | 106/186 | −26.8% |
| | Don | 62 | 18 | 42 (68%) | 106/186 | −10.3% |
| | Doug | 62 | 17 | 34 (55%) | 94/186 | −19.2% |
| **1.3.2** (10/22–11/14) | Model | 121 | 29 | 77 (64%) | 196/363 | −34.5% |
| | Don | 121 | 37 | 78 (64%) | 206/363 | −12.1% |
| | Doug | 119 | 36 | 70 (59%) | 184/357 | −15.5% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.7% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (20 cards) | Model | 173 | 46 | 106 (61%) | 273/519 | −22.1% |
| | Don | 164 | 52 | 104 (63%) | 273/492 | −8.8% |
| | Doug | 127 | 39 | 73 (57%) | 194/381 | −13.3% |
| | Doug, without best guesses | 124 | 37 | 71 (57%) | 188/372 | −16.8% |

The meet $2 win lines ($269.40 model, $299.20 Don, $220.20 Doug) match the
ticket replay (re-run 11/15 with the 11/14 card: 34 rows added, all 578
earlier rows unchanged).

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result |
|---|---|---|---|
| POD | R6 #8 Double Edge Sword (ML 3/1) | – | **3rd** at 1.7-1 (fav; $2.60 show) |
| EP4 R2–R5 | 1,2,5,7 / 3,4,7 / 3,4 / 1,5,8 (72 × $0.50) | $36 | lost: R2 (winner #4 Creole Lady, 10.4-1); R3 and R5 also missed, R4 hit |
| LP4 R8–R11 | 3,4,5,6 / 5 / 3,4,5 / 2,3,7 (36 × $0.50) | $18 | lost: R8 (winner #1 Sic'em Now Now); R9 and R10 also missed, R11 hit |

$54 on the two Pick 4s, $0 back.

### Doug's bets (`tracking/doug_bets.csv`)

**11/14**

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 1 | superfecta wheel, $0.10 | 1,4,6 / 1,4,6 / 1,4,6 / ALL (30 combos) | $3.00 | lost (3-4-6-1; #3 not in his top three) |
| CT | 7 | superfecta key, $0.10 | 4 / 1,6,8,9 / 1,6,8,9 / 1,6,8,9 (24 combos) | $2.40 | lost |

Night: **$5.40 wagered, $0 returned, −$5.40.** DED wagering $3.00,
**qualifies for the DED PP rebate.** CT is a personal bet, kept out of DED
scoring and the ticket replay.

**11/15** (no DED card; personal bets only)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| WO | 9 | trifecta key, $0.20 | 2 / 5,6 / 5,6 | $0.40 | lost |
| DMR | 3 | show, $2 | #2 | $2.00 | lost |
| DMR | 2 | superfecta box, $0.10 | 1,4,5,6 (24 combos) | $2.40 | **won $12.66** (+$10.26) |
| WO | 6 | trifecta box, $0.20 | 1,2,7 (6 combos) | $1.20 | lost |

Day: **$6.00 wagered, $12.66 returned, +$6.66.**

**Bankroll** (`tracking/bankroll.csv`): from $66.20 after 11/13: +$3.85
(11/13 rebate, 11/14 5:26 AM), −$3.85 (11/14 PP, 8:20 AM), −$5.40 (11/14
bets), +$6.66 (11/15 bets net) = $67.46, then **+$3.85 for the 11/14 rebate,
"inferred from balance; not yet seen in history" = $71.31**, which matches
the TwinSpires balance Doug reported. Confirm the 11/14 rebate on the next
reconcile.

## Watch list

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 3 | #5 Visions of War | J Devin Magnon | 7 of 9 | 20.5 | 9th | 55.7 |
| 4 | #5 The Boyz Priority | T Ronnie Ward | 5 of 9 | 29.8 | 4th | 12.5 |
| 8 | #2 Mosquito Dance | T Ronnie Ward | 4 of 6 | 50.9 | 5th | 12.9 |
| 8 | #6 B.G.'s Song | T Ronnie Ward | 3 of 6 | 52.7 | DNF (distanced) | 5.0 |
| 10 | #3 Liken It | J Devin Magnon, T Rylee Magnon | 4 of 8 | 39.9 | 6th | 3.1 |
| 10 | #4 Channelfortynine | T Ronnie Ward | 3 of 8 | 41.6 | **2nd** | 2.0 (fav) |
| 10 | #8 Chamois' Splendor | T Ronnie Ward | 7 of 8 | 28.9 | 8th | 38.2 |

No Calhoun starters. Meet tally after 11/14 (`watch_people_tally.csv`;
logged record runs only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 41 | 4 | 16 | 13.24 | 16 | **+2.76** (was +3.80) |
| J Devin H. Magnon | 34 | 4 | 10 | 10.83 | 10 | −0.83 (was −0.23) |
| T Rylee Magnon | 11 | 1 | 2 | 3.67 | 2 | −1.67 (was −1.27) |
| T W.B. Calhoun | 19 | 4 | 9 | 6.24 | 9 | +2.76 (no starter) |

Ward had five starters and one on the board (summed P(ITM) 2.04).

**Trip note (Doug): R7 #5 Blue Heavenly went about 4 wide into the turn and
ran 2nd** at 1.7-1 (fav), beaten 1½ by the wire-to-wire winner. The chart
says "came around the final turn on the outside ... a clear second" (calls
3rd, 3rd, 3rd, 2nd by a head in the stretch). Model 3rd of 6 (46.6). **Added
to `watch_list.csv`** as a horse, the same as Cincy's Player (10/17).

## Things that look off

1. **Javier Antonio Hernandez is off for the fourth night** (11 mounts
   replaced over 11/11–11/14, 6 hit the board). Tonight's only mount ran 3rd
   under Lozada with the apprentice allowance gone (115, not 110). The model
   keeps pricing him because he is still on the PP.
2. **The heavy favourites failed:** Romeo Spikes (0.5-1, P(ITM) 68.3, a
   high-confidence and consensus #1) 5th; Footprint (1.3-1, the reranked #1,
   also high-confidence and consensus) 4th.
3. **The high-confidence over-4-1 definition:** the pre-registration says
   final odds; the ML version differs in one horse each way so far (table
   above). Doug to fix it before race 40.
4. **Four non-finishers** on one card (two first-time starters). They are
   scored as starters off the board; nothing to fix.
5. **The 11/14 rebate is inferred from the balance**, not yet seen in the
   TwinSpires history. Confirm on the next reconcile.

## Queued (not started)

* Read-only paired name-matching OFF/ON check, now on 11/05–11/14, from the
  `-run.bak` files.
* PP-date recency fix (top of the queue; needs the OFF/ON validation first).
* First-time-starter maiden check (10 maidens with first-time starters; a
  first-time starter won 4).
* MNR 10/05 chart: retry after 11/21. Non-corpus tracks decision.
