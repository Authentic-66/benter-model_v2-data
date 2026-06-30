# Benter Model v2 — Data Pipeline

Phase 3A artifacts: a PDF parser, a SQLite schema, and a database loader for
Equibase result charts. The current build targets Gulfstream Park
(2019-2026, ~1,500 PDFs, ~15,000 races); the same pipeline is designed to
extend to CT, MNR, EVD, FP, FG, MVR, DD in Phase 3B.

## Layout

```
scripts/
  equibase_pdf_parser.py   ← parse one PDF or a directory of PDFs into JSON
  db_schema.sql            ← SQLite schema (tracks, races, entries, ...)
  db_loader.py             ← load parsed JSON into the SQLite DB
  run_validation.py        ← Phase 3A 100-PDF validation harness
  analyze_full_load.py     ← Phase 3B full-corpus analyzer
  PHASE_3A_VALIDATION.md   ← Phase 3A report (100-PDF sample)
  PHASE_3B_FULL_LOAD.md    ← Phase 3B report (full 1,483-PDF corpus)
  gp_2019_2026.db          ← 100-PDF validation sample DB (~6 MB)
  gp_full.db               ← production DB, 14,857 races, 116k entries (~73 MB)

Gulfstream Park/
  gp-results-2019/ ... gp-results-2026/   ← chart PDFs (3 filename conventions)
  gp-pps-files/                           ← Brisnet PP files (Phase 3C)
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
- **Phase 3B:** full GP corpus load (1,480 PDFs, 14,857 races) ← done; see
  `scripts/PHASE_3B_FULL_LOAD.md`
- **Phase 3C:** Brisnet PP parser, speed figures + additional tracks
- **Phase 3D:** v10 workbook signal integration
- **Phase 3E:** feature engineering pipeline (target 100-130 variables)
- **Phase 3F:** model training (time-decay weighted, 7-year window)
- **Phase 3G:** validation infrastructure

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
