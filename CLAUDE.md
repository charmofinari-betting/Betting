# CLAUDE.md — Paolo's personal sports-betting workspace

This folder is **Paolo's own sports-betting work**. It is NOT Veli/Velitech work, and the Claude account used here is his **personal** one.

## Read HANDOVER.md first
`HANDOVER.md` in this folder is the handover from his work-account session. It lists **two open decisions you must ask him about** (where match results come from, and his own Google access for the sheet), what the existing tracker is, and the agreed plan. Read it at the start of the first session, then do the interview below, then raise those two decisions before building anything.

## First session: interview him before doing anything else
This is a fresh account with an empty memory. On the first session, do NOT start building. Open with a short, friendly interview, one or two questions at a time, and save what you learn to memory as you go:

1. **Projects** — what betting projects does he have or want? (He already has a bet-tracking Google Sheet: Sheet1 bet log, Positions, Dashboard, a Status column. See "Existing tracker" below.)
2. **Goals** — profit, learning, finding edges, CLV, discipline, something else? What would "working" look like in 3 months?
3. **How he bets** — sports and leagues, market types, typical stakes and staking rules, bankroll, which books he uses.
4. **His edges and weak spots** — what he believes his edges are, and what he thinks leaks money.
5. **Data and tools** — where results/odds data should come from, what he already uses.
6. **How he likes to work with Claude** — plain language, push-back on bad ideas, how much to ask vs. just do.

Don't assume anything about him from other context. Ask. Then write a short summary back and ask him to correct it.

## Ground rules
- **Hard wall from Veli work.** Never use company systems for this: no Veli replica database, no VSB, no company `.env` / `service-account.json` / SSH keys, no Veli repos or their code, no Veli player/bet data. If a task seems to need one, stop and ask him instead.
- Personal betting data and analysis stay in this folder (or his own accounts), never in a company repo, Sheet, vault or Slack.
- Descriptive, not a verdict machine: show him the numbers and the sample sizes, flag small samples, let him decide. Never present a hunch as an edge.
- Explain plainly. He is an industrial engineer and thinks in systems; he is not new to betting.

## Existing tracker (as of 2026-10-05)
A Google Sheet logged from his bet screenshots: ~407 bets / ~198 positions, with a Status column (Upcoming / In play / Needs result / Settled), 22 detailed market types, odds bands, side, and a Dashboard with bet and position KPIs. It was built by an earlier work-account session, and its helper scripts leaned on company systems (Veli replica for match lookups and results, the company Google service account, company repo code). Those dependencies are being replaced — see `game-tracker/` if it exists. Do not reuse the company-dependent parts.
