"""Make the arm DB for the stretch-run ablation. See RULES.md.

    python _stretch/prep_stretch.py        (from scripts_dpv1/)

racing_s.db = byte copy of the live DB + the four stretch_run.FEATURES
columns in entry_features_dpv1. Writes db_hashes.txt.
"""
import hashlib, shutil, sqlite3, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parent.parent / "scripts")]
import stretch_run as sr  # noqa: E402

LIVE = HERE.parent.parent / "scripts" / "racing_full.db"
S = HERE / "racing_s.db"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


live_sha = sha(LIVE)
shutil.copyfile(LIVE, S)
assert sha(S) == live_sha, "snapshot differs from live"
c = sqlite3.connect(S)
feat = sr.last_race_features(c).set_index("entry_id")
with c:
    for col in sr.FEATURES:
        c.execute(f"ALTER TABLE entry_features_dpv1 ADD COLUMN {col} REAL")
    # by rowid: entry_id has no index on this table
    rows = c.execute("SELECT rowid, entry_id FROM entry_features_dpv1").fetchall()
    sub = feat.reindex([e for _, e in rows])
    vals = [tuple(None if v != v else float(v) for v in sub.iloc[i][sr.FEATURES]) + (rid,)
            for i, (rid, _) in enumerate(rows)]
    sets = ", ".join(f"{col}=?" for col in sr.FEATURES)
    c.executemany(f"UPDATE entry_features_dpv1 SET {sets} WHERE rowid=?", vals)
stats = [c.execute(f"SELECT count(*), count({col}), min({col}), max({col}) FROM entry_features_dpv1").fetchone()
         for col in sr.FEATURES]
c.close()
lines = [f"live   {live_sha}", f"s      {sha(S)}"]
lines += [f"{col}: {n} rows, {nn} non-null, range [{lo:.4f}, {hi:.4f}]"
          for col, (n, nn, lo, hi) in zip(sr.FEATURES, stats)]
(HERE / "db_hashes.txt").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
