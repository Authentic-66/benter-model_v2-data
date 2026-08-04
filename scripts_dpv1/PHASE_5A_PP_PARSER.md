# Phase 5A — Brisnet PP Parser Port + Small-Scale Test

**Date:** 2026-08-03
**Scope:** port the v1 Brisnet past-performance parser into the DPv1 repo, parse
the existing 64-file PP catalogue, register PP features in the DPv1 config, and
run a directional test on whether PP data changes DPv1's predictions.
**Not in scope:** full retraining, wagering ROI, production integration.

---

## Headline

The parser ports cleanly and the data is good: **57 of 64 files parse, and
99.7% of the starters in the races the catalogue covers now carry PP features.**

The prediction test gives a sharp two-part answer:

| Question | Answer |
|---|---|
| Do PP features carry information the **result charts** don't? | **Yes.** Out-of-fold log-loss gain +0.0017 against a permutation null of −0.0220 ± 0.0043 (p = 0.00). AUC +0.017. |
| Do PP features carry information the **charts + tote market** don't? | **No.** Log-loss gain −0.0189, permutation p = 0.35. AUC −0.017. Longshot-flag effect indistinguishable from the null (p = 0.40). |

The PP feed's information is real, and it is already in the closing price.
That is Phase 4D's conclusion arriving from an independent direction: the
constraint on this project is not *access to handicapping information*, it is
that the tote market has already priced whatever the PP feed publishes.

**Recommendation: this is decision-point outcome 2 with a specific caveat —
a deeper pause is warranted for the current architecture, but the one door
Phase 5A leaves open is a pre-convergence model (see §8).**

---

## 1. Parser port

`scripts_dpv1/brisnet_pp_parser.py`, ported from the v1 repo's
`scripts/brisnet_parser_v2.py` (2,417 lines → 2,050).

### Kept verbatim — this is the asset

ML odds · Brisnet speed figures (best / last / avg-3 / turf / AW) · pace figures
(E1 / E2 / late) · Prime Power + field rank · workouts and engineered workout
features (bullets, 60-day counts, avg pace, days since) · equipment and weight
changes · career records · distance / surface / distance×surface combo records ·
Brisnet proprietary trainer angles · jockey angles · running style · form
trajectory (OLS slope over recent figures and beaten lengths) · last class and
last distance · J/T combo rate · days off · QuickPlay angle counts.

**57 PP features**, mapped onto `entry_pp_features` by
`horse_to_pp_features()`.

### Dropped in the port

| Dropped | Lines | Why |
|---|---|---|
| `IRON_TRAINERS`, `SIRE_SIGNALS`, `IRON_HORSES`, `TRAINER_RULES` | ~250 | Hand-curated v10 signal constants (`'Farrior': ('🔥 IRON CT #1','287W/3yr/31%')`). DPv1 learns connection and pedigree strength from the corpus with shrinkage and time decay; a constant baked into the parser is a prior the model cannot see, audit, or decay. The equivalent DPv1 features already exist. |
| `print_card`, `write_picks_file`, `is_strong_pick`, `is_trainer_hotjt` | ~350 | Betting-workflow output. Phase 5A is data extraction. |
| Kelly sizing + `prob_predict.py` shell-out | ~40 | Same. |
| `write_entries_db` (→ `benter_model.db`) | ~140 | Replaced; output now goes to `racing_full.db`. |
| "is this today's card?" guard | ~8 | Phase 5A parses a back catalogue. |

### The ML-odds discipline

The v1 model used `log_ml` as its **largest coefficient — roughly 40% of the
prediction.** That structural flaw is what motivated the v2 rebuild, and the
port does not carry it:

* `pp_ml_decimal` is one of 57 columns, with no special handling anywhere.
* In `dpv1_feature_config.json` it sits in **bucket 9 (PP Data)**, not bucket 7
  (Market Signals), carrying `"anchor": false` and a note explaining why. The
  morning line is a bookmaker's opinion published before any money is bet; it
  belongs with the other PP-sourced opinions (Prime Power, Brisnet angles), not
  with the post-time tote term the Benter blend uses as its market signal.
* In the prediction test it is one column of a 92-column design matrix and
  earns no coefficient of note.

### Two parser bugs fixed during the port

Both were found by reconciling PP field sizes against result-chart field sizes,
and both were silently losing rows rather than raising errors.

