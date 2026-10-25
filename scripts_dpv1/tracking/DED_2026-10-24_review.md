# DED 2026-10-24 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Third card
on 1.3.2. One logged run, the record: `generated_at = 2026-10-23T22:30:26`,
pre-race (the night before), bridged, 79 rows, commit `fe4d7da`
(`picks/DED_2026-10-24_20261023-2230.*`).

## Load (2026-10-24 evening)

* Chart `Delta Downs/ded-results-2026/DED102426USA.pdf`, read with the
  standard chart parser (pdfplumber, the only text path; no fallback).
  9 races, 71 starters, 47 exotic rows. The 79-entry pre-race card was
  purged first. 0 errors, 0 parser warnings.
* DB backup: `scripts/racing_full.db.pre-ded1024res.bak`, verified: same
  sha256 as the live DB (`22d82bf0…0883f`), `integrity_check` ok on both,
  and the same row counts in six tables.
* Spot checks: R1 official 4-1-5-2 and R9 5-3-6-10, as expected. R4 $1
  exacta 5-10 $22.20, $0.50 trifecta $292.90, $0.10 superfecta $314.27; R5
  $0.50 Pick 4 5-2-5-5 $432.40 and Pick 5 4-5-2-5-5 $1,128.60: all match the
  chart.
* **No dead heats, no DQs** (crossing order = `official_finish_pos` in all 9
  races), **no non-betting starters**.
* **Two DNFs in R3:** #7 My Priorities (the model's #1) "was moving up
  around the turn, fell, lost rider and was transported by equine
  ambulance"; #8 Papermaker "fell over downed rival and walked off". Both
  were betting interests (5.8-1 and 27.9-1), so they count as starters that
  lost. Stewards' inquiry, no change.
* 8 logged horses scratched (5 vet, 2 also-eligibles that did not draw in,
  1 gate). Three of them were the model's #1 or #2:

  | R | horse | reason | logged rank | P(ITM) |
  |---|---|---|---|---|
  | 1 | #3 Cajun Catalina | vet | 4 of 6 | 46.9 |
  | 2 | #1 Run Bambi Run | vet | 7 of 7 | 29.9 |
  | 6 | #12 Clearly Majestic | AE | **1 of 12** | 47.9 |
  | 6 | #11 Runforjustice | AE | **2 of 12** | 39.2 |
  | 7 | #1 Sir Tristan | vet | **1 of 10** | 61.2 |
  | 7 | #5 Cajun Cyclone | vet | 10 of 10 | 10.0 |
  | 9 | #8 Miss T | gate | 5 of 10 | 27.9 |
  | 9 | #1 Peppermint Stripe | vet | 6 of 10 | 26.4 |

  Doug's list (R6 #11 and #12, R7 #1 and #5) is confirmed. The chart also
  scratches R1 #3, R2 #1, and R9 #8 and #1.
* Pick payouts, all parsed (per $0.50):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 4-5-2 | 79.20 |
  | Pick 3 | R2–R4 | 5-2-5 | 82.45 |
  | Pick 3 | R3–R5 | 2-5-5 | 40.45 |
  | Pick 3 | R4–R6 | 5-5-4 | 34.80 |
  | Pick 3 | R5–R7 | 5-4-3 | 28.80 |
  | Pick 3 | R6–R8 | 4-3-5 | 46.10 |
  | Pick 3 | R7–R9 | 3-5-5 | 97.60 |
  | Pick 4 (early) | R2–R5 | 5-2-5-5 | 432.40 |
  | Pick 5 (early) | R1–R5 | 4-5-2-5-5 | 1,128.60 |
  | Pick 4 (late) | R6–R9 | 4/11/12-3-5-5 | 352.90 |
  | Pick 5 (late) | R5–R9 | 5-4/11/12-3-5-5 | 1,332.30 |

  The `/` legs are scratch substitutes: in R6, #11 and #12 count as #4 (the
  post-time favourite, who won). R7's scratches (#1, #5) went to the
  favourite #10 Storm Sniper, who ran 3rd, so no R7 `/` appears. The chart
  prints the R4–R6 Pick 3 as plain 5-5-4 (no substitute); the parse matches
  the chart. The R9 Consolation Pick 3 (3-5-8, $19.05) is not parsed, which
  is a known gap (Consolation rows were never added).
