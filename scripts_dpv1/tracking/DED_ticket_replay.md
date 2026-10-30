# DED meet ticket replay — model, Don, Doug (through 2026-10-29)

> **⚠ Read this before choosing a bet from these tables.** Every number
> here is in-sample: the results were known when the bets were compared.
> Any strategy picked *because* it looks good below (for example "box Don's
> top two" or "the model's top-two Pick 3") has to be tested on **future
> cards, decided in advance**, before it is trusted with money. With 48–94
> races per source, one ticket can swing an ROI by tens of points, and
> picking the best of 11 bet types × 3 sources after the fact will find a
> "winner" by chance alone.

`tracking/ticket_replay.py` → `tracking/ticket_replay.csv` (one row per
source × card × bet). Re-run it after each card; it picks up every logged
DED card with results. Re-run 2026-10-22 (evening) after the corpus Pick backfill:
identical (the meet cards had been backfilled earlier the same day).
Re-run 2026-10-23 with a new model line, **Win (top P(win))**: all 165 earlier
rows unchanged. **Re-run 2026-10-23 (evening) with the 10/23 card: 32 rows
added, all earlier rows unchanged.** Re-run 2026-10-24 (evening) with the
10/24 card: 34 rows added, all 204 earlier rows unchanged. Re-run 2026-10-29
with the 10/28 card: 34 rows added, all 238 earlier rows unchanged. Re-run
2026-10-29 (evening) with the 10/29 card: **34 rows added, all 272 earlier rows
unchanged.** Sample now: 11 cards / 94 races for the model, 10 / 85 for Don,
6 / 48 for Doug.

Pick 3/4/5 tickets use the pools each card actually ran: a Pick N is
graded only where the chart has a Pick N ending in that race (DED: Pick 3
from R3 on; Pick 4 and Pick 5 ending in R5 and the last race).

## How it is scored

* **Picks.** Model = the record run per race (latest logged run), ranked by
  final P(ITM) (Config Y). Don = his four picks with the alt promoted over a
  scratch. Doug = his picks, scratched picks dropped, no alt. Everything is
  re-ranked among horses that ran; non-betting starters are left out.
* **Grading.** Win on official finish (`win_payout`, so dead heats pay the
  dead-heat price). Exotics and Picks on the chart's payout rows, combo by
  combo: a row's `/` or `ALL` counts any of those horses, and a Pick paid on
  fewer legs (10/22's early Pick 5, 4 of 5) pays any combo with that many
  right.
* **Bases** (the chart minimum): $2 win, $1 exacta, $0.50 trifecta, $0.10
  superfecta, $0.50 Pick 3/4/5. Boxes of 2/3/4 cost 2/6/24 combos; the
  wheel costs 6 × (starters − 3); a Pick's (b) ticket costs 2 per leg
  multiplied out (fewer where a source had only one pick left in a leg).
* **Not placed:** a box when the source had fewer picks than it needs (Don
  three times, after scratches took his alt too; Doug on "Pick 'em" blanks
  and scratches). Doug's **PASS races (10/23 R3 and R5)** place nothing, and
  any Pick 3/4/5 with a PASS leg is not placed for him. On 10/24 R1 Doug's
  #3 was scratched, leaving him 3 picks (no super box there). On 10/28 his
  R3 and R5 #1/#4 picks were scratched (#5 and #10), leaving 3 picks in each.
  On 10/29 his R1 #1 (#10 Creole Lady, vet) was scratched, leaving 2 picks
  (7-9), and he gave 3 picks in R7.
* **Doug's best guesses** (`doug_picks.csv` `best_guess = 1`: 10/24 R3, R5,
  R9, maiden races picked from breeding and jockey) are placed like any
  other race. The 10/24 review gives his record with and without them.

## Caveats

* **Small samples.** 94 races for the model, 85 for Don, 48 for Doug. One
  ticket moves the ROI by tens of points: Don's Pick 4 (b) and Pick 5 (b)
  return is three tickets ($205.15 + $328.80 on 10/22, $141.00 on 10/23).
  Without those two lines Don's total is $771.13 back on $1,383.90 (−44.3%).
  (Don's own LP4 ticket hit on 10/29 for $150.15; his real tickets are graded
  in the card reviews, not here.)
* **Not like for like on timing.** Doug picks on race day with scratches and
  odds known. Don's and the model's picks are made before scratches, and the
  re-rank here then gives them the benefit of knowing the scratches too.
* **Model record runs:** 10/10 and 10/14 were logged before the 10/15 PP
  fixes; 10/14 R1–R4 were logged after post. 1.3.0 ran 10/10–10/17, 1.3.1
  10/21, 1.3.2 10/22–10/29.
* Rankings are by P(ITM), not P(win): the win bet is the P(ITM) #1. Since
  2026-10-23 the model also has a **Win (top P(win))** line (see below). It is
  an alternative to the Win line, not an extra bet, so it is left out of the
  model's "all" totals.
* The 10/22 late Pick 4/5 rows exist only since the parser fix (`1c9fe65`).
* 10/23 Pick 4 (R2–R5) paid through a scratch substitute: the R4 leg is
  `1/3` (#3 D'busker scratched, the substitute #1 won). A ticket with #3 in
  R4 counts as hitting that leg.

## By source (each over its own cards)

### Model (11 cards: 10/10, 10/14, 10/15, 10/16, 10/17, 10/21, 10/22, 10/23, 10/24, 10/28, 10/29)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 94 | 23 | $188.00 | $146.80 | -21.9% |
| Win (top P(win)) *alt* | 94 | 24 | $188.00 | $152.80 | -18.7% |
| Exacta box 2 | 94 | 8 | $188.00 | $105.60 | -43.8% |
| Trifecta box 3 | 94 | 6 | $282.00 | $102.85 | -63.5% |
| Superfecta box 4 | 94 | 6 | $225.60 | $117.59 | -47.9% |
| Super wheel 3/3/3/ALL | 94 | 6 | $311.40 | $111.07 | -64.3% |
| Pick 3 (a) top 1 | 72 | 0 | $36.00 | $0.00 | -100.0% |
| Pick 3 (b) top 2 | 72 | 3 | $288.00 | $129.95 | -54.9% |
| Pick 4 (a) top 1 | 22 | 0 | $11.00 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 22 | 0 | $176.00 | $0.00 | -100.0% |
| Pick 5 (a) top 1 | 22 | 0 | $11.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 22 | 0 | $352.00 | $0.00 | -100.0% |
| **all** | 702 | 52 | $2,069.00 | $713.86 | -65.5% |

### Don (10 cards: 10/14, 10/15, 10/16, 10/17, 10/21, 10/22, 10/23, 10/24, 10/28, 10/29)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 85 | 28 | $170.00 | $149.80 | -11.9% |
| Exacta box 2 | 85 | 17 | $170.00 | $208.70 | **+22.8%** |
| Trifecta box 3 | 85 | 4 | $255.00 | $65.55 | -74.3% |
| Superfecta box 4 | 81 | 7 | $194.40 | $83.61 | -57.0% |
| Super wheel 3/3/3/ALL | 85 | 4 | $282.00 | $33.12 | -88.3% |
| Pick 3 (a) top 1 | 65 | 3 | $32.50 | $21.05 | -35.2% |
| Pick 3 (b) top 2 | 65 | 9 | $260.00 | $209.30 | -19.5% |
| Pick 4 (a) top 1 | 20 | 0 | $10.00 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 20 | 2 | $160.00 | $346.15 | **+116.3%** |
| Pick 5 (a) top 1 | 20 | 0 | $10.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 20 | 1 | $320.00 | $328.80 | **+2.8%** |
| **all** | 631 | 75 | $1,863.90 | $1,446.08 | -22.4% |

### Doug (6 cards: 10/21, 10/22, 10/23, 10/24, 10/28, 10/29)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 48 | 17 | $96.00 | $98.00 | **+2.1%** |
| Exacta box 2 | 47 | 5 | $94.00 | $68.60 | -27.0% |
| Trifecta box 3 | 46 | 3 | $138.00 | $79.50 | -42.4% |
| Superfecta box 4 | 38 | 3 | $91.20 | $48.34 | -47.0% |
| Super wheel 3/3/3/ALL | 46 | 3 | $147.00 | $43.05 | -70.7% |
| Pick 3 (a) top 1 | 33 | 2 | $16.50 | $14.70 | -10.9% |
| Pick 3 (b) top 2 | 33 | 4 | $126.00 | $72.65 | -42.3% |
| Pick 4 (a) top 1 | 11 | 0 | $5.50 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 11 | 0 | $80.00 | $0.00 | -100.0% |
| Pick 5 (a) top 1 | 10 | 0 | $5.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 10 | 0 | $144.00 | $0.00 | -100.0% |
| **all** | 333 | 37 | $943.20 | $424.84 | -55.0% |

## Win bet: top P(ITM) vs top P(win) (model, added 2026-10-23)

The model's top P(win) horse was the same as its top P(ITM) horse in **92 of
94 races** (10/29: all 8 the same). The two differences:

* 10/15 R4: #3 Piastri P(ITM) 45.5% / P(win) 15.8% vs #6 Easy Like Breezy
  45.2% / 15.9%. Easy Like Breezy won ($6.00), Piastri ran 2nd.
* 10/28 R4 (after the model's #1, #4 Clearly Colossal, was scratched): #3
  Z's Guitar P(ITM) 44.4% / P(win) 15.0% vs #9 All West 44.3% / 15.4%.
  All West ran 5th, Z's Guitar 7th; neither won.

10/15 R4 is still the whole gap (+1 hit, +$6.00; −21.9% → −18.7% on 94 bets).

So the replay does **not** show that betting the most likely winner beats
betting the top P(ITM): the two are nearly always the same horse, because
P(win) and P(ITM) come out of the same model and rank almost identically. A
race separated by 0.1–0.4pp of P(win) is a coin flip, not evidence.

## Head to head on the same cards

### Model vs Don, 10/14–10/29 (10 cards)

| bet | Model hits | Model ROI | Don hits | Don ROI |
|---|---|---|---|---|
| Win | 19/85 | -25.3% | 28/85 | -11.9% |
| Exacta box 2 | 6/85 | -57.4% | 17/85 | **+22.8%** |
| Trifecta box 3 | 6/85 | -59.7% | 4/85 | -74.3% |
| Superfecta box 4 | 5/85 | -46.9% | 7/81 | -57.0% |
| Super wheel 3/3/3/ALL | 6/85 | -60.6% | 4/85 | -88.3% |
| Pick 3 (a) top 1 | 0/65 | -100.0% | 3/65 | -35.2% |
| Pick 3 (b) top 2 | 3/65 | -50.0% | 9/65 | -19.5% |
| Pick 4 (a) top 1 | 0/20 | -100.0% | 0/20 | -100.0% |
| Pick 4 (b) top 2 | 0/20 | -100.0% | 2/20 | **+116.3%** |
| Pick 5 (a) top 1 | 0/20 | -100.0% | 0/20 | -100.0% |
| Pick 5 (b) top 2 | 0/20 | -100.0% | 1/20 | **+2.8%** |
| **all** | $1,874 → $652 | -65.2% | $1,864 → $1,446 | -22.4% |

### All three, 10/21–10/29 (6 cards)

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 8/50 | -54.4% | 16/50 | -18.6% | 17/48 | **+2.1%** |
| Exacta box 2 | 3/50 | -64.0% | 10/50 | **+16.7%** | 5/47 | -27.0% |
| Trifecta box 3 | 5/50 | -44.3% | 3/50 | -67.4% | 3/46 | -42.4% |
| Superfecta box 4 | 4/50 | -10.6% | 5/47 | -36.7% | 3/38 | -47.0% |
| Super wheel 3/3/3/ALL | 5/50 | -35.6% | 3/50 | -84.4% | 3/46 | -70.7% |
| Pick 3 (a) top 1 | 0/38 | -100.0% | 2/38 | -22.6% | 2/33 | -10.9% |
| Pick 3 (b) top 2 | 0/38 | -100.0% | 7/38 | **+21.3%** | 4/33 | -42.3% |
| Pick 4 (a) top 1 | 0/12 | -100.0% | 0/12 | -100.0% | 0/11 | -100.0% |
| Pick 4 (b) top 2 | 0/12 | -100.0% | 2/12 | **+260.6%** | 0/11 | -100.0% |
| Pick 5 (a) top 1 | 0/12 | -100.0% | 0/12 | -100.0% | 0/10 | -100.0% |
| Pick 5 (b) top 2 | 0/12 | -100.0% | 1/12 | **+71.3%** | 0/10 | -100.0% |
| **all** | $1,098 → $374 | -66.0% | $1,091 → $1,217 | **+11.5%** | $943 → $425 | -55.0% |

## By card

### 2026-10-10

| bet | Model hits | Model ROI |
|---|---|---|
| Win | 4/9 | +10.0% |
| Exacta box 2 | 2/9 | +83.9% |
| Trifecta box 3 | 0/9 | -100.0% |
| Superfecta box 4 | 1/9 | -56.8% |
| Super wheel 3/3/3/ALL | 0/9 | -100.0% |
| Pick 3 (a) top 1 | 0/7 | -100.0% |
| Pick 3 (b) top 2 | 0/7 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% |
| **all** | $196 → $62 | -68.2% |

### 2026-10-14

| bet | Model hits | Model ROI | Don hits | Don ROI |
|---|---|---|---|---|
| Win | 1/8 | +13.7% | 1/8 | -52.5% |
| Exacta box 2 | 0/8 | -100.0% | 1/8 | +63.7% |
| Trifecta box 3 | 0/8 | -100.0% | 0/8 | -100.0% |
| Superfecta box 4 | 0/8 | -100.0% | 0/8 | -100.0% |
| Super wheel 3/3/3/ALL | 0/8 | -100.0% | 0/8 | -100.0% |
| Pick 3 (a) top 1 | 0/6 | -100.0% | 0/6 | -100.0% |
| Pick 3 (b) top 2 | 0/6 | -100.0% | 0/6 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $180 → $18 | -89.9% | $180 → $34 | -81.3% |

### 2026-10-15

| bet | Model hits | Model ROI | Don hits | Don ROI |
|---|---|---|---|---|
| Win | 3/8 | +42.5% | 3/8 | +40.0% |
| Exacta box 2 | 2/8 | +53.1% | 1/8 | -46.9% |
| Trifecta box 3 | 0/8 | -100.0% | 0/8 | -100.0% |
| Superfecta box 4 | 0/8 | -100.0% | 0/8 | -100.0% |
| Super wheel 3/3/3/ALL | 0/8 | -100.0% | 0/8 | -100.0% |
| Pick 3 (a) top 1 | 0/6 | -100.0% | 0/6 | -100.0% |
| Pick 3 (b) top 2 | 0/6 | -100.0% | 0/6 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $183 → $47 | -74.2% | $183 → $31 | -83.2% |

### 2026-10-16

| bet | Model hits | Model ROI | Don hits | Don ROI |
|---|---|---|---|---|
| Win | 2/9 | -43.3% | 4/9 | +10.0% |
| Exacta box 2 | 0/9 | -100.0% | 2/9 | +58.3% |
| Trifecta box 3 | 0/9 | -100.0% | 1/9 | -38.1% |
| Superfecta box 4 | 0/9 | -100.0% | 1/8 | -41.2% |
| Super wheel 3/3/3/ALL | 0/9 | -100.0% | 1/9 | -73.7% |
| Pick 3 (a) top 1 | 0/7 | -100.0% | 0/7 | -100.0% |
| Pick 3 (b) top 2 | 0/7 | -100.0% | 0/7 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $199 → $10 | -94.9% | $197 → $85 | -56.8% |

### 2026-10-17

| bet | Model hits | Model ROI | Don hits | Don ROI |
|---|---|---|---|---|
| Win | 5/10 | +51.0% | 4/10 | -7.0% |
| Exacta box 2 | 1/10 | -40.0% | 3/10 | +44.0% |
| Trifecta box 3 | 1/10 | -35.8% | 0/10 | -100.0% |
| Superfecta box 4 | 1/10 | -96.1% | 1/10 | -96.1% |
| Super wheel 3/3/3/ALL | 1/10 | -69.6% | 0/10 | -100.0% |
| Pick 3 (a) top 1 | 0/8 | -100.0% | 1/8 | +58.7% |
| Pick 3 (b) top 2 | 3/8 | +306.1% | 2/8 | -22.3% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $212 → $202 | -4.8% | $212 → $80 | -62.6% |

### 2026-10-21

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 2/8 | -40.0% | 3/8 | +13.7% | 3/8 | +18.8% |
| Exacta box 2 | 1/8 | -55.6% | 3/8 | +228.8% | 1/7 | -14.3% |
| Trifecta box 3 | 1/8 | -15.0% | 0/8 | -100.0% | 0/7 | -100.0% |
| Superfecta box 4 | 0/8 | -100.0% | 2/7 | +53.5% | 0/5 | -100.0% |
| Super wheel 3/3/3/ALL | 1/8 | +106.7% | 0/8 | -100.0% | 0/7 | -100.0% |
| Pick 3 (a) top 1 | 0/6 | -100.0% | 0/6 | -100.0% | 0/6 | -100.0% |
| Pick 3 (b) top 2 | 0/6 | -100.0% | 0/6 | -100.0% | 1/6 | -2.8% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $175 → $84 | -51.9% | $173 → $97 | -44.0% | $131 → $48 | -63.0% |

### 2026-10-22

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 1/8 | -67.5% | 2/8 | -43.8% | 2/8 | -43.8% |
| Exacta box 2 | 0/8 | -100.0% | 2/8 | +33.7% | 0/8 | -100.0% |
| Trifecta box 3 | 1/8 | -44.0% | 0/8 | -100.0% | 0/8 | -100.0% |
| Superfecta box 4 | 0/8 | -100.0% | 1/8 | +64.3% | 1/7 | +7.6% |
| Super wheel 3/3/3/ALL | 1/8 | -80.0% | 0/8 | -100.0% | 0/8 | -100.0% |
| Pick 3 (a) top 1 | 0/6 | -100.0% | 0/6 | -100.0% | 0/6 | -100.0% |
| Pick 3 (b) top 2 | 0/6 | -100.0% | 3/6 | +285.2% | 0/6 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 1/2 | +1182.2% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 1/2 | +927.5% | 0/2 | -100.0% |
| **all** | $177 → $24 | -86.6% | $177 → $688 | +288.0% | $175 → $27 | -84.5% |

### 2026-10-23

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 0/9 | -100.0% | 2/9 | -27.8% | 2/7 | -15.7% |
| Exacta box 2 | 0/9 | -100.0% | 2/9 | **+17.8%** | 1/7 | -22.1% |
| Trifecta box 3 | 1/9 | -53.9% | 1/9 | -58.0% | 0/7 | -100.0% |
| Superfecta box 4 | 1/9 | -69.2% | 2/8 | -26.9% | 1/6 | **+25.8%** |
| Super wheel 3/3/3/ALL | 1/9 | -74.4% | 1/9 | -76.9% | 0/7 | -100.0% |
| Pick 3 (a) top 1 | 0/7 | -100.0% | 0/7 | -100.0% | 0/2 | -100.0% |
| Pick 3 (b) top 2 | 0/7 | -100.0% | 2/7 | **+176.1%** | 0/2 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/1 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 1/2 | **+781.2%** | 0/1 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | — | — |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | — | — |
| **all** | $195 → $26 | -86.4% | $192 → $285 | **+47.8%** | $105 → $41 | -61.1% |

### 2026-10-24

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 1/9 | -74.4% | 1/9 | -74.4% | 3/9 | **+22.2%** |
| Exacta box 2 | 1/9 | **+23.3%** | 0/9 | -100.0% | 1/9 | **+6.1%** |
| Trifecta box 3 | 1/9 | -6.7% | 0/9 | -100.0% | 2/9 | **+105.4%** |
| Superfecta box 4 | 2/9 | **+140.6%** | 0/9 | -100.0% | 1/8 | -36.8% |
| Super wheel 3/3/3/ALL | 1/9 | -54.0% | 0/9 | -100.0% | 2/9 | **+28.5%** |
| Pick 3 (a) top 1 | 0/7 | -100.0% | 0/7 | -100.0% | 0/7 | -100.0% |
| Pick 3 (b) top 2 | 0/7 | -100.0% | 0/7 | -100.0% | 1/7 | **+44.5%** |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $192 → $116 | -39.7% | $192 → $5 | -97.6% | $190 → $183 | -3.7% |

### 2026-10-28

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 3/8 | -8.8% | 6/8 | **+71.2%** | 5/8 | **+28.8%** |
| Exacta box 2 | 1/8 | -58.1% | 3/8 | **+34.4%** | 1/8 | -50.6% |
| Trifecta box 3 | 1/8 | -49.6% | 1/8 | -44.0% | 0/8 | -100.0% |
| Superfecta box 4 | 0/8 | -100.0% | 0/7 | -100.0% | 0/6 | -100.0% |
| Super wheel 3/3/3/ALL | 1/8 | **+4.6%** | 1/8 | -69.3% | 0/8 | -100.0% |
| Pick 3 (a) top 1 | 0/6 | -100.0% | 2/6 | **+390.0%** | 2/6 | **+390.0%** |
| Pick 3 (b) top 2 | 0/6 | -100.0% | 2/6 | -38.8% | 2/6 | -38.8% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $180 → $63 | -65.1% | $178 → $100 | -43.6% | $176 → $58 | -67.0% |

* Don's and Doug's Pick 3 (a) hits are the same two tickets: their #1s
  were the same horses in R1–R4 (7, 3, 9, 7), so R1–R3 7-3-9 ($7.05) and
  R2–R4 3-9-7 ($7.65) hit for both. Doug's real R2–R4 Pick 3 bet (3 / 9 /
  3,7,9) cashed the same $7.65.
* Both late Pick 4s died in R5 for everyone: #5 Tarkington Girl won at
  45.2-1 (model 7th of 9, Don and Doug did not have her).
* Model super wheel hit R2 (3-5-2-8, $29.51 on a $4.20 wheel). The model's
  R4 pick list lost its #1 (#4 Clearly Colossal, vet scratch) and its
  new #1 #3 Z's Guitar ran last.

### 2026-10-29

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 1/8 | -27.5% | 2/8 | -42.5% | 2/8 | -2.5% |
| Exacta box 2 | 0/8 | -100.0% | 0/8 | -100.0% | 1/8 | **+16.9%** |
| Trifecta box 3 | 0/8 | -100.0% | 1/8 | **+0.2%** | 1/7 | **+14.5%** |
| Superfecta box 4 | 1/8 | **+153.5%** | 0/8 | -100.0% | 0/6 | -100.0% |
| Super wheel 3/3/3/ALL | 0/8 | -100.0% | 1/8 | -64.6% | 1/7 | -58.9% |
| Pick 3 (a) top 1 | 0/6 | -100.0% | 0/6 | -100.0% | 0/6 | -100.0% |
| Pick 3 (b) top 2 | 0/6 | -100.0% | 0/6 | -100.0% | 0/6 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $178 → $60 | -66.1% | $178 → $42 | -76.2% | $167 → $67 | -59.5% |

* Model super box hit R3 (8-10-2-3 → 10-3-8-2, $48.68 on $2.40). It only
  hit because the reranker lifted #3 Bandit's Escape (2nd at 21.1-1) from
  7th to 4th; the base-only top four would have missed R3 but hit R7
  (4-7-6-5 → 5-4-7-6, $9.13), where the reranked top four (7-4-6-3) missed.
* Don's and Doug's R7 picks (7-4-5 and 4-5-7) both hit the trifecta box
  (5-4-7, $24.05) and the super wheel ($9.13). Doug's R7 top two 4-5 hit the
  exacta box ($18.70).
* All three missed R1 (#8 Sunnyday Lightning, 4.3-1) and R4 (#2 Jailhouse
  Religion, 30.1-1). The consensus #1s R1 #7 Gently (5th, 1.7-1 fav) and R6
  #4 Takethe Hint (3rd, 1.5-1 fav) both lost.
* Don's real LP4 ticket (R5–R8, 48 combos, $24) hit 7-2-5-5 for $150.15;
  the replay's Pick 4 (b) uses his top two per leg and missed R5 (2-3).
