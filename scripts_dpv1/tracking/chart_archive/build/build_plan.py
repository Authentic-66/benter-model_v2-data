"""Build the chart-archive plan files (no network).

Inputs (build/inputs): xml2023.json (2023 TCH XMLs), inventory.json (charts on D:),
lastrace.json (DED PP files this meet), plus every chart_download_log_*.csv in the repo root. Output: scripts_dpv1/tracking/chart_archive/.
"""
import csv, json, sys, os
from collections import Counter, defaultdict
from datetime import date, timedelta

A = sys.argv[1]
OUT = r"D:\Benter Model_v2 Data\benter-model_v2-data\scripts_dpv1\tracking\chart_archive"
os.makedirs(OUT, exist_ok=True)
END = date(2026, 11, 14)          # yesterday
YEARS = [2022, 2023, 2024, 2025, 2026]
BUF = 14
CAP = 1500

xml = json.load(open(A + r"\xml2023.json"))
inv = json.load(open(A + r"\inventory.json"))
lr = json.load(open(A + r"\lastrace.json"))
REPO = r"D:\Benter Model_v2 Data\benter-model_v2-data"
# download logs written by tools/chart_downloader.ps1 (Doug's runs): ok -> on disk, none -> 404
import glob
dl_ok, dl_404 = set(), set()
for lp in sorted(glob.glob(REPO + r"\chart_download_log_*.csv")):
    for r in csv.DictReader(open(lp, encoding="ascii", errors="replace")):
        if r["status"] == "ok": dl_ok.add((r["track"], r["date"]))
        elif r["status"] == "none": dl_404.add((r["track"], r["date"]))

# ---------------------------------------------------------------- track facts from 2023 XMLs
T = defaultdict(lambda: dict(name="", days_all=[], tb_days=[], tb_races=0, races=0, breeds=Counter()))
for r in xml:
    t = T[r["code"]]
    if r["name"]: t["name"] = r["name"]
    d = date.fromisoformat(r["date"])
    t["days_all"].append(d); t["breeds"].update(r["breeds"])
    t["races"] += sum(r["breeds"].values())
    if r["breeds"].get("TB", 0) > 0:
        t["tb_days"].append(d); t["tb_races"] += r["breeds"]["TB"]

CANADA = {"ASD", "CTD", "CTM", "FE", "GPR", "HST", "LBG", "MIL", "WO", "AJX"}
PUERTO_RICO = {"CMR"}
DROPPED = {"CMR": "dropped: Puerto Rico; test 2023-07-07 404 under usa; Doug 2026-11-15: US and Canada only"}
# National Steeplechase / hunt-meet cards (TB, 1-3 days a year, mostly jump races)
STEEPLE = {"AIK", "CAM", "CHA", "CHE", "CHL", "FH", "FX", "GLN", "GN", "GRM", "GV", "MAL", "MID", "MON", "MTP",
           "ODH", "PMT", "PW", "SHW", "TRY", "UNI", "WIL", "WNT"}
FEEDERS = ["PRM", "ARP", "GIL", "LS", "ATO", "RP", "SWF"]
# Closed tracks. GG last race day 2024-06-09 (Golden Gate Fields' final card).
# PLN: on TwinSpires' list as closed; its 2023 meet is in our XMLs; whether it raced in
# 2024 is NOT verified, so the 2024 window is probed and 2025+ is not.
CLOSED = {"GG": (date(2024, 6, 9), "closed; last race day 2024-06-09"),
          "PLN": (date(2024, 12, 31), "closed (TwinSpires); last race year not verified: 2023 meet in XMLs, 2024 window probed, 2025+ not"),
          "GPW": (None, "closed before 2022 (not in 2023 XMLs; no probes); exact date not verified"),
          "PM": (None, "closed 2019 (Portland Meadows; not in 2023 XMLs; no probes)"),
          "NP": (None, "closed (Northlands Park, Thoroughbred racing ended 2016; not in 2023 XMLs; no probes)")}
NAMES = {"CMR": "Camarero", "PID": "Presque Isle Downs", "ELY": "Ely", "MNR": "Mountaineer",
         "LA": "Los Alamitos QH", "LRC": "Los Alamitos", "HOU": "Sam Houston", "IND": "Horseshoe Indianapolis",
         "FAN": "Fairmount Park", "MVR": "Mahoning Valley", "CT": "CharlesTown", "ELP": "Ellis", "DED": "Delta Downs",
         "EVD": "Evangeline Downs", "LAD": "Louisiana Downs", "FG": "Fair Grounds", "GP": "Gulfstream Park",
         "KEE": "Keeneland", "ATO": "Atokad Downs", "DG": "Douglas", "SON": "Sonoita", "UN": "Union",
         "GIL": "Gillespie County", "SWF": "Sweetwater Downs", "BAQ": "Belmont at the Big A", "FAR": "North Dakota Horse Park",
         "PMT": "Pine Mountain", "EDR": "Energy Downs", "GPR": "Grande Prairie", "LS": "Lone Star Park",
         "RP": "Remington Park", "PRM": "Prairie Meadows", "ARP": "Arapahoe Park", "OP": "Oaklawn Park"}
