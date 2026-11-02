"""Staged paired comparison for one DED card.

usage: python stages.py <YYYY-MM-DD> <scratch_dir> <rebuild|repro|1.3.0|1.3.2|final>

Shares constants/helpers with run_card.py (lines before main). Each stage is
short enough for a foreground call and saves its output to scratch.
"""
import sys
from pathlib import Path
_src = (Path(__file__).parent / "run_card.py").read_text(encoding="utf-8")
exec(compile(_src.split("\ndef main():")[0], "run_card_head", "exec"))

# Harness-only speed-up: the PP bridge re-parses the whole PP PDF for every
# race. Cache the parse in this process and hand out deep copies, so callers
# see exactly what a fresh parse returns. (No change to protected code.)
import copy as _copy
import pp_feature_bridge as _ppb
_orig_pp_index = _ppb.pp_index
_PP_CACHE = {}
def _cached_pp_index(pdf, track_code=None):
    k = (str(pdf), track_code)
    if k not in _PP_CACHE:
        _PP_CACHE[k] = _orig_pp_index(pdf, track_code)
    return _copy.deepcopy(_PP_CACHE[k])
_ppb.pp_index = _cached_pp_index
cp.pp_index = _cached_pp_index


def paths():
    bak = REPO / "scripts" / f"racing_full.db.ded{MMDD}-run.bak"
    tmp = SCR / f"ded{MMDD}-run.copy.db"
    pp_file = str(REPO / "Delta Downs" / "ded-pps-files" / f"ded{MMDD}y.pdf")
    return bak, tmp, pp_file


def scorer(db, pp_file, starters, scratched):
    nums = cp.race_numbers(db, "DED", DATE)
    ml_map = cp.ml_lookup(pp_file, "DED")
    orig_load, orig_rr = cp.load_race_from_db, cp.get_reranker

    def post_load(model, db_, track, race_date, race_num):
        card = orig_load(model, db_, track=track, race_date=race_date, race_num=race_num)
        keep = [(race_num, normalize_name(n)) in starters for n in card.names()]
        scratched[race_num] = [f"#{p} {n}" for p, n, k in zip(card.programs(), card.names(), keep) if not k]
        card.frame = card.frame[keep].reset_index(drop=True)
        return card

    def score(model, rr_on, field):
        # Do NOT reset cp._RERANKER: get_reranker caches behind _RERANKER_TRIED,
        # so a reset makes every later call return None (bug found 2026-11-01).
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
        df = pd.DataFrame(out)
        if rr_on:
            assert orig_rr() is not None, "reranker did not load"
            assert (df.n_pp > 0).any(), f"reranker never fired on a +rr pass ({field})"
        else:
            assert (df.n_pp == 0).all(), "reranker fired on a no-rr pass"
        return df
    return score, nums


def stage_rebuild():
    for k, (p, s) in MODELS.items():
        assert sha(p) == s, f"{k} model hash mismatch"
    assert sha(DPV1 / "dpv1_pp_reranker.pkl") == RR_SHA, "reranker hash mismatch"
    res, ex = results()
    assert len(res) and len(ex), "no results/exacta rows in live DB"
    bak, tmp, pp_file = paths()
    shutil.copy2(bak, tmp)
    bak_sha = sha(bak)
    assert sha(tmp) == bak_sha, "copy mismatch"
    db = str(tmp)
    env = dict(os.environ); env.pop("BENTER_PP_READER", None)
    for cmd in (["load_pp_card.py", "load", pp_file, "--db", db],
                ["speed_figures_dpv1.py", "compute", "--db", db],
                ["feature_builder_dpv1.py", "build", "--db", db]):
        pr = subprocess.run([sys.executable, str(DPV1 / cmd[0])] + cmd[1:], cwd=str(REPO),
                            env=env, capture_output=True, text=True)
        (SCR / f"rebuild_{MMDD}_{cmd[0]}.log").write_text(pr.stdout + "\n" + pr.stderr, encoding="utf-8")
        if pr.returncode != 0:
            print(f"{DATE}: {cmd[0]} FAILED\n{pr.stderr[-1500:]}")
            return 1
    n_feat = sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute(
        "SELECT COUNT(*) FROM entry_features_dpv1").fetchone()[0]
    (SCR / f"stage_{MMDD}_rebuild.json").write_text(json.dumps(
        {"backup_sha256": bak_sha, "rebuilt_feature_rows": n_feat, "live_sha0": sha(LIVE)}))
    print(f"{DATE}: rebuilt, {n_feat} feature rows")
    return 0


