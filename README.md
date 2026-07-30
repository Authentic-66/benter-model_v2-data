# Benter Model v2 — Data Pipeline

Phase 3A artifacts: a PDF parser, a SQLite schema, and a database loader for
Equibase result charts. The current build targets Gulfstream Park
(2019-2026, ~1,500 PDFs, ~15,000 races); the same pipeline is designed to
extend to CT, MNR, EVD, FP, FG, MVR, DD in Phase 3B.

## Layout

```
scripts/
  equibase_pdf_parser.py       ← parse one PDF or a directory of PDFs into JSON
  db_schema.sql                ← SQLite schema (tracks, races, entries, ...)
  db_loader.py                 ← load parsed JSON into the SQLite DB
  run_validation.py            ← Phase 3A 100-PDF validation harness
  analyze_full_load.py         ← Phase 3B full-corpus analyzer

  bayesian_shrinkage.py        ← empirical-Bayes rate shrinkage utility
  time_decay.py                ← exponential-decay weighting utility
  speed_figure_calculator.py   ← Beyer-like par-time + speed figures
  feature_config.json          ← 105-feature catalog with active flags
  feature_builder.py           ← builds entry_features_v1 wide table
  generate_phase3c_report.py   ← rebuilds PHASE_3C_FEATURES.md from DB

  cross_validation.py          ← temporal CV splitter + holdout carver
  metrics.py                   ← log-loss, hit-rate, ECE, ROI, Kelly
  baselines.py                 ← BaselineFavorite / BaselineRandom / OldModel stub
  hyperparameter_search.py     ← model-agnostic grid-search framework
  diagnostics.py               ← slice-based performance breakdown
  generate_phase3d_report.py   ← rebuilds PHASE_3D_VALIDATION.md

  prepare_training.py          ← preprocessing pipeline + LEAKY_FEATURES tuple
  fundamental_model.py         ← conditional-logit (scipy L-BFGS)
  market_model.py              ← takeout-corrected implied probabilities
  blend_model.py               ← Benter α, β blend learner
  train_benter_v2.py           ← grid search + refit + pickle
  generate_phase3e_report.py   ← rebuilds PHASE_3E_MODEL_V1.md

  v10_signal_extractor.py      ← parse v10 workbook Iron Rules sheet -> JSON
  v10_iron_rules_extracted.json  ← 37 signals with Doug's review status
  apply_v10_priors.py          ← v10 flags -> entry_v10_flags table
  generate_phase3f_report.py   ← rebuilds PHASE_3F_V10_PRIORS.md

scripts_v2a/                   ← Phase 3G v2a work (isolated from v2)
  prepare_training_v2a.py      ← 2022+ filter, ITM target (finish_pos<=3)
  fundamental_model_v2a.py     ← binary logistic per entry (not softmax)
  market_model_v2a.py          ← Harville market P(ITM) reduction
  blend_model_v2a.py           ← α, β, γ blend (3-parameter, per entry)
  itm_metrics.py               ← ITM-specific metrics (top-K hit, sweep, ROI)
  longshot_detector.py         ← per-race JSON output + longshot flags
  train_benter_v2a.py          ← grid search + refit + pickle
  generate_phase3g_reports.py  ← rebuilds both v2a reports
  benter_v2a.pkl               ← trained v2a artifact
  benter_v2a_grid.csv          ← full 80-fit grid results
  PHASE_3G_ITM_MODEL.md        ← v2a validation
  V2_VS_V2A_COMPARISON.md      ← head-to-head vs v2 on ITM

  FEATURES_CATALOG.md          ← prose catalog of every planned feature
  PHASE_3A_VALIDATION.md       ← Phase 3A report (100-PDF sample)
  PHASE_3B_FULL_LOAD.md        ← Phase 3B report (full 1,483-PDF corpus)
  PHASE_3C_FEATURES.md         ← Phase 3C report (feature engineering)
  PHASE_3D_VALIDATION.md       ← Phase 3D report (validation infrastructure)
  PHASE_3E_MODEL_V1.md         ← Phase 3E report (first model — SHIP CRITERIA FAIL)
  PHASE_3F_V10_PRIORS.md       ← Phase 3F report (v10 priors — marginally helps)

  benter_v2.pkl                ← Phase 3E model (also copied as benter_v2_phase3e.pkl)
  benter_v2_phase3e.pkl        ← Phase 3E baseline for head-to-head comparisons
  benter_v2_v10.pkl            ← Phase 3F model with v10 features
  benter_v2_grid_results.csv   ← Phase 3E grid results
  benter_v2_grid_phase3e.csv   ← copy for reproducing head-to-head
  benter_v2_grid_v10.csv       ← Phase 3F grid results
  gp_2019_2026.db              ← 100-PDF validation sample DB (~6 MB)
  gp_full.db                   ← production DB (~73 MB base + features)

Gulfstream Park/
  gp-results-2019/ ... gp-results-2026/   ← chart PDFs (3 filename conventions)
  gp-pps-files/                           ← Brisnet PP files (Phase 3G)
```

