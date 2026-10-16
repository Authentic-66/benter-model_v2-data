# DED 2026-10-15 — card review

Model `dpv1.3.0-5track` + `pp-reranker-1.0` (Config Y). One logged run, the
record: `generated_at = 2026-10-15T16:52:08`, picks
`picks/DED_2026-10-15_20261015-1652.txt`, 88 rows. All eight races were logged
pre-race. This is the first post-fix card: it was run on commit `2d574f1`,
which has the reader guard, parser fixes, #9, #10 and #11 but not #12. See
`PHASE_6E_LOGGING.md`.

## Load

* Chart `DED101526USA.pdf`: 8 races, 76 starters, 44 exotic rows. The 88-entry
  pre-race card was purged first.
* DB backup: `scripts/racing_full.db.pre-ded1015res.bak`. (`pre-ded1015.bak`
  is the backup taken before the PP load.)
* 12 logged horses scratched: R2 #11/#12, R3 #11/#12, R4 #5/#11/#12, R5 #11/#12,
  R6 #6, R7 #11 and R8 #11.
* There were 2 DNF: R3 #4 Shred It Up and R8 #5 Meaner Than Mean. They count
  as starters and are ranked last.
* **R7 was a dead heat for win** between #5 Slewssongofthenile and #9 Misdeal.
  The chart parser forces the WPS winner to 1st and clears every other
  `finish_pos = 1` (`contradictory_winner_cleared`). It picked Misdeal as the
  WPS winner, set Slewssongofthenile to 1st from his Fin token, and then
  cleared Misdeal. **Misdeal is in the DB with `finish_pos` NULL.**
  `score_predictions` therefore skipped him (75 scored rows, not 76). This
  review scores him as dead-heat 1st. See the open item at the end.
* `score_predictions.py`, official figures: the top pick was ITM in 3 of 7 races
  and won 2 of 7. The 8th race is R6, whose logged top pick, #6 Bearcat,
  was a vet scratch.

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | $0.10 super |
|---|---|---|---|---|---|---|---|---|
| 1 | 4-5-2-6 | 4-5-9-1 | **1st** | 1 of 9 | 2/3 | miss | miss | 96.63 |
| 2 | 9-2-3-7 | 6-8-10-7 | 8th | 9 of 10 (15.8-1) | 0/3 | miss | miss | 403.52 |
| 3 | 1-9-2-8 | 9-10-7-2 | 9th | 2 of 10 (fav) | 1/3 | miss | miss | 143.99 |
| 4 | 3-6-9-2 | 6-3-4-10 | **2nd** | 2 of 9 (fav) | 2/3 | miss | miss | 11.47 |
| 5 | 1-9-7-5 | 5-8-6-2 | 9th | 4 of 10 (9.8-1) | 0/3 | miss | miss | 16,569.73 |
| 6 | 8-1-5-9 | 8-9-7-3 | **1st** | 1 of 8 | 1/3 | miss | miss | 125.62 |
| 7 | 5-6-1-2 | 5/9 DH-10-4 | **1st (DH)** | 1 and 9 of 10 | 1/3 | miss | miss | 95.71 / 138.75 |
| 8 | 1-9-6-3 | 6-10-3-2 | 7th | 3 of 10 (fav) | 1/3 | miss | miss | 82.94 |

**Model:** the #1 pick (re-ranked) won 3 races, one of them a dead heat, and
was ITM in 4 of 8. Top-3 overlap was 8 of 24. The top-3 wheel and the super box
each hit 0 of 8.

The reranker did not change the top pick in any race. Base-only and re-ranked
#1 were the same horse in all 8, so base-only is also 4 of 8 ITM. The logged
R6 #1, Bearcat, scratched, and the promoted #2, Theboyz Warning, won at 5.2-1.

The favourite won R3, R4, R7 and R8. The model ranked those favourites 2nd,
2nd, 1st and 3rd. R2 and R5 were the misses: 33.60 and 21.60 winners, both
with a 0/3 overlap.

## Reranker moves over 5 points

| R | horse | base → final | rank (base → final) | finished |
|---|---|---|---|---|
| 5 | #5 Maxxus | 28.9 → 34.3 (+5.4) | 4 → 4 | **1st** |
| 5 | #10 It's Miles | 22.7 → 16.5 (−6.2) | 6 → 7 | 8th |
| 8 | #7 Woodall Pass | 25.6 → 34.9 (+9.4) | 5 → 5 | 6th |

There were only three moves over 5 points, and none of them changed a top-4
set. Two went the right way (R5) and one the wrong way (R8).

## Low-coverage (<65%) horses

There were 4 of 76 starters below 65% coverage. Their summed P(ITM) was 0.62,
and 1 finished in the money.

