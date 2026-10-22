"""The word list (leagues, team spellings, book wordings) in the private book's `Vocab` tab.

Usage:
  python vocab.py                                   list the tab, grouped by kind (read-only)
  python vocab.py setup [--from vocab.json] [--wordings rows.json] [--apply]
                                                    add the tab, copying a vocab.json (and slip wording rows) in
  python vocab.py add "<kind>" "<key>" ["<meaning>"] ["<extra>"] [--by "<who>"] [--apply]

The sheet is the master (SPEC-slip-vocab.md). One row per entry:
  Kind | Key | Meaning | Extra | Added at (PHT) | Added by
Kinds: league sport (league -> sport), league alias (screenshot spelling -> sheet spelling),
team alias (same), api team alias (sheet name -> api-sports name), tennis tour (key only),
slip wording ("<book>: <wording>" -> "<Market> <Period>", Extra: "sport=Football", "line=-0.5", "split").
  Market may be "Team total" / "Team cards": Home or Away from the team the slip names.
load() returns the dict shape vocab.json had, plus "slip_wordings": {key: [entries]}.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from parse import MARKETS, PERIODS

TEAM_MARKETS = ("Team total", "Team cards")  # word-list only: Home/Away comes from the team named

TAB = "Vocab"
HEADER = ["Kind", "Key", "Meaning", "Extra", "Added at (PHT)", "Added by"]
DICT_KINDS = {"league sport": "league_sport", "league alias": "league_aliases",
              "team alias": "team_aliases", "api team alias": "api_team_aliases"}
KINDS = (*DICT_KINDS, "tennis tour", "slip wording")
PHT = timezone(timedelta(hours=8))
_cache = {}


class VocabError(ValueError):
    pass


def norm_label(label):
    """A book label compared loosely: case, spaces and a trailing colon don't matter."""
    return " ".join(label.replace(" ", " ").split()).rstrip(":").strip().lower()


def wording_key(book, label):
    return f"{book}: {norm_label(label)}"


def parse_wording(meaning, extra):
    """'Handicap FT' + 'sport=Football, line=-0.5' -> {"market", "period", "sport", "line", "split"}."""
    parts = meaning.rsplit(" ", 1)
    if len(parts) != 2 or parts[0] not in (*MARKETS, *TEAM_MARKETS) or parts[1] not in PERIODS:
        raise VocabError(f"slip wording meaning {meaning!r}: want '<Market> <Period>', e.g. 'Total FT'")
    entry = {"market": parts[0], "period": parts[1], "sport": None, "line": None, "split": False}
    for flag in (f.strip() for f in extra.split(",") if f.strip()):
        if flag == "split":
            entry["split"] = True
        elif flag.startswith("sport="):
            entry["sport"] = flag[6:].strip()
        elif flag.startswith("line="):
            entry["line"] = float(flag[5:])
        else:
            raise VocabError(f"slip wording extra {flag!r}: want sport=..., line=... or split")
    return entry


def from_rows(rows):
    """Tab rows (without the header) -> the vocab dict."""
    v = {name: {} for name in DICT_KINDS.values()}
    v["tennis_tours"], v["slip_wordings"] = [], {}
    for n, r in enumerate(rows, start=2):
        r = (list(r) + [""] * 4)[:4]
        kind, key, meaning, extra = (c.strip() for c in r)
        if not kind and not key:
            continue
        if kind in DICT_KINDS:
            v[DICT_KINDS[kind]][key] = meaning
        elif kind == "tennis tour":
            v["tennis_tours"].append(key)
        elif kind == "slip wording":
            book, _, label = key.partition(":")
            v["slip_wordings"].setdefault(wording_key(book.strip(), label), []).append(parse_wording(meaning, extra))
        else:
            raise VocabError(f"{TAB} row {n}: unknown kind {kind!r}")
    return v


def rows_from_json(v):
    """A vocab.json dict -> tab rows (Kind, Key, Meaning, Extra)."""
    rows = []
    for kind, name in DICT_KINDS.items():
        rows += [[kind, k, val, ""] for k, val in v.get(name, {}).items()]
    rows += [["tennis tour", t, "", ""] for t in v.get("tennis_tours", [])]
    return rows


def now_text():
    return datetime.now(PHT).strftime("%d %b %Y %H:%M")


