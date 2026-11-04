# Jockey / trainer name matching: build and validation, 2026-11-04

**Status: built, OFF by default, NOT live.** Nothing about live card scoring
changes until Doug approves. The live model (`dpv1.pkl`, sha 33bfb329…a918),
the reranker (`dpv1_pp_reranker.pkl`, cd4a5c79…29ea) and the protected Piece
1-4 code (`card_picks.py`, `score_predictions.py`, `model_health.py`,
`retrain_pipeline.py`) are untouched; the hashes were checked on every run.

## TL;DR

* **The bug.** PP spellings ("Barrera Elio J", "RAMIREZ, JR. JULIO") never
  matched the chart spellings ("Barrera, Elio", "Ramirez, Jr., Julio"). The
  loader created an empty jockey/trainer row, so those horses were scored
  with the 0.12 prior for every jockey/trainer win rate and
  `new_trainer_flag = 1`. Training data (charts) never had this problem, so it
  is a live-only skew.
* **The fix works.** On the six DED cards 10/23-11/04 (495 horses), horses
  with a jockey who has chart history go from **311 to 493**, trainer from
  **284 to 494**; **294 horses (59%) gain at least one**. 990 name
  resolutions were logged: 613 exact, 362 by core name, 10 by alias
  (Calhoun), 2 by the Jr./Sr. tie-break, 3 new rows, **0 ambiguous**.
  Spot-check found no wrong match.
* **Update, same day (follow-up):** a small alias table
  (`scripts_dpv1/name_aliases.csv`) now links PP "Calhoun W. Bret" to chart
  "Calhoun, W."; the switch-on arm was re-run with it. All numbers in this
  file are with the alias unless marked "no alias". Three of the four watch
  people (Ward, Devin Magnon, Calhoun) were unmatched on **every** DED PP card
  this meet; see "Watch list".
* **Switch OFF is exactly today's behaviour.** All six cards rebuilt from
  their pre-race backups reproduce the logged record runs bit-for-bit
  (max |dP(ITM)| 1.1e-16, 0 rank changes), and the parser output with the
  switch off is identical to the old code on all 73 staged PP files
  (see "Parse identity").
* **Results: a wash on 43 races, as expected for this sample size.**
  P(ITM) log loss 0.6007 -> 0.5985 per starter (-0.0022, 95% CI -0.0119 to
  +0.0076), Brier 0.2070 -> 0.2062 (-0.0007); #1 in the money 22 -> 20 of 43,
  #1 wins 7 -> 8. The #1 changed in 12 of 43 races. Log loss and Brier do not
  get worse; none of the differences is distinguishable from zero.
* **Recommendation: turn it ON** (set `BENTER_NAME_MATCH=1` for the card
  routine), on the grounds that it removes a known live-vs-training input
  mismatch, not on the short-run results. Details and caveats at the end.

## What was built

| file | change |
|---|---|
| `scripts_dpv1/name_match.py` (new) | switch (`BENTER_NAME_MATCH`, default off), name parsing, `resolve_person`, match log |
| `scripts_dpv1/brisnet_pp_parser.py` | switch on only: today's-jockey regex accepts hyphens, apostrophes, a Jr/Sr/II/III/IV suffix and up to 4 more name parts; past-race jockey regex accepts hyphens ("Nava-marinJ"); commas dropped before the jockey-change comparison ("Ramirez, Jr. Julio" vs "RamirezJJ") |
| `scripts_dpv1/load_pp_card.py` | switch on only: trainer and jockey ids come from `resolve_person` first, then the old get-or-create; every resolution appended to the match log |
| `scripts_dpv1/name_aliases.csv` (new, follow-up) | explicit PP name -> chart name pairs the rule cannot link; one row: trainers, "Calhoun W. Bret" -> "Calhoun, W." |

**Matching rule.** (1) `exact`: the old corpus key already names someone with
a charted start. (1b) `alias`: the PP spelling is in `name_aliases.csv` and
its chart name has a charted start (if not, the note says so and the rule
below runs). (2) Otherwise the *core name*: single-letter initials and
Jr/Sr/II/III/IV removed, remaining tokens joined in order. Only people with a
charted start are candidates. One candidate: `core`. Several: tie-break on
the suffix (`core+suffix`), then on middle initials (`core+initials`). Still
several, or none: a new row exactly as before (`ambiguous` / `new`).

