# DED meet ticket replay — model, Don, Doug (through 2026-11-18)

> **⚠ Read this before choosing a bet from these tables.** Every number
> here is in-sample: the results were known when the bets were compared.
> Any strategy picked *because* it looks good below (for example "box Don's
> top two" or "the model's top-two Pick 3") has to be tested on **future
> cards, decided in advance**, before it is trusted with money. With 127–180
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
unchanged.** Re-run 2026-10-30 (night) with the 10/30 card: **34 rows added,
all 306 earlier rows unchanged.** Re-run 2026-11-04 (night) with the 11/04
card: **34 rows added, all 340 earlier rows unchanged.** Re-run 2026-11-06 with
the 11/05 card: **34 rows added, all 374 earlier rows unchanged.** Re-run
2026-11-06 (night) with the 11/06 card: **34 rows added, all 408 earlier rows
unchanged.** Re-run 2026-11-07 (night) with the 11/07 card: **34 rows added, all
443 earlier rows unchanged.** Re-run 2026-11-12 (morning) with the 11/11 card:
**34 rows added, all 476 earlier rows unchanged.** Re-run 2026-11-13 (morning)
with the 11/12 card: **34 rows added, all 510 earlier rows unchanged.** (The
11/07 and 11/11 notes said 443 and 477 earlier rows; the true counts were 442
and 476, off by one.) Re-run 2026-11-14 (morning) with the 11/13 card: **23
rows added (model 12, Doug 11; Don sent no picks for 11/13, logged as missing
and skipped), all 544 earlier rows unchanged.** Re-run 2026-11-14 with **Don's 11/13
picks** (posted on X after the results, counted as pre-race on Doug's
confirmation): **11 Don rows added, all 567 earlier rows unchanged.** Re-run
2026-11-15 with the 11/14 card: **34 rows added (model 12, Don 11, Doug 11),
all 578 earlier rows unchanged.** Re-run 2026-11-19 with the 11/18 card: **23
rows added (model 12, Don 11; Doug did not handicap 11/18, logged as missing
and skipped), all 612 earlier rows unchanged.** 11/18 R6 was cancelled, so
the card has 7 races, and the Pick 3/4/5 pools with an `ALL` R6 leg are not
graded. Sample now: 21 cards / 180 races for the model, 20 / 171 for Don,
15 / 127 for Doug. (Don's 11/04
picks arrived after R1 had run; R1 is graded for him anyway.)

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
  fewer legs (10/22's early Pick 5, 4 of 5; 10/30's early Pick 4, 3 of 4,
  and early Pick 5, 4 of 5) pays any combo with that many right.
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
  (7-9), and he gave 3 picks in R7. On 10/30 he gave 3 picks in R6, and his
  R7 #4 pick (#9 Fiesty Fist, late vet scratch) left him 3 there.
* **Doug's best guesses** (`doug_picks.csv` `best_guess = 1`: 10/24 R3, R5,
  R9, maiden races picked from breeding and jockey) are placed like any
  other race. The 10/24 review gives his record with and without them.

## Caveats

* **Small samples.** 180 races for the model, 171 for Don, 127 for Doug. One
  ticket moves the ROI by tens of points: Don's Pick 4 (b) and Pick 5 (b)
  return is eight tickets ($205.15 + $328.80 on 10/22, $141.00 on 10/23,
  $178.60 on 11/11; on 11/12 both Pick 4s, $27.15 + $15.45, and both Pick 5s,
  $51.90 + $68.10). Without those two lines Don's total is $2,276.93 back on
  $2,740.50 (−16.9%).
  (Don's own LP4 ticket hit on 10/29 for $150.15; his real tickets are graded
  in the card reviews, not here.)
* **Not like for like on timing.** Doug picks on race day with scratches and
  odds known. Don's and the model's picks are made before scratches, and the
  re-rank here then gives them the benefit of knowing the scratches too.
* **Model record runs:** 10/10 and 10/14 were logged before the 10/15 PP
  fixes; 10/14 R1–R4 were logged after post. 1.3.0 ran 10/10–10/17, 1.3.1
  10/21, 1.3.2 10/22–11/18 (name matching ON from 11/05).
* Rankings are by P(ITM), not P(win): the win bet is the P(ITM) #1. Since
  2026-10-23 the model also has a **Win (top P(win))** line (see below). It is
  an alternative to the Win line, not an extra bet, so it is left out of the
  model's "all" totals.
