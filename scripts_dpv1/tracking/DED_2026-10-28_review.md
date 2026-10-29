# DED 2026-10-28 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Fourth card
on 1.3.2. One logged run, the record: `generated_at = 2026-10-28T14:33:40`,
pre-race, bridged, 82 rows, commit `5ac7c1a`
(`picks/DED_2026-10-28_20261028-1433.*`). The late scratches and jockey
changes (posted 4:50–5:10 PM ET) came after this run; it was not re-logged.

This pass is read-only on the live model: no changes to 1.3.2, the
rerankers or Piece 1–4 code. `scripts/racing_full.db.ded1028-run.bak` (the
pre-race DB) is kept for Saturday's paired comparison.

## Load (2026-10-29)

* Chart `Delta Downs/ded-results-2026/DED102826USA.pdf`, read with the
  standard chart parser (pdfplumber, the only text path; no fallback).
  8 races, 71 starters, 41 exotic rows. The 82-entry pre-race card was
  purged first. 0 errors.
* DB backup: `scripts/racing_full.db.pre-ded1028res.bak` (made 2026-10-28
  20:45, before the session stopped at the usage limit; the chart had not
  been loaded). Verified today: same sha256 as the live DB
  (`cfaf9836…8f13`), `integrity_check` ok on both, and the same row counts
  in six tables.
* Spot checks: R1 official 7-10-3-5 and R8 9-5-3-7, as expected. All
  payouts match the chart except one:

  | check | expected | chart | |
  |---|---|---|---|
  | R5 $1 exacta 5-9 | 229.10 | 229.10 | ok |
  | R5 $0.50 Pick 4 (R2–R5) | 659.75 | 659.75 | ok |
  | R5 $0.50 Pick 5 (R1–R5) | 1,318.40 | 1,318.40 | ok |
  | R8 $0.50 Pick 4 (R5–R8) | 1,257.40 | 1,257.40 | ok |
  | R8 $0.50 Pick 5 (R4–R8) | 3,712.20 | 3,712.20 | ok |
  | R4 $0.50 Pick 3 (R2–R4) 3-9-7 | 7.60 | **7.65** | **differs** |

  The chart prints "$0.50Pick3 3-9-7(3correct) 7.65 4,860", and the parser
  reads the same. Doug's bet is logged at $7.65 (see Doug's bets).
* **One dead heat:** R2, 5th place, #6 Critical Threat and #10 Warren L
  (out of the money; no ITM effect). **No DQs** (crossing order =
  `official_finish_pos` in all 8 races), **no non-betting starters**.
* **One non-finisher in R6:** #5 Ageof Reason, the 1.8-1 favourite (model
  3rd, Don's 3rd, Doug's 2nd), "refused" at the start. Stewards' inquiry
  into the start, no action. A betting interest, so a starter that lost.
  R7 also had an inquiry into the running, no change.
* 11 logged horses scratched. All 11 on Doug's list are confirmed; the chart
  gives these reasons:

  | R | horse | chart reason | Doug's list | logged rank | P(ITM) |
  |---|---|---|---|---|---|
  | 1 | #11 Imperial Cruiser | Also-Eligible | morning | 5 of 11 | 27.7 |
  | 1 | #1 The Big Ben | Gate | gate | 6 of 11 | 24.8 |
  | 3 | #5 Apollo's Fury | Veterinarian | late vet | 4 of 12 | 33.7 |
  | 3 | #11 Buster Scruggs | Also-Eligible | morning | 11 of 12 | 11.5 |
  | 3 | #12 Wildly Wicked | Also-Eligible | morning | 9 of 12 | 12.8 |
  | 4 | #4 Clearly Colossal | Veterinarian | morning | **1 of 9** | 45.1 |
  | 4 | #5 Cookn Wit Catman | Veterinarian | late vet | 9 of 9 | 12.3 |
  | 5 | #10 Betsy Louise | Veterinarian | late vet | 4 of 10 | 41.4 |
  | 8 | #11 Mo'z Star Sailor | Also-Eligible | morning | 9 of 12 | 18.6 |
  | 8 | #12 Quikonthetrigger | Also-Eligible | morning | 8 of 12 | 23.3 |
  | 8 | #2 Ocean Voyager | Veterinarian | late vet | 4 of 12 | 30.7 |

  Doug's "morning" scratches R1 #11, R3 #11/#12 and R8 #11/#12 are
  also-eligibles that did not draw in; R4 #4 is a vet scratch on the chart.