**Switch and log.** `BENTER_NAME_MATCH=1` (also `on`/`true`/`yes`) turns it
on for both the loader and the PP bridge parse; the bridge runs inside
`card_picks.py`, which reads it from the environment, so `card_picks.py` is
not modified. The log goes to `BENTER_NAME_MATCH_LOG` or, by default,
`scripts_dpv1/logs/name_matches.jsonl`. With the switch off nothing is
logged.

## Validation method

Harness: `tracking/name_matching_2026-11-04/nm_card.py` (one card, one arm per
call) and `compare.py`. For each DED card 10/23, 10/24, 10/28, 10/29, 10/30,
11/04:

1. copy `racing_full.db.dedMMDD-run.bak` (the DB just before that card's PP
   load) to scratch;
2. rebuild the card there: `load_pp_card load`, `speed_figures_dpv1 compute`,
   `feature_builder_dpv1 build`, with the arm's environment;
3. score 1.3.2 + pp-reranker-1.0 on the full pre-race field (seed 6001,
   10,000 iters), as logged;
4. **off** arm: compare to the logged record run and stop if it differs.

The live DB was only opened read-only (sha unchanged after every run).
Scoring: #1 = highest P(ITM) among the horses that ran (the nightly re-rank
method); ITM = official finish 1-3; log loss and Brier on P(ITM) over the
starters. 11/04 has no results yet, so it counts for history gains only.

## Reproduction (switch off)

| card | logged rows | rerun rows | unmatched | max abs dP(ITM) | rank changes |
|---|---|---|---|---|---|
| 10/23 | 82 | 82 | 0 | 1.1e-16 | 0 |
| 10/24 | 79 | 79 | 0 | 1.1e-16 | 0 |
| 10/28 | 82 | 82 | 0 | 1.1e-16 | 0 |
| 10/29 | 75 | 75 | 0 | 1.1e-16 | 0 |
| 10/30 | 100 | 100 | 0 | 5.6e-17 | 0 |
| 11/04 | 77 | 77 | 0 | 1.1e-16 | 0 |

## Parse identity

`parse_pp_file` was run on all 73 PP PDFs staged in the DB (CT, DED, ELP,
EVD, FP, GP, MNR; 5,565 horses) three times: old code, new code with the
switch off, new code with the switch on.

* **Old code vs switch off: identical on all 73 files** (deep-equal JSON).
* **Switch off vs on: only three fields change**, and only where they should:
  * `jockey`: 314 horses, every one a `'?'` that now has a name. No jockey
    that the old regex already read changed. The names recovered:
    Ramirez, Jr. Julio 70; Acosta J. D 48; Diaz, Jr. Sunday 44; Mcmahon C.J.
    39; Torrealba J.G. 32; Rios-Conde, Jr. Alexis 24; Nava-Marin Jose 21;
    Camacho, Jr. Samuel 12; Hernandez, Jr. Brian J 9; Arroyo, Jr. Norberto 4;
    Cacha-Padilla Benjamin 3; Santana, Jr. Ricardo 3; Jasim A. Rahim 2;
    Meza J.J. 1; Monserrate, Jr. Jorge A 1; Silva, Jr. Juan P 1.
  * `pp_jockey_first_time`: 314 (the same horses: missing -> computed).
  * `pp_jockey_change`: 416 (those horses, plus horses whose most recent
    race line had a hyphenated rider and was skipped before).

## History gains (switch on)

PP entries whose jockey / trainer has a charted start before the card date.

| card | horses | jockey off | jockey on | trainer off | trainer on | gained either | #1 changed (full field) |
|---|---|---|---|---|---|---|---|
| 10/23 | 82 | 49 | 81 | 47 | 81 | 50 | 2 of 9 |
| 10/24 | 79 | 48 | 79 | 47 | 79 | 46 | 2 of 9 |
| 10/28 | 82 | 54 | 82 | 46 | 82 | 48 | 3 of 8 |
| 10/29 | 75 | 45 | 74 | 39 | 75 | 47 | 3 of 8 |
| 10/30 | 100 | 69 | 100 | 60 | 100 | 54 | 3 of 9 |
| 11/04 | 77 | 46 | 77 | 45 | 77 | 49 | 0 of 8 |
| **all** | **495** | **311** | **493** | **284** | **494** | **294** | |

Mean |P(ITM) on - off| = 2.55pp (max 14.4pp); the base model alone moves
2.56pp, so the change comes through the base model's jockey/trainer
features, not the reranker.

