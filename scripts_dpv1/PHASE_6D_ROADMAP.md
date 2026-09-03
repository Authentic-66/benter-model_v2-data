# Phase 6D — model gap roadmap

A running catalog of things DPv1 cannot see, found during live use of the
Phase 6B card runner. Each entry is written when a gap shows up in a real
card, with the observed cases attached, so that the fix is argued from
evidence rather than from intuition.

This is a catalog, not a work plan. Nothing here is scheduled. Documented so
far: **Gap #1 (Shipper Blindness)** and **Gap #6 (Maiden Race Chaos)**, each
with an interim warning shipped in `card_picks.py`. Gap #6's recommended fix
was built and measured as main effects (2026-08-31) and again as within-race
interactions (2026-09-01). **Neither worked, and Option C is closed in full** —
see its status block. Gaps #2-#5 are headers only and get filled in as more
races are cataloged.

The two documented gaps overlap: a maiden race full of ship-ins triggers both,
and both trace to the same root cause — history features keyed on `horse_id`
against a corpus that holds four tracks. CT 2026-08-29 R6 is the worked example
of the compound case.

---

## Feature Design Principle

**Any new feature must vary WITHIN a race to affect ranking.**

Constant-per-race features — field averages, race conditions, meet-level bias —
can only affect *calibration* (the absolute level of P(ITM)), never *ranking*
(which horse to bet). Under DPv1's current no-interaction architecture, the
within-race ranking is a monotonic transform of the horse-level linear
predictor, so a term that is identical for every horse in the race shifts all
of them equally and reorders nothing.

Before implementing any candidate feature, classify it:

* **Horse-level** — varies between horses in the same race. Can change
  ranking. Build it.
* **Race-level** — constant across the race. Then either
  **(a)** plan an interaction with a horse-level feature, so the product varies
  within the race and can reorder it;
  **(b)** accept it as a calibration-only addition and measure it as such, with
  a calibration metric rather than top-pick ITM; or
  **(c)** skip it.

This is not theory. Gap #6's field-experience features were implemented as
race-level main effects, verified constant within all 29,285 races, and moved
top-pick ITM by -0.045pp against a corpus-matched control — noise, and
structurally guaranteed to be noise. The full evidence is in the Gap #6 status
block below.

**Necessary, not sufficient.** The same features were then rebuilt on
2026-09-01 as six interaction terms that *do* vary within a race (77.7-98.4% of
races), and they still moved nothing measurable — every subset p > 0.05 on an
exact McNemar test. Passing this principle means a feature *can* affect
ranking, not that it will. The principle rules candidates out cheaply; it never
rules one in.

**Apply this to Gaps #2-#5 before any implementation.** First-pass triage:

| gap | grain | verdict |
|---|---|---|
| #2 Pace Scenario | race-level as stated ("the race's pace shape") | **needs an interaction** — pace shape x *this horse's* running style varies within the race; the shape alone does not |
| #3 Hot Trainer/Jockey Combo | horse-level (each runner has its own J/T pair) | ranking-capable, build directly |
| #4 Declining Speed Trajectory | horse-level (per-horse figure slope) | ranking-capable, build directly |
| #5 Brisnet Angles Ingest | horse-level (per-runner trainer/jockey angles) | ranking-capable, build directly |

A calibration-only feature is not worthless — the Harville inversion, the race
simulator and any ticket EV all consume absolute probabilities, and those are
exactly what calibration governs. It is worthless *when measured by top-pick
ITM*, which is the metric Piece 3 and Piece 4 both report. Measure the thing
the feature can actually move.

---

## Gap #1 — Shipper Blindness

> **STATUS (2026-08-31): Option A is the natural next Phase 6D target.**
>
> It inherited the position from Gap #6 Option C, which was built, tested and
> closed the same day. The reason is the Feature Design Principle above: Option
> C's field aggregates are **race-level** and cannot reorder a race, whereas
> Option A's PP-backed history features — `pp_career_starts`,
> `pp_avg_speed_last3`, `pp_best_speed`, `pp_speed_fig_slope`,
> `pp_surface_winpct` and the rest — are **horse-level**. They differ between
> runners in the same race, so they supply exactly the within-race variation
> the field aggregates could not.
>
> That is not a guarantee they will work. It is the difference between a
> feature that *can* move the ranking metric and one that provably cannot.
>
> **STATUS: SHIPPED — `pp-reranker-1.0`, live in `card_picks.py` (2026-09-01).**
>
> Option A shipped as a **supplementary reranker** rather than as base-model
> features, because joinable coverage is 0.86%. `dpv1.pkl`, `train_dpv1.py`,
> `feature_builder_dpv1.py` and Piece 4 are untouched.
>
> Standalone cross-validated effect **+3.9pp top-pick ITM over 259 races
> (p=0.064)** — suggestive, not established. Positive on every track with
> evaluable data: CT +6.1pp (98 races), ELP +5.6pp (18), GP +2.1pp (143).
> MNR has no evaluable rows.
>
> Rankings now use the reranked P(ITM). The picks page shows base P(ITM)
> alongside it with a `+/-` marker at 2pp, and the log carries `base_p_itm`,
> `final_p_itm`, `reranker_delta` and `reranker_version` per horse.
>
> **Live validation is pending.** `model_health.py` has a base-only vs
> with-reranker section that reads 0/0 until reranked cards are scored;
> ~50-100 races are needed before it means anything. The standalone estimate
> is the prior, not the verdict.
>
> **DIAGNOSIS REVERSED.** This entry originally argued that the missing-data
> block pushes a corpus-invisible horse *down*, so the expensive error was
> treating a low-ranked shipper as a throw-out. Measured on 255 such horses,
> the opposite is true: **the base model on aggregate OVER-ranks
> corpus-invisible horses, it does not under-rank them.**
>
> | horse type | n | actual ITM | base predicts | error |
> |---|---|---|---|---|
> | corpus-visible | 1,655 | 0.421 | 0.408 | -1.3pp |
> | shipper | 108 | 0.324 | 0.350 | **+2.6pp too high** |
> | first-timer | 147 | 0.286 | 0.355 | **+6.9pp too high** |
>
> The mechanism is imputation, not suppression. A blank history block is filled
> with column medians and flagged by `__missing` indicators, which together
> pull the estimate toward a population-level prior around 0.35-0.41. These
> horses actually hit at 0.286-0.324, so the prior is too generous and the
> model lands above their true rate.
>
> **Just Deeds and Outdoor Cat were salient exceptions, not the pattern.** Two
> vivid cases drove the original diagnosis; 255 measured cases reverse it.
>
> **The `shipper_flag` warning in `card_picks.py` stays** — a reader should
> still open the PP on a flagged horse — but its justification has changed. Not
> "the model is unfairly burying this horse" but **"the model cannot see this
> horse and is, on average, too kind to it."** Update any reading of the flag
> accordingly.
>
> `load_pp_card.py` now stages every parsed starter into `pp_entries_raw` in
> the same transaction as the entries insert, plus a `stage` subcommand for
> backfilling cards whose results are already loaded. `pp_entries_raw` is
> **4,266 rows across 56 cards**; CT 2026-08-29 went from 0 rows to 71.
>
> **But coverage is the binding constraint, not ingest.** A backfill sweep on
> 2026-09-01 found **nothing left to stage**: all 45 PP files on the four
> corpus tracks were already staged (38) or are unparseable (7). Joinable
> coverage against `entries` is **0.86%**. See "Coverage ceiling" below before
> planning a retrain around this.
>
> The root cause was not missing code but a manual batch job:
> `parse_pp_files.py parse` was the only writer and was last run
> **2026-08-21T23:29:06**, so every card loaded since had no PP history. It is
> also DROP-and-replace, which is why staging now happens at load time instead
> of depending on someone remembering to re-run it.
>
> **The decisive validation:** Outdoor Cat — the Gap #1 case, ranked 9 of 11
> while being bet to 1/9 — has **0 corpus starts and 9 in PP**, with best speed
> 92 and Prime Power 123. Nine of the nineteen thin-corpus horses on that card
> have more starts in PP than the corpus can see. The other ten are 0 in both:
> genuine first-time starters. **PP separates the shipper from the first-timer,
> which is exactly what the corpus cannot do** and what Gap #6 Option C's third
> component needed.

### What the model can't see

A horse whose entire racing history is at a track outside the training corpus.
DPv1 knows CT, ELP, GP and MNR. A horse shipping in from Laurel, Parx,
Churchill Downs, Penn National or anywhere else arrives with no history the
model can read, and the model does not distinguish "this horse has a weak
record" from "this horse has no record here". Both render as the same thing:
a features block full of NaN and a probability that is a field-average prior
wearing the costume of an assessment.

