"""Rebuild one DED card on a scratch copy of its pre-race backup.

usage: python build_card_db.py <YYYY-MM-DD> <out.db> [--code-dir DIR] [--recompute-pars]
                               [--no-features]

copy scripts/racing_full.db.dedMMDD-run.bak -> out.db, then (with the code in
--code-dir, default the working tree's scripts_dpv1) load_pp_card load,
speed_figures_dpv1 compute, feature_builder_dpv1 build. The name-match log is
redirected next to out.db so the live logs/name_matches.jsonl is never touched.
Prints step timings as JSON on the last line.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

REPO = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
LIVE = REPO / "scripts" / "racing_full.db"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


ap = argparse.ArgumentParser()
ap.add_argument("date"); ap.add_argument("out")
ap.add_argument("--code-dir", default=str(REPO / "scripts_dpv1"))
ap.add_argument("--recompute-pars", action="store_true")
ap.add_argument("--no-features", action="store_true")
ap.add_argument("--skip-copy", action="store_true", help="out.db already holds the backup")
a = ap.parse_args()
mmdd = a.date[5:7] + a.date[8:10]
bak = REPO / "scripts" / f"racing_full.db.ded{mmdd}-run.bak"
pp = REPO / "Delta Downs" / "ded-pps-files" / f"ded{mmdd}y.pdf"
out = Path(a.out)
code = Path(a.code_dir)
env = dict(os.environ)
env["BENTER_NAME_MATCH_LOG"] = str(out.with_suffix(".name_matches.jsonl"))
env.pop("BENTER_NAME_MATCH", None)
live0 = LIVE.stat().st_mtime_ns
t = {}
if not a.skip_copy:
    t0 = time.time(); shutil.copy2(bak, out); t["copy"] = round(time.time() - t0, 1)
steps = [["load_pp_card.py", "load", str(pp), "--db", str(out)],
         ["speed_figures_dpv1.py", "compute", "--db", str(out)]
         + (["--recompute-pars"] if a.recompute_pars else [])]
if not a.no_features:
    steps.append(["feature_builder_dpv1.py", "build", "--db", str(out)])
for cmd in steps:
    t0 = time.time()
    pr = subprocess.run([sys.executable, str(code / cmd[0])] + cmd[1:], cwd=str(code.parent),
                        env=env, capture_output=True, text=True)
    t[cmd[0]] = round(time.time() - t0, 1)
    out.with_suffix(f".{cmd[0]}.log").write_text(pr.stdout + "\n" + pr.stderr, encoding="utf-8")
    if pr.returncode != 0:
        print(f"{cmd[0]} FAILED rc={pr.returncode}\n{pr.stderr[-2000:]}")
        sys.exit(1)
assert LIVE.stat().st_mtime_ns == live0, "live DB touched!"
print(json.dumps({"date": a.date, "out": str(out), "code": str(code), "timings_s": t}))
