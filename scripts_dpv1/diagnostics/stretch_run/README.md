# Stretch-run investigation (2026-10-21)

Doug's question: did race winners have a fast stretch run in their previous
race? Read-only diagnostics; run in order from the repo root.

| script | what |
|---|---|
| `s1_build.py` | beaten lengths at the stretch call and finish for every charted horse (margins are lengths ahead of the next horse, summed down the field), gain, rank in field -> `out/stretch.pkl` |
| `s2_winners.py` | winners vs all starters by last race's stretch rank (2022+); live model's out-of-fold P(ITM) gap |
| `s3_ded_winners.py` | DED meet winners from 10/9 with last race's stretch rank -> `ded_winners_stretch.csv` |
| `pp_vs_chart.py` | chart-derived vs PP-line-derived stretch values on the same horse and race (feature parity check) |

Findings (2026-10-21, `dpv1.3.1` folds): fastest stretch run last time =
19.2% of winners vs 14.7% of starters; model under-rates them by +3.13pp
P(ITM) (z +8.3), positive at every track. Feature definition:
`scripts_dpv1/stretch_run.py`. Ablation: `scripts_dpv1/_stretch/`.