* The 10/22 late Pick 4/5 rows exist only since the parser fix (`1c9fe65`).
* 10/23 Pick 4 (R2–R5) paid through a scratch substitute: the R4 leg is
  `1/3` (#3 D'busker scratched, the substitute #1 won). A ticket with #3 in
  R4 counts as hitting that leg.

## By source (each over its own cards)

### Model (21 cards: 10/10, 10/14, 10/15, 10/16, 10/17, 10/21, 10/22, 10/23, 10/24, 10/28, 10/29, 10/30, 11/4, 11/5, 11/6, 11/7, 11/11, 11/12, 11/13, 11/14, 11/18)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 180 | 47 | $360.00 | $273.20 | -24.1% |
| Win (top P(win)) *alt* | 180 | 48 | $360.00 | $279.20 | -22.4% |
| Exacta box 2 | 180 | 16 | $360.00 | $171.60 | -52.3% |
| Trifecta box 3 | 180 | 12 | $540.00 | $195.60 | -63.8% |
| Superfecta box 4 | 180 | 12 | $432.00 | $253.38 | -41.3% |
| Super wheel 3/3/3/ALL | 180 | 12 | $586.20 | $183.32 | -68.7% |
| Pick 3 (a) top 1 | 136 | 1 | $68.00 | $4.85 | -92.9% |
| Pick 3 (b) top 2 | 136 | 8 | $544.00 | $351.45 | -35.4% |
| Pick 4 (a) top 1 | 41 | 0 | $20.50 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 41 | 1 | $328.00 | $117.05 | -64.3% |
| Pick 5 (a) top 1 | 41 | 0 | $20.50 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 41 | 1 | $656.00 | $205.40 | -68.7% |
| **all** | 1336 | 110 | $3,915.20 | $1,755.85 | -55.2% |

### Don (20 cards: 10/14, 10/15, 10/16, 10/17, 10/21, 10/22, 10/23, 10/24, 10/28, 10/29, 10/30, 11/4, 11/5, 11/6, 11/7, 11/11, 11/12, 11/13, 11/14, 11/18)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 171 | 54 | $342.00 | $306.80 | -10.3% |
| Exacta box 2 | 171 | 31 | $342.00 | $381.10 | **+11.4%** |
| Trifecta box 3 | 171 | 18 | $513.00 | $412.65 | -19.6% |
| Superfecta box 4 | 153 | 15 | $367.20 | $311.58 | -15.1% |
| Super wheel 3/3/3/ALL | 171 | 18 | $556.80 | $374.80 | -32.7% |
| Pick 3 (a) top 1 | 129 | 3 | $64.50 | $21.05 | -67.4% |
| Pick 3 (b) top 2 | 129 | 19 | $516.00 | $468.95 | -9.1% |
| Pick 4 (a) top 1 | 39 | 0 | $19.50 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 39 | 5 | $312.00 | $567.35 | **+81.8%** |
| Pick 5 (a) top 1 | 39 | 0 | $19.50 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 39 | 3 | $624.00 | $448.80 | -28.1% |
| **all** | 1251 | 166 | $3,676.50 | $3,293.08 | -10.4% |

### Doug (15 cards: 10/21, 10/22, 10/23, 10/24, 10/28, 10/29, 10/30, 11/4, 11/5, 11/6, 11/7, 11/11, 11/12, 11/13, 11/14)

| bet | tickets | hits | cost | return | ROI |
|---|---|---|---|---|---|
| Win | 127 | 39 | $254.00 | $220.20 | -13.3% |
| Exacta box 2 | 126 | 19 | $252.00 | $258.50 | **+2.6%** |
| Trifecta box 3 | 123 | 8 | $369.00 | $171.95 | -53.4% |
| Superfecta box 4 | 104 | 7 | $249.60 | $181.19 | -27.4% |
| Super wheel 3/3/3/ALL | 123 | 8 | $394.80 | $161.72 | -59.0% |
| Pick 3 (a) top 1 | 94 | 3 | $47.00 | $25.90 | -44.9% |
| Pick 3 (b) top 2 | 94 | 11 | $370.00 | $268.90 | -27.3% |
| Pick 4 (a) top 1 | 29 | 0 | $14.50 | $0.00 | -100.0% |
| Pick 4 (b) top 2 | 29 | 0 | $224.00 | $0.00 | -100.0% |
| Pick 5 (a) top 1 | 28 | 0 | $14.00 | $0.00 | -100.0% |
| Pick 5 (b) top 2 | 28 | 0 | $432.00 | $0.00 | -100.0% |
| **all** | 905 | 95 | $2,620.90 | $1,288.36 | -50.8% |

## Win bet: top P(ITM) vs top P(win) (model, added 2026-10-23)

The model's top P(win) horse was the same as its top P(ITM) horse in **177 of
180 races** (11/18: all 7 the same). The three differences:

* 10/15 R4: #3 Piastri P(ITM) 45.5% / P(win) 15.8% vs #6 Easy Like Breezy
  45.2% / 15.9%. Easy Like Breezy won ($6.00), Piastri ran 2nd.
* 10/28 R4 (after the model's #1, #4 Clearly Colossal, was scratched): #3
  Z's Guitar P(ITM) 44.4% / P(win) 15.0% vs #9 All West 44.3% / 15.4%.
  All West ran 5th, Z's Guitar 7th; neither won.
* 11/11 R1: #7 Severus Squall P(ITM) 58.4% / P(win) 21.8% vs #1 Daat 58.3% /
  22.2%. Severus Squall ran 2nd, Daat 9th; neither won.

10/15 R4 is still the whole gap (+1 hit, +$6.00; −24.1% → −22.4% on 180 bets).

So the replay does **not** show that betting the most likely winner beats
betting the top P(ITM): the two are nearly always the same horse, because
P(win) and P(ITM) come out of the same model and rank almost identically. A
race separated by 0.1–0.4pp of P(win) is a coin flip, not evidence.

## Head to head on the same cards

### Model vs Don, 10/14–11/18 (20 cards)

| bet | Model hits | Model ROI | Don hits | Don ROI |
|---|---|---|---|---|
| Win | 43/171 | -25.9% | 54/171 | -10.3% |
| Exacta box 2 | 14/171 | -59.5% | 31/171 | **+11.4%** |
| Trifecta box 3 | 12/171 | -61.9% | 18/171 | -19.6% |
| Superfecta box 4 | 11/171 | -40.5% | 15/153 | -15.1% |
| Super wheel 3/3/3/ALL | 12/171 | -67.1% | 18/171 | -32.7% |
| Pick 3 (a) top 1 | 1/129 | -92.5% | 3/129 | -67.4% |
| Pick 3 (b) top 2 | 8/129 | -31.9% | 19/129 | -9.1% |
| Pick 4 (a) top 1 | 0/39 | -100.0% | 0/39 | -100.0% |
| Pick 4 (b) top 2 | 1/39 | -62.5% | 5/39 | **+81.8%** |
| Pick 5 (a) top 1 | 0/39 | -100.0% | 0/39 | -100.0% |
| Pick 5 (b) top 2 | 1/39 | -67.1% | 3/39 | -28.1% |
| **all** | $3,720 → $1,694 | -54.5% | $3,676 → $3,293 | -10.4% |

### All three, 10/21–11/14 (15 cards)

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 31/129 | -34.8% | 40/129 | -10.5% | 39/127 | -13.3% |
| Exacta box 2 | 10/129 | -62.0% | 23/129 | **+10.5%** | 19/126 | **+2.6%** |
| Trifecta box 3 | 11/129 | -54.4% | 16/129 | **+0.5%** | 8/123 | -53.4% |
| Superfecta box 4 | 9/129 | -23.2% | 13/114 | **+9.4%** | 7/104 | -27.4% |
| Super wheel 3/3/3/ALL | 11/129 | -57.6% | 16/129 | -11.8% | 8/123 | -59.0% |
| Pick 3 (a) top 1 | 1/99 | -90.2% | 2/99 | -70.3% | 3/94 | -44.9% |
| Pick 3 (b) top 2 | 5/99 | -44.1% | 17/99 | **+12.1%** | 11/94 | -27.3% |
| Pick 4 (a) top 1 | 0/30 | -100.0% | 0/30 | -100.0% | 0/29 | -100.0% |
| Pick 4 (b) top 2 | 1/30 | -51.2% | 5/30 | **+136.4%** | 0/29 | -100.0% |
| Pick 5 (a) top 1 | 0/30 | -100.0% | 0/30 | -100.0% | 0/28 | -100.0% |
| Pick 5 (b) top 2 | 1/30 | -57.2% | 3/30 | -6.5% | 0/28 | -100.0% |
| **all** | $2,817 → $1,403 | -50.2% | $2,781 → $3,040 | **+9.3%** | $2,621 → $1,288 | -50.8% |

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

### 2026-10-30

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 2/9 | -40.0% | 3/9 | **+14.4%** | 2/9 | -40.0% |
| Exacta box 2 | 0/9 | -100.0% | 1/9 | **+8.3%** | 1/9 | **+8.3%** |
| Trifecta box 3 | 0/9 | -100.0% | 2/9 | **+161.9%** | 0/9 | -100.0% |
| Superfecta box 4 | 0/9 | -100.0% | 0/9 | -100.0% | 0/7 | -100.0% |
| Super wheel 3/3/3/ALL | 0/9 | -100.0% | 2/9 | **+193.8%** | 0/9 | -100.0% |
| Pick 3 (a) top 1 | 0/7 | -100.0% | 0/7 | -100.0% | 0/7 | -100.0% |
| Pick 3 (b) top 2 | 0/7 | -100.0% | 0/7 | -100.0% | 0/7 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $202 → $11 | -94.6% | $202 → $215 | **+6.6%** | $197 → $30 | -84.6% |

* **The model's top two missed the exacta in all 9 races**, R9 included:
  its R9 top two were 5-2 (#2 Kama Can 37.9 vs #10 Captain Junuh 37.7, 0.2pp
  apart). Don's and Doug's R9 top two 5-10 hit ($19.50).
* Don's top three hit the trifecta box and the super wheel in R1 (1-9-6,
  $12.20 / $6.58) and R5 (3-10-1, $58.50 / $97.42); those two races carry his
  +6.6% night.
* The early Pick 4 (R2–R5) and early Pick 5 (R1–R5) paid only to 3 of 4 and
  4 of 5; no source's top two reached that many (Don's had 2 of 4). R2 (#6
  at 27.7-1, model last) and R4 (#5 at 17.4-1) broke them. The R2–R4 Pick 3
  paid only `ALL`-leg two-of-three combos, which no source's top two hit.
* The model's R8 top two (5-4) died at the start: #4 Copy This lost the
  rider.

### 2026-11-04

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 4/8 | **+31.2%** | 3/8 | **+10.0%** | 3/8 | -30.0% |
| Exacta box 2 | 1/8 | -45.6% | 2/8 | **+103.8%** | 0/8 | -100.0% |
| Trifecta box 3 | 1/8 | -34.6% | 3/8 | **+166.9%** | 1/8 | -34.6% |
| Superfecta box 4 | 0/8 | -100.0% | 0/6 | -100.0% | 0/5 | -100.0% |
| Super wheel 3/3/3/ALL | 1/8 | -39.8% | 3/8 | **+151.7%** | 1/8 | -39.8% |
| Pick 3 (a) top 1 | 1/6 | **+61.7%** | 0/6 | -100.0% | 0/6 | -100.0% |
| Pick 3 (b) top 2 | 3/6 | **+279.0%** | 1/6 | -79.8% | 0/6 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 1/2 | **+631.6%** | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 1/2 | **+541.9%** | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $179 → $480 | **+167.8%** | $174 → $187 | **+7.3%** | $172 → $43 | -74.9% |

* **The model's best replay night of the meet** (+167.8%), carried by its
  top two per leg hitting the early Pick 4 (8-4 / 1-9 / 6-3 / 5-1 →
  8-1/2-3-5, $117.05 on $16) and early Pick 5 (with R1 7-1, $205.40 on
  $32), plus 4 #1 winners. Don's real EP4 ticket hit the same $117.05.
* Don's top three hit the trifecta box and super wheel in R1, R2 and R5
  (R1 is after the race; his R5 trio 5-9-1 only formed because his #1 #2
  Grazed was scratched). His top two hit the exacta in R2 (8-5, $10.10)
  and R5 (5-9, $22.50).
* The late Pick 4 ($8,068.25) and late Pick 5 (paid to 4 of 5) died for
  everyone in R7 (#7 at 17.8-1) and R8 (#9 at 24.1-1, the model's last).

### 2026-11-05

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 3/8 | **+20.0%** | 3/8 | **+20.0%** | 1/8 | -28.7% |
| Exacta box 2 | 2/8 | **+83.7%** | 1/8 | -73.1% | 3/8 | **+231.9%** |
| Trifecta box 3 | 0/8 | -100.0% | 1/8 | **+235.0%** | 1/7 | -7.6% |
| Superfecta box 4 | 1/8 | -35.8% | 1/7 | **+283.0%** | 0/6 | -100.0% |
| Super wheel 3/3/3/ALL | 0/8 | -100.0% | 1/8 | **+290.7%** | 1/7 | **+215.4%** |
| Pick 3 (a) top 1 | 0/6 | -100.0% | 0/6 | -100.0% | 0/6 | -100.0% |
| Pick 3 (b) top 2 | 0/6 | -100.0% | 0/6 | -100.0% | 1/6 | -7.5% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $174 → $61 | -65.1% | $172 → $255 | **+48.3%** | $165 → $170 | **+3.4%** |

* **First card with name matching ON** (one card; see the 11/05 review).
* The model's top two hit the exacta in **R5** (2-3, $4.30) and **R7** (1-6
  → 6-1, $25.10), and its top four hit the R8 superfecta box (2-3-6-5 →
  2-5-3-6, $12.32). Its top three missed every trifecta: in R1 its #2 #2
  Josan (bled, pulled up) took a spot, and R7's #3 was #7 I Forgot the Time
  (5th), not #2 Wave Maker (3rd).
* **Don +48.3% on the night**: his top three were the R1 trifecta
  (3-1-4 → 1-4-3, $80.40 tri / $86.74 super wheel) and his top four the R7
  superfecta (1-2-8-6 → 6-1-2-8, $64.35). His real EP4 and LP4 tickets both
  missed (see the review).
* Doug's top two hit the exacta in R2 (2-10 → 10-2, $23.70), R5 (3-2 → 2-3,
  $4.30, after #6 scratched) and R7 (6-1, $25.10); his R7 top three made the
  super wheel ($64.35), and his top two per leg hit the R5–R7 Pick 3 (3-2 /
  2-5 / 6-1 → 2-5-6, $22.20).
* Every early Pick 4/5 (b) ticket died by R3: the model's Pick 5 in R1 (#1
  Zippy Toga at 5.3-1, its 6th), the model's and Don's in R2 (#10
  Quikonthetrigger at 6.3-1; Doug had him 2nd), Doug's in R3 (#5 First Flame
  at 5.8-1). The late Pick 4 (b) died in R6 for the model and Don (#5
  Eskenforaveand Ak at 7.5-1); Doug's (3-2 / 2-5 / 6-1 / 5-1) got through
  three legs and died in R8 (#2 Cassy Cassy). His late Pick 5 died in R4.

### 2026-11-06

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 2/9 | -52.2% | 4/9 | **+6.7%** | 3/9 | -27.8% |
| Exacta box 2 | 1/9 | -59.4% | 1/9 | -49.4% | 0/9 | -100.0% |
| Trifecta box 3 | 2/9 | **+125.7%** | 2/9 | **+43.1%** | 1/9 | **+8.5%** |
| Superfecta box 4 | 1/9 | -70.3% | 3/7 | **+535.5%** | 2/9 | **+32.1%** |
| Super wheel 3/3/3/ALL | 2/9 | **+39.9%** | 2/9 | -28.2% | 1/9 | -49.5% |
| Pick 3 (a) top 1 | 0/7 | -100.0% | 0/7 | -100.0% | 0/7 | -100.0% |
| Pick 3 (b) top 2 | 0/7 | -100.0% | 0/7 | -100.0% | 0/7 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $196 → $125 | -36.1% | $191 → $195 | **+2.1%** | $196 → $86 | -56.2% |

* Second card with name matching ON (see the 11/06 review).
* The model's top three hit the trifecta in **R1** (8-7-6 → 6-7-8, $51.60;
  top-3 wheel $35.56) and **R2** (4-5-1 in order, $9.35), and its top two and
  top four were the R2 exacta ($7.30) and superfecta ($6.41). R2 was the
  only race where all four of its top four ran 1-2-3-4.
