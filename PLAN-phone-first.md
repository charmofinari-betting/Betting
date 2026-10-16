# Plan: phone-first betting workflow

Status: draft for Paolo (16 Oct 2026). Goal: nothing waits for the laptop to be opened.

## The model
| Part | What | Where it runs | Who |
|---|---|---|---|
| Capture | Tip and slip screenshots | Phone → Drive `Betting Inbox/Tips`, `/Slips` | Paolo, Pat, Tish |
| Fetch | Daily match results (raw scores only) | Always-on job → "Results cache" tab | Automatic |
| Decide | Dry run → "yes" → write to sheet | Claude Code, driven from the phone | Paolo + Claude |
| Look | Capital, withdrawals, balances | Funds tab in the Sheets app | Paolo, any time |

Rules that don't change: dry run first, write on his yes; never invent a slip number, time or result.

## Target daily routine
- **Any time:** share screenshots to the Drive folder (10 seconds each).
- **Once or twice a day, from the phone:** "check inbox" → approve → "sync" → approve.
- **Any time:** open the Funds tab, or ask "funds?".

## Phases
**0. Today, nothing to build**
- Laptop stays on at home with keep-awake; Paolo uses the Claude app → Code → this workspace (Remote Control).
- Commit the pending vocab and parser edits.
- Done when: he logs one slip from his phone.

**1. Funds tab + `funds` skill**
- Sheet tab: capital (opening + deposits), total withdrawn, cash per book, open stakes, P&L check line. Own books separate from Pat/Tish.
- Skill: same numbers in a few lines on request; flags a gap if the sheet doesn't tie out.
- Done when: the numbers match the books he checks in the apps.

**2. Drive inbox + `check-inbox` skill**
- Folder shared with the personal service account only; Drive access enabled on it (free).
- Skill reads new files → log-picks or log-bets dry run → apply on yes → moves files to `Done`.
- Done when: a day of tips and slips gets logged without the laptop being touched.

**3. Always-on results fetch**
- Private GitHub repo + a daily scheduled job: fetch api-sports results into a "Results cache" tab. It never settles anything.
- `sync` settles from the cache, so missed days are not lost.
- Flashscore through the browser as a fallback (tennis, matches the feed missed), not scraped.
- Done when: a week passes with no unsettleable missed day.

**4. Optional: cloud sessions**
- Only if keeping the laptop on gets annoying. Needs Paolo's OK on keys in the cloud setup. Same Pro usage limits.

**Later:** tip scorecard (is the edge real?), overlap check before placing.

## Decisions needed
1. Is the laptop OK staying on at home? (Phase 0)
2. Code on a private GitHub repo? (Phase 3)
3. Does the tips platform have a web view? (could skip tip screenshots)
