# DED 2026-10-30 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Sixth card
on 1.3.2. One logged run, the record: `generated_at = 2026-10-30T14:47:18`,
pre-race, bridged, 100 rows (full fields), commit `4de8cd0`
(`picks/DED_2026-10-30_20261030-1447.*`). The scratches and jockey changes
came after this run; it was not re-logged.

This pass is read-only on the live model: no changes to 1.3.2, the
rerankers or Piece 1–4 code. `scripts/racing_full.db.ded1030-run.bak` (the
pre-race DB) is kept for Saturday's paired comparison, along with
`.ded1028-run.bak` and `.ded1029-run.bak`.

## Load (2026-10-30 night)

* Chart `Delta Downs/ded-results-2026/DED103026USA.pdf`, read with the
  standard chart parser (pdfplumber). 9 races, 86 starters, 48 exotic rows.
  The 100-entry pre-race card was purged first. 0 errors.
* DB backup: `scripts/racing_full.db.pre-ded1030res.bak`, verified before
  the load: same sha256 as the live DB, `integrity_check` ok on both, and the
  same row counts in six tables.
* Spot checks: R8 official 5-7-3-8 and R9 5-10-7-4, as expected. R8 payouts
  match: $1 exacta 5-7 $10.10, $0.50 trifecta 5-7-3 $41.65, $0.10
  superfecta 5-7-3-8 $40.72, $0.50 Pick 3 (R6–R8) 7-8-5 $106.20.
* **No dead heats, no DQs** (crossing order = `official_finish_pos` in all
  9 races), **no non-betting starters**.
* **Two non-finishers**, both starters that lost:
  * R3 #10 Catalina Classic (11.5-1, Devin Magnon, model 9th of 10): "broke
    in, bumped, pressed the early pace … dropped back and was eased to the
    wire."
  * R8 #4 Copy This (35.9-1, model **2nd of 9**, a no-history shipper at 64%
    coverage): "stumbled early, lost rider (Jansen Melancon) and walked off."
    This killed the model's R8 exacta box (5-4) and super box at the start.
