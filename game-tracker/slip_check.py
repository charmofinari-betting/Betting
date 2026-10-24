"""Check a transcribed slip leg's meaning ("sel") against the slip text and the word list.

Claude writes what the leg means: "sel": {"market": "Total", "period": "FT", "side": "Under", "line": 2.75}.
The book's wording is reduced to a key that doesn't depend on the match (wording_of):
  "Over/Under - Regular Time: Under 2.5,3"  ->  "~/~ - regular time: ~ #,#"
  "Handicap 1 (-8.5): Aris - Burgos (Including Overtime)"  ->  "handicap # (#): @ (including overtime)"
(team names -> @, numbers -> #, over/under/yes/no -> ~, W1/W2 -> w~). The word list (Vocab tab,
kind "slip wording", key "<book>: <that key>") says which market and period the wording means.
check_leg() returns the problems; an unknown wording is one ("NEW WORDING"), asked once, then added.
"""
import re
import unicodedata

from parse import MARKETS, PERIODS, Selection

# Words that make up market names; any other word is part of a team/player name.
WORDS = set("""total totals points point goals goal corners corner cards card team teams wins win winner handicap
asian sets set match result double chance draw or both to score regular time first second half live betting spread
moneyline ft ht incl including overtime head correct individual x w and of bet o u exact odd even period quarter
rebounds assists innings game games margin""".split())
SUFFIXES = {"st", "nd", "rd", "th", "up"}  # only after a number: "1st set", "(2UP)"
LINE_SIDES = {"Over": "Under", "Under": "Over", "Yes": "No", "No": "Yes"}
NO_LINE = {"Moneyline", "BTTS", "HT/FT", "Win either half", "Win both halves", "Score in both halves"}
HOME_AWAY = {"Handicap", "Moneyline", "Cards handicap", "Corners handicap", "Set handicap", "HT/FT",
             "Win either half", "Win both halves", "Score in both halves"}
NUM = r"[+-]?\d+(?:\.\d+)?"


def fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def _strip_score(text):
    return re.sub(r"^\s*\[\d+:\d+\]\s*", "", text)  # Solaire live bets start with the score at bet time


def wording_of(text):
    """The book's wording with the match-specific parts masked (see module doc)."""
    x = fold(_strip_score(text))
    x = re.sub(r"\b(over|under|yes|no)\b", "~", x)
    x = re.sub(r"\bw[12x]\b", "w~", x)
    x = re.sub(NUM, "#", x)
    x = re.sub(r"(#?)([a-z]+(?:['.][a-z]+)*\.?)",
               lambda m: m[0] if m[2].rstrip(".") in WORDS or (m[1] and m[2] in SUFFIXES) else m[1] + "@", x)
    for _ in range(3):
        x = re.sub(r"@(?:[\s.,'&/()#-]*@)+", "@", x)
        x = re.sub(r"@ ?\(@\)", "@", x)
    if x.count(")") > x.count("("):
        x = x.replace("@)", "@", 1)
    return " ".join(x.split())


def _numbers(text):
    """Numbers on the slip text as written: (value, had an explicit sign)."""
    return [(float(n), n[0] in "+-") for n in re.findall(NUM, _strip_score(text))]


def _line_shown(line, text):
    for n, signed in _numbers(text):
        if n == line or (not signed and line >= 0 and n == abs(line)):
            return True
    return False


def _split_line(text):
    m = re.search(rf"({NUM})\s*,\s*({NUM})", _strip_score(text))
    return (float(m[1]) + float(m[2])) / 2 if m else None


def _names(team):
    return {t for t in re.findall(r"[a-z]{3,}", fold(team)) if t not in WORDS}


def _side_from_text(text, home, away):
    """'Home'/'Away' when the text names only one team or says 1/2 (W1, Handicap 1, Team 2 Wins), else None."""
    h, a = _names(home), _names(away)
    h, a = h - a, a - h
    words = set(re.findall(r"[a-z]{3,}", fold(_strip_score(text))))
    in_h, in_a = bool(h & words), bool(a & words)
    if in_h != in_a:
        return "Home" if in_h else "Away"
    m = re.search(r"\b(?:w|handicap:? |team )([12])\b", fold(text)) or \
        re.search(r"double chance:? (?:([12])x|x([12]))\b", fold(text))
    return ("Home" if "1" in m.groups() else "Away") if m else None


def to_selection(sel):
    line = sel.get("line")
    return Selection(sel["market"], sel["period"], sel["side"], None if line is None else float(line))


