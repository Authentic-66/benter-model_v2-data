# Phase 4B — DPv1 Multi-Track Feature Engineering

**Date:** 2026-07-31
**Corpus:** `scripts/racing_full.db` — GP + CT + MNR, 28,105 races / 207,976 entries
**Config:** `scripts_dpv1/dpv1_feature_config.json` (version `dpv1.1.0`)
**Output:** `entry_features_dpv1` — 207,976 rows × 108 features
**Validation:** `python scripts_dpv1/validate_dpv1_features.py` → **ALL CHECKS PASS**

---

## 1. Headline

Doug's 154-feature ranking now drives the pipeline. 108 features are active and
written; every one of them is either something Doug ranked 1 or 2, or a
cross-track feature the 3-track corpus made possible for the first time.

Three things came out of this phase that were not on the task list and matter
more than most of the feature work:

1. **The MNR Q4 2024 gap is still open.** The 47 files have not actually been
   re-downloaded — they are still Equibase anti-bot HTML. MNR remains at 5,514
   races, not the expected ~5,800. Details in §2.
2. **A row-alignment bug in the Phase 3C feature builder** silently scrambled
   ~24 aggregate features — including four Doug ranked 1 — across entries.
   Measured hit rate against SQL ground truth: **9.8%**, i.e. chance. DPv1 does
   not inherit it, but Phase 3C/3E/3G model results are affected. Details in §7.
3. **Speed figures were GP-only and track-blind.** `computed_speed_figures` had
   zero rows for CT and MNR, so `last_race_speed_figure` (rank 1) was NULL for
   44% of the corpus. Fixed with a track-aware recompute. Details in §4.

Doug's own rank-1 handicapping intuitions hold up strongly against the data —
including the specific interaction he described in his notes. See §8.

---

## 2. Task 1 — MNR Q4 2024 reload: **gap NOT closed**

The brief stated "Doug's Q4 2024 MNR PDFs now downloaded (previously missed 47
dates)". That is not the case on disk.

Checked all 736 files under `Mountaineer/` by magic bytes:

| Year directory | Files | Real PDFs | Anti-bot HTML |
|---|---:|---:|---:|
| mnr-results-2021 | 133 | 133 | 0 |
| mnr-results-2022 | 132 | 132 | 0 |
| mnr-results-2023 | 124 | 124 | 0 |
| **mnr-results-2024** | **174** | **127** | **47** |
| mnr-results-2025 | 120 | 120 | 0 |
| mnr-results-2026 | 53 | 52 | 1 |

The 47 bad files are the same contiguous run (2024-10-10 → 2024-12-31), all
exactly 6,058 bytes, all beginning `<` rather than `%PDF`, all last modified
2026-07-30. Two files in that date range (`20241209`, `20241211`) *are* valid
PDFs and were re-fetched 2026-07-31 — but they were never in the failure list,
so nothing new was gained.

The loader was re-run anyway to pick up anything newly available:

```
python db_loader.py pipeline --db racing_full.db --schema db_schema.sql \
  --pdf-dir ..\Mountaineer --cache mnr_cache --resume
→ 688 ok, 0 skipped, 48 err
```

**MNR totals unchanged: 5,514 races / 37,080 entries.** The expected increase to
~5,800 did not happen and cannot happen until the files are actually downloaded.

One side effect was cleaned up: passing a relative `--pdf-dir` meant `--resume`
matched nothing (the DB stores absolute paths for MNR), so the run re-parsed all
688 files and inserted 48 duplicate failure rows under relative paths. Ingest is
idempotent so race/entry counts were untouched; the duplicate `parsed_files` rows
were deleted and provenance is back to 3,111 success / 51 failure.

> **Action for Doug:** re-download those 47 dates before Phase 4D. Until then,
> MNR Q4 2024 is a blind spot — it is a fourth-quarter run, so it biases the MNR
> slice seasonally, not just in volume.

---

## 3. Task 2 — Doug's ranked catalog

`DPv1_Feature_Ranking.xlsx`, sheet *Doug Parks v1 Feature Ranking*: 154 rows,
153 unique feature names (`is_first_time_lasix` is listed twice — kept once at
its stronger rank).

| Doug's rank | Count | Policy |
|---|---:|---|
| 1 — must have | 24 | active |
| 2 — important | 75 | active |
| 3 — nice to have | 45 | built where cheap, `active: false` |
| 4 — maybe | 7 | skipped |
| 5 — skip | 2 | skipped |

