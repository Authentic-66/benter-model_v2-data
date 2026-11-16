# Chart archive: Equibase result charts, US/Canada Thoroughbred, 2022 → today

Plan and prep only (2026-11-15). **No request was made to Equibase.** Doug runs
every download with `tools/chart_downloader.ps1`. Nothing pushed.

## Files

| file | what |
|---|---|
| `tracks.csv` | master list: 126 track codes from the 2023 XMLs, with category, country, status, 2023 race days/dates/months/weekdays, TwinSpires check, DED PP last-race count, charts on disk, priority |
| `estimate_by_track_year.csv` | per track × year: candidate dates, already on disk, requests, expected race days, expected new charts, expected MB |
| `batch_00_test.csv` | test batch, 52 rows (run first) |
| `batches/batch_01.csv` … `batch_20.csv` | all jobs in priority order, ≤1,500 requests each; `batch_index.csv` lists the tracks in each |
| `extra_pp_only_tracks.csv` | known HCN / EUR dates from DED PP lines (not in any batch; see §1) |
| `build/` | the three read-only scripts that made all of the above (rerun after the test) |
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

**Country:** Canada = WO, ASD, HST, FE, CTM, CTD, LBG, GPR, MIL (and AJX, QH).
**CMR (Camarero) is Puerto Rico**, which is neither US-state nor Canada but is on
Equibase; it is in the plan (1,525 TB races in 2023) behind a test row.

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
* **FPK**: Brisnet's code for Fairmount Park (PP lines 2025). Equibase uses FAN
  (2023–2024 charts on disk) and FP (2025–2026 on disk). **2022 is unknown:**
  the test has the same 2022 date under FAN and FP.
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
* **Tracks with charts on disk:** the earlier downloads swept their date ranges,
  so for those years only dates **before the first or after the last chart on
  disk** are probed. A gap inside the range is treated as a non-race day.
* Closed tracks are cut at the closing date (GG 2024-06-09; PLN after 2024).

**Expected race days** for a year = the track's 2023 TB days (2026 prorated to
11/14). **Size** = 16.1 KB per race (median of the charts on disk) × the track's
races per day.

| year | requests | expected new charts | expected MB |
|---|---|---|---|
| 2022 | 6,824 | 3,666 | 499 |
| 2023 | 3,646 | 3,646 | 496 |
| 2024 | 6,587 | 3,563 | 486 |
| 2025 | 6,337 | 3,435 | 469 |
| 2026 | 5,923 | 3,256 | 445 |
| **total** | **29,317** | **≈17,600** | **≈2.4 GB** |

| priority group | requests | expected new charts | expected MB |
|---|---|---|---|
| a. feeders | 2,040 | 1,233 | 181 |
| b. DED PP last-race tracks | 7,049 | 4,389 | 622 |
| c. everything else | 20,228 | 11,944 | 1,591 |

About 60% of requests should be hits; the rest are 404s on non-race days. At
the 4–8 s delay (about 7 s per request with the response), a 1,500-request
batch takes about **3 hours**; all 20 batches about **57 hours**. Disk is not a
constraint (2.4 GB of 705 GB free).

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

* **a. Feeders:** PRM, ARP, GIL, LS, ATO, RP, SWF (batch_01 and the start of
  batch_02).
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
  Checked on the test batch: 52 would-fetch rows, 5,146 charts indexed.

```powershell
cd 'D:\Benter Model_v2 Data\benter-model_v2-data'
.\tools\chart_downloader.ps1 -JobsCsv .\scripts_dpv1\tracking\chart_archive\batch_00_test.csv
.\tools\chart_downloader.ps1 -JobsCsv .\scripts_dpv1\tracking\chart_archive\batches\batch_01.csv
```

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

**After the test:**
1. If WO works only with `can`: set `country=can` for the Canadian tracks'
   rows (WO, ASD, HST, FE, CTM, CTD, LBG, GPR, MIL), or I regenerate the
   batches.
2. If CMR 404s on a known 2023 date: drop CMR (batches 07–08) or test another
   path.
3. Fairmount 2022: keep whichever code worked.
4. If the newest CT dates 404 at the long name: hold back the last N days of
   2026 in each batch until they move (N = the age where they start to work).
5. If the run stops on not-a-PDF: Equibase is serving the bot check to this
   client. Stop there; nothing in the downloader works around it.

Then run `batches/batch_01.csv` … in order, one per session (cap 1,500), and
compare each track's hits with `estimate_by_track_year.csv`.

## Not done / open

* GPW 2022, Stockton, Les Bois, Atlantic City, Retama TB: no codes or dates, so
  no jobs. HCN and EUR: dates listed separately, not in a batch.
* Loading these charts into the DB is a separate decision (pars, feature build,
  retrain; see PHASE_6D_ROADMAP 1.4 item 4). This plan only fills the archive.
* GG's closing date and the PM/NP dates are from memory, not checked against a
  source (TwinSpires only says "closed").
