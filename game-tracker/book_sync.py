"""Settle the private book's open legs from the shared sheet's tips. Dry run unless --apply.

Usage: python book_sync.py [--apply]

For each leg with a Tip ID and no result:
- if the tip has a Score, the leg is settled from that score with the leg's OWN market and line
  (a slip's line can differ from the tip's, e.g. Over 170.5 vs a tip at 169.5);
- if the tip has a result but no score (tennis, corners...), the result is copied only when the
  leg's line equals the tip's; otherwise it's listed for Paolo.
Own picks (no Tip ID) are listed for Paolo.
System tickets: once every leg has a result, their return (and return at tip odds) is computed
and written to Bets U/V.
"""
import re
import sys

from log_bets import SlipParseError, parse_slip_market, system_return, tip_rows
from log_picks import SHEETS
from settle import settle
from setup_book import BOOK_KEY

LEG = {"slip": 0, "tip": 2, "own": 3, "match": 4, "selection": 5, "odds": 6, "tip_odds": 7, "result": 9, "tip_line": 13}


def factor(result, odds):
    return {"Won": odds, "Lost": 0.0, "Void": 1.0, "Half Won": (odds + 1) / 2, "Half Lost": 0.5}[result]


def parse_score(text):
    """'2-1 (HT 1-0)' -> ((2, 1), (1, 0)); '85-80' -> ((85, 80), None)."""
    m = re.match(r"^\s*(\d+)-(\d+)(?:\s*\(HT (\d+)-(\d+)\))?", text or "")
    if not m:
        return None, None
    ft = (int(m[1]), int(m[2]))
    ht = (int(m[3]), int(m[4])) if m[3] is not None else None
    return ft, ht


def plan_legs(legs, tips_by_id, tip_scores):
    """legs: Legs rows (from row 2). Returns (updates {row: result}, report lines, asks)."""
    updates, lines, asks = {}, [], []
    for i, r in enumerate(legs, start=2):
        r = r + [""] * (14 - len(r))
        if not r[LEG["slip"]] or r[LEG["result"]]:
            continue
        label = f"{r[LEG['slip']]} {r[LEG['match']]} | {r[LEG['selection']]}"
        tid = r[LEG["tip"]]
        if not tid:
            asks.append(f"{label}: own pick, result needed")
            continue
        tip = tips_by_id.get(tid)
        if tip is None:
            asks.append(f"{label}: tip {tid} not found in the shared sheet")
            continue
        score = tip_scores.get(tid, "")
        if not tip.result and not score:
            continue  # not played / not settled yet
        home, _, away = r[LEG["match"]].partition(" vs ")
        try:
            sel = parse_slip_market(r[LEG["selection"]], tip.sport, home, away)
        except SlipParseError as e:
            asks.append(f"{label}: {e}")
            continue
        ft, ht = parse_score(score)
        res = settle(sel, tip.sport, ft, ht) if ft else None
        how = f"from score {score}"
        if res is None:
            if sel.line == tip.sel.line and tip.result:
                res, how = tip.result, f"copied from {tid} (same line, no score)"
            else:
                asks.append(f"{label}: tip {tid} is {tip.result or 'unsettled'} but the leg can't be settled "
                            f"from {'score ' + score if score else 'a score'}; result needed")
                continue
        updates[i] = res
        lines.append(f"{label} -> {res}  ({how})")
    return updates, lines, asks


def plan_systems(bets, legs, leg_results):
    """System tickets whose legs all have a result: (row, return, return at tip odds)."""
    by_slip = {}
    for i, r in enumerate(legs, start=2):
        r = r + [""] * (14 - len(r))
        if r[LEG["slip"]]:
            res = leg_results.get(i) or r[LEG["result"]]
            odds = float(r[LEG["odds"]].replace(",", ""))
            tip_odds = float(r[LEG["tip_odds"]].replace(",", "")) if r[LEG["tip_odds"]] else odds
            by_slip.setdefault(r[LEG["slip"]], []).append((res, odds, tip_odds))
    out = []
    for i, b in enumerate(bets, start=2):
        b = b + [""] * (22 - len(b))
        m = re.match(r"^System (\d+)/(\d+)$", b[3])
        if not b[0] or not m or b[20]:
            continue
        legs_ = by_slip.get(b[0], [])
        if not legs_ or any(not res for res, _, _ in legs_):
            continue
        k, stake = int(m[1]), float(b[4].replace(",", ""))
        ret = system_return([factor(res, o) for res, o, _ in legs_], k, stake)
        at_tip = system_return([factor(res, t) for res, _, t in legs_], k, stake)
        out.append((i, b[0], ret, at_tip))
    return out


def main():
    apply = "--apply" in sys.argv
    from inspect_sheet import READONLY, READWRITE, client
    c = client(READWRITE if apply else READONLY)
    shared = c.open_by_key(SHEETS["live"]).worksheet("Sheet1").get_all_values()
    tips = {t.id: t for t in tip_rows(shared)}
    scores = {r[0]: r[14] for r in shared[2:] if r and r[0] and len(r) > 14 and r[14]}
    book = c.open_by_key(BOOK_KEY)
    legs_ws, bets_ws = book.worksheet("Legs"), book.worksheet("Bets")
    legs = legs_ws.get_all_values()[1:]
    bets = bets_ws.get_all_values()[1:]

    updates, lines, asks = plan_legs(legs, tips, scores)
    systems = plan_systems(bets, legs, updates)
    print(f"[{book.title}] book sync {'APPLY' if apply else 'dry run'}: {len(updates)} legs to settle, "
          f"{len(systems)} system tickets complete, {len(asks)} need Paolo")
    for l in lines:
        print(f"  leg     {l}")
    for _, sid, ret, at_tip in systems:
        print(f"  system  {sid}: return {ret:,.2f} (at tip odds {at_tip:,.2f})")
    for a in asks:
        print(f"  ASK     {a}")
    if not apply:
        return
    if updates:
        legs_ws.batch_update([{"range": f"J{row}", "values": [[res]]} for row, res in updates.items()],
                             value_input_option="RAW")
    if systems:
        bets_ws.batch_update([{"range": f"U{row}:V{row}", "values": [[ret, at_tip]]} for row, _, ret, at_tip in systems],
                             value_input_option="RAW")
    print(f"  written: {len(updates)} leg results, {len(systems)} system returns")
    from bets_refresh import refresh
    for line in refresh(book, apply=True, auto=True):
        print("  refresh " + line)


if __name__ == "__main__":
    main()
