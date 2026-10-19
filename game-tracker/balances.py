"""Balance checks: the app balance Paolo sends vs what the sheet expected at that moment. Dry run unless --apply.

  PYTHONIOENCODING=utf-8 ../.venv/Scripts/python balances.py setup [--apply]
  PYTHONIOENCODING=utf-8 ../.venv/Scripts/python balances.py check "<account>" <amount> --at "19 Oct 2026 14:05" \
      --source <drive file id> [--note "..."] [--after-ledger 41,42 | --after-ledger none] [--apply]

Expected at check = today's Balances!Balance with everything after the screenshot undone: stakes of tickets placed
after it come back, returns of tickets settled after it go out, Ledger lines dated after it are reversed.
A ticket's settle time = the earlier of Bets "Settled at" and its last leg kickoff + 3 h. Ledger has dates only,
so lines dated the same day as the check are asked about (--after-ledger names the sheet rows that came after).
A gap is reported, never fixed: no Ledger or Bets writes here."""
import sys
from datetime import datetime, timedelta

from bets_refresh import BEFORE

TAB = "Balance checks"
HEADER = ["Checked at (PHT)", "Account", "App balance", "Expected at check", "Gap", "Source", "Note"]
LEDGER_SIGN = {"Opening balance": 1, "Deposit": 1, "Withdrawal": -1, "Transfer in": 1, "Transfer out": -1,
               "Bonus": 1, "Adjustment": 1}
SETTLE_AFTER_KICKOFF = timedelta(hours=3)


def num(s):
    return float(str(s).replace(",", "").replace("+", "") or 0)


def parse_pht(s):
    for fmt in ("%d %b %Y %H:%M", "%d %b %Y"):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except ValueError:
            pass
    return None


def settle_time(stamp, kickoffs):
    """None = settled before any check (no usable stamp, or 'before tracking')."""
    if not stamp or stamp == BEFORE:
        return None
    times = [t for t in (parse_pht(stamp),) if t]
    if kickoffs and all(kickoffs):
        times.append(max(kickoffs) + SETTLE_AFTER_KICKOFF)
    return min(times) if times else None


def expected_as_of(account, at, balance_now, bets, ledger, after_rows, legs=()):
    """-> (expected, trace lines, asks). bets / ledger / legs: sheet rows without the header."""
    kick = {}
    for l in legs:
        if l and l[0]:
            kick.setdefault(l[0], []).append(parse_pht(l[10]) if len(l) > 10 else None)
    exp, trace, asks = balance_now, [], []
    for r in bets:
        r = r + [""] * (25 - len(r))
        if r[2] != account or not r[0]:
            continue
        placed = parse_pht(r[1])
        if placed is None:
            asks.append(f"{r[0]}: Placed (PHT) {r[1]!r} unreadable; fix it in Bets")
            continue
        if placed > at:
            exp += num(r[4])
            trace.append(f"+{num(r[4]):,.2f}  {r[0]} placed {r[1]}, after the check")
        if r[7] != "Open":
            st = settle_time(r[24], kick.get(r[0]))
            if placed > at and (st is None or st < placed):
                st = placed  # it cannot have settled before it was placed
            if st is None and r[24] != BEFORE and num(r[8]):
                trace.append(f"   {r[0]}: no Settled at, assumed settled before the check")
            if st is not None and st > at and num(r[8]):
                exp -= num(r[8])
                trace.append(f"-{num(r[8]):,.2f}  {r[0]} returned, settled ~{st:%d %b %H:%M}, after the check")
    for i, r in enumerate(ledger, start=2):
        if len(r) < 4 or r[1] != account or r[2] not in LEDGER_SIGN:
            continue
        day = parse_pht(r[0])
        if day is None:
            asks.append(f"Ledger row {i}: date {r[0]!r} unreadable")
            continue
        amount = LEDGER_SIGN[r[2]] * num(r[3])
        same_day = day.date() == at.date()
        if day.date() > at.date() or (same_day and i in after_rows):
            exp -= amount
            trace.append(f"{-amount:+,.2f}  Ledger row {i} {r[2]} {r[0]}, after the check")
        elif same_day:
            asks.append(f"Ledger row {i}: {r[2]} {num(r[3]):,.2f} on {r[0]}: before or after the screenshot? "
                        f"(counted as before; --after-ledger {i} if after)")
    return round(exp, 2), trace, asks


