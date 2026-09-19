"""Parse EVD/FG/LAD result charts into scripts/ct_cache (the loader's cache format). No DB writes."""
import sys, json, glob, os, hashlib, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
REPO = Path(__file__).resolve().parents[2]
CACHE = REPO / "scripts" / "ct_cache"

def work(p):
    sys.path.insert(0, str(REPO / "scripts_dpv1")); sys.path.insert(0, str(REPO / "scripts"))
    import logging; logging.disable(logging.WARNING)
    import equibase_pdf_parser as parser
    p = Path(p); tgt = CACHE / (p.stem + ".json")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    if tgt.exists():
        try:
            if json.loads(tgt.read_text(encoding="utf-8")).get("file_sha256") == sha: return (str(p), "cached")
        except Exception: pass
    try:
        d = parser.parse_pdf(p)
    except Exception as e:
        return (str(p), "ERROR " + repr(e)[:200])
    tgt.write_text(json.dumps(d, indent=2), encoding="utf-8")
    return (str(p), "ok")

if __name__ == "__main__":
    files = [p for t in ("Evangeline Downs", "Fair Grounds", "Louisiana Downs") for p in sorted(glob.glob(str(REPO / t / "*-results-*" / "*.pdf")))]
    t0 = time.time(); res = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        for r in ex.map(work, files, chunksize=8): res.append(r)
    errs = [r for r in res if r[1].startswith("ERROR")]
    print(f"files {len(files)}  ok {sum(r[1]=='ok' for r in res)}  cached {sum(r[1]=='cached' for r in res)}  errors {len(errs)}  in {time.time()-t0:.0f}s")
    for e in errs: print("  ", e)
