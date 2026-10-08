# Spec: Multis builder (`multis.py`)

Status: **draft for Paolo's review** (2026-10-08). Nothing gets built until he approves it.
Never places bets. Read-only on both sheets; the only write is an optional "Multis plan" tab (dry run first).

## 1. Purpose
Turn the open tips for a betting day into a **proposed set of doubles / trebles / system bets spread across his books**, so that:
- every selection carries a similar share of the money (no accidental big position on one match),
- no two tickets look alike and no book sees the same pattern (account longevity),
- he sees the money at risk and "if k of n win → P&L" **before** he places anything,
- price drift is visible leg by leg once he types in what the book actually shows.

It proposes. He places, then logs with the existing `log-bets` flow. Advise, don't control: every flag is information, nothing blocks.

## 2. What it reads (read-only)
| Source | Used for |
|---|---|
| Shared sheet, Sheet1 | Candidate tips: Status **Upcoming** (and `--include-in-play`, `--include-no-kickoff`). Also settled tips, for the track-record line. |
| Private book, Accounts | Active books and currency. |
| Private book, Bets/Legs | What he already holds: stake and tickets per tip / per match / per book; which pairs and triples he has already combined. |
| Private book, Balances | Cash per account, to warn if a plan needs more than the book holds. |
| `--seen seen.tsv` (optional) | Odds he actually sees at a book (§6). |

## 3. Core rules
1. **Position = match.** All tips on one match are one position (same-match tips are correlated and books usually block them). Ladders (Over 2.5 / 2.75 / 3.0, Under 3.0 / 3.5) are *rungs* of one position.
2. **One leg per match per ticket.** Hard rule of the builder (it is how books accept multis).
3. **Rung choice: rotate.** Across tickets the builder rotates the rungs, so the match's money is split over its rungs instead of all on one. `--rung lowest|highest|first` fixes it instead. Different markets on one match (e.g. Handicap and Total) are also just rungs of that position.
4. **Held exposure is respected.** Matches he already holds in open tickets are shown with their ₱ and ticket count and are **de-prioritised** when slots are short (not excluded; `--exclude-held` drops them).
5. **No repeats of past patterns.** A pair/triple already combined in an open or settled ticket is penalised, as is the same pair appearing in two tickets of this plan.

## 4. What Paolo decides (inputs)
```
python multis.py --day 2026-10-10 \
    --plan double:8000 --plan treble:6000 --plan system3/5:4000 \
    [--books 1xbet:50,bet88:20,747-live:20,winzir:10] [--unit 1000]
```
- **`--day`**: the betting day = kickoffs from 12:00 PHT that day to 12:00 next day (late-night European kickoffs belong to the evening before). Default today.
- **`--plan FORMAT:TOTAL_STAKE`** (repeatable): the total ₱ he has decided to spend on that format. Formats: `double`, `treble`, `4fold`, `system k/n` (e.g. `system3/5`). **Total daily stake is the sum, fixed in advance, and never exceeded.**
- **Tickets per plan:** `TOTAL / --unit` (default ₱1,000) rounded; `--tickets double:6` overrides. Stakes are equal per ticket in a plan. `--jitter` varies them ±10% in whole ₱10 (sum unchanged), because round equal stakes are one of the signals books use.
- **`--books`**: share of the stake per book (default: equal across Active books). 1xbet is one book for spreading purposes; the account used inside it (PHP / USDT / TRX) defaults to PHP, `--account 1xbet=USDT` overrides.
- `--exclude T-0412,...`, `--only-leagues`, `--min-odds`, `--max-matches N` to shape the pool. `--seed N` for a different (but reproducible) draw.

## 5. How the plan is built
**Pool:** one position per match, up to `--max-matches`. If slots (tickets × legs) are fewer than matches, matches are chosen lowest-held-exposure first, and the rest are listed as "not covered".

**Doubles / trebles / n-folds:** tickets are drawn so that
1. each selection appears floor or ceil of the same number of times (balanced exposure; spread ≤ 1 ticket),
2. the same book never gets the same selection twice more than the balance allows, and each book's own mix is balanced too,
3. no identical ticket, no repeated pair within the plan, and few repeats of pairs already held,
4. the tickets then go to books in proportion to `--books`.
Method: seeded greedy fill followed by swap hill-climbing on a penalty (imbalance + repeats). Same inputs + seed → same output.

