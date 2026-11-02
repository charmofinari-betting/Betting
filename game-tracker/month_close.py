"""Close a month: one frozen snapshot of the month's results per pot. Dry run unless --apply.

Usage: python month_close.py "Oct 2026" [--apply] [--replace]

Writes plain values (not formulas) into the "Monthly close" tab, one block per month, so a closed
month stays as it was agreed even if rows are edited later. --replace rewrites a month already there.
Rules (Paolo, 2 Nov 2026):
- a ticket belongs to the month it was PLACED, even if it settles the next month;
- Bonus / Adjustment ledger lines and Costs rows count by their own date;
- deposits, withdrawals and transfers are money moving, not P&L, and are left out;
- crypto stays in its own units and is never added to the peso total;
- Costs rows whose item starts with "Holder" are holder costs, the rest project costs.
A pot with open tickets is flagged: its month is not final until they settle.
"""
import sys
from datetime import date

from funds import OWNER, num
from inspect_sheet import READONLY, READWRITE, client
from setup_book import BOOK_KEY

TAB = "Monthly close"
HEADER = ["Month", "Line", "Tickets settled", "Open", "Staked", "Betting P&L", "Bonus / adj.", "Total",
          "Currency", "Note"]
PNL_TYPES = ("Bonus", "Adjustment")


def month_of(cell):
    """'31 Oct 2026 10:32' -> 'Oct 2026'; anything that isn't a date -> ''."""
    parts = str(cell).split()
    return f"{parts[1]} {parts[2]}" if len(parts) >= 3 and parts[0].isdigit() else ""


def close_rows(month, accounts, bets, ledger, costs):
    """The month's rows: one per pot, then the PHP total, costs and net. Values only."""
    acc = {r[0]: (r[2], r[3]) for r in accounts[1:] if r and r[0]}
    pots = []
    for holder, cur in acc.values():
        if (holder, cur) not in pots:
            pots.append((holder, cur))
    pots.sort(key=lambda p: (p[0] != OWNER, p[0] == OWNER and p[1] != "PHP"))
    stats = {p: [0, 0, 0.0, 0.0, 0.0] for p in pots}  # settled n, open n, staked, P&L, bonus
    for r in bets[1:]:
        if not r or not r[0] or month_of(r[1]) != month or r[2] not in acc:
            continue
        s = stats[acc[r[2]]]
        if r[7] == "Open":
            s[1] += 1
        else:
            s[0] += 1
            s[2] += num(r[4])
            s[3] += num(r[9].replace("+", ""))
    for r in ledger[1:]:
        if r and r[1] in acc and r[2] in PNL_TYPES and month_of(r[0]) == month:
            stats[acc[r[1]]][4] += num(r[3])

    rows, php = [], 0.0
    for p in pots:
        n, op, staked, pnl, bonus = stats[p]
        if not (n or op or bonus):
            continue
        holder, cur = p
        line = f"Own {cur}" if holder == OWNER else (holder if cur == "PHP" else f"{holder} {cur}")
        total = round(pnl + bonus, 2)
        if cur == "PHP":
            php += total
        note = f"{op} open ticket(s): not final until they settle" if op else ""
        rows.append([month, line, n, op, round(staked, 2), round(pnl, 2), round(bonus, 2), total, cur, note])
    php = round(php, 2)
    rows.append([month, "All PHP before costs", "", "", "", "", "", php, "PHP", "own books + every holder"])
    hold = proj = 0.0
    for r in costs[1:]:
        if r and r[0] and month_of(r[0]) == month:
            if r[1].startswith("Holder"):
                hold += num(r[4])
            else:
                proj += num(r[4])
    hold, proj = round(-hold, 2), round(-proj, 2)
    rows.append([month, "Holder costs", "", "", "", "", "", hold, "PHP", "Costs tab: commissions, bonuses, fees"])
    rows.append([month, "Project costs", "", "", "", "", "", proj, "PHP", "Costs tab: subscriptions etc."])
    rows.append([month, "Net PHP", "", "", "", "", "", round(php + hold + proj, 2), "PHP",
                 f"closed {date.today():%d %b %Y}"])
    return rows


def main(argv):
    month = argv[0]
    apply, replace = "--apply" in argv, "--replace" in argv
    sh = client(READWRITE if apply else READONLY).open_by_key(BOOK_KEY)
    get = lambda t: sh.worksheet(t).get_all_values()
    rows = close_rows(month, get("Accounts"), get("Bets"), get("Ledger"), get("Costs"))
    for r in rows:
        print("  " + " | ".join(f"{x:,.2f}" if isinstance(x, float) else str(x) for x in r[1:]))
    if not apply:
        print(f"\nDry run. Re-run with --apply to write {month} to the {TAB} tab.")
        return
    try:
        ws = sh.worksheet(TAB)
        have = ws.get_all_values()
    except Exception:
        ws = sh.add_worksheet(TAB, rows=200, cols=len(HEADER))
        have = []
    old = [r for r in have[1:] if r and r[0]]
    keep = [r for r in old if r[0] != month]
    if len(keep) < len(old) and not replace:
        print(f"{month} is already in {TAB}; nothing written. Use --replace to rewrite it.")
        return
    body = [HEADER]
    for r in keep + rows:  # one blank row between months
        if len(body) > 1 and body[-1][0] != r[0]:
            body.append([""] * len(HEADER))
        body.append(r)
    ws.clear()
    ws.update(range_name="A1", values=body, value_input_option="USER_ENTERED")
    ws.batch_format([
        {"range": "A1:J1", "format": {"textFormat": {"bold": True}}},
        {"range": f"E2:H{len(body)}", "format": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}}},
    ])
    print(f"Written: {month} ({len(rows)} rows) to {TAB}.")


if __name__ == "__main__":
    main(sys.argv[1:])
