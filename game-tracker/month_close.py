"""Close a month: one frozen snapshot of the month's results per pot. Dry run unless --apply.

Usage:
  python month_close.py "Oct 2026" [--open Pat=4499.95 ...] [--note "Pat=..." ...] [--on "2 Nov 2026"]
                        [--apply] [--replace]

Writes plain values (not formulas) into the "Monthly close" tab, one block per month, so a closed
month stays as it was agreed even if rows are edited later. --replace rewrites a month already there;
openings and notes not given again are kept from the old rows.
The dashboard's Months page (apps-script/book-dashboard/Model.gs) reads this tab by column position:
keep HEADER's order, and leave "Next month opening" blank (not 0) when Paolo hasn't set one.

Rules (Paolo, 2 Nov 2026), the same as the Months page:
- a ticket belongs to the month it was PLACED, even if it settles the next month;
- Bonus / Adjustment ledger lines and Costs rows count by their own date;
- deposits, withdrawals and transfers are money moving, not P&L, and are left out;
- crypto stays in its own units (pots "Mine USDT", "Mine TRX") and out of the peso total;
- Result = Betting P&L + Bonus / adj.; Net = Result - Costs;
- a cost naming one or more holders is split evenly between them, one naming none is Mine's;
  in the summary rows, Costs items starting "Holder" are holder costs, the rest project costs.
A pot with open tickets is flagged: its month is not final until they settle.
"""
import re
import sys
from datetime import datetime

from funds import OWNER, num
from inspect_sheet import READONLY, READWRITE, client
from setup_book import BOOK_KEY
from vocab import PHT

TAB = "Monthly close"
HEADER = ["Month", "Pot", "Tickets settled", "Open", "Staked", "Betting P&L", "Bonus / adj.", "Result", "Costs",
          "Net", "Next month opening", "Currency", "Closed on", "Note"]
MINE = "Mine"
PNL_TYPES = ("Bonus", "Adjustment")
SUMMARY = ("All PHP before costs", "Holder costs", "Project costs", "Net PHP")


def month_of(cell):
    """'31 Oct 2026 10:32' or 'Oct 2026' -> 'Oct 2026'; anything else -> ''."""
    m = re.match(r"^(?:\d{1,2} )?([A-Z][a-z]{2}) (\d{4})", str(cell).strip())
    return f"{m[1]} {m[2]}" if m else ""


def pot_name(holder, cur):
    base = MINE if holder == OWNER else holder
    return base if cur == "PHP" else f"{base} {cur}"


def close_rows(month, accounts, bets, ledger, costs, openings=None, notes=None, on=""):
    """The month's rows: one per pot, then the PHP total, costs and net. Values only."""
    openings, notes = openings or {}, notes or {}
    acc = {r[0]: (pot_name(r[2] or OWNER, r[3] or "PHP"), r[3] or "PHP") for r in accounts[1:] if r and r[0]}
    pots = []
    for p in acc.values():
        if p not in pots:
            pots.append(p)
    pots.sort(key=lambda p: (not p[0].startswith(MINE), p[0].startswith(MINE) and p[1] != "PHP"))
    holders = [p for p, cur in pots if cur == "PHP" and p != MINE]
    stats = {p: [0, 0, 0.0, 0.0, 0.0, 0.0] for p, _ in pots}  # settled n, open n, staked, P&L, bonus, costs
    for r in bets[1:]:
        if not r or not r[0] or month_of(r[1]) != month or r[2] not in acc:
            continue
        s = stats[acc[r[2]][0]]
        if r[7] in ("", "Open"):
            s[1] += 1
        else:
            s[0] += 1
            s[2] += num(r[4])
            s[3] += num(r[9].replace("+", ""))
    for r in ledger[1:]:
        if r and r[1] in acc and r[2] in PNL_TYPES and month_of(r[0]) == month:
            stats[acc[r[1]][0]][4] += num(r[3])
    hold = proj = 0.0
    for r in costs[1:]:
        if not r or not r[1] or month_of(r[0]) != month:
            continue
        amount = num(r[4])
        if r[1].startswith("Holder"):
            hold += amount
        else:
            proj += amount
        named = [h for h in holders if re.search(rf"\b{re.escape(h)}\b", r[1])] or [MINE]
        for h in named:
            stats[h][5] += amount / len(named)

    rows, php = [], 0.0
    for p, cur in pots:
        n, op, staked, pnl, bonus, cost = stats[p]
        if not (n or op or bonus or cost or p in openings):
            continue
        result = round(pnl + bonus, 2)
        if cur == "PHP":
            php += result
        flag = f"{op} open ticket(s): not final until they settle" if op else ""
        note = "; ".join(x for x in (flag, notes.get(p, "")) if x)
        opening = openings.get(p, "")
        rows.append([month, p, n, op, round(staked, 2), round(pnl, 2), round(bonus, 2), result, round(cost, 2),
                     round(result - cost, 2), round(opening, 2) if opening != "" else "", cur, on, note])
    php, hold, proj = round(php, 2), round(hold, 2), round(proj, 2)
    blank = [""] * 5  # Tickets settled .. Bonus / adj.
    rows.append([month, SUMMARY[0], *blank, php, "", "", "", "PHP", on, "own books + every holder"])
    rows.append([month, SUMMARY[1], *blank, "", hold, "", "", "PHP", on, "Costs tab: items starting 'Holder'"])
    rows.append([month, SUMMARY[2], *blank, "", proj, "", "", "PHP", on, "Costs tab: subscriptions etc."])
    rows.append([month, SUMMARY[3], *blank, "", "", round(php - hold - proj, 2), "", "PHP", on, ""])
    return rows


