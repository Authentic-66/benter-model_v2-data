# DED 2026-10-22 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). **First card
on 1.3.2.** One logged run, the record: `generated_at = 2026-10-22T14:17:21`,
pre-race, bridged, 75 rows, commit `9522300`.

## Load (2026-10-22 evening)

* Chart `DED102226USA.pdf`: 8 races, 66 starters, 40 exotic rows. The
  75-entry pre-race card was purged first. 0 errors.
* DB backup: `scripts/racing_full.db.pre-ded1022res.bak`, verified: same
  sha256 as the live DB (`03ab9255…e5f5`), `integrity_check` ok on both,
  and the same row counts in six tables.
* **R7 DQ:** #6 Surveillance crossed 3rd and was placed 4th for brushing #3
  Gavel at the 1/16 pole. The parser applied it (`disqualified:pgm=6`,
  `official:1of1_applied:tote`); the official order 5-4-3-6 matches the
  tote. The `official_tote_mismatch:1` warning just records that the
  as-run order differed by that one swap.
* 1 DNF: R2 #9 Goodmorning Gracie. It counts as a starter and is ranked last.
* 9 logged horses scratched (5 vets, 4 also-eligibles that did not draw
  in), including **R7 #7 Clearasa Bele, the model's #1 (73.1%)**, and two
  model #2s: R4 #11 Ripple's Rocket and R6 #4 Fadeto Gold.
* Pick 4s: the R5 Pick 4 (R2–R5) parsed, `1-1-6-2` $3,959.55. The R8 Pick 4
  (R5–R8) did not (scratch substitute `5/7` in R7): `2-9-5/7-9` paid $205.15
  per $0.50, taken from the chart text.
  *Fixed 2026-10-22: the parser now reads these rows and they are
  backfilled in the DB (PHASE_6E, "Pick 3/4/5/6 payouts with scratch
  substitutes").*
* The chart calls R5 a STARTER ALLOWANCE; the PP loader had it as
  ALLOWANCE ("Alw 5000s"). Not chased.
* `score_predictions.py --track DED --date 2026-10-22`, official figures:
  * The logged top pick was ITM in 4 of 7 and won 1 of 7 (R7 is excluded:
    its top pick scratched).
  * Top-pick show ROI was −32.9% ($9.40 back on $14).
  * All horses were ITM 24 of 66.

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | $0.10 super |
|---|---|---|---|---|---|---|---|---|
| 1 | 1-2-7-9 | 5-8-9-2 | 5th (fav) | 8 of 10 (11.4-1) | 0/3 | miss | miss | 183.77 |
| 2 | 4-3-6-9 | 1-4-7-3 | **2nd** (fav) | 6 of 10 (10.4-1) | 1/3 | miss | miss | 110.93 |
| 3 | 5-2-8-7 | 1-8-7-2 | 5th (fav) | 5 of 9 (16.4-1) | 1/3 | miss | miss | 228.12 |
| 4 | 6-9-4-2 | 6-10-7-4 | **1st** | 1 of 8 (1.6-1) | 1/3 | miss | miss | 122.66 |
| 5 | 3-1-2-7 | 2-3-1-6 | **2nd** (fav) | 3 of 6 (2.7-1) | 3/3 | **HIT** | miss | 5.05 |
| 6 | 3-6-5-2 | 9-3-1-8 | **2nd** (fav) | 6 of 8 (7.4-1) | 1/3 | miss | miss | 31.55 |
| 7 | 6-2-5-1 | 5-4-3-6 | 4th (DQ from 3rd) | 3 of 6 (0.9-1, fav) | 1/3 | miss | miss | 11.00 |
| 8 | 7-4-9-2 | 9-6-4-7 | 4th (fav) | 3 of 9 (2.5-1) | 2/3 | miss | miss | 18.08 |

**Model:** the #1 pick won 1 race and was ITM in 4 of 8. Top-3 overlap was
10 of 24. The top-3 wheel hit once (R5, $5.05 per $0.10); the super box did
not hit.

* R7's re-ranked #1, Surveillance, crossed 3rd and was placed 4th, so the
  DQ cost the model one ITM.
* Long-shot winners the model had low: R1 Alterana (11.4-1, 8th of 10), R2
  Perfect Deal (10.4-1, 6th of 10), R3 Secret Injustice (16.4-1, 5th of 9;
  44% coverage) and R6 Proton Kitty (7.4-1, 6th of 8).
* R3 was the low-coverage race (55%): the model's #1 and #2 (both 52%
  coverage) ran 5th and 4th.

### Reranker

Base-only #1 differed once: in R5 base #1 was #1 Beamer (3rd), final #1 was
#3 Pondicherry (2nd). Both ITM. One top-3 set changed: R2 swapped #9 (DNF)
for #3 Mo Pumpkin (4th), a wash. Net: 0 on #1 ITM, 0 on overlap (10 → 10).

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #5 Alterana | 21.5 → 15.3 (−6.1) | 8 → 8 | **1st** |
| 2 | #9 Goodmorning Gracie | 35.4 → 30.2 (−5.2) | 2 → 4 | DNF |
| 3 | #8 Charming Gail | 37.9 → 45.5 (+7.6) | 3 → 3 | **2nd** |
| 4 | #9 Express Line | 31.3 → 40.1 (+8.8) | 3 → 2 | 6th |
| 6 | #6 Bronze Legacy | 39.4 → 46.2 (+6.7) | 2 → 2 | 6th |
| 6 | #8 Awree | 26.7 → 19.2 (−7.5) | 4 → 5 | 4th |
| 8 | #7 Youcandoitboy | 61.5 → 71.4 (+9.8) | 1 → 1 | 4th |
| 8 | #1 Uncle Eugene | 24.8 → 19.1 (−5.7) | 6 → 7 | 8th |

