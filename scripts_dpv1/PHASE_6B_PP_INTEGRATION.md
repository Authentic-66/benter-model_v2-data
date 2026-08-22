# Phase 6B — ELP Integration, PP Parser, Live Handicapping

Phase 6A left live use blocked on one thing: DPv1's 95 features are built from
the result corpus, so a race that has not run yet has no features, and hand
entry supplied only 26 of 95 — which measurably reorders the field rather than
just blurring it.

Phase 6B unblocks it. Feature coverage on a live card went from **27% to 71%**,
and the Sunday ELP predictions exist and are preserved.

---

## What shipped

| File | Purpose |
|---|---|
| `load_pp_card.py` | **new** — write an unraced PP card into `racing_full.db` so the feature builder can score it |
| `pp_feature_bridge.py` | **new** — fill DPv1 slots the corpus left NULL, from PP data |
| `card_picks.py` | **new** — top-4 ITM rankings for a card, the Phase 6B deliverable |
| `brisnet_pp_parser.py` | ELP registered in the filename→track map |
| `parse_pp_files.py` | ELP added to the PP directories and corpus tracks |
| `dpv1_common.py` | `TRACK_CODES` extended with ELP |
| `predict_race.py` | new `--pp-file` flag |

Deliverable: `scripts_dpv1/picks/ELP_2026-08-23_20260821-2330.{txt,csv}`

---

## 1. ELP loaded

173 result PDFs (2021–2026) parsed with the existing Equibase parser,
**0 errors**, into `racing_full.db`.

| year | days | races | entries | odds coverage | finish coverage |
|---|---:|---:|---:|---:|---:|
| 2021 | 31 | 251 | 1,709 | 99.4% | 98.3% |
| 2022 | 23 | 193 | 1,528 | 100.0% | 99.4% |
| 2023 | 41 | 380 | 2,743 | 99.0% | 98.4% |
| 2024 | 25 | 228 | 1,937 | 100.0% | 99.3% |
| 2025 | 27 | 251 | 1,867 | 98.7% | 97.9% |
| 2026 | 26 | 237 | 1,732 | 98.5% | 98.1% |
| **total** | **173** | **1,540** | **11,516** | **99.2%** | — |

Integrity matches the existing tracks (GP 99.9% odds, CT 99.4%, MNR 99.7%).
Average field 7.48. ELP runs a genuine turf course — 521 of 1,540 races on
turf, unlike the CT/MNR bullrings.

Doug estimated 500–700 races per meet; the actual figure is ~250/year. The
Ellis meet is a short July–August stand, so the corpus is 1,540 races rather
than the ~3,500 the estimate implied.

Nine result files parsed to zero entries. All nine are cancelled cards
(`Cancelled - Weather`), not parser failures — checked directly against the
PDF text.

Speed figures and the full DPv1 feature table were rebuilt over the expanded
corpus: **219,593 rows**, up from 207,976.

> **Train/serve note.** The model was trained on features computed *without*
> ELP. Rebuilding with ELP included shifts cross-track connection rates
> slightly for trainers and jockeys who ran there. This is a real if small
> distribution shift, accepted deliberately: the alternative is that ELP horses
> have no history at all, which makes ELP predictions worthless.

---

## 2. Parser port — already done, and verified

The task list called for porting `brisnet_parser_v2.py` (2,417 lines) from the
old repo. **Phase 5A already did this** — `scripts_dpv1/brisnet_pp_parser.py`
is that port at 2,052 lines. Verified rather than repeated:

- `IRON_TRAINERS` / `SIRE_SIGNALS` / `IRON_HORSES` / `TRAINER_RULES` are gone.
- Morning line is emitted as `pp_ml_decimal`, one of 57 feature columns, and is
  **not** wired into any DPv1 model slot. `card_picks.py` prints it beside the
  model's opinion, never inside it. The anchor discipline holds.
- Output is entry-grain against `racing_full.db`, not `benter_model.db`.

Phase 6B added ELP to the filename→track map and to the PP directory list.

