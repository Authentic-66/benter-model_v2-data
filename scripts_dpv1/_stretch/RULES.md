# Stretch-run retrain ablation: pre-registered rules (2026-10-21)

Committed **before any arm is trained**, on its own commit, as for the purse
test (`_purse15/RULES.md`). Doug's request of 2026-10-21: keep and test the
stretch-run feature; (s1) raw, (s2) pace-adjusted, both against
`dpv1.3.1-5track-clean`; report before promoting anything; live model
unchanged until Doug approves.

## Feature definitions (fixed now)

`scripts_dpv1/stretch_run.py` (committed with these rules) is the only
definition. Values come from the horse's previous race in the corpus
(strictly earlier date, the builder's own `_prior_last_value`).

| column | definition |
|---|---|
| `last_str_gain` | lengths behind the leader at the stretch call minus at the finish (positive = closed ground), clipped +-15 |
| `last_str_gain_rank_pct` | rank of the unclipped gain in that race's field, (rank-1)/(n-1), 0 = best, ties min |
| `last_str_gain_padj` | gain minus E[gain \| stretch-call bucket (0, 0-2, 2-5, 5-10, >10 L), early-pace bucket (z of leader's 2nd fraction vs the track/distance/surface median, cuts -1, -0.33, 0.33, 1)], E fitted on races before 2023-01-01 only; pooled over pace where the race has no par (cell < 20 races or no fractions); clipped +-15 |
| `last_str_gain_padj_rank_pct` | rank of padj in that race's field, as above |

A race contributes only when its Str and Fin calls are readable for every
starter (positions form 1..n). NULL otherwise, and NULL where the horse has
no previous corpus race.

## Arms

All arms: `dpv1.pkl`'s 94 fundamental features (dpv1.3.1-5track-clean,
asserted equal to the retired 1.3.0 list that defines them), pinned;
`train_dpv1.cmd_final` unchanged; half-life and L2 from
`dpv1_grid_results.csv` (as live); corpus and training tracks GP, CT, MNR,
ELP, DED; `PYTHONHASHSEED=0`; rolling-origin folds 2023-2026.

| arm | features |
|---|---|
| **c0** (control) | live's 94 |
| **s1** | live's 94 + `last_str_gain` + `last_str_gain_rank_pct` |
| **s2** | live's 94 + `last_str_gain_padj` + `last_str_gain_padj_rank_pct` |

All three train on `_stretch/racing_s.db`: a byte copy of the live
`scripts/racing_full.db` (sha256 recorded) plus the four columns above in
`entry_features_dpv1`. `prep_stretch.py` builds it; `train_arm.py` trains one
arm. Nothing under `scripts/`, the live DB, `dpv1.pkl` or the rerankers is
modified. No card is loaded into the live DB while an arm trains.

## Gate 0: control = live

`folds_c0.csv` must be byte-identical (md5) to `_purse15/folds_a.csv`, the
fold file of the installed `dpv1.3.1-5track-clean`. Nothing with results has
been loaded since that arm trained, so this checks both determinism and that
the snapshot is the live model's training table. If it fails, stop and find
the cause before reading anything; the fallback (only with the cause
understood and written down) is a determinism re-run `c0b` byte-identical to
`c0`, with `c0` as the control.

## Evaluation basis (as the purse test)

* **Rows:** entries in live's `dpv1_fold_predictions.csv` AND in both fold
  files compared (inner join on `entry_id`), with a finish in the snapshot.
* **Labels:** snapshot `finish_pos <= 3` for every arm.
* **Top pick:** highest `p_fund` per race among the rows kept.
* **Tests:** exact two-sided McNemar on discordant races; log-loss deltas
  with race-clustered z.

## Rules, applied to C1 and C2 (control -> candidate)

* **Rule 1, do not damage.** Top-pick ITM delta >= -0.5pp on each of GP, CT,
  MNR; >= -2pp on every track including ELP and DED; the pooled five-track
  delta not significantly negative (negative with McNemar p < 0.05).
* **Rule 2, must gain.** Pooled five-track top-pick ITM delta >= 0; positive
  in at least 3 of the 4 validation years; pooled fundamental log-loss delta
  < 0.
* Rule 3 (specialist) does not apply.

**Reported for every comparison, not gates:** per-track and per-year deltas
with discordant counts and p; fundamental and blended log-loss with z; AUC;
weighted mean |calibration error| (own deciles and fixed 0.1 bins) and mean
predicted - actual per track and overall; the stretch-rank bucket table
(actual vs predicted `p_fund` by `last_str_gain_rank_pct`: NULL, 0 = fastest,
(0, .25], (.25, .5], (.5, .75], (.75, 1]) with its weighted mean |error|.

## Comparisons

| | control -> candidate | question |
|---|---|---|
| **C1** | c0 -> s1 | does the raw stretch feature earn its keep? |
| **C2** | c0 -> s2 | does the pace-adjusted one? |
| **C3** | s1 -> s2 | descriptive only (no gate): which to prefer if both pass |

## Reading the result

* A comparison **passes** when Rules 1 and 2 both pass.
* If C1 or C2 fails Rule 2 but improves pooled fundamental log-loss with
  z <= -2 **and** lowers the stretch-bucket weighted mean |error|, it goes to
  Doug as a calibration-versus-ranking decision. Not an automatic pass.
* **If both pass:** prefer s1 (simpler; its gain is fully computable from a PP
  line) unless C3 shows s2 better by McNemar p < 0.05 or fundamental
  log-loss z <= -2.
* **Before any promotion** (not gates, reported): the reranker check as at
  the purse test (pp-reranker-1.0 and classctx on top of the candidate's
  folds); and the live-path work: the feature builder and PP bridge
  computing these columns, with builder output equal to `racing_s.db`'s
  columns on every row.
* **Open live-path decision, for Doug, not decided here:** a PP line gives the
  gain but never the rank. In training, rank is NULL exactly when gain is
  NULL. Bridging only the gain for PP-only horses creates a combination the
  model never saw (gain present, rank missing). Options: bridge neither (keep
  training semantics), or bridge the gain and fill the rank from a fitted
  gain -> rank map.
* Nothing is promoted without Doug. `dpv1.pkl` and the rerankers are not
  touched.
