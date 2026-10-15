# PP PDF reader audit (2026-10-15, read-only)

**Context.** `brisnet_pp_parser.extract_text` tries `pdftotext -layout` first
and silently falls back to pdfplumber when the binary is not on PATH.
* **Git Bash** has it: `C:\Program Files\Git\mingw64\bin\pdftotext.exe`.
  This is **Xpdf 4.00** (Glyph & Cog) bundled with Git for Windows, not
  poppler.
* **Doug's PowerShell** does not, so it uses pdfplumber.

The same PDF therefore parses differently depending on the shell. See
`PHASE_6E_LOGGING.md` follow-ups #8 and #9. Nothing was changed in this
audit.

## TL;DR

* **Neither reader is right everywhere. They fail on different parts of the
  page.**
  * pdfplumber reads the **race lines** (finish, beaten lengths, last
    distance) far more accurately, and is slightly ahead on the last speed
    figure.
  * pdftotext reads the **header box** (surface and distance records,
    today's weight) and the **block boundaries** (starts, days off,
    first-timers).
* **pdftotext's race-line damage cannot be fixed in the parser. pdfplumber's
  failures can.**
  * Xpdf's layout mode builds a race line from cells of *different rows*. On
    Finny's 08Aug26 line it pairs his fractions, figures and comment with the
    call positions and jockey from his 18Jly26 line. It also drops the
    fraction glyphs (½ ¼ ¾).
  * Everything pdfplumber gets wrong is present in its text. The parser's
    regex or block boundary misses it.
* **Recommendation: standardise on pdfplumber.** It is what every PowerShell
  run already uses, so no install is needed. Make the fallback explicit, and
  queue three parser fixes (below) for Doug's approval.
* **Separate finding: the beaten-lengths feature mixes two different measures.**
  The training corpus's `last_race_beaten_lengths` is the Equibase **margin
  over the next finisher**: the Fin superscript, 0 for a winner, median
  1.25. The PP bridge fills it with Brisnet's **lengths behind the winner**.
  A shipper beaten 22 lengths enters a feature trained on 0–5 values, and the
  coefficient is positive. This explains R5 #1 Brilliant Deal's +0.16 on DED
  10/14, which corrects follow-up #9's reading. It holds whichever reader is
  used. See follow-up #10.

## 1. Which reader gets the model's inputs right

Population: the 9 logged PP cards, 754 horses.

**Truth sources, all independent of both text readers:**
* **Result charts in the corpus.** These cover horses whose last start is in
  the corpus *and* whose days off matches at least one reader, so the chart
  race is the PP's top line.
  * Days off is the card date minus the chart date.
  * Won-last comes from the chart finish.
  * Lengths behind the winner is the sum of the margins of the horses ahead.
  * Last distance comes from the chart distance.
* **The header line itself** (`Life: N`). It gives career starts when N ≤ 8,
  so every start is shown, and identifies first-time starters.
* **A geometry reader**: the SPD value read from the rendered page by the x-position of the
  `SPD` column header. It was validated by eye on 5 horses.
* **Visual reads** of rendered blocks for 8 horses: DED 10/14 Discerner, Here
  Comes Hellcat, Shining Away, Olympiad's Choice; DED 10/10 Carli Bay; CT 8/28
  Sweet Manhattan, Finny; GP 10/2 It's On My Honor.

### Disagreements only: which reader matched the truth

