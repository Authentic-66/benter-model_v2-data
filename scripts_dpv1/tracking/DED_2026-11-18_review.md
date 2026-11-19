# DED 2026-11-18 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Fifteenth
card on 1.3.2, **ninth with name matching ON**. One logged run, the record:
`generated_at = 2026-11-18T08:06:53`, pre-race, bridged, 77 rows (full
fields), commit `72a1f1d` (`picks/DED_2026-11-18_20261118-0806.*`). Doug ran
runbook B himself; verified 11/19 (backup, load, watch check, frozen-par
speed recompute = 0 diffs, 326,636 rows, snapshot). The side-by-side was run
11/19 before the chart load: **clean, streak 3 of 14**.

Read-only on the live model: no changes to 1.3.2, the rerankers or the
Piece 1–4 code.

**R6 was cancelled** ("Cancelled - Management Decision" on the chart), so
this is a **7-race card**. R6's eight predictions have no outcome and are not
scored.

## Pre-race

* **Picks:** model logged 08:06 CST (Doug's run). The reranker #1 changes
  (R3, R4) and the high-confidence qualifiers (R6, R7) were **not** written
  to the tracking files pre-race; they are added at scoring from the record
  run, with the values as logged (notes say so).
* **Don:** picks, POD, EP4 and LP4 received **4:38 PM CST, before the first
  post** (chart R1 off 4:42).
* **Doug: did not handicap 11/18.** Logged as missing (`doug_picks.csv`,
  blank picks, `MISSING` note); **no consensus races**.
* **Scratches (from the chart):** R1 #8 Adieu Aces (vet; model 4th, Don's
  3rd), R2 #10 Moon Trip (stewards), **#11 Seeking Aces (also-eligible; the
  model's #1 at 58.4 and Don's 2nd)**, #12 Taurean (AE), R3 #5 Gaming Girl
  (stewards), R4 #11 Molto Vino, #12 Agami (both AE), R5 #4 Steal Tiz One
  (vet; model 4th), R7 #6 Kai Aloha (stewards; model 4th), R8 #11 Opaque
  (AE). Ten in all.
* **Late jockey changes** (every chart rider compared with
  `pp_entries_raw.pp_jockey`; Nava-Marin's hyphen is the same rider, no
  others): **Harry Hernandez rode R1–R4, then came off all his later mounts,
  all to Elio Barrera** (R5 #5, R7 #4, R8 #10; R6, where he had #3 Mo Diva,
  was cancelled). The chart gives no reason. **No Javier A. Hernandez mounts
  on the 11/18 PP at all** (off 11/11–11/14).

## Load (2026-11-19)

* `load_chart.py` on `Delta Downs/ded-results-2026/DED111826USA.pdf`:
  `parser warning R6: horse_table_header_not_found` (the cancelled race),
  `backup verified: racing_full.db.pre-ded1118res.bak`, `+8r 59e (purged 77
  first) [replaced a pre-race card]`, `"errors": 0`, `loaded: DED 2026-11-18
  8 races, 59 entries, 58 with a finish; replaced a pre-race card of 77
  entries`. 77 − 59 = 10 scratches + R6's 8. R6 is stored as an empty race,
  the same as the cancelled MNR races.
* **One non-finisher:** R4 #10 Easy Bet (8.3-1, model 9th of 10), "showed
  early speed, dropped back and was eased to the wire" (`DNF`, scored as a
  starter off the board).
