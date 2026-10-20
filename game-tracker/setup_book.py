"""Create the private book tabs (SPEC-private-book.md) on the "Private Betting" sheet.

Usage: python setup_book.py [--apply] [--rebuild]
Creates the tabs that don't exist yet: headers, formulas, formats, dropdowns and the starting
Accounts / FX rows. --rebuild first deletes every tab, and refuses if Bets or Ledger hold data.

Amounts are in each account's own currency (PHP, USDT, TRX). The FX tab holds the ₱ value of
one unit; log-bets stores the rate on each ticket, so a ticket's ₱ P&L uses the rate of the day
it was placed. Balances in ₱ use the current rate.
"""
import sys
import time

BOOK_KEY = "1zfPQqyLsFtFoDkluO4R7was3wyh5au6jV1Eyayykxdg"
LEG_RESULTS = ("Won", "Lost", "Half Won", "Half Lost", "Void")
LEDGER_TYPES = ("Opening balance", "Deposit", "Withdrawal", "Transfer in", "Transfer out", "Bonus", "Adjustment")
TICKET_TYPES = ("Single", "Double", "Treble", "4-fold", "5-fold", "6-fold", "7-fold", "8-fold",
                "System 2/3", "System 2/4", "System 3/4", "System 2/5", "System 3/5", "System 4/5",
                "System 2/6", "System 3/6", "System 4/6", "System 5/6")
CURRENCIES = ("PHP", "USDT", "TRX")
POTS = ("Paolo",)

ACCOUNTS = [  # Account | Book | Holder | Currency | Status | Notes
    ["1xbet PHP", "1xbet", "Paolo", "PHP", "Active", ""],
    ["1xbet USDT", "1xbet", "Paolo", "USDT", "Active", ""],
    ["1xbet TRX", "1xbet", "Paolo", "TRX", "Active", ""],
    ["bet88", "bet88", "Paolo", "PHP", "Active", ""],
    ["747-live", "747-live", "Paolo", "PHP", "Active", ""],
    ["winzir", "winzir", "Paolo", "PHP", "Active", ""],
]
FX_ROWS = [["PHP", 1, "fixed"], ["USDT", "", ""], ["TRX", "", ""]]  # Currency | ₱ per 1 unit | Updated

MONEY, ODDS, PCT, WHEN = "#,##0.00", "0.000", "+0.0%;-0.0%;0.0%", "d mmm yyyy h:mm"
SIGNED = "+#,##0.00;-#,##0.00;0"

