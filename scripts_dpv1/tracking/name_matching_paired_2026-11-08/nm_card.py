"""Paired name-matching check (2026-11-08), one DED card and one arm per call.
Copied from tracking/name_matching_2026-11-04/nm_card.py. Difference: these
cards (11/05-11/07) ran live with name matching ON, so the ON arm is the one
that must reproduce the logged record run; OFF is the counterfactual.

usage: python nm_card.py <YYYY-MM-DD> <off|on> <scratch_dir>

  on  = BENTER_NAME_MATCH=1 (live behaviour for these cards); must reproduce
        the logged record run, or the call exits 2.
  off = BENTER_NAME_MATCH=0 for the loader AND the PP bridge parse.

1. copy scripts/racing_full.db.dedMMDD-run.bak (the DB just before that
   card's PP load) to scratch, rebuild the card there (load_pp_card load,
   speed figures, features) with the arm's environment;
2. count PP entries whose jockey / trainer has charted history;
3. score 1.3.2 + pp-reranker-1.0 on the full pre-race field (what was logged);
4. write card_MMDD_<arm>.csv (+ _meta.json) here and delete the scratch copy.
The live DB is only ever opened read-only. The live model, reranker and
card_picks.py are used as-is (hash-checked).
"""
import copy, hashlib, json, os, shutil, sqlite3, subprocess, sys, logging
from pathlib import Path
import numpy as np
import pandas as pd

DATE, ARM, SCR = sys.argv[1], sys.argv[2], Path(sys.argv[3])
assert ARM in ("off", "on")
SCR.mkdir(parents=True, exist_ok=True)
MMDD = DATE[5:7] + DATE[8:10]
REPO = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
DPV1 = REPO / "scripts_dpv1"
HERE = Path(__file__).resolve().parent
OUT = HERE / f"card_{MMDD}_{ARM}.csv"
META = HERE / f"card_{MMDD}_{ARM}_meta.json"
LIVE = REPO / "scripts" / "racing_full.db"
BAK = REPO / "scripts" / f"racing_full.db.ded{MMDD}-run.bak"
TMP = SCR / f"ded{MMDD}-{ARM}.db"
PP = str(REPO / "Delta Downs" / "ded-pps-files" / f"ded{MMDD}y.pdf")
MATCH_LOG = HERE / f"matches_{MMDD}.jsonl"
RECORD = {"2026-11-05": "2026-11-05T09:31:23", "2026-11-06": "2026-11-06T08:55:13",
          "2026-11-07": "2026-11-07T09:54:15"}
REPRO_ARM = "on"
MODEL_SHA = "33bfb329cd5ba6e55a776967e4f2be39462e3403f9bf35cdcec12cd066d5a918"
RR_SHA = "cd4a5c791f7442d65a03c4b85e4dd3e8bd229a11592f1ef6c3f0e03e576429ea"
ITERS, SEED, TOL = 10000, 6001, 6e-5   # logged values are rounded to 4 dp

# The arm's switch must be set before card_picks / the parser are imported
# (both read it at call time, but set it once for the whole process).
os.environ.pop("BENTER_PP_READER", None)
if ARM == "on":
    os.environ["BENTER_NAME_MATCH"] = "1"
    os.environ["BENTER_NAME_MATCH_LOG"] = str(MATCH_LOG)
else:
    # Explicit OFF: since 2026-11-04 the config turns matching ON for DED
    # cards from 2026-11-05, so "unset" is no longer OFF for later cards.
    os.environ["BENTER_NAME_MATCH"] = "0"
    os.environ.pop("BENTER_NAME_MATCH_LOG", None)

sys.path.insert(0, str(DPV1)); sys.path.insert(0, str(REPO / "scripts"))
logging.basicConfig(level=logging.WARNING)
import card_picks as cp            # noqa: E402
import pp_feature_bridge as ppb    # noqa: E402

# Harness-only speed-up (as in paired_2026-11-01): cache the PP parse per
# process and hand out deep copies. One arm per process, so the cache
# never mixes switch states.
_orig_pp_index, _CACHE = ppb.pp_index, {}
def _cached(pdf, track_code=None):
    k = (str(pdf), track_code)
    if k not in _CACHE:
        _CACHE[k] = _orig_pp_index(pdf, track_code)
    return copy.deepcopy(_CACHE[k])
ppb.pp_index = _cached
cp.pp_index = _cached


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def history_counts(db):
    """Per PP entry on this card: does its jockey / trainer have a charted
    start before the card date?"""
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = """
    WITH card AS (
      SELECT e.id, r.race_num, e.program_num, e.jockey_id, e.trainer_id
      FROM entries e JOIN races r ON r.id=e.race_id
      JOIN race_days d ON d.id=r.race_day_id JOIN tracks t ON t.id=d.track_id
      WHERE t.code='DED' AND d.race_date=:d AND d.source_pdf LIKE 'PP-SCHEDULED%')
    SELECT card.race_num, card.program_num, j.name, tr.name,
      EXISTS(SELECT 1 FROM entries e2 JOIN races r2 ON r2.id=e2.race_id JOIN race_days d2 ON d2.id=r2.race_day_id
             WHERE e2.jockey_id=card.jockey_id AND e2.finish_pos IS NOT NULL AND d2.race_date<:d
               AND d2.source_pdf NOT LIKE 'PP-SCHEDULED%'),
      EXISTS(SELECT 1 FROM entries e2 JOIN races r2 ON r2.id=e2.race_id JOIN race_days d2 ON d2.id=r2.race_day_id
             WHERE e2.trainer_id=card.trainer_id AND e2.finish_pos IS NOT NULL AND d2.race_date<:d
               AND d2.source_pdf NOT LIKE 'PP-SCHEDULED%')
    FROM card LEFT JOIN jockeys j ON j.id=card.jockey_id LEFT JOIN trainers tr ON tr.id=card.trainer_id"""
    rows = c.execute(q, {"d": DATE}).fetchall()
    c.close()
    return pd.DataFrame(rows, columns=["race", "pgm", "jockey", "trainer", "jockey_hist", "trainer_hist"]).assign(
        pgm=lambda d: d.pgm.astype(str))


