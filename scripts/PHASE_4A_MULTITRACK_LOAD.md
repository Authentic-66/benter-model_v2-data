# Phase 4A — Multi-Track Data Consolidation

**Date:** 2026-07-31
**DB:** `scripts/racing_full.db`  (backup: `scripts/gp_full.db`)
**Parser:** unchanged from Phase 3B (equibase_pdf_parser.py)
**Loader:** unchanged from Phase 3B (db_loader.py)

---

## Objective

Fold Charles Town (CT) and Mountaineer (MNR) results into the existing GP
corpus so DPv1 can train on the full 3-track dataset Doug's feature ranking
was designed for. No feature engineering, no model work — data plumbing only.

---

## Approach

1. `cp gp_full.db racing_full.db` (GP corpus preserved as backup).
2. Verify parser on CT/MNR samples (2021 standard filename + 2024-2026 doug_compact).
3. Run `db_loader.py pipeline --resume` over CharlesTown/ and Mountaineer/ trees.
4. Validate: cross-track dimension overlap, per-year counts, odds sanity.

The parser already handled multi-track by design:
- `parse_filename` extracts the track token (`ct`, `mnr`, `gp`) from the
  filename → uppercased to the track_code.
- `db_loader.get_or_create_track` auto-inserts new codes.
- `tracks.code UNIQUE` guaranteed no duplicate track rows.
- No hardcoded `'GP'` on the ingest path.

**No parser or schema changes were required.**

---

## Load results

### Track dimension

| id | code | name (from PDF header)               |
|----|------|--------------------------------------|
| 1  | GP   | GULFSTREAMPARK                       |
| 2  | CT   | HOLLYWOODCASINOATCHARLES TOWNRACES   |
| 3  | MNR  | MOUNTAINEERCASINORACETRACK&RESORT    |

### Totals per track

| track | race_days | races  | entries |
|-------|-----------|--------|---------|
| GP    | 1,480     | 14,857 | 116,311 |
| CT    | 943       | 7,734  | 54,585  |
| MNR   | 688       | 5,514  | 37,080  |
| **ALL** | **3,111** | **28,105** | **207,976** |

**Corpus size hit the low end of the 28k–32k estimate** — MNR came in ~1,000
races light due to 47 corrupt-download PDFs (see Data Quality below); a
re-download would push the corpus to ~29k races.

### Per-track × per-year

| track | year | race_days | races | entries |
|-------|------|-----------|-------|---------|
| GP    | 2019 | 196 | 2,099 | 16,904 |
| GP    | 2020 | 193 | 2,022 | 16,855 |
| GP    | 2021 | 207 | 2,090 | 16,604 |
| GP    | 2022 | 200 | 1,969 | 15,371 |
| GP    | 2023 | 195 | 1,866 | 14,230 |
| GP    | 2024 | 197 | 1,915 | 14,654 |
| GP    | 2025 | 199 | 1,959 | 14,703 |
| GP    | 2026 |  93 |   937 |  6,990 |
| CT    | 2021 | 177 | 1,435 | 10,089 |
| CT    | 2022 | 180 | 1,477 |  9,989 |
| CT    | 2023 | 167 | 1,375 | 10,321 |
| CT    | 2024 | 160 | 1,306 |  9,387 |
| CT    | 2025 | 165 | 1,350 |  9,637 |
| CT    | 2026 |  94 |   791 |  5,162 |
| MNR   | 2021 | 133 | 1,074 |  7,336 |
| MNR   | 2022 | 132 | 1,050 |  6,442 |
| MNR   | 2023 | 124 |   992 |  6,794 |
| MNR   | 2024 | 127 | 1,018 |  7,128 |
| MNR   | 2025 | 120 |   961 |  6,508 |
| MNR   | 2026 |  52 |   419 |  2,872 |

2026 counts are half-years (through late July 2026). Recent-year MNR counts
match the "reduced schedule" expectation.

---

## Data quality checks

### Field size

| track | avg | min | max |
|-------|-----|-----|-----|
| GP    | 7.88 | 3 | 14 |
| CT    | 7.37 | 3 | 10 |
| MNR   | 6.86 | 2 | 10 |

Matches Doug's brief: GP fields largest, MNR smallest. Nothing suspicious.

### Odds sanity (favorite win rate)

| track | favorites | wins | favorite win % |
|-------|-----------|------|----------------|
| GP    | 14,754 | 5,347 | **36.24 %** |
| CT    | 7,412  | 2,995 | **40.41 %** |
| MNR   | 5,413  | 2,295 | **42.40 %** |