Still unmatched with the switch on: jockeys Del Cid Erick and Del Cid
Fernando on 10/23 only (no charted start before that date; correct) and
trainer Alejandro Ruiz-Rios (1).

11/04 with the alias: the background re-run of 11/04 was stopped by the
machine (low memory) and not restarted. 11/04 has no Calhoun starter
(no Calhoun line in its match log) and no results, so the alias cannot
change it; the 11/04 switch-on files are the first (no-alias) run, copied
from `on_without_alias/`.

## Every name match made (switch on)

Counts are entries across the six cards. All `exact` matches (613) are the
old behaviour and are not listed. Every matched person below has charted
starts on the DED/EVD/LAD/FG circuit (checked); none looks like a different
person with the same name.

**Jr./Sr. tie-break (both collision cases on these cards):**
* Tillis, Jr. Jerry E -> **Tillis, Jr., Jerry** (2), over candidates
  "Tillis, Jerry" and "Tillis, Jr., Jerry".

**Jockeys, by core name (11 people, 164 entries):** Barrera Elio J -> Barrera,
Elio (28); Hernandez Javier A -> Hernandez, Javier (27); Rodriguez Jose L ->
Rodriguez, Jose (24); Pompell Thomas L -> Pompell, Thomas (19); Hernandez
Colby J -> Hernandez, Colby (18); Vargas Juan P -> Vargas, Juan (17); Magnon
Devin H -> Magnon, Devin (9); Rosier Chris R -> Rosier, Chris (9); Murray
Erica M -> Murray, Erica (6); Ramos Adrian B -> Ramos, Adrian (6); Ruiz
Efigenio G -> Ruiz, Efigenio (1).

**Trainers, by core name (45 people, 198 entries):** Gonzalez Isai V (21),
Cano Juan M (16), Larrosa Juan A (15), Brinkman Brett A (14), Hibdon Mark N
(13), Ward Ronnie P (10), Bourgeois Keith G (9), Gelner Jayde J (9), Mojica
Edith A (8), Dison Phillip M (6), Zenon, Sr. Shelton J -> Zenon, Sr., Shelton
(6), Mocklin, Jr. Richard L -> Mocklin, Jr., Richard (5), Johnson, Jr. Henry B
-> Johnson, Jr., Henry (4), Ramirez Rosa E (4), Thompson Kevin J (4), Urbina
Ruperto R (4), Bryant George R (3), Daigle Walter C (3), Duhon Joe O (3),
Mouton Chadwick J (3), Nelson, Jr. Eric D -> Nelson, Jr., Eric (3), Rogers
Andy L (3), Woodley Carl J (3), Celestine Charles R (2), Dunn Henry R (2),
Gomez David C (2), Lorefice Matthew F (2), Pomier Chasey D (2), Sanchez Juan
C (2), Scherer Gary M (2), and one entry each for Bruno Roland L, Cangemi
Daniel R, Chevis Vincent A, Foster Joseph M, Garza Joaquin E, Husak Gary J,
Jackson Richard D, Leblanc John A, Morey William E, Moses Shannon L, Nixon
Thomas W, Richard Russell C, Roberson Kevin K, Thomas William B, Williams
Kevin M. Each maps to the chart name without the middle initial (e.g.
"Gonzalez, Isai").

The full per-entry log (card, race, program, horse, PP name, matched id and
name, candidates, method) is in `name_matching_2026-11-04/matches_MMDD.jsonl`.

**Worth a look:**
* "Rodriguez Jose L" -> "Rodriguez, Jose": the PP race lines show both
  "RodriguezJL" and "RodriguezJ", but the charts have one "Rodriguez, Jose"
  (about 1,900 charted starts at EVD, FG, DED and LAD), so the match is to the only candidate.
* "Morey William E" -> "Morey, William": mostly ELP/GP/MNR, one DED start; a
  shipper trainer, plausible.
* "Thomas William B" -> "Thomas, William": 4 charted starts (DED, FG).
* **W. Bret Calhoun** (watch list): the charts spell him "Calhoun, W." and
  the PP "Calhoun W. Bret". The rule does not link a first-name initial to a
  spelled-out middle name, on purpose, so he is linked through the alias
  table (`alias`, 10 entries, all logged). "Calhoun, W." has 1,405 charted
  starts (FG 766, EVD 248, DED 203, ELP 164, LAD 19, MNR 1); the only other
  Calhoun trainer is Amanda (65 starts), who still matches exactly.

## Scored against results (switch off vs on)