* **Late jockey changes (not rescored).** Timothy Thornton came off four
  mounts, and the model priced all four with Thornton's stats:

  | R | horse | model rank (runners) | replacement (chart) | finished | odds |
  |---|---|---|---|---|---|
  | 1 | #2 Hold My Hat | 4 of 9 | Colby Hernandez | 6th | 12.6 |
  | 2 | #3 Donegal Freedom | **1 of 10** | Colby Hernandez | **1st** | 0.7 (fav) |
  | 7 | #10 Miracle Mula | **1 of 10** (Don's POD) | Kevin Roman | 4th | 1.9 (fav) |
  | 8 | #9 Marks Legacy | 2 of 9 (base #1) | Colby Hernandez | **1st** | 0.7 (fav) |

  Two more changes the run did not see: R1 #6 Shot Gun Shack, Carlos Perez
  off, Baron Spann up (broke in the air, last of 9 at 5.0-1), and R3 #6
  Mr. Mo, first-time Lasix (last of 9 at 4.1-1).
* Pick payouts, all parsed (per $0.50):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 7-3-9 | 7.05 |
  | Pick 3 | R2–R4 | 3-9-7 | 7.65 |
  | Pick 3 | R3–R5 | 9-7-5 | 98.20 |
  | Pick 3 | R4–R6 | 7-5-1 | 284.85 |
  | Pick 3 | R5–R7 | 5-1-9 | 1,468.10 |
  | Pick 3 | R6–R8 | 1-9-9 | 42.35 |
  | Pick 4 (early) | R2–R5 | 3-5/9/11/12-4/5/7-5 | 659.75 |
  | Pick 5 (early) | R1–R5 | 1/7/11-3-5/9/11/12-4/5/7-5 | 1,318.40 |
  | Pick 4 (late) | R5–R8 | 5-1-9-2/9/11/12 | 1,257.40 |
  | Pick 5 (late) | R4–R8 | 4/5/7-5-1-9-2/9/11/12 | 3,712.20 |

  The `/` legs are scratch substitutes, each going to the post-time
  favourite, who won every time: R1 #1/#11 → #7, R3 #5/#11/#12 → #9, R4
  #4/#5 → #7, R8 #2/#11/#12 → #9. R5's #10 went to the favourite #1
  Exploding Circle, who ran 6th, so no R5 `/` appears. The Pick 3 rows print
  without substitutes, as on 10/24.
