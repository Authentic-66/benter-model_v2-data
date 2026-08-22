# Phase 6C — Adding Ellis Park to the DPv1 training corpus

**Status:** complete. **Recommendation: adopt the 4-track model** (decision path 1,
with one measured caveat in §6).

Phase 6B loaded ELP into `racing_full.db` but trained nothing on it. DPv1 scored
Ellis Park by generalising from GP/CT/MNR, with the `track_code` one-hot block
all zeros. Phase 6C adds ELP to the training set and measures what that costs
and buys, per track.

No feature engineering, no architecture change, no PP changes, no ticket EV.
The only inputs that changed are the rows in the training corpus — plus one data
bug found on the way in, documented in §2.

---

## 1. Summary

| | |
|---|---|
| Training corpus | 140,188 → **149,995** entries (18,904 → **20,115** races) |
| ELP contribution | 9,807 entries / 1,211 races — **6.5%** of the corpus |
| ELP top pick hits the board | **53.5% → 57.1%** (+3.5pp, 95% CI [+1.1, +6.2]) |
| ELP fundamental AUC | **0.627 → 0.659** (home tracks: 0.696) |
| GP / CT / MNR blended log-loss | **unchanged to five decimal places** |
| GP / CT / MNR top-1 selection | −0.25pp, CI [−0.52, +0.02] — not systematic (§6) |
| Sunday 2026-08-23 card | top pick changed in **2 of 9** races |

The gain is real, is present in every one of the four folds, and survives every
attempt made here to explain it away as an artifact. It is also modest, and it
comes with a small unresolved question mark on the incumbent tracks that §6
reports rather than rounds off.

---

## 2. Is the ELP data fit to train on?

### 2.1 Coverage — complete

Every ELP entry in scope has a feature row: **10,013 / 10,013** for 2022+.
Of the 1,540 ELP races Phase 6B loaded, 1,229 fall inside the HISA-era
`TRAIN_DATE_MIN = 2022-01-01` scope; the remainder are 2021 and are excluded by
the same rule that has always applied to the other three tracks.

| track | races | entries | with features |
|---|---:|---:|---:|
| GP | 8,563 | 65,948 | 65,948 |
| CT | 6,009 | 44,496 | 44,496 |
| MNR | 4,332 | 29,744 | 29,744 |
| ELP | 1,229 | 10,013 | 10,013 |

No new categorical levels. ELP is a strict subset of the levels already seen —
it lacks `AllWeather`, `Heavy`, four minor race types and the `mid`
track-bias bucket. Nothing in the ELP slice can surprise the preprocessor.

### 2.2 A label bug found on the way in — 206 fabricated negatives

`y_true = (finish_pos <= 3)` evaluates `NaN` to `False`. Phase 6A's prediction
runner loads *upcoming* cards into the same `entries` table the trainer reads,
so `racing_full.db` was carrying the ELP cards for **2026-08-22 and 2026-08-23**
— 18 races, 206 entries, none of them run yet, every one silently labelled
*missed the board*, and all of them inside the 2026 validation fold. That is
10.6% of the ELP 2026 validation slice.

Fixed in `prepare_training_dpv1.drop_unrun_races`, which drops races with **zero**
recorded finishers. The test is deliberately zero-finishers-in-the-race, not
null-finish-on-the-entry: a scratch is a null finish in a race that did run, and
those have always been carried (0.6% of the 3-track corpus). Leaving scratches
alone keeps this comparison to one change.

This bug did not affect any pre-6C result — ELP was not in the training set and
the 3-track corpus has no unrun races. It would have affected every Phase 6C
number had it not been caught, and it will affect any future retrain run while
an upcoming card is loaded.

### 2.3 The real gap — ELP's missingness, and why it looked dangerous

ELP's mean feature null rate is **33.2%** against **14.3%** on the three
incumbent tracks. The gap is concentrated entirely in prior-start-derived
features:

| feature | GP | CT | MNR | **ELP** |
|---|---:|---:|---:|---:|
| `second_race_back_pattern` | 0.285 | 0.170 | 0.178 | **0.775** |
| `distance_specialist_flag` | 0.329 | 0.205 | 0.209 | **0.740** |
| `historical_condition_winrate_shrunk` | 0.268 | 0.218 | 0.274 | **0.715** |
| `is_first_time_lasix` | 0.233 | 0.109 | 0.130 | **0.630** |
| `class_change_from_last` | 0.158 | 0.093 | 0.095 | **0.540** |
| `speed_trajectory_3_races` | 0.517 | 0.398 | 0.451 | **0.901** |

**This is not corrupt data — it is a boutique meet shipping in from tracks we
have not loaded.** Two independent tests establish that, because
`career_starts` and `last_race_*` are both derived from in-corpus history and
therefore agree by construction and cannot cross-check each other:

- **Non-maiden races.** A claiming or allowance horse is essentially never a
  debutant. **37.8%** of ELP non-maiden entries have no prior corpus start,
  against **4.7–6.6%** at GP/CT/MNR.
- **Within-meet decay.** ELP's no-prior-start rate falls from ~67% in the first
  third of each meet to ~41% in the last third, in all five years. A true debut
  rate cannot do that; "the DB has not seen this horse yet" does exactly that.

### 2.4 The pre-registered risk

The preprocessor emits one **shared** `{col}__missing` coefficient across all
tracks. That is only safe if the flag means the same thing everywhere. It did
not:

| | no-prior ITM | with-prior ITM | ratio |
|---|---:|---:|---:|
| GP (real debutants) | 0.358 | 0.407 | **0.879** |
| ELP (shippers) | 0.403 | 0.410 | **0.983** |

Same flag, different animal. GP's missing-history horses run like debutants;
ELP's run like ordinary horses the corpus simply cannot see. The stated risk
going into the rebuild was that mixing the two would muddy a coefficient the
incumbent tracks depend on. §5 reports what actually happened.

---

## 3. Experiment design

Two arms over **identical validation rows**:

- **Arm A** — train on GP/CT/MNR, validate on all four tracks.
- **Arm B** — train on GP/CT/MNR/ELP, validate on all four tracks.

Same rolling-origin folds by year (train `< Y`, validate `= Y`, for Y in
2023–2026), same feature set (95 fundamental features), same hyperparameters,
same 116,665 validation entries across 15,561 races in both arms. Every
difference below is attributable to the training corpus and nothing else.

Implemented as `--tracks` (corpus loaded and validated) and `--train-tracks`
(what is actually fit) on `train_dpv1.py`:

```
python scripts_dpv1/train_dpv1.py grid  --tracks 4 --train-tracks 4 --out .../dpv1_grid_results_4track.csv
python scripts_dpv1/train_dpv1.py final --tracks 4 --train-tracks 4 --grid .../dpv1_grid_results_4track.csv
```

**Hyperparameters are immaterial here and both arms use the same ones.** The
full 16-combo grid (4 half-lives × 4 L2 values) spans **1.0×10⁻⁵** in mean
log-loss on the 4-track corpus and 7.3×10⁻⁶ on the 3-track corpus. "Best combo"
selection at that scale is picking noise, so both arms were run at the 4-track
grid's winner — `half_life = 2.5y, l2 = 0.001` — rather than letting each arm
drift to a different point on a flat surface. The 3-track-train grid
independently picks the same half-life.

For reference, the archived Phase 4C artifact (`dpv1_3track.pkl`, trained
2026-07-31) reproduces exactly against the current DB — its 108,386 fold
predictions match the current GP/CT/MNR rows race for race — so no incumbent
data changed between Phase 4C and here.

---

## 4. Per-track results

### 4.1 Blended model (fundamental + market)

| slice | entries | log-loss 3-track | log-loss 4-track | Δ | 95% CI on Δ |
|---|---:|---:|---:|---:|---|
| GP | 50,577 | 0.55741 | 0.55741 | **0.00000** | [−0.00002, +0.00003] |
| CT | 34,507 | 0.55076 | 0.55078 | +0.00002 | [−0.00001, +0.00005] |
| MNR | 23,302 | 0.55331 | 0.55330 | −0.00002 | [−0.00006, +0.00003] |
| **ELP** | 8,279 | 0.56321 | **0.56271** | **−0.00049** | **[−0.00080, −0.00021]** |
| 3-track pooled | 108,386 | 0.55441 | 0.55441 | 0.00000 | [−0.00001, +0.00002] |
| ALL | 116,665 | 0.55503 | 0.55500 | −0.00003 | [−0.00006, −0.00000] |