TABS = {
    "Accounts": {
        "header": ["Account", "Book", "Holder", "Currency", "Status", "Notes"],
        "rows": ACCOUNTS,
        "dropdowns": {3: CURRENCIES, 4: ("Active", "Closed", "Limited")},
        "cols": 6,
    },
    "FX": {
        "header": ["Currency", "₱ per 1 unit", "Updated"],
        "rows": FX_ROWS,
        "formats": {"B": "#,##0.0000"},
        "cols": 3,
    },
    "Ledger": {
        "header": ["Date", "Account", "Type", "Amount", "Pot", "Note"],
        "dropdowns": {1: "=Accounts!$A$2:$A", 2: LEDGER_TYPES, 4: POTS},
        "formats": {"A": "d mmm yyyy", "D": MONEY},
        "cols": 6,
    },
    "Legs": {
        "header": ["Slip ID", "Leg", "Tip ID", "Own pick?", "Match", "Selection (as on slip)", "Odds taken",
                   "Tip odds", "Drift %", "Leg result", "Kickoff (PHT)", "Factor", "Factor at tip odds", "Tip line"],
        "formulas": {
            "I2": '=ARRAYFORMULA(IF((G2:G="")+(H2:H=""),,G2:G/H2:H-1))',
            "L2": '''=ARRAYFORMULA(IF(A2:A="",,IFS(J2:J="Won",G2:G,J2:J="Lost",0,J2:J="Void",1,
J2:J="Half Won",(G2:G+1)/2,J2:J="Half Lost",0.5,TRUE,)))''',
            # What the leg would have paid at the tip's price (own picks: the price taken).
            "M2": '''=ARRAYFORMULA(LET(o,IF(H2:H="",G2:G,H2:H),IF(A2:A="",,IFS(J2:J="Won",o,J2:J="Lost",0,
J2:J="Void",1,J2:J="Half Won",(o+1)/2,J2:J="Half Lost",0.5,TRUE,))))''',
        },
        "dropdowns": {3: ("Yes", "No"), 9: LEG_RESULTS},
        "formats": {"G": ODDS, "H": ODDS, "I": PCT, "K": WHEN, "L": ODDS, "M": ODDS},
        "cols": 14,
    },
    "Bets": {
        "header": ["Slip ID", "Placed (PHT)", "Account", "Type", "Stake", "Total odds", "Legs", "Result",
                   "Return", "P&L", "Cash-out", "Pot", "Placed by", "Notes", "Return at tip odds",
                   "Currency", "FX to ₱", "Stake ₱", "P&L ₱", "Book slip №", "System return",
                   "System return at tip odds"],
        "formulas": {
            "G2": '=MAP(A2:A,LAMBDA(id,IF(id="",,COUNTIF(Legs!A2:A,id))))',
            # System tickets (Type "System k/n"): their return is in U/V, written by the book sync script.
            "H2": '''=MAP(A2:A,K2:K,D2:D,E2:E,U2:U,LAMBDA(id,co,ty,stake,sr,IF(id="",,IFERROR(LET(r,FILTER(Legs!J2:J,Legs!A2:A=id),
IF(co<>"","Cashed out",
IF((LEFT(ty,6)<>"System")*(COUNTIF(r,"Lost")>0),"Lost",
IF(COUNTIF(r,"")>0,"Open",IF(COUNTIF(r,"Void")=ROWS(r),"Void",
IF(LEFT(ty,6)="System",IF(sr="","Open",IF(sr>=stake,"Won",IF(sr>0,"Partly won","Lost"))),
"Won")))))),"No legs"))))''',
            # Combo boost: slip total odds above the product of the legs' odds taken (bet88 x1.08, Solaire 2%).
            "I2": '''=MAP(A2:A,E2:E,K2:K,H2:H,D2:D,U2:U,F2:F,LAMBDA(id,stake,co,res,ty,sr,tot,IF((id="")+(res="Open")+(res="No legs"),,
IF(res="Cashed out",co,IF(res="Void",stake,IF(LEFT(ty,6)="System",sr,
LET(raw,PRODUCT(FILTER(Legs!G2:G,Legs!A2:A=id)),bst,IF((tot<>"")*(raw>0),IF(tot/raw>1.001,ROUND(tot/raw,2),1),1),
ROUND(stake*PRODUCT(FILTER(Legs!L2:L,Legs!A2:A=id))*bst,2))))))))''',
            "J2": '=ARRAYFORMULA(IF((A2:A="")+(I2:I=""),,I2:I-E2:E))',
            "O2": '''=MAP(A2:A,E2:E,H2:H,D2:D,V2:V,LAMBDA(id,stake,res,ty,sv,IF((id="")+(res="Open")+(res="No legs"),,
IF(res="Void",stake,IF(LEFT(ty,6)="System",sv,ROUND(stake*PRODUCT(FILTER(Legs!M2:M,Legs!A2:A=id)),2))))))''',
            "P2": '=ARRAYFORMULA(IF(A2:A="",,IFERROR(VLOOKUP(C2:C,Accounts!A2:D,4,FALSE),"?")))',
            # Q (FX to ₱) is a value written by log-bets: the rate on the day the ticket was placed.
            "R2": '=ARRAYFORMULA(IF((A2:A="")+(Q2:Q=""),,E2:E*Q2:Q))',
            "S2": '=ARRAYFORMULA(IF((A2:A="")+(J2:J="")+(Q2:Q=""),,J2:J*Q2:Q))',
        },
        "dropdowns": {2: "=Accounts!$A$2:$A", 3: TICKET_TYPES, 11: POTS},
        "formats": {"B": WHEN, "E": MONEY, "F": ODDS, "I": MONEY, "J": SIGNED, "K": MONEY, "O": MONEY,
                    "Q": "#,##0.0000", "R": MONEY, "S": SIGNED, "U": MONEY, "V": MONEY},
        "cols": 22,
    },
    "Balances": {
        "header": ["Account", "Opening", "Deposits", "Withdrawals", "Transfers (net)", "Bonus / adj.",
                   "Staked", "Returned", "Balance", "Open stakes", "Currency", "FX now", "Balance ₱", "Open stakes ₱"],
        "formulas": {
            "A2": "TOTAL in ₱ (current FX)", "M2": "=SUM(M3:M)", "N2": "=SUM(N3:N)",
            "A3": '=FILTER(Accounts!A2:A,Accounts!A2:A<>"")',
            "B3": '=MAP(A3:A,LAMBDA(a,IF(a="",,SUMIFS(Ledger!D2:D,Ledger!B2:B,a,Ledger!C2:C,"Opening balance"))))',
            "C3": '=MAP(A3:A,LAMBDA(a,IF(a="",,SUMIFS(Ledger!D2:D,Ledger!B2:B,a,Ledger!C2:C,"Deposit"))))',
            "D3": '=MAP(A3:A,LAMBDA(a,IF(a="",,SUMIFS(Ledger!D2:D,Ledger!B2:B,a,Ledger!C2:C,"Withdrawal"))))',
            "E3": '''=MAP(A3:A,LAMBDA(a,IF(a="",,SUMIFS(Ledger!D2:D,Ledger!B2:B,a,Ledger!C2:C,"Transfer in")
-SUMIFS(Ledger!D2:D,Ledger!B2:B,a,Ledger!C2:C,"Transfer out"))))''',
            "F3": '''=MAP(A3:A,LAMBDA(a,IF(a="",,SUMIFS(Ledger!D2:D,Ledger!B2:B,a,Ledger!C2:C,"Bonus")
+SUMIFS(Ledger!D2:D,Ledger!B2:B,a,Ledger!C2:C,"Adjustment"))))''',
            "G3": '=MAP(A3:A,LAMBDA(a,IF(a="",,SUMIFS(Bets!E2:E,Bets!C2:C,a))))',
            "H3": '=MAP(A3:A,LAMBDA(a,IF(a="",,SUMIFS(Bets!I2:I,Bets!C2:C,a))))',
            "I3": '=ARRAYFORMULA(IF(A3:A="",,B3:B+C3:C-D3:D+E3:E+F3:F-G3:G+H3:H))',
            "J3": '=MAP(A3:A,LAMBDA(a,IF(a="",,SUMIFS(Bets!E2:E,Bets!C2:C,a,Bets!H2:H,"Open"))))',
            "K3": '=MAP(A3:A,LAMBDA(a,IF(a="",,VLOOKUP(a,Accounts!A2:D,4,FALSE))))',
            "L3": '=MAP(K3:K,LAMBDA(c,IF(c="",,IF(VLOOKUP(c,FX!A2:B,2,FALSE)="","set FX",VLOOKUP(c,FX!A2:B,2,FALSE)))))',
            "M3": '=ARRAYFORMULA(IF(A3:A="",,IFERROR(I3:I*L3:L,0)))',
            "N3": '=ARRAYFORMULA(IF(A3:A="",,IFERROR(J3:J*L3:L,0)))',
        },
        "formats": {**{c: MONEY for c in "BCDEFGHIJMN"}, "L": "#,##0.0000"},
        "cols": 14,
    },
    "Dashboard": {"header": [], "cols": 8},
}