* **Scratches.** Fourteen logged horses scratched: the twelve on the
  morning list plus **two late vet scratches** (R2 #3, R7 #9):

  | R | horse | chart reason | morning list | logged rank | P(ITM) |
  |---|---|---|---|---|---|
  | 2 | #11 Lee Circle | Also-Eligible | yes | 9 of 11 | 19.2 |
  | 2 | #3 Wickedly Royal | Veterinarian | **no** | 5 of 11 | 28.0 |
  | 3 | #11 Making Noise | Also-Eligible | yes | 9 of 12 | 19.2 |
  | 3 | #12 One Grand Slam | Also-Eligible | yes | 8 of 12 | 22.3 |
  | 4 | #11 Drewmazing | Also-Eligible | yes | **1 of 12** | 39.4 |
  | 4 | #12 West Island | Also-Eligible | yes | 3 of 12 | 32.6 |
  | 5 | #11 Piastri | Also-Eligible | yes | 4 of 12 | 30.3 |
  | 5 | #12 After Party | Also-Eligible | yes | 11 of 12 | 13.0 |
  | 6 | #11 Cajun Coaster | Also-Eligible | yes | 3 of 12 | 37.0 |
  | 6 | #12 Misdeal | Also-Eligible | yes | 8 of 12 | 18.6 |
  | 7 | #9 Fiesty Fist | Veterinarian | **no** | 5 of 9 | 28.0 |
  | 8 | #6 Copper Key | Stakes scratch | yes | 5 of 12 | 24.6 |
  | 8 | #11 Louisiana Sis | Also-Eligible | yes | 10 of 12 | 17.9 |
  | 8 | #12 Pink Angel | Also-Eligible | yes | 9 of 12 | 19.2 |

  The model's R4 #1 (Drewmazing, an also-eligible) never drew in, so R4 is
  scored on its next horse, #7 Saint Peter's Bay. Wickedly Royal was on no
  one's list. **Fiesty Fist was Doug's R7 #4 pick** (5-4-2-9 → 5-4-2).
* **Late jockey changes (not rescored).** The model priced each horse with
  the rider in the PP file. **Thornton came off all five of his starters**
  (his sixth mount, R8 #6 Copper Key, was the stakes scratch):

  | R | horse | trainer | listed | rode (chart) | model rank (runners) | finished | odds |
  |---|---|---|---|---|---|---|---|
  | 2 | #10 Miss Super Mo | Calhoun | Timothy Thornton | Harry Hernandez | 2 of 9 | 6th | 4.6 |
  | 5 | #3 Imperial Cruiser | Calhoun | Timothy Thornton | Jansen Melancon | 7 of 10 | **1st** | 3.9 |
  | 6 | #1 Goodand Stout | Castille | Timothy Thornton | **Colby Hernandez** | 2 of 10 | 8th | 4.8 |
  | 7 | #3 Max Is G Money | Alberto | Timothy Thornton | Harry Hernandez | 4 of 8 | 4th | 2.3 |
  | 9 | #5 Lieutenant Charm | Berndt | Timothy Thornton | Chris Rosier | **1 of 10** (consensus #1) | **1st** | 2.8 (fav) |

  **Colby Hernandez rode all five of his listed mounts** this time (R2 #1
  5th, R3 #1 6th, R5 #1 3rd, R8 #7 2nd at 13.2-1, R9 #10 2nd), and picked up
  R6 #1 from Thornton. R3 #7 He's Therealdeal and R4 #4 Izzy's Baby Boy had
  no rider in the PP file (Julio Ramirez Jr. and Jose Nava-Marin rode). No
  other rider differed from the PP file (checked on first and last name).
* Pick payouts (per $0.50). **Neither early Pick 4 nor early Pick 5 was hit
  in full; both paid to fewer correct legs**:

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 1-6-2 | 3,882.35 |
  | Pick 3 | R2–R4 | 6-2-ALL / 6-ALL-5 / ALL-2-5 | 87.95 / 460.20 / 19.80 |
  | Pick 3 | R3–R5 | 2-5-3 | 392.20 |
  | Pick 3 | R4–R6 | 5-3-7 | 374.75 |
  | Pick 3 | R5–R7 | 3-7-8 | 225.15 |
  | Pick 3 | R6–R8 | 7-8-5 | 106.20 |
  | Pick 3 | R7–R9 | 8-5-5 | 38.45 |
  | Pick 4 (early) | R2–R5 | 6-2-5-3 (**3 correct**) | 283.45 |
  | Pick 5 (early) | R1–R5 | 1-6-2-5-3 (**4 correct**) | 1,121.10 |
  | Pick 4 (late) | R6–R9 | 7-8-5/6/11/12-5 | 456.85 |
  | Pick 5 (late) | R5–R9 | 3-7-8-5/6/11/12-5 | 5,569.90 |

  These figures are as the chart prints them. The R2–R4 Pick 3 had no
  6-2-5 ticket, so it paid three two-leg combos with `ALL` in the missed
  leg; the chart still labels them "3correct". R8's `/` leg sends #6, #11
  and #12 to the post-time favourite #5 Cajun Caviar, who won. R2 (#6 at
  27.7-1) and R4 (#5 at 17.4-1) broke the early Pick 4 and Pick 5.
* `score_predictions.py --track DED --date 2026-10-30`, official figures:
  * The logged top pick was ITM in 6 of 8 and won 2 of 8 (R4's logged #1
    was scratched).
  * Top-pick show ROI was −1.9% ($15.70 back on $16).
  * All horses were ITM 27 of 86. 86 rows scored (2,147 total).

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).
* **Exacta box:** a $1 exacta box of the model's top 2 ($2 a race).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 6-9-3-1 | 1-9-6-2 | **3rd** (fav) | 4 of 10 (2.8-1) | 2/3 | miss | miss | 6-9 miss | 6.58 |
| 2 | 9-10-7-5 | 6-7-2-4 | 8th | **9 of 9** (27.7-1) | 1/3 | miss | miss | 9-10 miss | 1,865.09 |
| 3 | 5-2-1-6 | 2-3-9-6 | 5th | 2 of 10 (3.6-1) | 1/3 | miss | miss | 5-2 miss | 683.61 |
| 4 | 7-8-1-6 | 5-1-8-6 | 7th (fav) | 7 of 10 (17.4-1) | 2/3 | miss | miss (3 of 4) | 7-8 miss | 1,074.28 |
| 5 | 10-8-6-2 | 3-10-1-5 | **2nd** | 7 of 10 (3.9-1) | 1/3 | miss | miss | 10-8 miss | 97.42 |
| 6 | 3-1-10-4 | 7-5-3-2 | **3rd** (fav) | 7 of 10 (5.5-1) | 1/3 | miss | miss | 3-1 miss | 672.36 |
| 7 | 4-1-6-3 | 8-1-4-3 | **3rd** (fav) | 6 of 8 (5.5-1) | 2/3 | miss | miss (3 of 4) | 4-1 miss | 52.36 |
| 8 | 5-4-1-2 | 5-7-3-8 | **1st** (fav) | 1 of 9 (0.6-1) | 1/3 | miss | miss | 5-4 miss | 40.72 |
| 9 | 5-2-10-3 | 5-10-7-4 | **1st** (fav) | 1 of 10 (2.8-1) | 2/3 | miss | miss | **5-2 miss** | 78.57 |

**Model:** the #1 pick won twice (R8 Cajun Caviar $3.20, R9 Lieutenant
Charm $7.60) and was ITM in 6 of 9. Top-3 overlap was 13 of 27. The top-two
exacta box, the top-3 wheel and the super box **missed all 9 races**.

* **R9 exacta box: a miss, not a hit.** The model's top two were #5
  Lieutenant Charm (46.5) and **#2 Kama Can (37.9)**, with #10 Captain Junuh
  third at 37.7, 0.2pp behind. The 5-10 exacta ($19.50) was Don's and
  Doug's top two, not the model's. The reranker made it close: it cut Kama
  Can 5.8pp (43.8 → 37.9) and lifted Captain Junuh 2.7pp (35.0 → 37.7), but
  not far enough to swap them. Kama Can ran 6th.
* **R2:** #6 My Other Half won gate to wire at 27.7-1 ($57.40), the model's
  **last** of 9 (6.7%). The $0.10 superfecta paid $1,865.09. The model's
  #1 Allons Betta Lee ran 8th at 5.2-1.
* **R4:** with Drewmazing out, the model's #1 was #7 Saint Peter's Bay, the
  2.5-1 favourite, who ran 7th. #5 Huey Duey won at 17.4-1 (model 7th).
  The model's #2–#4 (8-1-6) ran 3rd, 2nd and 4th.
* **R7:** the model's top four held 2nd–4th (1-4-3) but not the winner, #8
  Essay (5.5-1, model 6th of 8). The same thing happened in R4.
* **R8** (Louisiana Jewel S., 2yo fillies, 72% race coverage): the model's
  #2 Copy This lost the rider at the start. #7 Romantic Rumor (2nd, 13.2-1)
  and #3 My Hintof Platinum (3rd, 24.9-1) were 55%-coverage shippers the
  model had 9th and 5th.
* The model's #1 was the favourite in 6 races (R1, R4, R6, R7, R8, R9): 2
  won (R8, R9), 3 ran 3rd, and R4 ran 7th.

### Reranker

The reranker changed the #1 in **1 race** (R1):

| R | base #1 | finished | reranked #1 | finished | effect |
|---|---|---|---|---|---|
| 1 | #3 Mediator (41.9 → 38.4) | 9th (39.8-1) | #6 The Get Out (39.1 → 46.8) | **3rd** (2.3-1, fav) | +1 ITM, no win either way |

Net on the card: #1 wins 2 vs 2, #1 ITM **6 vs 5**, overlap **13 vs 11**
(the reranked top three also did better in R3, 5-2-1 vs base 5-1-6, and R4,
7-8-1 vs 7-4-1), exacta box 0 vs 0, super box 0 vs 0, $2 win $10.80 vs
$10.80. The reranker also lifted R1 winner #1 Liberty Simone 8.5pp
(rank 6 → 4), but that did not change any ticket.

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #1 Liberty Simone | 28.8 → 37.2 (+8.5) | 6 → 4 | **1st** (2.8-1) |
| 1 | #6 The Get Out | 39.1 → 46.8 (+7.7) | 3 → 1 | **3rd** (2.3-1, fav) |
| 1 | #5 Little Miss Jess | 24.5 → 17.7 (−6.9) | 7 → 8 | 7th (9.5-1) |
| 1 | #4 Saucy Diem | 20.6 → 14.5 (−6.1) | 9 → 9 | 10th (32.5-1) |
| 3 | #2 Dirty Deal | 29.5 → 34.9 (+5.4) | 4 → 2 | **1st** (3.6-1) |
| 7 | #1 Purple Heart | 46.5 → 52.2 (+5.7) | 3 → 2 | **2nd** (7.0-1) |
| 9 | #2 Kama Can | 43.8 → 37.9 (−5.8) | 2 → 2 | 6th (8.0-1) |

All seven moves went the right way: the four horses lifted finished 1st,
3rd, 1st and 2nd, and the three cut finished 7th, 10th and 6th.

**Running reranker tally, for Saturday's comparison** (record runs, re-ranked
among runners; all 12 cards, 103 races). The reranker has changed the #1 in
15 races:

| card | R | base #1 fin | reranked #1 fin |
|---|---|---|---|
| 10/10 | 1 | 2nd | **1st** |
| 10/10 | 4 | **1st** | 5th |
| 10/14 | 2 | **1st** | 8th |
| 10/17 | 2 | 3rd | **1st** |
| 10/17 | 9 | 7th | 9th |
| 10/22 | 5 | 3rd | 2nd |
| 10/24 | 4 | **1st** | 2nd |
| 10/24 | 5 | 3rd | **1st** |
| 10/24 | 6 | 3rd | 4th |
| 10/24 | 8 | 5th | 4th |
| 10/28 | 1 | 7th | 2nd |
| 10/28 | 5 | 6th | 4th |
| 10/28 | 8 | **1st** | 4th |
| 10/29 | 7 | 2nd | 3rd |
| 10/30 | 1 | 9th | 3rd |

In those 15 races: base #1 4 W, 10 ITM; reranked #1 3 W, 8 ITM.

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 10/30 | 9 | 1 | 2 / 6 / $10.80 (−40.0%) | 2 / 5 / $10.80 (−40.0%) |
| 1.3.2 (10/22–10/30) | 51 | 10 | 8 / 26 / $46.80 (−54.1%) | 9 / 26 / $59.60 (−41.6%) |
| 1.3.1 (10/21) | 8 | 0 | 2 / 4 / $9.60 (−40.0%) | same |
| 1.3.0 (10/10–10/17) | 44 | 5 | 15 / 25 / $101.20 (+15.0%) | 15 / 27 / $138.60 (+57.5%) |
| **Meet** | 103 | 15 | 25 / 55 / $157.60 (−23.5%) | 26 / 57 / $207.80 (+0.9%) |