**1. Collapsed silks column dropped whole horses.** `pdftotext` often merges the
silks cell into the owner line, so the anchor reads `10/1  Own: ...` instead of
starting at `Own:`. The v1 anchor (`^Own:` or `^<digits> Own:`) skipped every
such horse — **11 of 85 blocks on `gpx0509y.pdf` alone.** A skipped block is a
missing row, not a visible failure, so it never showed up as a parse error.

**2. Single-letter first words produced `pp_num = 0`.** The program number was
read by a backward scan requiring `[A-Z][a-z]`, so `1  H Abarrio (NA 1)` and
`4  I Wanna Be Me (E/P 1)` failed the match and the horse was discarded. Fixed
by reading the program number off the horse-name line, which carries it
directly.

Combined effect: **3,673 → 4,217 starters staged (+14.8%).**

**3. Jockey-change features fired on nearly every horse.** Today's rider renders
as `EBOW III WARREN` (surname first) while the PP race line abbreviates it
`EbowWI` (surname, then given-name initials in the *opposite* order). The v1
normalizer preserved initial order, producing `ebowiw` vs `ebowwi` — a
guaranteed mismatch. `_normalize_jockey` now sorts the initials.

---

## 2. Parse results — 57/64 files (89.1%)

| Track | Files | Parsed | Races | Horses | Rate |
|---|---:|---:|---:|---:|---:|
| GP | 25 | 20 | 243 | 1,576 | 80.0% |
| CT | 15 | 13 | 121 | 911 | 86.7% |
| FP | 12 | 12 | 94 | 744 | 100% |
| EVD | 11 | 11 | 94 | 899 | 100% |
| MNR | 1 | 1 | 8 | 87 | 100% |
| **Total** | **64** | **57** | **560** | **4,217** | **89.1%** |

### All 7 failures are non-`y` Brisnet products, not corrupt files

| File | Product (from page header) | Cost |
|---|---|---|
| `gpx0509j.pdf` | "Condensed PPs" | none — same card as `gpx0509y` |
| `gpx0509t.pdf` | "Race Summary" (no `Own:` blocks at all) | none — same card |
| `gpx0509v.pdf` | "Condensed Ultimate PP's" | none — same card |
| `gpx0509x.pdf` | "Condensed Ult. PP's w/Comments" | none — same card |
| `gpx0508x.pdf` | "Condensed Ult. PP's w/Comments" | none — `gpx0508y` covers it |
| `ctx0508x.pdf` | "Condensed Ult. PP's w/Comments" | **CT 2026-05-08 lost** — no `y` file exists |
| `CT20260618()_4x9PPs.pdf` | 4×9 card grid; filename has no date token | none — `ctx0618y` covers it |

The parser targets the **`y` product — "Ultimate PP's w/ QuickPlay Comments"**,
which is the richest variant and the one that anchors each horse on an `Own:`
line. Net coverage cost of all seven failures: **one race-day (CT 2026-05-08).**

> **Collection guidance for Phase 5B:** download the **`y`** variant. It is free
> with a qualifying TwinSpires bet and is the only format this parser reads. The
> `x`/`v`/`j`/`t` variants are not substitutes.

---

## 3. Match to results

`racing_full.db` holds **GP + CT + MNR only** (Phase 4A). FP (12 files, 744
starters) and EVD (11 files, 899 starters) parse perfectly but have **no result
corpus to match against** — 39% of the parsed PP data is currently unusable for
supervised work. That is a corpus gap, not a parser gap.

| Track | PP rows | matched | no_race | no_horse | duplicate_card | no_corpus |
|---|---:|---:|---:|---:|---:|---:|
| GP | 1,576 | 1,010 | 83 | 216 | 267 | — |
| CT | 911 | 569 | 280 | 62 | — | — |
| MNR | 87 | 0 | 87 | — | — | — |
| FP | 744 | — | — | — | — | 744 |
| EVD | 899 | — | — | — | — | 899 |

**Raw match rate on corpus tracks: 61.3%. On race-days the corpus actually
holds: 85.0%.** Every gap is accounted for:

* **`no_race` (450 rows)** — six race-days where the *entire day* is missing
  from `racing_full.db`: CT 05-07, CT 05-21, CT 06-11, CT 06-20, GP 06-20, and
  MNR 08-03. The first five are un-downloaded result charts; MNR 08-03 is
  tonight's card, which has not run yet. Not a matching failure — there is
  nothing on the other side of the join.
* **`no_horse` (278 rows)** — **236 (84.9%) are confirmed against the chart's
  own scratch list.** A PP card lists entrants; a result chart lists starters.
  Of the remaining 42, **39 come from `gpx0509a.pdf` alone** (see below), and
  **3** across the whole catalogue are genuinely unexplained.
