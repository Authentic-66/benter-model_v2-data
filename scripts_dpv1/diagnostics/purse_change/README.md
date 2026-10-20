# purse_change_from_last investigation (2026-10-19)

Read-only diagnostics behind PHASE_6D_ROADMAP.md, section
"`purse_change_from_last` representation". Run from anywhere, in order
(each later script reads `out/pc_df.pkl` written by the first two):

| script | what |
|---|---|
| `pc_load.py` | frame builder: feature, today's race, reconstructed last race, live OOF `p_fund` |
| `pc1_distribution.py` | 1. build check, distribution, tails, largest moves |
| `pc2_calibration.py` | 2. coefficient, calibration by bucket (raw / normalised / blend), by year and track |
| `pc2b_residual_slopes.py` | 2. residual slopes: raw vs log vs capped, by year and track, Kel-Co subset |
| `pc2c_kelco_test1.py` | 2. Kel-Co Test 1 recipe on same-track claiming → claiming |
| `pc3_ded_cards.py` | 3. logged DED horses whose largest negative reason was purse change |
| `pc4_screen.py` | 4. one-variable correction screen of candidate representations, 2023-24 → 2025-26 |

Outputs go to `out/` (git-ignored). Inputs: `scripts/racing_full.db`
(read-only), `dpv1.pkl`, `dpv1_fold_predictions.csv`, `logs/`, `picks/`.
