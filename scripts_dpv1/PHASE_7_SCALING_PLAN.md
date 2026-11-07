# Phase 7 scaling plan (read-only planning, 2026-11-07)

Nothing in the model, rerankers, pipeline code or live DB was changed for
this document. Measurements were taken on a scratch copy of
`racing_full.db`, with a profiler that wraps functions at run time. The
profiler lives in the session scratchpad and is not committed.

## Summary

* **A nightly card build takes about 10.6 minutes. 71% of that is
  re-reading the same PP PDF**, 11 times: once in `load_pp_card`, then 10
  times in `card_picks` (`pp_index` runs once for the morning line and once
  per race, about 39 s each). The feature build is 26% (165 s). Speed
  figures take 4 s.
* **Peak memory is 2.3 GB, in the feature build**, at the moment the
  132-column frame is written back with `to_sql`. Everything else stays
  under 0.9 GB.
* **The feature build recomputes all 326k entries every night by design.**
  It keeps no state, and speed-figure pars are medians over the whole
  corpus. **Today's 54-chart load changed 41,311 old speed figures (13% of
  the corpus, up to 3.7 points) and `last_race_speed_figure` on 35,844
  existing rows.** Until pars are frozen or computed as of each race's
  date, an incremental build cannot match a full rebuild.
* **Incremental design:** freeze pars and other fitted artifacts, then use
  per-key daily totals ("as of date d" = sum of days before d), dirty-set
  propagation for late or corrected history, and upsert only changed rows.
  Prove it by replaying real loads and requiring zero column differences
  against a full rebuild.
* **Snapshots:** store each card's exact model input when it is scored
  (about 0.2 MB a card) instead of full 0.5 GB DB copies. Add versioned
  feature rows only if feature-definition comparisons become routine.
* **Scaling:** at the current density (6,600 entries per track-year, 5
  years), 10 tracks is about today's size. 25 tracks (0.8M entries) works
  but is tight on this 11.9 GB machine. 100 tracks (3.3M) fails with the
  current design: about 24 GB peak and about 45 minutes. **SQLite isn't
  the limit; whole-corpus pandas rebuilds are.** SQLite stays fine as the
  record store for a single user at all three sizes. Add a columnar store
  for features and training reads at about 25 tracks. Move to Postgres
  only if several processes or users need to write at once.

## 1. Profile of one full card build

DED 2026-11-07 (9 races, 87 horses) on a copy of the live DB after this
morning's chart load: 326,195 corpus entries, 8 tracks, DB file 510 MB.
Each step ran in its own process. Memory is the Windows peak working set
(includes shared pages) and peak commit. One run per step, machine
otherwise idle.

| step | wall | peak WS | peak commit | where the time goes |
|---|---|---|---|---|
| `load_pp_card load` | 61 s | 0.73 GB | 0.88 GB | `build_card` (pdfplumber parse of the PDF) 60.1 s; DB write 0.1 s |
| `speed_figures_dpv1 compute` | 4 s | 0.42 GB | 0.56 GB | read entries 1.2 s, write 326k rows 1.0 s, compute 0.6 s |
| `feature_builder_dpv1 build` | 165 s | **2.34 GB** | 2.50 GB | table below |
| `card_picks --pp-file` (no `--save`) | 408 s | 0.83 GB | 1.15 GB | `pp_index` 10 calls, **392 s**; `load_race_from_db` 11.4 s; predict + simulate + rerank + reasons < 1 s |
| **total** | **~638 s (10.6 min)** | 2.34 GB | | the same PDF parsed 11 times ≈ 450 s |

The copy's card summary matched the 09:54 record run except for 0.1–0.2
points on R5, R8 and R9. Those horses' history changed with the chart load
in between, a small live case of section 2's point.

### Inside the feature build (165 s)

