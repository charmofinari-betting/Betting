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
COMBINED = "All PHP (mine)"
COST_LABEL = "Holder commissions and fees (Costs tab)"
NET_LABEL = "Betting P&L after holder costs"
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


def combined_php(accounts):
    """All PHP pots added together (Paolo's own books plus every holder): his money in total."""
    parts = [totals(accounts, p) for p in pots(accounts) if p[1] == "PHP"]
    return {k: sum(t[k] for t in parts) for k in parts[0]} if len(parts) > 1 else None


def report(accounts):
    cols = pots(accounts)
    w = 16
    ts = [totals(accounts, p) for p in cols]
    both = combined_php(accounts)
    head = [label(p) for p in cols] + ([COMBINED] if both else [])
    lines = [f"{'':<36}" + "".join(f"{h:>{w}}" for h in head)]
    for name, _, k in METRICS:
        if k in ("transfers", "bonus") and not any(t[k] for t in ts):
            continue
        cells = [fmt(t[k], p[1]) for p, t in zip(cols, ts)] + ([fmt(both[k], "PHP")] if both else [])
        lines.append(f"{name:<36}" + "".join(f"{c:>{w}}" for c in cells))
    return "\n".join(lines)


def tab_values(cols):
    """Funds tab grid: rows 1-4 title/criteria, then one formula row per metric."""
    n = len(cols)
    combined = sum(1 for p in cols if p[1] == "PHP") > 1  # one extra column: all the PHP pots, mine in total
    rows = [["Funds", "Live from Balances. Crypto in its own units; holders' money kept apart."] + [""] * (n - 1 + combined),
            ["Pot"] + [label(p) for p in cols] + ([COMBINED] if combined else []),
            ["Holder"] + [p[0] for p in cols] + (["All"] if combined else []),
            ["Currency"] + [p[1] for p in cols] + (["PHP"] if combined else [])]
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
        if combined:
            row.append(f'=SUMIF($B$4:${chr(ord("B") + n - 1)}$4,"PHP",B{r}:{chr(ord("B") + n - 1)}{r})')
        rows.append(row)
    if combined:
        c = chr(ord("B") + n)
        r_cost, r_net = 5 + len(METRICS), 6 + len(METRICS)
        rows.append([COST_LABEL] + [""] * n + [f'=SUMIF(Costs!$B$2:$B,"Holder*",Costs!$E$2:$E)'])
        rows.append([NET_LABEL] + [""] * n + [f"={c}{at['pnl']}-{c}{r_cost}"])
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
    extra = 2 if rows[1][-1] == COMBINED else 0
    ws.batch_format([
        {"range": "A1", "format": {"textFormat": {"bold": True, "fontSize": 14}}},
        {"range": f"A2:{last}2", "format": {"textFormat": {"bold": True}}},
        {"range": f"A3:{last}4", "format": {"textFormat": {"foregroundColor": {"red": .5, "green": .5, "blue": .5}}}},
        {"range": f"B5:{last}{end + extra}", "format": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"},
                                                 "horizontalAlignment": "RIGHT"}},
        {"range": f"A{end}:{last}{end}", "format": {"textFormat": {"bold": True}}},
    ] + ([{"range": f"A{end + 2}:{last}{end + 2}", "format": {"textFormat": {"bold": True}}},
          {"range": f"{last}1:{last}{end + 2}", "format": {"backgroundColor": {"red": .94, "green": .96, "blue": .98}}}]
         if extra else []))
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
