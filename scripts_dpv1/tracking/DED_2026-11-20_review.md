# DED 2026-11-20 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Seventeenth
card on 1.3.2, **tenth with name matching ON** (the 11/19 review said tenth;
it was the ninth). One logged run, the record: `generated_at =
2026-11-20T06:34:57`, pre-race, bridged, 79 rows (full fields), commit
`b0defbc` (`picks/DED_2026-11-20_20261120-0634.*`). Side-by-side after the
build: clean, **streak 5 of 14**.

Read-only on the live model: no changes to 1.3.2, the rerankers or the
Piece 1–4 code.

## Pre-race

* **Model:** logged 06:34 CST. **No reranker #1 changes** (base #1 = final
  #1 in all 9 races). High-confidence qualifiers R1, R6, R7, R8 written to
  `high_conf_top1.csv` pre-race.
* **Don:** picks, POD, EP4 and LP4 posted on X the morning of 11/20, before
  post.
* **Doug:** did not handicap R1–R4 (logged `MISSING`, skipped). R5–R9 sent
  **6:21 PM CST; R5 went off at 6:43** on the chart, so all five are valid.
* **Consensus: none.** No race had the same post-scratch #1 for all three
  (R5 was model #7 / Doug #7 / Don #6).
* **Scratches (from the chart):** R2 #2 Tough Love Torres (vet) and #9
  Welcometomyholiday (re-entered), R6 #6 Flashy Lover (vet), R7 #11 Parole
  Drama and #12 Saucer Eyes (also-eligibles), R9 #11 Our Indian Girl
  (also-eligible). Six in all; they match Doug's list (R9 #11 is the extra
  AE). None was a model top-4 horse after the build; R2 #2 and #9 were the
  model's full-field 3rd and 4th and Don's 4th and 3rd; R6 #6 was Don's 2nd.
* **Late jockey changes** (every chart rider compared with
  `pp_entries_raw.pp_jockey`; Nava-Marin's hyphen is the same rider): **one,
  R8 #2 Classy'n Connected, Juan P. Vargas → Alex Birzer** (Vargas's only PP
  mount). The chart gives no reason. Harry Hernandez rode all four of his PP
  mounts (R5, R7, R8, R9: two wins).

## Load (2026-11-20, night)

* `load_chart.py` on `Delta Downs/ded-results-2026/DED112026USA.pdf`:
  `backup verified: racing_full.db.pre-ded1120res.bak`, `+9r 73e (purged 79
  first) [replaced a pre-race card]`, `"errors": 0`, `loaded: DED 2026-11-20
  9 races, 73 entries, 72 with a finish; replaced a pre-race card of 79
  entries`. 79 − 73 = the 6 scratches.
* **One non-finisher:** R3 #4 Gallabye (12.0-1, model 5th of 8), "refused
  and walked off" (`DNF`, scored as a starter off the board). A stewards'
  inquiry into the start: no action.
* **First dead heat of the meet: R7, 4th, #3 Go Easy and #5 Life's Ride.**
  The parser flagged it (`dead_heat:pos=4:pgm=3`, `pgm=5`), and the DB
  stores **both with `official_finish_pos = 4`** (and `finish_pos = 4`); the
  next starter, #4 Taurean, is 6th. Both superfecta payouts are loaded as
  separate rows: **9-2-6-3 $134.32 and 9-2-6-5 $113.43** (per $0.10).
  * Scoring: neither horse was ITM, so P(ITM) scoring is unaffected (both
    count as 4th, off the board).
  * Ticket replay: `grade_ordered` checks every combo against every payout
    row, so a ticket holding either finish order is paid. Checked on the DB:
    a 9,2,6,3 box returns $134.32, a 9,2,6,5 box $113.43, a 9,2,6,3,5 box
    both ($247.75). No source's ticket had 9-2-6 on top, so nothing paid.