CIs are a paired bootstrap over races, 2,000 resamples.

The blended movement is tiny **because the blend is market-dominated** —
β ≈ 0.77 on the market logit against α ≈ 0.11 on the fundamental. The market
input is identical in both arms, so it dilutes any fundamental change by roughly
7:1. This table is the right place to confirm *no harm*; it is the wrong place
to look for the benefit.

### 4.2 Fundamental model — the side the card actually uses

`card_picks.py` calls `predict_card(..., use="fundamental")`. The deliverable
never sees the blend, so this is the decision-relevant table.

| slice | AUC 3-track | AUC 4-track | Δ | log-loss 3-track | log-loss 4-track | Δ |
|---|---:|---:|---:|---:|---:|---:|
| GP | 0.69485 | 0.69483 | −0.00002 | 0.61234 | 0.61220 | −0.00014 |
| CT | 0.69917 | 0.69848 | −0.00069 | 0.61213 | 0.61247 | +0.00034 |
| MNR | 0.69353 | 0.69346 | −0.00007 | 0.62347 | 0.62351 | +0.00004 |
| **ELP** | 0.62674 | **0.65863** | **+0.03189** | 0.66199 | **0.62301** | **−0.03898** |

ELP closes about **45% of the gap** to home-track AUC (0.627 → 0.659 against
~0.696). Phase 6B's estimate that ELP ran at "~75% of home-track accuracy" was
about right, and roughly half of that shortfall was the missing ELP training
data. The rest is the corpus gap of §2.3, which no amount of retraining fixes.

### 4.3 Top-pick selection — ranking by the fundamental

| slice | races | top-1 ITM 3-track | top-1 ITM 4-track | Δ | 95% CI | P(4-track better) |
|---|---:|---:|---:|---:|---|---:|
| GP | 6,613 | 0.6348 | 0.6331 | −0.0017 | [−0.0056, +0.0021] | 0.198 |
| CT | 4,609 | 0.6602 | 0.6594 | −0.0009 | [−0.0050, +0.0033] | 0.330 |
| MNR | 3,321 | 0.6585 | 0.6522 | −0.0063 | [−0.0129, +0.0003] | 0.026 |
| **ELP** | 1,018 | **0.5354** | **0.5707** | **+0.0354** | **[+0.0108, +0.0619]** | **0.996** |
| 3-track pooled | 14,543 | 0.6483 | 0.6458 | −0.0025 | [−0.0052, +0.0002] | 0.035 |

ELP's full top-k picture: hit-top3 0.9008 → 0.9332, precision-top3 0.4653 →
0.4971, precision-top4 0.4398 → 0.4718 — all moving together, all by about
+3pp.

**57.1% is inside the 55–57% band pre-registered in Phase 6B** for a card at
ELP's typical feature coverage, against a 36.9% base rate.

### 4.4 corr(logit p_f, logit p_m) — the Phase 4B.1 diagnostic

| slice | 3-track | 4-track | Δ |
|---|---:|---:|---:|
| GP | 0.6082 | 0.6134 | +0.0052 |
| CT | 0.6773 | 0.6783 | +0.0010 |
| MNR | 0.5506 | 0.5503 | −0.0004 |
| ELP | 0.4148 | 0.4968 | +0.0820 |
| CT+MNR | 0.6177 | 0.6180 | +0.0003 |

ELP's correlation rises materially — expected and healthy. A fundamental model
with no ELP coefficients was *decorrelated from the market by ignorance*, not by
independent insight; 0.41 was a symptom, not an achievement. At 0.497 it is
still the most independent of the four tracks and comfortably under the 0.60
bar.

