"""Log bet slips (transcribed from screenshots) into the private book. Dry run unless --apply.

Usage: python log_bets.py <slips.json> [--apply]

slips.json: a list of tickets, transcribed exactly from the book's slip screen:
  {"book_slip_no": "88409202869", "placed": "2026-10-07 18:34", "account": "1xbet PHP",
   "stake": 1000, "total_odds": 3.532, "potential": 3531.9, "opening": false,
   "legs": [{"sport": "Basketball", "home": "Aris Thessaloniki", "away": "Burgos",
             "market": "Handicap 1 (-8.5)", "odds": 1.83, "kickoff": "2026-10-08 00:00",
             "status": "Win", "own": false, "tip": null}]}
- placed / kickoff: as the book shows them (book-local time; converted with BOOK_UTC_OFFSET).
- "opening": true for tickets already placed when the book started (8 Oct 2026): adds an
  "Opening balance" ledger line equal to the stake, because the book's cash already excludes it.
- "own": true after Paolo confirms a leg is his own pick (no tip). "tip": "T-0123" forces a link.
Each leg is matched to a tip in the shared sheet by teams + kickoff + market/side; a line that
moved (e.g. Over 170.5 vs tips at 169.5) is linked to the nearest tip line and flagged.
"""
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fixtures import name_score
from log_picks import SHEETS
from parse import Selection
from setup_book import BOOK_KEY

SHEETS_EPOCH = datetime(1899, 12, 30)
BOOK_UTC_OFFSET = {"1xbet": 7}  # 1xbet shows times in UTC+7 on Paolo's account
PHT_OFFSET = 8
BOOK_START = datetime(2026, 10, 8)
SLIP_STATUS = {"win": "Won", "won": "Won", "loss": "Lost", "lost": "Lost", "return": "Void", "refund": "Void",
               "void": "Void", "half win": "Half Won", "half loss": "Half Lost", "half lost": "Half Lost"}
TYPES = {1: "Single", 2: "Double", 3: "Treble"}


class SlipParseError(ValueError):
    pass


def parse_slip_market(text, sport):
    """1xbet's market text -> Selection (same fields as the tips)."""
    x = re.sub(r"\s*\(including overtime\)\s*", " ", text, flags=re.I).strip()
    x = re.sub(r":.*$", "", x) if not x.lower().startswith("1x2") else x  # drop ": Team A - Team B" tails
    low = x.lower()
    half = "1H" if re.search(r"1st half|first half|\b1h\b", low) else "FT"
    m = re.match(r"^1x2:\s*(w1|w2|x)\b", low)
    if m:
        if m[1] == "x":
            raise SlipParseError(f"draw bet {text!r}: no tip market for it")
        side = "Home" if m[1] == "w1" else "Away"
        if sport == "Football":
            return Selection("Handicap", half, side, -0.5)  # a 1X2 win = Asian handicap -0.5
        return Selection("Moneyline", "FT", side)
    num = r"\(([+-]?\d+(?:\.\d+)?)\)"
    m = re.search(rf"(?:asian )?handicap ([12]) {num}", low)
    if m:
        return Selection("Handicap", half, "Home" if m[1] == "1" else "Away", float(m[2]))
    m = re.search(rf"individual total ([12]) (over|under) {num}", low)
    if m:
        return Selection(f"{'Home' if m[1] == '1' else 'Away'} team total", half, m[2].title(), float(m[3]))
    m = re.search(rf"total (over|under) {num}", low)
    if m:
        return Selection("Total", half, m[1].title(), float(m[2]))
    m = re.search(r"both teams to score\W+(yes|no)", low)
    if m:
        return Selection("BTTS", half, m[1].title())
    raise SlipParseError(f"unrecognised slip market {text!r}")


def to_pht(book_time, book):
    t = datetime.strptime(book_time, "%Y-%m-%d %H:%M")
    return t + timedelta(hours=PHT_OFFSET - BOOK_UTC_OFFSET.get(book, PHT_OFFSET))


def serial(dt):
    return (dt - SHEETS_EPOCH).total_seconds() / 86400


@dataclass
class TipRow:
    id: str
    kickoff: datetime | None
    sport: str
    home: str
    away: str
    sel: Selection
    odds: float
    result: str
    match: str


def tip_rows(sheet1_values):
    out = []
    for r in sheet1_values[2:]:
        if not r or not r[0]:
            continue
        r = r + [""] * (20 - len(r))
        ko = datetime.strptime(r[1], "%d %B %Y %H:%M") if r[1] else None
        line = float(r[11]) if r[11] else None
        out.append(TipRow(r[0], ko, r[2], r[6], r[7], Selection(r[8], r[9], r[10], line),
                          float(r[13]), r[15], r[5]))
    return out


