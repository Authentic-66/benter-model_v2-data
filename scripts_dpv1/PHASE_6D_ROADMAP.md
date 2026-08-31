# Phase 6D — model gap roadmap

A running catalog of things DPv1 cannot see, found during live use of the
Phase 6B card runner. Each entry is written when a gap shows up in a real
card, with the observed cases attached, so that the fix is argued from
evidence rather than from intuition.

This is a catalog, not a work plan. Nothing here is scheduled. Documented so
far: **Gap #1 (Shipper Blindness)** and **Gap #6 (Maiden Race Chaos)**, each
with an interim warning shipped in `card_picks.py`. Gaps #2-#5 are headers only
and get filled in as more races are cataloged.

The two documented gaps overlap: a maiden race full of ship-ins triggers both,
and both trace to the same root cause — history features keyed on `horse_id`
against a corpus that holds four tracks. CT 2026-08-29 R6 is the worked example
of the compound case.

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

The data to fix this is already parsed. `pp_entries_raw` holds 75 PP-derived
columns including `pp_career_starts`, `pp_avg_speed_last3`,
`pp_speed_fig_slope`, `pp_best_speed`, `pp_dist_starts`/`pp_dist_wins`,
`pp_surface_starts`/`pp_surface_wins`/`pp_surface_winpct`, `pp_jt_winpct` and
the trainer/jockey angle counts, and where a card has been ingested those
columns are well populated — `pp_career_starts` 100%, the speed block 91.5%,
`pp_prime_power` 95.8%. The feature builder never consults any of it.

**Corrected 2026-08-31.** An earlier version of this entry said the data was
"already in the database", which overstated it. The table holds only **4,318
rows across a handful of dates**, because it is populated by `load_pp_card.py`
and that is not being run routinely. CT 2026-08-29 has **zero rows** in it: its
PP file was parsed directly at prediction time by `pp_feature_bridge` and never
ingested. So Option A has an unmet prerequisite — routine PP ingest — without
which it would have nothing to read on precisely the cards that need it. Treat
that ingest as a small separate task that must land first.

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

> **PREREQUISITE — do not start Option A until this is done.**
> `load_pp_card.py` must be fixed so that PP cards are actually ingested into
> `pp_entries_raw` as a matter of routine. The table currently holds 4,318 rows
> across a handful of dates and has **zero rows for CT 2026-08-29**, whose PP
> file was read directly at prediction time by `pp_feature_bridge` and never
> stored. Building the fallback join first would produce a feature that is NULL
> on exactly the cards it exists to serve, and worse, would look like it worked
> on the few dates that happen to be loaded. Fix the ingest, confirm coverage
> across recent cards, then build the join.
> *(Agreed with Doug, 2026-08-31.)*

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

---

## Gap #6 — Maiden Race Chaos with Underraced Horses

### What the model can't see

A horse that has barely run, and — more damagingly — a *field* that has barely
run. Maiden races are non-winners by definition and are weighted heavily toward
first- and second-time starters. DPv1's signal lives in its history block, so a
maiden race is the case where the model has structurally least to work with,
and the shortfall is not confined to the individual blank horses.

### Root cause

Three mechanisms compound.

**1. Thin history per horse.** Every history feature is built from `entries`
and `computed_speed_figures_dpv1` keyed on `horse_id`. A horse with zero to two
starts has zero to two rows, so career win%, ITM%, `last_3_avg_finish`,
`speed_trajectory_3_races` and the rest are empty or computed from a sample too
small to mean anything.

**2. The model cannot tell "never raced" from "never raced here."**
`career_starts` is corpus-derived. A first-time starter reads 0, and so does a
shipper with twenty runs at Laurel. These are opposite situations — one horse
is unknown to everybody, the other is well documented somewhere the corpus
cannot see — and the model treats them identically. On CT 2026-08-29 R6 the
four horses showing 0 career starts were all also shipper-flagged; nothing in
the feature set distinguishes which of them had actually never run.

**3. Race-level contamination.** Pace projection (`expected_pace_shape`,
`pace_pressure_in_race`, `early_pace_position_projected`), class-of-field and
the field-relative features are computed *across the whole field*. A few blank
runners degrade those estimates for the experienced horses standing beside
them. This is why the failure is not confined to low-coverage horses: on
CT 2026-08-29 R3 the top pick had **80%** coverage and still finished 5th, and
on R5 the top pick had 86% and finished 4th.

### How it manifests in picks

The model's top pick in a maiden race is frequently the horse that simply has
the most data rather than the most ability — an experienced maiden ranked first
because the alternatives are blank. The winner then comes out of the blank
block, where the model had no opinion to offer. On CT 2026-08-29 the winners of
R5 and R6 were the model's rank 2 and rank **7**; R3's winner was disqualified.

### Observed cases

All three from CT 2026-08-29, the card that prompted this entry.