`model_health` (logged basis, top-pick scratches excluded) now has 1.3.2
**with-reranker 26/46 vs base-only 25/46** (+1, from level). Its four-arm
shadow reconstruction on 1.3.2 is X 10/18, Y 11/18, W 12/18, Z 11/18 (far
too few races). The paired 1.3.0 / 1.3.2 / 1.3.2-no-reranker run on
Saturday will use `.ded1028-run.bak`, `.ded1029-run.bak` and
`.ded1030-run.bak`.

### Stretch feature (1.3.2 vs 1.3.1)

Not run: the pre-race card has been replaced by the results card, and this
pass is read-only. (Saturday's paired comparison covers 1.3.0 vs 1.3.2.)

## Low-coverage (<65%) horses

**9 of 86** starters were below 65% coverage, all no-history shippers (10
of the card's 13 shippers ran). Summed P(ITM) 1.81, actual ITM 2. Both of the
night's non-finishers are in this group:

| R | horse | cov | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 1 | #5 Little Miss Jess | 61% | 8 of 10 | 17.7 | 7th | 9.5 |
| 1 | #4 Saucy Diem | 65% (64.6) | 9 of 10 | 14.5 | 10th | 32.5 |
| 1 | #7 Nayakim | 65% (64.6) | 10 of 10 | 12.8 | 6th | 92.0 |
| 3 | #10 Catalina Classic | 60% | 9 of 10 | 14.9 | eased (DNF) | 11.5 |
| 5 | #9 Saint Robert's Row | 65% (64.6) | 8 of 10 | 19.7 | 8th | 16.7 |
| 8 | #4 Copy This | 64% | **2 of 9** | 31.3 | lost rider (DNF) | 35.9 |
| 8 | #2 Mo Cantharus | 65% (64.6) | 4 of 9 | 30.3 | 8th | 24.4 |
| 8 | #3 My Hintof Platinum | 55% | 5 of 9 | 24.4 | **3rd** | 24.9 |
| 8 | #7 Romantic Rumor | 55% | 9 of 9 | 15.9 | **2nd** | 13.2 |

The model's R8 #1 Cajun Caviar, also a no-history shipper, was just above
the line at 65.6% and won. R8 (stakes, 2yo fillies, 72%) was the
lowest-coverage race; R1 (MC 10k, 80%) was next.

## Benchmarks: Don and Doug

Re-ranked around scratches as before (Don's alt moves up; Doug has no alt).

* Only alts and one Doug pick were scratched: Don's R4 alt #12 and R8 alt
  #6 (morning list), and **Doug's R7 #4 pick #9 Fiesty Fist (late vet
  scratch)**, leaving him 5-4-2. No scratch touched either one's top four
  otherwise.
* Doug's picks were all regular picks (no passes, no best guesses), made on
  race day with the morning scratches known. He gave three picks in R6.

| R | Don (re-ranked) | Don #1 fin | Don overlap | Doug (re-ranked) | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 6-9-1-10 | **3rd** | 3/3 | 9-6-4-8 | **2nd** | 2/3 | **3rd** | 2/3 |
| 2 | 7-2-9-1 | **2nd** | 2/3 | 10-2-9-7 | 6th | 1/3 | 8th | 1/3 |
| 3 | 1-2-6-4 | 6th | 1/3 | 4-6-5-9 | 7th | 0/3 | 5th | 1/3 |
| 4 | 6-1-7-4 | 4th | 1/3 | 6-4-1-10 | 4th | 1/3 | 7th | 2/3 |
| 5 | 3-1-10-8 | **1st** | 3/3 | 6-5-1-10 | 10th | 1/3 | **2nd** | 1/3 |
| 6 | 3-1-7-10 | **3rd** | 2/3 | 3-2-1 | **3rd** | 1/3 | **3rd** | 1/3 |
| 7 | 4-3-5-2 | **3rd** | 1/3 | 5-4-2 | 5th | 1/3 | **3rd** | 2/3 |
| 8 | 5-10-7-9 | **1st** | 2/3 | 5-9-10-1 | **1st** | 1/3 | **1st** | 1/3 |
| 9 | 5-10-2-9 | **1st** | 2/3 | 5-10-4-2 | **1st** | 2/3 | **1st** | 2/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | 2 | 6/9 | 13/27 | 0 | 0 | 0 | $10.80 on $18 (−40.0%) |
| Don | **3** | **7/9** | **17/27** | **2** (R1 $6.58, R5 $97.42) | 0 | 1 (R9 5-10, $19.50) | $20.60 on $18 (**+14.4%**) |
| Doug | 2 | 4/9 | 10/27 | 0 | 0 (7 placed) | 1 (R9 5-10, $19.50) | $10.80 on $18 (−40.0%) |

* Don's top three were the trifecta in R1 (6-9-1 → 1-9-6, $12.20 per
  $0.50) and **R5** (3-1-10 → 3-10-1, $58.50; the super wheel paid $97.42).
  His R5 #1 #3 Imperial Cruiser won at 3.9-1 ($9.80); the model had him
  7th of 10 and Doug did not have him.
* All three missed R2 (#6 at 27.7-1), R4 (#5 at 17.4-1), R6 (#7 Saint
  Gabriel at 5.5-1; Don's 3rd pick) and R7 (#8 Essay at 5.5-1).
* The model's #1 matched Don's in 5 races (R1, R6, R7, R8, R9) and Doug's in
  3 (R6, R8, R9). Don's and Doug's matched in 4 (R4, R6, R8, R9).

### Consensus #1s (`tracking/consensus_top1.csv`)

All three sources had the same #1 in 3 races tonight, all pre-race (no
scratch involved), all the favourite:

* **R6 #3 Letmikefigureitout** (also Don's POD; Devin Magnon): 3rd at
  1.2-1; show $2.40. "Outfinished for second."
* **R8 #5 Cajun Caviar**: **won** at 0.6-1 ($3.20).
* **R9 #5 Lieutenant Charm** (Thornton off, Chris Rosier up): **won** at
  2.8-1 ($7.60). On top of Doug's $0.10 superfecta part wheel (lost; see
  below).