def find_tip(leg_sel, sport, home, away, kickoff, tips):
    """(tip, note) for the best tip on the same match and market/side; note says if the line moved."""
    same_match = [t for t in tips if t.sport == sport
                  and min(name_score(home, t.home), name_score(away, t.away)) >= 0.8
                  and (t.kickoff is None or kickoff is None or abs((t.kickoff - kickoff).total_seconds()) <= 36 * 3600)]
    same_market = [t for t in same_match if (t.sel.market, t.sel.period, t.sel.side) ==
                   (leg_sel.market, leg_sel.period, leg_sel.side)]
    exact = [t for t in same_market if t.sel.line == leg_sel.line]
    if exact:
        return exact[0], ""
    if same_market and leg_sel.line is not None:
        t = min(same_market, key=lambda t: abs(t.sel.line - leg_sel.line))
        return t, f"line moved: tip {t.sel.line:g}, taken {leg_sel.line:g}"
    return None, (f"no tip with this market; tips on this match: "
                  + ", ".join(f"{t.id} {t.sel.market} {t.sel.side} {'' if t.sel.line is None else f'{t.sel.line:g}'}"
                              for t in same_match) if same_match else "match not in the tips")


@dataclass
class Plan:
    bets: list = field(default_factory=list)      # Bets rows (input columns only)
    legs: list = field(default_factory=list)      # Legs rows
    ledger: list = field(default_factory=list)    # Ledger rows
    lines: list = field(default_factory=list)     # dry-run report lines
    problems: list = field(default_factory=list)
    checks: list = field(default_factory=list)


def plan(slips, tips, existing_slip_nos, next_n, fx, accounts):
    out = Plan()
    for s in slips:
        no = str(s["book_slip_no"])
        if no in existing_slip_nos:
            out.lines.append(f"skip   slip № {no}: already logged as {existing_slip_nos[no]}")
            continue
        acct = s["account"]
        if acct not in accounts:
            out.problems.append(f"slip № {no}: unknown account {acct!r}")
            continue
        book, cur = accounts[acct]
        sid = f"S-{next_n:04d}"
        next_n += 1
        placed = to_pht(s["placed"], book)
        prod = 1.0
        out.lines.append(f"ticket {sid} (slip № {no}) {acct} {TYPES.get(len(s['legs']), f'{len(s['legs'])}-fold')} "
                         f"stake {s['stake']:,} {cur} @ {s['total_odds']}  placed {placed:%a %d %b %H:%M} PHT")
        for n, leg in enumerate(s["legs"], start=1):
            prod *= leg["odds"]
            ko = to_pht(leg["kickoff"], book) if leg.get("kickoff") else None
            try:
                sel = parse_slip_market(leg["market"], leg["sport"])
            except SlipParseError as e:
                sel = None
                if not leg.get("own"):
                    out.problems.append(f"{sid} leg {n}: {e}")
            tip, note = (None, "own pick") if leg.get("own") else (None, "")
            if sel and not leg.get("own"):
                if leg.get("tip"):
                    tip = next((t for t in tips if t.id == leg["tip"]), None)
                    note = "" if tip else f"tip {leg['tip']} not found"
                else:
                    tip, note = find_tip(sel, leg["sport"], leg["home"], leg["away"], ko, tips)
            if not tip and not leg.get("own"):
                out.problems.append(f"{sid} leg {n} {leg['home']} vs {leg['away']} {leg['market']}: {note}. "
                                    f"Own pick? (set \"own\": true) or name the tip (\"tip\": \"T-....\")")
            if note.startswith("line moved"):
                out.checks.append(f"{sid} leg {n}: {note} ({tip.id})")
            result = SLIP_STATUS.get(str(leg.get("status", "")).lower(), "")
            if tip and tip.result and not result:
                result = tip.result
            drift = f"{leg['odds'] / tip.odds - 1:+.1%}" if tip and not note else ("line moved" if tip else "")
            out.lines.append(f"   leg {n}: {leg['home']} vs {leg['away']} | {leg['market']} @ {leg['odds']}"
                             f"  -> {tip.id + ' ' + str(tip.odds) if tip else ('OWN PICK' if leg.get('own') else '??')}"
                             f"  {drift}  {result or 'open'}")
            out.legs.append([sid, n, tip.id if tip else "", "Yes" if leg.get("own") else "No",
                             f"{leg['home']} vs {leg['away']}", leg["market"], leg["odds"],
                             tip.odds if tip and not note else None, result or None,
                             serial(tip.kickoff) if tip and tip.kickoff else (serial(ko) if ko else None),
                             tip.sel.line if tip and note.startswith("line moved") else None])
        if abs(prod / s["total_odds"] - 1) > 0.005:
            out.problems.append(f"{sid}: legs multiply to {prod:.3f}, slip says {s['total_odds']}: check the transcription")
        if s.get("potential") and abs(s["stake"] * s["total_odds"] / s["potential"] - 1) > 0.002:
            out.problems.append(f"{sid}: stake × odds = {s['stake'] * s['total_odds']:.2f}, slip says {s['potential']}")
        rate = fx.get(cur)
        if rate in (None, ""):
            out.problems.append(f"{sid}: no FX rate for {cur}")
        n_legs = len(s["legs"])
        out.bets.append([sid, serial(placed), acct, TYPES.get(n_legs, f"{n_legs}-fold"), s["stake"], s["total_odds"],
                         "Paolo", "Paolo", s.get("notes", ""), rate, no])
        if s.get("opening"):
            out.ledger.append([serial(BOOK_START), acct, "Opening balance", s["stake"], "Paolo",
                               f"stake of {sid} (slip № {no}), open when the book started"])
            out.lines.append(f"   + ledger: Opening balance {s['stake']:,} {cur} (ticket open at start)")
    return out