| card | races | starters | #1 W off/on | #1 ITM off/on | LL per starter off | on | Brier per starter off | on |
|---|---|---|---|---|---|---|---|---|
#1 = highest P(ITM) among the horses that ran. Log loss and Brier are per
starter on P(ITM) (lower is better).

| card | races | starters | #1 W off | #1 W on | #1 ITM off | #1 ITM on | log loss off | log loss on | Brier off | Brier on |
|---|---|---|---|---|---|---|---|---|---|---|
| 10/23 | 9 | 75 | 0 | 0 | 2 | 2 | 0.6642 | 0.6403 | 0.2331 | 0.2233 |
| 10/24 | 9 | 71 | 1 | 2 | 5 | 5 | 0.5684 | 0.5773 | 0.1954 | 0.1999 |
| 10/28 | 8 | 71 | 3 | 3 | 4 | 4 | 0.5872 | 0.5762 | 0.2034 | 0.1982 |
| 10/29 | 8 | 67 | 1 | 1 | 5 | 3 | 0.5707 | 0.5899 | 0.1961 | 0.2047 |
| 10/30 | 9 | 86 | 2 | 2 | 6 | 6 | 0.6064 | 0.6046 | 0.2050 | 0.2044 |
| **all** | **43** | **370** | **7** | **8** | **22** | **20** | **0.6007** | **0.5985** | **0.2070** | **0.2062** |

Better with the switch on: 10/23, 10/28, 10/30 (log loss and Brier). Worse:
10/24, 10/29. The first (no-alias) run gave 0.5977 / 0.2058 overall, with
the same #1 W and ITM counts.

Paired race-level bootstrap (10,000 resamples of the 43 races), on - off:

* log loss -0.0022 per starter, 95% CI [-0.0119, +0.0076]; 22 races better,
  21 worse;
* Brier -0.0007 per starter, 95% CI [-0.0047, +0.0032]; 21 better, 22 worse.

Races where the #1 among runners changed (off -> on, P(ITM), finish):

| card | race | off #1 | on #1 |
|---|---|---|---|
| 10/23 | R3 | #1 Ella B Beautiful 45.6, 5th | #2 Leo's Chic 48.9, 4th |
| 10/23 | R8 | #3 Warrior Richard 50.9, **3rd** | #8 Kenmore West 50.0, **2nd** (alias race) |
| 10/24 | R3 | #7 My Priorities 41.7, fell (DNF) | #2 Lucky Spot 40.6, **won** |
| 10/24 | R4 | #10 Millie's Stardust 44.6, **2nd** | #3 Custom Punch 49.0, 6th |
| 10/28 | R1 | #10 Ripple's Rocket 41.5, **2nd** | #3 King Jules 41.1, **3rd** |
| 10/28 | R4 | #3 Z's Guitar 44.4, 7th | #9 All West 48.7, 5th |
| 10/28 | R5 | #4 Alyse Parker 45.9, 4th | #1 Exploding Circle 49.4, 6th |
| 10/29 | R3 | #8 Iron Cutter 46.9, **3rd** | #10 Trupeg's Dynasty 47.9, **won** |
| 10/29 | R5 | #7 Highstakes Hustler 68.4, **won** | #3 Hedge 74.9, 5th |
| 10/29 | R6 | #4 Takethe Hint 54.4, **3rd** | #7 Bellastone Country 53.9, 4th |
| 10/30 | R2 | #9 Allons Betta Lee 44.8, 8th | #10 Miss Super Mo 41.9, 6th (alias race) |
| 10/30 | R3 | #5 Electric Man 40.6, 5th | #1 Truvy's T Rex 40.3, 6th |

12 changed races: on-#1 in the money 4, off-#1 in the money 6. 11/04 (no
results yet): the #1 is the same in all 8 races with the switch on.

## Watch list

**Unmatched this meet (switch off).** Every DED PP file this meet (10/10,
10/14-10/17, 10/21-10/24, 10/28-10/30, 11/04) was re-parsed and each
watch-list name checked against the people with a charted start before that
card (`name_matching_2026-11-04/watch_unmatched.py`, run on the parse snapshots). Cards 10/10-10/22 may have been loaded
with an earlier parser revision; Brisnet spells these names the same way, so
the result should hold.

