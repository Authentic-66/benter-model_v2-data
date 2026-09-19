"""Promote Arm B to live, and retire the incumbent.

    python _ded/promote_armB.py            # dry run: report, change nothing
    python _ded/promote_armB.py --apply

Retirement name is the incumbent's own ``trained_at`` (UTC) plus a
non-numeric ``_retired`` suffix, which is what keeps ``prune_models`` from
reaping it -- a bare ``dpv1_YYYYMMDD_HHMMSS.pkl`` reads as a pipeline
candidate. Only ``version`` is rewritten on the promoted model; coefficients
are a byte-for-byte carry-over from the arm that was evaluated.
"""
import pickle
from datetime import datetime
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DPV1 = HERE.parent
sys.path.insert(0, str(DPV1))
from dpv1_runtime import load_model  # noqa: E402

LIVE = DPV1 / "dpv1.pkl"
ARM_B = HERE / "dpv1_armB.pkl"
NEW_VERSION = "dpv1.3.0-5track"

apply = "--apply" in sys.argv

incumbent = load_model(LIVE)
cand = load_model(ARM_B)

ts = incumbent.trained_at
if isinstance(ts, str):
    ts = datetime.fromisoformat(ts)
stamp = ts.strftime("%Y%m%d_%H%M%S")
retired = DPV1 / f"dpv1_{stamp}_retired.pkl"

print(f"incumbent : {incumbent.version}  trained {incumbent.trained_at}")
print(f"candidate : {cand.version}  trained {cand.trained_at}")
print(f"retire as : {retired.name}")
print(f"new version: {NEW_VERSION}")

if list(incumbent.fund_cols) != list(cand.fund_cols):
    raise SystemExit("!! feature lists differ between incumbent and candidate")
print(f"feature lists identical: {len(cand.fund_cols)} columns")

if retired.exists():
    raise SystemExit(f"!! {retired.name} already exists -- refusing to overwrite")

if not apply:
    print("\ndry run -- nothing written. Re-run with --apply")
    raise SystemExit(0)

shutil.copy2(LIVE, retired)
print(f"wrote {retired.name}")

with open(ARM_B, "rb") as f:
    blob = f.read()
model = pickle.loads(blob)
model.version = NEW_VERSION
with open(LIVE, "wb") as f:
    pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)

check = load_model(LIVE)
ref = load_model(ARM_B)
assert check.version == NEW_VERSION, check.version
assert list(check.fund_cols) == list(ref.fund_cols)
import numpy as np  # noqa: E402

for attr in ("alpha", "beta", "gamma"):
    if hasattr(ref, attr):
        a, b = getattr(check, attr), getattr(ref, attr)
        assert np.allclose(a, b), f"{attr} differs"
print(f"live is now {check.version}, trained {check.trained_at}, "
      f"{len(check.fund_cols)} features")
