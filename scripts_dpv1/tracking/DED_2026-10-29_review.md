# DED 2026-10-29 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Fifth card
on 1.3.2. One logged run, the record: `generated_at = 2026-10-29T15:06:13`,
pre-race, bridged, 75 rows, commit `fa14a7b`
(`picks/DED_2026-10-29_20261029-1506.*`). The late scratches and jockey
changes came after this run; it was not re-logged.

This pass is read-only on the live model: no changes to 1.3.2, the
rerankers or Piece 1–4 code. `scripts/racing_full.db.ded1029-run.bak` (the
pre-race DB) is kept for Saturday's paired comparison, along with
`.ded1028-run.bak`.

## Load (2026-10-29 evening)

* Chart `Delta Downs/ded-results-2026/DED102926USA.pdf`, read with the
  standard chart parser (pdfplumber). 8 races, 67 starters, 41 exotic rows.
  The 75-entry pre-race card was purged first. 0 errors.
* DB backup: `scripts/racing_full.db.pre-ded1029res.bak`, verified before
  the load: same sha256 as the live DB, `integrity_check` ok on both, and the
  same row counts in six tables.
* Spot checks: R1 official 8-1-5-9 and R2 5-1-8-6, as expected.
* **No dead heats, no DQs** (crossing order = `official_finish_pos` in all
  8 races), **no non-betting starters**.
* **One non-finisher:** R1 #6 My Pal Magic (88.5-1, model last of 9) "dueled
  for the early lead, dropped back and was eased to the wire". A starter
  that lost. R5's start was "good for all except #4" (U Rascal U, awkward
  start; 7th, model 7th of 7).
* **Scratches.** Eight logged horses scratched. All the known ones are
  confirmed, plus one that was not on Doug's list (R4 #9):

  | R | horse | chart reason | Doug's list | logged rank | P(ITM) |
  |---|---|---|---|---|---|
  | 1 | #10 Creole Lady | Veterinarian | late | 5 of 12 | 33.7 |
  | 1 | #11 Call Sadie | Also-Eligible | morning | 11 of 12 | 6.8 |
  | 1 | #12 Myspittinimage | Also-Eligible | morning | 9 of 12 | 12.7 |
  | 2 | #7 Yockey's Drivethru | Stewards | morning | 9 of 10 | 15.3 |
  | 3 | #11 Just Sailing Along | Also-Eligible | morning | 8 of 11 | 15.2 |
  | 4 | #9 Great Fortune | Veterinarian | **not listed** | 8 of 9 | 14.6 |
  | 8 | #12 Stormcatholic Spot | Also-Eligible | morning | 8 of 12 | 13.3 |
  | 8 | #3 Thunder Kiss | Trainer | morning | 11 of 12 | 10.6 |

  **R6 #7 Bellastone Country was not scratched.** The chart has him running
  4th at 9.4-1 with Elio Barrera, as listed. He was the model's 2nd pick and
  is scored as a starter. Great Fortune (R4 #9) was on no one's list (model
  8th; not in Don's or Doug's picks).
* **Late jockey changes (not rescored).** The model priced each horse with
  the rider in the PP file:

  | R | horse | listed | rode (chart) | model rank (runners) | finished | odds |
  |---|---|---|---|---|---|---|
  | 1 | #7 Gently | Timothy Thornton | Isaac Castillo | **1 of 9** (consensus #1) | 5th | 1.7 (fav) |
  | 2 | #1 Cajun Ami | Timothy Thornton | Alexander Castillo | 3 of 9 | **2nd** | 14.1 |
  | 4 | #4 Lolo's Girl | Colby Hernandez | Thomas Pompell | 2 of 8 | 7th | 9.3 |
  | 7 | #4 Jewlz | Timothy Thornton | Kevin Roman | 2 of 7 (**base #1**) | **2nd** | 3.5 |
  | 8 | #5 Yalla Vamos | Colby Hernandez | Thomas Pompell | 3 of 10 | **1st** | 1.0 (fav) |
  | 8 | #11 Cinco Blake | Javier Hernandez | Jose Rodriguez | 8 of 10 | **2nd** | 8.4 |

  Thornton came off all three of his mounts (as on 10/28, when he came off
  four), and Colby Hernandez off both of his. Javier Hernandez was listed on
  R8 #9 and #11 and rode #9. R3 #4 Ruler's Princess and R8 #7 Biblical Stones
  had no rider in the PP file; Julio Ramirez Jr. rode both.