### Root cause

`feature_builder_dpv1.py` builds every history-derived feature by querying
`entries` and `computed_speed_figures_dpv1` keyed on `horse_id`. Both tables
contain rows for the four training tracks and nothing else. A shipper has no
rows, so the whole history block comes back empty.

The PP bridge (`pp_feature_bridge.apply_to_card`) partially covers this at
prediction time, and it is worth being precise about how far it gets. For
Outdoor Cat on CT 2026-08-29 R8:

* **51** of the model's features were missing before the bridge ran.
* The bridge filled **17** — last-race speed figure, beaten lengths, days
  since last race, distance/class change, equipment and blinkers, running
  style, surface specialist.
* **34 stayed missing**, and they are precisely the career-and-form block:
  `career_win_pct_shrunk`, `career_itm_pct_shrunk`, `last_3_avg_finish`,
  `last_race_finish_pos`, `last_race_won`, `speed_trajectory_3_races`,
  `gate_break_avg_last_3`, `second_race_back_pattern`, `track_specialist_flag`,
  the trainer-angle win percentages, and the pace-projection block.

So the bridge lifts a shipper's coverage — 46% to 64% for Outdoor Cat — while
leaving untouched every feature that describes *how the horse has been
running*. The lift is real but it is not the same thing as the model seeing
the horse.

The data to fix this is already parsed. `pp_entries_raw` holds 75 PP-derived
columns including `pp_career_starts`, `pp_avg_speed_last3`,
`pp_speed_fig_slope`, `pp_best_speed`, `pp_dist_starts`/`pp_dist_wins`,
`pp_surface_starts`/`pp_surface_wins`/`pp_surface_winpct`, `pp_jt_winpct` and
the trainer/jockey angle counts, and where a card has been ingested those
columns are well populated — `pp_career_starts` 100%, the speed block 91.5%,
`pp_prime_power` 95.8%. The feature builder never consults any of it.

**Corrected 2026-08-31.** An earlier version of this entry said the data was
"already in the database", which overstated it. The table holds only **4,318
rows across a handful of dates**, because it is populated by `load_pp_card.py`
and that is not being run routinely. CT 2026-08-29 has **zero rows** in it: its
PP file was parsed directly at prediction time by `pp_feature_bridge` and never
ingested. So Option A has an unmet prerequisite — routine PP ingest — without
which it would have nothing to read on precisely the cards that need it. Treat
that ingest as a small separate task that must land first.

#### PP ingest — implementation notes (2026-09-01)

**What changed.** `load_pp_card.py` gained `stage_pp_entries()` and
`ensure_pp_raw_table()`, called from inside `load_card`'s transaction, plus a
`stage` CLI subcommand that writes PP rows *only*:

```
python scripts_dpv1/load_pp_card.py stage <pp.pdf> --track CT
```

`stage` exists because `load` cannot be used to backfill a card whose results
are already loaded — `remove_card` correctly refuses to delete a real result
chart — and there is no reason to touch `entries` merely to capture PP history.

**Idempotency is at card grain.** Every existing row for `(track, race_date)`
is deleted, then the card is written fresh. Row-level upserting on
`(track, race_date, race_num, program_num)` was rejected because a re-parse can
legitimately produce a *different* set of horses — a scratch dropped, a program
number corrected — and upserting would strand the originals. Verified: staging
CT 2026-08-29 twice leaves 71 rows, not 142.

**Scratches are staged.** The PP file is a pre-race document listing everyone
entered. CT 2026-08-29 staged **71** starters against **59** that went to post;
the 12 scratches are kept, which is the point of a staging table.

**Two compatibility rules with `parse_pp_files.py`,** both load-bearing:
the schema is generated from that module's own `_feature_ddl()` rather than a
copy, so the two writers cannot drift; and `horse_norm` uses that module's
`normalize_name`, because the `match` step joins on it and a second
normalisation would silently fail to match.

**A parser trap worth recording.** `brisnet_pp_parser.horse_to_pp_features()`
expects an older horse-dict shape and returns **almost all NULL** against what
`parse_pp_file` produces today — 3 of 57 columns non-null on a live card. The
current parser returns the `pp_*` columns *directly on the horse dict*, so the
correct staging is `h.get(col)`, which is what `parse_pp_files.py` does and
what the new code mirrors. Anything reaching for the mapper will silently
produce an empty table.

**Known interaction, not fixed.** `parse_pp_files.py parse` still does
`DROP TABLE IF EXISTS pp_entries_raw` and rebuilds from its directory walk.
Rows staged at load time survive that only because PP files live under its
`PP_DIRS` in practice. Making that command incremental is a sensible follow-up
but was out of scope here.

#### What is actually in `pp_entries_raw` now

**4,606 rows, 57 cards, 57 PP feature columns.**

| track | cards | rows | span | |
|---|---|---|---|---|
| CT | 15 | 1,094 | 2026-05-07 .. 2026-08-29 | corpus |
| GP | 16 | 1,576 | 2026-05-08 .. 2026-06-26 | corpus |
| ELP | 2 | 206 | 2026-08-22 .. 2026-08-23 | corpus |
| MNR | 1 | 87 | 2026-08-03 | corpus |
| EVD | 11 | 899 | 2026-05-09 .. 2026-06-25 | no result corpus |
| FP | 12 | 744 | 2026-05-05 .. 2026-06-23 | no result corpus |

Backfilled this session: **CT 2026-08-28 (112), CT 2026-08-29 (71), ELP
2026-08-22 (105)** — the three PP files on disk that had never been parsed.

Column coverage across all rows: **14 columns at 100%, 23 at 90-99%, 14 at
50-89%, 5 at 10-49%, 1 at 0%.**

* **Reliable (100%):** `pp_career_starts`, `pp_days_off`, `pp_running_style`,
  `pp_races_in_60d`, `pp_combo_starts`/`pp_combo_wins`, the equipment and
  blinkers flags, `pp_speed_improving`.
* **Sparse, use with care:** `pp_class_delta` and `pp_last_class` (40.9%),
  `pp_distance_delta` (47.3%), `pp_last_dist` (50.0%), `pp_beaten_len_last`
  (54.7%), `pp_class_drop_count` (59.3%), `pp_jt_winpct` (69.9%).
* **Effectively absent:** `pp_best_speed_aw` at **0.0%** — no all-weather
  surface in this corpus. Do not build a feature on it.
* `pp_best_speed_turf` at 32.9% reflects turf being a minority of these cards
  rather than a parser failure.

#### Coverage ceiling (backfill sweep, 2026-09-01)

**There was nothing to backfill.** Every PP file on disk for the four corpus
tracks is already staged or cannot be parsed:

| track | on disk | staged | unparseable | stageable |
|---|---|---|---|---|
| CT | 17 | 15 | 2 | **0** |
| GP | 25 | 20 | 5 | **0** |
| ELP | 2 | 2 | 0 | **0** |
| MNR | 1 | 1 | 0 | **0** |
| **total** | **45** | **38** | **7** | **0** |

(EVD 11 and FP 12 are also fully staged but have no result corpus to join to.)

The ceiling is **data acquisition, not ingest**. There are 45 PP files, full
stop. More coverage requires more PP files.

##### The 7 unparseable files are a different product, not corrupt

All seven are valid PDFs of 0.66-1.5 MB. Their first page identifies them:

| file(s) | product line |
|---|---|
| working files (`*y.pdf`) | `Ultimate PP's w/ QuickPlay Comments` |
| `gpx0509x`, `ctx0508x`, `gpx0508x` | `Condensed Ult. PP's w/Comments` |
| `gpx0509j`, `gpx0509t`, `gpx0509v` | `Condensed PPs` |
| `CT20260618()_4x9PPs.pdf` | a 4-per-page layout; the text begins with a wagering menu, which is why date detection failed |

`brisnet_pp_parser` targets the Ultimate PP layout. Supporting the condensed
variants is a parser project, and a condensed product may not even carry the
career-stat block that makes this data valuable. Not attempted.

##### Joinable coverage is 0.86%, not the ~2% previously stated

The earlier "~2%" compared raw row count to `entries` and was wrong. The number
that matters is how many entries actually join:

| measure | value |
|---|---|
| `pp_entries_raw` rows | 4,266 |
| entries with a matching PP row | **1,910 of 221,399 = 0.86%** |
| races with any PP row | **259 of 29,910 = 0.87%** |

The gap between 4,266 staged rows and 1,910 joinable ones is mostly EVD and FP
(1,643 rows, no result corpus), plus cards whose results were never loaded and
a residue of program-number mismatches.

