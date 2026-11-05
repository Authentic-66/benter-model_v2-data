# DED 2026-11-04 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Seventh card
on 1.3.2. One logged run, the record: `generated_at = 2026-11-04T10:14:46`,
pre-race, bridged, 77 rows (full fields), commit `ef8416b`
(`picks/DED_2026-11-04_20261104-1014.*`). **Name matching was OFF for this
card** (the switch goes live from the first DED card dated 2026-11-05; see
PHASE_6E "Input change, 2026-11-04"). The 11/04 rows carry no
`name_matching` field, which means off.

This pass is read-only on the live model: no changes to 1.3.2, the
rerankers or Piece 1–4 code.

## Load (2026-11-04 night)

* Chart `Delta Downs/ded-results-2026/DED110426USA.pdf`, read with the
  standard chart parser (pdfplumber). 8 races, 69 starters, 41 exotic rows.
  The 77-entry pre-race card was purged first. 0 errors.
* DB backup: `scripts/racing_full.db.pre-ded1104res.bak`, verified before
  the load: same sha256 as the live DB, `integrity_check` ok on both, and the
  same row counts in six tables.
* Spot checks: **R1 official 7-1-4-8 and R8 9-1-2-5, as expected.** Payouts
  match: R5 $0.50 Pick 4 (R2–R5) **$117.05**, R8 $0.50 Pick 4 (R5–R8)
  **$8,068.25**, R8 $1 exacta 9-1 **$151.30**.
* **No dead heats, no DQs** (crossing order = `official_finish_pos` in all
  8 races), **no non-betting starters**.
* **Two non-finishers:**
  * R2 #3 Uncle Eugene (38.5-1, model 10th of 10): "showed brief speed,
    retreated to the rear and was eased to the wire." (Not on Doug's list.)
  * **R8 #10 Heats Hero** (4.3-1, model 5th of 9): "pressed the early pace,
    **pulled up entering the final turn**, was transported by equine
    ambulance." The chart says entering the final turn, not the backstretch.
* **R7 #9 Prado's Priority** (the 1.9-1 favourite; model 2nd of 9; Don's and
  Doug's R7 #1): "bumped at the break, broke sharp, dropped back and lacked a
  bid" (chart comment "broke sharp, done"). He finished **7th of 9, not
  last**; #1 Avery's Gem (11.4-1) was last.
* **Scratches.** Eight logged horses scratched, exactly Doug's list; no
  others (every logged horse either ran or is below):

  | R | horse | chart reason | logged rank | P(ITM) |
  |---|---|---|---|---|
  | 1 | #11 Call Fern | Also-Eligible | 11 of 12 | — |
  | 1 | #12 One Fancy Lady | Also-Eligible | 10 of 12 | — |
  | 3 | #2 She Exaggerates | Veterinarian | 5 of 9 | — |
  | 4 | #2 Midnight Mischief | Veterinarian | 3 of 9 | 39.8 |
  | 5 | #2 Grazed | Veterinarian | **1 of 9** | 53.5 |
  | 5 | #3 My Pal Sweet | Veterinarian | 5 of 9 | — |
  | 6 | #5 After Party | Veterinarian | 6 of 9 | — |
  | 8 | #8 All Saints | Stewards | 10 of 10 | — |

  The model's R5 #1 (Grazed) was scratched, so R5 is scored on its next
  horse, #5 Vodka Martini. Midnight Mischief was Devin Magnon's only mount.
* **Jockey changes (not rescored).** One: **R7 #2 El Dan, Jansen Melancon
  off, Juan Vargas rode** (8th at 9.8-1; model 6th of 9). Every other rider
  matched the PP file on first and last name. The four PP "?" riders rode
  as named: Julio Ramirez Jr. on R2 #9, R3 #7 and R6 #3 Asaasy (2nd at
  11.3-1), Jose Nava-Marin on R4 #5. "Del Cid" / "DelCid" (R2 #2) is a
  spelling difference, not a change.