* Pick payouts, all parsed (per $0.50):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 8-5-10 | 31.35 |
  | Pick 3 | R2–R4 | 5-10-2 | 107.65 |
  | Pick 3 | R3–R5 | 10-2-7 | 248.00 |
  | Pick 3 | R4–R6 | 2-7-2 | 860.70 |
  | Pick 3 | R5–R7 | 7-2-5 | 69.05 |
  | Pick 3 | R6–R8 | 2-5-5 | 26.45 |
  | Pick 4 (early) | R2–R5 | 5/7-10/11-2-7 | 1,783.05 |
  | Pick 5 (early) | R1–R5 | 8-5/7-10/11-2-7 | 7,984.70 |
  | Pick 4 (late) | R5–R8 | 7-2-5-3/5/12 | 150.15 |
  | Pick 5 (late) | R4–R8 | 2-7-2-5-3/5/12 | 4,550.65 |

  The `/` legs are scratch substitutes, each going to the post-time
  favourite, who won every time: R2 #7 → #5, R3 #11 → #10, R8 #3/#12 → #5.
  R1's scratches went to the favourite #7 Gently (5th) and R4's #9 to #8
  Annie's Allie (4th), so no `/` appears for them.
* `score_predictions.py --track DED --date 2026-10-29`, official figures:
  * The logged top pick was ITM in 5 of 8 and won 1 of 8.
  * Top-pick show ROI was −7.5% ($14.80 back on $16).
  * All horses were ITM 24 of 67. 67 rows scored (2,061 total).

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).
* **Exacta box:** a $1 exacta box of the model's top 2 ($2 a race).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 7-9-1-8 | 8-1-5-9 | 5th (fav) | 4 of 9 (4.3-1) | 1/3 | miss | miss | 7-9 miss | 337.93 |
| 2 | 9-8-1-3 | 5-1-8-6 | 8th | 7 of 9 (1.6-1, fav) | 2/3 | miss | miss | 9-8 miss | 150.81 |
| 3 | 8-10-2-3 | 10-3-8-2 | **3rd** | 2 of 10 (2.0-1, fav) | 2/3 | miss | **HIT $48.68** | 8-10 miss | 48.68 |
| 4 | 1-4-6-2 | 2-1-6-8 | **2nd** | 4 of 8 (30.1-1) | 2/3 | miss | miss | 1-4 miss | 182.90 |
| 5 | 7-3-1-5 | 7-2-1-5 | **1st** | 1 of 7 (4.8-1) | 2/3 | miss | miss | 7-3 miss | 35.23 |
| 6 | 4-7-2-6 | 2-1-4-7 | **3rd** (fav) | 3 of 7 (2.3-1) | 2/3 | miss | miss | 4-7 miss | 22.80 |
| 7 | 7-4-6-3 | 5-4-7-6 | **3rd** (fav) | 6 of 7 (3.6-1) | 2/3 | miss | miss | 7-4 miss | 9.13 |
| 8 | 2-8-5-1 | 5-11-1-8 | 6th | 3 of 10 (1.0-1, fav) | 1/3 | miss | miss | 2-8 miss | 70.33 |

**Model:** the #1 pick won once (R5 Highstakes Hustler, $11.60) and was ITM
in 5 of 8. Top-3 overlap was 14 of 24. The top-two exacta box missed all 8
races ($0 back on $16), the top-3 wheel missed all 8 ($25.80), and the super
box hit once (R3 8-10-2-3, $48.68 on $2.40; $48.68 back on $19.20).

* **R2:** the model's #1 #9 Tensas Camp Road (49.6, lifted 5.6pp by the
  reranker) ran 8th at 14.6-1. The winner, the 1.6-1 favourite
  Nopenottonight, was the model's 7th of 9 (27.4%) and Don's #1.
