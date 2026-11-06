"""$2 win / place / show ROI on the model's post-scratch #1 pick, DED cards.

Usage: python scripts_dpv1/tracking/top1_roi.py

Read-only. The #1 pick is the highest logged P(ITM) among horses that ran
(non-betting starters excluded), from the record run (latest generated_at
per race, the same rule as ticket_replay.py). Graded on official finish with
the chart's $2 win, place and show payouts. Splits: overall, model version
(1.3.2 before and after name matching, 11/05), card, final odds (under 2-1,
2-1 to 4-1 inclusive, over 4-1) and P(ITM) (under 50%, 50-60%, over 60%).
First run 2026-11-06 over 119 races (10/10-11/05). It led to the
high-confidence forward test in PHASE_6D_ROADMAP.md; that backtest is the
reason for the test, not evidence for the rule.
"""
import json, sqlite3, sys
from collections import defaultdict
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
ROOT = str(Path(__file__).resolve().parents[2])
db = sqlite3.connect(f"file:{ROOT}/scripts/racing_full.db?mode=ro", uri=True)

# record run = latest generated_at per race (same rule as ticket_replay.py)
best = {}
for l in open(f"{ROOT}/scripts_dpv1/logs/predictions.jsonl", encoding="utf-8"):
    r = json.loads(l)
    if r["track"] != "DED":
        continue
    k = (r["race_date"], r["race_num"]); g = r["generated_at"]
    if k not in best or g > best[k][0]:
        best[k] = (g, {}, r["model_version"], r.get("name_matching"))
    if g == best[k][0]:
        best[k][1][r["pgm"]] = r

res = defaultdict(dict)
for d, rn, pgm, off, wp, pp, sp, nb, odds in db.execute("""
    select rd.race_date, r.race_num, e.program_num, e.official_finish_pos, e.win_payout, e.place_payout,
           e.show_payout, e.non_betting, e.final_odds
    from entries e join races r on r.id=e.race_id join race_days rd on rd.id=r.race_day_id
    join tracks t on t.id=rd.track_id where t.code='DED'"""):
    if nb:
        continue
    res[(d, rn)][str(pgm)] = dict(off=off, w=wp, p=pp, s=sp, odds=odds)

rows, issues = [], []
for k, (g, ps, ver, nm) in sorted(best.items()):
    ran = res.get(k)
    if not ran or not any(v["off"] == 1 for v in ran.values()):
        continue  # no results loaded
    cands = [p for p in ran if p in ps]
    if not cands:
        continue
    top = max(cands, key=lambda p: ps[p]["p_itm"])
    e = ran[top]; off = e["off"]
    ret = {}
    for bt, lim, col in (("win", 1, "w"), ("place", 2, "p"), ("show", 3, "s")):
        hit = off is not None and off <= lim
        pay = e[col] if hit else 0.0
        if hit and not pay:
            issues.append((k, top, bt, off, e[col]))
            pay = 0.0
        ret[bt] = pay or 0.0
    v = {"dpv1.3.0-5track": "1.3.0", "dpv1.3.1-5track-clean": "1.3.1"}.get(ver, "1.3.2")
    if v == "1.3.2":
        v = "1.3.2 NM on" if nm == "on" else "1.3.2 NM off"
    rows.append(dict(date=k[0], rn=k[1], pgm=top, horse=ps[top]["horse_name"], ver=v, nm=nm,
                     pitm=ps[top]["p_itm"], odds=e["odds"], off=off, **ret))

def line(label, rs):
    n = len(rs)
    if not n:
        return
    out = [f"{label:<22}{n:>4}"]
    for bt, lim in (("win", 1), ("place", 2), ("show", 3)):
        hits = sum(1 for r in rs if r["off"] is not None and r["off"] <= lim)
        back = sum(r[bt] for r in rs)
        out.append(f"{hits:>4} {hits/n*100:5.1f}% ${back:7.2f} {(back-2*n)/(2*n)*100:+6.1f}%")
    print("  ".join(out))

hdr = f"{'':<22}{'n':>4}  " + "  ".join(f"{b:^28}" for b in ("WIN hits hit% back ROI", "PLACE", "SHOW"))
print(hdr)
line("ALL", rows)
print("-- by version")
for v in ("1.3.0", "1.3.1", "1.3.2 NM off", "1.3.2 NM on"):
    line(v, [r for r in rows if r["ver"] == v])
line("1.3.2 all", [r for r in rows if r["ver"].startswith("1.3.2")])
print("-- by card")
for d in sorted({r["date"] for r in rows}):
    rs = [r for r in rows if r["date"] == d]
    line(f"{d} {rs[0]['ver']}", rs)
print("-- by final odds")
line("under 2-1", [r for r in rows if r["odds"] is not None and r["odds"] < 2])
line("2-1 to 4-1", [r for r in rows if r["odds"] is not None and 2 <= r["odds"] <= 4])
line("over 4-1", [r for r in rows if r["odds"] is not None and r["odds"] > 4])
line("odds missing", [r for r in rows if r["odds"] is None])
print("-- by P(ITM)")
line("under 50%", [r for r in rows if r["pitm"] < .5])
line("50-60%", [r for r in rows if .5 <= r["pitm"] <= .6])
line("over 60%", [r for r in rows if r["pitm"] > .6])
print("issues (hit but no payout):", issues)
print("odds exactly 2 or 4:", sum(1 for r in rows if r["odds"] in (2, 4)), " pitm exactly .5/.6:", sum(1 for r in rows if r["pitm"] in (.5, .6)))
# cross by version x odds / pitm for 1.3.2
print("-- 1.3.2 only, by odds")
r2 = [r for r in rows if r["ver"].startswith("1.3.2")]
line("under 2-1", [r for r in r2 if r["odds"] < 2]); line("2-1 to 4-1", [r for r in r2 if 2 <= r["odds"] <= 4]); line("over 4-1", [r for r in r2 if r["odds"] > 4])
print("-- 1.3.2 only, by P(ITM)")
line("under 50%", [r for r in r2 if r["pitm"] < .5]); line("50-60%", [r for r in r2 if .5 <= r["pitm"] <= .6]); line("over 60%", [r for r in r2 if r["pitm"] > .6])
# odds x pitm show only
print("-- show ROI, odds x P(ITM) (all)")
for ol, of in (("<2", lambda o: o < 2), ("2-4", lambda o: 2 <= o <= 4), (">4", lambda o: o > 4)):
    for pl, pf in (("<50", lambda p: p < .5), ("50-60", lambda p: .5 <= p <= .6), (">60", lambda p: p > .6)):
        rs = [r for r in rows if of(r["odds"]) and pf(r["pitm"])]
        if rs:
            print(f"  odds {ol:<4} P {pl:<6} n={len(rs):>3} show ROI {(sum(r['show'] for r in rs)-2*len(rs))/(2*len(rs))*100:+6.1f}%")
# median show payoff / biggest
sp = sorted(r["show"] for r in rows if r["show"])
print("show payoffs: min", sp[0], "median", sp[len(sp)//2], "max", sp[-1], "n<=2.20:", sum(1 for x in sp if x <= 2.2))
print("top show:", sorted(rows, key=lambda r: -r["show"])[:5])
