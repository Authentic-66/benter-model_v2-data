# DED meet ticket replay — model, Don, Doug (through 2026-10-22)

> **⚠ Read this before choosing a bet from these tables.** Every number
> here is in-sample: the results were known when the bets were compared.
> Any strategy picked *because* it looks good below (for example "box Don's
> top two" or "the model's top-two Pick 3") has to be tested on **future
> cards, decided in advance**, before it is trusted with money. With 16–60
> races per source, one ticket can swing an ROI by tens of points, and
> picking the best of 11 bet types × 3 sources after the fact will find a
> "winner" by chance alone.

`tracking/ticket_replay.py` → `tracking/ticket_replay.csv` (one row per
source × card × bet). Re-run it after each card; it picks up every logged
DED card with results. Re-run 2026-10-22 (evening) after the corpus Pick backfill:
identical (the meet cards had been backfilled earlier the same day).

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
  twice, after scratches took his alt too; Doug six times, "Pick 'em"
  blanks and scratches).

## Caveats

* **Small samples.** 60 races for the model, 51 for Don, 16 for Doug. One
  ticket moves the ROI by tens of points: Don's whole edge in the Picks is
  two 10/22 tickets ($533.95 back on $48). Without his 10/22 Pick tickets
  Don's total is $387.74 back on $1,045.90 (−62.9%).
* **Not like for like on timing.** Doug picks on race day with scratches and
  odds known. Don's and the model's picks are made before scratches, and the
  re-rank here then gives them the benefit of knowing the scratches too.
* **Model record runs:** 10/10 and 10/14 were logged before the 10/15 PP
  fixes; 10/14 R1–R4 were logged after post. 1.3.0 ran 10/10–10/17, 1.3.1
  10/21, 1.3.2 10/22.
* Rankings are by P(ITM), not P(win): the win bet is the P(ITM) #1.
* The 10/22 late Pick 4/5 rows exist only since the parser fix (`1c9fe65`).

## By source (each over its own cards)

### Model (7 cards: 10/10, 10/14, 10/15, 10/16, 10/17, 10/21, 10/22)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 60 | 18 | $120.00 | $116.00 | -3.3% |
| Exacta box 2 | 60 | 6 | $120.00 | $76.70 | -36.1% |
| Trifecta box 3 | 60 | 3 | $180.00 | $53.10 | -70.5% |
| Superfecta box 4 | 60 | 2 | $144.00 | $10.28 | -92.9% |
| Super wheel 3/3/3/ALL | 60 | 3 | $202.20 | $62.04 | -69.3% |
| Pick 3 (a) top 1 | 46 | 0 | $23.00 | $0.00 | -100.0% |
| Pick 3 (b) top 2 | 46 | 3 | $184.00 | $129.95 | -29.4% |
| Pick 4 (a) top 1 | 14 | 0 | $7.00 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 14 | 0 | $112.00 | $0.00 | -100.0% |
| Pick 5 (a) top 1 | 14 | 0 | $7.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 14 | 0 | $224.00 | $0.00 | -100.0% |
| **all** | 448 | 35 | $1,323.20 | $448.07 | -66.1% |

### Don (6 cards: 10/14, 10/15, 10/16, 10/17, 10/21, 10/22)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 51 | 17 | $102.00 | $95.60 | -6.3% |
| Exacta box 2 | 51 | 12 | $102.00 | $166.00 | **+62.7%** |
| Trifecta box 3 | 51 | 1 | $153.00 | $16.70 | -89.1% |
| Superfecta box 4 | 49 | 5 | $117.60 | $69.57 | -40.8% |
| Super wheel 3/3/3/ALL | 51 | 1 | $172.80 | $8.67 | -95.0% |
| Pick 3 (a) top 1 | 39 | 1 | $19.50 | $6.35 | -67.4% |
| Pick 3 (b) top 2 | 39 | 5 | $156.00 | $117.30 | -24.8% |
| Pick 4 (a) top 1 | 12 | 0 | $6.00 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 12 | 1 | $96.00 | $205.15 | **+113.7%** |
| Pick 5 (a) top 1 | 12 | 0 | $6.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 12 | 1 | $192.00 | $328.80 | **+71.2%** |
| **all** | 379 | 44 | $1,122.90 | $1,014.14 | -9.7% |

