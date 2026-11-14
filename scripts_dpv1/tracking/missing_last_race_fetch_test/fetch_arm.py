"""Missing-last-race fetch test, one DED card and one arm per call (scratch only).

usage: python fetch_arm.py <YYYY-MM-DD> <base|line|full> <scratch_dir> <targets.json>

base = the card rebuilt from scripts/racing_full.db.dedMMDD-run.bak as it ran
line = same, plus ONLY the missing horse's own line from each last-race chart
full = same, plus the WHOLE last-race charts (what a later chart load does)

Order follows the proposed runbook: load_pp_card load -> (inject) -> speed
figures -> features -> score. Pars are FROZEN (pars-v1-20261108 copied from
the live DB, read-only) in every arm, so arms differ only by the injected rows.
Writes arm_<MMDD>_<arm>_{scores,features}.csv + _meta.json next to this file.
The live DB is opened read-only; the scratch DB copy is deleted at the end.
"""
import copy, hashlib, json, os, shutil, sqlite3, subprocess, sys, logging
from pathlib import Path
import pandas as pd

DATE, ARM, SCR, TGT = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
assert ARM in ("base", "line", "full")
SCR.mkdir(parents=True, exist_ok=True)
MMDD = DATE[5:7] + DATE[8:10]
REPO = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
DPV1 = REPO / "scripts_dpv1"
HERE = Path(__file__).resolve().parent
LIVE = REPO / "scripts" / "racing_full.db"
BAK = REPO / "scripts" / f"racing_full.db.ded{MMDD}-run.bak"
TMP = SCR / f"ded{MMDD}-{ARM}.db"
PP = str(REPO / "Delta Downs" / "ded-pps-files" / f"ded{MMDD}y.pdf")
ITERS, SEED = 10000, 6001

os.environ.pop("BENTER_PP_READER", None)
os.environ.pop("BENTER_NAME_MATCH", None)      # config decides, as live
os.environ.pop("BENTER_NAME_MATCH_LOG", None)
sys.path.insert(0, str(DPV1)); sys.path.insert(0, str(REPO / "scripts"))
logging.basicConfig(level=logging.WARNING)
import card_picks as cp            # noqa: E402
import pp_feature_bridge as ppb    # noqa: E402
import equibase_pdf_parser as ep   # noqa: E402
import db_loader                   # noqa: E402

_orig, _C = ppb.pp_index, {}
def _cached(pdf, track_code=None):
    k = (str(pdf), track_code)
    if k not in _C:
        _C[k] = _orig(pdf, track_code)
    return copy.deepcopy(_C[k])
ppb.pp_index = _cached; cp.pp_index = _cached


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, tag):
    pr = subprocess.run([sys.executable, str(DPV1 / cmd[0])] + cmd[1:], cwd=str(REPO),
                        env=dict(os.environ), capture_output=True, text=True)
    (SCR / f"log_{MMDD}_{ARM}_{tag}.txt").write_text(pr.stdout + "\n" + pr.stderr, encoding="utf-8")
    if pr.returncode != 0:
        raise SystemExit(f"{cmd[0]} FAILED\n{pr.stderr[-2000:]}")
    return pr.stdout + pr.stderr


def inject(db, targets):
    """Group the wanted lines by chart; ingest line-only or whole charts."""
    by_chart = {}
    for t in targets:
        by_chart.setdefault(t["chart"], []).append(t)
    conn = sqlite3.connect(db)
    report = []
    for chart, ts in sorted(by_chart.items()):
        parsed = ep.parse_pdf((REPO / chart).resolve())
        parsed["source_pdf"] = chart + ("|fetch-test-line-only" if ARM == "line" else "")
        if ARM == "line":
            races = []
            for r in parsed["races"]:
                keep = [e for e in r["entries"]
                        if any(ep.normalize_name(e["horse_name"]) == ep.normalize_name(t["horse"]) for t in ts)]
                if keep:
                    r = dict(r); r["entries"] = keep; r["exotic_payouts"] = []
                    races.append(r)
            parsed["races"] = races; parsed["race_count"] = len(races)
        found = {ep.normalize_name(e["horse_name"]) for r in parsed["races"] for e in r["entries"]}
        for t in ts:
            hit = ep.normalize_name(t["horse"]) in found
            report.append({**t, "found_in_chart": hit})
        with conn:
            if db_loader.day_status(conn, parsed["track_code"], parsed["race_date"]):
                raise SystemExit(f"{chart}: day already in the scratch DB")
            c = db_loader.ingest_parsed_pdf(conn, parsed)
        report[-1]["ingested"] = c
    conn.close()
    return report


