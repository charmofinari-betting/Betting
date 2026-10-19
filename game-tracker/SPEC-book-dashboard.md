# Spec: Book dashboard (per-book balances, phone page)

Status: draft for review (18 Oct 2026). Brainstormed with Paolo; layout B (cards, problems first) chosen in a mockup.

## 1. Why
This is the first time in 10+ years Paolo tracks every bet properly, and he takes it seriously. The Funds tab adds everything up per pot (own PHP / own crypto / each holder), so he cannot see **what is in each sportsbook**, nor whether the sheet still agrees with the books. The dashboard's job is **trust**: each book's expected balance next to the balance the book's app actually shows, with any gap impossible to miss.

Success: he opens one link on his phone and, within seconds, knows which books match, which have a gap, and which haven't been checked lately.

## 2. Goals, non-goals, anti-goals
**Goals**
- A card per account (Accounts tab rows) showing expected cash vs the last app balance he gave us, the gap, when it was checked, and open stakes.
- Problem cards first: gap ≠ 0, then never checked / stale, then matched.
- A summary strip: own cash in books, own open stakes, own max return (ceiling if every open leg wins), books matched (n of m), crypto in native units.
- Holder accounts (Pat, Tish, Grace, and any future holder) in their own section, never added to Paolo's totals.
- App balances arrive as screenshots in the Betting Inbox and are logged by `check-inbox`, same dry-run → yes → apply flow as slips.
- Works from the phone with the laptop off, without the cloud move.

**Non-goals**
- Estimating how close a book is to limiting him (he dropped this: too hard to gauge).
- A detailed open-tickets view. Open positions are summary numbers only (stake at risk, max return); details stay with `positions.py` / asking Claude.
- Settled-results analytics, ROI, charts. That's the daily brief's job (separate project).
- Replacing the Funds or Dashboard tabs. Both stay as they are.

**Anti-goals (a failure even if it works)**
- Any number silently adjusted to make a gap disappear. A gap is shown, explained if we can, never "fixed" by the dashboard. Ledger corrections only via confirmed Ledger lines (existing rule).
- Crypto folded into ₱ totals ("1000 TRX is 1000 TRX").
- Holder money mixed into Paolo's figures.
- The page writing to the sheet. It is read-only.
- Anyone but Paolo able to open it.

## 3. Constraints
- Data lives in the Private Betting sheet (`BOOK_KEY` 1zfPQqyLsFtFoDkluO4R7was3wyh5au6jV1Eyayykxdg): Accounts, Balances (per-account Opening, Deposits, Withdrawals, Transfers, Bonus/adj., Staked, Returned, **Balance** = expected cash, Open stakes, Currency, Holder), Bets, Legs, Ledger.
- Hard wall (CLAUDE.md): Paolo's own Google account and the personal `sheet-bot@betting-511008` service account only. Nothing from work.
- All sheet writes go through Python with a dry run first and his yes (`feedback-dry-run-first`).
- Phone-first; he reads on a small screen.

