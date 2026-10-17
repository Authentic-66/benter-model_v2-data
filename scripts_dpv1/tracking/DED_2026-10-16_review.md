# DED 2026-10-16 — card review

Model `dpv1.3.0-5track` + `pp-reranker-1.0` (Config Y). One logged run, the
record: `generated_at = 2026-10-16T15:21:44`, picks
`picks/DED_2026-10-16_20261016-1521.txt`, 99 rows, commit `c56755e`. This is
the first card logged after the #14 corpus cleanup (B/A/D, starters).

## Load (2026-10-17 morning)

* Chart `DED101626USA.pdf`: 9 races, 82 starters, 42 exotic rows. The 99-entry
  pre-race card was purged first. Parser warnings: none.
* DB backup: `scripts/racing_full.db.pre-ded1016res.bak`. (Taken after the
  10/17 PP card was loaded; `.ded1017-run.bak` is the copy from before that
  load.)
* 17 logged horses scratched, including 7 also-eligibles that did not draw in.
* Each race has exactly one `finish_pos = 1` with a win payout, so no DQ and
  no dead heat. The interim DQ guard (2d96ea3) did not come into play.
* 3 DNF, chart finish "---". They count as starters and are ranked last:
  * R6 #3 Star Anise (bled, eased);
  * R8 #2 Miss Metoyer (bobbled, rider lost irons, pulled up);
  * R9 #7 Texano Hero (eased).
* `score_predictions.py`, official figures: the top pick was ITM in 6 of 9 and
  won 2 of 9. Top-pick show ROI was +52.2% ($27.40 back on $18). All horses
  were ITM 27 of 82.
* **Parser gap (new, not fixed):** Pick 4 and Pick 5 rows whose winning
  numbers carry scratch substitutes (for example `4/6/11/12-5-3-5`) are not
  parsed. They are missing from `exotic_payouts` and from the cache JSON for
  10/16, and also for 10/15. The payouts below were read from the chart text.

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | $0.10 super |
|---|---|---|---|---|---|---|---|---|
| 1 | 4-2-7-8 | 4-7-9-2 | **1st** | 1 of 6 (fav) | 2/3 | miss | miss | 11.29 |
| 2 | 1-6-5-10 | 6-10-3-5 | 8th | 2 of 9 (fav) | 1/3 | miss | miss | 8.67 |
| 3 | 1-4-2-3 | 5-2-7-1 | 4th | 10 of 10 (4.7-1) | 1/3 | miss | miss | 74.82 |
| 4 | 1-10-8-12 | 3-1-9-4 | **2nd** | 9 of 10 (32.9-1) | 1/3 | miss | miss | 6,772.69 |
| 5 | 7-5-9-2 | 5-2-3-9 | 6th (fav) | 2 of 10 (5.7-1) | 1/3 | miss | miss | 205.84 |
| 6 | 2-6-7-8 | 6-9-2-10 | **3rd** | 2 of 9 (fav) | 2/3 | miss | miss | 63.53 |
| 7 | 3-5-2-10 | 6-10-3-2 | **3rd** (fav) | 5 of 10 (10.8-1) | 1/3 | miss | miss | 49.16 |
| 8 | 5-6-2-1 | 6-10-5-1 | **3rd** | 2 of 8 (fav) | 2/3 | miss | miss | 191.83 |
| 9 | 8-5-3-2 | 8-3-10-4 | **1st** | 1 of 10 (fav) | 2/3 | miss | miss | 54.84 |

**Model:** the #1 pick won 2 races and was ITM in 6 of 9. Top-3 overlap was
13 of 27. The top-3 wheel and the super box each hit 0 of 9.

Base-only #1 was the same horse as the re-ranked #1 in all 9 races, so
base-only is also 6 of 9 ITM.

The favourite won 5 races (R1, R2, R6, R8, R9). The model had those
favourites ranked 1st, 2nd, 2nd, 2nd and 1st.

R3 was a 2yo maiden in which 9 of 10 starters were under 65% coverage. The
winner, Andrea Lee, was ranked last.

