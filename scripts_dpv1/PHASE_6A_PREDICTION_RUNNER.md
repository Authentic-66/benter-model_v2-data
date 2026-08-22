# Phase 6A — Prediction Runner, Monte Carlo Simulator, Ticket EV

Built the tooling that turns `dpv1.pkl` from a thing that scores historical
folds into a thing that scores a race card. Then backtested it, and the
backtest says the ticket-EV half does not work.

That headline is the point of this document. Everything else is machinery.

---

## What shipped

| File | Purpose |
|---|---|
| `dpv1_runtime.py` | Model loading, race loading, P(ITM) → win-probability inversion |
| `predict_race.py` | Score a card. DB / file / interactive / template |
| `simulate_race.py` | Plackett-Luce Monte Carlo → finish-position probabilities |
| `payout_model.py` | Parimutuel payout curves fitted to 99,021 real payoffs |
| `ticket_ev.py` | P(hit), expected payout, cost, EV, ROI, Kelly per ticket |
| `handicap_card.py` | The whole pipeline, one race or a whole card |
| `validate_phase6a.py` | The backtest that settles whether any of it works |

Artifacts: `dpv1_payout_model.json`, `phase6a_validation.json`.

Quick start:

```bash
python scripts_dpv1/handicap_card.py --track CT --date 2026-07-25 --race 5 --use fundamental
python scripts_dpv1/handicap_card.py --track CT --date 2026-07-25            # whole card
python scripts_dpv1/predict_race.py  --template card.csv                     # blank to fill in
```

---

## The headline result

`validate_phase6a.py` replays the entire pipeline over **14,517 out-of-sample
races** — each year scored by a model trained only on earlier years — builds
the standard ticket menu in each, keeps the tickets that price positive, and
looks up what the track actually paid from `exotic_payouts`.

| probability source | set | tickets | staked | hit % | forecast ROI | **realised ROI** |
|---|---|---:|---:|---:|---:|---:|
| fundamental | all | 86,758 | $410,669 | 19.3 | +35.9% | **−28.6%** |
| fundamental | +EV only | 37,078 | $187,894 | 13.2 | +118.1% | **−34.0%** |
| blend | all | 86,758 | $410,669 | 26.9 | −23.6% | **−23.3%** |
| blend | +EV only | 3,810 | $10,161 | 15.3 | +12.7% | **−34.0%** |
| market (control) | all | 86,758 | $410,669 | 26.8 | −12.9% | **−23.5%** |
| market (control) | +EV only | 18,303 | $60,790 | 16.2 | +15.1% | **−22.4%** |

95% bootstrap CI on the fundamental +EV selections: **−37.3% to −30.6%**.

Three things follow, and none of them are close calls:

1. **The EV column does not identify winning tickets.** Forecast +118%,
   returned −34%, with the whole confidence interval far below zero on
   $188k of simulated stakes.

2. **Filtering on +EV is worse than not filtering.** Betting every ticket
   returned −28.6%; betting only the ones the tool liked returned −34.0%. The
   filter has negative information content — it systematically selects
   longshot-heavy combinations whose realised returns are worse than the ones
   it rejects.

3. **The control beats the model.** Selecting tickets with the tote board
   itself returned −22.4%, better than either model-based selection. Where the
   fundamental model disagrees with the crowd about exotic combinations, the
   crowd is right more often than it is wrong.

The blend's behaviour is the tell. It labels only 3,810 of 86,758 tickets +EV
(4%, versus 43% for the fundamental model) precisely because it mostly agrees
with the market — and the few tickets it does flag return −34%, the same as
the fundamental model's. What is being measured in both cases is
*disagreement*, and disagreement with a parimutuel crowd is not an edge.

### Why the forecast was so wrong

The payout model is not the problem; it is validated to within a few percent
in every probability band and every field size (below). The problem is the
probability. DPv1's fundamental model is a per-entry binary logistic for
P(ITM); it was never fit to, or evaluated on, joint finishing order. Pushing it
through a Plackett-Luce chain to get P(1st AND 2nd AND 3rd) compounds its
errors multiplicatively, and the errors are large enough that "model says 3×
the crowd's probability" mostly means the model is wrong rather than the price
is.

