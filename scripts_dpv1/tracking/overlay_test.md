# Overlay test: does the live model find overlays? (read-only, 2026-11-20)

Doug's decision test. No change to the live model, the live DB or any live
code. Everything ran on a byte copy of `scripts/racing_full.db` (sha256
`e49cb1bd…`, identical to live when copied) in the scratchpad. Scripts and
the full numbers: `tracking/overlay_test/` (`oos.py`, `rerun.py`,
`analyse.py`, `results.json`).

**Short answer: no edge.** Both rules lose more than betting every horse.
The horses the model likes more than the tote finish in the money at about
the tote's rate, not the model's. Details below; plain reading at the end.

## 1. Scope and fairness checks

### The live model

| | |
|---|---|
| version | `dpv1.3.2-5track-stretch` (`dpv1.pkl`), plus `pp-reranker-1.0` (Config Y, as live) |
| trained | 2026-10-21 20:24 CDT, on `_stretch/racing_s.db`, a copy of the live DB taken that day |
| fitted tracks | GP, CT, MNR, ELP, DED, races from 2022-01-01 on (179,126 starters, 23,787 races) |
| last race in the training copy | GP 10/18, CT 10/17, DED 10/17 (DED 10/21 was not yet run and was dropped), ELP 8/23, MNR 7/29 |
| in the DB but never fitted | EVD (to 6/25), LAD (to 9/16), FG (to 3/22). These were history for the features only |
| probability used | the **fundamental** P(ITM) after the PP reranker, the same number `card_picks` prints. It has no odds input. The shipped blend (β 0.77 on the tote) was **not** used, because it is mostly the tote |

### Out-of-sample races

These are races with a chart in the live DB that were **not in the training
copy**, so the model was never fitted on any of them: **1,055 races, 7,958
starters.**

| track | races | days | dates |
|---|---|---|---|
| DED | 153 | 18 | 10/21–11/19 (this meet from the first card after training) |
| MNR | 399 | 51 | 2026-08-02 – 11-04 (loaded 11/07) |
| EVD | 322 | 38 | mostly Jun–Sep 2026 (also 9 from Jul 2025 and 17 from Apr–May 2026, all late loads) |
| CT | 66 | 9 | 2026-10-22 – 10-31 (and 2 from May 2026) |
| LAD | 51 | 7 | 2026-09-19 – 09-30 |
| GP | 50 | 5 | 2026-10-23 – 10-31 |
| FG | 14 | 1 | 2025-02-15 (a late-loaded day) |
| ELP | 0 | | nothing new since training |

* **347 races are dated after the training data ends (10/17).** The other 708
  are earlier-dated charts loaded after 10/21. The model never saw their
  results, but they fall inside the period it was trained on. Both groups
  are reported in section 2; they agree.
* **387 races are at EVD, LAD and FG, tracks the model has never been fitted
  on.** The other 668 are at its own tracks. These two groups also agree.

### Point-in-time features

* **Fixed in the scratch rerun:** `days_since_jockey_last_win` and
  `days_since_trainer_last_win` were recomputed as of the **start of the
  race day**, counting only wins on earlier dates (1.4 item 5).
  * In the stored table, these features read same-day results on 1,331
    jockey rows and 716 trainer rows of the 7,958.
  * **146 trainer rows carried the same-race stablemate leak**: a NULL caused
    by a stablemate winning that very race. After the fix, no feature depends
    on a same-day result.
* **Already start-of-day, so no change:** every other jockey and trainer
  feature. The 11/09 audit recomputed them all and found 0 differing rows.
  Horse features cannot leak, because a horse runs once a day. Track bias
  uses earlier dates only.
* **Not fixed, a mild look-ahead that favours the model:**
  * Speed-figure pars are the frozen `pars-v1-20261108`, medians over every
    race through 11/07. That includes most of these races, so earlier figures
    were scaled with a little later data.
  * Fixing it means pars as of each date, which is the open par-policy
    decision (PHASE_7). It was left alone because the error can only flatter
    the model, and the model still loses.
* **Rerun vs what was logged live (DED):**
  * The rerun scores charted rows: the actual starters, and no PP bridge for
    horses with no DB history. The live run scored the full field from the
    PP, with the bridge.
  * The two differ: correlation of P(ITM) 0.83 over 1,130 starters, same #1
    in 76% of races.
  * So both versions are reported for DED. The logged predictions are
    genuinely pre-race (136 races on 1.3.2, 10/22–11/19).