* `score_predictions.py --track DED --date 2026-10-28`, official figures:
  * The logged top pick was ITM in 4 of 7 and won 3 of 7 (R4's top pick
    was scratched).
  * Top-pick show ROI was −22.9% ($10.80 back on $14).
  * All horses were ITM 24 of 71.

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).
* **Exacta box:** a $1 exacta box of the model's top 2 ($2 a race).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 10-9-3-2 | 7-10-3-5 | **2nd** | 5 of 9 (1.6-1, fav) | 2/3 | miss | miss | 10-9 miss | 17.03 |
| 2 | 3-5-2-7 | 3-5-2-8 | **1st** (fav) | 1 of 10 (0.7-1, fav) | 3/3 | **HIT** | miss | **3-5 HIT $6.70** | 29.51 |
| 3 | 9-3-6-7 | 9-2-10-3 | **1st** (fav) | 1 of 9 (1.2-1, fav) | 1/3 | miss | miss | 9-3 miss | 63.68 |
| 4 | 3-9-2-7 | 7-6-8-2 | 7th (last) | 4 of 7 (1.1-1, fav) | 0/3 | miss | miss | 3-9 miss | 8.66 |
| 5 | 4-1-7-3 | 5-9-7-4 | 4th | 7 of 9 (45.2-1) | 1/3 | miss | miss | 4-1 miss | 430.81 |
| 6 | 1-8-5-2 | 1-6-2-7 | **1st** | 1 of 8 (2.4-1) | 1/3 | miss | miss | 1-8 miss | 288.41 |
| 7 | 10-6-3-5 | 9-1-6-10 | 4th (fav) | 6 of 10 (7.5-1) | 1/3 | miss | miss | 10-6 miss | 130.01 |
| 8 | 7-9-3-1 | 9-5-3-7 | 4th | 2 of 9 (0.7-1, fav) | 2/3 | miss | miss | 7-9 miss | 20.66 |

**Model:** the #1 pick won 3 races (R2 Donegal Freedom $3.40, R3 Forty Three
Cents $4.40, R6 Thats Unbelievable $6.80) and was ITM in 4 of 8. Top-3
overlap was 11 of 24. The top-3 wheel hit once (R2, $29.51 on a $4.20
wheel), the top-two exacta box once (R2 3-5, $6.70; $6.70 back on $16), and
the super box not at all (R2's 4th was #8 Unfathomed at 44.1-1; the model
had #7 4th).

* R4 lost the model's #1 (#4 Clearly Colossal, vet). The next pick, #3 Z's
  Guitar (44.4, 0.1pp ahead of #9 All West), ran last of 7 at 23.5-1. The
  model had the favourite Butler Cabin (won, 1.1-1) 4th.
* R5 winner Tarkington Girl (45.2-1) was the model's 7th of 9 (19.7%).
* R7 winner Hegs (7.5-1) was 6th of 10; the model's #1 Miracle Mula (Don's
  POD, Thornton off) ran 4th as the 1.9-1 favourite.
* R8: the base #1 Marks Legacy won at 0.7-1; the reranker had put Ahooga
  (4th) on top. See below.

### Reranker

The reranker changed the #1 in **3 races** (R1, R5, R8):

| R | base #1 | finished | reranked #1 | finished | effect |
|---|---|---|---|---|---|
| 1 | #9 That's Apriority (44.3 → 38.8) | 7th (13.3-1) | #10 Ripple's Rocket (43.0 → 41.5) | **2nd** (2.1-1) | +1 ITM |
| 5 | #1 Exploding Circle (44.0 → 44.0) | 6th (2.0-1, fav) | #4 Alyse Parker (42.0 → 45.9) | 4th (5.0-1) | none (both out) |
| 8 | #9 Marks Legacy (38.0 → 34.0) | **1st** (0.7-1, fav) | #7 Ahooga (36.4 → 43.8) | 4th (5.8-1) | −1 W, −1 ITM |

Net on the card: #1 wins 3 vs 4 (−1), #1 ITM 4 vs 4 (level), overlap 11 vs
12 (−1), exacta box 1 vs 1, super box 0 vs 0. The $2 win line was $14.60
reranked vs $18.00 base. In R1 the change was not a lift for #10 (it fell
1.5pp) but a 5.5pp cut to #9.

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #9 That's Apriority | 44.3 → 38.8 (−5.5) | 1 → 2 | 7th (13.3-1) |
| 1 | #3 King Jules | 28.2 → 34.3 (+6.1) | 3 → 3 | **3rd** (25.3-1) |
| 1 | #2 Hold My Hat | 24.6 → 30.3 (+5.6) | 4 → 4 | 6th (12.6-1) |
| 2 | #5 Julia's Warrior | 50.6 → 55.7 (+5.1) | 2 → 2 | **2nd** (4.0-1) |
| 4 | #9 All West | 35.6 → 44.3 (+8.6) | 4 → 2 | 5th (6.2-1) |
| 6 | #3 Very Cosmopolitan | 42.6 → 35.5 (−7.1) | 3 → 5 | 5th (2.1-1) |
| 6 | #6 Talksalot | 19.1 → 24.2 (+5.1) | 7 → 7 | **2nd** (27.8-1) |
| 7 | #10 Miracle Mula | 55.3 → 49.7 (−5.6) | 1 → 1 | 4th (1.9-1, fav) |
| 8 | #7 Ahooga | 36.4 → 43.8 (+7.3) | 2 → 1 | 4th (5.8-1) |

