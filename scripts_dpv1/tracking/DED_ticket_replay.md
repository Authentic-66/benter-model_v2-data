# DED meet ticket replay — model, Don, Doug (through 2026-10-24)

> **⚠ Read this before choosing a bet from these tables.** Every number
> here is in-sample: the results were known when the bets were compared.
> Any strategy picked *because* it looks good below (for example "box Don's
> top two" or "the model's top-two Pick 3") has to be tested on **future
> cards, decided in advance**, before it is trusted with money. With 32–78
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
10/24 card: **34 rows added, all 204 earlier rows unchanged.** Sample now:
9 cards / 78 races for the model, 8 / 69 for Don, 4 / 32 for Doug.

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
  #3 was scratched, leaving him 3 picks (no super box there).
* **Doug's best guesses** (`doug_picks.csv` `best_guess = 1`: 10/24 R3, R5,
  R9, maiden races picked from breeding and jockey) are placed like any
  other race. The 10/24 review gives his record with and without them.

## Caveats

* **Small samples.** 78 races for the model, 69 for Don, 32 for Doug. One
  ticket moves the ROI by tens of points: Don's Pick 4 (b) and Pick 5 (b)
  return is three tickets ($205.15 + $328.80 on 10/22, $141.00 on 10/23).
  Without those two lines Don's total is $628.34 back on $1,123.90 (−44.1%).
* **Not like for like on timing.** Doug picks on race day with scratches and
  odds known. Don's and the model's picks are made before scratches, and the
  re-rank here then gives them the benefit of knowing the scratches too.
* **Model record runs:** 10/10 and 10/14 were logged before the 10/15 PP
  fixes; 10/14 R1–R4 were logged after post. 1.3.0 ran 10/10–10/17, 1.3.1
  10/21, 1.3.2 10/22–10/24.
* Rankings are by P(ITM), not P(win): the win bet is the P(ITM) #1. Since
  2026-10-23 the model also has a **Win (top P(win))** line (see below). It is
  an alternative to the Win line, not an extra bet, so it is left out of the
  model's "all" totals.