Rank 1 shows 24 rather than 23 because `starts_at_track` was left unranked. It
is the denominator companion of `wins_at_track` (rank 1) and is meaningless
without it, so it inherits rank 1 — flagged in the config as
`rank_inherited_from: wins_at_track` rather than assumed silently.

**The "Include in DPv1?" column is empty for all 154 rows**, so rank alone drives
activation, as specified.

All ten of Doug's handicapping notes are preserved verbatim in the config under
`doug_notes`, and each one is quoted in the docstring of the module that
implements it — they are design constraints, not commentary. Two of them changed
the implementation (see §5).

---

## 4. Tasks 3 & 5 — Config and pipeline

### Config: `dpv1_feature_config.json` (`dpv1.1.0`)

Generated, not hand-written — `build_dpv1_config.py` reads the spreadsheet, so
re-running it after Doug revises a rank updates the active set automatically.
Each feature carries `doug_rank`, `doug_notes`, `bucket`, `type`, `implemented`,
`active`, plus the Phase 3C status and v2 activation for traceability.

A rank 1-2 feature the corpus cannot support is **not dropped silently** — it is
written `active: false` with an explicit reason, so the gap is visible in the
config itself:

| Feature | Rank | Status | Reason |
|---|---:|---|---|
| `recent_bullet_workout` | 2 | blocked | No workout data in Equibase result charts. Needs a Brisnet/DRF PP feed. |
| `pedigree_index` | 2 | deferred | v10 workbook composite — Phase 4D |
| `sire_dirt_index_v10` | 2 | deferred | v10 workbook — Phase 4D |
| `sire_turf_index_v10` | 2 | deferred | v10 workbook — Phase 4D |
| `sire_first_time_turf_flag` | 2 | deferred | Doug-curated v10 sire list — Phase 4D |

`recent_bullet_workout` is the single highest-value gap. Doug's note on it is
specific — *"Depends on the distance of the workout, how many other horses
worked at that distance that day, how many workouts the horse had and timing of
the work"* — and none of that exists in a result chart. Three further rank-3
features (`days_since_last_workout`, `workout_frequency_30d`,
`trainer_workout_pattern`) are blocked for the same reason. A PP feed would
unblock four ranked features at once; nothing else in the catalog is gated on a
single missing source like this.

### Pipeline: `feature_builder_dpv1.py`

```
python scripts_dpv1/feature_builder_dpv1.py build      # ~74s, 207,976 rows
python scripts_dpv1/validate_dpv1_features.py          # all checks
```

* Queries all three tracks from `racing_full.db` in one pass.
* Reuses the Phase 3C builder for buckets 1, 2, 6 and 7 by importing it —
  `scripts/` and `scripts_v2a/` are not modified. Buckets 3, 4 and 8 are
  re-implemented in `new_features/aggregate_features.py` for the reason in §7.
* Where a feature exists in both, the **DPv1 implementation wins** — the merge
  logs anything it supersedes.
* **Fails loudly** if any active feature is not produced, naming it and its
  rank, rather than shipping a table quietly missing a rank-1 column.
* Time-decay half-life for aggregates raised to **730 days** per the Phase 4B
  spec (Phase 3C used 180).

### Track-aware speed figures: `speed_figures_dpv1.py`

`scripts/speed_figure_calculator.py` keys par times on
`(surface, distance, condition)` with **no track in the key**. Correct for a
GP-only corpus; wrong here — Charles Town is a 4.5f bullring, Mountaineer a
one-mile oval, Gulfstream a mile-and-an-eighth. Pooling their final times gives
CT horses systematically low figures purely for where they ran. It had also only
ever been run on GP: `computed_speed_figures` held 116,311 rows — exactly the GP
entry count — so `last_race_speed_figure` (rank 1) was NULL for every CT and MNR
entry.

`computed_speed_figures_dpv1` recomputes with track in the par key, into a new
table (the v1 table is left intact for reproducing Phase 3 results):

| Track | Entries with a figure | Mean | Std |
|---|---:|---:|---:|
| GP | 98,756 (84.9%) | 76.93 | 7.94 |
| CT | 46,770 (85.7%) | 77.12 | 7.85 |
| MNR | 30,677 (82.7%) | 76.86 | 7.88 |

