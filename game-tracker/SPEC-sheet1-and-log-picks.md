# Spec: Sheet1 rework + log-picks

Status: **draft for Paolo's review** (2026-10-08). Nothing below gets built until he approves it.

## 1. Scope
**In:** the friend-shared picks sheet ("SportsBetting"): new Sheet1 layout, migration of the existing rows, and a repeatable way to log picks from screenshots (`log-picks`).
**Out (later phases):** private sheet (ledger, stakes, multis), multis builder, automatic settlement via api-sports, closing odds.

## 2. Principles
- The friend sheet records **tips only**: no stakes, books or balances.
- One row = one selection, every field filled on every row (no "date only on the first row").
- The bet is stored as structured fields, not decoded from free text later.
- Every script runs as a dry run by default; `--apply` writes. A Google service account in Paolo's personal project; key in `secrets/`.
- No company code, data or credentials anywhere.

## 3. New Sheet1 columns

| Col | Field | Filled by | Notes |
|---|---|---|---|
| A | ID | script | `T-0001`, sequential, never reused |
| B | Kickoff (PHT) | script / Paolo | date+time; blank = "No kickoff". Tennis: Paolo |
| C | Sport | script | Football / Basketball / Tennis, from the league list |
| D | Country | screenshot | tennis: tour (ATP, ATP 1000, Challenger, WTA) |
| E | League | screenshot | canonical spelling via the alias list |
| F | Home | screenshot | split from "Event" on ` vs ` |
| G | Away | screenshot | doubles keep the "A / B" form |
| H | Market | script | dropdown, see §4 |
| I | Period | script | FT / 1H / 2H |
| J | Side | script | Home / Away / Over / Under / Yes / No |
| K | Line | script | number, blank for ML/BTTS |
| L | Selection (as sent) | screenshot | e.g. `AWAY -0.25`, kept for checking |
| M | Tip odds | screenshot | number |
| N | Score | settlement | `2-1`, plus `HT 1-0` when the market needs it |
| O | Result | settlement / Paolo | Won / Lost / Half Won / Half Lost / Void |
| P | Status | sheet formula | Upcoming / In play / Needs result (KO + 2.5h) / No kickoff / Settled, same rules as now |
| Q | Closing odds | later | empty until a source is chosen |
| R | Notes | Paolo | free text |

## 4. Vocabulary (one fixed list, in `game-tracker/vocab.json`)
**Markets:** Handicap (AH in football, spread in basketball/tennis), Total, Team total, Moneyline, BTTS, Corners, Cards, Win either half, Win both halves, Score in both halves, Both halves over, Other.
**Parsing rules for "Selection (as sent)"**, all from forms already in the sheet:

| As sent | Market | Period | Side | Line |
|---|---|---|---|---|
| `HOME -0.25`, `AWAY 0.0` | Handicap | FT | Home/Away | -0.25 / 0.0 |
| `HT HOME -4.5` | Handicap | 1H | Home | -4.5 |
| `OVER 2.5`, `UNDER 170.5` | Total | FT | Over/Under | 2.5 |
| `OVER 1.5 FH` / `FH OVER 1.5` | Total | 1H | Over | 1.5 |
| `ML HOME` | Moneyline | FT | Home | — |
| `BTTS YES`, `BTTS YES 2H` | BTTS | FT / 2H | Yes/No | — |
| `CORNERS UNDER 9.5` | Corners | FT | Under | 9.5 |
| `CARDS UNDER 4.5` | Cards | FT | Under | 4.5 |
| `HOME TEAM OVER 1.5 [FH]` | Team total | FT/1H | Over/Under (which team is encoded as `Home Over` / `Away Over`) | 1.5 |
| `HOME WIN EITHER HALF` etc. | the half markets | FT | Home/Away | — |

The exact team-total and half-market encodings will be pinned down from the existing rows during the migration dry run; anything that doesn't parse is listed, not guessed.

