"""Make the arm DBs (2026-10-19 purse-change ablation). See RULES.md.

    python _purse15/prep_purse15.py        (from scripts_dpv1/)

racing_a.db = byte copy of the live DB; racing_b.db = the same plus
entry_features_dpv1.purse_logratio_clipped. Writes db_hashes.txt.
"""
import hashlib, math, shutil, sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE = HERE.parent.parent / "scripts" / "racing_full.db"
A, B = HERE / "racing_a.db", HERE / "racing_b.db"
CAP = math.log(4)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


shutil.copyfile(LIVE, A)
assert sha(A) == sha(LIVE), "snapshot differs from live"
shutil.copyfile(A, B)
c = sqlite3.connect(B)
with c:
    c.execute("ALTER TABLE entry_features_dpv1 ADD COLUMN purse_logratio_clipped REAL")
    rows = c.execute("SELECT entry_id, purse_change_from_last FROM entry_features_dpv1").fetchall()
    vals = [(None if x is None else max(-CAP, min(CAP, math.log1p(x))), eid) for eid, x in rows]
    c.executemany("UPDATE entry_features_dpv1 SET purse_logratio_clipped=? WHERE entry_id=?", vals)
n, nn, lo, hi = c.execute("""SELECT count(*), count(purse_logratio_clipped), min(purse_logratio_clipped),
                              max(purse_logratio_clipped) FROM entry_features_dpv1""").fetchone()
raw_nn = c.execute("SELECT count(purse_change_from_last) FROM entry_features_dpv1").fetchone()[0]
assert nn == raw_nn, (nn, raw_nn)
c.close()
lines = [f"live   {sha(LIVE)}", f"a      {sha(A)}", f"b      {sha(B)}",
         f"b column: {n} rows, {nn} non-null (= raw non-null), range [{lo:.4f}, {hi:.4f}], cap ln4={CAP:.4f}"]
(HERE / "db_hashes.txt").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