* `score_predictions.py --track DED --date 2026-10-24`, official figures:
  * The logged top pick was ITM in 5 of 7 and won 1 of 7. R6 and R7 top
    picks were scratched; R3's top pick (DNF) counts as a loss.
  * Top-pick show ROI was −9.3% ($12.70 back on $14).
  * All horses were ITM 27 of 71.

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).
* **Exacta box:** a $1 exacta box of the model's top 2 ($2 a race).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 5-1-6-4 | 4-1-5-2 | **3rd** (fav) | 4 of 5 (3.3-1) | 2/3 | miss | miss | 5-1 miss | 12.37 |
| 2 | 3-4-5-2 | 5-3-7-2 | **2nd** | 3 of 6 (6.6-1) | 2/3 | miss | miss | 3-4 miss | 22.63 |
| 3 | 7-9-3-2 | 2-4-3-1 | fell (DNF) | 4 of 9 (1.8-1, fav) | 1/3 | miss | miss | 7-9 miss | 62.76 |
| 4 | 10-5-3-4 | 5-10-2-9 | **2nd** (fav) | 2 of 10 (6.0-1) | 2/3 | miss | miss | **5-10 HIT $22.20** | 314.27 |
| 5 | 5-1-3-9 | 5-3-1-9 | **1st** (fav) | 1 of 9 (1.3-1, fav) | 3/3 | **HIT** | **HIT** | 5-1 miss | 12.14 |
| 6 | 9-2-10-5 | 4-5-2-9 | 4th | 5 of 10 (1.9-1, fav) | 1/3 | miss | miss | 9-2 miss | 25.41 |
| 7 | 8-10-4-3 | 3-4-10-8 | 4th | 4 of 8 (3.1-1) | 2/3 | miss | **HIT** | 8-10 miss | 39.83 |
| 8 | 2-6-4-3 | 5-6-4-2 | 4th | 6 of 6 (10.5-1) | 2/3 | miss | miss | 2-6 miss | 25.00 |
| 9 | 6-10-7-2 | 5-3-6-10 | **3rd** | 7 of 8 (3.6-1) | 1/3 | miss | miss | 6-10 miss | 21.55 |

**Model:** the #1 pick won 1 race (R5 Polar Wolf, $4.60) and was ITM in 5 of
9. Top-3 overlap was 16 of 27, tied with 10/17 (16 of 30) for its most on a card. The super box hit
twice (R5 $12.14, R7 $39.83: $51.97 back on $21.60), the top-3 wheel once
(R5 $12.14, on a $3.60 ticket), and the top-two exacta box once (**R4 5-10
$22.20**, $22.20 back on $18 over the card, +23.3%).

* The #1 was close but rarely first: 2nd in R2 and R4, 3rd in R1 and R9,
  and 4th in R6, R7 and R8. The R3 #1 fell.
* The two races that lost their #1 to scratches (R6, R7) went to the
  model's 5th and 4th choices among the runners.
* R8 winner Levigata (10.5-1) was the model's last of 6 (64% coverage; the
  reranker cut her 7.4pp, below).
* R9 winner Celestial Clock (debut, gate to wire by 6¼) was 7th of 8 in an
  all-maiden field at 49% race coverage. Added to the watch list.

### Reranker

The reranker changed the #1 in **4 races**, the most of any card this meet (the previous high was 2):

* R4: base #1 #5 Crusin Likea Cat (45.4 → 41.1) dropped to 2nd; #10
  Millie's Stardust (44.8 → 44.6) became #1. Crusin Likea Cat **won** ($14.00);
  Millie's Stardust ran 2nd. Lost a win, ITM unchanged. The base top 2 (5-10)
  also hit the exacta.