* **No DQs, no non-betting starters.**
* Pick payouts (per $0.50):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 3-5-5 | 81.35 |
  | Pick 3 | R2–R4 | 5-5-8 | 102.15 |
  | Pick 3 | R3–R5 | 5-8-2 | 90.40 |
  | Pick 4 (early) | R2–R5 | 5-5-8-2 | **1,042.10** |
  | Pick 5 (early) | R1–R5 | 3-5-5-8-2 | 3,580.70 |
  | Pick 3 | R4–R6 | 8-2-5 | 85.50 |
  | Pick 3 | R5–R7 | 2-5-9 | 36.75 |
  | Pick 3 | R6–R8 | 5-9-6 | 9.00 |
  | Pick 3 | R7–R9 | 9-6-10 | 17.20 |
  | Pick 4 (late) | R6–R9 | 5-9/11/12-6-10 | **75.60** |
  | Pick 5 (late) | R5–R9 | 2-5-9/11/12-6-10 | 459.05 |

  `9/11/12` = R7 also-eligibles #11 and #12 scratched (tickets on them took
  the post-time favourite, #9).
* `score_predictions.py --track DED --date 2026-11-20`: 9 races, 73 rows
  scored (2,914 total), 6 scratched, 1 DNF. **Top pick ITM 9 of 9**, WIN 2 of
  9, show ROI +35.6%.

### Late jockey changes (`tracking/late_jockey_changes.csv`)

| R | horse | PP rider → rode | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 8 | #2 Classy'n Connected | Juan P. Vargas → Alex Birzer | 2 of 6 | 66.1 | **3rd** | 4.1 |

One horse, ITM 1.

## Per race (re-ranked among horses that ran)

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2-1-3-7 | 3-2-1-7 | **2nd** | 3 of 8 (0.8-1 fav) | 3/3 | **hit** | **hit** | 2-1 miss | 5.95 |
| 2 | 10-8-1-5 | 5-3-10-4 | **3rd** (1.2) | 4 of 8 (11.2-1) | 1/3 | miss | miss (2 of 4) | 10-8 miss | 951.73 |
| 3 | 2-5-6-7 | 5-1-2-7 | **3rd** | 2 of 8 (3.3-1) | 2/3 | miss | miss (3 of 4) | 2-5 miss | 30.86 |
| 4 | 5-8-7-4 | 8-5-2-3 | **2nd** (fav) | 2 of 8 (2.3-1) | 2/3 | miss | miss (2 of 4) | **5-8 hit** | 12.54 |
| 5 | 7-1-4-2 | 2-6-7-9 | **3rd** (fav) | 4 of 9 (6.4-1) | 1/3 | miss | miss (2 of 4) | 7-1 miss | 65.49 |
| 6 | 5-3-4-2 | 5-2-7-4 | **1st** | 1 of 6 (2.7-1) | 1/3 | miss | miss (3 of 4) | 5-3 miss | 7.77 |
| 7 | 9-3-5-2 | 9-2-6-3/5 (DH) | **1st** (fav) | 1 of 10 (1.0-1) | 1/3 | miss | miss (3 of 4) | 9-3 miss | 134.32 / 113.43 |
| 8 | 3-2-6-5 | 6-3-2-1 | **2nd** | 3 of 6 (1.1-1 fav) | 3/3 | **hit** | miss (3 of 4) | 3-2 miss | 1.58 |
| 9 | 3-7-5-10 | 10-3-9-7 | **2nd** (fav) | 4 of 10 (4.2-1) | 1/3 | miss | miss (3 of 4) | 3-7 miss | 12.38 |

**Model:** #1 **ITM in all 9 races** (the first 1.3.2 card with every #1 in the money), but
it **won only 2** (R6, R7). $2 win on the #1: $11.40 on $18 (**−36.7%**).
Top-3 overlap 15 of 27. Top three hit the **R1 trifecta ($5.95) and R8
trifecta ($3.40)** and both top-3 wheels ($5.95 + $1.58 for $0.10); top four
the **R1 superfecta box ($5.95)**; top two the **R4 exacta ($9.00)**. Low
payouts: the board was mostly favourites and second choices.

