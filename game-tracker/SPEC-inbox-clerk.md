# Spec: inbox clerk

Status: approved 22 Oct 2026 — push only when needed, Sonnet, 8am reminder; QA = weekly 10-item audit for 2 weeks, then decide; slip-number format check.

## What it is
A cloud scheduled task that runs the `check-inbox` skill by itself, so screenshots shared to the
Drive inbox get logged without Paolo asking. Clean items go in under the Write rule (CLAUDE.md);
anything unclear waits for him, and his phone gets a Claude-app push (tested 22 Oct: arrives, tap
opens the run, he answers there and the run carries on).

## Schedule
Hourly at :07 from 08:07 to 00:07 PHT (17 runs a day), quiet 01:00–08:00.
Cron (UTC): `7 0-16 * * *`. Repo `charmofinari-betting/Betting`, environment `betting`.

## One run
1. **Empty inbox → stop.** No push, no log row (costs almost nothing).
2. **Lock.** If another clerk run or a laptop "check inbox" started less than 30 minutes ago and
   hasn't finished, stop. (A lock cell in the `Clerk` tab; `inbox.py` takes and releases it,
   and check-inbox on the laptop uses the same lock.)
3. **Skip files already waiting** for Paolo's answer in an earlier run (listed in the `Clerk` tab),
   so the same question isn't asked every hour.
4. **check-inbox as usual:** dry runs, apply what is clean, move those files to Done.
5. **Log one row** in a new `Clerk` tab:
   `Run at | Files seen | Logged (IDs) | Waiting (file + question) | Run link`.
6. **Push** (one line, under 200 characters):
   - something waits: "2 need you: msw 'Corner Handicap' = corners HC?; Tish slip cut off"
   - all clean: see decision 1.
7. **If he answers in the run:** finish those items (dry run → apply), update the row's Waiting
   cell, move the files to Done.
8. **Waiting longer than a day:** the 08:07 run sends one reminder push.

## Never
- Invent a slip number, time or result; add a word-list entry, account or Ledger line without his
  answer; touch code or commit; settle results (that's the later results hunter).
- The run's saved prompt is not Paolo's "yes": only the Write rule's clean items go in by themselves.

## Build
1. `Clerk` tab (structural: his yes) + lock and waiting-list helpers in `inbox.py`, with tests.
2. check-inbox skill: lock + waiting list + a "clerk mode" section (push, log row).
3. The scheduled task with a self-contained prompt; one supervised test run with a real screenshot.
Rough size: half a day.

## Slip numbers (23 Oct 2026)
`slip_no.py` learns each book's number format from the Bets tab (bet88 19 digits, Solaire 18, 1xbet 11,
747-live 10, msw.ph `XX1-G6F-SRW-CHS`); a number that doesn't fit is a PROBLEM. Books with < 5 numbered
slips aren't checked but still count for guessing. `"account": "?"` → the dry run lists the accounts and
the books the number fits, so the clerk asks "bet88?". No number on the screenshot (msw.ph shows it only
right after placing): `"book_slip_no": null` → own key `<account>-<type>-<MMDD>-<HHMM>` (Paolo's call).

## Weekly QA audit (first 2 weeks: Mon 26 Oct and Mon 2 Nov 2026, 09:00 PHT)
Routine "Clerk audit", Opus (a different reader than the clerk's Sonnet), read-only except one Clerk row.
`audit.py sample` picks 10 random clerk-logged items from the last 7 days and prints their sheet fields
plus the Done screenshots that could hold them; `audit.py pull` downloads those. The run compares field by
field (slip №, placed, account, stake, odds, each leg's match / market / side / line / odds; tips: match,
market, line, odds, kickoff), logs one line `clerk.py log --by audit --seen N --logged "<result>"`, and
pushes it. Error rate above zero → Paolo decides: a second read for slips, or the clerk on Opus.
