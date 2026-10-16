"""Where Paolo's money is: capital put in, withdrawn, cash in the books, open stakes.

Usage:
  python funds.py                  print the summary (read-only)
  python funds.py tab              preview the Funds tab (dry run)
  python funds.py tab --apply      write/refresh the Funds tab

Reads the Balances tab (its figures come from Ledger and Bets). One column per pot:
Paolo's own books per currency (PHP, USDT, TRX), then one per account holder.
Crypto stays in its own units and is never converted into the peso totals.
Capital = opening balances + deposits. Bonus/adjustments and transfers are kept apart.
Check line: cash + open stakes + withdrawn - capital - transfers - bonus = settled betting P&L.

The tab is live formulas over Balances. Re-run `tab --apply` only when a new holder or
currency appears (it adds the column).
"""
import sys

from inspect_sheet import READONLY, READWRITE, client
from setup_book import BOOK_KEY

OWNER = "Paolo"
# label, formula over Balances columns (B..J as letters), key for the printed summary
METRICS = [
    ("Capital (opening + deposits)", ["B", "C"], "capital"),
    ("Withdrawn", ["D"], "withdrawn"),
    ("Net taken out (withdrawn − capital)", None, "net_out"),
    ("Cash in accounts", ["I"], "cash"),
    ("Open stakes", ["J"], "open"),
    ("In play now (cash + open)", None, "value"),
    ("Transfers (net)", ["E"], "transfers"),
    ("Bonus / adjustments", ["F"], "bonus"),
    ("Betting P&L (settled)", None, "pnl"),
]


def num(s):
    try:
        return float(str(s).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def parse_balances(rows):
    """Balances rows (header + TOTAL first) -> one dict per account, native units."""
    out = []
    for r in rows[2:]:
        r = r + [""] * (15 - len(r))
        if not r[0]:
            continue
        b, c, d, e, f, g, h, i, j = (num(x) for x in r[1:10])
        out.append({"account": r[0], "holder": r[14] or "?", "currency": r[10] or "?",
                    "capital": b + c, "withdrawn": d, "transfers": e, "bonus": f,
                    "cash": i, "open": j})
    return out


def pots(accounts):
    """Columns: own books per currency (PHP first), then each holder per currency."""
    keys = []
    for a in accounts:
        k = (a["holder"], a["currency"])
        if k not in keys:
            keys.append(k)
    own = sorted([k for k in keys if k[0] == OWNER], key=lambda k: (k[1] != "PHP", k[1]))
    return own + [k for k in keys if k[0] != OWNER]


def label(pot):
    holder, cur = pot
    return f"Own {cur}" if holder == OWNER else (holder if cur == "PHP" else f"{holder} {cur}")


def totals(accounts, pot):
    pick = [a for a in accounts if (a["holder"], a["currency"]) == pot]
    t = {k: sum(a[k] for a in pick) for k in ("capital", "withdrawn", "transfers", "bonus", "cash", "open")}
    t["net_out"] = t["withdrawn"] - t["capital"]
    t["value"] = t["cash"] + t["open"]
    t["pnl"] = t["value"] + t["withdrawn"] - t["capital"] - t["transfers"] - t["bonus"]
    return t


def fmt(x, cur):
    sign = "-" if x < -0.005 else ""
    return f"{sign}₱{abs(x):,.2f}" if cur == "PHP" else f"{x:,.2f} {cur}"


def report(accounts):
    cols = pots(accounts)
    w = 16
    lines = [f"{'':<36}" + "".join(f"{label(p):>{w}}" for p in cols)]
    ts = [totals(accounts, p) for p in cols]
    for name, _, k in METRICS:
        if k in ("transfers", "bonus") and not any(t[k] for t in ts):
            continue
        lines.append(f"{name:<36}" + "".join(f"{fmt(t[k], p[1]):>{w}}" for p, t in zip(cols, ts)))
    return "\n".join(lines)


def tab_values(cols):
    """Funds tab grid: rows 1-4 title/criteria, then one formula row per metric."""
    n = len(cols)
    rows = [["Funds", "Live from Balances. Crypto in its own units; holders' money kept apart."] + [""] * (n - 1),
            ["Pot"] + [label(p) for p in cols],
            ["Holder"] + [p[0] for p in cols],
            ["Currency"] + [p[1] for p in cols]]
    at = {}
    for i, (name, src, k) in enumerate(METRICS):
        r = 5 + i
        at[k] = r
        row = [name]
        for j in range(n):
            col = chr(ord("B") + j)
            if src:
                crit = f"Balances!$O$3:$O,{col}$3,Balances!$K$3:$K,{col}$4"
                row.append("=" + "+".join(f"SUMIFS(Balances!${s}$3:${s},{crit})" for s in src))
            elif k == "net_out":
                row.append(f"={col}{at['withdrawn']}-{col}{at['capital']}")
            elif k == "value":
                row.append(f"={col}{at['cash']}+{col}{at['open']}")
            else:  # pnl: rows for transfers and bonus come before it
                row.append(f"={col}{at['value']}+{col}{at['withdrawn']}-{col}{at['capital']}"
                           f"-{col}{at['transfers']}-{col}{at['bonus']}")
        rows.append(row)
    rows.append([""])
    rows.append(["Betting P&L counts open stakes at cost: profit only once tickets settle. "
                 "Re-run funds.py tab --apply when a new holder or currency appears."])
    return rows


def write_tab(sh, rows):
    try:
        ws = sh.worksheet("Funds")
        ws.clear()
    except Exception:
        ws = sh.add_worksheet("Funds", rows=40, cols=max(10, len(rows[1]) + 1), index=1)
    ws.update(range_name="A1", values=rows, value_input_option="USER_ENTERED")
    last = chr(ord("A") + len(rows[1]) - 1)
    end = 4 + len(METRICS)
    ws.batch_format([
        {"range": "A1", "format": {"textFormat": {"bold": True, "fontSize": 14}}},
        {"range": f"A2:{last}2", "format": {"textFormat": {"bold": True}}},
        {"range": f"A3:{last}4", "format": {"textFormat": {"foregroundColor": {"red": .5, "green": .5, "blue": .5}}}},
        {"range": f"B5:{last}{end}", "format": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"},
                                                 "horizontalAlignment": "RIGHT"}},
        {"range": f"A{end}:{last}{end}", "format": {"textFormat": {"bold": True}}},
    ])
    sh.batch_update({"requests": [
        {"updateSheetProperties": {"properties": {"sheetId": ws.id, "gridProperties": {"frozenColumnCount": 1, "frozenRowCount": 2}},
                                   "fields": "gridProperties.frozenColumnCount,gridProperties.frozenRowCount"}},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                                       "properties": {"pixelSize": 260}, "fields": "pixelSize"}},
    ]})


def main(argv):
    apply = "--apply" in argv
    sh = client(READWRITE if apply else READONLY).open_by_key(BOOK_KEY)
    accounts = parse_balances(sh.worksheet("Balances").get_all_values())
    if argv and argv[0] == "tab":
        rows = tab_values(pots(accounts))
        print(f"Funds tab: {len(rows[1]) - 1} columns: " + ", ".join(rows[1][1:]))
        print(report(accounts))
        if apply:
            write_tab(sh, rows)
            print("\nWritten: Funds tab (live formulas).")
        else:
            print("\nDry run. Re-run with `tab --apply` to write the Funds tab.")
    else:
        print(report(accounts))


if __name__ == "__main__":
    main(sys.argv[1:])