* **`duplicate_card` (267 rows)** — TwinSpires publishes the same card in
  several products. GP 2026-05-09 has five. They are *not* interchangeable:
  `gpx0509a.pdf` numbers its pages such that its race 1 is the chart's race 2,
  and every race after is offset by one. Rather than let an arbitrary row win a
  `GROUP BY`, `parse_pp_files.py` picks per race-day the file that matched the
  most starters, tie-broken toward the `y` product. 24 of 28 matched files were
  selected; the offset `a` file was correctly rejected.

### The number that matters: coverage of result races

| Track | Races covered | Starters | With PP features | Coverage |
|---|---:|---:|---:|---:|
| GP | 143 | 1,014 | 1,010 | **99.6%** |
| CT | 77 | 570 | 569 | **99.8%** |

Of the starters in races the PP catalogue covers, essentially all of them have
PP features. **220 races, 1,579 entries — 0.78% of the 28,105-race corpus.**

---

## 4. Feature coverage

51 of 57 features clear 50% coverage; 44 clear 80%; 23 are at 99%+.

**100% coverage:** `pp_career_starts`, `pp_days_off`, `pp_running_style`,
`pp_races_in_60d`, `pp_speed_improving`, `pp_first_time_lasix`,
`pp_blinkers_added_today`, `pp_blinkers_removed_today`, `pp_equipment_change`,
`pp_combo_starts`, `pp_combo_wins`, `pp_jt_zero`, angle counts.

**Core signal block:** `pp_best_speed` / `pp_last_speed` / `pp_avg_speed_last3`
92.2% · `pp_best_e2` 92.5% · `pp_best_late` 92.2% · `pp_best_e1` 84.9% ·
`pp_prime_power` 95.6% · `pp_ml_decimal` 96.6% · workouts 99.8% ·
jockey angles 99.7% · trainer angles 81.1%.

### The six features below 50% — all diagnosed, none a parser defect

| Feature | Overall | GP | CT | Cause |
|---|---:|---:|---:|---|
| `pp_best_speed_aw` | 0.0% | 0.0 | 0.0 | Neither track ran an all-weather race in the May–June window. Structurally absent. |
| `pp_distance_delta` | 35.5% | 23.1 | 57.6 | Depends on both today's header distance and the last-race distance. |
| `pp_last_class` / `pp_class_delta` | 38.9% | 46.6 | 25.3 | Class money is only recoverable from some PP race-line formats. |
| `pp_last_dist` | 39.6% | 28.1 | 59.9 | Same. |
| `pp_best_speed_turf` | 39.8% | 56.3 | 10.5 | Requires prior turf starts. CT has no turf course — the 10.5% is shippers. Structural. |

A contributing cause for the distance features: `_header_furlongs` cannot read
mile-and-fraction headers where Brisnet renders the fraction as a mangled glyph
(`1^ Mile`, `1m70yds`). **Deliberately not patched** — the glyph's numeric value
is ambiguous, and guessing a distance wrong is worse than a NULL when
`racing_full.db` already carries exact `distance_yards` from the result charts.

Four of the six (`last_class`, `class_delta`, `last_dist`, `distance_delta`) are
**redundant** with chart-derived DPv1 features that have full corpus coverage
(`class_score_change_from_last`, `distance_change_bucket`). Their low coverage
costs nothing. All six are excluded from the prediction test and flagged
`low_coverage_flag: true` in the config.

---

## 5. Config integration — Bucket 9

`scripts_dpv1/add_pp_bucket9.py` → `dpv1_feature_config.json` **v1.2.0 →
v1.3.0**: 167 → 224 features, **active count unchanged at 100.**

* All 57 PP features ship `"active": false`, `"availability": "PP_AVAILABLE"`,
  with measured `pp_coverage_pct`. They are Phase 5B candidates, not part of the
  trained model — activating them in the main pipeline would null the column for
  99.2% of the corpus.
* `pp_ml_decimal` carries `"anchor": false` plus the rationale.
* Four previously-blocked features now carry `unblocked_by` pointers:
  `recent_bullet_workout` (Doug rank 2, the only blocked rank-1/2 feature in the
  config) → `pp_has_recent_bullet`; `days_since_last_workout`,
  `workout_frequency_30d`, `morning_line_odds` likewise.

Verified: `feature_builder_dpv1.py summarize` still reports 207,976 rows × 107
columns. **The DPv1 core is untouched.** No `scripts/` or `scripts_v2a/` file
was modified.