TWINSPIRES = {  # Doug's copy of twinspires.com/race-tracks (2026-11-15); name -> code
    "Turf Paradise": "TUP", "Rillito Park": "RIL", "Oaklawn Park": "OP", "Santa Anita Park": "SA",
    "Golden Gate Fields (closed)": "GG", "Del Mar": "DMR", "Los Alamitos": "LRC/LA", "Pleasanton (closed)": "PLN",
    "Santa Rosa": "SR", "Stockton": "?", "Fresno Fair": "FNO", "Ferndale": "FER", "Sacramento": "SAC",
    "Century Downs": "CTD", "Century Mile": "CTM", "Northlands Park (closed)": "NP", "Hastings": "HST",
    "Assiniboia Downs": "ASD", "Fort Erie": "FE", "Woodbine": "WO", "Arapahoe Park": "ARP", "Delaware Park": "DEL",
    "Gulfstream Park": "GP", "Gulfstream Park West (closed)": "GPW", "Tampa Bay Downs": "TAM", "Les Bois Park": "?",
    "Fairmount Park": "FAN/FP", "Hawthorne": "HAW", "Horseshoe Indianapolis": "IND", "Prairie Meadows": "PRM",
    "Churchill Downs": "CD", "Keeneland": "KEE", "Ellis Park": "ELP", "Kentucky Downs": "KD", "Turfway Park": "TP",
    "Delta Downs": "DED", "Evangeline Downs": "EVD", "Louisiana Downs": "LAD", "Fair Grounds": "FG",
    "Laurel Park": "LRL", "Pimlico": "PIM", "Canterbury Park": "CBY", "Fonner Park": "FON",
    "Atlantic City": "?", "Monmouth Park": "MTH", "Albuquerque Downs": "ALB", "Ruidoso Downs": "RUI",
    "Sunland Park": "SUN", "SunRay Park": "SRP", "Zia Park": "ZIA", "Aqueduct": "AQU", "Belmont Park": "BEL",
    "Saratoga": "SAR", "Belterra Park": "BTP", "Thistledown": "TDN", "Remington Park": "RP",
    "Will Rogers Downs": "WRD", "Portland Meadows (closed)": "PM", "Parx Racing": "PRX", "Penn National": "PEN",
    "Presque Isle Downs": "PID", "Lone Star Park": "LS", "Retama Park": "RET", "Sam Houston": "HOU",
    "Emerald Downs": "EMD", "Charles Town": "CT", "Mountaineer": "MNR"}
ts_codes = set()
for v in TWINSPIRES.values():
    ts_codes |= set(v.split("/"))


def folder(code):
    if code in NAMES: return NAMES[code]
    n = T[code]["name"] or code
    return " ".join(w.capitalize() for w in n.replace("'", "").split())


def category(code):
    t = T[code]
    if t["tb_races"] == 0: return "qh-only (skip)"
    if code in DROPPED: return "dropped"
    if code in STEEPLE: return "steeplechase/hunt meet"
    if len(t["tb_days"]) <= 25: return "small / fair meet"
    return "main"


# ---------------------------------------------------------------- charts on disk
have = set()
for r in inv:
    if not r["bad"] and r["pdf"]:
        have.add((r["track"], r["date"]))
        if r["track"] in ("FAN", "FP"):           # Fairmount: FAN 2023-2024, FP from 2025
            have.add(("FAN", r["date"]))
have_inv = set(have)        # charts on disk before the archive downloads (11/15 inventory)
on_disk = Counter((r["track"], r["date"][:4]) for r in inv if not r["bad"] and r["pdf"])
for (trk, d) in dl_ok:
    have.add((trk, d))
    if trk == "FP": have.add(("FAN", d))
    if (trk, d) not in have_inv: on_disk[(trk, d[:4])] += 1

# ---------------------------------------------------------------- DED PP last-race tracks
last = Counter(r["last_trk"] for r in lr["rows"] if r.get("last_trk"))
pp_pairs = defaultdict(set)
for trk, d in lr["pairs"]:
    pp_pairs[trk].add(date.fromisoformat(d))