**Aliases:** league and team aliases map new spellings to the one already in the sheet (e.g. *SuperLiga României* → *SuperLiga România*). The list grows as new names appear; a new alias is always shown in the dry run.
**League → sport:** moves from the Leagues tab into `vocab.json`. The Leagues tab stays as a read-only mirror for the friend.

## 5. Calc, Positions and Dashboard
- **Calc keeps its exact column layout**, so Positions and Dashboard keep working unchanged.
- Its formulas are rewritten to read the new structured columns (simple lookups, no regex). The 22+ detailed market labels stay the same ("Asian handicap - giving", "Spread - favourite", …), plus new ones: **Corners Over/Under** and **1st-half spread**.

## 6. Migration of the existing 663 rows
1. Copy the current Sheet1 to a tab named `Archive` (untouched, kept until Paolo signs off).
2. Parse each row: fill the kickoff down within each match group, split Event into Home/Away, parse Selection into Market/Period/Side/Line, assign IDs in current row order.
3. **Dry run output:** the full new table as a local file, a list of rows that failed to parse, and every reclassification (e.g. 19 corners rows Other → Corners).
4. **Check:** totals before vs after must match: bets, settled, pending, units P&L, ROI, per sport. Per-market numbers may only differ where a row was knowingly reclassified.
5. Paolo approves, then `--apply`.

## 7. log-picks (screenshot → rows)
Three parts:
1. **Skill** `.claude/skills/log-picks/SKILL.md`: the procedure Claude follows when Paolo sends screenshots and says "log these" or `/log-picks`:
   read every row (ignore the summary row at the top of the table) → write them to a TSV exactly as shown → run the script as a dry run → show Paolo the table → `--apply` only on his "yes".
2. **`vocab.json`**: §4.
3. **`log_picks.py`**: parses, applies aliases, infers sport, rejects anything outside the vocabulary, deduplicates, assigns IDs, writes.
   - **Duplicate key:** Home + Away + Market + Period + Side + Line (names normalised: no accents, lower case). Kickoff isn't in the key because the screenshots don't carry it.
   - **Dry run shows:** new rows, skipped duplicates, unknown leagues/teams (with suggested aliases), parse failures.
   - **Kickoff:** blank for now (status "No kickoff"). Filled from api-sports in the settlement phase; tennis by Paolo.

## 8. Testing
- Unit tests for the parser: every Selection string in the current sheet, plus the 35 rows from Paolo's sample screenshots (33 already logged + the 2 Serbian rows added 2026-10-08), which must come out as "all duplicates".
- The migration check in §6 step 4.

## 9. Assumptions — correct me
- Only Paolo adds rows; the friend only reads.
- Tennis kickoffs and results are entered by Paolo.
- No "tip received" time.
- League names already in the sheet stay as they are; new spellings get aliased to them.
- Status keeps the 2.5h "Needs result" rule for all sports.

## 10. Build order
1. Parser + tests on the existing rows.
2. Migration dry run → Paolo review → apply.
3. log-picks skill + script → test on the sample screenshots.
4. Next phase: api-sports coverage pilot, then settlement.

## 11. Changes after staging review (2026-10-08)
- **Match column added** (F, "Home vs Away") so a fixture is easy to find; Home/Away stay as G/H for matching. All later columns shift by one: Market I, Period J, Side K, Line L, Selection M, Tip odds N, Score O, Result P, Status Q, Closing odds R, Notes S.
- Team totals are stored as Market "Home team total" / "Away team total" with Side Over/Under (instead of Side "Home Over").
- **Formatting rebuilt** on the new columns: Status colours (No kickoff grey, In play amber, Needs result red) on Q; dropdowns on Market, Period, Side, Result. The old Settlement dropdown and the colour rules on the old positions are removed.
- **New "Open picks" tab:** every pick whose match isn't finished (Upcoming / In play / No kickoff), soonest kickoff first, same-match picks together. Updates itself.
- Corners get their own Side/Position ("Corners"), like Cards.