| Date | Race | Horse (top pick) | Model rank | ML | Coverage | Notes |
|---|---|---|---|---|---|---|
| 2026-08-29 | CT R3 MSW WV-bred | #3 Stettie Hayesen | 1 of 7 | 9/5 | 80% | Finished **5th**. Race won by #5 Conejo Dorado (2 career starts) who was **disqualified** — the race has no recorded winner in the DB and is excluded from WIN denominators. 5 of 7 starters had under 3 career starts. |
| 2026-08-29 | CT R5 MSW WV-bred | #7 Goldeck | 1 of 12 | 7/2 | 86% | Finished **4th**. Winner #10 Knight Sage (6/5 favourite) was model rank 2. 8 of 12 starters underraced. Doug reports the 3-track model picked this winner; no 3-track run is in the prediction log, so that is unverified here. |
| 2026-08-29 | CT R6 MSW open | #6 Improbable Dream | 1 of 10 | 15/1 | 64% | Finished **6th**. Winner #8 Zaptastic (26 career starts) was model rank **7**. 6 of 10 underraced, **4 also shipper-flagged** — the compound-broken race, Gap #1 and Gap #6 firing together. |

The card's three maiden races went **0 for 3** on top-pick ITM. Its five
non-maiden races went 3 of 5.

### Frequency estimate

Across all results-loaded races in the corpus, share with at least one starter
under 3 corpus career starts:

| | races | with an underraced starter |
|---|---|---|
| Maiden (all MAIDEN* types) | 9,081 | 8,934 = **98.4%** |
| Non-maiden | 20,084 | 14,199 = 70.7% |

Maiden races are **9,081 of 29,165 = 31.1%** of the corpus, so this is roughly
one race in three.

**The presence of a single underraced starter is close to vacuous on maidens.**
At 98.4% it barely narrows anything. The discriminating measure is the *share
of the field* that is underraced: median **67%**, mean 65%, and 44.1% of maiden
races have more than three-quarters of the field underraced.

The flag was moved onto that share on 2026-08-31. Thresholds evaluated against
the whole corpus, and against the three observed cases the threshold has to
keep (R3 = 5/7 = 71.4%, R5 = 8/12 = 66.7%, R6 = 6/10 = **60.0%**):

| rule | maidens flagged | share of all races | keeps R3/R5/R6? |
|---|---|---|---|
| any underraced starter (original) | 8,934/9,081 = 98.4% | 30.6% | yes |
| share >= 50% | 6,493 = 71.5% | 22.3% | yes |
| share > 60% | 5,127 = 56.5% | 17.6% | **no — drops R6** |
| **share >= 60% (adopted)** | **5,302 = 58.4%** | **18.2%** | **yes** |
| share >= 67% | 4,455 = 49.1% | 15.3% | no — drops R5 and R6 |
| share >= 75% | 4,007 = 44.1% | 13.7% | no — drops all three |

**The comparison is `>=`, not `>`, and that is load-bearing.** R6 — the worked
compound-chaos case, the one race on the card where four runners were also
shipper-flagged — sits at exactly 0.60. A strict `>` would drop precisely the
race the threshold was chosen to catch.

`>= 60%` cuts maiden flagging from 98.4% to **58.4%**, and flagged races from
30.6% to **18.2%** of all racing — roughly one race in five instead of one in
three. Worth being straight about the trade-off: it still flags a majority of
maiden races. Getting below half needs `>= 67%`, which drops R5 and R6. Given
that both of those are cases Doug identified from live use, the observed cases
win over the round number.

### Impact on picks

* **Trusting a top pick that is closer to a coin flip.** A rank of 1 in a
  maiden looks identical on the page to a rank of 1 in an allowance, and it is
  not the same object. On CT 2026-08-29 R6 the winner was the model's 7th
  choice.
* **Mistaking data availability for ability.** The top pick in a thin maiden is
  often just the horse the corpus knows. That is a selection artifact, not an
  assessment.
* **Exotics.** With most of the field blank, the model's ordering below the top
  few ranks carries little information, so tickets built off it are close to
  random within the blank block.
* **DQ interaction.** Maiden races with underraced horses appear more prone to
  disqualification (R3 here). Piece 2 excludes no-recorded-winner races from
  WIN denominators, so those races quietly leave the win-rate sample.

**What the aggregate evidence does *not* yet show.** The premise that the model
performs materially worse on maidens is **not currently supported by the scored
log**, and this entry should not claim it does:

| window | maiden | non-maiden |
|---|---|---|
| all scored races | 12/18 = **66.7%** | 21/37 = 56.8% |
| out-of-corpus only | 7/12 = **58.3%** | 16/25 = 64.0% |

The direction flips depending on the window and both samples are far too small
to separate. The all-scored maiden figure is inflated by two in-corpus cards
(CT 7/25 went 3/3, ELP 8/21 2/3) that the model trained on. The out-of-corpus
split is directionally consistent with the hypothesis — 5.7pp worse — on twelve
maiden races, which is nothing.

So the case for this gap currently rests on **mechanism and on the three
observed cases, not on aggregate evidence**. `maiden_flag` is now logged
precisely so that Piece 3 can accumulate that evidence and settle it.