* **R3** (maiden special weight): the model's top two were both no-history
  shippers at 53% coverage, #8 Iron Cutter (3rd) and #10 Trupeg's Dynasty
  (won, 2.0-1 fav), 0.4pp apart. The super box hit only because the reranker
  moved #3 Bandit's Escape (2nd, 21.1-1) up to 4th.
* **R4:** #2 Jailhouse Religion won at 30.1-1 (model 4th of 8, 37.8%; not in
  Don's or Doug's picks). The model's #1 Blue Mist ran 2nd.
* **R8:** the model's #1 Fruit Basket ran 6th at 2.4-1. The 1.0-1 favourite
  Yalla Vamos (Colby Hernandez off, Pompell up) won; model 3rd.
* The model's #1 was the favourite in R1, R6 and R7, and all three lost.

### Reranker

The reranker changed the #1 in **1 race** (R7):

| R | base #1 | finished | reranked #1 | finished | effect |
|---|---|---|---|---|---|
| 7 | #4 Jewlz (60.9 → 56.1) | **2nd** (3.5-1) | #7 Tortuga Coast (55.5 → 56.8) | **3rd** (2.1-1, fav) | none on W/ITM (both ITM, neither won) |

The cut was to Jewlz, a no-history shipper (64% coverage) listed with
Thornton, who came off (Kevin Roman up). Tortuga Coast rose only 1.3pp.

Net on the card: #1 wins 1 vs 1, #1 ITM 5 vs 5, overlap 14 vs 14, exacta box
0 vs 0, $2 win $11.60 vs $11.60. **Super box: reranked hit R3 ($48.68),
base-only would have hit R7 instead** (4-7-6-5 → 5-4-7-6, $9.13; the
reranked top four 7-4-6-3 had #3 My Southern Girl, 7th, in place of #5
Shesabeast, the winner). The R3 hit came from the +6.0pp move on #3 Bandit's
Escape (rank 7 → 4).

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #3 Mo Kitty | 18.9 → 12.6 (−6.2) | 6 → 8 | 7th (27.5-1) |
| 2 | #9 Tensas Camp Road | 44.0 → 49.6 (+5.6) | 1 → 1 | 8th (14.6-1) |
| 3 | #3 Bandit's Escape | 24.6 → 30.6 (+6.0) | 7 → 4 | **2nd** (21.1-1) |
| 3 | #1 Laura's Custom | 15.2 → 9.0 (−6.1) | 10 → 10 | 10th (17.1-1) |
| 5 | #3 Hedge | 60.4 → 67.4 (+7.0) | 2 → 2 | 5th (1.8-1, fav) |
| 5 | #4 U Rascal U | 26.5 → 20.4 (−6.1) | 7 → 7 | 7th (8.8-1) |
| 8 | #2 Fruit Basket | 53.5 → 58.8 (+5.2) | 1 → 1 | 6th (2.4-1) |
| 8 | #8 Promise Me Money | 39.0 → 45.9 (+6.9) | 4 → 2 | 4th (22.3-1) |
| 8 | #7 Biblical Stones | 17.5 → 10.8 (−6.7) | 7 → 9 | 9th (46.0-1) |

**Running reranker tally, for Saturday's comparison** (record runs, re-ranked
among runners; all 11 cards, 94 races). The reranker has changed the #1 in
14 races:

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

In those 14 races: base #1 4 W, 10 ITM; reranked #1 3 W, 7 ITM.

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 10/29 | 8 | 1 | 1 / 5 / $11.60 (−27.5%) | 1 / 5 / $11.60 (−27.5%) |
| 1.3.2 (10/22–10/29) | 42 | 9 | 6 / 20 / $36.00 (−57.1%) | 7 / 21 / $48.80 (−41.9%) |
| 1.3.1 (10/21) | 8 | 0 | 2 / 4 / $9.60 (−40.0%) | same |
| 1.3.0 (10/10–10/17) | 44 | 5 | 15 / 25 / $101.20 (+15.0%) | 15 / 27 / $138.60 (+57.5%) |
| **Meet** | 94 | 14 | 23 / 49 / $146.80 (−21.9%) | 24 / 52 / $197.00 (+4.8%) |

