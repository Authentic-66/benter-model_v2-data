# Missing-last-race fetch test (2026-11-14, read-only)

**Question.** Should the card night fetch the Equibase chart of a horse's last
race when that race is not in the DB, and load that horse's line before the
features are built?

**Short answer: not as a nightly step yet.**

1. **Most of the gap is at tracks outside the corpus.** The 19 horses whose
   missing race was at EVD or LAD (corpus tracks) were already well priced:
   6 in the money against 5.9 expected. The calibration gap is in the 30
   horses whose last race was outside the corpus: 14 in the money against
   9.3 expected. For those tracks a fetched line gets **no speed figure**,
   because there are no pars for the track.
2. **On the one card tested, loading the lines made the prices worse.** On
   11/04, log loss for the tested horses went from 0.554 to 0.619 with the
   horse's line only, and to 0.590 with the whole chart. This is one card
   and 19 horses.
3. **Loading only the horse's line is not the same as loading the chart.**
   The stretch-run features (the feature promoted in 1.3.2) need the rest of
   the field. They stayed blank for 18 of the 20 tested horses.
4. **A fetch makes the incremental build fall back to a full build every
   night.** Such nights are logged as "fallback": they don't reset the
   side-by-side streak, but they don't count towards it either.
5. **I could not fetch from Equibase.** A plain HTTP request gets an Imperva
   bot-check page instead of the PDF (details in section 2). Nothing was
   downloaded.

Nothing was changed in the live DB or the model. The live DB's sha256 was
the same before and after the scratch work. The scripts and outputs are in
`tracking/missing_last_race_fetch_test/`.

## 1. Missing-last-race horses, DED 11/04–11/13

Source: `missing_last.py`, `missing_last.txt`, `missing_last.json`.

For each card, the script parses the PP file and takes each horse's latest
dated running line. It then checks whether that race was in the DB when the
record run was made.

**Correction to the running tally.** The reviews' tally said **52 starters,
22 in the money against 16.1 expected**. The corrected count is **50
starters, 21 in the money against 15.5 expected (4 wins against 5.0)**.

* **Bug:** the list script matched PP blocks on program number plus the first
  8 letters of the name. On 11/04, R7 #6 **Daddy's Code** was given R3 #6
  **Daddy's Last Sweet**'s block. Daddy's Code actually last ran DED 10/21,
  which was in the DB. The match now uses the full name.
* **DNFs:** two DNF starters had been left out because of the status's
  letter case; they are now counted.
* After those two fixes, one starter of the old 52 is still unaccounted for.

| group | starters | in the money | sum of P(ITM) | wins | sum of P(win) |
|---|---|---|---|---|---|
| **A.** 11/04, chart in the corpus but loaded only on 11/05 (EVD/LAD) | 19 | 6 | 5.86 | 1 | 1.94 |
| **B.** last race at a track outside the corpus | 30 | **14** | **9.34** | 3 | 3.01 |
| **C.** corpus chart missing (MNR 10/05, corrupt at Equibase) | 1 | 1 | 0.33 | 0 | 0.10 |
| **all** | 50 | 21 | 15.52 | 4 | 5.05 |

Group B tracks: PRM 5, ARP 4, GIL 4, LS 3, RP 2, SWF 2, and one each at ATO,
BAQ, FON, BTP, EUR, HCN, DMR, IND, CBY and MED. Every flagged starter, with
card, race, last race, finish, odds and logged P(ITM), is in
`missing_last.txt`. Horses flagged "chart loaded, horse not matched" there
are scratched DED horses that were purged with their card, not data gaps
(runbook A gotcha).

## 2. Fetching from Equibase

