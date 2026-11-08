# DED 2026-11-07 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Tenth card
on 1.3.2, **third with name matching ON**. One logged run, the record:
`generated_at = 2026-11-07T09:54:15`, pre-race, bridged, 87 rows (full
fields), commit `4a2548d` (`picks/DED_2026-11-07_20261107-0954.*`).

This pass is read-only on the live model: no changes to 1.3.2, the
rerankers or Piece 1–4 code.

The morning's chart load (`a5b7f1e`: CT 5/1, EVD 6/11, FG 2/15 and 51 MNR
charts) ran **after** the record run, so tonight's predictions did not see
it.

## Pre-race

* **Picks logged before post:** model 09:54 CST, Don received 09:37
  (`702e6f5`), Doug (`6a4b242`). The high-confidence qualifier (R4 #2) was
  logged with the card (`4a2548d`).
* **Scratches (Doug's list, all confirmed by the chart):** R1 #11; R2 #7
  (the model's #1) and #9 (Doug's #1); R3 #11, #12; R5 #2; R6 #1 (the
  model's #1, Calhoun), #4, #6; R7 #6 (the model's #1); R8 #11; R9 #9.
  **No others.** Chart reasons: vet R2 #7, #9, R5 #2, R6 #1, #4, #6, R7
  #6; also-eligible R1 #11, R3 #11, #12, R8 #11; stewards R9 #9.
* **Late jockey changes (Doug's list, no others on the chart):** Jansen
  Melancon off R4 #4 Ayzee, R6 #5 Highland Creek (Casey Fusilier) and R8 #9
  Von Erich (Alex Birzer).

### Consensus (post-scratch rule, Doug 11/05)

| R | model | Don | Doug | consensus |
|---|---|---|---|---|
| 1 | 6 | 4 | 5 | no |
| 2 | 5 (#7 scratched) | 2 | 8 (#9 scratched) | no |
| 3 | 5 | 10 | 10 | no |
| 4 | 2 | 2 | 2 | **#2 Liteupthenite** |
| 5 | 5 | 1 | 3 | no |
| 6 | 5 (#1 scratched) | 5 | 2 | no |
| 7 | 2 (#6 scratched) | 4 | 4 | no |
| 8 | 3 | 3 | 1 | no |
| 9 | 3 | 10 | 3 | no |

## Load (2026-11-07 night)

* Chart `Delta Downs/ded-results-2026/DED110726USA.pdf`, read with the
  standard chart parser (pdfplumber). 9 races, 75 starters, 46 exotic rows.
  The 87-entry pre-race card was purged first. 0 errors.
* DB backup: `scripts/racing_full.db.pre-ded1107res.bak`, verified before
  the load: same sha256 as the live DB, `integrity_check` ok on both, and the
  same row counts in six tables.
* Spot checks: **R1 official 10-5-2-6 and R9 2-4-5-10, as expected.**
* **No DQs, no dead heats, no non-betting starters, no non-finishers.**
  Crossing order = official in every race.
* Speed figures and features were not rebuilt (the next card's build does
  that).
* Pick payouts (per $0.50, all on full legs, no scratch substitutes):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 10-8-8 | 173.45 |
  | Pick 3 | R2–R4 | 8-8-8 | 413.15 |
  | Pick 3 | R3–R5 | 8-8-1 | 725.65 |
  | Pick 4 (early) | R2–R5 | 8-8-8-1 | **1,945.35** |
  | Pick 5 (early) | R1–R5 | 10-8-8-8-1 | 9,595.25 |
  | Pick 3 | R4–R6 | 8-1-5 | 77.15 |
  | Pick 3 | R5–R7 | 1-5-7 | 16.80 |
  | Pick 3 | R6–R8 | 5-7-1 | 30.95 |
  | Pick 3 | R7–R9 | 7-1-2 | 222.05 |
  | Pick 4 (late) | R6–R9 | 5-7-1-2 | **638.20** |
  | Pick 5 (late) | R5–R9 | 1-5-7-1-2 | 2,817.35 |

* `score_predictions.py --track DED --date 2026-11-07`: top pick ITM **2 of
  6**, won 0 of 6 (the logged #1 scratched in R2, R6 and R7); top-pick show
  ROI −51.7%; all horses ITM 27 of 75. 75 rows scored (2,429 total). The
  per-race table below re-ranks among the horses that ran, as usual.

### Late jockey changes (`tracking/late_jockey_changes.csv`)

| R | horse | PP rider → rode | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 4 | #4 Ayzee | Melancon → Casey Fusilier | 7 of 8 | 24.4 | **3rd** | 20.0 |
| 6 | #5 Highland Creek | Melancon → Casey Fusilier | **1 of 6** (reranked) | 45.7 | **1st** | 1.6 (fav) |
| 8 | #9 Von Erich | Melancon → Alex Birzer | 5 of 10 | 30.0 | **3rd** | 2.9 (fav) |

Three horses, summed P(ITM) 1.00, ITM 3 (all three hit the board). Across
11/05–11/07 the list has 15 rows (summed P(ITM) 5.89, ITM 8).

## Per race (re-ranked among horses that ran)

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 6-5-2-4 | 10-5-2-6 | 4th | **8 of 10** (4.8-1) | 2/3 | miss | miss (3 of 4) | 6-5 miss | 103.75 |
| 2 | 5-1-2-8 | 8-1-5-4 | **3rd** | 4 of 7 (1.5-1 fav) | 2/3 | miss | miss (3 of 4) | 5-1 miss | 13.60 |
| 3 | 5-9-10-2 | 8-2-5-6 | **3rd** | **8 of 10** (14.4-1) | 1/3 | miss | miss (2 of 4) | 5-9 miss | 442.82 |
| 4 | 2-6-1-7 | 8-6-4-1 | 6th | 6 of 8 (12.0-1) | 1/3 | miss | miss (2 of 4) | 2-6 miss | 198.31 |
| 5 | 5-3-4-8 | 1-4-9-5 | 4th | 5 of 9 (3.5-1) | 1/3 | miss | miss (2 of 4) | 5-3 miss | 99.27 |
| 6 | 5-2-9-3 | 5-8-3-2 | **1st** (fav) | 1 of 6 (1.6-1) | 1/3 | miss | miss (3 of 4) | 5-2 miss | 8.75 |
| 7 | 2-4-7-5 | 7-2-1-5 | **2nd** | 3 of 6 (1.6-1) | 2/3 | miss | miss (3 of 4) | 2-4 miss | 11.47 |
| 8 | 3-10-8-4 | 1-3-9-10 | **2nd** | **8 of 10** (5.5-1) | 1/3 | miss | miss (2 of 4) | 3-10 miss | 36.41 |
| 9 | 3-6-10-8 | 2-4-5-10 | 7th | 7 of 9 (9.0-1) | 0/3 | miss | miss (1 of 4) | 3-6 miss | 244.91 |

**Model:** #1 **won 1 of 9** (R6 Highland Creek $5.20) and was **ITM in 5
of 9**. Top-3 overlap 11 of 27. No exacta, trifecta, super box or wheel
hit; $2 win on the #1: $5.20 on $18 (−71.1%), the weakest card on 1.3.2.

* **Seven of nine favourites lost** (only R2 #8 Beamer and R6 #5 Highland
  Creek won). The model's #1 was the favourite only in R6.
* **R1:** #10 Midnight Breeze (4.8-1, model 8th of 10, last raced at Lone
  Star, not in the DB) "lacked early speed, made a late bid and got up in
  time". The model's #1 Double L's Army (3.8-1) was 4th; #4 Hint Hint (2.2-1
  fav, model 4th) 10th.
* **R3** (2yo MSW, seven first-time starters, 53% coverage each): first-time
  starters ran **1st and 2nd**: #8 Roadster Runner (14.4-1, model 8th of 10)
  and #2 Ericka's Ocean (14.6-1, model 4th). The model's #1 Golden Mist
  (raced once, 3.5-1) was 3rd. Fav #10 Golden Protocol (2.5-1, first-time
  starter, model 3rd) 7th. Exacta $215.60.
* **R4:** the consensus horse and high-confidence pick #2 Liteupthenite
  (2.7-1) "void of early speed and showed little" (6th of 8). #8 Lolaand
  Rose (12.0-1, model 6th) "drove clear and held on well"; #6 Proton Kitty
  (fav, model 2nd) 2nd.
* **R5:** the model's #1 Fierce Cat (4.9-1) had last raced at Fonner Park
  in April, a race the DB does not have (see data issues). 4th. #1 Mr.
  Goodtime (Don's #1, model 5th) won.
* **R7:** the model's #1 #6 American Know How scratched; post-scratch #1 #2
  Paynted Blue (6.1-1, last race at SWF, not in the DB) was checked in tight
  quarters and closed for 2nd. Fav #4 Old Homestead (1.1-1, model 2nd) 6th.
* **R8:** #1 Sarah's Runner (5.5-1, model 8th of 10, Doug's #1) went wire
  to wire; the model's #1 Inchhighatahundred (3.0-1) 2nd.
* **R9:** the reranked #1 #3 Miss Country (12.2-1) "always raced near the
  back" (7th). The winner #2 Karsyn's Ocean (9.0-1) was the race's only
  first-time starter (model 7th of 9); Don's POD #10 Bobby's Native One
  (1.7-1 fav) 4th.

### Reranker

Logged pre-race (full fields) the reranker changed the #1 in R2 and R9. **After
scratches, among the horses that ran, it changed the #1 in R6 and R9**:

| R | base #1 (base → final) | finished | reranked #1 (base → final) | finished |
|---|---|---|---|---|
| 2 | #5 Megans Millions | 3rd | #7 Stephanie's Maria (pre-race) | **scratched**; among runners #5 is both #1s |
| 6 | #2 Moonlight Max (44.5 → 44.1) | 4th (1.7-1) | #5 Highland Creek (42.2 → 45.7) | **1st** (1.6-1 fav, $5.20) |
| 9 | #10 Bobby's Native One (41.4 → 36.5) | 4th (1.7-1 fav) | #3 Miss Country (40.9 → 46.0) | 7th (12.2-1) |

* **R2 does not count** (Doug's note; also, among runners base and reranked
  #1 are the same horse).
* **R6 counts under the written rule, although it was not in the pre-race
  log or Doug's note.** The rule (PHASE_6D, 2026-11-01) takes both #1s
  "among the horses that ran". The full-field #1 #1 Reaux Ban Da Man
  scratched; among runners the base #1 is #2 Moonlight Max and the reranked
  #1 is #5 Highland Creek. Row added to `reranker_changes.csv`, marked
  post-scratch. **Doug to confirm.**
* Race P(ITM) log loss, summed over starters (base → reranked): R6 4.654 →
  4.761 (worse, despite the winner), R9 6.717 → 6.204 (better: #4 Sugah Gem
  17.9 → 30.6 ran 2nd).

**Reranker review rule:** **4 qualifying races** (11/05 R4, 11/06 R4, 11/07
R6, R9): reranked #1 2 W / 3 ITM, base #1 0 W / 0 ITM. 36 to go. All on
the name-matching-ON part. Without R6 it would be 3: 1 W / 2 ITM vs 0 / 0.

Net on the card: #1 wins 1 vs 0, #1 ITM 5 vs 4, overlap 11 vs 11, $2 win
$5.20 vs $0.

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #1 Regal Time | 9.4 → 14.7 (+5.2) | 10 → 9 | 9th (77.9-1) |
| 4 | #6 Proton Kitty | 56.1 → 61.8 (+5.7) | 2 → 2 | **2nd** (1.7-1) |
| 5 | #8 The Petitioner | 35.2 → 40.2 (+5.0) | 4 → 4 | 8th (5.6-1) |
| 6 | #3 Causeway Benny | 30.8 → 25.8 (−5.1) | 4 → 4 | **3rd** (7.3-1) |
| 8 | #7 Clearly Majestic | 23.8 → 29.0 (+5.3) | 8 → 6 | 7th (14.7-1) |
| 9 | #3 Miss Country | 40.9 → 46.0 (+5.1) | 2 → 1 | 7th (12.2-1) |
| 9 | #8 Elaina Reins | 39.3 → 33.8 (−5.5) | 3 → 4 | 8th (6.0-1) |
| 9 | #4 Sugah Gem | 17.9 → 30.6 (+12.7) | 8 → 6 | **2nd** (10.5-1) |

3 of 8 went the right way (Proton Kitty, Sugah Gem, Elaina Reins cut).

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 11/07 | 9 | 2 | 1 / 5 / $5.20 (−71.1%) | 0 / 4 / $0 (−100%) |
| 1.3.2 (10/22–11/07) | 85 | 14 | 18 / 49 / $100.80 (−40.7%) | 17 / 46 / $101.80 (−40.1%) |
| **Meet** | 137 | 19 | 35 / 78 / $211.60 (−22.8%) | 34 / 77 / $250.00 (−8.8%) |

`model_health --model 1.3.2` (logged basis, top-pick scratches excluded):
**with-reranker 45/76 vs base-only 42/76** (+3, as after 11/06).

## High-confidence #1 forward test (`tracking/high_conf_top1.csv`)

One qualifier tonight: R4 #2 Liteupthenite, P(ITM) 64.5, no R4 scratches,
so still the post-scratch #1. **6th** at 2.7-1: $0 win, $0 place. No other
post-scratch #1 was over 60%.

**5 of 40** qualifying races so far: 0 W, 1 place. $2 win $0 on $10, $2
place $3.40 on $10. Over-4-1 subset: 1 race (11/06 Vineaux, 4th). No reading
until 40.

## Name matching ON: 11/05–11/07 vs the earlier 1.3.2 cards

Same basis as before (record run, among starters, logged P(ITM) not
renormalised; #1 re-ranked among runners).

| card | name matching | races | starters | #1 W | #1 ITM | sum P(ITM) | ITM | P(ITM) LL | Brier | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.3.2 off (7 cards, 10/22–11/04) | off | 59 | 505 | 12 | 32 (54%) | 158.82 | 177 | 0.609 | 0.210 | $67.80 (−42.5%) |
| 11/05 | on | 8 | 61 | 3 | 7 | 21.82 | 24 | 0.622 | 0.218 | $19.20 |
| 11/06 | on | 9 | 77 | 2 | 5 | 24.27 | 27 | 0.631 | 0.218 | $8.60 |
| **11/07** | **on** | 9 | 75 | 1 | 5 | 23.12 | 27 | **0.643** | 0.227 | $5.20 |
| 1.3.2 on (3 cards) | on | 26 | 213 | 6 | 17 (65%) | 69.20 | 78 | 0.633 | 0.221 | $33.00 (−36.5%) |

**The ON cards' log loss has risen each night (0.622, 0.631, 0.643), and
all three are above every OFF card except 10/22 and 10/23.** Ranking is still
better on ON (#1 ITM 65% vs 54%). Three cards with long-priced winners (R1,
R3, R4, R8 winners all 4.8-1 or longer, model ranks 6–8) can explain it, so
this is not yet evidence against name matching. Keep reporting ON and OFF
separately.

## Data issues on the model's top picks (`tracking/top_pick_data_issues.csv`)

**Two of nine post-scratch #1s had a stale last race**, both at tracks
outside the corpus:

| R | horse | PP last race | PP days off | DB days since | finished |
|---|---|---|---|---|---|
| 5 | #5 Fierce Cat | **FON 2026-04-18** | 203 | 274 (DED 2/06) | 4th (4.9-1) |
| 7 | #2 Paynted Blue | **SWF 2026-08-30** | 69 | 301 (DED 1/10) | **2nd** (6.1-1) |

* Fierce Cat's jockey Adrian Ramos also has only 17 prior DB starts.
* Both were the model's #1, so for both the model saw a much longer layoff
  than the horse had.
* All other top picks: jockey and trainer history in the DB, PP days off =
  DB days.

## Missing-last-race horses (read-only, running tally)

Same method as the 11/06 review (latest PP race line vs the DB at run time;
scratched horses left out).

**Tonight: 4 flagged starters, all last raced at non-corpus tracks. 3 hit
the board vs 1.6 expected; 1 W vs 0.5.**

| R | horse | last race (PP) | model rank (runners) | P(ITM) | odds | finished |
|---|---|---|---|---|---|---|
| 1 | #10 Midnight Breeze | LS 2026-07-12 | 8 of 10 | 21.2 | 4.8 | **1st** |
| 5 | #5 Fierce Cat | FON 2026-04-18 | **1 of 9** | 46.5 | 4.9 | 4th |
| 7 | #1 Our Last Chance | PRM 2026-09-20 | 5 of 6 | 34.1 | 9.1 | **3rd** (not on Doug's list) |
| 7 | #2 Paynted Blue | SWF 2026-08-30 | **1 of 6** | 53.3 | 6.1 | **2nd** |

| span | starters | ITM | model expected ITM | W | model expected W |
|---|---|---|---|---|---|
| 11/04–11/06 (11/06 review) | 38 | 15 | 11.0 | 3 | 3.6 |
| 11/07 | 4 | 3 | 1.6 | 1 | 0.5 |
| **11/04–11/07** | **42** | **18** | **12.6** | 4 | 4.1 |

* Still more ITM than the model expects (18 vs 12.6), wins in line. Not
  significant on 42 starters; the same direction as before.
* Non-corpus tracks seen so far: ARP, GIL, PRM, LS, ATO, BAQ, RP, SWF, plus
  **FON, EUR and OP** (OP 2/26 and EUR were on scratched or earlier-card
  horses).
* The only corpus gap left is MNR 10/05 (retry after 11/21).

## First-time starters in tonight's maidens (for the queued maiden check)

| R | first-time starters | finishes | model ranks | winner |
|---|---|---|---|---|
| 3 (2yo MSW) | 7 of 10 (#1, #2, #4, #6, #8, #9, #10) | **1st, 2nd**, 4th, 5th, 6th, 7th, 9th | 2nd–9th | #8 Roadster Runner, 14.4-1, model 8th |
| 9 (MCL) | 1 of 9 (#2) | **1st** | 7th | #2 Karsyn's Ocean, 9.0-1 |

* R3's raced horses: #5 Golden Mist (1 start, model 1st) 3rd; #7 Powerful
  Rose (5 starts) 8th; #3 Runnellie (1 start) 10th.
* With 11/06 R3 (first-time starters 1-2-3-4): in these three maidens a
  **first-time starter won each time**, and the model's #1 (a raced horse
  each time) ran 9th, 3rd and 7th. Small, but it is the pattern the queued
  check is for.

## Low-coverage (<65%) horses

Eight starters at 51–53%: the seven R3 first-time starters and R9 #2 Karsyn's
Ocean. Two of them won (Roadster Runner, Karsyn's Ocean) and one was 2nd
(Ericka's Ocean).

## Benchmarks: Don and Doug

* All three were logged before post.
* Scratches: **Don** lost his R6 3rd (#1), R7 2nd (#6) and R9 4th (#9); no
  alts given. **Doug** lost his R2 #1 (#9) and 4th (#7), R3 4th (#12) and
  R6 4th (#1).
* Doug's picks were all regular picks (no passes, no best guesses).

| R | Don (re-ranked) | Don #1 fin | Don overlap | Doug | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 4-2-5-6 | 10th | 2/3 | 5-2-6-10 | **2nd** | 2/3 | 4th | 2/3 |
| 2 | 2-1-4-8 | 5th | 1/3 | 8-1 | **1st** | 2/3 | **3rd** | 2/3 |
| 3 | 10-9-6-5 | 7th | 0/3 | 10-5-6 | 7th | 1/3 | **3rd** | 1/3 |
| 4 | 2-3-7-6 | 6th | 0/3 | 2-1-3-6 | 6th | 0/3 | 6th | 1/3 |
| 5 | 1-5-3-9 | **1st** | 1/3 | 3-8-1-5 | 5th | 1/3 | 4th | 1/3 |
| 6 | 5-2-3 | **1st** | 2/3 | 2-5-8 | 4th | 2/3 | **1st** | 1/3 |
| 7 | 4-5-7 | 6th | 1/3 | 4-7-5-1 | 6th | 1/3 | **2nd** | 2/3 |
| 8 | 3-9-1-10 | **2nd** | 3/3 | 1-3-8-6 | **1st** | 2/3 | **2nd** | 1/3 |
| 9 | 10-6-8 | 4th | 0/3 | 3-6-5-2 | 7th | 1/3 | 7th | 0/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | 1 | **5/9** | 11/27 | 0 | 0 | 0 | $5.20 on $18 (−71.1%) |
| Don | 2 | 3/9 | 10/27 | 1 (R8 $36.41) | 1 (R8 $36.41) | 0 | $14.20 on $18 (−21.1%) |
| Doug | 2 | 3/9 | **12/27** | 0 | **1 (R1 $103.75)** | **2 (R2 $9.30, R8 $28.00)** | **$18.00 on $18 (0.0%)** |

* A low night for all three. The model had the most #1s on the board (5)
  but one winner; Doug's #1s won R2 (Beamer, $5.00) and R8 (Sarah's Runner,
  $13.00).
* Doug's top four hit the R1 super box (5-2-6-10 → 10-5-2-6).

### Consensus #1s (`tracking/consensus_top1.csv`)

* **R4 #2 Liteupthenite** (2.7-1; second choice to #6 Proton Kitty, 1.7-1):
  **6th**, off the board. "Void of early speed and showed little."

So far: **6 W, 12 ITM from 17**. $2 win on all seventeen: $26.00 on $34
(−23.5%); $2 show $28.50 on $34 (−16.2%). Without 11/06 R2: 5 W, 11 ITM
from 16; $2 win $22.60 on $32 (−29.4%).

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **11/05–11/07** (name matching ON) | Model | 26 | 6 | 17 (65%) | 38/78 | −36.5% |
| | Don | 26 | 9 | 17 (65%) | 42/78 | +1.2% |
| | Doug | 26 | 6 | 12 (46%) | 36/78 | −18.5% |
| **1.3.2** (10/22–11/07) | Model | 85 | 18 | 49 (58%) | 128/255 | −40.7% |
| | Don | 85 | 28 | 53 (62%) | 142/255 | −9.4% |
| | Doug | 83 | 25 | 48 (58%) | 126/249 | −13.6% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.7% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (16 cards) | Model | 137 | 35 | 78 (57%) | 205/411 | −22.8% |
| | Don | 128 | 43 | 79 (62%) | 209/384 | −6.0% |
| | Doug | 91 | 28 | 51 (56%) | 136/273 | −10.8% |
| | Doug, without best guesses | 88 | 26 | 49 (56%) | 130/264 | −15.6% |

* The meet $2 win lines ($211.60 model, $240.60 Don, $162.40 Doug) match
  the ticket replay.
* `model_health --model dpv1.3.2-5track-stretch`: top pick ITM 45/76 =
  59.2%, win 16/76; show ROI −23.2% ($116.80 on $152).
* **The over-68% ITM alert no longer fires** ("[none] all metrics within
  expected bands"); tonight's 2 of 6 logged top picks ITM brought the
  window down.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R9 #10 Bobby's Native One (ML 4-1) | | **4th** at 1.7-1 (fav) | — | — |
| EP4 (R2–R5) | 1-2-4-8 / 5-6-9-10 / 2-3 / 1-5 (64 combos) | $32 | miss, **dead in R3** | 2/4 (R2 #8, R5 #1) | 8-8-8-1 paid **1,945.35** |
| LP4 (R6–R9) | 1-2-5 / 4-6 / 1-3-9 / 6-8-10 (54 combos) | $27 | miss, **dead in R7** | 2/4 (R6 #5, R8 #1) | 5-7-1-2 paid **638.20** |

* EP4: R3 #8 Roadster Runner (14.4-1, first-time starter) and R4 #8 Lolaand
  Rose (12.0-1) were not on his legs.
* LP4: his R6 #1 and R7 #6 scratched (R7 leg left with #4 only, the 1.1-1
  favourite, 6th); R7 #7 Red Roadster won. R9 #2 Karsyn's Ocean was not on
  the last leg either.
* Don's day: **$59 wagered, $0 back.**

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 2 | superfecta wheel, $0.10 | 1,2,8 / 1,2,8 / 1,2,8 / 1-6,8 (24 combos) | $2.40 | lost (8-1-5-4; #2 5th) |
| WO | 9 | trifecta box, $0.20 | 1,5,6 (6 combos) | $1.20 | **won, returned $7.88** |
| BEL | 8 | win, $2 | #6 | $2.00 | lost |

Night total: **$5.60 wagered, $7.88 returned, +$2.28.** DED wagering $2.40,
**qualifies for the DED PP rebate**. WO and BEL are personal bets, kept out
of DED scoring and the ticket replay (as with the CT and MNR bets).

## Watch list

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 2 | #3 Girl Thirsty | T Ronnie Ward | 7 of 7 | 17.6 | 6th | 24.5 |
| 3 | #6 Castle Rock | T Rylee Magnon, J Devin Magnon | 5 of 10 | 19.4 | 4th | 3.6 |
| 4 | #5 Inawinner | T Ronnie Ward | 8 of 8 | 5.5 | 5th | 12.4 |
| 6 | #1 Reaux Ban Da Man | T W.B. Calhoun | scratched (vet; the model's full-field #1) | | | |
| 8 | #4 Seitan | T Rylee Magnon, J Devin Magnon | 4 of 10 | 33.1 | 5th | 25.8 |
| 9 | #8 Elaina Reins | T Rylee Magnon, J Devin Magnon | 4 of 9 | 33.8 | 8th | 6.0 |

None hit the board. Meet tally after 11/07 (`watch_people_tally.csv`;
logged record runs only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 30 | 2 | 12 | 8.78 | 12 | **+3.22** (was +3.45) |
| J Devin H. Magnon | 27 | 4 | 8 | 8.72 | 8 | **−0.72** (was +0.14) |
| T Rylee Magnon | 9 | 1 | 2 | 3.12 | 2 | −1.12 (was −0.26) |
| T W.B. Calhoun | 19 | 4 | 9 | 6.24 | 9 | +2.76 (no starter) |

## Things that look off

1. **R6 is a post-scratch reranker change** that counts under the written
   rule but was not in the pre-race log or the scoring note (count 4/40
   with it, 3/40 without). Needs Doug's call.
2. **Two model #1s (R5, R7) had last races at non-corpus tracks** (FON,
   SWF), so the model priced them off much older DED races. One ran 2nd,
   one 4th.
3. **Name-matching-ON log loss has risen three cards running** (0.622 →
   0.631 → 0.643). Not conclusive (three cards, several long-priced
   winners), but worth watching.
4. **First-time starters won 11/06 R3, 11/07 R3 and 11/07 R9**, the three
   maidens with first-time starters reviewed so far, while the model's raced
   #1 lost each time.

## Queued (not started)

* The first-time-starter maiden check (now 3 races) and the last-race
  long-priced-winner check.
* MNR 10/05 chart: retry after 11/21.
* A decision on adding non-corpus tracks (now also FON, EUR, OP seen).
