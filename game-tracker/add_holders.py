"""Add the account-holder accounts (SPEC-account-holders.md, step 2) to the private book.

Usage: python add_holders.py [--apply]
Adds, only if missing: Accounts rows for Pat (msw.ph) and Tish (bet88), their funding Deposit lines
in Ledger (Pot = Paolo, his money), and the ₱200 processing fee in Costs. Dry run by default.
"""
import sys
from datetime import datetime

from log_bets import serial
from setup_book import BOOK_KEY

FUNDED = datetime(2026, 10, 11)
ACCOUNTS = [  # Account | Book | Holder | Currency | Status | Notes
    ["msw.ph Pat", "msw.ph", "Pat", "PHP", "Active", "Paolo's money; Pat places the bets"],
    ["bet88 Tish", "bet88", "Tish", "PHP", "Active", "Paolo's money; Tish places the bets"],
]
LEDGER = [  # Date | Account | Type | Amount | Pot | Note
    [serial(FUNDED), "msw.ph Pat", "Deposit", 5000, "Paolo", "funded by Paolo for holder Pat (₱200 fee in Costs)"],
    [serial(FUNDED), "bet88 Tish", "Deposit", 5000, "Paolo", "funded by Paolo for holder Tish"],
]
COSTS = [[serial(FUNDED), "Holder funding fee (Pat, msw.ph)", 200, "PHP", 200,
          "processing fee on the ₱5,200 transfer to Pat"]]


def first_empty(values):
    return 1 + max((i for i, r in enumerate(values, start=1) if r and r[0]), default=1)


def main():
    apply = "--apply" in sys.argv
    from inspect_sheet import READONLY, READWRITE, client
    book = client(READWRITE if apply else READONLY).open_by_key(BOOK_KEY)
    acc_ws, led_ws, cost_ws = (book.worksheet(t) for t in ("Accounts", "Ledger", "Costs"))
    accs = acc_ws.get_all_values()
    have = {r[0] for r in accs[1:] if r}
    new_accs = [r for r in ACCOUNTS if r[0] not in have]
    led = led_ws.get_all_values()
    done = {(r[1], r[2], r[5]) for r in led[1:] if len(r) > 5}
    new_led = [r for r in LEDGER if r[1] in have | {a[0] for a in new_accs}
               and (r[1], r[2], r[5]) not in done]
    costs = cost_ws.get_all_values()
    new_costs = [r for r in COSTS if r[1] not in {x[1] for x in costs[1:] if len(x) > 1}]

    print(f"[{book.title}] {'APPLY' if apply else 'dry run'}")
    for r in new_accs:
        print("  Accounts +", r)
    for r in new_led:
        print("  Ledger   +", r[1:4], r[5])
    for r in new_costs:
        print("  Costs    +", r[1:5])
    if not (new_accs or new_led or new_costs):
        print("  nothing to add")
    if not apply:
        return
    if new_accs:
        acc_ws.update(range_name=f"A{first_empty(accs)}", values=new_accs, value_input_option="RAW")
    if new_led:
        led_ws.update(range_name=f"A{first_empty(led)}", values=new_led, value_input_option="RAW")
    if new_costs:
        cost_ws.update(range_name=f"A{first_empty(costs)}", values=new_costs, value_input_option="RAW")
    print("  written")


if __name__ == "__main__":
    main()
