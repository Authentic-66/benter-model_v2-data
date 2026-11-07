# DED 2026-11-06 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Ninth card
on 1.3.2, **second with name matching ON**. One logged run, the record:
`generated_at = 2026-11-06T08:55:13`, pre-race, bridged, 89 rows (full
fields), commit `db19b69` (`picks/DED_2026-11-06_20261106-0855.*`). R4 (PP
"Alw 5000s") was relabelled STARTERALLOWANCE in the DB by hand before the
run (PHASE_6E, "Input fix by hand, DED 2026-11-06 R4").

This pass is read-only on the live model: no changes to 1.3.2, the
rerankers or Piece 1–4 code.

## Pre-race

* **Picks logged before post:** model 08:55 CST, Don received 08:40
  (`339cb17`), Doug (`d2219b4`). High-confidence qualifiers logged
  pre-race (`fabee7c`).
* **Morning scratches:** R3 #6; R4 #3, #9; R5 #8, #11; R6 #8; R9 #8.
* **Late scratches (Doug's list):** R2 #3 Diamond Country and **#6 Cajun
  Catalina (Don's #1)**; R6 #4 Half Way There and #7 My Golden M.
* **Late jockey changes (Doug's list):** Jansen Melancon off all three
  listed mounts: R2 #5 Stormy Lou and R3 #1 Essential George (Colby
  Hernandez), R4 #6 Call My Banker (Casey Fusilier).

### Consensus (post-scratch rule, Doug 11/05)

| R | model | Don | Doug | consensus |
|---|---|---|---|---|
| 1 | 8 | 8 | 8 | **#8 Miss River Rat** |
| 2 | 4 | 4 (#6 scratched late) | 4 | **#4 Cajun Cattitude** (see note) |
| 3 | 7 | 1 | 7 | no |
| 4 | 7 | 6 | 6 | no |
| 5 | 1 | 1 | 6 | no |
| 6 | 9 | 2 | 9 | no |
| 7 | 1 | 4 | 4 | no |
| 8 | 5 | 5 | 9 | no |
| 9 | 2 | 2 | 1 | no |

**Note on R2.** Doug's scoring note listed R1 only. The rule as written on
11/05 says "a race where someone's #1 scratched still counts if the
post-scratch #1s all match (as 10/28 R3 did)". Don's #1 #6 scratched late,
so his post-scratch #1 is #4, the same as the model's and Doug's. R2 is
logged in `consensus_top1.csv` under the written rule. **Doug confirmed
2026-11-07: R2 counts; the row stays.**

## Load (2026-11-06 night)

* Chart `Delta Downs/ded-results-2026/DED110626USA.pdf`, read with the
  standard chart parser (pdfplumber). 9 races, 77 starters, 46 exotic rows.
  The 89-entry pre-race card was purged first. 0 errors.
* DB backup: `scripts/racing_full.db.pre-ded1106res.bak`, verified before
  the load: same sha256 as the live DB, `integrity_check` ok on both, and the
  same row counts in six tables.
* Spot checks: **R1 official 6-7-8-5 and R9 1-7-10-2, as expected.**
* R4 loaded as STARTERALLOWANCE from the chart (the hand-relabelled race row
  was replaced by the chart's).
* **One DQ, no dead heats, no non-betting starters.** R4: #5 My Uncle Leon
  crossed 3rd and was **disqualified and placed 7th** ("came in around the
  second turn"; claim of foul by the rider of #2 Flashy Lover). Official
  11-7-4-10; payouts on the official order. All other races: crossing order
  = official.
* **Scratches: the 11 on the two lists, plus one more.** **R5 #10 Crime
  Spree (vet) was not on either list**; model 6th of 11 logged (P(ITM)
  22.1), nobody's pick. Chart reasons: R2 #3 Stewards, #6 Vet; R3 #6
  Trainer; R4 #3 Stewards, #9 Trainer; R5 #8 Stewards, #10 Vet, #11
  Also-Eligible; R6 #4 and #8 Stewards, #7 Vet; R9 #8 Vet.
* **One non-finisher:** R9 #5 Flash of Fire (43.1-1, model 4th of 9, rider
  change, see below): "pulled up down the backside and walked off."
* **Jockey changes: the three Melancon mounts plus three more** from the
  chart (all others matched the PP; R4 #8 Sir Tristan's "Nava-Marin" is a
  hyphen difference, not a change). All six in
  `tracking/late_jockey_changes.csv`:

  | R | horse | PP rider → rode | model rank (runners) | P(ITM) | finished | odds |
  |---|---|---|---|---|---|---|
  | 2 | #5 Stormy Lou | Melancon → Colby Hernandez | 2 of 8 | 46.9 | **2nd** | 5.1 |
  | 3 | #1 Essential George | Melancon → Colby Hernandez | 3 of 10 | 33.7 | **1st** | 1.4 (fav) |
  | 4 | #6 Call My Banker | Melancon → Casey Fusilier | 2 of 9 (base #1) | 61.4 | 5th | 3.4 |
  | 4 | #10 Grand Oracle | Misael Alvarez → Thomas Pompell | 6 of 9 | 18.5 | 4th | 17.3 |
  | 7 | #7 Cozzino | Misael Alvarez → Thomas Pompell | 9 of 9 | 13.9 | 5th | 29.3 |
  | 9 | #5 Flash of Fire | Isaac Castillo → Junior Inirio | 4 of 9 | 30.0 | DNF | 43.1 |

  Six horses, summed P(ITM) 2.04, ITM 2. Across 11/05–11/06 the late-change
  list now has 12 rows (summed P(ITM) 4.89, ITM 5).
* Pick payouts (per $0.50, all on full legs):

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 6-4-1 | 35.80 |
  | Pick 3 | R2–R4 | 4-1-11 | 44.85 |
  | Pick 3 | R3–R5 | 1-11-1 | 103.40 |
  | Pick 4 (early) | R2–R5 | 3/4/6-1/6-11-1/8/10/11 | **168.05** |
  | Pick 5 (early) | R1–R5 | 6-3/4/6-1/6-11-1/8/10/11 | 950.45 |
  | Pick 3 | R4–R6 | 11-1-5 | 128.60 |
  | Pick 3 | R5–R7 | 1-5-4 | 36.95 |
  | Pick 3 | R6–R8 | 5-4-1 | 71.45 |
  | Pick 3 | R7–R9 | 4-1-1 | 118.25 |
  | Pick 4 (late) | R6–R9 | 5-4-1-1/8 | **468.45** |
  | Pick 5 (late) | R5–R9 | 1/8/10/11-5-4-1-1/8 | 1,461.75 |

  The `/` legs are scratch substitutes, each the post-time favourite who
  won: R2 #3/#6 → #4, R3 #6 → #1, R5 #8/#10/#11 → #1, R9 #8 → #1.
* `score_predictions.py --track DED --date 2026-11-06`: top pick ITM **5 of
  9**, won 2 of 9 (no logged #1 scratched); top-pick show ROI −31.1%
  ($12.40 on $18); all horses ITM 27 of 77; 1 DNF. 77 rows scored (2,354
  total).

## Per race (re-ranked among horses that ran)

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 8-7-6-4 | 6-7-8-5 | **3rd** | 3 of 8 (5.2-1) | **3/3** | **hit $35.56** | miss (3 of 4) | 8-7 miss | 35.56 |
| 2 | 4-5-1-9 | 4-5-1-9 | **1st** (fav) | 1 of 8 (0.7-1) | **3/3** | **hit $6.41** | **hit $6.41** | **4-5 hit $7.30** | 6.41 |
| 3 | 7-3-1-11 | 1-8-9-2 | 9th | 3 of 10 (1.4-1) | 1/3 | miss | miss (1 of 4) | 7-3 miss | 312.51 |
| 4 | 7-6-5-8 | 11-7-4-10 | **2nd** (fav) | **8 of 9** (12.8-1) | 1/3 | miss | miss (1 of 4) | 7-6 miss | 371.70 |
| 5 | 1-6-2-7 | 1-5-2-7 | **1st** (fav) | 1 of 8 (1.6-1) | 2/3 | miss | miss (3 of 4) | 1-6 miss | 43.89 |
| 6 | 9-6-2-10 | 5-2-3-6 | 6th (fav) | 6 of 7 (3.8-1) | 1/3 | miss | miss (2 of 4) | 9-6 miss | 44.90 |
| 7 | 1-5-4-2 | 4-5-8-1 | 4th | 3 of 9 (1.9-1) | 2/3 | miss | miss (3 of 4) | 1-5 miss | 15.14 |
| 8 | 5-4-9-2 | 1-8-5-9 | **3rd** (fav) | 7 of 9 (16.2-1) | 1/3 | miss | miss (2 of 4) | 5-4 miss | 78.24 |
| 9 | 2-1-6-5 | 1-7-10-2 | 4th | 2 of 9 (0.9-1) | 1/3 | miss | miss (2 of 4) | 2-1 miss | 13.39 |

**$1 exacta box on the model's top two:** one hit, **R2 4-5 ($7.30)**;
$7.30 back on $18.

**Model:** #1 **won 2 of 9** (R2 Cajun Cattitude $3.40, R5 Wild Bert
$5.20) and was **ITM in 5 of 9**. Top-3 overlap 15 of 27. The top-3 wheel
hit R1 and R2; the super box hit R2.

* **R3** (2yo MSW, 69% race coverage, six first-time starters): the
  model's #1 Carlos the Kid (2.9-1, one of four runners with race history,
  92% coverage) "always raced near the back and lacked a bid" (9th of 10). The
  first-time starters ran 1-2-3-4: #1 Essential George (Melancon off,
  model 3rd, 1.4-1 fav) went wire to wire; #8 K R Maximus (model 9th,
  12.4-1) 2nd; #9 Our Friend Armando (model 7th) 3rd; #2 Favtastic 4th.
  This was the race flagged pre-race as a possible pass.
* **R4:** #11 Jabran (12.8-1, model 8th of 9, last raced at ATO, not in the
  DB) won clear; the reranker's #1 Mahoney Road (fav) got up for 2nd. Base
  #1 Call My Banker (Melancon off) ran 5th.
