# Book Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A phone page showing a card per sportsbook account: expected cash vs the app balance Paolo last gave us, problems first.

**Architecture:** Python (existing `game-tracker/`) keeps the sheet up to date: two new Bets columns (Max return, Settled at) refreshed after every book write, and a new `Balance checks` tab filled from balance screenshots via check-inbox. A Google Apps Script web app in Paolo's own Google account reads the sheet live and renders the cards; its logic sits in one pure file tested with Node.

**Tech Stack:** Python 3 + gspread (existing client in `inspect_sheet.py`), `unittest`; Google Apps Script (V8) + HtmlService; Node 24 `node --test` for the page logic.

**Spec:** `game-tracker/SPEC-book-dashboard.md`

## Global Constraints
- Every sheet-writing command is a dry run unless `--apply`; `--apply` only after Paolo's yes.
- Never adjust Ledger or Bets to close a gap. Gaps are shown, with a *possible* cause in Note.
- Crypto stays in native units (TRX, USDT); never folded into ₱ totals.
- Holder accounts (Holder ≠ Paolo in Accounts) are never added to Paolo's figures.
- The web page is read-only; deployed "Execute as: me", "Who has access: only myself".
- Matched = |gap| < 1.00 in the account's own currency. Stale = last check older than 3 days.
- Time zone: PHT (`Asia/Manila`). Sheet time format: `19 Oct 2026 14:05` (as in Bets "Placed (PHT)"); Ledger dates `19 Oct 2026`.
- Personal accounts only (Paolo's Google account, `sheet-bot@betting-511008`). Nothing from work.
- The private book has no staging copy: verify with unit tests + live dry runs (read-only) before any apply.
- Run tests from `game-tracker/`: `PYTHONIOENCODING=utf-8 ../.venv/Scripts/python -m unittest tests.<module> -v`.
- Commit locally after each task; Paolo runs `git push` himself.

## Review Focus
1. Screenshot with no visible time → Checked at = Drive createdTime converted from UTC to PHT (Task 4 test `test_created_time_to_pht`).
2. A ticket corrected back to Open (leg result overwritten) → its Settled at is cleared, Max return comes back (Task 1 test `test_reopened_ticket_clears_settled_at`).
3. Account name not exactly in Accounts (e.g. "msw" could be Pat or Grace) → `balances.py check` refuses and lists candidates (Task 3 test `test_unknown_account_refused`).
4. Crypto account → expected, app balance and gap all in native units, never ₱ (Task 5 test `crypto card stays in native units`).
5. Ticket with unparseable or blank Placed (PHT) → rebuild lists it as an ASK instead of guessing (Task 3 test `test_unparseable_placed_time_is_asked`).

---

### Task 1: Bets refresh — Max return, Max return at, Settled at

**Files:**
- Create: `game-tracker/bets_refresh.py`
- Test: `game-tracker/tests/test_bets_refresh.py`

**Interfaces:**
- Consumes: `positions.summarise(bets, legs) -> (rows, stake_php, max_return_php)`, rows = `(sid, account, kind, stake, max_return_native)`.
- Produces:
  - Bets columns: W `Max return` (index 22), X `Max return at` (23), Y `Settled at (PHT)` (24). Constant `COLS = {"max": 22, "max_at": 23, "settled": 24}`.
  - `BEFORE = "before tracking"` (Settled at value for tickets settled before this column existed).
  - `refresh_plan(bets: list[list[str]], legs: list[list[str]], now: str, first_run: bool) -> list[tuple[int, str, str, str]]` — `(sheet_row, max_return, max_at, settled_at)` only for rows whose W/X/Y change. `bets`/`legs` exclude the header; sheet_row is 1-based (data starts at 2).
  - `refresh(book, apply: bool, now: str | None = None) -> list[str]` — reads Bets + Legs, writes header W1:Y1 if missing (that read = `first_run`), batch-writes the plan with `value_input_option="RAW"` when `apply`, returns printable lines.
  - CLI: `python bets_refresh.py [--apply]`.

- [ ] **Step 1: Write the failing tests**

```python
NOW = "19 Oct 2026 14:05"
# bet()/leg() helpers as in tests/test_positions.py, widened to 25 columns

def test_open_ticket_gets_max_return_and_stamp(self):
    plan = refresh_plan([bet("S-1", "Double", "1,000.00")], [leg("S-1", "2.0"), leg("S-1", "3.0")], NOW, False)
    self.assertEqual(plan, [(2, "6000.00", NOW, "")])

def test_newly_settled_ticket_gets_settled_at_and_loses_max(self):
    b = bet("S-1", "Double", "1,000.00", result="Won"); b[22], b[23] = "6000.00", "18 Oct 2026 09:00"
    self.assertEqual(refresh_plan([b], [], NOW, False), [(2, "", "", NOW)])

def test_first_run_marks_old_settled_tickets_before_tracking(self):
    plan = refresh_plan([bet("S-1", "Single", "500", result="Lost")], [], NOW, True)
    self.assertEqual(plan, [(2, "", "", BEFORE)])

def test_reopened_ticket_clears_settled_at(self):
    b = bet("S-1", "Single", "500"); b[24] = "18 Oct 2026 22:10"
    self.assertEqual(refresh_plan([b], [leg("S-1", "1.9")], NOW, False), [(2, "950.00", NOW, "")])

def test_unchanged_rows_are_not_rewritten(self):
    b = bet("S-1", "Single", "500", result="Lost"); b[24] = "18 Oct 2026 22:10"
    self.assertEqual(refresh_plan([b], [], NOW, False), [])
```

- [ ] **Step 2: Run to verify they fail**
Run: `PYTHONIOENCODING=utf-8 ../.venv/Scripts/python -m unittest tests.test_bets_refresh -v`
Expected: FAIL / ImportError (`bets_refresh` missing).

- [ ] **Step 3: Implement `refresh_plan` and `refresh` in `bets_refresh.py`**
Max return per open ticket comes from `positions.summarise` (call it once on all bets, map by sid), formatted `f"{x:.2f}"`. An open ticket whose Max return is unchanged is not rewritten (so X keeps its older time); any change rewrites W and X. Settled = Result (col H) ≠ "Open" and Slip ID present.

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Live dry run**
Run: `PYTHONIOENCODING=utf-8 ../.venv/Scripts/python bets_refresh.py`
Expected: header W1:Y1 would be added; ~200 settled tickets "before tracking"; 16 open tickets with a Max return whose total (PHP accounts) matches `positions.py`. Show Paolo; `--apply` only on his yes.

- [ ] **Step 6: Commit**
`git add bets_refresh.py tests/test_bets_refresh.py && git commit -m "bets_refresh: Max return and Settled at columns on Bets"`

---

### Task 2: Run the refresh after every book write

**Files:**
- Modify: `game-tracker/log_bets.py` (end of `main`, after the Bets/Legs/Ledger writes)
- Modify: `game-tracker/book_sync.py` (end of `main`, after the writes)
- Modify: `game-tracker/set_leg_results.py` (end of `main`, after the writes)
- Modify: `.claude/skills/log-bets/SKILL.md` (one line: the refresh runs on apply and prints its lines)

**Interfaces:**
- Consumes: `bets_refresh.refresh(book, apply=True) -> list[str]` (Task 1).
- Produces: nothing new.

- [ ] **Step 1:** In each of the three `main`s, on the apply path only, call `refresh(book, apply=True)` after the existing writes and print each returned line prefixed `  refresh `. `set_leg_results.py` currently opens only the Legs worksheet: keep the `book` object so it can be passed. The ticket Result is a sheet formula over Legs, so the refresh must re-read Bets after the leg writes (it does: `refresh` reads fresh).
- [ ] **Step 2:** Run the whole suite: `PYTHONIOENCODING=utf-8 ../.venv/Scripts/python -m unittest discover -s tests -v` — all PASS.
- [ ] **Step 3:** Dry-run each script once on live (`log_bets.py <recent json>` without `--apply`, `book_sync.py`, `set_leg_results.py` with no args → empty) to confirm nothing breaks; dry runs must not call the refresh.
- [ ] **Step 4: Commit** `"book writes refresh Max return / Settled at"`.

---

### Task 3: balances.py — expected balance as of a screenshot, Balance checks tab

**Files:**
- Create: `game-tracker/balances.py`
- Test: `game-tracker/tests/test_balances.py`

**Interfaces:**
- Consumes: Balances tab (col A Account, I Balance), Legs (A Slip ID, K Kickoff (PHT)), Bets (A id, B Placed (PHT), C Account, E Stake, I Return, Y Settled at), Ledger (A Date, B Account, C Type, D Amount), Accounts (A Account), constant `bets_refresh.BEFORE`.
- Produces:
  - Tab `Balance checks`, header exactly: `Checked at (PHT) | Account | App balance | Expected at check | Gap | Source | Note`.
  - `LEDGER_SIGN = {"Opening balance": 1, "Deposit": 1, "Withdrawal": -1, "Transfer in": 1, "Transfer out": -1, "Bonus": 1, "Adjustment": 1}` (mirrors the Balances formulas in `setup_book.py`).
  - `parse_pht(s: str) -> datetime | None` for `"19 Oct 2026 14:05"` and date-only `"19 Oct 2026"`.
  - `expected_as_of(account: str, at: datetime, balance_now: float, bets: list[list[str]], ledger: list[list[str]], after_rows: set[int], legs: list[list[str]] = ()) -> tuple[float, list[str], list[str]]` → `(expected, trace_lines, asks)`. Rules:
    - Bet on `account` placed after `at`: **+stake**.
    - A settled ticket's **settle time** = the earlier of its Settled at stamp and (latest leg Kickoff (PHT), Legs col K, + 3 h). The stamp is when the *sheet* learned the result, which can be a day after the book paid, so the kickoff estimate catches the common case. Settled at = `BEFORE` or blank-but-settled: assume before, add a trace line saying so.
    - Bet on `account` with settle time after `at`: **−Return**.
    - Ledger line on `account` dated after `at`'s date: **−sign×amount**. Dated the same day: counted as before the check unless its sheet row is in `after_rows` (then undone); every same-day line goes into `asks`.
    - Placed time blank/unparseable on that account: an ask, not counted.
  - `check(book, account: str, amount: float, at: str, source: str, note: str, after_rows: set[int], apply: bool) -> list[str]`.
  - CLI: `python balances.py setup [--apply]` (adds the tab if missing) and `python balances.py check "<account>" <amount> --at "<PHT time>" --source <drive id> [--note "..."] [--after-ledger 41,42] [--apply]`. Prints account, app balance, expected, gap (2 dp, account's currency), trace and ASK lines. Refuses to apply while asks are unanswered (same-day Ledger lines need `--after-ledger` or an explicit `--after-ledger none`).

- [ ] **Step 1: Write the failing tests** (`AT = parse_pht("19 Oct 2026 14:00")`)

```python
def test_bet_placed_after_check_adds_stake_back(self):
    e, _, asks = expected_as_of("bet88", AT, 1000.0, [bet("S-1", "19 Oct 2026 15:00", "bet88", "200")], [], set())
    self.assertEqual((e, asks), (1200.0, []))

def test_ticket_settled_after_check_removes_return(self):
    b = bet("S-1", "18 Oct 2026 10:00", "bet88", "200", ret="500", settled="19 Oct 2026 16:00")
    self.assertEqual(expected_as_of("bet88", AT, 1000.0, [b], [], set())[0], 500.0)

def test_kickoff_estimate_beats_late_stamp(self):
    # book paid at ~13:00 (kickoff 10:00 + 3h), sheet only learned at 20:00: settled before the 14:00 check
    b = bet("S-1", "19 Oct 2026 09:00", "bet88", "200", ret="500", settled="19 Oct 2026 20:00")
    legs = [leg("S-1", kickoff="19 Oct 2026 10:00")]
    self.assertEqual(expected_as_of("bet88", AT, 1000.0, [b], [], set(), legs)[0], 1000.0)

def test_before_tracking_counts_as_settled_before(self):
    b = bet("S-1", "10 Oct 2026 10:00", "bet88", "200", ret="500", settled=BEFORE)
    self.assertEqual(expected_as_of("bet88", AT, 1000.0, [b], [], set())[0], 1000.0)

def test_ledger_next_day_undone_same_day_asked(self):
    led = [["20 Oct 2026", "bet88", "Deposit", "300", "Paolo", ""], ["19 Oct 2026", "bet88", "Withdrawal", "100", "Paolo", ""]]
    e, _, asks = expected_as_of("bet88", AT, 1000.0, [], led, set())
    self.assertEqual(e, 700.0); self.assertEqual(len(asks), 1)
    self.assertEqual(expected_as_of("bet88", AT, 1000.0, [], led, {3})[0], 800.0)   # row 3 = 2nd line, marked after

def test_other_accounts_ignored(self):
    self.assertEqual(expected_as_of("bet88", AT, 1000.0, [bet("S-1", "19 Oct 2026 15:00", "bet88 Tish", "200")], [], set())[0], 1000.0)

def test_unparseable_placed_time_is_asked(self):
    _, _, asks = expected_as_of("bet88", AT, 1000.0, [bet("S-1", "", "bet88", "200")], [], set())
    self.assertEqual(len(asks), 1)

def test_unknown_account_refused(self):
    with self.assertRaises(SystemExit):
        resolve_account("msw", ["msw.ph Pat", "msw.ph Grace"])   # exact match only; message lists both
```

(`resolve_account(name: str, accounts: list[str]) -> str` is the exact-match guard used by `check`.)

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement `balances.py`.** Gap = app − expected, rounded to 2 dp; written as values (`RAW`) with `write_rows`-style "first empty row" logic. Note column: Claude fills it from the dry-run trace when a gap ≠ 0 (possible cause only).
- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Live dry runs:** `balances.py setup` (shows the tab it would add), then `balances.py check "bet88" 9000.12 --at "<now>" --source test` → expected equals today's Balances!I for bet88, gap 0.00. Nothing applied without Paolo's yes.
- [ ] **Step 6: Commit** `"balances.py: Balance checks tab, expected balance as of screenshot time"`.

---

### Task 4: check-inbox picks up balance screenshots

**Files:**
- Modify: `game-tracker/inbox.py` (`FOLDERS`, add `pht_from_created`)
- Modify: `.claude/skills/check-inbox/SKILL.md`
- Test: `game-tracker/tests/test_inbox.py`

**Interfaces:**
- Consumes: `balances.py check` CLI (Task 3).
- Produces: `FOLDERS["Balances"] = "<id>"`; `pht_from_created(created_time: str) -> str` (Drive `2026-10-19T06:05:07.123Z` → `"19 Oct 2026 14:05"`).

- [ ] **Step 0 (Paolo):** create folder `Balances` inside `Betting Inbox` in Drive (bot already has Editor on the parent). Claude reads its id with a read-only listing and puts it in `FOLDERS`.
- [ ] **Step 1: Failing test** `test_created_time_to_pht`: `self.assertEqual(pht_from_created("2026-10-19T06:05:07.123Z"), "19 Oct 2026 14:05")`. Run — FAIL.
- [ ] **Step 2: Implement**; run `tests.test_inbox` — PASS. `list_new` needs no change beyond the dict entry (Balances has no holder subfolders).
- [ ] **Step 3: Update SKILL.md**, section 2 and 4:
  - `Balances/` → one balance screenshot per account. Read the single balance figure; account from the app shown (+ holder folder if it came from `Slips/<Holder>/`). Checked at = time visible on the screenshot, else `pht_from_created`. If the book shows a split balance, or the account is unclear: leave it and ask.
  - A balance screenshot in a Slips folder: route it as a balance (holders use their Slips folder).
  - Order: log slips first, then balance checks, in one dry-run summary.
  - Dry run: `balances.py check ... ` per screenshot; on yes, re-run with `--apply`, then move the file to Done.
  - Gap ≠ 0: state it plainly with the trace's possible cause; never "fix" it.
- [ ] **Step 4:** `inbox.py pull` dry run shows `Balances` as a folder (empty is fine).
- [ ] **Step 5: Commit** `"check-inbox: balance screenshots into Balance checks"`.

---

### Task 5: Page logic (pure, Node-tested)

**Files:**
- Create: `apps-script/book-dashboard/Model.gs`
- Test: `apps-script/book-dashboard/model.test.js`

**Interfaces:**
- Consumes: plain arrays as read from the sheet (`getDisplayValues()`, header row included): `accounts` (Accounts A:E), `balances` (Balances A:K, header + TOTAL row then data from row 3), `bets` (Bets A:Y), `checks` (Balance checks A:G).
- Produces: `buildModel(data: {accounts, balances, bets, checks}, now: Date) -> {summary, own: Card[], crypto: Card[], holders: {[holder: string]: {summary, cards: Card[]}}, hidden: Card[]}`.
  - `Card = {account, currency, status: "red"|"amber"|"green", expected, openStakes, openTickets, check: null | {at, app, expectedAtCheck, gap, note, ageDays}}`.
  - `summary = {cash, openStakes, maxReturn, maxReturnAt, matched, total}` — PHP only for Paolo; `crypto` cards carry their own units.
  - Status: red if latest check |gap| ≥ 1; else amber if no check or `ageDays > 3`; else green. Sort red (biggest |gap| first), amber, green, then account name.
  - Hidden: cash 0, open stakes 0, and Accounts Status ≠ "Active".
  - `Model.gs` ends with `if (typeof module !== 'undefined') module.exports = {buildModel};` so Node can load it; Apps Script ignores it.

- [ ] **Step 1: Failing tests** (`node:test`), each built from small inline arrays:
  - `gap of 500 is red and sorted first`
  - `gap of 0.40 is green` (tolerance)
  - `no check is amber; check 4 days old is amber; 2 days old matched is green`
  - `latest check per account wins` (two rows, older red, newer matched → green)
  - `holder accounts are grouped under the holder and excluded from summary.cash`
  - `crypto card stays in native units` (TRX account: expected 0.84, never multiplied by FX; not in summary.cash)
  - `inactive empty account is hidden`
  - `maxReturn sums Bets W for open own PHP tickets; maxReturnAt is the newest X`
- [ ] **Step 2:** `node --test apps-script/book-dashboard/` — FAIL.
- [ ] **Step 3: Implement `buildModel`** (parse numbers with commas, `"+"` and `"-"` signs; dates in the sheet format).
- [ ] **Step 4:** `node --test apps-script/book-dashboard/` — PASS.
- [ ] **Step 5: Commit** `"book dashboard: page model with tests"`.

---

### Task 6: Web app shell and deployment

**Files:**
- Create: `apps-script/book-dashboard/Code.gs`, `apps-script/book-dashboard/Index.html`, `apps-script/book-dashboard/README.md`

**Interfaces:**
- Consumes: `buildModel` (Task 5).
- Produces: `doGet() -> HtmlOutput`; `BOOK_KEY = '1zfPQqyLsFtFoDkluO4R7was3wyh5au6jV1Eyayykxdg'`.

- [ ] **Step 1: `Code.gs`:** `doGet` opens the sheet with `SpreadsheetApp.openById(BOOK_KEY)`, reads the four ranges with `getDisplayValues()`, calls `buildModel(data, new Date())`, renders `Index.html` via `HtmlService.createTemplateFromFile` with the model, title "Books", `addMetaTag('viewport','width=device-width, initial-scale=1')`.
- [ ] **Step 2: `Index.html`** to the spec's section 7 and the chosen mockup (layout B): as-of line (opened time, newest Bets/Balance-check time, Max return at); summary strip (Cash in books ₱, Open stakes ₱, Max return ₱ labelled "ceiling if every open leg wins", Books matched n of m, crypto line in native units); own cards; crypto cards; one section per holder with its small summary; a "show all" toggle for hidden accounts. Red cards show gap, expected at check, app balance, note; amber say "Never checked" or "Checked n days ago"; green are compact. Plain CSS, `prefers-color-scheme` dark mode, no external libraries.
- [ ] **Step 3: README.md (Paolo's steps):** script.google.com → New project "Book dashboard" → add files Model.gs, Code.gs, Index.html (paste from repo) → Deploy → New deployment → Web app, Execute as **Me**, Who has access **Only myself** → authorise → open the URL on the phone → Add to Home screen. Updating: paste new files → Deploy → Manage deployments → edit → New version (keeps the same URL).
- [ ] **Step 4 (with Paolo):** he deploys; we open it together and compare every card with the Balances tab by eye (spec section 9). Fix anything off, re-run `node --test`.
- [ ] **Step 5: Commit** `"book dashboard: Apps Script web app + setup notes"`.

---

### Task 7: Go live

- [ ] **Step 1:** Paolo approves and Claude applies, in order: `bets_refresh.py --apply`, `balances.py setup --apply`.
- [ ] **Step 2:** Paolo drops one balance screenshot per active book into `Betting Inbox/Balances` (holders into their Slips folders); Claude runs check-inbox → dry run → his yes → apply.
- [ ] **Step 3:** Every card shows green or red (no amber). Each red card has a traced possible cause in Note.
- [ ] **Step 4:** Update memory (`project-next-steps`, new `project-book-dashboard`) and `PLAN-phone-first.md` with the page URL location (not the URL itself in git).
