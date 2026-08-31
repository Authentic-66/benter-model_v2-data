# Phase 6E — what got built

## Piece 1: Prediction logging (done)

`card_picks.py --save` now writes a third artifact alongside the `.txt` and
`.csv` in `picks/`: one JSON line per horse appended to
`scripts_dpv1/logs/predictions.jsonl`. The directory is created on demand.

Pieces 3 (`model_health.py`) and 4 (`retrain_pipeline.py`) are **not** built
yet. Piece 2 is below.

### Row schema

| field | type | notes |
|---|---|---|
| `prediction_id` | str | `{TRACK}_{date}_R{race}_pgm{pgm}_{YYYYmmdd-HHMMSS}` |
| `generated_at` | str | ISO 8601, second resolution, local time |
| `track` | str | uppercased |
| `race_date` | str | `YYYY-MM-DD`, as passed to `--date` |
| `race_num` | int | |
| `pgm` | str | program number — **string**, not int (coupled entries are `1A`, `5B`) |
| `horse_name` | str | |
| `p_itm` | float | model P(top 3), 4dp |
| `p_win` | float | Harville-inverted P(win), 4dp |
| `coverage` | float | **per-horse** feature coverage, 0–1 |
| `race_coverage` | float | race-level coverage — extra field, not in the spec; piece 3 buckets by race |
| `ml_odds` | str/null | morning line, null unless `--pp-file` was passed |
| `prime_power` | float/null | Brisnet Prime Power, null unless `--pp-file` was passed |
| `model_version` | str | e.g. `dpv1.2.0-4track` |
| `model_pkl` | str | basename of `--model`, e.g. `dpv1.pkl` / `dpv1_3track.pkl` |
| `rank` | int | 1 = top pick, by descending `p_itm` |
| `n_horses_in_race` | int | |
| `picks_file` | str | path relative to `scripts_dpv1/`, posix separators |

Missing values are `null` — NaN and the display table's empty-string
"no morning line" both normalise to `null` so downstream code has one case
to handle.

### Design decisions worth knowing

**`prediction_id` is stamped to the second, the picks filename to the minute.**
The filename convention was already minute-resolution and re-running a card
inside one minute (a late scratch, say) is routine — harmless for a file that
gets overwritten, fatal for an id that has to stay unique. Verified: a full
card plus a same-minute single-race re-run produced 121 rows and 121 distinct
ids.

**Append-only, never fatal.** `append_predictions()` catches `OSError` and
`prediction_rows()` is wrapped in a bare `except` at the call site. A full disk
or a locked file costs one log row and prints a warning; it never takes down
pick generation.

**Both models log.** `model_pkl` and `model_version` come from whatever
`--model` pointed at, so 4-track and 3-track runs land in the same file and are
separable at read time.

**`pgm` is a string.** The spec example shows `4`; program numbers are not
always integers. Piece 2 should join on `(track, race_date, race_num, pgm)`
with `pgm` compared as text.

### New flag

`--log-file PATH` overrides the default `logs/predictions.jsonl`. Only
consulted when `--save` is passed. Added for testing; not needed in normal use.

### Verification

```
python scripts_dpv1/card_picks.py --track CT --date 2026-08-28 --save
```
→ 112 rows across 13 races, 7–11 rows per race, all ids unique.

```
python scripts_dpv1/card_picks.py --track CT --date 2026-08-28 --race 5 \
    --pp-file CharlesTown/ct-pps-files/ctx0828y.pdf --save
```
→ 9 more rows appended, `ml_odds` and `prime_power` populated.

---

## Piece 2: Post-race scoring (done)

`scripts_dpv1/score_predictions.py` reads `logs/predictions.jsonl`, joins it to
the finishing positions in `racing_full.db`, and writes
`logs/scored_predictions.jsonl`.

```
python scripts_dpv1/score_predictions.py --track CT --date 2026-07-25
python scripts_dpv1/score_predictions.py --all            # retro-score everything
python scripts_dpv1/score_predictions.py --all --dry-run  # summarise, write nothing
```

Flags: `--track`, `--date`, `--all`, `--db`, `--pred-file`, `--out-file`,
`--dry-run`. `--all` scores every card present in the prediction log (narrowed
by `--track` if given) — that is the "retro-score all recent cards" path.

### Scoring fields (added to every predictions.jsonl field)

