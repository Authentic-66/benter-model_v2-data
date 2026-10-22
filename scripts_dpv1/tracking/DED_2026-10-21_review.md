# DED 2026-10-21 — card review

Model `dpv1.3.1-5track-clean` + `pp-reranker-1.0` (Config Y). This is the
only card 1.3.1 ran (1.3.2 took over from 10/22). The record is the 10:25
run (`generated_at = 2026-10-21T10:25:12`, pre-race, bridged, 73 rows,
commit `66a94c9`, after the PP purse fix). It supersedes the 09:35 run.

## Load (2026-10-22)

* Chart `DED102126USA.pdf`: 8 races, 62 starters, 38 exotic rows. The
  73-entry pre-race card was purged first.
* DB backup: `scripts/racing_full.db.pre-ded1021res.bak`, verified: same
  sha256 as the live DB (`5e67f0cd…7938`), `integrity_check` ok on both,
  and the same row counts in six tables.
* Parser warnings: one dead heat for 6th in R8 (#2 RT's Cajun Star and #7
  Sugah Gem). No DQs.
* 1 DNF: R2 #2 Top Notch Protocol (eased; chart finish "---"). It counts as
  a starter and is ranked last.
* 11 logged horses scratched, none of them a model #1. Two were in the
  model's top 3: R5 #2 Enticing Spirit (#2) and R7 #5 Bayou Bertie (#3).
  Also R1 #8 Alvarado Cat (#3 before the re-rank).
* **Pick 4 rows did not parse** (the known scratch-substitute gap): R5
  `5-5/6-1-2/4/8` paid $287.55 and R8 `2/4/8-7-1-1` paid $115.10 (both per
  $0.50). Taken from the chart text by hand below.
* `score_predictions.py --track DED --date 2026-10-21`, official figures:
  * The logged top pick was ITM in 4 of 8 and won 2 of 8.
  * Top-pick show ROI was −8.1% ($14.70 back on $16).
  * All horses were ITM 24 of 62.

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | $0.10 super |
|---|---|---|---|---|---|---|---|---|
| 1 | 2-7-6-5 | 6-7-4-1 | 7th | 3 of 7 (3.7-1) | 2/3 | miss | miss | 11.64 |
| 2 | 3-6-4-7 | 5-4-1-3 | 4th (fav) | 7 of 9 (4.8-1) | 1/3 | miss | miss | 83.05 |
| 3 | 5-4-7-2 | 5-8-7-4 | **1st** (fav) | 1 of 7 (2.2-1) | 2/3 | miss | miss | 17.35 |
| 4 | 2-3-9-8 | 1-3-10-9 | 9th | 7 of 9 (12.6-1) | 1/3 | miss | miss | 93.63 |
| 5 | 8-5-6-7 | 8-5-3-1 | **1st** (fav) | 1 of 6 (0.6-1) | 2/3 | miss | miss | 4.95 |
| 6 | 1-7-3-5 | 7-3-1-4 | **3rd** | 2 of 9 (1.8-1) | 3/3 | **HIT** | miss | 47.13 |
| 7 | 3-4-6-2 | 1-6-4-3 | 4th (fav) | 5 of 5 (4.8-1) | 2/3 | miss | miss | 14.15 |
| 8 | 10-7-1-3 | 1-5-10-4 | **3rd** | 3 of 10 (3.6-1) | 2/3 | miss | miss | 86.71 |

**Model:** the #1 pick won 2 races and was ITM in 4 of 8. Top-3 overlap was
15 of 24. The top-3 wheel hit once (R6, $47.13 per $0.10); the super box
did not hit.

Base-only #1 was the same horse in all 8 races, so the reranker changed no
#1. It did change the top 3 in five races (below), and that took top-3
overlap from 10 to 15.

Two of the model's #1s were beaten odds-on favourites: R2 #3 Seeking Aces
(0.8-1, 4th) and R7 #3 Six String (1.0-1, 4th). R1's #2 Avery's Gem
(3.5-1) ran 7th. R7 went to Whata Moon at 4.8-1, ranked last of 5 by the
model.

## Reranker moves over 5 points (horses that ran)

| R | horse | base → final | rank (base → final) | finished |
|---|---|---|---|---|
| 2 | #3 Seeking Aces | 44.0 → 54.2 (+10.3) | 1 → 1 | 4th |
| 3 | #5 Tensas Union Girl | 66.9 → 76.0 (+9.2) | 1 → 1 | **1st** |
| 4 | #8 Max Base | 45.9 → 36.2 (−9.8) | 2 → 4 | 5th |
| 4 | #10 Deelitesandimsum | 27.1 → 34.8 (+7.7) | 6 → 6 | **3rd** |
| 6 | #5 Ry Ry | 25.5 → 32.4 (+6.8) | 5 → 4 | 5th |
| 6 | #10 Air Sahara | 15.5 → 10.5 (−5.0) | 7 → 9 | 9th |
| 8 | #7 Sugah Gem | 32.2 → 46.7 (+14.5) | 2 → 2 | 6th (DH) |
| 8 | #1 Reaux Day | 26.3 → 36.0 (+9.7) | 6 → 3 | **1st** |
| 8 | #2 RT's Cajun Star | 28.7 → 22.4 (−6.3) | 4 → 6 | 6th (DH) |
| 8 | #8 Peanutbutter Peggy | 22.6 → 16.3 (−6.3) | 7 → 8 | 10th |
| 8 | #9 Overqualified | 20.8 → 15.6 (−5.2) | 9 → 9 | 8th |

