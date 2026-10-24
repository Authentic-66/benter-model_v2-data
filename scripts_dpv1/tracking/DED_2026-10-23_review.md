# DED 2026-10-23 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Second card
on 1.3.2. One logged run, the record: `generated_at = 2026-10-23T09:29:50`,
pre-race, bridged, 82 rows, commit `456c8e3`
(`picks/DED_2026-10-23_20261023-0929.*`; the page header says 09:24 because
it prints when the run starts).

## Load (2026-10-23 evening)

* Chart `Delta Downs/ded-results-2026/DED102326USA.pdf`, read with the
  standard chart parser (pdfplumber, the only text path; no fallback).
  9 races, 75 starters, 46 exotic rows. The 82-entry pre-race card was
  purged first. 0 errors, 0 parser warnings.
* DB backup: `scripts/racing_full.db.pre-ded1023res.bak`, verified: same
  sha256 as the live DB (`f69cf990…fbff9`), `integrity_check` ok on both,
  and the same row counts in six tables.
* Spot checks: R1 official 1-3-7-5 and R2 3-6-7-1, as expected.
* **No dead heats, no DQs** (crossing order = `official_finish_pos` in all 9
  races), **no non-betting starters**, no DNFs.
* 7 logged horses scratched (4 vets, 3 also-eligibles that did not draw in).
  Three of them were the model's #2:

  | R | horse | reason | logged rank | P(ITM) |
  |---|---|---|---|---|
  | 3 | #6 Something Wild | vet | 8 of 8 | 29.1 |
  | 4 | #3 D'busker | vet | **2 of 10** | 52.5 |
  | 5 | #1 Autism Authentic | vet | **2 of 8** | 53.6 |
  | 6 | #9 Twofexusnexus | vet | 5 of 12 | 25.4 |
  | 6 | #11 The Boss Soss | AE | 9 of 12 | 19.9 |
  | 6 | #12 Gasoline | AE | 6 of 12 | 23.2 |
  | 7 | #11 East Shore | AE | **2 of 11** | 41.5 |

  The scratch list Doug sent had R4, R6 and R7. The chart also scratches
  R3 #6 and R5 #1; both are handled below.
* Pick payouts, all parsed (per $0.50):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 1-3-4 | 72.35 |
  | Pick 3 | R2–R4 | 3-4-1 | 52.75 |
  | Pick 3 | R3–R5 | 4-1-8 | 24.55 |
  | Pick 3 | R4–R6 | 1-8-7 | 18.65 |
  | Pick 3 | R5–R7 | 8-7-10 | 26.90 |
  | Pick 3 | R6–R8 | 7-10-9 | 40.40 |
  | Pick 3 | R7–R9 | 10-9-9 | 85.60 |
  | Pick 4 (early) | R2–R5 | 3-4-1/3-1/8 | 141.00 |
  | Pick 5 (early) | R1–R5 | 1-3-4-1/3-1/8 | 410.75 |
  | Pick 4 (late) | R6–R9 | 7/9/11/12-10-9-9 | 442.10 |
  | Pick 5 (late) | R5–R9 | 1/8-7/9/11/12-10-9-9 | 1,351.20 |

  The `/` legs are scratch substitutes: in R4, #3 counts as #1 (the post-time
  favourite, who won); in R5, #1 counts as #8; in R6, #9/#11/#12 count as #7.
* `score_predictions.py --track DED --date 2026-10-23`, official figures:
  * The logged top pick was ITM in 2 of 9 and won 0 of 9 (no top pick
    scratched).
  * Top-pick show ROI was −65.6% ($6.20 back on $18).
  * All horses were ITM 27 of 75.

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | $0.10 super |
|---|---|---|---|---|---|---|---|---|
| 1 | 6-1-3-2 | 1-3-7-5 | 5th (fav) | 2 of 7 (4.5-1) | 2/3 | miss | miss | 42.95 |
| 2 | 6-7-3-5 | 3-6-7-1 | **2nd** (fav) | 3 of 7 (3.2-1) | 3/3 | **HIT** | miss | 7.38 |
| 3 | 1-2-3-7 | 4-5-8-2 | 5th | 5 of 7 (2.7-1) | 0/3 | miss | miss | 39.57 |
| 4 | 2-9-10-5 | 1-9-10-2 | 4th | 6 of 9 (1.8-1, fav) | 2/3 | miss | miss | 18.12 |
| 5 | 2-5-7-4 | 8-6-7-2 | 4th | 5 of 7 (1.8-1, fav) | 1/3 | miss | miss | 24.94 |
| 6 | 8-7-10-4 | 7-5-3-1 | 8th | 2 of 9 (2.1-1, fav) | 1/3 | miss | miss | 42.83 |
| 7 | 7-4-10-3 | 10-2-6-7 | 4th | 3 of 10 (3.0-1) | 1/3 | miss | miss | 89.89 |
| 8 | 3-7-9-8 | 9-8-3-7 | **3rd** | 3 of 9 (2.6-1) | 2/3 | miss | **HIT** | 6.66 |
| 9 | 5-2-8-10 | 9-10-4-7 | 6th | 8 of 10 (7.8-1) | 0/3 | miss | miss | 683.49 |

