# Missing charts inventory, 2026-11-04 (read-only)

**Bottom line.** On the DED cards from 10/23 to 11/04, **251 of 495 horse
entries (51%) had a last race that is not in the DB**. 213 of them ran last
at EVD or LAD on dates after the DB's last chart for that track: **EVD stops
at 2026-06-25** and **LAD at 2026-09-16**. Loading the 44 charts below fixes
those 213. The other 38 ran last at tracks that are not in the corpus at all.

The model then reads an older race as "last race". Example: 11/04 R2 #1
Whatdidwedo, last start EVD 8/8 (88 days), priced off EVD 6/11 (146 days).

## Method

For every horse on the DED PP files for 10/23, 10/24, 10/28, 10/29, 10/30
and 11/04, the PP race lines (date + track) were read with the live parser
(`brisnet_pp_parser`, wrapped in a scratch script; no code changed) and each
date/track was checked against the charted race days in `racing_full.db`
(scheduled PP cards excluded). Counts are horse entries per card, so a horse
on two cards counts twice.

| card | horses | first-time starters | last race not in DB | at EVD | at LAD | at other tracks |
|---|---|---|---|---|---|---|
| 10/23 | 82 | 17 | 45 | 32 | 7 | 6 |
| 10/24 | 79 | 17 | 38 | 22 | 7 | 9 |
| 10/28 | 82 | 2 | 48 | 25 | 15 | 8 |
| 10/29 | 75 | 4 | 39 | 23 | 9 | 7 |
| 10/30 | 100 | 0 | 58 | 35 | 18 | 5 |
| 11/04 | 77 | 2 | 23 | 14 | 6 | 3 |
| **all** | **495** | **42** | **251** | **151** | **62** | **38** |

## Last race not charted, by impact (horse entries)

Corpus tracks (downloadable):

| track | date | horses | | track | date | horses |
|---|---|---|---|---|---|---|
| EVD | 2026-08-28 | 19 | | EVD | 2026-08-14 | 5 |
| EVD | 2026-09-07 | 16 | | EVD | 2026-08-20 | 5 |
| LAD | 2026-09-30 | 15 | | EVD | 2026-08-22 | 5 |
| EVD | 2026-08-27 | 12 | | LAD | 2026-09-29 | 5 |
| EVD | 2026-09-04 | 11 | | EVD | 2026-07-31 | 4 |
| LAD | 2026-09-21 | 11 | | EVD | 2026-08-06 | 4 |
| LAD | 2026-09-22 | 11 | | EVD | 2026-08-15 | 4 |
| LAD | 2026-09-19 | 10 | | EVD | 2026-07-18 | 3 |
| EVD | 2026-08-07 | 9 | | EVD | 2026-08-13 | 3 |
| EVD | 2026-08-29 | 9 | | EVD 2026-06-26, 07-03, 07-11, 07-24, 07-25, 08-01, 08-31; LAD 09-23 | | 2 each |
| LAD | 2026-09-28 | 8 | | EVD 2026-06-20 (gap inside the DB range), 06-27, 07-16, 07-23, 07-30 | | 1 each |
| EVD | 2026-08-21 | 7 | | | | |
| EVD | 2026-09-05 | 6 | | | | |
| EVD | 2026-07-10 | 5 | | | | |
| EVD | 2026-08-08 | 5 | | | | |

Tracks not in the corpus (38 entries; not fixable by downloading charts
without adding the track): PRM 8, SWF 7, ATO 4, CBY 3, GIL 3, HCN 3, RP 3,
LS 2, ARP 1, IND 1, LEG 1, OP 1, WO 1.

## Charts to download (44)

Every corpus-track date that appears on *any* PP race line of these horses
and has no chart in the DB (not only last races). The four marked "gap" are
inside the DB's date range: they were never downloaded (no file on disk, no
`parsed_files` row).

**EVD (37):**
* 2025: 07-04 (gap)
* 2026: 04-24 (gap), 05-07 (gap), 06-20 (gap),
  06-26, 06-27,
  07-02, 07-03, 07-04, 07-09, 07-10, 07-11, 07-16, 07-17, 07-18, 07-23,
  07-24, 07-25, 07-30, 07-31,
  08-01, 08-06, 08-07, 08-08, 08-13, 08-14, 08-15, 08-20, 08-21, 08-22,
  08-27, 08-28, 08-29, 08-31,
  09-04, 09-05, 09-07

**LAD (7):** 2026-09-19, 09-21, 09-22, 09-23, 09-28, 09-29, 09-30

This list only has dates on which at least one of these horses ran. For
future cards, the full remainder of each meet is the safer download: every
EVD race day from 2026-06-26 to the end of its meet, and every LAD race day
after 2026-09-16.

After loading: purge rule as usual (back up, `rp.load_charts`), then rebuild
speed figures and features before the next card.
