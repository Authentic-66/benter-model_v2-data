# DED 2026-11-05 — card review

Model `dpv1.3.2-5track-stretch` + `pp-reranker-1.0` (Config Y). Eighth card
on 1.3.2. One logged run, the record: `generated_at = 2026-11-05T09:31:23`,
pre-race, bridged, 69 rows (full fields), commit `631b39c`
(`picks/DED_2026-11-05_20261105-0931.*`). **First card with name matching
ON** (config `name_matching_config.json`, ON from 2026-11-05; header "name
matching: ON", alias 0 / new 1 / ambiguous 0; every row tagged
`name_matching = "on"`).

This pass is read-only on the live model: no changes to 1.3.2, the
rerankers or Piece 1–4 code.

## Pre-race

* **Picks logged before post** (first post 4:41 PM CT, chart time): model
  09:31 CDT, Doug (`8d5485f`), Don 16:24 CST by X (`1e13796`; website
  posting issues).
* **Late scratches** (track list, 5:21 PM ET): R2 #11 Borongan, #12
  Rexinator (also-eligibles); R3 #4 Gary P, #8 Hard Cry; R5 #6 Brilliant
  Deal; R7 #3 Levee Native, #5 Letsgowinthisthing; R8 #7 Sell the Buffalo
  (all vet except the R2 also-eligibles). No model #1 scratched.
* **Late jockey changes:** Jansen Melancon off all five mounts: R2 #1 Life's
  Ride and R3 #7 Here Comes Benny (Casey Fusilier), R6 #3 Coco Bella Blue
  (Javier Antonio Hernandez), R7 #2 Wave Maker and R8 #3 Sweet Kantha (Harry
  Hernandez). R8 #1 Zarlana Misael Alvarez -> Erick Del Cid. The model scored
  them with the original jockeys.
* Other changes: R7 #7 I Forgot the Time first-time Lasix, 120 lb (2 over);
  R2 #5 Mo'z Star Sailor 1 lb over.

### Consensus rule (Doug, 2026-11-05)

Use each source's #1 **after scratches**, from picks logged before post. A
race counts only if all three post-scratch #1s are the same horse. A race
where someone's #1 scratched still counts if the post-scratch #1s all match.

| R | model | Don | Doug | consensus |
|---|---|---|---|---|
| 1 | 3 | 3 | 3 | **#3 Midnight Halo** |
| 2 | 2 | 2 | 2 | **#2 Gomarkgo** |
| 3 | 7 | 7 | 7 | **#7 Here Comes Benny** |
| 4 | 6 | 6 | 8 | no |
| 5 | 2 | 2 (6 scratched) | 3 (6 scratched) | no |
| 6 | 3 | 3 | 2 | no |
| 7 | 1 | 1 | 6 | no |
| 8 | 2 | 2 | 5 | no |

## Load (2026-11-06 morning)

* Chart `Delta Downs/ded-results-2026/DED110526USA.pdf`, read with the
  standard chart parser (pdfplumber). 8 races, 61 starters, 41 exotic rows.
  The 69-entry pre-race card was purged first. 0 errors, 0 parser warnings.
* DB backup: `scripts/racing_full.db.pre-ded1105res.bak`, verified before
  the load: same sha256 as the live DB, `integrity_check` ok on both, and the
  same row counts in six tables.
* Spot checks: **R1 official 1-4-3-5, R7 6-1-2-8 and R8 2-5-3-6, as
  expected.**
* **No dead heats, no DQs** (crossing order = `official_finish_pos` in all
  8 races), **no non-betting starters**.
