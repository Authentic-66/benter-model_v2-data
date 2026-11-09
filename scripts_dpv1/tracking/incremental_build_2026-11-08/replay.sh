#!/usr/bin/env bash
# Step 6 replay. usage:
#   replay.sh base                 A = .ded1104-run.bak, pars frozen (proof-1104), full build + record
#   replay.sh det                  determinism: B = A, full build on B, diff A B
#   replay.sh card  MMDD           load PP card into A, speed (frozen), incremental update
#   replay.sh chart MMDD           load chart into A, speed (frozen), incremental update
#   replay.sh cmp   LABEL [MMDD]   B = A, full build on B, diff A B; with MMDD also card_picks on A and B
#   replay.sh adv   TEST           hand edit on A (adv_edit.py: scratch, restore, attrs, relabel), speed, update
#   replay.sh config               edit a copy of the feature config: update --no-fallback must refuse,
#                                  then update (falls back to full); later cmp steps build B with it
# S = work dir (set REPLAY_DIR; holds s6/A.db, s6/B.db, s6/out). H = this harness folder.
set -e
S="${REPLAY_DIR:?set REPLAY_DIR to a scratch folder}"
H="$(cd "$(dirname "$0")" && pwd)"
R="D:/Benter Model_v2 Data/benter-model_v2-data"; N="$R/scripts_dpv1"
A="$S/s6/A.db"; B="$S/s6/B.db"; O="$S/s6/out"
export BENTER_NAME_MATCH_LOG="$S/s6/name_matches.jsonl" PYTHONIOENCODING=utf-8
L0=$(stat -c %Y "$R/scripts/racing_full.db")
t() { local s=$(date +%s); "$@"; echo "  [$(( $(date +%s) - s ))s] $1 $(basename "$2" 2>/dev/null)" >&2; }
speed() { python "$N/speed_figures_dpv1.py" compute --db "$1" --par-version proof-1104 2>&1 | grep -o "Pars:.*\|Wrote.*" ; }
CFG="$S/s6/cfg.json"; [ -f "$CFG" ] || CFG="$N/dpv1_feature_config.json"
full() { python "$N/feature_builder_dpv1.py" build --db "$1" --config "$CFG" 2>&1 | grep -o "done.*\|WARN.*" ; }
inc() { python "$N/feature_incremental.py" update --db "$A" --config "$CFG" --no-fallback 2>&1 | tail -1; }
case $1 in
 base)
  cp "$R/scripts/racing_full.db.ded1104-run.bak" "$A"
  python "$N/speed_figures_dpv1.py" freeze --db "$A" --version proof-1104 --note "Step 6 replay" 2>&1 | grep -o "Froze.*"
  t speed "$A"; t full "$A" ;;
 det)
  cp "$A" "$B"; t full "$B"
  python "$H/table_diff.py" "$A" "$B" > "$O/det.json"; python -c "import json;d=json.load(open(r'$O/det.json'));print({k:d[k] for k in ['rows_a','rows_b','columns_compared','differing_cells','type_diffs_by_column','identical']}, d['hash_a']==d['hash_b'])"
  rm -f "$S/s6/B.db" ;;
 card)
  t python "$N/load_pp_card.py" load "$R/Delta Downs/ded-pps-files/ded$2y.pdf" --db "$A" 2>&1 | grep -o "^loaded.*"
  t speed "$A"; t inc ;;
 chart)
  t python "$H/load_chart.py" "$A" "$R/Delta Downs/ded-results-2026/DED${2}26USA.pdf" "$S/s6/cache"
  t speed "$A"; t inc ;;
 adv)
  t python "$H/adv_edit.py" "$A" "$S/s6/stash" "$2"
  t speed "$A"; t inc ;;
 config)
  python - "$N/dpv1_feature_config.json" "$S/s6/cfg.json" <<'PY2'
import json,sys
c=json.load(open(sys.argv[1],encoding="utf-8")); c["_replay_note"]="config change test (no feature change)"
json.dump(c,open(sys.argv[2],"w",encoding="utf-8"),indent=2)
PY2
  CFG="$S/s6/cfg.json"
  echo "  update --no-fallback (must refuse):"; python "$N/feature_incremental.py" update --db "$A" --config "$CFG" --no-fallback 2>&1 | tail -1 || true
  echo "  update (falls back):"; t python "$N/feature_incremental.py" update --db "$A" --config "$CFG" 2>&1 | tail -1 ;;
 cmp)
  cp "$A" "$B"; t full "$B"
  python "$H/table_diff.py" "$A" "$B" > "$O/cmp_$2.json"; python -c "import json;d=json.load(open(r'$O/cmp_$2.json'));print('$2', {k:d[k] for k in ['rows_a','rows_b','ids_only_a','ids_only_b','columns_compared','differing_cells','differing_cells_by_column','type_diffs_by_column','identical']}, 'hash_eq', d['hash_a']==d['hash_b'])"
  if [ -n "$3" ]; then
    d="2026-${3:0:2}-${3:2:2}"
    rm -f "$O/picks_${3}_A.jsonl" "$O/picks_${3}_B.jsonl"
    for X in A B; do (cd "$N" && python card_picks.py --track DED --date $d --pp-file "../Delta Downs/ded-pps-files/ded$3y.pdf" --db "$S/s6/$X.db" --save --log-file "$O/picks_${3}_$X.jsonl" --outdir "$O/picks" >/dev/null 2>&1); done
    python - "$O/picks_${3}_A.jsonl" "$O/picks_${3}_B.jsonl" <<'PY'
import json,sys
a=[json.loads(l) for l in open(sys.argv[1],encoding="utf-8")]; b=[json.loads(l) for l in open(sys.argv[2],encoding="utf-8")]
skip={"generated_at","prediction_id","picks_file"}
print("  card_picks A vs B:", len(a), len(b), "diffs", sum(1 for x,y in zip(a,b) for k in x if k not in skip and x[k]!=y.get(k)))
PY
  fi
  rm -f "$S/s6/B.db" ;;
esac
[ "$L0" = "$(stat -c %Y "$R/scripts/racing_full.db")" ] || { echo "LIVE DB CHANGED"; exit 9; }
