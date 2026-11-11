# Runbook: card night by hand (2026-11-10)

Run from `D:\Benter Model_v2 Data\benter-model_v2-data`. Example: DED, 11/10
card, after the 11/09 races. Change the track, the dates and the file names.

## A. Results load (previous card's chart), first

```
python scripts_dpv1/load_chart.py "Delta Downs/ded-results-2026/DED110926USA.pdf"
python scripts_dpv1/score_predictions.py --track DED --date 2026-11-09
python scripts_dpv1/tracking/watch_people_tally.py
```

`load_chart.py` takes and checks its own backup
(`scripts\racing_full.db.pre-ded1109res.bak` + `.json`), purges the pre-race
card and loads the chart (`retrain_pipeline.load_charts`, the same path as
every chart since 10/16). No `Copy-Item` needed.

**Good:**
* `backup verified: racing_full.db.pre-ded1109res.bak`.
* One line ending `+Nr Ne (purged M first) [replaced a pre-race card]`.
  N races and entries match the chart; M is the card's entries.
* The totals show `"errors": 0`, and the last line is
  `loaded: DED <date> N races, E entries, E with a finish; replaced a
  pre-race card of M entries`.

It refuses and writes nothing (`REFUSED: ...`) if the file is not a chart,
its header and file-name dates disagree, the track is not in the DB, the day
already holds a chart (`--reload` to replace one, e.g. a re-download), the
chart has fewer races than the card (truncated), or an existing backup no
longer matches the DB. Since 2026-11-11 no load path keeps a card silently:
`db_loader.py ingest` / `pipeline` refuse a day that is already loaded
(exit 2) unless given `--replace` (PHASE_6E "Code change, 2026-11-11").

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
* The card_picks header names the model `dpv1.3.2-5track-stretch` (first
  line: `DPv1 dpv1.3.2-5track-stretch — DED <date>`).
* The card_picks header says `name matching: ON` (with the config line and
  the alias / new-person counts).

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
| card_picks header shows another model than `dpv1.3.2-5track-stretch` | Stop. Don't use or send the picks. Check `scripts_dpv1/dpv1.pkl` and ask. |
| card_picks header says `name matching: OFF` | Stop. Check `name_match_config.json` and that `BENTER_NAME_MATCH` is not set, then reload the card (B from the backup) and ask. |
| Chart load: `errors` > 0, `FAILED` or `CHECK FAILED` | Restore `pre-...res.bak` and ask. Don't build the card on it. |
| Chart load: `REFUSED` | Nothing was written. Read the reason: re-download a short chart; `--reload` only for a deliberate re-download over a chart; for "backup exists but the DB has changed", find out what wrote to the DB before moving the old backup aside. |

Restore = `Copy-Item <backup> scripts\racing_full.db` (close every other
program using the DB first).
