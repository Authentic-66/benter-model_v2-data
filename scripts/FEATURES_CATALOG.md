# Feature Catalog — Benter Model v2

**Version 1.0.0 · Generated 2026-07-01**

This catalog documents every feature we might ever want the model to see.
The `scripts/feature_config.json` file mirrors this catalog and controls
which features are actually built by `feature_builder.py`; the two are
kept deliberately in lockstep. Set `"active": true` in the config to
turn a feature on for the next build.

## Design principles

- **NULL is honest.** If a horse has zero prior starts, its `career_win_pct` is
  NULL — never zero, never imputed. If a chart doesn't report a beaten-lengths
  margin, we don't guess.
- **Prior-only computation.** Every rolling or "career" statistic uses ONLY
  races strictly before the target race, and excludes same-day races on the
  same card. There is no look-ahead leakage.
- **Bayesian shrinkage** is applied to all rate features via the
  `shrink_rate_vec` utility in `bayesian_shrinkage.py`. Per-feature k values
  are configured in `feature_config.json → defaults.shrinkage_k_defaults`.
- **No cross-distance mixing.** Distance-sensitive computations (par time,
  distance-bucket rates) never average across sprint and route regimes.
- **Config-driven activation.** Every feature has an `active` flag. Turning
  on a "planned" feature is a single edit + rebuild.

## Taxonomy

Features are grouped into 8 buckets:

| # | Bucket | Focus |
|---|---|---|
| 1 | Race Context | The race itself — distance, surface, purse, race type, field size |
| 2 | Horse Immutable | Age, sex, country of origin |
| 3 | Recent Form | Last N starts, career totals, speed trajectory |
| 4 | Connections | Trainer, jockey, trainer × jockey aggregate rates |
| 5 | Pedigree | Sire, dam, damsire (deferred until Phase 3F v10 integration) |
| 6 | Race Dynamics | Post position, weight, pace type |
| 7 | Market Signals | Final tote odds and derived rank/probability |
| 8 | Track-Specific | Track bias, historical wins at this track/surface/condition |

## v1.0.0 snapshot

| Bucket | Cataloged | Active in v1 |
|---|---:|---:|
| 1 · Race Context | 16 | 12 |
| 2 · Horse Immutable | 6 | 4 |
| 3 · Recent Form | 16 | 12 |
| 4 · Connections | 22 | 20 |
| 5 · Pedigree | 12 | 0 |
| 6 · Race Dynamics | 13 | 11 |
| 7 · Market Signals | 9 | 6 |
| 8 · Track-Specific | 11 | 8 |
| **Totals** | **105** | **73** |

Bucket 5 (Pedigree) is intentionally all-off in v1: those features get built
from Doug's v10 workbook + Brisnet PP data in Phase 3F+.

---

## Bucket 1 — Race Context

Race-level attributes that apply to every entry in a given race. Mostly
straight-from-DB pulls; low computational cost.

| Feature | Active | Type | Source | Notes |
|---|---|---|---|---|
| `distance_yards` | ✅ | numeric | `races.distance_yards` | Race distance in yards. |
| `distance_furlongs` | ✅ | numeric | derived (yards / 220) | Convenient reading unit. |
| `surface` | ✅ | categorical | `races.surface` | Dirt / Turf / AllWeather / Tapeta. |
| `track_condition` | ✅ | categorical | `races.track_condition` | Fast, Firm, Good, Sloppy, Muddy, Yielding, WetFast. |
| `is_sealed_track` | ✅ | boolean | derived | True when condition ∈ {Sloppy, Muddy, WetFast}. |
| `purse` | ✅ | numeric | `races.purse` | USD, raw. |
| `log_purse` | ✅ | numeric | `log1p(purse)` | Smoother distribution for linear models. |
| `race_type` | ✅ | categorical | `races.race_type` | CLAIMING, ALLOWANCE, STAKES, MAIDEN, etc. |
| `claiming_price` | ✅ | numeric | `races.claiming_price` | Top claiming price; NULL for non-claiming. |
| `field_size` | ✅ | numeric | `races.field_size` | Starters, after scratches. |
| `month_of_year` | ✅ | categorical | derived from race_date | 1-12. Captures seasonal biases (GP meets, hot weather). |
| `day_of_week` | ✅ | cyclic | derived from race_date | 1-7. Weekday/weekend can matter for field quality. |
| `days_since_last_workout` | 🕓 | numeric | Brisnet PP (Phase 3G) | Freshness proxy from published works. |
| `weather_temperature_f` | 🕓 | numeric | `races.temperature_f` | Ambient temp — likely low signal for GP. |
| `is_stakes` | 🕓 | boolean | derived | Convenience flag; `race_type LIKE 'STAKES%'`. |
| `distance_change_bucket` | 🕓 | categorical | derived | sprint→sprint, sprint→route, route→sprint, route→route. |