* R5: #5 Polar Wolf +14.3 (61.2 → 75.5) passed #1 Not Behavin. Polar Wolf
  **won**; Not Behavin ran 3rd. Gained a win, and made the top-3 wheel and
  the super box (base top 4 was 1-5-6-9: #6 ran 5th).
* R6: #9 Our Majestic +6.5 passed #2 Robbiesstormangel. Our Majestic ran 4th,
  Robbiesstormangel 3rd. Lost an ITM.
* R8: #2 La Foret +15.2 (43.7 → 58.9) went from 6th to 1st, and #3 Kaydences
  Calamity −9.6 from 1st to 4th. La Foret ran 4th, Kaydences Calamity 5th.
  #5 Levigata −7.4 (4th → 6th) won at 10.5-1.

Net on the card: #1 wins 1 vs 1 (base R4 won at $14.00, reranked R5 won at
$4.60), #1 ITM 5 vs 6 (−1), overlap 16 vs 15 (+1), super box 2 vs 1 (+1),
top-3 wheel 1 vs 0 (+1). The $2 win line was $4.60 reranked vs $14.00 base.

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 3 | #1 Atta Boy Peter Roy | 33.4 → 28.1 (−5.3) | 7 → 8 | 4th (8.9-1) |
| 4 | #9 Give Em Hail Gayle | 26.7 → 34.1 (+7.3) | 7 → 5 | 4th (8.3-1) |
| 5 | #5 Polar Wolf | 61.2 → 75.5 (+14.3) | 2 → 1 | **1st** |
| 5 | #1 Not Behavin | 63.3 → 70.8 (+7.5) | 1 → 2 | **3rd** |
| 5 | #6 Graceful Standard | 35.6 → 29.3 (−6.4) | 3 → 5 | 5th |
| 5 | #2 Waiting On Lon | 24.9 → 15.3 (−9.6) | 6 → 8 | 9th |
| 6 | #9 Our Majestic | 30.9 → 37.5 (+6.5) | 2 → 1 | 4th |
| 7 | #2 Lil Sweet Thang | 20.7 → 26.0 (+5.3) | 6 → 5 | 7th |
| 8 | #2 La Foret | 43.7 → 58.9 (+15.2) | 6 → 1 | 4th |
| 8 | #3 Kaydences Calamity | 57.7 → 48.2 (−9.6) | 1 → 4 | 5th |
| 8 | #5 Levigata | 49.6 → 42.1 (−7.4) | 4 → 6 | **1st** (10.5-1) |

### Stretch feature (1.3.2 vs 1.3.1)

Not run, for the same reason as 10/23: the pre-race card has been replaced
by the results card, and this pass is read-only.

## Low-coverage (<65%) horses

22 of 71 starters were below 65% coverage: R3 8 of 9 and R9 8 of 8 (the
all-maiden, mostly first-time-starter fields), R5 3, R2 1, R4 1, R8 1. Their
summed P(ITM) was 6.89, and 7 finished in the money:
* R3 #2 Lucky Spot (1st, fav), #4 Unosailor (2nd, 14.9-1) and #3 Parole
  Pass (3rd);
* R8 #5 Levigata (1st, 10.5-1; 64%);
* R9 #5 Celestial Clock (1st), #3 Lets Getthe Muney (2nd) and #6 Epic Stolen
  Kiss (3rd).

In the two all-low-coverage races the model's #1 fell (R3) and ran 3rd (R9).

## Benchmarks: Don and Doug

Re-ranked around scratches as before (Don's alt moves up; Doug has no alt).

* Don, R1: #3 scratched, alt #2 moves up. R6: #12 scratched, alt #8 moves
  up. R7: #1 scratched, alt #3 moves up. R9: his alt #1 scratched (not
  needed).
* Doug, R1: **#3 Cajun Catalina (his 3rd pick) was a vet scratch**, so he
  has 3 picks there (5-4-1). Doug passed no races (`pass_flag = 0` for all 9).
* **Best guesses:** Doug's R3, R5 and R9 picks were best guesses in maiden
  races, from breeding and jockey. `doug_picks.csv` has a new `best_guess`
  column (1 for those three, 0 for every other row).

Doug's picks were made on race day with scratches and odds known.

