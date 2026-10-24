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
           "sel": {"market": "Handicap", "period": "FT", "side": "Home", "line": -8.5},
           "odds": 1.83, "kickoff": "2026-10-08 00:00", "status": "Win"}]}
```
- **sel** = what the leg means, in the tips' terms (`parse.py` MARKETS / PERIODS; side Home/Away/Over/Under/Yes/No; line or null). Conventions: football 1X2 / winner = Handicap -0.5; double chance = Handicap +0.5; draw no bet = Handicap 0; a split line "2.5,3" = 2.75; Moneyline for non-football winners; a named team's cards/total = "Home team cards", "Away team total", ... The script checks it against the slip text and the Vocab tab's book wordings. Own picks with no tips market (draws, correct score, props): leave sel out.
- Times exactly as the book shows them; never shift them by hand. **1xbet flips between UTC+7 and PHT**: the script decides per slip from the tips' known kickoffs and prints "1xbet times read as UTC+…". If it can't tell (own picks only, or kickoffs disagree) it raises a PROBLEM: check the phone clock in the screenshot's status bar (PHT) against a just-placed slip, or ask Paolo, then set `"tz": 7` or `"tz": 8` on the slip.
- **account**: the Accounts tab name (e.g. "1xbet PHP", "1xbet USDT"). Use the stake's currency on the slip to pick it. **Never guess an account from the code or docs, never make one up.** No book name on the slip, or unsure: set `"account": "?"`; the dry run's PROBLEM lists the real accounts and the books whose slip-number format fits ("fits bet88 = bet88, bet88 Tish, bet88 Bret"). Ask Paolo with that guess ("bet88?"), not an open question.
- **sport** from the slip's icon / league line. **market**: the full market line, **copied character for character as the book prints it** (bet type, colon, selection): the Vocab tab's wordings are keyed on this exact text, so a paraphrase ("FT O/U" instead of "FT O/U: Over 2.5") shows up as a false NEW WORDING. Real examples per book:
  - 1xbet: `1X2: W2: Botosani - UTA Arad`, `Total Over (2.5): Turun Palloseura - FF Jaro`, `Handicap 1 (-8.5): Aris Thessaloniki - Burgos (Including Overtime)`
  - bet88: `1x2 KS Lechia Gdansk`, `Total under 2.5`, `Handicap (incl. overtime) BC Aris Thessaloniki (-8.5)`, `1st set - winner Jodar, Rafael`
  - Solaire: `FT 1x2: Qingdao West Coast`, `FT O/U: Over 2.5`, `FT Asian Handicap: Qingdao Hainiu +1.75`, `Corners FT O/U: Under 8.5`, `Both Teams To Score - Yes`, live: `[3:0]Live Betting Moneyline: Gladiators Trier`
  - msw.ph: `Win/Draw/Win - Regular Time: NK Varazdin`, `Head to Head - Match: Turk Telekom`, `Asian Handicap - Regular Time: Boluspor (+0.5,+1)`
  - 747-live: `Match Winner Fajing Sun`, `Total Goals Under (2.5)`, `Total Points Over (168.5)`
  - BingoPlus: `Handicap 2 (-7): Bamberg Baskets - UCAM Murcia (Including Overtime)`, `Winner Iva Jovic`
  - Okada: `1x2 Port Vale`, `Both Teams To Score - No`, `Winner (incl. overtime) KK Crvena zvezda Belgrade`
  A NEW WORDING on a book you've logged before: first re-check the market text against these, before asking Paolo.
- **status**: the leg status shown (Unsettled / Win / Loss / Return...).
- The slip header (date, type, odds, stake, potential winnings) must be visible; if a screenshot starts below it, ask Paolo for the top part.
- **book_slip_no**: exactly as shown. No number on the screenshot (msw.ph shows it only right after placing, not in Open bets): `null`, and the script makes our own key from account, type and placed time (`msw.ph-pat-system-2-5-1022-2208`, Paolo agreed 23 Oct 2026). Never type a number or key yourself. A number that doesn't fit its book's usual format is a PROBLEM: re-read it digit by digit.
- **opening: true** only for tickets that were already placed and open when the book started (8 Oct 2026). Tickets placed after the opening entries are normal (false).

## 2. Dry run
```
cd game-tracker   # from the repo root (laptop or cloud)
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python log_bets.py <json>
```
Show Paolo each ticket with its legs → tip IDs, drift %, and every CHECK / PROBLEM.

## 3. Resolve, never guess
- **Tip uses a short name** (HJK vs "VPS" for Vaasan): find the tip IDs in the tips sheet and force the link with `"tip": "T-...."`.
- **No tip found, "likely T-…":** the book spells a team differently from the tip (SW Bregenz / Schwarz-Weiß Bregenz). Ask "is it T-1637?", not "own pick?". On his yes: `"tip": "T-1637"` and add the spelling, dry run first: `../.venv/Scripts/python vocab.py add "team alias" "<book spelling>" "<tips spelling>" --apply`.
- **No tip found, nothing likely:** ask Paolo whether it's his own pick (set `"own": true`) or which tip it was (`"tip": "T-...."`).
- **CHECK line moved:** confirm with Paolo it's the right tip (he took a different line than tipped).
- **Odds or potential mismatch:** re-read the screenshot; it's almost always a transcription slip.
- **NEW WORDING:** a book wording the word list doesn't know yet. Ask Paolo what it means (say what you think), then add it, dry run first: `../.venv/Scripts/python vocab.py add "slip wording" "<key exactly as printed>" "<Market> <Period>" ["sport=Football, line=-0.5" | "split"] --apply`. A winner/1X2 wording needs two rows: `sport=Football, line=-0.5` with "Handicap FT", and one with "Moneyline FT". Never guess a meaning to make it clean.
- **"old parser reads ..."** (until ~5 Nov 2026): the old parser and your sel disagree. Re-read the slip; if your sel is right, tell Paolo the old parser is wrong for this wording (it is being retired, don't fix it).
- **"side ... but the text ..." / "line ... not on the slip":** almost always a transcription slip: re-read.

## 4. Apply (Write rule in CLAUDE.md)
Clean dry run (no CHECK / PROBLEM, every leg linked, odds and potential tie out) → re-run with `--apply` straight away. Anything from step 3 → apply only after Paolo answers. Report ticket IDs and rows written either way. Advisory, not policing: show drift plainly when large,
never refuse or lecture (see memory: advise, don't control).

## Notes
- FX: `fx.py --apply` refreshes USDT/TRX ₱ rates; run it before logging non-PHP tickets.
- Books supported: 1xbet (UTC+7 or PHT, detected per slip; 1X2 W1/W2), bet88 and 747-live (PHT; team-named 1x2 / Match Winner / Match Result). Systems: set "system": "3/5".
- Leg results: `book_sync.py` settles legs from the tips' scores (each leg on its own line) and writes system returns; Result/Return/P&L are sheet formulas.
- Slip formats handled: 1xbet "Total: Over 2.5" and "Total Under (9.5): Corners A - Corners B" (corners = market `Corners`, never goals; probably settled by hand, since scores carry no corners); 747-live "Total Goals Over (3.5)", "Total Points Under (167.5)".
- **Placed time missing** (system slips cut off at the top): look at the neighbouring screenshots first: a bet-history list ("Combo Oct 24 at 12:29") or the balance shown before/after this stake often pins it. Propose that time to Paolo with how you got it ("12:29 from the next screenshot's history; balance 17,605.09 − 2,605.09 = 15,000.00 ties out") and put it in `"notes"`; it still needs his yes, since it isn't on the slip itself. Otherwise the phone clock minus "N minutes ago". Phone and 747-live are PHT; 1xbet is detected per slip (see section 1). A bet already settled at logging time: set the leg `"status": "Win"` and `"own": true` for his own picks.
- **Cash:** deposits and withdrawals are logged as Ledger lines only when Paolo says so (dry run first). "Opening balance" lines = stakes already sitting in open bets (cash held was 0). Never infer a deposit from a balance gap; ask.
- **After logging, report** `python positions.py` (open stake, max return, balances) and sanity-check the balances against his apps (1xbet / 747 balances he quotes). A gap means missing ledger lines, not a bug to hide.
- `--apply` (here, in `book_sync.py` and `set_leg_results.py`) also refreshes Bets W:Y (Max return, Max return at, Settled at) for the book dashboard; its lines print as `refresh ...`.

