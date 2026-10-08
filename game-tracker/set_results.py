"""Enter results by hand (tennis, postponed matches, corners, cards...). Dry run unless --apply.

Usage: python set_results.py T-0502=Won T-0505=Lost "T-0582=Void:postponed" [--apply] [--staging]
Each argument is ID=Result, optionally with :note (written to Notes). Results must be one of
Won, Lost, Half Won, Half Lost, Void. Rows that already have a result are refused.
"""
import sys

from formulas import RESULTS
from log_picks import SHEETS


def parse_args(args):
    out = []
    for a in args:
        if a.startswith("--"):
            continue
        rid, _, rest = a.partition("=")
        result, _, note = rest.partition(":")
        out.append((rid.strip(), result.strip(), note.strip()))
    return out


def main():
    apply = "--apply" in sys.argv
    key = SHEETS["staging" if "--staging" in sys.argv else "live"]
    wanted = parse_args(sys.argv[1:])
    bad = [f"{rid}: {res!r} is not one of {', '.join(RESULTS)}" for rid, res, _ in wanted if res not in RESULTS]
    if bad:
        sys.exit("\n".join(bad))

    from inspect_sheet import READONLY, READWRITE, client
    sh = client(READWRITE if apply else READONLY).open_by_key(key)
    ws = sh.worksheet("Sheet1")
    rows = {r[0]: (i, r + [""] * (20 - len(r))) for i, r in enumerate(ws.get_all_values(), start=1) if r and r[0].startswith("T-")}
    print(f"[{sh.title}] {'APPLY' if apply else 'dry run'}")
    updates, problems = [], []
    for rid, res, note in wanted:
        if rid not in rows:
            problems.append(f"{rid}: no such ID")
            continue
        i, r = rows[rid]
        if r[15]:
            problems.append(f"{rid}: already has result {r[15]!r}")
            continue
        print(f"  {rid} {r[5]} | {r[12]} @ {r[13]} -> {res}{'  (note: ' + note + ')' if note else ''}")
        updates.append({"range": f"P{i}", "values": [[res]]})
        if note:
            updates.append({"range": f"S{i}", "values": [[(r[18] + "; " if r[18] else "") + note]]})
    for p in problems:
        print(f"  PROBLEM {p}")
    if apply:
        if problems:
            sys.exit("not applying: fix the problems above first")
        ws.batch_update(updates, value_input_option="RAW")
        print(f"  written: {len(wanted)} results")


if __name__ == "__main__":
    main()