* **R6:** the model's #1 Drilling Report (1.8-1 fav) "always raced near the
  back and showed little" (6th of 7). #5 Loudermilk (model 6th, 3.8-1) beat
  #2 Brahms Boy (model 3rd) after a duel.
* **R7:** #1 Vineaux (4.1-1, P(ITM) 64.2) "void of early speed, made a
  steady gain, but was no real factor" (4th). #4 Maximus Amar (model 3rd,
  fav) beat #5 Soft Hands (model 2nd); exacta 4-5 $9.10.
* **R8:** #1 Heavenly Dream (16.2-1, model 7th of 9) "challenged on the
  front end ... drove clear and held on well"; the
  shipper #8 D's a Rock (model 6th, no DB history) 2nd; the model's #1
  Nana's Corn Muffin (Don's POD) 3rd. Exacta $142.00.
* **R9:** #2 The Red Wicked One (P(ITM) 63.1) "dueled for the early lead and
  weakened" (4th); #1 Hannah Boo (model 2nd, 0.9-1) won.
* The model's #1 was the favourite in 5 races (R2, R4, R5, R6, R8): 2 won,
  4 ITM.

### Reranker

The reranker changed the #1 in **one race, R4** (logged pre-race in
`tracking/reranker_changes.csv`, now with finishes):