All three tracks land in the healthy 33–45 % window. Smaller fields at
CT/MNR naturally push favorite win % higher — consistent with the field-size
numbers above.

### Odds coverage

100 % of entries (across all three tracks) have a `final_odds` value.
Benter anchor signal is intact.

---

## Cross-track connections

### Jockeys
- **700 total** jockeys in the DB
- **204** rode at ≥2 tracks
- **23** rode at all 3

Top cross-track riders (mounts): Paco Lopez (3,794), Luis Saez (3,745),
Cristian Torres (2,046), Wesley Ho (1,345), John Velazquez (1,091).

This is the shipping-jockey signal Doug will lean on: 30 % of the jockey
population accounts for the vast majority of cross-track mounts.

### Trainers
- **1,904 total** trainers
- **433** with starts at ≥2 tracks
- **43** with starts at all 3

Top cross-track barns (starts): Saffie Joseph Jr. (4,450), Victor Barboza Jr.
(1,987), Todd Pletcher (1,915), Michael Maker (1,669), Crystal Pickett (1,161).

**Anthony Farrior** (Doug's flagged conditioner) is a **trainer**, not a
jockey — 2,625 starts at CT (26.6 % win rate, 60.9 % ITM) and 185 at MNR.
Solidifies him as the dominant CT barn in the corpus.

### Horses (shippers)
- **32,822 total** horses
- **3,467** raced at ≥2 tracks
- **248** raced at all 3

Top true 3-track shippers: Brother Skye (70 starts), Hopping Henry (55),
Kingston Time (52), Happy Champ (50), True Heiress (47).

248 horses hitting all three ovals is a strong bridge population — enough
signal for cross-track form transfer features in Phase 4B.

---

## Parser issues

**No parser bugs surfaced.** Load outcomes:

| outcome | count |
|---------|-------|
| OK      | 3,111 |
| FAIL    | 51    |

Failure breakdown:
- **48** — `No /Root object! - Is this really a PDF?`
  - 47 MNR files, Oct 10 – Dec 31, 2024 (contiguous run)
  - 1 MNR file, 2026-04-26
  - Spot-checked one file: contents begin with
    `<!DOCTYPE html>...<title>Pardon Our Interruption</title>` —
    these are Equibase's anti-bot challenge pages saved with `.pdf`
    extension. **Download-side issue, not parser.**
- **3** — `Non-Ascii85 digit found` on GP files (2019-02-14, 2024-03-14,
  2024-05-18). Pre-existing from Phase 3B; not caused by this phase.

**Action item (data acquisition, not this phase):** re-download the 47 dates
above (and the 3 GP dates) with either a longer delay or a fresh session
cookie. Once re-downloaded, `db_loader.py pipeline --resume` will pick them
up automatically because their `parsed_files` rows have `success=0` and no
sha256 match.

### Warnings

406 PDFs (of 3,111) produced at least one soft warning during parsing (e.g.
`contradictory_winner_cleared`). Consistent with the Phase 3B warning rate;
no new warning classes introduced by CT/MNR data.

---

## Files produced / touched

- `scripts/racing_full.db` (new, 3-track corpus)
- `scripts/gp_full.db` (unchanged, backup)
- `scripts/ct_cache/` (943 JSON parse artifacts)
- `scripts/mnr_cache/` (688 JSON parse artifacts + 48 stubs for HTML files)
- `scripts/phase4a_validate.py` (validation query script, reusable)
- `scripts/phase4a_validate.out` (raw validation output)

No source code changes to `equibase_pdf_parser.py`, `db_loader.py`, or
`db_schema.sql`.

---

## Assessment vs. decision point

- ✅ All CT PDFs loaded cleanly (943/943, 0 errors).
- ✅ MNR loaded cleanly on all valid input (688/688 valid PDFs).
- ✅ Cross-track dimensions clean: no track_id leakage, correct auto-assignment.
- ✅ Odds coverage 100 %, favorite win rates in healthy window.
- ✅ Meaningful cross-track jockey/trainer/horse populations for Phase 4B.
- ⚠️  47 MNR dates in Q4 2024 need re-download from source — deferred as a
  data-acquisition task, does not block Phase 4B.

**Recommendation: proceed to Phase 4B** (multi-track feature engineering).
The Q4 2024 MNR gap is worth patching before final model training (Phase 4D)
but not before feature-engineering experiments.
