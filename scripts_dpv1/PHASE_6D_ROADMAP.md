# Phase 6D — model gap roadmap

A running catalog of things DPv1 cannot see, found during live use of the
Phase 6B card runner. Each entry is written when a gap shows up in a real
card, with the observed cases attached, so that the fix is argued from
evidence rather than from intuition.

This is a catalog, not a work plan. Nothing here is scheduled. Gaps #2-#5 are
headers only and get filled in as more races are cataloged.

---

## Gap #1 — Shipper Blindness

### What the model can't see

A horse whose entire racing history is at a track outside the training corpus.
DPv1 knows CT, ELP, GP and MNR. A horse shipping in from Laurel, Parx,
Churchill Downs, Penn National or anywhere else arrives with no history the
model can read, and the model does not distinguish "this horse has a weak
record" from "this horse has no record here". Both render as the same thing:
a features block full of NaN and a probability that is a field-average prior
wearing the costume of an assessment.

### Root cause

`feature_builder_dpv1.py` builds every history-derived feature by querying
`entries` and `computed_speed_figures_dpv1` keyed on `horse_id`. Both tables
contain rows for the four training tracks and nothing else. A shipper has no
rows, so the whole history block comes back empty.

The PP bridge (`pp_feature_bridge.apply_to_card`) partially covers this at
prediction time, and it is worth being precise about how far it gets. For
Outdoor Cat on CT 2026-08-29 R8:

* **51** of the model's features were missing before the bridge ran.
* The bridge filled **17** — last-race speed figure, beaten lengths, days
  since last race, distance/class change, equipment and blinkers, running
  style, surface specialist.
* **34 stayed missing**, and they are precisely the career-and-form block:
  `career_win_pct_shrunk`, `career_itm_pct_shrunk`, `last_3_avg_finish`,
  `last_race_finish_pos`, `last_race_won`, `speed_trajectory_3_races`,
  `gate_break_avg_last_3`, `second_race_back_pattern`, `track_specialist_flag`,
  the trainer-angle win percentages, and the pace-projection block.

So the bridge lifts a shipper's coverage — 46% to 64% for Outdoor Cat — while
leaving untouched every feature that describes *how the horse has been
running*. The lift is real but it is not the same thing as the model seeing
the horse.

The data to fix this is already parsed and already in the database.
`pp_entries_raw` holds 4,318 rows and 75 PP-derived columns, including
`pp_career_starts`, `pp_avg_speed_last3`, `pp_speed_fig_slope`,
`pp_best_speed`, `pp_dist_starts`/`pp_dist_wins`,
`pp_surface_starts`/`pp_surface_wins`/`pp_surface_winpct`, `pp_jt_winpct` and
the trainer/jockey angle counts. The feature builder simply never consults it.

### How it manifests in picks

The shipper ranks low, usually mid-pack to last, with a coverage figure in the
40s. The morning line disagrees sharply — the horse is often favoured — and
the live tote disagrees more sharply still. The model is not making a
contrarian call it can defend. It is ranking a horse it cannot see, and the
missing-data block pushes the horse *down* rather than toward the field mean.

The tell is the combination: low coverage, low rank, short price.

### Observed cases

| Date | Race | Horse | Model rank | ML | Coverage | Notes |
|---|---|---|---|---|---|---|
| 2026-08-28 | CT R3 | #2 Just Deeds | 4 of 8 entered (6 started) | 3/5 | 45% | **Won**, final odds 1/5, despite stumbling at the start. Prime Power 116.1. Zero prior starts in corpus — the only `entries` row for this horse is the race itself. |
| 2026-08-29 | CT R8 | #2 Outdoor Cat | 9 of 11 (6 of 11 with the PP bridge applied) | 3/5 | 46% | Bet to 1/9 live pre-race. Prime Power 123.0. Zero prior starts in corpus. |

Both horses were the shortest price in their race and both sat in the bottom
half of the model's ranking. Neither was a first-time starter — both had full
past-performance lines in the Brisnet PP file, parsed and available.

### Frequency estimate

Measured as the share of starters with fewer than two prior starts in the
corpus at the time of their race:

| Track | Window | Thin-history starters |
|---|---|---|
| CT | 2026-07-30 → 2026-08-29 | 140 / 920 = **15.2%** |
| ELP | 2026-08-01 → 2026-08-23 | 656 / 883 = **74.3%** |

CT's figure is the one that matters for routine use: roughly one starter in
seven, or **one to two per race**. ELP's 74.3% is a different problem in
degree — a boutique meet whose runners nearly all ship in — and it is the
reason the Phase 6C ELP model underperforms its home-track counterpart.

Applying the interim warning rule to live cards gives a consistent picture:
9 of 71 horses flagged on CT 2026-08-29 (12.7%), 5 of 57 on CT 2026-07-25
(8.8%).

### Impact on picks

What a reader might get wrong:

* **Treating a low-ranked shipper as a throw-out.** This is the expensive
  error. A rank of 9 of 11 reads as a considered judgment; for a shipper it is
  an absence of judgment. Just Deeds won at 1/5 from rank 4.
* **Reading the model/market disagreement as an edge.** The whole value of
  DPv1's fundamental is that it forms an opinion without looking at the board,
  so disagreement with the price is normally informative. On a shipper it is
  not information, it is a blind spot, and betting against the market on that
  basis is betting on nothing.