* **Reranker:** it fired in 162 races, the DED cards plus some EVD days that
  have PP files. Everywhere else the base model ran alone, as it would live
  with no PP.

### PP files on disk (reference)

| track | files | dates (2026) | in `pp_entries_raw` |
|---|---|---|---|
| DED | 23 | 10/10 – 11/20, every card this meet | 23 dates |
| GP | 27 | 5/08 – 6/26, 9/04, 10/02 | 18 dates |
| CT | 18 | 5/07 – 6/25, 8/28, 8/29, 10/01 | 16 dates |
| FP (Fairmount) | 12 | 5/05 – 6/23 | 12 (no charts in the DB) |
| EVD | 11 | 5/09 – 6/25 | 11 |
| ELP | 2 | 8/22, 8/23 | 2 |
| MNR | 1 | 8/03 | 1 |
| KEE | 1 | 10/31 | not loaded |

## 2. The test

* **Inputs:** final tote odds and chart payouts only. Every bet is $2.
* **Market probabilities:**
  * Market P(win) is 1/(odds+1) for each betting starter, normalised so the
    field sums to 1. This removes the takeout.
  * Market P(ITM) is that win vector through the existing Harville layer
    (`dpv1_runtime.market_itm_from_odds`).
* **Model probabilities:**
  * Model P(ITM) is the reranked fundamental P(ITM).
  * Model P(win) is that P(ITM), rescaled so the field sums to 3, then
    inverted through Harville (`normalise_itm` → `invert_harville`, as in
    `predict_card`).
* **Bets left out (refunded):**
  * 119 races had no show bet: 78 had no show wagering (fields of 2–5, mostly
    MNR), and in 41 the DB is missing an in-the-money show payout. Show bets
    and the show baseline cover the remaining **936 races**.
  * 4 races (MNR fields of 2–3) have no win payout. Win bets and the win
    baseline cover **1,051 races**.
* **Rules and thresholds:** exactly as written, nothing tuned.
  * Rule A, as Doug stated it, has no rank condition.
  * The July v2a version (PHASE_3G) also required the horse to be outside the
    model's top three. That version is shown as a second line for reference.
* **Intervals:** 90% bootstrap, 5,000 resamples **by race**, because bets in
  the same race are not independent.

### Rule A: $2 show, model P(ITM) > 25% and market P(ITM) < 20%

| | bets | hits | hit rate | staked | returned | ROI | 90% interval |
|---|---|---|---|---|---|---|---|
| **Rule A** | 1,171 | 181 | 15.5% | $2,342 | $1,427.20 | **−39.1%** | −46.3% to −31.4% |
| Rule A + outside model top 3 (v2a) | 1,006 | 148 | 14.7% | $2,012 | $1,199.00 | −40.4% | −48.3% to −32.3% |
| *Baseline: show on every horse* | 7,279 | 2,813 | 38.6% | $14,558 | $11,114.70 | *−23.7%* | −25.4% to −21.8% |

* **Hits were 181 against 387 expected by the model and 150 by the market.**
  The model's average P(ITM) on these horses was 33%; they hit 15.5%. The
  tote's average was 13%.
* So the horses do hit a little more often than Harville says. That is the
  known Harville bias on longshots, not a model edge, and show pools pay
  little on it.
* The typical qualifier went off at **25-1** (median; quartiles 19-1 to 38-1).

| split | Rule A bets | hits | ROI | 90% interval | baseline show ROI |
|---|---|---|---|---|---|
| DED | 177 | 24 | −46.0% | −63.1% to −27.6% | −23.2% |
| MNR | 377 | 56 | −40.1% | −52.5% to −26.9% | −25.1% |
| EVD | 398 | 67 | −29.8% | −44.0% to −14.9% | −22.5% |
| CT | 82 | 18 | −33.5% | −56.1% to −8.5% | −25.9% |
| LAD | 56 | 6 | −65.2% | −89.2% to −36.2% | −28.9% |
| GP | 52 | 8 | −37.3% | −72.0% to +0.4% | −15.5% |
| FG | 29 | 2 | −79.3% | −100% to −41.9% | −26.9% |
| maidens | 320 | 41 | −45.1% | −58.9% to −30.6% | −23.8% |
| non-maidens | 851 | 140 | −36.8% | −45.3% to −28.1% | −23.6% |
| no-data shippers | 113 | 17 | −32.3% | −58.2% to −4.5% | −23.0% |
| the rest | 1,058 | 164 | −39.8% | −47.5% to −31.8% | −23.7% |
| dated after 10/17 | 403 | 65 | −36.9% | | −22.7% |
| earlier-dated, loaded later | 768 | 116 | −40.2% | | −24.2% |
| model's own tracks | 688 | 106 | −40.6% | | −23.8% |
| EVD / LAD / FG | 483 | 75 | −36.9% | | −23.4% |

