# Phase 6D — model gap roadmap

A running catalog of things DPv1 cannot see, found during live use of the
Phase 6B card runner. Each entry is written when a gap shows up in a real
card, with the observed cases attached, so that the fix is argued from
evidence rather than from intuition.

This is a catalog, not a work plan. Nothing here is scheduled. Documented so
far: **Gap #1 (Shipper Blindness)** and **Gap #6 (Maiden Race Chaos)**, each
with an interim warning shipped in `card_picks.py`, **Gap #7 (Trip
Signal)**, tested and **rejected**, and **Gap #8 (Class Drop Intent)**, where
the stated hypothesis was rejected but a real, stable **calibration** error was
found underneath it. Read both status blocks before re-opening either. Gap #6's recommended fix
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
---

## Representation Principle

**A feature the model cannot resolve is a feature the model does not have.**

Varying within a race (above) is about whether a quantity *can* reorder a
field. This principle is about whether the model can *see* the quantity at all
once it has passed through discretisation and scaling. A feature can be
present in the config, built correctly, non-null, and within-race varying, and
still be invisible — in which case the gap it was meant to close is still open,
and nothing in the feature list will say so.

Two failure modes, both found in the same place on 2026-09-13 (Step 3, below):

* **Deadband.** A categorical built from a continuous quantity with a
  threshold discards everything inside the band. `class_change_from_last`
  labels a move UP or DOWN only at `class_change_threshold = 3.0`, so on a
  ladder where a tier is 10 points, **all 38,707 rows moving 1 or 2 points are
  labelled `SAME`** — indistinguishable from no move at all. The residual
  across that band was a clean monotone gradient from +3.8pp to -5.6pp. The
  model was pricing a real, large, monotone effect as a single flat category.
* **Scale swamping.** A raw signed magnitude is standardised, not winsorised
  (`Preprocessor.fit` takes a median, mean and std and stops). When the
  distribution is heavy-tailed, the std is set by the tail and small values
  collapse toward zero. `class_score_change_from_last` spans -66 to +66 with
  **16% of rows beyond |20|**, so a 1-2 point move arrives at the model as
  about **0.1 sigma**. Its fitted coefficient was rank 136 of 239: the model
  had effectively discarded it.

The two compound. The categorical throws away the small moves; the numeric
that could have rescued them is scaled into irrelevance. Between them the
model had **no usable representation of a 1-2 point class move**, which is the
single most common class move there is.

**Why this matters beyond class.** Nothing here is specific to the class
ladder. Any Phase 3C/DPv1 feature built as *categorical-with-threshold plus
raw-magnitude-numeric* is exposed to the same pair, and the pattern is common
in this codebase — `distance_change_bucket`, the pace and bias shapes, and the
layoff gates all take that shape. The fix in every case is the same shape as
Step 3's: give the model a **bounded, fine-grained** encoding of the quantity
alongside the coarse one.

**How to check a feature for this, before concluding it does not work:**

1. **Plot the residual against the raw quantity**, not against the encoded
   feature. A monotone gradient inside one encoded category is the signature.
2. **Compare the encoding's band to the quantity's real resolution.** Count
   how many rows fall inside the deadband — if it is a large share of the
   corpus, that is the population being priced blind.
3. **Check the standardised scale.** Divide a *typical* (not extreme) value by
   the column's std. If a meaningful move is under ~0.2 sigma, the model
   cannot act on it whatever its coefficient.
4. **Read the coefficient rank.** A rank far down the list on a feature that
   should matter is evidence of a representation failure, not of a dead
   signal.

**The consequence for the gap catalog.** A "we tested it and it did nothing"
verdict is only valid if the feature was *representable*. Any earlier rejection
where the candidate was encoded as a coarse categorical over a heavy-tailed
numeric deserves re-reading against this principle before it is treated as
settled. Step 3 is the worked example: the -4.86pp error attributed to a
missing interaction was mostly a representation failure, and the representation
fix earned coefficient rank 10 of 250 against ranks 193-220 for the interaction
terms.

**A corollary, learned by getting it wrong in the same session.** Coefficient
rank measures a term's **average** contribution over the whole corpus. It is
not evidence that a term is idle in the **cell it was built for**. Step 3's
interaction terms ranked 197 and 220 of 250, were called dead on that basis,
and were trimmed — and the target cell gave back 0.7pp (-1.13 -> -1.84pp),
because that cell is exactly where the interacted variable is large. A term on
a +/-10 scale with a small coefficient still moves the tail of its own
distribution. **Before dropping a term for a low coefficient rank, measure the
subgroup it was built to fix.** The reverse also holds: `_down` really was idle,
and dropping it cost nothing, because it had no such cell.


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

---

## Gap #7 — Trip Signal (Equibase chart comments and running lines)

> **STATUS: DOCUMENTED AND CLOSED — hypothesis tested and REJECTED (2026-09-11).**
>
> Do not re-open without *new evidence*, meaning a new data source or a new
> framing — not a re-run of this one. The measurement below is large,
> out-of-sample and unambiguous.

### The hypothesis

That Equibase trip comments and running lines carry ranking signal DPv1 cannot
see: specifically that the model's top pick is disproportionately a horse that
met trouble, and the longshots that beat it got clean trips — so that trip
quality explains where the model mis-ranks.

### What was actually available

**No PDF extraction was required.** The data was already ingested:

| field | coverage |
|---|---|
| `entries.trip_comment` | 222,303 / 222,367 (**100%**) |
| `entries.pace_calls_json` (position + beaten lengths per call) | 222,303 (**100%**) |
| `races.footnotes` (long-form narrative) | 29,421 / 30,055 (97.9%) |

`scored_predictions.jsonl` held only **57 scored races** (6 cards, CT and ELP,
Aug 2026) — too small to bucket. The measurement therefore ran on
`dpv1_fold_predictions.csv`: **116,555 genuinely out-of-sample (year-fold CV)
predictions across 15,526 races**, four tracks, 2023-2026. Ranking used
`p_fund`, because `card_picks.py` reranks `pred.p_fund`; the blend is
alpha=0.106 fundamental against beta=0.772 market and is mostly a tote board.

Extraction success **100%** (trip comments), **99.7%** (running lines),
**57/57** live races joined.

### Classifier accuracy

Rule-based classification of the short comments was validated against an
**independent** long-form classifier run on `races.footnotes` (different
vocabulary) over 2,676 horse-segments: **89.9% agreement** (87.4% before four
bugs were fixed). Precision is high; the residual is mostly *short-comment
omission* — roughly **30% of the trouble the footnote records never appears in
the short comment**. If trip is ever revisited, `footnotes` is the
higher-recall source.

Two parsing traps, recorded because they silently corrupt naive matching:

* **`1/8p` is the eighth POLE (a location); `3p` is the three PATH (ground
  loss).** Collapsing both flags half of every field as "wide".
* Comments are whitespace-stripped, so `\b` anchors never fire inside a token
  (`bmpdbtw`, `stdydinto`), while substrings collide: `altered` in `faltered`,
  `lug` in `sluggish`, `wide` in `widened`, `steady` in `steadygain`.

### Finding 1 — "positive trip" is a label leak, not a feature

P(descriptor) by actual finish position:

| finish | n | positive% | trouble% | fade% | wide% |
|---|---|---|---|---|---|
| 1 | 15,434 | **45.5** | 11.2 | 0.1 | 46.6 |
| 2 | 15,545 | 29.6 | 15.1 | 1.6 | 49.0 |
| 3 | 15,525 | 22.6 | 16.4 | 13.1 | 50.8 |
| 4 | 15,525 | 6.4 | 16.9 | 40.5 | 50.0 |
| 5 | 15,266 | 2.0 | 18.0 | 59.2 | 47.8 |
| 6+ | 38,577 | **0.5** | 20.6 | 66.7 | 42.6 |

"Rallied / drew away / driving" is a **restatement of the finish position**,
45.5% to 0.5% monotone. `fade` is the same in reverse. This is a fourth
instance of the label-leak class. Only `trouble` is quasi-exogenous (11.2% to
20.6%) and therefore usable. **`wide` is nearly flat** (46.6 to 42.6) and
carries almost no signal — contradicting standard handicapping practice.

### Finding 2 — the mis-ranking hypothesis is false

Winners do have trouble ~4pp less often than top picks, in every bucket
(ALL -4.0pp; maiden -5.2pp; turf -4.9pp; dirt -3.7pp; small field -3.9pp;
large field -4.1pp). But that is an **ex post** correlation.

Tested directly on the 4,808 races where the top pick missed ITM *and* a
rank-5+ horse hit ITM:

| quantity | measured | chance baseline | lift |
|---|---|---|---|
| top pick had trouble | **19.6%** | 15.4% | +4.2pp |
| winning longshot had a clean trip | **44.8%** | 44.4% | **+0.4pp** |
| *both* (the hypothesised pattern) | **6.0%** | 6.8% | **-0.8pp** |
| *neither* | 41.6% | — | — |

**The hypothesised pattern occurs slightly LESS often than chance.** The live
57-race sample agrees independently: top-pick trouble 17% against a 17.5%
baseline, longshot clean 33% — *below* baseline.

### Finding 3 — the decisive test: no lift as a lagged feature

Trip comments do not exist at prediction time. The only usable form is lagged.
Across **98,939 entries with a prior start**, within `p_fund` deciles:

**prior-trouble ITM 40.14% vs prior-clean 40.71% — delta -0.57pp, p=0.167.**
Wrong sign, not significant.

Calibration conditional on prior trip: trouble **+0.26pp**, wide **+0.13pp**,
clean **-0.97pp**. The model is **already calibrated on trip to within 1pp**.
The classic "troubled horse bounces back" angle is false in this corpus.

Eleven targeted subgroups were stressed. One survived nominally — *severe
interference last race AND beaten <5L*, +2.86pp net, z=2.58, p=0.010,
n=2,765 — and it does not hold up:

* **Multiple comparisons:** 11 tests; Bonferroni gives p≈0.11.
* **Unstable:** 2023 +1.5pp, 2024 +1.1pp, 2025 +3.4pp, 2026 +9.2pp. The
  magnitude lives almost entirely in the newest, smallest folds.
* **Practically inert:** it would change the top pick in **102 of 15,382
  races (0.7%)**.

**Running lines (99.7% parsed) showed nothing either.** Every prior-race shape
feature — ground gained early-to-wire, led at first call, far back early — has
a *negative* residual (-0.40 to -1.75pp net of control).

### Turf routes and closing kick — tested, NOT found

Checked explicitly, because a weak turf effect was suspected. Prior-race late
ground gain, split by today's surface and distance (route = 1,540+ yards):

| bucket | subgroup | n | net resid | z |
|---|---|---|---|---|
| turf routes | prior gain >3L | 284 | **-1.55pp** | -0.94 |
| dirt routes | prior gain >5L | 467 | -2.05pp | -0.89 |
| dirt sprints | prior gain >5L | 848 | -2.12pp | -1.19 |

**Every cell is negative and none is significant.** There is no turf
closing-kick signal in this corpus; the sign is the opposite of the
hypothesis. Recorded here so the idea is not revived as an open lead.

### Verdict

Trip signal is **not strong enough to justify feature building**. The ex post
correlation is real, which is why trip *feels* explanatory when reading charts.
It does not survive translation into a prediction-time feature. By the Feature
Design Principle above, trip trouble is ranking-capable but empirically
empty — the same shape as Gap #6 Option C.

No model changes, no features, no retraining came out of this session.

---

## Gap #7-alt — next places to look if pursuing ranking-error investigation

Recorded as candidate directions only. **None has been measured**; none has an
observed case attached yet; no implementation is proposed. Each needs the
Feature Design Principle applied before any work.

* **Fundamental class assessment** — **INVESTIGATED, see Gap #8.** The model
  reads class direction correctly for ranking, but misprices poor-form horses
  taking a class drop. Calibration-only; do not re-test with top-pick ITM.
* **Field-relative talent shift** — a horse's ability measured *against the
  specific field it faces today* rather than against an absolute scale.
* **Pace shape** — partially covered by **Gap #2**; as noted there it is
  race-level and needs an interaction with each horse's running style to
  reorder anything.
* **Distance-surface interactions** — whether distance aptitude is being
  modelled separately enough per surface.
* **Form reliability (consistent good form)** — **found incidentally in
  Gap #9, exploratory.** Low finish variance plus good mean finish is
  under-rated by +2.35pp and reorders 3.4% of races. It needs a pre-registered
  test on new data before anything else; see Gap #9. **Mechanism investigated
  in Gap #10:** two-sided under-extrapolation of a reliable record comparable
  to today's class. The mechanism does not sharpen the ranking gain.
* **Multi-race class context** — **found in Gap #11.** Horses racing below
  their recent-average class are under-rated and those above over-rated; the
  model's class feature looks one race back. Held out, +0.42pp top-pick ITM on
  all horses. This is the recommended next build direction; see Gap #11.

---

## Gap #8 — Class Drop Intent (Kuck A/B/C framework)

> **STATUS: INVESTIGATED 2026-09-11. Hypothesis as stated REJECTED, but a real
> and stable CALIBRATION error was found underneath it.**
>
> This is **not** a Gap #7-style dead end. Read the verdict before deciding
> anything: the signal is real, survives every control, and is stable across
> all four years and all four tracks — but it moves **calibration, not
> ranking**. Measuring it with top-pick ITM will show nothing, and that would
> be the wrong instrument, not a negative result.
>
> **THE NUMBER THAT MATTERS — the interaction.** "No ITM in the last 3" is
> worth **+0.07pp (z=0.19)** on its own: nothing. Split by class direction, the
> halves have **opposite signs** — **-1.68pp** for horses not dropping,
> **+2.88pp** for horses dropping (z=+4.30). Adding the severity filter gives
> bucket C at **+3.80pp (z=4.84)**. The model prices poor form, and prices
> class change, but **not their product**. A main-effect test on either
> variable alone declares this dead; that is how it stayed hidden.
>
> **MECHANISM IS NOT ESTABLISHED — do not reopen this without the follow-up
> test.** What is measured is *that* the model misprices poor-form droppers,
> not *why*. The class-relief reading (the horse meets materially weaker
> company and the model under-credits that) is the most plausible account but
> was **not tested causally**, and at least two rivals survive: a **claiming
> -price/eligibility effect**, where the drop changes who the horse actually
> races against in ways `class_score` only proxies; and **connections' private
> information**, where the drop encodes barn intent that partly predicts the
> outcome on its own. Distinguishing them needs a test that holds the beaten
> field's strength fixed while varying the drop — not another residual split.
> **Do not build features on the class-relief story alone.**
>
> **CLASSIFIER VALIDATION IS SELF-CONSISTENCY, NOT INTER-ANNOTATOR.** 27/30 is
> one labeler, in-sample. A threshold-perturbation test (2026-09-12) found the
> **C rule structural**: numeric gates move <=3.2% of labels singly and <=10.5%
> jointly across 162 combos, with hand accuracy 23-28/30. C is also immune by
> construction to every A-side choice. The **A/B boundary is definitional**:
> reshaping the A rule relabels 6.5-22.8% of droppers. The finding rests on C.

### The hypothesis

Tested from Gap #7-alt's "fundamental class assessment". For a claiming horse
dropping in class, the Kuck framework splits intent three ways:

* **A (positive)** — consistent competence at the higher level; placed to win.
* **B (neutral)** — mixed form, hoping it improves against cheaper.
* **C (negative)** — no ability shown recently, dropped hard; connections
  effectively giving up, hoping the horse is claimed.

The hypothesis was that DPv1 cannot tell these apart, and specifically that it
**over**-ranks C horses.

### Sample

`dpv1_fold_predictions.csv` joined to `entry_features_dpv1`. Filtered to
claiming and optional-claiming, **excluding maidens and stakes**, then to
horses whose `class_score_change_from_last < 0`: **17,149 out-of-sample
class-droppers**, against 40,306 non-dropper controls in the same race types.
Ranking on `p_fund`, as in Gap #7.

Two data notes. `purse_change_from_last` is a **fractional** change (-0.54 = a
54% purse cut), not a dollar delta. `class_score` is higher-is-better (STAKES
77.7, ALLOWANCE 54.5), so a drop is negative.

### Classifier and its calibration

The A/B/C rules as originally specified scored **22/30 (73.3%)** against
hand-labels, failing in two systematic directions:

* **B-should-be-A:** the "modest drop" gate (<=25% purse cut, <=1 notch)
  blocked A for horses with strong repeated form at the higher level taking a
  *large* drop. That is the strongest "placed to win" case there is, not the
  weakest. Drop magnitude was removed as a gate on A.