### Stretch feature (1.3.2 vs 1.3.1, scratch run, not logged)

1.3.1 re-ranked among the same runners gives the same #1 in every race and
the same top-3 sets: 1 win, 4/8 ITM, 10/24 overlap for both. The only order
change in a top 4 was R2 (#3 and #6 swapped 2nd/3rd; they ran 4th and 5th).
The biggest P(ITM) moves: R5 #5 Two Jet −5.0 (ran 5th), R2 #4 All Star Tout
+4.2 (ran 2nd), R7 #5 Achromedoutcat −2.6 (won; both stretch columns blank,
so that move is the refit, not the feature). One card: no signal either way.

## Low-coverage (<65%) horses

11 of 66 starters were below 65% coverage: R3 8, R1 2, R8 1. Their summed
P(ITM) was 3.25, and 3 finished in the money:
* R1 #8 Runhappy d'Oro (2nd);
* R3 #1 Secret Injustice (1st, 16.4-1) and #7 Rosie's Getaway (3rd).

## Benchmarks: Don and Doug

Re-ranked around scratches as before (Don's alt moves up; Doug has no alt).

* Don, R4: #11 scratched, alt #10 moves up. R6: #4 scratched, alt #1 moves
  up. R7: #7 scratched, alt #3 moves up.
* Doug, R6: #4 Fadeto Gold (vet scratch) dropped, so 3 picks.

Doug's picks were made on race day with scratches and odds known.

| R | Don (re-ranked) | Don #1 fin | Don overlap | Doug (re-ranked) | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 2-1-9-8 | 4th | 1/3 | 2-1-8-7 | 4th | 1/3 | 5th | 0/3 |
| 2 | 4-6-1-9 | **2nd** | 2/3 | 2-4-1-10 | 8th | 2/3 | **2nd** | 1/3 |
| 3 | 7-9-5-8 | **3rd** | 1/3 | 7-9-6-8 | **3rd** | 1/3 | 5th | 1/3 |
| 4 | 6-9-4-10 | **1st** | 1/3 | 6-9-4-10 | **1st** | 1/3 | **1st** | 1/3 |
| 5 | 3-2-6-5 | **2nd** | 2/3 | 6-2-3-7 | 4th | 2/3 | **2nd** | 3/3 |
| 6 | 3-9-8-1 | **2nd** | 2/3 | 3-7-8 | **2nd** | 1/3 | **2nd** | 1/3 |
| 7 | 5-2-6-3 | **1st** | 1/3 | 5-2-4-6 | **1st** | 2/3 | 4th | 1/3 |
| 8 | 7-9-1-6 | 4th | 1/3 | 6-7-9-4 | **2nd** | 2/3 | 4th | 2/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box |
|---|---|---|---|---|---|
| Model | 1 | 4/8 | 10/24 | 1 (R5, $5.05) | 0 |
| Don | 2 | 6/8 | 11/24 | 0 | 1 (R6, $31.55) |
| Doug | 2 | 5/8 | 12/24 | 0 | 1 (R8, $18.08) |

* All three had R4 #6 Miracle On Central (won) as #1.
* Don and the model shared #1 in R2 (All Star Tout, 2nd), R5 (Pondicherry,
  2nd) and R6 after the scratch (Della Do, 2nd).
* R7: Don's and Doug's #1 Achromedoutcat (0.9-1) won; the model had it 4th
  before the scratch and 3rd after it.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R2 #4 All Star Tout (ML 3-1) | | 2nd at 0.7-1 | — | — |
| EP4 (R2–R5) | 1-4-6-9 / 5-7-9 / 6-9-11 / 2-3 (72 combos) | $36 | miss | 3/4 | 1-1-6-2 paid 3,959.55 |
| LP4 (R5–R8) | 2-3 / 3-4 / 2-5-7 / 1-7-9 (36 combos) | $18 | miss | 3/4 | 2-9-5/7-9 paid 205.15 |

* The EP4 went out in R3 to Secret Injustice (#1, 16.4-1), who was in none of
  Don's picks. With #1 in that leg the ticket would have paid $3,959.55.
* The LP4 went out in R6 to Proton Kitty (#9, 7.4-1). Don had #9 as his
  third pick there, but not on the ticket.

### Doug's bets

None reported for 10/22.

## Watch list

| R | horse | watch | model rank (runners) | finished | odds |
|---|---|---|---|---|---|
| 3 | #9 Visions of War | J D. Magnon | 9 of 9 | 8th | 5.8 |
| 4 | #2 Taurean | J D. Magnon | 4 of 8 | 5th | 28.9 |
| 6 | #3 Della Do | T Ward | 1 of 8 | **2nd** | 0.3 (fav) |
| 6 | #1 Walksonwater | T Ward | 7 of 8 | **3rd** | 32.0 |

Meet tally after 10/22 (`watch_people_tally.csv`; logged record runs only,
pooled across 1.3.0, 1.3.1 and 1.3.2):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 16 | 2 | 8 | 5.14 | 8 | +2.86 |
| J Devin H. Magnon | 14 | 4 | 5 | 4.63 | 5 | +0.37 |
| T Rylee Magnon | 4 | 1 | 1 | 1.66 | 1 | −0.66 |
| T W.B. Calhoun | 10 | 3 | 6 | 3.21 | 6 | +2.79 |

Ward went 2-for-2 in the money, including Walksonwater at 32-1 (the model's
7th of 8). Ward is now +2.86 ITM over the model on 16 starts, the biggest gap on
the list. Still a small sample.
