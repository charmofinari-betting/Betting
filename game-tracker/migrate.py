"""Migrate the old Sheet1 (free-text selection) to the new structured layout.

Usage: python migrate.py <sheet_key> [--apply]
Dry run (default): reads the sheet, writes the proposed new table and a report to
game-tracker/out/, and changes nothing in the sheet.
--apply: copies Sheet1 to an "Archive" tab, rewrites Sheet1 in the new layout, puts in
the new Status / Calc / Dashboard formulas (formulas.py), then diffs the Dashboard
before vs after.
"""
import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import formulas
from inspect_sheet import READWRITE, client
from parse import ParseError, market_detail, parse_selection

OUT = Path(__file__).resolve().parent / "out"
HEADER = ["ID", "Kickoff (PHT)", "Sport", "Country", "League", "Match", "Home", "Away", "Market",
          "Period", "Side", "Line", "Selection (as sent)", "Tip odds", "Score", "Result",
          "Status", "Closing odds", "Notes"]
SHEETS_EPOCH = datetime(1899, 12, 30)


def units(result, odds):
    r = result.strip().title()
    return {"Won": odds - 1, "Lost": -1.0, "Half Won": (odds - 1) / 2, "Half Lost": -0.5}.get(
        r, 0.0 if r in ("Void", "Push", "Refund", "Cancelled") else None)


def kickoff_text(serial):
    return (SHEETS_EPOCH + timedelta(days=serial)).strftime("%Y-%m-%d %H:%M")


def load(key):
    sh = client().open_by_key(key)
    # After a first apply the original rows live in Archive; reading from there makes re-runs safe.
    tabs = [w.title for w in sh.worksheets()]
    s1 = sh.worksheet("Archive" if "Archive" in tabs else "Sheet1")
    values = s1.get_all_values()
    raw = s1.get_all_values(value_render_option="UNFORMATTED_VALUE")
    leagues = {r[0].strip(): r[1].strip() for r in sh.worksheet("Leagues").get_all_values()[1:] if r and r[0].strip()}
    return values, raw, leagues


def migrate(values, raw, leagues):
    rows, problems = [], []
    body = [(i, v, raw[i] if i < len(raw) else []) for i, v in enumerate(values) if i >= 2 and any(c.strip() for c in v[:7])]
    # Old sheet: the kickoff is only on the first row of each match; later rows look it up by match name.
    ko_by_match = {}
    for _, v, r in body:
        if r and isinstance(r[0], (int, float)):
            ko_by_match.setdefault(v[3].strip(), r[0])
    for n, (i, v, _) in enumerate(body, start=1):
        country, league, match, text, odds_s, result = (c.strip() for c in v[1:7])
        where = f"row {i + 1}"
        home, sep, away = match.partition(" vs ")
        if not sep:
            problems.append(f"{where}: can't split teams in {match!r}")
        try:
            sel = parse_selection(text)
        except ParseError as e:
            problems.append(f"{where}: {e}")
            sel = None
        sport = leagues.get(league, "")
        if not sport:
            problems.append(f"{where}: league {league!r} not in Leagues tab")
        ko = ko_by_match.get(match)
        try:
            odds = float(odds_s)
        except ValueError:
            problems.append(f"{where}: odds {odds_s!r} not a number")
            odds = None
        rows.append({
            "ID": f"T-{n:04d}", "Kickoff (PHT)": kickoff_text(ko) if ko is not None else "",
            "Sport": sport, "Country": country, "League": league, "Match": match,
            "Home": home.strip(), "Away": away.strip(),
            "Market": sel.market if sel else "", "Period": sel.period if sel else "",
            "Side": sel.side if sel else "", "Line": "" if not sel or sel.line is None else f"{sel.line:g}",
            "Selection (as sent)": text, "Tip odds": odds_s, "Score": "", "Result": result,
            "Status": "", "Closing odds": "", "Notes": "",
            "_sheet_row": i + 1, "_odds": odds, "_ko": ko, "_line": sel.line if sel else None, "_detail": market_detail(sel, sport) if sel else "",
        })
    return rows, problems


def totals(rows, label_of):
    t = defaultdict(lambda: [0, 0, 0.0])  # bets, settled, units
    for r in rows:
        u = units(r["Result"], r["_odds"]) if r["_odds"] is not None else None
        for k in ("ALL", f"sport:{r['Sport']}", f"market:{label_of(r)}"):
            t[k][0] += 1
            if u is not None:
                t[k][1] += 1
                t[k][2] += u
    return t


def cell_value(r, h):
    """Kickoff as a date serial, line and odds as numbers, everything else as text."""
    if h == "Kickoff (PHT)":
        return "" if r["_ko"] is None else r["_ko"]
    if h == "Line":
        return "" if r["_line"] is None else r["_line"]
    if h == "Tip odds":
        return r["_odds"] if r["_odds"] is not None else r[h]
    return r[h]