* **Scratches: exactly the eight on the late list, no others.** R1, R4 and
  R6 had none. Chart reasons: R2 #11/#12 Also-Eligible; R3 #4, #8, R5 #6, R7
  #3, #5 and R8 #7 Veterinarian.

  | R | horse | logged rank | P(ITM) | whose pick |
  |---|---|---|---|---|
  | 2 | #11 Borongan | 12 of 12 | 7.0 | — |
  | 2 | #12 Rexinator | 11 of 12 | 7.3 | — |
  | 3 | #4 Gary P | 7 of 9 | 24.9 | — |
  | 3 | #8 Hard Cry | 9 of 9 | 10.3 | — |
  | 5 | #6 Brilliant Deal | 2 of 7 | 51.1 | **Don's and Doug's #1** |
  | 7 | #3 Levee Native | 2 of 8 | 48.0 | — |
  | 7 | #5 Letsgowinthisthing | 7 of 8 | 30.7 | — |
  | 8 | #7 Sellthe Buffalo | 3 of 8 | 39.0 | Doug's #3 |

* **Two non-finishers:**
  * **R1 #2 Josan** (7.5-1, **model #2 of 9**; the reranker had lifted him
    8.0pp): "raced near the back, clipped heels, stumbled around the first
    turn, pulled up around the final turn, **bled** and transported by
    equine ambulance."
  * R4 #7 She's Extra (28.0-1, model 7th of 8): "broke sharp, dropped back,
    pulled up at the head of the lane and walked off."
* **Jockey changes: exactly the six on the late list**, every other rider
  matched the PP on first and last name. Tagged in the new
  `tracking/late_jockey_changes.csv` for the late-jockey work:

  | R | horse | PP rider → rode | model rank (runners) | P(ITM) | finished | odds |
  |---|---|---|---|---|---|---|
  | 2 | #1 Life's Ride | Melancon → Casey Fusilier | 2 of 10 | 44.2 | 6th | 20.0 |
  | 3 | #7 Here Comes Benny | Melancon → Casey Fusilier | **1 of 7** | 67.5 | 6th | 1.2 (fav) |
  | 6 | #3 Coco Bella Blue | Melancon → Javier Hernandez | **1 of 8** | 63.3 | **2nd** | 0.8 (fav) |
  | 7 | #2 Wave Maker | Melancon → Harry Hernandez | 5 of 6 | 32.5 | **3rd** | 1.0 (fav) |
  | 8 | #3 Sweet Kantha | Melancon → Harry Hernandez | 2 of 7 | 40.8 | **3rd** | 2.1 (fav) |
  | 8 | #1 Zarlana | Misael Alvarez → Erick Del Cid | 5 of 7 | 36.6 | 5th | 18.7 |

  Six horses, summed P(ITM) 2.85, ITM 3. Four of the five Melancon mounts
  went off favourite; the model had two of them #1. One card, no
  conclusion.
* Pick payouts (per $0.50). All paid on full legs (the chart's "Ncorrect"
  = all legs).

  | pool | legs | winning | paid |
  |---|---|---|---|
  | Pick 3 | R1–R3 | 1-10-5 | 415.80 |
  | Pick 3 | R2–R4 | 10-5-6 | 352.90 |
  | Pick 3 | R3–R5 | 5-6-2 | 25.25 |
  | Pick 4 (early) | R2–R5 | 10-5-6-2/6 | **216.00** |
  | Pick 5 (early) | R1–R5 | 1-10-5-6-2/6 | 1,378.45 |
  | Pick 3 | R4–R6 | 6-2-5 | 15.75 |
  | Pick 3 | R5–R7 | 2-5-6 | 22.20 |
  | Pick 3 | R6–R8 | 5-6-2 | 93.70 |
  | Pick 4 (late) | R5–R8 | 2/6-5-6-2 | **141.40** |
  | Pick 5 (late) | R4–R8 | 6-2/6-5-6-2 | 937.05 |

  The `/` legs are the R5 scratch substitute: #6 Brilliant Deal → #2 Shots
  From Above (post-time favourite at 0.3-1, who won).
* `score_predictions.py --track DED --date 2026-11-05`, official figures:
  * The logged top pick was ITM in **7 of 8** and won 3 of 8 (no logged #1
    scratched).
  * Top-pick show ROI +3.8% ($16.60 back on $16).
  * All horses were ITM 24 of 61; 2 DNFs. 61 rows scored (2,277 total).

## Per race (re-ranked among horses that ran)

