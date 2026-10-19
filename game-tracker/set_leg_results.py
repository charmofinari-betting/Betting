"""Enter results for the private book's own-pick legs by hand (tennis sets, corners...). Dry run unless --apply.

Usage: python set_leg_results.py S-0033:2=Lost S-0034:6=Lost [--apply]
Each argument is SLIP:LEG=Result with Result one of Won, Lost, Half Won, Half Lost, Void.
Legs that already have a result are refused unless you pass --overwrite (for corrections, e.g. a bet the book voided). System returns are written by book_sync.py afterwards."""
import sys

from formulas import RESULTS
from setup_book import BOOK_KEY


def parse_args(args):
    out = []
    for a in args:
        if a.startswith("--"):
            continue
        left, _, result = a.partition("=")
        slip, _, leg = left.partition(":")
        out.append((slip.strip(), int(leg), result.strip()))
    return out


def main():
    apply = "--apply" in sys.argv
    wanted = parse_args(sys.argv[1:])
    bad = [f"{s}:{n}: {r!r} is not one of {', '.join(RESULTS)}" for s, n, r in wanted if r not in RESULTS]
    if bad:
        sys.exit("\n".join(bad))
    from inspect_sheet import READONLY, READWRITE, client
    book = client(READWRITE if apply else READONLY).open_by_key(BOOK_KEY)
    ws = book.worksheet("Legs")
    rows = ws.get_all_values()
    print(f"[Private Betting] set leg results: {'APPLY' if apply else 'dry run'}")
    todo = []
    for slip, leg, result in wanted:
        hit = [i for i, r in enumerate(rows, 1) if i > 1 and r[0] == slip and r[1] == str(leg)]
        if not hit:
            sys.exit(f"{slip} leg {leg}: not found")
        r = rows[hit[0] - 1]
        if r[9] and "--overwrite" not in sys.argv:
            sys.exit(f"{slip} leg {leg} already has a result ({r[9]}); refusing to overwrite (use --overwrite to correct it)")
        print(f"  {slip} leg {leg}: {r[4]} | {r[5]} -> {result}" + (f"  (was {r[9]})" if r[9] else ""))
        todo.append((hit[0], result))
    if apply:
        for row, result in todo:
            ws.update(range_name=f"J{row}", values=[[result]], value_input_option="RAW")
        print(f"  written: {len(todo)} leg results")
        from bets_refresh import refresh
        for line in refresh(book, apply=True):
            print("  refresh " + line)


if __name__ == "__main__":
    main()
