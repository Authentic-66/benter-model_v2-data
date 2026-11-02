"""Paired comparison, one DED card per call.

usage: python run_card.py <YYYY-MM-DD> <scratch_dir>

1. copy the card's -run.bak (the DB just before its PP load) to scratch and
   rebuild the card there (load_pp_card load, speed figures, features);
2. reproduce the logged 1.3.2+rr record run on the full field -- exit 2 if it
   does not match;
3. score 4 arms x 2 fields (full = pre-race field, used for the re-rank method;
   post = scratched horses dropped before scoring);
4. write checkpoint scripts_dpv1/tracking/paired_2026-11-01/card_MMDD.csv
   (+ _meta.json) and delete the scratch copy.
Never opens the live DB for writing (results are read with a read-only URI).
"""
import gc, hashlib, json, os, shutil, sqlite3, subprocess, sys, logging
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
DPV1 = REPO / "scripts_dpv1"
sys.path.insert(0, str(DPV1)); sys.path.insert(0, str(REPO / "scripts"))
import card_picks as cp
from equibase_pdf_parser import normalize_name

DATE = sys.argv[1]; SCR = Path(sys.argv[2]); SCR.mkdir(parents=True, exist_ok=True)
MMDD = DATE[5:7] + DATE[8:10]
CKDIR = DPV1 / "tracking" / "paired_2026-11-01"; CKDIR.mkdir(parents=True, exist_ok=True)
CK = CKDIR / f"card_{MMDD}.csv"; META = CKDIR / f"card_{MMDD}_meta.json"
LIVE = REPO / "scripts" / "racing_full.db"
RECORD = {"2026-10-23": "2026-10-23T09:29:50", "2026-10-24": "2026-10-23T22:30:26",
          "2026-10-28": "2026-10-28T14:33:40", "2026-10-29": "2026-10-29T15:06:13",
          "2026-10-30": "2026-10-30T14:47:18"}
MODELS = {"1.3.0": (DPV1 / "dpv1_20260919_040326_retired.pkl",
                    "70b529db8ab60aeb74f9c7f0d8a88a78566522bdaa7978fb7d9bfaf11fc97ff1"),
          "1.3.2": (DPV1 / "dpv1.pkl",
                    "33bfb329cd5ba6e55a776967e4f2be39462e3403f9bf35cdcec12cd066d5a918")}
RR_SHA = "cd4a5c791f7442d65a03c4b85e4dd3e8bd229a11592f1ef6c3f0e03e576429ea"
ITERS, SEED = 10000, 6001
TOL = 6e-5  # logged values are rounded to 4 dp
logging.basicConfig(level=logging.WARNING)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def results():
    c = sqlite3.connect(f"file:{LIVE}?mode=ro", uri=True)
    res = pd.read_sql_query(
        """SELECT r.race_num, e.program_num, h.name, e.official_finish_pos, e.finish_pos,
                  e.final_odds, e.win_payout, e.show_payout, e.non_betting
           FROM entries e JOIN horses h ON h.id=e.horse_id
           JOIN races r ON r.id=e.race_id JOIN race_days rd ON rd.id=r.race_day_id
           JOIN tracks t ON t.id=rd.track_id
           WHERE t.code='DED' AND rd.race_date=?""", c, params=(DATE,))
    ex = pd.read_sql_query(
        f"""SELECT r.race_num, x.base_amount, x.winning_numbers, x.payoff
            FROM exotic_payouts x JOIN races r ON r.id=x.race_id
            JOIN race_days rd ON rd.id=r.race_day_id JOIN tracks t ON t.id=rd.track_id
            WHERE t.code='DED' AND rd.race_date=? AND x.wager_name='Exacta'""", c, params=(DATE,))
    c.close()
    res["key"] = [normalize_name(n) for n in res["name"]]
    return res, ex


