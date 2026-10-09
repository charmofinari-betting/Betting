---
name: log-bets
description: Log Paolo's own bet slips (tickets he placed: singles, doubles, trebles, accas) from bookmaker screenshots into his PRIVATE book ("Private Betting" sheet). Use when Paolo sends a bet slip / "Bet slip details" screenshot (stake, odds, legs) and asks to log or track his bets. Not for tipster tip tables — those go to log-picks.
---

# log-bets

Bet-slip screenshots → `game-tracker/log_bets.py` → private book (Bets, Legs, Ledger).
The script matches legs to tips, checks the slip's maths and writes; you only transcribe.
This is Paolo's private money data: it goes to the private sheet only, never the shared one.

## 1. Transcribe into JSON (session scratchpad, not the project folder)
One object per ticket, values exactly as the slip shows them:
```json
{"book_slip_no": "88409202869", "placed": "2026-10-07 18:34", "account": "1xbet PHP",
 "stake": 1000, "total_odds": 3.532, "potential": 3531.9, "opening": false,
 "legs": [{"sport": "Basketball", "home": "Aris Thessaloniki", "away": "Burgos",
           "market": "Handicap 1 (-8.5): Aris Thessaloniki - Burgos (Including Overtime)",
           "odds": 1.83, "kickoff": "2026-10-08 00:00", "status": "Win"}]}
```
- Times as the book shows them (1xbet = UTC+7; the script converts to PHT).
- **account**: the Accounts tab name (e.g. "1xbet PHP", "1xbet USDT"). Use the stake's currency on the slip to pick it. Ask if unsure.
- **sport** from the slip's icon / league line. **market**: the full market line.
- **status**: the leg status shown (Unsettled / Win / Loss / Return...).
- The slip header (slip №, date, type, odds, stake, potential winnings) must be visible; if a screenshot starts below it, ask Paolo for the top part. Never invent a slip number.
- **opening: true** only for tickets that were already placed and open when the book started (8 Oct 2026). Tickets placed after the opening entries are normal (false).

## 2. Dry run
```
cd C:/Users/jnplz/betting/game-tracker
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python log_bets.py <json>
```
Show Paolo each ticket with its legs → tip IDs, drift %, and every CHECK / PROBLEM.

## 3. Resolve, never guess
- **Tip uses a short name** (HJK vs "VPS" for Vaasan): find the tip IDs in the tips sheet and force the link with `"tip": "T-...."`.
- **No tip found:** ask Paolo whether it's his own pick (set `"own": true`) or which tip it was (`"tip": "T-...."`).
- **CHECK line moved:** confirm with Paolo it's the right tip (he took a different line than tipped).
- **Odds or potential mismatch:** re-read the screenshot; it's almost always a transcription slip.
- **Unrecognised market:** don't force it; tell Paolo and extend `parse_slip_market` with a test.

## 4. Apply only on Paolo's "yes"
Re-run with `--apply`; report ticket IDs. Advisory, not policing: show drift plainly when large,
never refuse or lecture (see memory: advise, don't control).

## Notes
- FX: `fx.py --apply` refreshes USDT/TRX ₱ rates; run it before logging non-PHP tickets.
- Books supported: 1xbet (UTC+7 times; 1X2 W1/W2), bet88 and 747-live (PHT; team-named 1x2 / Match Winner / Match Result). Systems: set "system": "3/5".
- Leg results: `book_sync.py` settles legs from the tips' scores (each leg on its own line) and writes system returns; Result/Return/P&L are sheet formulas.
- Slip formats handled: 1xbet "Total: Over 2.5" and "Total Under (9.5): Corners A - Corners B" (corners = market `Corners`, never goals; probably settled by hand, since scores carry no corners); 747-live "Total Goals Over (3.5)", "Total Points Under (167.5)".
- **Placed time missing** (system slips cut off at the top): ask; or use the phone clock minus "N minutes ago". Phone and 747-live are PHT, 1xbet slips are UTC+7 (script converts). A bet already settled at logging time: set the leg `"status": "Win"` and `"own": true` for his own picks.
- **Cash:** deposits and withdrawals are logged as Ledger lines only when Paolo says so (dry run first). "Opening balance" lines = stakes already sitting in open bets (cash held was 0). Never infer a deposit from a balance gap; ask.
- **After logging, report** `python positions.py` (open stake, max return, balances) and sanity-check the balances against his apps (1xbet / 747 balances he quotes). A gap means missing ledger lines, not a bug to hide.