**Running reranker tally, for Saturday's comparison** (record runs, re-ranked
among runners; all 10 cards, 86 races). The reranker has changed the #1 in
13 races:

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

In those 13 races: base #1 4 W, 9 ITM; reranked #1 3 W, 6 ITM.

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 10/28 | 8 | 3 | 3 / 4 / $14.60 (−8.8%) | 4 / 4 / $18.00 (+12.5%) |
| 1.3.2 (10/22–10/28) | 34 | 8 | 5 / 15 / $24.40 (−64.1%) | 6 / 16 / $37.20 (−45.3%) |
| 1.3.1 (10/21) | 8 | 0 | 2 / 4 / $9.60 (−40.0%) | same |
| 1.3.0 (10/10–10/17) | 44 | 5 | 15 / 25 / $101.20 (+15.0%) | 15 / 27 / $138.60 (+57.5%) |
| **Meet** | 86 | 13 | 22 / 44 / $135.20 (−21.4%) | 23 / 47 / $185.40 (+7.8%) |

The meet base-only line through 10/24 (19 W, 43/78, +7.3%) matches the 10/24
review. `model_health` (logged basis, top-pick scratches excluded) has
1.3.2 base-only and with-reranker level at 15/30 ITM; its four-arm shadow
reconstruction on 1.3.2 is X 6/13, Y 6/13, W 7/13, Z 6/13 (far too few
races). The paired 1.3.0 / 1.3.2 / 1.3.2-no-reranker run on Saturday will
use `.ded1028-run.bak`.

### Stretch feature (1.3.2 vs 1.3.1)

Not run: the pre-race card has been replaced by the results card, and this
pass is read-only. (Saturday's paired comparison covers 1.3.0 vs 1.3.2.)

## Low-coverage (<65%) horses

Only **1 of 71** starters was below 65% coverage: R3 #7 He's Wicked (53%,
model 4th of 9 at 28.1%), 5th at 3.2-1. The other no-history shippers sat
just above the line (65–68%), and none of the five that ran hit the board:
R1 #8 Big Country Boy (5th, 58.6-1), R2 #10 Warren L (dead heat 5th),
R3 #8 Readyto Ride (6th), R3 #7 He's Wicked (5th), R6 #3 Very Cosmopolitan
(5th, 2.1-1; Doug's #1). Summed P(ITM) 1.08, 0 ITM. R3 (maiden special
weight, 77% race coverage) was the lowest-coverage race again, and the model's
#1 won it.

## Benchmarks: Don and Doug

Re-ranked around scratches as before (Don's alt moves up; Doug has no alt).

* Don, R1: #11 (his 3rd pick) scratched, alt #4 moves up. R3: **#5 Apollo's
  Fury, his #1, was a late vet scratch**; alt #7 moves up. R4: his alt #4
  scratched (not needed). R5: #10 (his 4th) scratched, alt #9 moves up.
  R8: #2 (his 3rd) **and** alt #12 both scratched, so he has 3 picks (9-7-6).
* Doug, R3: **#5 Apollo's Fury (his #1) scratched**, leaving 9-10-6. R5: #10
  (his 3rd) scratched, leaving 9-7-4. Doug passed no races and made no best
  guesses tonight (`pass_flag = 0`, `best_guess = 0` for all 8; this
  answers the open question on R3 from the 10/28 pre-race log).

Doug's picks were made on race day with scratches and odds known (the late
vet scratches came after his picks).

