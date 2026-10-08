"""Write rows into the first empty rows of a tab. Dry run unless --apply.

Usage: python write_rows.py <sheet_key> <tab> <rows.tsv> [--apply]
Only writes into rows whose target columns are empty, starting below the
last non-empty row of column A..(width), so it never overwrites data.
"""
import sys

from inspect_sheet import READWRITE, client


def main():
    key, tab, path = sys.argv[1:4]
    apply = "--apply" in sys.argv
    rows = [l.rstrip("\n").split("\t") for l in open(path, encoding="utf-8") if l.strip()]
    width = max(len(r) for r in rows)
    ws = client(READWRITE).open_by_key(key).worksheet(tab)
    values = ws.get_all_values()
    last = max((i for i, r in enumerate(values) if any(c.strip() for c in r[:width])), default=-1)
    start = last + 2  # 1-based row after the last non-empty one
    end_col = chr(ord("A") + width - 1)
    rng = f"A{start}:{end_col}{start + len(rows) - 1}"
    print(f"{tab}!{rng}  ({'APPLY' if apply else 'dry run'})")
    for r in rows:
        print("  " + " | ".join(r))
    if apply:
        ws.update(range_name=rng, values=rows, value_input_option="USER_ENTERED")
        print("written")


if __name__ == "__main__":
    main()
