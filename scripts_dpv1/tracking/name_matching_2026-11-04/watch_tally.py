"""Watch-list tally, switch OFF vs ON, DED 10/23-10/30 (11/04 has no results).

usage: python watch_tally.py   (writes watch_tally_output.txt and watch_tally_rows.csv)

Same rules as tracking/watch_people_tally.py: people identified from the
chart's trainer / jockey (so a rider change counts for whoever rode), graded
on official_finish_pos, non-betting starters left out. Model expectation =
summed P(ITM) of the full pre-race field as logged (OFF reproduces the
logged record run exactly). ON = BENTER_NAME_MATCH=1 incl. the alias table;
"ON, no alias" is the first validation run (before name_aliases.csv).
Read-only on the live DB.
"""
import sys, sqlite3
from pathlib import Path
import pandas as pd

REPO = Path(r"D:/Benter Model_v2 Data/benter-model_v2-data")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "scripts_dpv1" / "tracking"))
from check_watch_list import load_watch_list, person_matches  # noqa: E402

DATES = ["2026-10-23", "2026-10-24", "2026-10-28", "2026-10-29", "2026-10-30"]
ARMS = {"off": HERE, "on": HERE, "on_noalias": HERE / "on_without_alias"}
c = sqlite3.connect(f"file:{REPO}/scripts/racing_full.db?mode=ro", uri=True)
watch = [w for w in load_watch_list() if w["type"] in ("trainer", "jockey")]

rows = []
for d in DATES:
    m = d[5:7] + d[8:10]
    arm = {}
    for a, folder in ARMS.items():
        f = pd.read_csv(folder / f"card_{m}_{'off' if a == 'off' else 'on'}.csv", dtype={"pgm": str})
        f["pgm"] = f.pgm.str.strip().str.upper()
        arm[a] = f.set_index(["race", "pgm"])
    res = c.execute("""
        SELECT r.race_num, e.program_num, e.official_finish_pos, tr.name, j.name
        FROM entries e JOIN races r ON r.id=e.race_id JOIN race_days rd ON rd.id=r.race_day_id
        JOIN tracks t ON t.id=rd.track_id
        LEFT JOIN trainers tr ON tr.id=e.trainer_id LEFT JOIN jockeys j ON j.id=e.jockey_id
        WHERE t.code='DED' AND rd.race_date=? AND rd.source_pdf NOT LIKE 'PP-SCHEDULED%'
          AND e.finish_status IS NOT NULL AND e.non_betting=0""", (d,)).fetchall()
    for rn, pgm, fin, trn, jky in res:
        k = (int(rn), str(pgm).strip().upper())
        for w in watch:
            who = trn if w["type"] == "trainer" else jky
            if not person_matches(w, who) or k not in arm["off"].index:
                continue
            col = "trainer_hist" if w["type"] == "trainer" else "jockey_hist"
            rows.append({"date": d, "race": k[0], "pgm": k[1], "horse": arm["off"].loc[k, "horse"],
                         "type": w["type"], "who": w["name"], "fin": fin,
                         "itm": int(fin is not None and fin <= 3),
                         "hist_off": int(arm["off"].loc[k, col]), "hist_on": int(arm["on"].loc[k, col]),
                         **{f"p_{a}": float(arm[a].loc[k, "p_itm"]) for a in ARMS}})
R = pd.DataFrame(rows)
R.to_csv(HERE / "watch_tally_rows.csv", index=False)

out = []
P = out.append
P("Watch-list tally, DED 10/23-10/30 logged starters (full-field P(ITM) as logged)")
P(f"{'who':24s} {'starts':>6s} {'hist off/on':>11s} {'ITM':>4s} | {'sum P off':>9s} {'gap off':>8s} | "
  f"{'sum P on':>8s} {'gap on':>7s} | {'P moved':>7s} | {'on, no alias: sum P':>19s}")
for (t, w), g in R.groupby(["type", "who"], sort=False):
    po, pn, pa, a = g.p_off.sum(), g.p_on.sum(), g.p_on_noalias.sum(), g.itm.sum()
    P(f"{t[0].upper()} {w:22s} {len(g):6d} {g.hist_off.sum():5d}/{g.hist_on.sum():<5d} {a:4d} | "
      f"{po:9.2f} {a - po:+8.2f} | {pn:8.2f} {a - pn:+7.2f} | {pn - po:+7.2f} | {pa:19.2f}")
P("\ngap = actual ITM - summed P(ITM); P moved = sum P on - sum P off (the part of the gap that was missing history)")
P("\nPer card (sum P off -> on, actual ITM):")
for (t, w), g in R.groupby(["type", "who"], sort=False):
    parts = [f"{d[5:]}: {h.p_off.sum():.2f}->{h.p_on.sum():.2f} ({h.itm.sum()}/{len(h)})" for d, h in g.groupby("date")]
    P(f"  {w}: " + "; ".join(parts))
txt = "\n".join(out)
(HERE / "watch_tally_output.txt").write_text(txt + "\n", encoding="utf-8")
print(txt)