Distribution, corpus tracks only: CT 15 cards (May 6, Jun 7, Aug 2), GP 16
(May 7, Jun 9), ELP 2 (Aug), MNR 1 (Aug). Nothing between late June and late
August.

##### Data quality found by looking harder

**A five-fold fan-out, now fixed.** GP 2026-05-09 had **five** source PDFs
staged — `gpx0509a/p/u/y/z` — 425 rows for an 85-horse card. `parse_pp_files.py
parse` inserts per file with no per-card dedup, so every Brisnet product for
that date accumulated. Any Session 2 join on
`(track, race_date, race_num, program_num)` would have silently multiplied
those rows fivefold in a training frame.

Worse, the five did not agree: `gpx0509a.pdf` parsed race 1 with **two horses
on program number 1 and two on number 2**, a mis-parse the other four do not
share. Collapsed by re-staging `gpx0509y.pdf` through the new `stage` path,
which deletes by `(track, race_date)` first. The table now has **one source_pdf
per card, zero duplicated keys**, and is safe to join.

Row count fell 4,606 -> 4,266 as a result. That is a correction, not a loss.

##### The shipper/first-timer split replicates

Across all 28 cards where PP and entries both exist, of horses the corpus shows
as having **zero** career starts:

| | horses | share |
|---|---|---|
| have PP history (**shipper** — invisible to the corpus, not inexperienced) | 108 | **42%** |
| zero in PP too (**genuine first-time starter**) | 147 | 58% |
| total zero-corpus horses | 255 | |

CT 2026-08-29's 50/50 was typical. The per-card range is wide — GP 2026-06-13
was 1 shipper in 14, CT 2026-08-28 was 10 of 10 — which is what one would
expect, since a maiden-heavy card is mostly debuts and a stakes card is mostly
ship-ins. **The distinction is real, it generalises, and DPv1 currently scores
both groups identically.**

##### What this means for Session 2

The feature is well-motivated and the signal is real, but at 0.86% joinable
coverage a PP-backed history feature fires on fewer than one training row in a
hundred. Gap #6 established that a corpus-matched control plus a paired
significance test are the minimum bar for believing a sub-1pp movement; a
feature this sparse is very unlikely to clear it in a fold-level ITM
comparison, however sound it is.

Two honest options for Session 2, worth choosing deliberately rather than
discovering afterwards:

1. **Build it as a prediction-time feature and judge it on live cards**, where
   PP coverage is 100% because the runner is handed the PP file. This is where
   the shipper problem actually bites, and `pp_feature_bridge` already operates
   there.
2. **Build it into training anyway**, accept that the fold comparison will be
   underpowered, and treat the retrain as plumbing rather than evidence until
   PP coverage grows.

What would genuinely change the picture is more PP files — the constraint is
upstream of anything code can fix.

#### PP reranker — built and evaluated standalone (2026-09-01)

`dpv1_pp_reranker_train.py` trains a second-stage logistic model over the base
model's logit; artifact is `dpv1_pp_reranker.pkl`. **`dpv1.pkl`,
`train_dpv1.py` and `feature_builder_dpv1.py` are untouched.** Not yet wired
into `card_picks.py` — that is gated on review.

```
python scripts_dpv1/dpv1_pp_reranker_train.py evaluate --base-folds <folds.csv>
python scripts_dpv1/dpv1_pp_reranker_train.py train    --base-folds <folds.csv>
```

##### Why the small sample is honest here

Two properties, both load-bearing:

* The base contribution is its **out-of-sample fold prediction**, not the
  shipped model's in-sample logit. Otherwise the reranker would learn to
  correct memorisation rather than genuine error.
* The reranker is cross-validated by **race group**, not by entry. Top-pick ITM
  is a within-race ranking metric, so leaking one horse of a race into training
  leaks its rivals' relative standing.

Base logits come from `dpv1_fold_predictions_20260831_corpus_only.csv` rather
than the 2.0 fold file. Same feature set, larger corpus — and it covers ELP and
the August CT cards, which the 2.0 file predates. Using 2.0's folds costs 39
races and excludes the very cards that motivated Gap #1 (220 races, CT+GP only,
May-June).

##### Results — 1,910 rows, 259 races, CT/ELP/GP, 2026-05-08 to 2026-08-29

| model | top-pick ITM | delta | discordant | p (exact McNemar) |
|---|---|---|---|---|
| base (DPv1 alone) | 171/259 = 66.0% | — | — | — |
| reranked (`free`) | 180/259 = 69.5% | +3.5pp | 18 gained / 9 lost | 0.122 |
| **reranked (`offset`)** | **181/259 = 69.9%** | **+3.9pp** | **17 gained / 7 lost** | **0.064** |

**Not significant at 0.05, but far the most promising result Phase 6D has
produced.** Gap #6's best was p=0.135 on a negative delta; this is p=0.064 on a
positive one with discordant races running better than 2:1. It is 259 races and
should be treated as suggestive, not established.

`free` mode learns a **base_logit coefficient of +0.896** — it trusts the base
model at about 90% weight and does not want to discard it. That is a useful
independent check that the base opinion is sound and the PP block is an
adjustment, not a replacement.

##### The finding that revises Gap #1's diagnosis

**The base model OVERRATES corpus-invisible horses. It does not underrate
them.** Measured on the 1,910-row set:

| horse type | n | actual ITM | base model's mean P(ITM) | error |
|---|---|---|---|---|
| corpus-visible | 1,655 | 0.421 | 0.408 | -1.3pp (well calibrated) |
| **shipper** (PP history, corpus blank) | 108 | **0.324** | 0.350 | **+2.6pp too high** |
| **first-timer** (blank in both) | 147 | **0.286** | 0.355 | **+6.9pp too high** |

The fitted coefficients follow: `is_first_timer` **-0.501**, `is_shipper`
**-0.174**. The reranker earns its gain by pushing corpus-invisible horses
*down*, not by rescuing them.

The mechanism is visible directly. The base model puts a corpus-invisible horse
in the top-pick slot in **18 of 259 races (6.9%)**; the reranker cuts that to
**9 (3.5%)**. Across the 47 races where the top pick changed, base hit 23 and
reranked hit 33 — **net +10**.

This contradicts what this entry previously argued. Gap #1 said the missing-data
block "pushes the horse *down* rather than toward the field mean" and that
"treating a low-ranked shipper as a throw-out is the expensive error." On this
sample the opposite holds: the base model is too *generous* to horses it cannot
see, and **Just Deeds and Outdoor Cat were salient exceptions rather than the
pattern**. Two vivid cases drove the diagnosis; 255 measured cases reverse it.

The warning shipped in `card_picks.py` remains useful — a reader should still
check the PP directly on a flagged horse — but the reason has changed. It is not
"the model is unfairly burying this horse". It is "the model cannot see this
horse, and on average it is too kind to it."

##### Final specification (2026-09-01, cleanup pass)

The `pp_running_style` caveat was investigated by refitting three ways. All
figures are cross-validated by race group, offset mode, 259 races.

| spec | top-pick ITM | delta | gain/lose | p |
|---|---|---|---|---|
| A `reference-na` (original) | 181/259 = 69.9% | +3.9pp | 17/7 | 0.064 |
| B `drop` running_style | 178/259 = 68.7% | +2.7pp | 12/5 | 0.143 |
| **C `explicit-na` (adopted)** | **181/259 = 69.9%** | **+3.9pp** | **17/7** | **0.064** |

A and C are identical because they span the same column space — four degrees of
freedom over five style levels, differently parameterised. C is adopted because
it is the *interpretable* parameterisation, not because it scores better.

**The key flags are stable across all three specs**, which is the answer to the
leak worry:

| spec | `is_first_timer` | `is_shipper` |
|---|---|---|
| A | -0.5014 | -0.1736 |
| B | -0.5482 | -0.1822 |
| C | -0.4642 | -0.1698 |

The core signal — demote horses the corpus cannot see — does not depend on
running style at all.

**Is `pp_running_style` genuine or a proxy for "has a record"?** Spec C settles
it by giving availability its own coefficient:

* `running_style__p` **+0.191** — a real style contrast against `e`
* `running_style_unknown` **-0.120** — the pure data-availability term
* `running_style__ep` -0.060, `running_style__s` -0.001

The largest style term is a genuine contrast and it is *larger* than the
availability indicator. The two are not collinear either: `na` appears in 265
rows, 63% of them corpus-invisible, but **89 corpus-invisible rows carry a known
style**. So running style is doing real work, with a second-order availability
component that spec C now isolates rather than hides.

Dropping it entirely (spec B) costs 1.2pp and answers nothing. Occam favours the
simpler model only when the effect is close; a 30% relative reduction is not
close, and spec C is the same size as A while being easier to read in six
months.