The three distributions now sit on top of each other, which is exactly what
track-relative pars should produce and is the evidence the fix worked. The
missing ~15% is entries with a NULL beaten-margin (chart didn't report one) —
left NULL, not imputed.

---

## 5. Task 4 — New features built

23 rank 1-2 features that did not previously exist, plus 14 cross-track
additions. Doug's notes changed two implementations:

**`distance_specialist_flag`** — the catalog description says "horse has
multiple wins at this distance", but Doug's note says *"If a majority of the
horse's success **or ITM standings** come at the distance of their current race,
it matters"*. Implemented to Doug's reading: fires when a majority of the
horse's prior **in-the-money** finishes came at today's distance bucket, with a
minimum of two prior ITM finishes so a single lucky board hit doesn't make every
horse a specialist. Same treatment for the surface and track variants.

**`last_race_was_maiden`** — Doug's note is specifically about a horse that
*won* its maiden and is now facing winners. The flag is built to be read
together with `last_race_won` rather than alone; §8 shows that interaction is
real and large.

### Bucket 3 — Recent form
`class_change_from_last` (R1), `last_race_won` (R1), `last_race_troubled_trip`,
`last_race_was_maiden`, `distance_specialist_flag`, `surface_specialist_flag`,
`track_specialist_flag`, `purse_change_from_last`, `second_race_back_pattern`,
plus support columns `class_score` and `class_score_change_from_last`.

**Class ladder.** `races.class_level` is NULL for all 28,105 races, so class had
to be derived: `class_score = tier × 10 + within-tier offset (0-9)`. Tier comes
from the race type (maiden claiming 1 → stakes 7). Claiming races are positioned
by claiming tag, which is track-independent — a $10k claimer is a $10k claimer
anywhere. Non-claiming races are positioned by log purse, which *is*
track-sensitive; an MNR allowance genuinely draws weaker company than a GP
allowance, so a horse shipping down registering a class drop is intended
behaviour. A ±3-point deadband keeps purse jitter from reading as a class move.

**Trouble detection** (`troubled_trip_detector.py`) — trip comments are present
on 100% of entries, the highest-coverage new signal in the corpus. Five trouble
categories (gate, contact, stopped, altered, catastrophe) matched against
Equibase's run-together abbreviations. Wide trips and self-inflicted drifting
are detected but deliberately *excluded* from the trouble flag — a wide trip is
a tactical outcome, not an incident — and remain available as separate
categories if Doug wants them folded in.

### Bucket 6 — Race dynamics
`pace_progression_last_race`, `early_pace_position_projected`,
`pace_pressure_in_race`, `running_style_last_3`, `equipment_change_flag`,
`blinkers_change_flag`, `lasix_off`, `is_first_time_lasix` / `lasix_first_time`.

`pace_pressure_in_race` describes today's race but is built only from each
entrant's **prior** starts — no part of today's result is consulted.

The equipment flags are derived rather than read off the chart:
`entries.first_time_blinkers` and `first_time_bandages` are **0 across all
207,976 rows** — the parser's uppercase-code convention never fires because
these charts use lowercase equipment codes only. Rather than ship a rank-2
feature that is constant, the flags come from comparing today's equipment string
against the horse's previous start.

### Bucket 1 — Race context
`distance_change_bucket` (4-way, per Doug's note about fitness carrying over
from routes to sprints), `track_code`.

### Bucket 7 — Market
`market_probability_normalized` (R1) — implied probabilities normalised to sum
to 1 within each race, removing the overround. Verified: **27,569 / 27,569 races
sum to 1.0**.

### Bucket 8 — Cross-track (new, not in Doug's 154)
`trainer_at_other_tracks_winrate`, `jockey_at_other_tracks_winrate`,
`horse_shipping_success_rate`, `trainer_home_track`, `jockey_home_track`, plus
`is_at_*_home_track`, `is_shipping_today`, and the `_starts` sample-size
companions.

All prior-only: "home track" is the home track *as of that race*, so a trainer
who relocates mid-corpus shows the move rather than being retro-labelled.

---

## 6. Task 6 — Validation

`validate_dpv1_features.py` runs six checks, any of which fails the run.

```
[1] ROW INTEGRITY          PASS   207,976 rows = entries in DB, 0 duplicates
[2] COVERAGE PER TRACK            51/108 features ≥90%, 94-100/108 ≥50%
[3] DEAD FEATURES          PASS   0 all-null, 0 constant
[4] DISTRIBUTION SANITY    PASS   0 rate features outside [0,1]
                                  27,569/27,569 races: market probs sum to 1
[5] BAYESIAN SHRINKAGE     PASS   dispersion grows monotonically with n
[6] LEAKAGE PROBE          PASS   0 prior-form features set on first-time starters
```

### Coverage distribution (108 features)

| Coverage band | Features |
|---|---:|
| ≥99% | 42 |
| 90-99% | 9 |
| 70-90% | 36 |
| 50-70% | 8 |
| <50% | 13 |

Per track, features at ≥90% coverage: **GP 51, CT 52, MNR 51** — near-identical,
which is the important result. There is no track that is systematically
under-served by the feature set.

### Where the missing data actually is

Low coverage here is almost entirely **structural**, not broken. The dominant
pattern: 32,822 entries (15.8%) are a horse's first appearance in the corpus, so
every last-race feature is legitimately NULL. That sets a natural ceiling of
~84% on the whole prior-form family, and that family clusters tightly at
81-88% — exactly at the ceiling.

The genuinely low-coverage features and why:

| Feature | Cov. | Cause |
|---|---:|---|
| `sire_first_time_starter_win_pct` | 6.0% | Only meaningful on debut runs (15.8%) *and* needs a known sire (70%) |
| `horse_shipping_success_rate` | 10.2% | Only 3,467 horses have ever shipped between these tracks |
| `trainer_*_class_win_pct` (4) | 12.5-15.8% | By design — reported only when the horse is actually in that situation today |
| `track_turf_bias_90d` | 20.5% | CT has **no turf course** (0.0% there); MNR runs turf rarely |
| `trainer/jockey_at_other_tracks_winrate` | 32% | NULL when a connection has never left this track — see below |
| `sire_*_win_pct` | 31-46% | Sire known for 70% of entries, then split by surface/distance |
| `speed_trajectory_3_races` | 48.2% | Needs 3 prior starts *with* speed figures |

The `_starts` sample-size companions are at 100% everywhere, so the model can
always tell "no cross-track record" from "poor cross-track record" — the NULL is
informative and paired with a count that isn't.

### Bayesian shrinkage

| `trainer_starts_30d` | n | mean | std | mean &#124;rate − prior&#124; |
|---|---:|---:|---:|---:|
| 0 | 10,657 | 0.1200 | 0.0000 | 0.0000 |
| 1-4 | 49,294 | 0.1182 | 0.0218 | 0.0176 |
| 5-19 | 97,018 | 0.1230 | 0.0384 | 0.0303 |
| 20-59 | 47,098 | 0.1536 | 0.0535 | 0.0491 |
| 60+ | 3,909 | 0.1864 | 0.0555 | 0.0723 |

Behaving correctly: at zero evidence the estimate is exactly the 0.12 prior with
zero variance; dispersion and distance from the prior both grow monotonically
with sample size. No trainer with 2 wins from 3 starts is being handed a 67%
win rate.

---

## 7. Bug found in the inherited Phase 3C feature builder

**This is the most consequential finding of the phase and it affects existing
model results, not just DPv1.**

`_prior_by_entity_expanding` and `_prior_by_entity_windowed` in
`scripts/feature_builder.py` return rows sorted by `(entity, race_date,
entry_id)` with a fresh `RangeIndex`. Several call sites then assign the result
straight onto an entry-ordered frame:

```python
rolled = _prior_by_entity_expanding(df_w, "horse_id", ["one"], "horse")
out["career_starts"] = rolled["horse_one"]      # positional — not joined on entry_id
```

`out` is in `entries.id` order; `rolled` is in horse order. The values land on
the wrong rows.

**Measured** against a SQL ground-truth count of prior starts, on a sample of
entries:

| Method | Matches ground truth |
|---|---:|
| v1 positional assignment | **9.8%** |
| merged on `entry_id` | **100%** |

9.8% is chance. Affected v1 outputs — roughly two dozen features:

* `career_starts`, `career_wins`, `career_win_pct_shrunk`, `career_itm_pct_shrunk` — **all rank 1**
* every trainer/jockey rolling window rate (30/90/365d) and `_starts_30d`
* every trainer/jockey `at_track` / `at_surface` / `at_distance` rate
* `trainer_recent_form_trend`, the trainer×jockey combo features
* `starts_at_track`, `wins_at_track` (**rank 1**), `historical_surface_winrate_shrunk`, `historical_condition_winrate_shrunk`

Features derived via `_prior_last_value` (all `last_race_*`, weight/distance
deltas, gate break) merge on `entry_id` in v1 and are **not** affected.

**In DPv1:** buckets 3, 4 and 8 are re-implemented in
`new_features/aggregate_features.py`, joined on `entry_id` throughout. The
leakage probe went from 18 features carrying values on first-time starters to
zero, which is the independent confirmation the fix landed.

**Not fixed in `scripts/`** — the brief says preserve v2/v2a as reference and do
not modify them, so I have left it alone and documented it here instead.

> **Action for Doug — decision needed.** Phase 3C's `entry_features_v1` table
> and therefore the Phase 3E and 3G models (`benter_v2.pkl`, `benter_v2a.pkl`)
> were trained on scrambled connection and career features. Their reported
> metrics are not trustworthy as a baseline for DPv1 comparison. Options: (a)
> patch `scripts/feature_builder.py` and rebuild the v1 table to get an honest
> baseline, or (b) accept DPv1 as the new baseline and retire the v2 numbers.
> I'd recommend (a) — it is a handful of one-line changes and without it there
> is no valid "did DPv1 improve on v2?" comparison in Phase 4C.

A second, smaller issue in the same file: v1 emitted `0` rather than NULL for
`surface_change_from_last_race` on first-time starters — asserting "no change"
for a horse with nothing to change from. DPv1 overrides it with NULL semantics.
Two v1 bucket-1/2 features inherited into DPv1 have the same pattern at low
stakes: `is_sealed_track` and `is_florida_bred` return 0 where the underlying
field is NULL (536 races with no track condition; horses with no foaling place).
Left as-is for now, noted here.

---

## 8. Do Doug's rank-1 intuitions hold up?

Signal checks against ITM outcome across all 207,976 entries. These are raw
marginals, not model coefficients — but they are the right first test of whether
a feature encodes what Doug thinks it encodes.

**`class_change_from_last`** — *"A significant change in class, up or down, is a
big factor imo"*

| Class move | ITM rate | n |
|---|---:|---:|
| DOWN | **45.2%** | 26,641 |
| SAME | 40.7% | 121,590 |
| UP | **36.1%** | 25,936 |

Cleanly monotone across a 9-point spread. The derived class ladder is measuring
something real.

**`last_race_won`** — *"winning multiple races in a row is difficult, unless the
horse really is that good, and especially if/as it moves up in class"*

| Won last out | ITM rate | n |
|---|---:|---:|
| No | 39.4% | 149,296 |
| Yes | **48.9%** | 24,288 |

And the second half of Doug's sentence — the interaction — is the striking one:

| Won last out | Class move | ITM rate | n |
|---|---|---:|---:|
| Yes | DOWN | **59.3%** | 1,331 |
| Yes | SAME | 55.1% | 10,674 |
| Yes | **UP** | **42.4%** | 12,279 |
| No | DOWN | 44.5% | 25,180 |
| No | SAME | 39.3% | 110,511 |
| No | UP | 30.4% | 13,586 |

A horse that won last time out and steps up in class drops from 55% to 42% ITM —
a 13-point penalty, and it lands within a point of a horse that *didn't* win but
stays at the same level. That is precisely the effect Doug described in his note,
recovered from the data without being told to look for it. It is also a strong
argument for giving Phase 4C an explicit `last_race_won × class_change`
interaction term rather than trusting a linear model to find it.

**`last_race_troubled_trip`** — 39.1% ITM after a troubled trip vs 41.0% after a
clean one. Weak and in the *opposite* direction to the usual "forgive the
trouble" read. Honest assessment: the flag is currently detecting "ran badly"
more than "was unlucky". It is kept active (Doug ranked it 2 and it is
information-bearing when paired with `pace_progression_last_race`, as his own
note suggests), but it should not be expected to carry weight on its own, and
the five trouble sub-categories are the obvious thing to try next if Phase 4C
finds it dead.

---

## 9. Cross-track feature analysis

The corpus supports these far better than the 248 three-track horses suggested:

* **3,467 horses** raced at more than one track (3,219 at two, 248 at all three)
* **433 trainers** operate at more than one track — covering **102,435 entries
  (49.3%)**
* Cross-track connection features carry a value on **32%** of all entries

### Coverage

| Feature | All | GP | CT | MNR |
|---|---:|---:|---:|---:|
| `trainer_at_other_tracks_starts` | 100.0% | 100.0% | 100.0% | 100.0% |
| `trainer_at_other_tracks_winrate` | 32.2% | 17.2% | 58.0% | 41.1% |
| `jockey_at_other_tracks_winrate` | 32.6% | 18.5% | 57.2% | 40.6% |
| `trainer_home_track` | 98.9% | 99.2% | 98.9% | 98.3% |
| `jockey_home_track` | 99.5% | 99.5% | 99.5% | 99.2% |
| `is_shipping_today` | 84.2% | 81.1% | 88.5% | 87.7% |
| `horse_shipping_starts` | 100.0% | 100.0% | 100.0% | 100.0% |
| `horse_shipping_success_rate` | 10.2% | 0.5% | 16.9% | 31.0% |

The GP/CT-MNR asymmetry is the real structure of the circuit, not a defect:

| Track today | Trainer's home = GP | = CT | = MNR |
|---|---:|---:|---:|
| GP | **99.7%** | 0.1% | 0.2% |
| CT | 0.9% | **97.4%** | 1.7% |
| MNR | 2.0% | **6.3%** | 91.7% |

Gulfstream is a closed shop — 99.7% of GP starters come from GP-based barns, so
`trainer_at_other_tracks_winrate` is NULL for 83% of GP entries. CT and MNR are
40 miles apart and share a barn population heavily: 6.3% of MNR starters are
sent by CT-based trainers, and 58% of CT entries have a trainer with a
cross-track record. **This feature will do most of its work on the CT/MNR
circuit and very little at GP** — worth knowing before Phase 4C interprets its
importance.

### Two findings worth carrying into Phase 4C

**Shipping is mildly positive.** Horses shipping in go 43.4% ITM vs 40.6% for
horses staying put (n=5,444 vs 168,747).

**Trainers do better away from home** — 44.7% ITM off their home track vs 39.9%
at it (n=4,773 vs 199,687). Counter-intuitive at first, but it is almost
certainly selection: a barn only vans a horse 40 miles when it thinks the horse
is well spotted. That makes `is_at_trainer_home_track` a **proxy for trainer
intent**, which is a genuinely useful thing for an ITM model to have and is not
available at all in a single-track corpus. It also means the feature should not
be read as "trainers are better away" — worth a note when Doug reviews feature
importances.

---

## 10. Sample race spot check

**MNR, 2026-07-22, race 6** — $5,000 claiming, 6f dirt, fast, 7 starters.
Chosen because it contains two shippers and every runner has prior starts, so
the cross-track and prior-form columns are all exercised.

| Fin | Horse | Odds | Class chg | Δ | Won last | Last fin | Last SF | Dist chg | Career | Trn home | At home | Ship | Mkt prob |
|---|---|---:|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|
| 1 | Lomachenko | 9.7 | **DOWN** | −30 | 0 | 3 | 73.5 | route→sprint | 16 | MNR | 1 | 0 | 0.075 |
| 2 | Poppy's Pride | 3.6 | **DOWN** | −33 | 0 | 4 | 86.8 | sprint→sprint | 14 | MNR | 1 | **1** | 0.174 |
| 3 | Roadto Stardom | 15.2 | SAME | −1 | 0 | 6 | 78.4 | sprint→sprint | 21 | MNR | 1 | 0 | 0.049 |
| 4 | Belts'n Brooks | 16.5 | SAME | 0 | 0 | 4 | 77.7 | route→sprint | 29 | **GP** | **0** | **1** | 0.046 |
| 5 | Gavea | 0.5 | SAME | −1 | 0 | 2 | 79.4 | sprint→sprint | 2 | MNR | 1 | 0 | 0.534 |
| 6 | Big Producer | 6.4 | SAME | +2 | 0 | 4 | 73.6 | sprint→sprint | 5 | MNR | 1 | 0 | 0.108 |
| 7 | Weekend Flame | 55.4 | SAME | +2 | 0 | 8 | 74.9 | sprint→sprint | 13 | MNR | 1 | 0 | 0.014 |

Everything reads correctly:

* Market probabilities sum to **1.000** across the field.
* The two horses dropping sharply in class ran 1-2, at 9.7-1 and 3.6-1, while
  the 0.5-1 favourite ran fifth — a nice small illustration of why Doug ranked
  class change a 1.
* **Belts'n Brooks** is the cross-track case: a GP-based barn, a CT-based
  jockey, shipping in to MNR. Exactly the row that is featureless in a
  single-track corpus.
* `horse_shipping_success_rate` is populated only for the two horses with prior
  ships (0.422, 0.436) and NULL for the rest — no fabricated values.
* `starts_at_track` / `wins_at_track` are consistent with each horse's career
  count, and both shippers correctly show 0 prior MNR starts.

---

## 11. Recommendations for Phase 4C (ITM model training)

**Blocking — resolve first**

1. **Decide on the Phase 3C bug (§7).** Without a rebuilt v1 baseline there is
   no honest "DPv1 vs v2" comparison. Recommend patching
   `scripts/feature_builder.py` and rebuilding `entry_features_v1`.
2. **Re-download the 47 MNR Q4 2024 dates (§2).** A missing fourth quarter is a
   seasonal hole, not just a volume shortfall.

**Modelling**

3. **Add an explicit `last_race_won × class_change_from_last` interaction.** The
   effect in §8 is 13 points and Doug predicted it in writing. Don't rely on a
   linear model to recover it.
4. **Include `track_code` as a fixed effect.** Base ITM rates and field sizes
   differ enough between GP and the CT/MNR bullrings that pooling without it
   will bias the intercept.
5. **Expect cross-track features to matter at CT/MNR and not at GP** (§9). If
   feature importance is computed pooled, their GP NULLs will dilute them —
   compute importances per track as well.
6. **Use `_starts` companions as gates, not just features.** Every shrunk rate
   ships with its sample size; a tree model given both can learn "trust this
   rate only above n=20" directly.
7. **Handle NULL honestly in the model too.** 13 features sit under 50%
   coverage. Native-NaN learners (LightGBM/XGBoost) are strongly preferred over
   imputing, which would undo the pipeline's whole NULL discipline.

**Feature work, if time allows**

8. **Split `last_race_troubled_trip` into its five categories** (§8). The
   aggregate flag is weak and directionally odd; `catastrophe` and `stopped`
   plausibly behave very differently from `contact`.
9. **Consider activating the 45 rank-3 features as an ablation.** 31 of them are
   already implemented and one config edit away — a cheap test of whether Doug's
   3-vs-2 boundary is where the model agrees the value stops.
10. **Chase a PP feed for workouts (§4).** It is the only single source that
    would unblock four ranked features, one of them a rank 2.

---

## 12. Files delivered

```
scripts_dpv1/
├── dpv1_common.py                    shared primitives: class ladder, pace, bucketing
├── build_dpv1_config.py              spreadsheet -> config generator
├── dpv1_feature_config.json          dpv1.1.0 — 153 catalogued, 108 active
├── speed_figures_dpv1.py             track-aware par times -> computed_speed_figures_dpv1
├── feature_builder_dpv1.py           main pipeline -> entry_features_dpv1
├── validate_dpv1_features.py         6-check validation suite
├── dpv1_validation.json              machine-readable validation results
├── PHASE_4B_MULTITRACK_FEATURES.md   this report
└── new_features/
    ├── __init__.py
    ├── aggregate_features.py         career/connection/at-track — supersedes buggy v1 paths
    ├── class_change_features.py      class ladder, class + purse movement
    ├── cross_track_features.py       the 3-track payoff
    ├── equipment_features.py         lasix / blinkers / equipment changes
    ├── pace_bias_features.py         pace projection + track bias
    ├── pedigree_features.py          sire / broodmare-sire progeny rates
    ├── recent_form_features.py       last_race_won, specialist flags, bounce pattern
    └── troubled_trip_detector.py     trip-comment trouble taxonomy
```

New DB tables: `entry_features_dpv1` (207,976 × 115), `computed_speed_figures_dpv1`
(207,976). Nothing in `scripts/` or `scripts_v2a/` was modified; `entry_features_v1`
and `computed_speed_figures` are untouched.

---

## 13. Decision point

Per the Phase 4B brief:

* **Features build cleanly** — 108/108 active features produced, all six
  validation checks pass, no dead or constant columns.
* **Cross-track coverage is workable but asymmetric** — 32% overall, concentrated
  on the CT/MNR circuit. Not a defect; it needs to be understood before Phase 4C
  reads feature importances.
* **Two items need Doug's decision before training**: the Phase 3C alignment bug
  (§7) and the MNR Q4 2024 download gap (§2).

Recommend **checkpointing here** for Doug to review the active feature list and
rule on the v1 rebuild, then proceeding to Phase 4C.