R4 went to Lovea Fighter at 32.9-1 and the superfecta paid $6,772.69. The
model's #1, Campanario (38.3-1), ran 2nd. The 1.2-1 favourite, After Party
(model #3), ran 8th.

## Reranker moves over 5 points

| R | horse | base → final | rank (base → final) | finished |
|---|---|---|---|---|
| 1 | #7 Dawson James | 35.3 → 45.3 (+10.0) | 6 → 3 | **2nd** |
| 1 | #9 Mr. Mo | 39.7 → 34.1 (−5.6) | 3 → 5 | **3rd** |
| 1 | #1 Thunder Kiss | 36.7 → 31.6 (−5.1) | 5 → 6 | 6th |
| 2 | #5 Unlawful | 19.0 → 24.9 (+5.9) | 8 → 3 | 4th |
| 3 | #1 Excusemelady's | 43.1 → 50.5 (+7.4) | 1 → 1 | 4th |
| 3 | #2 Angel's Anthem | 37.5 → 31.4 (−6.0) | 2 → 3 | **2nd** |
| 4 | #8 After Party | 32.2 → 37.4 (+5.1) | 3 → 3 | 8th |
| 5 | #1 Track Ranger | 20.2 → 25.3 (+5.1) | 7 → 6 | 7th |
| 6 | #5 Ridearoundsalley | 20.8 → 26.5 (+5.8) | 5 → 5 | 8th |
| 7 | #2 Drilling Report | 38.2 → 43.7 (+5.5) | 3 → 3 | 4th |
| 7 | #8 Baseball Lover | 13.3 → 4.2 (−9.1) | 9 → 10 | 10th |
| 9 | #9 Triple | 21.3 → 14.8 (−6.5) | 6 → 9 | 9th |

Three moves changed a top-3 set:
* R1 swapped Mr. Mo (3rd) for Dawson James (2nd), a wash.
* R2 swapped Cozzino (2nd) out for Unlawful (4th), which cost one overlap.
* R9 swapped Does Not Compute (3rd) for Straight Dropbilly (2nd), a wash.

Net, the reranker cost 1 point of top-3 overlap on the card.

## Low-coverage (<65%) horses

There were 16 of 82 starters below 65% coverage: R1 4, R3 9, R4 2 and R9 1.
Their summed P(ITM) was 4.51, and 5 finished in the money: R1 #4 (1st) and
#9 (3rd), and R3 #5 (1st), #2 (2nd) and #7 (3rd). The R3 maiden is most of
the list; the model's top 2 there (#1 50.5%, #4 34.2% at 63.8%) ran 4th and
7th.

## Don's picks (benchmark; `tracking/don_picks.csv`)

His picks are re-ranked around scratches in the same way as the model's:
* R2: #4 and alt #12 scratched, so he has only 3 runners.
* R3: #11 scratched, so alt #5 moves up. #5 won.
* R5: #11 scratched.
* R6: #11 scratched.

| R | Don (re-ranked) | Don #1 fin | Don top-3 overlap | model #1 fin | model top-3 overlap |
|---|---|---|---|---|---|
| 1 | 4-2-7-9 | **1st** | 2/3 | **1st** | 2/3 |
| 2 | 6-10-3 | **1st** | 3/3 | 8th | 1/3 |
| 3 | 2-8-6-5 | **2nd** | 1/3 | 4th | 1/3 |
| 4 | 8-4-6-5 | 8th | 0/3 | **2nd** | 1/3 |
| 5 | 3-7-2-4 | **3rd** | 2/3 | 6th | 1/3 |
| 6 | 6-2-8-4 | **1st** | 2/3 | **3rd** | 2/3 |
| 7 | 2-3-6-9 | 4th | 2/3 | **3rd** | 1/3 |
| 8 | 5-6-9-8 | **3rd** | 2/3 | **3rd** | 2/3 |
| 9 | 8-3-4-5 | **1st** | 2/3 | **1st** | 2/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box |
|---|---|---|---|---|---|
| Model | 2 | 6/9 | 13/27 | 0 | 0 |
| Don | 4 | 7/9 | 16/27 | 1 (R2) | 1 (R1, $11.29) |

Don and the model had the same #1 in three races:
* R1, #4 Pericles, won;
* R8, #5 Jojo Bean, 3rd;
* R9, #8 El Chavo, won.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R2 #6 Gold Thief (ML 6-1) | | **won** at 1.5-1 ($5.00) | — | — |
| EP4 (R2–R5) | 3-4-6-10-12 / 2-6-8-11 / 4-8 / 3-7 (80 combos) | $40 | miss | 1/4 (R2) | 6-5-3-5 paid 2,415.30 |
| LP4 (R6–R9) | 2-6-8-11 / 2-3-6 / 5-6-9 / 3-8 (72 combos) | $36 | **HIT** | 4/4 | 6-6-6-8 paid **126.80** |

The LP4 returned $126.80 on $36 (+$90.80). The EP4 went out in R3 (Andrea
Lee, 4.7-1). Don had alt #5 there, but it was not on the ticket.

## Doug's bets (`tracking/doug_bets.csv`)

| R | bet | ticket | cost | result | returned |
|---|---|---|---|---|---|
| 8 | $0.10 superfecta part wheel | 5,6 / 5,6 / 9,8,2,10 / 9,8,2,10 | $2.40 | lost (6-10-5-1) | — |
| 9 | $1 exacta box | 3,8 | $2.00 | **won** (8-3) | $14.00 |

Card total: $4.40 bet, $14.00 back (+$9.60).

## Watch list

`check_watch_list.py` flagged R1, R4, R6 and R7. Every flagged runner started:

| R | horse | watch | model rank | finished | odds |
|---|---|---|---|---|---|
| 1 | #2 La Normede Jour | T Calhoun | 2 of 6 | 4th | 1.5 |
| 4 | #10 Imperial Bandit | J D. Magnon | 2 of 10 | 10th | 4.2 |
| 6 | #10 Girl Thirsty | T Ward | 7 of 9 | 4th | 51.3 |
| 7 | #4 The Boyz Priority | T Ward | 9 of 10 | 7th | 67.6 |

Meet tally after 10/16 (`watch_people_tally.csv`; logged record runs only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 13 | 2 | 5 | 3.98 | 5 | +1.02 |
| J Devin H. Magnon | 5 | 3 | 3 | 1.63 | 3 | +1.37 |
| T Rylee Magnon | 1 | 1 | 1 | 0.27 | 1 | +0.73 |
| T W.B. Calhoun | 8 | 2 | 4 | 2.50 | 4 | +1.50 |

None of the four watch-list runners hit the board on this card. All four
people are still ahead of the model on the meet, but the samples are too small
to read.