**Final coefficients** (`dpv1_pp_reranker.pkl`, `pp-reranker-1.0`, offset mode,
12 features, intercept -0.786):

```
is_first_timer          -0.4642      pp_best_speed__missing  +0.0644
running_style__p        +0.1907      running_style__ep       -0.0603
is_shipper              -0.1698      pp_best_speed           +0.0127
pp_races_in_60d         -0.1242      pp_career_starts        +0.0103
running_style_unknown   -0.1195      career_starts_delta     +0.0052
                                     pp_days_off             -0.0011
                                     running_style__s        -0.0008
```

`career_starts_delta` and `pp_days_off` are inert. The work is done by the two
indicator flags, running style, and `pp_races_in_60d`.

##### Per-track breakdown

| track | races | rows | ITM base | ITM reranked | delta | gain/lose | p |
|---|---|---|---|---|---|---|---|
| CT | 98 | 729 | 69/98 = 70.4% | 75/98 = 76.5% | **+6.1pp** | 8/2 | 0.109 |
| GP | 143 | 1,012 | 90/143 = 62.9% | 93/143 = 65.0% | +2.1pp | 7/4 | 0.549 |
| ELP | 18 | 169 | 12/18 = 66.7% | 13/18 = 72.2% | +5.6pp | 2/1 | 1.000 |
| MNR | — | — | — | — | — | — | — |
| **all** | **259** | **1,910** | **171/259 = 66.0%** | **181/259 = 69.9%** | **+3.9pp** | **17/7** | **0.064** |

**The effect is positive on every track that has evaluable data**, which is the
generalisation check. It is not a CT-only artifact — though CT (+6.1pp) carries
most of it and GP (+2.1pp) is weak.

MNR has no rows: its single PP card (2026-08-03) has no loaded entries to join
to. ELP's 18 races are too few to mean anything on their own, which is a pity —
at **38.5% corpus-invisible runners** against CT's 8.4% and GP's 12.7%, ELP is
where the reranker has by far the most to do and the least sample to prove it.

##### Deployment verification, CT 2026-08-28 and 2026-08-29

Both cards generated successfully, 21 races, 159 horses.

* **Reranker fired on 159 of 159 horses (100%)** — the predicted outcome for a
  live card handed a PP file, and the reason this was built as a
  prediction-time reranker rather than a training feature.
* All four log fields populate on every row; `reranker_version` is
  `pp-reranker-1.0` throughout.
* Logit delta ranged -0.657 to +0.664, mean +0.053. **76 of 159 horses moved
  at least 2pp** in P(ITM).

**Two of 21 races had the top pick change, and they split one-all.**

| race | base top pick | reranked top pick | outcome |
|---|---|---|---|
| CT 8/29 R6 | #6 Improbable Dream 47.9 -> 36.5 (-0.657) | #7 Saint Shance 36.3 -> 52.3 (+0.485) | **reranker right** — Saint Shance 2nd, Improbable Dream 6th |
| CT 8/29 R8 | #10 Solomons Gold 70.1 -> 68.5 (-0.057) | #2 Outdoor Cat 64.1 -> 68.7 (+0.228) | **reranker wrong** — Solomons Gold 2nd, Outdoor Cat DNF |

R6 is the mechanism working as designed: Improbable Dream has 0 corpus starts
and 5 PP starts with no speed figure; Saint Shance has 2 corpus and 7 PP starts
with a best speed of 88. The reranker demoted the one PP could not vouch for
and promoted the one it could.

R8 is worth recording plainly. **Outdoor Cat — the horse this entire gap was
named for — was promoted to top pick by the reranker and then did not finish.**
The base model's pick finished second. One race proves nothing either way, but
it is a fitting coda to the diagnosis reversal: the anecdote that motivated
Gap #1 did not pay off even once the model was rebuilt to act on it.

##### Notes for whoever picks this up

* The artifact is a `__main__` pickle. Use
  `dpv1_pp_reranker_train.load_reranker()`, never a bare `pickle.load`.
  `card_picks.get_reranker()` wraps it and returns None on any failure, so a
  missing or broken artifact degrades to base-model behaviour with a warning
  rather than killing the card.
* Inference builds its features by calling the training module's own
  `build_features()`, so the two cannot drift apart. A feature-name mismatch is
  detected and skips the rerank rather than scoring against the wrong columns.
* The `pp_best_speed` imputation median (79.0) is stored in the artifact's
  `training_notes`. Without it a live card would impute against its own field
  and use a different scale from the fitted coefficients.
* The adjustment is applied to the *fundamental* probability and then pushed
  back through `normalise_itm` and `invert_harville`, so P(win) and the
  simulator stay consistent with the reranked P(ITM) instead of describing a
  different race.

##### Session 3 follow-ups

1. ~~**`parse_pp_files.py` per-card idempotency**~~ — **DONE 2026-09-02.**
   `parse` gained an `--incremental` flag: `CREATE TABLE IF NOT EXISTS` instead
   of `DROP`, and each parsed card replaces only its own rows. Default stays
   drop-and-replace for backward compatibility. Card-grain replacement rather
   than row-grain UPSERT, because the table has no UNIQUE constraint on
   `(track, race_date, race_num, program_num)` and adding one is unsafe — the
   parser has emitted two horses on the same program number in one race, which
   a unique index would turn into an insert failure.

   It also closes the fivefold-multiplication hole: parsing a second Brisnet
   product for a card now replaces rather than accumulates, and warns naming
   the superseded source. Verified on a database copy — 4,266 rows preserved,
   zero duplicate keys, zero cards with multiple sources; default mode
   reproduces the old 4,606-row state exactly.

2. **PP acquisition automation** — **now unblocked.** New PP files can be
   staged without a full rebuild, either through
   `parse_pp_files.py parse --incremental` for a catalogue sweep or
   `load_pp_card.py stage` for a single card. Coverage at 0.86% remains the
   binding constraint on everything in Gap #1 and is upstream of anything code
   can fix; this removes the ingest friction that made growing it painful.

##### Loading the artifact

The pickle is written by this script run as `__main__`, so
`PPReranker` is pickled as `__main__.PPReranker` and a bare `pickle.load`
elsewhere raises AttributeError — the same property `dpv1.pkl` has. Use
`dpv1_pp_reranker_train.load_reranker()`, which installs the shim.

##### Feature notes (superseded by the cleanup pass above)

The `pp_running_style` caveat recorded here on first build — that the one-hots
might be re-encoding "has a racing record" — was investigated and largely
cleared. Spec C isolates the availability term at -0.120 against a genuine
style contrast of +0.191, and the two indicator flags are stable whether style
is included or dropped. Kept as a record of the concern and how it was settled.

##### An implementation bug worth recording

The first `offset` implementation fitted `w . X` against `y` *ignoring*
`base_logit`, then added `base_logit` at prediction time. That is not an offset
model — it is an equal-weight ensemble of two full predictors, double-counting
the signal, and it showed up as an intercept of **-2.59** compensating for the
doubled scale. It scored *better* (70.3%) precisely because ensembling helps,
which is exactly how such a bug survives review.

Replaced with a true penalised offset fit (L-BFGS, `fit_offset_logistic`),
since sklearn has no offset term and statsmodels is not installed. Corrected
intercept is **-0.884** and the mean absolute logit shift fell from 0.452 to
0.192.

##### Session 3 candidates (noted, not started)

1. **Make `parse_pp_files.py` per-card idempotent** — scope its
   drop-and-replace to one card instead of the whole table, so it can be run
   routinely without wiping load-time staged rows.
2. **PP file acquisition automation** — coverage is the binding constraint at
   0.86%, and it is upstream of anything code can fix.

#### Three things that affect Option A's feature design

**1. Start counts are far more reliable than speed figures.**
`pp_career_starts` is populated for every row; the speed block is 91-95% and,
more importantly, is often NULL *precisely for the lightly-raced horses that
matter here*. On CT 2026-08-29, Reportittourlawyer has 2 PP starts and no
`pp_best_speed` at all. A shipper feature built on PP speed will be NULL for a
meaningful share of the horses it exists to serve; one built on PP start counts
will not.

**2. The first-timer/shipper split is now available and is the single most
valuable thing here.** `pp_career_starts = 0` with `career_starts = 0` is a
true debut runner; `pp_career_starts > 0` with `career_starts = 0` is a shipper
the corpus cannot see. Nine of nineteen thin-corpus horses on CT 2026-08-29
fell on the shipper side. These are opposite situations that DPv1 currently
scores identically, and this is horse-level, so it can reorder a race — unlike
the field aggregates of Gap #6 Option C.