| part | s | memory after (WS) |
|---|---|---|
| `aggregates` (career, connections 30/90/365 d, combos, horse cells, track bias) | 68.3 | 0.9 GB (peak 1.16) |
| `stretch_run` (re-reads the DB, parses every race's calls) | 20.7 | 1.1 GB (peak 1.37) |
| `write_table` (`to_sql`, drop and replace, 132 cols) | 9.7 | **peak 2.34 GB** |
| `derive_row_local` (pace JSON, trip comments) | 9.5 | 0.73 GB |
| `build_context` (previous race, career counts) | 9.1 | 0.79 GB |
| `cross_track` | 8.5 | 1.0 GB |
| `pace_bias` | 7.0 | |
| `load_raw` (one 40-column join) | 5.7 | 0.70 GB |
| `class_context`, `recent_form`, `class_change/trainer`, `field_experience` | 5.0–5.7 each | |
| v1 bucket 6, extras, rest | 4.3 | |

A cProfile pass (240 s with profiler overhead) shows where the time goes
within those parts:

* The prior-history helpers in `scripts/feature_builder.py`
  (`_prior_by_entity_expanding` 23 calls, `_prior_by_entity_windowed` 8,
  `_prior_last_value` 5, `_prior_days_to_event` 2) take about 71 s
  together. They are Python `while`/`for` loops over every row.
* `aggregate_features.compute_recent_form`: a `groupby('horse_id')
  .transform(lambda …rolling(3)…)` with 99k Python lambda calls, 28 s.
* `stretch_run.race_stretch_table`: per-race Python parse of the call
  table, 33 s. Pace JSON is parsed 652k times, and race types are
  normalized 979k times.

### Tables

| table | rows | cols | payload |
|---|---|---|---|
| `entry_features_dpv1` | 326,282 | 132 | **244 MB (48% of the file)** |
| `races` | 43,827 | 36 | 66 MB (text: footnotes, conditions, fractions) |
| `entry_features_v1` (legacy, GP only) | 116,311 | 78 | 60 MB |
| `entries` | 326,195 | 35 | 56 MB |
| `computed_speed_figures_dpv1` | 326,282 | 9 | 15 MB |
| `exotic_payouts` | 251,702 | 10 | 13 MB |
| everything else | | | < 15 MB |

The dominant costs are fixed per card (PDF parsing) or proportional to the
whole corpus every night (features, then speed figures). Nothing in the
nightly path is proportional to *what changed*.

**Quick wins, outside this plan's scope (each a code change for Doug to
approve):**
* Parse the PP PDF once per `card_picks` run (cache `pp_index` by path and
  sha). This saves about 350 s a night and changes no output. The paired
  harness already did this in-process and verified identical results.
* Write the features table without the `to_sql` row-tuple copy. This
  lowers peak memory only; same rows.

## 2. Why the build recomputes everything, and an incremental design

### Why it recomputes every night

1. **No stored state.** Every feature is a function over the whole entry
   frame: sort by (entity, date, entry), then scan each block with a
   Python loop that keeps strictly-earlier sums. Each run discards those
   running totals, so the next night must rescan the corpus.
2. **History is not append-only.**
   * Charts arrive out of order: today's MNR 8/02–11/04 backfill and three
     repaired charts.
   * A chart replaces a loaded card (purge and reload, new entry ids).
   * Past rows get corrected: DQ labels, dead heats, official finish (#14
     C), and the 11/06 hand relabel.
   * People and horses get relinked: name matching, aliases, the
     winner-pedigree fix.
   A drop-and-replace build is correct after any of these with no
   bookkeeping.
3. **Speed-figure pars use the whole corpus.**
   `speed_figures_dpv1.compute_par_times` takes the median final time per
   (track, surface, distance, condition) over every race in the DB,
   including races *after* the one being scored. Any new race can move a
   cell's median, and with it every figure in that cell. Measured today:
   41,311 figures and 35,844 `last_race_speed_figure` values changed on
   rows that already existed. This is also a mild look-ahead in the
   training rows (historical figures use pars that include later races).
   Changing it is a model-input decision (see Decisions).