### Rule B: $2 win, model P(win) ≥ 1.2 × market P(win) and model P(win) ≥ 10%

| | bets | wins | hit rate | staked | returned | ROI | 90% interval |
|---|---|---|---|---|---|---|---|
| **Rule B** | 2,462 | 166 | 6.7% | $4,924 | $3,287.60 | **−33.2%** | −42.6% to −23.4% |
| *Baseline: win on every horse* | 7,948 | 1,054 | 13.3% | $15,896 | $11,922.90 | *−25.0%* | −29.7% to −19.8% |

* **Wins were 166 against 385 expected by the model and 195 by the market.**
  The model's average P(win) on these horses was 15.6%; they won 6.7%. The
  tote's average was 7.9%.
* The typical qualifier went off at **10-1** (median; quartiles 7-1 to 17-1).

| split | Rule B bets | wins | ROI | 90% interval | baseline win ROI |
|---|---|---|---|---|---|
| DED | 341 | 21 | −34.3% | −59.8% to −6.1% | −23.5% |
| MNR | 983 | 58 | −43.0% | −56.7% to −29.6% | −29.9% |
| EVD | 755 | 55 | −27.5% | −43.8% to −10.1% | −23.7% |
| CT | 146 | 10 | −32.5% | −71.9% to +17.0% | −31.7% |
| LAD | 106 | 12 | −5.1% | −46.6% to +43.6% | −21.7% |
| GP | 102 | 8 | −37.6% | −70.6% to −3.3% | −0.1% |
| FG | 29 | 2 | +71.0% | −100% to +342% | −18.2% |
| maidens | 539 | 23 | −54.6% | −71.3% to −35.9% | −29.2% |
| non-maidens | 1,923 | 143 | −27.2% | −38.1% to −15.8% | −23.6% |
| no-data shippers | 204 | 12 | −38.2% | −69.2% to −1.4% | −33.6% |
| the rest | 2,258 | 154 | −32.8% | −42.5% to −22.3% | −24.1% |
| dated after 10/17 | 775 | 50 | −35.8% | | −20.3% |
| earlier-dated, loaded later | 1,687 | 116 | −32.1% | | −27.4% |
| model's own tracks | 1,572 | 97 | −39.8% | | −26.1% |
| EVD / LAD / FG | 890 | 69 | −21.7% | | −23.2% |

FG's +71% is two winners from one day (29 bets) and means nothing.

### The pattern behind both rules

All bettable starters are split into fifths by how much more the model likes
each horse than the tote does (model ÷ market):

| fifth | median model ÷ market | model P(ITM) | market P(ITM) | **actual ITM** | $2 show ROI |
|---|---|---|---|---|---|
| 1 (model likes less) | 0.61 | 39.8% | 67.5% | **62.8%** | −11.8% |
| 2 | 0.84 | 47.3% | 56.9% | **55.0%** | −13.9% |
| 3 | 1.11 | 41.9% | 37.8% | **39.9%** | −20.0% |
| 4 | 1.65 | 34.8% | 21.2% | **23.6%** | −31.7% |
| 5 (model likes most) | 3.06 | 29.0% | 9.5% | **11.8%** | −40.9% |

| fifth | median model ÷ market | model P(win) | market P(win) | **actual win** | $2 win ROI |
|---|---|---|---|---|---|
| 1 | 0.53 | 15.2% | 30.5% | **33.0%** | −7.9% |
| 2 | 0.91 | 15.4% | 17.4% | **18.3%** | −13.6% |
| 3 | 1.36 | 14.0% | 10.4% | **8.7%** | −29.0% |
| 4 | 2.16 | 11.5% | 5.4% | **4.7%** | −36.6% |
| 5 | 4.11 | 10.0% | 2.4% | **1.7%** | −37.8% |