### Proposed fix — options

**Option A — a maiden-specific model.** Train a separate model on maiden races
only. The corpus has 9,081 of them with results, which is enough data to fit on.
*Effort: large, 2-4 sessions plus a retrain and a promotion decision.*
Risk: splits an already-thin corpus into two smaller ones, and the aggregate
evidence that a split is warranted does not yet exist.

**Option B — PP-backed history bridge.** The same fix as Gap #1 Option A: fill
the history block from `pp_entries_raw` when the corpus has nothing.
*Effort: medium-large, shared with Gap #1.*
Two caveats specific to this gap. It does **nothing for a true first-time
starter**, who has no past performances anywhere. And it has an unmet
prerequisite: `pp_entries_raw` is only populated for cards that have been run
through `load_pp_card.py`, which is not happening routinely — the table holds
4,318 rows across a handful of dates and has **zero rows for CT 2026-08-29**,
whose PP file was read directly at prediction time and never ingested.

**Option C — field-experience features. ← APPROVED as the preferred fix
(Doug, 2026-08-31).** Give the model an explicit representation of how thin the
field is: share of field under N career starts, count of true first-time
starters, and — using `pp_career_starts` — the distinction between a
first-timer and a shipper that the corpus cannot make.
*Effort: medium, roughly 1-2 sessions plus a retrain.*
Note the third component inherits Option B's prerequisite: `pp_career_starts`
is only readable for cards ingested into `pp_entries_raw`. The first two
components have no such dependency and can be built immediately.

**Option D — runtime shrinkage on thin fields.** When most of a field is blank,
shrink the spread of P(ITM) toward uniform rather than presenting a confident
ordering built on nothing.
*Effort: small, no retrain.* Same shape as Gap #1 Option C and could share an
implementation.

**Option E — warning only.** Implemented; see below.

### Recommended option and why

**Option C, then Option B. — Approved by Doug 2026-08-31.**

Option C is recommended first because the model currently has **no
representation of field-level experience at all**. It scores a race where eight
of twelve runners have never started exactly as it scores a race where all
twelve are seasoned, and mechanism 3 above — race-wide contamination of pace
and class estimates — is a direct consequence. That is the part of this gap
that is genuinely distinct from Gap #1, and it is a feature addition rather
than a corpus split, so it is cheap to test and easy to reverse.

Option B follows because it is shared work with Gap #1 and would be built once
for both. Its prerequisite — routine PP ingest — should be treated as a
separate small task, since without it Option B has no data to read on the cards
that need it most.

**Option A is not recommended yet.** A dedicated maiden model is the kind of
change that needs evidence first, and the scored log currently does not show
maidens underperforming. Revisit once `maiden_flag` has accumulated a few
hundred races and Piece 3 can report the split with a straight face.

### Interim mitigation — shipped

`card_picks.py` prints a race-level warning immediately under the race header
when the race type starts with `MAIDEN` **and at least 60% of the field** has
fewer than 3 corpus career starts. NULL counts as underraced — the feature
builder writes NULL when it found no history at all, which is the most
underraced a horse can be.

```
--- Race 6  (10 horses)  MAIDENSPECIALWEIGHT  1430  Dirt  $32,900
    ⚠ MAIDEN with underraced horses — high variance, model recommends handicapping directly
      (6 of 10 = 60% have under 3 career starts)
    feature coverage 81%
```

The count is printed beside the warning so a reader can see how thin the race
actually is rather than taking the flag on faith — 60% of a field and 100% of
it are different races.

Every logged prediction carries `maiden_flag` (race-level, repeated on each row)
and `underraced_share`, alongside `shipper_flag` and `corpus_coverage`.

Predictions are still produced for maiden races and the output is otherwise
unchanged. **This is a warning, not a fix.**

Threshold history: the rule originally fired on *any* underraced starter, which
hit 98.4% of maiden races and functioned as a category label rather than a
discriminator. Moved to the share-based rule on 2026-08-31 — see the frequency
section above for the thresholds evaluated and why `>=` matters.

Effect on recent cards:

| card | old rule | new rule |
|---|---|---|
| CT 2026-08-29 | R3, R5, R6 | **R3, R5, R6** (all three observed cases kept) |
| CT 2026-08-28 | none | none (no maiden races) |
| CT 2026-08-27 | R1 | **none** |
| CT 2026-07-25 | R1, R4, R9 | **R4** |
| ELP 2026-08-22 | R1, R5, R6, R9 | R1, R5, R6, R9 |
| ELP 2026-08-23 | R2, R3, R4, R5, R7, R9 | R2, R3, R4, R5, R7, R9 |

At CT the rule now discriminates — CT 7/25 drops from three flags to one, CT
8/27 from one to none — while the compound cases survive. At ELP nothing
changes, and that is a finding rather than a failure: ELP maiden fields really
are more than 60% invisible to the corpus, because ELP's runners ship in. Gap
#1 and Gap #6 are the same problem there.