def main():
    if OUT.exists():
        print(f"{DATE} {ARM}: done already"); return 0
    assert sha(DPV1 / "dpv1.pkl") == MODEL_SHA, "live model hash mismatch"
    assert sha(DPV1 / "dpv1_pp_reranker.pkl") == RR_SHA, "reranker hash mismatch"
    live0 = sha(LIVE)
    if ARM == "on" and MATCH_LOG.exists():
        MATCH_LOG.unlink()
    shutil.copy2(BAK, TMP)
    bak_sha = sha(BAK)
    assert sha(TMP) == bak_sha, "copy mismatch"
    db = str(TMP)
    for cmd in (["load_pp_card.py", "load", PP, "--db", db],
                ["speed_figures_dpv1.py", "compute", "--db", db],
                ["feature_builder_dpv1.py", "build", "--db", db]):
        pr = subprocess.run([sys.executable, str(DPV1 / cmd[0])] + cmd[1:], cwd=str(REPO),
                            env=dict(os.environ), capture_output=True, text=True)
        (SCR / f"rebuild_{MMDD}_{ARM}_{cmd[0]}.log").write_text(pr.stdout + "\n" + pr.stderr, encoding="utf-8")
        if pr.returncode != 0:
            print(f"{DATE} {ARM}: {cmd[0]} FAILED\n{pr.stderr[-1500:]}"); return 1
    hist = history_counts(db)

    model = cp.load_model(str(DPV1 / "dpv1.pkl"))
    nums = cp.race_numbers(db, "DED", DATE)
    ml_map = cp.ml_lookup(PP, "DED")
    out = []
    for rn in nums:
        r = cp.one_race("DED", DATE, rn, model, db, PP, ml_map, ITERS, SEED, use_classctx=False)
        if r is None:
            continue
        for _, h in r["table"].iterrows():
            out.append({"race": rn, "pgm": str(h["pgm"]), "horse": h["horse"],
                        "p_itm": float(h["P(ITM)"]), "p_win": float(h["P(win)"]),
                        "base_itm": float(h["base"]), "cov": float(h["cov"]),
                        "rank": int(h["rank"]), "n_pp": int(r["n_reranked_pp"])})
    df = pd.DataFrame(out)
    assert (df.n_pp > 0).any(), "reranker never fired"
    df = df.merge(hist, on=["race", "pgm"], how="left")

    meta = {"date": DATE, "arm": ARM, "backup": BAK.name, "backup_sha256": bak_sha,
            "rows": len(df), "jockey_hist": int(df.jockey_hist.sum()),
            "trainer_hist": int(df.trainer_hist.sum()),
            "live_db_unchanged": sha(LIVE) == live0}
    if ARM == REPRO_ARM:
        lg = [json.loads(l) for l in open(DPV1 / "logs/predictions.jsonl", encoding="utf-8")
              if '"DED"' in l and DATE in l]
        lg = pd.DataFrame([r for r in lg if r["race_date"] == DATE and r["generated_at"] == RECORD[DATE]])
        lg["pgm"] = lg.pgm.astype(str)
        mm = lg.merge(df, left_on=["race_num", "pgm"], right_on=["race", "pgm"], how="outer",
                      suffixes=("_log", "_new"), indicator=True)
        repro = {"logged_rows": len(lg), "rerun_rows": len(df),
                 "unmatched": int((mm._merge != "both").sum()),
                 "max_d_p_itm": float(np.abs(mm.p_itm_log - mm.p_itm_new).max()),
                 "max_d_base": float(np.abs(mm.base_p_itm - mm.base_itm).max()),
                 "rank_mismatches": int((mm.rank_log != mm.rank_new).sum())}
        meta["reproduction"] = repro
        if not (repro["unmatched"] == 0 and repro["rank_mismatches"] == 0
                and max(repro["max_d_p_itm"], repro["max_d_base"]) <= TOL):
            META.write_text(json.dumps(meta, indent=1)); mm.to_csv(SCR / f"repro_{MMDD}.csv", index=False)
            print(f"{DATE} {ARM}: REPRODUCTION FAILED {repro}"); return 2
    df.assign(date=DATE, arm=ARM).to_csv(OUT, index=False)
    META.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    TMP.unlink()
    print(f"{DATE} {ARM}: {len(df)} rows, jockey hist {meta['jockey_hist']}, trainer hist "
          f"{meta['trainer_hist']}" + (f", repro {meta['reproduction']}" if ARM == REPRO_ARM else "")
          + f", live DB unchanged={meta['live_db_unchanged']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