**Model:** the #1 pick won 0 races and was ITM in 2 of 9, its worst card of
the meet. Top-3 overlap was 12 of 27. The top-3 wheel hit once (R2, $7.38 per
$0.10, on a $2.40 ticket); the super box hit once (R8, $6.66 on $2.40).

* Only 3 of 9 favourites won (R4, R5, R6), and the model had all three low:
  R4 Stephanie's Maria 6th of 9 (20.6% P(ITM)), R5 Merlot 5th of 7 (44%
  coverage), R6 Chupapi Munyayo 2nd of 9.
* The model's #1 was the favourite only in R1 (Look At Me Nah, 0.7-1: bobbled,
  steadied, 5th) and R2 (Double Salty, 1.6-1, 2nd).
* Winners were mostly short prices (7 of 9 at 3.2-1 or less), so this wasn't
  long shots beating the model. The one long-ish winner, R9 Quick Sand (7.8-1,
  gate to wire), was its 8th of 10.
* The model ranked the winner 2nd or 3rd in 5 races (R1, R2, R6, R7, R8):
  the #1 slot missed more than the top of the order did.
* R3 (54%) and R5 (48%) were the low-coverage races; the model's #1 ran 5th
  and 4th.

### Reranker

Base-only #1 was the same in all 9 races. Two top-3/top-4 sets changed:

* R3: base top 3 was 1-2-4; the reranker cut #4 Fearless Maximus (the winner)
  by 2.5 to 5th and moved #3 Golden Penelope (7th) up. Overlap −1.
* R8: base top 4 was 3-9-7-6; the reranker lifted #8 Kenmore West +5.5 from
  6th to 4th, which made the super box (+$6.66).

Net: 0 on #1 ITM, −1 on overlap (13 → 12), +1 super box hit.

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #1 Tasteof Freedom | 48.9 → 58.4 (+9.6) | 2 → 2 | **1st** |
| 1 | #4 Goldenbraids | 19.9 → 13.1 (−6.8) | 7 → 7 | 6th |
| 4 | #2 Stormy Lou | 49.4 → 56.2 (+6.8) | 1 → 1 | 4th |
| 6 | #7 Chupapi Munyayo | 32.7 → 38.3 (+5.7) | 3 → 2 | **1st** |
| 7 | #3 Lil Temptation | 24.5 → 32.3 (+7.8) | 4 → 4 | 8th (93-1) |
| 8 | #3 Warrior Richard | 44.0 → 50.9 (+6.9) | 1 → 1 | **3rd** |
| 8 | #8 Kenmore West | 30.1 → 35.5 (+5.5) | 6 → 4 | **2nd** |
| 9 | #2 Lassie Bee | 33.8 → 41.1 (+7.3) | 3 → 2 | 8th |

### Stretch feature (1.3.2 vs 1.3.1)

Not run tonight. The 10/22 comparison was a scratch run on the pre-race card,
and that card has now been replaced by the results card (features for the
75 reloaded entries aren't rebuilt until the next card's routine). A
like-for-like run would need the `.ded1023-run.bak` state. Skipped to keep
this pass read-only.

## Low-coverage (<65%) horses

17 of 75 starters were below 65% coverage: R5 7 (the whole field), R3 6,
R1 3, R7 1. Their summed P(ITM) was 5.98, and 7 finished in the money:
* R1 #7 Zarlana (3rd, 27.3-1);
* R3 #5 Spitfire Cat (2nd) and #8 Shelliehasmoney (3rd);
* R5 #8 Merlot (1st), #6 Maximum Truth (2nd) and #7 Kipster (3rd);
* R7 #2 Freckles Forever (2nd, 16.4-1).

