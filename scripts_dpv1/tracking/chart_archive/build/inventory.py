"""Inventory of result-chart PDFs on a drive (read-only, no network).

    python -I scripts_dpv1/tracking/chart_archive/build/inventory.py D:/ <out>/inventory.json

Writes the list build_plan.py reads as inventory.json: one record per chart file
(path, track, date, style, country, bytes, bad, pdf).

Naming styles recognised:
  long   20221101-usa-mnr-a-d.standard.pdf            (anywhere)
  short  MNR110122USA.pdf, MVR030326USA8.pdf           (anywhere)
  and, only inside a folder whose name contains "results" (as the downloader):
  short_noctry  GP020126.pdf
  dotted        01.01.26 GP Results.pdf
(The last two were added 2026-11-16: 47 GP 2026 charts are saved that way.)

build_plan.py treats the inventory as the charts that existed BEFORE the archive
downloads (their date ranges count as swept). So files that a chart_download_log
in the repo root logged as `ok` are left out by default; --include-downloads
keeps them.
"""
import csv, glob, json, os, re, sys

REPO = r"D:\Benter Model_v2 Data\benter-model_v2-data"
RE_LONG = re.compile(r"^(\d{4})(\d{2})(\d{2})-(usa|can)-([a-z]+)-a-d\.standard\.pdf$", re.I)
RE_SHORT = re.compile(r"^([A-Za-z]+?)(\d{2})(\d{2})(\d{2})(USA|CAN)(\d?)\.pdf$", re.I)
RE_NOCTRY = re.compile(r"^([A-Za-z]+)(\d{2})(\d{2})(\d{2})\.pdf$")
RE_DOTTED = re.compile(r"^(\d{2})\.(\d{2})\.(\d{2}) ([A-Za-z]+) Results\.pdf$", re.I)
SKIP_DIRS = {"$RECYCLE.BIN", "System Volume Information", ".git"}


def parse(name, in_results):
    m = RE_LONG.match(name)
    if m:
        return m[5].upper(), f"{m[1]}-{m[2]}-{m[3]}", "long", m[4].lower()
    m = RE_SHORT.match(name)
    if m:
        return m[1].upper(), f"20{m[4]}-{m[2]}-{m[3]}", "short+suffix" if m[6] else "short", m[5].lower()
    if in_results:
        m = RE_NOCTRY.match(name)
        if m:
            return m[1].upper(), f"20{m[4]}-{m[2]}-{m[3]}", "short_noctry", "usa"
        m = RE_DOTTED.match(name)
        if m:
            return m[4].upper(), f"20{m[3]}-{m[1]}-{m[2]}", "dotted", "usa"
    return None


def main():
    root, out = sys.argv[1], sys.argv[2]
    include_dl = "--include-downloads" in sys.argv
    # archive download = logged ok AND a job (not a recheck row) in a chart-archive
    # batch file -- the same rule as retrain_pipeline's archive guard. The 11/05 and
    # 11/07 logs are re-downloads of charts that were already loaded; they stay in.
    downloaded = set()
    if not include_dl:
        ca = os.path.join(REPO, "scripts_dpv1", "tracking", "chart_archive")
        jobs = set()
        for bf in [os.path.join(ca, "batch_00_test.csv")] + glob.glob(os.path.join(ca, "batches", "*.csv")):
            if os.path.basename(bf) == "batch_index.csv" or not os.path.exists(bf):
                continue
            for r in csv.DictReader(open(bf, encoding="utf-8")):
                if (r.get("recheck") or "").strip() != "1":
                    jobs.add((r["track"].strip().upper(), r["date"].strip()))
        for lp in glob.glob(os.path.join(REPO, "chart_download_log_*.csv")):
            for r in csv.DictReader(open(lp, encoding="ascii", errors="replace")):
                if r["status"] == "ok" and (r["track"], r["date"]) in jobs:
                    downloaded.add((r["track"], r["date"]))
    recs, left_out = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        in_results = "results" in os.path.basename(dirpath).lower()
        for fn in filenames:
            if not fn.lower().endswith(".pdf"):
                continue
            k = parse(fn, in_results)
            if not k:
                continue
            trk, d, style, ctry = k
            if (trk, d) in downloaded:
                left_out += 1
                continue
            p = os.path.join(dirpath, fn)
            try:
                with open(p, "rb") as f:
                    head = f.read(4)
                size = os.path.getsize(p)
            except OSError:
                continue
            recs.append(dict(path=p.replace("\\", "/"), track=trk, date=d, style=style, country=ctry,
                             bytes=size, bad="_bad_charts" in p.replace("\\", "/").split("/"),
                             pdf=head == b"%PDF"))
    recs.sort(key=lambda r: r["path"])
    json.dump(recs, open(out, "w"), indent=0)
    print(f"{len(recs)} chart files ({sum(1 for r in recs if r['pdf'] and not r['bad'])} good); "
          f"{left_out} archive downloads left out")


if __name__ == "__main__":
    main()
