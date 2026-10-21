"""Settle a selection from the score. Pure logic, no I/O.

settle(sel, sport, ft, ht) -> "Won" / "Lost" / "Half Won" / "Half Lost" / "Void", or None when it
can't be settled from a score (corners, cards) and needs Paolo.
ft, ht: (home, away) goals/points. Football ft = 90 minutes (extra time and penalties don't
count); basketball ft = final including overtime, ht = Q1 + Q2.
Quarter lines (-0.25, 2.75, ...) are split into two half-stakes on the neighbouring lines.
"""
from parse import Selection

WIN, PUSH, LOSE = 1, 0, -1


def _one(diff):
    return WIN if diff > 0 else LOSE if diff < 0 else PUSH


def _lines(line):
    """A quarter line splits into two halves; anything else is one line."""
    if round(line * 4) % 2:  # .25 or .75
        return [line - 0.25, line + 0.25]
    return [line]


def _combine(parts):
    if len(parts) == 1:
        return {WIN: "Won", LOSE: "Lost", PUSH: "Void"}[parts[0]]
    s = sorted(parts)
    if s == [WIN, WIN]:
        return "Won"
    if s == [LOSE, LOSE]:
        return "Lost"
    if s == [PUSH, WIN]:
        return "Half Won"
    if s == [LOSE, PUSH]:
        return "Half Lost"
    raise ValueError(f"impossible split {parts}")  # a quarter line can't win one half and lose the other


def _against_line(value, line, side_sign):
    """Asian-style settlement of value vs line; side_sign +1 for Over/handicap, -1 for Under."""
    return _combine([_one(side_sign * (value - l)) for l in _lines(line)])


def settle(sel: Selection, sport: str, ft, ht=None):
    if sel.market in ("Corners", "Cards", "Home team cards", "Away team cards", "Cards handicap", "Corners handicap", "Set handicap", "1st set winner"):
        return None
    if sel.period == "1H" or (sel.market == "BTTS" and sel.period == "2H"):
        if ht is None or None in ht:
            return None
    h, a = ft
    if sel.market == "HT/FT":  # leads at half-time and wins the match (same team both times)
        if ht is None or None in ht:
            return None
        mine, theirs = (0, 1) if sel.side == "Home" else (1, 0)
        return "Won" if ht[mine] > ht[theirs] and ft[mine] > ft[theirs] else "Lost"
    second = (h - ht[0], a - ht[1]) if ht and None not in ht else None
    if sel.period == "2H" and second is None:
        return None
    sh, sa = {"FT": (h, a), "1H": ht, "2H": second}[sel.period]

    m = sel.market
    if m == "Handicap":
        mine, theirs = (sh, sa) if sel.side == "Home" else (sa, sh)
        return _combine([_one(mine - theirs + l) for l in _lines(sel.line)])
    if m == "Total":
        return _against_line(sh + sa, sel.line, +1 if sel.side == "Over" else -1)
    if m in ("Home team total", "Away team total"):
        goals = sh if m.startswith("Home") else sa
        return _against_line(goals, sel.line, +1 if sel.side == "Over" else -1)
    if m == "Moneyline":
        mine, theirs = (sh, sa) if sel.side == "Home" else (sa, sh)
        return "Won" if mine > theirs else "Lost"  # a football draw loses a moneyline (1X2) bet
    if m == "BTTS":
        both = sh > 0 and sa > 0
        return "Won" if both == (sel.side == "Yes") else "Lost"

    # Half markets need both halves.
    if second is None:
        return None
    halves = [ht, second]
    team = 0 if sel.side == "Home" else 1
    if m == "Win either half":
        return "Won" if any(x[team] > x[1 - team] for x in halves) else "Lost"
    if m == "Win both halves":
        return "Won" if all(x[team] > x[1 - team] for x in halves) else "Lost"
    if m == "Score in both halves":
        return "Won" if all(x[team] > 0 for x in halves) else "Lost"
    if m == "Both halves over":
        return "Won" if all(sum(x) > sel.line for x in halves) else "Lost"
    return None