* **URL** (Doug's example):
  `https://www.equibase.com/static/chart/<yyyy>/usa/<trk>/<yyyymmdd>-usa-<trk>-a-d.standard.pdf`.
* **One request** to that example URL (2025-01-01 DED) returned **HTTP 200
  with `text/html`**. It was the Imperva "Pardon Our Interruption" bot check,
  not the PDF. So the "stop after three 403s" rule would not even trigger: a
  plain client gets a 200 that is not a chart.
* **I stopped there.** I did not try to get past the bot check (cookies,
  browser automation, header tricks). The fetch has to go through Doug's
  downloader.
* **Archived-name fallback:** not tested. Doug's message left the example
  archived URL as "[paste one here]". The fetch list gives each chart's
  archived file name (`<TRK><MMDDYY>USA.pdf`), but no archived URL.
* **Fetch list:** `fetch_list.csv` covers the 31 charts groups B and C need,
  one row per chart. Each row has the recent URL, the archived name, the
  long name to save under, the chart's age on 11/14 (23–210 days) and the
  horses it is for.
  * Track codes are the PP's (Brisnet). I assumed Equibase uses the same
    codes; I have not checked that.
  * With Doug's downloader, the same list will show at what age Equibase
    switches a chart from the recent URL to the archived one.
* **Charts already on disk** (Fairmount Park, Mahoning Valley) match none of
  the 50 horses. I used them only for the side-by-side test in section 5.

## 3. Load test: DED 11/04, three arms on scratch copies

Group A is the only group with charts on disk. Their 14 EVD/LAD charts were
loaded into the live DB on 11/05, after the 11/04 card ran.

`fetch_arm.py` rebuilds the 11/04 card from `racing_full.db.ded1104-run.bak`
on a scratch copy, in the order a nightly step would use:
`load_pp_card load` → (inject) → speed figures → features → score. The three
arms:

| arm | what is added before the build |
|---|---|
| **base** | nothing |
| **line** | only the missing horse's own line from each chart (race header + that entry, no exotics) |
| **full** | the whole 14 charts (what the 11/05 load did) |

The arms share these settings:

* Pars are frozen in all three (`pars-v1-20261108`), with 0 timed cells
  missing.
* 20 target horses, 19 of which started; Midnight Mischief scratched.
* Model 1.3.2 + `pp-reranker-1.0`, scored the same way as the paired
  harnesses (10,000 iterations, seed 6001).

The base arm picks the same #1 as the logged run in all 8 races. Its P(ITM)
differs from the logged run by up to 0.033, because the logged run
recomputed pars and the arms use the frozen ones. Each arm is compared only
with the other arms.

### What filled in for the 20 target horses (line arm)

* **Always filled:** days off, career starts, career win and ITM rates, and
  the field-experience features.
* **Filled for most:**
  * last-race finish (19 of 20)
  * pace type and pace progression (19 / 17)
  * beaten lengths and last-race field size (18)
  * last-3 finish average (18)
  * gate break average (17)
  * purse change (16)
  * distance, surface and condition change
  * class features (12–13)
  * second race back (12)
  * trouble in last trip (8)
* **Speed figure:** filled for 17 of 20. The other 3 had no margin
  (`beaten_lengths`) on the chart, so they get no horse time; that is the
  existing rule.
* **Still blank, or only right with the full chart:**
  * **`last_str_gain` and `last_str_gain_rank_pct` (the 1.3.2 stretch-run
    feature):** filled for only 2 of 20 in the line arm, against 18 of 20 in
    the full arm. Both need the other horses in the race.
  * `trainer_first_time_starters_win_pct` (20), `trainer_rising_class` (17)
    and `trainer_dropping_class` (16): same in all arms, they need
    situations that didn't arise.
  * Jockey and trainer home-track features (9–11): the same with the full
    chart.
* **Speed figures at tracks with no pars:** not testable here, because EVD
  and LAD have pars. From the code (`speed_figures_dpv1.resolve_par`), a
  race at a track that has no frozen cell falls to "insufficient", and the
  figure is NULL; the par never borrows from another track. In the section 5
  test, the three Fairmount and Mahoning lines added 2 new timed cells. **So
  every group-B line would come in without a speed figure.**

### Did other starters' features change?

**Yes, in both arms.** In the line arm, 52 of the 58 other starters had at
least one changed cell; in the full arm, 57. The changes were of two kinds:

* **Field-composition features** (`field_avg_career_starts`,
  `field_experience_variance`, `career_starts_vs_field_mean`, …). These change
  because a target horse's career starts changed.
* **Jockey and trainer rates** (90 and 365 days, surface, distance, other
  tracks). These change because the added lines are starts for those
  jockeys and trainers. The full arm moves more of them, because it adds
  every starter's jockey and trainer from those races.

The largest P(ITM) move for another starter was 0.065 (line arm) and 0.092
(full arm). Every cell change is in `featdiff_1104_line.csv` and
`featdiff_1104_full.csv`.

**Line vs full on the targets:** 45 columns differ (`compare_output.txt`):
the stretch features, career counts where the horse had other starts in
those charts, and the jockey and trainer rates.

## 4. Old vs new for the tested horses

| arm | tested starters | sum of P(ITM) | in the money | log loss | Brier | card log loss (69 starters) | #1 among runners, W / ITM of 8 |
|---|---|---|---|---|---|---|---|
| base | 19 | 5.86 | 6 | **0.554** | **0.189** | **0.578** | 4 / 6 |
| line | 19 | 6.25 | 6 | 0.619 | 0.213 | 0.599 | 4 / 6 |
| full | 19 | 6.06 | 6 | 0.590 | 0.200 | 0.593 | 4 / **7** |

* **Calibration:** group A was not under-priced before the fetch (5.86
  expected, 6 actual). Loading the lines pushed it slightly over (6.25 and
  6.06). It does nothing for the meet-wide gap (15.5 expected, 21 actual),
  which is in group B.
* **#1:** only the full arm changes a #1. In R4 it moves from #6 Cutting
  Class to #1 Phila Street, who ran 2nd (P(ITM) 0.334 → 0.485 line → 0.511
  full).