---

## 6. Small-scale prediction test

`scripts_dpv1/pp_prediction_test.py` → `phase5a_pp_test.json`,
`phase5a_pp_predictions.csv`.

**Sample:** 1,579 entries, 220 races, 18 race-days, GP 1,010 / CT 569.
ITM rate 41.5%.

**Design.** Baseline = DPv1's own out-of-sample `fold_val2026` predictions
(fundamental model trained on 2022–2025, never on 2026). Augmented = an
L2-penalised logistic on 92 PP predictors (50 features + missing flags + running
style) with `logit(baseline)` as a fixed **offset**, so a zero coefficient
vector reproduces the baseline exactly and the augmentation can only earn its
keep by explaining what the baseline got wrong. Evaluated **leave-one-race-day-
out** inside the subset.

**Noise floor.** With 1,579 rows and 92 predictors, a fitting procedure *will*
find something. Every headline number is compared against 40 draws in which the
PP rows are permuted while labels and baselines stay put.

### 6.1 Against the fundamental model (charts only) — PP adds real signal

| | Baseline | Augmented (OOF) | Gain |
|---|---:|---:|---:|
| Log-loss | 0.62185 | 0.62017 | **+0.00168** |
| AUC | 0.6939 | 0.7113 | **+0.0174** |
| Brier | 0.21646 | 0.21448 | +0.00198 |

Permutation null: mean gain **−0.0220**, sd 0.0043. The observed +0.0017 sits
**≈5.5 sd above the null mean, p = 0.00 (0/40).** PP data carries information
the result charts do not. The effect is real; the magnitude is small (1.7
millinats).

Top-3 picks move in **140 of 220 races (63.6%)**; the top pick changes in 94
(42.7%); mean absolute probability shift 0.112.

### 6.2 Against the full blend (charts + tote) — PP adds nothing

| | Baseline | Augmented (OOF) | Gain |
|---|---:|---:|---:|
| Log-loss | 0.57942 | 0.59831 | **−0.01888** |
| AUC | 0.7621 | 0.7450 | **−0.0171** |
| Brier | 0.19502 | 0.20167 | −0.00665 |

Permutation null: mean **−0.0203**, sd 0.0050, **p = 0.35.** The augmented model
performs exactly as well as feeding it *random* features. Top-3 picks still move
in 91 of 220 races (41.4%) — but the movement is noise, not improvement.

### 6.3 The longshot result that did not survive its own noise floor

Against the blend, the flag changes looked striking at first:

| | n | ITM |
|---|---:|---:|
| Longshot band (odds ≥ 8) | 736 | 22.0% |
| Baseline flagged | 396 | 13.4% |
| Augmented flagged | 330 | **19.4%** |
| Newly added | 122 | **31.1%** |
| Newly removed | 188 | **14.4%** |

Added-minus-removed = **+0.168**, a two-proportion z of 3.55. It looks like PP
data finds better longshots.

**It does not.** The permutation null for that same statistic has **mean +0.163
— p = 0.40.** Randomly permuted PP features reproduce the entire effect. The
mechanism is mechanical: any perturbation of a calibrated probability near a
threshold preferentially removes horses the baseline over-rated and adds ones it
under-rated, and the realised outcome correlates with the perturbation direction
by construction. Confirmed independently by AUC *within* the longshot band,
which **falls 0.070** (0.704 → 0.644).

This is the finding the phase most easily could have got wrong, and it is the
reason the permutation null was built before the subgroup was reported.

### 6.4 Where the signal lives (directional only)

Residual correlations against the blend baseline, noise sd ≈ 0.0252 at n=1,579
— so only the top few clear 2 sd, and none clears 3:

| Feature | n | r |
|---|---:|---:|
| `pp_jockey_change` | 1,344 | +0.061 |
| `pp_jockey_first_time` | 1,483 | +0.051 |
| `pp_career_starts` | 1,579 | +0.051 |
| `pp_pos_angle_count` | 1,579 | −0.050 |
| `pp_workout_avg_pace` | 1,576 | −0.046 |
| `pp_workout_count_60d` | 1,576 | −0.042 |
| `pp_prime_power_rank` | 1,510 | −0.041 |

Two things worth noting. `pp_pos_angle_count` correlates **negatively** with the
residual — horses with more positive Brisnet QuickPlay angles underperform the
model's expectation, which is the classic signature of a public signal that is
over-bet. And `pp_prime_power_rank` (negative = better rank predicts better
outcome) is the strongest *rating* in the list, but at r = −0.041 against a
noise floor of 0.025 it is barely distinguishable from zero.