**System k/n:** the n legs are n distinct matches (one rung each, fixed for that system). The slip is one ticket at one book with `C(n,k)` combinations at `stake / C(n,k)` each. If several systems or more matches than n are planned, the matches are split into overlapping groups so every match is in a similar number of systems. Returns use `log_bets.system_return`, so it matches how the book will settle.

## 6. Drift (what he actually sees)
Two-step, because the real price is only known at the book:
1. Run the proposal. It prints every leg at **tip odds**.
2. He looks up the prices and types them in a small file, one per line (book is optional; no book = applies to every book):
   ```
   T-0412    1.85
   T-0412    1.90    bet88
   T-0409    1.40
   ```
   Re-run with `--seen seen.tsv`. Drift = seen / tip − 1.

Output then adds, per leg and per ticket:
- **Leg drift %**; flagged `DRIFT` when worse than **−5%** (`--drift-threshold`). His own history: legs taken at −15% to −30%.
- **Ticket drift cost**: the product of the legs' ratios. Example: a treble with legs at −15% each pays only 61% of what the tip odds promise (0.85³), i.e. **39% of the payout gone** before any bet is lost.
- For a flagged leg, the **other rungs of the same match** with their drift (if seen).
- `--skip-flagged` rebuilds without flagged legs. Off by default: he decides.
- Legs with no seen odds are marked `tip odds (not checked)`.

## 7. Output (printed; same content optionally in the sheet)
1. **Header:** day, candidates found / matches / positions, total stake, tip track record (settled n, flat ROI, ± 1 standard error, with a small-sample warning, e.g. "n=496, +9.0% ± ~4.5%: about 2 standard errors, still a thin sample").
2. **Tickets table:** `#`, book/account, type, legs (match, selection, tip odds, seen odds, drift), total odds (tip and seen), stake, "pays if all win" (tip and seen).
3. **Exposure:** per selection (tickets, ₱), per match (₱ now + ₱ already held), per book (₱, % of plan, cash available → warning if short). Spread of tickets per selection, min–max.
4. **"If j of the M selections win → P&L"** per plan and for the whole day: average, worst and best P&L over every possible set of j winners (exact for M ≤ 20, else 20,000 random draws, labelled), the **break-even j**, and at seen odds when available. Example for a 3/5 system at ₱4,000, odds ≈ 2: 3 winners return one combination (≈ ₱3,200) = **−₱800**; it needs 4 of 5 to profit.
5. **Notes (soft):** matches not covered; held-exposure overlaps; planned stake vs his average daily stake and "yesterday was a losing day" (information only, he has named chasing losses as the main leak; shown only with ≥ 5 days of history).

## 8. Writing the plan
- Default: print only.
- `--apply`: writes a **"Multis plan"** tab in the PRIVATE sheet (created if missing; fully replaced each run, since it is a proposal, not a record). Without `--apply` it prints what it would write.
- Never writes to Bets/Legs/Ledger; logging what he placed stays with `log-bets`.

## 9. Code layout and tests
- `multis.py`: CLI + sheet I/O (thin). Pure, testable functions: `candidates()`, `positions()`, `build_tickets()`, `allocate_books()`, `system_plan()`, `scenario_table()`, `drift_report()`, `exposure()`.
- Reuses `log_bets.tip_rows`, `log_bets.system_return`, `log_picks.SHEETS`, `setup_book.BOOK_KEY`, `inspect_sheet.client()`.
- `tests/test_multis.py`: one leg per match; balanced counts (spread ≤ 1); no duplicate tickets/pairs; stake sums exact to the peso; books proportional; system k/n returns match `system_return`; scenario table vs hand-computed examples; drift flags and ticket drift cost; held exposure and `--exclude`; seed reproducibility; seen-odds parsing; all 47 existing tests still pass.

## 10. Out of scope (now)
Staking or edge estimates per tip (no probabilities exist; it treats every tip equally), automatic placing, CLV, investor pots, any book-specific rule (min legs, min leg odds) beyond a `--min-odds` filter.

## 11. Decisions for Paolo (my recommendation first)
1. **Betting day 12:00 → 12:00 PHT** and rungs **rotate**? 
2. **Unit ₱1,000 per ticket**, equal stakes, `--jitter` off unless you want it?
3. **Book split:** equal across the 4 active books, 1xbet in PHP? Or give me your shares.
4. **Held matches** de-prioritised, not excluded?
5. **Drift** −5% threshold, seen odds via a small TSV (or I paste them in chat for you)?
6. The "Multis plan" tab in the private sheet, or print-only for now?
