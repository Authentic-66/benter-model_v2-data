"""Backfill one card's snapshot from a rebuilt DB, using the card_picks of
the code that made the logged run (run with that code dir first on sys.path).

usage: python capture_card.py <code_dir> <new_dpv1_dir> <date> <db> <model_file>
                              <generated_at> <out.json.gz> [<name_match_log>]

Runs the old one_race for every race exactly as its CLI did (same ml_map,
iters 10000, seed 6001), with wrappers that record what the race scored:
the frame before and after the PP bridge, the pre-bridge coverage, the PP
reranker rows and the shipper flags. Rebuilds the logged rows with the old
prediction_rows at the record stamp and checks them against the log
(reproduction), then writes the snapshot with the new card_snapshot writer.
"""
import importlib.util, json, os, sys
from datetime import datetime
from pathlib import Path

code, newd, date, db, model_file, gen, out = sys.argv[1:8]
if len(sys.argv) > 8:
    os.environ["BENTER_NAME_MATCH_LOG"] = sys.argv[8]
code, newd = Path(code), Path(newd)
REPO = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
sys.path.insert(0, str(code.parent / "scripts"))
sys.path.insert(0, str(code))
import logging; logging.basicConfig(level=logging.WARNING)
import card_picks as cp  # the OLD module
import numpy as np

spec = importlib.util.spec_from_file_location("card_snapshot_new", newd / "card_snapshot.py")
cs = importlib.util.module_from_spec(spec); spec.loader.exec_module(cs)

mmdd = date[5:7] + date[8:10]
pp = str(REPO / "Delta Downs" / "ded-pps-files" / f"ded{mmdd}y.pdf")
CAP = {}

_apply = cp.apply_to_card
def apply_wrap(card, pdf, model, *a, **k):
    c = CAP.setdefault(int(card.race_num), {})
    c["frame_pre"] = card.frame.copy()
    c["base_cov"] = np.asarray(cp.coverage_report(card, model)["per_horse"])
    r = _apply(card, pdf, model, *a, **k)
    c["frame_post"] = card.frame.copy()
    c["card"] = card
    return r
cp.apply_to_card = apply_wrap

_pprows = cp.pp_rows_for_race
def pprows_wrap(db_, track, date_, race_num):
    r = _pprows(db_, track, date_, race_num)
    CAP.setdefault(int(race_num), {})["pp_rows"] = r
    return r
cp.pp_rows_for_race = pprows_wrap

_ship = cp.shipper_flags
def ship_wrap(card, per_horse_cov, db_, race_date):
    r = _ship(card, per_horse_cov, db_, race_date)
    CAP.setdefault(int(card.race_num), {})["shipper"] = list(r)
    return r
cp.shipper_flags = ship_wrap

try:
    import name_match
    name_match.set_card("DED", date)
    nm_on = name_match.state()[0]
except ImportError:
    nm_on = False
model = cp.load_model(str(code / model_file))
nums = cp.race_numbers(db, "DED", date)
ml_map = cp.ml_lookup(pp, "DED")
results = []
for rn in nums:
    r = cp.one_race("DED", date, rn, model, db, pp, ml_map, 10000, 6001, use_classctx=False)
    if r:
        results.append(r)

logged = [json.loads(l) for l in open(newd / "logs" / "predictions.jsonl", encoding="utf-8") if gen in l]
logged = [r for r in logged if r["generated_at"] == gen and r["race_date"] == date and r["track"] == "DED"]
stamp = logged[0]["prediction_id"].rsplit("_", 1)[1]
kw = dict(track="DED", race_date=date, model=model, model_pkl=logged[0]["model_pkl"],
          picks_file=logged[0]["picks_file"], generated_at=datetime.fromisoformat(gen), stamp=stamp)
import inspect
if "name_matching" in inspect.signature(cp.prediction_rows).parameters:
    kw["name_matching"] = logged[0].get("name_matching")
rows = cp.prediction_rows(results, **kw)
L = {r["prediction_id"]: r for r in logged}
diffs = []
for r in rows:
    a = L.get(r["prediction_id"])
    if a is None:
        diffs.append(f"{r['prediction_id']} not in log"); continue
    for f in a:
        if not cs._same(a[f], r.get(f)):
            diffs.append(f"{r['prediction_id']} {f}: {a[f]!r} vs {r.get(f)!r}")
repro = {"logged": len(logged), "rerun": len(rows), "diffs": len(diffs), "first": diffs[:8]}

races = []
for r in results:
    c = CAP[int(r["race_num"])]
    races.append(cs.race_snapshot(c["card"], c["frame_pre"], c["frame_post"], c["base_cov"],
                                  c.get("pp_rows"), c["shipper"], ml_map))
meta = {"generated_at": gen, "stamp": stamp, "track": "DED", "race_date": date,
        "iters": 10000, "seed": 6001, "use_classctx": False,
        "picks_file": logged[0]["picks_file"], "pp_file": pp, "pp_file_sha256": cs.sha256(pp),
        "name_matching": logged[0].get("name_matching"), "logged_rows": len(logged),
        "source": f"backfill 2026-11-08 from racing_full.db.ded{mmdd}-run.bak, rebuilt with code {code}",
        "model_version": getattr(model, "version", None), "model_pkl": logged[0]["model_pkl"],
        "model_file": next(f.name for f in sorted(newd.glob("*.pkl"))
                           if cs.sha256(f) == cs.sha256(code / model_file)),
        "model_sha256": cs.sha256(code / model_file),
        "pp_reranker_version": getattr(cp.get_reranker(), "version", None),
        "pp_reranker_sha256": cs.sha256(code / "dpv1_pp_reranker.pkl"),
        "classctx_version": getattr(cp.get_classctx_reranker(), "version", None),
        "classctx_sha256": cs.sha256(code / "dpv1_classctx_reranker.pkl"),
        "feature_config_version": json.load(open(code / "dpv1_feature_config.json"))["version"],
        "feature_config_sha256": cs.sha256(code / "dpv1_feature_config.json"),
        "par_version": None,
        "git_commit": __import__("subprocess").run(["git", "-C", str(code), "rev-parse", "HEAD"],
                                                   capture_output=True, text=True).stdout.strip(),
        "git_dirty": None, "backfill_reproduction": repro}
cs.write_snapshot(out, meta, races)
print(json.dumps({"date": date, "races": len(races), "repro": repro,
                  "size_mb": round(Path(out).stat().st_size / 1e6, 3)}))
sys.exit(0 if repro["diffs"] == 0 and repro["logged"] == repro["rerun"] else 2)