`model_health` (logged basis, top-pick scratches excluded) has 1.3.2
base-only and with-reranker level at 20/38 ITM; its four-arm shadow
reconstruction on 1.3.2 is X 9/16, Y 9/16, W 10/16, Z 9/16 (far too few
races). The paired 1.3.0 / 1.3.2 / 1.3.2-no-reranker run on Saturday will
use `.ded1028-run.bak` and `.ded1029-run.bak`.

### Stretch feature (1.3.2 vs 1.3.1)

Not run: the pre-race card has been replaced by the results card, and this
pass is read-only. (Saturday's paired comparison covers 1.3.0 vs 1.3.2.)

## Low-coverage (<65%) horses

**11 of 67** starters were below 65% coverage, all no-history shippers (13
of the card's 14 shippers ran; R8 #12 Stormcatholic Spot was an
also-eligible). Summed P(ITM) 3.02, actual ITM 4:

| R | horse | cov | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 1 | #3 Mo Kitty | 61% | 8 of 9 | 12.6 | 7th | 27.5 |
| 3 | #8 Iron Cutter | 53% | **1 of 10** | 46.9 | **3rd** | 2.6 |
| 3 | #10 Trupeg's Dynasty | 53% | 2 of 10 | 46.5 | **1st** | 2.0 (fav) |
| 3 | #4 Ruler's Princess | 45% | 5 of 10 | 28.2 | 7th | 50.7 |
| 3 | #7 Princess Peach | 56% | 6 of 10 | 28.2 | 6th | 4.8 |
| 3 | #9 Rockaby Baby | 57% | 8 of 10 | 13.9 | 9th | 32.9 |
| 4 | #7 Vern | 56% | 7 of 8 | 15.6 | 6th | 48.0 |
| 5 | #6 Husker Butch | 58% | 5 of 7 | 29.7 | 6th | 12.6 |
| 7 | #4 Jewlz | 64% | 2 of 7 (base #1) | 56.1 | **2nd** | 3.5 |
| 8 | #11 Cinco Blake | 61% | 8 of 10 | 13.2 | **2nd** | 8.4 |
| 8 | #7 Biblical Stones | 56% | 9 of 10 | 10.8 | 9th | 46.0 |

The two shippers just above the line, R8 #6 Time to Jive (66%, 5th) and #10
Let's Get Together (68%, 8th), missed. R3 (maiden special weight, 70% race
coverage) was the lowest-coverage race again; the model's top two there
finished 1st and 3rd.

## Benchmarks: Don and Doug