| R | base #1 (base → final) | finished | reranked #1 (base → final) | finished |
|---|---|---|---|---|
| 4 | #6 Call My Banker (63.1 → 61.4) | 5th (3.4-1; Melancon off) | #7 Mahoney Road (58.9 → 65.5) | **2nd** (1.9-1 fav, place $3.40) |

**Reranker review rule:** 2 qualifying races so far: reranked #1 1 W / 2
ITM, base #1 0 / 0. 38 to go. Both are on the name-matching-ON part.

Net on the card: #1 wins 2 vs 2, #1 ITM 5 vs 4, overlap 15 vs 13, $2 win
$8.60 vs $8.60. The overlap difference is R5 (reranked top three had #2
Maximus Freedom, 3rd, instead of #7 Spinning Aces, 4th) and R6 (#2 Brahms
Boy, 2nd, instead of #10 Theboyz Warning, 7th).

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 3 | #7 Carlos the Kid | 48.5 → 54.1 (+5.6) | 1 → 1 | 9th (2.9-1) |
| 3 | #11 Parole Pass | 22.3 → 28.8 (+6.5) | 6 → 4 | 5th (16.7-1) |
| 4 | #7 Mahoney Road | 58.9 → 65.5 (+6.5) | 2 → 1 | **2nd** (1.9-1) |
| 6 | #2 Brahms Boy | 30.0 → 35.3 (+5.2) | 4 → 3 | **2nd** (2.3-1) |
| 6 | #10 Theboyz Warning | 40.8 → 33.8 (−7.0) | 2 → 4 | 7th (10.4-1) |
| 7 | #2 Ongoing Challenge | 26.5 → 34.2 (+7.8) | 6 → 4 | 8th (43.7-1) |
| 7 | #8 Lotta Spirit Here | 21.3 → 14.5 (−6.8) | 8 → 8 | **3rd** (4.3-1) |

3 of 7 went the right way (Mahoney Road, Brahms Boy, Theboyz Warning cut).

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 11/06 | 9 | 1 | 2 / 5 / $8.60 (−52.2%) | 2 / 4 / $8.60 (−52.2%) |
| 1.3.2 (10/22–11/06) | 76 | 12 | 17 / 44 / $95.60 (−37.1%) | 17 / 42 / $101.80 (−33.0%) |
| **Meet** | 128 | 17 | 34 / 73 / $206.40 (−19.4%) | 34 / 73 / $250.00 (−2.3%) |

`model_health` (logged basis, top-pick scratches excluded) has 1.3.2
**with-reranker 43/70 vs base-only 40/70** (+3; was +2 after 11/05).

## High-confidence #1 forward test (`tracking/high_conf_top1.csv`)

First night of the test pre-registered in PHASE_6D_ROADMAP (`fabee7c`):
post-scratch #1 with P(ITM) over 60%, paper $2 win and $2 place.

| R | horse | P(ITM) | odds | finished | $2 win | $2 place |
|---|---|---|---|---|---|---|
| 1 | #8 Miss River Rat | 71.6 | 1.6 | 3rd | 0 | 0 |
| 4 | #7 Mahoney Road | 65.5 | 1.9 | **2nd** | 0 | 3.40 |
| 7 | #1 Vineaux | 64.2 | **4.1** | 4th | 0 | 0 |
| 9 | #2 The Red Wicked One | 63.1 | 3.8 | 4th | 0 | 0 |

Win $0 on $8, place $3.40 on $8. Over-4-1 subset: 1 race (Vineaux, 4th).
**4 of 40** qualifying races. No reading until 40; the pass mark is still
to be set by Doug.

## Name matching ON: 11/05–11/06 vs the earlier 1.3.2 cards

Two cards. Same basis as the 11/05 review (record run, among starters,
DNFs not ITM, logged P(ITM) not renormalised; #1 re-ranked among runners).

| card | name matching | races | starters | #1 W | #1 ITM | sum P(ITM) | ITM | P(ITM) LL | Brier | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.3.2 off (7 cards, 10/22–11/04) | off | 59 | 505 | 12 | 32 (54%) | 158.82 | 177 | 0.609 | 0.210 | $67.80 (−42.5%) |
| 11/05 | on | 8 | 61 | 3 | 7 | 21.82 | 24 | 0.622 | 0.218 | $19.20 |
| **11/06** | **on** | 9 | 77 | 2 | 5 | 24.27 | 27 | 0.631 | 0.218 | $8.60 |
| 1.3.2 on (2 cards) | on | 17 | 138 | 5 | 12 (71%) | 46.09 | 51 | 0.627 | 0.218 | $27.80 (−18.2%) |

Ranking still better on the two ON cards, probabilities still worse (both
cards' log loss above the off-card average; tonight's misses: Carlos the
Kid 54.1 (9th), Drilling Report 44.2 (6th), Vineaux 64.2 (4th), The Red
Wicked One 63.1 (4th), Miss Dealority 44.3 (8th)). Two cards is not enough
to separate this from the cards themselves. Keep reporting on and off
separately.

## Data issues on the model's top picks (`tracking/top_pick_data_issues.csv`)

**No top pick had a data issue tonight.** All nine had jockey and trainer
history in the DB (smallest: 460 prior starts) and a last race the DB has
(PP days off = DB days, 16–45). No contribution over ±0.8 on the card. The
one new person under name matching was trainer Jeff Schindler (R4 #11
Jabran), the R4 winner.

## Missing-last-race horses, 11/04–11/06 (read-only)

**Method.** For every horse on the 11/04, 11/05 and 11/06 PP files, the
most recent PP race line (date + track) was read with the live PP parser
(wrapped in a scratch script, no code changed) and checked against the DB
**as it was when that card was run** (chart `parsed_at`, UTC, against the
run's `generated_at`, CST + 6h). Outcomes are from the record runs.
Scratched horses are left out (their pre-race rows are purged at chart
load, so their status cannot be checked the same way).

**38 starters** were flagged: 23 on 11/04, 5 on 11/05, 10 on 11/06.

| group | starters | ITM | model expected ITM | W | model expected W |
|---|---|---|---|---|---|
| all flagged | 38 | **15** | 11.0 | 3 | 3.6 |
| 11/04 (EVD/LAD charts loaded the next morning) | 20 | 7 | 6.1 | 1 | 2.0 |
| last race at a track not in the corpus | 16 | 7 | 4.3 | 2 | 1.4 |
| other (MNR 10/05 not loaded; EVD 6/11 chart incomplete) | 2 | 1 | 0.6 | 0 | 0.2 |
| **11/06 only** | **10** | **5** | 2.4 | 1 | 0.8 |
| all other starters, same three cards | 169 | 60 | 56.8 | 22 | 19.1 |

* The flagged horses hit the board **more** often than the model expected:
  15 vs 11.0 (z about +1.5 on a binomial spread); on 11/06 alone 5 vs 2.4.
  Wins were in line (3 vs 3.6). Not significant on 38 starters, and the
  direction is the opposite of the Gap #1 finding (the model over-rating
  unseen horses), so it is a lead to keep counting, not a conclusion.
* The excess sits in the non-corpus group (7 vs 4.3). The 11/04 group,
  whose last races are now loaded, ran close to expectation (7 vs 6.1).

**11/06 flagged starters** (Doug's 9 plus R8 #8 D's a Rock, which has no DB
history at all; 5 of 10 hit the board; on Doug's 9, 4 vs 2.1 expected):

| R | horse | last race (PP) | model rank (runners) | P(ITM) | odds | finished |
|---|---|---|---|---|---|---|
| 4 | #11 Jabran | ATO 2026-09-07 | 8 of 9 | 10.9 | 12.8 | **1st** |
| 4 | #4 Special Moment | GIL 2026-07-05 | 7 of 9 | 15.4 | 25.5 | **3rd** (DQ promotion) |
| 4 | #5 My Uncle Leon | ARP 2026-08-01 | 3 of 9 | 25.6 | 3.5 | 7th (DQ from 3rd) |
| 5 | #5 Josh's Dream | LS 2026-06-27 | 5 of 8 | 25.7 | 8.4 | **2nd** |
| 5 | #9 Mud On My Boots | GIL 2026-08-29 | 7 of 8 | 15.6 | 12.8 | 6th |
| 6 | #2 Brahms Boy | GIL 2026-08-30 | 3 of 7 | 35.3 | 2.3 | **2nd** |
| 8 | #2 Tennessee Moon | ARP 2026-08-08 | 4 of 9 | 36.9 | 16.0 | 6th |
| 8 | #6 Blushing Belle | LS 2026-07-11 | 9 of 9 | 16.4 | 67.1 | 9th |
| 8 | #8 D's a Rock | BAQ 2026-05-14 | 6 of 9 | 27.7 | 4.1 | **2nd** |
| 9 | #6 Dat Hint | EVD 2026-06-11 | 3 of 8 | 30.3 | 18.3 | 5th |

**11/04–11/05 flagged starters:**

| card | R | horse | last race (PP) | model rank | P(ITM) | odds | finished |
|---|---|---|---|---|---|---|---|
| 11/04 | 1 | #1 Miss Landlock | EVD 08-27 | 2 of 10 | 48.6 | 3.8 | **2nd** |
| 11/04 | 1 | #4 Faye L. | EVD 08-29 | 3 of 10 | 36.8 | 4.3 | **3rd** |
| 11/04 | 1 | #5 Magical Deal | EVD 07-31 | 10 of 10 | 11.9 | 84.9 | 9th |
| 11/04 | 1 | #10 She's a Target | EVD 08-22 | 7 of 10 | 19.6 | 23.9 | 6th |
| 11/04 | 2 | #1 Whatdidwedo | EVD 08-08 | 3 of 9 | 34.8 | 57.4 | 4th |
| 11/04 | 2 | #6 Rescue Squad | EVD 08-06 | 7 of 9 | 27.9 | 6.7 | 5th |
| 11/04 | 3 | #4 Queenofpoker | EVD 08-27 | 8 of 8 | 18.7 | 2.8 | 5th |
| 11/04 | 3 | #5 Royal Coast | LAD 09-23 | 7 of 8 | 20.9 | 49.6 | 8th |
| 11/04 | 3 | #6 Daddy's Last Sweet | LAD 09-21 | 3 of 8 | 39.4 | 7.6 | **3rd** |
| 11/04 | 3 | #7 Onedayatatime | EVD 08-28 | 4 of 8 | 38.4 | 35.9 | 6th |
| 11/04 | 3 | #8 Our Castle Queen | LAD 09-21 | 5 of 8 | 26.9 | 12.3 | 7th |
| 11/04 | 4 | #1 Phila Street | EVD 08-08 | 3 of 8 | 33.4 | 2.7 | **2nd** |
| 11/04 | 4 | #3 Time to Tell | PRM 08-15 | 2 of 8 | 45.6 | 6.9 | **1st** |
| 11/04 | 4 | #5 Girlie's Max | LAD 09-28 | 7 of 8 | 23.7 | 49.6 | 8th |
| 11/04 | 4 | #7 E Z Words | EVD 08-27 | 5 of 8 | 28.7 | 26.8 | **3rd** |
| 11/04 | 6 | #4 Mr. Brad's Cowboy | LAD 09-28 | 2 of 8 | 40.9 | 18.8 | 7th |
| 11/04 | 6 | #8 Midshakin | PRM 09-04 | 6 of 8 | 28.3 | 5.9 | **3rd** |
| 11/04 | 6 | #9 Blue Chair Bay | LAD 09-22 | **1 of 8** | 49.5 | 5.4 | 8th |
| 11/04 | 7 | #2 El Dan | EVD 09-07 | 6 of 9 | 29.7 | 9.8 | 8th |
| 11/04 | 7 | #6 Daddy's Code | LAD 09-21 | 8 of 9 | 23.1 | 6.1 | **2nd** |
| 11/04 | 7 | #7 The Boss Soss | EVD 07-10 | 5 of 9 | 31.3 | 17.8 | **1st** |
| 11/04 | 8 | #5 S D's Takeover | EVD 09-04 | 5 of 8 | 25.0 | 26.2 | 4th |
| 11/04 | 8 | #10 Heats Hero | RP 10-09 | — | — | — | DNF |
| 11/05 | 2 | #6 Chatty Milligan | ARP 08-14 | 6 of 10 | 24.0 | 32.3 | 5th |
| 11/05 | 7 | #2 Wave Maker | MNR 10-05 | 5 of 6 | 32.5 | 1.0 | **3rd** |
| 11/05 | 7 | #4 Gracie Baby | ARP 07-10 | 6 of 6 | 19.5 | 39.0 | 6th |
| 11/05 | 7 | #7 I Forgot the Time | PRM 09-26 | 3 of 6 | 34.4 | 3.8 | 5th |
| 11/05 | 7 | #8 Kason's Buckaroo | SWF 09-12 | 4 of 6 | 32.7 | 15.7 | 4th |

### Where the missing races are

| missing race | starters (all 3 cards) | in the corpus? | can the chart be fixed? |
|---|---|---|---|
| EVD / LAD, Jun–Sep 2026 | 20 (11/04 only) | yes | **Already loaded** 11/05 morning (`f2f4a0a`); 11/05 and 11/06 have none |
| **EVD 2026-06-11 R8** (Dat Hint) | 1 | yes | **Chart file on disk is incomplete**: `EVD061126USA.pdf` has 7 pages, Races 1–7; Dat Hint ran in R8. Re-download the full chart |
| **MNR 2026-10-05** (Wave Maker) | 1 | yes | **Downloadable**: corpus track, chart not on disk |
| ARP (Arapahoe Park) | 4 | no | Equibase charts exist; adding the track is a model-input change |
| GIL (Gillespie County) | 4 | no | same (short fair meet) |
| PRM (Prairie Meadows) | 3 | no | same |
| LS (Lone Star) | 2 | no | same |
| ATO (Atokad) | 1 (Jabran) | no | same (short meet) |
| BAQ (Belmont at Aqueduct) | 1 (D's a Rock) | no | same |
| RP (Remington) | 1 | no | same |
| SWF | 1 | no | code not identified here; check before adding |

* "Equibase charts exist" is from general knowledge, not tested here. The
  chart downloads on 11/05 hit HTTP 403 on 151 of 487 requests
  (`chart_download_log_20261105.csv`), so any batch needs the same retry
  handling.
* **Adding a non-corpus track is not just a download.** The loader would
  insert the new track, and the track-keyed features (`dpv1_common`,
  `*_at_other_tracks_*`, home-track) would then see races they did not see
  in training. That needs a decision and a PHASE_6E input-change entry,
  like name matching.
* The EVD 6/11 gap suggests checking the other downloaded EVD/LAD charts
  for missing races (PP race number vs races in the DB). Not done here.

## Low-coverage (<65%) horses

Six of 77 starters, all R3 first-time starters at 53%: #3 Cousin Michael
(model 2nd, 7th), #1 Essential George (3rd, **won**), #2 Favtastic (5th,
**4th**), #9 Our Friend Armando (7th, **3rd**), #10 Gladiator Strong (8th,
8th), #8 K R Maximus (9th, **2nd**). They took the first four places. R8
#8 D's a Rock (66%, no DB history) ran 2nd.

## Benchmarks: Don and Doug

* All three were logged before post.
* Scratches: **R2 #6 Cajun Catalina was Don's #1** (late; → 4-1-5). **R4 #3
  Briterdayzahead was Don's 3rd** (morning; → 6-5-7). No scratch touched
  Doug's picks.
* Doug's picks were all regular picks (no passes, no best guesses).

| R | Don (re-ranked) | Don #1 fin | Don overlap | Doug | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 8-4-6-7 | **3rd** | 2/3 | 8-4-2-7 | **3rd** | 1/3 | **3rd** | 3/3 |
| 2 | 4-1-5 | **1st** | 3/3 | 4-10-9-5 | **1st** | 1/3 | **1st** | 3/3 |
| 3 | 1-7-3-11 | **1st** | 1/3 | 7-11-4-9 | 9th | 0/3 | 9th | 1/3 |
| 4 | 6-5-7 | 5th | 1/3 | 6-7-5-8 | 5th | 1/3 | **2nd** | 1/3 |
| 5 | 1-6-4-7 | **1st** | 1/3 | 6-4-7-1 | 7th | 0/3 | **1st** | 2/3 |
| 6 | 2-9-5-6 | **2nd** | 2/3 | 9-10-2-6 | 6th | 1/3 | 6th | 1/3 |
| 7 | 4-5-8-1 | **1st** | 3/3 | 4-8-5-1 | **1st** | 3/3 | 4th | 2/3 |
| 8 | 5-8-9-1 | **3rd** | 2/3 | 9-4-8-5 | 4th | 1/3 | **3rd** | 1/3 |
| 9 | 2-1-7-10 | 4th | 2/3 | 1-2-10-7 | **1st** | 2/3 | 4th | 1/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | 2 | 5/9 | 15/27 | 2 (R1 $35.56, R2 $6.41) | 1 (R2 $6.41) | 1 (R2 $7.30) | $8.60 on $18 (−52.2%) |
| Don | **4** | **7/9** | **17/27** | 2 (R2 $6.41, R7 $15.14) | **3** (R7 $15.14, R8 $78.24, R9 $13.39) | 1 (R7 $9.10) | $19.20 on $18 (**+6.7%**) |
| Doug | 3 | 4/9 | 10/27 | 1 (R7 $15.14) | 2 (R7 $15.14, R9 $13.39) | 0 | $13.00 on $18 (−27.8%) |

* Don's #1 won four races (R2, R3, R5, R7) and his top four hit three
  superfecta boxes.
* **R3** split the sources: Don had #1 Essential George first (won); the
  model and Doug had Carlos the Kid (9th).
* Doug's R9 #1 Hannah Boo won ($3.80); his only #1 winner the model and
  Don did not share.

### Consensus #1s (`tracking/consensus_top1.csv`)

* **R1 #8 Miss River Rat** (1.6-1): 3rd, show $2.20. "Lacked early speed,
  moved up on the outside ... closed, racing four wide and was best of
  others."
* **R2 #4 Cajun Cattitude** (0.7-1, fav): **1st**, $3.40 / $2.80 / $2.40.
  Logged under the written rule; **Doug confirmed 2026-11-07** (see Pre-race).

So far (with R2): **6 W, 12 ITM from 16**, all favourites except Miss River
Rat (second choice to #4 Ground Control, 1.3-1). $2 win on all sixteen:
$26.00 on $32 (−18.8%); $2 show $28.50 on $32 (−10.9%). Without R2: 5 W, 11
ITM from 15; $2 win $22.60 on $30 (−24.7%).

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **11/05–11/06** (name matching ON) | Model | 17 | 5 | 12 (71%) | 27/51 | −18.2% |
| | Don | 17 | 7 | 14 (82%) | 32/51 | +12.9% |
| | Doug | 17 | 4 | 9 (53%) | 24/51 | −28.2% |
| **1.3.2** (10/22–11/06) | Model | 76 | 17 | 44 (58%) | 117/228 | −37.1% |
| | Don | 76 | 26 | 50 (66%) | 132/228 | −8.0% |
| | Doug | 74 | 23 | 45 (61%) | 114/222 | −15.3% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.7% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (15 cards) | Model | 128 | 34 | 73 (57%) | 194/384 | −19.4% |
| | Don | 119 | 41 | 76 (64%) | 199/357 | −4.9% |
| | Doug | 82 | 26 | 48 (59%) | 124/246 | −12.0% |
| | Doug, without best guesses | 79 | 24 | 46 (58%) | 118/237 | −17.3% |

* The meet $2 win lines ($206.40 model, $226.40 Don, $144.40 Doug) match
  the ticket replay.
* `model_health --model dpv1.3.2-5track-stretch`: top pick ITM 43/70 =
  61.4%, win 16/70; show ROI −20.7% ($111.00 on $140).
* **The alert still fires:** "top pick ITM over last 29 races is 75.9%,
  above the 68% ceiling". Same window as yesterday's check plus tonight
  (5/9), all record runs logged pre-race (`db19b69` at 08:55, before the
  first post). A hot run, not leakage; tonight pulled it down from 78.6%.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R8 #5 Nana's Corn Muffin (ML 6-1) | | **3rd** at 1.7-1 (fav; show $2.60) | — | — |
| EP4 (R2–R5) | 4-6 / 1-3-7-9-11 / 5-6 / 1-4-6-7 (80 combos) | $40 | miss, **dead in R4** | 3/4 | 3/4/6-1/6-11-1/8/10/11 paid **168.05** |
| LP4 (R6–R9) | 2-5-9 / 1-4-5-8 / 5-8 / 1-2 (48 combos) | $24 | miss, **dead in R8** | 3/4 | 5-4-1-1/8 paid **468.45** |

* EP4: R2 #4 (his #6 scratched late; #6 would have been substituted to #4
  anyway), R3 #1 and R5 #1 hit; **R4 #11 Jabran** (12.8-1) was not on the
  5-6 leg.
* LP4: R6 #5, R7 #4 and R9 #1 hit; **R8 #1 Heavenly Dream** (16.2-1) was
  **his own 4th pick** but not on the 5-8 leg.
* Don's day: **$64 wagered, $0 back.**

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 4 | superfecta wheel, $0.10 | 5,6,7 / 5,6,7 / 5,6,7 / ALL (36 combos) | $3.60 | lost (11-7-4-10) |
| DED | 8 | win, $2 | #9 Bet Towinit | $2.00 | lost (4th) |

Night total: **$5.60 wagered, $0 returned, −$5.60.** **Qualifies for the
DED PP rebate** (at least $2 wagered on the card).

* R4: #11 Jabran (12.8-1) won, so no top three from 5-6-7 could hit. #5 My
  Uncle Leon crossed 3rd and was DQ'd to 7th; #6 Call My Banker (Melancon
  off) 5th; #7 Mahoney Road 2nd. Official super $371.70.
* R8: #9 Bet Towinit (1.9-1) "bobbled at the start, racing near the back
  ... made a wide bid and was outfinished for show" (4th).

## Watch list

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 3 | #7 Carlos the Kid | J Devin Magnon | **1 of 10** | 54.1 | 9th | 2.9 |
| 4 | #3 Briterdayzahead | J Devin Magnon | scratched (morning) | | | |
| 6 | #10 Theboyz Warning | T Ronnie Ward | 4 of 7 | 33.8 | 7th | 10.4 |
| 9 | #7 Little Millie | T Ronnie Ward | 5 of 9 | 28.8 | **2nd** | 4.1 |

Meet tally after 11/06 (`watch_people_tally.csv`; logged record runs only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 28 | 2 | 12 | 8.55 | 12 | **+3.45** (was +3.08) |
| J Devin H. Magnon | 24 | 4 | 8 | 7.86 | 8 | **+0.14** (was +0.68) |
| T Rylee Magnon | 6 | 1 | 2 | 2.26 | 2 | −0.26 |
| T W.B. Calhoun | 19 | 4 | 9 | 6.24 | 9 | +2.76 |

**Added:** horse **D's a Rock** (R8 #8). Shipper from Belmont at Aqueduct
(last start BAQ 5/14, 176 days off, 10 career starts), 2nd in his first DED
start at 4.1-1: "raced within striking distance, moved up around the turn,
made a bid, couldn't get to the winner, but was best of others". Model 6th
of 9 (27.7% P(ITM), 66% coverage, no DB history). Don's #2. Trainer
William E. Morey, J Harry Hernandez.

## Queued (not started)

* Read-only checks once the meet has enough races: first-time starters in
  DED maiden races (tonight's R3: first-time starters ran 1-2-3-4 and the
  model's #1, a raced horse, ran 9th), and last-race long-priced winners.
* New from tonight: check the downloaded EVD/LAD charts for missing races
  (EVD 6/11 has R1–R7 only); MNR 10/05 chart; a decision on adding
  non-corpus tracks (ARP, GIL, PRM, LS, ATO, BAQ, RP, SWF).