* **Five #1s ran 2nd or 3rd behind a horse the model ranked 2nd–4th.**
  R1 (#3 After Party, 0.8-1, model 3rd), R4 (#8 Eligio, model 2nd, 0.1pp
  behind), R8 (#6 Lady Orient, model 3rd; SAR shipper, last race missing),
  R3 (#5 Gary P, model 2nd), R9 (#10 Be Back Again, model 4th).
* **R2:** the #1 #10 Millie's Stardust (1.2-1) ran 3rd; #5 Tarkington Sunrise
  (11.2-1, model 4th of 8) went wire to wire and #3 True Chief (28.6-1,
  model 7th) rallied for 2nd: $951.73 superfecta, $1,042.10 early Pick 4.
* **R5 (maiden special weight, 5 first-time starters):** #1 Kipster (2.1-1
  fav) 3rd; first-time starter #2 Faith and Credit (6.4-1, model 4th, cov
  53%) won.
* Favourites: 3 of 9 won (R1, R7, R8); the favourite was off the board in
  R2 (6th), R3 (4th), R6 (5th, Don's POD).
* **Card log loss 0.5486 per starter (Brier 0.184), the second best of the
  ten name-matching-ON cards** (11/12 was 0.5275).

### Reranker

**No #1 changes tonight**, so `reranker_changes.csv` has no rows for 11/20.
**Reranker review rule: still 15 of 40** (reranked #1 3 W / 9 ITM, base
#1 3 W / 6 ITM).

Card log loss **0.5545 (base) → 0.5486 (reranked) per starter**: better in
R1, R4, R5, R7, R8, R9; worse in R2, R3, R6.

**But the reranker cost top-3 overlap tonight: 15 reranked vs 19 base-only.**
It changed the 3rd pick in seven races. Base-only would have had the winner
or a placer in its top three in R2 (#5, won), R5 (#2, won), R6 (#2, 2nd), R7
(#2, 2nd) and R9 (#10, won); the reranked 3rd was better only in R1 (#3
After Party, won). R4 was a wash.

| R | top 3 reranked | top 3 base-only | actual top 3 | better |
|---|---|---|---|---|
| 1 | 2-1-**3** | 2-1-7 | 3-2-1 | reranked |
| 2 | 10-8-1 | 10-8-**5** | 5-3-10 | base |
| 4 | 5-8-7 | 5-8-4 | 8-5-2 | same |
| 5 | 7-1-4 | 7-1-**2** | 2-6-7 | base |
| 6 | 5-3-4 | 5-3-**2** | 5-2-7 | base |
| 7 | 9-3-5 | 9-3-**2** | 9-2-6 | base |
| 9 | 3-7-5 | 3-7-**10** | 10-3-9 | base |

Moves of more than 5pp (all up; none down by more than 5pp):

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 2 | #7 Cranky Sheila | 17.7 → 25.2 (+7.5) | 6 → 5 | 8th (41.0-1) |
| 3 | #4 Gallabye | 34.8 → 41.6 (+6.9) | 5 → 5 | DNF (refused) |
| 4 | #8 Eligio | 48.1 → 57.5 (+9.4) | 2 → 2 | **1st** (2.3-1) |
| 4 | #7 Ongoing Challenge | 36.4 → 44.4 (+8.1) | 4 → 3 | 5th (8.4-1) |
| 7 | #9 Seeking Aces | 50.2 → 60.5 (+10.3) | 1 → 1 | **1st** (1.0-1) |
| 7 | #5 Life's Ride | 29.3 → 36.4 (+7.2) | 4 → 3 | 4th, dead heat (11.2-1) |
| 8 | #6 Lady Orient | 55.2 → 61.4 (+6.2) | 3 → 3 | **1st** (1.1-1) |
| 9 | #5 Educated Wish | 26.3 → 35.6 (+9.3) | 5 → 3 | 7th (33.3-1) |

3 of 8 went the right way (Eligio, Seeking Aces, Lady Orient). Ongoing
Challenge, Life's Ride and Educated Wish were each lifted into the top three
and missed the board.

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 11/20 | 9 | 0 | 2 / 9 / $11.40 (−36.7%) | 2 / 9 / $11.40 (−36.7%) |
| 1.3.2 (10/22–11/20) | 145 | 25 | 37 / 97 / $201.20 (−30.6%) | 38 / 94 / $209.80 (−27.7%) |
| **Meet** | 197 | 30 | 54 / 126 / $312.00 (−20.8%) | 55 / 125 / $358.00 (−9.1%) |

`model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
scratches excluded): **with-reranker 92/135 vs base-only 89/135** (+3, as
before). Top pick ITM 68.1%, win 25.9%; show ROI −8.3%. **Alert:** "top pick
ITM over last 29 races is 79.3%, above the 68% ceiling" (the same hot-run
check as 11/05–11/19; these are out-of-sample logged runs, so a hot run,
not leakage).

## High-confidence #1 forward test (`tracking/high_conf_top1.csv`)

Four qualifiers, all logged pre-race:

| R | horse | P(ITM) | ML | final odds | finished | $2 win | $2 place |
|---|---|---|---|---|---|---|---|
| 1 | #2 Cause I'm Rollin | 62.1 | 9/2 | 2.8 | **2nd** | – | 3.40 |
| 6 | #5 Time to Tell | 62.9 | 8/1 | 2.7 | **1st** | 7.40 | 5.20 |
| 7 | #9 Seeking Aces | 60.5 | 7/2 | 1.0 (fav) | **1st** | 4.00 | 2.60 |
| 8 | #3 Jewlz | 75.2 | 7/2 | 1.7 | **2nd** | – | 2.80 |

All four ran 1st or 2nd. None over 4-1 on final odds (the registered
subset). On the morning line (reference only), R1 (9/2) and R6 (8/1) were
over 4-1: one 2nd, one win.

**25 of 40** qualifying races so far: **10 W, 18 ITM, 17 in the first
two**. Expected ITM from the logged P(ITM): 16.56 (13.95 + 2.61 tonight).
$2 win $47.60 on $50 (−4.8%), $2 place $57.90 on $50 (+15.8%). Over-4-1
subset (final odds): still 3 races. Pass mark: open until Doug picks
(PHASE_6D_ROADMAP), before race 40; 15 races left.

## Name matching ON: 11/05–11/20 vs the earlier 1.3.2 cards

Same basis as before (record run, among starters, logged P(ITM) not
renormalised; #1 re-ranked among runners; DNFs count as starters that
missed the board).

| card | name matching | races | starters | #1 W | #1 ITM | sum P(ITM) | ITM | P(ITM) LL | Brier | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.3.2 off (7 cards, 10/22–11/04) | off | 59 | 505 | 12 | 32 (54%) | 158.82 | 177 | 0.609 | 0.210 | $67.80 (−42.5%) |
| **11/20** | **on** | 9 | 73 | 2 | 9 | 25.59 | 27 | **0.5486** | **0.184** | $11.40 |
| 1.3.2 on (10 cards, 11/05–11/20) | on | 86 | 698 | 25 | 65 (76%) | 239.12 | 258 | **0.5954** | **0.205** | $133.40 (−22.4%) |

ON is now further below OFF on log loss (0.5954 vs 0.609) and Brier. The
read-only paired OFF/ON check from the `-run.bak` files still decides it.

## Data issues on the model's top picks (`tracking/top_pick_data_issues.csv`)

None. All nine post-scratch #1s had their last race in the DB (PP days off =
DB days, 16–35) and jockey and trainer history. R5 #7 Kipster was one of
four starters with DB history in a 9-horse maiden (race coverage 69%).

## Missing-last-race horses (`missing_last_race_tally.py --to 2026-11-20`)

Six flagged starters, **all no-data tracks** (LS counts as no-data: no LS
charts in the DB):

| R | horse | last race | model rank | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 2 | #4 Railey Jean | HCN 8/08 | 6 of 8 | 18.3 | 4th | 76.2 |
| 6 | #1 My Golden M | GIL 8/30 | 6 of 6 | 15.9 | 6th | 43.1 |
| 6 | #4 Three Echoes | SWF 9/19 | 3 of 6 | 51.5 | 4th | 13.5 |
| 6 | #7 Bettys Cash | SWF 8/21 (no DB history) | 5 of 6 | 37.8 | **3rd** | 2.9 |
| 8 | #4 Paintbrush | LS 7/12 | 6 of 6 | 10.2 | 6th | 57.9 |
| 8 | #6 Lady Orient | SAR 8/02 | 3 of 6 | 61.4 | **1st** | 1.1 (fav) |

Tonight: **no-data tracks 6 starters, ITM 2 vs 2.0 expected, W 1 vs 0.6**;
data tracks 0.

| group (11/04–11/20) | starters | ITM | exp ITM | W | exp W |
|---|---|---|---|---|---|
| data tracks | 21 | 7 | 6.5 | 1 | 2.1 |
| no-data tracks | 48 | **22** | **15.0** | 4 | 4.8 |
| both | 69 | 29 | 21.5 | 5 | 7.0 |
| all other starters | 698 | 253 | 239.3 | 89 | 80.1 |

Tonight the no-data group ran to its P(ITM) again (the second card in a
row). Over the stretch it still beats it (22 vs 15.0). The data-track group
is on expectation.

## First-time starters

| R | first-time starters | finishes | model ranks | winner |
|---|---|---|---|---|
| 5 (MSW 35000) | #1 Anchors Away, #2 Faith and Credit, #3 Tuition Man, #8 Vinny Vee, #9 Salty Strike | 5th (3.1-1), **1st (6.4-1)**, 6th (27.9-1), 7th (67.3-1), 4th (6.8-1) | 2nd, 4th, 6th, 9th, 8th of 9 | **#2 Faith and Credit (first-timer)** |

Tally: **14 maidens with first-time starters, a first-time starter won 5**
(R5 added). R3 (MCL 18000) had none (every starter 2–10 career starts).

## Low-coverage (<65%) horses

R5's five first-time starters (52–53%): #2 Faith and Credit **1st**, #9 Salty
Strike 4th, #1 Anchors Away 5th (the model's 2nd), #3 Tuition Man 6th, #8
Vinny Vee 7th.

## Benchmarks: Don and Doug

* Don lost R2 #9 and #2 (his 3rd and 4th) and R6 #6 (his 2nd) to scratches.
* Doug has R5–R9 only (R1–R4 not handicapped).
* The model's #1 = Don's #1 in R1, R4 and R9; = Doug's #1 in R5.

| R | Don | Don #1 fin | Don ov | Doug | Doug #1 fin | Doug ov | model | model #1 fin | model ov |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2-3-6-8 | **2nd** | 2/3 | – | – | – | 2-1-3-7 | **2nd** | 3/3 |
| 2 | 8-10 | 6th | 1/3 | – | – | – | 10-8-1-5 | **3rd** | 1/3 |
| 3 | 7-2-5-3 | 4th | 2/3 | – | – | – | 2-5-6-7 | **3rd** | 2/3 |
| 4 | 5-4-7-8 | **2nd** | 1/3 | – | – | – | 5-8-7-4 | **2nd** | 2/3 |
| 5 | 6-1-7-2 | **2nd** | 2/3 | 7-1-5-6 | **3rd** | 1/3 | 7-1-4-2 | **3rd** | 1/3 |
| 6 | 3-7-5 | 5th | 2/3 | 4-7-2-5 | 4th | 2/3 | 5-3-4-2 | **1st** | 1/3 |
| 7 | 3-9-10-8 | 4th (DH) | 1/3 | 5-3-9-8 | 4th (DH) | 1/3 | 9-3-5-2 | **1st** | 1/3 |
| 8 | 6-3-2-5 | **1st** | 3/3 | 6-2-5-3 | **1st** | 2/3 | 3-2-6-5 | **2nd** | 3/3 |
| 9 | 3-9-10-7 | **2nd** | 3/3 | 10-7-3-5 | **1st** | 2/3 | 3-7-5-10 | **2nd** | 1/3 |

| | races | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|
| Model | 9 | 2 | **9** | 15/27 | 2 (R1 $5.95, R8 $1.58) | 1 (R1 $5.95) | 1 (R4 $9.00) | $11.40 on $18 (−36.7%) |
| Don | 9 | 1 | 5 | **17/27** | 2 (R8 $1.58, R9 $12.38) | 1 (R9 $12.38) | 2 (R1 $4.00, R8 $3.80) | $4.20 on $18 (−76.7%) |
| Doug | 5 | **2** | 3 | 8/15 | 0 | 1 (R6 $7.77) | 0 | **$14.60 on $10 (+46.0%)** |

Don's top three also hit the R8 and R9 trifectas ($3.40, $24.60); the
model's the R1 and R8 trifectas ($5.95, $3.40).

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **11/05–11/20** (name matching ON) | Model | 86 | 25 | 65 (76%) | 146/258 | −22.4% |
| | Don | 86 | 24 | 53 (62%) | 148/258 | −13.3% |
| | Doug | 74 | 20 | 42 (57%) | 112/222 | −19.9% |
| **1.3.2** (10/22–11/20) | Model | 145 | 37 | 97 (67%) | 236/435 | −30.6% |
| | Don | 145 | 43 | 89 (61%) | 248/435 | −13.6% |
| | Doug | 131 | 39 | 78 (60%) | 202/393 | −16.2% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.7% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (23 cards) | Model | 197 | 54 | 126 (64%) | 313/591 | −20.8% |
| | Don | 188 | 58 | 115 (61%) | 315/564 | −10.3% |
| | Doug | 139 | 42 | 81 (58%) | 212/417 | −14.2% |
| | Doug, without best guesses | 136 | 40 | 79 (58%) | 206/408 | −17.4% |

The meet $2 win lines ($312.00 model, $337.20 Don, $238.60 Doug) match the
ticket replay (re-run 11/20 night with the 11/20 card: 34 rows added, all
669 earlier rows unchanged).

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result |
|---|---|---|---|
| POD | R6 #3 Sir Tristan (ML 5/1) | – | lost: **5th** at 1.9-1 (fav), "pressed the early pace, made a bid at the 3/8 pole and faded" |
| EP4 R2–R5 | 8,9,10 / 2,5,7 / 4,5,7 / 1,6,7 (81 × $0.50) | $40.50 | lost in R2 (#5 Tarkington Sunrise, 11.2-1); R4 and R5 legs also missed |
| LP4 R6–R9 | 3,5,6,7 / 3,9 / 6 / 3,7,9,10 (32 × $0.50) | $16 | **HIT** 5-9-6-10: **$75.60** |

$56.50 on the two Pick 4s, **$75.60 back** (+33.8%). R2 #9 (on the EP4) and
R6 #6 (on the LP4) were scratched; the post-time favourite substitutes (#8
Stormy Lou, #3 Sir Tristan) were already on his tickets. His R8 single, #6
Lady Orient, won.

### Doug's bets (`tracking/doug_bets.csv`)

| R | bet | ticket | cost | result |
|---|---|---|---|---|
| 5 | $1 exacta box (placed 6:41 PM) | 1,7 | $2.00 | lost (2-6-7-9) |
| 6 | $0.10 superfecta box | 2,4,5,7 (24 combos) | $2.40 | **won** 5-2-7-4: **$7.74** (+$5.34) |
| 8 | $0.10 superfecta part-wheel | 2,6 / 2,6 / ALL / ALL (24 combos) | $2.40 | lost (6-3-2-1) |
| 9 | $2 win | #10 Be Back Again | $2.00 | **won**: $10.40 chart + $1.06 boost = **$11.46** (+$9.46) |

Night: **$8.80 wagered, $19.20 returned, +$10.40.** DED 11/20 wagering
$8.80: **qualifies for the 11/20 PP rebate.**

Two small differences from the chart, logged as reported:

* R6: the chart pays **$7.77** per $0.10; TwinSpires returned **$7.74**.
* R9: the 15% profit boost token paid **$1.06**. 15% of the $8.40 profit
  would be $1.26. The bankroll uses what TwinSpires paid.

**Bankroll** (`tracking/bankroll.csv`): from $62.51 after the 11/19
rebate: −3.85 (11/20 PP, 6:13 AM) = $58.66; −2.00 (R5), −2.40 + 7.74 (R6),
−2.40 (R8), −2.00 + 10.40 (R9 chart win) + 1.06 (R9 boost, its own row) =
**$69.06 = TwinSpires**. The 11/20 rebate (+$3.85) is logged when it lands.

## Watch list

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 5 | #2 Faith and Credit | T W.B. Calhoun | 4 of 9 | 37.0 | **1st** ($14.80) | 6.4 |
| 7 | #10 Native Requite | T Ronnie P. Ward | 6 of 10 | 18.2 | 9th | 31.4 |

No watch-list horses on the card; Devin Magnon and Rylee Magnon had no
mounts or starters. Meet tally after 11/20 (`watch_people_tally.csv`;
logged record runs only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 43 (+1) | 4 | 17 | 13.71 | 17 | +3.29 |
| J Devin H. Magnon | 34 | 4 | 10 | 10.83 | 10 | −0.83 |
| T Rylee Magnon | 11 | 1 | 2 | 3.67 | 2 | −1.67 |
| T W.B. Calhoun | 20 (+1) | 5 | 10 | 6.61 | 10 | **+3.39** |

Calhoun's first-time starter won at 6.4-1: his meet line is now 5 W / 10
ITM of 20 against 6.61 expected (+27.5% $2 win ROI).

## Stablemate entries (`stablemate_tally.py`)

| R | trainer | runners (ML → final, finish) | backed one ahead? |
|---|---|---|---|
| 5 | Chasey Pomier | #5 Heartofa Hero (5/1 → 15.4, 9th); #3 Tuition Man (15/1 → 27.9, 6th) | **no** |
| 6 | Mark Hibdon | #7 Bettys Cash (9/5 → 2.9, **3rd**); #4 Three Echoes (5/1 → 13.5, 4th) | yes |

Doug listed R6 (Hibdon). The tally also found R5 (Pomier).

**Meet (10/09–11/20): 106 races with a trainer running two or more.** In
the 104 with different final odds, **the more heavily backed stablemate
finished ahead in 69 (66%)**, against **68%** for any two runners in the same
race (4,621 of 6,781). Backed ones 23 W / 51 ITM of 104 ($2 win $201.00 on
$208); others 7 W / 23 ITM ($304.80 on $208). Still no sign of a stable
edge either way.

## Things that look off

1. **First dead heat of the meet (R7, 4th).** Stored and graded correctly
   (see Load). Nothing to fix.
2. **The reranker cost four top-3 overlaps tonight** (15 vs 19 base-only)
   while leaving every #1 alone. Its 3rd-pick lifts (Ongoing Challenge,
   Life's Ride, Educated Wish) all missed the board. One card; the reranker
   rule is judged on #1 ITM and log loss at 40 races, and the card log loss
   was better with it.
3. **TwinSpires paid 3 cents under the chart on the R6 superfecta** ($7.74
   vs $7.77), and the R9 boost was $1.06, not 15% of the profit ($1.26).
   Both logged as reported; Doug may want to check the boost terms.
4. The 11/19 review and replay note called 11/19 the "tenth" name-matching
   card; it was the ninth (corrected here and in the replay note).
5. The `-run.bak.partial` from 11/18 (`scripts/racing_full.db.ded1110-run.bak.partial`)
   is still on disk, waiting on Doug.

## Queued (not started)

* Read-only paired name-matching OFF/ON check, now on 11/05–11/20, from the
  `-run.bak` files.
* PP-date recency fix (top of the queue; needs the OFF/ON validation first).
* First-time-starter maiden check (14 maidens with first-time starters; a
  first-time starter won 5).
* High-confidence pass mark (A/B/C) before race 40 (25 graded).
* MNR 10/05 chart: retry after 11/21. MNR 11/08–11/11 charts are on disk
  (chart archive) and held: live-DB gaps, not loaded.
