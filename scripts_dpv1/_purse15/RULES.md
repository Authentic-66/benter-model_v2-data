# Purse-change retrain ablation: pre-registered rules (2026-10-19)

Committed **before any arm is trained**. The Stage 4 lesson (rules written in
the same hour as the run they grade) is the reason this file exists on its
own commit. Doug's decisions of 2026-10-19: P1 only, no arm (c); fix the 7
misread DQ'd-winner labels first (done, `fa48fee`); live model unchanged.

## Arms

All arms: live `dpv1.pkl`'s 94 fundamental features pinned (asserted present),
`train_dpv1.cmd_final` unchanged, half-life and L2 from `dpv1_grid_results.csv`
(2.5y, 0.001, as live), corpus and training tracks GP, CT, MNR, ELP, DED,
`PYTHONHASHSEED=0`, rolling-origin folds 2023-2026.

| arm | table | features |
|---|---|---|
| **(a)** | `racing_a.db`: snapshot of live `racing_full.db` after `fa48fee` (cleaned labels, current feature table) | live's 94 |
| **(a2)** | same file as (a) | live's 94 (determinism re-run) |
| **(b)** | `racing_b.db`: the same snapshot plus one column `entry_features_dpv1.purse_logratio_clipped` = clip(ln(1 + `purse_change_from_last`), -ln 4, +ln 4), NULL where the raw value is NULL | live's 94 with `purse_change_from_last` replaced by `purse_logratio_clipped` |

`prep_purse15.py` makes both DBs and records their sha256; `train_arm.py`
trains one arm. Nothing under `scripts/` or the live DB is modified.

## Evaluation basis

* **Rows:** entries present in live's `dpv1_fold_predictions.csv` AND in the
  arm fold files being compared (inner join on `entry_id`), with a finishing
  position in the snapshot.
* **Labels:** `finish_pos <= 3` from the snapshot (cleaned crossing order) for
  every arm, including live. Live's own `y_true` column is NOT used.
* **Top pick:** highest `p_fund` per race among the rows kept.
* **Tests:** exact two-sided McNemar (binomial on discordant races);
  log-loss deltas with race-clustered z.

## Gate 0: determinism

`folds_a2.csv` must be byte-identical (md5) to `folds_a.csv`. If not, stop:
no comparison below is read until the cause is found.

## Rules, applied to each comparison (control → candidate)

* **Rule 1, do not damage.** Top-pick ITM delta ≥ -0.5pp on each of GP, CT,
  MNR; ≥ -2pp on every track including ELP and DED; the pooled five-track
  delta not significantly negative (negative delta with McNemar p < 0.05).
* **Rule 2, must gain.** Pooled five-track top-pick ITM delta ≥ 0; positive
  in at least 3 of the 4 validation years; pooled fundamental log-loss delta
  < 0.
* Rule 3 (specialist) does not apply.

**Reported for every comparison, not gates:** per-track and per-year deltas
with discordant counts and p; fundamental and blended log-loss with z; AUC;
weighted mean |calibration error| (own deciles and fixed 0.1 bins) and mean
predicted − actual per track and overall; the purse-change bucket table
(actual vs predicted `p_fund` per bucket, same buckets as the roadmap) with
its weighted mean |error|.

## Comparisons and what each answers

| | control → candidate | question |
|---|---|---|
| **C1** | live → (a) | does the corpus cleanup earn its keep? |
| **C2** | (a) → (b) | does P1 earn its keep on top of the cleanup? |
| **C3** | live → (b) | the full change, as a promotion candidate |

C1 is a bundle: live's folds were fitted on the 2026-09-19 table and labels,
so (a) carries every label and feature-table change since then (#10-#15,
dead heats, DQs, the 35 starters, rebuilds). It is not separable here.

## Reading the result

* A comparison **passes** when Rules 1 and 2 both pass.
* P1's expected gain is calibration (roadmap screen). If C2 fails Rule 2 but
  improves pooled fundamental log-loss with z ≤ -2 **and** lowers the
  purse-bucket weighted mean |error|, it goes to Doug as a calibration-versus-
  ranking decision, as Stage 4's DED did. It is not an automatic pass.
* Nothing is promoted without Doug. `dpv1.pkl` and the rerankers are not
  touched; Wednesday's card runs on dpv1.3.0-5track unless Doug approves.
* No card is loaded into the live DB while an arm is training.