* **Don's top four hit the superfecta box three times**: R7 (4-5-8-1 in
  order, $15.14), R8 (5-8-9-1 → 1-8-5-9, $78.24; his 4th pick #1 Heavenly
  Dream won at 16.2-1) and R9 (2-1-7-10 → 1-7-10-2, $13.39). R2 and R4 had
  three picks left after scratches (his R2 #1 #6 late, his R4 #3 in the
  morning), so his super box ran in 7 races.
* Doug's top four hit the R7 and R9 superfecta boxes ($15.14, $13.39) and
  his top three the R7 trifecta ($29.30).
* Every Pick 4/5 (b) ticket missed. Early Pick 5: all three died in R1 (#6
  Sue's Little Zing, 5.2-1). Early Pick 4: the model and Doug died in R3 (#1
  Essential George, the 1.4-1 favourite: the model's 3rd, not on Doug's
  list); Don's got to R4 (#11 Jabran, 12.8-1). Late Pick 4 and Pick 5: all
  three died in R6 (#5 Loudermilk, 3.8-1), except Doug's late Pick 5, which
  died in R5 (#1 Wild Bert).

### 2026-11-07

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 1/9 | -71.1% | 2/9 | -21.1% | 2/9 | +0.0% |
| Exacta box 2 | 0/9 | -100.0% | 0/9 | -100.0% | 2/9 | **+107.2%** |
| Trifecta box 3 | 0/9 | -100.0% | 1/9 | **+87.0%** | 0/8 | -100.0% |
| Superfecta box 4 | 0/9 | -100.0% | 1/6 | **+152.8%** | 1/6 | **+620.5%** |
| Super wheel 3/3/3/ALL | 0/9 | -100.0% | 1/9 | **+26.4%** | 0/8 | -100.0% |
| Pick 3 (a) top 1 | 0/7 | -100.0% | 0/7 | -100.0% | 0/7 | -100.0% |
| Pick 3 (b) top 2 | 0/7 | -100.0% | 0/7 | -100.0% | 1/7 | **+10.5%** |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $195 → $5 | -97.3% | $188 → $138 | -26.7% | $182 → $190 | **+4.2%** |

* Third card with name matching ON (see the 11/07 review). Seven of nine favourites
  lost; the model's only #1 winner was R6 #5 Highland Creek ($5.20).
* **The model hit nothing beyond that win**: no exacta, trifecta, super box
  or wheel. Its top four had three of the first four in R1, R2, R6 and R7,
  but never the top three.
* **Don's top four hit R8** (3-9-1-10 → 1-3-9-10): trifecta box $50.50,
  super box and wheel $36.41. Three races had three picks left after
  scratches (R6 #1, R7 #6, R9 #9), so his super box ran in 6.
* **Doug's top four hit the R1 superfecta box** (5-2-6-10 → 10-5-2-6,
  $103.75), his top two the R2 (8-1, $9.30) and R8 (1-3, $28.00) exactas,
  and his top two the R6–R8 Pick 3 (5-7-1, $30.95). His R2 #1 (#9) and 4th
  (#7) both scratched, leaving two picks there.
* Every Pick 4/5 ticket missed. Early Pick 5 (10-8-8-8-1, $9,595.25): all
  three died in R1 (#10 Midnight Breeze, 4.8-1). Early Pick 4 (8-8-8-1,
  $1,945.35): the model and Don died in R2 (#8 Beamer, the 1.5-1 favourite,
  was neither's top two); Doug's got to R3 (#8 Roadster Runner, 14.4-1).
  Late Pick 4 (5-7-1-2, $638.20): the model and Don died in R7 (#7 Red
  Roadster); Doug's got to R9 (#2 Karsyn's Ocean, 9.0-1). Late Pick 5
  (1-5-7-1-2, $2,817.35): the model and Doug died in R5, Don in R7.

### 2026-11-11

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 4/8 | **+50.0%** | 3/8 | **+65.0%** | 2/8 | -16.2% |
| Exacta box 2 | 0/8 | -100.0% | 3/8 | **+159.4%** | 3/8 | **+63.1%** |
| Trifecta box 3 | 0/8 | -100.0% | 1/8 | -74.8% | 0/8 | -100.0% |
| Superfecta box 4 | 0/8 | -100.0% | 2/8 | -30.5% | 0/6 | -100.0% |
| Super wheel 3/3/3/ALL | 0/8 | -100.0% | 1/8 | -83.8% | 0/8 | -100.0% |
| Pick 3 (a) top 1 | 0/6 | -100.0% | 0/6 | -100.0% | 0/6 | -100.0% |
| Pick 3 (b) top 2 | 0/6 | -100.0% | 3/6 | **+724.4%** | 2/6 | **+362.1%** |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 1/2 | **+1016.2%** | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $179 → $24 | -86.6% | $179 → $468 | **+162.1%** | $174 → $150 | -13.5% |

* Fifth card with name matching ON. The model's #1 won 4 of 8 ($24.00 on $16)
  but **its top two, three and four missed every exotic**: in every race at
  least one of its top three ran out of the money.
* **Don's late Pick 4 (b) ticket hit: $178.60** (R5 9-5, R6 5-6, R7 2-1, R8
  6-4 → 5-5-1-6). His real LP4 ticket (5-6-9 / 1-5-6 / 1-2-3 / 4-6) hit the
  same pool ($178.60 on $27, see the 11/11 review). His R7 second pick #1
  Yockey's Drivethru (5.1-1) carried both; the model had that horse last of
  7.
* Don's top two hit the R1 ($8.00), R2 ($22.00) and R3 ($11.50) exactas, his
  top four the R6 ($9.06) and R8 ($4.29) superfectas, and his top three the
  R8 trifecta ($6.05). Three Pick 3 (b) hits: R1–R3 $64.30, R5–R7 $64.70,
  R6–R8 $68.85.
* Doug's top two hit the R1, R3 and R8 exactas; his Pick 3 (b) hit R3–R5
  ($69.75) and R4–R6 ($41.15). His super box ran in 6 races (R4 #9 and R6 #2
  scratched).
* Every model Pick ticket missed: early Pick 5 died in R1 (#4 He's Readyto
  Win, the model's 3rd), early Pick 4 in R2 (#8 Traitour, 7.1-1, the model's
  9th of 10), late Pick 5 in R4 (#2 Field Study, 3rd) and late Pick 4 in R7
  (#1 Yockey's Drivethru, last of 7).

### 2026-11-12

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 3/8 | -23.8% | 3/8 | -20.0% | 5/8 | **+43.8%** |
| Exacta box 2 | 2/8 | -35.0% | 3/8 | **+50.0%** | 2/8 | -26.2% |
| Trifecta box 3 | 2/8 | -59.6% | 3/8 | **+24.2%** | 0/8 | -100.0% |
| Superfecta box 4 | 2/8 | -46.4% | 1/7 | -57.8% | 1/8 | -97.0% |
| Super wheel 3/3/3/ALL | 2/8 | -71.5% | 3/8 | -28.7% | 0/8 | -100.0% |
| Pick 3 (a) top 1 | 0/6 | -100.0% | 0/6 | -100.0% | 1/6 | **+273.3%** |
| Pick 3 (b) top 2 | 1/6 | -72.3% | 6/6 | **+137.3%** | 3/6 | **+34.2%** |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 2/2 | **+166.2%** | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 2/2 | **+275.0%** | 0/2 | -100.0% |
| **all** | $174 → $55 | -68.1% | $171 → $309 | **+80.1%** | $174 → $79 | -54.7% |

* Sixth card with name matching ON. The model's #1 won 3 of 8 ($12.20 on
  $16) and hit the board in 7. Its top three hit the R3 and R8 trifectas
  ($2.25, $7.45; the same races as its two super-wheel hits), its top four
  the R3 ($0.57) and R4 ($9.72) superfectas, and its top two the R3 ($2.60)
  and R6 ($7.80) exactas. In R2 and R5 the reranker took the #1 off the
  eventual winner (see the 11/12 review).
* **Don's top two hit every Pick (b) ticket**: all six Pick 3s, both Pick 4s
  (early $27.15, late $15.45) and both Pick 5s (early $51.90, late $68.10).
  His real EP4 and LP4 tickets hit the same two Pick 4 pools. His top two
  hit the R2, R3 and R4 exactas and his top three the R2, R6 and R8
  trifectas.
* Doug's #1 won 5 of 8 ($23.00 on $16). His top two hit the R3 and R4
  exactas; his Pick 3 (a) hit R3–R5 ($11.20) and his Pick 3 (b) hit R3–R5,
  R4–R6 ($11.85) and R5–R7 ($9.15).
* The model's Pick 3 (b) hit R1–R3 ($6.65). Every other model Pick ticket
  died in R4 (#2 Luvto Win, 1.6-1 fav, the model's 3rd), R5 (#4 Shred It Up,
  0.9-1 fav, the base #1 that the reranker dropped to 3rd) or R7 (#8 Timeto
  Party, 1.9-1 fav, 4th).

### 2026-11-13

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 2/9 | -45.6% | 2/9 | -35.6% | 4/9 | **+18.9%** |
| Exacta box 2 | 1/9 | -65.6% | 1/9 | -65.6% | 1/9 | -65.6% |
| Trifecta box 3 | 1/9 | -76.3% | 0/9 | -100.0% | 2/9 | **+3.9%** |
| Superfecta box 4 | 0/9 | -100.0% | 0/7 | -100.0% | 0/8 | -100.0% |
| Super wheel 3/3/3/ALL | 1/9 | -70.9% | 0/9 | -100.0% | 2/9 | -15.1% |
| Pick 3 (a) top 1 | 0/7 | -100.0% | 0/7 | -100.0% | 0/7 | -100.0% |
| Pick 3 (b) top 2 | 1/7 | **+342.5%** | 0/7 | -100.0% | 0/7 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $193 → $154 | -20.2% | $188 → $18 | -90.5% | $191 → $79 | -58.8% |

* Seventh card with name matching ON. **Don's picks were posted after the
  results** and added 11/14 on Doug's confirmation (first logged as missing).
  The model's #1 won 2 of 9 ($9.80 on $18) and hit
  the board in 7. Its top two hit the R6 exacta ($6.20) and the R5–R7 Pick 3
  ($123.90: R5 #1 Asaasy, its 2nd at 24.4-1, then R6 and R7); its top three
  hit the R9 trifecta ($6.40). Its early Pick 4 and Pick 5 tickets died in R3
  or earlier (R1 winner #2 Lady Calypso was its 5th, R3 winner #2 Brother Ron
  its 6th); the late ones in R8 (#5 Miss Metoyer, its 7th).
* Doug's #1 won 4 of 9 ($21.40 on $18). His top two hit the R6 exacta
  ($6.20); his top three the R1 ($21.65) and R9 ($6.40) trifectas. He had no
  Pick hits.
* Don's #1 won 2 of 9 (R4 #7 Sounds Like Power $8.00, R9 #9 Vekowin $3.60;
  $11.60 on $18). His top two hit the R6 exacta ($6.20); nothing else. His
  early Pick tickets died in R1 (#2 Lady Calypso, not in his four) or R3 (his
  #1 #6 Heat of Battle unseated his rider), the late ones in R8 (#5 Miss
  Metoyer). R3 and R9 had three picks after the #11 scratches, so no super
  box there.

### 2026-11-14

| bet | Model hits | Model ROI | Don hits | Don ROI | Doug hits | Doug ROI |
|---|---|---|---|---|---|---|
| Win | 2/11 | -46.4% | 1/11 | -64.5% | 0/11 | -100.0% |
| Exacta box 2 | 0/11 | -100.0% | 1/11 | **+41.8%** | 2/11 | **+63.2%** |
| Trifecta box 3 | 0/11 | -100.0% | 0/11 | -100.0% | 0/11 | -100.0% |
| Superfecta box 4 | 1/11 | **+284.2%** | 0/10 | -100.0% | 0/11 | -100.0% |
| Super wheel 3/3/3/ALL | 0/11 | -100.0% | 0/11 | -100.0% | 0/11 | -100.0% |
| Pick 3 (a) top 1 | 0/9 | -100.0% | 0/9 | -100.0% | 0/9 | -100.0% |
| Pick 3 (b) top 2 | 0/9 | -100.0% | 0/9 | -100.0% | 0/9 | -100.0% |
| Pick 4 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 4 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (a) top 1 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| Pick 5 (b) top 2 | 0/2 | -100.0% | 0/2 | -100.0% | 0/2 | -100.0% |
| **all** | $228 → $113 | -50.2% | $225 → $39 | -82.7% | $228 → $36 | -84.2% |

* Eighth card with name matching ON. All three sources sent picks before
  post. Scratches R2 #3, R7 #1 Watering (the model's base #1 and Don's #1;
  Don's R7 has three picks, so no super box there) and R9 #2.
* **The model's top four hit the R1 superfecta box ($101.43 for $0.10):**
  1-4-3-6 against 3-4-6-1, with its #1 Footprint (1.3-1 fav) 4th. Its #1 won
  2 of 11 (R4 Bearcat $4.00, R10 Dromas $7.80; $11.80 on $22). No exacta,
  trifecta or wheel hits. Its Pick 4 and Pick 5 tickets died in R1 (#3 Brock's Boy, its
  3rd), R2 (#4 Creole Lady, its 4th) or R9 (#1 Mr. Brad's Cowboy, its 4th at
  13.7-1); the top two held the winner in R4, R7, R8 and R10 only.
* Don's #1 won 1 of 11 (R7 #6 Madison Rae, $7.80, after his #1 Watering
  scratched). His top two hit the R11 exacta ($31.20).
* Doug's #1 won none of 11. His top two hit the R7 ($9.80) and R8 ($26.10)
  exactas.
* R5 (#3 First Class Harlow, 26.4-1) and R9 (#1 Mr. Brad's Cowboy, 13.7-1,
  over the 0.5-1 favourite Romeo Spikes, everyone's #1) beat all three.

### 2026-11-18

| bet | Model hits | Model ROI | Don hits | Don ROI |
|---|---|---|---|---|
| Win | 1/7 | -72.9% | 2/7 | -45.7% |
| Exacta box 2 | 1/7 | -71.4% | 1/7 | -71.4% |
| Trifecta box 3 | 0/7 | -100.0% | 1/7 | -66.9% |
| Superfecta box 4 | 1/7 | -68.2% | 0/5 | -100.0% |
| Super wheel 3/3/3/ALL | 0/7 | -100.0% | 1/7 | -76.6% |
| Pick 3 (a) top 1 | 0/3 | -100.0% | 0/3 | -100.0% |
| Pick 3 (b) top 2 | 0/3 | -100.0% | 0/3 | -100.0% |
| Pick 4 (a) top 1 | 0/1 | -100.0% | 0/1 | -100.0% |
| Pick 4 (b) top 2 | 0/1 | -100.0% | 0/1 | -100.0% |
| Pick 5 (a) top 1 | 0/1 | -100.0% | 0/1 | -100.0% |
| Pick 5 (b) top 2 | 0/1 | -100.0% | 0/1 | -100.0% |
| **all** | $127 → $13 | -89.7% | $122 → $24 | -80.5% |

* Ninth card with name matching ON. **Doug did not handicap 11/18** (logged as
  missing, no consensus races). Don's picks arrived 4:38 PM, before the
  4:42 first post. **R6 was cancelled** (management decision), so the card
  has 7 graded races; the Pick 3 R5–R7 / R6–R8, the Pick 4 R5–R8 and the
  Pick 5 R4–R8 ran with an `ALL` R6 leg and are left out.
* Scratches R1 #8 Adieu Aces (Don's #3), R2 #10, #11 Seeking Aces (the
  model's #1 and Don's #2, also-eligible), #12, R3 #5, R4 #11, #12, R5 #4,
  R7 #6, R8 #11.
* **The model's top four hit the R1 superfecta box ($5.34 for $0.10)** and its
  top two the R1 exacta ($4.00): 1-9-4-5 against 9-1-5-4. Its #1 won 1 of 7
  (R7 Rhone Valley, $3.80), placed 2nd in R1, R2 and R5.
* Don's #1 won 2 of 7 (R1 #9 Rocketeightyeight $3.80, R7 #2 Rhone Valley
  $3.80). His top three hit the R1 trifecta ($6.95) and wheel ($5.34).
* Long shots beat both sources in R3 (#10 Secret Hint 12.1-1, the model's
  last of 9), R4 (#4 Tiffany's Ferrari 12.2-1) and R5 (#6 Kissesfor Cooper
  23.0-1).