Top-3 sets the reranker changed (including knock-on moves under 5 points):
* R2: #7 (base #2) out, #4 in (2nd): +1.
* R3: #2 out, #7 Anna K in (3rd): +1.
* R4: #8 Max Base (5th) out, #3 in (2nd): +1.
* R7: #2 out, #6 in (2nd): +1.
* R8: #3 out, #1 Reaux Day in (won): +1.

Net, the reranker gained 5 points of top-3 overlap (10 → 15) and changed
no #1. That is the best single card for the reranker so far.

## Low-coverage (<65%) horses

9 of 62 starters were below 65% coverage: R5 4, R3 2, R8 2 and R6 1. Their
summed P(ITM) was 2.31, and 5 finished in the money:
* R3 #8 True Fire (2nd, Don's POD) and #7 Anna K (3rd);
* R5 #5 Free Deal (2nd) and #3 Warmhearted Lady (3rd);
* R8 #5 Kathleen's Ace (2nd, 2.2-1 favourite).

## Benchmarks: Don and Doug

Picks are re-ranked around scratches the same way as the model's. Don's
alt moves up when a pick scratches. Doug has no alt; a scratched pick just
drops.

* Don, R5: #4 scratched and alt #2 scratched too, so 3 picks (8-1-6).
* Don, R6: #6 scratched, so alt #1 moves up.
* Doug, R5: #4 Watch Me I'm Ready scratched, so only #8 is left.

Doug's picks are new in `tracking/doug_picks.csv`. **They were made on race
day with scratches and odds known; Don's and the model's were not.** Read
Doug's numbers with that in mind. "Pick 'em" slots are left blank.

| R | Don (re-ranked) | Don #1 fin | Don overlap | Doug (re-ranked) | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 6-1-7-4 | **1st** | 2/3 | 6-7-1-5 | **1st** | 2/3 | 7th | 2/3 |
| 2 | 3-4-5-2 | 4th | 2/3 | 2-3-5-7 | DNF | 1/3 | 4th | 1/3 |
| 3 | 8-5-4-3 | **2nd** | 2/3 | 5-3-7 | **1st** | 2/3 | **1st** | 2/3 |
| 4 | 2-5-8-3 | 9th | 0/3 | 5-7-3-8 | 8th | 1/3 | 9th | 1/3 |
| 5 | 8-1-6 | **1st** | 1/3 | 8 | **1st** | 1/3 | **1st** | 2/3 |
| 6 | 7-3-5-1 | **1st** | 2/3 | 11-7-8-10 | 8th | 1/3 | **3rd** | 3/3 |
| 7 | 3-6-1-4 | 4th | 2/3 | 3-1-6-2 | 4th | 2/3 | 4th | 2/3 |
| 8 | 5-1-4-2 | **2nd** | 2/3 | 9-8-3 | 8th | 0/3 | **3rd** | 2/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box |
|---|---|---|---|---|---|
| Model | 2 | 4/8 | 15/24 | 1 (R6, $47.13) | 0 |
| Don | 3 | 5/8 | 13/24 | 0 | 2 (R1 $11.64, R7 $14.15) |
| Doug | 3 | 3/8 | 10/24 | 0 | 0 (R3, R5, R8 short of 4 picks) |

Same #1 as the model:
* Don: R2 #3 Seeking Aces (4th), R5 #8 Joking Around (won), R7 #3 Six
  String (4th).
* Doug: R3 #5 Tensas Union Girl (won), R5 #8 Joking Around (won).

All three had the same top pick in R5 and all three missed R4 (My Special
Star, 12.6-1, the model's 7th of 9).

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R3 #8 True Fire (ML 8-1) | | 2nd at 4.9-1 | — | — |
| EP4 (R2–R5) | 3-4-5 / 3-4-5-8 / 2-5-8 / 1-8 (72 combos) | $36 | miss | 3/4 | 5-5/6-1-2/4/8 paid 287.55 |
| LP4 (R5–R8) | 1-8 / 6-7 / 3-6 / 1-2-4-5 (32 combos) | $16 | miss | 3/4 | 2/4/8-7-1-1 paid 115.10 |

* The EP4 went out in R4 to My Special Star (#1, 12.6-1). Don had 2-5-8.
* The LP4 went out in R7 to Whata Moon (#1, 4.8-1). Don had #1 as his third
  pick there, but not on the ticket.

### Doug's bets (`tracking/doug_bets.csv`)

| R | bet | ticket | cost | result | returned |
|---|---|---|---|---|---|
| 2 | $2 win | #2 Top Notch Protocol | $2.00 | lost (eased, DNF) | $0 |
| 8 | unknown | #8 Peanutbutter Peggy (79.3-1) | unknown | lost (10th of 10) | $0 |

The R8 amount and bet type are logged as unknown; they come from TwinSpires
history if Doug adds it. Nothing could have cashed: the horse ran last.

## Watch list

`check_watch_list.py` flagged R1 and R5:

| R | horse | watch | model rank | finished | odds |
|---|---|---|---|---|---|
| 1 | #7 Briterdayzahead | J D. Magnon | 2 of 7 | **2nd** | 1.8 (fav) |
| 5 | #6 Bayou Baby | J D. Magnon | 3 of 6 | 5th | 11.8 |

Meet tally after 10/21 (`watch_people_tally.csv`; logged record runs only,
pooled across 1.3.0 and 1.3.1):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 14 | 2 | 6 | 4.40 | 6 | +1.60 |
| J Devin H. Magnon | 12 | 4 | 5 | 4.17 | 5 | +0.83 |
| T Rylee Magnon | 4 | 1 | 1 | 1.66 | 1 | −0.66 |
| T W.B. Calhoun | 10 | 3 | 6 | 3.21 | 6 | +2.79 |

Only Devin Magnon had runners on 10/21. The samples are still too small to
read.
