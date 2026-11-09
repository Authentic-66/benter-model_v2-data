# Runbook: card night by hand (2026-11-10)

Run from `D:\Benter Model_v2 Data\benter-model_v2-data`. Example: DED, 11/10
card, after the 11/09 races. Change the track, the dates and the file names.

## A. Results load (previous card's chart), first

```
Copy-Item scripts\racing_full.db scripts\racing_full.db.pre-ded1109res.bak
python scripts_dpv1/tracking/incremental_build_2026-11-08/load_chart.py scripts/racing_full.db "Delta Downs/ded-results-2026/DED110926USA.pdf" scripts/ct_cache
python scripts_dpv1/score_predictions.py --track DED --date 2026-11-09
python scripts_dpv1/tracking/watch_people_tally.py
```

**Good:**
* the chart load prints one line ending `+Nr Ne (purged M first)`. N races
  and entries match the chart; M is the card's starters.
* The totals show `"errors": 0`.

`load_chart.py` purges the pre-race card and then loads the chart. Loading a
chart over a card any other way silently keeps the card.

## B. Card build

```
python scripts_dpv1/pre_race_backup.py --track DED --date 2026-11-10
python scripts_dpv1/load_pp_card.py load "Delta Downs/ded-pps-files/ded1110y.pdf"
python scripts_dpv1/tracking/check_watch_list.py --track DED --date 2026-11-10
python scripts_dpv1/speed_figures_dpv1.py compute
python scripts_dpv1/feature_builder_dpv1.py build
python scripts_dpv1/card_picks.py --track DED --date 2026-11-10 --pp-file "Delta Downs/ded-pps-files/ded1110y.pdf" --save
```

**Good:**
* The backup writes `racing_full.db.ded1110-run.bak` plus `.json`, with no
  refusal.
* The load says `text reader: pdfplumber` and `loaded: N races, M entries`.
* Speed says `Pars: FROZEN version pars-v1-20261108` and `0 timed cells not
  in it` (or a small number).
* Features says `done — N rows` (about 160 s). N is the previous run's count
  plus tonight's starters.
* card_picks writes the picks file and `snapshot -> ...`. Its header has no
  PP-reader WARNING.

Always pass `--pp-file`; without it, P(ITM) changes.

## If a check fails

| Symptom | Do this |
|---|---|
| pre_race_backup: "already contains that night's card" | The card is already loaded, so the backup would be wrong. Stop. Restore the last `-run.bak` or ask. |
| pre_race_backup: "same sha256 as the previous card's backup" | The previous chart was not loaded. Do section A first. |
| pre_race_backup warns that the previous card has no results | The chart is late. Go on, and load it tomorrow before that night's backup. |
| load_pp_card refuses (backup missing or sha mismatch) | Something changed the DB after the backup. Rerun pre_race_backup with `--replace` only if nothing else was loaded since. Never use `--no-backup-check` on the live DB. |
| text reader is not pdfplumber, or "PP text reader error" | Clear `BENTER_PP_READER` and load again. |
| Speed: many timed cells not in the frozen pars | Stop and ask. Don't pass `--recompute-pars` on the live DB. |
| Feature build error, or a row count off by more than the card | Stop. The live table was not replaced. Restore the `-run.bak` and ask. |
| card_picks PP-reader WARNING | Re-run the load (step 2 of B), then card_picks. |
| Chart load: `errors` > 0, or entries far from the chart | Restore `pre-...res.bak` and ask. Don't build the card on it. |

Restore = `Copy-Item <backup> scripts\racing_full.db` (close every other
program using the DB first).
