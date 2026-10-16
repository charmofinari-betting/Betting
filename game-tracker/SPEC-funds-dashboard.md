# Spec: Funds dashboard (private book)

Status: **superseded 16 Oct 2026** by the Funds tab in the sheet + the `funds` skill (phone-viewable; see PLAN-phone-first.md). Kept for reference. Original status: draft for review (2026-10-10). Read-only: it never writes to the sheet, never places bets, never writes results.

## 1. Purpose
One page that answers *"where is my money right now?"* at a glance. Descriptive only: numbers and sample sizes, no verdicts.

## 2. Where it lives and how it refreshes (recommendation)
**A local HTML file generated from the sheet**: `game-tracker/out/funds.html` (the `out/` folder is git-ignored, so the numbers never reach git).
- Refresh: `PYTHONIOENCODING=utf-8 ../.venv/Scripts/python dashboard.py` from `game-tracker`, then it opens in the browser. Reads the sheet with the read-only client; takes a few seconds.
- Single self-contained file (inline CSS, no external scripts or fonts). Works offline, opens by double-click, follows light/dark mode, readable on a phone if you copy the file over.
- Shows "as of" time and the FX used, so a stale page is obvious.

Why not the alternatives:
- *Artifact page*: it is hosted on claude.ai; this is your money, so it would mean publishing it. Not by default. Can be done later with your explicit yes.
- *Improve the Dashboard tab*: fine for tables, weak for layout and charts, and it is already crowded. I would leave that tab as it is.

## 3. What it shows (top to bottom)
1. **Headline strip**: Total value at cost (cash + open stakes) · Cash in books · Open stakes · Net money put in · Settled P&L.
2. **Money in / out** (the capital story):
   - Opening money: ₱31,964.61 + 100 USDT (= ₱6,303 at current FX)
   - Deposited: ₱7,000 (10 Oct) · Withdrawn: ₱3,000 (9 Oct)
   - Net put in, then **settled P&L**, then **value at cost**, with a reconciliation line (net in + settled P&L = cash + open stakes). If it does not tie out, the page says so in red rather than hiding it.
3. **Per book** (1xbet PHP, 1xbet USDT, 747-live, bet88, winzir; TRX hidden while empty): cash, open stakes, open tickets, max return, settled P&L, and share of total as a bar. USDT shown in USDT with the ₱ equivalent.
4. **Open exposure**:
   - Open stakes and **max return, labelled "ceiling if every open leg wins, not a forecast"** (dead legs already cut it, via `positions.py`).
   - Ticket table: slip, book, type, stake, legs still alive / total, max return, earliest next kickoff.
   - **Overlap by match**: matches that appear in more than one open ticket, with the stake riding on them and how many tickets. Concentration is shown as a number (largest single match as % of open stakes), not a warning.
5. **Settled results**: tickets settled, staked, P&L, ROI, **n shown beside every figure**; split by ticket type. A fixed note: *"open stakes are not realised profit; ROI is on settled turnover and the sample is small."*
6. **Project costs** (Costs tab): total and a line per item (e.g. Claude Pro ₱1,420.04). Also shown: settled P&L net of costs, as a separate line, never mixed into betting P&L.

## 4. Build
- `dashboard.py`: `load()` (read sheet) → pure functions `compute(...)` (all the arithmetic, reusing `positions.summarise` and `log_bets.system_return`) → `render(model) -> html`. Logic is separated from I/O so it is unit-tested with fixtures: `tests/test_dashboard.py`.
- Currency: tickets at the FX stored on them; balances at current FX (same convention as the sheet). Coin price moves are not betting P&L, so the USDT line shows the FX effect separately if the baseline and current ₱ differ.
- No new sheet tabs, no writes, no network except Google Sheets read. Costs and money figures are never sent anywhere.

## 4a. Holder accounts (added 11 Oct, from SPEC-account-holders.md)
Pat (msw.ph) and Tish (bet88) hold accounts with Paolo's money. Their ₱5,000 deposits each (11 Oct) are Ledger deposits but **not** new own capital. So:
- Capital, cash, P&L and the reconciliation in section 3 filter on **Holder = Paolo** (Balances col O; Bets "Placed by" = Paolo).
- Holder accounts get their own small section (cash, open stakes, tickets per holder), outside the own-capital maths.
- Open question for Paolo: should the headline "value at cost" include holder accounts (all Paolo's money in play) or only his own books? Default: show both totals, labelled.

## 4b. Checked against the app (11 Oct)
1xbet PHP: app ₱2,000 = sheet ₱2,000.00. Known lag: the book pays system ticket S-0012 out in parts, so its settled part can sit in the app before the sheet closes the ticket (and the reverse). The reconciliation line therefore says "ties out" or shows the gap in ₱; it never auto-corrects.

## 5. Open questions for Paolo
1. Local HTML OK as the home for it (recommended), or do you want it published as a private Artifact?
2. Baseline: I will compute capital from the **Ledger** (opening + deposits − withdrawals) rather than hard-coding. Opening ₱31,964.61 + 100 USDT is treated as your own money (confirmed 10 Oct). OK?
3. Anything to add or drop from section 3? (Ideas I left out: drawdown from peak, price-drift cost, by-pick-source. All already on the sheet Dashboard; can add.)
