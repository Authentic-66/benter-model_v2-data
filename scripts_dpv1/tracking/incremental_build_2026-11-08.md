# Incremental feature build, stage 7b-1 (closure recompute), 2026-11-08

**Status (2026-11-09): first-stage proofs done on the final code, all
identical. Stopped for Doug's review.** It is not wired into the nightly
flow; `feature_builder_dpv1.py build` is still the build of record. The
running-totals stage (7b-2) is not started. Final-code results are in
"Final-code rerun (2026-11-09)" below; the proposal for the next step is in
"Proposal: side-by-side period".

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

The table below is the 2026-11-08 run. Its card, chart, scratch and
also-eligible rows ran before fix 4. They were rerun on the final code on
2026-11-09 (section "Final-code rerun"), and the `cmp_*.json` files in the
harness folder now hold those results; the 11/08 files are in git history
(ef9e7a4).

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
trainer's rows in (date, entry_id) order. A win earlier the same day sets
"last win date" to today, so later same-day rows get NULL instead of the days
since the previous win. Live card rows never see this, because a card has no
results. **The 2026-11-09 audit showed this is not mild.**
* 19% (jockey) and 8% (trainer) of training rows are affected.
* 2,690 trainer rows read a stablemate's win **in the same race**.

See `tracking/same_day_audit_2026-11-09.md`. It is now 1.4 candidate item 5.
If it ships, these two features no longer need same-day rows in propagation
and closure. Keep them in until then.

## Final-code rerun (2026-11-09)

The same base and method as above, on the final code (ef9e7a4 plus the
harness changes). Driver: `run_all.sh` (set `REPLAY_DIR` to a scratch
folder). Log: `run_all_2026-11-09.log`. The live DB was never written: its
mtime is still 2026-11-08 17:18, and the harness checks it after every step.

| step | seeds (new / removed / changed / attr) | dirty | closure | update s | vs full build | card_picks A vs B |
|---|---|---|---|---|---|---|
| determinism: two full builds | - | - | - | - | identical, same hash | - |
| 11/04 card | 77 / 0 / 0 / 0 | 77 | 71,599 | 49 | identical | 77/77, 0 diffs |
| 11/04 chart (purge + reload) | 69 / 77 / 0 / 22 | 69 | 80,269 | 46 | identical | - |
| 11/05 card | 69 / 0 / 0 / 0 | 69 | 77,960 | 49 | identical | 69/69, 0 diffs |
| 11/05 chart | 61 / 69 / 0 / 13 | 61 | 77,288 | 44 | identical | - |
| 11/06 card | 89 / 0 / 0 / 0 | 89 | 82,090 | 51 | identical | 89/89, 0 diffs |
| 11/06 chart | 77 / 89 / 0 / 0 | 77 | 80,741 | 48 | identical | - |
| 11/07 card | 87 / 0 / 0 / 0 | 87 | 79,591 | 49 | identical | 87/87, 0 diffs |
| scratch a card entry (R5, highest program no.) | 0 / 1 / 0 / 0 | 86 | 79,512 | 45 | identical | 86/86, 0 diffs |
| add it back (also-eligible) | 1 / 0 / 0 / 0 | 87 | 79,591 | 45 | identical | 87/87, 0 diffs |
| 11/07 chart | 75 / 87 / 0 / 3 | 75 | 77,422 | 45 | identical | - |
| **new:** sire and foaled date of horse 45871 (9 starts) | 0 / 0 / 0 / 9 | **0** | 0 | 14 | identical | - |
| **new:** relabel DED 10/10 R5 CLAIMING -> STARTERALLOWANCE | 0 / 0 / 10 / 0 | 1,243 | 93,304 | 55 | identical | - |
| **new:** purge + reload DED 10/24 in one step (chart over itself) | 71 / 71 / 0 / 0 | 651 | 91,503 | 52 | identical | - |
| **new:** config change (copy with one added key) | - | - | - | 160 (full) | identical | - |