def copy_pars(db):
    """Frozen pars into the scratch copy (pre-freeze .bak files lack them)."""
    live = sqlite3.connect(f"file:{LIVE}?mode=ro", uri=True)
    conn = sqlite3.connect(db)
    for t in ("par_versions_dpv1", "par_times_dpv1"):
        ddl = live.execute("select sql from sqlite_master where name=?", (t,)).fetchone()[0]
        rows = live.execute(f"select * from {t}").fetchall()
        conn.execute(f"drop table if exists {t}"); conn.execute(ddl)
        if rows:
            conn.executemany(f"insert into {t} values ({','.join('?' * len(rows[0]))})", rows)
    conn.commit(); conn.close(); live.close()


def card_features(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    f = pd.read_sql_query(
        """select r.race_num as race, e.program_num as pgm, h.name as horse, f.*
           from entry_features_dpv1 f join entries e on e.id=f.entry_id join horses h on h.id=e.horse_id
           join races r on r.id=e.race_id join race_days d on d.id=r.race_day_id join tracks t on t.id=d.track_id
           where t.code='DED' and d.race_date=?""", c, params=(DATE,))
    c.close()
    return f.drop(columns=["entry_id"], errors="ignore")


def main():
    targets = [t for t in json.load(open(TGT, encoding="utf-8")) if t["date"] == DATE]
    live0 = sha(LIVE)
    shutil.copy2(BAK, TMP)
    db = str(TMP)
    out = {"date": DATE, "arm": ARM, "backup": BAK.name, "targets": len(targets)}
    load = run(["load_pp_card.py", "load", PP, "--db", db, "--no-backup-check"], "load")
    out["load_tail"] = load.strip().splitlines()[-3:]
    if ARM != "base":
        out["inject"] = inject(db, targets)
    copy_pars(db)
    sp = run(["speed_figures_dpv1.py", "compute", "--db", db], "speed")
    out["speed"] = [l for l in sp.splitlines() if "FROZEN" in l or "with a figure" in l]
    fb = run(["feature_builder_dpv1.py", "build", "--db", db], "features")
    out["features"] = [l for l in fb.splitlines() if "done" in l][-1:]
    card_features(db).to_csv(HERE / f"arm_{MMDD}_{ARM}_features.csv", index=False)
    model = cp.load_model(str(DPV1 / "dpv1.pkl"))
    ml = cp.ml_lookup(PP, "DED")
    rows = []
    for rn in cp.race_numbers(db, "DED", DATE):
        r = cp.one_race("DED", DATE, rn, model, db, PP, ml, ITERS, SEED, use_classctx=False)
        if r is None:
            continue
        for _, h in r["table"].iterrows():
            rows.append({"race": rn, "pgm": str(h["pgm"]), "horse": h["horse"], "p_itm": float(h["P(ITM)"]),
                         "p_win": float(h["P(win)"]), "base_itm": float(h["base"]), "cov": float(h["cov"])})
    pd.DataFrame(rows).to_csv(HERE / f"arm_{MMDD}_{ARM}_scores.csv", index=False)
    out["rows"] = len(rows)
    out["live_db_unchanged"] = sha(LIVE) == live0
    (HERE / f"arm_{MMDD}_{ARM}_meta.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    TMP.unlink()
    print(json.dumps({k: v for k, v in out.items() if k != "inject"}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
