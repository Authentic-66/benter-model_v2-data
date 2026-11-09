# Same-day features audit (read-only), 2026-11-09

**Question (Doug, 2026-11-08):** which features can see results from earlier
races on the same day, how many training rows that affects, and how different
the value would be if it were computed as of the start of the race day.

**Answer.** Two of the 1.3.2 features, `days_since_jockey_last_win` and
`days_since_trainer_last_win`. Every other jockey, trainer and track feature
already uses only earlier dates; recomputing them as of the start of the day
gives the stored values exactly. The two affected features are **not** a mild
leak by row count: about 19% of training rows for the jockey feature and 8%
for the trainer feature have a NULL in training where the start-of-day value
is a number. For about 2,700 trainer rows, the result that causes the NULL
comes from **the row's own race**.

Live card rows are not affected, because a card has no results when it is
scored. The problem is that training and live rows mean different things by
NULL. Nothing was changed. This is a 1.4 candidate item (PHASE_6D_ROADMAP).

Script: `tracking/same_day_audit_2026-11-09.py`. It opens the live DB
read-only and uses its own code (per-day totals), not the feature builder.
Training rows = the 1.3.2 training frame: 2022-01-01 on,
GP/CT/MNR/ELP/DED, races that have been run (183,516 rows).

## 1. Which features read same-day races

The builder looks up past rows with four helpers
(`scripts/feature_builder.py`). All the code in `feature_builder_dpv1.py` and
`new_features/` goes through them:

| helper | "prior" means | same-day results visible? |
|---|---|---|
| `_prior_by_entity_expanding` (via `grouped_prior_rate`) | dates strictly earlier | no |
| `_prior_by_entity_windowed` | dates strictly earlier, within N days | no |
| `_prior_last_value` | the previous row, used only if its date is earlier | no* |
| `_prior_days_to_event` | rows in (date, entry_id) order, **including earlier ids the same day** | **yes** |

\* For a jockey or trainer, `_prior_last_value` gives NULL on every ride after
their first that day, because the previous row is from the same day. It does
not leak. The only 1.3.2 features that use it are keyed on the horse
(`new_trainer_flag`, last-race features), and a horse runs once a day. The
inactive `jockey_won_last_race` / `trainer_won_last_race` would hit it.

The 1.3.2 jockey/trainer features and their helpers:

* **Same-day results visible (`_prior_days_to_event`):**
  `days_since_jockey_last_win`, `days_since_trainer_last_win`.
* **Earlier dates only:**
  * `jockey_/trainer_` `30d/90d/365d_winrate_shrunk`, `starts_30d`,
    `recent_form_trend` (windowed);
  * `at_track/at_surface/at_distance_winrate_shrunk` (grouped);
  * `at_other_tracks_winrate/starts`, `home_track`, `is_at_*_home_track`
    (expanding);
  * the trainer situation rates (dropping class, rising class, off layoff,
    first-time starters; grouped);
  * `new_trainer_flag` (horse's previous row).
* **Other prior-row features:** track bias (`track_dirt/turf_bias_90d`,
  rail/outside/running-style bias) uses windowed, earlier dates only. Horse
  features have no same-day rows.

## 2. Check against the stored table (all 326,195 rows)

A start-of-day value was recomputed for each feature. It counts wins and
starts on dates strictly before the race date, then applies the same
shrinkage, and is compared with `entry_features_dpv1`.

| feature | rows differing (all) | rows differing (training) |
|---|---|---|
| jockey / trainer 30d, 90d, 365d win rate | 0 | 0 |
| jockey / trainer starts_30d | 0 | 0 |
| jockey / trainer at-track win rate | 0 | 0 |
| **days_since_jockey_last_win** | **64,638 (19.8%)** | **35,192 (19.2%)** |
| **days_since_trainer_last_win** | **26,335 (8.1%)** | **15,323 (8.3%)** |

Every difference is the same kind: the stored value is NULL and the
start-of-day value is a number. There are no rows where both are numbers and
differ.

## 3. The two affected features in training rows

| | jockey | trainer |
|---|---|---|
| training rows | 183,516 | 183,516 |
| stored NULL, all reasons | 39,015 | 22,571 |
| ... because of a same-day win (start-of-day value exists) | **35,192 (90% of NULLs)** | **15,323 (68% of NULLs)** |
| ... genuinely no earlier win | 3,823 | 7,248 |
| start-of-day value on affected rows: median (IQR) | 4 days (1-7) | 6 days (2-13) |
| affected rows within 7 days of a win | 81% | 63% |
| ITM rate, affected rows | **43.6%** | **46.1%** |
| ITM rate, the other NULL rows | 27.2% | 30.0% |
| ITM rate, all training rows | 39.9% | 39.9% |

Affected rows by year are steady, about 7-8k a year for jockeys and 3k for
trainers (2026 is a part year).

**Where the win comes from** (training rows that can see a same-day win):

| | earlier race | **same race** | later race |
|---|---|---|---|
| jockey | 35,345 | - | 2 |
| trainer | 12,675 | **2,690** | 50 |

* **Same race (trainer):** the trainer had two starters in the race and the
  other one won, with the lower entry id. The losing stablemate's row then
  reads that win and gets NULL. This is the row's own race result leaking
  into its input (the horse cannot have won). These rows run ITM 37.0%.
* **Later race:** comes from 24 of 4,855 race days where entry-id order is not
  race order.

## 4. What it does to the model

* The preprocessor fills a NULL with the training median (jockey 6 days,
  trainer 19 days) and sets a `__missing` indicator.
  * 1.3.2 coefficients: jockey value −0.0072 and missing −0.0009; trainer
    value −0.0189 and missing **−0.0473**.
  * Rank by absolute size: 188 and 135 of 230 for the values.
* **The jockey feature.** In training, the missing indicator means "won
  earlier today" 90% of the time (ITM 43.6%). Live, it means "has never
  won". The two groups have opposite form, and the near-zero coefficient is
  consistent with them cancelling. The real value on those rows (mostly
  1-7 days, a hot rider) was replaced by the median.
* **The trainer feature.** The NULL group is two-thirds hot barns (ITM 46%)
  and one-third trainers with no earlier win (ITM 30%). The −0.047 is
  therefore probably milder than a clean fit would give. On a live card, a
  trainer with no earlier win is then probably rated too high. This is an
  inference, not measured; the retrain will show it.
* **Size.** These are two low-ranked terms. No claim about how much ranking
  changes until a retrain is run.

## 5. Proposed fix (1.4 candidate, not started)

Compute both features **as of the start of the race day**:
* the last win on a date strictly before the race date;
* the same rule as every other connection feature.

This is a one-line rule change in `_prior_days_to_event`: record the event
date only after all of that entity's rows for the day have been passed. It
also removes the same-race leak and the 24-day ordering issue.

Live card rows do not change, because a card has no same-day results. Only
training rows and charted rows change, so the OFF switch reproduces 1.3.2's
logged runs by construction.

The incremental build (7b-1) would then no longer need same-day rows in
propagation or closure for these features. Keep them until the change is
live.