**3. Coverage is thin and recent, which caps what a retrain can prove.**
Superseded by the Coverage ceiling section above: the real joinable figure is
**0.86%**, not the ~2% first stated, and a backfill sweep found nothing left to
stage. Concentrated in May-June and late August 2026. A PP-backed history fallback will therefore fire
on a small minority of training rows. That is not a reason not to build it, but
it does mean a fold-level ITM comparison may be underpowered in the same way
Gap #6's was — and the Gap #6 sessions established that a corpus-matched
control plus a paired significance test are the minimum bar for believing any
sub-1pp movement. Expect to need PP files loaded across many more cards before
a retrain can settle the question.

### How it manifests in picks

The shipper ranks low, usually mid-pack to last, with a coverage figure in the
40s. The morning line disagrees sharply — the horse is often favoured — and
the live tote disagrees more sharply still. The model is not making a
contrarian call it can defend. It is ranking a horse it cannot see, and the
missing-data block pushes the horse *down* rather than toward the field mean.

The tell is the combination: low coverage, low rank, short price.

### Observed cases

| Date | Race | Horse | Model rank | ML | Coverage | Notes |
|---|---|---|---|---|---|---|
| 2026-08-28 | CT R3 | #2 Just Deeds | 4 of 8 entered (6 started) | 3/5 | 45% | **Won**, final odds 1/5, despite stumbling at the start. Prime Power 116.1. Zero prior starts in corpus — the only `entries` row for this horse is the race itself. |
| 2026-08-29 | CT R8 | #2 Outdoor Cat | 9 of 11 (6 of 11 with the PP bridge applied) | 3/5 | 46% | Bet to 1/9 live pre-race. Prime Power 123.0. Zero prior starts in corpus. |

Both horses were the shortest price in their race and both sat in the bottom
half of the model's ranking. Neither was a first-time starter — both had full
past-performance lines in the Brisnet PP file, parsed and available.

### Frequency estimate

Measured as the share of starters with fewer than two prior starts in the
corpus at the time of their race:

| Track | Window | Thin-history starters |
|---|---|---|
| CT | 2026-07-30 → 2026-08-29 | 140 / 920 = **15.2%** |
| ELP | 2026-08-01 → 2026-08-23 | 656 / 883 = **74.3%** |

CT's figure is the one that matters for routine use: roughly one starter in
seven, or **one to two per race**. ELP's 74.3% is a different problem in
degree — a boutique meet whose runners nearly all ship in — and it is the
reason the Phase 6C ELP model underperforms its home-track counterpart.

Applying the interim warning rule to live cards gives a consistent picture:
9 of 71 horses flagged on CT 2026-08-29 (12.7%), 5 of 57 on CT 2026-07-25
(8.8%).

### Impact on picks

What a reader might get wrong:

* **Treating a low-ranked shipper as a throw-out.** This is the expensive
  error. A rank of 9 of 11 reads as a considered judgment; for a shipper it is
  an absence of judgment. Just Deeds won at 1/5 from rank 4.
* **Reading the model/market disagreement as an edge.** The whole value of
  DPv1's fundamental is that it forms an opinion without looking at the board,
  so disagreement with the price is normally informative. On a shipper it is
  not information, it is a blind spot, and betting against the market on that
  basis is betting on nothing.
* **Trusting P(ITM) as calibrated.** For a shipper the probability is closer
  to a prior than an assessment, and its position in the ranking is largely an
  artifact of how the missing-data block happens to score.
* **Exotics construction.** A shipper wrongly excluded from a tri/super box is
  a structural hole in the ticket, not a marginal one.

### Proposed fix — options

**Option A — PP-backed history fallback in the feature builder.**
When a horse has no corpus history, populate the history block from
`pp_entries_raw` instead of leaving it NaN. The data is already parsed and
stored; the work is a fallback join in `feature_builder_dpv1.py`, a scale
reconciliation, and a retrain.
*Effort: medium-large, roughly 2-4 sessions.*

> **PREREQUISITE — do not start Option A until this is done.**
> `load_pp_card.py` must be fixed so that PP cards are actually ingested into
> `pp_entries_raw` as a matter of routine. The table currently holds 4,318 rows
> across a handful of dates and has **zero rows for CT 2026-08-29**, whose PP
> file was read directly at prediction time by `pp_feature_bridge` and never
> stored. Building the fallback join first would produce a feature that is NULL
> on exactly the cards it exists to serve, and worse, would look like it worked
> on the few dates that happen to be loaded. Fix the ingest, confirm coverage
> across recent cards, then build the join.
> *(Agreed with Doug, 2026-08-31.)*

Risks, both real:
- **Scale mismatch.** Brisnet speed figures are not `computed_speed_figures_dpv1`
  figures. Feeding them into the same column without calibration would put two
  different units in one feature. A mapping has to be fitted on horses that
  appear in both sources.
- **Leak class.** The obvious implementation adds a "history came from PP"
  indicator, which is a missingness-derived feature — precisely the class that
  has bitten this project before. If such an indicator is added it must be
  validated the way the earlier leaks were, not assumed safe.

**Option B — load result charts from the shipper tracks.**
Acquire and load Laurel, Parx, Churchill, Penn National and the rest, so the
shippers stop being shippers. This is the only option that fixes the problem at
its source rather than patching around it.
*Effort: large and open-ended.* Per-track parser validation, an unbounded data
acquisition commitment, a corpus rebuild and a retrain. The track list has no
natural end — CT alone draws from a dozen tracks.

**Option C — coverage-aware shrinkage at prediction time.**
Do not add information; stop the model from spending information it does not
have. When coverage is low, shrink the horse's score toward the field mean
instead of letting the missing-data block push it to the bottom.
*Effort: small, roughly 1 session.* Purely a runtime change, no retrain.
It would not have ranked Just Deeds first, but it would have moved it from
"throw-out" to "unknown", which is the honest answer.

**Option D — warning only.** Implemented; see below.

### Recommended option and why

**Option A**, with **Option C** shipping alongside it as a stopgap.

Option A is recommended because the data already exists in the database. This
is not a data acquisition problem dressed as a modelling problem — the PP files
are parsed, `pp_entries_raw` is populated, and the feature builder simply never
looks at it. That makes A by a wide margin the best value per unit of effort,
and it addresses the actual cause: the history block is empty when a filled
version is sitting one join away.

Option B is the theoretically correct fix and should not be attempted. It
trades a bounded engineering task for an unbounded data-acquisition
commitment, and it would still leave every *new* shipping track blind until
someone noticed and loaded it.

Option C is recommended alongside rather than instead, because it is cheap,
needs no retrain, and is honest in a way A is not yet: until A is validated,
shrinking toward the mean states "no opinion" rather than manufacturing one.

The sequencing matters: C is safe to ship immediately, A needs a retrain and
therefore a Piece 4 promotion decision, which needs a much larger out-of-sample
window than currently exists.

### Interim mitigation — shipped

`card_picks.py` flags likely shippers inline. A horse is flagged when **corpus
coverage is under 60%** *and* it has **fewer than two prior starts** across
CT/ELP/GP/MNR. Both conditions are required: low coverage alone catches
first-time starters, who are genuinely unknown to everybody and not a model
failure; no corpus history alone catches horses the today's-race fields still
describe well.

The warning prints under the horse's reasons block:

```
        ⚠ SHIPPER — check PP directly, model may be blind to prior form
```

Coverage for this test is measured **before** the PP bridge runs. The bridge
lifts a shipper's coverage substantially — 46% to 64% for Outdoor Cat — which
would push the horse back over the threshold and silence the warning on exactly
the runs where the reader has the PP file open. What the warning is about is
what the corpus knows, and that is the pre-bridge number.

Every logged prediction now carries `shipper_flag` and `corpus_coverage`, so
`model_health.py` can eventually report shipper-warning frequency and, once
enough cards accumulate, the ITM rate of flagged horses against unflagged ones.
That comparison is the empirical case for or against Option A.

**This is a warning, not a fix. The model is exactly as blind as it was.**

---

## Gap #2 — Pace Scenario

*Placeholder.* The model reads projected pace per horse but has no explicit
representation of how a race's pace shape collectively advantages front-runners
or closers. To be documented with observed cases.

## Gap #3 — Hot Trainer/Jockey Combo

*Placeholder.* Trainer and jockey win rates enter separately; the combination —
a barn and a rider who win together at a rate neither achieves apart — is not
represented. `pp_entries_raw` already carries `pp_jt_winpct` and
`pp_hot_jt_combo`. To be documented with observed cases.

## Gap #4 — Declining Speed Trajectory

*Placeholder.* `speed_trajectory_3_races` is a single slope and may not
distinguish a horse regressing off a peak from one improving off a low base.
To be documented with observed cases.

