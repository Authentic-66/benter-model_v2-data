# DED meet ticket replay — model, Don, Doug (through 2026-10-23)

> **⚠ Read this before choosing a bet from these tables.** Every number
> here is in-sample: the results were known when the bets were compared.
> Any strategy picked *because* it looks good below (for example "box Don's
> top two" or "the model's top-two Pick 3") has to be tested on **future
> cards, decided in advance**, before it is trusted with money. With 23–69
> races per source, one ticket can swing an ROI by tens of points, and
> picking the best of 11 bet types × 3 sources after the fact will find a
> "winner" by chance alone.

`tracking/ticket_replay.py` → `tracking/ticket_replay.csv` (one row per
source × card × bet). Re-run it after each card; it picks up every logged
DED card with results. Re-run 2026-10-22 (evening) after the corpus Pick backfill:
identical (the meet cards had been backfilled earlier the same day).
Re-run 2026-10-23 with a new model line, **Win (top P(win))**: all 165 earlier
rows unchanged. **Re-run 2026-10-23 (evening) with the 10/23 card: 32 rows
added, all earlier rows unchanged.** Sample now: 8 cards / 69 races for the
model, 7 / 60 for Don, 3 / 23 for Doug.

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
  any Pick 3/4/5 with a PASS leg is not placed for him.

## Caveats

* **Small samples.** 69 races for the model, 60 for Don, 23 for Doug. One
  ticket moves the ROI by tens of points: Don's Pick 4 (b) and Pick 5 (b)
  return is three tickets ($205.15 + $328.80 on 10/22, $141.00 on 10/23).
  Without those two lines Don's total is $623.74 back on $979.40 (−36.3%).
* **Not like for like on timing.** Doug picks on race day with scratches and
  odds known. Don's and the model's picks are made before scratches, and the
  re-rank here then gives them the benefit of knowing the scratches too.
* **Model record runs:** 10/10 and 10/14 were logged before the 10/15 PP
  fixes; 10/14 R1–R4 were logged after post. 1.3.0 ran 10/10–10/17, 1.3.1
  10/21, 1.3.2 10/22–10/23.
* Rankings are by P(ITM), not P(win): the win bet is the P(ITM) #1. Since
  2026-10-23 the model also has a **Win (top P(win))** line (see below). It is
  an alternative to the Win line, not an extra bet, so it is left out of the
  model's "all" totals.
* The 10/22 late Pick 4/5 rows exist only since the parser fix (`1c9fe65`).
* 10/23 Pick 4 (R2–R5) paid through a scratch substitute: the R4 leg is
  `1/3` (#3 D'busker scratched, the substitute #1 won). A ticket with #3 in
  R4 counts as hitting that leg.

## By source (each over its own cards)

### Model (8 cards: 10/10, 10/14, 10/15, 10/16, 10/17, 10/21, 10/22, 10/23)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 69 | 18 | $138.00 | $116.00 | -15.9% |
| Win (top P(win)) *alt* | 69 | 19 | $138.00 | $122.00 | -11.6% |
| Exacta box 2 | 69 | 6 | $138.00 | $76.70 | -44.4% |
| Trifecta box 3 | 69 | 4 | $207.00 | $65.55 | -68.3% |
| Superfecta box 4 | 69 | 3 | $165.60 | $16.94 | -89.8% |
| Super wheel 3/3/3/ALL | 69 | 4 | $231.00 | $69.42 | -69.9% |
| Pick 3 (a) top 1 | 53 | 0 | $26.50 | $0.00 | -100.0% |
| Pick 3 (b) top 2 | 53 | 3 | $212.00 | $129.95 | -38.7% |
| Pick 4 (a) top 1 | 16 | 0 | $8.00 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 16 | 0 | $128.00 | $0.00 | -100.0% |
| Pick 5 (a) top 1 | 16 | 0 | $8.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 16 | 0 | $256.00 | $0.00 | -100.0% |
| **all** | 515 | 38 | $1,518.10 | $474.56 | -68.7% |

### Don (7 cards: 10/14, 10/15, 10/16, 10/17, 10/21, 10/22, 10/23)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 60 | 19 | $120.00 | $108.60 | -9.5% |
| Exacta box 2 | 60 | 14 | $120.00 | $187.20 | **+56.0%** |
| Trifecta box 3 | 60 | 2 | $180.00 | $28.05 | -84.4% |
| Superfecta box 4 | 57 | 7 | $136.80 | $83.61 | -38.9% |
| Super wheel 3/3/3/ALL | 60 | 2 | $201.60 | $15.33 | -92.4% |
| Pick 3 (a) top 1 | 46 | 1 | $23.00 | $6.35 | -72.4% |
| Pick 3 (b) top 2 | 46 | 7 | $184.00 | $194.60 | **+5.8%** |
| Pick 4 (a) top 1 | 14 | 0 | $7.00 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 14 | 2 | $112.00 | $346.15 | **+209.1%** |
| Pick 5 (a) top 1 | 14 | 0 | $7.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 14 | 1 | $224.00 | $328.80 | **+46.8%** |
| **all** | 445 | 55 | $1,315.40 | $1,298.69 | -1.3% |

### Doug (3 cards: 10/21, 10/22, 10/23)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 23 | 7 | $46.00 | $39.80 | -13.5% |
| Exacta box 2 | 22 | 2 | $44.00 | $22.90 | -48.0% |
| Trifecta box 3 | 22 | 0 | $66.00 | $0.00 | -100.0% |
| Superfecta box 4 | 18 | 2 | $43.20 | $36.20 | -16.2% |
| Super wheel 3/3/3/ALL | 22 | 0 | $70.20 | $0.00 | -100.0% |
| Pick 3 (a) top 1 | 14 | 0 | $7.00 | $0.00 | -100.0% |
| Pick 3 (b) top 2 | 14 | 1 | $50.00 | $17.50 | -65.0% |
| Pick 4 (a) top 1 | 5 | 0 | $2.50 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 5 | 0 | $32.00 | $0.00 | -100.0% |
| Pick 5 (a) top 1 | 4 | 0 | $2.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 4 | 0 | $48.00 | $0.00 | -100.0% |
| **all** | 153 | 12 | $410.90 | $116.40 | -71.7% |

## Win bet: top P(ITM) vs top P(win) (model, added 2026-10-23)

The model's top P(win) horse was the same as its top P(ITM) horse in **68 of
69 races**. The only difference was 10/15 R4: #3 Piastri P(ITM) 45.5% / P(win)
15.8% vs #6 Easy Like Breezy 45.2% / 15.9%. Easy Like Breezy won ($6.00),
Piastri ran 2nd. That one race is still the whole gap (+1 hit, +$6.00;
−15.9% → −11.6% on 69 bets).

So the replay does **not** show that betting the most likely winner beats
betting the top P(ITM): the two are nearly always the same horse, because
P(win) and P(ITM) come out of the same model and rank almost identically. One
race separated by 0.1pp of P(win) is a coin flip, not evidence. (DED 10/23:
the same horse led both in all 9 races, and none of the 9 won.)

## Head to head on the same cards

### Model vs Don, 10/14–10/23 (7 cards)

| bet | Model hits | Model ROI | Don hits | Don ROI |
|---|---|---|---|---|
| Win | 14/60 | -19.8% | 19/60 | -9.5% |
| Exacta box 2 | 4/60 | -63.7% | 14/60 | **+56.0%** |
| Trifecta box 3 | 4/60 | -63.6% | 2/60 | -84.4% |
| Superfecta box 4 | 2/60 | -94.7% | 7/57 | -38.9% |
| Super wheel 3/3/3/ALL | 4/60 | -65.6% | 2/60 | -92.4% |
| Pick 3 (a) top 1 | 0/46 | -100.0% | 1/46 | -72.4% |
| Pick 3 (b) top 2 | 3/46 | -29.4% | 7/46 | **+5.8%** |
| Pick 4 (a) top 1 | 0/14 | -100.0% | 0/14 | -100.0% |
| Pick 4 (b) top 2 | 0/14 | -100.0% | 2/14 | **+209.1%** |
| Pick 5 (a) top 1 | 0/14 | -100.0% | 0/14 | -100.0% |
| Pick 5 (b) top 2 | 0/14 | -100.0% | 1/14 | **+46.8%** |
| **all** | $1,323 → $412 | -68.8% | $1,315 → $1,299 | -1.3% |

### All three, 10/21–10/23 (3 cards)

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 3/25 | -70.4% | 7/25 | -19.6% | 7/23 | -13.5% |
| Exacta box 2 | 1/25 | -85.8% | 7/25 | **+90.4%** | 2/22 | -48.0% |
| Trifecta box 3 | 3/25 | -38.3% | 1/25 | -84.9% | 0/22 | -100.0% |
| Superfecta box 4 | 1/25 | -88.9% | 5/23 | **+29.3%** | 2/18 | -16.2% |
| Super wheel 3/3/3/ALL | 3/25 | -22.4% | 1/25 | -91.3% | 0/22 | -100.0% |
| Pick 3 (a) top 1 | 0/19 | -100.0% | 0/19 | -100.0% | 0/14 | -100.0% |
| Pick 3 (b) top 2 | 0/19 | -100.0% | 5/19 | **+123.4%** | 1/14 | -65.0% |
| Pick 4 (a) top 1 | 0/6 | -100.0% | 0/6 | -100.0% | 0/5 | -100.0% |
| Pick 4 (b) top 2 | 0/6 | -100.0% | 2/6 | **+621.1%** | 0/5 | -100.0% |
| Pick 5 (a) top 1 | 0/6 | -100.0% | 0/6 | -100.0% | 0/4 | -100.0% |
| Pick 5 (b) top 2 | 0/6 | -100.0% | 1/6 | **+242.5%** | 0/4 | -100.0% |
| **all** | $547 → $134 | -75.4% | $542 → $1,069 | **+97.1%** | $411 → $116 | -71.7% |

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