| R | Don (re-ranked) | Don #1 fin | Don overlap | Doug (re-ranked) | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 5-4-6-2 | **3rd** | 2/3 | 5-4-1 | **3rd** | 3/3 | **3rd** | 2/3 |
| 2 | 4-2-5-7 | 5th | 1/3 | 2-7-6-3 | 4th | 1/3 | **2nd** | 2/3 |
| 3 | 6-2-1-7 | 5th | 1/3 | 7-2-6-8 *(bg)* | fell | 1/3 | fell | 1/3 |
| 4 | 3-10-5-8 | 6th | 2/3 | 4-5-10-8 | 7th | 2/3 | **2nd** | 2/3 |
| 5 | 5-9-1-6 | **1st** | 2/3 | 5-9-1-3 *(bg)* | **1st** | 2/3 | **1st** | 3/3 |
| 6 | 10-4-2-8 | 7th | 2/3 | 10-5-4-2 | 7th | 2/3 | 4th | 1/3 |
| 7 | 6-4-10-3 | 6th | 2/3 | 3-6-10-7 | **1st** | 2/3 | 4th | 2/3 |
| 8 | 4-6-1-3 | **3rd** | 2/3 | 1-6-2-4 | 6th | 1/3 | 4th | 2/3 |
| 9 | 4-6-5-3 | 8th | 2/3 | 5-3-6-2 *(bg)* | **1st** | 3/3 | **3rd** | 1/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | 1 | 5/9 | 16/27 | 1 (R5, $12.14) | 2 (R5 $12.14, R7 $39.83) | 1 (R4, $22.20) | $4.60 on $18 (−74.4%) |
| Don | 1 | 3/9 | 16/27 | 0 | 0 | 0 | $4.60 on $18 (−74.4%) |
| Doug | 3 | 4/9 | 17/27 | 2 (R1 $12.37, R9 $21.55) | 1 (R5, $12.14) | 1 (R9, $19.10) | $22.00 on $18 (**+22.2%**) |
| Doug, without best guesses (6 races) | 1 | 2/6 | 11/18 | 1 (R1) | 0 | 0 | $8.20 on $12 (−31.7%) |
| Doug, best guesses only (R3, R5, R9) | 2 | 2/3 | 6/9 | 1 (R9) | 1 (R5) | 1 (R9) | $13.80 on $6 (+130.0%) |

* **Doug's R9 best guess was the exact trifecta and the top three of the
  superfecta: 5-3-6** (paid $22.70 per $0.50 trifecta; superfecta 5-3-6-10
  $21.55, his 4th pick #2 ran 5th). Two of his three wins tonight (R5 Polar
  Wolf, R9 Celestial Clock $9.20) came from the best-guess races; the third
  was R7 Daddy's Gift ($8.20), with the model's #1 Sir Tristan scratched.