* Pick payouts (per $0.50). **The late Pick 5 paid to 4 of 5 correct.**

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 7-8-1 | 4.85 |
  | Pick 3 | R2–R4 | 8-1-3 | 9.65 |
  | Pick 3 | R3–R5 | 1-3-5 | 76.45 |
  | Pick 4 (early) | R2–R5 | 8-1/2-3-5 | **117.05** |
  | Pick 5 (early) | R1–R5 | 7/11/12-8-1/2-3-5 | 205.40 |
  | Pick 3 | R4–R6 | 3-5-1 | 71.45 |
  | Pick 3 | R5–R7 | 5-1-7 | 111.55 |
  | Pick 3 | R6–R8 | 1-7-9 | 604.25 |
  | Pick 4 (late) | R5–R8 | 5-1/5-7-9 | **8,068.25** |
  | Pick 5 (late) | R4–R8 | 3-5-1/5-7-9 (**4 correct**) | 779.40 |

  The `/` legs are scratch substitutes: R1 #11/#12 → #7, R3 #2 → #1, R6 #5
  → #1 (each the post-time favourite, and each won). The late Pick 4 was
  broken by R7 #7 The Boss Soss (17.8-1) and R8 #9 Grey Street (24.1-1).
* `score_predictions.py --track DED --date 2026-11-04`, official figures:
  * The logged top pick was ITM in 5 of 7 and won 3 of 7 (R5's logged #1
    was scratched).
  * Top-pick show ROI was −11.4% ($12.40 back on $14).
  * All horses were ITM 24 of 69. 69 rows scored (2,216 total).

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).
* **Exacta box:** a $1 exacta box of the model's top 2 ($2 a race).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 7-1-4-2 | 7-1-4-8 | **1st** (fav) | 1 of 10 (1.1-1) | 3/3 | **hit $16.25** | miss (3 of 4) | **7-1 hit $8.70** | 16.25 |
| 2 | 8-4-1-2 | 8-5-10-1 | **1st** (fav) | 1 of 10 (0.7-1) | 1/3 | miss | miss | 8-4 miss | 30.04 |
| 3 | 1-9-6-7 | 1-3-6-9 | **1st** (fav) | 1 of 8 (1.0-1) | 2/3 | miss | miss (3 of 4) | 1-9 miss | 45.48 |
| 4 | 6-3-1-8 | 3-1-7-8 | 5th (fav) | 2 of 8 (6.9-1) | 2/3 | miss | miss (3 of 4) | 6-3 miss | 186.46 |
| 5 | 5-1-6-7 | 5-9-1-7 | **1st** | 1 of 7 (3.7-1) | 2/3 | miss | miss (3 of 4) | 5-1 miss | 21.66 |
| 6 | 9-4-3-1 | 1-3-8-6 | 8th | 4 of 8 (0.5-1 fav) | 1/3 | miss | miss | 9-4 miss | 19.79 |
| 7 | 4-9-3-8 | 7-6-4-3 | **3rd** | 5 of 9 (17.8-1) | 1/3 | miss | miss | 4-9 miss | 600.36 |
| 8 | 2-1-3-6 | 9-1-2-5 | **3rd** (fav) | **9 of 9** (24.1-1) | 2/3 | miss | miss | 2-1 miss | 386.69 |

**Model:** the #1 pick **won 4 of 8** (R1 Sarah's Rolling $4.20, R2 Candy
Dreamin $3.40, R3 Running Faith $4.00, R5 Vodka Martini $9.40) and was ITM
in 6 of 8, its best card on 1.3.2. Top-3 overlap was 14 of 24. The top-two
exacta box hit **R1 only** (7-1, $8.70 on $16 for the night); the top-3
wheel hit R1 ($16.25 on a $4.20 wheel); the super box missed all 8 (3 of 4
in R1, R3, R4 and R5).

* **The model's top two per leg hit the early Pick 4 and Pick 5** in the
  replay (8-4 / 1-9 / 6-3 / 5-1 → 8-1-3-5, $117.05 on a $16 ticket; Pick 5
  with R1 7-1 added, $205.40 on $32). Its first Pick 4/5 hit of the meet.
* **R4:** the model's #1 Cutting Class (1.3-1, three-way consensus, Don's
  POD) "pressed the early pace, raced four wide around the final turn, made a
  bid and hung" (5th). Its #2 and #3, the no-history shippers #3 Time to
  Tell (65% coverage) and #1 Phila Street (61%), ran 1-2: exacta $33.40.
* **R6:** the model's #1 Blue Chair Bay (5.4-1) "rushed to the front, drove
  clear … faded down the home stretch and was done" (8th of 8). The DB had
  his last race 100 days back; the PP shows a start 43 days ago (not
  charted). #1 Last Attack, the 0.5-1 favourite, won; the model had him 4th.
* **R7:** #7 The Boss Soss won at 17.8-1 (model 5th of 9; his last start,
  117 days back in the PP, is not charted, so the model used one 153 days
  back). Model #1 Stovall ran 3rd; #9 Prado's Priority (model #2) 7th.