One real parser gap was found and worked around rather than patched. Its
race-header regex returned **empty conditions for 2 of the 9 races** on the
Sunday card — `TMElPTurfB175K` (a named stakes with no class token) and
`Moc 50000`. A race with no conditions gets no class, no distance and no
surface, which would have silently produced three unscoreable races.
`load_pp_card.headers_from_text` re-extracts the header from the raw text
instead, recovering all nine. It identifies the track name as the longest
common word-prefix across every page header, which avoids hardcoding a track
list.

---

## 3. PP corpus parsed

**58 of 65 files OK, 4,318 starters staged.**

| track | files OK | failed |
|---|---:|---:|
| GP | 20 | 5 |
| CT | 13 | 2 |
| FP | 12 | 0 |
| EVD | 11 | 0 |
| MNR | 1 | 0 |
| ELP | 1 | 0 |

The 7 failures cost almost nothing. Five are alternate Brisnet products for a
race day already covered by a working file — `gpx0509j/t/v/x.pdf` all failed,
but `gpx0509a/p/u/y/z.pdf` parsed the same card. Only two represent real loss:
`ctx0508x.pdf` (no working sibling) and `CT20260618()_4x9PPs.pdf` (filename
date unparseable). The `y`-suffix "Ultimate PP" layout is what the parser
handles; the others are different products.

Matched into `entry_pp_features`: **1,680 entries** — GP 1,010, CT 569,
ELP 101. Unmatched staging rows are accounted for: 1,643 `no_corpus`
(FP and EVD have PP files but no result corpus), 450 `no_race` (PP card dates
past the result coverage window), 278 `no_horse`, 267 `duplicate_card`.

---

## 4. Feature coverage — the core result

Sunday's ELP card, 101 horses, measured against DPv1's 95 features:

| source | coverage | per-horse median |
|---|---:|---:|
| Phase 6A hand entry | 27% | — |
| DB path after loading the card | 65.5% | 74% |
| **+ PP bridge** | **71.0%** | — |

The 65.5% splits sharply: horses the corpus has seen before come out near 88%,
the rest at 40%. The boundary is exactly the **58% of the field with prior
starts in `racing_full.db`**.

The other 42% are mostly *not* first-time starters — they are shippers from
Churchill, Indiana Grand and Kentucky Downs, tracks outside this corpus. To
DPv1 they were indistinguishable from debut runners, because every
`last_race_*` and `career_*` column was NULL and the preprocessor's
`{col}__missing` indicators fired exactly as they would for a real debut. That
is a *wrong* signal, not merely a missing one, and it is what the bridge exists
to fix. 533 cells filled across 19 features; all 101 horses matched to the PP
file.

Which drove a design decision worth recording. Brisnet's speed figures
correlate with DPv1's computed figures at only **r=0.40** on 1,206 entries
carrying both (`dpv1 = 58.4 + 0.28 × brisnet`, R²=0.16). The calibrated fill is
so shrunk toward the mean that it carries almost no ranking information — and
it is still worth making, because "raced before, ran about average" is a far
better description of a shipper than "never raced". **The value of the bridge
is in switching off a false first-time-starter signal, more than in the numbers
themselves.** The regression is applied rather than a raw copy because the raw
scales differ by ~8 points.

Not bridged, deliberately: `class_score_change_from_last` (Brisnet's delta is
purse dollars, DPv1's is a ladder position — only the UP/DOWN/SAME direction
transfers), and anything derived from morning line.

`pp_career_starts` saturates at 10 because a Brisnet PP prints ten past-
performance lines. It is bridged for its has-raced signal and flagged as
right-censored rather than treated as a true career count.

Still NULL for the whole Sunday card: `track_dirt_bias_90d`,
`track_turf_bias_90d`, `weight_lbs`, `weight_change_from_last_race`,
`track_distance_par_time_sec`.

---

## 5. Does the model work at a track it never saw?

This is the question that decides whether Sunday's picks mean anything. ELP was
never in training, and there are now 1,211 completed ELP races with full
features — a clean out-of-sample track test.

