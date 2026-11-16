"""Scan the 2023 TCH chart XMLs: one row per (track, date) with race counts by breed."""
import sys, os, re, json, xml.etree.ElementTree as ET
from collections import Counter
SRC = sys.argv[1]; OUT = sys.argv[2]
rows = []
for fn in sorted(os.listdir(SRC)):
    m = re.match(r"^([a-z]+)(\d{8})tch\.xml$", fn)
    if not m:
        print("skip", fn); continue
    try:
        r = ET.parse(os.path.join(SRC, fn)).getroot()
    except ET.ParseError as e:
        print("parse error", fn, e); continue
    code = (r.findtext("TRACK/CODE") or "").strip()
    name = (r.findtext("TRACK/NAME") or "").strip()
    date = r.attrib.get("RACE_DATE")
    br = Counter((x.findtext("BREED") or "").strip() for x in r.findall("RACE"))
    lastpp = Counter((e.findtext("LAST_PP/TRACK/CODE") or "").strip() for x in r.findall("RACE") for e in x.findall("ENTRY"))
    rows.append(dict(file=fn, code=code, file_code=m.group(1).upper(), name=name, date=date, file_date=m.group(2),
                     breeds=dict(br), lastpp=dict(lastpp)))
json.dump(rows, open(OUT, "w"), indent=0)
print(len(rows), "files")