* **R8:** #9 Grey Street won at 24.1-1, the model's **last** of 9 (14.8%;
  both jockey and trainer history missed by the name issue). The $1 exacta
  paid $151.30 and the late Pick 4 $8,068.25.
* **R2:** the reranker lifted #1 Whatdidwedo 11.1pp (23.7 → 34.8, rank 9 →
  3; this is the horse with the margin / speed-figure artifact). He ran 4th
  at 57.4-1 and missed the show.
* The model's #1 was the favourite in 5 races (R1–R4, R8): 3 won, R4 ran
  5th, R8 3rd.

### Reranker

The reranker changed the #1 in **no race**, also among runners after the
scratches (R5's base and reranked #1 among runners are both #5 Vodka
Martini). So: **no entries for the review log tonight, and 0 qualifying
races so far** toward the 40-race reranker review (the count starts with
this card). Net on the card: #1 wins 4 vs 4, #1 ITM 6 vs 6, overlap 14 vs 15
(base R2 top three 8-4-5 had #5 Perfect Timing, 2nd; reranked 8-4-1), $2 win
$21.00 vs $21.00.

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 2 | #1 Whatdidwedo | 23.7 → 34.8 (+11.1) | 9 → 3 | 4th (57.4-1) |
| 2 | #5 Perfect Timing | 35.6 → 29.4 (−6.2) | 3 → 5 | **2nd** (5.9-1) |
| 3 | #1 Running Faith | 47.0 → 53.3 (+6.4) | 1 → 1 | **1st** (1.0-1, fav) |
| 3 | #7 Onedayatatime | 31.1 → 38.4 (+7.3) | 4 → 4 | 6th (35.9-1) |
| 3 | #5 Royal Coast | 26.3 → 20.9 (−5.4) | 7 → 7 | 8th (49.6-1) |
| 4 | #3 Time to Tell | 39.2 → 45.6 (+6.3) | 2 → 2 | **1st** (6.9-1) |
| 4 | #4 Garnet Jubilee | 29.9 → 24.9 (−5.1) | 5 → 6 | 6th (17.2-1) |
| 5 | #7 Track Ranger | 21.2 → 27.4 (+6.1) | 5 → 4 | 4th (6.4-1) |
| 5 | #8 All Together | 20.7 → 15.0 (−5.7) | 6 → 6 | 6th (10.8-1) |
| 6 | #4 Mr. Brad's Cowboy | 46.3 → 40.9 (−5.3) | 2 → 2 | 7th (18.8-1) |
| 7 | #4 Stovall | 47.0 → 53.0 (+6.0) | 1 → 1 | **3rd** (2.4-1) |

7 of 11 went the right way (lifted horse ITM or cut horse out of it); the
misses were Whatdidwedo (4th), Onedayatatime (6th), Track Ranger (4th) and
Perfect Timing (cut, ran 2nd).

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 11/04 | 8 | 0 | 4 / 6 / $21.00 (+31.2%) | same |
| 1.3.2 (10/22–11/04) | 59 | 10 | 12 / 32 / $67.80 (−42.5%) | 13 / 32 / $80.60 (−31.7%) |
| **Meet** | 111 | 15 | 29 / 61 / $178.60 (−19.5%) | 30 / 63 / $228.80 (+3.1%) |

`model_health` (logged basis, top-pick scratches excluded) has 1.3.2
**with-reranker 31/53 vs base-only 30/53** (+1, unchanged from 10/30).

## Data issues on the model's top picks (`tracking/top_pick_data_issues.csv`)

Each top pick (among runners) is tagged for the three 11/04 data issues:
**J/T** = the jockey's or trainer's charted history was not used (the name
issue; matching was OFF), **stale** = the DB's last race for the horse is
older than the PP's (a later chart is missing), **artifact** = the
Whatdidwedo margin / speed-figure artifact (only R2 #1 had a contribution
over ±0.8, and he was not a top pick).

| R | top pick | J/T history missed | stale last race | artifact | finished |
|---|---|---|---|---|---|
| 1 | #7 Sarah's Rolling | — | — | — | **1st** |
| 2 | #8 Candy Dreamin | trainer | — | — | **1st** |
| 3 | #1 Running Faith | trainer | — | — | **1st** |
| 4 | #6 Cutting Class | trainer | — | — | 5th |
| 5 | #5 Vodka Martini | — | — | — | **1st** |
| 6 | #9 Blue Chair Bay | — | **yes** (PP 43 days, DB 100) | — | 8th |
| 7 | #4 Stovall | jockey | — | — | **3rd** |
| 8 | #2 Paired | jockey + trainer | — | — | **3rd** |

Affected: **6 of 8** top picks, 2 W / 4 ITM. Unaffected: 2 (R1, R5), both
won. The one stale top pick (Blue Chair Bay) ran last.

All 69 starters by group (logged P(ITM) vs actual):

| group | starters | sum P(ITM) | ITM | sum P(win) | W |
|---|---|---|---|---|---|
| J/T history missed | 44 | 13.99 | 17 | 4.65 | 5 |
| stale last race | 17 | 5.49 | 5 | 1.83 | 1 |
| no DB history (shippers, first-timers) | 6 | 1.70 | 4 | 0.55 | 1 |
| any of the three | 51 | 16.44 | 19 | 5.49 | 6 |
| none | 18 | 5.25 | 5 | 1.75 | 2 |

The J/T group outran its P(ITM) by 3 (both of the night's longshot winners,
Grey Street and The Boss Soss, are in it), as the name-matching validation
would predict (missing history pulls a horse toward the prior). One card;
the CSV is there so later cards can be added and compared.

## Low-coverage (<65%) horses

**5 of 69** starters were below 65% coverage, all no-history shippers.
Summed P(ITM) 1.51, **actual ITM 4**:

| R | horse | cov | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 3 | #3 She Sails | 46% | 6 of 8 | 22.9 | **2nd** | 26.2 |
| 3 | #5 Royal Coast | 60% | 7 of 8 | 20.9 | 8th | 49.6 |
| 4 | #3 Time to Tell | 65% (64.6) | 2 of 8 | 45.6 | **1st** | 6.9 |
| 4 | #1 Phila Street | 61% | 3 of 8 | 33.4 | **2nd** | 2.7 |
| 6 | #8 Midshakin | 61% | 6 of 8 | 28.3 | **3rd** | 5.9 |

R3 #2 She Exaggerates (54%, first-time starter) was scratched. R3 (MC
20000, 74%) was the lowest-coverage race.

