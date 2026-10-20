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
- **Balances/** (or a balance screenshot in a holder's `Slips/<Holder>/`) → the app's **one balance figure** for one account → `balances.py check` dry run (below). Account = the app shown (+ the holder if it came from their folder), exactly as in Accounts. Checked at = time visible on the screenshot, else the pull's "taken ..." time (`inbox.capture_time`: phone file name, then photo metadata, then upload time; say which when it's upload time, it can be hours late). A split balance (cash / bonus / pending) or an unclear account: leave it and ask.
- **Order (two rounds when a batch has both):** round 1 = tips + slips dry run → apply (straight away if clean, else on his yes). Round 2 = balance checks dry run (now the expected balance includes this batch's slips) → apply the same way. A balance dry run made before the slips are applied shows a wrong gap: never apply one.
- A file in the wrong folder: route it by what it shows, and mention it.
- Not a tip table or slip, unreadable, or cut off (no slip header): leave it in the inbox and ask Paolo. Never invent a slip number, time or result.
- Several screenshots of one tips table or one slip: treat them together.

### Balance check commands
```
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python balances.py check "<account>" <amount> --at "19 Oct 2026 14:05" --source <drive id>   # dry run
... same + [--after-ledger <rows>|none] [--note "possible cause"] --apply
```
Prints app vs expected-at-check and a trace. A gap ≥ 1.00: say it plainly with the trace's most likely cause (a ticket the book settled that the sheet hasn't, an unlogged deposit/withdrawal) and put that in `--note` as a *possible* cause. Never "fix" a gap: Ledger/Bets change only through their own confirmed flows. ASK lines (same-day Ledger lines) need Paolo's answer → `--after-ledger`. First time only: `balances.py setup` (dry run, then `--apply` on his yes) adds the Balance checks tab.

## 3. Dry run, then apply if clean (see "Write rule" in CLAUDE.md)
Always run the dry runs. **Clean** parts of the batch (no PROBLEM / CHECK / ASK line, every leg linked, odds and returns tie out, no vocab edit, a balance check that matches) are applied straight away. Anything **not sure** waits: show Paolo one compact summary (he reads on a phone) of what was applied, what needs his answer, and files skipped and why. A balance gap ≥ 1.00 always waits for him.

## 4. Apply, then clear the inbox
Clean parts right away, the rest on his yes: `--apply` in log_picks / log_bets as their skills say; for balances, re-run the same `balances.py check` line with `--apply` (and the `--note` / `--after-ledger` he agreed). Then move **only the files whose contents were logged or found already logged**:
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
