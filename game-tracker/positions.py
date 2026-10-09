"""Open position, max win and balances of the private book (read-only).

  PYTHONIOENCODING=utf-8 ../.venv/Scripts/python positions.py

Max return = every leg of every open ticket wins (systems: every k-combination pays, so a ceiling,
not an expectation). Non-PHP tickets convert at the FX stored on the ticket."""
from math import prod

from log_bets import BOOK_KEY, system_return


def num(s):
    return float(str(s).replace(",", "").replace("+", "") or 0)


def summarise(bets, legs):
    """bets / legs: sheet rows without the header. -> (rows, stake_php, max_return_php)."""
    rows, stake_t, ret_t = [], 0.0, 0.0
    for r in bets:
        if r[7] != "Open":
            continue
        sid, kind, stake, fx = r[0], r[3], num(r[4]), num(r[16]) or 1.0
        odds = [num(l[6]) for l in legs if l[0] == sid]
        if kind.startswith("System"):
            top = system_return(odds, int(kind.split()[1].split("/")[0]), stake)
        else:
            top = stake * prod(odds)
        rows.append((sid, r[2], kind, stake, round(top, 2)))
        stake_t += stake * fx
        ret_t += top * fx
    return rows, round(stake_t, 2), round(ret_t, 2)


def main():
    from inspect_sheet import READONLY, client
    book = client(READONLY).open_by_key(BOOK_KEY)
    bets = book.worksheet("Bets").get_all_values()[1:]
    legs = book.worksheet("Legs").get_all_values()[1:]
    rows, stake, ret = summarise(bets, legs)
    for sid, acct, kind, st, top in rows:
        print(f"{sid}  {acct:<11} {kind:<11} stake {st:>10,.2f}  max {top:>11,.2f}")
    print(f"\n{len(rows)} open: staked ₱{stake:,.2f}, max return ₱{ret:,.2f}, max profit ₱{ret - stake:,.2f}")
    print("\nBalances (₱)")
    for r in book.worksheet("Balances").get_all_values()[1:]:
        if r[0] and r[12] not in ("", "0.00"):
            print(f"  {r[0]:<26} {r[12]:>12}")


if __name__ == "__main__":
    main()