"Identical" means:
* the same 131 columns and the same entry ids;
* 0 differing cells and 0 SQLite type differences;
* the same table hash.

Edits are made by `adv_edit.py`.

Notes:
* **Scratch and also-eligible: the dirty set changed.** The scratch now
  dirties 86 rows and the also-eligible 87 (on 11/08: 11 and 12). This comes
  from fix 4: the whole card shares the day with the changed entry, through
  jockey and trainer keys. Still identical.
* **Sire / foaled date: as expected.** Nothing in 1.3.2 reads horse
  attributes, so the change is counted as attribute-only, nothing is
  recomputed, and the table still matches a full build. With an attribute
  feature active, `plan` would fall back to a full build.
* **Config change.**
  * `update --no-fallback` refused: "feature code, config or library
    versions changed since the last recorded build".
  * `update` then ran a full build and recorded the reason in
    `feature_build_log`.
  * The result matches a full build made with the same config.
* **Not covered by any replay so far:** the real 11/05 EVD/LAD 44-chart
  backfill and the real 11/06 hand relabel (plan section 2, step 2). The
  relabel is covered in kind by the test above. A 44-chart backfill is a
  bigger seed set than anything tested; it may fall back to a full build,
  which is the safe outcome.

**First-stage proofs (plan steps 1-3) are complete.** Every replay step and
every adversarial edit in the plan has matched a full rebuild, cell for cell.
Step 4 (prediction check) has 4 logged cards (11/04-11/07) plus the
scratch / also-eligible variants, all 0 diffs.

## Proposal: side-by-side period (plan step 5; not started, for Doug)

The full build stays the build of record throughout. Nothing the model
scores comes from the incremental table.

1. **Setup (one session). One code change is needed first.**
   * The input fingerprint (`feature_input_hashes`) is one table per DB, and
     every full build replaces it (`record_full_build`). A side table in the
     live DB would therefore lose its state each night: the live full build
     records the new inputs, and the side table's next `update` would see no
     change.
   * Fix: key the fingerprint by feature table (add `table_name`, as
     `feature_build_log` already has). This is a recording change only; it
     does not change any feature value. Test it with a rerun of this replay.
   * Then add the side copy, `feature_incremental.py update --table
     entry_features_dpv1_inc` (the `--table` option exists).
   * Seed the side table once with a full build into that table.
   * Pars stay frozen (`pars-v1-20261108`). Any par refreeze or config
     change resets the side table with a full build, logged as such.
2. **Each card night**, in the existing order.
   * After the live full build, run `update` on the side table.
   * Compare the two tables cell for cell: `table_diff.py`, every column,
     types, and hash.
   * Run `card_picks` from both, to scratch for the side copy, and compare
     P(ITM) per horse.
   * Do the same after each chart load.
   * Append one line per step to `tracking/incremental_side_by_side.csv`:
     date, step, seeds, dirty, closure, seconds, differing cells, hash
     equal, picks diffs.
   * Cost: about 1 min per step, plus the compare.
3. **Pass rule (set before starting).** 14 consecutive card nights, each with
   0 differing cells, the same hash and 0 pick diffs, after both the card
   and the chart step.
   * Any difference stops the clock. Investigate it, fix it, and restart the
     count at 0.
   * Fallbacks to a full build are allowed and counted, but they don't count
     as incremental passes.
4. **Real backfills during the period.** Next is the MNR 10/05 retry after
   11/21; any EVD/LAD batches go through the side table too. This covers
   the backfill case the replay did not.
5. **After a pass.** Doug decides whether incremental becomes the build of
   record. If it does:
   * keep a weekly full rebuild plus diff as a permanent check;
   * keep `feature_builder_dpv1.py build` as the fallback.
   7b-2 (running totals) would start only after that decision.

**Interaction with 1.4.** Item 5, same-day features as of start of day,
changes `_prior_days_to_event`. That changes the code hash, which resets the
side table, and this is expected. If 1.4 lands during the period, restart
the count.

