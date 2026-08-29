Phase 6E — Prediction Logging + Post-Race Scoring

Goal: Build the audit trail and monitoring infrastructure so we can objectively track DPv1 model performance across cards and detect drift.

Scope: Four scripts, built incrementally. Piece 1 unblocks the rest.

🎯 Piece 1: Prediction Logging (start here)

File: modify scripts_dpv1/card_picks.py

Change: When --save is passed, in addition to writing the human-readable picks file, also append one row per horse to scripts_dpv1/logs/predictions.jsonl.

Row schema:

json
{
  "prediction_id": "CT_2026-08-28_R5_pgm4_20260828-0845",
  "generated_at": "2026-08-28T08:45:00",
  "track": "CT",
  "race_date": "2026-08-28",
  "race_num": 5,
  "pgm": 4,
  "horse_name": "Coach Siggy",
  "p_itm": 0.706,
  "p_win": 0.301,
  "coverage": 0.91,
  "ml_odds": "2/1",
  "prime_power": 117.7,
  "model_version": "dpv1.2.0-4track",
  "model_pkl": "dpv1.pkl",
  "rank": 1,
  "n_horses_in_race": 9,
  "picks_file": "picks/CT_2026-08-28_20260828-0845.txt"
}

Rules:

Append-only. Never modify existing rows.
Create logs/ dir if not present
One row per horse per prediction run (not per race)
prediction_id is unique per (track, date, race, pgm, timestamp) — allows multiple runs per card
Log for BOTH 4-track and 3-track when both are run
Silent failure if disk full — don't crash the pick generation

Test: Run card_picks.py --track CT --date 2026-08-28 --save on a card that already has picks. Verify predictions.jsonl has 8-13 rows per race and no dupes when re-run (or dupes are OK, just tagged with different timestamps).

