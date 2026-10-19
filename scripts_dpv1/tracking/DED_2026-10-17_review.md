# DED 2026-10-17 — card review

Model `dpv1.3.0-5track` + `pp-reranker-1.0` (Config Y). One logged run, the
record: `generated_at = 2026-10-17T07:58:47`, pre-race, bridged, 101 rows,
commit `3fe1088`.

## Load (2026-10-18 evening)

* Chart `DED101726USA.pdf`: 10 races, 84 starters, 53 exotic rows. The
  101-entry pre-race card was purged first. Parser warnings: none.
* Loaded in the same batch as 30 CT/GP charts (see PHASE_6E_LOGGING.md,
  "Results catch-up, 2026-10-18").
* DB backup: `scripts/racing_full.db.pre-results1018.bak`, verified: same
  sha256 as the live DB at copy time, `integrity_check` ok, and the same row
  counts in six tables.
* 17 logged horses scratched. That includes R10 #3 Ready Renee, the logged #1.
* Each race has exactly one `finish_pos = 1` with a win payout, so no DQ and
  no dead heat. The interim DQ guard (2d96ea3) did not come into play.
* 1 DNF: R2 #1 Getthe Gate (trailed, eased; chart finish "---"). The DNF
  counts as a starter and is ranked last.
* The Pick 4 and Pick 5 rows (R5, R10) parsed this time. Neither carried
  scratch substitutes.
* `score_predictions.py`, official figures:
  * The logged top pick was ITM in 6 of 9 and won 5 of 9 (R10 is excluded:
    its top pick scratched).
  * Top-pick show ROI was +12.8% ($20.30 back on $18).
  * All horses were ITM 30 of 84.

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | $0.10 super |
|---|---|---|---|---|---|---|---|---|
| 1 | 3-9-1-8 | 3-7-9-2 | **1st** | 1 of 9 (3.0-1) | 2/3 | miss | miss | 75.89 |
| 2 | 7-4-2-6 | 7-6-4-5 | **1st** | 1 of 7 (3.3-1) | 2/3 | miss | miss | 47.55 |
| 3 | 7-9-2-5 | 9-10-5-6 | 8th (fav) | 2 of 10 (5.3-1) | 1/3 | miss | miss | 462.99 |
| 4 | 6-5-1-4 | 6-2-5-4 | **1st** (fav) | 1 of 7 (1.0-1) | 2/3 | miss | miss | 32.16 |
| 5 | 5-3-7-8 | 10-5-8-3 | **2nd** | 9 of 9 (18.0-1) | 1/3 | miss | miss | 299.94 |
| 6 | 1-2-5-3 | 1-3-5-2 | **1st** (fav) | 1 of 5 (0.8-1) | 2/3 | miss | **HIT** | 0.94 |
| 7 | 10-7-11-8 | 7-5-6-10 | 4th | 2 of 10 (fav, 1.5-1) | 1/3 | miss | miss | 217.90 |
| 8 | 3-7-6-1 | 3-7-4-6 | **1st** (fav) | 1 of 9 (2.0-1) | 2/3 | miss | miss | 32.18 |
| 9 | 2-8-10-7 | 7-11-9-3 | 9th | 4 of 9 (3.7-1) | 0/3 | miss | miss | 195.12 |
| 10 | 7-10-1-6 | 1-10-7-4 | **3rd** | 3 of 9 (fav, 2.5-1) | 3/3 | **HIT** | miss | 9.86 |

**Model:** the #1 pick won 5 races and was ITM in 7 of 10. Top-3 overlap was
16 of 30. The top-3 wheel hit once (R10, $9.86 per $0.10) and the super box
hit once (R6, a 5-horse field, $0.94 per $0.10: less than the box costs).

Base-only #1 was also ITM in 7 of 10 but won 4. The one difference is R2: the
reranker moved Can See Da Feet (won) over base #1 #4 (3rd).

The favourite won 5 races (R4, R6, R7, R8, R10). The model had those
favourites ranked 1st, 1st, 2nd, 1st and 3rd. Three favourites the model
ranked in its top 3 ran off the board: R2 #2 (1.2-1, 6th), R3 #7 (2.4-1, the
model's #1, 8th) and R9 #8 (1.8-1, 7th).