BY_TYPE = ('=IFERROR(LET(t,UNIQUE(FILTER(Bets!D2:D,Bets!A2:A<>"",Bets!H2:H<>"Open")),HSTACK(t,'
           'MAP(t,LAMBDA(x,COUNTIFS(Bets!D2:D,x,Bets!H2:H,"<>Open"))),'
           'MAP(t,LAMBDA(x,SUMIFS(Bets!R2:R,Bets!D2:D,x,Bets!H2:H,"<>Open"))),'
           'MAP(t,LAMBDA(x,SUMIFS(Bets!S2:S,Bets!D2:D,x,Bets!H2:H,"<>Open"))))),"No settled tickets yet")')

DASHBOARD = [
    ["Private book", "", "", "", "", "", "", ""],
    ["Started 8 Oct 2026 · in ₱ (balances at current FX, ticket P&L at the FX of the day placed) · "
     "a ticket's stake leaves the balance when placed", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", ""],
    ["Bankroll ₱", "Cash in books ₱", "Open stakes ₱", "Settled P&L ₱", "Turnover ₱ (settled)", "ROI",
     "Tickets open", "Tickets settled"],
    ["=B5+C5", "=Balances!M2", "=Balances!N2", "=SUM(Bets!S2:S)", '=SUMIFS(Bets!R2:R,Bets!I2:I,"<>")',
     "=IF(E5=0,,D5/E5)", '=COUNTIF(Bets!H2:H,"Open")', '=COUNTIFS(Bets!A2:A,"<>",Bets!H2:H,"<>Open")'],
    ["", "", "", "", "", "", "", ""],
    ["Price drift", "Returned at odds taken ₱", "Would have returned at tip odds ₱", "Drift cost ₱", "", "", "", ""],
    ["", "=SUMPRODUCT(N(+Bets!I2:I),N(+Bets!Q2:Q))", "=SUMPRODUCT(N(+Bets!O2:O),N(+Bets!Q2:Q))", "=C8-B8",
     "", "", "", ""],
    ["", "", "", "", "", "", "", ""],
    ["By ticket type (settled)", "", "", "", "", "", "", ""],
    ["Type", "Tickets", "Staked ₱", "P&L ₱", "", "", "", ""],
    [BY_TYPE, "", "", "", "", "", "", ""],
]
ORDER_CREATE = ["Accounts", "FX", "Ledger", "Legs", "Bets", "Balances", "Dashboard"]
ORDER_SHOW = ["Dashboard", "Bets", "Legs", "Ledger", "Balances", "Accounts", "FX"]


def build_tab(sh, t, spec):
    ws = sh.add_worksheet(t, rows=1000, cols=spec["cols"])
    if spec["header"]:
        ws.update(range_name="A1", values=[spec["header"]], value_input_option="RAW")
    if spec.get("rows"):
        ws.update(range_name="A2", values=spec["rows"], value_input_option="RAW")
    if spec.get("formulas"):
        ws.batch_update([{"range": c, "values": [[f]]} for c, f in spec["formulas"].items()],
                        value_input_option="USER_ENTERED")
    fmts = [{"range": f"{l}2:{l}", "format": {"numberFormat": {
        "type": "DATE_TIME" if "yyyy" in pat else "NUMBER", "pattern": pat}}}
        for l, pat in spec.get("formats", {}).items()]
    if spec["header"]:
        fmts.append({"range": f"A1:{chr(64 + spec['cols'])}1", "format": {"textFormat": {"bold": True}}})
        ws.freeze(rows=1)
    if fmts:
        ws.batch_format(fmts)
    reqs = []
    for col, src in spec.get("dropdowns", {}).items():
        rng = {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": 1000, "startColumnIndex": col, "endColumnIndex": col + 1}
        cond = ({"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": src}]} if isinstance(src, str)
                else {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in src]})
        reqs.append({"setDataValidation": {"range": rng, "rule": {"condition": cond, "strict": True, "showCustomUi": True}}})
    if reqs:
        sh.batch_update({"requests": reqs})
    return ws