* **No DQs, no dead heats, no non-betting starters.**
* Pick payouts (per $0.50). R6 is an `ALL` leg in every pool that crossed it:

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 9-9-10 | 173.60 |
  | Pick 3 | R2–R4 | 9-10-4 | 396.40 |
  | Pick 3 | R3–R5 | 10-4-6 | 1,450.80 |
  | Pick 4 (early) | R2–R5 | 9-10-4-6 | **15,385.80** |
  | Pick 5 (early) | R1–R5 | 8/9-9-10-4-6 | 1,211.50 (4 correct) |
  | Pick 3 | R5–R7 | 6-ALL-2 | 23.15 (consolation 6-ALL $25.20 per $1) |
  | Pick 3 | R6–R8 | ALL-2-5 | 6.95 |
  | Pick 4 (late) | R5–R8 | 6-ALL-2/6-5 | 102.15 |
  | Pick 5 (late) | R4–R8 | 4-6-ALL-2/6-5 | 1,925.30 |

  `8/9` and `2/6` are scratch substitutes (R1 #8 and R7 #6 scratched).
* `score_predictions.py --track DED --date 2026-11-18`: 7 races scored, R6
  skipped (no results); 59 rows scored (2,777 total), 10 scratched, 1 DNF.
  Top pick ITM 3 of 6 on the tool's basis (R2's logged #1 scratched).

### Late jockey changes (`tracking/late_jockey_changes.csv`)

| R | horse | PP rider → rode | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 5 | #5 Nectarofthe Gods | Harry Hernandez → Elio Barrera | 5 of 6 | 39.6 | 4th | 0.5 (fav) |
| 7 | #4 Riscatto | Harry Hernandez → Elio Barrera | 2 of 7 | 49.1 | 5th | 2.6 |
| 8 | #10 Irish Punch | Harry Hernandez → Elio Barrera | **1 of 10** | 42.5 | 10th | 2.4 |

Three horses, summed P(ITM) 1.31, **ITM 0**. Across 11/05–11/18 the list
has 33 rows (summed P(ITM) 13.09, ITM 16). Harry Hernandez has seven mounts
on tonight's 11/19 card.

## Per race (re-ranked among horses that ran)

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1-9-4-5 | 9-1-5-4 | **2nd** | 2 of 8 (0.9-1 fav) | 2/3 | miss | **hit** (4 of 4) | **1-9 hit ($4.00)** | **5.34** |
| 2 | 1-2-9-7 | 9-1-6-3 | **2nd** | 3 of 9 (8.3-1) | 2/3 | miss | miss (2 of 4) | 1-2 miss | 208.84 |
| 3 | 3-6-1-4 | 10-6-7-3 | 4th | 9 of 9 (12.1-1) | 1/3 | miss | miss (2 of 4) | 3-6 miss | 74.52 |
| 4 | 6-5-8-7 | 4-2-7-5 | 6th | 7 of 10 (12.2-1) | 0/3 | miss | miss (2 of 4) | 6-5 miss | 129.39 |
| 5 | 3-7-2-6 | 6-3-2-5 | **2nd** | 4 of 6 (23.0-1) | 2/3 | miss | miss (3 of 4) | 3-7 miss | 37.28 |
| 6 | – | **cancelled** | – | – | – | – | – | – | – |
| 7 | 2-4-7-1 | 2-8-7-3 | **1st** (fav) | 1 of 7 (0.9-1) | 2/3 | miss | miss (2 of 4) | 2-4 miss | 18.55 |
| 8 | 10-3-5-7 | 5-7-3-4 | 10th | 3 of 10 (3.8-1) | 2/3 | miss | miss (3 of 4) | 10-3 miss | 44.54 |

**Model:** #1 **won 1 of 7** (R7 Rhone Valley $3.80) and was **ITM in 4 of
7** (three 2nds: R1, R2, R5). $2 win on the #1: $3.80 on $14 (−72.9%).
Top-3 overlap 11 of 21. **Its top four hit the R1 superfecta box ($5.34 for
$0.10) and its top two the R1 exacta ($4.00 for $1).**

* **R2:** the model's #1 #11 Seeking Aces was an also-eligible scratch; the
  post-scratch #1 is #1 Emily's Boy, 2nd. #9 Senor Smoke (8.3-1, model
  3rd) went wire to wire; the 0.9-1 favourite #2 Unlawful (model 2nd) ran
  5th.
* **R3:** #10 Secret Hint (12.1-1) won from the model's **last** of 9
  (P(ITM) 11.7). The reranked #1 Aloha Angel ran 4th; the base #1 Free Deal
  2nd.
* **R4 and R5:** long shots won (#4 Tiffany's Ferrari 12.2-1, model 7th;
  #6 Kissesfor Cooper 23.0-1, model 4th, trainer Cedric Carmouche Jr, new to
  the DB at the 11/18 load). The R2–R5 Pick 4 paid $15,385.80.