Re-ranked around scratches as before (Don's alt moves up; Doug has no alt).

* **R1: #10 Creole Lady, both Don's and Doug's #1, was a late vet scratch.**
  Don's alt #8 moves up (7-1-9-8); Doug is left with 7-9. That made #7 Gently
  the #1 for all three.
* No other scratch touched Don's or Doug's picks (R4 #9 Great Fortune was on
  neither list).
* Doug's picks were all regular picks (no passes, no best guesses), made on
  race day with the morning scratches known. He gave three picks in R1 and R7.

| R | Don (re-ranked) | Don #1 fin | Don overlap | Doug (re-ranked) | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 7-1-9-8 | 5th | 1/3 | 7-9 | 5th | 0/3 | 5th | 1/3 |
| 2 | 5-8-2-6 | **1st** | 2/3 | 8-3-9-10 | **3rd** | 1/3 | 8th | 2/3 |
| 3 | 2-8-10-7 | 4th | 2/3 | 5-8-3-7 | 5th | 2/3 | **3rd** | 2/3 |
| 4 | 8-4-1-6 | 4th | 1/3 | 6-8-4-3 | **3rd** | 1/3 | **2nd** | 2/3 |
| 5 | 2-3-7-1 | **2nd** | 2/3 | 7-3-1-5 | **1st** | 2/3 | **1st** | 2/3 |
| 6 | 4-2-3-1 | **3rd** | 2/3 | 4-5-2-3 | **3rd** | 2/3 | **3rd** | 2/3 |
| 7 | 7-4-5-1 | **3rd** | 3/3 | 4-5-7 | **2nd** | 3/3 | **3rd** | 2/3 |
| 8 | 5-2-8-1 | **1st** | 1/3 | 5-9-1-2 | **1st** | 2/3 | 6th | 1/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | 1 | 5/8 | 14/24 | 0 | **1** (R3, $48.68) | 0 | $11.60 on $16 (−27.5%) |
| Don | 2 | 5/8 | 14/24 | 1 (R7, $9.13) | 0 | 0 | $9.20 on $16 (−42.5%) |
| Doug | 2 | **6/8** | 13/24 | 1 (R7, $9.13) | 0 (6 placed) | 1 (R7 4-5, $18.70) | $15.60 on $16 (−2.5%) |

* R7: Don's top three 7-4-5 and Doug's 4-5-7 were the trifecta in some order
  (5-4-7, $24.05 per $0.50 box).
* Don's #1 won R2 (Nopenottonight $5.20) and R8 (Yalla Vamos $4.00); Doug's
  won R5 (Highstakes Hustler $11.60, with the model) and R8.
* All three missed R1 (#8 Sunnyday Lightning, 4.3-1; Don's 4th pick after the
  scratch) and R4 (#2 Jailhouse Religion, 30.1-1).
* The model's #1 matched Don's in 3 races (R1, R6, R7) and Doug's in 3 (R1,
  R5, R6).

### Consensus #1s (`tracking/consensus_top1.csv`, new)

All three sources had the same #1 (after scratches) in 2 races tonight:

* **R1 #7 Gently**: 5th at 1.7-1 (fav). The consensus came only after the
  #10 scratch; Thornton came off (Isaac Castillo up). "Pressed the early
  pace, faded and finished evenly."
* **R6 #4 Takethe Hint**: 3rd at 1.5-1 (fav); show $2.20.

The new tally file holds every three-way consensus #1 since the 10/28 bet
that started the tag (both cards, 5 races):

| card | R | horse | odds | finished | $2 win | Doug's bet |
|---|---|---|---|---|---|---|
| 10/28 | 2 | #3 Donegal Freedom | 0.7 | **1st** | 3.40 | |
| 10/28 | 3 | #9 Forty Three Cents | 1.2 | **1st** | 4.40 | |
| 10/28 | 7 | #10 Miracle Mula | 1.9 | 4th | | $2 win, lost |
| 10/29 | 1 | #7 Gently | 1.7 | 5th | | (underneath in his 9-7 exacta) |
| 10/29 | 6 | #4 Takethe Hint | 1.5 | **3rd** | | $1 exacta 4-5, lost |

So far: 2 W, 3 ITM from 5, every one the favourite. $2 win on all five:
$7.80 on $10 (−22.0%); $2 show $7.20 on $10 (−28.0%). Doug's two bets on
them: $3.00, $0 back. Five races is no sample.

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

Model rows are by the version that made the record run. Don and Doug are
split by the same dates. Doug has no picks before 10/21.

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **10/29** | Model | 8 | 1 | 5 (62%) | 14/24 | −27.5% |
| | Don | 8 | 2 | 5 (62%) | 14/24 | −42.5% |
| | Doug | 8 | 2 | 6 (75%) | 13/24 | −2.5% |
| **1.3.2** (10/22–10/29) | Model | 42 | 6 | 20 (48%) | 63/126 | −57.1% |
| | Don | 42 | 13 | 24 (57%) | 67/126 | −24.8% |
| | Doug | 40 | 14 | 27 (68%) | 64/120 | −1.2% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.8% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (11 cards) | Model | 94 | 23 | 49 (52%) | 140/282 | −21.9% |
| | Don | 85 | 28 | 50 (59%) | 134/255 | −11.9% |
| | Doug | 48 | 17 | 30 (62%) | 74/144 | +2.1% |
| | Doug, without best guesses | 45 | 15 | 28 (62%) | 68/135 | −6.4% |

* The meet $2 win lines ($146.80 model, $149.80 Don, $98.00 Doug) match the
  ticket replay.
* `model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
  scratches excluded): top pick ITM 20/38 = 52.6%, win 6/38; show ROI
  −29.1% ($53.90 on $76). **The alert is still on** (show ROI below −25%
  over the window), though it improved from −34.8%.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R4 #8 Annie's Allie (ML 9-2) | | **4th** at 1.1-1 (fav) | — | — |
| EP4 (R2–R5) | 2-5-8 / 2-7-8-10 / 4-8 / 2-3-7 (72 combos) | $36 | miss, dead in R4 | 3/4 | 5/7-10/11-2-7 paid 1,783.05 |
| LP4 (R5–R8) | 1-2-3-7 / 2-4 / 4-5-7 / 2-5 (48 combos) | $24 | **HIT** 7-2-5-5 | 4/4 | 7-2-5-3/5/12 paid **150.15** |

* POD Annie's Allie went off the 1.1-1 favourite and ran 4th.
* EP4: R2 #5, R3 #10 and R5 #7 were on the ticket; the R4 leg (4-8) died to
  #2 Jailhouse Religion at 30.1-1.
* **LP4 hit:** R5 #7 Highstakes Hustler, R6 #2 Cajun Country, R7 #5
  Shesabeast, R8 #5 Yalla Vamos. One winning combo at $0.50 = $150.15.
* Don's day: $60 wagered, $150.15 back (**+$90.15**).

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 1 | exacta, $1 | 9-7 | $1.00 | lost (8-1-5-9; #9 4th, #7 5th) |
| DED | 2–5 | Pick 4, $0.50 | 8 / 8 / 1,4,6 / 7 (3 combos) | $1.50 | lost in R2 (#8 3rd; #5 won) |
| DED | 6 | exacta, $1 | 4-5 | $1.00 | lost (2-1-4-7; #4 3rd, #5 5th) |
| CT | 2 | superfecta part wheel, $0.10 | 1,3,5 / 1,3,5 / 1,3,5 / 1-6 (18 combos) | $1.80 | lost |

Night total: **$5.30 wagered, $0 returned, −$5.30**. These bets qualify Doug
for the DED PP rebate.

* The CT bet is logged with `track = CT` and is kept out of the DED scoring
  and the ticket replay. It is graded from Doug's report; there is no CT
  10/29 chart on disk.
* The R6 exacta is tagged `consensus_top1` (#4 Takethe Hint, the three-way
  #1, on top). The R1 exacta is not tagged: Gently, the consensus #1, was
  underneath.
* The Pick 4 would have died in R4 as well (1-4-6 vs #2 at 30.1-1); its R3
  (#8 Iron Cutter, 3rd) and R5 (#7, won) legs were split.

## Watch list

No starters for the watched horses (Discerner, Cincy's Player, Celestial
Clock) and no Magnon starters.

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 1 | #7 Gently | T Calhoun | **1 of 9** | 54.9 | 5th | 1.7 (fav) |
| 3 | #9 Rockaby Baby | T Ward | 8 of 10 | 13.9 | 9th | 32.9 |

Meet tally after 10/29 (`watch_people_tally.csv`; logged record runs only,
pooled across 1.3.0, 1.3.1 and 1.3.2):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 21 | 2 | 9 | 6.66 | 9 | +2.34 |
| J Devin H. Magnon | 20 | 4 | 7 | 6.26 | 7 | +0.74 |
| T Rylee Magnon | 6 | 1 | 2 | 2.26 | 2 | −0.26 |
| T W.B. Calhoun | 16 | 3 | 8 | 5.45 | 8 | +2.55 |

Both watch starters missed (0.69 summed P(ITM), 0 ITM). Gently was the
model's #1 and went off the favourite with a replacement rider (Thornton
off), then faded. Calhoun drops from +3.10 to +2.55 on 16 starts,
Ward from +2.48 to +2.34 on 21. Small samples.
