# Rebuilding the plan files (read-only, no network)

Run from the repo root, with a scratch folder `<S>` for the intermediate JSON:

```
python -I scripts_dpv1/tracking/chart_archive/build/parse_xml.py "D:/From Downloads/2023 Result Charts" <S>/xml2023.json
python scripts_dpv1/tracking/chart_archive/build/lastrace.py <S>/lastrace.json      # ~25 min, parses all DED PP files
python -I scripts_dpv1/tracking/chart_archive/build/inventory.py D:/ <S>/inventory.json   # ~20 s; chart PDFs on D:, all naming styles, archive downloads left out
python -I scripts_dpv1/tracking/chart_archive/build/build_plan.py <S>
```

build_plan.py writes tracks.csv, estimate_by_track_year.csv, batch_00_test.csv,
batches/ and extra_pp_only_tracks.csv. Rerun it after the test batch (e.g. to set
country=can for Canadian tracks) and after each download batch (the on-disk
index changes the windows).

## Saved inputs (2026-11-15)

`inputs/` holds the three JSON inputs as they were when the plan was built, so the
plan can be rebuilt without the 25-minute PP scan:

```
python -I scripts_dpv1/tracking/chart_archive/build/build_plan.py scripts_dpv1/tracking/chart_archive/build/inputs
```

`inventory.json` is a snapshot of charts on D: on 11/15. After downloads it is
stale, which only matters for the windows (the downloader indexes the disk itself
at every start, so nothing is downloaded twice). Regenerate it before rebuilding
batches after real downloads.

2026-11-16: regenerated with `inventory.py` (adds the 47 hand-named GP 2026
charts; otherwise identical to the 11/15 snapshot). The inventory means "charts
that existed before the archive": `inventory.py` leaves out every archive download
(logged ok and a job in a batch file), so archive dates are counted through the
logs, not as swept ranges.