* In every fifth, the actual rate sits next to the tote's number, not the
  model's. **The more the model disagrees with the tote, the worse the
  return.**
* Log loss over the same starters: the tote is better on win (0.320 vs the
  model's 0.363) and on ITM (0.550 vs 0.599).
* Where the model and the tote disagree, the tote has been right.

### DED cross-check on the logged pre-race predictions

136 races on 1.3.2, 10/22–11/19. These are the predictions actually made
before post, with the PP bridge and the full field.

| | bets | hits | ROI | 90% interval | baseline |
|---|---|---|---|---|---|
| Rule A | 139 | 23 | −24.0% | −49.6% to +3.4% | −22.9% (show, every horse) |
| Rule A + outside top 3 | 110 | 16 | −27.0% | −55.7% to +5.0% | |
| Rule B | 300 | 21 | −22.8% | −52.6% to +10.6% | −21.5% (win, every horse) |

* **Expected vs actual:** Rule A hit 23 against 49.5 expected by the model
  and 18.2 by the tote. Rule B won 21 against 45.0 and 23.1.
* **Same picture as the rerun:** about the baseline, no better.
* **Maidens:** Rule A was +21.4% on 44 bets (11 hits; interval −34% to
  +89%). That is a split of a split, it was not pre-registered, and the
  rerun's maiden line is −45%. It is not evidence.

## 3. Tracks only in the archive (not run)

**What it would take:**
* **The charts.** The archive holds about **10,900 charts at 36 tracks**
  that are not in the live DB (2022: 2,333; 2023: 2,289; 2024: 2,287; 2025:
  2,150; 2026: 1,857). At roughly 8–9 races a chart, that is about 90,000
  races, about 15,000 of them from 2026.
* **A scratch DB load.** Load every archive chart into a copy of the DB
  (`db_loader.py` against the copy, or `retrain_pipeline.py --load-archive`
  pointed at a copy, never live). Purge non-Thoroughbred races
  (breed-filter rule). Check parse quality track by track; Canadian and
  small-meet charts are unproven in the parser.
* **Pars.** The new tracks have no par cells, so they get no speed figures,
  and with no figures the model's speed, track-bias and class terms are
  blank. A test needs pars for each new (track, surface, distance) cell.
  To be clean, those should be built only from races before the test
  window. This runs into the par-policy decision.
* **A feature build** over the whole scratch DB: a few minutes at today's
  size, plausibly 15–20 at 3–4 times the rows. Then the same rerun and
  analysis.
* **What to score.** Only races with enough earlier history at the same
  track, e.g. 2025–26, using 2022–24 as history. That is roughly 30,000–35,000
  races.

**Caveats:**
* The model has never been fitted on any of these tracks. It would score
  them through its "other track" terms, with no track or home-trainer
  coefficient.
* EVD/LAD/FG above are the nearest thing to that today, and they look no
  better or worse than its own tracks.
* So a bigger sample at new tracks would mostly tighten the intervals
  around the same answer. It cannot turn the result around unless those
  tracks behave very differently.

## 4. Plain reading

**There is no evidence the model finds overlays.**
* Over 1,055 races it never saw, betting the horses it likes more than the
  tote lost more than betting every horse: −39% vs −24% for the show rule,
  −33% vs −25% for the win rule.
* The 90% intervals of both rules sit wholly below zero. For Rule A the
  interval is also wholly below the baseline.
* The same happens at every track, in maidens and non-maidens, for shippers
  and the rest, before and after the training date, and on the live DED
  predictions made before post.
* The reason is plain: where the model and the tote disagree, the horses run
  to the tote's numbers, not the model's. On these horses the model claims
  more than twice the market's chance and gets about the market's.
* So these rules give nothing worth forward testing.

**What survives** is the earlier finding that the model is a reasonable
handicapper of who hits the board. That is ranking within a race. Pricing
against the tote is the separate job these rules test, and it fails that
job.

An edge, if there is one, would need a model that **beats the tote's own
probabilities**. The way to test that is the blend's market-adjusted
probability, or a new fundamental model, compared with the tote out of
sample. These raw fundamental-vs-tote rules cannot show it.