def upgrade(sh, apply):
    """Bring existing tabs up to the current TABS spec: width, header row, formula cells, formats
    and dropdowns. Data cells are never written (formula cells are formula-only by design)."""
    for t in ORDER_CREATE:
        spec = TABS[t]
        if t == "Dashboard" or not spec["header"]:
            continue
        ws = sh.worksheet(t)
        current = ws.row_values(1)
        changes = [h for h in spec["header"] if h not in current]
        print(f"  {t}: new columns {changes or 'none'}; {len(spec.get('formulas', {}))} formula cells refreshed")
        if not apply:
            continue
        if ws.col_count < spec["cols"]:
            ws.add_cols(spec["cols"] - ws.col_count)
        ws.update(range_name="A1", values=[spec["header"]], value_input_option="RAW")
        if spec.get("formulas"):
            ws.batch_update([{"range": c, "values": [[f]]} for c, f in spec["formulas"].items()],
                            value_input_option="USER_ENTERED")
        fmts = [{"range": f"{l}2:{l}", "format": {"numberFormat": {
            "type": "DATE_TIME" if "yyyy" in pat else "NUMBER", "pattern": pat}}}
            for l, pat in spec.get("formats", {}).items()]
        fmts.append({"range": f"A1:{chr(64 + spec['cols'])}1", "format": {"textFormat": {"bold": True}}})
        ws.batch_format(fmts)
        reqs = []
        for col, src in spec.get("dropdowns", {}).items():
            rng = {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": ws.row_count, "startColumnIndex": col, "endColumnIndex": col + 1}
            cond = ({"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": src}]} if isinstance(src, str)
                    else {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in src]})
            reqs.append({"setDataValidation": {"range": rng, "rule": {"condition": cond, "strict": True, "showCustomUi": True}}})
        if reqs:
            sh.batch_update({"requests": reqs})
        time.sleep(4)