def resolve_account(name, accounts):
    if name in accounts:
        return name
    near = [a for a in accounts if name.lower() in a.lower()]
    sys.exit(f"account {name!r} not in Accounts" + (f"; did you mean: {', '.join(near)}" if near else "")
             + f". Accounts: {', '.join(accounts)}")


def plan_check(account, app, at, expected, source, note):
    gap = round(app - expected, 2)
    return [at, account, f"{app:.2f}", f"{expected:.2f}", f"{gap:.2f}", source, note], gap


def opt(argv, flag, default=""):
    return argv[argv.index(flag) + 1] if flag in argv else default


def check(book, argv, apply):
    accounts = [r[0] for r in book.worksheet("Accounts").get_all_values()[1:] if r and r[0]]
    account, app = resolve_account(argv[1], accounts), num(argv[2])
    at_s = opt(argv, "--at")
    at = parse_pht(at_s)
    if at is None:
        sys.exit(f"--at {at_s!r}: use the sheet format, e.g. '19 Oct 2026 14:05'")
    after = opt(argv, "--after-ledger")
    after_rows = set() if after in ("", "none") else {int(x) for x in after.split(",")}
    balances = {r[0]: num(r[8]) for r in book.worksheet("Balances").get_all_values()[2:] if r and r[0]}
    exp, trace, asks = expected_as_of(account, at, balances[account],
                                      book.worksheet("Bets").get_all_values()[1:],
                                      book.worksheet("Ledger").get_all_values()[1:], after_rows,
                                      book.worksheet("Legs").get_all_values()[1:])
    row, gap = plan_check(account, app, at_s, exp, opt(argv, "--source"), opt(argv, "--note"))
    status = "matches" if abs(gap) < 1 else f"GAP {gap:+,.2f}"
    print(f"[{book.title}] balance check {'APPLY' if apply else 'dry run'}: {account} at {at_s}")
    print(f"  app {app:,.2f} | expected {exp:,.2f} (now {balances[account]:,.2f}) | {status}")
    for t in trace:
        print("  trace " + t)
    blocking = [a for a in asks if not (a.startswith("Ledger row") and after)]
    for a in asks:
        print("  ASK   " + a)
    if not apply:
        return
    if blocking:
        sys.exit("not applying: answer the ASK lines first (--after-ledger <rows> or --after-ledger none)")
    ws = book.worksheet(TAB)
    n = 1 + max((i for i, r in enumerate(ws.get_all_values(), start=1) if r and r[0]), default=1)
    ws.update(range_name=f"A{n}:G{n}", values=[row], value_input_option="RAW")
    print(f"  written: {TAB} row {n}")


def setup(book, apply):
    if TAB in [w.title for w in book.worksheets()]:
        print(f"{TAB}: already there")
        return
    print(f"{TAB}: would add, header: {' | '.join(HEADER)}" if not apply else f"{TAB}: adding")
    if apply:
        ws = book.add_worksheet(TAB, rows=500, cols=len(HEADER))
        ws.update(range_name="A1:G1", values=[HEADER], value_input_option="RAW")
        ws.freeze(rows=1)
        print("  written")


def main(argv):
    apply = "--apply" in argv
    from inspect_sheet import READONLY, READWRITE, client
    from setup_book import BOOK_KEY
    book = client(READWRITE if apply else READONLY).open_by_key(BOOK_KEY)
    if argv and argv[0] == "setup":
        setup(book, apply)
    elif argv and argv[0] == "check" and len(argv) >= 3:
        check(book, argv, apply)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