| field | type | notes |
|---|---|---|
| `actual_finish` | int/null | `finish_pos`; null for DNF |
| `hit_itm` | bool | finished 1-3 |
| `hit_win` | bool | finished 1 |
| `was_top_pick` | bool | `rank == 1` in this run |
| `top_pick_hit_itm` | bool/null | did *this race's* top pick hit; **null if it had no outcome** |
| `show_payoff` | float/null | `entries.show_payout`, per $2; non-null only for ITM horses |

Extra fields beyond the spec, all cheap and all wanted downstream:

| field | why |
|---|---|
| `top_pick_scratched` | makes the `top_pick_hit_itm` null case explicit for Piece 3 |
| `finish_status` | the only way to tell DNF from scratched from not-loaded |
| `final_odds` | Piece 3's ROI section, and any market comparison |
| `n_starters` | horses that actually ran, vs `n_horses_in_race` at prediction time |
| `scored_at` | when the join ran |

### The three ways a horse has no outcome

These are not interchangeable and the summary counts them separately:

* **scratched** — name appears in `races.scratched_horses`. No scored row.
* **no result recorded** — an `entries` row exists with `finish_status` NULL.
  In this corpus that is normally a disqualification: the loader renames the
  horse `DQ-<name>` and leaves `finish_pos` NULL, so the race ends up with no
  recorded winner at all. **168 of 29,020 results-loaded races (0.58%) have no
  `finish_pos = 1`.** Pre-existing corpus issue, not a scoring one, but it
  depresses measured win rate slightly and Piece 3 should know. No scored row.
* **unmatched** — no `entries` row and not on the scratch list. A real join
  failure; warns loudly. Zero of these across 131 rows scored so far.

A **DNF** (`finish_status = 'DNF'`, `finish_pos` NULL) *is* scored: the horse
ran and did not hit the board, so `hit_itm` is false with `actual_finish` null.

### Why a scratched top pick is null, not false

Counting a scratched top pick as a miss biases the model's headline metric
downward by however often the top pick scratches. When rank 1 has no outcome,
the race carries `top_pick_hit_itm = null` and `top_pick_scratched = true`.
**Piece 3 must exclude those races from the denominator, not count them as
misses.** This matches how the CT 2026-08-28 card was checked by hand (7 of 12
non-scratched top picks, from a 13-race card).

### Idempotency

Re-scoring rewrites that card's rows rather than appending. Every row matching
the `(track, race_date)` being scored is dropped from
`scored_predictions.jsonl` and replaced; other cards pass through untouched.
The rewrite goes via a `.tmp` file and `os.replace`, so an interrupted run
cannot truncate the history. Verified: scoring CT 2026-07-25 three times leaves
131 rows and 131 distinct `prediction_id`s, with the ELP rows intact.

### Grouping

Rows group by `(generated_at, model_pkl, race_num)`, not by race alone. A card
can be run more than once — a different model, or a re-run after a scratch —
and each run is a separate opinion with its own rank 1.

### Verification

| card | races | rows | top pick ITM | top pick WIN | show ROI |
|---|---|---|---|---|---|
| CT 2026-07-25 | 9 | 56 | 6/9 = 66.7% | 2/9 = 22.2% | -23.3% |
| ELP 2026-08-21 | 9 | 75 | 4/9 = 44.4% | 3/9 = 33.3% | -27.0% |

All 131 scored rows were cross-checked against a second independent SQL query:
zero mismatches on `actual_finish`, `hit_itm`, `hit_win`, `finish_status` and
`show_payoff`. 17 of 18 race-runs contain exactly 3 ITM horses; the 18th is the
`DQ-Oscor` race described above. Every race-run has exactly one `was_top_pick`.

**These two cards are inside the training corpus** (`dpv1.pkl` was trained
2026-08-22), so the rates above verify the plumbing, not the model. They are
not out-of-sample performance and must not be read as such.

### ~~Blocked~~ RESOLVED 2026-08-29: CT 2026-08-28

The card the spec asks to score has **no results in `racing_full.db`** — all
112 entries have `finish_pos` and `finish_status` NULL. `CT082826USA.pdf` is on
disk in `CharlesTown/ct-results-2026/` but has never been parsed; the newest
row in `parsed_files` is ELP 2026-08-21, loaded 2026-08-22. The same is true of
CT 2026-08-29, ELP 2026-08-22 and ELP 2026-08-23 — these are the four
"upcoming card" days, loaded from entries with no outcomes.

