"""Keep the dashboard columns on Bets current. Dry run unless --apply.

  PYTHONIOENCODING=utf-8 ../.venv/Scripts/python bets_refresh.py [--apply]

W Max return       open tickets: ceiling if every open leg wins (positions.summarise), ticket currency
X Max return at    when W was last written (PHT)
Y Settled at (PHT) when the sheet first saw the ticket settled; "before tracking" for tickets settled
                   before this column existed. A ticket that goes back to Open loses it.
log_bets, book_sync and set_leg_results call refresh() after their writes."""
import sys
from datetime import datetime, timedelta, timezone

from positions import summarise

COLS = {"max": 22, "max_at": 23, "settled": 24}
HEADER = ["Max return", "Max return at", "Settled at (PHT)"]
BEFORE = "before tracking"
PHT = timezone(timedelta(hours=8))


def now_pht():
    d = datetime.now(PHT)
    return f"{d.day} {d:%b %Y %H:%M}"


def refresh_plan(bets, legs, now, first_run):
    """bets / legs: sheet rows without the header. -> [(sheet_row, max_return, max_at, settled_at)] for changed rows."""
    bets = [r + [""] * (25 - len(r)) for r in bets]
    tops = {sid: top for sid, _, _, _, top in summarise(bets, legs)[0]}
    out = []
    for i, r in enumerate(bets, start=2):
        if not r[0]:
            continue
        cur = (r[COLS["max"]], r[COLS["max_at"]], r[COLS["settled"]])
        if r[7] == "Open":
            top = f"{tops.get(r[0], 0.0):.2f}"
            new = (top, cur[1] if top == cur[0] and cur[1] else now, "")
        else:
            new = ("", "", cur[2] or (BEFORE if first_run else now))
        if new != cur:
            out.append((i,) + new)
    return out


def refresh(book, apply, now=None, auto=False):
    """auto=True (called from log_bets / book_sync / set_leg_results): never does the first run, which
    needs its own dry run and Paolo's yes."""
    ws = book.worksheet("Bets")
    values = ws.get_all_values()
    head = values[0] + [""] * (25 - len(values[0]))
    first_run = head[22:25] != HEADER
    if auto and first_run:
        return ["skipped: Bets W:Y not set up yet; run bets_refresh.py (dry run, then --apply) first"]
    plan = refresh_plan(values[1:], book.worksheet("Legs").get_all_values()[1:], now or now_pht(), first_run)
    settled = sum(1 for p in plan if p[3])
    lines = [f"Bets W:Y {'APPLY' if apply else 'dry run'}: {len(plan)} rows ({len(plan) - settled} open, {settled} settled)"
             + ("; header W1:Y1 " + ("added" if apply else "would be added") if first_run else "")]
    shown = [p for p in plan if p[3] != BEFORE]
    lines += [f"{values[row - 1][0]} {values[row - 1][2]}: max {m or '-'} | settled {s or '-'}" for row, m, _, s in shown]
    if len(shown) < len(plan):
        lines.append(f"{len(plan) - len(shown)} settled tickets marked '{BEFORE}'")
    if apply:
        updates = [{"range": f"W{row}:Y{row}", "values": [[m, at, s]]} for row, m, at, s in plan]
        if first_run:
            updates.insert(0, {"range": "W1:Y1", "values": [HEADER]})
        if updates:
            if ws.col_count < 25:
                ws.add_cols(25 - ws.col_count)  # Bets was created 22 columns wide
            ws.batch_update(updates, value_input_option="RAW")
    return lines


def main(argv):
    apply = "--apply" in argv
    from inspect_sheet import READONLY, READWRITE, client
    from setup_book import BOOK_KEY
    book = client(READWRITE if apply else READONLY).open_by_key(BOOK_KEY)
    for line in refresh(book, apply):
        print(line)


if __name__ == "__main__":
    main(sys.argv[1:])
