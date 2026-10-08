"""Migrate the old Sheet1 (free-text selection) to the new structured layout.

Usage: python migrate.py <sheet_key>
Dry run only for now: reads the sheet, writes the proposed new table and a report
to game-tracker/out/, and changes nothing in the sheet.
"""
import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from inspect_sheet import client
from parse import ParseError, market_detail, parse_selection

OUT = Path(__file__).resolve().parent / "out"
HEADER = ["ID", "Kickoff (PHT)", "Sport", "Country", "League", "Home", "Away", "Market",
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
    s1 = sh.worksheet("Sheet1")
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
            "Sport": sport, "Country": country, "League": league, "Home": home.strip(), "Away": away.strip(),
            "Market": sel.market if sel else "", "Period": sel.period if sel else "",
            "Side": sel.side if sel else "", "Line": "" if not sel or sel.line is None else f"{sel.line:g}",
            "Selection (as sent)": text, "Tip odds": odds_s, "Score": "", "Result": result,
            "Status": "", "Closing odds": "", "Notes": "",
            "_sheet_row": i + 1, "_odds": odds, "_detail": market_detail(sel, sport) if sel else "",
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


if __name__ == "__main__":
    main()
