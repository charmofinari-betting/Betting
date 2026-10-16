# Handover: picks and bets tracking session (as of 11 Oct 2026, ~5pm PHT)

Paolo's personal sports-betting workspace. This doc lets a fresh session carry on logging bets, settling results and reporting numbers without the old (very long) conversation. Read `CLAUDE.md` first (ground rules, hard wall from Veli/company systems). Memory files in `C:\Users\jnplz\.claude\projects\C--Users-jnplz-betting\memory\` hold the longer background.

## What you do here
1. **Log bet slips** (screenshots from 1xbet, 747-live, bet88, msw.ph) into the private Google Sheet "Private Betting" with `game-tracker/log_bets.py` (skill: `.claude/skills/log-bets/SKILL.md`).
2. **Settle results**: tip results (`set_results.py`), own-pick leg results (`set_leg_results.py`), then `sync.py` and `book_sync.py`.
3. **Report**: open position, max win, balances, P&L/ROI (`positions.py`, `projections.py`).
4. **Ledger**: deposits, withdrawals, adjustments (via `write_rows.py`); project costs go in the Costs tab.

Run everything from `C:\Users\jnplz\betting\game-tracker`. On Windows set `PYTHONIOENCODING=utf-8` (the ₱ sign crashes cp1252).

## Rules of engagement (Paolo's preferences)
- **Dry run first, show him, write on his "yes".** Every script is dry-run by default; `--apply` writes. Ledger rows are shown as a preview before writing. When he says "apply all" or "log these", that is the yes.
- **Never invent** a slip number, a placed time, or a result. Ask. (Slip headers are often cut off in screenshots.)
- Advise, don't police. Show numbers with sample sizes; flag small samples; never present a hunch as an edge.
- Be concise. He reads on a phone. He is an industrial engineer and sportsbook risk manager; he is not new to betting.
- Use they/them for people whose pronouns he hasn't given. Pat and Tish are account holders (see below).

## The Private Betting sheet
Key lives in `game-tracker/setup_book.py` (`BOOK_KEY`). Tabs: Dashboard, Bets, Legs, Ledger, Balances, Accounts, FX, Costs, Multis plan, Holders.
- **Bets**: Slip ID (S-00xx), Placed (PHT), Account, Type, Stake, Total odds, Legs, Result, Return, P&L, ..., Placed by, Currency, FX to ₱, Stake ₱, P&L ₱, Book slip №, System return. Result/Return/P&L are formulas.
- **Legs**: Slip ID, Leg, Tip ID, Own pick?, Match, Selection, Odds taken, Tip odds, Drift %, Leg result (column J), Kickoff, ...
- **Ledger**: Date, Account, Type, Amount, Pot, Note. Types: Opening balance, Deposit, Withdrawal, Transfer in/out, Bonus, Adjustment.
- **Accounts**: 1xbet PHP, 1xbet USDT, 1xbet TRX, bet88, 747-live, winzir, `msw.ph Pat`, `bet88 Tish`. Pat's and Tish's accounts hold Paolo's money (Pot = Paolo); the Holder column separates them.
- The shared **tips sheet** (`SHEETS["live"]`, Sheet1) holds a friend's tips with IDs T-xxxx. Paolo's slips are matched to tips; picks with no tip are his **own picks** (`"own": true`).

## Logging a slip (the loop)
1. Read the screenshot into a JSON file (put it in the scratchpad, not the project). Fields: `book_slip_no, placed, account, system ("2/5"), stake, total_odds, potential, opening, notes, boost, legs[sport, home, away, market, odds, kickoff, status, own, tip]`.
2. `python log_bets.py file.json` (dry run). Fix PROBLEM lines: set `"own": true` or `"tip": "T-xxxx"` (find the tip by team names/market in the tips sheet; names differ between books, e.g. "Al Ahly" vs "Al Ahli Cairo").
3. Show Paolo the table (legs, taken odds, tip odds and drift, own-pick flags, max return, new balance). On yes: `--apply`.
4. Then `python positions.py` and report: open tickets, staked, max return, max profit, balances. Split **own books** from **Pat/Tish**.