### Doug (2 cards: 10/21, 10/22)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 16 | 5 | $32.00 | $28.00 | -12.5% |
| Exacta box 2 | 15 | 1 | $30.00 | $12.00 | -60.0% |
| Trifecta box 3 | 15 | 0 | $45.00 | $0.00 | -100.0% |
| Superfecta box 4 | 12 | 1 | $28.80 | $18.08 | -37.2% |
| Super wheel 3/3/3/ALL | 15 | 0 | $46.20 | $0.00 | -100.0% |
| Pick 3 (a) top 1 | 12 | 0 | $6.00 | $0.00 | -100.0% |
| Pick 3 (b) top 2 | 12 | 1 | $42.00 | $17.50 | -58.3% |
| Pick 4 (a) top 1 | 4 | 0 | $2.00 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 4 | 0 | $24.00 | $0.00 | -100.0% |
| Pick 5 (a) top 1 | 4 | 0 | $2.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 4 | 0 | $48.00 | $0.00 | -100.0% |
| **all** | 113 | 8 | $306.00 | $75.58 | -75.3% |

## Head to head on the same cards

### Model vs Don, 10/14–10/22 (6 cards)

| bet | Model hits | Model ROI | Don hits | Don ROI |
|---|---|---|---|---|
| Win | 14/51 | -5.7% | 17/51 | -6.3% |
| Exacta box 2 | 4/51 | -57.3% | 12/51 | +62.7% |
| Trifecta box 3 | 3/51 | -65.3% | 1/51 | -89.1% |
| Superfecta box 4 | 1/51 | -99.2% | 5/49 | -40.8% |
| Super wheel 3/3/3/ALL | 3/51 | -64.1% | 1/51 | -95.0% |
| Pick 3 (a) top 1 | 0/39 | -100.0% | 1/39 | -67.4% |
| Pick 3 (b) top 2 | 3/39 | -16.7% | 5/39 | -24.8% |
| Pick 4 (a) top 1 | 0/12 | -100.0% | 0/12 | -100.0% |
| Pick 4 (b) top 2 | 0/12 | -100.0% | 1/12 | +113.7% |
| Pick 5 (a) top 1 | 0/12 | -100.0% | 0/12 | -100.0% |
| Pick 5 (b) top 2 | 0/12 | -100.0% | 1/12 | +71.2% |
| **all** | $1,128 → $386 | -65.8% | $1,123 → $1,014 | -9.7% |

### All three, 10/21–10/22 (2 cards)

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 3/16 | -53.8% | 5/16 | -15.0% | 5/16 | -12.5% |
| Exacta box 2 | 1/16 | -77.8% | 5/16 | +131.2% | 1/15 | -60.0% |
| Trifecta box 3 | 2/16 | -29.5% | 0/16 | -100.0% | 0/15 | -100.0% |
| Superfecta box 4 | 0/16 | -100.0% | 3/15 | +59.3% | 1/12 | -37.2% |
| Super wheel 3/3/3/ALL | 2/16 | +8.7% | 0/16 | -100.0% | 0/15 | -100.0% |
| Pick 3 (a) top 1 | 0/12 | -100.0% | 0/12 | -100.0% | 0/12 | -100.0% |
| Pick 3 (b) top 2 | 0/12 | -100.0% | 3/12 | +92.6% | 1/12 | -58.3% |
| Pick 4 (a) top 1 | 0/4 | -100.0% | 0/4 | -100.0% | 0/4 | -100.0% |
| Pick 4 (b) top 2 | 0/4 | -100.0% | 1/4 | +541.1% | 0/4 | -100.0% |
| Pick 5 (a) top 1 | 0/4 | -100.0% | 0/4 | -100.0% | 0/4 | -100.0% |
| Pick 5 (b) top 2 | 0/4 | -100.0% | 1/4 | +413.8% | 0/4 | -100.0% |
| **all** | $352 → $108 | -69.4% | $350 → $785 | +124.3% | $306 → $76 | -75.3% |

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
