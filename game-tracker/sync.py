"""Daily sync with api-sports: fill kickoffs and fixture IDs on Sheet1. Dry run unless --apply.

Usage: python sync.py [--apply] [--staging] [--accept T-0123,T-0124]

Free plan: only yesterday, today and tomorrow (PHT) are available, so run this daily.
- 'sure' matches are written on --apply.
- 'check' matches are listed; after Paolo confirms, pass their IDs with --accept and the
  team names are saved to vocab.json (api_team_aliases) so they match by themselves next time.
Tennis is skipped (not on api-sports; Paolo fills it).
"""
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from fixtures import PHT, SHEETS_EPOCH, fetch, games, match
from log_picks import SHEETS, VOCAB

HERE = Path(__file__).resolve().parent
LAST_RUN = HERE / "data" / "last_sync.json"
COL = {"id": 0, "kickoff": 1, "sport": 2, "match": 5, "home": 6, "away": 7, "result": 15, "fixture": 19}
API_SPORTS = ("Football", "Basketball")


def window(today):
    return [(today + timedelta(days=d)).isoformat() for d in (-1, 0, 1)]


def day_of(serial):
    return (SHEETS_EPOCH + timedelta(days=serial)).date().isoformat()


def ko_text(serial):
    return (SHEETS_EPOCH + timedelta(days=serial)).strftime("%a %d %b %H:%M")


def gap_warning(today):
    if not LAST_RUN.exists():
        return None
    last = datetime.fromisoformat(json.loads(LAST_RUN.read_text())["date"]).date()
    lost = [(last + timedelta(days=d)).isoformat() for d in range(0, (today - last).days - 1)]
    if lost:
        return (f"last sync was {last.isoformat()}: results for {', '.join(lost)} are outside the free "
                f"plan's window now; settle those by hand")
    return None


def main():
    apply = "--apply" in sys.argv
    accept = set()
    if "--accept" in sys.argv:
        accept = set(sys.argv[sys.argv.index("--accept") + 1].split(","))
    key = SHEETS["staging" if "--staging" in sys.argv else "live"]
    today = datetime.now(PHT).date()
    days = window(today)
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    aliases = vocab.setdefault("api_team_aliases", {})

    from inspect_sheet import READONLY, READWRITE, client
    sh = client(READWRITE if apply else READONLY).open_by_key(key)
    ws = sh.worksheet("Sheet1")
    rows = ws.get_all_values()
    print(f"[{sh.title}] {'APPLY' if apply else 'dry run'} | window {days[0]} .. {days[-1]} (PHT)")
    warn = gap_warning(today)
    if warn:
        print(f"  WARNING {warn}")

    # Rows that still need a fixture: API sports, unsettled, no fixture ID yet.
    todo = {}
    for i, r in enumerate(rows[2:], start=3):
        r = r + [""] * (20 - len(r))
        if not r[0] or r[COL["sport"]] not in API_SPORTS or r[COL["result"]] or r[COL["fixture"]]:
            continue
        todo.setdefault((r[COL["sport"]], r[COL["home"]], r[COL["away"]]), []).append((i, r))

    # Fetch only the days we need: the kickoff's day if known and in the window, else the whole window.
    needed = set()
    for (sport, _, _), group in todo.items():
        ko = group[0][1][COL["kickoff"]]
        ko_day = None
        if ko:
            ko_day = datetime.strptime(ko, "%d %B %Y %H:%M").date().isoformat()
        needed |= {(sport, d) for d in ([ko_day] if ko_day in days else days if not ko_day else [])}
    pool, spent = [], 0
    for sport, d in sorted(needed):
        cached = (HERE / "data" / "api" / sport.lower() / f"{d}.json")
        fresh = cached.exists() and time.time() - cached.stat().st_mtime < 3 * 3600
        pool += games(sport, fetch(sport, d))
        spent += 0 if fresh else 1
    print(f"  {len(todo)} matches need a fixture; fetched {len(needed)} day(s), {spent} new API request(s)")

    updates, sure, checks, missing = [], 0, [], []
    for (sport, home, away), group in sorted(todo.items(), key=lambda kv: kv[1][0][0]):
        first = group[0][1]
        ko_known = first[COL["kickoff"]]
        ko_serial = None
        if ko_known:
            ko_serial = (datetime.strptime(ko_known, "%d %B %Y %H:%M") - SHEETS_EPOCH).total_seconds() / 86400
            if day_of(ko_serial) not in days:
                continue  # outside the window: try again on a later day
        g, conf = match(sport, home, away, pool, ko_serial, aliases)
        ids = ", ".join(r[COL["id"]] for _, r in group)
        if conf == "check" and any(r[COL["id"]] in accept for _, r in group):
            aliases[home], aliases[away] = g.home, g.away
            conf = "sure"
        if conf == "sure":
            sure += 1
            moved = ko_serial is not None and abs(g.kickoff - ko_serial) > 5 / 1440
            note = f"  KICKOFF MOVED from {ko_text(ko_serial)}" if moved else ""
            print(f"  found  {ids}: {home} vs {away} -> {g.home} vs {g.away} [{g.league}] {ko_text(g.kickoff)} "
                  f"id {g.id}{note}")
            for i, _ in group:
                updates.append({"range": f"B{i}", "values": [[g.kickoff]]})
                updates.append({"range": f"T{i}", "values": [[f"{sport[0]}{g.id}"]]})
        elif conf == "check":
            checks.append(group[0][1][COL["id"]])
            print(f"  CHECK  {ids}: {home} vs {away} -> {g.home} vs {g.away} [{g.league}, {g.country}] "
                  f"{ko_text(g.kickoff)}?")
        elif not ko_known or day_of(ko_serial) in days:
            missing.append(f"{ids}: {home} vs {away}")
    if missing:
        print(f"  not found in the window ({len(missing)}): kickoff probably later, or not covered")
        for m in missing:
            print(f"    {m}")
    if checks:
        print(f"  to accept the CHECK lines after confirming: --accept {','.join(checks)}")
    print(f"  summary: {sure} found, {len(checks)} to check, {len(missing)} not found")

    LAST_RUN.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN.write_text(json.dumps({"date": today.isoformat()}))
    if not apply:
        return
    if rows[1][19:20] != ["Fixture ID"]:
        updates.append({"range": "T2", "values": [["Fixture ID"]]})
    n_rows = sum(1 for u in updates if u["range"].startswith("T")) - (1 if {"range": "T2", "values": [["Fixture ID"]]} in updates else 0)
    if updates:
        ws.batch_update(updates, value_input_option="RAW")
    VOCAB.write_text(json.dumps(vocab, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  written: {sure} matches, {n_rows} rows")


if __name__ == "__main__":
    main()