* **Biggest moves on the tested horses:**
  * The Boss Soss, R7: 0.334 → 0.196, and he **won** at 17.8-1.
  * Queenofpoker, R3: 0.188 → 0.365; ran 5th at 2.8-1.
  * El Dan, R7: 0.274 → 0.373; ran 8th.

  All 19 are in `compare_output.txt`.
* **Log loss** got worse for the tested horses and for the whole card in
  both arms. One card is far too small to call; it does not show a gain.

## 5. The nightly step and the incremental side-by-side

**Test** (`sbs_fetch_test.py`, `sbs_test.csv`):

1. Copy the live DB to scratch.
2. Inject 3 backdated line-only rows from tracks outside the corpus:
   FP 6/23, FP 6/16 and MVR 4/10.
3. Speed figures, then a full build, then `incremental_side_by_side.py run
   --step card` against the scratch DB with its own log.

**Result:**

* **The incremental plan falls back to a full build.** Three seeds made
  17,977 rows dirty. Spreading through jockeys, trainers, tracks and whole
  races, the closure reached 326,199 of 326,565 rows, which is over the 60%
  limit.
* **The fallback was correct:** 0 differing cells, hash equal, card_picks
  92 rows with 0 diffs.
* **But it is logged as `fallback`.** Per the runbook a fallback does not
  reset the streak, but it doesn't count either. **Any night with a fetch
  would not advance the 14-night count.** (The scratch log shows "streak 0"
  only because it started empty.)
* This is the same cause as the 3-month MNR backfill in
  `incremental_build_2026-11-08.md` ("Remaining refinement": a row that
  shares a race with a changed horse spreads along every key).

**What adding it after `load_pp_card` would take:**

1. **A fetch script:**
   * List the missing horses: PP last-race date and track against the DB,
     for horses on the card.
   * Download through Doug's downloader, throttled (3–6 s apart, stop on
     repeated blocks), into its own folder, never the results folders.
   * Log which URL form worked and the chart's age.
2. **A line-only loader:**
   * Ingest the race header and the horse's entry only.
   * Mark `source_pdf` (e.g. `…|line-only`).
   * Don't write `parsed_files`.
   * A later full chart load already purges any existing day before it
     loads (`retrain_pipeline.load_charts`), so the partial day is replaced,
     not merged. Better: load the whole chart, so the stretch-run features
     are right.
3. **Runbook B changes:**
   * The speed step will report new timed cells for tracks outside the
     corpus. The "many timed cells → stop" check needs a threshold that
     allows for them.
   * Expect `fallback` in runbook C on fetch nights.
4. **Reproducibility:**
   * A `-run.bak` would no longer rebuild the logged card unless the fetched
     files are kept and re-injected. The paired harnesses, `nm_card.py` and
     the snapshot checks would need a fetch manifest per card.
   * The card snapshot still records the scored frames, so `card_snapshot
     rescore` keeps working.
5. **It is a model-input change:** it needs an OFF/ON validation and a
   PHASE_6E entry before it goes live, like name matching. The roadmap's
   PP-date days-off fix (queue item 1) already gets days off for every horse
   with no chart at all.

**Recommendation (my read):**

* Don't wire it into card night now.
* If Doug wants to pursue it, first get the 31 charts in `fetch_list.csv`
  with his downloader. Then rerun this test on group B (11/05–11/13) with
  whole charts. That is the group where the gap is.
* Expect group B to come in without speed figures. Most of its jockeys and
  trainers will also be new people.
* Decide together with the incremental streak: either pause the count on
  fetch nights, or narrow the closure first.

## Files (`tracking/missing_last_race_fetch_test/`)

| file | what |
|---|---|
| `missing_last.py`, `.txt`, `.json` | the list (full-name PP block match) |
| `fetch_list.csv` | 31 charts for groups B and C: URLs, names, age, horses; none fetched |
| `targets.json` | the 21 group-A targets on 11/04 (Daddy's Code is a false positive, excluded at comparison) |
| `fetch_arm.py` | one card, one arm, on a scratch copy |
| `arm_1104_{base,line,full}_{scores,features}.csv`, `_meta.json` | arm outputs |
| `compare_arms.py`, `compare_output.txt` | section 3–4 numbers |
| `featdiff_1104_{line,full}.csv` | every changed feature cell vs base |
| `sbs_fetch_test.py`, `sbs_test.csv` | section 5 test |