def main():
    if CK.exists():
        print(f"{DATE}: checkpoint exists, skipped"); return 0
    for k, (p, s) in MODELS.items():
        assert sha(p) == s, f"{k} model hash mismatch"
    assert sha(DPV1 / "dpv1_pp_reranker.pkl") == RR_SHA, "reranker hash mismatch"
    live_sha0 = sha(LIVE)
    res, ex = results()
    assert len(res) and len(ex), "no results/exacta rows in live DB"
    starters = {(int(r.race_num), r.key) for r in res.itertuples()}

    bak = REPO / "scripts" / f"racing_full.db.ded{MMDD}-run.bak"
    tmp = SCR / f"ded{MMDD}-run.copy.db"
    shutil.copy2(bak, tmp)
    bak_sha = sha(bak); assert sha(tmp) == bak_sha, "copy mismatch"
    db = str(tmp)
    pp_file = str(REPO / "Delta Downs" / "ded-pps-files" / f"ded{MMDD}y.pdf")
    env = dict(os.environ); env.pop("BENTER_PP_READER", None)
    for cmd in (["load_pp_card.py", "load", pp_file, "--db", db],
                ["speed_figures_dpv1.py", "compute", "--db", db],
                ["feature_builder_dpv1.py", "build", "--db", db]):
        pr = subprocess.run([sys.executable, str(DPV1 / cmd[0])] + cmd[1:], cwd=str(REPO),
                            env=env, capture_output=True, text=True)
        (SCR / f"rebuild_{MMDD}_{cmd[0]}.log").write_text(pr.stdout + "\n" + pr.stderr, encoding="utf-8")
        if pr.returncode != 0:
            print(f"{DATE}: {cmd[0]} FAILED\n{pr.stderr[-1500:]}"); return 1
    n_feat = sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute(
        "SELECT COUNT(*) FROM entry_features_dpv1").fetchone()[0]

    nums = cp.race_numbers(db, "DED", DATE)
    ml_map = cp.ml_lookup(pp_file, "DED")
    orig_load, orig_rr = cp.load_race_from_db, cp.get_reranker
    scratched = {}

    def post_load(model, db_, track, race_date, race_num):
        card = orig_load(model, db_, track=track, race_date=race_date, race_num=race_num)
        keep = [(race_num, normalize_name(n)) in starters for n in card.names()]
        scratched[race_num] = [f"#{p} {n}" for p, n, k in zip(card.programs(), card.names(), keep) if not k]
        card.frame = card.frame[keep].reset_index(drop=True)
        return card

    def score(model, rr_on, field):
        cp._RERANKER = None
        cp.get_reranker = orig_rr if rr_on else (lambda path=None: None)
        cp.load_race_from_db = post_load if field == "post" else orig_load
        out = []
        try:
            for rn in nums:
                r = cp.one_race("DED", DATE, rn, model, db, pp_file, ml_map, ITERS, SEED,
                                use_classctx=False)
                if r is None:
                    continue
                for _, h in r["table"].iterrows():
                    out.append({"race": rn, "pgm": str(h["pgm"]), "horse": h["horse"],
                                "key": normalize_name(h["horse"]), "p_itm": float(h["P(ITM)"]),
                                "p_win": float(h["P(win)"]), "base_itm": float(h["base"]),
                                "cov": float(h["cov"]), "rank": int(h["rank"]),
                                "n_pp": int(r["n_reranked_pp"])})
        finally:
            cp.load_race_from_db, cp.get_reranker = orig_load, orig_rr
        return pd.DataFrame(out)

    # 2. reproduction
    m132 = cp.load_model(str(MODELS["1.3.2"][0]))
    rep = score(m132, True, "full")
    lg = [json.loads(l) for l in open(DPV1 / "logs/predictions.jsonl", encoding="utf-8")]
    lg = pd.DataFrame([r for r in lg if r["track"] == "DED" and r["race_date"] == DATE
                       and r["generated_at"] == RECORD[DATE]])
    mm = lg.merge(rep, left_on=["race_num", "pgm"], right_on=["race", "pgm"], how="outer",
                  suffixes=("_log", "_new"), indicator=True)
    d_itm = float(np.abs(mm.p_itm_log - mm.p_itm_new).max())
    d_win = float(np.abs(mm.p_win_log - mm.p_win_new).max())
    d_base = float(np.abs(mm.base_p_itm - mm.base_itm).max())
    rank_mis = int((mm.rank_log != mm.rank_new).sum())
    unmatched = int((mm._merge != "both").sum())
    repro = {"logged_rows": len(lg), "rerun_rows": len(rep), "unmatched": unmatched,
             "max_d_p_itm": d_itm, "max_d_p_win": d_win, "max_d_base": d_base,
             "rank_mismatches": rank_mis}
    ok = unmatched == 0 and rank_mis == 0 and max(d_itm, d_win, d_base) <= TOL
    if not ok:
        (CKDIR / f"card_{MMDD}_REPRO_FAILED.json").write_text(json.dumps(repro, indent=1))
        mm.to_csv(SCR / f"repro_{MMDD}.csv", index=False)
        tmp.unlink()
        print(f"{DATE}: REPRODUCTION FAILED {repro}"); return 2

    # 3. four arms x two fields
    frames = []
    for mname in ("1.3.0", "1.3.2"):
        model = m132 if mname == "1.3.2" else cp.load_model(str(MODELS[mname][0]))
        fe_cols = {r[1] for r in sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute(
            "PRAGMA table_info(entry_features_dpv1)")}
        miss = [c for c in model.fund_cols if c not in fe_cols]
        assert not miss, f"{mname} missing columns {miss}"
        for rr_on in (True, False):
            for field in ("full", "post"):
                df = rep if (mname == "1.3.2" and rr_on and field == "full") else score(model, rr_on, field)
                frames.append(df.assign(date=DATE, model=mname, reranker=rr_on, field=field))
        del model; gc.collect()
    arms = pd.concat(frames, ignore_index=True)
    arms = arms.merge(res[["race_num", "key", "program_num", "official_finish_pos", "finish_pos",
                           "final_odds", "win_payout", "show_payout", "non_betting"]]
                      .rename(columns={"race_num": "race"}), on=["race", "key"], how="left")
    arms["scratched"] = arms.program_num.isna()
    post = arms[arms.field == "post"]
    assert not post.scratched.any(), "post-scratch run contains a non-starter"
    assert (post.pgm == post.program_num).all(), "program mismatch"
    for (mo, rr), g in post.groupby(["model", "reranker"]):
        assert len(g) == len(res), f"{mo} {rr}: {len(g)} rows vs {len(res)} starters"
    full_starters = arms[(arms.field == "full") & ~arms.scratched].groupby(["model", "reranker"]).size()
    assert (full_starters == len(res)).all(), "full-field run is missing a starter"

    ex_map = {int(r.race_num): {"numbers": r.winning_numbers, "per_dollar": r.payoff / r.base_amount}
              for r in ex.itertuples()}
    arms.to_csv(CK, index=False)
    meta = {"date": DATE, "backup": bak.name, "backup_sha256": bak_sha, "pp_file": Path(pp_file).name,
            "rebuilt_feature_rows": n_feat, "record_run": RECORD[DATE], "reproduction": repro,
            "races": len(nums), "starters": len(res),
            "scratched": {str(k): v for k, v in scratched.items() if v},
            "exacta": ex_map, "live_db_sha_unchanged": sha(LIVE) == live_sha0}
    META.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    tmp.unlink()
    print(f"{DATE}: done. backup {bak.name}, rebuilt {n_feat} feature rows; reproduced {len(lg)} logged rows "
          f"(max |dP(ITM)| {d_itm:.5f}, 0 rank mismatches); {len(nums)} races, {len(res)} starters, "
          f"{sum(len(v) for v in scratched.values())} scratched; checkpoint {CK.name}; live DB unchanged={meta['live_db_sha_unchanged']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