## Gap #5 — Brisnet Angles Ingest

*Placeholder.* The PP parser extracts trainer and jockey angle statistics
(`pp_has_strong_trainer_angle`, `pp_positive_trainer_angles`,
`pp_pos_angle_count`, `pp_neg_angle_count`) that no model feature consumes.
To be documented with observed cases.

---

## Gap #6 — Maiden Race Chaos with Underraced Horses

### What the model can't see

A horse that has barely run, and — more damagingly — a *field* that has barely
run. Maiden races are non-winners by definition and are weighted heavily toward
first- and second-time starters. DPv1's signal lives in its history block, so a
maiden race is the case where the model has structurally least to work with,
and the shortfall is not confined to the individual blank horses.

### Root cause

Three mechanisms compound.

**1. Thin history per horse.** Every history feature is built from `entries`
and `computed_speed_figures_dpv1` keyed on `horse_id`. A horse with zero to two
starts has zero to two rows, so career win%, ITM%, `last_3_avg_finish`,
`speed_trajectory_3_races` and the rest are empty or computed from a sample too
small to mean anything.

**2. The model cannot tell "never raced" from "never raced here."**
`career_starts` is corpus-derived. A first-time starter reads 0, and so does a
shipper with twenty runs at Laurel. These are opposite situations — one horse
is unknown to everybody, the other is well documented somewhere the corpus
cannot see — and the model treats them identically. On CT 2026-08-29 R6 the
four horses showing 0 career starts were all also shipper-flagged; nothing in
the feature set distinguishes which of them had actually never run.

**3. Race-level contamination.** Pace projection (`expected_pace_shape`,
`pace_pressure_in_race`, `early_pace_position_projected`), class-of-field and
the field-relative features are computed *across the whole field*. A few blank
runners degrade those estimates for the experienced horses standing beside
them. This is why the failure is not confined to low-coverage horses: on
CT 2026-08-29 R3 the top pick had **80%** coverage and still finished 5th, and
on R5 the top pick had 86% and finished 4th.

### How it manifests in picks

The model's top pick in a maiden race is frequently the horse that simply has
the most data rather than the most ability — an experienced maiden ranked first
because the alternatives are blank. The winner then comes out of the blank
block, where the model had no opinion to offer. On CT 2026-08-29 the winners of
R5 and R6 were the model's rank 2 and rank **7**; R3's winner was disqualified.

### Observed cases

All three from CT 2026-08-29, the card that prompted this entry.

| Date | Race | Horse (top pick) | Model rank | ML | Coverage | Notes |
|---|---|---|---|---|---|---|
| 2026-08-29 | CT R3 MSW WV-bred | #3 Stettie Hayesen | 1 of 7 | 9/5 | 80% | Finished **5th**. Race won by #5 Conejo Dorado (2 career starts) who was **disqualified** — the race has no recorded winner in the DB and is excluded from WIN denominators. 5 of 7 starters had under 3 career starts. |
| 2026-08-29 | CT R5 MSW WV-bred | #7 Goldeck | 1 of 12 | 7/2 | 86% | Finished **4th**. Winner #10 Knight Sage (6/5 favourite) was model rank 2. 8 of 12 starters underraced. Doug reports the 3-track model picked this winner; no 3-track run is in the prediction log, so that is unverified here. |
| 2026-08-29 | CT R6 MSW open | #6 Improbable Dream | 1 of 10 | 15/1 | 64% | Finished **6th**. Winner #8 Zaptastic (26 career starts) was model rank **7**. 6 of 10 underraced, **4 also shipper-flagged** — the compound-broken race, Gap #1 and Gap #6 firing together. |

The card's three maiden races went **0 for 3** on top-pick ITM. Its five
non-maiden races went 3 of 5.

### Frequency estimate

Across all results-loaded races in the corpus, share with at least one starter
under 3 corpus career starts:

| | races | with an underraced starter |
|---|---|---|
| Maiden (all MAIDEN* types) | 9,081 | 8,934 = **98.4%** |
| Non-maiden | 20,084 | 14,199 = 70.7% |

Maiden races are **9,081 of 29,165 = 31.1%** of the corpus, so this is roughly
one race in three.

**The presence of a single underraced starter is close to vacuous on maidens.**
At 98.4% it barely narrows anything. The discriminating measure is the *share
of the field* that is underraced: median **67%**, mean 65%, and 44.1% of maiden
races have more than three-quarters of the field underraced.

The flag was moved onto that share on 2026-08-31. Thresholds evaluated against
the whole corpus, and against the three observed cases the threshold has to
keep (R3 = 5/7 = 71.4%, R5 = 8/12 = 66.7%, R6 = 6/10 = **60.0%**):

| rule | maidens flagged | share of all races | keeps R3/R5/R6? |
|---|---|---|---|
| any underraced starter (original) | 8,934/9,081 = 98.4% | 30.6% | yes |
| share >= 50% | 6,493 = 71.5% | 22.3% | yes |
| share > 60% | 5,127 = 56.5% | 17.6% | **no — drops R6** |
| **share >= 60% (adopted)** | **5,302 = 58.4%** | **18.2%** | **yes** |
| share >= 67% | 4,455 = 49.1% | 15.3% | no — drops R5 and R6 |
| share >= 75% | 4,007 = 44.1% | 13.7% | no — drops all three |

**The comparison is `>=`, not `>`, and that is load-bearing.** R6 — the worked
compound-chaos case, the one race on the card where four runners were also
shipper-flagged — sits at exactly 0.60. A strict `>` would drop precisely the
race the threshold was chosen to catch.

`>= 60%` cuts maiden flagging from 98.4% to **58.4%**, and flagged races from
30.6% to **18.2%** of all racing — roughly one race in five instead of one in
three. Worth being straight about the trade-off: it still flags a majority of
maiden races. Getting below half needs `>= 67%`, which drops R5 and R6. Given
that both of those are cases Doug identified from live use, the observed cases
win over the round number.

### Impact on picks

* **Trusting a top pick that is closer to a coin flip.** A rank of 1 in a
  maiden looks identical on the page to a rank of 1 in an allowance, and it is
  not the same object. On CT 2026-08-29 R6 the winner was the model's 7th
  choice.
* **Mistaking data availability for ability.** The top pick in a thin maiden is
  often just the horse the corpus knows. That is a selection artifact, not an
  assessment.
* **Exotics.** With most of the field blank, the model's ordering below the top
  few ranks carries little information, so tickets built off it are close to
  random within the blank block.
* **DQ interaction.** Maiden races with underraced horses appear more prone to
  disqualification (R3 here). Piece 2 excludes no-recorded-winner races from
  WIN denominators, so those races quietly leave the win-rate sample.

**What the aggregate evidence does *not* yet show.** The premise that the model
performs materially worse on maidens is **not currently supported by the scored
log**, and this entry should not claim it does:

| window | maiden | non-maiden |
|---|---|---|
| all scored races | 12/18 = **66.7%** | 21/37 = 56.8% |
| out-of-corpus only | 7/12 = **58.3%** | 16/25 = 64.0% |

The direction flips depending on the window and both samples are far too small
to separate. The all-scored maiden figure is inflated by two in-corpus cards
(CT 7/25 went 3/3, ELP 8/21 2/3) that the model trained on. The out-of-corpus
split is directionally consistent with the hypothesis — 5.7pp worse — on twelve
maiden races, which is nothing.

So the case for this gap currently rests on **mechanism and on the three
observed cases, not on aggregate evidence**. `maiden_flag` is now logged
precisely so that Piece 3 can accumulate that evidence and settle it.

### Proposed fix — options

**Option A — a maiden-specific model.** Train a separate model on maiden races
only. The corpus has 9,081 of them with results, which is enough data to fit on.
*Effort: large, 2-4 sessions plus a retrain and a promotion decision.*
Risk: splits an already-thin corpus into two smaller ones, and the aggregate
evidence that a split is warranted does not yet exist.

**Option B — PP-backed history bridge.** The same fix as Gap #1 Option A: fill
the history block from `pp_entries_raw` when the corpus has nothing.
*Effort: medium-large, shared with Gap #1.*
Two caveats specific to this gap. It does **nothing for a true first-time
starter**, who has no past performances anywhere. And it has an unmet
prerequisite: `pp_entries_raw` is only populated for cards that have been run
through `load_pp_card.py`, which is not happening routinely — the table holds
4,318 rows across a handful of dates and has **zero rows for CT 2026-08-29**,
whose PP file was read directly at prediction time and never ingested.

