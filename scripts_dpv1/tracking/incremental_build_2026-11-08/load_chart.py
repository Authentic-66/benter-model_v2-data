"""usage: load_chart.py <db> <chart pdf> <cache dir>  (retrain_pipeline.load_charts)"""
import sys, sqlite3, json
from pathlib import Path
R = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
sys.path.insert(0, str(R / "scripts_dpv1")); sys.path.insert(0, str(R / "scripts"))
import retrain_pipeline as rp
c = sqlite3.connect(sys.argv[1]); c.execute("PRAGMA foreign_keys = ON")
r = rp.load_charts(c, [Path(sys.argv[2])], Path(sys.argv[3]))
c.commit()
print(json.dumps(r.get("totals", r), default=str)[:300])