4. At 200k rows a 3-minute full rebuild was the simplest correct design.

### Features that depend on later or changing data

Every statistic uses strictly-earlier dates, except where noted. "Later
data" here means data that arrives or changes after an entry's features
were first computed.

| dependency | features affected | handling in the incremental build |
|---|---|---|
| **Pars over the whole corpus** (speed figures) | `speed_figure_own` → `last_race_speed_figure`, speed trajectory and averages, track bias (`race_bias` = winner's figure − 80), class context and cross-track terms that use figures | **Prerequisite:** freeze the par table as a versioned artifact (`par_version`), or compute pars from races before each race's date. Refresh only with a full rebuild (e.g. at retrain). |
| **Fitted artifacts:** stretch-run pace par and expected-gain table (races before 2023) | `last_str_gain_padj*` (research only; the live `last_str_gain` and `_rank_pct` don't use the fit) | Store the fit as an artifact; refit only on a full rebuild. Today it silently changes whenever a pre-2023 chart is added. |
| **Same-race (cross-sectional) values** | `field_experience` (field mean, median, min, max, rank of career starts), `market_probability_normalized`, `weight_vs_field_avg`, `beat_favorite`, stretch `rank_pct`, pace-bias front-runner counts | The unit of recompute is the **race**. If any entry in a race is dirty, recompute the whole race. Field features read *other* horses' career counts, so an upstream change dirties every race those horses later ran in. |
| **Population cells** (prior-only but shared by everyone in the cell) | (track, surface) 90-day bias, (track, post) win %, trainer × condition, jockey × surface, trainer × jockey, sire / dam / damsire (× context), cross-track per-track counts | A backfilled or corrected race at date d dirties **every later entry in the cell**. Windowed cells (bias 90 d, 30/90/365 d connection rates) only within the window. |
| **Entity identity** | everything keyed on horse, jockey, trainer, sire or dam id | Alias, merge or relink: both ids' entries after the earliest affected date are dirty. |
| **Horse attributes** (foaled date, sex, country, pedigree) | `horse_age`, sex, country, pedigree rates | A `horses` row change dirties that horse's entries and, for pedigree, its relatives' cells. |
| **Card vs chart** | equipment pre-race rule (`pre_race` = race has no result), today's lasix/blinkers, all card rows | Card rows are temporary. On purge and reload they're deleted and the new chart entries computed fresh. |
| **Global code and config** | everything | A `feature_build_version` = hash of `dpv1_feature_config.json`, feature code, `CLASS_TIERS`/race-type mapping, `par_version` and fit version. Any change forces a full rebuild. |
| **Frame-dependent code** | `cross_track._track_ids(raw)` (tracks present in the frame), dtype inference on all-NULL columns | Use the global track list from `tracks`; cast output to a fixed schema. |

### Design

**Storage**

* `entry_features_dpv1` stays one row per entry, written by upsert, plus
  `build_version`, `computed_at` and `input_fingerprint`.
* `feature_build_log`: run id, mode (full or incremental), seeds, dirty
  count, version, and a table hash.
* `par_times_dpv1` (versioned) and `fit_artifacts` (stretch fit).
* `key_daily_totals`: one table per key family, one row per (key, date),
  with integer sums (starts, wins, ITM) and float sums (bias, figures).
  "Prior sum as of date d" = sum over dates < d (expanding), or over
  [d − window, d) (windowed). This replaces the row scans. A backfill is
  just an insert at its date, and later lookups are right automatically.

**Nightly flow**

1. **Seeds.** New, changed and deleted entries since the last run. Detect
   them by **fingerprint diff**, not by loader events: a hash per entry of
   every raw column the builder reads (entry, race, horse, sire/dam,
   figure). That also catches hand edits like the 11/06 relabel.
2. **Propagate.** For each key family, the later entries (strictly later
   date; same-day excluded, as in training) that share a key with a seed.
   Windowed families only within the window. Then expand to whole races
   (the cross-sectional rule above). One pass is enough, because no
   feature reads another horse's *derived* feature from a past race.
3. **Compute** features for the dirty set only: entity rows come from the
   daily totals, the previous race comes from a per-horse last-race
   index, and same-race values come from the dirty races.
4. **Upsert** the dirty rows, update the daily totals, log the run.
5. **Fallback:** if the version changed or the dirty set is over N% of
   the corpus, run the existing full build (unchanged code, kept as the
   reference implementation).

**Two ways to build it, in order**

* **7b-1 "closure recompute" (reuses today's code).** Run the existing
  `build_features` on only the rows the dirty set needs: same keys, prior
  dates, same races. Keep the dirty rows' output. Because each helper is
  per entity and sums in (entity, date, entry) order, the result is
  bit-identical when the subset contains all prior rows of every key. Cost
  is set by the closure: **tonight's 87 entries pull 97,382 history rows
  (30%)**. Jockeys (31k), trainers (32k), sires (29k), damsires (32k) and
  DED post/bias cells (30k) dominate; the horses themselves are only 1.1k.
  That's about 50 s instead of 165 s. Low risk, modest gain.
* **7b-2 "daily totals" (the real fix).** Replace the scans for the heavy
  families (connections, pedigree, track cells, career) with
  `key_daily_totals` lookups. Cost becomes proportional to dirty entries.
  A normal night (87 card rows + about 70 chart rows) is seconds. Count
  sums are exact. Float sums (`race_bias`, figure sums) can differ from
  the row scan in the last bit because addition order changes. Either sum
  in the same order (keep per-day rows ordered by entry_id and add day by
  day in date order, which is the scan order), or accept |Δ| ≤ 1e-12 for
  those columns only. Decide before building.

### Proving the incremental output matches a full rebuild

1. **Determinism baseline.** Two full builds on the same DB must give the
   same table hash (sha256 per row over a fixed column order with
   round-trip float repr). If not, fix that first.
2. **Replay test on real history.** Restore a pre-load backup (e.g.
   `.ded1104-run.bak`) and run a full build. Apply the real sequence of
   loads since then (11/04 card, charts, 11/05 EVD/LAD 44-chart backfill,
   the 11/06 relabel, the DED cards, today's 54-chart backfill and purge
   and reload), with an incremental update after each one. After every
   step, compare against a full rebuild of that state: same entry ids,
   same dtypes, **zero differing cells per column** (NULL = NULL; counts
   exact; float sums exact or within the agreed bound). Report mismatch
   counts per column, which must all be 0.
3. **Adversarial edits on a copy:**
   * backfill an old chart;
   * purge and reload a day;
   * flip a DQ / official finish;
   * merge two jockey ids (alias);
   * change a horse's sire or foaled date;
   * scratch a card entry, or add an also-eligible;
   * change a config value (must trigger a full rebuild).
   Each must give zero differences.
4. **Prediction-level check.** Score the last N logged cards from both
   tables: P(ITM) identical.
5. **Shadow period.** Run incremental alongside the nightly full build for
   2 weeks (full build stays the source of truth) and compare table hashes
   every night. Promote after 14 zero-diff nights. Keep a **weekly full
   rebuild + diff** as a permanent canary.

Both builds must use the same frozen par and fit versions, or no
comparison can come out equal.

## 3. Point-in-time feature snapshots

**Today:** the paired comparison (2026-11-01) needed `.ded1028/1029/1030
-run.bak`, full 0.5 GB copies taken before each PP load. Each arm then
re-ran PP load, speed figures and features on a copy (about 5 minutes a
pass, and runs were killed for low memory). At 100 tracks each copy would
be about 5 GB. A copy is needed because the live DB doesn't keep "what the
model saw that night": features are recomputed, history is backfilled,
and pars drift (today's load moved 35,844 `last_race_speed_figure`
values).

**Proposal, in three layers:**

1. **Card input snapshot (do first; small and exact).** At `card_picks
   --save`, write one row per horse to `card_feature_snapshots` (SQLite
   table, or one Parquet file per run once pyarrow is installed):
   * `prediction_id` and `entry_id`;
   * the stored feature row (pre-bridge) and the **post-bridge vector the
     model scored**;
   * the PP-reranker inputs (`pp_entries_raw` rows used) and coverage;
   * versions: model, reranker, config, `feature_build_version`,
     `par_version`, git commit and name-matching state.
   That's about 87 × 260 values ≈ 0.2 MB a card, about 200 MB per 1,000
   cards. **Model and reranker arms** (1.3.0 vs 1.3.2, with or without the
   reranker, classctx shadow) then re-score straight from snapshots in
   seconds, with no DB copy. Validation: re-scoring the record run's
   snapshot must reproduce the logged P(ITM) exactly. That's also a
   standing reproducibility check.
2. **Versioned feature rows (only if history arms become routine).** A
   `load_events` table gives each load a sequence number (chart, PP card,
   correction, alias). Incremental upserts close the old row version
   (`valid_to_seq`) instead of overwriting. "Features as of load L" = rows
   with `valid_from_seq ≤ L < valid_to_seq`. Growth is only the dirty rows
   (a few hundred on a normal night, tens of thousands on a backfill
   night), and compaction can drop versions no snapshot references. This
   answers "what would the history have looked like that night" for
   **input arms** (name matching on/off, the queued PP-date days-off test
   #4) without copying the DB.
3. **Feature-definition arms** (a new or changed feature) need the raw
   inputs as of L. Prefer replaying the chart and PP files (they're in git
   with sha256 in `parsed_files`) up to L into an empty DB. That's slow
   but exact, and rare. Add soft deletes to raw tables only if this
   becomes frequent.

Layer 1 alone would have covered the 11/01 comparison. Layer 2 covers the
on/off input tests that have come up twice this meet (name matching, PP
date).

## 4. Scaling estimates

**Assumptions.** Density is the measured 2022–2025 mean, **6,568 entries
per track-year** (median 5,510; GP 14.7k, ELP 2.0k), 7.44 entries a race,
5 years. Per-entry costs are scaled linearly from the measured run: DB
1.56 KB/entry, feature build 0.48 ms/entry, plus `cross_track` scaling
with **tracks × entries** (it loops once per track over the whole frame),
and peak memory 7.2 KB/entry. Machine: 11.9 GB RAM. These are linear
extrapolations of one run, not measurements. Treat them as ±30%.

| | today (8 tracks, mixed years) | 10 tracks | 25 tracks | 100 tracks |
|---|---|---|---|---|
| entries / races | 326k / 44k | 330k / 44k | 820k / 110k | 3.3M / 440k |
| DB size (raw + features) | 0.51 GB | 0.5 GB | 1.3 GB | 5.1 GB |
| **current:** feature build | 165 s | ~3 min | ~8 min | ~45 min |
| **current:** peak memory | 2.3 GB | 2.4 GB | ~5.9 GB (tight) | **~24 GB+ (does not fit)** |
| **current:** speed figures | 4 s | 4 s | 9 s | ~40 s, 4.3 GB |
| **current:** nightly total, one card (PDF parsed 11×) | 10.6 min | ~11 min | ~15 min | ~52 min |
| same with `pp_index` cached (1 parse) | ~5 min | ~5 min | ~10 min | ~46 min |
| full features read for training (SQLite → pandas) | 17 s | 17 s | ~45 s | ~3 min |
| **7b-1 closure:** normal night | ~50 s, ~1 GB | ~50 s | ~2 min, ~2 GB | ~10–15 min with many cards a night, ~7 GB |
| **7b-2 daily totals:** normal night | seconds, < 1 GB | seconds | seconds | < 1 min, ~1–2 GB (365-day window state) |
| incremental, backfill night | proportional to dirty set; fallback full build | | | full build must be chunked by date to fit |
| paired-comparison storage | 3 × 0.5 GB copies | same | 3 × 1.3 GB | 3 × 5 GB → **snapshots: ~0.2 MB/card** |

Notes:

* **10 tracks × 5 years is roughly today's corpus.** Nothing breaks.
* **25 tracks** works with the current design. But peak memory (~6 GB)
  plus the OS leaves little margin on this machine, and background jobs
  have already been killed for low memory at today's size. Pre-race
  rebuilds become an ~8-minute wait.
* **100 tracks** does not fit the current design on this machine. Peak
  memory alone is about 2× the RAM, and `cross_track` grows to about 18
  minutes by itself.
* **3.3M is an upper bound.** Our 8 tracks are mid-to-large. If "100
  tracks" means all of North American thoroughbred racing, total yearly
  starts are much lower than 100 × 6,568. My recollection is about a
  quarter-million a year, which would mean about 1.2–1.5M entries over 5
  years. Check that against the Jockey Club fact book before planning on
  it. At 1.3M the current design is about 17 minutes and 9–10 GB peak:
  still over this machine's comfortable limit.

### When SQLite stops being the right choice

Size is not the issue: 5 GB is small for SQLite. The limits are:

1. **Whole-frame pandas, not SQLite, is the first wall.** It's hit at
   about 30–40 tracks on this machine. The incremental design removes it.
2. **Wide analytical reads.** A row store converted through Python reads
   132 columns at about 50k rows a second here (17 s for 326k). At 25+
   tracks, training and research reads take minutes. A columnar store for
   the features (Parquet queried with DuckDB) is the usual fix. Not
   measured here because pyarrow isn't installed, and installing it is a
   dependency decision.
3. **Concurrent writers.** SQLite allows one writer at a time. A
   single-user nightly batch is fine even at 100 tracks. Several loaders
   running in parallel, a web front end, or several people or agents
   writing at once need Postgres.
4. **Copies as the unit of comparison.** At 5 GB, full-DB copies per
   experiment stop being practical. Section 3 replaces them regardless of
   the engine.

**Recommendation:**
* Keep SQLite as the record store (charts, entries, picks) through 100
  tracks while the work stays single-user batch.
* Add a columnar feature and snapshot store when the features table
  passes about 1M rows (about 25–30 tracks) or a training read passes
  about 1 minute, whichever comes first.
* Move the record store to Postgres only when concurrent writes or remote
  access are needed.

## Suggested order and decisions for Doug

1. **Decide the par policy** (prerequisite for everything incremental):
   * (a) **freeze** the current pars as `par_version` 1, refreshed only at
     retrain. History stops drifting; no other change until refreshed.
   * (b) **point-in-time pars** (median of races before each race's
     date). This removes the look-ahead but changes training inputs, so
     it's an ablation and retrain like any feature change.
   Either way, record it in PHASE_6E as an input change.
2. Quick win: cache `pp_index` in `card_picks` (−350 s a night, output
   identical; verify on two logged cards).
3. Card input snapshots (section 3, layer 1) from the next card; validate
   that re-scoring reproduces logged P(ITM).
4. 7b-1 closure recompute plus the equivalence harness (determinism
   baseline, replay test, adversarial edits, 2-week shadow).
5. 7b-2 daily totals for the heavy key families, when tracks go past
   about 15–20 or nightly time matters.
6. Versioned feature rows (section 3, layer 2) if input-arm comparisons
   keep coming up.
7. A columnar feature store at about 25 tracks; Postgres only for
   concurrency.

Nothing here touches the live model, rerankers or the protected Piece 1–4
code until Doug picks items.
