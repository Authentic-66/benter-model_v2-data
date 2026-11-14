"""Would a nightly fetch step break the incremental side-by-side? (scratch copy only)

1. copy the live DB (read-only source) to scratch;
2. inject line-only rows from 3 on-disk charts at tracks NOT in the corpus
   (Fairmount Park, Mahoning Valley: the case that is left after the EVD/LAD
   load), backdated months, the way a fetch for a shipper would;
3. speed figures (frozen pars), plan() for the side table, full build,
   then incremental_side_by_side run --step card on the scratch DB with its
   own log, so the live csv is untouched.
"""
import json, os, shutil, sqlite3, subprocess, sys
from pathlib import Path
REPO = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
DPV1 = REPO / "scripts_dpv1"
SCR = Path(sys.argv[1]); SCR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(DPV1)); sys.path.insert(0, str(REPO / "scripts"))
import equibase_pdf_parser as ep, db_loader, feature_incremental as fi  # noqa: E402

db = SCR / "sbs_test.db"
shutil.copy2(REPO / "scripts/racing_full.db", db)
CH = ["Fairmount Park/fp-results-2026/FP062326USA.pdf",
      "Mahoning Valley/mvr-2026-results/20260410-usa-mvr-a-d.standard.pdf",
      "Fairmount Park/fp-results-2026/FP061626USA.pdf"]
conn = sqlite3.connect(db)
print("plan before:", {k: v for k, v in fi.plan(conn, table="entry_features_dpv1_inc").items() if not k.startswith("_")})
for ch in CH:
    p = ep.parse_pdf((REPO / ch).resolve())
    r = dict(p["races"][0]); r["entries"] = r["entries"][:1]; r["exotic_payouts"] = []
    p["races"] = [r]; p["race_count"] = 1; p["source_pdf"] = ch + "|fetch-test-line-only"
    with conn:
        db_loader.ingest_parsed_pdf(conn, p)
    print("injected", p["track_code"], p["race_date"], r["entries"][0]["horse_name"])
conn.close()
def run(args):
    pr = subprocess.run([sys.executable] + args, cwd=str(REPO), capture_output=True, text=True)
    out = pr.stdout + pr.stderr
    print(f"$ {' '.join(a for a in args[:3])} -> exit {pr.returncode}")
    for l in out.splitlines():
        if any(k in l for k in ("FROZEN", "with a figure", "done", "result:", "side table", "main vs side", "picks:", "REFUSED", "Error", "Traceback", "fallback", "closure")):
            print("   ", l.strip()[:220])
    return pr.returncode
run([str(DPV1 / "speed_figures_dpv1.py"), "compute", "--db", str(db)])
conn = sqlite3.connect(db)
print("plan after inject:", {k: v for k, v in fi.plan(conn, table="entry_features_dpv1_inc").items() if not k.startswith("_")})
conn.close()
run([str(DPV1 / "feature_builder_dpv1.py"), "build", "--db", str(db)])
run([str(DPV1 / "incremental_side_by_side.py"), "run", "--step", "card", "--track", "DED", "--date", "2026-11-14",
     "--pp-file", str(REPO / "Delta Downs/ded-pps-files/ded1114y.pdf"), "--db", str(db), "--log", str(SCR / "sbs_test.csv")])
os.remove(db)
print(open(SCR / "sbs_test.csv").read())
