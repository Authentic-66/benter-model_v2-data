# Rebuilding the plan files (read-only, no network)

Run from the repo root, with a scratch folder `<S>` for the intermediate JSON:

```
python -I scripts_dpv1/tracking/chart_archive/build/parse_xml.py "D:/From Downloads/2023 Result Charts" <S>/xml2023.json
python scripts_dpv1/tracking/chart_archive/build/lastrace.py <S>/lastrace.json      # ~25 min, parses all DED PP files
<inventory>: <S>/inventory.json (list of chart PDFs on D:, both naming styles; see PLAN.md section 2)
python -I scripts_dpv1/tracking/chart_archive/build/build_plan.py <S>
```

build_plan.py writes tracks.csv, estimate_by_track_year.csv, batch_00_test.csv,
batches/ and extra_pp_only_tracks.csv. Rerun it after the test batch (e.g. to set
country=can for Canadian tracks) and after each download batch (the on-disk
index changes the windows).