The scorer handles this correctly (skips the races, warns, writes nothing), but
the 58% sanity check cannot be reproduced from the database until the results
PDF is loaded. **Loading it is Piece 4 step 1**, which also has to guard the
NaN-as-False labeling bug on exactly these upcoming-card rows.

---

## Result load, 2026-08-29 (manual Piece 4 step 1)

Ran `scripts_dpv1/_load_pending_results.py`. Backup at
`scripts/racing_full.db.pre6e.bak` (taken before any write).

| card | purged | loaded |
|---|---|---|
| CT 2026-08-28 | 112 entries / 13 races / 224 derived | 13 races, 100 entries, 62 exotics |
| ELP 2026-08-22 | 105 / 9 / 210 | 9 races, 84 entries, 55 exotics |
| ELP 2026-08-23 | 101 / 9 / 303 | 9 races, 85 entries, 55 exotics |

Post-load integrity: zero duplicate `(race_id, program_num)`, zero orphaned
rows in `entry_features_dpv1` or `computed_speed_figures_dpv1`.

### The purge is mandatory, and it is not just a retrain concern

`entries` carries `UNIQUE(race_id, program_num)`; `db_loader` inserts with
`INSERT OR IGNORE` and `ingest_race_day`/`ingest_race` return the *existing*
row when the day is present. Loading a chart onto a day already loaded as an
upcoming card therefore **silently drops every result row and reports
success** — the NULL `finish_pos` entries survive and the race rows never get
their chart fields. Piece 4 must purge before it loads, not just before it
trains.

### Side effect: feature tables are emptied

The purge deletes `entry_features_dpv1` / `computed_speed_figures_dpv1` rows
for those entries (they key on `entry_id` and would otherwise orphan). The
reloaded entries have **no feature rows**, so `card_picks.py` cannot score
those three cards until the DPv1 feature pipeline is re-run — it warns
`race_id=N has no rows in entry_features_dpv1` and produces nothing.

This does not affect the scoring below: those predictions were logged *before*
the purge and the results were loaded after. But **Piece 4 must rebuild
features after its purge/load step**, or the freshly loaded cards are
unpredictable.

### Validation against manual scoring

| card | scorer | manual | match |
|---|---|---|---|
| CT 2026-08-28 | top pick ITM **7 / 12 = 58.3%** | 7 of 12 | yes |
| ELP 2026-08-23 | top pick ITM **8 / 8 = 100%** | 8/8 | yes |
| ELP 2026-08-22 | top pick ITM 5 / 9 = 55.6% | — | — |

CT 2026-08-28 detail: 13 races, 12 scratches, 1 DNF, 109 scored rows. R13's top
pick was scratched and is excluded from the denominator, giving 12 not 13.

ELP 8/22 and 8/23 were scored from the **original pre-race picks CSVs** in
`picks/`, joined to the DB directly — those cards predate Piece 1, so they have
no rows in `predictions.jsonl`. They cannot be re-predicted into the log until
features are rebuilt (see above).

### Bug found and fixed: re-run races were double-counted

The first scored pass reported CT 2026-08-28 as **8/13 = 61.5%**, not 7/12.
The scored rows were correct; `print_summary` was wrong. R5 had been predicted
twice (once with the whole card, once alone with a PP file), and both runs'
top picks were counted — inflating both numerator and denominator.

Fixed with `latest_run_only()`: the scored file still keeps every run, because
the audit trail is the point, but rates are computed from the most recent run
per race and the summary reports how many rows were superseded.

**Piece 3 must call `latest_run_only()` before aggregating anything.** Without
it, any card that gets re-run pulls the rolling average toward its own result,
weighted by how many times it happened to be re-run.

## Queued: CT backlog (Part 2, not executed)

`scripts_dpv1/_load_ct_backlog.py` — defaults to `--dry-run`, needs
`--execute`. Dry run verified: **14 unparsed files, 13 unique charts**, CT
2026-07-30 through 2026-08-27, 106 races and 749 entries. None of the 13 dates
exist in the DB, so no purge is expected; the guard runs anyway and would purge
rather than silently no-op.

The duplicate: `20260801-usa-ct-a-d.standard.pdf` and
`20260801-usa-ct-a-d.standard (1).pdf` are byte-identical — 125,161 bytes,
sha256 `45f7df71b568…`. The **file without the `(1)` suffix is canonical**; the
`(1)` copy is a browser re-download one minute newer and is skipped, with no
`parsed_files` row.

