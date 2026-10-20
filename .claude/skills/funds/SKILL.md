---
name: funds
description: Tell Paolo where his money stands — capital (opening + deposits), total withdrawn, cash in the books, open stakes, settled betting P&L — per pot (own PHP, own crypto in its own units, each account holder). Use when he asks "capital?", "funds?", "how much is in the accounts", "how much have I withdrawn", or types /funds.
---

# funds

`game-tracker/funds.py` reads the Balances tab (built from Ledger + Bets) and prints one column per pot.
Read-only. The same numbers live in the **Funds** tab of the Private Betting sheet (phone: Sheets app).

## Run
```
cd game-tracker   # from the repo root (laptop or cloud)
PYTHONIOENCODING=utf-8 ../.venv/Scripts/python funds.py
```

## Answer (phone-short)
- Lead with **Own PHP**: capital, withdrawn, cash in accounts, open stakes, settled P&L.
- Then own crypto **in its own units** (TRX, USDT). Never convert crypto into the peso totals; Paolo treats 1,000 TRX as 1,000 TRX. A ₱ estimate only if he asks.
- Then each holder (Pat, Tish, Grace...) on its own line: their capital, cash, open, P&L. This is the base for their commission, so never fold it into his own figures.
- Definitions: capital = opening balances + deposits; P&L counts open stakes at cost (profit only once tickets settle).

## Checks
- If he quotes an app balance, compare it with "Cash in accounts" for that book (Balances tab). A gap means a missing slip or ledger line: say so, never adjust to make it match.
- Deposits/withdrawals only enter via Ledger lines he confirms (dry run first, `write_rows.py`).
- A new holder or currency: run `funds.py tab` (dry run), then `tab --apply` on his yes to add the column.
