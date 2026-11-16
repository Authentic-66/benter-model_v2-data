# Chart archive: Equibase result charts, US/Canada Thoroughbred, 2022 → today

Plan and prep only (2026-11-15). **Claude made no request to Equibase.** Doug runs
every download with `tools/chart_downloader.ps1`. Nothing pushed.

**Status 2026-11-16:** feeders and the feeder follow-up are done (§7). Archive
PDFs are **not committed** (`.gitignore`). Live-track charts (the
DED/EVD/LAD/FG/CT/GP/ELP/MNR folders) are committed **only together with the
change that loads them into the DB** (Doug 11/16); the logs are committed each
time. Next: the ARP probe (119 requests) and group b, one batch per session.

```powershell
cd 'D:\Benter Model_v2 Data\benter-model_v2-data'
.\tools\chart_downloader.ps1 -JobsCsv .\scripts_dpv1\tracking\chart_archive\batches\probe_arp_01.csv
.\tools\chart_downloader.ps1 -JobsCsv .\scripts_dpv1\tracking\chart_archive\batches\batch_03.csv
```

**Live DB safety.** The card-night runbook only loads the chart it names
(`load_chart.py <one pdf>`), and the side-by-side reads only the DB, so new
files in the live folders change nothing by themselves.
`retrain_pipeline.py --execute` scans `CharlesTown`, `Ellis`, `Gulfstream
Park` and `Mountaineer` (plus `Delta Downs`, `Evangeline Downs`, `Fair Grounds`
and `Fairmount Park` with `--all-tracks`) and loads every chart not yet in
`parsed_files`, **but since 11/16 it holds every chart-archive download** (a
chart whose track and date are a job in a batch file here, recheck rows
excepted) and lists them under "HELD". Only `--load-archive` loads them, for a
planned rebuild (RUNBOOK_card_night.md). On 11/16 it holds the 8 CT test-batch
charts (11/04–11/14), which a plain `--execute` would otherwise have loaded.
`db_loader.py pipeline --pdf-dir` and `_load_ct_backlog.py`
(`ct-results-2026`) also load a whole folder; neither is in the runbook. No
scheduled task runs any project script (checked 11/16).

Do **not** rerun `build_plan.py` before batches 03–07: it renumbers the
batches (group a would shrink to the 2 LS retries) and group b is unchanged
by the feeder logs.

Feeders = `batch_01` (1,500 requests: PRM, ARP, GIL, LS, ATO, part of RP) +
`batch_02` (578: rest of RP, SWF): about 2.7 h + 1 h at the test's measured
pace (6.5 s per request), about 1,200 charts expected.

## Files

| file | what |
|---|---|
| `tracks.csv` | master list: 126 track codes from the 2023 XMLs, with category, country, status, 2023 race days/dates/months/weekdays, TwinSpires check, DED PP last-race count, charts on disk, priority |
| `estimate_by_track_year.csv` | per track × year: candidate dates, already on disk, requests, expected race days, expected new charts, expected MB |
| `batch_00_test.csv` | test batch, 52 rows, **run 2026-11-15** (kept as run; the build no longer rewrites it) |
| `batches/batch_01.csv` … `batch_20.csv` | all jobs in priority order, ≤1,500 requests each, **a new batch at each group boundary** (01–02 feeders, 03–07 group b, 08–20 group c); `batch_index.csv` lists the tracks in each |
| `extra_pp_only_tracks.csv` | known HCN / EUR dates from DED PP lines (not in any batch; see §1) |
| `build/` | the read-only scripts that made all of the above, and `inputs/`. `build_plan.py` also reads every `chart_download_log_*.csv` in the repo root (ok = on disk, 404 = never asked again) and `known_gaps.csv` (never asked again; §10) |
| `known_gaps.csv` | charts corrupt at Equibase: excluded from batches, each retried once by hand (§10) |
| `../../../tools/chart_downloader.ps1` | the downloader |

## 1. Master track list (`tracks.csv`)