def main():
    path = sys.argv[1]
    apply = "--apply" in sys.argv
    from inspect_sheet import READONLY, READWRITE, client
    c = client(READWRITE if apply else READONLY)
    tips = tip_rows(c.open_by_key(SHEETS["live"]).worksheet("Sheet1").get_all_values())
    book = c.open_by_key(BOOK_KEY)
    bets_ws, legs_ws, led_ws = book.worksheet("Bets"), book.worksheet("Legs"), book.worksheet("Ledger")
    bets = bets_ws.get_all_values()
    existing = {r[19]: r[0] for r in bets[1:] if len(r) > 19 and r[19]}
    next_n = 1 + max([int(r[0].split("-")[1]) for r in bets[1:] if r and r[0].startswith("S-")] or [0])
    fx = {r[0]: (float(r[1]) if len(r) > 1 and r[1] else None) for r in book.worksheet("FX").get_all_values()[1:]}
    accounts = {r[0]: (r[1], r[3]) for r in book.worksheet("Accounts").get_all_values()[1:] if r and r[0]}
    slips = json.load(open(path, encoding="utf-8"))
    p = plan(slips, tips, existing, next_n, fx, accounts)

    print(f"[{book.title}] {'APPLY' if apply else 'dry run'}: {len(p.bets)} tickets, {len(p.legs)} legs, "
          f"{len(p.ledger)} ledger lines, {len(p.problems)} problems, {len(p.checks)} checks")
    for l in p.lines:
        print("  " + l)
    for ch in p.checks:
        print(f"  CHECK   {ch}")
    for pr in p.problems:
        print(f"  PROBLEM {pr}")
    if not apply:
        return
    if p.problems:
        sys.exit("not applying: fix the problems above first")

    def first_empty(values):
        return 1 + max((i for i, r in enumerate(values, start=1) if r and r[0]), default=1)

    b0, l0, g0 = first_empty(bets), first_empty(legs_ws.get_all_values()), first_empty(led_ws.get_all_values())
    bu = []
    for k, r in enumerate(p.bets):
        row = b0 + k
        bu += [{"range": f"A{row}:F{row}", "values": [r[0:6]]},
               {"range": f"L{row}:N{row}", "values": [r[6:9]]},
               {"range": f"Q{row}", "values": [[r[9]]]},
               {"range": f"T{row}", "values": [[r[10]]]}]
    lu = []
    for k, r in enumerate(p.legs):
        row = l0 + k
        lu += [{"range": f"A{row}:H{row}", "values": [r[0:8]]},
               {"range": f"J{row}:K{row}", "values": [r[8:10]]},
               {"range": f"N{row}", "values": [[r[10]]]}]
    bets_ws.batch_update(bu, value_input_option="RAW")
    legs_ws.batch_update(lu, value_input_option="RAW")
    if p.ledger:
        led_ws.update(range_name=f"A{g0}", values=p.ledger, value_input_option="RAW")
    print(f"  written: tickets from Bets row {b0}, legs from Legs row {l0}" + (f", ledger from row {g0}" if p.ledger else ""))


if __name__ == "__main__":
    main()