## Benchmarks: Don and Doug

Re-ranked around scratches as before (Don's alt moves up; Doug has no alt).

* **Don's picks came by direct message on X at 16:59, after R1 had run**
  (R1 went off at 4:42, R2 at 5:11, chart times; the TwinSpires posting
  failed). R1 is scored for him anyway; without it Don is 2 W / 4 ITM from 7.
* Don's scratches: R1 #12 (4th pick; alt #6 moves up → 7-4-1-6), R3 #2 (4th
  pick → 1-9-4-6), **R5 #2 (his top pick) and alt #3** (→ 5-9-1, three
  picks), R6 #5 (4th pick → 9-1-3-7). R8 logged as 2-6-10 (he wrote
  "2-6-10-10").
* Doug's picks were all regular picks (no passes, no best guesses); R1 and
  R2 made before those races ran; three picks in R1, R2 and R5. No scratch
  touched them.

| R | Don (re-ranked) | Don #1 fin | Don overlap | Doug (re-ranked) | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 7-4-1-6 *(after the race)* | **1st** | 3/3 | 7-4-1 | **1st** | 3/3 | **1st** | 3/3 |
| 2 | 5-8-10-9 | **2nd** | 3/3 | 5-4-8 | **2nd** | 2/3 | **1st** | 1/3 |
| 3 | 1-9-4-6 | **1st** | 1/3 | 1-6-8-4 | **1st** | 2/3 | **1st** | 2/3 |
| 4 | 6-8-3-1 | 5th | 1/3 | 6-1-3-9 | 5th | 2/3 | 5th | 2/3 |
| 5 | 5-9-1 | **1st** | 3/3 | 6-5-9 | 5th | 2/3 | **1st** | 2/3 |
| 6 | 9-1-3-7 | 8th | 2/3 | 1-9-3-6 | **1st** | 2/3 | 8th | 1/3 |
| 7 | 9-6-4-3 | 7th | 2/3 | 9-4-3-8 | 7th | 1/3 | **3rd** | 1/3 |
| 8 | 2-6-10 | **3rd** | 1/3 | 2-10-1-6 | **3rd** | 2/3 | **3rd** | 2/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | **4** | **6/8** | 14/24 | 1 (R1 $16.25) | 0 | 1 (R1 7-1, $8.70) | $21.00 on $16 (**+31.2%**) |
| Don | 3 | 5/8 | **16/24** | **3** (R1 $16.25, R2 $30.04, R5 $21.66) | 0 | **2** (R2 8-5 $10.10, R5 5-9 $22.50) | $17.60 on $16 (+10.0%) |
| Doug | 3 | 5/8 | **16/24** | 1 (R1 $16.25) | 0 (5 placed) | 0 | $11.20 on $16 (−30.0%) |

