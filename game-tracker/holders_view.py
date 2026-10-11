"""Holder split for the private book (SPEC-account-holders.md, step 3). Dry run unless --apply.

Usage: python holders_view.py [--apply]
- Balances: new column O "Holder" (looked up from Accounts).
- Dashboard: the KPI row, price drift and by-ticket-type now count Paolo's own tickets/accounts only
  (Bets "Placed by" = Paolo, Balances holder = Paolo). Holder accounts get their own tab.
- Holders (new tab): per holder: deposited, withdrawn, balance, open stakes, net result, and the DRAFT deal
  (floor / share are editable cells; nothing is paid or enforced). Amounts assume PHP accounts.
Not part of setup_book.py: run this on top of an existing book.
"""
import sys
import time

from setup_book import BOOK_KEY, BY_TYPE, MONEY

OWN = '"Paolo"'
DASH = {  # cell -> own-only formula
    "B5": f'=SUMIFS(Balances!M3:M,Balances!O3:O,{OWN})',
    "C5": f'=SUMIFS(Balances!N3:N,Balances!O3:O,{OWN})',
    "D5": f'=SUMIFS(Bets!S2:S,Bets!M2:M,{OWN})',
    "E5": f'=SUMIFS(Bets!R2:R,Bets!I2:I,"<>",Bets!M2:M,{OWN})',
    "G5": f'=COUNTIFS(Bets!H2:H,"Open",Bets!M2:M,{OWN})',
    "H5": f'=COUNTIFS(Bets!A2:A,"<>",Bets!H2:H,"<>Open",Bets!M2:M,{OWN})',
    "B8": f'=SUMPRODUCT(N(+Bets!I2:I),N(+Bets!Q2:Q),--(Bets!M2:M={OWN}))',
    "C8": f'=SUMPRODUCT(N(+Bets!O2:O),N(+Bets!Q2:Q),--(Bets!M2:M={OWN}))',
    "A12": (BY_TYPE.replace('Bets!H2:H<>"Open")', f'Bets!H2:H<>"Open",Bets!M2:M={OWN})')
            .replace('Bets!H2:H,"<>Open")', f'Bets!H2:H,"<>Open",Bets!M2:M,{OWN})')),
    "A3": "Own accounts and tickets only (Placed by Paolo). Holder accounts: see the Holders tab.",
    # holder totals, to the right of the KPI row
    "J4": "Holder accounts ₱ (balance + open stakes)",
    "J5": '=SUMIFS(Balances!M3:M,Balances!O3:O,"<>Paolo",Balances!O3:O,"<>")+SUMIFS(Balances!N3:N,Balances!O3:O,"<>Paolo",Balances!O3:O,"<>")',
}
BAL_O1 = "Holder"
BAL_O3 = '=ARRAYFORMULA(IF(A3:A="",,IFERROR(VLOOKUP(A3:A,Accounts!A2:C,3,FALSE),"?")))'
BAL_A2 = "TOTAL in ₱ (all accounts, current FX)"

HOLDERS_HEADER = ["Holder", "Account", "Since", "Deposited", "Withdrawn", "Balance", "Open stakes",
                  "Net result (cash)", "Net incl. open stakes at cost", "Floor", "Share", "Draft payout", "Notes"]


def holder_row(n, name, account):
    r = n
    sumif = lambda col: f"=SUMIFS(Balances!{col}3:{col},Balances!A3:A,B{r})"
    return [name, account, "11 Oct 2026", sumif("C"), sumif("D"), sumif("I"), sumif("J"),
            f"=F{r}+E{r}-D{r}-SUMIFS(Balances!B3:B,Balances!A3:A,B{r})", f"=H{r}+G{r}", 5000, 0.1,
            f"=MAX(J{r},K{r}*MAX(H{r},0))", "draft deal, month not defined; paid by Paolo, logged in Costs"]


HOLDERS = [holder_row(2, "Pat", "msw.ph Pat"), holder_row(3, "Tish", "bet88 Tish")]
HOLDERS_NOTE = ("Draft deal (not final): each holder gets max(Floor, Share x net result) per period. Net result = balance + "
                "withdrawn - deposited. Period, payout timing, bonus/fee/carry-forward rules are open. "
                "This tab records and computes; it pays and enforces nothing.")


def main():
    apply = "--apply" in sys.argv
    from inspect_sheet import READONLY, READWRITE, client
    sh = client(READWRITE if apply else READONLY).open_by_key(BOOK_KEY)
    dash, bal = sh.worksheet("Dashboard"), sh.worksheet("Balances")
    print(f"[{sh.title}] {'APPLY' if apply else 'dry run'}")
    for cell, f in DASH.items():
        try:
            old = dash.get(cell, value_render_option="FORMULA")
            old = old[0][0] if old and old[0] else ""
        except Exception:
            old = "(outside grid, widened on apply)"
        print(f"  Dashboard {cell}: {str(old)[:70]!r} -> {f[:90]!r}")
    print(f"  Balances O1 {BAL_O1!r}, O3 holder lookup, A2 label -> {BAL_A2!r}")
    print(f"  Holders tab ({'exists' if 'Holders' in [w.title for w in sh.worksheets()] else 'new'}): "
          f"{[h[0] for h in HOLDERS]}")
    if not apply:
        return
    if dash.col_count < 10:
        dash.add_cols(10 - dash.col_count)
    if bal.col_count < 15:
        bal.add_cols(15 - bal.col_count)
    bal.batch_update([{"range": "O1", "values": [[BAL_O1]]}, {"range": "O3", "values": [[BAL_O3]]},
                      {"range": "A2", "values": [[BAL_A2]]}], value_input_option="USER_ENTERED")
    bal.format("O1", {"textFormat": {"bold": True}})
    time.sleep(3)
    dash.batch_update([{"range": c, "values": [[f]]} for c, f in DASH.items()], value_input_option="USER_ENTERED")
    dash.batch_format([{"range": "J4", "format": {"textFormat": {"bold": True}}},
                       {"range": "J5", "format": {"numberFormat": {"type": "NUMBER", "pattern": MONEY}}}])
    time.sleep(3)
    names = [w.title for w in sh.worksheets()]
    ws = sh.worksheet("Holders") if "Holders" in names else sh.add_worksheet("Holders", rows=50, cols=len(HOLDERS_HEADER))
    ws.update(range_name="A1", values=[HOLDERS_HEADER] + HOLDERS, value_input_option="USER_ENTERED")
    ws.update(range_name="A6", values=[[HOLDERS_NOTE]], value_input_option="RAW")
    ws.format("A1:M1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)
    ws.batch_format([{"range": "D2:L3", "format": {"numberFormat": {"type": "NUMBER", "pattern": MONEY}}},
                     {"range": "K2:K3", "format": {"numberFormat": {"type": "PERCENT", "pattern": "0%"}}}])
    sh.worksheet("Holders").update_index(names.index("Balances") + 1 if "Balances" in names else len(names))
    print("  written")


if __name__ == "__main__":
    main()
