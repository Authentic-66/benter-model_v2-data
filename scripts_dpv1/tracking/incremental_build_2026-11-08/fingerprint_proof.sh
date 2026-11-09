# per-table fingerprint proof. usage: proof.sh old|new|side   (scratch copies only)
set -e
S="${PROOF_DIR:?set PROOF_DIR to a scratch folder}"
R="D:/Benter Model_v2 Data/benter-model_v2-data"; N="$R/scripts_dpv1"; A="$S/A.db"; O="$S/out"
export BENTER_NAME_MATCH_LOG="$S/nm.jsonl" PYTHONIOENCODING=utf-8
L0=$(stat -c %Y "$R/scripts/racing_full.db")
PP="$R/Delta Downs/ded-pps-files/ded1107y.pdf"
picks() { rm -f "$O/picks_$1.jsonl"; (cd "$N" && python card_picks.py --track DED --date 2026-11-07 --pp-file "$PP" --db "$A" --save --log-file "$O/picks_$1.jsonl" --outdir "$O/picks" >"$O/cp_$1.txt" 2>&1); wc -l < "$O/picks_$1.jsonl"; }
case $1 in
 old)
  cp "$R/scripts/racing_full.db.ded1107-run.bak" "$A"
  python "$N/load_pp_card.py" load "$PP" --db "$A" --no-backup-check 2>&1 | grep -o "^loaded.*\|text reader.*" | head -2
  python "$N/speed_figures_dpv1.py" compute --db "$A" --recompute-pars 2>&1 | grep -o "Pars:.*\|Wrote.*"
  python "$N/feature_builder_dpv1.py" build --db "$A" 2>&1 | grep -o "done.*\|WARN.*\|Error.*"
  cp "$A" "$S/A_old.db"; picks old ;;
 new)
  python "$N/feature_builder_dpv1.py" build --db "$A" 2>&1 | grep -o "done.*\|WARN.*\|Error.*"
  python "$R/scripts_dpv1/tracking/incremental_build_2026-11-08/table_diff.py" "$S/A_old.db" "$A" > "$O/cmp_old_new.json"
  python -c "import json;d=json.load(open(r'$O/cmp_old_new.json'));print('old vs new table:',{k:d[k] for k in ['rows_a','rows_b','ids_only_a','ids_only_b','differing_cells','type_diffs_by_column','identical']},'hash_eq',d['hash_a']==d['hash_b'])"
  python -c "import sqlite3;c=sqlite3.connect(r'$A');print('fingerprint layout:',[r[1] for r in c.execute('pragma table_info(feature_input_hashes)')][:3], c.execute('select table_name,count(*) from feature_input_hashes group by 1').fetchall())"
  rm -f "$S/A_old.db"; picks new
  python - "$O/picks_old.jsonl" "$O/picks_new.jsonl" "$N/logs/predictions.jsonl" <<'PY'
import json,sys
ld=lambda p:[json.loads(l) for l in open(p,encoding="utf-8")]
a,b=ld(sys.argv[1]),ld(sys.argv[2])
rec=[r for r in ld(sys.argv[3]) if r.get("race_date")=="2026-11-07" and r.get("track")=="DED"]
skip={"generated_at","prediction_id","picks_file"}
key=lambda r:(r["race_num"],str(r["pgm"]))
def diff(x,y):
    m={key(r):r for r in y}; return sum(1 for r in x for k in r if k not in skip and r[k]!=m.get(key(r),{}).get(k))
print("picks rows old/new/logged:",len(a),len(b),len(rec),"| old vs new diffs",diff(a,b),"| new vs logged 09:54 diffs",diff(b,rec))
PY
  ;;
 side)
  [ -f "$A" ] || { cp "$R/scripts/racing_full.db.ded1107-run.bak" "$A"; python "$N/load_pp_card.py" load "$PP" --db "$A" --no-backup-check 2>&1 | grep -o "^loaded.*"; }
  python "$N/speed_figures_dpv1.py" freeze --db "$A" --version proof-fp --note "fingerprint proof" 2>&1 | grep -o "Froze.*"
  python "$N/speed_figures_dpv1.py" compute --db "$A" --par-version proof-fp 2>&1 | grep -o "Pars:.*"
  python "$N/feature_builder_dpv1.py" build --db "$A" --table entry_features_dpv1_inc 2>&1 | grep -o "done.*\|Error.*"
  python "$N/feature_builder_dpv1.py" build --db "$A" 2>&1 | grep -o "done.*\|Error.*"
  echo "side plan after a main full build (must be none):"; python "$N/feature_incremental.py" plan --db "$A" --table entry_features_dpv1_inc 2>&1 | tail -1
  python "$R/scripts_dpv1/tracking/incremental_build_2026-11-08/load_chart.py" "$A" "$R/Delta Downs/ded-results-2026/DED110726USA.pdf" "$S/cache" | tail -1
  python "$N/speed_figures_dpv1.py" compute --db "$A" --par-version proof-fp 2>&1 | grep -o "Pars:.*"
  python "$N/feature_builder_dpv1.py" build --db "$A" 2>&1 | grep -o "done.*\|Error.*"
  echo "side update after the 11/07 chart AND a main full build (nightly order):"; python "$N/feature_incremental.py" update --db "$A" --table entry_features_dpv1_inc --no-fallback 2>&1 | tail -1
  python - "$A" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]); m,s="entry_features_dpv1","entry_features_dpv1_inc"
cm=[r[1] for r in c.execute(f"pragma table_info({m})")]; cs=[r[1] for r in c.execute(f"pragma table_info({s})")]
cols=",".join(cm)
n=lambda q:c.execute(q).fetchone()[0]
print("side vs main after chart: cols equal",cm==cs,"rows",n(f"select count(*) from {m}"),n(f"select count(*) from {s}"),
 "main-not-side",n(f"select count(*) from (select {cols} from {m} except select {cols} from {s})"),
 "side-not-main",n(f"select count(*) from (select {cols} from {s} except select {cols} from {m})"),
 "type diffs",sum(n(f"select count(*) from {m} a join {s} b using(entry_id) where typeof(a.{k})<>typeof(b.{k})") for k in cm))
print("fingerprint rows per table:",c.execute("select table_name,count(*) from feature_input_hashes group by 1").fetchall())
PY
  rm -f "$A" ;;
esac
[ "$L0" = "$(stat -c %Y "$R/scripts/racing_full.db")" ] || { echo "LIVE DB CHANGED"; exit 9; }