**Reporting honestly:** DPv1's ship criterion is `corr < 0.60` on CT+MNR, and
CT+MNR sits at **0.618 in both arms**. That criterion is not met, and was not
met before Phase 6C either. It is a pre-existing condition, unchanged here
(Δ = +0.0003), and outside this phase's scope — but it should not go unstated.

---

## 5. Where the ELP gain comes from

Three checks, because "more data helped" is the kind of claim that deserves
adversarial testing before it is believed.

**It is not the missing ELP intercept.** That was Phase 6B's hypothesis. The
3-track model's fundamental averaged **45.5%** P(ITM) on ELP against a **36.9%**
actual rate — badly over-confident. But after fitting an *oracle* Platt
recalibration on ELP's own held-out labels — an upper bound on what any pure
level-and-slope fix could buy — the 3-track model still trails by **+0.0125**
log-loss. That residual is ranking skill, not calibration. AUC confirms it
independently, being shift-invariant by construction. And the fitted
`track_code__ELP` coefficient is only **−0.023**, far too small to be the story.

**The gain is largest on exactly the rows §2.4 flagged as the risk.**

| ELP group | n | Δ log-loss | Δ AUC |
|---|---:|---:|---:|
| no corpus history (shipper) | 4,421 | **−0.0480** | **+0.0323** |
| corpus history present | 3,858 | −0.0286 | +0.0275 |

The feared mechanism was real — the largest coefficient moves between the two
models *are* `__missing` flags (`track_dirt_bias_90d__missing` +0.119,
`last_race_finish_pos__missing` +0.068, `is_at_jockey_home_track__missing`
−0.096; 9 of the 30 largest moves are missing-flags). But the sign is the
opposite of the worry. Rather than ELP corrupting a coefficient the incumbents
rely on, the model learned to condition the flag's meaning, and the shipper rows
— previously the worst-served population on the card — improved most.

**It is not a data-volume threshold.** The gain is present in all four folds,
including fold 2023, which had only 1,528 ELP training entries:

| val year | ELP train entries available | Δ log-loss | Δ AUC |
|---|---:|---:|---:|
| 2023 | 1,528 | −0.0480 | +0.0290 |
| 2024 | 4,271 | −0.0446 | +0.0415 |
| 2025 | 6,208 | −0.0169 | +0.0191 |
| 2026 | 8,075 | −0.0422 | +0.0333 |

One prior meet is enough to get most of the benefit. That is the directly
useful finding for expansion to CD, IND and KDW.

---

## 6. The caveat: a possible small cost on the incumbent tracks

Pooled 3-track top-1 selection moves **−0.25pp**, CI [−0.52, +0.02],
P(4-track worse) = 0.965. MNR carries most of it at −0.63pp. This is the one
number in the phase that does not favour the 4-track model, and it should not
be rounded away.

Two things argue it is noise in a coarse metric rather than real degradation:

**It is not systematic across folds.** A real cost would show a consistent sign.

| fold | GP | CT | MNR | ELP |
|---|---:|---:|---:|---:|
| 2023 | +0.0005 | +0.0060 | −0.0052 | **+0.0425** |
| 2024 | +0.0032 | −0.0047 | −0.0169 | **+0.0175** |
| 2025 | −0.0036 | −0.0062 | +0.0021 | **+0.0441** |
| 2026 | −0.0118 | +0.0028 | −0.0024 | **+0.0333** |

GP and CT flip sign twice each. MNR's deficit is concentrated in fold 2024
(−0.0169) — one year of 1,004 races. ELP is positive in all four.

**The underlying ranking is unchanged.** Top-1 hit is a coarse, high-variance
functional of the ranking; AUC is the smooth one, and 3-track AUC moves by
−0.00002 to −0.00069. Blended log-loss on the 3-track pool moves by 0.00000.
A genuine ~0.25pp ranking degradation would be visible in AUC. It is not.

**If it is real**, it is roughly a wash in absolute terms: −0.0025 × 14,543
races ≈ **36 fewer** board hits on the incumbents, +0.0354 × 1,018 races ≈
**36 more** at ELP. Per race, the ELP gain is about 14× the incumbent loss.
Either way, this is the honest shape of the trade — a small, unproven cost
spread thin across tracks that are already well served, against a large,
fold-consistent gain on the track that was not.

