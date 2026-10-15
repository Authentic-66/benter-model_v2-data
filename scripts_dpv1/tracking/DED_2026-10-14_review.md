# DED 2026-10-14 — card review

Model `dpv1.3.0-5track` + `pp-reranker-1.0` (Config Y). One logged run:
the picks page header reads 18:19, and the log rows carry
`generated_at = 2026-10-14T18:22:02`. Picks:
`picks/DED_2026-10-14_20261014-1822.txt`.

> **R1–R4 are post-time logs.** They were logged after those races went off.
> Their results were not in the DB, so the model could not see them, but they
> are not pre-race predictions in the strict sense. R5–R8 were logged pre-race.

The run went through the **pdfplumber** text path. Doug's PowerShell has no
`pdftotext` on PATH. This was confirmed by reproducing the R5 reasons block
exactly; see `PHASE_6E_LOGGING.md`, follow-up #8.

## Load

* Chart `DED101426USA.pdf`: 8 races, 71 starters, 39 exotic rows. The 80-entry
  pre-race card was purged first.
* DB backup: `scripts/racing_full.db.pre-ded1014.bak`.
* All 71 result entries join to a logged prediction (race + program + name).
* The 9 logged horses with no outcome are all on the chart's scratch lists:
  R2 #1, R3 #10/#11/#12, R5 #2, R7 #7/#12, R8 #11/#12.
* There were 2 DNF (eased): R5 #3 Here Comes Hellcat and R8 #7 Saint Ronin.
  They count as starters and are ranked last.
* `score_predictions.py`: 71 scored rows. The official top pick was ITM in
  2/6 races; the two top picks that scratched were R2 Playing Hardball and
  R3 Preach It Sister.

## Per race (re-ranked among horses that ran)

Bets checked:
* **Tri-box key:** the model's top 3 boxed in 1st–3rd, with ALL underneath for 4th.
* **Super box:** a straight 4-horse box of the model's top 4.

| R | | model top 4 | actual 1-2-3-4 | model #1 fin | top-3 overlap | tri-box key | super box |
|---|---|---|---|---|---|---|---|
| 1 | post | 7-5-3-1 | 7-4-5-6 | **1st** | 2/3 | miss | miss |
| 2 | post | 6-9-8-2 | 2-4-8-9 | 8th | 1/3 | miss | miss |
| 3 | post | 2-1-5-7 | 1-6-2-9 | **3rd** | 2/3 | miss | miss |
| 4 | post | 5-1-8-7 | 8-2-1-3 | 8th | 2/3 | miss | miss |
| 5 | pre | 7-1-4-6 | 5-4-6-1 | 5th | 1/3 | miss | miss |
| 6 | pre | 2-3-5-4 | 5-2-7-4 | **2nd** | 2/3 | miss | miss |
| 7 | pre | 10-2-1-3 | 3-1-4-2 | 7th | 1/3 | miss | miss |
| 8 | pre | 3-5-4-9 | 6-4-5-2 | 5th | 2/3 | miss | miss |

**Model:** the #1 pick won 1 race and hit the board in 3/8 (R1–R4 2/4,
R5–R8 1/4). Top-3 overlap was 13/24. The tri-box key hit 0/8 and the super
box 0/8, so a 4th-place subset never came into play. A base-only ranking
(no reranker) would have had 4/8 #1 ITM; the difference is R2, below.

## Reranker moves over 5 points

| R | horse | base → final | rank (base → final) | finished |
|---|---|---|---|---|
| 1 | #7 Thats Unbelievable | 52.0 → 58.3 (+6.3) | 1 → 1 | **1st** |
| 2 | #8 Castle Island | 27.6 → 33.5 (+5.9) | 4 → 3 | **3rd** |
| 2 | #2 Steady On | 35.0 → 27.1 (−7.9) | **1 → 4** | **1st** |
| 3 | #5 Secret Rolls | 37.0 → 30.3 (−6.6) | 2 → 3 | 9th |
| 5 | #7 Uthinkshecanrun | 59.0 → 67.8 (+8.8) | 1 → 1 | 5th |
| 8 | #6 Don'tstopthaspirit | 27.4 → 20.5 (−6.9) | 4 → 6 | **1st** |

Three moves went the right way and three the wrong way. The costly one is R2:
the reranker demoted the base #1 (among runners), and that horse won. One card;
this is a reading, not evidence.

## Low-coverage (<65%) horses

12 of the 71 starters were under 65% coverage, and 6 of them finished in the
money. Their summed P(ITM) was 3.86, so they produced 6 ITM against 3.9
expected. All of R5 was under 65%: it was a 2yo maiden claimer, every horse a
shipper.

| R | horse | cov | model rank | P(ITM) | finished |
|---|---|---|---|---|---|
| 1 | #4 Annie's Allie | 50% | 7 | 22.1 | **2nd** |
| 3 | #5 Secret Rolls | 54% | 3 | 30.3 | 9th |
| 3 | #9 Melissa Gale | 59% | 8 | 18.4 | 4th |
| 5 | #7 Uthinkshecanrun | 63% | 1 | 67.8 | 5th |
| 5 | #1 Brilliant Deal | 53% | 2 | 42.4 | 4th |
| 5 | #4 Olympiad's Choice | 57% | 3 | 40.7 | **2nd** |
| 5 | #6 Swiftly Engaged | 61% | 4 | 39.2 | **3rd** |
| 5 | #5 Cairo's Chic | 53% | 5 | 37.6 | **1st** |
| 5 | #3 Here Comes Hellcat | 57% | 6 | 27.6 | DNF |
| 7 | #3 Discerner | 59% | 4 | 24.3 | **1st** |
| 8 | #6 Don'tstopthaspirit | 63% | 6 | 20.5 | **1st** |
| 8 | #8 Fulton | 64% | 10 | 15.2 | 8th |

## Don's picks (benchmark; `tracking/don_picks.csv`)

Re-ranked around scratches the same way. R3 #10 scratched, so his alt #2 moves
up to 4th. R5 #2 scratched, so his alt #4 moves up.

| R | Don (re-ranked) | Don #1 fin | Don top-3 overlap | model #1 fin | model top-3 overlap |
|---|---|---|---|---|---|
| 1 | 4-1-3-5 | 2nd | 1/3 | 1st | 2/3 |
| 2 | 8-5-3-2 | 3rd | 1/3 | 8th | 1/3 |
| 3 | 5-1-8-2 | 9th | 1/3 | 3rd | 2/3 |
| 4 | 5-6-1-2 | 8th | 1/3 | 8th | 2/3 |
| 5 | 7-5-6-4 | 5th | 2/3 | 5th | 1/3 |
| 6 | 8-5-2-3 | 6th | 2/3 | 2nd | 2/3 |
| 7 | 4-10-2-3 | 3rd | 1/3 | 7th | 1/3 |
| 8 | 6-4-3-5 | **1st** | 2/3 | 5th | 2/3 |

| | #1 wins | #1 ITM | top-3 overlap | tri-box | super box |
|---|---|---|---|---|---|
| Model | 1 | 3/8 | 13/24 | 0 | 0 |
| Don | 1 | 4/8 | 11/24 | 0 | 0 |

Don and the model had the same top pick in R4 (#5 Parisi, 8th) and R5
(#7 Uthinkshecanrun, 5th).

## Watch list

Added Discerner (`tracking/watch_list.csv`). Check a newly loaded card with
`python scripts_dpv1/tracking/check_watch_list.py --track DED --date <date>`.