* **A-should-be-B:** a single ITM in the last 3 was accepted as "consistent
  competence" even when the horse was 10th last out. A now requires two board
  hits at or above today's level, or one plus an in-the-money last-out.

Refined rules (`classify_v2`) score **27/30 (90.0%)**, with bucket C separated
perfectly (10/10) and all residual confusion on the A/B boundary.

**Methodology — self-consistency, NOT inter-annotator agreement.** Read the
27/30 precisely:

* **Single labeler.** The 30 hand-labels (a stratified sample, 10 per v1
  bucket, `random.seed(7)`) were produced by the same author who wrote the
  rules. Unlike Gap #7's trip classifier, which was checked against an
  *independent* source (`races.footnotes`), nothing here is independent.
* **No second annotator, no inter-annotator variance test.** None was run and
  none is recorded anywhere in this entry; do not remember one.
* **In-sample.** `classify_v2` was refined *on these same 30 cases*, so 27/30
  is a training-set score, not a held-out one. One case is 3.3pp.

Three things stand in for independent validation:

1. the headline rests on a **judgment-free cut** needing no classifier at all
   (Finding 3);
2. a **label-stability threshold perturbation** (2026-09-12, below): the
   closest real analogue for a *rule-based* classifier. Annotator variance is
   the wrong instrument when labels come from thresholds rather than people;
   the right question is whether nearby thresholds give the same labels; and
3. an **effect-size sensitivity sweep** on the C gates (below), which asks a
   different question: whether the +3.80pp survives, not whether labels do.

**Label-stability perturbation (2026-09-12).** Every A/B/C gate was varied
within a reasonable range. Two readings for each variant: accuracy against the
30 hand-labels, and **population swing**, the share of all 17,149 droppers whose
bucket changes against baseline. Swing is the better brittleness measure,
because it does not ride on 30 cases.

*Numeric thresholds, one at a time:*

| gate | variant | hand acc | pop swing | C kept |
|---|---|---|---|---|
| — | baseline `classify_v2` | 27/30 | 0.0% | 100% |
| level slack (claiming `class_score` steps) | 0 / 2 / 3 steps (base 1) | 27 / 27 / 27 | 0.7 / 0.5 / 0.6% | 100% |
| last-out ITM counts for A | only 1st/2nd (base <=3rd) | 28 | 2.9% | 100% |
| severe drop: purse cut | -35 / -40 / -60 / -65% (base -50%) | 27 / 27 / 26 / 25 | 3.1 / 1.7 / 1.4 / 2.0% | 100 / 100 / 94 / 91% |
| severe drop: claiming notches | >=1 / >=3 (base >=2) | 27 / 27 | 1.9 / 1.7% | 100 / 92% |
| layoff (gates A and C) | 60 / 75 / 120 / 180d (base 90d) | 27 / 27 / 25 / 25 | 2.6 / 0.9 / 1.3 / 3.2% | 100 / 100 / 99 / 97% |

*Numeric thresholds, jointly:* a full grid of slack {0,1,2} x purse cut
{-35,-50,-65%} x notches {1,2,3} x layoff {60,90,120d} x last-out bar {2nd,3rd}
gives **162 combinations**:

* **Hand accuracy 23-28/30.** Distribution: 23 (9 combos), 24 (9), 25 (36),
  26 (36), 27 (36), 28 (36). **108 of 162 (67%) sit at 26-28.**
* **Population swing: median 6.0%, 90th percentile 8.8%, max 10.5%.**
* **Worst case is the joint-strict corner** (slack 0, -65%, 3 notches, 120d) at
  23/30. Its losses come from the purse -65% and layoff 120d gates, each
  costing 2 hand cases. The C bucket still keeps 81% of its members there, and
  its effect is still +3.51pp (effect-size table below).
* The single 28/30 (last-out bar 1st/2nd) is **one case on the tuning set and
  should NOT be adopted**. It is noise at n=30.

*Rule shape (structural choices, not thresholds):*

| change | hand acc | pop swing | A kept |
|---|---|---|---|
| re-add "modest drop" gate on A: purse >=-15%, <=1 notch | 23/30 | 20.6% | 18% |
| ...purse >=-25%, <=1 notch (= v1) | 24/30 | 18.6% | 26% |
| ...purse >=-35%, <=1 notch | 25/30 | 16.2% | 36% |
| ...purse >=-50%, <=2 notches | 26/30 | 10.5% | 59% |
| consistency bar: >=1 ITM at level (v1 bar) | 24/30 | 22.8% | 100% (B kept 57%) |
| consistency bar: >=2 ITM at level only | 25/30 | 6.5% | 74% |
| consistency bar: 1 ITM at level + last-out ITM only | 26/30 | 8.5% | 66% |
| consistency bar: 3 of 3 ITM at level | 23/30 | 22.0% | 13% |

**Verdict: the C rule is structural; the A/B boundary is a definitional
choice.**

* **Numeric thresholds are stable.** No single numeric perturbation moves more
  than 2 hand labels or more than 3.2% of the population. Across the whole
  joint grid, at most 10.5% of horses change bucket.
* **C is insulated from every A-side choice by construction.** A requires an
  ITM in the last 3 and C requires none, so A-side changes can only trade
  A<->B. C keeps 100% of its members under all eight rule-shape changes above.
  Its own gates (purse cut, notches, layoff) keep 91-100% singly and 81% in the
  harshest joint corner. **The Gap #8 finding rests on C, so it does not
  depend on how A is defined.**
* **The A/B boundary is where the judgment lives.** Changing the *shape* of the
  A rule relabels 6.5-22.8% of all droppers. Two consequences:
  * Finding 1's A-bucket numbers (+1.33pp, p=0.077) are the least robust in
    this entry. Treat them as definition-dependent.
  * The "modest drop" gate is not merely a threshold that was tuned. Accuracy
    falls **monotonically** as the gate tightens (26 -> 25 -> 24 -> 23), which
    supports v2's decision to remove it: drop size is not evidence against
    "placed to win".
* **This is still not independent validation.** Every accuracy number above is
  scored against the same single labeler's 30 in-sample cases. The perturbation
  shows the rules are not balanced on a knife-edge. It cannot show they match
  anyone else's reading of the Kuck framework.

Script: `g8_perturb.py` (session scratchpad, not committed). It re-implements
`classify_v2` with parameterised gates and asserts an exact match to the
original on all 30 hand cases and on the first 3,000 population rows before
perturbing.

**Effect-size sensitivity (C gates only).** A separate question from the table
above: whether the +3.80pp *effect* survives. Every gate in the C rule was
perturbed independently and jointly:

| variant | n | net | z |
|---|---|---|---|
| baseline (purse -50%, 2 notches, 90d) | 3,775 | +3.80pp | +4.84 |
| purse cut -35% | 4,299 | +3.44pp | +4.66 |
| purse cut -65% | 3,439 | +3.87pp | +4.71 |
| notches >=1 | 4,107 | +3.27pp | +4.34 |
| notches >=3 | 3,489 | +3.57pp | +4.36 |
| layoff >=60d | 3,874 | +3.51pp | +4.53 |
| layoff >=120d | 3,731 | +3.77pp | +4.77 |
| loose (-35%, 1 notch, 60d) | 4,569 | +2.99pp | +4.19 |
| strict (-65%, 3 notches, 120d) | 3,062 | +3.51pp | +4.04 |

The result is **insensitive to every threshold choice** — the whole range is
+2.99 to +3.87pp at z 4.04 to 4.84. The finding is not an artifact of where the
cuts were drawn.

### Finding 1 — the model DOES distinguish the three buckets

| bucket | n | share | predicted ITM | actual ITM | residual | 95% CI on actual |
|---|---|---|---|---|---|---|
| A | 4,333 | 25.3% | 0.547 | 0.560 | +1.33pp | [0.545, 0.575] |
| B | 9,041 | 52.7% | 0.430 | 0.429 | -0.11pp | [0.418, 0.439] |
| C | 3,775 | 22.0% | 0.338 | **0.370** | **+3.20pp** | [0.355, 0.386] |
| all droppers | 17,149 | — | 0.439 | 0.449 | +0.98pp | [0.442, 0.456] |
| non-droppers | 40,306 | — | 0.405 | 0.393 | -1.19pp | [0.389, 0.398] |

The ordering is correct and well separated in both prediction and outcome
(predicted 0.547 > 0.430 > 0.338; actual 0.560 > 0.429 > 0.370). **The premise
that DPv1 confuses strategic drops with give-up drops is false.**

When the top pick *is* a class-dropper, bucket ordering holds and all three
beat the non-dropper top pick: A 68.1% ITM (n=1,420), B 63.9% (n=1,278),
C 59.2% (n=179), against 62.3% for non-dropper top picks (n=5,246).

### Finding 2 — the model UNDER-rates C, the opposite of the hypothesis

A is +1.33pp (z=1.77, p=0.077 — not significant). B is flat. **C is +3.20pp,
z=4.07, p<0.001.** Net of a `p_fund`-matched control drawn from the same
claiming/OC pool, C is **+3.80pp, z=4.84**.

The give-up narrative assumes the connections' intent predicts the outcome. It
does not: the horse still receives a large *class relief*, and the model —
reading poor recent form — under-credits it.

**Stability.** Contrast this with Gap #7's one survivor, which lived in a
single fold:

| year | n | net | z |
|---|---|---|---|
| 2023 | 1,064 | +4.53pp | +3.05 |
| 2024 | 1,008 | +4.64pp | +3.05 |
| 2025 | 1,119 | +3.58pp | +2.48 |
| 2026 | 584 | +1.37pp | +0.69 |

| track | n | net | z |
|---|---|---|---|
| CT | 782 | +5.23pp | +3.01 |
| ELP | 285 | +1.83pp | +0.63 |
| GP | 1,772 | +3.84pp | +3.38 |
| MNR | 936 | +3.09pp | +1.94 |

Positive in **every** year and **every** track.

### Finding 3 — it is an INTERACTION, invisible as a main effect

The specificity test, which uses **no classifier judgment at all** — just two
booleans:

| cut | n | net resid | z |
|---|---|---|---|
| no ITM in last 3 (any claiming/OC horse) | 14,139 | **+0.07pp** | +0.19 |
| ...and NOT dropping class | 8,957 | **-1.68pp** | -3.67 |
| ...and dropping class | 5,182 | **+2.88pp** | +4.30 |
| bucket C (adds severe-drop/layoff filter) | 3,775 | +3.80pp | +4.84 |
| dropping class but HAS recent ITM | 13,374 | +0.93pp | +2.16 |

Poor form alone is worth **nothing** (+0.07pp). Split by class direction, the
two halves have **opposite signs** — which is exactly why the main effect is
zero. The model prices poor form, and prices class change, but not their
product. The bucket-C severity filter sharpens +2.88 to +3.80, so the
classifier adds real signal on top of the judgment-free cut, but **the core
result does not depend on the classifier.**

### Finding 4 — `trainer_dropping_class_win_pct` does NOT already capture it

The control this investigation was designed around. The feature is populated
only for class-droppers (0% of non-droppers), covering 59.9% of them.

A-minus-C spread in **actual** ITM, within each trainer group:

* bottom quartile of `trainer_dropping_class_win_pct`: A 0.459, C 0.312 —
  spread **+14.7pp**
* top quartile: A 0.616, C 0.528 — spread **+8.7pp**

**The A/B/C signal does not disappear when conditioning on trainer stats.** It
is largely orthogonal to that channel, so explicit Kuck classification would
not be redundant with what is already in the model.

Residuals by cell show where the mispricing concentrates:

| bucket | bottom quartile | top quartile |
|---|---|---|
| A | -3.72pp | -2.68pp |
| B | -3.13pp | -0.11pp |
| C | -0.16pp | **+6.02pp** |

The worst-priced cell is **C with a hot dropping-class trainer**: net
**+6.43pp, z=2.54 (n=388)**. A give-up-looking horse whose barn actually wins
with class drops is live, and the model does not see it — the trainer feature
is in the model as a **main effect**, and this is an interaction. Treat this
cell as suggestive only: n=388, and only 2024 (+12.38pp) and 2025 (+9.26pp)
have enough rows to evaluate.

### Verdict — real signal, but calibration, not ranking

| question | answer |
|---|---|
| Does the model distinguish A/B/C? | **Yes** — ordering correct, well separated |
| Does it over-rank C? | **No — it under-rates C** by +3.80pp |
| Does it under-rank A? | No (+1.33pp, p=0.077) |
| Do existing trainer features capture it? | **No** — spread persists in both quartiles |
| Would Kuck features be worth building? | **For calibration only, and not on the class-relief story alone** — mechanism is untested. |

**Practical impact on ranking is 0.7%**, the same ceiling Gap #7 hit:

* races containing at least one bucket-C horse: 2,863 of 15,532 (18.4%)
* races where the top pick is already a C horse: 179 (1.2%)
* races whose **top pick changes** under a +3.8pp correction: **101 (0.7%)**

C horses sit low in the ranking by construction, so a +3.8pp bump on a horse at
p=0.34 rarely overtakes one at p=0.60. By the Feature Design Principle this is
a **calibration-only** effect: it is horse-level and does vary within a race,
so it *can* reorder, but empirically it almost never does.

**That does not make it worthless — it makes top-pick ITM the wrong
instrument.** The Harville inversion, `simulate_race.py` and `ticket_ev.py` all
consume absolute probabilities, and a systematic +3.8pp error on 22% of
claiming droppers is exactly the kind of thing that distorts exotic pricing
while leaving win-bet rankings untouched. If this is ever built, **measure it
with a calibration metric (log-loss, Brier, reliability curve) on the dropper
subgroup, not with top-pick ITM.** Measuring it the wrong way will produce a
false negative and close the question incorrectly.

No features were built, no model was retrained, nothing outside the diagnostic
script was modified.

---

## Gap #9 — Erratic Horse Factor (finish-position variance)