---

## 7. Sunday 2026-08-23 ELP card — head to head

Three versions exist, and conflating them would be wrong:

| | model | DB snapshot |
|---|---|---|
| **6B** | 3-track | 2026-08-21 23:30 |
| **A** | 3-track | now (2026-08-22 09:25) |
| **B** | 4-track | now (2026-08-22 09:24) |

Comparing 6B directly to B would mix a model change with a data change: the
2026-08-21 ELP results were loaded into `racing_full.db` this morning, lifting
feature coverage about a point across the card. **Only A vs B isolates the
model**, so the 3-track model was re-run on the current DB for the comparison.

| R | 6B (3t, old DB) | A (3t, now) | B (4t, now) | P(ITM) B | cause of change |
|---|---|---|---|---:|---|
| 1 | #4 Tiz Freedom | #4 Tiz Freedom | **#6 Restore** | 45.0 | **model** |
| 2 | #2 Honor Bound | #2 Honor Bound | #2 Honor Bound | 43.5 | — |
| 3 | #2 Positive Equity | #2 Positive Equity | #2 Positive Equity | 58.1 | — |
| 4 | #4 She's Gotta Go | #4 She's Gotta Go | #4 She's Gotta Go | 38.4 | — |
| 5 | #1 Ever Forward | #1 Ever Forward | #1 Ever Forward | 55.7 | — |
| 6 | #3 Military Cruiser | #7 Livehappy | #7 Livehappy | 49.1 | **new data** |
| 7 | #1 Ali's Glory | #1 Ali's Glory | #1 Ali's Glory | 36.3 | — |
| 8 | #4 Next Up | #4 Next Up | **#6 Lush Lips** | 47.6 | **model** |
| 9 | #3 Ciarlatano | #3 Ciarlatano | #3 Ciarlatano | 28.7 | — |

**Top pick changed by the model in 2 of 9 races. New data changed 1 more** —
Race 6 was already #7 Livehappy under the 3-track model once yesterday's results
were loaded, so that switch is not attributable to Phase 6C.

Agreement between the two models across all 101 entries: Pearson r **0.985** on
P(ITM), Spearman ρ **0.975**, mean within-race Kendall τ **0.766** (min 0.467).
Mean |ΔP(ITM)| **1.42pp**, range −6.5 to +4.9pp.

The two model-driven flips:

- **Race 1** — #6 Restore (6/1, 84% cov) 41.7% → 45.0%, passing #4 Tiz Freedom
  (5/2, 85% cov, 44.6% → 45.0%). The two are now effectively tied.
- **Race 8** — #6 Lush Lips (**2/5**, 86% cov) 44.3% → 47.6%, passing #4 Next Up
  (15/1, 84% cov, 49.3% → 45.1%). The 4-track model moves *toward* the heavy
  favourite here, which is worth noting given that the whole v2/DPv1 rebuild
  exists to correct a v1 model that anchored on the morning line. The
  fundamental model does not see odds at all, so this is agreement, not
  anchoring — but it removes what was the card's most striking disagreement.

**One thing the card cannot show you.** `card_picks` reports P(ITM) from a
Plackett-Luce simulation, whose first-three position marginals sum to 3 over any
field by construction. So the card is normalised to 3/field-size regardless of
model, mean P(ITM) is identical (26.73%) in both versions, and **none of the
calibration repair in §5 reaches the card at all**. What reaches the card is the
ranking component only — the +0.032 AUC and the +3.5pp top-1 hit rate. The
raw-probability improvement matters for anything that consumes `p_fund`
directly, and not for this page.

Both versions are preserved for validation:

```
scripts_dpv1/picks/ELP_2026-08-23_20260821-2330.{txt,csv}   3-track, Phase 6B
scripts_dpv1/picks/ELP_2026-08-23_20260822-0924.{txt,csv}   4-track, Phase 6C
```

Race 9 remains flagged at 58% coverage — a 15-horse 2yo maiden turf field. It is
the weakest ranking on the card under either model.