* The 10/22 late Pick 4/5 rows exist only since the parser fix (`1c9fe65`).
* 10/23 Pick 4 (R2–R5) paid through a scratch substitute: the R4 leg is
  `1/3` (#3 D'busker scratched, the substitute #1 won). A ticket with #3 in
  R4 counts as hitting that leg.

## By source (each over its own cards)

### Model (9 cards: 10/10, 10/14, 10/15, 10/16, 10/17, 10/21, 10/22, 10/23, 10/24)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 78 | 19 | $156.00 | $120.60 | -22.7% |
| Win (top P(win)) *alt* | 78 | 20 | $156.00 | $126.60 | -18.8% |
| Exacta box 2 | 78 | 7 | $156.00 | $98.90 | -36.6% |
| Trifecta box 3 | 78 | 5 | $234.00 | $90.75 | -61.2% |
| Superfecta box 4 | 78 | 5 | $187.20 | $68.91 | -63.2% |
| Super wheel 3/3/3/ALL | 78 | 5 | $257.40 | $81.56 | -68.3% |
| Pick 3 (a) top 1 | 60 | 0 | $30.00 | $0.00 | -100.0% |
| Pick 3 (b) top 2 | 60 | 3 | $240.00 | $129.95 | -45.9% |
| Pick 4 (a) top 1 | 18 | 0 | $9.00 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 18 | 0 | $144.00 | $0.00 | -100.0% |
| Pick 5 (a) top 1 | 18 | 0 | $9.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 18 | 0 | $288.00 | $0.00 | -100.0% |
| **all** | 582 | 44 | $1,710.60 | $590.67 | -65.5% |

### Don (8 cards: 10/14, 10/15, 10/16, 10/17, 10/21, 10/22, 10/23, 10/24)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 69 | 20 | $138.00 | $113.20 | -18.0% |
| Exacta box 2 | 69 | 14 | $138.00 | $187.20 | **+35.7%** |
| Trifecta box 3 | 69 | 2 | $207.00 | $28.05 | -86.4% |
| Superfecta box 4 | 66 | 7 | $158.40 | $83.61 | -47.2% |
| Super wheel 3/3/3/ALL | 69 | 2 | $228.00 | $15.33 | -93.3% |
| Pick 3 (a) top 1 | 53 | 1 | $26.50 | $6.35 | -76.0% |
| Pick 3 (b) top 2 | 53 | 7 | $212.00 | $194.60 | -8.2% |
| Pick 4 (a) top 1 | 16 | 0 | $8.00 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 16 | 2 | $128.00 | $346.15 | **+170.4%** |
| Pick 5 (a) top 1 | 16 | 0 | $8.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 16 | 1 | $256.00 | $328.80 | **+28.4%** |
| **all** | 512 | 56 | $1,507.90 | $1,303.29 | -13.6% |

### Doug (4 cards: 10/21, 10/22, 10/23, 10/24)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 32 | 10 | $64.00 | $61.80 | -3.4% |
| Exacta box 2 | 31 | 3 | $62.00 | $42.00 | -32.3% |
| Trifecta box 3 | 31 | 2 | $93.00 | $55.45 | -40.4% |
| Superfecta box 4 | 26 | 3 | $62.40 | $48.34 | -22.5% |
| Super wheel 3/3/3/ALL | 31 | 2 | $96.60 | $33.92 | -64.9% |
| Pick 3 (a) top 1 | 21 | 0 | $10.50 | $0.00 | -100.0% |
| Pick 3 (b) top 2 | 21 | 2 | $78.00 | $57.95 | -25.7% |
| Pick 4 (a) top 1 | 7 | 0 | $3.50 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 7 | 0 | $48.00 | $0.00 | -100.0% |
| Pick 5 (a) top 1 | 6 | 0 | $3.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 6 | 0 | $80.00 | $0.00 | -100.0% |
| **all** | 219 | 22 | $601.00 | $299.46 | -50.2% |

## Win bet: top P(ITM) vs top P(win) (model, added 2026-10-23)

The model's top P(win) horse was the same as its top P(ITM) horse in **77 of
78 races**. The only difference was 10/15 R4: #3 Piastri P(ITM) 45.5% / P(win)
15.8% vs #6 Easy Like Breezy 45.2% / 15.9%. Easy Like Breezy won ($6.00),
Piastri ran 2nd. That one race is still the whole gap (+1 hit, +$6.00;
−22.7% → −18.8% on 78 bets).

So the replay does **not** show that betting the most likely winner beats
betting the top P(ITM): the two are nearly always the same horse, because
P(win) and P(ITM) come out of the same model and rank almost identically. One
race separated by 0.1pp of P(win) is a coin flip, not evidence. (DED 10/23:
the same horse led both in all 9 races, and none of the 9 won. DED 10/24:
the same in all 9 again; one won.)

## Head to head on the same cards

### Model vs Don, 10/14–10/24 (8 cards)

| bet | Model hits | Model ROI | Don hits | Don ROI |
|---|---|---|---|---|
| Win | 15/69 | -27.0% | 20/69 | -18.0% |
| Exacta box 2 | 5/69 | -52.3% | 14/69 | **+35.7%** |
| Trifecta box 3 | 5/69 | -56.2% | 2/69 | -86.4% |
| Superfecta box 4 | 4/69 | -64.0% | 7/66 | -47.2% |
| Super wheel 3/3/3/ALL | 5/69 | -64.2% | 2/69 | -93.3% |
| Pick 3 (a) top 1 | 0/53 | -100.0% | 1/53 | -76.0% |
| Pick 3 (b) top 2 | 3/53 | -38.7% | 7/53 | -8.2% |
| Pick 4 (a) top 1 | 0/16 | -100.0% | 0/16 | -100.0% |
| Pick 4 (b) top 2 | 0/16 | -100.0% | 2/16 | **+170.4%** |
| Pick 5 (a) top 1 | 0/16 | -100.0% | 0/16 | -100.0% |
| Pick 5 (b) top 2 | 0/16 | -100.0% | 1/16 | **+28.4%** |
| **all** | $1,515 → $528 | -65.1% | $1,508 → $1,303 | -13.6% |

### All three, 10/21–10/24 (4 cards)

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 4/34 | -71.5% | 8/34 | -34.1% | 10/32 | -3.4% |
| Exacta box 2 | 2/34 | -56.9% | 7/34 | **+40.0%** | 3/31 | -32.3% |
| Trifecta box 3 | 4/34 | -29.9% | 1/34 | -88.9% | 2/31 | -40.4% |
| Superfecta box 4 | 3/34 | -28.1% | 5/32 | -7.1% | 3/26 | -22.5% |
| Super wheel 3/3/3/ALL | 4/34 | -30.5% | 1/34 | -93.5% | 2/31 | -64.9% |
| Pick 3 (a) top 1 | 0/26 | -100.0% | 0/26 | -100.0% | 0/21 | -100.0% |
| Pick 3 (b) top 2 | 0/26 | -100.0% | 5/26 | **+63.2%** | 2/21 | -25.7% |
| Pick 4 (a) top 1 | 0/8 | -100.0% | 0/8 | -100.0% | 0/7 | -100.0% |
| Pick 4 (b) top 2 | 0/8 | -100.0% | 2/8 | **+440.9%** | 0/7 | -100.0% |
| Pick 5 (a) top 1 | 0/8 | -100.0% | 0/8 | -100.0% | 0/6 | -100.0% |
| Pick 5 (b) top 2 | 0/8 | -100.0% | 1/8 | **+156.9%** | 0/6 | -100.0% |
| **all** | $740 → $251 | -66.1% | $735 → $1,074 | **+46.1%** | $601 → $299 | -50.2% |

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
Model races 78 cards 9
Don races 69 cards 8
Doug races 32 cards 4
