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

from fixtures import PHT, SHEETS_EPOCH, DateNotAvailable, fetch, games, match
from log_picks import SHEETS, VOCAB
from parse import Selection
from settle import settle

HERE = Path(__file__).resolve().parent
LAST_RUN = HERE / "data" / "last_sync.json"
COL = {"id": 0, "kickoff": 1, "sport": 2, "match": 5, "home": 6, "away": 7, "market": 8, "period": 9,
       "side": 10, "line": 11, "selection": 12, "result": 15, "status": 16, "fixture": 19}
API_SPORTS = ("Football", "Basketball")
FINISHED = {"FT", "AET", "PEN", "AOT"}          # settle from the score
NOT_PLAYED = {"PST", "CANC", "ABD", "AWD", "WO", "SUSP", "INT"}  # Paolo decides (books differ on voids)


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

    # Rows to settle: fixture known, no result yet.
    to_settle, too_late, manual = {}, [], []
    for i, r in enumerate(rows[2:], start=3):
        r = r + [""] * (20 - len(r))
        if not r[0] or r[COL["result"]]:
            continue
        if r[COL["fixture"]]:
            ko = datetime.strptime(r[COL["kickoff"]], "%d %B %Y %H:%M")
            if ko.date().isoformat() in days:
                to_settle.setdefault((r[COL["sport"]], ko.date().isoformat(), r[COL["fixture"]]), []).append((i, r))
            elif ko.date().isoformat() < days[0]:
                too_late.append(r)
        elif r[COL["status"]] == "Needs result":
            manual.append(r)  # tennis, or a match the API never found

    # Fetch only the days we need: the kickoff's day if known and in the window, else the whole window.
    needed = {(sport, d) for sport, d, _ in to_settle}
    for (sport, _, _), group in todo.items():
        ko = group[0][1][COL["kickoff"]]
        ko_day = None
        if ko:
            ko_day = datetime.strptime(ko, "%d %B %Y %H:%M").date().isoformat()
        needed |= {(sport, d) for d in ([ko_day] if ko_day in days else days if not ko_day else [])}
    pool, spent, skipped = [], 0, []
    for sport, d in sorted(needed):
        cached = (HERE / "data" / "api" / sport.lower() / f"{d}.json")
        fresh = cached.exists() and time.time() - cached.stat().st_mtime < 3 * 3600
        try:
            pool += games(sport, fetch(sport, d))
        except DateNotAvailable:
            skipped.append(f"{sport} {d}")  # near UTC midnight the API's window is a day behind PHT's
            continue
        spent += 0 if fresh else 1
    print(f"  {len(todo)} matches need a fixture; fetched {len(needed)} day(s), {spent} new API request(s)")
    if skipped:
        print(f"  skipped (the free plan refuses these dates for now): {', '.join(skipped)}")

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
            # Settle in this same run if it's already played.
            to_settle.setdefault((sport, day_of(g.kickoff), f"{sport[0]}{g.id}"), []).extend(group)
            found_ids = {r[COL["id"]] for _, r in group}
            manual[:] = [r for r in manual if r[COL["id"]] not in found_ids]
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

    # Settlement
    by_id = {f"{g.sport[0]}{g.id}": g for g in pool}
    settled, waiting, ask = 0, 0, []
    for (sport, d, fid), group in sorted(to_settle.items(), key=lambda kv: kv[1][0][0]):
        g = by_id.get(fid)
        if g is None:
            ask.append((group, f"fixture {fid} not in the API data for {d}"))
            continue
        if g.status in NOT_PLAYED:
            ask.append((group, f"match status {g.status} (postponed/cancelled/abandoned)"))
            continue
        if g.status not in FINISHED or g.home_score is None:
            waiting += 1
            continue
        ht = (g.home_ht, g.away_ht)
        score = f"{g.home_score}-{g.away_score}" + (f" (HT {g.home_ht}-{g.away_ht})" if None not in ht else "")
        print(f"  result {g.home} vs {g.away}: {score}{'' if g.status == 'FT' else ' [' + g.status + ']'}")
        for i, r in group:
            line = float(r[COL["line"]]) if r[COL["line"]] else None
            sel = Selection(r[COL["market"]], r[COL["period"]], r[COL["side"]], line)
            res = settle(sel, sport, (g.home_score, g.away_score), ht if None not in ht else None)
            updates.append({"range": f"O{i}", "values": [[score]]})
            if res is None:
                ask.append(([(i, r)], f"{r[COL['selection']]} can't be settled from the score; score {score} filled in"))
                continue
            settled += 1
            updates.append({"range": f"P{i}", "values": [[res]]})
            print(f"           {r[COL['id']]} {r[COL['selection']]:22s} -> {res}")
    for group, why in ask:
        print(f"  ASK    {', '.join(r[COL['id']] for _, r in group)} {group[0][1][COL['match']]}: {why}")
    for r in too_late:
        print(f"  BY HAND {r[COL['id']]} {r[COL['match']]} {r[COL['selection']]}: kickoff before the window, enter the result by hand")
    for r in manual:
        print(f"  BY HAND {r[COL['id']]} {r[COL['match']]} {r[COL['selection']]} ({r[COL['sport']]}): needs a result")
    print(f"  results: {settled} settled, {waiting} matches not finished yet, {len(ask)} to ask, "
          f"{len(too_late) + len(manual)} by hand")

    LAST_RUN.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN.write_text(json.dumps({"date": today.isoformat()}))
    if not apply:
        return
    if rows[1][19:20] != ["Fixture ID"]:
        updates.append({"range": "T2", "values": [["Fixture ID"]]})
    n_cells = len(updates)
    if updates:
        ws.batch_update(updates, value_input_option="RAW")
    VOCAB.write_text(json.dumps(vocab, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  written: {sure} fixtures found, {settled} picks settled ({n_cells} cells)")


if __name__ == "__main__":
    main()