def stage_score(which):
    res, ex = results()
    starters = {(int(r.race_num), r.key) for r in res.itertuples()}
    bak, tmp, pp_file = paths()
    db = str(tmp)
    assert tmp.exists(), "no rebuilt copy; run the rebuild stage"
    scratched = {}
    score, nums = scorer(db, pp_file, starters, scratched)
    if which == "repro":
        m132 = cp.load_model(str(MODELS["1.3.2"][0]))
        rep = score(m132, True, "full")
        lg = [json.loads(l) for l in open(DPV1 / "logs/predictions.jsonl", encoding="utf-8")]
        lg = pd.DataFrame([r for r in lg if r["track"] == "DED" and r["race_date"] == DATE
                           and r["generated_at"] == RECORD[DATE]])
        mm = lg.merge(rep, left_on=["race_num", "pgm"], right_on=["race", "pgm"], how="outer",
                      suffixes=("_log", "_new"), indicator=True)
        repro = {"logged_rows": len(lg), "rerun_rows": len(rep),
                 "unmatched": int((mm._merge != "both").sum()),
                 "max_d_p_itm": float(np.abs(mm.p_itm_log - mm.p_itm_new).max()),
                 "max_d_p_win": float(np.abs(mm.p_win_log - mm.p_win_new).max()),
                 "max_d_base": float(np.abs(mm.base_p_itm - mm.base_itm).max()),
                 "rank_mismatches": int((mm.rank_log != mm.rank_new).sum())}
        ok = (repro["unmatched"] == 0 and repro["rank_mismatches"] == 0 and
              max(repro["max_d_p_itm"], repro["max_d_p_win"], repro["max_d_base"]) <= TOL)
        (SCR / f"stage_{MMDD}_repro.json").write_text(json.dumps(repro))
        if not ok:
            (CKDIR / f"card_{MMDD}_REPRO_FAILED.json").write_text(json.dumps(repro, indent=1))
            mm.to_csv(SCR / f"repro_{MMDD}.csv", index=False)
            print(f"{DATE}: REPRODUCTION FAILED {repro}")
            return 2
        rep.assign(date=DATE, model="1.3.2", reranker=True, field="full").to_csv(
            SCR / f"part_{MMDD}_132_rr_full.csv", index=False)
        print(f"{DATE}: reproduced {repro}")
        return 0
    assert (SCR / f"stage_{MMDD}_repro.json").exists(), "run repro first"
    model = cp.load_model(str(MODELS[which][0]))
    fe_cols = {r[1] for r in sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute(
        "PRAGMA table_info(entry_features_dpv1)")}
    miss = [c for c in model.fund_cols if c not in fe_cols]
    assert not miss, f"{which} missing columns {miss}"
    tag = which.replace(".", "")  # 130 / 132
    for rr_on in (True, False):
        for field in ("full", "post"):
            f = SCR / f"part_{MMDD}_{tag}_{'rr' if rr_on else 'norr'}_{field}.csv"
            if f.exists():
                continue
            score(model, rr_on, field).assign(date=DATE, model=which, reranker=rr_on,
                                              field=field).to_csv(f, index=False)
    if scratched:
        (SCR / f"stage_{MMDD}_scratched.json").write_text(
            json.dumps({str(k): v for k, v in scratched.items() if v}))
    print(f"{DATE}: scored {which}")
    return 0


def stage_final():
    res, ex = results()
    bak, tmp, pp_file = paths()
    parts = sorted(SCR.glob(f"part_{MMDD}_*.csv"))
    assert len(parts) == 8, f"{len(parts)} parts, expected 8"
    arms = pd.concat([pd.read_csv(p, dtype={"pgm": str}) for p in parts], ignore_index=True)
    arms = arms.merge(res[["race_num", "key", "program_num", "official_finish_pos", "finish_pos",
                           "final_odds", "win_payout", "show_payout", "non_betting"]]
                      .rename(columns={"race_num": "race"}), on=["race", "key"], how="left")
    arms["scratched"] = arms.program_num.isna()
    post = arms[arms.field == "post"]
    assert not post.scratched.any(), "post-scratch run contains a non-starter"
    assert (post.pgm == post.program_num.astype(str)).all(), "program mismatch"
    for (mo, rr), g in post.groupby(["model", "reranker"]):
        assert len(g) == len(res), f"{mo} {rr}: {len(g)} rows vs {len(res)} starters"
    fs = arms[(arms.field == "full") & ~arms.scratched].groupby(["model", "reranker"]).size()
    assert len(fs) == 4 and (fs == len(res)).all(), "full-field run is missing a starter"
    rb = json.loads((SCR / f"stage_{MMDD}_rebuild.json").read_text())
    repro = json.loads((SCR / f"stage_{MMDD}_repro.json").read_text())
    sf = SCR / f"stage_{MMDD}_scratched.json"
    scratched = json.loads(sf.read_text()) if sf.exists() else {}
    ex_map = {int(r.race_num): {"numbers": r.winning_numbers, "per_dollar": r.payoff / r.base_amount}
              for r in ex.itertuples()}
    arms.to_csv(CK, index=False)
    meta = {"date": DATE, "backup": bak.name, "backup_sha256": rb["backup_sha256"],
            "pp_file": Path(pp_file).name, "rebuilt_feature_rows": rb["rebuilt_feature_rows"],
            "record_run": RECORD[DATE], "reproduction": repro,
            "races": int(res.race_num.nunique()), "starters": len(res),
            "scratched": scratched, "exacta": ex_map,
            "live_db_sha_unchanged": sha(LIVE) == rb["live_sha0"]}
    META.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    tmp.unlink()
    for p in parts:
        p.unlink()
    n_scr = sum(len(v) for v in scratched.values())
    print(f"{DATE}: done. backup {bak.name}, rebuilt {rb['rebuilt_feature_rows']} feature rows; reproduced "
          f"{repro['logged_rows']} logged rows (max |dP(ITM)| {repro['max_d_p_itm']:.5f}, "
          f"{repro['rank_mismatches']} rank mismatches); {meta['races']} races, {len(res)} starters, "
          f"{n_scr} scratched; checkpoint {CK.name}; live DB unchanged={meta['live_db_sha_unchanged']}")
    return 0


if __name__ == "__main__":
    st = sys.argv[3]
    if CK.exists():
        print(f"{DATE}: checkpoint exists, skipped"); sys.exit(0)
    if st == "rebuild":
        sys.exit(stage_rebuild())
    if st in ("repro", "1.3.0", "1.3.2"):
        sys.exit(stage_score(st))
    if st == "final":
        sys.exit(stage_final())
    raise SystemExit(f"unknown stage {st}")
