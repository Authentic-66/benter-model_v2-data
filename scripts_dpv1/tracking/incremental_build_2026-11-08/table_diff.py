"""Cell-by-cell diff of entry_features_dpv1 between two DBs.

usage: python table_diff.py <a.db> <b.db> [--table T] [--only-card TRACK DATE]
Prints JSON: rows, ids only-in-a/b, per-column count of differing cells
(NULL = NULL; floats compared exactly), and a table hash for each side
(sha256 over rows sorted by entry_id, fixed column order, repr floats).
"""
import argparse, hashlib, json, sqlite3, sys
import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("a"); ap.add_argument("b")
ap.add_argument("--table", default="entry_features_dpv1")
ap.add_argument("--only-card", nargs=2, default=None)
x = ap.parse_args()


def load(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = f"SELECT f.* FROM {x.table} f"
    params = ()
    if x.only_card:
        q += " JOIN tracks t ON t.id = f.track_id WHERE t.code = ? AND f.race_date = ?"
        params = tuple(x.only_card)
    df = pd.read_sql_query(q, c, params=params)
    c.close()
    return df.sort_values("entry_id").reset_index(drop=True)


def table_hash(df):
    cols = sorted(df.columns)
    h = hashlib.sha256()
    for row in df[cols].itertuples(index=False, name=None):
        h.update(repr(tuple(None if (isinstance(v, float) and np.isnan(v)) else v for v in row)).encode())
    return h.hexdigest()


A, B = load(x.a), load(x.b)
out = {"rows_a": len(A), "rows_b": len(B),
       "cols_only_a": sorted(set(A.columns) - set(B.columns)),
       "cols_only_b": sorted(set(B.columns) - set(A.columns))}
ida, idb = set(A.entry_id), set(B.entry_id)
out["ids_only_a"], out["ids_only_b"] = len(ida - idb), len(idb - ida)
common = sorted(ida & idb)
A2 = A.set_index("entry_id").loc[common]
B2 = B.set_index("entry_id").loc[common]
diff = {}
for c in sorted(set(A2.columns) & set(B2.columns)):
    a, b = A2[c], B2[c]
    na, nb = a.isna().to_numpy(), b.isna().to_numpy()
    av, bv = a.to_numpy(dtype=object), b.to_numpy(dtype=object)
    neq = (na != nb) | (~na & ~nb & (av != bv))
    if neq.any():
        diff[c] = int(neq.sum())
# Stored SQLite type per cell (dtype check): typeof() on both sides.
def types(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cs = [r[1] for r in c.execute(f"PRAGMA table_info({x.table})")]
    t = pd.read_sql_query("SELECT entry_id, " + ", ".join(f'typeof("{k}") AS "{k}"' for k in cs if k != "entry_id")
                          + f" FROM {x.table}", c).set_index("entry_id")
    c.close()
    return t
TA, TB = types(x.a).loc[common], types(x.b).loc[common]
tdiff = {c: int((TA[c] != TB[c]).sum()) for c in TA.columns if c in TB.columns and (TA[c] != TB[c]).any()}
out["type_diffs_by_column"] = tdiff
out["columns_compared"] = len(set(A2.columns) & set(B2.columns))
out["differing_cells_by_column"] = diff
out["differing_cells"] = int(sum(diff.values()))
out["hash_a"], out["hash_b"] = table_hash(A), table_hash(B)
out["identical"] = (not diff and not tdiff and not out["ids_only_a"] and not out["ids_only_b"]
                    and not out["cols_only_a"] and not out["cols_only_b"])
print(json.dumps(out))