* **Top-3 wheel:** a superfecta wheel 1,2,3/1,2,3/1,2,3/ALL on the model's top 3.
* **Super box:** a 4-horse superfecta box of the model's top 4 (24 combos).
* **Exacta box:** a $1 exacta box of the model's top 2 ($2 a race).

| R | model top 4 | actual 1-2-3-4 | model #1 fin | winner's model rank | top-3 overlap | top-3 wheel | super box | exacta box | $0.10 super |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3-2-4-9 | 1-4-3-5 | **3rd** (fav) | 6 of 9 (5.3-1) | 2/3 | miss | miss (2 of 4) | 3-2 miss | 86.74 |
| 2 | 2-1-3-7 | 10-2-3-5 | **2nd** (fav) | 5 of 10 (6.3-1) | 2/3 | miss | miss (2 of 4) | 2-1 miss | 46.51 |
| 3 | 7-2-3-5 | 5-9-6-3 | 6th (fav) | 4 of 7 (5.8-1) | 0/3 | miss | miss (2 of 4) | 7-2 miss | 101.59 |
| 4 | 6-8-3-1 | 6-1-4-2 | **1st** | 1 of 8 (2.3-1) | 1/3 | miss | miss (2 of 4) | 6-8 miss | 165.14 |
| 5 | 2-3-1-4 | 2-3-7-1 | **1st** (fav) | 1 of 6 (0.3-1) | 2/3 | miss | miss (3 of 4) | **2-3 hit $4.30** | 3.11 |
| 6 | 3-2-1-7 | 5-3-8-6 | **2nd** (fav) | 5 of 8 (7.5-1) | 1/3 | miss | miss (1 of 4) | 3-2 miss | 55.32 |
| 7 | 1-6-7-8 | 6-1-2-8 | **2nd** | 2 of 6 (4.7-1) | 2/3 | miss | miss (3 of 4) | **1-6 hit $25.10** | 64.35 |
| 8 | 2-3-6-5 | 2-5-3-6 | **1st** | 1 of 7 (4.0-1) | 2/3 | miss | **hit $12.32** | 2-3 miss | 12.32 |

**Model:** the #1 pick **won 3 of 8** (R4 Memory Maker $6.60, R5 Shots From
Above $2.60, R8 Cassy Cassy $10.00) and was **ITM in 7 of 8**, its best ITM
card on 1.3.2. Top-3 overlap was 12 of 24. The top-two exacta box hit **R5
and R7** ($29.40 on $16); the super box hit R8 ($12.32 on $19.20); the top-3
wheel missed all 8.

* **R3** was the one miss: the three-way consensus #1 Here Comes Benny
  (1.2-1, Melancon off) "always raced near the back ... showed little"
  (6th of 7), and the model's #2 Ohm Namo (3.6-1) was last. #5 First Flame
  (model 4th, 5.8-1) went gate to wire. The only race with 0/3 overlap.
* **R1:** model #1 Midnight Halo (0.7-1) "sprinted to the front, drove
  clear ... lacked a late kick" (3rd). #1 Zippy Toga (5.3-1, model 6th of 9)
  won with a wide rally. The model's #2 Josan bled and was pulled up.
* **R4:** the reranker's #1 Memory Maker won going away; the base #1 Shining
  Away ran 7th (see Reranker). The 1.9-1 favourite Cheyenne Moon (model #2)
  ran 6th.
* **R6:** model #1 Coco Bella Blue (0.8-1, Melancon off) "vied for the early
  advantage, drove clear ... couldn't match strides with the winner" (2nd).
  #5 Eskenforaveand Ak (7.5-1, model 5th) won.
* **R7:** model #1 Luau Larry's (Don's POD, 3.0-1) dueled and was
  outfinished by #6 Mo Sippi (model #2, Doug's #1): exacta 6-1 $25.10.
* **R8:** #2 Cassy Cassy (4.0-1) "made a wide bid and got up late". The
  first-time starter #5 Strawberry Streets (53% coverage, model 4th) closed
  for 2nd (watch list, below).
* The model's #1 was the favourite in 5 races (R1, R2, R3, R5, R6): 1 won,
  4 ITM.

### Reranker

The reranker changed the #1 in **one race, R4** (also among runners; logged
pre-race in `tracking/reranker_changes.csv`, now with finishes):

