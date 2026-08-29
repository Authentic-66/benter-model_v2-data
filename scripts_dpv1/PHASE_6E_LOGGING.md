# Phase 6E — what got built

## Piece 1: Prediction logging (done)

`card_picks.py --save` now writes a third artifact alongside the `.txt` and
`.csv` in `picks/`: one JSON line per horse appended to
`scripts_dpv1/logs/predictions.jsonl`. The directory is created on demand.

Pieces 2 (`score_predictions.py`), 3 (`model_health.py`) and 4
(`retrain_pipeline.py`) are **not** built yet.

### Row schema

| field | type | notes |
|---|---|---|
| `prediction_id` | str | `{TRACK}_{date}_R{race}_pgm{pgm}_{YYYYmmdd-HHMMSS}` |
| `generated_at` | str | ISO 8601, second resolution, local time |
| `track` | str | uppercased |
| `race_date` | str | `YYYY-MM-DD`, as passed to `--date` |
| `race_num` | int | |
| `pgm` | str | program number — **string**, not int (coupled entries are `1A`, `5B`) |
| `horse_name` | str | |
| `p_itm` | float | model P(top 3), 4dp |
| `p_win` | float | Harville-inverted P(win), 4dp |
| `coverage` | float | **per-horse** feature coverage, 0–1 |
| `race_coverage` | float | race-level coverage — extra field, not in the spec; piece 3 buckets by race |
| `ml_odds` | str/null | morning line, null unless `--pp-file` was passed |
| `prime_power` | float/null | Brisnet Prime Power, null unless `--pp-file` was passed |
| `model_version` | str | e.g. `dpv1.2.0-4track` |
| `model_pkl` | str | basename of `--model`, e.g. `dpv1.pkl` / `dpv1_3track.pkl` |
| `rank` | int | 1 = top pick, by descending `p_itm` |
| `n_horses_in_race` | int | |
| `picks_file` | str | path relative to `scripts_dpv1/`, posix separators |

Missing values are `null` — NaN and the display table's empty-string
"no morning line" both normalise to `null` so downstream code has one case
to handle.

### Design decisions worth knowing

**`prediction_id` is stamped to the second, the picks filename to the minute.**
The filename convention was already minute-resolution and re-running a card
inside one minute (a late scratch, say) is routine — harmless for a file that
gets overwritten, fatal for an id that has to stay unique. Verified: a full
card plus a same-minute single-race re-run produced 121 rows and 121 distinct
ids.

**Append-only, never fatal.** `append_predictions()` catches `OSError` and
`prediction_rows()` is wrapped in a bare `except` at the call site. A full disk
or a locked file costs one log row and prints a warning; it never takes down
pick generation.

**Both models log.** `model_pkl` and `model_version` come from whatever
`--model` pointed at, so 4-track and 3-track runs land in the same file and are
separable at read time.

**`pgm` is a string.** The spec example shows `4`; program numbers are not
always integers. Piece 2 should join on `(track, race_date, race_num, pgm)`
with `pgm` compared as text.

### New flag

`--log-file PATH` overrides the default `logs/predictions.jsonl`. Only
consulted when `--save` is passed. Added for testing; not needed in normal use.

### Verification

```
python scripts_dpv1/card_picks.py --track CT --date 2026-08-28 --save
```
→ 112 rows across 13 races, 7–11 rows per race, all ids unique.

```
python scripts_dpv1/card_picks.py --track CT --date 2026-08-28 --race 5 \
    --pp-file CharlesTown/ct-pps-files/ctx0828y.pdf --save
```
→ 9 more rows appended, `ml_odds` and `prime_power` populated.
