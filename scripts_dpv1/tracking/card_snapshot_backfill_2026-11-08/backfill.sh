#!/usr/bin/env bash
# usage: backfill.sh <YYYY-MM-DD> <code: current|commit> <record generated_at> <build|capture|all>
# build: rebuild the card from its pre-race backup with that code.
# capture: run that code's card_picks with capture hooks -> snapshot in
#          logs/card_snapshots (checked against the logged record run), then
#          rescore the snapshot with today's code against logs/predictions.jsonl,
#          then delete the scratch DB.
set -e
S="C:/Users/bornr/AppData/Local/Temp/claude/4f22c0db0d78fb97/0b8e8077-2c9b-44c7-8b9d-13c5e3bd304c/scratchpad"
N="D:/Benter Model_v2 Data/benter-model_v2-data/scripts_dpv1"
d=$1; code=$2; gen=$3; phase=$4
m=${d:5:2}${d:8:2}
db="$S/cards/ded$m.db"
if [ "$code" = current ]; then CD="$N"; RP="--recompute-pars"; else CD="$S/wt/$code/scripts_dpv1"; RP=""; fi
stamp=$(echo "$gen" | sed 's/[-:]//g; s/T/-/')
out="$N/logs/card_snapshots/DED_${d}_${stamp}.json.gz"
if [ "$phase" = build ] || [ "$phase" = all ]; then
  python "$S/build_card_db.py" "$d" "$db" --code-dir "$CD" $RP 2>&1 | tail -1 | grep -o '"timings_s".*'
fi
if [ "$phase" = capture ] || [ "$phase" = all ]; then
  PYTHONIOENCODING=utf-8 python "$S/step5/capture_card.py" "$CD" "$N" "$d" "$db" dpv1.pkl "$gen" "$out" \
      "${db%.db}.name_matches.jsonl" 2>&1 | grep -v Warn | tail -1
  (cd "$N" && python card_snapshot.py rescore "$out" 2>&1 | grep -v Warn | tr -d '\n ' ; echo)
  rm -f "C:/Users/bornr/AppData/Local/Temp/claude/4f22c0db0d78fb97/0b8e8077-2c9b-44c7-8b9d-13c5e3bd304c/scratchpad/cards/ded$m.db"
fi