| R | base #1 (base → final) | finished | reranked #1 (base → final) | finished |
|---|---|---|---|---|
| 4 | #3 Shining Away (56.1 → 52.8) | 7th (5.5-1) | #6 Memory Maker (51.9 → 57.1) | **1st** (2.3-1, $6.60) |

**Reranker review rule:** 1 qualifying race so far (counted from the 11/04
card): reranked #1 1 W / 1 ITM, base #1 0 / 0. 39 to go.

Net on the card: #1 wins 3 vs 2, #1 ITM 7 vs 6, overlap 12 vs 13, $2 win
$19.20 vs $12.60. The overlap difference: the base top three had #2 Wave
Maker in R7 (3rd) and #5 Strawberry Streets in R8 (2nd), the reranked one
had #3 Parole Drama in R2 (3rd) instead of #7 AG's Charlie.

Moves of more than 5pp:

| R | horse | base → final | rank among runners (base → final) | finished |
|---|---|---|---|---|
| 1 | #2 Josan | 40.6 → 48.6 (+8.0) | 3 → 2 | DNF (bled, pulled up) |
| 4 | #6 Memory Maker | 51.9 → 57.1 (+5.1) | 2 → 1 | **1st** (2.3-1) |
| 6 | #8 Air Sahara | 30.8 → 24.1 (−6.8) | 5 → 8 | **3rd** (15.7-1) |
| 7 | #1 Luau Larry's | 51.4 → 57.0 (+5.5) | 1 → 1 | **2nd** (3.0-1) |
| 8 | #1 Zarlana | 30.8 → 36.5 (+5.7) | 6 → 5 | 5th (18.7-1) |
| 8 | #8 Funhouse | 38.3 → 31.8 (−6.5) | 5 → 6 | 6th (9.9-1) |

3 of 6 went the right way (Memory Maker, Luau Larry's, Funhouse cut); the
misses were Josan (DNF), Air Sahara (cut to last, ran 3rd) and Zarlana.

| span | races | #1 changed | reranked #1 W / ITM / $2 win | base-only #1 W / ITM / $2 win |
|---|---|---|---|---|
| 11/05 | 8 | 1 | 3 / 7 / $19.20 (+20.0%) | 2 / 6 / $12.60 (−21.2%) |
| 1.3.2 (10/22–11/05) | 67 | 11 | 15 / 39 / $87.00 (−35.1%) | 15 / 38 / $93.20 (−30.4%) |
| **Meet** | 119 | 16 | 32 / 68 / $197.80 (−16.9%) | 32 / 69 / $241.40 (+1.4%) |

`model_health` (logged basis, top-pick scratches excluded) has 1.3.2
**with-reranker 38/61 vs base-only 36/61** (+2; was +1 after 11/04).

## Name matching ON: tonight vs the earlier 1.3.2 cards

**One card only.** Nothing here separates the effect of name matching from
the card itself (field quality, scratches, the five Melancon mounts). The
43-race validation (`name_matching_validation_2026-11-04.md`) expected a
change in log loss of about noise size.

All on the record run, among starters (DNFs count as not ITM). LL and Brier
are on the logged P(ITM) (not renormalised after scratches, the same on
every card). #1 is the re-ranked #1 among runners.

| card | name matching | races | starters | #1 W | #1 ITM | sum P(ITM) | ITM | P(ITM) LL | Brier | $2 win on #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 10/22 | off | 8 | 66 | 1 | 4 | 21.01 | 24 | 0.685 | 0.237 | $5.20 |
| 10/23 | off | 9 | 75 | 0 | 2 | 24.55 | 27 | 0.664 | 0.233 | $0.00 |
| 10/24 | off | 9 | 71 | 1 | 5 | 24.11 | 27 | 0.568 | 0.195 | $4.60 |
| 10/28 | off | 8 | 71 | 3 | 4 | 21.18 | 24 | 0.587 | 0.203 | $14.60 |
| 10/29 | off | 8 | 67 | 1 | 5 | 22.78 | 24 | 0.571 | 0.196 | $11.60 |
| 10/30 | off | 9 | 86 | 2 | 6 | 23.51 | 27 | 0.606 | 0.205 | $10.80 |
| 11/04 | off | 8 | 69 | 4 | 6 | 21.69 | 24 | 0.581 | 0.199 | $21.00 |
| **11/05** | **on** | 8 | 61 | 3 | **7** | 21.82 | 24 | 0.622 | 0.218 | $19.20 |
| 1.3.2 off (7 cards) | off | 59 | 505 | 12 | 32 (54%) | 158.82 | 177 | 0.609 | 0.210 | $67.80 (−42.5%) |
| 1.3.2 on (1 card) | on | 8 | 61 | 3 | 7 (88%) | 21.82 | 24 | 0.622 | 0.218 | $19.20 (+20.0%) |

* **Ranking:** best #1 ITM of the eight 1.3.2 cards, and second-best $2 win
  after 11/04.
* **Probabilities:** P(ITM) log loss and Brier were **worse** than the
  off-card average (third-worst of the eight cards). The confident misses
  carry it: Here Comes Benny 67.5 (6th), Ohm Namo 53.7 (7th), Cheyenne Moon
  54.5 (6th), Shining Away 52.8 (7th), Balitrix 47.7 (5th), Life's Ride
  44.2 (6th), plus Josan 48.6 (DNF). Two of these (Here Comes Benny, Life's
  Ride) had Melancon replaced.
* So tonight's number points both ways (better #1 picks, worse
  probabilities) and is one card. Keep reporting on and off separately (the
  6D review rule) and read it after several more cards.