## Quick start

### Requirements

- Python 3.10+
- `pdfplumber` (`python -m pip install pdfplumber`)
- SQLite ships with the Python standard library

### Parse a single PDF and dump JSON

```bash
python scripts/equibase_pdf_parser.py parse \
    "Gulfstream Park/gp-results-2024/20240101-usa-gp-a-d.standard.pdf" \
    --json out.json
```

### Batch-parse a directory

```bash
python scripts/equibase_pdf_parser.py batch "Gulfstream Park" \
    --cache .cache --limit 50
```

`--cache` writes one JSON sidecar per PDF. Re-runs skip files whose SHA-256
matches an existing cache entry (resumable; `--force` to re-parse anyway).

### End-to-end: parse + load into SQLite

```bash
python scripts/db_loader.py pipeline \
    --db gp.db \
    --schema scripts/db_schema.sql \
    --pdf-dir "Gulfstream Park" \
    --cache .cache \
    --exclude gp-pps-files \
    --resume
```

This creates `gp.db` (if missing), parses every PDF under the directory,
caches JSON sidecars, then loads them into the SQLite DB. Flags:

- `--exclude gp-pps-files` skips Brisnet PP files (Phase 3C); repeatable
- `--resume` skips PDFs already successfully recorded (by sha256 in
  `parsed_files`), so an interrupted run can be restarted safely
- `--force-parse` bypasses the JSON cache and re-parses every PDF

### Re-run the validation report

```bash
python scripts/run_validation.py
```

Samples 100 random PDFs (≈13 per year, distributed across 2019-2026),
populates `gp_2019_2026.db`, and writes `scripts/PHASE_3A_VALIDATION.md`.

### Build the feature table (Phase 3C)

```bash
# 1. Compute par times & speed figures (~5 s)
python scripts/speed_figure_calculator.py compute --db scripts/gp_full.db

# 2. Build the wide entry_features_v1 table (~20 s)
python scripts/feature_builder.py build \
    --db scripts/gp_full.db --config scripts/feature_config.json

# 3. Regenerate the Phase 3C report
python scripts/generate_phase3c_report.py
```

Feature activation is controlled by `scripts/feature_config.json` — flip
`"active": true` on any cataloged feature and rebuild to include it. See
`scripts/FEATURES_CATALOG.md` for the full menu (105 features across 8
buckets; 73 active in v1).

### Train the Benter Light v2 model (Phase 3E)

```bash
# Grid search over 5 half-lives × 4 L2 values × 4 CV folds (~15 min)
# Refits final model on all data + saves scripts/benter_v2.pkl
python scripts/train_benter_v2.py

# Regenerate the report from grid_results.csv + benter_v2.pkl
python scripts/generate_phase3e_report.py
```

The current v1 fails ship criteria — see `PHASE_3E_MODEL_V1.md` for the
diagnosis and next steps. Adding features (Phase 3F v10 priors, Phase 3G
Brisnet PP) is expected to close the gap.

### Layer in v10 workbook priors (Phase 3F)

