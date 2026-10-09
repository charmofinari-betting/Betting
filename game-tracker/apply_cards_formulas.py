"""One-off: teach the sheet the three new card markets (Home/Away team cards, Cards handicap).
Updates Calc H2, M2, N2 (bet type, market detail, side) and the Sheet1 Market dropdown. Dry run unless --apply.
Usage: python apply_cards_formulas.py [--apply] [--staging]
Backs up the old formulas to out/calc_formulas_backup_<sheet>.json first and checks the Dashboard is unchanged.
"""
import json
import sys

import formulas
from inspect_sheet import READONLY, READWRITE, client
from log_picks import SHEETS

CELLS = {"H2": ("H2",), "M2": ("M2",), "N2": ("N2", "O2")}  # N2's formula spills into O


def main():
    apply = "--apply" in sys.argv
    key = SHEETS["staging" if "--staging" in sys.argv else "live"]
    sh = client(READWRITE if apply else READONLY).open_by_key(key)
    calc, dash, s1 = sh.worksheet("Calc"), sh.worksheet("Dashboard"), sh.worksheet("Sheet1")
    old = {c: calc.get(c, value_render_option="FORMULA")[0][0] for c in CELLS}
    changed = [c for c in CELLS if old[c] != formulas.CALC[c]]
    print(f"[{sh.title}] {'APPLY' if apply else 'dry run'}: {len(changed)} Calc formulas differ ({', '.join(changed) or 'none'}); "
          f"Market dropdown gets {len(formulas.MARKETS_NEW)} new values")
    if not apply:
        return
    before = dash.get_all_values()
    json.dump(old, open(f"out/calc_formulas_backup_{key[:6]}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for c in changed:
        calc.batch_clear([f"{CELLS[c][0]}:{CELLS[c][-1]}"])
        calc.update(range_name=c, values=[[formulas.CALC[c]]], value_input_option="USER_ENTERED")
    meta = sh.fetch_sheet_metadata(params={"fields": "sheets(properties(sheetId,title))"})
    sh.batch_update({"requests": [{"setDataValidation": {
        "range": {"sheetId": s1.id, "startRowIndex": 2, "endRowIndex": 1000, "startColumnIndex": 8, "endColumnIndex": 9},
        "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": o} for o in formulas.DROPDOWNS[8]]},
                 "strict": True, "showCustomUi": True}}}]})
    after = dash.get_all_values()
    diffs = [(i, j) for i in range(len(before)) for j in range(len(before[i])) if i >= len(after) or j >= len(after[i]) or before[i][j] != after[i][j]]
    print(f"  written; Dashboard cells changed: {len(diffs)}")
    for i, j in diffs[:10]:
        print(f"   {chr(65 + j)}{i + 1}: {before[i][j]!r} -> {after[i][j] if i < len(after) and j < len(after[i]) else None!r}")


if __name__ == "__main__":
    main()