pp_not_in_xml = {k: v for k, v in last.items() if k not in T}
pp_lines_not_in_xml = {k: v for k, v in lr["all_lines"].items() if k not in T}


# ---------------------------------------------------------------- windows
def to2023(d):
    try: return d.replace(year=2023)
    except ValueError: return date(2023, 2, 28)


def window(code, y):
    """Candidate dates in year y: within BUF days (same month-day) of a 2023 TB race day,
    on a weekday the track raced in 2023, plus any real dates known from PP lines."""
    t = T[code]; tb = sorted(t["tb_days"])
    if y == 2023:
        return set(tb)
    if code == "ATO":
        # Atokad races 2-5 days a year and the meet moves (2023: Jun 3-4; 2026: Aug 29-Sep 7),
        # so the 2023 pattern is useless. Scan every Saturday May 1-Oct 31 plus PP-known dates;
        # each Saturday hit gets Fri/Sun/Mon follow-ups from the log (follow-up batch).
        out = {d for d in pp_pairs.get(code, set()) if d.year == y and d <= END}
        d = date(y, 5, 1)
        while d <= min(date(y, 10, 31), END):
            if d.weekday() == 5: out.add(d)
            d += timedelta(days=1)
        return out
    wd = {d.weekday() for d in tb}
    near = set()
    for d in tb:
        for k in range(-BUF, BUF + 1):
            near.add(d + timedelta(days=k))
    out = set()
    d = date(y, 1, 1)
    while d.year == y and d <= END:
        if d.weekday() in wd and to2023(d) in near:
            out.add(d)
        d += timedelta(days=1)
    out |= {d for d in pp_pairs.get(code, set()) if d.year == y and d <= END}
    c = CLOSED.get(code)
    if c and c[0]:
        out = {d for d in out if d <= c[0]}
    return out


# ---------------------------------------------------------------- KB per race (from charts on disk)
xml_rpd = {k: (v["races"] / len(v["days_all"])) for k, v in T.items() if v["days_all"]}
kb = []
for r in inv:
    if not r["bad"] and r["pdf"] and r["date"][:4] in ("2024", "2025", "2026") and r["track"] in xml_rpd:
        kb.append(r["bytes"] / 1024 / xml_rpd[r["track"]])