* **Trusting P(ITM) as calibrated.** For a shipper the probability is closer
  to a prior than an assessment, and its position in the ranking is largely an
  artifact of how the missing-data block happens to score.
* **Exotics construction.** A shipper wrongly excluded from a tri/super box is
  a structural hole in the ticket, not a marginal one.

### Proposed fix — options

**Option A — PP-backed history fallback in the feature builder.**
When a horse has no corpus history, populate the history block from
`pp_entries_raw` instead of leaving it NaN. The data is already parsed and
stored; the work is a fallback join in `feature_builder_dpv1.py`, a scale
reconciliation, and a retrain.
*Effort: medium-large, roughly 2-4 sessions.*
Risks, both real:
- **Scale mismatch.** Brisnet speed figures are not `computed_speed_figures_dpv1`
  figures. Feeding them into the same column without calibration would put two
  different units in one feature. A mapping has to be fitted on horses that
  appear in both sources.
- **Leak class.** The obvious implementation adds a "history came from PP"
  indicator, which is a missingness-derived feature — precisely the class that
  has bitten this project before. If such an indicator is added it must be
  validated the way the earlier leaks were, not assumed safe.

**Option B — load result charts from the shipper tracks.**
Acquire and load Laurel, Parx, Churchill, Penn National and the rest, so the
shippers stop being shippers. This is the only option that fixes the problem at
its source rather than patching around it.
*Effort: large and open-ended.* Per-track parser validation, an unbounded data
acquisition commitment, a corpus rebuild and a retrain. The track list has no
natural end — CT alone draws from a dozen tracks.

**Option C — coverage-aware shrinkage at prediction time.**
Do not add information; stop the model from spending information it does not
have. When coverage is low, shrink the horse's score toward the field mean
instead of letting the missing-data block push it to the bottom.
*Effort: small, roughly 1 session.* Purely a runtime change, no retrain.
It would not have ranked Just Deeds first, but it would have moved it from
"throw-out" to "unknown", which is the honest answer.

**Option D — warning only.** Implemented; see below.

### Recommended option and why

**Option A**, with **Option C** shipping alongside it as a stopgap.

Option A is recommended because the data already exists in the database. This
is not a data acquisition problem dressed as a modelling problem — the PP files
are parsed, `pp_entries_raw` is populated, and the feature builder simply never
looks at it. That makes A by a wide margin the best value per unit of effort,
and it addresses the actual cause: the history block is empty when a filled
version is sitting one join away.

Option B is the theoretically correct fix and should not be attempted. It
trades a bounded engineering task for an unbounded data-acquisition
commitment, and it would still leave every *new* shipping track blind until
someone noticed and loaded it.

Option C is recommended alongside rather than instead, because it is cheap,
needs no retrain, and is honest in a way A is not yet: until A is validated,
shrinking toward the mean states "no opinion" rather than manufacturing one.

The sequencing matters: C is safe to ship immediately, A needs a retrain and
therefore a Piece 4 promotion decision, which needs a much larger out-of-sample
window than currently exists.

### Interim mitigation — shipped

`card_picks.py` flags likely shippers inline. A horse is flagged when **corpus
coverage is under 60%** *and* it has **fewer than two prior starts** across
CT/ELP/GP/MNR. Both conditions are required: low coverage alone catches
first-time starters, who are genuinely unknown to everybody and not a model
failure; no corpus history alone catches horses the today's-race fields still
describe well.

The warning prints under the horse's reasons block:

```
        ⚠ SHIPPER — check PP directly, model may be blind to prior form
```

Coverage for this test is measured **before** the PP bridge runs. The bridge
lifts a shipper's coverage substantially — 46% to 64% for Outdoor Cat — which
would push the horse back over the threshold and silence the warning on exactly
the runs where the reader has the PP file open. What the warning is about is
what the corpus knows, and that is the pre-bridge number.

Every logged prediction now carries `shipper_flag` and `corpus_coverage`, so
`model_health.py` can eventually report shipper-warning frequency and, once
enough cards accumulate, the ITM rate of flagged horses against unflagged ones.
That comparison is the empirical case for or against Option A.

**This is a warning, not a fix. The model is exactly as blind as it was.**

---

## Gap #2 — Pace Scenario

*Placeholder.* The model reads projected pace per horse but has no explicit
representation of how a race's pace shape collectively advantages front-runners
or closers. To be documented with observed cases.

## Gap #3 — Hot Trainer/Jockey Combo

*Placeholder.* Trainer and jockey win rates enter separately; the combination —
a barn and a rider who win together at a rate neither achieves apart — is not
represented. `pp_entries_raw` already carries `pp_jt_winpct` and
`pp_hot_jt_combo`. To be documented with observed cases.

## Gap #4 — Declining Speed Trajectory

*Placeholder.* `speed_trajectory_3_races` is a single slope and may not
distinguish a horse regressing off a peak from one improving off a low base.
To be documented with observed cases.

## Gap #5 — Brisnet Angles Ingest

*Placeholder.* The PP parser extracts trainer and jockey angle statistics
(`pp_has_strong_trainer_angle`, `pp_positive_trainer_angles`,
`pp_pos_angle_count`, `pp_neg_angle_count`) that no model feature consumes.
To be documented with observed cases.