---

## Bucket 2 — Horse Immutable

Attributes of the horse that don't change race-to-race.

| Feature | Active | Type | Source | Notes |
|---|---|---|---|---|
| `horse_age` | ✅ | numeric | derived from foaled_date | Years, fractional. NULL for unknown foaled dates and impossible negatives. |
| `horse_sex` | ✅ | categorical | `horses.sex` | Filly / Mare / Colt / Gelding / Horse. |
| `horse_country_origin` | ✅ | categorical | `horses.country` / `foaled_place` | USA, GB, IRE, FR, etc. |
| `is_florida_bred` | ✅ | boolean | `foaled_place = 'Florida'` | Florida-bred races at GP heavily favor state-breds. |
| `days_since_foaled` | 🕓 | numeric | derived | Overlaps `horse_age`; redundant. |
| `horse_color` | 🕓 | categorical | `horses.color` | Rarely predictive. |

**Coverage note.** In Phase 3A, horse pedigree info (`sex`, `color`, `foaled_date`,
`sire`, `dam`) is populated only when a horse appears as a race winner. That means
~64% of entries have `horse_age` and `horse_sex` — the horses that have never
won a race in the corpus lack this metadata. Phase 3H (multi-track expansion)
will likely raise this to >90% simply by adding more chances for the horse to
have won *somewhere*.

---

## Bucket 3 — Recent Form

Rolling-window and last-race features per horse. Every value is
"as-of" the target race and excludes future information.

| Feature | Active | Type | Source | Notes |
|---|---|---|---|---|
| `last_race_finish_pos` | ✅ | numeric | prior entry | Finish position last time out; NULL for first-time starters. |
| `last_race_beaten_lengths` | ✅ | numeric | prior entry | 0 for winner, NULL when chart omits margin. |
| `last_race_field_size` | ✅ | numeric | prior entry | Contextualizes the finish. |
| `last_race_days_ago` | ✅ | numeric | derived | Days between prior start and today. |
| `days_since_last_race` | ✅ | numeric | derived | Alias — same value, kept for legacy naming. |
| `career_starts` | ✅ | numeric | prior entries count | Total prior starts. |
| `career_wins` | ✅ | numeric | prior entries wins | Total prior wins. |
| `career_win_pct_shrunk` | ✅ | numeric | shrunk rate | prior 0.12, k=15. NULL if 0 prior starts. |
| `career_itm_pct_shrunk` | ✅ | numeric | shrunk rate | prior 0.35, k=15. NULL if 0 prior starts. |
| `last_race_speed_figure` | ✅ | numeric | `computed_speed_figures` via prior entry | Beyer-like scale (0-120). |
| `last_3_avg_finish` | ✅ | numeric | rolling(3) over prior finishes | Requires ≥ 1 prior start. |
| `speed_trajectory_3_races` | ✅ | numeric | (SF[-1] − SF[-3]) / 2 | Positive = improving; NULL for fewer than 3 prior starts. |
| `career_earnings_usd` | 🕓 | numeric | sum of win/place/show payouts | Proxy for class. |
| `career_avg_speed_figure` | 🕓 | numeric | mean of prior speed figures | Outlier-sensitive. |
| `last_race_won` | 🕓 | boolean | derived | Trivially derivable from `last_race_finish_pos`. |
| `last_race_was_maiden` | 🕓 | boolean | derived | Class-transition signal. |

---

## Bucket 4 — Connections

Trainer, jockey, and their combination. Rolling windows (30/90/365 day) and
all-time contextual rates (at track / surface / distance-bucket). Every
rate is Bayesian-shrunk toward the population win rate (0.12 default) so
brand-new trainers/jockeys get a sensible prior rather than 0.

