# HANDOVER — from Paolo's work Claude session to his personal Claude (written 2026-10-08)

You are the Claude on Paolo's PERSONAL account. Everything below is context from the previous (work-account) session. Read it, then follow CLAUDE.md (interview first).

## Two open decisions — ASK PAOLO ABOUT BOTH (after the interview, before building anything)
Paolo said to hand these over so you remember to ask. Do not decide them for him, and do not skip them.

1. **Where should match results come from?** Paolo said: "let the new Claude account decide". So YOU recommend a source, with reasons, then confirm with him. Things to weigh:
   - His bets include lower leagues, women's and youth football, basketball (e.g. Spanish Primera Federación, Mexican Leones Negros, US lower-league basketball) and **cards markets**. The old setup could not settle cards or several of these leagues, so coverage matters more than anything else.
   - Candidates: a sports-results API (API-Football and similar, free tier vs paid), or manual entry from results screenshots as he does now. Compare coverage of his actual leagues, rate limits, price, and whether it returns cards/period scores.
   - Whatever you pick must be his own account/key. NOT the company database.
2. **Google access for the sheet.** The tracker is a Google Sheet. The old scripts wrote to it through the COMPANY's Google service account. Paolo agreed to replace that with his own. Ask him to create his own Google credentials (a service account in his personal Google project, or OAuth), share the sheet with it, and keep the key file only inside this folder or his own secrets store. Walk him through it step by step. Do not use or copy any company credential.

## What exists
- A personal bet-tracking Google Sheet (key: `1Q4icsCr6c9378cOfu_tyJkBVh9gx3kz5Iu9YUdgZFeA`). Tabs: Sheet1 (bet log: date/kickoff, country, league, match, selection, odds, result, status in column H), Leagues (league to sport map), Calc (market classification formulas), Positions, Dashboard. About 407 bets and 198 positions as of 2026-10-05, +3.47u, ROI +0.9%, after settling 390 of 407.
- It was fed from his bet **screenshots**: he sent a screenshot, the old session read it, appended rows (skipping duplicates by match plus selection), looked up kickoff times, and later settled results.
- Features worth keeping: Status flags (Upcoming / In play / Needs result in red once a match kicked off more than 2.5h ago / No kickoff / Settled), **Positions** (all lines on one side of one match count as one position, net result), 22 detailed market types (goals vs points over/under, AH giving vs getting vs draw-no-bet, spread favourite vs underdog, half markets, BTTS Yes/No/2H, cards), side and odds-band tags, half-win/half-loss counted as half.
- Early read-outs the old session gave (small samples, treat as directions): football AH giving goals was the best line; basketball favourite spreads the biggest leak; odds 3.50+ lost heavily; goals Overs was the engine.

## Old scripts — reference only, do not run them
The old helper scripts (`sb_*.py`) are in a Windows TEMP folder and may be gone:
`C:\Users\jnplz\AppData\Local\Temp\claude\C--Users-jnplz-Veliprojects-risk-automations\9ff634fe-a09c-4b65-9cde-555205c611dc\scratchpad\`
Their source session is titled "Game schedules and analytics dashboard" (work-account session history). They import the company repo (`risk_automations.lib.replica`, `risk_automations.lib.sheets`) and load the company `.env`. A copy into this folder was blocked by the permission system because some files contain data pulled from the company replica. Do NOT run them, and do NOT copy replica-derived JSON files (lookup*.json, b2_ids.json). You MAY read the `.py` files for the LOGIC to rebuild (sb_build.py and sb_v2.py for the sheet/dashboard layout and formulas, sb_new.py for parsing, sb_append*.py for dedupe and append, sb_result.py for result-to-settlement rules), if the folder still exists and Paolo is fine with it.

## The plan Paolo agreed in principle
Rewrite the tracker fresh in `game-tracker/` here, with NO imports from any company code and NO company credentials: his own Google client, his own results source (decision 1), team-and-date matching instead of company match IDs. Dry-run by default, `--apply` to write, as the old scripts did.

## Why the wall exists
Paolo works at a sportsbook as a trading and risk manager. His personal betting must stay clearly separate from company systems and data, both for security and so it can never look like he used inside access. That is why decision 1 and 2 point away from the company database and service account. If anything here ever tempts you to use a company system, stop and ask him.