R3 was the low-coverage race: all 10 starters were under 65%. The model's #1,
King Gabes Money, ran 8th; its #2, Date Money, won.

R5 went to Sister Speaker at 18.0-1, ranked last of 9 by the model; the
superfecta paid $299.94.

## Reranker moves over 5 points

| R | horse | base → final | rank (base → final) | finished |
|---|---|---|---|---|
| 1 | #3 Authentic Queen | 45.4 → 54.6 (+9.2) | 1 → 1 | **1st** |
| 1 | #1 Regal Time | 20.6 → 30.4 (+9.8) | 6 → 3 | 9th |
| 2 | #7 Can See Da Feet | 52.4 → 59.9 (+7.5) | 2 → 1 | **1st** |
| 3 | #9 Date Money | 29.1 → 39.1 (+9.9) | 5 → 2 | **1st** |
| 3 | #8 Indian Bell | 20.0 → 13.4 (−6.6) | 10 → 10 | 10th |
| 4 | #1 KG's Magic | 54.4 → 59.7 (+5.3) | 3 → 3 | 6th |
| 5 | #6 Steal Tiz One | 17.0 → 26.3 (+9.4) | 9 → 5 | 9th |
| 6 | #3 Party At Jays | 32.2 → 37.3 (+5.1) | 4 → 4 | **2nd** |
| 8 | #7 Footprint | 23.8 → 32.0 (+8.1) | 5 → 2 | **2nd** |
| 10 | #2 She's by My Side | 22.3 → 14.2 (−8.1) | 7 → 8 | 5th |

Six top-3 sets changed (counting the knock-on moves of horses under 5 points):
* R1 swapped #8 (8th) for Regal Time (9th), a wash.
* R2 swapped #3 (5th) for #2 (6th), a wash. It also changed the #1 to the winner.
* R3 swapped #5 (3rd) for Date Money (1st), a wash on overlap.
* R5 swapped #8 (3rd) for #7 (8th), which cost one overlap.
* R8 swapped #1 (5th) for Footprint (2nd), which gained one.
* R10 swapped #6 (9th) for #1 Seraphina Sea (1st), which gained one.

R9 kept the same top 3 but swapped the order: #1 went from #8 Payne (7th) to
#2 Lambo (9th).

Net, the reranker gained 1 point of top-3 overlap (15 → 16) and 1 win at #1.

## Low-coverage (<65%) horses

19 of 84 starters were below 65% coverage: R3 10, R5 5, R10 2, R1 1 and
R9 1. Their summed P(ITM) was 4.77, and 5 finished in the money:
* R1 #7 Breaker Wave (2nd);
* R3 #9 Date Money (1st), #10 Stormin' Starfist (2nd) and #5 Take the Money
  (3rd);
* R5 #10 Sister Speaker (1st, 18.0-1).

## Don's picks (benchmark; `tracking/don_picks.csv`)

His picks are re-ranked around scratches in the same way as the model's.
Only R9 needed it: #5 Hay Jude scratched, so alt #2 moves up.

| R | Don (re-ranked) | Don #1 fin | Don top-3 overlap | model #1 fin | model top-3 overlap |
|---|---|---|---|---|---|
| 1 | 9-10-2-7 | **3rd** | 1/3 | **1st** | 2/3 |
| 2 | 2-4-7-6 | 6th | 2/3 | **1st** | 2/3 |
| 3 | 2-4-9-5 | 9th | 1/3 | 8th | 1/3 |
| 4 | 6-4-1-3 | **1st** | 1/3 | **1st** | 2/3 |
| 5 | 3-5-10-9 | 4th | 2/3 | **2nd** | 1/3 |
| 6 | 1-3-2-5 | **1st** | 2/3 | **1st** | 2/3 |
| 7 | 7-5-10-4 | **1st** | 2/3 | 4th | 1/3 |
| 8 | 3-7-2-4 | **1st** | 2/3 | **1st** | 2/3 |
| 9 | 8-7-3-2 | 7th | 1/3 | 9th | 0/3 |
| 10 | 10-6-7-1 | **2nd** | 2/3 | **3rd** | 3/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box |
|---|---|---|---|---|---|
| Model | 5 | 7/10 | 16/30 | 1 (R10, $9.86) | 1 (R6, $0.94) |
| Don | 4 | 6/10 | 16/30 | 0 | 1 (R6, $0.94) |

