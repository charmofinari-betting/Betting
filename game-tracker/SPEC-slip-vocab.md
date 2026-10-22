# Spec: slips checked against a word list, word list in the sheet

Status: approved by Paolo 22 Oct 2026 (tab in private book, vocab.json deleted after copy, old parser 2 weeks).

## Problem
1. `log_bets.py` reads each book's market wording with hand-written rules (`parse_slip_market`).
   Every new wording ("Over/Under - Match", "FT Spread", ...) is a code change plus a test:
   about half of the recent commits.
2. Everything the tools learn (league → sport, team spellings, api-sports names) lives in
   `vocab.json` in the repo. A cloud/phone session that learns something has to change a file,
   which lands on a branch and waits for a merge.

## Change

### A. Claude writes the meaning, the script checks it
For each leg, besides the slip text exactly as shown (`market`), the transcription gives:
```json
"label": "Over/Under - Match",          // the book's market name, without team / line / odds
"sel": {"market": "Total", "period": "FT", "side": "Under", "line": 2.75}
```
`log_bets.py` then checks, and any failure is a PROBLEM (so the slip is not clean):
- **Known wording:** `(book, label)` is in the word list, and the list's market/period agree with `sel`.
  An unknown wording is `NEW WORDING`: I ask you once what it means, it goes into the word list,
  and it never asks again.
- **Shape:** market, period and side are allowed values (`parse.py` lists them); the line is there
  when the market needs one, absent when not, and in steps of 0.25.
- **Text agrees:** Over/Under/Yes/No is in the slip text; a team named in the text is the side
  chosen (same name matching as today); the line's number is in the text, unless the word-list
  entry fixes the line (e.g. football 1X2 = handicap -0.5, double chance = +0.5) or says it is
  a split line ("2.5,3" = 2.75).
- **Second opinion:** the old parser still runs. If it reads the leg and disagrees with `sel`,
  it's a PROBLEM. If it can't read it, that's no longer a problem. After 2 clean weeks, the old
  parser is deleted.
Everything else (tip matching, slip maths, time zones) stays as it is.

### B. The word list moves to a `Vocab` tab in the private book sheet
One row per entry: `Kind | Key | Meaning | Extra | Added at | Added by`.
| Kind | Key | Meaning | Extra |
|---|---|---|---|
| slip wording | `msw.ph: Over/Under - Match` | `Total FT` | split line `a,b` |
| slip wording | `bet88: 1x2` | `Handicap FT` | football line -0.5, else Moneyline |
| league sport | `Vysshaya Liga` | `Basketball` | |
| league alias | `SuperLiga României` | `Liga I` | |
| team alias | `Ekenas` | `EIF` | |
| api team alias | `FF Jaro` | `Jaro` | |
| tennis tour | `ATP 500` | | |
- The sheet is the master; `vocab.json` is deleted after a one-off copy into the tab.
- One new `vocab.py` module loads and saves it (one read per run); `log_picks`, `log_bets` and `sync`
  use it instead of the file. Tests use a small fixture copy instead of the live list.
- New rows are added by the same flows as today (alias, league, wording) and follow the Write rule:
  any word-list change is "not sure", so it waits for your yes.
- Phone/cloud sessions learn without code changes or merges.

## Not in scope
Results source, tip seen time, tips (log-picks) market parsing (`parse.py` rules for the tipster's
format rarely change and stay as code).

## Build order (each step tested, dry run, then applied)
1. `vocab.py` + `Vocab` tab (structural: your yes), copy `vocab.json` in, switch the three readers.
2. Slip wordings seeded from today's parser rules (one row per wording it knows).
3. `label`/`sel` check in `log_bets.py`, old parser as second opinion; update the log-bets skill.
4. After 2 clean weeks: delete `parse_slip_market`.
Rough size: a day.
