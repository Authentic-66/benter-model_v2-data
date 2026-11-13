# DED 2026-11-12 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Twelfth card
on 1.3.2, **fifth with name matching ON**. One logged run, the record:
`generated_at = 2026-11-12T13:59:25`, pre-race, bridged, 67 rows (full
fields), commit `1711b04` (`picks/DED_2026-11-12_20261112-1359.*`).

Read-only on the live model: no changes to 1.3.2, the rerankers or the
Piece 1–4 code.

## Pre-race

* **Picks logged before post:** model 13:59 CST (`1711b04`), Don and Doug
  (`c3a13ac`). The four high-confidence qualifiers (R3, R4, R6, R8) and the
  three reranker #1 changes (R2, R5, R7) were logged with the card.
* **Scratches (Doug's list, all confirmed by the chart):** R1 #2 Golden
  Penelope (vet) and #10 Leslie's Lucky (vet), R3 #1 Little Miss Jess (vet),
  R5 #5 Thunder Kiss (vet), R8 #7 Global Dawn (trainer), #11 Midnight
  Cigarette (also-eligible, not drawn in) and #12 Louie Vee (vet). **No
  others.** None was anyone's #1.
* **Late jockey changes (Doug's list; no others on the chart):**
  * **Javier Antonio Hernandez off all his mounts for the second night
    running** (his R1 #2 Golden Penelope scratched): R2 #7 Brisa Veloz (Alex
    Birzer), R4 #5 Whiskeyand Easy (Chris Rosier), R7 #1 Hey Boss (Jose
    Rodriguez).
  * **Jansen Melancon off R3 #3 Ocean's Appeal** (Harry Hernandez rode). That
    was the model's #1 and its highest P(ITM) so far (88.4): the model priced
    the wrong rider, as flagged at the card build.

### Consensus (post-scratch rule, Doug 11/05)

| R | model | Don | Doug | consensus |
|---|---|---|---|---|
| 1 | 3 | 3 | 3 | **#3 True Fire** |
| 2 | 4 | 3 | 7 | no |
| 3 | 3 | 3 | 4 | no |
| 4 | 4 | 4 | 2 | no |
| 5 | 3 | 7 | 4 | no |
| 6 | 4 | 6 | 3 | no |
| 7 | 2 | 8 | 8 | no |
| 8 | 1 | 1 | 10 | no |

## Load (2026-11-13 morning)

* `load_chart.py` on `Delta Downs/ded-results-2026/DED111226USA.pdf`:
  `backup verified: racing_full.db.pre-ded1112res.bak`, `+8r 60e (purged 67
  first) [replaced a pre-race card]`, `"errors": 0`, `loaded: DED 2026-11-12
  8 races, 60 entries, 60 with a finish; replaced a pre-race card of 67
  entries`. 67 − 60 = the 7 scratches.
* Spot checks: **R1 official 3-1-5-4 and R8 1-8-10-3, as expected.**
* **No DQs, no dead heats, no non-betting starters, no non-finishers.** R3
  had a stewards' inquiry; no action was taken.
* Speed figures and features were not rebuilt here (the next card build does
  that).
* Pick payouts (per $0.50):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 3-5-4 | 6.65 |
  | Pick 3 | R2–R4 | 5-4-2 | 8.00 |
  | Pick 3 | R3–R5 | 4-2-4 | 11.20 |
  | Pick 4 (early) | R2–R5 | 5-4-2-4/5 | **27.15** |
  | Pick 5 (early) | R1–R5 | 2/3/10-5-4-2-4/5 | 51.90 |
  | Pick 3 | R4–R6 | 2-4-4 | 11.85 |
  | Pick 3 | R5–R7 | 4-4-8 | 9.15 |
  | Pick 3 | R6–R8 | 4-8-1 | 10.10 |
  | Pick 4 (late) | R5–R8 | 4/5-4-8-1/7/11/12 | **15.45** |
  | Pick 5 (late) | R4–R8 | 2-4/5-4-8-1/7/11/12 | 68.10 |

  Scratched horses are replaced by the favourite (R1 #2/#10 → #3, R5 #5 →
  #4, R8 #7/#11/#12 → #1). The R4–R5 daily double 2-4 paid $7.40; a $1
  consolation (2-5, the scratched #5) paid $2.80.
* `score_predictions.py --track DED --date 2026-11-12`: top pick ITM **7 of
  8**, won 3 of 8; top-pick show ROI +2.5%; all horses ITM 24 of 60. 60 rows
  scored (2,557 total). No logged #1 scratched.

### Late jockey changes (`tracking/late_jockey_changes.csv`)

| R | horse | PP rider → rode | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 2 | #7 Brisa Veloz | J. A. Hernandez → Alex Birzer | 3 of 7 | 49.9 | 5th | 4.1 |
| 3 | #3 Ocean's Appeal | Jansen Melancon → Harry Hernandez | **1 of 5** | 88.4 | **2nd** | 0.7 (fav) |
| 4 | #5 Whiskeyand Easy | J. A. Hernandez → Chris Rosier | 4 of 8 | 38.8 | **3rd** | 4.9 |
| 7 | #1 Hey Boss | J. A. Hernandez → Jose Rodriguez | 8 of 8 | 16.6 | 6th | 26.9 |

Four horses, summed P(ITM) 1.94, **ITM 2**. Across 11/05–11/12 the list has
23 rows (summed P(ITM) 9.09, ITM 13). J. A. Hernandez alone: 7 mounts over
two nights, summed P(ITM) 2.32, ITM 4.

## Per race (re-ranked among horses that ran)

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3-8-5-6 | 3-1-5-4 | **1st** (fav) | 1 of 8 (1.0-1) | 2/3 | miss | miss (2 of 4) | 3-8 miss | 46.53 |
| 2 | 4-5-7-2 | 5-3-1-4 | 4th | 2 of 7 (1.8-1) | 1/3 | miss | miss (2 of 4) | 4-5 miss | 7.09 |
| 3 | 3-4-2-6 | 4-3-2-6 | **2nd** (fav) | 2 of 5 (1.1-1) | **3/3** | **hit** | **hit** | **3-4 hit** | 0.57 |
| 4 | 4-3-2-5 | 2-4-5-3 | **2nd** | 3 of 8 (1.6-1) | 2/3 | miss | **hit** | 4-3 miss | 9.72 |
| 5 | 3-8-4-6 | 4-9-3-7 | **3rd** | 3 of 9 (0.9-1) | 2/3 | miss | miss (2 of 4) | 3-8 miss | 20.03 |
| 6 | 4-1-3-6 | 4-1-6-5 | **1st** (fav) | 1 of 6 (1.6-1) | 2/3 | miss | miss (3 of 4) | **4-1 hit** | 2.72 |
| 7 | 2-7-5-8 | 8-7-2-4 | **3rd** | 4 of 8 (1.9-1) | 2/3 | miss | miss (3 of 4) | 2-7 miss | 15.79 |
| 8 | 1-10-8-9 | 1-8-10-3 | **1st** (fav) | 1 of 9 (0.5-1) | **3/3** | **hit** | miss (3 of 4) | 1-10 miss | 5.59 |

**Model:** #1 **won 3 of 8** (R1 True Fire $4.00, R6 CF Spunie Style $5.20,
R8 Dragon Navy $3.00) and was **ITM in 7 of 8**. $2 win on the #1: $12.20 on
$16 (−23.8%). Top-3 overlap 17 of 24.

* **Seven of eight winners were the favourite** (0.5-1 to 1.9-1); R3's Gem
  Sauce was the 1.1-1 second choice. The model's #1 was the
  favourite in four races (R1, R3, R6, R8): three won, R3 ran 2nd.
* **R3:** the model's top four finished as the top four (3-4-2-6 vs
  4-3-2-6); Ocean's Appeal (0.7-1) was outfinished by #4 Gem Sauce, the
  model's 2nd.
* **R2 and R5:** the base #1 won and the reranker had moved it to 2nd (R2 #5
  Fulla Wicked Sugar, 1.8-1) and 3rd (R5 #4 Shred It Up, 0.9-1). See below.
* **R5:** #9 Zong's Creed (23.7-1, model 7th of 9) ran 2nd; #8 Donegal Now
  (model 2nd) "was shut off at the start and showed little" (8th).
* **R7:** #8 Timeto Party (1.9-1 fav, model 4th) won; the reranked #1
  Underhill's Tab ran 3rd and the base #1 Caught Off Guard 7th.

### Reranker

Three #1 changes, the same pre-race and among runners:

| R | base #1 | finished | reranked #1 | finished | race P(ITM) log loss, base → reranked |
|---|---|---|---|---|---|
| 2 | #5 Fulla Wicked Sugar (1.8-1 fav) | **1st** | #4 Sassi Idol (4.7-1) | 4th | 4.506 → 4.690 (worse) |
| 5 | #4 Shred It Up (0.9-1 fav) | **1st** | #3 Cinco Blake (2.3-1) | **3rd** | 4.970 → 5.134 (worse) |
| 7 | #5 Caught Off Guard (6.6-1) | 7th | #2 Underhill's Tab (2.4-1) | **3rd** | 4.388 → 4.016 (better) |

On ITM: one for the reranker (R7), one for the base (R2), R5 both. On wins
the base took two winners away from the reranker. Over the three races the
summed log loss is about even (13.864 base vs 13.840 reranked), and over the
whole card the reranker lowered it (0.542 → 0.528 per starter).

**Reranker review rule: 7 of 40** qualifying races (11/05 R4, 11/06 R4,
11/07 R6, R9, 11/12 R2, R5, R7). Reranked #1 **2 W / 5 ITM**, base #1 **2 W /
2 ITM**. The rule judges ITM and log loss at 40, not wins; no reading until
then.

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #8 Anna K | 41.8 → 47.8 (+6.0) | 2 → 2 | 7th (3.2-1) |
| 1 | #5 Excusemelady's | 36.8 → 42.8 (+6.0) | 4 → 3 | **3rd** (8.4-1) |
| 3 | #3 Ocean's Appeal | 81.9 → 88.4 (+6.5) | 1 → 1 | **2nd** |
| 4 | #4 Julia's Warrior | 56.2 → 65.3 (+9.2) | 1 → 1 | **2nd** |
| 4 | #7 Unfathomed | 30.8 → 24.2 (−6.7) | 6 → 6 | 5th (34.2-1) |
| 5 | #10 Carrythe Flag | 17.5 → 25.0 (+7.4) | 7 → 6 | 5th (18.4-1) |
| 7 | #2 Underhill's Tab | 47.7 → 54.3 (+6.6) | 3 → 1 | **3rd** |
| 7 | #7 Ambridge | 48.7 → 54.0 (+5.3) | 2 → 2 | **2nd** |
| 7 | #5 Caught Off Guard | 49.3 → 42.6 (−6.6) | 1 → 3 | 7th |
| 7 | #3 Mr. Faversham | 41.2 → 35.4 (−5.9) | 4 → 6 | 5th |
| 8 | #1 Dragon Navy | 60.7 → 66.9 (+6.2) | 1 → 1 | **1st** |

9 of 11 went the right way (Anna K and Carrythe Flag did not). In R1 and R6
the reranker changed the third pick: top-3 overlap 17 vs base 16.

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 11/12 | 8 | 3 | 3 / 7 / $12.20 (−23.8%) | 5 / 7 / $21.60 (+35.0%) |
| 1.3.2 (10/22–11/12) | 101 | 17 | 25 / 63 / $137.00 (−32.2%) | 26 / 60 / $147.40 (−27.0%) |
| **Meet** | 153 | 22 | 42 / 92 / $247.80 (−19.0%) | 43 / 91 / $295.60 (−3.4%) |

`model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
scratches excluded): **with-reranker 59/92 vs base-only 56/92** (+3, as
before). Top pick ITM 64.1%, win 25.0%; show ROI −18.2%. No alerts.

## High-confidence #1 forward test (`tracking/high_conf_top1.csv`)

Four qualifiers, all still the post-scratch #1 (every scratch was in another
race):

| R | horse | P(ITM) | odds | finished | $2 win | $2 place |
|---|---|---|---|---|---|---|
| 3 | #3 Ocean's Appeal | 88.4 | 0.7 (fav) | 2nd | 0 | 2.10 |
| 4 | #4 Julia's Warrior | 65.3 | 3.6 | 2nd | 0 | 3.40 |
| 6 | #4 CF Spunie Style | 65.6 | 1.6 (fav) | **1st** | 5.20 | 2.80 |
| 8 | #1 Dragon Navy | 66.9 | 0.5 (fav) | **1st** | 3.00 | 2.40 |

All four ran 1st or 2nd. **10 of 40** qualifying races so far: **3 W, 6 in
the first two**. $2 win $14.40 on $20, $2 place $19.10 on $20. Over-4-1
subset: still 1 race (11/06 Vineaux, 4th). No reading until 40.

## Name matching ON: 11/05–11/12 vs the earlier 1.3.2 cards

Same basis as before (record run, among starters, logged P(ITM) not
renormalised; #1 re-ranked among runners).

| card | name matching | races | starters | #1 W | #1 ITM | sum P(ITM) | ITM | P(ITM) LL | Brier | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.3.2 off (7 cards, 10/22–11/04) | off | 59 | 505 | 12 | 32 (54%) | 158.82 | 177 | 0.609 | 0.210 | $67.80 (−42.5%) |
| 11/05 | on | 8 | 61 | 3 | 7 | 21.82 | 24 | 0.622 | 0.218 | $19.20 |
| 11/06 | on | 9 | 77 | 2 | 5 | 24.27 | 27 | 0.631 | 0.218 | $8.60 |
| 11/07 | on | 9 | 75 | 1 | 5 | 23.12 | 27 | 0.643 | 0.227 | $5.20 |
| 11/11 | on | 8 | 68 | 4 | 7 | 23.15 | 24 | 0.580 | 0.199 | $24.00 |
| **11/12** | **on** | 8 | 60 | 3 | 7 | 23.02 | 24 | **0.5275** | **0.176** | $12.20 |
| 1.3.2 on (5 cards) | on | 42 | 341 | 13 | 31 (74%) | 115.37 | 126 | **0.604** | **0.209** | $69.20 (−17.6%) |

**11/12 is the best 1.3.2 card on log loss and Brier, ON or OFF**, and for
the first time the ON cards together are below OFF (0.604 vs 0.609). A
chalky night (seven favourites won) helps any model's log loss, so
this still does not decide anything: the read-only paired OFF/ON check from
the `-run.bak` files does.

## Data issues on the model's top picks (`tracking/top_pick_data_issues.csv`)

**No data gaps.** All eight post-scratch #1s had their last race in the DB
(PP days off = DB days, 14–76 days) and jockey and trainer history. Noted in
the rows: **R3 Ocean's Appeal's late jockey change** (Melancon off), and the
three reranker #1s (R2, R5, R7).

## Missing-last-race horses (read-only, running tally)

Five flagged starters tonight:

| R | horse | last race | model rank | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 2 | #1 Papas Lady | BTP 10/01 | 6 of 7 | 36.5 | **3rd** | 3.6 |
| 2 | #2 Kingston Lady | EUR 10/17 | 4 of 7 | 47.3 | 6th | 32.2 |
| 4 | #1 Scallywag | HCN 8/21 | 5 of 8 | 34.5 | 8th | 17.0 |
| 5 | #7 H Q Wilson | DMR 8/16 | 5 of 9 | 34.1 | 4th | 12.4 |
| 5 | #10 Carry the Flag | GIL 8/16 | 6 of 9 | 25.0 | 5th | 18.4 |

Tonight W 0 vs 0.6 expected, ITM 1 vs 1.8. **Tally 11/04–11/12: 47
starters, ITM 19 vs 14.4 expected, W 4 vs 4.7.** All other 11/12 starters: W
8 vs 7.2 expected, ITM 23 vs 21.2. (R8 #12 Louie Vee, LS, scratched. Run
after the chart load, the script also lists the scratched DED horses as
"horse not matched": they were purged with the card, so that is not a data
gap.)

## First-time starters in tonight's maidens

| R | first-time starters | finishes | model ranks | winner |
|---|---|---|---|---|
| 1 (MCL) | #1 Strike Power Queen | **2nd** (11.9-1) | 6th of 8 | #3 True Fire (raced), the model's #1 |
| 8 (MCL) | #6 Gabbys Wings | 9th | 7th of 9 | #1 Dragon Navy (raced), the model's #1 |

R3 (MSW) and R5 (MCL) had no first-time starters. Tally for the queued
check: **7 maidens with first-time starters, first-time starter won 3**.

## Low-coverage (<65%) horses

R1 #1 Strike Power Queen (54%, **2nd**), R2 #1 Papas Lady (64%, BTP shipper,
**3rd**), R8 #6 Gabbys Wings (54%, 9th).

## Benchmarks: Don and Doug

* All three were logged before post.
* Scratches: **Don** lost his R8 4th (#7, no alt given). **Doug** lost
  nothing.
* Doug's picks were all regular picks (no passes, no best guesses).

| R | Don | Don #1 fin | Don overlap | Doug | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 3-7-6-5 | **1st** | 1/3 | 3-8-7-9 | **1st** | 1/3 | **1st** | 2/3 |
| 2 | 3-5-1-4 | **2nd** | 3/3 | 7-4-5-1 | 5th | 1/3 | 4th | 1/3 |
| 3 | 3-4-6-5 | **2nd** | 2/3 | 4-3-6-2 | **1st** | 2/3 | **2nd** | 3/3 |
| 4 | 4-2-3-6 | **2nd** | 2/3 | 2-4-1-3 | **1st** | 2/3 | **2nd** | 2/3 |
| 5 | 7-4-8-3 | 4th | 1/3 | 4-6-7-3 | **1st** | 1/3 | **3rd** | 2/3 |
| 6 | 6-4-1-3 | **3rd** | 3/3 | 3-4-5-2 | 6th | 1/3 | **1st** | 2/3 |
| 7 | 8-2-5-7 | **1st** | 2/3 | 8-5-6-3 | **1st** | 1/3 | **3rd** | 2/3 |
| 8 | 1-10-8 | **1st** | 3/3 | 10-3-1-6 | **3rd** | 2/3 | **1st** | 3/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | 3 | **7/8** | **17/24** | 2 (R3 $0.57, R8 $5.59) | **2 (R3 $0.57, R4 $9.72)** | 2 (R3 $2.60, R6 $7.80) | $12.20 on $16 (−23.8%) |
| Don | 3 | **7/8** | **17/24** | **3 (R2 $7.09, R6 $2.72, R8 $5.59)** | 1 (R2 $7.09) | **3 (R2 $12.20, R3 $2.60, R4 $9.20)** | $12.80 on $16 (−20.0%) |
| Doug | **5** | 6/8 | 11/24 | 0 | 1 (R3 $0.57) | 2 (R3 $2.60, R4 $9.20) | **$23.00 on $16 (+43.8%)** |

* **Doug's #1 won five races** (R1, R3, R4, R5, R7), the most of the three on
  11/12. His R4 and R5 #1s were the two legs of his daily double.
* Don's top two hit every Pick (b) ticket in the replay; his real Pick 4s
  hit too (below).

### Consensus #1s (`tracking/consensus_top1.csv`)

* **R1 #3 True Fire** (1.0-1 fav): **won**, $4.00 / $2.80 / $2.40; "dueled
  down the home stretch with Strike Power Queen and prevailed". Not bet.

So far: **8 W, 15 ITM from 20**. $2 win on all twenty: $36.20 on $40
(−9.5%); $2 show $36.90 on $40 (−7.8%).

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **11/05–11/12** (name matching ON) | Model | 42 | 13 | 31 (74%) | 70/126 | −17.6% |
| | Don | 42 | 15 | 31 (74%) | 75/126 | +9.3% |
| | Doug | 42 | 13 | 23 (55%) | 61/126 | −6.2% |
| **1.3.2** (10/22–11/12) | Model | 101 | 25 | 63 (62%) | 160/303 | −32.2% |
| | Don | 101 | 34 | 67 (66%) | 175/303 | −4.4% |
| | Doug | 99 | 32 | 59 (60%) | 151/297 | −9.2% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.7% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (18 cards) | Model | 153 | 42 | 92 (60%) | 237/459 | −19.0% |
| | Don | 144 | 49 | 93 (65%) | 242/432 | −2.8% |
| | Doug | 107 | 35 | 62 (58%) | 161/321 | −7.1% |
| | Doug, without best guesses | 104 | 33 | 60 (58%) | 155/312 | −11.1% |

The meet $2 win lines ($247.80 model, $279.80 Don, $198.80 Doug) match the
ticket replay.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R2 #3 Kaydences Calamity (ML 5-1) | | **2nd** at 3.7-1 (place $4.80, show $3.40) | — | — |
| EP4 (R2–R5) | 1-3-5 / 3-4 / 2-4 / 1-3-4-7-8 (60 combos) | $30 | **HIT** | **4/4** | 5-4-2-4 paid **27.15** |
| LP4 (R5–R8) | 1-3-4-7-8 / 1-3-4-6 / 2-5-8 / 1 (60 combos) | $30 | **HIT** | **4/4** | 4-4-8-1 paid **15.45** |

* **Both Pick 4s hit**, but on a night of winning favourites they paid less
  than they cost: **$60 wagered, $42.60 back (−$17.40).**
* His POD ran 2nd to the gate-to-wire favourite.

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 4–5 | daily double, $1 | 2,4 / 4,7 (4 combos) | $4.00 | **won: 2-4 paid $7.40** |
| CT | 1 | superfecta wheel, $0.10 | 1,2,6 / 1,2,6 / 1,2,6 / ALL (18 combos) | $1.80 | lost (a 24-1 shot ran 2nd) |

Night total: **$5.80 wagered, $7.40 returned, +$1.60.** DED wagering $4.00,
**qualifies for the DED PP rebate**. CT is a personal bet, kept out of DED
scoring and the ticket replay.

**Bankroll** (`tracking/bankroll.csv`): from the reported $73.00, the 11/12 PP
purchase (−$3.85, **assumed**: not reported separately, same price as 11/11),
−$4.00, −$1.80, +$7.40 = **$70.75 computed**, no balance reported to check
against. Both rebates (11/11 and 11/12, +$3.85 each) are still to be logged
when they land; with them the balance would be $78.45.

## Watch list

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 6 | #6 Majestic Palace | T Ronnie Ward | 4 of 6 | 48.1 | **3rd** | 3.5 |

No Devin Magnon, Rylee Magnon or Calhoun starters. Meet tally after 11/12
(`watch_people_tally.csv`; logged record runs only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 33 | 3 | 14 | 9.82 | 14 | **+4.18** (was +3.66) |
| J Devin H. Magnon | 29 | 4 | 9 | 9.30 | 9 | −0.30 (no starter) |
| T Rylee Magnon | 9 | 1 | 2 | 3.12 | 2 | −1.12 (no starter) |
| T W.B. Calhoun | 19 | 4 | 9 | 6.24 | 9 | +2.76 (no starter) |

## Things that look off

1. **Javier Antonio Hernandez is off all his mounts for the second night**
   (7 replaced over 11/11–11/12, 4 hit the board). Treat it as an ongoing
   absence; check his mounts on each new card, as for Thornton and Melancon.
2. **Melancon was replaced again**, on the model's highest-P(ITM) #1 (R3,
   ran 2nd at 0.7-1).
3. **The reranker took the winner off #1 in R2 and R5**, both favourites. It
   is 7 of 40 under the review rule, judged on ITM and log loss, not wins.
4. **Bankroll:** the 11/12 PP purchase is logged at an assumed $3.85, and the
   11/11 $0.03 gap is still open. Ask Doug for a TwinSpires balance.

## Queued (not started)

* Read-only paired name-matching OFF/ON check, now on 11/05–11/12, from the
  `-run.bak` files.
* PP-date recency fix (top of the queue; needs the OFF/ON validation first).
* First-time-starter maiden check (7 maidens with first-time starters;
  first-time starter won 3).
* MNR 10/05 chart: retry after 11/21. Non-corpus tracks decision.