| card | R | horse | odds | finished | $2 win | Doug's bet |
|---|---|---|---|---|---|---|
| 10/28 | 2 | #3 Donegal Freedom | 0.7 | **1st** | 3.40 | |
| 10/28 | 3 | #9 Forty Three Cents | 1.2 | **1st** | 4.40 | |
| 10/28 | 7 | #10 Miracle Mula | 1.9 | 4th | | $2 win, lost |
| 10/29 | 1 | #7 Gently | 1.7 | 5th | | (underneath in his 9-7 exacta) |
| 10/29 | 6 | #4 Takethe Hint | 1.5 | **3rd** | | $1 exacta 4-5, lost |
| 10/30 | 6 | #3 Letmikefigureitout | 1.2 | **3rd** | | |
| 10/30 | 8 | #5 Cajun Caviar | 0.6 | **1st** | 3.20 | |
| 10/30 | 9 | #5 Lieutenant Charm | 2.8 | **1st** | 7.60 | $0.10 super part wheel, lost |

So far: **4 W, 6 ITM from 8**, every one the favourite. $2 win on all
eight: $18.60 on $16 (+16.3%); $2 show $15.00 on $16 (−6.3%). Doug's three
bets on them: $5.40, $0 back. Eight races is no sample.

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

Model rows are by the version that made the record run. Don and Doug are
split by the same dates. Doug has no picks before 10/21.

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **10/30** | Model | 9 | 2 | 6 (67%) | 13/27 | −40.0% |
| | Don | 9 | 3 | 7 (78%) | 17/27 | +14.4% |
| | Doug | 9 | 2 | 4 (44%) | 10/27 | −40.0% |
| **1.3.2** (10/22–10/30) | Model | 51 | 8 | 26 (51%) | 76/153 | −54.1% |
| | Don | 51 | 16 | 31 (61%) | 84/153 | −17.8% |
| | Doug | 49 | 16 | 31 (63%) | 74/147 | −8.4% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.8% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (12 cards) | Model | 103 | 25 | 55 (53%) | 153/309 | −23.5% |
| | Don | 94 | 31 | 57 (61%) | 151/282 | −9.4% |
| | Doug | 57 | 19 | 34 (60%) | 84/171 | −4.6% |
| | Doug, without best guesses | 54 | 17 | 32 (59%) | 78/162 | −12.0% |

