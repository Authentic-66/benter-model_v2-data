"""Re-parse every loaded DED/CT/GP chart with the fixed parser; dump payout rows.

Read-only on the DB. Output: one JSON line per chart.
"""
import json, os, sqlite3, sys, time
from multiprocessing import Pool
from pathlib import Path

REPO = "D:/Benter Model_v2 Data/benter-model_v2-data"
OUT = sys.argv[1]
BS = chr(92)


def targets():
    c = sqlite3.connect(f"file:{REPO}/scripts/racing_full.db?mode=ro", uri=True)
    seen, out = set(), []
    for s, h in c.execute("select source_pdf, file_sha256 from parsed_files where success=1 order by id"):
        p = s.replace(BS, "/")
        if not p.startswith("D:"):
            p = f"{REPO}/{p}"
        low = p.lower()
        if not any(k in low for k in ("/delta downs/", "/gulfstream park/", "/charlestown/")):
            continue
        if h in seen or not os.path.exists(p):
            continue
        seen.add(h)
        out.append(p)
    return out


def work(p):
    sys.path.insert(0, f"{REPO}/scripts")
    import equibase_pdf_parser as parser
    try:
        d = parser.parse_pdf(Path(p))
        return {"file": p, "track": d.get("track_code"), "date": d.get("race_date"),
                "races": [{"race_num": r["race_num"], "exotics": r["exotic_payouts"]} for r in d.get("races", [])]}
    except Exception as e:
        return {"file": p, "error": repr(e)}


if __name__ == "__main__":
    t = targets()
    print(len(t), "charts", flush=True)
    t0 = time.time()
    with Pool(6) as pool, open(OUT, "w", encoding="utf-8") as f:
        for i, res in enumerate(pool.imap_unordered(work, t, chunksize=4), 1):
            f.write(json.dumps(res) + "\n")
            if i % 200 == 0:
                print(i, f"{time.time() - t0:.0f}s", flush=True)
    print("done", f"{time.time() - t0:.0f}s", flush=True)