| who | PP spelling | DED PP entries this meet | unmatched (switch off) | cards |
|---|---|---|---|---|
| T Ronnie P. Ward | Ward Ronnie P | 28 | **28 (all)** | all 12 he had entries on |
| J Devin H. Magnon | Magnon Devin H | 24 | **24 (all)** | all 12 he had mounts on |
| T W.B. Calhoun | Calhoun W. Bret | 20 | **20 (all)** | all 10 he had entries on |
| T Rylee Magnon | Magnon Rylee | 7 | 0 | matched exactly every time |

With the switch on, Ward and Devin Magnon match by core name and Calhoun by
alias. None of them was a "?" parse miss; the cause was always spelling.

**Tally, switch off vs on** (`name_matching_2026-11-04/watch_tally.py`; same
rules as `watch_people_tally.py`: chart trainer/jockey, official finish,
non-betting left out, full-field P(ITM) as logged). Only 10/23-10/30 can be
compared: earlier cards ran on 1.3.0/1.3.1 and cannot be replayed with the
current model, and 11/04 has no results.

| who | starts | with history off/on | ITM | sum P(ITM) off | gap off | sum P(ITM) on | gap on | P moved |
|---|---|---|---|---|---|---|---|---|
| T Ronnie P. Ward | 8 | 0 / 8 | 2 | 2.35 | -0.35 | 2.24 | -0.24 | -0.11 |
| J Devin H. Magnon | 8 | 0 / 8 | 3 | 2.27 | +0.73 | 2.44 | +0.56 | +0.17 |
| T W.B. Calhoun | 9 | 0 / 9 | 3 | 3.03 | -0.03 | 3.77 | -0.77 | +0.75 |
| T Rylee Magnon | 2 | 2 / 2 | 1 | 0.60 | +0.40 | 0.61 | +0.39 | +0.01 |

gap = actual ITM - summed P(ITM). For reference, the full-meet tally
(`watch_people_tally.csv`, 10/10-10/30, switch off) has gaps of Ward +2.51
(24 starts), Calhoun +2.76 (19), Devin Magnon +1.10 (22), Rylee Magnon -0.26
(6).

Reading: on these five cards the missing history explains little of any
gap. Devin Magnon's +0.73 shrinks to +0.56 (about a quarter). Ward's
expectation barely moves and slightly down. Calhoun's moves the most (+0.75
over 9 starts, almost all from the alias; the no-alias run gave 3.01), but he
was already on expectation on these cards, so with the switch on the model
would have over-rated him here by 0.77. Most of the meet-wide gaps for Ward
and Calhoun came from 10/10-10/22, which this comparison cannot replay. Per
card: `watch_tally_output.txt`; per starter: `watch_tally_rows.csv`.

## Recommendation

**Turn the switch ON for the card routine, after Doug's go**, for these
reasons:

1. It is a correctness fix for a live-only input error. The model was
   trained on chart rows where every jockey and trainer carries their real
   history. On PP cards about 58% of horses were scored with priors in their
   place and a spurious `new_trainer_flag`. Turning it on makes live inputs
   look like training inputs.
2. The OFF path is proven unchanged (bit-for-bit reproduction on 6 cards,
   identical parse output on all staged PP files), so the switch is safe to
   leave in the code either way.
3. The 43-race result does not argue against it: log loss and Brier point
   slightly the right way, #1 ITM slightly the wrong way, all well inside the
   noise. A sample this size cannot show a small real effect in either
   direction; that is not a reason to keep a known input error.

Caveats:

* Turning it on changes live P(ITM) by about 2.5pp per horse on average and
  can change the #1 (12 of 43 races here). Mark the switch date in
  PHASE_6E and in the reranker review count, as for a model change.
* Doug's condition (follow-up): log loss and Brier must not get worse. With
  the alias they are 0.6007 -> 0.5985 and 0.2070 -> 0.2062: met, though
  within noise. **Not switched on**; Doug to approve from the next card.
* New PP spellings the rule cannot link go in `name_aliases.csv` (table,
  pp_name, chart_name); the match log shows them as `new`.
* `check_watch_list.py` reads `pp_entries_raw.pp_jockey`; with the switch on,
  Ramirez Jr. and Nava-Marin now appear by name instead of "?". That is the
  intended change.
* Run it for a few cards with the match log on and skim new `core`, `ambiguous`
  and `new` lines after each load, since each new card can bring new names.

How to turn it on (when approved), in the shell that runs the card:

    $env:BENTER_NAME_MATCH = "1"      # PowerShell
    export BENTER_NAME_MATCH=1        # Bash

Set it for both `load_pp_card.py load` and `card_picks.py`, since the PP
bridge parse also reads it.