def main():
    apply = "--apply" in sys.argv
    rebuild = "--rebuild" in sys.argv
    if "--upgrade" in sys.argv:
        from inspect_sheet import READONLY, READWRITE, client
        sh = client(READWRITE if apply else READONLY).open_by_key(BOOK_KEY)
        print(f"[{sh.title}] upgrade {'APPLY' if apply else 'dry run'}")
        upgrade(sh, apply)
        return
    from inspect_sheet import READONLY, READWRITE, client
    sh = client(READWRITE if apply else READONLY).open_by_key(BOOK_KEY)
    existing = [w.title for w in sh.worksheets()]
    if rebuild:
        for t in ("Bets", "Ledger"):
            if t in existing and any(any(c.strip() for c in r) for r in sh.worksheet(t).get_all_values()[1:]):
                sys.exit(f"refusing --rebuild: {t} has data rows")
    todo = ORDER_CREATE if rebuild else [t for t in ORDER_CREATE if t not in existing]
    print(f"[{sh.title}] {'APPLY' if apply else 'dry run'}: existing {existing}; "
          f"{'rebuild all' if rebuild else 'create'} {todo}")
    for t in todo:
        print(f"  {t}: {', '.join(TABS[t]['header']) or '(dashboard)'}")
    if not apply or not todo:
        return
    if rebuild:
        keep = sh.add_worksheet("_tmp", rows=1, cols=1)  # a sheet must always have one tab
        for w in sh.worksheets():
            if w.id != keep.id:
                sh.del_worksheet(w)
        time.sleep(5)
    for t in todo:
        build_tab(sh, t, TABS[t])
        print(f"  created {t}")
        time.sleep(8)  # stay under 60 writes/minute
    if "Dashboard" in todo:
        d = sh.worksheet("Dashboard")
        d.update(range_name="A1", values=DASHBOARD, value_input_option="USER_ENTERED")
        d.batch_format([
            {"range": "A1", "format": {"textFormat": {"bold": True, "fontSize": 14}}},
            {"range": "A4:H4", "format": {"textFormat": {"bold": True}}},
            {"range": "A7:D7", "format": {"textFormat": {"bold": True}}},
            {"range": "A10:D11", "format": {"textFormat": {"bold": True}}},
            {"range": "C12:D", "format": {"numberFormat": {"type": "NUMBER", "pattern": MONEY}}},
            {"range": "A5:E5", "format": {"numberFormat": {"type": "NUMBER", "pattern": MONEY}}},
            {"range": "F5", "format": {"numberFormat": {"type": "PERCENT", "pattern": PCT}}},
            {"range": "B8:D8", "format": {"numberFormat": {"type": "NUMBER", "pattern": MONEY}}},
        ])
    for i, t in enumerate(ORDER_SHOW):
        sh.worksheet(t).update_index(i)
    for leftover in ("Sheet1", "_tmp"):
        if leftover in [w.title for w in sh.worksheets()]:
            sh.del_worksheet(sh.worksheet(leftover))
    print("  done:", [w.title for w in sh.worksheets()])


if __name__ == "__main__":
    main()