```bash
# 1. Extract signals from Doug's workbook  (~5 s)
python scripts/v10_signal_extractor.py

# 2. Doug reviews scripts/v10_iron_rules_extracted.json — sets each
#    signal's review_status to 'approved' | 'rejected' | 'modified'.
#    (Uncurated signals are ignored by the applier.)

# 3. Compute v10 firing flags per entry -> entry_v10_flags table (~2 s)
python scripts/apply_v10_priors.py

# 4. Retrain — training auto-detects entry_v10_flags and includes it
python scripts/train_benter_v2.py --model-out scripts/benter_v2_v10.pkl \
                                   --results-out scripts/benter_v2_grid_v10.csv

# 5. Head-to-head report vs Phase 3E baseline
python scripts/generate_phase3f_report.py
```

Phase 3F prototype outcome: v10 signals ARE informative but already mostly
priced by the market. Recommendation is to combine with Phase 3G Brisnet
PP (fundamentally different information).

### Train v2a — ITM-target model (Phase 3G)

```bash
# 1. Full grid search + refit (~2 min on 2022+ scope)
python scripts_v2a/train_benter_v2a.py

# 2. Head-to-head reports (v2a self-report + v2-vs-v2a comparison)
python scripts_v2a/generate_phase3g_reports.py
```

v2a uses the same feature table, v10 flags, and Phase 3D CV framework
as v2 — only the target and loss differ. Results are essentially tied
with v2 on ITM metrics; v2a's advantage is that its fundamental model
learns a genuinely nonzero blend weight (α ≈ 0.17), so future feature
additions have room to help.

### Evaluate a model / regenerate Phase 3D report

```bash
# Regenerate baseline results + slice diagnostics + grid-search demo
python scripts/generate_phase3d_report.py
```

The Phase 3D modules (`cross_validation.py`, `metrics.py`, `baselines.py`,
`hyperparameter_search.py`, `diagnostics.py`) are model-agnostic — Phase 3E's
Benter model will plug in the same way any baseline does. Each module runs
its own self-test when invoked directly:

```bash
python scripts/cross_validation.py       # confirms folds are leakage-free
python scripts/metrics.py                # synthetic 2-race smoke test
python scripts/baselines.py              # tiny demo output
python scripts/hyperparameter_search.py  # 4-value scale grid × 4 folds
python scripts/diagnostics.py            # 100-race synthetic slicing
```

## Filename conventions handled

| Convention | Example | Era |
|---|---|---|
| Equibase standard | `20190101-usa-gp-a-d.standard.pdf` | 2019-2023 (and many 2024-2026) |
| Doug short | `01.01.26 GP Results.pdf` | 2026 |
| Doug compact | `GP020126.pdf`, `GP041626USA.pdf` | 2026 |

The parser detects the convention from the filename, extracts the date and
track code, then cross-checks against the date in the PDF header text.

## Data extracted

### Race level
- distance (text, normalized yards), surface, track condition
- purse, available money, value of race + per-place breakdown
- race type (CLAIMING, MAIDEN SPECIAL WEIGHT, STAKES, etc.), stakes name when present
- conditions paragraph (raw text)
- field size and scratched horses with reasons
- weather, temperature, off-time, start note, timing method
- fractional times, final time, time from gate, split times
- run-up feet, temporary rail feet
- total WPS pool and the full exotic-payouts table
- footnotes (raw race narrative)

### Per horse
- name (canonical with restored spaces, country code separated)
- jockey, trainer, owner (deduped via normalized names)
- weight, equipment flags (Lasix, blinkers, bandages, first-time markers)
- post position, starting position
- pace calls at each fractional split (raw `<pos><margin>` tokens preserved)
- official finish position, beaten lengths from leader, winning margin text
- final tote odds (Benter anchor, ~100% coverage), favorite flag
- trip comment (raw text from chart caller)
- speed figure (NULL — not in standard charts; sourced from Brisnet PP in Phase 3B)
- WPS payouts (top 3 finishers)
- claimed-in-race flag plus new-trainer/new-owner when claimed
- last-raced raw token (date + race + track + finish, parse deferred)

## Honest extraction policy

- **NULL means unknown**, never imputed and never zero-filled.
- Missing speed figures, missing fractional times, missing trip comments are
  all stored as NULL. Phase 3D feature engineering decides what to do with
  them, not the parser.
- Trip comments are preserved as raw text (pdfplumber strips intra-field
  whitespace; this is preserved so a later phase can decide whether to
  tokenize on punctuation or treat as a single string).

## Known limitations

