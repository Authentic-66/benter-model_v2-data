# DED 2026-11-13 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Thirteenth
card on 1.3.2, **sixth with name matching ON**. One logged run, the record:
`generated_at = 2026-11-13T07:32:48`, pre-race, bridged, 78 rows (full
fields), commit `45f4954` (`picks/DED_2026-11-13_20261113-0732.*`).

Read-only on the live model: no changes to 1.3.2, the rerankers or the
Piece 1–4 code.

## Pre-race

* **Picks:** model logged 07:32 CST (`45f4954`). The three high-confidence
  qualifiers (R4, R5, R6) and the three reranker #1 changes (R1, R4, R6)
  were logged with the card.
* **Don: no picks received** (no POD, EP4 or LP4 either). Logged as missing
  in `don_picks.csv` (blank picks, note); `ticket_replay.py` now skips a
  source's race with no picks. **No consensus races this card.**
* **Doug:** picks taken from `DED_Picks.xlsx`, sheet "DED 11.13.26", and
  logged at scoring. **Valid, all made before post** (Doug, 11/14): R1–R2
  at 4:34 PM (R1 off 4:45), R3–R9 at 4:55 PM (before R2, off 5:13).
* **Scratches (Doug's list, all confirmed by the chart):** R3 #10 Acadian
  Skies (vet), #11 Unosailor (also-eligible), #12 Chainsaw Man
  (also-eligible); R9 #3 Lil J. Henry (vet), #11 One Sure Hit
  (also-eligible), #12 Biblical Stones (also-eligible). **No others.** R9 #11
  was the model's 2nd and R3 #11 its 4th; none was anyone's #1. Doug lost his
  R9 3rd pick (#3).
* **Late jockey changes** (chart riders compared with
  `pp_entries_raw.pp_jockey`):
  * **Javier Antonio Hernandez off all three mounts, the third night
    running:** R2 #5 He's Exaggerating (Alex Birzer), R5 #6 The Monopoly Man
    (Kelvin Arana), R7 #6 Life Isa Banquet (Erick Del Cid).
  * R3 #3 Pocketnaut: Fernando Del Cid for Alex Birzer.
  * **R4 #2 Skenes Crews: Juan Vargas for Colby Hernandez. Not on Doug's
    list.** This was the base #1 (the reranker had moved it to 2nd) and the
    1.2-1 favourite; it ran 4th.

## Load (2026-11-14 morning)

* `load_chart.py` on `Delta Downs/ded-results-2026/DED111326USA.pdf`:
  `backup verified: racing_full.db.pre-ded1113res.bak`, `+9r 72e (purged 78
  first) [replaced a pre-race card]`, `"errors": 0`, `loaded: DED 2026-11-13
  9 races, 72 entries, 71 with a finish; replaced a pre-race card of 78
  entries`. 78 − 72 = the 6 scratches.
* Spot checks: **R5 official 1-5-3-6 with #1 Asaasy paying $50.80 to win, and
  R9 9-2-6-7, as expected.**
* **R3 #6 Heat of Battle (non-finisher).** The chart's running line shows
  Start 2, ¼ 2¹, ½ 2 Head, Stretch 1², Fin `---`. The footnote says he "drew
  off then shied from the whip at the top of the stretch and ducked in hitting
  the inside rail and unseated the rider". He was 3.4-1 and is not in the
  official order (8 finishers of 9 starters). The load stored him with
  `finish_status = 'DNF'`, `finish_pos` NULL, `official_finish_pos` NULL,
  `non_betting = 0` and odds 3.4. `score_predictions.py` counts him under
  "DNF (ran, no pos): 1": scored as a starter with `actual_finish` NULL and
  `hit_itm` false. That makes him a non-finisher who missed the board, not a
  9th-place finish. The stewards held an inquiry and took no action.
* **No DQs, no dead heats, no non-betting starters.**
* Pick payouts (per $0.50):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 2-3-2 | 88.95 |
  | Pick 3 | R2–R4 | 3-2-7 | 39.00 |
  | Pick 3 | R3–R5 | 2-7-1 | 215.00 |
  | Pick 4 (early) | R2–R5 | 3-2-7-1 | **844.65** |
  | Pick 5 (early) | R1–R5 | 2-3-2-7-1 | **5,427.45** |
  | Pick 3 | R4–R6 | 7-1-4 | 199.20 |
  | Pick 3 | R5–R7 | 1-4-2 | 123.90 |
  | Pick 3 | R6–R8 | 4-2-5 | 33.20 |
  | Pick 3 | R7–R9 | 2-5-9 | 23.90 |
  | Pick 4 (late) | R6–R9 | 4-2-5-3/9/11/12 | 63.05 |
  | Pick 5 (late) | R5–R9 | 1-4-2-5-3/9/11/12 | 1,790.25 |

  The R9 scratches (#3/#11/#12) went to the favourite, #9 Vekowin, who won.
* `score_predictions.py --track DED --date 2026-11-13`: top pick ITM **7 of
  9**, won 2 of 9; top-pick show ROI +20.6%; all horses ITM 27 of 72. 72 rows
  scored (2,629 total), 6 scratched, 1 DNF. No logged #1 scratched.

### Late jockey changes (`tracking/late_jockey_changes.csv`)

| R | horse | PP rider → rode | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 2 | #5 He's Exaggerating | J. A. Hernandez → Alex Birzer | 8 of 9 | 16.5 | **2nd** | 55.8 |
| 3 | #3 Pocketnaut | Alex Birzer → Fernando Del Cid | 9 of 9 | 17.5 | 6th | 17.8 |
| 4 | #2 Skenes Crews | Colby Hernandez → Juan Vargas | 2 of 7 | 57.7 | 4th | 1.2 (fav) |
| 5 | #6 The Monopoly Man | J. A. Hernandez → Kelvin Arana | 6 of 7 | 27.2 | 4th | 5.4 |
| 7 | #6 Life Isa Banquet | J. A. Hernandez → Erick Del Cid | 5 of 7 | 39.9 | 6th | 8.0 |

Five horses, summed P(ITM) 1.59, **ITM 1**. Across 11/05–11/13 the list has
28 rows (summed P(ITM) 10.68, ITM 14). J. A. Hernandez alone: 10 mounts over
three nights, summed P(ITM) 3.15, ITM 5.

## Per race (re-ranked among horses that ran)

R3 counts Heat of Battle (DNF) as a runner: he started.

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1-3-4-6 | 2-3-1-7 | **3rd** | 5 of 7 (3.9-1) | 2/3 | miss | miss (2 of 4) | 1-3 miss | 15.06 |
| 2 | 3-6-1-7 | 3-5-6-4 | **1st** (fav) | 1 of 9 (1.7-1) | 2/3 | miss | miss (2 of 4) | 3-6 miss | 111.19 |
| 3 | 7-4-5-6 | 2-4-5-8 | 5th (fav) | 6 of 9 (4.9-1) | 2/3 | miss | miss (2 of 4) | 7-4 miss | 646.71 |
| 4 | 1-2-4-6 | 7-1-6-2 | **2nd** | 6 of 7 (3.0-1) | 1/3 | miss | miss (3 of 4) | 1-2 miss | 34.03 |
| 5 | 2-1-3-7 | 1-5-3-6 | 7th (fav) | 2 of 7 (24.4-1) | 2/3 | miss | miss (2 of 4) | 2-1 miss | 308.22 |
| 6 | 1-4-7-8 | 4-1-5-2 | **2nd** (fav) | 2 of 8 (1.7-1) | 2/3 | miss | miss (2 of 4) | **1-4 hit** | 67.25 |
| 7 | 2-1-3-4 | 2-7-3-1 | **1st** (fav) | 1 of 7 (1.2-1) | 2/3 | miss | miss (3 of 4) | 2-1 miss | 15.15 |
| 8 | 6-8-1-7 | 5-6-1-2 | **2nd** | 7 of 9 (5.4-1) | 2/3 | miss | miss (2 of 4) | 6-8 miss | 71.62 |
| 9 | 6-9-2-1 | 9-2-6-7 | **3rd** | 2 of 9 (0.8-1) | **3/3** | **hit** | miss (3 of 4) | 6-9 miss | 7.87 |

**Model:** #1 **won 2 of 9** (R2 Mingling Mo $5.40, R7 Charco $4.40) and was
**ITM in 7 of 9**. $2 win on the #1: $9.80 on $18 (−45.6%). Top-3 overlap
18 of 27.

* **Three favourites won** (R2, R7, R9). The model's #1 was the favourite in
  five races: R2 and R7 won, R6 ran 2nd, and R3 (5th) and R5 (7th, last at
  0.8-1) missed.
* **R5:** #1 Asaasy (24.4-1, model 2nd at 50.8) won and paid $50.80; the #1
  Motor City (0.8-1) was "unhurried early while inside and was no threat".
  The model's top two (2-1) were the two ends of the result.
* **R3:** #4 Cheers to Standard (56.2-1, Devin Magnon) ran 2nd as the
  model's 2nd, lifted there by the reranker (22.4 → 32.8). The winner #2
  Brother Ron was a first-time starter (4.9-1, model 6th). The $0.10 super
  paid $646.71.
* **R4:** #7 Sounds Like Power (3.0-1, model 6th of 7) won. The model's top
  four took 2nd to 4th.
* **R8:** #5 Miss Metoyer (5.4-1, model 7th of 9, P(ITM) 15.2) "circled six
  wide" and drew off.

### Reranker

Three #1 changes, the same pre-race and among runners:

| R | base #1 | finished | reranked #1 | finished | race P(ITM) log loss, base → reranked |
|---|---|---|---|---|---|
| 1 | #6 Whisper Park (6.1-1) | 7th | #1 My Happy Dance (5.9-1) | **3rd** | 4.405 → 4.172 (better) |
| 4 | #2 Skenes Crews (1.2-1 fav) | 4th | #1 Cajun Coaster (9.6-1) | **2nd** | 4.616 → 4.486 (better) |
| 6 | #4 Knocked Out (1.7-1) | **1st** | #1 Yuma's Shadow (1.6-1 fav) | **2nd** | 4.702 → 4.578 (better) |

On ITM the reranker gained two (R1, R4; R6 both on the board). On wins it
lost one (R6, where the two were 0.2pp apart). Log loss was lower in all
three races, and over the whole card it fell from 0.6085 to 0.5965 per
starter.

**Reranker review rule: 10 of 40** qualifying races (11/05 R4, 11/06 R4,
11/07 R6, R9, 11/12 R2, R5, R7, 11/13 R1, R4, R6). Reranked #1 **2 W / 8
ITM**, base #1 **3 W / 3 ITM**. The rule judges ITM and log loss at 40, not
wins; no reading until then.

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #4 Sweet Lextheflex | 37.5 → 46.1 (+8.7) | 6 → 3 | 6th (12.5-1) |
| 1 | #5 Nic Sweet Time | 39.3 → 32.4 (−6.8) | 5 → 6 | 5th (10.0-1) |
| 2 | #1 King Jules | 36.5 → 42.5 (+6.0) | 4 → 3 | 8th (20.9-1) |
| 3 | #4 Cheers to Standard | 22.4 → 32.8 (+10.3) | 7 → 2 | **2nd** (56.2-1) |
| 4 | #1 Cajun Coaster | 56.1 → 62.2 (+6.1) | 2 → 1 | **2nd** (9.6-1) |
| 8 | #8 Incognito Burrito | 44.0 → 50.2 (+6.2) | 2 → 2 | 7th (4.5-1) |
| 8 | #7 Prima Bella | 34.7 → 40.3 (+5.7) | 6 → 4 | 5th (13.8-1) |
| 8 | #2 Bombacha Veloz | 38.4 → 28.3 (−10.1) | 4 → 6 | 4th (2.5-1 fav) |
| 9 | #6 Youcandoitboy | 50.6 → 58.7 (+8.1) | 1 → 1 | **3rd** |
| 9 | #7 Coleccionde Gatos | 14.9 → 9.3 (−5.6) | 6 → 7 | 4th (31.2-1) |

6 of 10 went the right way (Sweet Lextheflex, King Jules, Incognito Burrito
and Prima Bella did not). Top-3 overlap 18 for the reranked and the base
order alike.

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 11/13 | 9 | 3 | 2 / 7 / $9.80 (−45.6%) | 3 / 5 / $15.20 (−15.6%) |
| 1.3.2 (10/22–11/13) | 110 | 20 | 27 / 70 / $146.80 (−33.3%) | 29 / 65 / $162.60 (−26.1%) |
| **Meet** | 162 | 25 | 44 / 99 / $257.60 (−20.5%) | 46 / 96 / $310.80 (−4.1%) |

`model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
scratches excluded): **with-reranker 66/101 vs base-only 61/101** (+5, was
+3). Top pick ITM 65.3%, win 24.8%; show ROI −14.8%. **Alert:** "top pick
ITM over last 28 races is 78.6%, above the 68% ceiling". This is the same
check as on 11/05–11/06. These are pre-race record runs on out-of-corpus
cards, so it is a hot run, not leakage.

## High-confidence #1 forward test (`tracking/high_conf_top1.csv`)

Three qualifiers, all still the post-scratch #1 (no scratches in R4–R6):

| R | horse | P(ITM) | odds | finished | $2 win | $2 place |
|---|---|---|---|---|---|---|
| 4 | #1 Cajun Coaster | 62.2 | 9.6 | **2nd** | 0 | 6.40 |
| 5 | #2 Motor City | 64.4 | 0.8 (fav) | 7th (last) | 0 | 0 |
| 6 | #1 Yuma's Shadow | 62.3 | 1.6 (fav) | **2nd** | 0 | 2.60 |

**13 of 40** qualifying races so far: **3 W, 8 in the first two**. $2 win
$14.40 on $26, $2 place $28.10 on $26. **Over-4-1 subset: 2 races** (11/06
Vineaux 4th, 11/13 Cajun Coaster 2nd, place $6.40). No reading until 40.

R6 #4 Knocked Out (62.1, the model's 2nd) was also above 60% and won. It is
not in the test, which counts only the #1.

## Name matching ON: 11/05–11/13 vs the earlier 1.3.2 cards

Same basis as before (record run, among starters, logged P(ITM) not
renormalised; #1 re-ranked among runners; the R3 DNF counts as a starter
that missed the board).

| card | name matching | races | starters | #1 W | #1 ITM | sum P(ITM) | ITM | P(ITM) LL | Brier | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.3.2 off (7 cards, 10/22–11/04) | off | 59 | 505 | 12 | 32 (54%) | 158.82 | 177 | 0.609 | 0.210 | $67.80 (−42.5%) |
| 11/05 | on | 8 | 61 | 3 | 7 | 21.82 | 24 | 0.622 | 0.218 | $19.20 |
| 11/06 | on | 9 | 77 | 2 | 5 | 24.27 | 27 | 0.631 | 0.218 | $8.60 |
| 11/07 | on | 9 | 75 | 1 | 5 | 23.12 | 27 | 0.643 | 0.227 | $5.20 |
| 11/11 | on | 8 | 68 | 4 | 7 | 23.15 | 24 | 0.580 | 0.199 | $24.00 |
| 11/12 | on | 8 | 60 | 3 | 7 | 23.02 | 24 | 0.5275 | 0.176 | $12.20 |
| **11/13** | **on** | 9 | 72 | 2 | 7 | 25.56 | 27 | **0.5965** | **0.205** | $9.80 |
| 1.3.2 on (6 cards) | on | 51 | 413 | 15 | 38 (75%) | 140.93 | 153 | **0.6025** | **0.208** | $79.00 (−22.5%) |

ON stays just below OFF on log loss (0.6025 vs 0.609) and Brier (0.208 vs
0.210). That is still too close to call; the read-only paired OFF/ON check
from the `-run.bak` files is what decides it.

## Data issues on the model's top picks (`tracking/top_pick_data_issues.csv`)

* **R1 #1 My Happy Dance (reranked #1, 3rd): trainer history missed.** The PP
  trainer "Garcia J. Luis" loaded as a new person (trainer id 2892, flagged
  "new" at the card build). The chart has the trainer as "Garcia, J." (id
  2456, 128 earlier starts). The model therefore ran this horse with no
  trainer history. **This may be an alias like Calhoun's** (PP "Calhoun W.
  Bret" = chart "Calhoun, W."). Adding it to `name_aliases.csv` is Doug's
  call; I have not added it.
* The other eight #1s had their last race in the DB (PP days off = DB days,
  13–99 days) and jockey and trainer history. Also noted in the rows: the
  three reranker #1s (R1, R4, R6), R4's base #1 late jockey change, and R9's
  #2 scratch.

## Missing-last-race horses (read-only, running tally)

Five flagged starters tonight:

| R | horse | last race | model rank | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 1 | #3 Rosie Spoonbill | IND 10/06 | 2 of 7 | 50.3 | **2nd** | 2.1 (fav) |
| 1 | #5 Nic Sweet Time | CBY 8/09 | 6 of 7 | 32.4 | 5th | 10.0 |
| 6 | #6 Norma Jean Bling | RP 10/22 | 6 of 8 | 20.6 | 7th | 27.4 |
| 7 | #3 Seasonal Love | MED 10/02 | 3 of 7 | 45.4 | **3rd** | 4.8 |
| 7 | #7 El Rojo Vivo | PRM 9/25 | 7 of 7 | 22.9 | **2nd** | 5.0 |

All five last ran at tracks outside the corpus. Tonight W 0 vs 0.55
expected, ITM 3 vs 1.72. **Tally 11/04–11/13: 52 starters, ITM 22 vs 16.1
expected, W 4 vs 5.3.** All other 11/13 starters: W 9 vs 8.0 expected, ITM
24 vs 23.8. None of the six scratched horses was flagged.

## First-time starters in tonight's maidens

| R | first-time starters | finishes | model ranks | winner |
|---|---|---|---|---|
| 3 (MSW) | #2 Brother Ron, #3 Pocketnaut, #5 The Wicked Outlaw, #9 Get Back Jack (#10, #12 scratched) | **1st** (4.9-1), 6th, **3rd** (8.2-1), 7th | 6th, 9th, 3rd, 8th of 9 | **#2 Brother Ron, a first-time starter** |

R1 (MCL) and R9 (MCL) had no first-time starters. R8 #2 Bombacha Veloz (Chilean-bred,
allowance, 2.5-1 fav) had no running lines on the PP and ran 4th. Tally for the
queued check: **8 maidens with first-time starters, a first-time starter won
4**.

## Low-coverage (<65%) horses

R1 #5 Nic Sweet Time (65%, 5th), R3 #2 Brother Ron (53%, **won**), #3
Pocketnaut (53%, 6th), #5 The Wicked Outlaw (53%, **3rd**), #9 Get Back Jack
(53%, 7th), R8 #2 Bombacha Veloz (55%, 4th).

## Benchmarks: Doug (Don sent no picks)

* Doug's picks were all regular picks (no passes, no best guesses). He lost
  his R9 3rd pick (#3, scratched), so R9 has three.
* Doug's #1 = the model's #1 in R2, R3, R5, R6, R7.

| R | Doug | Doug #1 fin | Doug overlap | model | model #1 fin | model overlap |
|---|---|---|---|---|---|---|
| 1 | 3-1-2-4 | **2nd** | **3/3** | 1-3-4-6 | **3rd** | 2/3 |
| 2 | 3-4-2-6 | **1st** | 1/3 | 3-6-1-7 | **1st** | 2/3 |
| 3 | 7-6-8-3 | 5th | 0/3 | 7-4-5-6 | 5th | 2/3 |
| 4 | 7-2-1-5 | **1st** | 2/3 | 1-2-4-6 | **2nd** | 1/3 |
| 5 | 2-5-6-1 | 7th | 1/3 | 2-1-3-7 | 7th | 2/3 |
| 6 | 1-4-7-8 | **2nd** | 2/3 | 1-4-7-8 | **2nd** | 2/3 |
| 7 | 2-6-1-3 | **1st** | 1/3 | 2-1-3-4 | **1st** | 2/3 |
| 8 | 1-6-8-2 | **3rd** | 2/3 | 6-8-1-7 | **2nd** | 2/3 |
| 9 | 9-6-2 | **1st** | **3/3** | 6-9-2-1 | **3rd** | **3/3** |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | 2 | **7/9** | **18/27** | 1 (R9 $7.87) | 0 | 1 (R6 $6.20) | $9.80 on $18 (−45.6%) |
| Doug | **4** | **7/9** | 15/27 | **2 (R1 $15.06, R9 $7.87)** | 0 | 1 (R6 $6.20) | **$21.40 on $18 (+18.9%)** |

* **Doug's #1 won four races** (R2, R4, R7, R9). His R4 #1 #7 Sounds Like
  Power was the model's 6th of 7; his R4 exacta box used #2 and #7.
* His R6 top four was the model's exactly (1-4-7-8).

### Consensus #1s (`tracking/consensus_top1.csv`)

None: Don sent no picks. The file is unchanged at **8 W, 15 ITM from 20**.

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **11/05–11/13** (name matching ON) | Model | 51 | 15 | 38 (75%) | 88/153 | −22.5% |
| | Don (to 11/12) | 42 | 15 | 31 (74%) | 75/126 | +9.3% |
| | Doug | 51 | 17 | 30 (59%) | 76/153 | −1.8% |
| **1.3.2** (10/22–11/13) | Model | 110 | 27 | 70 (64%) | 178/330 | −33.3% |
| | Don (to 11/12) | 101 | 34 | 67 (66%) | 175/303 | −4.4% |
| | Doug | 108 | 36 | 66 (61%) | 166/324 | −6.9% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.7% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (19 cards) | Model | 162 | 44 | 99 (61%) | 255/486 | −20.5% |
| | Don | 144 | 49 | 93 (65%) | 242/432 | −2.8% |
| | Doug | 116 | 39 | 69 (59%) | 176/348 | −5.1% |
| | Doug, without best guesses | 113 | 37 | 67 (59%) | 170/339 | −8.7% |

The meet $2 win lines ($257.60 model, $279.80 Don, $220.20 Doug) match the
ticket replay.

### Don's bets (`tracking/don_bets.csv`)

None received for 11/13.

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 4 | exacta box, $1 | 2,7 (2 combos) | $2.00 | lost (7-1; #2 ran 4th) |
| LRL | 5 | exacta, $1 | 4 / 1,7 (2 combos) | $2.00 | lost |
| CT | 2 | superfecta box, $0.10 | 4,5,6,7 (24 combos) | $2.40 | lost |
| CT | 6 | win, $2 | #5 | $2.00 | lost |

Night total: **$8.40 wagered, $0 returned, −$8.40.** DED wagering $2.00,
**qualifies for the DED PP rebate** (at least $2 on the card). LRL and CT are
personal bets, kept out of DED scoring and the ticket replay.

**Bankroll** (`tracking/bankroll.csv`): from the confirmed $74.60 (after the
11/13 PP purchase and the 11/11 and 11/12 rebates), −$2.00, −$2.00, −$2.40,
−$2.00 = **$66.20**, as Doug expected. The 11/13 rebate (+$3.85) is still to
be logged when it lands.

## Watch list

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 2 | #3 Mingling Mo | T Ronnie Ward | **1 of 9** | 56.6 | **1st** | 1.7 (fav) |
| 3 | #4 Cheers to Standard | J Devin Magnon | 2 of 9 | 32.8 | **2nd** | 56.2 |
| 4 | #3 Lee Street | T Ronnie Ward | 5 of 7 | 37.2 | 7th | 27.5 |
| 4 | #4 Chad's Flashy Ways | T Ronnie Ward | 3 of 7 | 44.2 | 6th | 2.8 |
| 7 | #4 Maxxus | J Devin Magnon | 4 of 7 | 44.8 | 5th | 12.2 |
| 8 | #3 Berlaine | J Devin Magnon, T Rylee Magnon | 9 of 9 | 14.8 | 8th | 55.0 |

No Calhoun starters. Meet tally after 11/13 (`watch_people_tally.csv`;
logged record runs only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 36 | 4 | 15 | 11.20 | 15 | **+3.80** (was +4.18) |
| J Devin H. Magnon | 32 | 4 | 10 | 10.23 | 10 | −0.23 (was −0.30) |
| T Rylee Magnon | 10 | 1 | 2 | 3.27 | 2 | −1.27 (was −1.12) |
| T W.B. Calhoun | 19 | 4 | 9 | 6.24 | 9 | +2.76 (no starter) |

## Things that look off

1. **Javier Antonio Hernandez is off all his mounts for the third night**
   (10 replaced over 11/11–11/13, 5 hit the board). His R2 replacement ran 2nd
   at 55.8-1. The model keeps pricing him because he is still on the PP.
2. **An unlisted late jockey change on the base #1:** R4 #2 Skenes Crews
   (Colby Hernandez → Juan Vargas, 1.2-1 fav, 4th). Doug's list didn't have
   it; the chart-vs-PP comparison did. *Doug 11/14:* keep it in
   `late_jockey_changes.csv` (row kept).
3. **Possible trainer alias:** PP "Garcia J. Luis" vs chart "Garcia, J."
   (128 starts). The reranked R1 #1 ran without trainer history. Doug decides
   whether it goes into `name_aliases.csv`. *Read-only check 11/14 (nothing
   added yet):* see "Garcia alias check" below.
4. **Doug's 11/13 picks** came from the workbook, last saved 16:54 CST, and
   the chart's R1 off time is 4:45. Please confirm they were made before
   post. *Resolved 11/14:* Doug confirmed all were made before post (R1–R2
   4:34 PM, R3–R9 4:55 PM, before R2); marked valid in `doug_picks.csv`.
5. **The model_health last-28 ITM alert is on again** (78.6%). It is a hot
   run on pre-race record runs, as checked on 11/05. *Doug 11/14:* noted, no
   action.

## Garcia alias check (2026-11-14, read-only)

**(a) One trainer.** Before 11/13, "Garcia, J." (trainer id 2456) had 128
starts:

| track | starts | dates |
|---|---|---|
| DED | 40 | 2021-01-20 – 2026-10-16 |
| EVD | 20 | 2022-06-04 – 2025-08-28 |
| FG | 14 | 2021-11-27 – 2025-03-04 |
| LAD | 54 | 2022-05-10 – 2026-05-25 |

That is 10–33 starts a year from 2021 to 2026, which looks like one Louisiana
circuit stable. **120 of the 128 starts are for one owner, Melissa
Cantacuzene.** Of the rest, 4 are for "Fairchild, Amy and **Garcia, Jose
Luis**", 3 for Amy Fairchild and 1 for Jose L. Gomez. The "Jose Luis Garcia"
owner line ties "Garcia, J." to the PP's "Garcia J. Luis". **My Happy Dance's
only earlier start (DED 10/16 R3, 6th) was trained by "Garcia, J."** for
Melissa Cantacuzene, and the chart gives the same trainer and owner on 11/13.
The PP spelled him "Garcia J. Luis" on both of her cards (10/16 and 11/13),
and on no other PP card in `pp_entries_raw`.

A different "Garcia, Jose" (id 2486, 8 starts, DED/EVD 2021–2024, owners
Black Diamond LLC and KK Horse Racing) is a separate record. The alias
would not touch it.

**(b) No change to built rows, so the streak would not reset.**
* No entry uses the PP-only trainer record "Garcia J. Luis" (id 2892) now.
  The 11/13 chart load replaced the card entry with the chart's trainer
  2456. Every existing `entries.trainer_id` stays as it is, so no
  `entry_features_dpv1` row changes.
* The alias is read only by `name_match.py` while `load_pp_card.py` loads a
  new PP card. It changes which trainer id a future card's entries get.
  Both the full build and the side table read the same entries, so both
  see the same change.
* `name_aliases.csv` is not part of the feature build version
  (`feature_incremental.build_version` hashes the feature config, the
  feature code files and the pandas/numpy versions). Adding a row does not
  force a seed or fallback.
* So the next side-by-side should still compare clean and count toward the
  14. The only effect: when Garcia next has a PP starter, the model gets his
  trainer history (129 starts) instead of the "new trainer" prior.

## Queued (not started)

* Read-only paired name-matching OFF/ON check, now on 11/05–11/13, from the
  `-run.bak` files.
* PP-date recency fix (top of the queue; needs the OFF/ON validation first).
* First-time-starter maiden check (8 maidens with first-time starters; a
  first-time starter won 4).
* MNR 10/05 chart: retry after 11/21. Non-corpus tracks decision.
