"""Month close: freeze what Paolo agreed for a month, per pot, in the 'Month close' tab.

Usage:
  python month_close.py setup [--apply]
      add the tab (header only)
  python month_close.py show "Oct 2026"
      the month per pot as the sheet has it now (read-only)
  python month_close.py add "Oct 2026" <pot> <next-month opening> [--note "..."] [--on "2 Nov 2026"] [--apply]
      one row: the pot's result + bonus/adj. and costs for the month as they stand now,
      and the opening he set for the next month. Pot = Mine (own PHP books) or a holder name.

Same rules as the dashboard's Months page (apps-script/book-dashboard/Model.gs, buildMonths):
tickets count in the month they were placed (settled ones only), Ledger Bonus/Adjustment and Costs
by date; a cost naming several holders is split evenly, one naming none is Mine's. PHP pots only.
The dashboard flags a closed month whose live result later moves away from the row written here.
"""
import re
import sys
from datetime import datetime

from vocab import PHT, open_book

TAB = "Month close"
HEADER = ["Month", "Pot", "Result at close", "Costs at close", "Next month opening", "Closed on", "Note"]
OWNER = "Paolo"
MINE = "Mine"


def num(s):
    try:
        return float(str(s).replace(",", "").replace("+", "") or 0)
    except ValueError:
        return 0.0


def month_of(s):
    m = re.match(r"^(?:\d{1,2} )?([A-Z][a-z]{2}) (\d{4})", str(s).strip())
    return f"{m[1]} {m[2]}" if m else ""


def month_figures(accounts, bets, ledger, costs, month):
    """{pot: {"result": result + bonus/adj., "costs": costs}} for one month, e.g. 'Oct 2026'."""
    pot_of = {a[0]: (MINE if (a[2] or OWNER) == OWNER else a[2]) for a in accounts[1:] if a[0] and (a[3] or "PHP") == "PHP"}
    pots = sorted(set(pot_of.values()))
    out = {p: {"result": 0.0, "costs": 0.0} for p in pots}
    for r in bets[1:]:
        if r[0] and r[2] in pot_of and month_of(r[1]) == month and r[7] not in ("", "Open"):
            out[pot_of[r[2]]]["result"] += num(r[18])
    for r in ledger[1:]:
        if r[1] in pot_of and month_of(r[0]) == month and r[2] in ("Bonus", "Adjustment"):
            out[pot_of[r[1]]]["result"] += num(r[3])
    for r in costs[1:]:
        if not r[1] or month_of(r[0]) != month:
            continue
        named = [p for p in pots if p != MINE and re.search(rf"\b{re.escape(p)}\b", r[1])] or [MINE]
        for p in named:
            out[p]["costs"] += num(r[4]) / len(named)
    return {p: {k: round(v, 2) for k, v in x.items()} for p, x in out.items()}


def read(book):
    return [book.worksheet(t).get_all_values() for t in ("Accounts", "Bets", "Ledger", "Costs")]


def opt(argv, flag, default=""):
    return argv[argv.index(flag) + 1] if flag in argv else default


def main(argv):
    apply = "--apply" in argv
    cmd = argv[0] if argv else ""
    if cmd == "setup":
        book = open_book(apply)
        if TAB in [w.title for w in book.worksheets()]:
            sys.exit(f"{TAB} already exists")
        print(f"[{book.title}] {'APPLY' if apply else 'dry run'}: add tab {TAB}: {' | '.join(HEADER)}")
        if apply:
            ws = book.add_worksheet(TAB, rows=200, cols=len(HEADER))
            ws.update(range_name="A1", values=[HEADER], value_input_option="RAW")
            ws.freeze(rows=1)
            print("  written")
    elif cmd == "show":
        month = month_of(argv[1])
        for p, x in month_figures(*read(open_book()), month).items():
            print(f"  {month}  {p:<8} result+bonus {x['result']:>14,.2f}   costs {x['costs']:>12,.2f}")
    elif cmd == "add":
        month, pot, opening = month_of(argv[1]), argv[2], num(argv[3])
        book = open_book(apply)
        fig = month_figures(*read(book), month)
        if not month or pot not in fig:
            sys.exit(f"unknown month or pot: {argv[1]!r} {pot!r} (pots: {', '.join(fig)})")
        ws = book.worksheet(TAB)
        rows = ws.get_all_values()
        if any(r[:2] == [month, pot] for r in rows[1:]):
            sys.exit(f"{month} {pot} is already closed; change that row by hand if it must move")
        on = opt(argv, "--on") or datetime.now(PHT).strftime("%d %b %Y").lstrip("0")
        row = [month, pot, f"{fig[pot]['result']:.2f}", f"{fig[pot]['costs']:.2f}", f"{opening:.2f}", on, opt(argv, "--note")]
        print(f"[{book.title}] {'APPLY' if apply else 'dry run'}: {TAB} row {len(rows) + 1}: {' | '.join(row)}")
        if apply:
            ws.update(range_name=f"A{len(rows) + 1}", values=[row], value_input_option="RAW")
            print("  written")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