* Don's top three were the trifecta in R1 (7-4-1), R2 (5-8-10 → 8-5-10) and
  R5 (5-9-1); the R5 one came only because his #1 #2 Grazed was scratched.
* The model's #1 matched Don's in 6 races (R1, R3, R4, R5, R6, R8) and
  Doug's in 4 (R1, R3, R4, R8). Don's and Doug's matched in 6 (R1, R2, R3,
  R4, R7, R8).
* All three missed R7 (#7 at 17.8-1) and R8 (#9 at 24.1-1).

### Consensus #1s (`tracking/consensus_top1.csv`)

All three sources had the same #1 in **R3, R4 and R8**, all pre-race, all
the favourite. **R1 #7 Sarah's Rolling (won, 1.1-1) was also everyone's #1
but is not added**: Don's picks arrived after R1 had run. Rule (Doug,
11/04): a race counts as consensus only when **all three picks were logged
before post**.

* **R3 #1 Running Faith**: **won** at 1.0-1 ($4.00). Led throughout.
* **R4 #6 Cutting Class** (also Don's POD): 5th at 1.3-1. Off the board.
* **R8 #2 Paired**: 3rd at 1.5-1, show $2.20. "Lacked early speed … was
  gaining on the leaders and needed more ground."

| card | R | horse | odds | finished | $2 win | Doug's bet |
|---|---|---|---|---|---|---|
| 10/28 | 2 | #3 Donegal Freedom | 0.7 | **1st** | 3.40 | |
| 10/28 | 3 | #9 Forty Three Cents | 1.2 | **1st** | 4.40 | |
| 10/28 | 7 | #10 Miracle Mula | 1.9 | 4th | | $2 win, lost |
| 10/29 | 1 | #7 Gently | 1.7 | 5th | | (underneath in his 9-7 exacta) |
| 10/29 | 6 | #4 Takethe Hint | 1.5 | **3rd** | | $1 exacta 4-5, lost |
| 10/30 | 6 | #3 Letmikefigureitout | 1.2 | **3rd** | | |
| 10/30 | 8 | #5 Cajun Caviar | 0.6 | **1st** | 3.20 | |
| 10/30 | 9 | #5 Lieutenant Charm | 2.8 | **1st** | 7.60 | $0.10 super part wheel, lost |
| 11/04 | 3 | #1 Running Faith | 1.0 | **1st** | 4.00 | |
| 11/04 | 4 | #6 Cutting Class | 1.3 | 5th | | |
| 11/04 | 8 | #2 Paired | 1.5 | **3rd** | | |

So far: **5 W, 8 ITM from 11**, every one the favourite. $2 win on all
eleven: $22.60 on $22 (+2.7%); $2 show $19.60 on $22 (−10.9%).

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

Model rows are by the version that made the record run. Don and Doug are
split by the same dates. Doug has no picks before 10/21. (Don's 11/04 R1
is included.)

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **11/04** | Model | 8 | 4 | 6 (75%) | 14/24 | +31.2% |
| | Don | 8 | 3 | 5 (62%) | 16/24 | +10.0% |
| | Doug | 8 | 3 | 5 (62%) | 16/24 | −30.0% |
| **1.3.2** (10/22–11/04) | Model | 59 | 12 | 32 (54%) | 90/177 | −42.5% |
| | Don | 59 | 19 | 36 (61%) | 100/177 | −14.1% |
| | Doug | 57 | 19 | 36 (63%) | 90/171 | −11.4% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.8% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (13 cards) | Model | 111 | 29 | 61 (55%) | 167/333 | −19.5% |
| | Don | 102 | 34 | 62 (61%) | 167/306 | −7.8% |
| | Doug | 65 | 22 | 39 (60%) | 100/195 | −7.7% |
| | Doug, without best guesses | 62 | 20 | 37 (60%) | 94/186 | −14.4% |

* The meet $2 win lines ($178.60 model, $188.00 Don, $120.00 Doug) match the
  ticket replay.