Dedup is by sha256 with the canonical file chosen **by name, not sort order** —
`(1)` sorts *before* the clean name, so a naive `sorted(glob('*.pdf'))` walk
keeps the copy and discards the real filename.

---

## CT backlog load + feature rebuild, 2026-08-29

Backup taken first: `scripts/racing_full.db.pre-backlog.bak`.

`_load_ct_backlog.py --execute` loaded **13 charts, 108 races, 749 entries,
535 exotics** (CT 2026-07-30 → 2026-08-27). The `(1)` duplicate was skipped and
not recorded in `parsed_files`. No date needed a purge.

Feature rebuild, in this order — both are whole-corpus drop-and-replace, there
is no per-date rebuild:

```
python scripts_dpv1/speed_figures_dpv1.py compute    # 220,581 rows, 84.7% with a figure
python scripts_dpv1/feature_builder_dpv1.py build    # 220,581 rows x 107 cols, 66s
```

Confirmations:

* All 16 dates present (13 backlog + CT 8/28, ELP 8/22, ELP 8/23).
  `parsed_files` success rows 3,284 → 3,300 (+16).
* `entry_features_dpv1` complete for all three reloaded cards — CT 8/28
  100/100, ELP 8/22 84/84, ELP 8/23 85/85 — and for the backlog. Zero orphans.
* Re-scoring picked up nothing new: the only card still skipped is CT
  2026-08-29, whose chart has not been published yet.

### Rolling totals

| | |
|---|---|
| scored rows | 240 (240 distinct `prediction_id`) |
| cards covered | 3 — CT 2026-07-25, CT 2026-08-28, ELP 2026-08-21 |
| rows after run-dedupe | 231 (9 superseded) |
| distinct races scored | 31 |
| pooled top pick ITM | 17 / 30 = 56.7% |
| pooled top pick WIN | 8 / 30 = 26.7% |
| pooled show ROI | $40.54 on $60.00 = **-32.4%** |

Pooled figures mix in-corpus and out-of-corpus cards and are **not** a
performance measurement. Piece 3's job is to separate them.

Per card, unchanged from the previous pass:

| card | top pick ITM | in log? |
|---|---|---|
| CT 2026-08-28 | **7 / 12 = 58.3%** | yes |
| ELP 2026-08-23 | **8 / 8 = 100%** | no — scored from the original picks CSV |
| ELP 2026-08-22 | 5 / 9 = 55.6% | no — scored from the original picks CSV |
| CT 2026-07-25 | 6 / 9 = 66.7% | yes |
| ELP 2026-08-21 | 4 / 9 = 44.4% | yes |

ELP 8/22 and 8/23 predate Piece 1 and have no rows in `predictions.jsonl`, so
they sit outside the scored log. Now that features are rebuilt they *can* be
re-predicted into it — but the field would be the post-scratch starter list
from the chart, not what was on the board pre-race, so the ranks would not
necessarily reproduce the originals. Back-filling from the picks CSVs would be
faithful; neither has been done.

---

## Piece 3: Model health dashboard (done)

`scripts_dpv1/model_health.py`. Reads `logs/scored_predictions.jsonl`, joins
race metadata from `racing_full.db`, prints. Never writes.

```
python scripts_dpv1/model_health.py                      # rolling summary
python scripts_dpv1/model_health.py --out-of-corpus      # the real number
python scripts_dpv1/model_health.py --track CT
python scripts_dpv1/model_health.py --model dpv1.pkl
python scripts_dpv1/model_health.py --last-n 100
python scripts_dpv1/model_health.py --since 2026-08-01
```

Also `--until`, `--in-corpus`, `--training-cutoff DATE`, `--model-file`,
`--db`, `--scored-file`. Output is ASCII — the Windows console mangles box
drawing the same way it mangles em-dashes.

### Constraints from Pieces 1-2, all enforced

* `latest_run_only()` is applied **before anything is counted**. Without it CT
  2026-08-28 reads 8/13 instead of 7/12.
* Races with `top_pick_scratched` leave the ITM **and** WIN denominators.
* Races with no recorded winner (DQ) leave the **WIN** denominator only; the
  board is still well defined, so they stay in ITM. Detected from the DB
  (`EXISTS finish_pos = 1`), not inferred from the scored rows.
