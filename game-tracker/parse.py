"""Turn a selection as the tipster sends it ("AWAY -0.25", "HOME TEAM OVER 1.5 FH")
into structured fields, and derive the detailed market label the Dashboard uses.

parse_selection("HT HOME -4.5")
  -> Selection(market="Handicap", period="1H", side="Home", line=-4.5)
"""
import re
from dataclasses import dataclass

MARKETS = (
    "Handicap", "Total", "Home team total", "Away team total", "Moneyline", "BTTS",
    "Corners", "Cards", "Home team cards", "Away team cards", "Cards handicap", "Corners handicap", "Set handicap", "HT/FT", "Win either half", "Win both halves", "Score in both halves",
    "Both halves over",
)
PERIODS = ("FT", "1H", "2H")
SIDES = ("Home", "Away", "Over", "Under", "Yes", "No")

NUM = r"([+-]?\d+(?:\.\d+)?)"
FH = r"(?:FH|1H|HT)"


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Selection:
    market: str
    period: str
    side: str
    line: float | None = None


# (pattern, builder) — first match wins; patterns run on the trimmed, upper-cased text.
_RULES = [
    (rf"^(?:{FH} )?(HOME|AWAY) {NUM}$",
     lambda m, half: Selection("Handicap", half, m[1].title(), float(m[2]))),
    (rf"^(?:{FH} )?(OVER|UNDER) {NUM}(?: {FH})?$",
     lambda m, half: Selection("Total", half, m[1].title(), float(m[2]))),
    (rf"^(HOME|AWAY) TEAM (OVER|UNDER) {NUM}(?: {FH})?$",
     lambda m, half: Selection(f"{m[1].title()} team total", half, m[2].title(), float(m[3]))),
    (r"^(?:ML (HOME|AWAY)|(HOME|AWAY) ML)$",
     lambda m, half: Selection("Moneyline", "FT", (m[1] or m[2]).title())),
    (r"^BTTS (YES|NO)(?: (1H|2H))?$",
     lambda m, half: Selection("BTTS", m[2] or "FT", m[1].title())),
    (rf"^(CORNERS|CARDS) (OVER|UNDER) {NUM}$",
     lambda m, half: Selection(m[1].title(), half, m[2].title(), float(m[3]))),
    (rf"^CARDS (HOME|AWAY) (OVER|UNDER) {NUM}$",
     lambda m, half: Selection(f"{m[1].title()} team cards", "FT", m[2].title(), float(m[3]))),
    (rf"^CARDS (HOME|AWAY) {NUM}$",
     lambda m, half: Selection("Cards handicap", "FT", m[1].title(), float(m[2]))),
    (rf"^CORNERS (HOME|AWAY) {NUM}$",
     lambda m, half: Selection("Corners handicap", "FT", m[1].title(), float(m[2]))),
    (rf"^SET HANDICAP {NUM} (HOME|AWAY)$",
     lambda m, half: Selection("Set handicap", "FT", m[2].title(), float(m[1]))),
    (r"^HTFT (HOME)/(HOME)$|^HTFT (AWAY)/(AWAY)$",
     lambda m, half: Selection("HT/FT", "FT", (m[1] or m[3]).title())),
    (r"^(HOME|AWAY) TEAM TO WIN EITHER HALF$",
     lambda m, half: Selection("Win either half", "FT", m[1].title())),
    (r"^(HOME|AWAY) TEAM TO WIN BOTH HALVES$",
     lambda m, half: Selection("Win both halves", "FT", m[1].title())),
    (r"^(HOME|AWAY) TEAM TO SCORE IN BOTH HALVES$",
     lambda m, half: Selection("Score in both halves", "FT", m[1].title())),
    (rf"^BOTH HALVES OVER {NUM}$",
     lambda m, half: Selection("Both halves over", "FT", "Over", float(m[1]))),
]


def parse_selection(text: str) -> Selection:
    x = re.sub(r"\s+", " ", text.strip().upper())
    half = "1H" if re.search(rf"(^{FH} | {FH}$)", x) else "FT"
    for pattern, build in _RULES:
        m = re.match(pattern, x)
        if m:
            return build(m, half)
    raise ParseError(f"unrecognised selection: {text!r}")


def market_detail(sel: Selection, sport: str) -> str:
    """The detailed market label shown on the Dashboard (kept identical to the old sheet's
    labels, plus Corners and 1st-half handicaps, which the old sheet lumped into 'Other')."""
    basketball = sport == "Basketball"
    if sel.market == "Handicap":
        if sel.period == "1H":
            return "1st-half spread" if basketball else "1st-half Asian handicap"
        if basketball:
            return "Spread - favourite" if sel.line < 0 else "Spread - underdog"
        if sel.line == 0:
            return "Draw no bet (0.0)"
        return "Asian handicap - giving" if sel.line < 0 else "Asian handicap - getting"
    if sel.market == "Total":
        if sel.period == "1H":
            return f"1st-half {sel.side}"
        return f"{'Points' if basketball else 'Goals'} {sel.side}"
    if sel.market.endswith("team total"):
        return f"Team goals {sel.side}" + (" (1st half)" if sel.period == "1H" else "")
    if sel.market == "BTTS":
        return "BTTS 2nd half" if sel.period == "2H" else f"BTTS {sel.side}"
    if sel.market in ("Corners", "Cards"):
        return f"{sel.market} {sel.side}"
    if sel.market.endswith("team cards"):
        return f"Team cards {sel.side}"
    return sel.market  # Moneyline and the half markets keep their own names
