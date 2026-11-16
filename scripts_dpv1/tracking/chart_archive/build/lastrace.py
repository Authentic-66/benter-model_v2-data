"""Read-only: last-race track of every horse in every DED PP file this meet."""
import json, re, sys
from collections import Counter
from pathlib import Path
ROOT = Path(r"D:\Benter Model_v2 Data\benter-model_v2-data")
sys.path.insert(0, str(ROOT / "scripts_dpv1")); sys.path.insert(0, str(ROOT / "scripts"))
import brisnet_pp_parser as bp
CAP = []
_o = bp.last_finish_and_margin
def _cap(b, p=None):
    CAP.append(b); return _o(b, p)
bp.last_finish_and_margin = _cap
rows = []; alltrk = Counter(); pairs = set()
for f in sorted((ROOT / "Delta Downs/ded-pps-files").glob("ded*y.pdf")):
    CAP.clear()
    out = bp.parse_pp_file(str(f))
    for race in out["races"]:
        for h in race.get("horses", []):
            pgm = str(h.get("program_num") or h.get("pgm")); name = h.get("horse_name") or h.get("name")
            blk = next((b for b in CAP if b and re.match(r"^\s*" + re.escape(pgm) + r"\s+" + re.escape(name) + r"(?![A-Za-z])", b[0])), None)
            if blk is None:
                rows.append(dict(card=f.name, race=race.get("race_num"), pgm=pgm, horse=name, last_trk=None, note="no PP block")); continue
            dated = [(bp._pp_line_date(l), l) for l in blk if bp._pp_line_date(l)]
            for d, l in dated:
                _t = re.match(r"^\s*\d{1,2}[A-Za-z]{3}\d{2}([A-Za-z]+)", l).group(1).upper(); alltrk[_t] += 1; pairs.add((_t, d.isoformat()))
            if not dated:
                rows.append(dict(card=f.name, race=race.get("race_num"), pgm=pgm, horse=name, last_trk=None, note="first-time starter")); continue
            ld, line = max(dated, key=lambda x: x[0])
            trk = re.match(r"^\s*\d{1,2}[A-Za-z]{3}\d{2}([A-Za-z]+)", line).group(1).upper()
            rows.append(dict(card=f.name, race=race.get("race_num"), pgm=pgm, horse=name, last_trk=trk, last_date=ld.isoformat()))
    print(f.name, len(rows), flush=True)
json.dump(dict(rows=rows, all_lines=alltrk, pairs=sorted(pairs)), open(sys.argv[1], "w"), indent=0)
print(Counter(r["last_trk"] for r in rows).most_common())
print("all PP lines:", alltrk.most_common())