* **R8:** the #1 #10 Irish Punch (2.4-1, a stale-last-race shipper, LS 6/21;
  Barrera for Harry Hernandez) ran last.
* Favourites: 2 of 7 won (R1, R7); R8's 2nd, R4's and R5's 4th, R2's and
  R3's 5th.

### Reranker

Two #1 changes, both among runners (`both_ran = 1`):

| R | base #1 | finished | reranked #1 | finished | race P(ITM) log loss, base → reranked |
|---|---|---|---|---|---|
| 3 | #6 Free Deal (3.4-1) | **2nd** | #3 Aloha Angel (16.5-1) | 4th | 6.300 → 6.570 (worse) |
| 4 | #5 Radiant Rebel (1.4-1 fav) | 4th | #6 Roberts Revenge (4.4-1) | 6th | 7.054 → 6.682 (better) |

On the card the reranker cost one ITM (R3) and no wins. **Card log loss
0.6105 (base) → 0.5955 (reranked) per starter** (better in five of seven
races).

**Reranker review rule: 13 of 40** qualifying races (11/05 R4, 11/06 R4,
11/07 R6, R9, 11/12 R2, R5, R7, 11/13 R1, R4, R6, 11/14 R1, 11/18 R3, R4).
Reranked #1 **2 W / 8 ITM**, base #1 **3 W / 5 ITM**. The rule judges ITM and
log loss at 40, not wins; no reading until then.

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #4 Scooteria | 38.0 → 43.4 (+5.4) | 3 → 3 | 4th (6.4-1) |
| 1 | #7 Alterana | 29.2 → 23.9 (−5.3) | 5 → 6 | 5th |
| 2 | #1 Emily's Boy | 40.8 → 47.2 (+6.4) | 1 → 1 | **2nd** |
| 3 | #3 Aloha Angel | 41.6 → 54.4 (+12.8) | 3 → 1 | 4th (16.5-1) |
| 4 | #5 Radiant Rebel | 49.9 → 43.6 (−6.3) | 1 → 2 | 4th (1.4-1 fav) |
| 4 | #7 Lassie Bee | 24.3 → 29.6 (+5.2) | 5 → 4 | **3rd** (8.9-1) |
| 5 | #5 Nectarofthe Gods | 46.4 → 39.6 (−6.9) | 4 → 5 | 4th (0.5-1 fav) |
| 5 | #1 Flirti Birdi | 29.5 → 19.8 (−9.8) | 6 → 6 | 6th |
| 7 | #8 Mindful Keeper | 24.5 → 19.1 (−5.3) | 6 → 7 | **2nd** (8.7-1) |
| 8 | #3 Caroom's Croupier | 32.7 → 38.7 (+6.0) | 3 → 2 | **3rd** (17.5-1) |
| 8 | #5 Echo Juliet | 31.6 → 37.6 (+6.0) | 4 → 3 | **1st** (3.8-1) |

8 of 11 went the right way (Scooteria, Aloha Angel and Mindful Keeper did
not). Top-3 overlap 11 reranked vs 11 base (R8: 10-3-5 vs 10-7-3, each 2/3).

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 11/18 | 7 | 2 | 1 / 4 / $3.80 (−72.9%) | 1 / 5 / $3.80 (−72.9%) |
| 1.3.2 (10/22–11/18) | 128 | 23 | 30 / 81 / $162.40 (−36.6%) | 32 / 78 / $178.20 (−30.4%) |
| **Meet** | 180 | 28 | 47 / 110 / $273.20 (−24.1%) | 49 / 109 / $326.40 (−9.3%) |

