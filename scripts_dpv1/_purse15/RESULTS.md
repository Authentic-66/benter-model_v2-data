# Purse-change retrain ablation: results (2026-10-19)

Graded by `eval_purse15.py` against `RULES.md` (committed `40c0b6b`, before
any arm trained). Full outputs: `eval_gate0.txt`, `eval_C1.txt`, `eval_C2.txt`,
`eval_C3.txt`; training logs `arm_*.log`; DB hashes `db_hashes.txt`. Arm
models and fold files are on disk in this directory, not in git.
Live `dpv1.pkl` and both rerankers: sha256 unchanged after training.

Basis: 137,094 rows / 18,220 races (live's fold rows with a finish in the
snapshot), labels = cleaned crossing order for every arm.

**Gate 0: PASS.** `folds_a2.csv` byte-identical to `folds_a.csv`
(md5 e5678d35…).

| | top-pick ITM | McNemar | years + | fund log-loss | Rule 1 | Rule 2 |
|---|---|---|---|---|---|---|
| **C1** live → (a) cleanup | **+0.23pp** (64.56 → 64.79) | 149/108, **p 0.012** | 4/4 | -0.00061, **z -9.15** | PASS | **PASS** |
| **C2** (a) → (b) P1 | +0.06pp (64.79 → 64.85) | 351/340, p 0.70 | 3/4 (2023 exactly 0.00) | -0.00101, **z -6.54** | PASS | **PASS (thin)** |
| **C3** live → (b) | +0.29pp (64.56 → 64.85) | 418/366, p 0.068 | 4/4 | -0.00162, **z -9.72** | PASS | **PASS** |

## C1: the cleanup earns its keep

The clearest result. Every track up or flat (GP +0.00, CT +0.38 p 0.044,
MNR +0.36, ELP +0.39, DED +0.31), every year positive (2023 +0.63 p 0.001
carries most of it), fundamental log-loss better on every track and year,
blended log-loss better too (z -5.77), AUC 0.6943 → 0.6953. Calibration
error is mixed by track (MNR/CT better, DED/ELP worse on deciles; DED mean
pred - actual +0.26 → +0.35). Bundle caveat in RULES.md: this is every label
and table change since 2026-09-19, not separable.

## C2: P1 is a calibration fix; its ranking gain is nil

* **Ranking:** +0.06pp, 351 vs 340 discordant races, p 0.70. Rule 2's year
  count passes 3 of 4 on deltas of +0.08 / +0.12 / +0.03 with 2023 at
  exactly 0.00, so the pass is decided by noise; read it as "no ranking
  effect", as the screen predicted. **DED -0.36pp** (46/54, p 0.48),
  negative in 2023-2025, the one track below control.
* **Fundamental log-loss:** better on every track and year (z -6.54
  pooled; MNR z -5.80, CT -3.90, DED -2.85). AUC 0.6953 → 0.6966.
* **Blended log-loss:** +0.00002 (z +1.57), i.e. the market already absorbed
  this; the gain is in the odds-free P(ITM).
* **Purse buckets, the target:** weighted mean |error| 1.107 → **0.874pp**.
  Stakes tail > 3x +14.37 → +4.25pp; +10..+60% -3.3 → -2.2 / -1.9pp.
  **New error: ≤ -50% drops flip from +1.55 to -2.35pp (z -4.2)** — the log
  stretches big drops (ln 0.25 = -1.39 vs raw -0.75), so the model now
  over-credits them.
* **Overall calibration error:** mixed. Own-decile 0.497 → 0.556 (worse; GP,
  CT, MNR worse), fixed bins 0.526 → 0.503 (better); DED own-decile 0.839 →
  0.700 (better). Mean pred - actual +0.14 → +0.18.
* Coefficient: P1 -0.217/sd, |coef| rank 7 of 226 (raw term in (a): -0.197,
  rank 10).

## C3: the full change

+0.29pp (p 0.068), all years positive, fund log-loss z -9.72, AUC 0.6943 →
0.6966. Most of the ranking gain is C1's.

## Not decided here

Nothing promoted. What a promotion would involve, for Doug's call:
* **(a)** is a drop-in: same 94 features and same live code path.
* **(b)** also needs `purse_logratio_clipped` in `feature_builder_dpv1.py`,
  the config, and the PP bridge (`pp_feature_bridge.py` currently bridges
  `purse_change_from_last` on cards); otherwise live cards would feed NaN
  (`dpv1_runtime._ensure_columns`).
* Either resets the live record (Piece 3 filters by `model_version`); the
  rerankers sit on the old fold basis (Stage 4 caveat still applies).

## Decision (Doug, 2026-10-19)

**Arm (a) promoted** as `dpv1.3.1-5track-clean` after the reranker check
(`reranker_check.txt`: PP reranker +5.2pp over (a) vs +4.1pp over 1.3.0 on
the same 268 races; classctx shadow +0.6pp). Installed byte-for-byte; record
in PHASE_6E "Promotion decision, 2026-10-19". **Arm (b) held**; asymmetric
drop cap (b2) is PHASE_6E follow-up #16. Scripts here now read the frozen
1.3.0 files (`dpv1_20260919_040326_retired.pkl`,
`dpv1_fold_predictions_dpv1.3.0.csv`) and reproduce their outputs.
