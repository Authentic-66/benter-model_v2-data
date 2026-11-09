export REPLAY_DIR="${REPLAY_DIR:?set REPLAY_DIR to a scratch folder}"
X="D:/Benter Model_v2 Data/benter-model_v2-data/scripts_dpv1/tracking/incremental_build_2026-11-08/replay.sh"
r() { echo "=== $* [$(date +%H:%M:%S)]"; bash "$X" "$@" || { echo "STEP FAILED rc=$?: $*"; exit 1; }; }
r base; r det
for d in 1104 1105 1106; do r card $d; r cmp card$d $d; r chart $d; r cmp chart$d; done
r card 1107; r cmp card1107 1107
r adv scratch; r cmp adv_scratch 1107
r adv restore; r cmp adv_also_eligible 1107
r chart 1107; r cmp chart1107
r adv attrs; r cmp adv_attrs
r adv relabel; r cmp adv_relabel
r chart 1024; r cmp adv_purge_reload_1024
r config; r cmp adv_config
echo "=== ALL DONE [$(date +%H:%M:%S)]"