---

## 7. What this means

Phase 4D concluded that 91% of the apparent DPv1 edge was Harville
recalibration rather than information, and recommended pausing until a PP feed
was available. Phase 5A obtained the PP feed and tested it. The result:

**PP data beats result charts. PP data does not beat result charts plus the
closing tote price.**

That is not a contradiction — it is the efficient-market finding stated
precisely. The Brisnet PP feed is a *published* product. Every serious bettor at
GP and CT reads the same speed figures, the same Prime Power, the same trainer
angles. By post time that information is in the price. The measurement is
consistent with `pp_pos_angle_count` correlating negatively with the residual:
the most visible PP signals are the most over-bet.

Phase 4D's recommendation was "only a PP feed changes the odds." Phase 5A tested
that hypothesis directly and **falsified it, within DPv1's current
architecture.**

---

## 8. Recommendation

**Decision-point outcome 2 — deeper pause warranted — with one qualification.**

Do not plan a full Phase 5B retraining on PP features. The measurement above is
small-sample (220 races) but it is not ambiguous in the direction that would
justify the spend: against the blend the augmentation is statistically
indistinguishable from random noise (p = 0.35), and its only apparently positive
subgroup result was fully explained by its own permutation null (p = 0.40).
Collecting 10× more PP files would sharpen a confidence interval that is already
centred on zero.

### The one door this leaves open

The test measures PP value **against the final tote odds** — the closing price,
which DPv1 uses as its market term per Benter. That is the correct test for
DPv1's architecture, and it is the wrong test for a different one:

* §6.1 shows PP data **genuinely beats the fundamental model** (p = 0.00). The
  information is real. It is simply not *private* by post time.
* A model that must commit **before the market converges** — early wagering,
  pick-N tickets constructed hours ahead, morning-line-relative pricing — does
  not get to condition on the closing price. For that model, §6.1 is the
  relevant number and §6.2 is not.

If Doug ever wants to bet into early pools rather than at the bell, the
PP-versus-fundamental result is the foundation to build on and Phase 5A's
parser is ready for it. That is a different project with a different data
requirement (timestamped odds series, which this corpus does not have) and it
should be scoped deliberately rather than drifted into.

### If Phase 5B is pursued anyway

Cost estimate for a defensible full retraining:

| Item | Estimate |
|---|---|
| PP files needed for ~3,000 races (≈10% of corpus) | ~400 files, ~1 year of daily collection at 1–2 tracks |
| Missing result charts to backfill | 5 known race-days; likely more once collection is continuous |
| Corpus gap: FP + EVD have PP data but no results | 23 files / 1,643 starters currently stranded; loading two more tracks is a Phase 4A-scale job |
| Engineering | `feature_builder_dpv1.py` join + activation, ~1 day; retraining grid is existing machinery |
| **Realistic calendar** | **12+ months of collection before the sample supports a conclusion the 220-race test can't already give** |

The binding constraint is collection time, not engineering. That is the honest
reason to pause rather than proceed.

---

## 9. Artifacts

| Path | What |
|---|---|
| `scripts_dpv1/brisnet_pp_parser.py` | Ported parser, 57 PP features, no signal constants, no anchor |
| `scripts_dpv1/parse_pp_files.py` | Batch parse → `pp_entries_raw` / `pp_parsed_files`; match → `entry_pp_features`; `report` |
| `scripts_dpv1/add_pp_bucket9.py` | Registers bucket 9 in `dpv1_feature_config.json` |
| `scripts_dpv1/pp_prediction_test.py` | Offset-logistic test with permutation nulls |
| `scripts_dpv1/phase5a_pp_test.json` | Full test results |
| `scripts_dpv1/phase5a_pp_predictions.csv` | Per-entry baseline vs augmented predictions |
| `racing_full.db: entry_pp_features` | 1,579 entries × 57 PP features, keyed on `entries.id` |
| `racing_full.db: pp_entries_raw` | 4,217 staged rows incl. unmatched, with `match_status` |
| `racing_full.db: pp_parsed_files` | Per-file parse outcome and error message |

### Reproduce

```
python scripts_dpv1/parse_pp_files.py parse
python scripts_dpv1/parse_pp_files.py match
python scripts_dpv1/parse_pp_files.py report
python scripts_dpv1/add_pp_bucket9.py
python scripts_dpv1/pp_prediction_test.py
```