## Remaining refinement (not started)

A row brought in only because it shares a race with a changed horse is
propagated along every key, track included. That is why the 3-month-back MNR
backfill reached 6,020 rows and fell back. Narrowing it needs a careful read
of which past-race values later rows use.

## Per-table fingerprint (2026-11-10, side-by-side step 1 done)

**What changed.** `feature_input_hashes` gains a `table_name` column, and its
key is now (`table_name`, `entry_id`). `record_full_build`, `update` and
`plan` each read and write only their own table's rows. A table in the old
one-per-DB layout is dropped on the next full build (`_ensure_tables`). It
holds state only; with no state, the next update does a full build. No
feature code changed (`build_version` is unchanged).

**Proof.** On a copy of `.ded1107-run.bak` with the 11/07 card loaded and
pars recomputed as on the night (`fingerprint_proof.sh old|new|side`).

1. **Old code vs new code: identical.**
   * Full builds: 323,329 rows, 0 differing cells, no type differences, same
     hash (`cmp_fingerprint_old_new.json`).
   * 11/07 `card_picks`: 87 rows each, 0 diffs old vs new, and 0 diffs
     against the logged 09:54 record run. Generated time, prediction id and
     picks file are not compared.
   * The new build replaced the old-layout table and wrote the new layout.
2. **A side table keeps its own state.** Pars were frozen on the copy. The
   run built `entry_features_dpv1_inc`, then the main table, then checked
   `plan --table entry_features_dpv1_inc`: "no input changed". Then, in the
   nightly order:
   * load the 11/07 chart, then speed;
   * a **main full build**;
   * `update --table entry_features_dpv1_inc --no-fallback`.

   The side update still found the chart's seeds (75 new, 87 removed, 3
   attribute-only) and recomputed 75 rows in 45 s. The side table then
   equals the main table: 323,317 rows, 0 rows either way, 0 type
   differences. Each table has its own 323,317 fingerprint rows. With the
   old shared layout, the main build would have overwritten the record and
   the side update would have seen no change.
3. The live DB was not written (mtime checked after every phase).

## Big-backfill test (2026-11-11, side-by-side step 2): PASSED

Replay of the real 11/05 load of 44 EVD/LAD charts, on a copy only.

* **Base:** `.pre-charts1105.bak` (320,156 entries). Pars were frozen on the
  copy as `proof-1105`, then speed figures and a full build, which recorded
  the state. `plan` said "no input changed".
* **Load:** the same 44 files in the same order, with
  `retrain_pipeline.load_charts` (new code). Result: 372 races, 2,948
  entries, 1,962 exotics, 0 errors, 0 purged. This matches the PHASE_6E
  record exactly. Speed figures were then computed with frozen pars (0 cells
  missing).
* **Plan:** seeds 2,948 new plus 613 attribute-only. They propagate in 5
  rounds to 62,208 dirty rows, and the closure is the whole corpus (323,104).
  So the result is mode `full` with reason "closure 323104 rows is over 60%
  of 323104".
  * `update --no-fallback` refused with that reason.
  * `update` ran the full build, and `feature_build_log` holds the reason in
    `note`.
* **Fallback result vs a fresh full build:** 323,104 rows each, 131 columns,
  0 differing cells, 0 type differences, same hash
  (`cmp_backfill_fallback.json`).
* **Extra: forced incremental** (`--max-frac 1.0 --no-fallback`) on the same
  state. It recomputed the 62,208 dirty rows in 185 s, against 169 s for the
  full build. The result is identical to the full build: 0 cells, same hash
  (`cmp_backfill_forced.json`). So the dirty set is right on a 3,000-seed
  backfill too, and the fallback costs nothing.

The live DB was not written (mtime checked). The scratch copies are deleted.

**Still to do:** step 3, wiring the side-by-side into the card night (below,
when done).