| R | Don (re-ranked) | Don #1 fin | Don overlap | Doug (re-ranked) | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 7-10-5-4 | **1st** | 2/3 | 7-9-3-10 | **1st** | 2/3 | **2nd** | 2/3 |
| 2 | 3-5-6-9 | **1st** | 2/3 | 3-10-2-6 | **1st** | 2/3 | **1st** | 3/3 |
| 3 | 9-10-6-7 | **1st** | 2/3 | 9-10-6 | **1st** | 2/3 | **1st** | 1/3 |
| 4 | 7-6-8-9 | **1st** | 3/3 | 7-6-9-2 | **1st** | 2/3 | 7th | 0/3 |
| 5 | 1-3-4-9 | 6th | 0/3 | 9-7-4 | **2nd** | 2/3 | 4th | 1/3 |
| 6 | 1-3-5-8 | **1st** | 1/3 | 3-5-8-1 | 5th | 0/3 | **1st** | 1/3 |
| 7 | 10-2-6-8 | 4th | 1/3 | 10-8-1-6 | 4th | 1/3 | 4th | 1/3 |
| 8 | 9-7-6 | **1st** | 1/3 | 9-7-6-3 | **1st** | 1/3 | 4th | 2/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | 3 | 4/8 | 11/24 | 1 (R2, $29.51) | 0 | 1 (R2, $6.70) | $14.60 on $16 (−8.8%) |
| Don | **6** | **6/8** | 12/24 | 1 (R4, $8.66) | 0 (7 placed) | **3** (R1 $6.90, R2 $6.70, R4 $7.90) | $27.40 on $16 (**+71.2%**) |
| Doug | 5 | 6/8 | 12/24 | 0 | 0 (6 placed) | 1 (R4, $7.90) | $20.60 on $16 (**+28.8%**) |

* **Don's best card of the meet:** 6 winners from 8 #1s, all at short
  prices (R1 $5.20, R2 $3.40, R3 $4.40 after his #1 scratched, R4 $4.20,
  R6 $6.80, R8 $3.40). His R4 top three 7-6-8 was the exact trifecta
  ($13.45 per $0.50).
* Doug's #1 matched Don's in 6 of 8 races (R1–R4, R7, R8); the model's #1
  matched Don's in 4 (R2, R3, R6, R7) and Doug's in 3 (R2, R3, R7).
* All three missed R5 (Tarkington Girl, 45.2-1) and R7 (Hegs, 7.5-1).
* Doug's R6 #1 Very Cosmopolitan (no-history shipper, model 5th) ran 5th
  as the 2.1-1 second choice.

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

Model rows are by the version that made the record run. Don and Doug are
split by the same dates. Doug has no picks before 10/21.

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **10/28** | Model | 8 | 3 | 4 (50%) | 11/24 | −8.8% |
| | Don | 8 | 6 | 6 (75%) | 12/24 | +71.2% |
| | Doug | 8 | 5 | 6 (75%) | 12/24 | +28.8% |
| **1.3.2** (10/22–10/28) | Model | 34 | 5 | 15 (44%) | 49/102 | −64.1% |
| | Don | 34 | 11 | 19 (56%) | 53/102 | −20.6% |
| | Doug | 32 | 12 | 21 (66%) | 51/96 | −0.9% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.8% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (10 cards) | Model | 86 | 22 | 44 (51%) | 126/258 | −21.4% |
| | Don | 77 | 26 | 45 (58%) | 120/231 | −8.7% |
| | Doug | 40 | 15 | 24 (60%) | 61/120 | +3.0% |
| | Doug, without best guesses | 37 | 13 | 22 (59%) | 55/111 | −7.3% |