def shape_problems(s):
    out = []
    if s.market not in MARKETS:
        out.append(f"market {s.market!r} is not one of {', '.join(MARKETS)}")
    if s.period not in PERIODS:
        out.append(f"period {s.period!r} is not one of {', '.join(PERIODS)}")
    wants = ("Home", "Away") if s.market in HOME_AWAY else ("Yes", "No") if s.market == "BTTS" else ("Over", "Under")
    if s.side not in wants:
        out.append(f"side {s.side!r} doesn't fit {s.market} (want {'/'.join(wants)})")
    if s.market in NO_LINE and s.line is not None:
        out.append(f"{s.market} has no line, got {s.line:g}")
    if s.market not in NO_LINE and s.line is None:
        out.append(f"{s.market} needs a line")
    if s.line is not None and (s.line * 4) % 1:
        out.append(f"line {s.line:g} is not in steps of 0.25")
    return out


def _mask_numbered_teams(text, home, away):
    """Team names with digits in them (FA 2000, Jong PSV U21) blanked out, so their numbers aren't read as lines."""
    for name in (home, away):
        if name and re.search(r"\d", name):
            text = re.sub(re.escape(name), "Xteamx", text, flags=re.I)
    return text


def find_wording(book, text, sport, wordings):
    """(key, entry or None): the word-list entry for this book's wording, sport-specific first."""
    from vocab import wording_key
    key = wording_key(book, wording_of(text))
    entries = wordings.get(key, [])
    entry = next((e for e in entries if e["sport"] == sport), None) or next((e for e in entries if not e["sport"]), None)
    return key, entry


def check_leg(leg, book, wordings, old_parser=None):
    """(Selection or None, [problems]) for one transcribed leg. old_parser(text, sport, home, away) is the
    second opinion during the changeover; it may raise when it can't read the text."""
    text, sport, home, away = leg["market"], leg["sport"], leg.get("home", ""), leg.get("away", "")
    if not leg.get("sel"):
        return None, ['no "sel" transcribed (market, period, side, line)']
    s = to_selection(leg["sel"])
    probs = shape_problems(s)
    if probs:
        return None, probs
    mtext = _mask_numbered_teams(text, home, away)
    key, entry = find_wording(book, mtext, sport, wordings)
    team_market = entry and entry["market"] in ("Team total", "Team cards")
    if entry is None:
        probs.append(f"NEW WORDING {key!r} ({sport}): does it mean {s.market} {s.period}? "
                     f"Add it with vocab.py add \"slip wording\" once Paolo confirms")
    else:
        if team_market:
            named = _side_from_text(text, home, away)
            want = {f"Home {entry['market'].lower()}", f"Away {entry['market'].lower()}"}
            if s.market not in want or s.period != entry["period"]:
                probs.append(f"word list says {key!r} = {entry['market']} {entry['period']} (Home/Away), "
                             f"sel says {s.market} {s.period}")
            elif named and not s.market.startswith(named):
                probs.append(f"sel says {s.market} but the text names the {named.lower()} team")
        elif (entry["market"], entry["period"]) != (s.market, s.period):
            probs.append(f"word list says {key!r} = {entry['market']} {entry['period']}, sel says {s.market} {s.period}")
        if entry["line"] is not None and s.line != entry["line"]:
            probs.append(f"word list fixes the line of {key!r} at {entry['line']:g}, sel says {s.line}")
    if s.side in LINE_SIDES:
        words = re.findall(r"[a-z]+", fold(text))
        if words.count(s.side.lower()) <= words.count(LINE_SIDES[s.side].lower()):
            probs.append(f"side {s.side} but the text doesn't say {s.side}")
    else:
        named = _side_from_text(text, home, away)
        if named and named != s.side:
            probs.append(f"side {s.side} but the text points to {named}")
    if s.line is not None and not (entry and entry["line"] is not None):
        split = _split_line(mtext)
        if split is not None:
            if s.line != split:
                probs.append(f"split line on the slip = {split:g}, sel says {s.line:g}")
        elif not _line_shown(s.line, mtext):
            probs.append(f"line {s.line:g} is not on the slip text")
    if old_parser:
        try:
            old = old_parser(text, sport, home, away)
        except ValueError:
            old = None
        if old and old != s:
            probs.append(f"old parser reads {old.market} {old.period} {old.side}"
                         f"{'' if old.line is None else f' {old.line:g}'}, sel says {s.market} {s.period} {s.side}"
                         f"{'' if s.line is None else f' {s.line:g}'}")
    return s, probs
