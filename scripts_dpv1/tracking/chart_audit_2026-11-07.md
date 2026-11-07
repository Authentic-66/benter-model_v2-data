# Chart audit, 2026-11-07 (read-only)

Doug asked for every chart file on disk that looks truncated or only
partly loaded, like `EVD061126USA.pdf` (R1-R7 only). Nothing in the DB or
on disk was changed. Script: `tracking/chart_audit.py <out_dir>` (writes
`chart_audit_all.csv`, one row per file).

## How "expected" was found

A file can end cleanly and still be short. `EVD061126USA.pdf` stops after
a complete R7, and the parser's `races_found` = `races_loaded` = 7, so the
file alone cannot show the gap. The check uses the charts' **Last Raced**
column instead (`entries.last_raced_raw`, e.g. `11Jun26 8EVD`). Every later
chart names the date, race number and track each horse last ran. For each
track/date, the expected races are all the race numbers those later
charts name. A named race that is not in the DB means a missing race.

* 303,197 Last Raced strings parsed. The 20,045 that did not are `---`
  (first-time starters) or foreign tracks with no race number.
* Mixed QH/TB cards (DED, EVD, LAD) have gaps in race numbers by design
  (QH races are purged). TB horses never point to QH races, so gaps don't
  cause false flags.
* **Expected counts are lower bounds.** A race shows up only if one of
  its runners later ran at a loaded track. A missing race that nobody
  re-ran from would not be caught.

Scope: 5,137 chart PDFs in `*results*` folders. 4,900 are on the eight
loaded tracks (CT, DED, ELP, EVD, FG, GP, LAD, MNR). The other 237 (FAN
60, FP 71, MVR 106) have never been loaded, so they are not partial loads.
They are listed at the end only.

## Files to delete and re-download (11)

55 races are missing in all (lower bound).

### A. File is short: every page reads, races are missing at the end

| track | date | file (folder) | races in file / DB | expected (at least) | missing | later refs |
|---|---|---|---|---|---|---|
| CT | 2026-05-01 | `CharlesTown/ct-results-2026/CT050126USA.pdf` | 7 (R1-R7) | 9 | R8, R9 | 4, 6 |
| EVD | 2026-06-11 | `Evangeline Downs/evd-results-2026/EVD061126USA.pdf` | 7 (R1-R7) | 8 | R8 | 10 |
| MNR | 2023-06-18 | `Mountaineer/mnr-results-2023/20230618-usa-mnr-a-d.standard.pdf` | 7 (R1-R7) | 8 | R8 | 8 |

* **EVD 2026-06-11 is already deleted** on disk (git shows it as deleted,
  not committed). The deletion was made outside this session.
* MNR 2023-06-18 is already a long Equibase name and ends with the
  attendance/handle line. Equibase's own file may simply be missing R8.
  If the new download is the same, re-downloading won't recover R8.

### B. Races are in the file as images, so the parser can't read them

pdfplumber gets no text from these pages ("inline image" warnings), so the
parser skips them. The races after them loaded normally.

| track | date | file (folder) | races in DB | expected (at least) | missing (on image pages) |
|---|---|---|---|---|---|
| CT | 2022-03-18 | `CharlesTown/ct-results-2022/20220318-usa-ct-a-d.standard.pdf` | 7 (R1, R3-R8) | 8 | R2 (page 2) |
| GP | 2019-07-18 | `Gulfstream Park/gp-results-2019/20190718-usa-gp-a-d.standard.pdf` | 6 (R4-R9) | 9 | R1-R3 (page 1) |
| GP | 2021-04-04 | `Gulfstream Park/gp-results-2021/20210404-usa-gp-a-d.standard.pdf` | 4 (R1, R2, R6, R10) | 10 | R3-R5, R7-R9 (pages 3, 6) |
| GP | 2024-02-21 | `Gulfstream Park/gp-results-2024/20240221-usa-gp-a-d.standard.pdf` | 1 (R9) | 9 | R1-R8 (page 1) |
| GP | 2024-04-05 | `Gulfstream Park/gp-results-2024/20240405-usa-gp-a-d.standard.pdf` | 5 (R4-R8) | 8 | R1-R3 (page 1) |
| MNR | 2022-08-07 | `Mountaineer/mnr-results-2022/20220807-usa-mnr-a-d.standard.pdf` | 1 (R8) | 8 | R1-R7 (pages 1-2) |

All six are already long Equibase names, so Equibase served them this way.
A re-download may come back with the same image pages. If it does, those
races can't be loaded without OCR, which would be a separate decision.

### C. File is damaged and won't open (nothing loaded)