**Source:** `D:\From Downloads\2023 Result Charts\` (4,906 TCH chart XMLs,
`<trk><yyyymmdd>tch.xml`, all 2023). Each race has a `<BREED>` tag (TB 35,989
races, QH 6,016, mixed 559, Arabian 54). A **race day** below = a day with at
least one Thoroughbred race; QH-only nights (e.g. at DED, EVD, LAD) are not
counted. The XMLs have no country field: country is from the track.

| category | tracks | notes |
|---|---|---|
| main (26+ TB days in 2023) | 55 | |
| small / fair meet (≤25 TB days) | 41 | includes feeders GIL, ATO, SWF |
| steeplechase / hunt meet | 23 | AIK, CAM, CHA, CHE, CHL, FH, FX, GLN, GN, GRM, GV, MAL, MID, MON, MTP, ODH, PMT, PW, SHW, TRY, UNI, WIL, WNT (1–3 days a year; last in the queue) |
| QH-only in 2023 (skipped) | 7 | AJX, FPL, FTP, JRM, **RET**, SRM, WBR. Retama had no TB race in 2023 (QH and Arabian only) although TwinSpires lists it |
| dropped | 1 | **CMR** (Camarero, Puerto Rico): 404 on a known 2023 race day under `usa`; Doug 11/15: US and Canada only |

**Country:** Canada = WO, ASD, HST, FE, CTM, CTD, LBG, GPR, MIL (and AJX, QH).
**Canadian charts are under `can`** (test: WO 2023-08-27 404 under `usa`, ok
under `can`), so every job for those nine tracks has `country=can` (2,673
jobs). The file is saved as `<yyyymmdd>-can-<trk>-a-d.standard.pdf`.

**Closed tracks:**

| code | track | status used in the plan |
|---|---|---|
| GG | Golden Gate Fields | closed; last race day **2024-06-09**; probed only to that date |
| PLN | Pleasanton | closed (TwinSpires). 2023 meet is in the XMLs (6/16–7/09). **Year of the last meet not verified:** the 2024 window is probed (31 requests), 2025+ not |
| GPW | Gulfstream Park West | closed, not in the 2023 XMLs; no probes. **Not verified whether it raced in 2022**; if it did, those charts are not in the plan |
| PM | Portland Meadows | closed 2019 (from memory, not verified); out of scope |
| NP | Northlands Park | closed; TB racing ended 2016 (from memory, not verified); out of scope |

**TwinSpires cross-check** (Doug's copy of twinspires.com/race-tracks; the
page itself timed out twice for me). On the TwinSpires list but **not in the
2023 XMLs:** Stockton, Les Bois Park, Atlantic City, and the three closed ones
(GPW, PM, NP). Their Equibase codes and race dates are unknown, so they have no
jobs. In the XMLs with TB racing but **not on TwinSpires' list** (the list says
"most" tracks): 58 codes, mostly fair, hunt and small meets, plus BAQ, CNL,
FL, MED, MVR, TIM, WYO, CMR, GPR, LBG and the feeders ATO, GIL, SWF. All are
kept.

**DED PP last-race codes not in the 2023 XMLs** (all 20 DED PP files this meet,
1,651 horses):

* **HCN**: 5 last-race horses, 56 PP lines, all 2026 (Fri–Sun, 7/24–8/23),
  Nebraska horses (e.g. Husker Butch). **Probably Harrah's Columbus, Nebraska,
  replacing CLS (Columbus); not verified.** If so, the CLS jobs for 2024–2026
  will mostly 404, and HCN needs its own windows. 13 known dates are in
  `extra_pp_only_tracks.csv`.
* **EUR**: Eureka Downs, Kansas. 2 last-race horses, one date (2026-10-17).
* **FPK**: Brisnet's code for Fairmount Park (PP lines 2025). Equibase uses
  **FAN for 2022–2024** (test: 2022-08-06 ok as FAN, 404 as FP) and **FP from
  2025**. The batches follow that split.
* Every other DED PP last-race code is also a code in the 2023 XMLs (same letters; I did not check each is the same track).

## 2. Inventory (charts already on D:)

Scanned all of D: for both naming styles (`<yyyymmdd>-usa-<trk>-a-d.standard.pdf`
and `<TRK><MMDDYY>USA.pdf`, plus `MVR030326USA8.pdf`-style suffixes):
**5,157 files, 5,147 good charts, 833 MB** (about 166 KB each; recent GP charts
are about 370 KB). 10 are in `_bad_charts` folders. Long name 4,891, short 265.
**Free space on D: 705 GB** (228 GB used of 932 GB).

| track | folder | 2022 | 2023 | 2024 | 2025 | 2026 | older |
|---|---|---|---|---|---|---|---|
| CT | CharlesTown | 180 | 167 | 160 | 165 | 127 (109 short) | 2021: 177 |
| DED | Delta Downs | 77 | 83 | 73 | 76 | 52 (22 short) | 2021: 75 |
| ELP | Ellis | 23 | 41 | 25 | 27 | 28 | 2021: 31 |
| EVD | Evangeline Downs | 84 | 61 | 71 | 73 | 73 | |
| FG | Fair Grounds | 84 | 78 | 92 | 76 | 51 | 2021: 21 |
| FAN / FP | Fairmount Park (`fp-results-*`) | – | – | 60 (FAN) | 53 (FP) | 18 (FP) | |
| GP | Gulfstream Park | 200 | 195 | 197 | 199 | 99 | 2019–21: 596 |
| LAD | Louisiana Downs | 84 | 61 | 70 | 62 | 56 | |
| MNR | Mountaineer | 132 | 124 | 127 | 120 | 103 | 2021: 133 |
| MVR | Mahoning Valley (**`mvr-<year>-results`**) | – | – | – | 44 | 63 | |

Outside the repo: `D:\From Downloads\MVR030326USA8.pdf` and
`D:\20261005MNRUSA0.pdf` (the corrupted MNR 10/05). Every track in
`tracks.csv` has a `charts_on_disk` column.

The downloader indexes **every** chart under the repo by (track, date) at start,
in both naming styles, so neither the MVR folder layout nor short names cause a
second download.

## 3. Race-day windows and the request estimate

* **2023:** the exact XML race days (no guessing): 3,646 requests, all
  expected hits.
* **2022, 2024, 2025, 2026 (to 11/14):** a date is probed if (a) the same
  month-day in 2023 is within **14 days** of a 2023 race day at that track
  (this keeps split meets split) and (b) it falls on a **weekday the track raced
  in 2023**. Real dates from DED PP running lines are added even outside the
  window.
* **Atokad (ATO) has its own rule.** It races 2–5 days a year and the meet
  moves (2023: Jun 3–4; 2026 from PP lines: Aug 29–30, Sep 5–7). The
  2023-based guesses for 2022, 2024 and 2025 all 404'd (Jun 5, Jun 2, Jun 1).
  So for those years and 2026: **every Saturday May 1 – Oct 31** plus the
  PP-known dates (26–29 requests a year, 108 in all, vs 38 before). A race
  weekend almost always has a Saturday; after `batch_01`, each Saturday hit
  gets a small follow-up (Fri, Sun, Mon of that weekend) built from the log.
* **Tracks with charts on disk:** the earlier downloads swept their date ranges,
  so for those years only dates **before the first or after the last chart on
  disk** are probed. A gap inside the range is treated as a non-race day.
* Closed tracks are cut at the closing date (GG 2024-06-09; PLN after 2024).
* **Logs feed back in:** a date the downloader logged `ok` counts as on disk,
  and a date it logged `none` (404) is never put in a batch again. The test
  charts count as single dates, not as swept ranges.
* **End date 2026-11-14.** The test showed charts are at the long-name address
  the next day (CT 11/14 fetched 11/15), so nothing is held back. Dates after
  11/14 need a later top-up batch (rerun `build_plan.py` with a new `END`).

**Expected race days** for a year = the track's 2023 TB days (2026 prorated to
11/14). **Size** = 16.1 KB per race (median of the charts on disk) × the track's
races per day.

Rebuilt 2026-11-15 after the test (CMR dropped, Canada on `can`, ATO Saturday
scan, test charts and 404s taken out). Before: 29,317 requests, ≈17,600 charts.

| year | requests | expected new charts | expected MB |
|---|---|---|---|
| 2022 | 6,469 | 3,447 | 474 |
| 2023 | 3,426 | 3,426 | 471 |
| 2024 | 6,233 | 3,346 | 461 |
| 2025 | 5,984 | 3,217 | 444 |
| 2026 | 5,605 | 3,058 | 422 |
| **total** | **27,717** | **≈16,500** | **≈2.3 GB** |

| priority group | batches | requests | expected new charts | expected MB |
|---|---|---|---|---|
| a. feeders | 01–02 | 2,078 | 1,202 | 178 |
| b. DED PP last-race tracks | 03–07 | 7,038 | 4,379 | 621 |
| c. everything else | 08–20 | 18,601 | 10,913 | 1,474 |

About 60% of requests should be hits; the rest are 404s on non-race days. The
test ran at **6.5 s per request** (52 in 5 min 37 s), so a 1,500-request batch
takes about **2.7 hours** and all 20 batches about **50 hours**. Disk is not a
constraint (2.3 GB of 705 GB free).

**Known weak spots:**
* A track that changed its race weekdays after 2023 will have missed dates
  (e.g. raced Wed in 2025 but not in 2023). Check each track's hit count
  against expected after its batch; for a big shortfall, probe the other
  weekdays.
* Tracks or meets that raced in 2022 or 2024–2026 but **not in 2023** have no
  window (HCN, EUR, possibly GPW 2022, Stockton, Les Bois, Retama TB).
* Weekday and 14-day buffer are estimates; dates far outside the 2023 meet
  (a meet moved by a month) will be missed.

## 4. Priority order

* **a. Feeders:** PRM, ARP, GIL, LS, ATO, RP, SWF (batch_01 and batch_02).
* **b. DED PP last-race tracks, by count this meet** (all 20 PP files, 1,651
  horses; 121 with no running line): EVD 561, DED 480, LAD 335, FG 18, CBY 10,
  OP 5, then DEL, ELP, GP, HOU, IND, WO (2 each), then ALB, BAQ, BTP, CD, CNL,
  CT, DMR, FON, KEE, LEG, MED, MNR (1 each). EVD/DED/LAD/FG/GP/CT/MNR are
  mostly on disk already, so they cost few requests. (SWF 19, PRM 16, LS 15,
  ARP 13, GIL 13, ATO 7, RP 7 are the feeders in group a.)
* **c. Everything else**, main tracks by 2023 race days, then small/fair
  meets, then steeplechase/hunt meets last.

Within a batch: track by track, oldest date first.

## 5. Downloader (`tools/chart_downloader.ps1`)

Built around Doug's `Get-Chart`. **The web request is unchanged:** plain
`Invoke-WebRequest -UseBasicParsing`, no headers, no user-agent. Nothing tries
to get past a bot check; a block stops the run. The only change inside
`Get-Chart` is that the `usa` in the URL and file names comes from the job's
`country` column (default `usa`).

* **Jobs from a CSV:** `track,country,folder,date` (`date` = yyyy-MM-dd;
  optional `recheck`, test batches only). Saves to
  `<Root>\<folder>\<trk>-results-<year>\`.
* **Stops the whole run** after **3 HTTP 403s** (total, as before) or **3
  not-a-PDF responses in a row** (the bot-check page is an HTTP 200 HTML page,
  so it never counts as a 403). The stop is logged as a `stop` row.
* **Per-run cap** `-MaxRequests` (default 1,500) and a **random 4–8 s delay**
  between requests. Skips are not requests and are not delayed.
* **Skips** charts on disk in either naming style anywhere under the repo
  (index built at start), and `Get-Chart` keeps its own check of the target
  folder.
* **Log:** the same CSV (`timestamp,track,date,status,detail`), default
  `chart_download_log_<yyyyMMdd>.csv` in the repo root. **Summary:** one line
  per track, then
  `Downloaded: X   Already had: Y   No race day: Z   Errors: N`.
* **`-DryRun`:** no requests, nothing logged; prints what it would fetch.
  Checked on the test batch (52 would-fetch, 5,146 charts indexed) and, after
  the rebuild, on batch_01 (1,500 would-fetch, 0 already on disk, 5,187
  indexed) and batch_05 (WO rows go to `can`).
* **Empty folders (added 11/15):** a 404 or error now removes the year folder
  if it is empty, so a no-race probe leaves no empty `xxx-results-<year>`
  folder. The request line is untouched.

**Fairmount folder:** the FAN-coded jobs (2022–2024) create `fan-results-<year>`,
while the existing folders are `fp-results-<year>`. Skipping is unaffected (the
index is by track code and date, and FAN/FP are both indexed). Move them by hand
if you want one folder.

## 6. Test batch (`batch_00_test.csv`, 52 requests, about 6 minutes)

| rows | what | tells us |
|---|---|---|
| 35 | one date per feeder per year 2022–2026. 2023 dates are from the XMLs; other years from DED PP running lines where a horse ran there (ARP 2025, ATO 2026, …), otherwise **estimated** from the 2023 pattern (`date_source` column) | the URL pattern works for each feeder and year; an estimated-date 404 means "no race that day", not a failure |
| 2 | WO 2023-08-27 with `usa`, then the same date with `can` (`recheck=1`, so both run) | which country path Canadian charts use |
| 1 | CMR 2023-07-07, `usa` | whether Puerto Rico is under `usa` |
| 2 | Fairmount 2022-08-06 as FAN, then as FP | which code Fairmount used in 2022 |
| 8 | CT 11/14 back to 11/04 (Wed–Sat; 1–11 days old), not on disk | how soon a chart appears at the long-name address |
| 4 | CT 10/28–10/31 (15–18 days old), on disk under the short name only; `recheck=1`, saved to `chart_archive_recheck\CharlesTown\` | whether the long-name address has caught up by 2–3 weeks. Delete that folder afterwards |

**Results (Doug ran it 2026-11-15, 21:15–21:20; 52 requests, 45 ok, 7 × 404,
0 errors, no bot check, no 403):**

| question | answer | change made |
|---|---|---|
| long-name URL, 2022–2026 | works every year | none |
| Canadian path | WO: 404 under `usa`, ok under `can` | `country=can` for all 9 Canadian tracks |
| Puerto Rico | CMR 2023-07-07 404 (a known race day) | CMR dropped (Doug: US and Canada only) |
| Fairmount 2022 code | FAN ok, FP 404 | FAN 2022–2024, FP 2025+ |
| recent-date lag | CT 11/04–11/14 all ok on 11/15 (11/14 one day old) | nothing held back |
| bot check at 4–8 s | none, no 403 | none |
| feeder guesses | 404: ARP 2024-07-29 (a Monday; ARP raced Sat–Mon in 2023), ATO 2022-06-05, 2024-06-02, 2025-06-01 | these were single test dates; the batches probe the full window for every year. ATO now has the Saturday scan (§3) |

**CT recheck (10/28–10/31):** each long-name copy matched the short-name copy
already on disk: same page count (8, 9, 8, 8), same races (8 each), and the
same text once whitespace and one stray watermark glyph per page are ignored
(file sizes differ by 9–26 bytes). The `chart_archive_recheck` folder (4 PDFs,
640,588 bytes) was deleted. Empty folders left by the 404s were also removed:
`Fairmount Park\fp-results-2022`, `Camarero\` (with `cmr-results-2023`),
`Atokad Downs\ato-results-2022`, `-2024`, `-2025`, `Arapahoe Park\arp-results-2024`.

**Next:** run `batches/batch_01.csv` and `batch_02.csv` (commands at the top),
one per session (cap 1,500). After each, compare each track's hits with
`estimate_by_track_year.csv`, and build the ATO follow-up from the log.

## 7. Feeders: batch_01 + batch_02 (Doug, 2026-11-15/16)

Rebuilt from the logs (the window closed overnight). **Both ran to the end:**
every job in the CSV is in the log, in order; no `stop` row, no 403.

| batch | log | ran | requests | ok | 404 | errors | s/req |
|---|---|---|---|---|---|---|---|
| 01 | `chart_download_log_20261115.csv` rows 53–1552 | 11/15 21:29 → 11/16 00:07 | 1,500 | 827 | 671 | 2 | 6.3 |
| 02 | `chart_download_log_20261116.csv` | 11/16 05:07 → 06:09 | 578 | 299 | 279 | 0 | 6.4 |

The 2 errors are single `not a PDF` responses (LS 2022-04-29, LS 2026-04-24),
each followed by an ok, so not a block. 1,126 new PDFs = 1,126 `ok` rows.

| track | downloaded | expected (estimate) | 404 rate | note |
|---|---|---|---|---|
| PRM | 394 | 395 | 15% | on target |
| ARP | 105 | 176 | 57% | **short**: 2024 6 (Sep 7–22 only), 2025 12 (Sep 13 – Nov 14); 2026 races Fri–Sun, Fridays probed only on PP dates |
| GIL | 34 | 30 | 66% | on target (7 a year) |
| LS | 201 | 205 | 51% | on target; 2 retries |
| ATO | 7 | 8 | 94% | 2022: no Saturday hit; 2024 May 11; 2025 Aug 16; 2026 Aug 29–30, Sep 5–7 |
| RP | 304 | 313 | 50% | on target |
| SWF | 81 | 75 | 39% | on target |
| **total** | **1,126** | **1,202** | **46%** | |

**Follow-up** `batches/followup_feeders_01.csv` (11 requests): ATO Fri/Sun/Mon
around each Saturday hit not already covered (2024-05-10/12/13,
2025-08-15/17/18, 2026-08-28, 08-31, 09-04) + the 2 LS retries. ATO 2022 had no
Saturday hit in May–Oct; not followed up (a Sunday-only or outside-window meet
would need a separate probe). **ARP open:** the 2024 and 2025 meets look moved
or cut short and 2026 runs Fri–Sun; a probe of Fridays and of Sep–Nov 2025 is
not built yet.

**Follow-up run (Doug, 11/16 06:35, log `chart_download_log_20261116.csv`):**
ATO 2024-05-10 ok; the other 8 ATO dates 404 (so ATO = 2024 May 10–11,
2025 Aug 16 only, 2026 Aug 29–30 + Sep 5–7). Both LS retries were `not a PDF`
**again**. Each of those two dates gives a non-PDF every time while the
requests around them are fine, so it is the dates, not a block. They are not
retried; whether those days raced is open.

## 8. ARP probe (`batches/probe_arp_01.csv`, 119 requests)

Every Fri, Sat and Sun from Jun 1 to Nov 30 (2026: to Nov 14), plus the
holiday Mondays in that span (Labor Day and Columbus Day each year, Veterans
Day 2024-11-11), for 2024–2026. Dates already on disk or logged ok/404 are taken
out: 2024 49 requests (6 on disk, 27 logged 404), 2025 39 (13, 29), 2026 31
(29, 13).

**Result (Doug, 11/16 06:40–06:53; log `chart_download_log_20261116.csv`):**
119 requests, 45 ok, 74 × 404, 0 errors, no stop. The meets **moved to the fall**
in 2024 and 2025 and race Fri–Sun:

| year | new | ARP charts on disk now | meet (from the hits) |
|---|---|---|---|
| 2024 | 27 | 33 | Fri 9/06 – Sun 11/17 |
| 2025 | 17 | 30 | Fri 9/12 – Sun 11/16 |
| 2026 | 1 (Fri 7/31) | 30 | Fri 6/12 – Sun 8/16 |

No holiday Monday hit. The two weeks after each meet's last day were probed and
404'd, so the ends look complete. 2022 (25 charts) has hits on Sundays and Mondays
only, and every Saturday 404'd. Fridays were never probed for 2022 (about 17 dates,
not built).

## 9. Live-track dates in group b (`live_track_dates_b03_07.csv`)

Group b has 322 rows in the live-loader folders (DED 9, EVD 23, FG 35 and
LAD 23 in batch_03; ELP 185 and GP 65 in batch_04; CT 27 in batch_06; MNR 32 in
batch_07). By construction the plan only probes dates **outside** each year's
span of charts on disk, so nearly all are season edges, and many will be 404s:

| track | rows | why not on disk |
|---|---|---|
| DED | 9 | New Year edges (Dec 30–Jan 3) of 2022/24/25/26 |
| EVD | 23 | 7 before DB coverage (2022 March); 16 opening week (late March / early April) before each year's first chart |
| LAD | 23 | 8 before DB coverage (2022 April); 15 late-April opening days |
| FG | 35 | 30 after DB coverage (2026, after 03-22: not loaded yet); 5 year-end edges |
| ELP | 185 | 129 late May / June dates from the 2023 meet (DB years start Jul 3–8, except 2023 Jun 10); 40 late Aug / early Sep; 16 after DB coverage (2026 after 08-23) |
| GP | 65 | 34 **already on disk** under hand-saved names (below); 16 Tue/Wed Jan–Feb 2026; 12 after DB coverage (2026 after 10-31); 3 year-end |
| CT | 27 | Christmas/New Year edges (Dec 17 – Jan 5) |
| MNR | 32 | Dec 10–27 meet end and mid-April opening; 4 after DB coverage (2026 after 11-04) |

**Inside a year's charted span in the DB (possible gaps), only GP 2026:**
the 8 Wednesdays 01-07, 01-14, 01-21, 01-28, 02-04, 02-11, 02-18, 02-25 (GP
raced Wednesdays in Jan–Feb 2024 and 2025, but the DB has none in 2026) and the
8 Tuesdays a day before each (GP did not race Tuesdays then, so probably 404).
Loading any of these is a later planned rebuild, not now.

**After batch_04 runs (open):** report which of these 16 dates downloaded
(`ok` in the log). Any that did are gaps in the live DB: list them here for the
planned rebuild; **do not load them.** Run batch_04 **as committed**: a
rebuilt plan (with the fixed inventory) no longer contains these dates at all,
because they fall inside GP 2026's span on disk and the builder treats dates
inside a span as non-race days.

**GP 2026 hand-saved names.** `Gulfstream Park\gp-results-2026` holds 47 charts
named `GP020126.pdf` or `01.01.26 GP Results.pdf`, which the 11/15 inventory and
the downloader index did not recognise. They are all charted in the DB. The
downloader index now recognises both styles (only inside a `*results*` folder),
so batch_04 skips the 34 that are in it (dry run: 1,466 requests, 34 already
had). **Inventory fixed 11/16:** new `build/inventory.py` (read-only scan, all
four naming styles, archive downloads left out) regenerated
`build/inputs/inventory.json`: exactly the 47 GP files added, nothing else
changed (5,157 → 5,204 files). A scratch rebuild then has no GP Jan–Feb 2026 rows
(the committed batch_04 has 50).

## 10. Known gaps (`known_gaps.csv`)

Charts that are corrupt or missing **at Equibase**. `build_plan.py` reads this
file and never puts these dates in a batch (tested 11/16 on a scratch copy:
the LS dates drop out with the list and come back without it). Each one is
retried **once**, by hand, after its `retry_after` date, from its own small
batch; then `status` is set to `fixed` or `permanent`.

| track | date | problem | retry after | how |
|---|---|---|---|---|
| MNR | 2026-10-05 | downloaded 11/07, damaged (Unexpected EOF) | 2026-11-21 | by hand (live track; `load_chart.py --reload`) |
| LS | 2022-04-29 | not a PDF twice (11/15, 11/16); won't load on equibase.com (Doug) | 2026-11-30 | `batches/retry_ls_after_20261130.csv` |
| LS | 2026-04-24 | same | 2026-11-30 | same batch |

```powershell
# on or after 2026-11-30, once only
.\tools\chart_downloader.ps1 -JobsCsv .\scripts_dpv1\tracking\chart_archive\batches\retry_ls_after_20261130.csv
```

The 8 known gaps from `../chart_audit_2026-11-07.md` (image pages, short
files, EVD 2023-08-10) are files on disk, so the builder never asks for them
anyway; they are not in this list.

## Not done / open

* GPW 2022, Stockton, Les Bois, Atlantic City, Retama TB: no codes or dates, so
  no jobs. HCN and EUR: dates listed separately, not in a batch.
* Other small meets can move as ATO did. The per-track hit check after each
  batch is how a shortfall shows up.
* Loading these charts into the DB is a separate decision (pars, feature build,
  retrain; see PHASE_6D_ROADMAP 1.4 item 4). This plan only fills the archive.
* GG's closing date and the PM/NP dates are from memory, not checked against a
  source (TwinSpires only says "closed").