| Feature | Active | Type | Notes |
|---|---|---|---|
| `trainer_30d_winrate_shrunk` | ✅ | numeric | Trainer's win rate in the last 30 days. k=20. |
| `trainer_90d_winrate_shrunk` | ✅ | numeric | 90-day window. |
| `trainer_365d_winrate_shrunk` | ✅ | numeric | 365-day window. |
| `trainer_at_track_winrate_shrunk` | ✅ | numeric | All-time at THIS track. k=30. |
| `trainer_at_surface_winrate_shrunk` | ✅ | numeric | All-time on THIS surface. k=25. |
| `trainer_at_distance_winrate_shrunk` | ✅ | numeric | All-time at this distance bucket. k=30. |
| `trainer_recent_form_trend` | ✅ | numeric | 30d rate minus 90d rate — positive = trainer heating up. |
| `trainer_starts_30d` | ✅ | numeric | Activity proxy (busy vs quiet trainer). |
| `days_since_trainer_last_win` | ✅ | numeric | Freshness of trainer's most recent win. |
| `jockey_30d_winrate_shrunk` | ✅ | numeric | Same recipe as trainer, k=20. |
| `jockey_90d_winrate_shrunk` | ✅ | numeric | |
| `jockey_365d_winrate_shrunk` | ✅ | numeric | |
| `jockey_at_track_winrate_shrunk` | ✅ | numeric | All-time at THIS track. k=30. |
| `jockey_at_surface_winrate_shrunk` | ✅ | numeric | k=25. |
| `jockey_at_distance_winrate_shrunk` | ✅ | numeric | k=30. |
| `jockey_starts_30d` | ✅ | numeric | Jockey's book size proxy. |
| `days_since_jockey_last_win` | ✅ | numeric | Freshness. |
| `trainer_jockey_combo_winrate_shrunk` | ✅ | numeric | Rate for this (trainer, jockey) pair. k=25. |
| `trainer_jockey_combo_starts` | ✅ | numeric | How many prior starts together. |
| `is_first_time_combo` | ✅ | boolean | First-time-together indicator. |
| `trainer_jockey_bond_strength` | 🕓 | numeric | Fraction of trainer's starts using this jockey. |
| `trainer_workout_pattern` | 🕓 | categorical | Requires Brisnet PP (Phase 3G). |

---

## Bucket 5 — Pedigree

**All deferred to Phase 3F** (v10 workbook integration). Doug's v10 sheet
has curated sire/dam signals — those become priors on the features below.

| Feature | Active | Type | Notes |
|---|---|---|---|
| `sire_id` | 🕓 | categorical | Raw sire ID; embedding or high-cardinality target. |
| `sire_at_surface_winrate_shrunk` | 🕓 | numeric | Progeny surface preference. |
| `sire_at_distance_winrate_shrunk` | 🕓 | numeric | Progeny distance preference. |
| `sire_first_time_turf_flag` | 🕓 | boolean | Doug's flagged pattern. |
| `damsire_at_surface_winrate` | 🕓 | numeric | Broodmare-sire influence. |
| `dam_progeny_avg_finish` | 🕓 | numeric | Dam's other foals' typical result. |
| `is_first_time_lasix` | 🕓 | boolean | Class change signal — needs prior-equipment lookup. |
| `is_first_time_blinkers` | 🕓 | boolean | From `entries.first_time_blinkers`. |
| `pedigree_index` | 🕓 | numeric | Composite from v10 signals. |
| `sire_turf_index_v10` | 🕓 | numeric | v10 curated signal. |
| `sire_dirt_index_v10` | 🕓 | numeric | v10 curated signal. |
| `sire_wet_index_v10` | 🕓 | numeric | v10 curated signal. |

---

## Bucket 6 — Race Dynamics

Physical race dynamics: post, weight, pace type, distance change.

| Feature | Active | Type | Source | Notes |
|---|---|---|---|---|
| `post_position` | ✅ | numeric | `entries.post_pos` | Actual gate. |
| `post_rank_in_field` | ✅ | numeric | derived (post / field_size) | 0-1 relative post. |
| `is_outside_post` | ✅ | boolean | derived | One of the outermost two gates. |
| `is_inside_post` | ✅ | boolean | derived | Rail or rail+1. |
| `weight_lbs` | ✅ | numeric | `entries.weight_lbs` | Impost. |
| `weight_vs_field_avg` | ✅ | numeric | derived per race | Horse's weight vs. race mean. |
| `weight_change_from_last_race` | ✅ | numeric | prior entry lookup | Positive = heavier today. |
| `distance_change_from_last_race` | ✅ | numeric | prior entry lookup | Yards_now − yards_last. |
| `pace_type_last_race` | ✅ | categorical | derived from prior `pace_calls_json` | front / stalk / mid / close. |
| `gate_break_avg_last_3` | ✅ | numeric | rolling mean of `start_pos` | Lower = sharper breaker. |
| `surface_change_from_last_race` | ✅ | boolean | prior entry lookup | Different surface than last time. |
| `start_pos_last_race` | 🕓 | numeric | prior entry | Overlaps `gate_break_avg_last_3`. |
| `pace_progression_last_race` | 🕓 | numeric | derived from all pace calls | Position change through the race. |

---

## Bucket 7 — Market Signals

Post-time tote odds and derivations. These are the Benter *anchor* signals —
in a Benter-style model they get fused with the fundamental score in a
second-stage blend.

