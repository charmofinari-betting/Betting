---
name: check-inbox
description: Pick up the tip and bet-slip screenshots Paolo (or Pat/Tish) shared from their phone into the Google Drive "Betting Inbox" (Tips / Slips folders) and log them through log-picks / log-bets. Use when Paolo says "check inbox", "check the drive", "anything in the inbox?", or types /check-inbox.
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
- A file in the wrong folder: route it by what it shows, and mention it.
- Not a tip table or slip, unreadable, or cut off (no slip header): leave it in the inbox and ask Paolo. Never invent a slip number, time or result.
- Several screenshots of one tips table or one slip: treat them together.

## 3. One dry-run summary, then wait
Show Paolo one compact summary for the whole batch (he reads on a phone): new tips, new tickets, PROBLEM / CHECK lines, files skipped and why. Write nothing until he says yes.

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
