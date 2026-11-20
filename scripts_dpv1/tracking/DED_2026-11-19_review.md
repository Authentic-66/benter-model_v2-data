# DED 2026-11-19 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Sixteenth
card on 1.3.2, **tenth with name matching ON**. One logged run, the record:
`generated_at = 2026-11-19T14:27:50`, pre-race, bridged, 69 rows (full
fields), commit `0bbe60e` (`picks/DED_2026-11-19_20261119-1427.*`).
Side-by-side after the build: clean, **streak 4 of 14**.

Read-only on the live model: no changes to 1.3.2, the rerankers or the
Piece 1–4 code.

## Pre-race

* **Model:** logged 14:27 CST. Reranker #1 changes (R4, R6) and the
  high-confidence qualifiers (R3, R5, R7) were written to the tracking files
  pre-race.
* **Don:** picks, POD, EP4 and LP4 received **2:11 PM CST, before post**.
* **Doug:** R1 picks (8-5-6-7) sent **4:56 PM, after the 4:40 post** (chart R1
  off 4:41): **logged as reference only, not scored** (blank pick columns,
  picks in the note). R2 sent 4:56 (about 9 minutes before the 5:07 post) and
  R3–R8 at 5:05: valid.
* **Consensus: none scored.** R1 would have been one: Doug's note, "would have
  been consensus (#8 All Star Tout, won); my picks were after post". No other
  race had the same post-scratch #1 for all three.
* **Scratches (from the chart):** R3 #1 Uncle Eugene (vet), R4 #7 Highstakes
  Hustler (vet), **R7 #3 Same Play (vet; the model's 2nd)**, R8 #1 Izzy's
  Baby Boy and #6 Beach Blanket (stewards; Beach Blanket was the model's
  full-field 2nd and Don's 4th). Five in all; R1–R6 orders and scratches match
  Doug's list.
* **Late jockey changes** (every chart rider compared with
  `pp_entries_raw.pp_jockey`; Nava-Marin's hyphen is the same rider): **one,
  R7 #5 Sweet Fantasy, Devin H. Magnon → Casey Fusilier.** The chart gives
  no reason. **Harry Hernandez rode all seven of his PP mounts** (R1–R7), the
  day after coming off his last three on 11/18.

## Load (2026-11-20)

* `load_chart.py` on `Delta Downs/ded-results-2026/DED111926USA.pdf`:
  `backup verified: racing_full.db.pre-ded1119res.bak`, `+8r 64e (purged 69
  first) [replaced a pre-race card]`, `"errors": 0`, `loaded: DED 2026-11-19
  8 races, 64 entries, 63 with a finish; replaced a pre-race card of 69
  entries`. 69 − 64 = the 5 scratches.
* **One non-finisher:** R2 #1 Don'tstopthaspirit (19.6-1, model 3rd of 10),
  "always raced in the back, pulled up down the final stretch and walked off"
  (`DNF`, scored as a starter off the board).
* **No DQs, no dead heats, no non-betting starters.**
* Pick payouts (per $0.50):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 8-2-3 | 16.75 |
  | Pick 3 | R2–R4 | 2-3-6 | 23.60 |
  | Pick 3 | R3–R5 | 3-6-1 | 12.25 |
  | Pick 4 (early) | R2–R5 | 2-1/3-6-1 | **39.30** |
  | Pick 5 (early) | R1–R5 | 8-2-1/3-6-1 | 131.45 |
  | Pick 3 | R4–R6 | 6-1-1 | 21.00 |
  | Pick 3 | R5–R7 | 1-1-5 | 15.05 |
  | Pick 3 | R6–R8 | 1-5-9 | 59.05 |
  | Pick 4 (late) | R5–R8 | 1-1-3/5-9 | **104.00** |
  | Pick 5 (late) | R4–R8 | 6-1-1-3/5-9 | 400.55 |

  `1/3` and `3/5` are scratch substitutes (R3 #1 and R7 #3 scratched).
* `score_predictions.py --track DED --date 2026-11-19`: 8 races, 64 rows
  scored (2,841 total), 5 scratched, 1 DNF. Top pick ITM 7 of 8, WIN 5 of 8.

### Late jockey changes (`tracking/late_jockey_changes.csv`)

| R | horse | PP rider → rode | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 7 | #5 Sweet Fantasy | Devin H. Magnon → Casey Fusilier | **1 of 6** | 64.5 | **1st** | 2.0 (fav) |

One horse, ITM 1. Across 11/05–11/19 the list has 34 rows (summed P(ITM)
13.73, ITM 17).

## Per race (re-ranked among horses that ran)

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 8-6-5-1 | 8-5-4-6 | **1st** | 1 of 8 (2.1-1) | 2/3 | miss | miss (3 of 4) | 8-6 miss | 23.23 |
| 2 | 3-9-1-6 | 2-3-5-6 | **2nd** | 8 of 10 (2.4-1 fav) | 1/3 | miss | miss (2 of 4) | 3-9 miss | 174.70 |
| 3 | 3-5-7-2 | 3-6-9-7 | **1st** (fav) | 1 of 8 (0.9-1) | 1/3 | miss | miss (2 of 4) | 3-5 miss | 274.20 |
| 4 | 6-8-1-5 | 6-1-8-2 | **1st** | 1 of 7 (2.6-1) | 3/3 | **hit** | miss (3 of 4) | 6-8 miss | 28.13 |
| 5 | 1-5-8-3 | 1-3-6-7 | **1st** (fav) | 1 of 8 (1.1-1) | 1/3 | miss | miss (2 of 4) | 1-5 miss | 24.78 |
| 6 | 6-3-1-8 | 1-4-5-8 | 6th | 3 of 8 (2.7-1 fav) | 1/3 | miss | miss (2 of 4) | 6-3 miss | 62.55 |
| 7 | 5-6-2-1 | 5-2-6-4 | **1st** (fav) | 1 of 6 (2.0-1) | 3/3 | **hit** | miss (3 of 4) | 5-6 miss | 15.57 |
| 8 | 5-2-9-4 | 9-5-4-10 | **2nd** (fav) | 3 of 9 (5.3-1) | 2/3 | miss | miss (3 of 4) | 5-2 miss | 201.39 |

**Model:** #1 **won 5 of 8** (R1, R3, R4, R5, R7) and was **ITM in 7 of 8**.
$2 win on the #1: $27.40 on $16 (**+71.2%**). Top-3 overlap 14 of 24. Top
three hit the **R4 trifecta ($53.10) and R7 trifecta ($31.75)** and both
top-3 wheels ($28.13 + $15.57 for $0.10). No exacta, no superfecta box.
Five #1 winners ties 10/17 (5 of 10) for the most on a card this meet.

* **R2:** the #1 #3 Polar Wolf (7.6-1; +9.4 from the reranker) ran 2nd. The
  winner #2 Donegal Light (2.4-1 fav, ML 8/1) was the model's **8th of 10**
  (25.2): wire to wire on the rail.
* **R6:** the only #1 off the board. #1 Jabran (2.7-1 fav, model 3rd) went
  gate to wire; both the reranked #1 Castle Island (6th) and the base #1 Call
  My Banker (5th) missed.
* **R8:** #5 Ampitup (0.9-1) dueled to the wire and was outfinished by
  #9 You Good (5.3-1, model 3rd; Don's POD).
* Favourites: 5 of 8 won (R2, R3, R5, R6, R7); R8's 2nd, R1's and R4's 4th.

### Reranker

Two #1 changes, both among runners (`both_ran = 1`):

| R | base #1 | finished | reranked #1 | finished | race P(ITM) log loss, base → reranked |
|---|---|---|---|---|---|
| 4 | #8 Powerful (13.2-1) | 3rd | **#6 Chupapi Munyayo (2.6-1)** | **1st** | 3.858 → 3.616 (better) |
| 6 | #3 Call My Banker (3.6-1) | 5th | #6 Castle Island (3.1-1) | 6th | 5.235 → 5.685 (worse) |

The reranker gained a win in R4 and lost nothing in R6 (both off the
board). **Card log loss 0.6037 (base) → 0.6047 (reranked) per starter**
(better in R1, R2, R4, R5; worse in R3, R6, R7, R8).

**Reranker review rule: 15 of 40** qualifying races (adds 11/19 R4, R6).
Reranked #1 **3 W / 9 ITM**, base #1 **3 W / 6 ITM**. The rule judges ITM
and log loss at 40, not wins; no reading until then.

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 2 | #3 Polar Wolf | 45.4 → 54.8 (+9.4) | 1 → 1 | **2nd** (7.6-1) |
| 3 | #3 Debriseason | 63.0 → 68.2 (+5.1) | 1 → 1 | **1st** (0.9-1) |
| 3 | #7 Minimus Maximus | 36.1 → 42.0 (+5.9) | 4 → 3 | 4th (5.2-1) |
| 3 | #4 Our Shining Star | 13.2 → 7.4 (−5.7) | 7 → 8 | 7th |
| 4 | #6 Chupapi Munyayo | 50.3 → 59.6 (+9.3) | 2 → 1 | **1st** (2.6-1) |
| 5 | #1 Epic Stolen Kiss | 71.1 → 78.8 (+7.7) | 1 → 1 | **1st** (1.1-1) |
| 6 | #6 Castle Island | 46.3 → 54.6 (+8.3) | 2 → 1 | 6th (3.1-1) |
| 6 | #5 Field Study | 36.2 → 30.8 (−5.4) | 5 → 6 | **3rd** (5.3-1) |

5 of 8 went the right way (Minimus Maximus, Castle Island and Field Study
did not). Top-3 overlap 14 reranked vs 15 base (R3: 3-5-7 vs 3-5-6, R8:
5-2-9 vs 5-2-4).

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 11/19 | 8 | 2 | 5 / 7 / $27.40 (+71.2%) | 4 / 7 / $20.20 (+26.2%) |
| 1.3.2 (10/22–11/19) | 136 | 25 | 35 / 88 / $189.80 (−30.2%) | 36 / 85 / $198.40 (−27.1%) |
| **Meet** | 188 | 30 | 52 / 117 / $300.60 (−20.1%) | 53 / 116 / $346.60 (−7.8%) |

`model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
scratches excluded): **with-reranker 83/126 vs base-only 80/126** (+3, as
before). Top pick ITM 65.9%, win 26.2%; show ROI −11.5%. **Alert:** "top pick
ITM over last 29 races is 72.4%, above the 68% ceiling" (the same hot-run
check as 11/05–11/18; back up after this card).

## High-confidence #1 forward test (`tracking/high_conf_top1.csv`)

Three qualifiers, all logged pre-race:

| R | horse | P(ITM) | ML | final odds | finished | $2 win | $2 place |
|---|---|---|---|---|---|---|---|
| 3 | #3 Debriseason | 68.2 | 2/1 | 0.9 (fav) | **1st** | 3.80 | 2.60 |
| 5 | #1 Epic Stolen Kiss | 78.8 | 9/5 | 1.1 (fav) | **1st** | 4.20 | 2.20 |
| 7 | #5 Sweet Fantasy | 64.5 | 3/1 | 2.0 (fav) | **1st** | 6.00 | 4.00 |

**R4 #6 Chupapi Munyayo (59.6) won at 2.6-1 but is below the 60% line: not
a qualifier.** Sweet Fantasy was ridden by Casey Fusilier, not Devin Magnon
as on the PP.

**21 of 40** qualifying races so far: **8 W, 14 ITM, 13 in the first two**.
$2 win $36.20 on $42 (−13.8%), $2 place $43.90 on $42 (+4.5%). Over-4-1
subset (final odds, as registered): still 3 races (none tonight over 4-1 on
final odds or ML). Pass mark: open until Doug picks (PHASE_6D_ROADMAP),
before race 40.

## Name matching ON: 11/05–11/19 vs the earlier 1.3.2 cards

Same basis as before (record run, among starters, logged P(ITM) not
renormalised; #1 re-ranked among runners; DNFs count as starters that
missed the board).

| card | name matching | races | starters | #1 W | #1 ITM | sum P(ITM) | ITM | P(ITM) LL | Brier | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.3.2 off (7 cards, 10/22–11/04) | off | 59 | 505 | 12 | 32 (54%) | 158.82 | 177 | 0.609 | 0.210 | $67.80 (−42.5%) |
| **11/19** | **on** | 8 | 64 | 5 | 7 | 22.29 | 24 | 0.6047 | 0.206 | $27.40 |
| 1.3.2 on (9 cards, 11/05–11/19) | on | 77 | 625 | 23 | 56 (73%) | 213.53 | 231 | **0.6008** | **0.207** | $122.00 (−20.8%) |

ON stays just below OFF on log loss (0.6008 vs 0.609) and Brier. The
read-only paired OFF/ON check from the `-run.bak` files still decides it.

## Data issues on the model's top picks (`tracking/top_pick_data_issues.csv`)

None. All eight post-scratch #1s had their last race in the DB (PP days off =
DB days, 15–36, except R3 Debriseason at 152 days, DED 6/20, also in the DB)
and jockey and trainer history. R4 and R6 #1s are reranker picks; R7 #5 had
the late jockey change.

## Missing-last-race horses (`missing_last_race_tally.py --to 2026-11-19`)

Four flagged starters, **all no-data tracks**:

| R | horse | last race | model rank | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 2 | #4 Liamster | AQU 2/12 (no DB history) | 9 of 10 | 15.6 | 6th | 20.1 |
| 4 | #8 Powerful | Europe 10/25 | 2 of 7 | 52.5 | **3rd** | 13.2 |
| 7 | #4 Ridgewood Runner | RP 9/27 (no DB history) | 5 of 6 | 27.4 | 4th | 2.3 |
| 7 | #7 Otello | KEE 10/10 | 6 of 6 | 25.0 | 6th | 12.2 |

Tonight: **no-data tracks 4 starters, ITM 1 vs 1.2 expected, W 0 vs 0.4**;
data tracks 0.

| group (11/04–11/19) | starters | ITM | exp ITM | W | exp W |
|---|---|---|---|---|---|
| data tracks | 21 | 7 | 6.5 | 1 | 2.1 |
| no-data tracks | 42 | **20** | **13.1** | 3 | 4.2 |
| both | 63 | 27 | 19.6 | 4 | 6.4 |
| all other starters | 631 | 228 | 215.6 | 81 | 72.2 |

Tonight the no-data group ran to its P(ITM); over the stretch it still
beats it (20 vs 13.1). The data-track group is on expectation.

## First-time starters

| R | first-time starters | finishes | model ranks | winner |
|---|---|---|---|---|
| 5 (MSW 35000, 2yo fillies) | #3 Prideof Heaven, #4 Eme's Party Gal, #7 Global Warrior | **2nd** (1.9-1), 8th (44.1-1), 4th (3.7-1) | 4th, 5th, 6th of 8 | #1 Epic Stolen Kiss (not a first-timer) |

Tally: **13 maidens with first-time starters, a first-time starter won 4**
(R5 added; Prideof Heaven "just missed" at 1.9-1). R3 (MCL 20000) had none.

## Low-coverage (<65%) horses

R5's three first-time starters (53%): #3 Prideof Heaven **2nd**, #7 Global
Warrior 4th, #4 Eme's Party Gal 8th.

## Benchmarks: Don and Doug

* Don lost R8 #6 Beach Blanket (his 4th) to a scratch: three picks left.
* Doug's R1 is not scored (sent after post), so his line has 7 races.
* The model's #1 = Don's #1 in R1 only; = Doug's #1 in R3 and R6.

| R | Don | Don #1 fin | Don ov | Doug | Doug #1 fin | Doug ov | model | model #1 fin | model ov |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 8-6-1-5 | **1st** | 1/3 | (8-5-6-7, ref. only) | – | – | 8-6-5-1 | **1st** | 2/3 |
| 2 | 6-9-2-8 | 4th | 1/3 | 4-9-6-2 | 6th | 0/3 | 3-9-1-6 | **2nd** | 1/3 |
| 3 | 8-3-5-7 | 8th | 1/3 | 3-5-7-8 | **1st** | 1/3 | 3-5-7-2 | **1st** | 1/3 |
| 4 | 2-1-6-5 | 4th | 2/3 | 1-2-8-6 | **2nd** | 2/3 | 6-8-1-5 | **1st** | 3/3 |
| 5 | 7-1-6-2 | 4th | 2/3 | 3-1-2-7 | **2nd** | 2/3 | 1-5-8-3 | **1st** | 1/3 |
| 6 | 1-6-3-7 | **1st** | 1/3 | 6-1-3-2 | 6th | 1/3 | 6-3-1-8 | 6th | 1/3 |
| 7 | 4-2-6-5 | 4th | 2/3 | 6-4-5-7 | **3rd** | 2/3 | 5-6-2-1 | **1st** | 3/3 |
| 8 | 9-5-4 | **1st** | 3/3 | 4-5-8-2 | **3rd** | 2/3 | 5-2-9-4 | **2nd** | 2/3 |

| | races | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|
| Model | 8 | **5** | **7** | **14/24** | **2 (R4 $28.13, R7 $15.57)** | 0 | 0 | **$27.40 on $16 (+71.2%)** |
| Don | 8 | 3 | 3 | 13/24 | 1 (R8 **$201.39**) | 1 (R7 $15.57) | 1 (R8 $20.40) | $26.20 on $16 (+63.7%) |
| Doug | 7 | 1 | 5 | 10/21 | 0 | 1 (R4 $28.13) | 1 (R5 $4.50) | $3.80 on $14 (−72.9%) |

Don's top three also hit the R8 trifecta ($35.30); the model's the R4 and R7
trifectas ($53.10, $31.75).

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **11/05–11/19** (name matching ON) | Model | 77 | 23 | 56 (73%) | 131/231 | −20.8% |
| | Don | 77 | 23 | 48 (62%) | 131/231 | −5.8% |
| | Doug | 69 | 18 | 39 (57%) | 104/207 | −24.6% |
| **1.3.2** (10/22–11/19) | Model | 136 | 35 | 88 (65%) | 221/408 | −30.2% |
| | Don | 136 | 42 | 84 (62%) | 231/408 | −9.4% |
| | Doug | 126 | 37 | 75 (60%) | 194/378 | −18.7% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.7% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (22 cards) | Model | 188 | 52 | 117 (62%) | 298/564 | −20.1% |
| | Don | 179 | 57 | 110 (61%) | 298/537 | −7.0% |
| | Doug | 134 | 40 | 78 (58%) | 204/402 | −16.4% |
| | Doug, without best guesses | 131 | 38 | 76 (58%) | 198/393 | −19.8% |

The meet $2 win lines ($300.60 model, $333.00 Don, $224.00 Doug) match the
ticket replay (re-run 11/20 with the 11/19 card: 34 rows added, all 635
earlier rows unchanged).

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result |
|---|---|---|---|
| POD | R8 #9 You Good (ML 8/1) | – | **WON** at 5.3-1 ($12.60) |
| EP4 R2–R5 | 2,6,9 / 3,5,8 / 1,2,6 / 1,7 (54 × $0.50) | $27 | **HIT** 2-3-6-1: **$39.30** |
| LP4 R5–R8 | 1,7 / 1,3,6 / 2,4,5,6 / 5,9 (48 × $0.50) | $24 | **HIT** 1-1-5-9: **$104.00** |

$51 on the two Pick 4s, **$143.30 back** (+181%). Scratches on the LP4 legs
(R7 #3, R8 #1/#6) were not on his ticket.

### Doug's bets (`tracking/doug_bets.csv`)

| track | date | R | bet | ticket | cost | result |
|---|---|---|---|---|---|---|
| MNR | 11/17 | 4 | superfecta part-wheel, $0.20 | 9 / 7 / 2,8 / 2,3,5-9 (8 combos) | $1.60 | lost (personal; reported 11/20) |
| DED | 11/19 | 2 | $2 win | #4 Liamster | $2.00 | lost (6th at 20.1-1; ML 8/1) |

DED 11/19 wagering $2.00: **qualifies for the 11/19 PP rebate.**

**Bankroll** (`tracking/bankroll.csv`), **reconcile CLOSED**. The 11/19
gap was the unlogged 11/17 MNR bet (−$1.60) plus the 11/18 rebate
(+$3.85, adjustment 11/19 3:29 AM). From $71.31 after 11/15: −1.60 (MNR
11/17), −3.85 (11/18 PP), −5.20 (11/18 bets), +3.85 (11/18 rebate), −3.85
(11/19 PP, 2:10 PM) = **$60.66 = TwinSpires** after the 11/19 PP purchase;
then −2.00 (11/19 R2), +3.85 (11/19 rebate, overnight 11/20, inferred from
the balance) = **$62.51 = TwinSpires**. The open-difference row is removed.
The 11/20 PP purchase (−$3.85) is logged when Doug buys it.

## Watch list

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 7 | #5 Sweet Fantasy | J Devin H. Magnon (on the PP) | 1 of 6 | 64.5 | **1st** | 2.0 |

**Magnon did not ride**: Casey Fusilier replaced him, so the mount does not
count in his tally (the tally reads the chart's rider). No Ward, Rylee
Magnon or Calhoun starters. Meet tally after 11/19
(`watch_people_tally.csv`; logged record runs only), all unchanged:

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 42 | 4 | 17 | 13.53 | 17 | +3.47 |
| J Devin H. Magnon | 34 | 4 | 10 | 10.83 | 10 | −0.83 |
| T Rylee Magnon | 11 | 1 | 2 | 3.67 | 2 | −1.67 |
| T W.B. Calhoun | 19 | 4 | 9 | 6.24 | 9 | +2.76 |

**Trip note (Doug):** R4 #6 Chupapi Munyayo came from last on the
backstretch to win. Chart: 7th of 7 at the start, 1/4 and 1/2, 5th by 3 in
the stretch, **won by 3/4 length** (Doug had about half); "void of early
speed ... made a wide rally, five wide and proved the best". **Added to
`watch_list.csv`** (as Blue Heavenly was on 11/14).

## Stablemate entries (new, read-only: `stablemate_tally.py`)

One trainer with 2+ runners in a race: `tracking/stablemate_entries.csv`
(one row per runner: ML, final odds, finish), backfilled from the 10/09
chart on (the 10/09 and 10/31 cards have no PP file, so no ML).

Tonight:

| R | trainer | runners (ML → final, finish) | backed one ahead? |
|---|---|---|---|
| 2 | Dane Noel (Donegal Racing) | #2 Donegal Light (8/1 → 2.4, **1st**); #4 Liamster (8/1 → 20.1, 6th) | yes |
| 3 | Samuel Breaux | #3 Debriseason (2/1 → 0.9, **1st**); #4 Our Shining Star (20/1 → 40.6, 7th) | yes |
| 6 | Juan Munoz Cano | #6 Castle Island (5/1 → 3.1, 6th); #5 Field Study (15/1 → 5.3, **3rd**) | **no** |
| 8 | Juan Larrosa | #5 Ampitup (3/1 → 0.9, **2nd**); #8 Aller Vite (5/1 → 8.8, 5th) | yes |

Doug listed R2 and R6. R3 and R8 are also two-runner stables. Liamster's
ML on the PP is 8/1, the same as Donegal Light's; 20.1-1 was his final
price.

**Meet (10/09–11/19): 104 races with a trainer running two or more.** In
the 102 with different final odds, **the more heavily backed stablemate
finished ahead in 68 (67%)**. That is the **same rate as any two runners
in the same race** (shorter price ahead in 4,419 of 6,516 pairs, 68%). So
the market's preference within a stable is right about as often as it is
anywhere else: no sign of a stable edge either way. Backed ones: 23 W / 50
ITM of 102 ($2 win $201.00 on $204). Others: 7 W / 23 ITM of 102 ($304.80 on
$204, carried by a few long-priced winners: Tarkington Girl 45.2, Mo Sippi
42.6, Secret Injustice 16.4, Grey Street 24.1). Small sample; no action.

## Things that look off

1. **Late jockey change on a high-confidence #1**: Magnon off R7 #5 Sweet
   Fantasy (won with Fusilier). No reason in the chart.
2. **Doug's R1 picks came after post**: reference only. Nothing to fix; R1
   just is not scored for Doug and there is no consensus race.
3. **R2 winner #2 Donegal Light was the model's 8th of 10** (ML 8/1, bet to
   2.4-1 fav). The market moved hard on it; the model had nothing.
4. The `-run.bak.partial` from 11/18 (`scripts/racing_full.db.ded1110-run.bak.partial`)
   is still on disk, waiting on Doug.

## Queued (not started)

* Read-only paired name-matching OFF/ON check, now on 11/05–11/19, from the
  `-run.bak` files.
* PP-date recency fix (top of the queue; needs the OFF/ON validation first).
* First-time-starter maiden check (13 maidens with first-time starters; a
  first-time starter won 4).
* MNR 10/05 chart: retry after 11/21. MNR 11/08–11/11 charts are on disk
  (chart archive) and held: live-DB gaps, not loaded.