* The meet $2 win lines ($157.60 model, $170.40 Don, $108.80 Doug) match the
  ticket replay.
* `model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
  scratches excluded): top pick ITM 26/46 = 56.5%, win 8/46; show ROI
  −24.3% ($69.60 on $92). **The alert is off for the first time since
  10/24** (show ROI was −29.1% after 10/29; the threshold is −25%).

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R6 #3 Letmikefigureitout (ML 5-2) | | **3rd** at 1.2-1 (fav) | — | — |
| EP4 (R2–R5) | 1-2-7-9 / 1-2-6 / 1-6 / 1-3 (48 combos) | $24 | miss, dead in R2 | 2/4 | 6-2-5-3 paid 283.45 to 3 of 4 |
| LP4 (R6–R9) | 1-3 / 3-4 / 5 / 2-5-10 (12 combos) | $6 | miss, **dead in R6** | 2/4 | 7-8-5/6/11/12-5 paid 456.85 |

* POD Letmikefigureitout went off the 1.2-1 favourite and ran 3rd (show
  $2.40), beaten by #7 Saint Gabriel (5.5-1) and #5 Tdzshininluckystar
  (11.5-1).
* EP4: R3 #2 and R5 #3 were on the ticket; R2 (#6 at 27.7-1) and R4 (#5 at
  17.4-1) were not. The pool paid on 3 of 4 correct; Don had 2, so even the
  3-of-4 payout missed him.
* LP4: died in R6 (1-3 vs #7). R7 (3-4 vs #8) missed too; R8 #5 and R9 #5
  were on the ticket.
* Don's day: $30 wagered, $0 back (−$30).

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 4 | win, $2 | #6 Luvto Win | $2.00 | lost (4th at 3.3-1; 5-1-8-6) |
| DED | 9 | superfecta part wheel, $0.10 | 5,10 / 5,10 / 2,3,4,9 / 2,3,4,9 (24 combos) | $2.40 | lost (5-10-7-4; #7 not on the ticket) |

Night total: **$4.40 wagered, $0 returned, −$4.40**. These bets qualify Doug
for the DED PP rebate.

* The R4 win bet is **not** a consensus bet: Luvto Win was Don's and Doug's
  #1 but the model's 4th among runners. He showed speed and weakened.
* The R9 super is tagged `consensus_top1` (#5 Lieutenant Charm, the
  three-way #1, won). The top two (5-10) and 4th (#4 Struck Out) were on the
  ticket; #7 Lick Skillet (3rd, 5.3-1, model 7th of 10, in no one's top
  four) was not.

## Watch list

No starters for the watched horses (Discerner, Cincy's Player, Celestial
Clock) and no Rylee Magnon starters.

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 2 | #10 Miss Super Mo | T Calhoun | 2 of 9 | 37.0 | 6th | 4.6 |
| 2 | #1 What's Love | T Calhoun | 8 of 9 | 18.8 | 5th | 10.9 |
| 5 | #3 Imperial Cruiser | T Calhoun | 7 of 10 | 22.9 | **1st** | 3.9 |
| 2 | #8 Pot's Paycheck | T Ward | 6 of 9 | 26.5 | 7th | 7.2 |
| 3 | #6 Minimus Maximus | T Ward | 4 of 10 | 32.9 | 4th | 2.3 (fav) |
| 8 | #3 My Hintof Platinum | T Ward | 5 of 9 | 24.4 | **3rd** | 24.9 |
| 3 | #10 Catalina Classic | J Devin Magnon | 9 of 10 | 14.9 | eased (DNF) | 11.5 |
| 6 | #3 Letmikefigureitout | J Devin Magnon | **1 of 10** | 48.9 | **3rd** | 1.2 (fav) |

Meet tally after 10/30 (`watch_people_tally.csv`; logged record runs only,
pooled across 1.3.0, 1.3.1 and 1.3.2):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 24 | 2 | 10 | 7.49 | 10 | +2.51 |
| J Devin H. Magnon | 22 | 4 | 8 | 6.90 | 8 | +1.10 |
| T Rylee Magnon | 6 | 1 | 2 | 2.26 | 2 | −0.26 |
| T W.B. Calhoun | 19 | 4 | 9 | 6.24 | 9 | +2.76 |

Eight watch starters: summed P(ITM) 2.26, actual ITM 3. Calhoun's Imperial
Cruiser won with Thornton off (Melancon up), at 3.9-1 from the model's 7th.
Ward's My Hintof Platinum, a 55%-coverage shipper, ran 3rd at 24.9-1.
Calhoun is +2.76 on 19, Ward +2.51 on 24, Devin Magnon +1.10 on 22. Small
samples.