> **STATUS: INVESTIGATED 2026-09-12. Hypothesis REJECTED. A different,
> unplanned signal turned up underneath it: CONSISTENT good-form horses are
> under-rated. That signal is EXPLORATORY, not established.**
>
> **The erratic-horse claim is dead under every definition tried.** High
> finish-position variance is priced correctly: net of a p_fund-matched
> control, **+0.07pp (z=0.13, n=8,366)**. With a top-3 in the window it is
> +0.12pp. Across 13 threshold and definition variants it never comes out
> significantly under-rated; the range is -1.17pp to +1.05pp. The model already
> credits erratic horses' upside, through career ITM/win rates (Finding 4).
>
> **Two apparent leads inside the high-variance bucket are artifacts:**
> * The **class-context split** (best finish at higher class +3.75pp, at lower
>   class -2.00pp) is **not specific to variance**. The same gradient appears
>   in moderate- and low-variance horses, and it vanishes for erratic horses
>   who are not dropping in class today. It is Gap #8's class-relief family,
>   seen from another angle.
> * The **CT -3.59pp / GP +1.77pp track split** is a **field-size artifact** of
>   raw finish positions. With finish normalised by field size, both are null.
>
> **The surprise — read the caveat before acting on it.** Low-variance horses
> with a good recent mean finish (<4.5) are under-rated by **+2.35pp (z=6.60,
> n=15,268)**:
> * positive in all 4 years (+1.69 to +3.17pp) and at 3 of 4 tracks;
> * robust to every perturbation (+1.55 to +2.62pp, including
>   field-normalised and a 3-start window);
> * it **changes the top pick in 3.4% of races**, about 5x the ceiling
>   Gaps #7 and #8 hit;
> * leave-one-year-out it improves top-pick ITM by **+0.26pp** (160 races
>   gained vs 119 lost, exact McNemar p=0.016).
>
> **But this cell was found by looking**, not pre-registered. It came out of
> roughly 70 exploratory cuts. The residual (z=6.60) survives any reasonable
> multiple-comparison correction; the ranking gain (p=0.016) is conditional on a
> post-hoc cell and does not. **Treat it as a hypothesis for a pre-registered
> test, not a feature spec.** The mechanism is also untested (see "What is not
> established").

### The hypothesis

From a longshot handicapping article. DPv1's recent-form features
(`last_3_avg_finish`, `speed_trajectory_3_races`) average over recent starts.
An erratic horse, e.g. finishes [4, 8, 2, 9, 3], averages 5.2, and the claim
is that the alternation signals a horse that can run big when it tries, so
averaged form **understates its upside**.

Testable form: horses with above-average finish-position variance outperform
their predicted P(ITM), particularly when the variance includes a top-3 finish
at similar class and distance to today.

### Sample and definitions

**Sample.** `dpv1_fold_predictions.csv` (116,665 out-of-fold horse-starts,
15,561 races) joined to `entry_features_dpv1`. Kept: horses with at least 3
prior **finished** starts in the corpus, strictly before today, giving
**75,940 rows**. 60,927 use a 5-start window and 15,013 the 3-start fallback;
40,725 lacked 3 prior starts. The live scored log (933 rows, 83 races) is far
too small to bucket and is used only as a consistency check at the end.
Predictions are `p_fund`, as in Gaps #7 and #8.

**Definitions — each one was a judgment call:**

* **Variance** is the **sample** SD (n-1) of finish position over the last 5
  finished starts, falling back to the last 3 when fewer than 5 exist.
  Sample rather than population SD because the brief's own example
  [4, 8, 2, 9, 3] is 3.11 by sample SD (erratic) but 2.79 by population SD
  (not erratic).
* **DNFs** (1,172 in the corpus) carry no finish position and are excluded
  from the window.
* **Starts outside the corpus tracks are invisible.** "Last 5 starts" means the
  last 5 corpus starts.
* **Buckets:** LOW sd <= 1.5, MODERATE 1.5-3.0, HIGH > 3.0. The sample
  quantiles are p10 1.00, p25 1.41, p50 1.92, p75 2.51, p90 3.05, so HIGH is
  the top ~11%.
* **Class.** `races.class_level` is NULL in all 30,055 races, so class comes
  from `class_score`. Its scale runs in ~10-point bands by race type (claiming
  21-29, allowance 53-59, stakes 75-79) with 1-point steps inside each band.
  "Within 1 class level" is read as **+/-1 `class_score` point**, the same
  slack Gap #8 used. When several starts tie for best finish, the most recent
  one sets the class and distance context.
* **Similar distance** means within **220 yards (1 furlong)**. The brief's
  "or 1 half-mile" was ambiguous and was not implemented separately.
* **Error bars.** Horses in a race are not independent (exactly three hit the
  board), so every z below uses a **race-clustered** standard error.
* **"Net"** is the group's residual minus the residual that `p_fund`-matched
  rows outside the group show (20 bins). This removes the model's generic
  calibration curve. On this sample the model's overall residual is -0.33pp.

### Finding 1 — high variance is priced correctly

| bucket | n | predicted ITM | actual ITM [95% CI] | residual | net | z |
|---|---|---|---|---|---|---|
| LOW (sd <= 1.5) | 20,828 | 0.444 | 0.450 [0.444, 0.457] | +0.65pp | **+1.53pp** | +5.32 |
| MODERATE | 46,746 | 0.404 | 0.396 [0.392, 0.401] | -0.78pp | **-1.27pp** | -7.88 |
| **HIGH (sd > 3.0)** | 8,366 | 0.388 | 0.386 [0.375, 0.396] | -0.21pp | **+0.07pp** | +0.13 |
| HIGH with >= 1 top-3 in window | 8,129 | 0.391 | 0.389 [0.379, 0.400] | -0.16pp | +0.12pp | +0.24 |
| HIGH with no top-3 | 237 | 0.281 | 0.262 [0.206, 0.318] | -1.97pp | -1.54pp | -0.58 |

The ordering is right in both prediction and outcome, and the erratic bucket's
prediction lands on its outcome. Nearly every erratic horse (97%) has a top-3
in its window by construction: a high SD needs a spread of finishes. So the
"especially with a top-3" qualifier barely changes the set.

**Stability of the null:** by year -0.29, -0.79, +0.91, +1.06pp, all
|z| < 1.1. Non-maiden -0.20pp; maiden +1.64pp (z 1.19).

### Finding 2 — the class-context split is class relief, not variance

Within HIGH + top-3, split by the best finish's class relative to today:

| best finish at | n | predicted | actual | net | z |
|---|---|---|---|---|---|
| higher class | 1,355 | 0.411 | 0.446 | **+3.75pp** | +2.93 |
| same class | 3,540 | 0.413 | 0.416 | +0.62pp | +0.82 |
| lower class | 3,234 | 0.359 | 0.337 | **-2.00pp** | -2.59 |

Read alone, this says the model fails to discriminate erratic horses by where
their big race came. **The control says it is not about variance.** The same
split in the other buckets:

| bucket | higher class | same class | lower class |
|---|---|---|---|
| LOW | +2.79pp (z 2.99) | +3.17pp (z 6.59) | -0.70pp (z -1.06) |
| MODERATE | +2.05pp (z 3.76) | -0.36pp (z -1.35) | -2.58pp (z -7.12) |
| HIGH | +3.75pp (z 2.93) | +0.62pp (z 0.82) | -2.00pp (z -2.59) |

"Best recent finish came at a higher class than today" is under-rated at every
variance level. That is a horse stepping down to a level below its best, which
is Gap #8's class-relief mispricing. **Restricted to horses not dropping in
class today**, the HIGH higher-class cell goes to **-0.83pp (z -0.36,
n=380)**. Stability was also weak: every year positive, but at z 0.90-1.89,
none above 2. By track only GP clears z 2 (+5.40pp, z 3.03); CT and MNR sit at
z 0.51 and 0.63.

**Distance context carries nothing:** best finish at similar distance +0.05pp,
not similar +0.52pp.

### Finding 3 — the track split is a field-size artifact

HIGH by track looked like a textbook masked interaction (the Gap #8 lesson):
**CT -3.59pp (z -3.92)** against **GP +1.77pp (z +2.68)**, cancelling to zero.
It is not. Raw finish-position SD is mechanically smaller in small fields, and
CT runs small fields. With finish normalised by field size and bucket cuts
matched to the same shares, **CT is -1.07pp (z -1.27) and GP +0.63pp
(z +0.86)**, both null. Under population SD, CT is also null (-1.17pp).
Recorded so this split is not mistaken for a lead.

### Finding 4 — existing features already carry the erratic horse's upside

Step 5's question: does the model use variance through a different channel?
**Yes, through career rates.** At the same recent mean finish, erratic horses
carry higher `career_itm_pct_shrunk`, and `p_fund` rises with it:

| window mean finish | LOW career ITM / p_fund | MOD | HIGH |
|---|---|---|---|
| 3.0-4.5 | 0.403 / 0.450 | 0.409 / 0.438 | 0.416 / 0.433 |
| 4.5-6.0 | 0.312 / 0.307 | 0.351 / 0.347 | 0.372 / 0.373 |
| 6.0-8.0 | 0.286 / 0.242 | 0.299 / 0.261 | **0.334 / 0.322** |

A horse averaging 6th-7th that sometimes hits the board has a better career
record than one that runs 6th-7th every time, and the model prices that. The
averaged recent form understates the erratic horse; the career features
restore it. That is why the HIGH residual is zero.

Within `career_itm_pct_shrunk` quartiles the HIGH residual is -0.48, +0.17,
-1.91, +2.56pp: no consistent sign, and no |z| above 1.94.

### Finding 5 — not a last-race effect (step 6)

| cut | n | net | z |
|---|---|---|---|
| HIGH, last race NOT top-3 | 4,849 | +0.34pp | +0.54 |
| HIGH + top-3 in window, last race NOT top-3 | 4,612 | +0.43pp | +0.66 |
| HIGH, last race WAS top-3 | 3,517 | -0.38pp | -0.48 |
| LOW, last race NOT top-3 | 10,006 | +0.94pp | +2.21 |
| LOW, last race WAS top-3 | 10,822 | **+2.08pp** | +4.84 |

The erratic null holds whether or not the last race was strong. The LOW
effect concentrates in horses whose last race was also on the board. That is
consistent with the surprise below ("consistently good") rather than a pure
last-race effect, since LOW still carries +0.94pp without it.

### The surprise — consistent good form is under-rated

The LOW bucket's +1.53pp is two opposite halves, split by form level:

| cell | n | predicted | actual | net vs all others | net vs same-level others |
|---|---|---|---|---|---|
| **LOW, mean finish < 4.5** | 15,268 | 0.504 | 0.518 | **+2.35pp (z 6.60)** | **+2.35pp (z 6.60)** |
| LOW, mean 4.5-6 | 3,308 | 0.307 | 0.309 | +0.56pp | +0.81pp |
| LOW, mean >= 6 | 2,252 | 0.238 | 0.199 | -3.41pp (z -4.23) | -1.76pp (z -2.18) |

* **Consistently good horses are under-rated** by +2.35pp. The two nets agree
  to two decimals (+2.3508 vs +2.3500); that was checked, and it is not a
  code error.
* **Consistently poor horses look over-rated**, but most of that is the
  model's general over-rating of poor form. Against same-level horses it
  shrinks from -3.41 to -1.76pp (z -2.18), and it is concentrated in maidens
  (-4.62pp). Weak; not pursued.

**Stability (LOW & good):**

| year | n | net | z |
|---|---|---|---|
| 2023 | 4,243 | +3.17pp | +4.69 |
| 2024 | 4,510 | +1.69pp | +2.60 |
| 2025 | 4,280 | +1.95pp | +2.87 |
| 2026 | 2,235 | +2.59pp | +2.80 |

| track | n | net | z |
|---|---|---|---|
| CT | 5,490 | +3.48pp | +5.96 |
| GP | 5,866 | +1.66pp | +2.89 |
| MNR | 3,680 | +1.72pp | +2.32 |
| ELP | 232 | -0.03pp | -0.01 |

Non-maiden +2.43pp (z 6.24); maiden +1.69pp (z 1.91).

**Ranking impact.** This cell differs from Gaps #7 and #8 because consistent
good horses sit *near the top* of the ranking:

* races containing a LOW & good horse: 9,373 of 15,561 (60%)
* **races whose top pick changes** under a +2.35pp correction: **530 (3.4%)**
  (Gap #8: 0.7%)

**Leave-one-year-out ranking test.** The correction was estimated on the other
three years, applied to the held-out year, and scored by exact McNemar on the
discordant races:

| held-out year | net (train) | top pick changed | gained | lost | top-pick ITM delta | p |
|---|---|---|---|---|---|---|
| 2023 | +2.00pp | 132 | 38 | 33 | +0.11pp | 0.635 |
| 2024 | +2.62pp | 161 | 46 | 40 | +0.14pp | 0.590 |
| 2025 | +2.48pp | 138 | 44 | 29 | +0.34pp | 0.101 |
| 2026 | +2.29pp | 92 | 32 | 17 | +0.66pp | 0.044 |
| **all** | — | **523** | **160** | **119** | **+0.26pp** | **0.016** |

Positive in every held-out year, and the train-fold estimate is stable
(+2.00 to +2.62pp). **Read the p-value precisely:** the magnitude was estimated
out of sample, but *the cell itself* was chosen after seeing all four years.
The p=0.016 does not account for that selection.

### Threshold and definition perturbation

| variant | HIGH net | HIGH + top-3 net | LOW & good net | HIGH at CT | HIGH at GP |
|---|---|---|---|---|---|
| baseline (sample SD, 5/3, LOW <= 1.5, HIGH > 3.0) | +0.07 (z 0.13) | +0.12 | **+2.35 (z 6.60)** | -3.59 (z -3.92) | +1.77 (z 2.68) |
| HIGH > 2.5 | -1.17 (z -4.02) | -1.08 | +2.35 | -2.59 | -0.48 |
| HIGH > 3.5 | +0.56 (z 0.70) | +0.56 | +2.35 | -2.15 | +1.33 |
| HIGH > 4.0 | +0.25 (z 0.19) | +0.26 | +2.35 | -4.81 | +1.91 |
| LOW <= 1.00 | — | — | +1.64 (z 2.98) | — | — |
| LOW <= 1.25 | — | — | +1.78 (z 4.18) | — | — |
| LOW <= 1.75 | — | — | +1.61 (z 5.73) | — | — |
| LOW <= 2.00 | — | — | +1.55 (z 6.48) | — | — |
| population SD | +1.05 (z 1.39) | +0.98 | +1.62 (z 5.70) | -1.17 | +2.28 |
| exactly 5 starts, no fallback | +0.19 (z 0.33) | +0.26 | +2.62 (z 6.48) | -3.58 | +2.86 |
| last 3 only | -0.54 (z -1.30) | -0.50 | +1.70 (z 5.25) | -2.34 | -0.12 |
| last 4 (fallback 3) | -0.69 (z -1.46) | -0.61 | +1.57 (z 4.97) | -4.65 | +1.45 |
| **field-normalised finish, share-matched cuts** | -0.32 (z -0.67) | -0.33 | **+2.16 (z 5.49)** | **-1.07 (z -1.27)** | **+0.63 (z 0.86)** |

(pp; "—" = unchanged from baseline, because the LOW threshold does not move
the HIGH cells.)

* **The erratic hypothesis is never supported.** HIGH is null or *negative*.
  The one significant reading (sd > 2.5, -1.17pp) is the loose cut absorbing
  over-rated moderate horses: the wrong sign for the claim.
* **The consistent-good signal survives every variant**, at +1.55 to +2.62pp,
  z 2.98 to 6.60. It survives field normalisation, so it is not a small-field
  artifact. It survives a 3-start window matching `last_3_avg_finish`'s own
  span, so it is not just information from starts 4 and 5.
* **The track split dies under field normalisation** (Finding 3).

### Live log consistency check

`dpv1.2.0-4track`, latest run per race per model. 517 scored horses, 229 with
3+ prior finished starts:

| bucket | n | predicted | actual | residual |
|---|---|---|---|---|
| LOW | 88 | 0.425 | 0.466 | +4.04pp |
| MOD | 114 | 0.366 | 0.439 | +7.27pp |
| HIGH | 27 | 0.332 | 0.185 | -14.71pp |
| LOW & good | 73 | 0.460 | 0.562 | +10.16pp |

**Uninformative at this size.** Live cards are under-predicted across the board
(62.5% top-pick ITM), and n=27 for HIGH is noise. It does not contradict
anything above. Nothing should be read from it until the live log is several
times larger.

### What is not established

* **The mechanism behind the consistent-good signal.** The most natural reading
  is **reliability**: a mean finish from a low-variance history is a more
  precise estimate of ability. The model's averaged-form features treat a
  4.0 mean from [4,4,4] and from [1,7,4] identically, so it under-reacts to the
  reliable one. Plausible, but **not tested**. At least two rivals survive:
  * **class stability.** Consistently good horses may be staying at a level
    they suit, which `class_score_change_from_last` sees only for the last
    race.
  * **selection by connections.** Horses that keep running well keep being
    entered where they fit, and that placement intent is invisible to the
    model.
* **Whether it is calibration or ranking.** Unlike Gaps #7 and #8 it reorders
  enough races (3.4%) to register on top-pick ITM, and the held-out gain is
  positive. But +0.26pp is small, and the cell is post hoc.
* **Anything about erratic horses beyond "priced correctly".**

### Verdict

| question | answer |
|---|---|
| Are high-variance horses under-predicted? | **No** — +0.07pp net (z 0.13), null under all 13 variants |
| Does a top-3 in the window matter? | No — 97% of erratic horses have one; +0.12pp |
| Does best-finish class context discriminate them? | Yes, but it is **not variance-specific**: the same gradient appears in every bucket (class relief, Gap #8 family) |
| Does best-finish distance context matter? | No |
| Do career rates already capture it? | **Yes** — they lift erratic horses' p_fund in step with their actual ITM |
| Is it a last-race effect? | No — the null holds with or without a top-3 last out |
| Anything real underneath? | **Exploratory:** consistent good form under-rated, +2.35pp (z 6.60), stable and threshold-robust, with a small held-out ranking gain |

**The erratic-horse factor is closed. Do not reopen it without a new data
source or framing.** The article's intuition is right that averaged form
understates an erratic horse's recent performance. DPv1 already corrects for
it through career rates.

**The consistent-good cell is open, and next is a pre-registered test, not a
feature.** Fix the definition now (sample SD <= 1.5 over the last 5 finished
starts, fallback 3; window mean finish < 4.5). Then measure it on data not
used here, for example the next ~3 months of live cards once the scored log
can bucket, and test the reliability mechanism against its rivals before any
feature is designed. Because it does reorder races, **measure it with both**
top-pick ITM (paired McNemar) **and** a calibration metric on the subgroup.
It is the first gap in this series where the ranking metric is not
automatically the wrong instrument.

No features were built, no model was retrained, the reranker was not touched,
and nothing outside the diagnostic scripts (session scratchpad: `g9_build.py`,
`g9_lib.py`, `g9_main.py`, `g9_controls.py`, `g9_robust.py`) was modified.

---

## Gap #10 — Cause of the consistent-good mispricing (from Gap #9)

> **STATUS: INVESTIGATED 2026-09-12. A mechanism is IDENTIFIED for the
> calibration error. It does NOT explain the ranking gain. Read both halves
> before choosing a build path.**
>
> **Mechanism — the model under-trusts a finish record that is a reliable
> guide to TODAY's race.** Three conditions stack:
> * **consistent:** low finish variance;
> * **comparable:** earned at one class band, and today is at that class;
> * **long:** more starts, a weaker contributor.
>
> Where all hold, the model under-extrapolates recent form **in both
> directions**: good records are under-credited and poor ones under-penalised.
> The decisive split:
> * consistent good form earned at today's class: **+4.02pp (z 6.12)**;
> * the same consistency earned at a *different* class than today:
>   **+0.06pp** (nothing).
>
> The residual slope on mean finish for consistent horses is **-0.0197 per
> position (z -6.2)** where the record is comparable, and flat (-0.0007)
> where it is not.
>
> **Scoring the three brief mechanisms:**
> 1. **RELIABILITY — SUPPORTED, in a refined form.** Two-sided and
>    variance-graded, as reliability predicts. The literal "more starts" test
>    is only weakly positive; *comparability* of the starts matters more than
>    their number.
> 2. **CLASS STABILITY (placement at true level) — REJECTED as stated.**
>    Controlling for it does **not** eliminate the residual; it
>    **concentrates** it. Class-stable horses as a group are *over*-rated
>    (-1.48pp), which placement cannot explain. Its real role is to make the
>    record comparable, which belongs to mechanism 1.
> 3. **TRAINER PLACEMENT — REJECTED.** No top-quartile concentration in any of
>    14 variants; if anything the effect is largest for *bottom*-quartile
>    trainers (+3.99pp).
>
> **THE CAVEAT THAT DECIDES THE BUILD PATH.** Held out by year, a flat bump on
> the mechanism-sharpened cell gains only **+0.08pp top-pick ITM (p=0.26)**.
> The *non*-comparable remainder of the Gap #9 cell carries most of Gap #9's
> +0.26pp (**+0.21pp, p=0.024**), and this investigation does **not** explain
> that part. The mechanism describes where the **calibration** error is;
> it is **not** yet a better ranking rule. A feature built from it must be the
> **two-sided interaction** (form slope conditioned on consistency x class
> comparability), never a one-sided bonus.

### Sample and test design

Same sample as Gap #9: 75,940 out-of-fold horse-starts with 3+ prior finished
starts. The cell is Gap #9's, unchanged: sample SD <= 1.5 over the last 5
finished starts (fallback 3) and window mean finish < 4.5; n=15,268, baseline
+2.35pp (z 6.60). Stats use race-clustered SEs and p_fund-matched nets, as in
Gap #9. The added data was trainer fields for today plus the trainer on every
prior start.

Each brief test was sharpened before running, because each has a confound as
literally stated:

* **Test 1 (5 starts vs 3).** Horses on the 3-start fallback are also
  *less experienced* (mean 3.5 prior starts vs 15.0), and a 3-point SD is
  noisier. The literal comparison was run, plus a fixed-population version
  (horses with 8+ prior starts) and a **two-sided prediction** unique to
  reliability: consistently poor horses should be over-rated too, so the
  residual slope on mean finish should steepen as variance falls.
* **Test 2 (class stability).** Looking only at class-stable horses cannot
  separate cause from confounding. Run instead: the cell *within* class-stable
  and *within* non-stable strata, and class-stable horses at *any* variance.
  "Class-stable" means every window start is within +/-1 `class_score` of
  today.
* **Test 3 (trainer).** `trainer_365d_winrate_shrunk` quartiles (the brief's
  "trainer_win_pct or similar") and `trainer_at_track_winrate_shrunk`, plus
  whether the same trainer handled every window start.
* **Step 4 (joint).** The residual (y - p_fund) was regressed on the cell
  indicator plus all mechanism controls and p_fund bins, with race-clustered
  SEs.
  * **A column-indexing bug** in the first run printed control coefficients
    from the wrong positions. It was caught because one z came out NaN.
    Columns are now named, and only the corrected run is reported.

### Mechanism 1 — reliability

**1a, literal (cell over 5 starts vs the 3-start fallback, each vs same-window
others):** 5 starts **+2.62pp (z 6.48, n 11,971)**; 3 starts **+1.23pp
(z 1.50, n 3,297)**. Larger with more starts, but confounded by experience.

**1b, fixed population (8+ prior starts, n 45,408), cell re-defined over k
starts:**

| k | net | z | cell share |
|---|---|---|---|
| 3 | +2.21pp | 5.24 | 24.1% |
| 4 | +2.40pp | 5.88 | 26.0% |
| 5 | +3.03pp | 6.48 | 20.2% |
| 6 | +2.56pp | 5.11 | 17.8% |
| 8 | +2.31pp | 4.05 | 14.0% |

**Not monotone; it peaks at k=5.** Holding the set fixed does show a dose
effect: horses consistent over 3 **and** 8 starts net **+3.05pp (z 4.21)**,
against **+1.72pp (z 3.12)** for horses consistent over 3 only. Verdict on the
literal "more observations" prediction: **weakly supported**.

**1c, two-sided (the prediction only reliability makes).** Residual slope on
window mean finish, by variance bucket, mean finish 1-9:

| bucket | n | actual slope | model slope | residual slope | z |
|---|---|---|---|---|---|
| LOW (sd <= 1.5) | 20,809 | -0.0791 | -0.0706 | **-0.0085** | -4.71 |
| MODERATE | 46,722 | -0.0646 | -0.0611 | -0.0035 | -2.22 |
| HIGH (sd > 3) | 8,361 | -0.0420 | -0.0433 | +0.0014 | +0.28 |

The model already gives consistent horses a steeper form slope than erratic
ones, so it partly accounts for reliability, but **not enough**, and the
shortfall grades with variance. That is the reliability signature: under-
extrapolation of a trustworthy mean in *both* directions, not an upward shift.
The poor half is weaker than the good half: consistent-poor horses net
-1.46pp (z -1.08) and -1.93pp (z -1.94) in the two class strata.

### Mechanism 2 — class stability

| cut | n | net | z |
|---|---|---|---|
| cell, within class-stable horses | 4,341 | **+4.03pp** | +5.74 |
| cell, within non-stable horses | 10,927 | **+1.86pp** | +4.39 |
| class-stable horses, any variance, vs non-stable | 17,965 | **-1.48pp** | -4.94 |
| class-stable, not in cell, vs non-stable non-cell | 13,624 | -2.24pp | -6.46 |

Class-stable share: 28.4% of the cell against 22.5% of other horses.

**As stated, the mechanism fails both of its predictions.** Controlling for
class stability leaves a significant residual in each stratum, and class-stable
horses are *over*-rated as a group; trainers placing horses at their true level
would push the other way. What class stability does is **steepen the
two-sided slope**:

| residual slope on mean finish | class-stable | not class-stable |
|---|---|---|
| LOW | **-0.0194 (z -5.63)** | -0.0047 (z -2.18) |
| MODERATE | **-0.0130 (z -3.96)** | -0.0000 (z -0.02) |
| LOW, window 5 vs 3 | -0.0102 (z -4.63) | -0.0051 (z -1.55) |

Among moderate-variance horses the *entire* under-extrapolation lives in the
class-stable group. Class stability is not a placement effect; it decides
whether the finish record is a comparable measure of today.

### Disentangling: consistent-with-itself vs matched-to-today

"Class-stable" as defined also means *no class change today*, which overlaps
Gap #8. It was split into two separate conditions:
* **internal:** window starts within a 2-point `class_score` band of each
  other;
* **today-match:** today within +/-1 of the window's mean class.

| internal | today-match | n | cell vs same-stratum others | consistent-horse residual slope |
|---|---|---|---|---|
| yes | **yes** | 21,091 | **+4.02pp (z 6.12, n 4,945)** | **-0.0197 (z -6.16)** |
| yes | **no** | 7,053 | **+0.06pp (z 0.05, n 1,717)** | -0.0007 (z -0.12) |
| no | yes | 2,700 | +4.05pp (z 1.77, n 425) | -0.0058 (z -0.52) |
| no | no | 45,096 | +1.97pp (z 3.94, n 8,181) | -0.0039 (z -1.53) |

**A consistent record earned at a class other than today's shows no mispricing
at all.** The model is right to discount it. When today *is* at that class,
the model under-trusts it. Excluding every horse changing class today (Gap #8's
territory), the cell is still **+2.82pp (z 5.47)** with slope -0.0125
(z -4.89). This is not Gap #8 resurfacing.

The "no/no" row (+1.97pp) is the part of the effect this mechanism does
**not** account for.

### Mechanism 3 — trainer placement

| `trainer_365d_winrate_shrunk` quartile | cell vs same-quartile others |
|---|---|
| Q1 (<= 0.092) | **+3.99pp (z 4.42, n 2,813)** |
| Q2 | +2.16pp (z 2.65) |
| Q3 | +1.08pp (z 1.45) |
| Q4 (> 0.169) | +2.53pp (z 3.92, n 5,090) |

`trainer_at_track_winrate_shrunk` gives the same picture: Q1 +4.52pp, Q4
+1.36pp. The same trainer across the whole window: +2.33pp; not the same:
+2.14pp. **No concentration in sharp barns.** Separately, top-quartile trainers
are mildly under-rated as a *main effect* (+1.84pp, z 3.50 in the joint model),
but the cell x trainer-Q4 interaction is **-0.79pp (z -0.82)**. The trainer
channel and the consistent-good cell are independent.

### Step 4 — joint control

Residual regression, race-clustered SEs, p_fund bins in every spec:

| spec | cell | notes |
|---|---|---|
| cell only | **+2.48pp (z 5.61)** | |
| + class_stable, window-5, same trainer, trainer quartiles | **+2.61pp (z 5.90)** | class_stable -1.58pp (z -4.22); window-5 +0.14pp; same trainer +0.62pp (z 1.81); trainer Q4 +1.84pp (z 3.50) |
| + window mean-finish bins | **+2.14pp (z 4.15)** | survives conditioning on form level |
| + cell x {class_stable, window-5, trainer Q4} | -0.30pp (z -0.27) | **cell x class_stable +3.09pp (z 3.22)**, cell x window-5 +2.17pp (z 2.05), cell x trainer Q4 -0.79pp (z -0.82) |

**The effect holds after controlling for all three mechanisms as main
effects.** It resolves into **interactions**: with them in the model, the
cell's base term goes to zero, and the effect lives where the record is
comparable (strongly) and long (moderately). Trainer does not interact.

### Threshold and definition perturbation

Values are pp (z) unless shown as slopes. "CS" = class-stable.

| variant | cell net | joint cell | cell in CS | cell not in CS | cell x CS | cell x W5 | trainer Q1 | trainer Q4 | LOW slope, CS | LOW slope, not CS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +2.35 (6.6) | +2.61 (5.9) | +4.03 (5.7) | +1.86 (4.4) | +3.09 (3.2) | +2.17 (2.0) | +3.99 (4.4) | +2.53 (3.9) | -0.0194 (-5.6) | -0.0047 (-2.2) |
| LOW sd <= 1.00 | +1.64 (3.0) | +1.85 (3.0) | +2.98 (2.8) | +1.21 (1.9) | +3.37 (2.5) | +0.62 (0.5) | +2.60 (1.9) | +3.53 (3.8) | -0.0203 (-4.5) | -0.0042 (-1.5) |
| LOW sd <= 1.25 | +1.78 (4.2) | +2.08 (4.2) | +4.19 (5.1) | +0.99 (1.9) | +4.30 (4.0) | +1.60 (1.4) | +3.82 (3.5) | +2.44 (3.3) | -0.0200 (-5.2) | -0.0038 (-1.6) |
| LOW sd <= 1.75 | +1.61 (5.7) | +1.90 (4.8) | +3.96 (6.8) | +1.01 (3.0) | +3.31 (3.9) | +1.88 (2.0) | +3.46 (4.7) | +1.75 (3.3) | -0.0179 (-6.1) | -0.0031 (-1.7) |
| LOW sd <= 2.00 | +1.55 (6.5) | +1.87 (5.0) | +4.36 (8.3) | +0.87 (3.0) | +3.51 (4.4) | +1.94 (2.2) | +3.49 (5.5) | +0.97 (2.1) | -0.0166 (-6.2) | -0.0028 (-1.7) |
| good mean < 4.0 | +2.37 (6.1) | +2.62 (5.5) | +4.63 (6.0) | +1.67 (3.7) | +4.02 (3.9) | +2.24 (2.0) | +4.10 (4.0) | +2.60 (3.9) | -0.0194 (-5.6) | -0.0047 (-2.2) |
| good mean < 5.0 | +2.39 (7.0) | +2.63 (6.1) | +4.06 (6.0) | +1.91 (4.6) | +3.02 (3.2) | +2.16 (2.1) | +3.95 (4.7) | +2.73 (4.3) | -0.0194 (-5.6) | -0.0047 (-2.2) |
| class tolerance +/-0 | +2.35 (6.6) | +2.59 (5.8) | +3.74 (3.9) | +2.20 (5.7) | +2.45 (2.0) | +2.20 (2.1) | +3.99 (4.4) | +2.53 (3.9) | -0.0177 (-3.8) | -0.0071 (-3.6) |
| class tolerance +/-2 | +2.35 (6.6) | +2.61 (5.9) | +3.87 (6.2) | +1.68 (3.7) | +3.19 (3.5) | +2.13 (2.0) | +3.99 (4.4) | +2.53 (3.9) | -0.0179 (-6.0) | -0.0034 (-1.5) |
| class tolerance +/-3 | +2.35 (6.6) | +2.60 (5.9) | +3.96 (6.5) | +1.56 (3.4) | +3.33 (3.7) | +2.12 (2.0) | +3.99 (4.4) | +2.53 (3.9) | -0.0161 (-5.5) | -0.0039 (-1.7) |
| population SD | +1.62 (5.7) | +1.91 (4.8) | +3.87 (6.6) | +1.04 (3.1) | +3.19 (3.8) | +1.88 (2.0) | +3.36 (4.6) | +1.47 (2.7) | -0.0177 (-6.0) | -0.0033 (-1.8) |
| exactly 5 starts | +2.62 (6.5) | +2.84 (5.7) | +3.92 (4.8) | +2.36 (4.9) | n/a* | n/a* | +4.78 (4.6) | +2.47 (3.4) | -0.0163 (-3.9) | -0.0076 (-2.9) |
| last 3 only | +1.70 (5.3) | +1.90 (4.5) | +4.58 (8.5) | **+0.11 (0.3)** | +5.02 (6.0) | n/a | +3.33 (4.1) | +1.63 (2.8) | -0.0198 (-8.2) | -0.0008 (-0.4) |
| field-normalised finish | +2.16 (5.5) | +2.40 (5.1) | +3.49 (4.6) | +1.79 (3.8) | +2.70 (2.7) | +1.81 (1.7) | +2.66 (2.7) | +2.77 (4.0) | -0.0214 (-7.4) | -0.0053 (-2.9) |

\* With no fallback every row has window 5, so the window-5 term is collinear
with the constant and cell x window-5 is collinear with the cell. The
regression's split of those terms is not interpretable.

**Every structural reading holds in all 14 variants:**
* the cell is larger inside class-stable horses than outside;
* the consistent-horse slope is steep where the record is comparable (z -3.8
  to -8.2) and near-flat elsewhere;
* cell x class-stable is positive (z 2.0-6.0);
* trainer Q4 never concentrates the effect. Q4 exceeds Q1 only at sd <= 1.00
  (+3.53 vs +2.60) and under field normalisation (+2.77 vs +2.66), and neither
  is a concentration.

**The weakest component is window length** (cell x window-5, z 0.5 to 2.2).
With a 3-start window, the entire effect sits inside class-stable horses
(+4.58pp vs +0.11pp).

### Ranking: the mechanism does not sharpen the ranking gain

Leave-one-year-out, as in Gap #9. The correction is estimated on three years,
applied to the fourth, and scored by exact McNemar on discordant races. 32.4%
of the Gap #9 cell has a comparable class record.

| cell | top pick changed | gained | lost | top-pick ITM | p |
|---|---|---|---|---|---|
| Gap #9 cell | 523 (3.4%) | 160 | 119 | **+0.26pp** | 0.016 |
| **sharpened: cell & comparable class** | 198 (1.3%) | 54 | 42 | **+0.08pp** | 0.261 |
| cell & NOT comparable | 322 (2.1%) | 110 | 78 | **+0.21pp** | 0.024 |

Per year, the sharpened cell reads -0.02, +0.20, +0.02, +0.13pp; the
non-comparable remainder +0.02, +0.20, +0.23, +0.53pp.

**Most of Gap #9's held-out ranking gain comes from the part the mechanism
does not explain.** The likely reason is structural, not a contradiction.
Measured against *all* horses, comparable-class horses are over-rated as a
group (class-stable main effect -1.58pp), so a flat upward bump on only their
good half is the wrong-shaped correction. The mechanism is two-sided, and a
one-sided flat bonus cannot express it. That is a hypothesis about the shape a
feature needs; **it is not tested here.**

### Verdict

| question | answer |
|---|---|
| Reliability? | **Supported, refined:** two-sided under-extrapolation that grades with variance (slope -0.0085 / -0.0035 / +0.0014 for LOW / MOD / HIGH) and concentrates where the record is comparable. "More starts" alone is weak. |
| Class stability (placement)? | **Rejected as stated.** Control does not eliminate the residual, and class-stable horses are over-rated. It works as the *comparability* condition of reliability. |
| Trainer placement? | **Rejected.** No Q4 concentration in any variant; the interaction is null. |
| Holds after controlling all three? | **Yes**, +2.61pp (z 5.90), +2.14pp with form-level bins. It resolves into cell x comparability (+3.09pp) and cell x window length (+2.17pp). |
| Stable to thresholds? | **Yes**, all structural readings in all 14 variants. |
| Does the mechanism give a better ranking rule? | **No.** The sharpened flat cell gains +0.08pp (p 0.26); most of the ranking gain is in the unexplained remainder. |
| Unexplained | The non-comparable consistent-good horses: +1.97pp calibration, +0.21pp held-out ranking |

**Input for the build decision (not a decision).**
* The mechanism is identified well enough to specify a **feature shape**:
  recent-form level *interacted with* a reliability term (finish consistency)
  and a comparability term (window class band matching today). It must be
  two-sided, and it is horse-level, so by the Feature Design Principle it
  can reorder.
* The evidence does **not** support shipping a one-sided "consistent-good
  bonus". It also does not show that the mechanism-shaped feature would beat
  Gap #9's cruder cell on ranking; that must be measured.
* **Any build must be measured three ways on held-out folds:** top-pick ITM
  with paired McNemar; log-loss/Brier on the consistent and comparable
  subgroups; and the residual slope table above, which should flatten if the
  feature works.
* Build it **alongside a corpus-matched control** (Gap #6 rule).
* Nothing here yet explains the ranking gain from non-comparable
  consistent-good horses.

No features were built, no model was retrained, the reranker was not touched,
and nothing outside the diagnostic scripts (session scratchpad: `g10_build.py`,
`g10_lib.py`, `g10_main.py`, `g10_joint.py`, `g10_robust.py`, `g10_rank.py`)
was modified.

---

## Gap #11 — The residual ranking gain (Gap #10's unexplained remainder)

> **STATUS: INVESTIGATED 2026-09-12. The remainder is REAL, and its mechanism
> is identified. It is NOT a second consistency effect. It is a slice of a
> broader, general CLASS-CONTEXT gap that affects every horse.**
>
> **Mechanism — the model misprices a horse racing below (or above) its
> RECENT AVERAGE class.** DPv1's only class-movement feature,
> `class_score_change_from_last`, looks back one race.
> * Horses racing below their 3-5-start average class are **under-rated
>   +1.60pp raw (z 7.58, n 31,027)**.
> * Horses racing above it are **over-rated -2.01pp raw (z -7.88)**.
> * Where the model's own feature cannot see the drop, because the last race
>   was already at today's class, the miss is **+3.38pp (z 9.0)** against
>   level horses in the same stratum.
>
> **The Gap #10 remainder is exactly this.** Not-comparable consistent horses
> racing below their window class gain **+0.31pp top-pick ITM held out
> (p 0.001)**; the rest of the remainder gains **-0.03pp**. Comparable horses
> are level by construction, so the two effects are **disjoint**.
>
> **As a rule on all horses it beats every consistent-cell rule on ranking.**
> Below-window-class alone, held out by year: **+0.42pp (p 0.001)**. Combined
> with Gap #10's comparable-cell term: **+0.48pp (p 0.0004)**, positive in every
> year. Gap #9's crude cell: +0.26pp.
>
> **Brief candidates:**
> * **class improvement — NULL; the sign is reversed.** It is the drop.
> * **fresh start — null.**
> * **layoff — null or negative.** It cancels the effect rather than
>   explaining it.
> * **sample artifact (maiden graduation / `class_score` cross-type scale) —
>   ruled out.** Maiden special weight -> claiming, the scale-artifact
>   transition, contributes nothing.
>
> **TWO CAVEATS THAT SHAPE ANY BUILD:**
> 1. **The ranking gain comes from drops that cross race types** (allowance,
>    stakes or starter into cheaper company): +0.28pp, p 0.001. Drops within
>    one race family are mispriced (+4.21pp net) but reorder almost nothing
>    (+0.03pp). A feature has to carry class across race-type bands.
> 2. **The direction was data-chosen.** The brief proposed class
>    *improvement*, and this is its reverse. The evidence is strong (raw z 7.6,
>    held-out gain in every variant and year), but the build should be judged
>    on a pre-registered held-out test like any other.

### Sample

Same as Gaps #9 and #10: 75,940 out-of-fold horse-starts with 3+ prior finished
starts. The Gap #9 cell (15,268) splits into **comparable 4,945 / not
comparable 10,323**, using Gap #10's definition: window class band <= 2 points
and today within +/-1 of the window's mean class.

`dir` = today's `class_score` minus the window's mean `class_score`.
**BELOW** = dir < -1; **ABOVE** = dir > +1. Race families (maiden, claiming,
starter, allowance, stakes) come from `races.race_type` for every window start.

**Composition of the remainder** (not-comparable cell vs comparable cell vs
non-cell horses):

| attribute | not comparable | comparable | non-cell |
|---|---|---|---|
| today ABOVE window class | **50.8%** | 0% | 26.2% |
| today BELOW window class | **45.1%** | 0% | 43.5% |
| window includes a different race type than today | **80.1%** | 0.1% | 57.1% |
| maiden graduate (maiden in window, not today) | 27.4% | 0% | 20.9% |
| maiden race today | 12.9% | 26.2% | 18.0% |
| never raced within +/-1 of today's class | 24.8% | 0% | 17.5% |
| layoff >= 60d | 19.1% | 11.9% | 16.6% |
| model top pick | 26.8% | 25.4% | 11.3% |
| mean p_fund | 0.508 | 0.495 | 0.390 |

The remainder is almost entirely horses **moving class**, split roughly half up
and half down, and mostly across race types. Both halves of the cell sit near
the top of the ranking.

### Finding 1 — the remainder is real, and it lives in one stratum

| subset | calibration net | LOYO top-pick ITM | p |
|---|---|---|---|
| not comparable (all) | **+2.08pp (z 4.76)** | **+0.21pp** (gained 110, lost 78) | 0.024 |
| ...internally class-consistent, today at another class | -0.35pp | +0.02pp | 0.68 |
| ...not internally consistent, today matches | +1.57pp (n 425) | -0.01pp | 1.00 |
| ...**neither** | **+2.62pp (z 5.24)** | **+0.22pp** | 0.023 |

**Placebo.** The same per-year corrections were applied to random non-cell
horses matched on model rank (50 draws), testing whether the gain comes merely
from bumping horses near the top.
* Placebo mean +0.003pp; 5th-95th percentile -0.103 to +0.109pp; max +0.129pp.
* **The real +0.206pp beats all 50 draws.** The gain comes from mispricing,
  not ranking position.

### Finding 2 — mechanism candidates

Columns:
* **[A]** not-comparable cell horses with the attribute, net vs non-cell horses;
* **[B]** cell horses with the attribute vs non-cell horses *with the same
  attribute* (is it consistency-specific?);
* **[C]** the attribute among non-cell horses generally (is it general?);
* **[D]** LOYO ranking on [A].

| candidate | share | [A] | [B] | [C] | [D] |
|---|---|---|---|---|---|
| **class improvement** (today ABOVE window) | 50.8% | **+0.17pp (z 0.27)** | +2.77pp | **-2.27pp (z -7.29)** | **-0.03pp** |
| **class drop** (today BELOW window) | 45.1% | **+4.28pp (z 6.38)** | +2.23pp (z 3.33) | **+3.90pp (z 16.41)** | **+0.31pp, p 0.001** |
| fresh start (never at today's class) | 24.8% | -0.30pp | -0.35pp | +0.71pp | +0.08pp |
| layoff >= 60d | 19.1% | -2.21pp (z -2.12) | +0.17pp | -0.54pp | +0.03pp |
| layoff >= 180d | 7.6% | -4.61pp (z -2.70) | -1.64pp | -1.48pp | -0.06pp |
| maiden graduate | 27.4% | +0.45pp | +1.99pp | -1.62pp | +0.01pp |
| any race-type change in window | 80.1% | +1.79pp | +1.83pp | +0.65pp | +0.08pp |
| ABOVE, no type change | 7.1% | -1.86pp | +0.52pp | -2.12pp | +0.01pp |
| BELOW, no type change | 10.8% | +6.36pp (z 4.47) | +2.21pp | +3.13pp (z 6.22) | +0.10pp |

* **Class improvement — rejected.** The brief's idea was that consistency at a
  lower class makes the model over-penalise a move up. Instead, horses moving
  up are priced correctly when consistent ([A] +0.17pp) and **over**-rated in
  general ([C] -2.27pp). The model under-penalises a move up, if anything.
* **Class drop — the mechanism.** Consistent horses racing below their recent
  average class carry the whole ranking gain. [C] shows the effect is
  **general**: +3.90pp across 26,371 non-cell horses. [B] shows consistency
  adds to it (+2.23pp), not that it creates it.
* **Fresh start — rejected.** Null on every column.
* **Layoff — rejected.** Negative, and in a residual regression it *cancels*
  the remainder: not-comparable x layoff 60+ is -4.13pp (z -3.19); x fresh class
  -2.76pp (z -2.22).
* **Maiden-graduation artifact — rejected.** See Finding 4.

### Finding 3 — the effect is general, and the model's class feature misses it

Raw residuals (actual - p_fund), no pooling:

| window direction | all horses | non-cell | cell |
|---|---|---|---|
| ABOVE (> +1) | **-2.01pp (z -7.88)**, n 21,122 | -2.46pp | -0.65pp |
| LEVEL | -1.36pp (z -5.37), n 23,791 | -2.31pp | +1.91pp |
| BELOW (< -1) | **+1.60pp (z +7.58)**, n 31,027 | +1.34pp | **+3.13pp** |

On this sample the model's overall residual is -0.33pp. The gradient runs
about 3.6pp from ABOVE to BELOW.

**Specificity vs the existing feature (step 3).** BELOW-window horses against
LEVEL-window horses, within strata of the model's own
`class_score_change_from_last`:

| last-race class change | share BELOW | BELOW vs LEVEL |
|---|---|---|
| drop | 75% | **+0.53pp (z 1.53)** — the model already sees these |
| same | 33% | **+3.38pp (z 9.02)** — invisible to the model |
| rise | 18% | **+3.38pp (z 4.28)** — invisible to the model |

**`class_score_change_from_last` captures the drop only when it happened in the
last race.** A horse whose last start was already at today's level, or was a
brief step up, but whose recent average class was higher, is under-rated by
about 3.4pp. The model has no multi-race class context.

**Stability (BELOW, all horses, net vs non-BELOW):**
* **By year:** 2023 +3.72pp (z 9.42), 2024 +3.23pp (z 8.14), 2025 +3.05pp
  (z 7.63), 2026 +3.88pp (z 7.07).
* **By track:** CT +3.50, GP +3.81, MNR +2.56pp (all z > 5); ELP +0.46pp
  (n 498).
* **By today's race family:** positive in every family (claiming +4.49pp,
  z 17.4).

### Finding 4 — where the ranking gain lives: cross-type class relief, not a scale artifact

`class_score` is not monotone across race types: maiden special weight
(43-48) scores above ordinary claiming (21-29). The worry was that "BELOW"
ranking gains came from that scale. Split by transition (dominant window
family -> today):

| BELOW group | n | calibration net | raw | LOYO ITM | p |
|---|---|---|---|---|---|
| no race-type change | 7,765 | **+4.21pp (z 9.18)** | +2.48pp | **+0.03pp** | 0.71 |
| type change, maiden graduate | 5,030 | +2.31pp | +0.52pp | +0.01pp | 0.86 |
| **type change, not maiden graduate** | 18,232 | **+3.34pp (z 11.58)** | +1.53pp | **+0.28pp** | **0.001** |
| ...allowance -> claiming | 4,052 | +4.76pp (z 6.83) | +2.93pp | +0.08pp | 0.19 |
| ...stakes -> allowance/claiming | 968 | +4.63pp (z 3.19) | +2.47pp | +0.08pp | 0.029 |
| ...starter -> claiming | 1,587 | +4.92pp (z 4.24) | +3.13pp | +0.05pp | 0.32 |
| ...claiming -> starter | 283 | +1.55pp | -0.11pp | -0.01pp | 1.00 |
| **...maiden special weight -> claiming** (scale-artifact candidate) | 1,888 | +1.28pp (z 1.26) | **-0.55pp** | **-0.01pp** | 1.00 |

* **The scale-artifact transition contributes nothing.** It is null on raw
  residual and on ranking.
* **The ranking gain is genuine class relief across race-type bands**, spread
  over allowance, stakes and starter horses dropping into cheaper company.
  Each is individually under-rated +4.6 to +4.9pp on calibration, and no
  single transition carries the ranking gain.
* **Within-family drops are a calibration-only error.** They are mispriced
  +4.21pp but reorder almost nothing. That is consistent with the model's
  last-race feature doing most of the within-family ordering, but the
  explanation is **not tested**.

Mean ranking position is similar in both groups (rank 4.20 vs 4.01), so
position does not explain the difference.

### Finding 5 — overlap with Gap #8

Gap #8's judgment-free cut is claiming/OC, no ITM in last 3, last-race class
drop. **81% of it is BELOW-window.**

| stratum | no-ITM-last-3 & last-race drop | no-ITM-last-3 & NOT dropping |
|---|---|---|
| all claiming/OC | +3.30pp (z 4.40), n 3,625 | -3.12pp (z -6.91) |
| BELOW window | +2.10pp (z 2.46), n 2,936 | -3.00pp (z -3.69) |
| NOT BELOW window | +0.87pp (z 0.55), n 689 | -2.77pp (z -4.96) |

**Partial overlap.** Window class direction absorbs part of Gap #8's
under-rated dropper half: +3.30pp overall, +2.10pp within BELOW. It leaves
+2.10pp within BELOW, and n=689 outside it is too small to read. It does
**not** touch Gap #8's over-rated half (poor form, not dropping: about -3pp in
every stratum). One class-context feature might cover part of Gap #8, not all
of it.

### Threshold and definition perturbation

LOYO values are top-pick ITM in pp.

| variant | remainder calib | remainder LOYO | remainder & BELOW | remainder & not BELOW | BELOW raw | BELOW (all) LOYO | BELOW vs LEVEL, last-race same | BELOW, no type change LOYO | two-part LOYO |
|---|---|---|---|---|---|---|---|---|---|
| baseline | +2.08 (z 4.8) | +0.21 p .024 | +0.31 p .001 | -0.03 | +1.60 (z 7.6) | **+0.42 p .001** | +3.38 (z 9.0) | +0.03 | **+0.48 p .0004** |
| BELOW dir < -0.5 | +2.08 | +0.21 | +0.31 p .001 | -0.03 | +1.58 (z 8.2) | +0.41 p .004 | +3.63 (z 10.7) | +0.08 | +0.45 p .002 |
| BELOW dir < -3 | +2.08 | +0.21 | +0.24 p .004 | +0.08 p .035 | +1.94 (z 8.0) | +0.46 p .000 | +3.53 (z 8.2) | +0.03 | +0.50 p .000 |
| BELOW dir < -5 | +2.08 | +0.21 | +0.22 p .003 | +0.09 | +2.20 (z 8.3) | +0.35 p .006 | +3.11 (z 6.5) | -0.01 | +0.38 p .003 |
| comparability band 1, tol 0 | +2.38 (z 6.1) | +0.25 p .018 | +0.31 p .001 | +0.12 p .018 | +1.60 | +0.42 | +3.38 | +0.03 | +0.46 p .001 |
| comparability band 3, tol 2 | +1.95 (z 4.3) | +0.17 p .039 | +0.24 p .006 | -0.03 | +1.60 | +0.42 | +3.38 | +0.03 | +0.44 p .001 |
| cell sd <= 1.25 | +1.19 (z 2.3) | **+0.08 p .16** | +0.09 p .20 | -0.04 | +1.60 | +0.42 | +3.38 | +0.03 | +0.43 p .001 |
| cell sd <= 1.75 | +1.29 (z 3.7) | **+0.08 p .30** | +0.24 p .020 | -0.02 | +1.60 | +0.42 | +3.38 | +0.03 | +0.48 p .000 |
| cell mean < 4.0 | +1.79 (z 3.8) | +0.15 p .052 | +0.30 p .000 | -0.04 | +1.60 | +0.42 | +3.38 | +0.03 | +0.47 p .001 |
| cell mean < 5.0 | +2.19 (z 5.2) | +0.21 p .025 | +0.42 p .000 | -0.03 | +1.60 | +0.42 | +3.38 | +0.03 | +0.42 p .001 |
| exactly 5 starts | +2.68 (z 5.4) | +0.21 p .029 | +0.37 p .000 | -0.02 | +1.74 (z 7.1) | +0.42 p .001 | +3.49 (z 8.5) | +0.04 | +0.40 p .003 |
| last 3 only | +0.63 (z 1.4) | **+0.06 p .14** | +0.15 p .031 | -0.03 | +1.68 (z 6.9) | +0.33 p .008 | +2.93 (z 6.2) | +0.08 | +0.29 p .029 |

Two readings with opposite robustness:
* **The remainder, as a slice of the consistent cell, is threshold-fragile.**
  It loses significance at sd <= 1.25, sd <= 1.75 and with a 3-start window.
  The consistency label was never the operative variable.
* **The class-context effect is robust everywhere.** BELOW (all horses) holds
  in all 12 variants (+0.33 to +0.46pp, p <= 0.008). The miss invisible to
  the model's feature holds at +2.93 to +3.63pp, z >= 6.2. The two-part
  correction holds at +0.29 to +0.50pp, and within-family drops never gain on
  ranking.

### What is not established

* **Why within-family drops mispricing stays calibration-only.** The model's
  last-race feature may already order them; untested.
* **Whether a trained feature reproduces a flat-bump gain.** Every ranking
  number here is a flat per-year correction on `p_fund`, not a retrained
  model. A trained feature interacts with everything else and could capture
  more or less.
* **The over-rated ABOVE half.** It is as large as the under-rated BELOW half
  (-2.01 vs +1.60pp raw), but a flat penalty on it was not tested for ranking.
* **Gap #8's residual** after window context: +2.10pp dropper half, -3pp
  non-dropper half.

### Verdict

| question | answer |
|---|---|
| Is the +0.21pp remainder real? | **Yes.** Placebo beats 50/50 draws; calibration +2.08pp (z 4.76). As a consistent-cell slice it is threshold-fragile, because consistency is not the operative variable. |
| Mechanism | **Racing below recent average class** (window-mean `class_score`, not last race). General to all horses; consistency amplifies calibration but is not required. |
| Class improvement / fresh start / layoff / artifact? | Improvement null (reversed); fresh start null; layoff null or negative; maiden-graduation and cross-type scale artifacts ruled out. |
| Does an existing feature capture it? | **Only partly.** `class_score_change_from_last` handles drops from the last race (+0.53pp residual) and misses drops relative to the recent average (+3.38pp, z 9.0). |
| Two real effects on the consistent-good cell? | **Yes, disjoint.** Gap #10 (reliable comparable record, two-sided, mainly calibration) and Gap #11 (window class drop, calibration and ranking). |
| What was Gap #9's crude cell? | **A proxy.** It picked up Gap #10's comparable horses (calibration) plus a slice of Gap #11's class-drop horses (ranking). Its +0.26pp ranking gain is mostly Gap #11. |

**Shipping decision input (a recommendation, not a decision):**

| option | held-out top-pick ITM | assessment |
|---|---|---|
| Gap #9 crude cell | +0.26pp (p 0.016) | **Do not ship.** A proxy for two other effects, and threshold-fragile. |
| Gap #10 cause-sharpened cell | +0.08pp (p 0.26) | **Do not ship as a flat bonus.** The mechanism is two-sided; worth it only inside a slope-shaped feature. |
| Gap #11 BELOW-window, all horses | **+0.42pp (p 0.001)** | Strongest single rule, general, robust in every variant. |
| **Gap #11 + Gap #10 two-part** | **+0.48pp (p 0.0004)** | Best measured. Every year positive (+0.29 to +0.61pp). |

**The recommended next build is a new cause-informed feature:**
* **Multi-race class context:** today's class relative to the horse's recent
  window of 3-5 starts. Signed, so it covers the over-rated ABOVE side as well
  as the BELOW side, and it must carry class across race-type bands.
* **Optionally, Gap #10's two-sided comparability term:** form slope x
  consistency x class match. Both are horse-level and vary within a race, so
  both can reorder.

Requirements for that build:
* Train it **alongside a corpus-matched control.**
* Judge it on **held-out folds** with paired McNemar on top-pick ITM, **plus**
  log-loss/Brier on the BELOW and ABOVE subgroups, **plus** the raw
  direction-residual table above, which should flatten.
* **Check Gap #8's residual** in the same run.

**Unifying hypothesis, untested:** Gaps #8, #10 and #11 each trace to the same
structural blind spot. DPv1's form features are **class-agnostic averages**,
and its class feature looks **one race back**. A single class-contextualised
form representation might address all three. Record it as a direction, not a
finding.

No features were built, no model was retrained, the reranker was not touched,
and nothing outside the diagnostic scripts (session scratchpad: `g11_lib.py`,
`g11_part1.py` to `g11_part5.py`) was modified.

### Gap #11 build — Path A (base-model feature), 2026-09-12

> **RESULT: the class-context feature improves the base model on every
> measure asked for, against a corpus- and feature-matched control.**
> * **Top-pick ITM +0.43pp:** 535 races gained vs 467 lost, exact McNemar
>   **p = 0.034**, positive in all 4 years.
> * **Log-loss improves:** z -7.6 overall, and in every class-direction
>   subgroup.
> * **The class-direction residual spread collapses** from 3.56pp to -0.48pp.
> * **Gap #10's two-sided slope flattens** from -0.0189 to -0.0009.
>
> **Two new problems, and a caveat:**
> * **A new miscalibration.** Horses whose last race was a class rise but who
>   still sit below their recent average class are now **over-rated -4.86pp
>   (z -6.2, n 3,145)**, where the control had -1.97pp.
> * **Gap #8 is mostly not fixed.** Bucket C goes from +3.60 to +3.18pp.
> * **Not a pre-registered test.** The feature was designed from Gaps #9-#11,
>   which analysed out-of-fold outcomes over these same years. The fold
>   comparison is out-of-sample for the *model*, not for the *design*.
>   Confirmation needs data after 2026-09-12.
>
> **Not promoted.** `dpv1.pkl` is unchanged (sha256 verified).

**What was built**
* `new_features/class_context_features.py`, registered in
  `feature_builder_dpv1.DPV1_MODULES`.
* `class_direction` registered in `prepare_training_dpv1.DPV1_CATEGORICAL_FEATURES`.
  Without that entry an object-dtype column is silently dropped by the
  Preprocessor.
* Config `dpv1.3.0` -> **`dpv1.4.0`** (121 active features).

Eight columns:

| column | definition |
|---|---|
| `avg_class_recent` | mean `class_score` over the last 5 prior finished starts (fallback 3) |
| `class_drop_signed` | today minus the window mean (+ = rising) |
| `class_direction` | DROPPING < -0.5 / SAME / RISING > +0.5 / NO_HISTORY |
| `class_context_missing` | explicit flag; values imputed with today's race class |
| `low_finish_variance` | window finish SD <= 1.5 |
| `lowvar_x_dropping`, `lowvar_x_rising` | spec interaction; SAME is the reference |
| `lowvar_same_x_mean_finish` | Gap #10's two-sided slope term |

`lowvar_same_x_mean_finish` goes beyond the brief's literal flag x flag
interaction. Gap #10 found a slope, which a level shift cannot express.

**Verification before training**
* **Exact reproduction of the Gap #11 diagnostic** on its 75,940 rows: max
  |signed - dir| = 0; BELOW 31,027 / LEVEL 23,791 / ABOVE 21,122 identical.
  The low-variance flag and mean finish also match exactly.
* **Imputation:** 39.6% of entries flagged missing (career_starts < 3: 39.5%);
  every missing row has signed = 0.
* **Values vary within races:** 87.8% of races.
* **Range:** signed runs -52 to +65. The 412 rows beyond |40| are cross-band
  moves such as stakes to maiden-claiming, not outliers.

**Control design**
* **Trained through Piece 4** (`retrain_pipeline.py --execute --skip-load`) on
  the identical corpus: 152,865 rows, 20,525 races, no charts pending.
* **Control** `dpv1_20260912_classctx_control.pkl` (`dpv1.3.2-4track-ctrl`):
  the pre-change config, which includes the 13 Gap #6 features
  (108 fundamental cols).
* **Candidate** `dpv1_20260912_classctx_candidate.pkl`
  (`dpv1.4.0-4track-classctx`): the same, plus the 8 columns.
* **Both artifacts carry protected suffixes**, so Piece 4 housekeeping cannot
  prune them.
* **Both runs pinned `PYTHONHASHSEED=0`**, because of the determinism bug
  below. After the runs, **all 120 pre-existing feature columns were
  byte-identical** between the control's and candidate's training tables. The
  only difference between the two models is the eight new columns.

**FOUND DURING THE BUILD — pre-existing bug, FIXED the same day in `d317f76`:
`running_style_last_3` was nondeterministic.**
* **Cause.** `pace_bias_features._dominant_style_last_3` breaks ties by
  iterating `set(vals)`. Python randomises string hash order per process, so a
  horse whose last three starts show three different styles gets a random
  "dominant" style on **every rebuild**. The comment says ties break toward the
  most recent start; the code does not.
* **Evidence.** Two consecutive rebuilds on 2026-09-12 disagreed on **23,799 of
  222,362 rows (10.7%)**. A probe reproduced it under different seeds and gave
  stable output with the seed pinned.
* **Consequences.**
  * Every model has been trained on one random draw of this column, while live
    picks read whatever the latest rebuild produced.
  * Any before/after model comparison that did not pin the seed carries this
    noise, including the Gap #6 comparisons.
* **Fixed in `d317f76`** (2026-09-12, after this build). Ties now break toward
  the most recent start, which is what the docstring already claimed. Output is
  identical under hash seeds 1, 7 and 12345, and the feature table was rebuilt
  so live picks read deterministic values. `running_style_last_3` was the only
  column that changed: 33,043 rows (14.9%), the full tie population. No model
  was retrained for it, so **the control and candidate above were trained on
  the pre-fix `PYTHONHASHSEED=0` draw and are not comparable to anything built
  on the current table.** Step 3 therefore retrained its own control rather
  than reusing these two artifacts.

**Results (fold predictions, 119,535 rows, 15,971 races, rank by `p_fund`)**

| measure | control | candidate | delta |
|---|---|---|---|
| top-pick ITM | 64.310% | **64.736%** | **+0.426pp**, 535 vs 467 discordant, **p 0.034** |
| top-pick win | 28.646% | 28.940% | +0.29pp, 426 vs 379, p 0.10 |
| top pick changed | — | — | 1,783 races (11.2%) |
| log-loss, all | 0.61536 | **0.61436** | -0.00100 (z -7.61) |

On the 15,561 races shared with the live model's own 8/22 folds: live 2.0
64.090%, control 64.212%, candidate **64.617%**.

**Per year, top-pick ITM delta:** 2023 +0.24pp (p 0.56), **2024 +0.82pp
(p 0.035)**, 2025 +0.27pp (p 0.49), 2026 +0.33pp (p 0.54).

**Log-loss by class direction** (negative = better; residual = y - p_fund):

| subgroup | n | log-loss delta | z | residual control -> candidate |
|---|---|---|---|---|
| DROPPING (feature, +/-0.5) | 36,389 | -0.00101 | -4.27 | +1.45 -> -0.55pp |
| SAME | 17,057 | -0.00200 | -4.87 | -1.89 -> -0.36pp |
| RISING | 24,478 | -0.00202 | -7.18 | -2.17 -> -0.25pp |
| NO_HISTORY | 41,588 | +0.00004 | +0.26 | -0.22 -> -0.22pp (untouched, as expected) |
| Gap #11 BELOW (< -1) | 31,705 | -0.00107 | -4.01 | +1.48 -> -0.62pp |
| Gap #11 ABOVE (> +1) | 21,818 | -0.00195 | -6.42 | -2.08 -> -0.14pp |

**Class-direction residual table** (raw y - p_fund, horses with 3+ prior
finished starts):

| stratum | BELOW | LEVEL | ABOVE | ABOVE-to-BELOW spread |
|---|---|---|---|---|
| all, control | +1.48 (z 7.1) | -1.39 | -2.08 (z -8.3) | 3.56pp |
| all, **candidate** | -0.62 (z -3.0) | -0.39 | -0.14 | **-0.48pp** |
| last-race class SAME, control | +2.27 (z 6.1) | -1.24 | -1.81 | 4.07pp |
| last-race class SAME, **candidate** | -0.21 | -0.13 | +0.51 | **-0.72pp** |
| last-race class DROP, control | +1.52 | +0.87 | -2.51 | 4.03pp |
| last-race class DROP, **candidate** | -0.10 | +1.01 | +0.45 | -0.55pp |
| last-race class RISE, control | -1.97 | -5.12 | -2.18 | 0.22pp |
| last-race class RISE, **candidate** | **-4.86 (z -6.2)** | -3.90 | -0.67 | **-4.19pp** |

* **The gap is closed, slightly over-corrected.** BELOW overall went from
  +1.48 to -0.62pp.
* **The stratum the old feature could not see is fixed completely.**
* **New error in the last-race RISE x window BELOW cell.** These horses fell
  well below their average, then rose partway back. A main-effect feature
  credits the window drop without knowing the last move was up, so they are
  now over-rated -4.86pp.
  **TESTED IN STEP 3 (below), and the interaction hypothesis was WRONG.** The
  cause is not a missing interaction with last-race direction — it is a
  **representation failure** in the model's *existing* class features, which
  Path A did not create and could not have fixed. `class_change_from_last`
  discards every 1-2 point move into its `SAME` category (all 38,707 of them),
  and `class_score_change_from_last` is standardised against a tail where 16%
  of rows exceed 20 points, so a small move reaches the model at about
  0.1 sigma. The model had **no usable representation of a 1-2 point class
  move at all**, and the residual across that band ran +3.8pp to -5.6pp **in
  the control as well as the candidate**. What Path A did was credit those
  horses a second time, turning a pre-existing blind spot into a visible cell.
  See the **Representation Principle** at the top of this file — this is its
  worked example — and Step 3 for the fix, which measured the interaction
  terms at coefficient ranks 193-220 of 250 against rank 10 for the
  representation fix — though one of the two turned out to be load-bearing for
  the target cell despite that rank; see Step 3's trim experiment.

**Gap #10 two-sided slope** (consistent, same-class horses, n 5,564): residual
slope on mean finish **-0.0189/pos (z -5.29) -> -0.0009 (z -0.25)**. Flattened.

**Gap #8 recheck** (claiming/OC droppers, `classify_v2` buckets, net vs
p_fund-matched claiming/OC pool):

| cut | control | candidate |
|---|---|---|
| bucket A | +2.69pp (z 3.9) | +2.20pp (z 3.2) |
| bucket B | +0.30pp | -0.17pp |
| **bucket C** | **+3.60pp (z 4.9)** | **+3.18pp (z 4.3)** |
| droppers, no ITM last 3 | +2.67pp (z 4.3) | +2.13pp (z 3.4) |
| droppers, has recent ITM | +1.36pp (z 3.5) | +0.87pp (z 2.3) |

**Gap #8 is reduced by about 0.4-0.5pp but not fixed.** Its poor-form x drop
interaction needs its own term.

**Coefficients** (standardised, of 239 model columns):
`low_finish_variance` +0.163 (rank 18), `lowvar_x_dropping` -0.105 (30),
`class_direction__DROPPING` +0.095 (33), `class_drop_signed` -0.092 (36),
`lowvar_x_rising` -0.088 (39), `lowvar_same_x_mean_finish` -0.076 (50). For
scale: the old one-race `class_score_change_from_last` is -0.021 (rank 136),
and `field_size` -0.342 (rank 4). The three `__missing` flags come from the 28
rows with NULL class (coefficients about 0.003).

**Live safety**
* `card_picks.py` with `dpv1.pkl` and `pp-reranker-1.0` runs all 9 races of GP
  2026-09-04 from the rebuilt table; models read only their own `fund_cols`.
* sha256 of `dpv1.pkl`, `dpv1_pp_reranker.pkl` and `dpv1_3track.pkl` are
  unchanged.

**Carry into Session 2 (Path B) and the promotion review**
* **The reranker is trained on live 2.0's logit.** If the Path A candidate were
  promoted, `pp-reranker-1.0` would sit on a different base, so it needs
  re-validating on that base.
* **Picks would change a lot.** The candidate changes the top pick in 11.2% of
  races, so the live baseline window (Piece 3, by `model_version`) would
  restart.
* **Open follow-ups:**
  * the last-race RISE x window BELOW over-rating — **taken up as Step 3 below**;
  * ~~the `running_style_last_3` determinism bug~~ — fixed in `d317f76`;
  * Gap #8's residual.

### Gap #11 build — Step 3 (last-race deadband), 2026-09-13

> **RESULT: the -4.86pp step-up-then-return bucket is resolved, and the base
> model improves again on top of Path A.** Against a corpus- and
> feature-matched Path A control:
> * **Target bucket -4.84pp -> -1.13pp (z -1.46)**, no longer distinguishable
>   from zero.
> * **Top-pick ITM +0.30pp** over Path A (264 vs 216, McNemar **p = 0.032**);
>   **+0.73pp over the no-class-context base** (608 vs 492, **p = 0.0005**).
> * **Log-loss improves** z -6.3 vs Path A, z -9.8 vs base, in every
>   class-direction subgroup.
>
> **But the cause was not the hypothesised interaction.** It was a **deadband**.
> And two new problems appeared. See "What this did not fix", below.
>
> **Final candidate: `dpv1_20260913_step3_up.pkl` (`dpv1.5.2-4track-lastdir-up`),
> 3 of the 4 built columns.** The fourth was trimmed after a measured
> experiment; see "Coefficients, and the trim experiment", below.
>
> **Not promoted.** `dpv1.pkl`, `dpv1_pp_reranker.pkl` and `dpv1_3track.pkl`
> are byte-identical to HEAD.

**The diagnosis: a blind spot exactly one to two ladder points wide**

Path A's -4.86pp cell was framed as "a main-effect feature credits the window
drop without knowing the last move was up". That framing is right about the
symptom and wrong about the cause. The cause is that **the model cannot see a
1-2 point class move at all**:

* `class_change_from_last` is categorical with
  `class_change_threshold = 3.0`, so every move of 1 or 2 points is labelled
  `SAME`. Verified on the built table: **all 38,707 rows with |move| in {1,2}
  carry the `SAME` label**.
* `class_score_change_from_last` is a raw signed difference on a ladder where
  **16% of rows move more than 20 points** (tier = 10). The Preprocessor
  standardises without winsorising, so after scaling a 1-2 point move is about
  0.1 sigma. Its fitted coefficient was rank 136 of 239 — the model had
  effectively discarded it.

Residual (y - p_fund) by integer last-race move, Path A fold predictions:

| move | -2 | -1 | 0 | +1 | +2 |
|---|---|---|---|---|---|
| Path A candidate | +2.88 | +1.17 | -0.03 | -4.69 | -5.27 |
| Path A control | +3.82 | +1.97 | -0.20 | -5.14 | -5.57 |

A clean monotone gradient the model treats as one flat category, asymmetric —
small rises hurt about twice as much as small drops help. **It is present in
the control, so Path A did not create it.** What Path A did was credit these
horses twice: `class_drop_signed` resolves fractional class, so a horse that
dropped hard last out and steps back up 1-2 points today still reads BELOW its
window average and is credited for relief it is not getting.

Robustness of the gradient: holds in **all 4 years**, **all 4 tracks**, and
every race type with meaningful n (claiming -6.42, maiden-claiming -6.60,
allowance -4.30, MSW -2.97; stakes ~0). It **also holds where the multi-race
window is missing** (-3.63, z -3.4), which is why the direction terms are
deliberately *not* gated on window context.

**Spec selection (done before training, on the Path A fold predictions)**

Twelve specifications were fitted as corrections on top of the Path A logit as
an offset, and ranked by **leave-one-year-out** gain — fit on three years,
scored on the held-out year:

| spec | LOYO log-loss gain (e-3) |
|---|---|
| **dirs + s x dir slopes + clipped move (chosen)** | **+0.553**, positive all 4 years |
| dirs + hinge magnitudes (+ variants) | +0.48 to +0.52 |
| dirs + clip(move, +/-5) | +0.452 |
| dirs + clip(move, +/-3) | +0.377 |
| Doug's option (b), `return_to_normal` flag | +0.242 |
| clipped move alone, no direction flags | **-0.028** (useless alone) |

Doug's option (c), a signed weight on recent-history depth, was **rejected as
collinear by construction**: `last_race_vs_window` = `class_drop_signed` minus
`class_score_change_from_last` exactly, so as a linear main effect it adds
nothing to a model that already has both. It can only contribute in a
non-linear form.

**What was built** — 4 columns built and measured, **3 shipped**. Config
`dpv1.4.0` -> `dpv1.5.0` (125 active) -> `dpv1.5.1` (123, both interactions
trimmed) -> **`dpv1.5.2`** (**124 active**, final):

| column | definition | final |
|---|---|---|
| `last_class_direction_fine` | UP / SAME / DOWN / NO_LAST at +/-0.5, not 3.0 | **kept** |
| `last_class_move_clipped` | last-race signed move clipped to +/-10, so small moves survive standardisation | **kept** |
| `class_drop_signed_x_last_up` | clip(`class_drop_signed`, +/-10) where the last race was a rise, else 0 | **kept** — carries the target cell |
| `class_drop_signed_x_last_down` | the same for a drop | **trimmed** — no cell, no cost |

`last_class_direction_fine` is registered in
`prepare_training_dpv1.DPV1_CATEGORICAL_FEATURES`; without it the object column
is silently dropped.

**Verification before training**
* **0 band violations** across all four labels; `NO_LAST` is exactly the 38,525
  rows with no prior in-corpus start.
* `last_class_move_clipped` matches `clip(move, -10, 10)` with 0-fill on all
  222,334 non-null rows.
* Interactions are **exactly zero off-regime**; within UP the value equals
  `clip(class_drop_signed, +/-10)`.
* **Determinism confirmed end to end:** the trimmed config was accidentally
  trained twice, and the two runs produced **bit-identical** fold predictions
  (max abs difference 0.0) — an unplanned but real check on the seed pinning.
* **Varies within a race:** 88.7% (move) and 94.5% (direction) of races.

**Three models, not two.** The `a8325cf` Path A pickles were trained on the
pre-fix `running_style_last_3` draw and are no longer comparable to anything
built on the current table, so Step 3 retrained the whole ladder on the fixed
table: base (`dpv1.3.3-4track-ctrl-step3`, 113 active), Path A
(`dpv1.4.1-4track-classctx-step3`, 121), Step 3
(`dpv1.5.0-4track-lastdir`, 125), and after the trim experiment the final
**`dpv1.5.2-4track-lastdir-up`** (124). All seed-pinned `PYTHONHASHSEED=0`,
all through Piece 4 (`--execute --skip-load`), identical corpus (152,865 rows,
20,525 races). **All 120 pre-existing feature columns verified byte-identical**
between the base-config and Step 3-config builds — content hash per column,
no column present in one and not the other.

**Results (fold predictions, 119,535 rows, 15,971 races, rank by `p_fund`)**

| comparison | top-pick ITM | delta | discordant | McNemar p |
|---|---|---|---|---|
| Path A vs base | 64.335 -> 64.761% | +0.426pp | 524 vs 456 | 0.032 |
| **Step 3 vs Path A** | 64.761 -> 65.062% | **+0.301pp** | 264 vs 216 | **0.032** |
| **Step 3 vs base** | 64.335 -> 65.062% | **+0.726pp** | 608 vs 492 | **0.0005** |

Path A rebuilt on the fixed table reproduced its original +0.426pp / p 0.034
almost exactly, so the `running_style` fix did not disturb that conclusion.

**Step 3 vs base, per year:** 2023 +0.27pp (p 0.52), **2024 +0.89pp (p 0.030)**,
2025 +0.71pp (p 0.078), **2026 +1.26pp (p 0.020)**. Win rate +0.57pp
(508 vs 417, p 0.0031). On the 15,561 races shared with the live model's own
8/22 folds: live 2.0 64.090%, base 64.231%, Path A 64.649%, **Step 3 64.957%**.

**Log-loss** (negative = better): vs base **-0.00156 (z -9.82)**; vs Path A
-0.00055 (z -6.32). Better in all four class-direction subgroups against both.

**The target bucket, and the deadband it came from**

| cell | n | Path A control | Step 3 candidate |
|---|---|---|---|
| **last-race RISE x window BELOW (the target)** | 3,145 | **-4.84 (z -6.17)** | **-1.13 (z -1.46)** |
| last-race RISE x window LEVEL | 2,599 | -3.85 (z -4.62) | -0.76 (z -0.92) |
| last-race RISE x window ABOVE | 11,813 | -0.67 | -0.42 |

Residual by integer last-race move, window present:

| move | -2 | -1 | 0 | +1 | +2 |
|---|---|---|---|---|---|
| control | +2.91 | +1.21 | +0.01 | -4.61 | -5.20 |
| **candidate** | **+0.62** | **-1.31** | **-0.05** | **-0.81** | **-1.84** |

By fine direction overall: UP -1.69 (z -6.90) -> **-0.42**; DOWN +0.69
(z +2.94) -> -0.37.

**Coefficients, and the trim experiment that corrected their reading**

In the 4-column build: `last_class_direction_fine__UP` **-0.2248 (rank 10 of
250)**, `__DOWN` +0.1781 (rank 16), `last_class_move_clipped` +0.0365 (rank
101), while `class_drop_signed_x_last_up` sat at rank 197 and
`class_drop_signed_x_last_down` at rank 220. The first reading was that the
fix is the deadband level shift and **both** interactions were unearned.

**That reading was half wrong, and the trim proved it.** Three builds:

| build | cols | top-pick ITM vs base | target cell |
|---|---|---|---|
| 4-column (`dpv1.5.0`) | dirs + move + both interactions | +0.726pp (p 0.0005) | **-1.13pp (z -1.46)** |
| trimmed (`dpv1.5.1`) | dirs + move only | +0.720pp (p 0.0006) | **-1.84pp (z -2.36)** |
| **final (`dpv1.5.2`)** | **dirs + move + `_x_last_up`** | **+0.726pp (p 0.0005)** | **-1.13pp (z -1.46)** |

Dropping both interactions left the **headline untouched** (+0.720 vs +0.726pp)
but **gave back 0.7pp on the target cell**, pushing it back over significance.
Restoring `_x_last_up` alone recovered the target cell exactly, at the same
headline, with `_down` gone for good.

**The lesson, now recorded as a corollary to the Representation Principle:**
coefficient rank measures a term's *average* contribution, and is not evidence
it is idle in the cell it was built for. `_x_last_up` ranks 193 of 248 in the
final build and is still load-bearing for its 3,145-row cell, because that is
exactly where `class_drop_signed` is large and negative. `_down` had no such
cell, and dropping it cost nothing on every measure.

For scale in the final build, `class_score_change_from_last` is -0.0296
(rank 115) and `field_size` -0.3444 (rank 4).

**What this did not fix, and what it broke**

* **Over-correction on the mirror cell.** Small last-race DROP x window far
  below (`move -3..-1` x `s -3..-1`, n 2,358) goes **+0.00pp -> -2.10pp
  (z -2.28)** in the final build (-2.05 in the 4-column, -2.11 trimmed — the
  interaction columns do not touch it). The DOWN-side level term over-fires. This is the same shape of
  error Step 3 was created to fix, with the sign flipped.
* **Gap #8 moved the wrong way.** Every dropper cut is now *below* control:
  bucket A +2.16 -> +0.96, **bucket C +3.20 -> +2.08**, droppers with no ITM in
  last 3 +2.15 -> +1.05, and **bucket B -0.20 -> -1.21 (z -2.65)**, newly
  over-rated. Gap #8's under-rating is being absorbed by a class term that is
  not Gap #8's poor-form x drop interaction, and bucket B overshoots as a
  result. Gap #8 still needs its own term; it is now partly masked.
* **Gap #10's slope was already flat** in the Path A control (-0.0014, z -0.39)
  and stays flat (-0.0009). Step 3 neither helps nor hurts it.
* Persistent, untouched by Step 3: `move <=-10 x s>3` -4.64pp (n 309) and
  `move 3..9 x s>3` -3.29pp (n 1,661) — large moves in one direction with the
  window in the other. Both were already there in the control.

**Still not a pre-registered test.** The deadband was found by inspecting
residuals on the same fold predictions the comparison is scored on. Spec
selection used LOYO, which is honest about *year* but not about *design* — the
design saw all four years. **Confirmation needs races after 2026-09-13.** The
promotion gate is unchanged: a pre-registered live evaluation over 100-200
races before any promotion.

**Live safety**
* `card_picks.py` runs all 9 races of GP 2026-09-04 under `dpv1.2.0-4track`
  with `pp-reranker-1.0` from the rebuilt table.
* `dpv1.pkl`, `dpv1_pp_reranker.pkl`, `dpv1_3track.pkl` byte-identical to HEAD.
* DB backed up as `scripts/racing_full.db.pre-step3.bak` before the rebuild.
* Artifacts on disk (all protected from `prune_models` by their non-numeric
  suffixes): `dpv1_20260913_step3_base.pkl`, `_patha.pkl`, `_cand.pkl`
  (4-column), `_trim.pkl` (both interactions removed), `_up.pkl` (**final**),
  each with a matching `dpv1_fold_predictions_20260913_step3_*.csv` left
  untracked on disk.

**Carry into Step 4**
* ~~Decide the two unearned interaction columns~~ — resolved 2026-09-13:
  `_x_last_down` trimmed, `_x_last_up` kept. See the trim experiment above.
* The mirror-cell over-correction and bucket B are the next two errors in line.
* Gap #8's interaction is now **partly masked** by the class terms — measure it
  against the Step 3 control, never against the old live-2.0 folds.
* Promotion still restarts the live baseline window and needs the reranker
  re-validated on the new base.

### Gap #11 build — Path B (reranker architecture), Step 4 Track 1, 2026-09-13

> **RESULT: the class-context signal is fully captureable in the reranker
> architecture, and the two routes are the SAME signal — not complements.**
>
> On the identical 15,561 races with identical entry sets, against the live
> `dpv1.2.0-4track` base:
>
> | | top-pick ITM | vs base | McNemar p |
> |---|---|---|---|
> | live `dpv1.2.0-4track` | 64.090% | — | — |
> | **Path B reranker** | **64.977%** | **+0.887pp** | **<0.0001** |
> | Path A `dpv1.5.2` | 64.944% | +0.855pp | 0.0001 |
> | **Path B vs Path A** | — | **+0.032pp** | **0.865** |
>
> **Indistinguishable.** 278 races where Path B hits and Path A misses against
> 273 the other way.
>
> **Stacking them adds nothing.** A class-context reranker fitted over the
> Path A base finds nothing left to correct: **-0.039pp (127 vs 133, p 0.757)**
> and log-loss very slightly *worse* (+0.00010, z +2.09). **So "ship both"
> would double-count a single correction. This is an either/or.**
>
> **Not promoted, nothing shipped.** `dpv1.pkl`, `dpv1_pp_reranker.pkl` and
> `dpv1_3track.pkl` are byte-identical to HEAD.

**What was built**

`dpv1_classctx_reranker_train.py`, deliberately mirroring
`dpv1_pp_reranker_train.py` — same `PPReranker`-shaped dataclass, the same
`fit_offset_logistic` L-BFGS offset fit (lifted with its warning that adding
an offset at prediction time is not an offset model), the same GroupKFold-by-race
cross-validation, the same `__main__` unpickling shim. Artifact
`dpv1_classctx_reranker.pkl`, version `classctx-reranker-0.1`, **offset mode**
to match `pp-reranker-1.0`.

Feature block: the 11 shipped Step 3 columns (config `dpv1.5.2`), one-hot on
the two categoricals with `SAME` as the dropped reference level, median
imputation stored on the artifact so a live card cannot silently use a
different fill.

**One structural difference from the PP reranker, stated because it changes
how to read the result.** The PP reranker exists because PP data joins to only
0.86% of the corpus; it adjusts a small, well-defined subpopulation. Class
context is present for almost every row, so this is a correction applied to the
whole field — much closer to "refit the model" than the PP case, and a weaker
device than Path A only in that the base's 95 coefficients stay frozen. The
finding is that freezing them costs nothing.

**Method**

* Base contribution is the base model's **out-of-sample** fold prediction
  (`dpv1_fold_predictions.csv`, written with `dpv1.pkl` on 2026-08-22),
  never a refit on rows it trained on.
* Reranker cross-validated by **race group** (5-fold) *and* **leave-one-year-out**.
  LOYO is reported because GroupKFold shuffles races across time and LOYO does
  not; it is the discipline Step 3 was held to. **The two agree closely**, so
  nothing here rests on the weaker scheme.
* Head-to-head restricted to races whose **full entry set** appears in both
  corpora, so the top-pick comparison is like for like.

| CV scheme | mode | top-pick ITM | delta | McNemar p | log-loss delta (z) |
|---|---|---|---|---|---|
| by race | offset | 64.912% | +0.823pp | 0.0001 | -0.00138 (-9.13) |
| by race | free | 64.970% | +0.880pp | <0.0001 | -0.00146 (-9.38) |
| by year | offset | 64.919% | +0.829pp | 0.0001 | -0.00137 (-9.09) |
| **by year** | **free** | **64.977%** | **+0.887pp** | **<0.0001** | **-0.00140 (-9.03)** |

**The free base coefficient is +0.9593** — near unit weight. That is the
reassuring answer to the question the PP reranker's docstring raises: a
whole-field reranker *could* have degenerated into recalibrating every horse,
and a coefficient materially below 1 would have said so. It did not; `offset`
(which forces exactly 1.0) gives nearly identical coefficients and gives up
only 0.06pp, which is why the shipped artifact is `offset`.

**Per year, vs base** (both routes positive in all four years):

| year | races | Path B | Path A |
|---|---|---|---|
| 2023 | 4,498 | +0.38pp (p 0.34) | +0.33pp (p 0.43) |
| 2024 | 4,392 | **+1.41pp (p 0.001)** | **+1.25pp (p 0.002)** |
| 2025 | 4,389 | +0.62pp (p 0.13) | +0.84pp (p 0.039) |
| 2026 | 2,282 | **+1.40pp (p 0.020)** | +1.14pp (p 0.064) |

**Class-direction residuals flatten the same way** (base -> Path B):
BELOW +1.60 -> **-0.03**, LEVEL -1.36 -> **+0.04**, ABOVE -2.01 -> **-0.03**.

**The deadband gradient closes the same way** (base -> Path B): move -2
+3.67 -> +1.19, -1 +2.30 -> -0.57, 0 -0.37 -> -0.01, **+1 -4.93 -> -0.27**,
**+2 -4.75 -> -0.81**.

**Gap #8 recheck** (claiming/OC droppers, `classify_v2`, net of a
p-matched pool):

| cut | n | base | Path B | Path A |
|---|---|---|---|---|
| bucket A | 4,333 | +2.73 (z 3.9) | +0.98 (z 1.4) | +1.02 (z 1.5) |
| bucket B | 9,041 | +0.29 | **-1.35 (z -3.0)** | **-1.19 (z -2.6)** |
| bucket C | 3,775 | +3.61 (z 4.9) | +1.61 (z 2.2) | +2.11 (z 2.8) |
| droppers, no ITM last 3 | 5,182 | +2.68 (z 4.3) | +0.59 | +1.07 |
| droppers, has recent ITM | 11,967 | +1.37 (z 3.5) | -0.42 | -0.36 |

Path B absorbs slightly more of Gap #8's under-rating than Path A (C +1.61 vs
+2.11) and **overshoots bucket B slightly harder** (-1.35 vs -1.19). **Both
routes carry the same bucket-B defect**, which is further evidence they are one
signal. Gap #8 still needs its own poor-form x drop term either way, and must
be measured against whichever route is chosen, never against the old live-2.0
folds.

**Miscalibration scan.** Broadly the same cells as Path A, with the same
mirror-cell residue (`L -3..-1 x s -3..-1`: base +1.33, Path B -1.71, Path A
-2.17 — Path B slightly gentler). One cell where Path B is worse than base and
worse than Path A: `L>=10 x s>3`, base +0.06 -> **Path B +1.06 (z +2.24)**,
Path A +0.63 (n 7,020).

**What this means for the ship decision**

* **The signal is architecture-independent.** It is an additive correction that
  does not need the base model's other 95 coefficients refitted jointly. That
  was the open question Path B was built to answer.
* **They are substitutes, not complements** — the stacking test settles it.
* **Operationally the two routes are very different**, and that, not the point
  estimate, is the real basis for choosing:

| | Path A (`dpv1.5.2`) | Path B (`classctx-reranker-0.1`) |
|---|---|---|
| touches `dpv1.pkl` | **yes, base swap** | no |
| live baseline window | **restarts** (Piece 3 filters by `model_version`) | preserved |
| `pp-reranker-1.0` | **needs re-validating on a new base** | unaffected base, but two rerankers now compose over one logit — untested |
| reversibility | redeploy the old pickle | drop one artifact |
| where the signal lives | 124-feature config, one model | base + a 15-coefficient correction |

* **The unexamined risk in Path B is reranker composition.** `pp-reranker-1.0`
  and this one would both adjust the same base logit, on overlapping rows.
  Nothing here tested how they compose. Path A has the mirror-image problem
  (the PP reranker would sit on a base it was not fitted against). **Either
  route requires a reranker-interaction test before shipping; neither has one.**

**Still not pre-registered.** Path B uses the same feature block designed on
these same years in Steps 1-3. Its fold structure is honest for the *reranker*,
but the *design* saw all four years. Confirmation needs races after
2026-09-13 — the same gate as Path A, which is what Track 2 exists to collect.

### Reranker composition test — Step 4 Session 1, 2026-09-13

> **VERDICT: no interference. The two rerankers do orthogonal work and their
> effects are additive. But this test cannot settle a ranking question — 220
> races is far too few — and it should not be used to justify shipping.**

**Configurations**, shipped artifacts unmodified, replicating the live
application path (`card_picks.rerank_probabilities`): the PP reranker fires
only on horses with a PP row; the class-context reranker fires on the whole
field.

| config | definition | top-pick ITM (220 races) |
|---|---|---|
| **X** | base `dpv1.pkl` alone | 66.364% |
| **Y** | base + `pp-reranker-1.0` (shipped state) | 68.182% |
| **Z** | base + `pp-reranker-1.0` + `classctx-reranker-0.1` | 69.545% |
| **W** | base + `classctx-reranker-0.1` only | **70.455%** |

| comparison | delta | discordant | McNemar p |
|---|---|---|---|
| Y vs X (pp alone) | +1.818pp | 10 vs 6 | 0.45 |
| Z vs X (both) | +3.182pp | 14 vs 7 | 0.19 |
| **Z vs Y (adding classctx)** | **+1.364pp** | 10 vs 7 | **0.63** |
| W vs X (classctx alone) | +4.091pp | 12 vs 3 | **0.035** |
| Z vs W (adding pp) | -0.909pp | 8 vs 10 | 0.81 |

**The evidence for clean composition is the log-loss decomposition, not the
ranking table.** Adding the two corrections in either order gives the same
total, to five decimals:

| path | step | cumulative |
|---|---|---|
| X -> Y (pp) | -0.00521 (z -2.49) | |
| Y -> Z (classctx) | -0.00141 (z -0.93) | **-0.00662** |
| X -> W (classctx) | -0.00168 (z -1.12) | |
| W -> Z (pp) | -0.00493 (z -2.37) | **-0.00661** |

There is no interaction term. Corroborating it directly: the per-horse logit
adjustments the two rerankers make are **uncorrelated — r = +0.059**, and they
agree in sign on 49.1% of rows, which is chance. They are adjusting different
things about the same horses.

**They contribute on different axes.** The PP reranker carries the calibration
gain (z -2.49 as the first step, z -2.37 as the second); the class-context
reranker carries the ranking gain (the only nominally significant ranking
result in the table is W vs X). That is consistent with what each was built
for, and it is why Z beats Y on ranking while W beats Z.

**Why this test cannot decide the ship question**

* **220 races.** Every comparison rests on 13-21 discordant races. Z vs Y's
  +1.364pp meets the pre-stated +0.5pp bar on the point estimate and is
  meaningless at p = 0.63. One nominal significance out of five comparisons is
  what chance produces.
* **Config Y is in-sample.** `pp-reranker-1.0` was trained on exactly these
  rows, so Y is flattered and the Y-baseline is too high. The classctx
  reranker is effectively out-of-sample here (15 coefficients fitted on
  116,665 rows, of which these are 1.4%), so the asymmetry runs against
  classctx, not for it.
* **These are not disjoint subpopulations.** PP coverage inside these races is
  **99.9%** — 1,582 of 1,584 runners. So both rerankers act on essentially the
  whole field, and the composition question here is "two whole-field
  corrections", not "two corrections on different horses". On a live card with
  a PP file this is the realistic case.
* **`W > Z` is unresolved.** On these races, dropping the PP reranker ranks
  better than keeping it. It is not significant, it contradicts the log-loss
  reading, and 220 races cannot separate the two. It is a reason to carry
  config W into live testing, not a reason to act now.

**Flagged, out of scope, needs its own look: the PP reranker's applicable
population has shrunk.** *(**CORRECTED 2026-09-13 — this paragraph is wrong.
The population did not shrink; the comparison below is between a de-duplicated
count and a duplicate-inflated published figure. See the join-drop
investigation at the end of this file.** Left in place so the correction is
traceable.)* `pp_entries_raw` now joins to **1,969** corpus entries
across 29 cards, up from ingestion; but only **1,582** have an out-of-sample
base logit, against **1,910 rows / 259 races** when `pp-reranker-1.0` was
evaluated on 2026-09-01. 387 rows are simply after the base fold cutoff
(2026-08-21) and are expected. **That still leaves roughly 330 historical rows
that previously joined and now do not.** Candidate causes: the 2026-09-02
`parse_pp_files --incremental` change to card-grain replace, the GP 9/4
purge-and-reload, or the CT backlog loads altering `program_num` formatting.
Not diagnosed here. It does not affect this test's internal validity — every
config is scored on the same 1,582 rows — but it bears on how often
`pp-reranker-1.0` actually fires live, and should be checked before any
shipping decision that depends on it.

**Conclusion.** The composition risk raised in the Path B entry is **not
realised**: no interference, no degradation of the PP-covered subset
(residual +0.48 -> +0.27 -> +0.57pp across X/Y/Z), additive log-loss,
orthogonal adjustments. That removes the blocker. It does **not** establish
that Z is better than Y, or that Z is better than W. Those are ranking
questions at a sample size that cannot answer them, and the instrument for
them is Track 2's live parallel picks.

### PP join-drop investigation — Step 4 Session A, 2026-09-13

> **RESOLVED: there is no join drop, and nothing is broken. The applicable
> population is 1,582 unique entries / 220 races, and it is IDENTICAL before
> and after the period in question.** The apparent loss was my own measurement
> error: I compared a de-duplicated current count against a published figure
> that had been inflated by duplicate rows.
>
> **But the investigation turned up a real finding underneath it:
> `pp-reranker-1.0` was trained and evaluated on a dataset containing ~299
> duplicate rows (~16%), with 75 entries counted more than once and one entry
> appearing 6 times.** See "What this means for Gap #1", below.

**What was measured**

The `load_dataset` join (`pp_entries_raw` -> `entries` -> base fold
predictions) was replayed against every surviving database backup. The fold
file is fixed on disk (written with `dpv1.pkl`, 2026-08-22), so it is a
constant across all of them.

| backup | mtime (UTC) | pp rows | join rows | join rows in folds |
|---|---|---|---|---|
| `pre6b` | 08-22 01:20 | 4,217 | 1,881 | 1,881 |
| `pre6e` | 08-29 18:26 | 4,318 | 1,982 | 1,881 |
| `pre-backlog` | 08-29 18:41 | 4,318 | 1,966 | 1,881 |
| `pre0829` | 08-31 13:18 | 4,318 | 1,966 | 1,881 |
| `pre-retrain` | 08-31 19:10 | 4,318 | 1,966 | 1,881 |
| `pre-gap6` | 08-31 19:23 | 4,318 | 1,966 | 1,881 |
| `pre-ppingest` | 09-01 18:15 | 4,318 | 1,966 | **1,881** |
| `pre-gp0904` | 09-04 00:04 | 4,330 | 1,974 | **1,582** |
| `pre-classctx` .. current | 09-12 .. 09-13 | 4,330 | 1,969 | 1,582 |

The drop sits between 09-01 and 09-04 — and note `pp_entries_raw` **grew**
(4,318 -> 4,330) while the joined count did not fall. That is the shape of a
de-duplication, not a data loss.

**The cause, confirmed directly**

| database | rows | distinct `(track, race_date, race_num, program_num)` | duplicated keys | excess rows |
|---|---|---|---|---|
| `pre-ppingest` (09-01) | 4,318 | 3,978 | **85** | **340** |
| `pre-gp0904` (09-03) | 4,330 | 4,330 | 0 | 0 |
| current | 4,330 | 4,330 | 0 | 0 |

The pre-fix table held up to **6 copies** of the same horse in the same race
(GP 2026-05-09 race 1 had 6 copies of every program number). The
**2026-09-02 `parse_pp_files.py parse --incremental` change** — each parsed
card replaces only its own rows, instead of the table being dropped and
re-accumulated — is what removed them. It is the culprit only in the sense
that it is the **fix**; the duplicates predate it.

**Counting unique entries rather than join rows, the population is unchanged:**

| | join rows (with duplicates) | in folds | **unique entries** | **races** |
|---|---|---|---|---|
| before (09-01) | 1,966 | 1,881 | **1,582** | **220** |
| now | 1,969 | 1,582 | **1,582** | **220** |

Set difference of joined-and-in-folds entry ids between the two: **0 lost**.

**The three candidate causes, resolved**

* **`parse_pp_files --incremental` change — implicated, as the fix.** No action
  needed; the table is clean and the mechanism that accumulated duplicates is
  gone.
* **GP 9/4 purge-and-reload — not implicated.** No entry ids were lost; the
  card postdates the fold cutoff and never contributed.
* **CT backlog loads altering `program_num` — not implicated.** The unique
  join is byte-identical before and after.

**No data migration and no code fix are required.** A `UNIQUE` constraint on
`(track, race_date, race_num, program_num)` would be the obvious guard and is
**still the wrong move**, for the reason already recorded against the
incremental fix: the parser has legitimately emitted two different horses on
the same program number in one race, so the constraint would reject real data.
Card-grain replace is the correct mechanism and it is already in place.

**What this means for Gap #1**

`pp-reranker-1.0`'s published evaluation — **+3.9pp top-pick ITM over 259
races, p = 0.064** — was computed on the pre-fix table. Reconstructed from the
closest surviving backup, that dataset carried **1,881 rows for 1,582 unique
entries: 299 duplicate copies, 75 entries duplicated, one entry six times.**
Consequences, stated precisely:

* **No fold leakage.** Cross-validation is `GroupKFold` by `race_id`, and
  duplicates of an entry are by construction in the same race, hence the same
  fold. Duplicated rows never crossed the train/validation boundary.
* **The fit is weighted oddly.** Races with duplicated rows carried up to 6x
  their proper weight in the likelihood, so the shipped coefficients are
  tilted toward those races.
* **The reported sample size is overstated.** "259 races" cannot be reproduced
  from any surviving backup; the closest reconstruction is **220**. Part of the
  gap is duplicates and part is a PP-table state no backup captured. Either
  way, `n` and therefore `p = 0.064` were computed on non-independent rows.

**Recommended, not done:** re-run `dpv1_pp_reranker_train.py evaluate` against
the clean table to get an honest number for Gap #1. That is an evaluation, not
a retrain, and it does not touch the shipped artifact. Whether to refit
`pp-reranker-1.0` on de-duplicated data is a separate decision, and it would
restart that artifact's own validation.

**Correction to the record.** The "applicable population has shrunk by ~330
rows" note in the Step 4 Session 1 entry above is **wrong** and is retained
only so the correction is traceable. The population did not shrink; the
comparison was between a de-duplicated count and a duplicate-inflated one.