**Option C — field-experience features.**
Give the model an explicit representation of how thin the field is: share of
field under N career starts, count of true first-time starters, and — using
`pp_career_starts` — the distinction between a first-timer and a shipper that
the corpus cannot make.

> **STATUS: main effects BUILT, TESTED and CLOSED (2026-08-31).**
> Approved 2026-08-31, implemented the same day, measured, and closed the same
> day. The two race-level components — share of field underraced, debut counts —
> are constant within a race and therefore cannot reorder it. Measured effect
> on top-pick ITM against a corpus-matched control: **-0.045pp overall,
> -0.043pp on maidens.** Evidence in the status block below.
>
> **Still live:** the *third* component, first-timer-versus-shipper separation
> via `pp_career_starts`. That one is **horse-level** — it differs between
> runners in the same race — so it can reorder a race where the other two
> cannot. It remains blocked on routine PP ingest, and it is properly part of
> Gap #1 Option A rather than a maiden-specific fix.

*Effort spent: 1 session. Remaining component: blocked on PP ingest.*

**Option D — runtime shrinkage on thin fields.** When most of a field is blank,
shrink the spread of P(ITM) toward uniform rather than presenting a confident
ordering built on nothing.
*Effort: small, no retrain.* Same shape as Gap #1 Option C and could share an
implementation.

**Option E — warning only.** Implemented; see below.

### Recommended option and why

**Option C, then Option B. — Approved by Doug 2026-08-31.**

Option C is recommended first because the model currently has **no
representation of field-level experience at all**. It scores a race where eight
of twelve runners have never started exactly as it scores a race where all
twelve are seasoned, and mechanism 3 above — race-wide contamination of pace
and class estimates — is a direct consequence. That is the part of this gap
that is genuinely distinct from Gap #1, and it is a feature addition rather
than a corpus split, so it is cheap to test and easy to reverse.

Option B follows because it is shared work with Gap #1 and would be built once
for both. Its prerequisite — routine PP ingest — should be treated as a
separate small task, since without it Option B has no data to read on the cards
that need it most.

**Option A is not recommended yet.** A dedicated maiden model is the kind of
change that needs evidence first, and the scored log currently does not show
maidens underperforming. Revisit once `maiden_flag` has accumulated a few
hundred races and Piece 3 can report the split with a straight face.

### Gap #6 status: DOCUMENTED, MAIN-EFFECTS AND INTERACTIONS TESTED, OPTION C CLOSED (2026-09-01)

**Option C's field-experience features as race-level main effects are TESTED
AND CLOSED.** They do not improve top-pick ITM, and there is a structural
reason why they cannot — see the Feature Design Principle at the top of this
document, which this result produced.

"Closed" applies to the main-effects implementation specifically, not to the
gap. Gap #6 itself remains open and unfixed; the interim `maiden_flag` warning
is still the only mitigation in place.

**Artifacts**

| what | where |
|---|---|
| feature module | `new_features/field_experience_features.py` |
| distribution diagnostic | `logs/gap6_diagnostic.txt` (`diagnose_field_experience.py`) |
| candidate model | `dpv1_20260831.pkl` (`dpv1.3.0-4track`), 102 fundamental cols vs 95 |
| corpus-only control | `dpv1_20260831_corpus_only.pkl` (`dpv1.2.1-4track`) |
| retrain log | `logs/retrain_history.jsonl` |

Seven features, computed per race and broadcast to every entry:
`field_avg_career_starts`, `field_median_career_starts`,
`field_max_career_starts`, `field_min_career_starts`, `field_pct_debut`,
`field_pct_underraced`, `field_experience_variance`.

Absent history counts as **0 starts**, not excluded — excluding unknown horses
would make `field_pct_debut` structurally incapable of exceeding 0, since the
horses it exists to count are exactly the ones that would be dropped. Variance
uses population std so a one-horse field is 0.0 rather than NaN. No nulls are
produced, so the preprocessor generates no `__missing` indicators: there is
nothing missing to indicate.

#### The diagnostic says the features are real

Across 29,285 races they separate maiden from non-maiden cleanly:

| feature | non-maiden mean | maiden mean | separation |
|---|---|---|---|
| `field_pct_underraced` | 0.261 | 0.653 | **+0.392** |
| `field_pct_debut` | 0.095 | 0.322 | +0.226 |
| `field_avg_career_starts` | 9.048 | 2.630 | -6.418 |
| `field_max_career_starts` | 19.025 | 6.992 | -12.033 |
| `field_experience_variance` | 5.680 | 2.254 | -3.426 |

And they place Gap #6's three observed cases in the underraced tail of all
racing — CT 2026-08-29 R3, R5 and R6 sit at the **78th, 74th and 73rd**
percentile of `field_pct_underraced` across the corpus.

One honest qualification the diagnostic surfaced: *among maiden races* those
three sit at only the 52nd, 44th and 42nd percentile. They are extreme
relative to racing generally and unremarkable relative to other maidens. R6 is
the exception, and it is the interesting one — its `field_experience_variance`
of 7.54 is the **98th percentile among maidens**, because Zaptastic's 26 starts
sat in a field of debutants. Zaptastic won, from model rank 7.

#### The retrain says they add nothing

Cross-validated, 15,561 shared fold races, three models compared. The
corpus-only control is what makes this readable — it isolates the effect of the
features from the effect of the 265 races of corpus growth that arrived with
them.

| subset | current 2.0 | corpus-only 2.1 | field-exp 3.0 | features alone |
|---|---|---|---|---|
| all races | 64.090% | 64.109% | 64.064% | **-0.045pp** |
| maiden only (n=4,634) | 65.063% | 65.170% | 65.127% | **-0.043pp** |
| non-maiden (n=10,927) | 63.677% | 63.659% | 63.613% | **-0.046pp** |
| `field_pct_underraced >= 0.60` (n=3,484) | 62.658% | 62.744% | 62.715% | **-0.029pp** |

Against the *current* model the candidate looks flat-to-slightly-positive on
maidens (+0.065pp). Against the *control* it is negative everywhere. Every
apparent gain belongs to the corpus, not to the features.

**Keeping the corpus-only control is what made this legible.** Without it the
+0.065pp maiden movement would have read as the features working.

Coefficients are correspondingly small. The largest, `field_experience_variance`
at +0.0374, ranks 88th of 219 — about the median |coefficient| of 0.0252.
`field_pct_debut` is effectively zero at -0.0014, rank 209/219. For scale, the
pre-existing `field_size` sits at -0.3471, rank 4.

#### Why they cannot work as main effects

This is the finding worth carrying forward, and it is not a data problem.

**A race-level feature is constant within its race.** Verified: across the whole
corpus, zero races have more than one distinct value for any of the seven. A
constant shifts every horse's linear predictor by the same amount, the logistic
link is monotonic, so the **within-race ordering is unchanged**. The candidate
model has `with_interaction = False`.

Top-pick ITM is a pure within-race ranking metric. So these features cannot move
it by construction — only indirectly, by perturbing the fit of other
coefficients, which is exactly the ±0.05pp noise observed.

Knowing a field is green tells the model the race is uncertain. It does not tell
it *which* green horse will hit the board, and ranking is the only thing
top-pick ITM measures.

Where they could still pay:

* **Calibration.** They shift the absolute level of P(ITM), which is what the
  Harville inversion, the simulator and any ticket EV consume. Nothing here
  measured that.
* **Interactions.** `career_starts x field_pct_underraced` varies within a race
  and *can* reorder it. `train_dpv1.py` already has a `--with-interaction` path.
* **A separate maiden model**, which refits every coefficient inside the maiden
  regime rather than adding a constant to it.

#### Interaction test, 2026-09-01: also null — Option C fully closed

The mechanism analysis said race-level main effects cannot reorder a race but
*interactions* with horse-level features could. That was tested. **They do not
help either, and no result is statistically distinguishable from noise.**

**`--with-interaction` does not do this.** The flag toggles a hardcoded pair of
class-change terms — `INTERACTION_FEATURES = ("won_last_class_up_flag",
"won_last_class_down_flag")` in `prepare_training_dpv1.py`, Doug's rank-1
"won last out and stepping up in class" insight. It has nothing to do with
field experience. All four models compared here were trained with
`with_interaction = False`, so that variable is held constant and the only
thing that changes is the field-experience feature set.

Six new terms were built instead, in `field_experience_features.py`, each
combining the horse's own `career_starts` with the field around it:
`career_starts_vs_field_mean`, `career_starts_pctile_in_field`,
`is_most_experienced_in_field`, `career_starts_x_field_pct_underraced`,
`career_starts_x_field_variance`, `experience_edge_x_pct_underraced`.

The premise checks out — they do vary within a race, where the main effects do
not:

| set | races where the feature varies within the race |
|---|---|
| 7 main effects | **0 of 29,285 (0.0%)** |
| 6 interactions | 22,756-28,824 (77.7-98.4%) |

The two at 77.7% are the ones multiplied by `field_pct_underraced`, which is
zero for the whole field in 22% of races, making the product uniformly zero
there.

##### Results — four models, same 15,561 shared fold races

| subset | current 2.0 | corpus-only 2.1 | field-exp 3.0 | **fx+interact 3.1** |
|---|---|---|---|---|
| all races (n=15,561) | 64.090% | 64.109% | 64.064% | **64.154%** |
| maiden only (n=4,634) | 65.063% | 65.170% | 65.127% | **65.235%** |
| `pct_underraced >= 0.60` (n=3,484) | 62.658% | 62.744% | 62.715% | **62.342%** |

Against the corpus-only control — the fair baseline — the interacted model is
**+0.045pp** overall, **+0.065pp** on maidens, and **-0.402pp** on the
high-underraced subset that Gap #6 is actually about.

##### None of it is significant

Small deltas on subsets this size demand a paired test rather than eyeballing.
Exact McNemar on the discordant races, 3.1 against the corpus-only control:

| subset | control missed / candidate hit | control hit / candidate missed | net | delta | p |
|---|---|---|---|---|---|
| all races | 181 | 173 | +8 | +0.051pp | **0.710** |
| maiden only | 52 | 49 | +3 | +0.064pp | **0.842** |
| `pct_underraced >= 0.60` | 31 | 45 | -14 | -0.395pp | **0.135** |

**This is a null result, not a negative one.** The -0.40pp on the target subset
looks alarming and is the kind of number that invites a story about interaction
terms adding noise. It rests on 31 versus 45 discordant races out of 3,540 and
does not survive a significance test. The honest summary is that the
interactions changed nothing measurable in either direction.

##### Coefficients: the targeted terms landed mid-pack

No interaction term reached the top 30 of 225 coefficients. The best is
`career_starts_x_field_variance` at rank 53 (+0.0608). The term the mechanism
analysis specifically nominated, `career_starts_x_field_pct_underraced`, came
in at **rank 106/225 with +0.0297** — barely above the model's median
|coefficient| of 0.0284.

| rank | coef | term |
|---|---|---|
| 53/225 | +0.0608 | `career_starts_x_field_variance` |
| 54/225 | +0.0606 | `career_starts_pctile_in_field` |
| 56/225 | -0.0591 | `career_starts_vs_field_mean` |
| 106/225 | +0.0297 | `career_starts_x_field_pct_underraced` |
| 111/225 | -0.0293 | `experience_edge_x_pct_underraced` |
| 183/225 | +0.0080 | `is_most_experienced_in_field` |

##### Complexity and regularisation are fine

| model | fund cols | coefficients | max abs coef | median abs coef |
|---|---|---|---|---|
| corpus-only 2.1 | 95 | 212 | 0.4745 | 0.0277 |
| field-exp 3.0 | 102 | 219 | 0.4867 | 0.0252 |
| fx+interact 3.1 | 108 | 225 | 0.4570 | 0.0284 |

Same `l2 = 0.001` from the same grid combo as every reference model. Zero
coefficients exceed 1.0, the maximum actually *fell* slightly against both
other models, and the largest interaction coefficient (0.0608) is an order of
magnitude below the model maximum. **No instability, no blow-up, and no reason
to think stronger regularisation would change the answer.** The features are
not being suppressed by the penalty; they are simply not carrying signal.

##### Verdict: Option C is closed entirely

Per the decision framework: the interacted candidate *matches* the corpus-only
control — two subsets within 0.07pp, the third negative but not significant,
all three p > 0.05.

**Option C is closed in full**, main effects and interactions alike. The
information "this field is inexperienced" does not improve which horse DPv1
ranks first, whether supplied as a race-level constant or interacted down to
horse level.

That is worth stating plainly because it narrows the problem usefully. Gap #6's
mechanism section argued the model cannot see the experience composition of a
field. It now can, in six forms that vary within the race, and it does not
rank any better for it. So the maiden problem — if it is real, which the
aggregate evidence still does not establish — is not a *field-composition*
problem. Something else is going on in maiden races.

**Path forward is Gap #1 Option A**, unchanged: horse-level history features
from `pp_entries_raw`, blocked on routine PP ingest. That path supplies
information the model genuinely lacks about individual horses, rather than
re-expressing information it already has about fields.

Remaining live from Option C: nothing. The first-timer-versus-shipper split via
`pp_career_starts` was already reassigned to Gap #1 Option A on 2026-08-31 and
stays there.

##### Artifacts

| what | where |
|---|---|
| candidate | `dpv1_20260901_interact.pkl` (`dpv1.3.1-4track-interact`), 108 fund cols |
| fold predictions | `dpv1_fold_predictions_20260901_interact.csv` |
| reference: corpus-only | `dpv1_20260831_corpus_only.pkl` (`dpv1.2.1-4track`) |
| reference: main effects | `dpv1_20260831.pkl` (`dpv1.3.0-4track`) |
| main-effects diagnostic | `logs/gap6_diagnostic.txt` |

All thirteen features stay in the config and the built table. They cost no
measurable accuracy, the interaction terms are the more defensible half of the
set, and re-deriving them later would be rework. **Not promoted.** `dpv1.pkl`
remains `dpv1.2.0-4track`.

#### This reverses the recommendation

The roadmap previously recommended **Option C over Option A**, on the reasoning
that Option C is a feature addition rather than a corpus split and so is cheap
to test and easy to reverse. That reasoning held — it was cheap, it was tested,
and the answer is no.

Option C as specified is **closed**: field-experience main effects do not
improve ranking and will not, whatever the corpus. What remains live is the part
of Option C that was never about main effects — the first-timer-versus-shipper
separation via `pp_career_starts`, which is a *horse-level* feature and does
vary within a race. That stays blocked on routine PP ingest.

**Option A (a maiden-specific model) is now the better candidate**, for the
reason that made it look expensive before: it refits all coefficients within the
maiden regime instead of adding a race-level constant to a global fit. The
earlier objection — that the aggregate evidence for maidens underperforming did
not exist — still stands and still needs the `maiden_flag` window to accumulate.

The seven features are left in the config and the built table. They cost one
module and no measurable accuracy, they are the natural inputs to the
interaction terms above, and re-deriving them later would be pure rework.
**They are not in a promoted model** — `dpv1.pkl` remains `dpv1.2.0-4track`.

### Interim mitigation — shipped

`card_picks.py` prints a race-level warning immediately under the race header
when the race type starts with `MAIDEN` **and at least 60% of the field** has
fewer than 3 corpus career starts. NULL counts as underraced — the feature
builder writes NULL when it found no history at all, which is the most
underraced a horse can be.

```
--- Race 6  (10 horses)  MAIDENSPECIALWEIGHT  1430  Dirt  $32,900
    ⚠ MAIDEN with underraced horses — high variance, model recommends handicapping directly
      (6 of 10 = 60% have under 3 career starts)
    feature coverage 81%
```

The count is printed beside the warning so a reader can see how thin the race
actually is rather than taking the flag on faith — 60% of a field and 100% of
it are different races.

Every logged prediction carries `maiden_flag` (race-level, repeated on each row)
and `underraced_share`, alongside `shipper_flag` and `corpus_coverage`.

Predictions are still produced for maiden races and the output is otherwise
unchanged. **This is a warning, not a fix.**

Threshold history: the rule originally fired on *any* underraced starter, which
hit 98.4% of maiden races and functioned as a category label rather than a
discriminator. Moved to the share-based rule on 2026-08-31 — see the frequency
section above for the thresholds evaluated and why `>=` matters.

Effect on recent cards:

| card | old rule | new rule |
|---|---|---|
| CT 2026-08-29 | R3, R5, R6 | **R3, R5, R6** (all three observed cases kept) |
| CT 2026-08-28 | none | none (no maiden races) |
| CT 2026-08-27 | R1 | **none** |
| CT 2026-07-25 | R1, R4, R9 | **R4** |
| ELP 2026-08-22 | R1, R5, R6, R9 | R1, R5, R6, R9 |
| ELP 2026-08-23 | R2, R3, R4, R5, R7, R9 | R2, R3, R4, R5, R7, R9 |

At CT the rule now discriminates — CT 7/25 drops from three flags to one, CT
8/27 from one to none — while the compound cases survive. At ELP nothing
changes, and that is a finding rather than a failure: ELP maiden fields really
are more than 60% invisible to the corpus, because ELP's runners ship in. Gap
#1 and Gap #6 are the same problem there.
