"""Log tipster picks (transcribed from screenshots) into Sheet1. Dry run unless --apply.

Usage: python log_picks.py <picks.tsv> [--apply] [--staging]

picks.tsv: one pick per line, tab-separated, columns exactly as the tips table shows them:
    Country  League  Event  Market  Sent Odds  [Kickoff]
Kickoff is optional ("YYYY-MM-DD HH:MM", PHT), e.g. for tennis, which Paolo fills himself.

Rows are checked against vocab.json (leagues, aliases) and parse.py (markets). Any problem
blocks --apply; fix vocab.json (or the TSV) and run again.
"""
import difflib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from parse import ParseError, parse_selection

HERE = Path(__file__).resolve().parent
VOCAB = HERE / "vocab.json"
SHEETS = {"live": "1Q4icsCr6c9378cOfu_tyJkBVh9gx3kz5Iu9YUdgZFeA",
          "staging": "128WyTtzzKIxQd7X7rOQZgwKXsemYvzMt6kldpjlyhLs"}
SHEETS_EPOCH = datetime(1899, 12, 30)
LAST_WRITTEN_COL = "P"  # A ID .. P Result; Q Status is a formula; R, S stay empty


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def dedupe_key(home, away, market, period, side, line):
    line = "" if line in ("", None) else f"{float(line):g}"
    return (norm(home), norm(away), market, period, side, line)


@dataclass
class Plan:
    new: list = field(default_factory=list)         # rows ready to write (list of column values A..P)
    duplicates: list = field(default_factory=list)  # (input line no, existing ID or "this batch", text)
    problems: list = field(default_factory=list)    # (input line no, message)
    warnings: list = field(default_factory=list)    # (input line no, message): shown, never block


LADDER = re.compile(r"^(.*\S)\s*\(([^()]*,[^()]*)\)$")


def expand_ladder(text, odds_s):
    """A ladder tip ("UNDER (2.5, 3*)" @ "2.45 / 1.95") -> one (text, odds) per line, the
    tipster's starred line keeping its "*" in the text. Anything else comes back unchanged.
    Raises ValueError when the number of lines and odds differ."""
    m = LADDER.match(text)
    if not m:
        return [(text, odds_s)]
    lines = [x.strip() for x in m[2].split(",")]
    odds = [x.strip() for x in odds_s.split("/")]
    if len(lines) != len(odds):
        raise ValueError(f"ladder has {len(lines)} lines but {len(odds)} odds")
    return [(f"{m[1]} {ln}", o) for ln, o in zip(lines, odds)]


