---
name: log-picks
description: Log Paolo's tipster picks from screenshots into the SportsBetting sheet (Sheet1), the same way every time. Use when Paolo sends screenshots of the tips table (Country / League / Event / Market / Sent Odds) and asks to log, add or update the picks, or types /log-picks.
---

# log-picks

Turns screenshots of the tips table into Sheet1 rows through `game-tracker/log_picks.py`,
which does the checking, de-duplication, IDs and writing. You transcribe; the script decides.
Never write picks into the sheet any other way.

## 1. Transcribe
For each screenshot, write one line per pick into a TSV file in the session scratchpad
(not the project folder), tab-separated, in the table's own column order:

```
Country<TAB>League<TAB>Event<TAB>Market<TAB>Sent Odds
```

- Copy text **exactly as shown**: accents (Rzeszów, Gdańsk, București), capitals, "/" in doubles names. Don't fix or translate names; aliases do that.
- Skip the summary row at the top of the table (the one with only an odds number) and any repeated header rows.
- Screenshots often overlap: transcribe everything; the script drops repeats.
- If a cell is cut off or unreadable, don't guess: list it and ask Paolo.
- Tennis kickoffs: if Paolo gives them, add a 6th column `YYYY-MM-DD HH:MM` (PHT).
- Re-read your TSV against the screenshot once before running, line by line (odds especially).

## 2. Dry run
```
cd game-tracker   # from the repo root (laptop or cloud)
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python log_picks.py <tsv>
```
Show Paolo: how many are new / already logged / problems, the new rows as a short table
(match, selection, odds, kickoff), and every PROBLEM and CHECK line.

## 3. Resolve problems (never guess)
- **Unknown league:** if it's a new spelling of a league already in the word list → propose a `league alias`. If it's really new → ask Paolo the sport, then add a `league sport`. Also tennis: if the Country column is a tour not in the list, ask before adding a `tennis tour`.
- The word list is the **Vocab tab** in the private book (`vocab.py`; `vocab.json` is gone). Add an entry, dry run first: `../.venv/Scripts/python vocab.py add "league alias" "<screenshot spelling>" "<sheet spelling>" --apply` (kinds: league sport, league alias, team alias, api team alias, tennis tour).
- **CHECK "new team looks like existing":** ask Paolo if it's the same team; if yes, add a `team_aliases` entry (screenshot spelling → sheet spelling).
- **Unrecognised selection:** don't map it by hand. Tell Paolo; a new market type needs a `parse.py` change with tests.
- Show any word-list addition in the summary, then run the dry run again until clean.

## 4. Apply (Write rule in CLAUDE.md)
Clean dry run (no PROBLEM / CHECK, no vocab edit) → apply straight away; otherwise after Paolo answers step 3.
```
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python log_picks.py <tsv> --apply
```
Report the IDs and sheet rows written.

## 5. Then sync kickoffs
Run `sync.py` (dry run) right after logging, and `--apply` straight away if clean (else show Paolo the CHECK / not-found lines first):
```
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python sync.py
```
Picks more than a day ahead stay "No kickoff" until a later sync (free-plan window).

## Notes
- Default target is the live sheet. `--staging` targets the staging copy; use it to try anything new.
- Kickoffs for football/basketball come from `sync.py` (api-sports, yesterday..tomorrow only). Tennis kickoffs and results are Paolo's.
- Sync also settles: for finished matches it writes Score (O) and Result (P) from the 90-minute score (basketball incl. OT). ASK lines (postponed/cancelled, corners, cards) and BY HAND lines (tennis, matches before the window) go to Paolo; enter his answers in Result (P) via a dry-run-first write.
- **"sync" also settles the private book:** after `sync.py --apply`, run `book_sync.py` (dry run) — it settles his ticket legs from the tips' scores on each leg's own line, and computes system-bet returns — then `--apply` (same rule: clean → straight away).
- When Paolo says "sync" on its own: run `sync.py` dry run, apply the clean results straight away, show him the CHECK / not-found lines. CHECK lines: ask him, then re-run with `--accept <IDs>`.
- Duplicates are matched on Home + Away + Market + Period + Side + Line (accents and case ignored), not on kickoff.
