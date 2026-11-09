# Incremental feature build, stage 7b-1 (closure recompute), 2026-11-08

**Status: built, proof tests partly done, stopped at Doug's request.** Not
wired into the nightly flow; `feature_builder_dpv1.py build` is still the
build of record. The running-totals stage (7b-2) is not started.

Code: `scripts_dpv1/feature_incremental.py` (`update`, `plan`, `full`).
Harness and per-test diff JSONs: `tracking/incremental_build_2026-11-08/`.
All tests ran on scratch copies (deleted). The live DB was never written
(mtime checked after every step).

## What it does

1. **Seeds.** At each full build the inputs are fingerprinted: one hash per
   entry over every raw column `load_raw` and `stretch_run` read, plus a
   separate hash over horse attributes. `update` finds new, removed and
   changed entries by fingerprint diff.
2. **Propagate.** It marks every row dated **on or after** a seed that
   shares a horse, jockey, trainer or track with it, then their whole races,
   and repeats until nothing is added. Sire, dam and damsire count only when
   a pedigree or attribute feature is active; none is in 1.3.2.
3. **Closure.** For each dirty row it collects the rows it reads: earlier and
   same-day rows of its jockey and trainer, plus *those rows' horses' earlier
   entries*, and earlier and same-day whole races of its horse and track.
4. **Compute.** It runs the unchanged `build_features` on an in-memory copy
   of the closure and upserts only the dirty rows.
5. **Fallback.** It runs a full build (and says why) when there is no
   recorded state, the code, config or library versions changed, the table
   doesn't match the record, an attribute changed while an attribute feature
   is active, or the closure is over 60% of the corpus.

## Live code changed with it (on every full build)

* **Fixed column types:** `dpv1_feature_schema.json` +
  `feature_builder_dpv1.write_table`.
  * Previously pandas chose each column's SQL type from that night's rows. A
    loaded card flipped `weight_lbs` from INTEGER to REAL, and the chart
    flipped it back. The live table is REAL right now.
  * The schema holds the types of a no-card build (132 columns; only
    `weight_lbs` differs from live today).
  * Values unchanged. Proof: DED 11/07 rebuilt from `.ded1107-run.bak` with
    the schema; `card_picks` reproduces the 87 logged rows of the 09:54 record
    run exactly.
* **Recording:** `feature_builder_dpv1.py build` now also writes
  `feature_input_hashes` and `feature_build_log`. Best-effort, about 9 s.

## Proof tests

The base is `.ded1104-run.bak` with pars frozen on the copy (`proof-1104`)
and a full build. After every step, A (incremental) was compared with a fresh
full build of the same state (B): same ids, every cell of 131 columns, the
SQLite type of every cell, and a table hash.

| test | seeds (new / removed / changed / attr) | dirty | closure | update s | result |
|---|---|---|---|---|---|
| determinism: two full builds | - | - | - | - | identical, same hash |
| 11/04 card | 77 / 0 / 0 / 0 | 77 | 71,599 | 42 | identical; card_picks 77/77 |
| 11/04 chart (purge + reload) | 69 / 77 / 0 / 22 | 69 | 80,269 | 49 | identical |
| 11/05 card | 69 / 0 / 0 / 0 | 69 | 77,960 | 48 | identical; card_picks 69/69 |
| 11/05 chart | 61 / 69 / 0 / 13 | 61 | 77,288 | 45 | identical |
| 11/06 card | 89 / 0 / 0 / 0 | 89 | 82,090 | 50 | identical; card_picks 89/89 |
| 11/06 chart | 77 / 89 / 0 / 0 | 77 | 80,741 | 46 | identical |
| 11/07 card | 87 / 0 / 0 / 0 | 87 | 79,591 | 50 | identical; card_picks 87/87 |
| scratch a card entry | 0 / 1 / 0 / 0 | 11 | 58,912 | 39 | identical; card_picks 86/86 |
| add an also-eligible | 1 / 0 / 0 / 0 | 12 | 60,024 | 38 | identical; card_picks 87/87 |
| 11/07 chart | 75 / 87 / 0 / 3 | 75 | 77,422 | 45 | identical |
| remove an old day (DED 10/24) | 0 / 71 / 0 / 0 | 580 | 90,415 | 51 | identical |
| backfill it (DED 10/24 chart) | 71 / 0 / 0 / 0 | 651 | 91,503 | 51 | identical |
| backfill MNR 08/02 (3 months back) | 55 / 0 / 0 / 1 | 6,020 | 319,340 | - | falls back to full (by design) |
| DQ flip (DED 10/16 R5, 1st/2nd) | 0 / 0 / 2 / 0 | 948 | 92,363 | 51 | **2 cells differed**, fixed, see below |
| DQ flip again, after the fix | 0 / 0 / 2 / 0 | 1,020 | 92,706 | 52 | identical |
| merge jockey with rides from 2021 | - | - | 320,424 | - | falls back to full |
| merge jockey 948 (18 rides from 10/09) into 887 | 0 / 0 / 18 / 0 | 1,324 | 94,869 | 53 | identical |

A full build takes about 160 s, so a normal card or chart step is about
45-50 s instead (closure about 25% of the corpus).

### Found and fixed along the way

1. **Hashes depended on pandas' inferred dtypes.** A card's NULL finish
   positions turned integer columns into float and changed every row's hash.
   Now a type-stable per-value hash.
2. **Trainer situation stats.** These are win % dropping in class, rising,
   off a layoff, and with first-time starters. They read the past row's
   horse's previous race and career count. The closure now includes those
   horses' earlier entries. Before the fix, 23 cells differed on the 11/04
   card.
3. **Chart pedigree fill-ins.** A chart load fills in pedigree and attributes
   for some horses (22 on 11/04), which changes their older entries. These
   are hashed separately and reach no feature in 1.3.2.
4. **Same-day dependence.** The DQ flip changed `days_since_jockey_last_win`
   and `days_since_trainer_last_win` in later races *that same day*.
   Propagation and closure now include same-day rows.

### Same-day behaviour of `days_since_*_last_win` (not changed)

`scripts/feature_builder.py::_prior_days_to_event` walks a jockey's or
trainer's rows in (date, entry_id) order. A win in an earlier race the same
day sets "last win date" to today, so later same-day rows get NULL instead of
the days since the previous win. Training rows therefore see same-day results
(a mild leak, NULL when the jockey or trainer won earlier that card). Live card
rows never do, because the card has no results. No change made (no model or
feature changes today). For review.

## Not done (where it stopped)

* **Final-code rerun of the replay.** The four card and four chart steps,
  the scratch and the also-eligible ran *before* fix 4 (same-day rows). Fix 4
  only adds rows to the dirty set and closure. Only the DQ flip and the
  jockey merge ran on the final code. The replay should be rerun once on the
  final code (about 45 min).
* **Adversarial tests not yet run:**
  * change a horse's sire or foaled date (expected: no dirty rows in 1.3.2);
  * hand relabel of an old race's `race_type`;
  * purge and reload an old day in one step;
  * config change (expected: full build).
* **Plan items after these:**
  * prediction check on more logged cards;
  * the 2-week shadow period;
  * a decision on wiring it into the nightly flow.
* **Possible refinement:** a row brought in only because it shares a race
  with a changed horse is propagated along every key, track included. That
  is why the 3-month-back MNR backfill reached 6,020 rows and fell back.
  Narrowing it needs a careful read of which past-race values later rows
  use.
