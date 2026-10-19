---
name: check-inbox
description: Pick up the tip, bet-slip and balance screenshots Paolo (or Pat/Tish) shared from their phone into the Google Drive "Betting Inbox" (Tips / Slips / Balances folders) and log them through log-picks / log-bets. Use when Paolo says "check inbox", "check the drive", "anything in the inbox?", or types /check-inbox.
---

# check-inbox

Drive `Betting Inbox/Tips` and `/Slips` → `game-tracker/inbox.py` → the usual log-picks / log-bets flow → files moved to `Done`.
This skill only fetches and routes. The logging rules live in the other two skills: follow them exactly.

## 1. Pull
```
cd C:/Users/jnplz/betting/game-tracker
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python inbox.py pull
```
Downloads every file still in Tips/Slips to `game-tracker/out/inbox/` (git-ignored) and prints its Drive id.
Read-only on Drive. Empty inbox → say so in one line and stop.

## 2. Read and route
Open each downloaded image with Read.
- **Tips/** → tips table → follow the `log-picks` skill (TSV in the scratchpad, dry run).
- **Slips/** → bet slip → follow the `log-bets` skill (JSON in the scratchpad, dry run).
- **Balances/** (or a balance screenshot in a holder's `Slips/<Holder>/`) → the app's **one balance figure** for one account → `balances.py check` dry run (below). Account = the app shown (+ the holder if it came from their folder), exactly as in Accounts. Checked at = time visible on the screenshot, else the file's Drive time converted to PHT (`inbox.pht_from_created`). A split balance (cash / bonus / pending) or an unclear account: leave it and ask.
- **Order:** slips first, then balance checks, so the expected balance already includes this batch's slips.
- A file in the wrong folder: route it by what it shows, and mention it.
- Not a tip table or slip, unreadable, or cut off (no slip header): leave it in the inbox and ask Paolo. Never invent a slip number, time or result.
- Several screenshots of one tips table or one slip: treat them together.

### Balance check commands
```
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python balances.py check "<account>" <amount> --at "19 Oct 2026 14:05" --source <drive id>   # dry run
... same + [--after-ledger <rows>|none] [--note "possible cause"] --apply
```
Prints app vs expected-at-check and a trace. A gap ≥ 1.00: say it plainly with the trace's most likely cause (a ticket the book settled that the sheet hasn't, an unlogged deposit/withdrawal) and put that in `--note` as a *possible* cause. Never "fix" a gap: Ledger/Bets change only through their own confirmed flows. ASK lines (same-day Ledger lines) need Paolo's answer → `--after-ledger`. First time only: `balances.py setup` (dry run, then `--apply` on his yes) adds the Balance checks tab.

## 3. One dry-run summary, then wait
Show Paolo one compact summary for the whole batch (he reads on a phone): new tips, new tickets, balance checks (match / gap), PROBLEM / CHECK / ASK lines, files skipped and why. Write nothing until he says yes.

## 4. Apply, then clear the inbox
On his yes: `--apply` in log_picks / log_bets as their skills say. Then move **only the files whose contents were logged or found already logged**:
```
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python inbox.py done <id> <id> ...           # dry run
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python inbox.py done <id> <id> ... --apply
```
Files with open questions stay in the inbox for the next check. Finish with the log-bets report (positions) if slips were logged.

## Notes
- Folder ids are in `inbox.py`. The bot (`sheet-bot@betting-511008`) has Editor on Betting Inbox only.
- **Holder slips** sit in `Slips/<Holder>/` (Pat, Tish, Grace; each folder shared only with that person). The pull shows "(placed by Pat)": set `"placed_by"` to that name and use that holder's account (e.g. `msw.ph Pat`). If the book on the slip doesn't match the holder's account, ask.
- A new holder: Paolo creates `Slips/<Name>` (name exactly as in the Accounts tab Holder column) and shares it with them as Editor. No code change needed.
- Local copies in `out/inbox/` can be deleted any time; Drive `Done` keeps the originals.