The EV machinery is left in place because the numbers are informative as a
measure of model/market disagreement, and because a future model may earn
them. It is not left in place as a betting signal, and the tools say so at
runtime: `ticket_ev.py` and `handicap_card.py` read `phase6a_validation.json`
and print the measured realised ROI directly underneath any positive EV they
report. If the backtest is ever re-run with better numbers, the caveat updates
itself.

---

## What does work

**Ranking and probabilities from the database path.** Feeding a race's built
features to the model reproduces exactly what it was trained on, and the
prediction/simulation chain is internally exact:

- Harville inversion residual ~1e-11 in P(ITM) space, converging at every
  field size from 4 to 12.
- Simulated P(ITM) agrees with closed-form Harville to under 1 sigma.
- Monte Carlo combination probabilities agree with closed-form Plackett-Luce
  to a mean absolute difference of 0.0015, against an MC standard error of
  0.0032 — i.e. within noise.

**The payout model.** Fitted to 99,021 settled exactas, trifectas and
superfectas:

```
log(payoff / base) = a + b·(−log q) + c·log(n_combos)
```

with `q` the public's Plackett-Luce probability of the combination from
tote-implied win odds, fitted per (wager, track), plus Duan smearing for the
log-to-level conversion, a level-bias correction, and a measured per-field-size
adjustment. R² 0.85–0.94. Validated two ways: predicted vs realised mean payoff
by probability band (ratios 0.94–1.09), and return-to-covering-every-
combination by field size (ratios 0.98–1.09).

**The value flags.** `handicap_card.py` reports `edge = fund / mkt` per horse.
These are not backtested as bets and should not be used as such, but they are
the honest form of what the model has to say that the price does not.

---

## Two things measured along the way that are worth keeping

**Hand entry is not a degraded prediction, it is a different one.** Blanking
every feature outside the hand-entry schema — leaving 26 of 95 — and rescoring
300 real races:

| | full features | hand entry |
|---|---|---|
| Spearman rho vs full ranking | 1.00 | 0.61 |
| top pick unchanged | — | 44% |
| within-race P(ITM) spread | 36.7pp | 20.1pp |

Sparse entry both compresses the field toward the base rate *and* reorders it.
The `--interactive` and `--file` paths are useful for seeing what the model
thinks about inputs you control; they are not a source of probabilities. Making
live use real is a parser problem, not a UI problem — see below.

**"Covering every combination returns 1 − takeout" is false.** It was the
obvious sanity check on the payout model and it produced a confident diagnosis
of a bias that did not exist. It holds only if the crowd's exotic pool shares
match its win-odds-implied probabilities, and the fitted `b ≈ 0.78–0.88` is
direct evidence that they do not. Measured from real payoffs, covering every
combination returns **0.55–0.70**, well below `1 − takeout ≈ 0.78`. The payout
model is validated against that measured number instead.

---

## Where this leaves Phase 6B

The blocking problem for live use is not the simulator or the EV maths — both
are sound and both are now verified. It is that the features do not exist
before the result chart does. `entry_features_dpv1` is built from charts, so
the fidelity-preserving path only scores races that have already been run, and
the hand-entry fallback loses 40% of the ranking.

`brisnet_pp_parser.py` already extracts PP features for pre-race entries. The
useful Phase 6B is a builder that maps a PP file into the *same* 95 columns
DPv1 trains on, rather than the 45 PP-native columns Phase 5A tested as an
augmentation. That would make `predict_race.py` usable on a live card at full
coverage.

Worth being clear that it would not fix the EV result. Better feature coverage
gives better ITM probabilities; the backtest says the gap between a good ITM
probability and a profitable exotic ticket is not a coverage problem. Closing
that would need a model fit to finishing order rather than to a binary ITM
label — a different model, not a better-fed one.