| Feature | Active | Type | Source | Notes |
|---|---|---|---|---|
| `final_odds` | ✅ | numeric | `entries.final_odds` | Post-time tote odds (100.0% coverage). |
| `log_final_odds` | ✅ | numeric | `log1p(final_odds)` | Smoother distribution for GLMs. |
| `odds_rank_in_field` | ✅ | numeric | rank within race | 1 = favorite. |
| `implied_probability` | ✅ | numeric | `1 / (odds + 1)` | Raw implied probability (no takeout removal). |
| `is_favorite` | ✅ | boolean | `entries.is_favorite` | Chart flag — post-time favorite. |
| `odds_ratio_to_favorite` | ✅ | numeric | horse odds / favorite odds | 1.0 = favorite; >1 = longer. |
| `market_probability_normalized` | 🕓 | numeric | probs normalized after takeout | Takeout adjustment TBD. |
| `morning_line_odds` | 🕓 | numeric | Brisnet PP (Phase 3G) | Enables price-drift features. |
| `odds_drop_from_morning_line` | 🕓 | numeric | ML − final | Positive = bet-down. |

---

## Bucket 8 — Track-Specific

Track bias, historical horse × track/surface/condition rates. Uses the
`computed_speed_figures` table for par times and bias signals.

| Feature | Active | Type | Notes |
|---|---|---|---|
| `track_dirt_bias_90d` | ✅ | numeric | Rolling 90-day mean (winner speed − 80) on this track's dirt. Positive = fast surface. |
| `track_turf_bias_90d` | ✅ | numeric | Same on turf. |
| `historical_condition_winrate_shrunk` | ✅ | numeric | Horse's shrunk win rate under THIS track condition. k=15. |
| `historical_surface_winrate_shrunk` | ✅ | numeric | Horse's shrunk win rate on THIS surface. k=15. |
| `track_distance_par_time_sec` | ✅ | numeric | Par time for this (surf, dist, cond) cell. |
| `condition_change_from_last_race` | ✅ | boolean | Different condition than last time. |
| `starts_at_track` | ✅ | numeric | Horse's prior starts at THIS track. |
| `wins_at_track` | ✅ | numeric | Prior wins at THIS track. |
| `expected_pace_shape` | 🕓 | categorical | Aggregate of `pace_type_last_race` across entrants. |
| `track_speed_yield_90d` | 🕓 | numeric | Rolling avg of `par − actual` over 90d. |
| `rail_setting_feet` | 🕓 | numeric | `races.temporary_rail_feet` for turf. |

---

## Bayesian shrinkage strengths

All rate features use `shrink_rate = (num + k · prior) / (den + k)`. The k
values live in `feature_config.json → defaults.shrinkage_k_defaults`:

| Cell type | k |
|---|---:|
| `trainer_overall` | 20 |
| `trainer_at_track` | 30 |
| `trainer_at_surface` | 25 |
| `trainer_at_distance` | 30 |
| `trainer_jockey_combo` | 25 |
| `jockey_overall` | 20 |
| `jockey_at_track` | 30 |
| `jockey_at_surface` | 25 |
| `jockey_at_distance` | 30 |
| `horse_career` | 15 |
| `speed_par_time` | 50 |

These will be tuned during Phase 3D validation (grid search around each
value). Priors: `prior_win_rate = 0.12`, `prior_itm_rate = 0.35`, both
population-approximate.

## Time-decay half-lives

Two configurable half-lives live in
`feature_config.json → defaults.half_life_days`:

| Use | Half-life (days) | Notes |
|---|---:|---|
| `training_loss` | 730 (2 years) | Applied at model-training time, not in features. |
| `aggregate_stats` | 180 | Applied in rolling stats (feature layer). |

The v1 aggregate features use uniform weighting within each rolling window
for interpretability — decay is only applied at training. Phase 3D can
switch this on inside the aggregate features if half-life tuning suggests
it helps.

## Building the features

```bash
# 1. Compute par times & speed figures (writes computed_speed_figures)
python scripts/speed_figure_calculator.py compute --db scripts/gp_full.db

# 2. Build the wide feature table (writes entry_features_v1)
python scripts/feature_builder.py build \
    --db scripts/gp_full.db --config scripts/feature_config.json

# 3. Inspect coverage
python scripts/feature_builder.py summarize --db scripts/gp_full.db
```

The full pipeline runs in **~25 seconds** on the full 116,311-entry GP
dataset. Re-running is safe — the tables are drop-and-replaced each time.

## Toggling features on/off

Edit `scripts/feature_config.json`, flip `"active"` on any feature, and
rebuild. To add a *new* feature (not yet in the catalog), add it to
`feature_config.json` AND write the computation in `feature_builder.py`
under the appropriate `compute_bucket*` function. Keep the two files in
lockstep.

## Deferred to future phases

| Phase | Additions |
|---|---|
| 3D | Cross-validation, hyperparameter tuning (k values, half-lives) |
| 3E | Model training (conditional logit + Benter blend) |
| 3F | v10 workbook parsing → pedigree bucket + priors |
| 3G | Brisnet PP parsing → morning line, workout, class-change features |
| 3H | Multi-track expansion (CT, MNR, EVD, FP, FG, MVR, DD) |