* Uses `race_coverage` for coverage buckets, `n_starters`, `final_odds`,
  `show_payoff`, `finish_status` via Piece 2's fields.

### The corpus split is data-driven, and the spec's date rule is wrong

The spec says out-of-corpus is `race_date > 2026-08-22`, then lists ELP
2026-08-22 as out-of-corpus. Both cannot hold. The chart load times settle it:

| card | chart parsed_at | vs trained_at 2026-08-22T14:20Z | corpus |
|---|---|---|---|
| CT 2026-07-25 | 2026-07-31 17:07 | before | in |
| ELP 2026-08-21 | 2026-08-22 01:47 | before | in |
| ELP 2026-08-22 | 2026-08-29 18:32 | after | **out** |
| ELP 2026-08-23 | 2026-08-29 18:32 | after | **out** |
| CT 2026-08-28 | 2026-08-29 18:32 | after | **out** |

ELP 2026-08-22 ran *on* the cutoff date but its chart was not loaded until a
week after the model was trained, so it is genuinely out-of-sample. The
inventory in the spec is right; the date rule is not.

Default behaviour therefore compares `parsed_files.parsed_at` against the
reference pickle's `trained_at`. `--training-cutoff DATE` forces the date rule;
running it with `2026-08-23` reproduces the spec's error and moves ELP 8/22
into the in-corpus bucket, which is a useful demonstration of why the default
is not that.

### Alert thresholds

Spec bands, with a floor: a bucket under **20 races** is printed as `(thin)`
and never alerted on. The bands were written for ~100-race windows and firing
them on nine races manufactures alarms out of noise. All four rules were
exercised against synthetic windows and fire correctly; a thin window prints
`window too thin to alert on`, not `all metrics within expected bands`.

### Back-fill: ELP 8/22 and 8/23 (`_backfill_picks_csv.py`)

Those cards predate Piece 1 and existed only as `picks/*.csv`. Re-predicting
them today would not reproduce them — the charts are loaded now, so the field
is the post-scratch starter list and the Harville inversion renormalises over a
different set of horses. The CSVs are the actual pre-race opinion, so 206 rows
were back-filled from them and scored. They reproduce the manual numbers
exactly: ELP 8/22 **5/9**, ELP 8/23 **8/8**.

**Model attribution: `dpv1.2.0-4track`, from the picks-file header.** The CSV
carries no model version but the `.txt` beside it does — the runner writes
`DPv1 <version> -- <TRACK> <date>` as its second line. Both back-filled cards
read `dpv1.2.0-4track`, so that is written to `model_version` with
`backfill_attribution: "picks_file_header"` recording where it came from.
`model_pkl` stays null: the header records a version, not an artifact filename.

**A timezone trap worth remembering.** `dpv1.pkl` has
`trained_at = 2026-08-22T14:20:19Z` and these cards were generated at 09:24 and
09:44 *local*. Read side by side that looks like the picks predate the model —
but local time here is **UTC-5**, so training finished at 09:20 local and the
cards were predicted minutes later on the freshly trained 4-track model. An
earlier version of this document drew the wrong conclusion from exactly that
comparison. Convert before inferring.

The *earlier* runs of both cards — ELP 8/22 at 08:13, ELP 8/23 the night before
at 23:30 — do carry `dpv1.1.0` in their headers. The back-fill names the
09:24/09:44 files explicitly rather than globbing, so it picks the 4-track pair.

`_backfill_picks_csv.py --replace` rewrites previously back-filled rows for
these cards instead of skipping them as duplicates; that is the one sanctioned
exception to the log being append-only, and it goes via a temp file.

### Verification

| filter | result | target |
|---|---|---|
| `--track CT --since/--until 2026-08-28` | ITM **7 / 12 = 58.3%** | 7/12 |
| `--track ELP --since/--until 2026-08-23` | ITM **8 / 8 = 100%** | 8/8 |
| `--track ELP --since/--until 2026-08-22` | ITM **5 / 9 = 55.6%** | 5/9 |
| `--in-corpus` | 18 races, ITM 55.6% | CT 7/25 + ELP 8/21 |
| `--out-of-corpus` | 31 races, ITM **20/29 = 69.0%** | CT 8/28 + ELP 8/22 + 8/23 |
| `--model dpv1.2.0-4track --out-of-corpus` | 31 races, ITM **20/29 = 69.0%** | all attributed to one model |
| `--model dpv1.pkl --out-of-corpus` | 13 races, ITM **7/12 = 58.3%** | CT 8/28 only (back-fill has no `model_pkl`) |