---

## 8. Artifacts

**New / replaced**

| file | what |
|---|---|
| `dpv1.pkl` | **4-track model**, `dpv1.2.0-4track`, 149,995 rows / 20,115 races |
| `dpv1_grid_results.csv` | 4-track grid, 16 combos × 4 folds (copy of `..._4track.csv`) |
| `dpv1_grid_results_4track.csv` | same, under an explicit name |
| `dpv1_fold_predictions.csv` | 116,665 out-of-sample validation entries, 4 tracks |
| `dpv1_eval.json` | per-track evaluation incl. ELP |
| `dpv1_predictions_sample.json` | sample race per track, now 4 races incl. ELP |
| `picks/ELP_2026-08-23_20260822-0924.{txt,csv}` | Sunday card, 4-track |

`evaluate_dpv1.py` re-derives its hyperparameters from `dpv1_grid_results.csv`
rather than reading them off the model, so that file must track the shipped
artifact or the evaluation silently scores a differently-tuned model than the
one in `dpv1.pkl`. It did, briefly, during this phase. Given the grid surface
spans 1×10⁻⁵ the numbers were unaffected, but the canonical grid file is now
the 4-track one and the 3-track grid is kept under its `_3track` name.

**Preserved 3-track backups**

| file | what |
|---|---|
| `dpv1_3track.pkl` | Phase 4C/5A model, `dpv1.1.0`, unchanged |
| `dpv1_grid_results_3track.csv` | original grid |
| `dpv1_fold_predictions_3track.csv` | original 108,386 fold predictions |
| `dpv1_eval_3track.json` | original evaluation |

Rollback is `cp dpv1_3track.pkl dpv1.pkl`. Every consumer takes `--model`.

**Code changes** — all additive, no architecture change:

- `prepare_training_dpv1.py` — `TRACKS_3` / `TRACKS_4`; `tracks=` filter on
  `load_full_frame`; new `drop_unrun_races` (§2.2).
- `train_dpv1.py` — `ELP` and `3TRACK` slices; `--tracks` / `--train-tracks`;
  `--version`; final refit honours the training-track restriction.
- `card_picks.py` — reads the trained track list off the artifact instead of
  hard-coding GP/CT/MNR; docstring rewritten (it stated as fact that the model
  had never seen Ellis Park).
- `dpv1_common.py`, `evaluate_dpv1.py` — stale 3-track comments and the
  sample-race track list.

---

## 9. Recommendation

**Adopt the 4-track model.** This is decision path 1: better where it was
supposed to get better, no measurable harm elsewhere, with the §6 caveat
recorded rather than smoothed over.

Supporting reasons, in order of weight:

1. The ELP gain is **fold-consistent** (all four), **mechanism-checked** (not an
   intercept, not a volume threshold), and lands on the metric the deliverable
   actually uses — top pick hits the board 53.5% → 57.1%.
2. Incumbent blended log-loss is unchanged to five decimals and incumbent AUC to
   four. The one adverse number (§6) is fold-inconsistent and invisible in AUC.
3. It generalises. One prior meet (1,528 entries) captured most of the benefit,
   which is a direct, quantified argument for the CD / IND / KDW expansion.

**Do not read this as ELP now being a solved track.** ELP's fundamental AUC is
0.659 against ~0.696 at home, and the remaining gap is the corpus, not the
coefficients: 38% of ELP's non-maiden starters have no history in
`racing_full.db` because they ship in from tracks that are not loaded. Phase
6B's recommendation #2 stands and is now quantified — **loading Churchill,
Indiana Grand and Kentucky Downs would do more for ELP accuracy than anything
done in this phase**, because it converts blank rows into real ones rather than
teaching the model to handle blanks better.

**Still pending, and unaffected by any of this:** the nine Sunday picks are not
yet scored. Nine races prove nothing on their own; the point is to start
accumulating. Phase 6C changes two of those nine top picks, so score **both**
saved versions when the chart lands.

---

*Phase 6C — 2026-08-22. Per-track evaluation on 116,665 out-of-sample entries
across 15,561 races, identical in both arms.*