* `model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
  scratches excluded): top pick ITM 31/53 = 58.5%, win 11/53; show ROI
  −22.6% ($82.00 on $106). Alert off.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R4 #6 Cutting Class (ML 4-1) | | 5th at 1.3-1 (fav), off the board | — | — |
| EP4 (R2–R5) | 5-8-10 / 1-9 / 1-3-6-8 / 2-5-9 (72 combos) | $36 | **HIT** | 4/4 | **$117.05** (8-1/2-3-5) |
| LP4 (R5–R8) | 2-5-9 / 1-9 / 3-4-6-9 / 2-6 (48 combos) | $24 | miss, **dead in R7** | 2/4 | 5-1/5-7-9 paid 8,068.25 |

* EP4: R2 #8, R3 #1, R4 #3 (Time to Tell, 6.9-1) and R5 #5 (Vodka Martini,
  3.7-1). His R5 leg had the scratched #2 Grazed; Vodka Martini was on it
  in his own right.
* LP4: R5 #5 and R6 #1 hit; died in R7 (3-4-6-9 vs #7 The Boss Soss at
  17.8-1). R8 (2-6 vs #9 at 24.1-1) missed too.
* Don's day: $60 wagered, $117.05 back (**+$57.05**). The tickets went in
  by X after R1, as noted in `don_bets.csv`.

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 2 | place, $2 | #5 Perfect Timing | $2.00 | **won $5.20** (2nd at 5.9-1) |
| DED | 3 | show, $2 | #6 Daddy's Last Sweet | $2.00 | **won $5.20** (3rd at 7.6-1) |
| MNR | 2 | superfecta part wheel, $0.10 | 3,4,5,7 / 3,4,5,7 / 3,4,5 / 3,5 (8 combos) | $1.60 | lost (3-7-8-2) |

Night total: **$5.60 wagered, $10.40 returned, +$4.80**. These bets qualify
Doug for the DED PP rebate.

* The MNR bet is logged with `track = MNR` and is kept out of the DED
  scoring and the ticket replay (no MNR 11/04 chart on disk; graded from
  Doug's report).
* Perfect Timing was Don's and Doug's R2 #1; the model had him 5th (the
  reranker cut him 6.2pp). Daddy's Last Sweet was Doug's #2 and the model's
  #3. Neither is a consensus bet.

## Watch list

No starters for the watched horses (Discerner, Cincy's Player, Celestial
Clock, Cajun Caviar), no Calhoun or Rylee Magnon starters. **Devin Magnon's
only mount, R4 #2 Midnight Mischief, was scratched** (vet).

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 1 | #10 She's a Target | T Ward | 7 of 10 | 19.6 | 6th | 23.9 |
| 3 | #3 She Sails | T Ward | 6 of 8 | 22.9 | **2nd** | 26.2 |

She Sails was a **first-time starter** (46% coverage): "raced within
striking distance, saved ground around the final turn, made a late bid and
finished willingly." Both horses also had Ward's history missed (name
matching OFF).

Meet tally after 11/04 (`watch_people_tally.csv`; logged record runs only,
pooled across 1.3.0, 1.3.1 and 1.3.2):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 26 | 2 | 11 | 7.92 | 11 | **+3.08** |
| J Devin H. Magnon | 22 | 4 | 8 | 6.90 | 8 | +1.10 |
| T Rylee Magnon | 6 | 1 | 2 | 2.26 | 2 | −0.26 |
| T W.B. Calhoun | 19 | 4 | 9 | 6.24 | 9 | +2.76 |

The "2026 meet" window now counts **logged cards only** (Doug, 11/04): the
10/31 card was charted but never run through the model, so its starts are
left out. Before this change the file showed Ward 28 starts / 3 W / 13 ITM
and Calhoun 22 / 4 / 9.

**Read Ward's +3.08 with care.** It is not a steady meet-wide edge:

| span | starts | sum P(ITM) | ITM | diff |
|---|---|---|---|---|
| 10/10–10/22 (early cards) | 16 | 5.14 | 8 | +2.86 |
| 10/23–10/30 (1.3.2) | 8 | 2.35 | 2 | −0.35 (−0.24 with name matching on) |
| 11/04 | 2 | 0.43 | 1 | +0.57 |

On the 1.3.2 cards the name-matching validation rebuilt (10/23–10/30), his
gap was close to zero with matching on. Most of the +3.08 comes from the
early cards and from tonight's She Sails (+0.77 by herself, 2nd at 26-1, a
first-time starter at 46% coverage). One horse at that price moves the
number a lot. From 11/05 on, name matching links Ward's and Calhoun's PP
names to their chart history, so read the gap from that card on separately.
