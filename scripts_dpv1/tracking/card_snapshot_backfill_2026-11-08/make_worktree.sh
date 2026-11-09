#!/usr/bin/env bash
# usage: make_worktree.sh <commit>  -> prints the worktree's scripts_dpv1 path
# Sparse worktree (code + pickles + configs only) under the scratchpad.
set -e
C="$1"
REPO="D:/Benter Model_v2 Data/benter-model_v2-data"
WT="C:/Users/bornr/AppData/Local/Temp/claude/4f22c0db0d78fb97/0b8e8077-2c9b-44c7-8b9d-13c5e3bd304c/scratchpad/wt/$C"
if [ ! -f "$WT/scripts_dpv1/card_picks.py" ]; then
  [ -d "$WT" ] || git -C "$REPO" worktree add --no-checkout --detach "$WT" "$C" >/dev/null 2>&1
  git -C "$WT" config --worktree core.sparseCheckout true
  GD=$(git -C "$WT" rev-parse --git-dir)
  mkdir -p "$GD/info"
  printf '%s\n' '/scripts/' '/scripts_v2a/*.py' '/scripts_dpv1/' '!/scripts_dpv1/*fold_predictions*.csv' \
    '!/scripts_dpv1/logs/' '!/scripts_dpv1/picks/' '!/scripts_dpv1/tracking/' \
    '!/scripts_dpv1/_*/' > "$GD/info/sparse-checkout"
  MSYS_NO_PATHCONV=1 git -C "$WT" read-tree -mu HEAD
  mkdir -p "$WT/scripts_dpv1/logs"
fi
echo "$WT/scripts_dpv1"