`model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
scratches excluded): **with-reranker 76/118 vs base-only 73/118** (+3, was
+4). Top pick ITM 64.4%, win 23.7%; show ROI −14.2%. **Alert:** "top pick
ITM over last 29 races is 69.0%, above the 68% ceiling" (the same hot-run
check as 11/05–11/14; it is easing).

## High-confidence #1 forward test (`tracking/high_conf_top1.csv`)

Two qualifiers (added at scoring from the record run; Doug's run did not
log them pre-race):

| R | horse | P(ITM) | ML | final odds | finished | $2 win | $2 place |
|---|---|---|---|---|---|---|---|
| 6 | #3 Mo Diva | 65.3 | 2/1 | – | **race cancelled** | – | – |
| 7 | #2 Rhone Valley | 61.6 | 3/1 | 0.9 (fav) | **1st** | 3.80 | 3.00 |

**R6 is not graded and does not count toward the 40.** **18 of 40**
qualifying races so far: **5 W, 11 ITM, 10 in the first two**. $2 win
$22.20 on $36, $2 place $35.10 on $36. Over-4-1 subset (final odds, as
registered): still 3 races (Rhone Valley went off at 0.9-1). Pass mark: open
until Doug picks (PHASE_6D_ROADMAP), before race 40.

## Name matching ON: 11/05–11/18 vs the earlier 1.3.2 cards

Same basis as before (record run, among starters, logged P(ITM) not
renormalised; #1 re-ranked among runners; DNFs count as starters that
missed the board).

| card | name matching | races | starters | #1 W | #1 ITM | sum P(ITM) | ITM | P(ITM) LL | Brier | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.3.2 off (7 cards, 10/22–11/04) | off | 59 | 505 | 12 | 32 (54%) | 158.82 | 177 | 0.609 | 0.210 | $67.80 (−42.5%) |
| 11/05–11/14 (7 cards) | on | 62 | 502 | 17 | 45 (73%) | 173.10 | 186 | 0.6010 | 0.208 | $90.80 (−26.8%) |
| **11/18** | **on** | 7 | 59 | 1 | 4 | 18.13 | 21 | **0.5955** | **0.206** | $3.80 |
| 1.3.2 on (8 cards) | on | 69 | 561 | 18 | 49 (71%) | 191.24 | 207 | **0.6004** | **0.208** | $94.60 (−31.4%) |

ON stays just below OFF on log loss (0.6004 vs 0.609) and Brier; the card
ran a little hotter than its P(ITM) (21 ITM vs 18.13). The read-only paired
OFF/ON check from the `-run.bak` files still decides it.

## Data issues on the model's top picks (`tracking/top_pick_data_issues.csv`)

* **R8 #10 Irish Punch (10th): stale last race.** PP last race LS
  2026-06-21 (150 days, track not in the corpus); DB last race 2026-03-13
  (250 days). Also a late jockey change (Barrera for Harry Hernandez).
* **R2 #1 Emily's Boy** is the post-scratch #1 (the full-field #1 #11 Seeking
  Aces was an also-eligible scratch).
* R3 and R4 #1s are reranker picks (base #1s 2nd and 4th). R3 #3 Aloha Angel
  had one DB start (11/07).
* The other #1s had their last race in the DB (PP days off = DB days,
  12–28) and jockey and trainer history.

## Missing-last-race horses (`missing_last_race_tally.py --to 2026-11-18`)

Three flagged starters, **all no-data tracks**:

| R | horse | last race | model rank | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 1 | #6 Born Flawless | OP 2/26 | 7 of 8 | 16.8 | 6th | 63.5 |
| 7 | #8 Mindful Keeper | CD 4/25 | 7 of 7 | 19.1 | **2nd** | 8.7 |
| 8 | #10 Irish Punch | LS 6/21 | **1 of 10** | 42.5 | 10th | 2.4 |

Tonight: **no-data tracks 3 starters, ITM 1 vs 0.8 expected, W 0 vs 0.3**;
data tracks 0.

| group (11/04–11/18) | starters | ITM | exp ITM | W | exp W |
|---|---|---|---|---|---|
| data tracks | 21 | 7 | 6.5 | 1 | 2.1 |
| no-data tracks | 38 | **19** | **11.9** | 3 | 3.8 |
| both | 59 | 26 | 18.4 | 4 | 6.0 |
| all other starters | 571 | 205 | 194.6 | 73 | 65.1 |

The no-data group keeps beating its P(ITM) (19 vs 11.9); the data-track group
is on expectation.

## First-time starters

| R | first-time starters | finishes | model ranks | winner |
|---|---|---|---|---|
| 3 (MCL 20000) | #2 Fast Money Diva, #4 Sarahsrunningbayou, #9 Mac Betsy (#5 Gaming Girl scratched) | 8th (3.6-1), 7th (5.9-1), 6th (11.1-1) | 6th, 4th, 7th of 9 | #10 Secret Hint (not a first-timer) |
| 7 (MCL 20000) | #4 Riscatto, #1 Tater Time (#6 Kai Aloha scratched) | 5th (2.6-1), 7th (17.1-1) | 2nd, 4th of 7 | #2 Rhone Valley (not a first-timer) |

Tally: **12 maidens with first-time starters, a first-time starter won 4**
(R3 and R7 added, neither won).

## Low-coverage (<65%) horses

R3 #4 Sarahsrunningbayou (54%, 7th), #2 Fast Money Diva (54%, 8th), #9 Mac
Betsy (54%, 6th), #8 Something Wild (53%, 9th); R7 #4 Riscatto (54%, 5th),
#1 Tater Time (54%, 7th), #8 Mindful Keeper (64%, **2nd** at 8.7-1, the
model's last).

## Benchmarks: Don (Doug missing)

* Don lost R1 #8 (his 3rd) and R2 #11 (his 2nd) to scratches; no alts given,
  so those races have three picks.
* Don's #1 = the model's #1 only in R7.

| R | Don | Don #1 fin | Don overlap | model | model #1 fin | model overlap |
|---|---|---|---|---|---|---|
| 1 | 9-1-5 | **1st** | 3/3 | 1-9-4-5 | **2nd** | 2/3 |
| 2 | 2-1-6 | 5th | 2/3 | 1-2-9-7 | **2nd** | 2/3 |
| 3 | 1-4-7-6 | 5th | 1/3 | 3-6-1-4 | 4th | 1/3 |
| 4 | 5-2-6-4 | 4th | 1/3 | 6-5-8-7 | 6th | 0/3 |
| 5 | 5-7-3-1 | 4th | 1/3 | 3-7-2-6 | **2nd** | 2/3 |
| 7 | 2-4-7-8 | **1st** | 2/3 | 2-4-7-1 | **1st** | 2/3 |
| 8 | 7-10-5-8 | **2nd** | 2/3 | 10-3-5-7 | 10th | 2/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | 1 | **4/7** | 11/21 | 0 | **1 (R1 $5.34)** | 1 (R1 $4.00) | $3.80 on $14 (−72.9%) |
| Don | **2** | 3/7 | **12/21** | **1 (R1 $5.34)** | 0 | 1 (R1 $4.00) | $7.60 on $14 (−45.7%) |

Don's top three also hit the R1 trifecta ($6.95).

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **11/05–11/18** (name matching ON) | Model | 69 | 18 | 49 (71%) | 117/207 | −31.4% |
| | Don | 69 | 20 | 45 (65%) | 118/207 | −13.9% |
| | Doug (to 11/14) | 62 | 17 | 34 (55%) | 94/186 | −19.2% |
| **1.3.2** (10/22–11/18) | Model | 128 | 30 | 81 (63%) | 207/384 | −36.6% |
| | Don | 128 | 39 | 81 (63%) | 218/384 | −14.0% |
| | Doug | 119 | 36 | 70 (59%) | 184/357 | −15.5% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.7% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (21 cards) | Model | 180 | 47 | 110 (61%) | 284/540 | −24.1% |
| | Don | 171 | 54 | 107 (63%) | 285/513 | −10.3% |
| | Doug | 127 | 39 | 73 (57%) | 194/381 | −13.3% |
| | Doug, without best guesses | 124 | 37 | 71 (57%) | 188/372 | −16.8% |

The meet $2 win lines ($273.20 model, $306.80 Don, $220.20 Doug) match the
ticket replay (re-run 11/19 with the 11/18 card: 23 rows added, all 612
earlier rows unchanged).

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result |
|---|---|---|---|
| POD | R7 #2 Rhone Valley (ML 3/1) | – | **WON** at 0.9-1 (fav; $3.80) |
| EP4 R2–R5 | 1,2,6,11 / 1,3,4,6,7 / 2,5 / 5,7 (80 × $0.50) | $40 | lost: R2 (winner #9 Senor Smoke, 8.3-1); R3, R4, R5 also missed. #11 scratched → post-time favourite #2 (already on the ticket) |
| LP4 R5–R8 | 3,5,7 / 3,6 / 2,4,7 / 5,7,10 (54 × $0.50) | $27 | lost: R5 (winner #6 Kissesfor Cooper, 23.0-1). R6 cancelled = ALL; R7 and R8 legs hit. Paid $102.15 |

$67 on the two Pick 4s, $0 back.

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 5 | superfecta box, $0.10 | 2,3,5,7 (24 combos) | $2.40 | lost (6-3-2-5; #6 at 23.0-1 not on the ticket) |
| DED | 8 | superfecta wheel, $0.10 | 7,10 / 7,10 / 3,5 / ALL (28 combos) | $2.80 | lost (5-7-3-4; #5 won, #10 last) |

Night: **$5.20 wagered, $0 returned, −$5.20.** DED wagering $5.20,
**qualifies for the 11/18 PP rebate.**

**Bankroll** (`tracking/bankroll.csv`): from $71.31 after 11/15: −$3.85
(11/18 PP, adjustment 11/18 7:54 AM), −$5.20 (11/18 bets), −$3.85 (11/19 PP)
= **$58.41 computed, without the 11/18 rebate.** TwinSpires after buying the
11/19 PP: **$60.66** (Doug). With the 11/18 rebate posted it would be $62.26.
So the gap is **+$2.25** (rebate not yet posted) or **−$1.60** (rebate
posted); **something from 11/16–11/17 is probably missing.** Not forced: a
zero-amount `RECONCILE OPEN` row records it. **Open: Doug sends the 7-day
TwinSpires history**, which also confirms the 11/14 rebate (inferred 11/15).

## Watch list

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 4 | #7 Lassie Bee | T Ronnie Ward | 4 of 10 | 29.6 | **3rd** | 8.9 |

No Devin or Rylee Magnon, no Calhoun starters; no watch-list horses. Meet
tally after 11/18 (`watch_people_tally.csv`; logged record runs only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 42 | 4 | 17 | 13.53 | 17 | **+3.47** (was +2.76) |
| J Devin H. Magnon | 34 | 4 | 10 | 10.83 | 10 | −0.83 (no mount) |
| T Rylee Magnon | 11 | 1 | 2 | 3.67 | 2 | −1.67 (no starter) |
| T W.B. Calhoun | 19 | 4 | 9 | 6.24 | 9 | +2.76 (no starter) |

## Things that look off

1. **R6 cancelled** (management decision). The pre-race rows were purged
   at the load and R6 is an empty race. It is not scored, Mo Diva's
   high-confidence row is not graded, and the Pick pools that crossed it ran
   with an `ALL` leg (the ticket replay skips them).
2. **Harry Hernandez came off his last three mounts** (to Elio Barrera),
   with no reason in the chart. All three missed the board, including the
   model's R8 #1. He is named on seven horses tonight (11/19).
3. **Doug's run logged no reranker or high-confidence rows pre-race.** They
   are added at scoring from the record run (values exactly as logged). Not
   a data problem, but worth adding to runbook B's checklist for hand runs.
4. **Bankroll gap open** (+$2.25 / −$1.60); waiting on the 7-day history.
5. A stray `scripts/racing_full.db.ded1110-run.bak.partial` (796 MB, 11/18
   07:59:29) is left from an interrupted backup with the runbook's example
   date. Copy only, the DB is untouched. Delete it when Doug says so.

## Queued (not started)

* Read-only paired name-matching OFF/ON check, now on 11/05–11/18, from the
  `-run.bak` files.
* PP-date recency fix (top of the queue; needs the OFF/ON validation first).
* First-time-starter maiden check (12 maidens with first-time starters; a
  first-time starter won 4).
* MNR 10/05 chart: retry after 11/21. MNR 11/08–11/11 charts are on disk
  (chart archive) and held: live-DB gaps, not loaded.
