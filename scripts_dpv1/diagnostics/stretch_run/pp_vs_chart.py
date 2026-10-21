"""Feature parity: stretch-run values from charts vs from Brisnet PP lines.

    python scripts_dpv1/diagnostics/stretch_run/pp_vs_chart.py [pdf ...]

Two levels, both on horses that have both sources:
* line level: every PP race line whose race is charted in the corpus (same
  horse by normalized name, same date): bl_str, bl_fin, gain.
* feature level: horses on the PP card whose card-day entry is in the corpus
  and whose most recent PP line is that entry's previous corpus race:
  last_str_gain and last_str_gain_padj from scripts_dpv1/stretch_run.py
  (charts) vs pp_features() on the PP line.
Read-only on scripts/racing_full.db. Writes out/pp_vs_chart.csv.
"""
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "scripts_dpv1"), str(ROOT / "scripts")]
import brisnet_pp_parser as bp  # noqa: E402
import stretch_run as sr  # noqa: E402
from equibase_pdf_parser import normalize_name  # noqa: E402

DEFAULT = (
    [f"Delta Downs/ded-pps-files/ded10{d}y.pdf" for d in ("10", "14", "15", "16", "17")]
    + [f"CharlesTown/ct-pps-files/{f}" for f in sorted(p.name for p in (ROOT / "CharlesTown/ct-pps-files").glob("*.pdf"))[-6:]]
    + [f"Gulfstream Park/gp-pps-files/{f}" for f in sorted(p.name for p in (ROOT / "Gulfstream Park/gp-pps-files").glob("gpx*.pdf"))[-6:]]
    + [f"Evangeline Downs/evd-pps-files/{f}" for f in sorted(p.name for p in (ROOT / "Evangeline Downs/evd-pps-files").glob("*.pdf"))[-3:]]
    + [f"Ellis/elp-pps-files/{p.name}" for p in sorted((ROOT / "Ellis/elp-pps-files").glob("*.pdf"))]
)
files = sys.argv[1:] or DEFAULT

CAP = []
_orig = bp.last_finish_and_margin
def _capture(block, page_lines=None):
    CAP.append((block, page_lines))
    return _orig(block, page_lines)
bp.last_finish_and_margin = _capture

con = sqlite3.connect(f"file:{ROOT / 'scripts' / 'racing_full.db'}?mode=ro", uri=True)
chart, fit = sr.chart_entry_values(con)
feat = sr.last_race_features(con)
ent = pd.read_sql("""SELECT e.id entry_id, h.normalized_name nn, rd.race_date
                     FROM entries e JOIN horses h ON h.id = e.horse_id
                     JOIN races r ON r.id = e.race_id JOIN race_days rd ON rd.id = r.race_day_id""", con)
ent = ent.merge(chart[["entry_id", "bl_str", "bl_fin", "gain"]], on="entry_id", how="left")
ent = ent.merge(feat, on="entry_id", how="left")
by_key = ent.drop_duplicates(["nn", "race_date"], keep=False).set_index(["nn", "race_date"])

lines, feats = [], []
for f in files:
    CAP.clear()
    try:
        out = bp.parse_pp_file(ROOT / f)
    except Exception as ex:  # a bad file should not stop the check
        print(f"skip {f}: {ex}")
        continue
    card_date = str(out.get("race_date"))
    for block, page_lines in CAP:
        m = re.match(r"^\s*\d+[A-Z]?\s+(.+?)\s*\(", block[0] if block else "")
        if not m:
            continue
        nn = normalize_name(m.group(1))
        dated = [(bp._pp_line_date(l), l) for l in block if bp._pp_line_date(l)]
        if not dated:
            continue
        for d, l in dated:
            full = bp._full_width_line(l, page_lines)
            r = sr.pp_line_stretch(full)
            key = (nn, d.isoformat())
            if r is None or key not in by_key.index:
                continue
            c = by_key.loc[key]
            if pd.isna(c.gain):
                continue
            lines.append(dict(file=Path(f).name, horse=nn, date=d.isoformat(), pp_bl_str=r["bl_str"],
                              ch_bl_str=c.bl_str, pp_bl_fin=r["bl_fin"], ch_bl_fin=c.bl_fin,
                              pp_gain=r["gain"], ch_gain=c.gain))
        # feature level: today's entry, most recent PP line = previous corpus race
        tkey = (nn, card_date)
        if tkey in by_key.index and pd.notna(by_key.loc[tkey].last_str_gain):
            d, l = max(dated, key=lambda x: x[0])
            pf = sr.pp_features(bp._full_width_line(l, page_lines), fit)
            prev_dates = ent[(ent.nn == nn) & (ent.race_date < card_date)].race_date
            if pf["last_str_gain"] is not None and len(prev_dates) and prev_dates.max() == d.isoformat():
                t = by_key.loc[tkey]
                feats.append(dict(file=Path(f).name, horse=nn, pp_gain=pf["last_str_gain"],
                                  ch_gain=t.last_str_gain, pp_padj=pf["last_str_gain_padj"],
                                  ch_padj=t.last_str_gain_padj))
    print(f"{Path(f).name}: {len(lines)} line pairs, {len(feats)} feature pairs so far", flush=True)

L, F = pd.DataFrame(lines).drop_duplicates(["horse", "date"]), pd.DataFrame(feats)
L.to_csv(HERE / "out" / "pp_vs_chart.csv", index=False)

def agree(a, b, name):
    d = (a - b).abs()
    print(f"  {name:<16} n={len(d):5,}  exact(<=0.01) {np.mean(d <= .01):6.1%}  <=0.25L {np.mean(d <= .25):6.1%}"
          f"  <=1L {np.mean(d <= 1):6.1%}  median |diff| {d.median():.2f}  corr {np.corrcoef(a, b)[0, 1]:.4f}")

print(f"\nLINE LEVEL (PP race line vs chart of the same race), {L.horse.nunique()} horses, {len(L)} races")
agree(L.pp_bl_str, L.ch_bl_str, "BL stretch call")
agree(L.pp_bl_fin, L.ch_bl_fin, "BL finish")
agree(L.pp_gain, L.ch_gain, "gain")
print(f"\nFEATURE LEVEL (today's value: PP most recent line vs charts), n={len(F)}")
if len(F):
    agree(F.pp_gain, F.ch_gain, "last_str_gain")
    G = F.dropna(subset=["pp_padj", "ch_padj"])
    agree(G.pp_padj, G.ch_padj, "padj (pooled pace)")
    print("  (padj from a PP line uses the pooled pace expectation; charts use the race's pace bucket, so padj can differ by design)")
big = L.assign(d=(L.pp_gain - L.ch_gain).abs()).sort_values("d", ascending=False).head(8)
print("\nlargest line-level gain differences:\n" + big.to_string(index=False))