KB_PER_RACE = sorted(kb)[len(kb) // 2]

# ---------------------------------------------------------------- priority
prio = {}
for i, c in enumerate(FEEDERS): prio[c] = ("a", i + 1)
rest = [c for c in T if c not in prio and T[c]["tb_races"] > 0 and c not in DROPPED]
b = sorted([c for c in rest if last.get(c, 0) > 0], key=lambda c: (-last[c], c))
for i, c in enumerate(b): prio[c] = ("b", i + 1)
cc = sorted([c for c in rest if c not in prio],
            key=lambda c: (category(c) == "steeplechase/hunt meet", -len(T[c]["tb_days"]), c))
for i, c in enumerate(cc): prio[c] = ("c", i + 1)

# ---------------------------------------------------------------- tracks.csv
rows = []
for code in sorted(T, key=lambda c: (prio.get(c, ("z", 0)), c)):
    t = T[code]; tb = sorted(t["tb_days"])
    months = sorted({d.month for d in tb})
    wds = Counter(d.strftime("%a") for d in tb)
    st = DROPPED.get(code) or CLOSED.get(code, (None, "open"))[1]
    rows.append(dict(
        priority_group=prio.get(code, ("skip", ""))[0], priority_rank=prio.get(code, ("", ""))[1], track_code=code,
        track_name=t["name"] or NAMES.get(code, ""), folder=folder(code),
        country="CAN" if code in CANADA else ("PR" if code in PUERTO_RICO else "USA"),
        category=category(code), status=st,
        race_days_2023=len(t["days_all"]), tb_race_days_2023=len(tb), tb_races_2023=t["tb_races"],
        first_2023=tb[0].isoformat() if tb else "", last_2023=tb[-1].isoformat() if tb else "",
        months_2023=" ".join(date(2023, m, 1).strftime("%b") for m in months),
        weekdays_2023=" ".join(f"{k}:{v}" for k, v in sorted(wds.items(), key=lambda kv: -kv[1])),
        breeds_2023=" ".join(f"{k}:{v}" for k, v in t["breeds"].most_common()),
        on_twinspires_list="Y" if code in ts_codes else "",
        ded_pp_last_race_count=last.get(code, 0),
        charts_on_disk=" ".join(f"{y}:{on_disk[(code, str(y))]}" for y in range(2019, 2027) if on_disk[(code, str(y))])))
with open(OUT + r"\tracks.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

# ---------------------------------------------------------------- jobs + estimates
est = []
jobs = []
for code in sorted(prio, key=lambda c: prio[c]):
    t = T[code]
    if code in CLOSED and CLOSED[code][0] is None: continue
    n23 = len(t["tb_days"])
    frac26 = sum(1 for d in t["tb_days"] if (d.month, d.day) <= (END.month, END.day)) / max(1, n23)
    clos = CLOSED.get(code, (None,))[0]
    for y in YEARS:
        cand = sorted(window(code, y))
        # years with charts on disk: the earlier downloads swept those date ranges, so a
        # gap inside [first, last] on disk is a non-race day; probe only outside it.
        # Only the pre-archive inventory counts as a sweep (a test-batch chart is one date).
        disk = sorted(date.fromisoformat(dd) for (tt, dd) in have_inv if tt == code and dd[:4] == str(y))
        if y != 2023 and disk:
            cand = [d for d in cand if d < disk[0] or d > disk[-1]]
        trk = "FP" if (code == "FAN" and y >= 2025) else code
        todo = [d for d in cand if (code, d.isoformat()) not in have and (trk, d.isoformat()) not in dl_404]
        exp_days = n23 if y in (2022, 2023, 2024, 2025) else round(n23 * frac26)
        if clos and y > clos.year: exp_days = 0
        if clos and y == clos.year: exp_days = sum(1 for d in t["tb_days"] if (d.month, d.day) <= (clos.month, clos.day))
        exp_have = on_disk[(code, str(y))] + (on_disk[("FP", str(y))] if code == "FAN" else 0)
        exp_new = max(0, exp_days - exp_have)
        est.append(dict(group=prio[code][0], track=code, year=y, candidates=len(cand), on_disk=len(cand) - len(todo),
                        requests=len(todo), expected_race_days=exp_days, expected_new_charts=exp_new,
                        expected_mb=round(exp_new * KB_PER_RACE * xml_rpd.get(code, 8) / 1024, 1)))
        for d in todo:
            jobs.append(dict(group=prio[code][0], rank=prio[code][1], track=trk, country="can" if code in CANADA else "usa",
                             folder=folder(code), date=d.isoformat()))

with open(OUT + r"\estimate_by_track_year.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(est[0])); w.writeheader(); w.writerows(est)

# batches of CAP rows, in priority order (a, b, c), track by track, oldest date first
bdir = OUT + r"\batches"
os.makedirs(bdir, exist_ok=True)
for fn in os.listdir(bdir):
    os.remove(os.path.join(bdir, fn))
# a new batch starts at each priority-group boundary (a, b, c), so a batch never mixes groups
parts = []
for g in ("a", "b", "c"):
    gj = [j for j in jobs if j["group"] == g]
    parts += [gj[i:i + CAP] for i in range(0, len(gj), CAP)]
nb = 0
batch_index = []
for part in parts:
    nb += 1
    with open(bdir + rf"\batch_{nb:02d}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["track", "country", "folder", "date"], extrasaction="ignore")
        w.writeheader(); w.writerows(part)
    batch_index.append(dict(batch=f"batch_{nb:02d}.csv", rows=len(part),
                            groups="".join(sorted({j["group"] for j in part})),
                            tracks=" ".join(dict.fromkeys(j["track"] for j in part))))
with open(bdir + r"\batch_index.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(batch_index[0])); w.writeheader(); w.writerows(batch_index)

# ---------------------------------------------------------------- test batch
# batch_00_test.csv is kept as run on 2026-11-15 (log: chart_download_log_20261115.csv); not rewritten
WRITE_TEST = not os.path.exists(OUT + r"\batch_00_test.csv")
test = []
def mid_date(code, y):
    """A likely race day in year y: the 2023 race day nearest the middle of the meet,
    moved to the same weekday in the same week of year y."""
    tb = sorted(T[code]["tb_days"]); m = tb[len(tb) // 2]
    d = to2023(m).replace(year=y) if not (m.month == 2 and m.day == 29) else date(y, 2, 28)
    d = d + timedelta(days=(m.weekday() - d.weekday() + 3) % 7 - 3)
    return d
for code in FEEDERS:
    for y in YEARS:
        if y == 2023:
            tb = sorted(T[code]["tb_days"]); d = tb[len(tb) // 2]; src = "known (2023 XML)"
        else:
            known = sorted(d for d in pp_pairs.get(code, set()) if d.year == y)
            if known:
                d = known[len(known) // 2]; src = "known (DED PP running line)"
            else:
                d = mid_date(code, y); src = "estimated (2023 pattern)"
        if d > END: d = mid_date(code, y) - timedelta(days=364); src += "; moved back"
        test.append(dict(track=code, country="usa", folder=folder(code), date=d.isoformat(), recheck="",
                         purpose=f"feeder {y}", date_source=src))
wo = sorted(T["WO"]["tb_days"]); d = wo[len(wo) // 2]
test.append(dict(track="WO", country="usa", folder=folder("WO"), date=d.isoformat(), recheck="", purpose="Canadian, usa path", date_source="known (2023 XML)"))
test.append(dict(track="WO", country="can", folder=folder("WO"), date=d.isoformat(), recheck="1", purpose="Canadian, can path (same date; recheck so it runs even if usa worked)", date_source="known (2023 XML)"))
cm = sorted(T["CMR"]["tb_days"]); d = cm[len(cm) // 2]
test.append(dict(track="CMR", country="usa", folder=folder("CMR"), date=d.isoformat(), recheck="", purpose="Puerto Rico (Camarero), usa path", date_source="known (2023 XML)"))
# Fairmount 2022 code: FAN or FP?
fd = mid_date("FAN", 2022)
test.append(dict(track="FAN", country="usa", folder=folder("FAN"), date=fd.isoformat(), recheck="", purpose="Fairmount 2022 code check (FAN)", date_source="estimated (2023 pattern)"))
test.append(dict(track="FP", country="usa", folder=folder("FAN"), date=fd.isoformat(), recheck="1", purpose="Fairmount 2022 code check (FP)", date_source="estimated (2023 pattern)"))
# recent-date check, CT (races Wed-Sat): 11/14 back to 11/04 are not on disk
for d in sorted([date(2026, 11, 14) - timedelta(days=k) for k in range(0, 15)], reverse=True):
    if d.weekday() in (2, 3, 4, 5) and ("CT", d.isoformat()) not in have:
        test.append(dict(track="CT", country="usa", folder=folder("CT"), date=d.isoformat(), recheck="",
                         purpose=f"recent-date check ({(date(2026, 11, 15) - d).days} days old)", date_source="CT Wed-Sat pattern"))
# CT 10/28-10/31: on disk under the short name only -> does the long-name address work yet?
for dd in (31, 30, 29, 28):
    d = date(2026, 10, dd)
    test.append(dict(track="CT", country="usa", folder=r"chart_archive_recheck\CharlesTown", date=d.isoformat(), recheck="1",
                     purpose=f"long-name address for a chart we hold under the short name ({(date(2026, 11, 15) - d).days} days old)",
                     date_source="known (on disk, short name)"))
if WRITE_TEST:
    with open(OUT + r"\batch_00_test.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(test[0])); w.writeheader(); w.writerows(test)

# PP-only tracks (not in the 2023 XMLs): real dates from DED PP running lines; not in any batch
with open(OUT + r"\extra_pp_only_tracks.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["track", "country", "folder", "date", "note"]); w.writeheader()
    for trk, nm, note in (("HCN", "Harrahs Columbus", "probably Harrah's Columbus Nebraska (successor of CLS?); NOT verified"),
                          ("EUR", "Eureka Downs", "Eureka Downs, Kansas")):
        for d in sorted(pp_pairs.get(trk, set())):
            w.writerow(dict(track=trk, country="usa", folder=nm, date=d.isoformat(), note=note))

# ---------------------------------------------------------------- report numbers
by_g = defaultdict(lambda: Counter())
for e in est:
    g = by_g[e["group"]]; g["requests"] += e["requests"]; g["new"] += e["expected_new_charts"]; g["mb"] += e["expected_mb"]
summary = dict(KB_PER_RACE=round(KB_PER_RACE, 1), jobs=len(jobs), batches=nb, test_rows=len(test),
               by_group={k: dict(v) for k, v in by_g.items()},
               total=dict(requests=sum(e["requests"] for e in est), new=sum(e["expected_new_charts"] for e in est),
                          mb=round(sum(e["expected_mb"] for e in est), 1)),
               pp_last_race=last.most_common(), pp_not_in_xml=pp_not_in_xml, pp_lines_not_in_xml=pp_lines_not_in_xml,
               ts_not_in_xml=[k for k, v in TWINSPIRES.items() if not any(c in T for c in v.split("/"))],
               xml_tb_not_on_ts=sorted(c for c in T if c not in ts_codes and T[c]["tb_races"] > 0),
               qh_only=sorted(c for c in T if T[c]["tb_races"] == 0))
json.dump(summary, open(A + r"\summary.json", "w"), indent=1, default=str)
print(json.dumps(summary, indent=1, default=str)[:6000])
