# Spec: Private book ("Private Betting" sheet)

Status: **draft for Paolo's review** (2026-10-08). Private sheet, shared with the service account only.
Starts **8 Oct 2026** from opening balances; no backfill. Own money only for now.

## 1. Purpose
The shared SportsBetting sheet answers *"are the tips good?"* (flat 1u per tip).
This sheet answers *"how is my money doing?"*: what was actually placed, where, at what price, and what it returned.
They connect through **tip IDs** (T-0601...): a leg's result comes from the shared sheet, so a result is never entered twice.

## 2. Built in from day one, used later
- **Holder vs owner.** Every account has a *holder* (whose login it is) and every bet/ledger line has a *pot* (whose money). Today both are always "Paolo". Account holders betting for him and an investor pot slot in later without restructuring.
- No investor or holder features until they are real.

## 3. Tabs

### Accounts
| Account ID | Book | Holder | Currency | Status | Notes |
|---|---|---|---|---|---|
| A-01 | 1xbet | Paolo | PHP | Active | |

### Ledger: money in and out of accounts (not bets)
| Date | Account | Type | Amount ₱ | Pot | Note |
|---|---|---|---|---|---|
Types: Opening balance, Deposit, Withdrawal, Transfer out, Transfer in, Bonus, Adjustment.
**Paolo types the opening balances himself** (amounts don't go through the chat).

### Bets: one row per ticket
| Slip ID | Placed | Account | Type | Stake ₱ | Total odds | Legs | Result | Return ₱ | P&L ₱ | Pot | Placed by | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
Type: Single, Double, Treble, 4-fold, 5-fold, ...; System (e.g. "Doubles from 4") as a later addition if he uses them.
Result / Return / P&L are **calculated** from the legs (§4).

### Legs: one row per selection on a ticket
| Slip ID | Leg | Tip ID | Own pick? | Selection (as on slip) | Odds taken | Tip odds | Drift % | Leg result |
|---|---|---|---|---|---|---|---|---|
- **Tip ID** links to the shared sheet; blank for his own picks (e.g. ML add-ons on handicap tips) → **Own pick = Yes**, result entered by hand (or from api-sports later).
- **Drift % = Odds taken / Tip odds − 1.** Example: T-0603 1.82 → 1.55 = −14.8%.
- **Leg result** is copied from the shared sheet by the sync script (values, not IMPORTRANGE, so the private sheet never depends on a live link).

### Balances (calculated)
Per account: opening + deposits − withdrawals ± transfers − stakes + returns of settled tickets = **balance**; stakes on open tickets = **exposure**.

### Dashboard (calculated)
- Bankroll (balances + open stakes), P&L and ROI since 8 Oct, turnover.
- By book, by ticket type (single / double / treble / 4-fold), by own pick vs tip.
- **Price drift cost:** P&L at the odds taken vs what the same tickets would have paid at tip odds.
- Drawdown from peak bankroll.
- **Losing-day flag** (soft, never blocks): after a losing day, today's stake vs the average daily stake.

## 4. Ticket settlement (accumulators)
Return = Stake × product of each leg's factor:
| Leg result | Factor |
|---|---|
| Won | odds |
| Lost | 0 (ticket lost) |
| Void | 1 |
| Half Won | (odds + 1) / 2 |
| Half Lost | 0.5 |
This is the standard rule (1xbet uses it). If another book differs, its rule gets added per book.
Ticket is **open** until every leg has a result.

## 5. Input and scripts (same pattern as the picks sheet)
- **`log-bets` skill:** Paolo sends bet-slip screenshots (top part with type/stake + the legs) → Claude transcribes → script matches each leg to a tip ID (by match + selection, within the tip's kickoff day), computes drift → dry run → write on "yes". Legs without a matching tip are asked about ("own pick?").
- **Matching slip markets to tips:** 1xbet writes moneylines as 1X2. Football **W1/W2 = Handicap -0.5** (T-0436 `AWAY -0.5` = slip `W2`); tennis/basketball **W1/W2 = ML HOME/AWAY**. A slip leg that only resembles a tip (e.g. W2 when the tip was DNB `AWAY 0.0`) is **not** auto-linked; it is asked about.
- 1xbet's "Potential winnings" is the gross return (stake × odds), used as a check on the transcription.
- **`book_sync.py`:** copies leg results from the shared sheet for open tickets; dry run, `--apply`.
- Kickoff times come from the tips/API (PHT). 1xbet shows times 1h earlier (account likely on UTC+7); ignored.

## 6. Worked example (from Paolo's 1xbet slip, 8 Oct)
4-fold, ₱1,500: T-0602 Gadamauri ML 1.52 · T-0603 Dabrowski/Stefani ML 1.55 · T-0601 Rincon ML 1.70 · T-0499 Bayern–Virtus Over 169.5 1.814.
Total ≈ 7.27 → ₱10,898 if all win. At tip odds the same ticket would be ≈ 9.75 (₱14,628): drift costs ~25% of the payout.

Treble, ₱1,500, odds 7.021: T-0436 Novorizontino W2 (tip AWAY -0.5) 2.40 → 1.94 (−19.2%) · T-0567 Correcaminos W2 (tip AWAY -0.5) 2.47 → 1.73 (−30.0%) · T-0599 Rublev/Khachanov W1 2.05 → 2.092 (+2.0%).
₱10,531.76 if all win; at tip odds ≈ 12.15 (₱18,229): drift costs ~42% of the payout.

## 7. Build order
1. Create tabs + formulas on the private sheet; Paolo enters opening balances.
2. `log-bets` skill + script, tested on today's two slips.
3. `book_sync.py` for leg results.
4. Dashboard.
5. Multis builder (Open picks → proposed tickets across books, with drift flags).

## 8. Assumptions — correct me
- Only Paolo sees this sheet.
- **Multi-currency (changed 2026-10-08):** 1xbet has PHP, USDT and TRX accounts. Amounts stay in each account's currency; the FX tab holds ₱ per unit; each ticket stores the FX of the day it was placed (its ₱ P&L is fixed then); balances in ₱ use the current FX. Coin price moves are not betting P&L.
- Tickets placed before 8 Oct and still open: the book's cash balance already excludes their stake, so log-bets adds an "Opening balance" ledger line equal to that stake (note: open ticket before start). Balances then add up.
- A ticket's stake leaves the balance when placed; the return arrives when the last leg settles.
- Cash-outs: recorded as a ticket result "Cashed out" with the amount, when they happen.