Time and market rules:
- **1xbet slip times are UTC+7** (the script converts to PHT; give it the slip's own times, kickoffs too). 747-live, bet88, msw.ph and Paolo's phone are PHT.
- Football 1X2 W1/W2 = Asian handicap ∓0.5; other sports 1X2 / Match Winner = Moneyline. Double Chance 1X/2X = +0.5 handicap. "Total. Cards: Over 4.5" = Cards market; corners = Corners market (neither can be settled from the score; ask Paolo for the count).
- bet88 ComboBoost: total odds = leg product × boost (`"boost": 1.08`).
- Systems k/n: stake split evenly over C(n,k) combos; the sheet credits a system only when all legs have settled, although books pay winning combos earlier (known lag).
- Duplicate slips are skipped by slip number; a re-sent screenshot is harmless.
- A bet already settled when logged: set the leg `"status": "Win"/"Loss"` and `"own": true`.
- A moved line (e.g. tip Under 2.5, taken Under 2): Paolo decides whether to link to the tip; link with a CHECK note.

## Settling
- Tip results: `python set_results.py "T-0615=Won:1-1" "T-0612=Won:1-3" [--apply]` (refuses to overwrite an existing result).
- Own-pick legs: `python set_leg_results.py S-0058:1=Lost [--overwrite] [--apply]`.
- `python sync.py` (api-sports free plan: yesterday..tomorrow only) then `python book_sync.py [--apply]` settles legs from tips and writes system returns. It lists own picks and unsettleable markets (cards/corners) as ASK. Needs Paolo's final scores for anything the feed doesn't cover.
- Void/postponed: ask Paolo. If the book voided a leg that the tip says Won, correct with `--overwrite` (done for S-0043).

## Money model
Balance = opening + deposits − withdrawals − staked + returned. Open stakes counted at cost. Check: cash + open stakes + withdrawals − capital = realised P&L. Capital baseline ≈ ₱63.08k + 100 USDT (memory: project-capital-baseline). FX stored per ticket at placement (`fx.py`); balances use current FX. Paolo tells me about every deposit/withdrawal ("I'll notify you"); log them, and sanity-check balances against app figures he quotes. A gap means a missing ledger line or slip, not a bug to hide.

## Account holders (Pat & Tish)
Paolo funds both (₱5,000 each on 11 Oct; ₱200 fee on Pat's funding in Costs). Bets show "Placed by" Pat/Tish. Dashboard and capital/P&L figures count **own books only** (Holder = Paolo); report open position both ways. Their tickets: S-0056 (Tish, bet88, ₱5,000 single, max ₱10,400) and S-0057 (Pat, msw.ph, ₱5,000 system 2/5, max ₱21,249.15). Pat/Tish scheme design is in the account-holders session, not finished.

## State right now
- ~69 tickets logged (S-0001..S-0069). Realised P&L about +₱90k on ₱151k staked (+59.5% turnover ROI), but excluding the top 3 wins about +₱4k: small sample, a few big system wins.
- **13 open tickets**: ₱54,126.52 staked, max return ₱276,642.16 (own books: 11 tickets, ₱44,126.52, max ₱244,993.01). Open: S-0007, S-0030, S-0053, S-0055, S-0056 (Tish), S-0057 (Pat), S-0060, S-0062, S-0065, S-0066, S-0067, S-0068, S-0069, plus any status changes since.
- Balances (sheet, ₱): 1xbet PHP 16,999.99; 1xbet USDT 185.57 USDT (≈11,633); 747-live 12,000.00; bet88 0. Total ≈ ₱40,633.
- Withdrawals so far: ₱63,000 (earlier) + ₱25,997 (1xbet PHP, 11 Oct) + 114 USDT; capital is back with more taken out.
- Stacked exposure: Lokomotiva/Varazdin and Zamalek/Al Ahly sit in many tickets; Olimpia +12 in three. Mention it when reporting max win.

## Open items
- **Results needed from Paolo**: Zheng vs Andreeva (S-0060, S-0065), Khachanov and de Minaur (S-0059, already lost via Shelton), Ajax vs N.E.C. corners count (T-0826, S-0032, already lost, cosmetic).
- Tennis legs on lost tickets S-0033/S-0034 still unsettled in the sheet (cosmetic).
- Possible future design: handling partial system payouts in the sheet (plan first, don't build unasked).
- Funds dashboard: spec `game-tracker/SPEC-funds-dashboard.md` awaits Paolo's approval (3 answers, plus section 4a on holder accounts). Nothing built.
- Pat & Tish scheme: separate session was designing the sheet split; check the Holders tab and `add_holders.py` / `holders_view.py` before changing anything there.
- Uncommitted: `game-tracker/vocab.json` modified, and the new Cards market parser plus tests in `log_bets.py` / `tests/test_log_bets.py`. Run `python -m unittest discover -s tests` (93 tests pass) and ask before committing.

## Gotchas
- Never use company systems (Veli replica, VSB, service accounts, repos). Personal Google service account key lives in `secrets/`.
- Sheet spill/#REF! gotchas and write quotas are in memory (project-private-book). Do not put a SUM inside its own range.
- Scratch files (slip JSON) go in the scratchpad, not the repo.
- Verify any figure he quotes from an app against the sheet before saying it matches.