def open_book(write=False):
    from inspect_sheet import READONLY, READWRITE, client
    from setup_book import BOOK_KEY
    return client(READWRITE if write else READONLY).open_by_key(BOOK_KEY)


def load(book=None):
    """The live word list (read once per run)."""
    if "v" not in _cache:
        book = book or open_book()
        _cache["v"] = from_rows(book.worksheet(TAB).get_all_values()[1:])
    return _cache["v"]


def append(book, rows, by="Claude"):
    """Add [kind, key, meaning, extra] rows at the bottom of the tab; returns the first row written."""
    for kind, key, meaning, extra in rows:
        if kind not in KINDS:
            raise VocabError(f"unknown kind {kind!r}; one of {', '.join(KINDS)}")
        if kind == "slip wording":
            parse_wording(meaning, extra)
    ws = book.worksheet(TAB)
    start = len(ws.col_values(1)) + 1
    stamp = now_text()
    ws.update(range_name=f"A{start}", values=[[*r, stamp, by] for r in rows], value_input_option="RAW")
    _cache.pop("v", None)
    return start


def setup(src, apply, wordings=None):
    v = json.loads(Path(src).read_text(encoding="utf-8"))
    rows = rows_from_json(v)
    by = ["vocab.json"] * len(rows)
    if wordings:
        extra = json.loads(Path(wordings).read_text(encoding="utf-8"))
        rows += extra
        by += ["seeded from Legs"] * len(extra)
    from_rows(rows)  # same checks the readers will run
    book = open_book(write=apply)
    if TAB in [ws.title for ws in book.worksheets()]:
        sys.exit(f"{TAB} already exists on {book.title}; nothing to do")
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    print(f"[{book.title}] {'APPLY' if apply else 'dry run'}: add tab {TAB} ({' | '.join(HEADER)})")
    print(f"  copy from {Path(src).name}{' + ' + Path(wordings).name if wordings else ''}: " + ", ".join(f"{n} {k}" for k, n in counts.items()) + f" = {len(rows)} rows")
    if not apply:
        return
    ws = book.add_worksheet(TAB, rows=len(rows) + 500, cols=len(HEADER))
    stamp = now_text()
    ws.update(range_name="A1", values=[HEADER] + [[*r, stamp, b] for r, b in zip(rows, by)], value_input_option="RAW")
    ws.freeze(rows=1)
    print(f"  written: {len(rows)} rows")


def opt(argv, flag, default=""):
    return argv[argv.index(flag) + 1] if flag in argv else default


def main(argv):
    apply = "--apply" in argv
    if argv and argv[0] == "setup":
        setup(opt(argv, "--from", str(Path(__file__).resolve().parent / "vocab.json")), apply, opt(argv, "--wordings") or None)
    elif argv and argv[0] == "add":
        args = [a for i, a in enumerate(argv[1:], start=1) if not a.startswith("--") and argv[i - 1] != "--by"]
        if len(args) < 2:
            sys.exit('usage: vocab.py add "<kind>" "<key>" ["<meaning>"] ["<extra>"] [--apply]')
        row = (args + ["", ""])[:4]
        if row[0] == "slip wording":
            entry = parse_wording(row[2], row[3])
            print(f"  slip wording {row[1]!r} = {entry}")
        book = open_book(write=apply)
        dup = [r for r in book.worksheet(TAB).get_all_values()[1:] if r[:2] == row[:2] and (r + [""] * 4)[2:4] == row[2:4]]
        if dup:
            sys.exit(f"already in {TAB}: {' | '.join(row)}")
        print(f"[{book.title}] {'APPLY' if apply else 'dry run'}: add {' | '.join(row)}")
        if apply:
            print(f"  written: {TAB} row {append(book, [row], opt(argv, '--by', 'Claude'))}")
    else:
        v = load()
        for name, entries in v.items():
            print(f"{name}: {len(entries)}")
        for key, entries in sorted(v["slip_wordings"].items()):
            for e in entries:
                flags = ", ".join(f for f in (e["sport"] and f"sport={e['sport']}", e["line"] is not None and f"line={e['line']:g}",
                                               e["split"] and "split") if f)
                print(f"  {key} = {e['market']} {e['period']}{'  (' + flags + ')' if flags else ''}")


if __name__ == "__main__":
    main(sys.argv[1:])