## 4. Decided
- **Layout B**: card per book, problems first; summary strip on top (mockup: `.superpowers/brainstorm/.../dashboard-layout.html`, not committed).
- **Real balances come from screenshots dropped in the Betting Inbox**, read by `check-inbox`.
- **Where it lives (Claude's proposal, Paolo said "go for it")**: a Google Apps Script **web app** in Paolo's own Google account, reading the sheet live. Opened as a bookmarked link on his phone. Deployed "Execute as: me", "Who has access: only myself". Source kept in the repo at `apps-script/book_dashboard.gs` (+ `.html`), like `results_fetch.gs`.

## 5. Data
### 5.1 New tab: `Balance checks` (one row per screenshot reading)
| Column | Meaning |
|---|---|
| Checked at (PHT) | time shown on the screenshot if visible, else the Drive file's created time |
| Account | exactly as in Accounts (e.g. `bet88`, `msw.ph Pat`) |
| App balance | the app's one balance figure, in the account's own currency (Paolo, 19 Oct: every book shows a single balance; he rarely takes bonuses or free bets. If a book ever shows a split, ask, don't pick) |
| Expected at check | expected cash **as of Checked at**, rebuilt by Python (see below), written as a value |
| Gap | App balance − Expected at check (written value) |
| Source | Drive file id of the screenshot |
| Note | free text (e.g. "gap = return of S-0201, not settled in sheet yet") |

The dashboard uses the **latest row per account**. History stays for later (does a book drift?).

Why "as of Checked at" and not today's figure: the sheet moves on after the screenshot (new slips, Ledger lines, settlements), and check-inbox may run hours later, so comparing with today's Balance would invent gaps and turn trusted cards red. (Claude's call, after the builder check.)

How expected-as-of is rebuilt: start from today's Balance and undo what happened after Checked at:
- Bets placed after Checked at: add their stake back.
- Ledger lines dated after Checked at: undo them. Ledger has dates only, so a same-day line is ambiguous; the dry run lists it and asks.
- Tickets settled after Checked at: take their return back out. This needs a new **Settled at (PHT)** column on Bets, stamped by the Python paths that settle book tickets (`book_sync.py`, `set_leg_results.py`) when Result first leaves Open. Tickets settled before the column exists have no stamp; for those the dry run assumes "settled before the check" and says so. Because the stamp is when the sheet learned the result (can be a day after the book paid), the settle time used is the earlier of the stamp and the ticket's last leg kickoff + 3 h (Claude's call, found in planning).
The dry run prints the rebuild line by line, so a gap can be traced.

### 5.2 New column on Bets: `Max return` (open tickets only)
Written by Python wherever book ticket state changes (`log_bets.py`, `book_sync.py`, `set_leg_results.py` apply paths; the Sheet1 scripts don't touch the book), plus a `Max return written at` timestamp the page shows next to the figure, so a hand edit in the Sheets app (leg result, cash-out) can't make it silently wrong without the page showing its age. Uses the existing `positions.summarise` logic (dead legs cut the ceiling; systems = every combination wins; combo boosts kept). Blank for settled tickets. Native currency of the ticket. The web page only sums it; no betting maths in Apps Script.

## 6. Logging a balance (check-inbox)
- New Drive folder `Betting Inbox/Balances` (Paolo's own screenshots). Holders' balance screenshots may land in their `Slips/<Holder>/` folders; route by what the image shows (the skill already does this for misfiled files).
- Order inside one inbox run: log any slips first, then balance checks, so "Expected at check" includes slips in the same batch.
- New script entry point (e.g. `balances.py check <account> <amount> [--at ...] [--source <id>]`, dry run by default, `--apply` writes) prints: account, app balance, expected, gap. If gap ≠ 0, Claude looks for an obvious cause (an open ticket that the book has settled but the sheet hasn't; an unlogged deposit/withdrawal) and puts it in Note as a *possible* cause. Never changes Ledger or Bets on its own.
- A screenshot that shows no clear account or balance: leave it in the inbox and ask (same as slips).

## 7. The page
Top to bottom:
1. **As-of line**: "Live from the sheet · opened 18 Oct 21:40". Also the newest Bets/Balance-check timestamp so staleness is visible.
2. **Summary strip (own money only)**: Cash in books ₱ · Open stakes ₱ · Max return ₱ ("ceiling if every open leg wins") · Books matched n of m · Crypto line in native units (TRX, USDT).
3. **Own books** (cards, sorted): 
   - Red: last check has a gap (|gap| ≥ 1 unit). Shows gap, expected-at-check, app balance, note.
   - Amber: never checked, or last check older than the stale limit.
   - Green: matched and recent. Compact.
   - Every card: account, expected cash now, open stakes, open tickets count, last check age.
4. **Holders**: one sub-section per holder, same card rules, their own small summary (cash, open stakes).
5. Hidden by default: accounts with zero cash, zero open stakes and status not Active (e.g. winzir). A "show all" toggle.

Matching tolerance: |gap| < 1.00 in the account's currency counts as matched (cent rounding). Crypto uses the same rule in its own units.

## 8. Left to the builder (Claude's calls, Paolo may override)
- Stale limit: 3 days without a check → amber.
- Visuals: plain cards, light/dark following the phone, no external libraries.
- Exact column positions; whether `Max return` is written by a shared helper called from each apply path.
- Apps Script reads via `SpreadsheetApp.openById` with Paolo's own access (he owns/edits the sheet).

## 9. Testing
- Python: unit tests for the gap/snapshot logic and Max return writing (tests/ alongside existing ones), run against the staging copy before the live sheet.
- Page: deploy, open on his phone, compare every card with Balances tab by eye on day one.
- First real check: one balance screenshot per active book, so every card starts green or red, not amber.