* The meet $2 win lines ($135.20 model, $140.60 Don, $82.40 Doug) match the
  ticket replay.
* `model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
  scratches excluded): top pick ITM 15/30 = 50.0%, win 5/30; show ROI
  −34.8% ($39.10 on $60). **The alert is still on** (show ROI below −25%
  over the window).

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R7 #10 Miracle Mula (ML 7-2) | | **4th** at 1.9-1 (fav) | — | — |
| EP4 (R2–R5) | 3-5-6 / 5-9-10 / 6-7 / 1-3-4-10 (72 combos) | $36 | miss, dead in R5 | 3/4 | 3-5/9/11/12-4/5/7-5 paid 659.75 |
| LP4 (R5–R8) | 1-3-4-10 / 1-3 / 2-6-10 / 7-9 (48 combos) | $24 | miss, dead in R5 | 2/4 (R6, R8) | 5-1-9-2/9/11/12 paid 1,257.40 |

* POD Miracle Mula (Thornton off, Kevin Roman up) ran 4th as the favourite.
* EP4: R2 #3, R3 #9 and R4 #7 were on the ticket. **Scratched ticket horses:**
  R3 #5 (his #1, vet) would have taken the favourite #9, who won, but #9 was
  on the ticket anyway. R5 #10 (vet) took the favourite #1 Exploding Circle,
  who ran 6th, so the R5 leg (1-3-4-10) died to #5 Tarkington Girl at 45.2-1.
* LP4: dead in R5 the same way. R6 #1 and R8 #9 were on the ticket; R7 (2-6-10)
  missed Hegs (#9). R8's #2 Ocean Voyager (vet) was not on the LP4 leg.
* Don's day: $60 wagered, $0 back.

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 2–4 | Pick 3, $0.50 | 3 / 9 / 3,7,9 (3 combos) | $1.50 | **won**: 3-9-7, **$7.65** |
| DED | 2–5 | Pick 4, $0.50 | 3 / 9 / 7 / 1,4,9 (3 combos) | $1.50 | lost in R5 (#5 at 45.2-1) |

Night total: **$3.00 wagered, $7.65 returned**. Both are DED bets and qualify
Doug for the DED PP rebate.

* **Payout:** Doug reported $7.60; the chart (and the parse) print $7.65 per
  $0.50 for the R2–R4 Pick 3. Logged at $7.65, with a note on the row. Worth
  checking against the TwinSpires statement.
* The Pick 4's R5 leg (1, 4, 9): #9 Whata Hangover ran 2nd, #4 Alyse
  Parker 4th, #1 Exploding Circle 6th.

## Watch list

No starters for Discerner, Cincy's Player or Celestial Clock. Calhoun's only
entry, R1 #11 Imperial Cruiser, was an also-eligible that did not draw in.

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 3 | #10 Boss Kid | J D. Magnon | 5 of 9 | 25.7 | **3rd** | 5.2 |
| 7 | #2 Gorilla Trek | T Rylee Magnon, J D. Magnon | 8 of 10 | 22.7 | 5th | 10.7 |
| 8 | #3 Native Requite | T Ward | 3 of 9 | 32.8 | **3rd** | 12.9 |

Meet tally after 10/28 (`watch_people_tally.csv`; logged record runs only,
pooled across 1.3.0, 1.3.1 and 1.3.2):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 20 | 2 | 9 | 6.52 | 9 | +2.48 |
| J Devin H. Magnon | 20 | 4 | 7 | 6.26 | 7 | +0.74 |
| T Rylee Magnon | 6 | 1 | 2 | 2.26 | 2 | −0.26 |
| T W.B. Calhoun | 15 | 3 | 8 | 4.90 | 8 | +3.10 |

The three watch starters had 0.81 summed P(ITM) and 2 hit the board (Boss
Kid, Native Requite). Ward moves to +2.48 on 20 starts; Calhoun is still the
biggest gap (+3.10 on 15). Small samples.