- **Speed figures absent.** Equibase standard charts do not include Equibase
  Ratings. Phase 3B Brisnet PP files will populate these.
- **pdfplumber whitespace stripping.** Names like `Star of Distinction`
  render as `StarofDistinction`. We restore spaces at case boundaries
  (`JerseyRose` → `Jersey Rose`) but cannot recover spaces around lowercase
  particles (`of`, `and`, `the`). Normalized-name keys are consistent across
  appearances, so joins still work.
- **DQs.** The chart relabels disqualified on-track winners with a `DQ-`
  prefix and lists the official winner in the WPS table. The parser treats
  the WPS table as ground truth — `finish_pos = 1` is the official winner;
  the DQ'd horse's row keeps its `DQ-` prefix in the `horses` table.

## Database schema highlights

See `scripts/db_schema.sql` for the full schema. Key tables:

```
tracks (1 row per track code)
race_days (track_id, race_date) UNIQUE
races (race_day_id, race_num) UNIQUE — distance/surface/times/footnotes
entries (race_id, program_num) UNIQUE — per-horse facts
horses, trainers, jockeys, owners, sires, dams — deduped dimensions
exotic_payouts — one row per exotic wager line
parsed_files — provenance: per-PDF processing log (success, warnings, sha256)
```

Indexes are on `(track+date)`, `horse_name`, `trainer`, `jockey`, and
`finish_pos` — the queries Phase 3D feature engineering will hit most.

## Phase plan

- **Phase 3A:** parser + DB + 100-PDF validation ← done
- **Phase 3B:** full GP corpus load (1,480 PDFs, 14,857 races) ← done;
  see `scripts/PHASE_3B_FULL_LOAD.md`
- **Phase 3C:** feature engineering (105-feature catalog, 73 active in v1) ← done;
  see `scripts/PHASE_3C_FEATURES.md`
- **Phase 3D:** validation infrastructure (CV, metrics, baselines, grid search) ← done;
  see `scripts/PHASE_3D_VALIDATION.md`
- **Phase 3E:** first model (Benter Light v2) ← **ship criteria FAIL**;
  the fundamental model with current feature set adds no signal beyond the
  market. Caught a subtle look-ahead leak in Bucket 2 pedigree fields;
  fixed via `prepare_training.LEAKY_FEATURES`.
  See `scripts/PHASE_3E_MODEL_V1.md`.
- **Phase 3F:** v10 workbook priors (prototype) ← **marginally helps**.
  37 signals from Cross-Track Iron Rules extracted, reviewed by Doug,
  applied as fundamental features. CV α climbs from ~0 to ~0.03, log-loss
  falls by 0.0003. Ship criteria still not met — see
  `scripts/PHASE_3F_V10_PRIORS.md`.
- **Phase 3G:** v2a ITM-target model ← **tied with v2 on ITM metrics**.
  Pivots the target from WIN (top-1) to ITM (top-3), 2022+ scope, binary
  logistic per entry. Top-3 hit rate 97.7% (×1.15 random), full-sweep
  15.6% (×4.5 random), trifecta ROI -24.9% (right at takeout). Head-to-
  head with v2 rescored on ITM: essentially tied. But v2a's fundamental
  learns α ≈ 0.17 (v2's α ≈ 0), so architecturally better positioned
  to absorb future feature sources. See `scripts_v2a/PHASE_3G_ITM_MODEL.md`
  and `scripts_v2a/V2_VS_V2A_COMPARISON.md`. **scripts/ folder untouched.**
- **Phase 3H:** Brisnet PP integration / multi-track expansion

## Verifying a build

```bash
# Schema-only init
python scripts/db_loader.py init --db /tmp/x.db --schema scripts/db_schema.sql

# Smoke test on one PDF
python scripts/equibase_pdf_parser.py parse \
    "Gulfstream Park/gp-results-2026/01.01.26 GP Results.pdf" --json /tmp/test.json

# Inspect the report
cat scripts/PHASE_3A_VALIDATION.md
```

## Performance

Validation throughput is ~30 PDFs/minute, ~300 races/minute on a typical
laptop (single-threaded). The full 1,500-PDF GP corpus parses in ~50 minutes
end-to-end. The `--cache` flag makes subsequent re-runs near-instant.