## Benchmarks: Don and Doug

Re-ranked around scratches as before (Don's alt moves up; Doug has no alt).

* Don, R3: #6 scratched, alt #5 moves up. R4: #3 scratched, alt #5 moves up.
  R6: #9 scratched and his alt #12 scratched too, so 3 picks. R7: #11
  scratched, alt #4 moves up.
* Doug: no scratched picks. **R3 and R5 were PASS** (logged in
  `doug_picks.csv` with blank picks, note "PASS"), so Doug's figures are over
  7 races. R9 4th = "Pick 'em" (blank).

Doug's picks were made on race day with scratches and odds known.

| R | Don (re-ranked) | Don #1 fin | Don overlap | Doug (re-ranked) | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 6-5-3-1 | 5th | 1/3 | 3-6-7-1 | **2nd** | 2/3 | 5th | 2/3 |
| 2 | 6-3-1-7 | **2nd** | 2/3 | 6-7-2-3 | **2nd** | 2/3 | **2nd** | 3/3 |
| 3 | 4-2-7-5 | **1st** | 1/3 | PASS | — | — | 5th | 0/3 |
| 4 | 2-1-9-5 | 4th | 2/3 | 1-9-2-10 | **1st** | 2/3 | 4th | 2/3 |
| 5 | 8-4-6-5 | **1st** | 2/3 | PASS | — | — | 4th | 1/3 |
| 6 | 8-5-7 | 8th | 2/3 | 7-10-8-5 | **1st** | 1/3 | 8th | 1/3 |
| 7 | 7-10-5-4 | 4th | 1/3 | 6-4-7-5 | **3rd** | 1/3 | 4th | 1/3 |
| 8 | 8-9-3-7 | **2nd** | 3/3 | 8-3-6-9 | **2nd** | 2/3 | **3rd** | 2/3 |
| 9 | 5-6-7-2 | 6th | 0/3 | 6-8-5 | 5th | 0/3 | 6th | 0/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | $2 win on #1 |
|---|---|---|---|---|---|---|
| Model | 0 | 2/9 | 12/27 | 1 (R2, $7.38) | 1 (R8, $6.66) | $0 on $18 (−100%) |
| Don | 2 | 4/9 | 14/27 | 1 (R8, $6.66) | 2 (R2 $7.38, R8 $6.66) | $13.00 on $18 (−27.8%) |
| Doug | 2 | 6/7 | 10/21 | 0 | 1 (R4, $18.12) | $11.80 on $14 (−15.7%) |

* On Doug's 7 races the model's #1 was ITM 2/7 and Don's 2/7 (Don's two
  winners came in R3 and R5, Doug's PASS races).
* Don and the model shared #1 in 5 races: R1 Look At Me Nah (5th), R2 Double
  Salty (2nd, Doug's #1 too), R6 Wordsof Wisdom (8th), R7 She's No Angel
  (4th), R9 Tarkington Sunrise (6th).
* Don's two winners were favourite-ish picks the model had low: R3 Fearless
  Maximus (model 5th) and R5 Merlot (model 5th).

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

Model rows are by the version that made the record run. Don and Doug are
split by the same dates. Doug has no picks before 10/21.

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **10/23** | Model | 9 | 0 | 2 (22%) | 12/27 | −100.0% |
| | Don | 9 | 2 | 4 (44%) | 14/27 | −27.8% |
| | Doug | 7 | 2 | 6 (86%) | 10/21 | −15.7% |
| **1.3.2** (10/22–10/23) | Model | 17 | 1 | 6 (35%) | 22/51 | −84.7% |
| | Don | 17 | 4 | 10 (59%) | 25/51 | −35.3% |
| | Doug | 15 | 4 | 11 (73%) | 22/45 | −30.7% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.8% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (8 cards) | Model | 69 | 18 | 35 (51%) | 99/207 | −15.9% |
| | Don | 60 | 19 | 36 (60%) | 92/180 | −9.5% |
| | Doug | 23 | 7 | 14 (61%) | 32/69 | −13.5% |

* The model's meet $2 win line ($116.00 on $138) matches the ticket replay.
* `model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
  scratches excluded): top pick ITM 6/16 = 37.5%, win 1/16; show ROI −51.2%.
  Too thin to alert on.
* For reference, base-only (no reranker) over the meet: 18 W, 37/69 ITM,
  $2 win +11.2%. All of the base-vs-reranked gap in $2 win is from the 1.3.0
  cards; on 1.3.1 and 1.3.2 the two lines are identical.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R8 #8 Kenmore West (ML 7-2) | | 2nd at 1.5-1 (fav) | — | — |
| EP4 (R2–R5) | 1-3-6-7 / ALL / 3 / 4-8 (64 combos) | $32 | **HIT** | 4/4 | **3-4-1/3-1/8 paid 141.00** |
| LP4 (R6–R9) | 5-7-8-9 / 5-7-10 / 3-8-9 / 5-6 (72 combos) | $36 | miss | 3/4 | 7/9/11/12-10-9-9 paid 442.10 |

* The EP4 hit through a scratch: Don's only R4 horse, #3 D'busker, was a vet
  scratch. The payout row's R4 leg is `1/3`, so #3 took the post-time
  favourite, #1 Stephanie's Maria, who won. The winning combo was 3-4-3-8,
  $141.00 back on $32.
* The LP4 went out in R9 to Quick Sand (#9, 7.8-1). Don had #9 as his alt
  there, but not on the ticket.
* Don's day: $68 wagered, $141.00 back (+$73).

### Doug's bets (`tracking/doug_bets.csv`)

| R | bet | ticket | cost | result |
|---|---|---|---|---|
| 1 | superfecta wheel, $0.10 | 1-3-6 / 1-3-6 / 1-3-6 / ALL (1-7) | $2.40 | lost (1-3-7-5) |
| 2 | superfecta part wheel, $0.10 | 3-6 / 3-6 / 1-2 / ALL (1-7) | $1.60 | lost (3-6-7-1) |

Card total: $4.00 wagered, $0 returned. These are Doug's only 10/23 bets, and
they qualify him for the PP rebate ($3.85).

* Both missed on the 3rd-place horse. R1: Zarlana (#7, 27.3-1) ran 3rd;
  Doug's own picks had #7 3rd but the wheel used 1-3-6. R2: Skenes Crews
  (#7, 2.1-1) ran 3rd; Doug's picks had #7 2nd, but the ticket's 3rd leg was
  1-2. With #7 in the third leg, R2 would have paid $7.38 per $0.10.

## Watch list

No starters for T Rylee Magnon, Discerner or Cincy's Player. (R4 winner
Stephanie's Maria is trained by Derrick Ward, not Ronnie P. Ward; not counted.)

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 2 | #2 Imma Deal | T Ward | 5 of 7 | 29.5 | 5th | 10.4 |
| 4 | #8 Fret No More | J D. Magnon | 5 of 9 | 25.6 | 7th | 12.8 |
| 5 | #6 Maximum Truth | T Calhoun | 6 of 7 | 29.2 (44% cov) | **2nd** | 3.3 |
| 5 | #5 Twisted Zydeco | T Calhoun | 2 of 7 | 40.1 (48% cov) | 7th | 5.1 |
| 7 | #4 The Girlin Red | T Calhoun | **2 of 10** | 35.0 | 9th | 12.1 |
| 8 | #8 Kenmore West | T Calhoun | **4 of 9** | 35.5 | **2nd** | 1.5 (fav) |
| 9 | #2 Lassie Bee | T Ward | 2 of 10 | 41.1 | 8th | 7.1 |

**Calhoun vs model:** 4 starters, summed P(ITM) 1.40, 2 ITM (+0.60).
* R7 #4 The Girlin Red: the model's #2 at 35.0%, "showed little", 9th at
  12-1. Model too high.
* R8 #8 Kenmore West (Don's POD): the model's #4 at 35.5% (base 30.1%, 6th;
  the reranker lifted him), 2nd at 1.5-1. Model too low; the crowd had him
  as the clear favourite.
* Those two together: 0.70 expected, 1 ITM.

Meet tally after 10/23 (`watch_people_tally.csv`; logged record runs only,
pooled across 1.3.0, 1.3.1 and 1.3.2):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 18 | 2 | 8 | 5.85 | 8 | +2.15 |
| J Devin H. Magnon | 15 | 4 | 5 | 4.89 | 5 | +0.11 |
| T Rylee Magnon | 4 | 1 | 1 | 1.66 | 1 | −0.66 |
| T W.B. Calhoun | 14 | 3 | 8 | 4.61 | 8 | +3.39 |

Calhoun is now the biggest gap on the list (+3.39 ITM over the model on 14
starts, 8 ITM). Ward went 0-for-2 tonight (+2.86 → +2.15). Still small samples.