def apply(key, rows):
    sh = client(READWRITE).open_by_key(key)
    tabs = [w.title for w in sh.worksheets()]
    dash = sh.worksheet("Dashboard")
    before = dash.get_all_values()
    s1 = sh.worksheet("Sheet1")
    if "Archive" in tabs:
        print(f"[{sh.title}] Archive already exists: rebuilding Sheet1 from it")
    else:
        s1.duplicate(new_sheet_name="Archive", insert_sheet_index=len(tabs))
        print(f"[{sh.title}] Sheet1 copied to Archive")

    s1.batch_clear(["A1:Z"])
    # None, not "": an empty-string cell counts as data and blocks the Status formula's spill.
    body = [[None if v == "" else v for v in (cell_value(r, h) for h in HEADER)] for r in rows]
    s1.update(range_name="A2", values=[HEADER], value_input_option="RAW")
    s1.update(range_name="A3", values=body, value_input_option="RAW")
    s1.format("B3:B", {"numberFormat": {"type": "DATE_TIME", "pattern": "d mmmm yyyy h:mm"}})
    s1.format("A2:S2", {"textFormat": {"bold": True}})
    s1.freeze(rows=2)
    for cell, f in formulas.SHEET1_STATUS.items():
        s1.update(range_name=cell, values=[[f]], value_input_option="USER_ENTERED")
    meta = sh.fetch_sheet_metadata(params={"fields": "sheets(properties(sheetId,title),conditionalFormats)"})
    old_rules = next(len(x.get("conditionalFormats", [])) for x in meta["sheets"] if x["properties"]["title"] == "Sheet1")
    sh.batch_update({"requests": formulas.format_requests(s1.id, old_rules)})
    print(f"[{sh.title}] Sheet1 rewritten: {len(body)} rows + Status formula; "
          f"{old_rules} old colour rules and old dropdowns replaced")

    calc = sh.worksheet("Calc")
    # Clear first: a None cell in an update means "leave as is", so stale formulas would
    # stay in the spill cells and block the new formulas from expanding.
    calc.batch_clear(["A2:P2"])
    row2 = [formulas.CALC.get(f"{chr(65 + j)}2") for j in range(16)]
    calc.update(range_name="A2:P2", values=[row2], value_input_option="USER_ENTERED")
    for cell, f in formulas.DASHBOARD.items():
        dash.update(range_name=cell, values=[[f]], value_input_option="USER_ENTERED")
    print(f"[{sh.title}] Calc + Dashboard formulas replaced")

    if formulas.OPEN_PICKS_TAB in tabs:
        op = sh.worksheet(formulas.OPEN_PICKS_TAB)
        op.batch_clear(["A1:Z"])
    else:
        op = sh.add_worksheet(formulas.OPEN_PICKS_TAB, rows=1000, cols=len(formulas.OPEN_PICKS_HEADER), index=1)
    op.update(range_name="A1", values=[formulas.OPEN_PICKS_HEADER], value_input_option="RAW")
    for cell, f in formulas.OPEN_PICKS.items():
        op.update(range_name=cell, values=[[f]], value_input_option="USER_ENTERED")
    op.format("A1:H1", {"textFormat": {"bold": True}})
    op.format("A2:A", {"numberFormat": {"type": "DATE_TIME", "pattern": "ddd d mmm h:mm"}})
    op.freeze(rows=1)
    print(f"[{sh.title}] '{formulas.OPEN_PICKS_TAB}' tab set up")

    after = dash.get_all_values()
    changed = [(i, j, b, a) for i in range(max(len(before), len(after)))
               for j in range(max(len(before[i]) if i < len(before) else 0, len(after[i]) if i < len(after) else 0))
               for b, a in [((before[i][j] if i < len(before) and j < len(before[i]) else ""),
                             (after[i][j] if i < len(after) and j < len(after[i]) else ""))] if b != a]
    print(f"\nDashboard cells changed: {len(changed)}")
    for i, j, b, a in changed:
        print(f"  {chr(65 + j)}{i + 1}: {b!r} -> {a!r}")


def main():
    values, raw, leagues = load(sys.argv[1])
    rows, problems = migrate(values, raw, leagues)
    OUT.mkdir(exist_ok=True)
    with (OUT / "migration_dryrun.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(HEADER)
        w.writerows([r[h] for h in HEADER] for r in rows)

    # Old labels come from the live Calc tab, so the comparison is against what the Dashboard shows today.
    sh = client().open_by_key(sys.argv[1])
    calc = sh.worksheet("Calc").get_all_values()  # Calc row n+1 mirrors Sheet1 row n+2
    old_label = {r["ID"]: calc[r["_sheet_row"] - 2][12] for r in rows}
    before = totals(rows, lambda r: old_label[r["ID"]])
    after = totals(rows, lambda r: r["_detail"])
    moved = defaultdict(int)
    for r in rows:
        if old_label[r["ID"]] != r["_detail"]:
            moved[(old_label[r["ID"]], r["_detail"])] += 1

    lines = [f"Rows: {len(rows)}   problems: {len(problems)}   no kickoff: {sum(1 for r in rows if not r['Kickoff (PHT)'])}", ""]
    lines += ["Problems:"] + [f"  {p}" for p in problems] + [""] if problems else []
    lines.append("Totals (bets / settled / units)   before -> after")
    for k in sorted(set(before) | set(after)):
        b, a = before.get(k, [0, 0, 0.0]), after.get(k, [0, 0, 0.0])
        flag = "" if (b[0], b[1], round(b[2], 4)) == (a[0], a[1], round(a[2], 4)) else "   <-- changed"
        lines.append(f"  {k:40s} {b[0]:4d} {b[1]:4d} {b[2]:+8.2f}u -> {a[0]:4d} {a[1]:4d} {a[2]:+8.2f}u{flag}")
    lines += ["", "Reclassified (old label -> new label: rows):"] + [f"  {o or '(blank)'} -> {n}: {c}" for (o, n), c in sorted(moved.items())]
    lines += ["", "Rows with no kickoff:"] + [f"  {r['ID']} (sheet row {r['_sheet_row']}): {r['Home']} vs {r['Away']} {r['Selection (as sent)']}" for r in rows if not r["Kickoff (PHT)"]]
    (OUT / "migration_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if "--apply" in sys.argv:
        if problems:
            sys.exit("problems found, not applying")
        apply(sys.argv[1], rows)


if __name__ == "__main__":
    main()