## Piece 1 Implementation Notes (post-build)
- `prediction_id` uses %Y%m%d-%H%M%S timestamp (not -%H%M as originally spec'd) 
  to handle same-minute re-runs. `picks_file` field keeps the original minute stamp.
- `pgm` is stored as string (not int) to handle coupled entries (1A, 1B).
- Added `race_coverage` field beyond original spec — race-level coverage 
  needed for Piece 3 bucketing.

🎯 Piece 2: Post-Race Scoring

File: new scripts_dpv1/score_predictions.py

Usage:

python scripts_dpv1/score_predictions.py --track CT --date 2026-08-28

What it does:

Read all predictions from predictions.jsonl matching (track, race_date)
For each race, query racing_full.db for actual finishing positions
For each prediction, compute:
actual_finish (1-N or NULL for scratched)
hit_itm (bool: finished ≤ 3)
hit_win (bool: finished == 1)
was_top_pick (bool: rank == 1 in this prediction)
top_pick_hit_itm (bool: race's top pick hit ITM)
show_payoff (if available in DB; else NULL)
Append scored rows to scripts_dpv1/logs/scored_predictions.jsonl

Row schema: same as predictions.jsonl plus the scoring fields above.

Rules:

Skip races where results aren't loaded yet (log a warning)
Skip scratched horses (finish_pos NULL)
Idempotent — re-running should replace existing scored rows for that card, not append duplicates
Ex/Tri/Super box hit calculations deferred to Piece 3 (payoffs live in a separate table)

Test: Score CT 2026-08-23 through CT 2026-08-28. Verify counts match expected ITM rates.

🎯 Piece 3: Model Health Dashboard

File: new scripts_dpv1/model_health.py

Usage:

python scripts_dpv1/model_health.py                    # rolling summary
python scripts_dpv1/model_health.py --track CT         # filter by track
python scripts_dpv1/model_health.py --model dpv1_3track.pkl  # by model version
python scripts_dpv1/model_health.py --last-n 100       # last N races
python scripts_dpv1/model_health.py --since 2026-08-01 # since date

What it prints:

DPv1 Model Health — dpv1.2.0-4track
Window: last 100 races (2026-08-15 to 2026-08-28)

═══ Overall ═══
Top pick ITM:        57 / 100 = 57.0%   (target: 55-57%)   ✓ on target
Top pick WIN:        22 / 100 = 22.0%   (baseline: 15%)    ✓ above baseline
Top-4 avg ITM cap:   2.87 / 3.00                            ✓ good coverage

═══ By Track ═══
CT:   ITM 58% (n=42)   Win 23%
GP:   ITM 61% (n=28)   Win 25%
MNR:  ITM 52% (n=18)   Win 17%
ELP:  ITM 54% (n=12)   Win 25%

═══ By Feature Coverage ═══
90-100% cov:   ITM 63% (n=51)   ← high-coverage races most reliable
80-89% cov:    ITM 55% (n=32)
<80% cov:      ITM 48% (n=17)   ← low-cov races underperform, as expected

═══ By Race Type ═══
Claiming:     ITM 62% (n=28)
Allowance:    ITM 58% (n=41)
Maiden:       ITM 51% (n=18)
Stakes:       ITM 45% (n=13)   ← known weak spot

═══ Show ROI on Top Pick ═══
Total stake:      $200
Total return:     $186.40
Net:              -$13.60
ROI:              -6.8%

═══ Alerts ═══
[none]  (all metrics within expected bands)

Alert logic: Flag if any of:

Top pick ITM in last 30 races drops below 45% or exceeds 68%
Feature coverage-adjusted ITM drops below 40% in high-cov bucket
Show ROI drops below -25% over last 60 races
Any track's ITM diverges >15pp from the overall average

Print alerts inline, don't email/notify. This is diagnostic, not operational.

## Corpus Awareness for Piece 3

Current dpv1.pkl trained on data through 2026-08-22. This means:
Corpus membership is determined by CHART LOAD TIME vs model TRAINED_AT, 
not race date. A race can occur before training but its chart can be 
loaded after — in which case it's out-of-corpus. Piece 3 determines 
this by joining parsed_files.loaded_at against the model artifact's 
trained_at metadata. Use --training-cutoff DATE as a manual override 
when needed.Piece 3 must distinguish these when reporting headline metrics. In-corpus 
numbers measure code correctness only; out-of-corpus numbers measure model 
performance.

As of Piece 2 completion (2026-08-29):
- In-corpus scored cards: CT 7/25, ELP 8/21 (18 races)
- Out-of-corpus scored cards: CT 8/28, ELP 8/22, ELP 8/23 (30 races)
- Missing from log: CT 8/29 (results not yet published)

Every time dpv1.pkl is promoted (Piece 4), this cutoff shifts. Piece 3 
should probably read the cutoff from a metadata source, not hardcode it.

🎯 Piece 4: Weekly Retrain Pipeline

File: new scripts_dpv1/retrain_pipeline.py

Usage:

python scripts_dpv1/retrain_pipeline.py            # dry-run: check state, don't retrain
python scripts_dpv1/retrain_pipeline.py --execute  # actually do it

What it does:

Load any new result PDFs from <Track>/<track>-results-YYYY/ that aren't in the DB yet
CRITICAL: Remove any loaded upcoming cards from entries table (the NaN-as-False labeling bug). This is a documented failure mode — must be automated or the retrain corrupts labels.
Run train_dpv1.py final on the expanded corpus
Save output to dpv1_YYYYMMDD.pkl (never overwrite dpv1.pkl)
Run model_health.py --model <new> --last-n 100 and same for current
Print a side-by-side comparison:
   CANDIDATE:  dpv1_20260901.pkl
   CURRENT:    dpv1.pkl (dpv1.2.0-4track)
   
   Metric              Current    Candidate    Δ
   ITM (top pick)      57.0%      58.4%        +1.4pp   ✓
   Win (top pick)      22.0%      23.1%        +1.1pp   ✓
   Show ROI            -6.8%      -3.2%        +3.6pp   ✓
   
   RECOMMENDATION: Candidate outperforms on all metrics.
   To promote:  cp scripts_dpv1/dpv1_20260901.pkl scripts_dpv1/dpv1.pkl
DOES NOT auto-promote. Human decides.

Rules:

Log the retrain event (start time, end time, races added, records processed) to scripts_dpv1/logs/retrain_history.jsonl
If NaN-as-False bug guard fails (finds loaded upcoming cards), REFUSE to retrain and print clear error
Preserve last 5 model versions on disk; delete older ones
Order of Build
Piece 1 first — trivial, unblocks everything, starts building the audit trail immediately
Piece 2 second — needs Piece 1 to have data; once done, retro-score all recent cards
Piece 3 third — needs Piece 2 output; gives objective performance measurement
Piece 4 last — most complex, most valuable, needs Piece 3 to validate promotions
Notes for CC
All scripts respect the existing dpv1_runtime.py conventions (DEFAULT_DB, DEFAULT_MODEL, sys.path setup)
Use existing SQLite connection patterns from card_picks.py
JSONL over CSV (easier to append, easier to parse in Python)
Windows PowerShell friendly (no bash-isms)
Write a short PHASE_6E_LOGGING.md as you go documenting what got built