| model input | where it goes | pdftotext right | pdfplumber right | both wrong | how the loser fails |
|---|---|---|---|---|---|
| career starts | bridge, reranker | **11** | 0 | 0 | pdfplumber: the previous horse's oldest line bleeds in (+1 start) |
| days off | bridge, reranker | **5** | 0 | 0 | the same bleed |
| first-timer has no last race (of 96 true first-timers) | reranker `is_first_timer` (−0.46), bridge | **4/4** | 0/4 | — | pdfplumber invents a last race (Olympiad's Choice: 1 start, 102 days, 32 L) |
| races in last 60 days | reranker | 5 differ; pdftotext right on the one checked | | | |
| beaten lengths (vs lengths behind the winner) | bridge | 4 | **216** | 22 | pdftotext: 129 blanks; 109 wrong values, 34 of them off by more than 3 L. pdfplumber: 26 wrong, 24 within 1 L (drops fractions on big margins) |
| won last race | (via beaten lengths) | 4 | **158** | 0 | pdftotext: blank or wrong |
| last distance | bridge (distance change) | 1 | **176** | 0 | pdftotext: always a blank |
| last speed figure (geometry truth, n=292) | bridge | 13 | **21** | 33 | both sometimes take the LP or CR column; pdfplumber gave 110 for Discerner and Carli Bay, a value not in the SPD column |
| surface and distance records | bridge (surface win rate, specialist flags, surface change) | **24/28** values checked by eye | blank on 745/754 | | pdfplumber renders `Fst(105) 6 1 - 2 - 1`, which the regex misses |
| weight change → `equipment_change` | bridge | **2 of 4** checked by eye (1 wrong, 1 blank) | blank on 445 | | pdfplumber does not find today's weight |
| running style, blinkers, first-time Lasix | bridge, reranker | identical | identical | | |

Two notes on the table:
* `equipment_change` is defined as any equipment flag **or** a weight swing of
  2 lb or more. So pdftotext's frequent 1 is by design (e.g. 121 → 118); it is
  not a blinkers misread.
* Both readers get the extremes wrong. Here Comes Hellcat's last race has
  SPD **1** and Fin 6⁴⁹ (beaten 49 lengths); neither reader has either value.

### Display-only fields

| field | pdftotext | pdfplumber |
|---|---|---|
| Prime Power, against the header-line truth | 3 blanks, **29 bleeds** (a first-timer takes the next horse's figure), 2 wrong | **13 blanks** (the cropped header copy cuts it off), 0 bleeds |
| Morning line | `'?'` where the silks column collapses (Hellenic Spirit; DED 10/10 R5 #2, #4, #5; R7 #10) | reads them (16 differ in all) |

Prime Power and ML are not inputs to the model, the bridge or the reranker.

## 2. Recommendation

**Standard: pdfplumber.**
* It reads the race lines faithfully, and the race lines are most of what a
  PP is.
* Every failure it has is recoverable from its own text:
  * **The header box.** Allow `Fst(105)` without a space, and find today's
    weight.
  * **The block boundary.** Stop the left-crop block from starting on the
    previous horse's last race line. This removes phantom starts and phantom
    last races on first-timers.
  * **Prime Power.** Read it from the full-layout header line by name, not
    from the cropped copy. Also fix the map regex's `[A-Z][A-Za-z]`, which
    skips "C C", "E Z" and "I'm".
* Doug's PowerShell already uses it, so no install is needed and DED 10/14,
  CT 10/1, GP 9/4 and GP 10/2 stay on the standard reader.

> **Applied 2026-10-15**, one commit each: block boundary `87ee6fa`, header
> box `c1143dd`, Prime Power `02c0163`. Two corrections to the description
> above:
> * **Header box.** The record regex already accepts `Fst(105)`. The real
>   cause is that the box sits on the right half of the header, outside the
>   left-crop block. The fix reads it by position.
> * **Today's weight.** It was **not** applied. Filling it turns on a
>   weight-swing rule inside `equipment_change_flag` that the corpus does not
>   have; see `PHASE_6E_LOGGING.md` follow-up #11.
>
> Per-fix counts are in the commit messages.

These three fixes are parser changes. They were proposed, not applied, and
each will change P(ITM) on the horses it touches, so each needs Doug's go and
its own before/after record.

**Why not pdftotext.** Its errors come from Xpdf's layout engine
interleaving rows, so no downstream fix recovers them. It also gives
**confidently wrong** beaten lengths (34 off by more than 3 L) and blank
last distance on 176 of the 347 chart-checked horses.

**If Doug still prefers pdftotext:**
* Do **not** install poppler. Poppler's pdftotext is a different layout engine
  and would be a third, untested variant.
* Point the parser at the exact binary that produced the numbers above:
  `C:\Program Files\Git\mingw64\bin\pdftotext.exe` (Xpdf 4.00). Use an
  explicit path setting (see the proposal), not a PATH edit. Adding Git's
  `mingw64\bin` to the PowerShell PATH would also put Git's `curl`,
  `openssl` and other tools in front of the Windows ones.
* If a PATH edit is still wanted, append the directory, don't prepend it:
  `[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";C:\Program Files\Git\mingw64\bin", "User")`,
  then open a new PowerShell and check with `Get-Command pdftotext`.

## 3. Never fall back silently (APPLIED 2026-10-15)

> Applied as proposed, with two additions: both CLIs print
> `PP text reader error: ...` instead of a traceback, and the header line reads
> `PP text reader: bridge <reader>; staged rows <reader>`. Verification results
> are in `PHASE_6E_LOGGING.md`, follow-up #8. The proposal text below is kept as
> written.

**`brisnet_pp_parser.py`**
* `extract_text(filepath, reader=None)`. The reader comes from the argument,
  then the env var `BENTER_PP_READER`, then the default `"pdfplumber"`.
* With `"pdftotext"`, it uses `BENTER_PDFTOTEXT` (a full path) if set,
  otherwise PATH.
* If the requested reader is unavailable, or pdftotext fails or returns
  empty, it **raises** with a message naming the reader, the path tried and
  the fix. **No fallback.**
* `parse_pp_file` adds `text_reader` (for example `pdfplumber 0.11.9` or
  `pdftotext Xpdf 4.00 @ <path>`) to its result.

**`load_pp_card.py`**
* Prints `PP text reader: …` on load and on `inspect`.
* Stores it in a new nullable `pp_entries_raw.pp_text_reader` column, added
  by `ensure_pp_raw_table` with `ALTER TABLE ... ADD COLUMN`. Existing rows
  stay NULL; their reader is recorded in section 4 instead.
* `parse_pp_files.py` inherits the same behaviour.

**`card_picks.py`** (display only)
* A header line, ` PP reader: pdfplumber 0.11.9 (card staged with: pdfplumber)`.
* A **warning** when the bridge's reader differs from the reader the card was
  staged with.
* The prediction log gets no new field, so the Piece 2 and Piece 3 readers
  are untouched.

**Protected-file impact.** None of the protected artifacts are touched:
`dpv1.pkl`, `dpv1_3track.pkl` and `dpv1_pp_reranker.pkl`. Their sha256 is
recorded before and checked after, as in the 2026-09-12 forward test. The
files edited are the parser, the loader and the `card_picks` header. The
parser was fenced in the last two briefs, so this needs an explicit go.

**Verification that P(ITM) does not move on cards loaded with the chosen
reader:**
1. **Parse identity.** For every PP PDF in the catalogue, compare
   `parse_pp_file` before (pdfplumber forced by stubbing pdftotext, as in this
   audit) with after (`reader="pdfplumber"`). The two must be deep-equal
   except for the new `text_reader` key.
2. **Card identity.** On a scratch DB copy, re-run
   `card_picks.py --pp-file … --log-file <scratch>` for each pdfplumber-staged
   card: CT 10/1, GP 9/4, GP 10/2, and DED 10/14 on `pre-ded1014.bak`. Run
   it with the old code (in PowerShell) and the new code, at the same seed
   (6001) and iters (10000). `final_p_itm`, `base_p_itm` and `rank` must be
   **bit-identical** for every horse.
3. **Guard test.** Set `BENTER_PP_READER=pdftotext` with a bad
   `BENTER_PDFTOTEXT`. The loader must exit non-zero with the message and
   write nothing to the DB (row counts unchanged).
4. **Protected sha256** unchanged.

Cards staged with pdftotext (CT 8/28, CT 8/29, ELP 8/22, ELP 8/23, DED 10/10)
are **expected** to move if re-run, because the reader changes. Their logged
records stand as logged; nothing is re-logged.

## 4. Which reader each logged card used

* **Staged.** This is what `pp_entries_raw` matches. For every horse where
  the two readers differ, the staged row equals one reader exactly. No card
  is mixed.
* **Bridged at run time.** I re-ran the bridge both ways on the current
  features and compared the result to each run's logged per-horse coverage
  lift. Runs logged before `corpus_coverage` existed cannot be checked this
  way.

| card | staged with | horses deciding (differ / matched) | logged run(s) bridged with |
|---|---|---|---|
| CT 2026-07-25 | — (no staged rows; card predates staging) | — | not determinable |
| CT 2026-08-28 | pdftotext | 86 / 86 | not determinable (no `corpus_coverage` logged; features have drifted since) |
| CT 2026-08-29 | pdftotext | 52 / 52 | 14:51 and 8/31 08:17 runs: **pdftotext** (7–0). Earlier runs that day: not determinable |
| ELP 2026-08-21 | — (no PP file on disk) | — | not determinable |
| ELP 2026-08-22 | pdftotext | 58 / 58 | not determinable |
| ELP 2026-08-23 | pdftotext | 62 / 62 | not determinable (3–0 pdfplumber; too few horses to call) |
| GP 2026-09-04 | pdfplumber | 40 / 40 | no-bridge runs (see 6E) |
| CT 2026-10-01 | pdfplumber | 55 / 55 | no-bridge run (see 6E) |
| GP 2026-10-02 | pdfplumber | 54 / 54 | 08:49: no-bridge (superseded). 09:15 record run: **pdftotext** (44–0) |
| DED 2026-10-10 | pdftotext | 53 / 53 | both runs: **pdftotext** (12–1) |
| DED 2026-10-14 | pdfplumber | 59 / 59 | **pdfplumber** (74–0; R5 reasons reproduced exactly) |

The counts are horses whose logged coverage lift matches one reader's
simulated lift and not the other's. Horses where both readers fill the same
cells cannot decide either way. "Neither" mismatches come from feature drift
since the run.

**GP 10/2 is split.** It was staged with pdfplumber, but its record run
bridged with pdftotext. The staged rows were re-staged after the run, which is
why the logged page shows Prime Power for R Firebird, D Orbie's Girl and I'm
Chill while the DB now has blanks. Under the proposal, `card_picks` would warn
about a mismatch like this.

The staged reader tracks the shell that ran `load_pp_card`. Git Bash
(Claude sessions) gives pdftotext, and PowerShell gives pdfplumber.