def pairs(argv, flag):
    """--open Pat=4499.95 --open Mine=0 -> {"Pat": "4499.95", "Mine": "0"}."""
    out = {}
    for i, a in enumerate(argv[:-1]):
        if a == flag and "=" in argv[i + 1]:
            k, v = argv[i + 1].split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main(argv):
    if not argv or not month_of(argv[0]):
        sys.exit(__doc__)
    month = month_of(argv[0])
    apply, replace = "--apply" in argv, "--replace" in argv
    on = argv[argv.index("--on") + 1] if "--on" in argv else datetime.now(PHT).strftime("%d %b %Y").lstrip("0")
    sh = client(READWRITE if apply else READONLY).open_by_key(BOOK_KEY)
    try:
        ws = sh.worksheet(TAB)
        have = ws.get_all_values()
    except Exception:
        ws, have = None, []
    old = [r + [""] * (len(HEADER) - len(r)) for r in have[1:] if r and r[0]]
    mine = [r for r in old if r[0] == month]
    if mine and not replace:
        sys.exit(f"{month} is already in {TAB}; nothing written. Use --replace to rewrite it.")
    # keep what Paolo agreed before unless he gives it again
    openings = {r[1]: num(r[10]) for r in mine if r[10] != "" and r[1] not in SUMMARY}
    openings.update({k: num(v) for k, v in pairs(argv, "--open").items()})
    notes = {r[1]: r[13] for r in mine if r[13] and r[1] not in SUMMARY and "open ticket" not in r[13]}
    notes.update(pairs(argv, "--note"))
    get = lambda t: sh.worksheet(t).get_all_values()
    rows = close_rows(month, get("Accounts"), get("Bets"), get("Ledger"), get("Costs"), openings, notes, on)
    for r in rows:
        print("  " + " | ".join(f"{x:,.2f}" if isinstance(x, float) else str(x) for x in r[1:]))
    if not apply:
        print(f"\nDry run. Re-run with --apply to write {month} to the {TAB} tab.")
        return
    if ws is None:
        ws = sh.add_worksheet(TAB, rows=200, cols=len(HEADER))
    body = [HEADER]
    for r in [r for r in old if r[0] != month] + rows:  # one blank row between months
        if len(body) > 1 and body[-1][0] != r[0]:
            body.append([""] * len(HEADER))
        body.append(r)
    ws.clear()
    ws.update(range_name="A1", values=body, value_input_option="USER_ENTERED")
    ws.batch_format([
        {"range": "A1:N1", "format": {"textFormat": {"bold": True}}},
        {"range": f"E2:K{len(body)}", "format": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}}},
    ])
    ws.freeze(rows=1, cols=2)
    print(f"Written: {month} ({len(rows)} rows) to {TAB}.")


if __name__ == "__main__":
    main(sys.argv[1:])