### How to read the current numbers

The `--out-of-corpus` figure is **20 / 29 = 69.0%**, and all 29 races are
`dpv1.2.0-4track` — 12 logged by the runner (CT 8/28) plus 17 attributed from
picks-file headers (ELP 8/22, 8/23). It is a single-model, genuinely
out-of-sample number.

It is also 29 races. It sits **above the 68% alert ceiling**, and one card
carries it: ELP 2026-08-23 went 8-for-8. Drop that card and the remaining 21
races run 12/21 = 57.1%, which is squarely in the target band. The honest read
is that the model looks fine and the sample is far too small to say more.

Per card, out-of-sample: CT 8/28 **7/12 = 58.3%**, ELP 8/22 **5/9 = 55.6%**,
ELP 8/23 **8/8**. Piece 4 should not use any of this as a promotion criterion
until the window is several hundred races.

Note `--model dpv1.pkl` matches only CT 8/28, because the back-filled rows have
no `model_pkl`. Use `--model dpv1.2.0-4track` to select all 29.

### Mixed-window banner

The header names the model. It appends `(MIXED -- rates below span more than
one model)` only when the window genuinely spans models:

| window | banner |
|---|---|
| runner-logged + attributed, same version | no banner |
| attributed row with a *different* version | **MIXED** |
| any row with no version at all | **MIXED** |

An attributed back-fill is a recorded fact about a known model, not a gap, so
it counts as the version it names. A `=== Provenance ===` block reports how
many races were attributed and from where, so the header's confidence is always
traceable to its source.

`By Model` groups by **version**, not by pickle filename — an attributed
back-fill has a version but no filename, and version is the model's identity.

---

## Carry-forward notes for Piece 4

Three constraints established while building Pieces 1-3. All have already
caused a wrong number once.

**1. Filter candidate-vs-current by `model_version`, never `model_pkl`.**
`model_pkl` is null for every back-filled row, so filtering on it silently
drops legitimate baseline data — `--model dpv1.pkl` returns 12 races where
`--model dpv1.2.0-4track` returns 29. A promotion comparison run on the
filename would be judged against less than half the available baseline.

**2. Normalise every timestamp to UTC before comparing.** `parsed_files.parsed_at`
is UTC, the pickle's `trained_at` is UTC with an offset, picks-file stamps and
file mtimes are local (UTC-5 here). Comparing across those unconverted is what
produced the wrong provenance conclusion for ELP 8/22-8/23. Piece 4 compares
timestamps in at least three places — new-PDF detection, the corpus cutoff, and
model-artifact age — so it should add a `to_utc()` helper to `dpv1_runtime.py`
and route every comparison through it rather than repeating the fix.

**3. Expected baseline is ~57%, not 69%.** The out-of-corpus aggregate is
20/29 = 69.0%, and it is honest, but ELP 2026-08-23's 8-for-8 carries it.
Excluding that card, the remaining 21 races run **12/21 = 57.1%** — the more
realistic figure for Piece 4 to treat as the expected baseline. Neither number
is enough sample to gate a promotion on. Piece 4 should require a materially
larger window before its recommendation means anything, and should say so in
its output rather than reporting a delta on 29 races as if it were decisive.

---

## Addendum: `shipper_flag` and `corpus_coverage` (Phase 6D groundwork)

`card_picks.py` gained two more logged fields on 2026-08-29. Piece 3 does not
read them yet; they are logged now so that a window exists to analyse later.

| field | type | notes |
|---|---|---|
| `shipper_flag` | bool | corpus coverage < 60% **and** < 2 prior starts across CT/ELP/GP/MNR |
| `corpus_coverage` | float | per-horse coverage **before** the PP bridge runs |

`coverage` remains the post-bridge figure shown in the table, so a row can
legitimately read `shipper_flag: true` with `coverage: 0.64` — the flag was
decided on `corpus_coverage: 0.46`. The two are different measurements and
both are kept.

Rationale and the underlying gap are in `PHASE_6D_ROADMAP.md`. When enough
cards accumulate, the question worth asking is the ITM rate of flagged horses
against unflagged — that is the empirical case for or against wiring
`pp_entries_raw` into the feature builder.