| track | races | base ITM% | AUC | top-pick ITM% | top-pick WIN% | lift |
|---|---:|---:|---:|---:|---:|---:|
| CT | 6,009 | 40.7 | 0.701 | 66.9 | 30.7 | +26.2 |
| GP | 8,563 | 39.1 | 0.696 | 63.9 | 28.1 | +24.9 |
| MNR | 4,332 | 43.9 | 0.697 | 67.2 | 29.2 | +23.3 |
| **ELP** | **1,211** | **37.3** | **0.655** | **56.4** | **22.3** | **+19.1** |

It generalises, and it generalises worse. AUC 0.655 against 0.696–0.701 on the
trained tracks; the top pick hits the board 56.4% of the time against a 37.3%
base rate. Stable across years (0.637–0.664, no trend). Real signal, roughly
three-quarters of the edge it has at home.

Accuracy tracks coverage, on ELP races where the result is known:

| race feature coverage | races | top-pick ITM% | top-pick WIN% |
|---|---:|---:|---:|
| ≤60% | 376 | 53.2 | 18.1 |
| 60–70% | 278 | 57.2 | 23.7 |
| 70–80% | 328 | 54.6 | 21.0 |
| 80–90% | 206 | 63.6 | 28.2 |
| >90% | 23 | 60.9 | 39.1 |

**Sunday's card averages 71% coverage, so the honest expectation is a top pick
that hits the board roughly 55–57% of the time against a ~37% base rate.**
Useful as a second opinion. Not a system.

---

## 6. Sunday ELP predictions — 2026-08-23

Preserved at `scripts_dpv1/picks/ELP_2026-08-23_20260821-2330.{txt,csv}`,
generated before the races ran, for validation afterwards.

| R | top pick | P(ITM)% | ML | coverage |
|---|---|---:|---|---:|
| 1 | #4 Tiz Freedom | 44.8 | 5/2 | 70% |
| 2 | #2 Honor Bound | 45.0 | 12/1 | 75% |
| 3 | #2 Positive Equity | 52.7 | — | 78% |
| 4 | #4 She's Gotta Go | 41.4 | 6/1 | 77% |
| 5 | #1 Ever Forward | 57.7 | 3/1 | 70% |
| 6 | #3 Military Cruiser | 48.2 | 7/2 | 77% |
| 7 | #1 Ali's Glory | 33.7 | 12/1 | 65% |
| 8 | #4 Next Up | 47.7 | 15/1 | 80% |
| 9 | #3 Ciarlatano | 30.2 | 9/2 | 57% |

Race 9 is under 60% coverage — a 15-horse 2yo maiden-optional-claiming turf
field where most runners have no corpus history. Its ranking is weak and the
file says so.

Races 2 and 8 are where the model most disagrees with the morning line
(12/1 and 15/1 top picks). Per Phase 6A, treat a disagreement as a question
worth investigating, not as a bet — the EV path was backtested and does not
work.

No ticket EV is produced anywhere in Phase 6B, by design.

---

## 7. Recommendation for Phase 6C

**Validate before building anything.** Sunday's nine predictions are recorded.
Score them Monday: did the top pick hit the board near 55–57%? Nine races is
far too few to conclude anything on its own, but it is the start of a live
record, and the tooling to extend it costs one command per card.

Ranked by expected value:

1. **Accumulate live cards.** Same command per race day. Thirty cards gives
   ~270 races, enough to tell whether live coverage behaves like the
   historical 71%-coverage stratum. This is the highest-value and cheapest
   next step.

2. **Widen the result corpus, not the feature list.** The binding constraint
   is the 42% of the field with no history here, and the fix is loading the
   tracks ELP ships from — Churchill, Indiana Grand, Kentucky Downs. That
   converts bridged rows into real feature rows and would raise coverage more
   than any parser work.

3. **Retrain including ELP.** Deferred correctly in Phase 6B, but the model
   scores ELP with `track_code` all-zeros and no ELP bias figures, and the
   0.655-vs-0.70 AUC gap is partly that. A retrain over the 219,593-row corpus
   would close some of it — and would also remove the train/serve shift noted
   in §1.

Not recommended: more PP feature extraction. Phase 5A found PP features carried
no significant residual information over chart features, and §4 here found
Brisnet speed figures correlate with DPv1's at r=0.40. The PP file's value in
this pipeline is telling us *who is entered and that they have raced* — not
supplying better numbers.