def plan(picks, existing, vocab):
    """picks: list of input rows [country, league, event, market, odds, kickoff?].
    A ladder row is logged as one row per line (see expand_ladder).
    existing: Sheet1 data rows (from row 3). Pure function: no I/O."""
    expanded = []
    for n, p in enumerate(picks, start=1):
        p = [c.strip() for c in p] + [""] * (6 - len(p))
        try:
            expanded += [(n, p[:3] + [t, o] + p[5:6]) for t, o in expand_ladder(p[3], p[4])]
        except ValueError as e:
            expanded.append((n, p[:6] + [str(e)]))
    out = Plan()
    seen = {}
    teams = {}  # normalised -> spelling used in the sheet
    next_id = 1
    for r in existing:
        if not r or not r[0]:
            continue
        next_id = max(next_id, int(r[0].split("-")[1]) + 1)
        seen[dedupe_key(*r[6:12])] = r[0]
        teams.update({norm(t): t for t in r[6:8]})
    tours = set(vocab["tennis_tours"])
    for n, p in expanded:
        country, league, event, text, odds_s, ko_s = p[:6]
        if len(p) > 6:  # ladder that couldn't be expanded
            out.problems.append((n, f"{event} {text}: {p[6]}"))
            continue
        league = vocab["league_aliases"].get(league, league)
        home, sep, away = event.partition(" vs ")
        home = vocab["team_aliases"].get(home.strip(), home.strip())
        away = vocab["team_aliases"].get(away.strip(), away.strip())
        problems = []
        if not sep:
            problems.append(f"can't split teams in {event!r} (expected 'Home vs Away')")
        sport = "Tennis" if country in tours else vocab["league_sport"].get(league)
        if not sport:
            problems.append(f"unknown league {league!r} ({country}): add it to league_sport, or an alias")
        try:
            sel = parse_selection(text.rstrip("*"))
        except ParseError as e:
            problems.append(str(e))
            sel = None
        try:
            odds = float(odds_s)
            if odds <= 1:
                problems.append(f"odds {odds_s!r} must be above 1")
        except ValueError:
            problems.append(f"odds {odds_s!r} not a number")
            odds = None
        ko = None
        if ko_s:
            try:
                ko = (datetime.strptime(ko_s, "%Y-%m-%d %H:%M") - SHEETS_EPOCH).total_seconds() / 86400
            except ValueError:
                problems.append(f"kickoff {ko_s!r} not 'YYYY-MM-DD HH:MM'")
        if problems:
            out.problems += [(n, f"{event} {text}: {m}") for m in problems]
            continue
        key = dedupe_key(home, away, sel.market, sel.period, sel.side, sel.line)
        if key in seen:
            out.duplicates.append((n, seen[key], f"{home} vs {away} {text}"))
            continue
        for t in (home, away):
            if norm(t) not in teams:
                close = difflib.get_close_matches(norm(t), list(teams), n=1, cutoff=0.85)
                if close:
                    out.warnings.append((n, f"new team {t!r} looks like existing {teams[close[0]]!r}: add a team alias if it's the same team"))
        rid = f"T-{next_id:04d}"
        next_id += 1
        seen[key] = "this batch"
        out.new.append([rid, ko, sport, country, league, f"{home} vs {away}", home, away,
                        sel.market, sel.period, sel.side, sel.line, text, odds, None, None])
    return out


def read_tsv(path):
    return [line.rstrip("\n").split("\t") for line in open(path, encoding="utf-8") if line.strip()]


def main():
    path = sys.argv[1]
    apply = "--apply" in sys.argv
    key = SHEETS["staging" if "--staging" in sys.argv else "live"]
    from inspect_sheet import READONLY, READWRITE, client  # local import keeps plan() testable offline
    sh = client(READWRITE if apply else READONLY).open_by_key(key)
    ws = sh.worksheet("Sheet1")
    existing = ws.get_all_values()[2:]
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    result = plan(read_tsv(path), existing, vocab)

    print(f"[{sh.title}] {'APPLY' if apply else 'dry run'}: {len(result.new)} new, "
          f"{len(result.duplicates)} already logged, {len(result.problems)} problems")
    for n, msg in result.problems:
        print(f"  PROBLEM line {n}: {msg}")
    for n, msg in result.warnings:
        print(f"  CHECK   line {n}: {msg}")
    for n, rid, text in result.duplicates:
        print(f"  skip   line {n}: {text}  (already {rid})")
    for r in result.new:
        ko = "no kickoff" if r[1] is None else (SHEETS_EPOCH + timedelta(days=r[1])).strftime("%a %d %b %H:%M")
        line = "" if r[11] is None else f" {r[11]:g}"
        print(f"  new    {r[0]}  {r[2]:10s} {r[4]} | {r[5]} | {r[8]} {r[9]} {r[10]}{line}  @ {r[13]}  ({ko})")
    if not apply:
        return
    if result.problems:
        sys.exit("not applying: fix the problems above first")
    if not result.new:
        print("nothing to write")
        return
    last = max((i for i, r in enumerate(existing) if r and r[0]), default=-1)
    start = last + 4  # existing[0] is sheet row 3; next empty row after the last ID
    end = start + len(result.new) - 1
    ws.update(range_name=f"A{start}:{LAST_WRITTEN_COL}{end}", values=result.new, value_input_option="RAW")
    print(f"written to Sheet1 rows {start}-{end}")


if __name__ == "__main__":
    main()