## Data issues on the model's top picks (`tracking/top_pick_data_issues.csv`)

Same tags as 11/04, now with name matching ON. **No top pick had a data
issue tonight**: all eight had their jockey and trainer linked to charted
history (137 of 138 PP people linked; the one new person is trainer Darryl
T. Balthazar, R6 #2 Balitrix), and none had a stale last race (the
EVD/LAD charts loaded 11/05 morning closed most of that gap). No horse on
the card had a margin / speed-figure contribution over ±0.8 (largest 0.45).
R3 and R6's top picks are noted for the late jockey change, which is not a
history gap.

| R | top pick | J/T history missed | stale last race | finished |
|---|---|---|---|---|
| 1 | #3 Midnight Halo | — | — | **3rd** |
| 2 | #2 Gomarkgo | — | — | **2nd** |
| 3 | #7 Here Comes Benny | — (Melancon off) | — | 6th |
| 4 | #6 Memory Maker | — | — | **1st** |
| 5 | #2 Shots From Above | — | — | **1st** |
| 6 | #3 Coco Bella Blue | — (Melancon off) | — | **2nd** |
| 7 | #1 Luau Larry's | — | — | **2nd** |
| 8 | #2 Cassy Cassy | — | — | **1st** |

All 61 starters by group (logged P(ITM) vs actual):