| R | horse | cov | model rank | P(ITM) | finished |
|---|---|---|---|---|---|
| 3 | #5 Petty Officer | 54% | 8 | 15.4 | 6th |
| 4 | #1 Grey Street | 64.9% | 7 | 18.0 | 9th |
| 5 | #8 Grand Oracle | 62.8% | 8 | 15.1 | **2nd** |
| 5 | #2 Cutting Class | 64.9% | 9 | 13.9 | 4th |

## Don's picks (benchmark; `tracking/don_picks.csv`)

His picks are re-ranked around scratches the same way as the model's. In R6
his #3, #6 Bearcat, scratched, so his alt #5 moves up. His other picks all ran.

| R | Don (re-ranked) | Don #1 fin | Don top-3 overlap | model #1 fin | model top-3 overlap |
|---|---|---|---|---|---|
| 1 | 4-2-6-5 | **1st** | 1/3 | **1st** | 2/3 |
| 2 | 2-10-8-3 | 10th | 2/3 | 8th | 0/3 |
| 3 | 9-1-3-2 | **1st** | 1/3 | 9th | 1/3 |
| 4 | 3-6-1-2 | **2nd** | 2/3 | **2nd** | 2/3 |
| 5 | 9-7-8-10 | 5th | 1/3 | 9th | 0/3 |
| 6 | 8-1-7-5 | **1st** | 2/3 | **1st** | 1/3 |
| 7 | 6-5-1-10 | 6th | 1/3 | **1st (DH)** | 1/3 |
| 8 | 1-10-9-6 | 7th | 1/3 | 7th | 1/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box |
|---|---|---|---|---|---|
| Model | 3 | 4/8 | 8/24 | 0 | 0 |
| Don | 3 | 4/8 | 11/24 | 0 | 0 |

Don and the model had the same #1 in four races:
* R1, #4 Highstakes Hustler, won;
* R4, #3 Piastri, 2nd;
* R6, #8 Theboyz Warning, won (the model's after the Bearcat scratch);
* R8, #1 Lady Ella, 7th.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R8 #1 Lady Ella (ML 9-2) | | 7th | — | — |
| EP4 (R2–R5) | 2 / 1-3-9 / 1-3-6 / 7-8-9-10 (36 combos) | $18 | **miss** | 2/4 (R3, R4) | 6-9-6-5 paid 736.95 |
| LP4 (R5–R8) | 7-8-9 / 1-6-8 / 1-5-6 / 1-10 (54 combos) | $27 | **miss** | 2/4 (R6, R7) | 5-8-5/9-6 paid 762.80 |

Both Pick 4s went out in R5, where Maxxus won at 9.8-1. The EP4 also missed
the opening leg, R2, which went to the 15.8-1 winner. None of Don's legs held
a scratched horse.

## Watch list

`check_watch_list.py` flagged R5–R8. Every flagged runner that started:

| R | horse | watch | model rank | finished | odds |
|---|---|---|---|---|---|
| 5 | #3 Majestic Palace | T Ward | 5 of 10 | 7th | 23.5 |
| 5 | #5 Maxxus | J D. Magnon | 4 of 10 | **1st** | 9.8 |
| 6 | #8 Theboyz Warning | T Ward | 1 of 8 | **1st** | 5.2 |
| 7 | #5 Slewssongofthenile | T Ward | 1 of 10 | **1st (DH)** | 2.3 |
| 7 | #10 Reaux Ban Da Man | T Calhoun | 6 of 10 | **3rd** | 8.4 |
| 8 | #3 Married for Money | T Ward | 4 of 10 | **3rd** | 7.4 |

R7 #11 Seitan (T Rylee Magnon, J D. Magnon) was an also-eligible scratch.

Meet tally after 10/15 (`watch_people_tally.csv`; logged record runs only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 11 | 2 | 5 | 3.72 | 5 | +1.28 |
| J Devin H. Magnon | 4 | 3 | 3 | 1.26 | 3 | +1.74 |
| T Rylee Magnon | 1 | 1 | 1 | 0.27 | 1 | +0.73 |
| T W.B. Calhoun | 7 | 2 | 4 | 2.03 | 4 | +1.97 |

All four are running ahead of the model, but the samples are 1–11 starts, which
is too few to read anything from.

## Open item (for Doug): dead heats for win in the chart parser

`equibase_pdf_parser.py` (~line 1212) treats the WPS winner as the ground
truth and clears any other `finish_pos = 1`. In a dead heat for win, both
horses have a win payout, so one of the two co-winners loses its finish. This
card's case is R7 #9 Misdeal: `finish_pos` is NULL in the DB. As a result:
* it is missing from `scored_predictions.jsonl`;
* it will enter the training corpus as a non-finisher unless it is fixed.

171 cached chart JSONs carry a `contradictory_winner_cleared` warning. Most of
them should be the legitimate 10+-field "12 vs 1-by-2" case; how many are dead
heats has not been checked. Nothing was changed.