Don and the model had the same #1 in three races, and all three won:
* R4, #6 Serious Rock;
* R6, #1 Same Play;
* R8, #3 Call My Banker.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R4 #6 Serious Rock (ML 7-2) | | **won** at 1.0-1 ($4.00) | — | — |
| POD | R5 #3 Dolabella (ML 3-1) | | 4th (0.7-1 fav) | — | — |
| POD | R9 #8 Payne (ML 6-1) | | 7th (1.8-1 fav) | — | — |
| EP4 (R2–R5) | 2-4-7 / 2-4-5-9 / 4-6 / 3-5 (48 combos) | $24 | miss | 3/4 | 7-9-6-10 paid 844.20 |
| LP4 (R7–R10) | 5-7-10 / 2-3-7 / 5-7-8 / 6-10 (54 combos) | $27 | miss | 3/4 | 7-3-7-1 paid 82.40 |

Both Pick 4s went out in the last leg:
* The EP4 lost in R5 to Sister Speaker (#10, 18.0-1). Don had #10 as his
  third pick there, but not on the ticket.
* The LP4 lost in R10 to Seraphina Sea (#1, the 2.5-1 favourite). Don had #1
  as his fourth pick there, but not on the ticket.

## Doug's bets (`tracking/doug_bets.csv`, today's DED bet only)

| R | bet | ticket | cost | result | returned |
|---|---|---|---|---|---|
| 8 | $2 win | #3 Call My Banker | $2.00 | **won** (3-7-4-6) | $6.00 |

Card total: $2.00 bet, $6.00 back (+$4.00). Doug's CT 10/17 R6 superfecta is
logged in the same file as a personal bet; CT 10/17 was not a logged model card.

## Watch list

`check_watch_list.py` flagged R1, R2, R3, R6 and R9 (against the list as it
stood before Cincy's Player was added):

| R | horse | watch | model rank | finished | odds |
|---|---|---|---|---|---|
| 1 | #6 Flash of Fire | J D. Magnon | 6 of 9 | 6th | 20.1 |
| 2 | #2 Aoide | T R. Magnon | 3 of 7 | 6th | 1.2 |
| 2 | #3 Elaina Reins | T R. Magnon, J D. Magnon | 5 of 7 | 5th | 16.8 |
| 2 | #6 Chamois' Splendor | T Ward | 4 of 7 | **2nd** | 9.6 |
| 3 | #1 Cheers to Standard | J D. Magnon | 9 of 10 | 5th | 73.5 |
| 3 | #5 Take the Money | T Calhoun | 4 of 10 | **3rd** | 12.2 |
| 3 | #9 Date Money | T Calhoun | 2 of 10 | **1st** | 5.3 |
| 6 | #2 Seitan | T R. Magnon, J D. Magnon | 2 of 5 | 4th | 5.1 |
| 9 | #4 Lee Street | T Ward | — | scratched | — |
| 9 | #7 Sweet Fantasy | J D. Magnon | 4 of 9 | **1st** | 3.7 |

Meet tally after 10/17 (`watch_people_tally.csv`; logged record runs only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 14 | 2 | 6 | 4.40 | 6 | +1.60 |
| J Devin H. Magnon | 10 | 4 | 4 | 3.26 | 4 | +0.74 |
| T Rylee Magnon | 4 | 1 | 1 | 1.66 | 1 | −0.66 |
| T W.B. Calhoun | 10 | 3 | 6 | 3.21 | 6 | +2.79 |

Calhoun went 1st and 3rd with both R3 runners. Rylee Magnon's three
runners all missed the board (Aoide at 1.2-1), which leaves Rylee Magnon as
the only one behind the model. The samples are still too small to read.

**Added 2026-10-18:** horse Cincy's Player (R10 #7). Doug's note: wide trip,
closed strongly for 3rd. The chart has him 8th early, "widegain,clearthird",
beaten 2 1/4 at 4.1-1. He was the model's #1 once Ready Renee scratched
(40.1% P(ITM), 94% coverage).