| group | starters | sum P(ITM) | ITM | sum P(win) | W |
|---|---|---|---|---|---|
| J/T history missed | 1 (R6 #2 Balitrix) | 0.48 | 0 | 0.16 | 0 |
| stale last race | 1 (R2 #6 Chatty Milligan: PP 83 days, DB 273) | 0.24 | 0 | 0.08 | 0 |
| no DB history (R7 #2/#4/#7/#8 shippers, R8 #5 FTS) | 5 | 1.56 | 2 | 0.50 | 0 |
| any of the three | 7 | 2.28 | 2 | 0.73 | 0 |
| none | 54 | 19.54 | 22 | 6.57 | 8 |

On 11/04 (matching OFF, before the EVD/LAD charts) the same groups were 44
J/T-missed and 17 stale of 69 starters; tonight 1 and 1 of 61.

## Low-coverage (<65%) horses

**1 of 61** starters was below 65% coverage: R8 #5 **Strawberry Streets**
(53%, first-time starter, model 4th of 7, P(ITM) 37.0), **2nd** at 2.1-1.
The four R7 shippers were 66–68% (Wave Maker 3rd, Kason's Buckaroo 4th, I
Forgot the Time 5th, Gracie Baby 6th). R7 (Alw/OC $36k, 79%) was the
lowest-coverage race.

## Benchmarks: Don and Doug

Re-ranked around scratches as before (Don gave no alt; Doug has none).

* All three were logged before post (Don 16:24 CST, first post 4:41 PM CT).
* Scratches: **R5 #6 Brilliant Deal was Don's and Doug's #1** (Don → 2-3-1,
  Doug → 3-2, two picks; Doug gave three in R5). R8 #7 was Doug's #3 (→
  5-1-6). No scratch touched Don's or Doug's other races.
* Doug's picks were all regular picks (no passes, no best guesses).

| R | Don (re-ranked) | Don #1 fin | Don overlap | Doug (re-ranked) | Doug #1 fin | Doug overlap | model #1 fin | model overlap |
|---|---|---|---|---|---|---|---|---|
| 1 | 3-1-4-9 | **3rd** | 3/3 | 3-1-5-7 | **3rd** | 2/3 | **3rd** | 2/3 |
| 2 | 2-6-3-1 | **2nd** | 2/3 | 2-10-1-8 | **2nd** | 2/3 | **2nd** | 2/3 |
| 3 | 7-2-9-5 | 6th | 1/3 | 7-9-3-2 | 6th | 1/3 | 6th | 0/3 |
| 4 | 6-4-8-3 | **1st** | 2/3 | 8-4-6-2 | 6th | 2/3 | **1st** | 1/3 |
| 5 | 2-3-1 | **1st** | 2/3 | 3-2 | **2nd** | 2/3 | **1st** | 2/3 |
| 6 | 3-2-1-5 | **2nd** | 1/3 | 2-5-6-3 | 5th | 1/3 | **2nd** | 1/3 |
| 7 | 1-2-8-6 | **2nd** | 2/3 | 6-1-2-7 | **1st** | 3/3 | **2nd** | 2/3 |
| 8 | 2-3-8-5 | **1st** | 2/3 | 5-1-6 | **2nd** | 1/3 | **1st** | 2/3 |

| | #1 wins | #1 ITM | top-3 overlap | top-3 wheel | super box | exacta box | $2 win on #1 |
|---|---|---|---|---|---|---|---|
| Model | 3 | **7/8** | 12/24 | 0 | 1 (R8 $12.32) | 2 (R5 $4.30, R7 $25.10) | $19.20 on $16 (**+20.0%**) |
| Don | 3 | **7/8** | **15/24** | 1 (R1 $86.74) | 1 (R7 $64.35) | 1 (R5 $4.30) | $19.20 on $16 (**+20.0%**) |
| Doug | 1 | 5/8 | 14/24 | 1 (R7 $64.35) | 0 | **3** (R2 $23.70, R5 $4.30, R7 $25.10) | $11.40 on $16 (−28.7%) |

* **The model's #1 matched Don's in all 8 races** (post-scratch), so their
  #1 lines are identical. Doug's matched both only in R1–R3.
* Don's top three were the R1 trifecta (3-1-4 → 1-4-3, $80.40) and his top
  four the R7 superfecta (1-2-8-6 → 6-1-2-8, $64.35).
* Doug's R7 #1 #6 Mo Sippi won ($11.40), his only #1 winner and the one
  race where he had the winner first and the model and Don did not. His R8
  #1 Strawberry Streets ran 2nd.

### Consensus #1s (`tracking/consensus_top1.csv`)

Post-scratch rule (Doug, 11/05; restated in the pre-race section): **R1, R2
and R3**, all the favourite, all logged before post. Added with final odds.

* **R1 #3 Midnight Halo** (0.7-1): 3rd, show $2.20. Led, lacked a late kick.
* **R2 #2 Gomarkgo** (0.5-1): 2nd, place $2.10 / show $2.10. Dueled down the
  lane with #10 Quikonthetrigger (6.3-1) and was outfinished.
* **R3 #7 Here Comes Benny** (1.2-1): 6th of 7, off the board. Melancon off
  (Casey Fusilier).

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
| 11/05 | 1 | #3 Midnight Halo | 0.7 | **3rd** | | |
| 11/05 | 2 | #2 Gomarkgo | 0.5 | **2nd** | | |
| 11/05 | 3 | #7 Here Comes Benny | 1.2 | 6th | | |

So far: **5 W, 10 ITM from 14**, every one the favourite. $2 win on all
fourteen: $22.60 on $28 (−19.3%); $2 show $23.90 on $28 (−14.6%).

### Meet to date, by model version (re-ranked among runners, $2 win on #1)

Model rows are by the version that made the record run. Don and Doug are
split by the same dates. Doug has no picks before 10/21.

| span | source | races | #1 W | #1 ITM | overlap | $2 win ROI |
|---|---|---|---|---|---|---|
| **11/05** (name matching ON) | Model | 8 | 3 | 7 (88%) | 12/24 | +20.0% |
| | Don | 8 | 3 | 7 (88%) | 15/24 | +20.0% |
| | Doug | 8 | 1 | 5 (62%) | 14/24 | −28.7% |
| **1.3.2** (10/22–11/05) | Model | 67 | 15 | 39 (58%) | 102/201 | −35.1% |
| | Don | 67 | 22 | 43 (64%) | 115/201 | −10.0% |
| | Doug | 65 | 20 | 41 (63%) | 104/195 | −13.5% |
| **1.3.1** (10/21) | Model | 8 | 2 | 4 (50%) | 15/24 | −40.0% |
| | Don | 8 | 3 | 5 (62%) | 13/24 | +13.8% |
| | Doug | 8 | 3 | 3 (38%) | 10/24 | +18.8% |
| **1.3.0** (10/10–10/17) | Model | 44 | 15 | 25 (57%) | 62/132 | +15.0% |
| | Don (from 10/14) | 35 | 12 | 21 (60%) | 54/105 | −2.3% |
| **Meet** (14 cards) | Model | 119 | 32 | 68 (57%) | 179/357 | −16.9% |
| | Don | 110 | 37 | 69 (63%) | 182/330 | −5.8% |
| | Doug | 73 | 23 | 44 (60%) | 114/219 | −10.0% |
| | Doug, without best guesses | 70 | 21 | 42 (60%) | 108/210 | −16.0% |

* The meet $2 win lines ($197.80 model, $207.20 Don, $131.40 Doug) match the
  ticket replay.
* `model_health --model dpv1.3.2-5track-stretch` (logged basis, top-pick
  scratches excluded): top pick ITM 38/61 = 62.3%, win 14/61; show ROI
  −19.2% ($98.60 on $122).
* **New alert:** "top pick ITM over last 28 races is 78.6%, above the 68%
  ceiling -- check for leakage". Checked: the last 28 races (22/28 ITM)
  run from 10/29 R4 through 11/05, all scored on record runs logged
  pre-race (11/05 at 09:31, committed in `631b39c` before the 4:41
  first post; 11/04 at 10:14, `ef8416b`). No result could have reached the
  inputs, so this reads as a hot run on a small window, not leakage. Worth
  watching rather than acting on.

### Don's bets (`tracking/don_bets.csv`)

| bet | ticket | cost | result | legs hit | paid ($0.50) |
|---|---|---|---|---|---|
| POD | R7 #1 Luau Larry's (ML 6-1) | | **2nd** at 3.0-1 (place $3.80) | — | — |
| EP4 (R2–R5) | 2 / 2-5-6-7-9 / 3-4-6-8 / 2-6 (40 combos) | $20 | miss, **dead in R2** | 3/4 | 10-5-6-2/6 paid **216.00** |
| LP4 (R5–R8) | 2-6 / 1-2-3 / 1-2 / 2-3-8 (36 combos) | $18 | miss, **dead in R6** | 2/4 | 2/6-5-6-2 paid **141.40** |

* EP4: single #2 Gomarkgo in R2 ran 2nd to #10 Quikonthetrigger (6.3-1).
  The other three legs hit (R3 #5 First Flame, R4 #6 Memory Maker, R5 #2).
  His R5 leg had the scratched #6; #2 was on it in his own right.
* LP4: **died in R6, not R7**: the R6 leg was 1-2-3 and #5 Eskenforaveand Ak
  (his 4th pick, 7.5-1) won. R7 (1-2 vs #6 Mo Sippi, his 4th pick) missed as
  well; R5 #2 and R8 #2 hit.
* Don's day: **$38 wagered, $0 back.**

### Doug's bets (`tracking/doug_bets.csv`)

| track | R | bet | ticket | cost | result |
|---|---|---|---|---|---|
| DED | 6 | superfecta box, $0.10 | 2,3,5,6 (24 combos) | $2.40 | lost (5-3-8-6) |
| DED | 6–8 | Pick 3, $0.50 | 2 / 6 / 1,5 (2 combos) | $1.00 | lost in R6 |

Night total: **$3.40 wagered, $0 returned, −$3.40.**

* R6 super box: #5, #3 and #6 ran 1st, 2nd and 4th; #8 Air Sahara (15.7-1,
  3rd) was not on the ticket. Doug's #1 #2 Balitrix was squeezed at the
  start (chart: "shuffled back at the start", 8th of 8 to the stretch) and
  ran 5th. Official super $55.32.
* Pick 3: R6 #2 lost to #5. R7 #6 Mo Sippi won; the R8 leg 1,5 missed too
  (#2 Cassy Cassy won, #5 Strawberry Streets 2nd). Official 5-6-2 $93.70.
* **New TwinSpires rule from 11/05:** the DED PP rebate ($3.85) now needs
  **at least $2 wagered on the card** (it used to be any bet). Tonight's
  $3.40 qualifies. Flag any future card under $2. (Recorded in both bet
  notes.)

## Watch list

Only one watched starter: **J Devin Magnon on R5 #1 Bayou Baby** (no Ward,
Calhoun or Rylee Magnon starters, no watched horses).

| R | horse | watch | model rank (runners) | P(ITM) | finished | odds |
|---|---|---|---|---|---|---|
| 5 | #1 Bayou Baby | J Devin Magnon | 3 of 6 | 42.0 | 4th | 5.6 |

"Dueled on the front end and faded." Meet tally after 11/05
(`watch_people_tally.csv`; logged record runs only):

| who | starts | W | ITM | logged sum P(ITM) | actual ITM | diff |
|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 26 | 2 | 11 | 7.92 | 11 | +3.08 |
| J Devin H. Magnon | 23 | 4 | 8 | 7.32 | 8 | **+0.68** (was +1.10) |
| T Rylee Magnon | 6 | 1 | 2 | 2.26 | 2 | −0.26 |
| T W.B. Calhoun | 19 | 4 | 9 | 6.24 | 9 | +2.76 |

Devin Magnon split by span / name matching:

| span | starts | sum P(ITM) | ITM | diff |
|---|---|---|---|---|
| 10/10–11/04 (matching OFF) | 22 | 6.90 | 8 | +1.10 |
| 11/05 (matching ON) | 1 | 0.42 | 0 | −0.42 |

Ward, Calhoun and Rylee Magnon are unchanged (no starters). Their gaps from
11/05 on are now on linked history and should be read separately.

**Added:** horse **Strawberry Streets** (R8 #5). First-time starter, maiden
special weight 7f: "lacked early speed, made a late wide bid and got up for
second" — 6th of 7 at the quarter, 5th at the half and in the stretch, 2nd
by a neck at 2.1-1 (ML 6/1). Doug's R8 #1. The model had her 4th of 7 (37.0%
P(ITM), 53% coverage, no DB history). Trainer Lonnie Briley, J Juan Vargas.

## Queued (not started)

Read-only checks once the meet has enough races: first-time starters in DED
maiden races, and last-race long-priced winners.