| track | date | file (folder) | races in DB | expected (at least) | error |
|---|---|---|---|---|---|
| EVD | 2023-08-10 | `Evangeline Downs/evd-results-2023/20230810-usa-evd-a-d.standard.pdf` | 0 | 9 | `Non-Ascii85 digit found` |
| FG | 2025-02-15 | `Fair Grounds/fg-results-2025/20250215-usa-fg-a-d.standard.pdf` | 0 | 14 | `Non-Ascii85 digit found` |

Both have `success = 0` rows in `parsed_files`, and the pipeline retries
them on every run.

## Status, 2026-11-07

* EVD 2026-06-11: Doug deleted the short file and downloaded
  `20260611-usa-evd-a-d.standard.pdf` (R1-R8, Dat Hint in R8).
* The other 10 files were **moved, not deleted** (`git mv`) into a
  `_bad_charts/` subfolder of their own results folder, so the download
  script fetches fresh copies. `retrain_pipeline.discover_charts` globs
  `*-results-*/*.pdf` (one level), so it ignores `_bad_charts/`. The old
  batch tools `equibase_pdf_parser.py batch` and `db_loader.py pipeline`
  use `rglob` and **would** find them; pass `--exclude _bad_charts` if
  either is ever run on a results folder.
* The DB is unchanged until the replacements are loaded: those days
  still hold the partial data.

## Result after re-download and load (2026-11-07, PHASE_6E "Results load, 2026-11-07")

**Fixed and loaded (3):** CT 2026-05-01 (now 9 races), EVD 2026-06-11
(now 8, with Dat Hint's R8), FG 2025-02-15 (now 14).

**Came back byte-identical to the bad copy: KNOWN GAPS (8).** These were
not reloaded. The identical re-downloads sit in the results folders and
the old copies in `_bad_charts/`.

| track | date | problem | races in DB / expected |
|---|---|---|---|
| CT | 2022-03-18 | image page (R2) | 7 / 8 |
| GP | 2019-07-18 | image page (R1-R3) | 6 / 9 |
| GP | 2021-04-04 | image pages (R3-R5, R7-R9) | 4 / 10 |
| GP | 2024-02-21 | image page (R1-R8) | 1 / 9 |
| GP | 2024-04-05 | image page (R1-R3) | 5 / 8 |
| MNR | 2022-08-07 | image pages (R1-R7) | 1 / 8 |
| MNR | 2023-06-18 | Equibase file has no R8 | 7 / 8 |
| EVD | 2023-08-10 | file damaged (won't open) | 0 / 9 |

Recovering the image-page races would need OCR (a separate decision).
Equibase may not have a better copy of the other two.

**New from the MNR 2026 load:** `20261005-usa-mnr-a-d.standard.pdf` is
damaged ("Unexpected EOF") and not loaded. This is the Wave Maker chart
from the DED 11/05 card. **KNOWN GAP (2026-11-07):** Doug confirmed the
file is corrupted on Equibase's side, so it is skipped, not re-downloaded.

The rerun of `chart_audit.py` after the load shows exactly these 9 files
and nothing else.

## Other checks (all clean)

* `races_found` = `races_loaded` for every parsed file on the loaded tracks.
* No track/date has two files on disk.
* Every DB race day was loaded from the file now on disk for that date.

## Loading the re-downloads (long Equibase name)

`retrain_pipeline.load_charts` replaces the day; it does not duplicate it.
It reads the track and date **from the chart's contents**, not the file
name. If that day has any entries in the DB, it calls `purge_card(track,
date)` first: features, speed figures, entries, exotic rows, races and
the race day are all deleted. Then it loads the new file in the same
transaction. So `20260611-usa-evd-a-d.standard.pdf` wipes the 7-race EVD
6/11 day and loads the full card. Also:

* `discover_charts` sees the new name as new (it isn't in `parsed_files`,
  and its sha256 differs from the old file's), so it is picked up.
* The old short-name `parsed_files` row stays as a history row. It does
  no harm once the old file is gone. If the old file stays on disk, the
  load still won't duplicate anything (purge by date). This audit would
  then list the date under "two files on disk".
* The parse cache (`scripts/ct_cache/<stem>.json`) is keyed by file name
  and sha, so a new name always gets a fresh parse.
* For the two damaged files there is no day in the DB, so the new file
  loads fresh.

Suggested order when they arrive: back up the DB; dry-parse each new file
and check its race count against the "expected" column above (for group
B, also check every page has a "Race N" header); load in one
`load_charts` batch; check one race day per date with the expected
race count; rebuild speed figures and features; rerun this audit, which
should show none of these dates.

## Not loaded at all (for reference, not partial loads)

FAN 60, FP 71, MVR 106 chart files are on disk with no `parsed_files`
rows. They are tracks outside the corpus. Loading them would be a
model-input decision.