* On the same three best-guess races: model #1 1 W, 2/3 ITM; Don #1 1 W,
  1/3 ITM (his R9 #1 was his POD, last).
* Don had his weakest card of the meet: #1 ITM 3/9, no exotic box hits.
* Don and the model shared #1 in 2 races: R1 Fulla Wicked Sugar (3rd, 0.8-1
  fav) and R5 Polar Wolf (won, Doug's #1 too).

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

Model rows are by the version that made the record run. Don and Doug are
split by the same dates. Doug has no picks before 10/21.

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **10/24** | Model | 9 | 1 | 5 (56%) | 16/27 | −74.4% |
| | Don | 9 | 1 | 3 (33%) | 16/27 | −74.4% |
| | Doug | 9 | 3 | 4 (44%) | 17/27 | +22.2% |
| **1.3.2** (10/22–10/24) | Model | 26 | 2 | 11 (42%) | 38/78 | −81.2% |
| | Don | 26 | 5 | 13 (50%) | 41/78 | −48.8% |
| | Doug | 24 | 7 | 15 (62%) | 39/72 | −10.8% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.8% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (9 cards) | Model | 78 | 19 | 40 (51%) | 115/234 | −22.7% |
| | Don | 69 | 20 | 39 (57%) | 108/207 | −18.0% |
| | Doug | 32 | 10 | 18 (56%) | 49/96 | −3.4% |
| | Doug, without best guesses | 29 | 8 | 16 (55%) | 43/87 | −17.2% |

* The model's meet $2 win line ($120.60 on $156) matches the ticket replay.
* `model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
  scratches excluded): top pick ITM 11/23 = 47.8%, win 2/23; show ROI
  −38.5%. **It now raises its alert** (show ROI below −25% over the window).
  26 races is still a small sample, but this is the first alert on 1.3.2.
* For reference, base-only (no reranker) over the meet: 19 W, 43/78 ITM,
  $2 win +7.3%. On 1.3.2 the base-only line is now ahead too ($19.20 vs
  $9.80 on $52), all from tonight's R4. Until tonight the two lines were
  identical on 1.3.1 and 1.3.2.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R9 #4 Rocksy Diamond (ML 8-1) | | **8th of 8** at 7.8-1 | — | — |
| EP4 (R2–R5) | 2-4-5 / 1-2-6-7 / 3-10 / 5-9 (48 combos) | $24 | miss, dead in R4 | 3/4 | 5-2-5-5 paid 432.40 |
| LP4 (R6–R9) | 2-4-10-12 / 1-6 / 1-4-6 / 4-5-6 (72 combos) | $36 | miss, dead in R7 | 2/4 (R6, R9) | 4/11/12-3-5-5 paid 352.90 |

* POD Rocksy Diamond showed brief speed (2nd early), dropped back on the
  turn and was done, last by 28½.
* EP4: R2 #5 Secured, R3 #2 Lucky Spot and R5 #5 Polar Wolf were all on
  the ticket; R4 went to #5 Crusin Likea Cat (6.0-1), and Don's R4 leg was
  3-10 (#10 ran 2nd). Don had #5 as his 3rd pick in R4 but not on the ticket.
* LP4, **scratched ticket horses:** R6 #12 Clearly Majestic (AE) took the
  favourite #4, who won, but #4 was on the ticket anyway. R7 #1 Sir Tristan
  (vet) took the favourite #10 Storm Sniper, who ran 3rd, and #6 ran 6th, so
  the ticket died in R7 (winner #3 Daddy's Gift, Don's alt). R8 (1-4-6) also
  missed: Levigata #5 won.
* Don's day: $60 wagered, $0 back.

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 5 | superfecta part wheel, $0.10 | 5 / 1,9 / 1,2,9 / ALL (1-9) | $2.40 | lost (5-3-1-9) |
| CT | 5 | exacta box, $1 | 3,9 | $2.00 | lost (7-6-3-1) |
| CT | 7 | superfecta part wheel, $0.10 | 6 / 4,7 / 2,4,6,7 / 1,2,4,5,6,7 (12 combos) | $1.20 | lost (4-1-6-5) |

Night total: $5.60 wagered, $0 returned. The DED R5 bet is the only DED bet,
and it qualifies Doug for the DED PP rebate.

* DED R5: the #2 in the third leg was a mis-tap for #3. The intended ticket
  (5 / 1,9 / 1,3,9 / ALL) also loses, because #3 Alotlikechocolate (12.4-1)
  ran **2nd**, not 3rd, and the second leg was 1,9. The model's top 4 that
  race (5-1-3-9) was the superfecta, $12.14 on a 24-combo $2.40 box.
* Both CT bets are logged with `track = CT` and are not part of the DED
  scoring or the ticket replay. The CT 10/24 chart is not on disk; they are
  graded from the finishes Doug reported.

## Watch list

No starters for Discerner or Cincy's Player.

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 3 | #1 Atta Boy Peter Roy | J D. Magnon | 8 of 9 | 28.1 (52% cov) | 4th | 8.9 |
| 4 | #9 Give Em Hail Gayle | T Ward | 5 of 10 | 34.1 | 4th | 8.3 |
| 5 | #6 Graceful Standard | T Calhoun | 5 of 9 | 29.3 | 5th | 5.6 |
| 7 | #10 Storm Sniper | T Rylee Magnon, J D. Magnon | **2 of 8** | 37.2 | **3rd** | 1.9 (fav) |
| 9 | #9 Prollydid | J D. Magnon | 8 of 8 | 23.4 (44% cov) | 7th | 35.9 |

**New on the watch list (`watch_list.csv`): R9 winner #5 Celestial Clock.**
2yo chestnut filly (Drain the Clock – Kalani, by Afleet Alex), KY-bred,
trainer Jayde Gelner, J Kevin Roman. Debut in a $35k maiden special weight
(5f dirt): "shot to the front, opened up on the field, was never challenged
and won easily", by 6¼ at 3.6-1. The model had her 7th of 8 runners (24.6%
P(ITM), 48% coverage).

Meet tally after 10/24 (`watch_people_tally.csv`; logged record runs only,
pooled across 1.3.0, 1.3.1 and 1.3.2):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 19 | 2 | 8 | 6.19 | 8 | +1.81 |
| J Devin H. Magnon | 18 | 4 | 6 | 5.78 | 6 | +0.22 |
| T Rylee Magnon | 5 | 1 | 2 | 2.03 | 2 | −0.03 |
| T W.B. Calhoun | 15 | 3 | 8 | 4.90 | 8 | +3.10 |

All five watch starters were roughly where the model put them: 1.52 summed
P(ITM), 1 ITM (Storm Sniper). Calhoun is still the biggest gap (+3.10 on 15
starts). Still small samples.
