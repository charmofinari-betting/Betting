"""Inbox clerk bookkeeping (SPEC-inbox-clerk.md): the `Clerk` tab in the private book.

Usage:
  python clerk.py setup [--apply]               add the Clerk tab
  python clerk.py lock "<who>"                  take the lock; exit 2 = busy (another run started < 30 min ago)
  python clerk.py unlock
  python clerk.py waiting                        files waiting for Paolo's answer (Drive ids), with age
  python clerk.py log --by "<who>" --seen N [--logged "S-0270, T-1650"] [--waiting "<file>: <question>; ..."]
                      [--ids id1,id2] [--link <run url>]
  python clerk.py clear <id>...                  answered: drop these ids from the waiting list (done --apply does it too)
  python clerk.py logged <row> "<IDs>"           a follow-up in the same run: add IDs to that run's row
  python clerk.py remind                         ids waiting > 24 h and not yet reminded; marks them reminded

Layout: A1:C1 = Lock | <who> | <since PHT>; row 3 = header; one row per run from row 4.
"""
import sys
from datetime import datetime, timedelta

from vocab import PHT, open_book

TAB = "Clerk"
HEADER = ["Run at (PHT)", "By", "Files seen", "Logged", "Waiting", "Waiting file ids", "Reminded", "Run link"]
FIRST = 4
LOCK_MINUTES = 30
ANSWERED = "answered: "
REMIND_AFTER = timedelta(hours=24)
FMT = "%d %b %Y %H:%M"


def now():
    return datetime.now(PHT).replace(tzinfo=None, second=0, microsecond=0)


def parse_time(s):
    try:
        return datetime.strptime(s.strip(), FMT)
    except ValueError:
        return None


def lock_state(cell_row, at):
    """('free'|'busy'|'stale', who, since) from the A1:C1 values."""
    r = (list(cell_row) + ["", "", ""])[:3]
    who, since = r[1].strip(), parse_time(r[2])
    if not who:
        return "free", "", None
    if since is None or at - since >= timedelta(minutes=LOCK_MINUTES):
        return "stale", who, since
    return "busy", who, since


def waiting(rows):
    """{file id: (sheet row, run at, reminded?)} over the log rows (rows = tab values from row FIRST)."""
    out = {}
    for n, r in enumerate(rows, start=FIRST):
        r = (list(r) + [""] * len(HEADER))[:len(HEADER)]
        for fid in (i.strip() for i in r[5].split(",") if i.strip()):
            out[fid] = (n, parse_time(r[0]), bool(r[6].strip()))
    return out


def due_reminders(rows, at):
    return sorted(fid for fid, (_, run_at, reminded) in waiting(rows).items()
                  if not reminded and run_at and at - run_at >= REMIND_AFTER)


def clear_updates(rows, ids):
    """{sheet row: (new Waiting-file-ids value, new Waiting text or None)} removing ids from every row
    that lists them. A row left with no ids gets its question marked "answered: "."""
    out = {}
    for n, r in enumerate(rows, start=FIRST):
        r = list(r) + [""] * 6
        cur = [i.strip() for i in r[5].split(",") if i.strip()]
        if any(i in ids for i in cur):
            left = ", ".join(i for i in cur if i not in ids)
            text = r[4].strip()
            out[n] = (left, f"{ANSWERED}{text}" if not left and text and not text.startswith(ANSWERED) else None)
    return out


def clear(ids, ws=None):
    """Drop ids from the waiting list (all rows). Called by `inbox.py done --apply` too."""
    if not ids:
        return
    ws = ws or _ws(True)
    ups = clear_updates(ws.get_all_values()[FIRST - 1:], set(ids))
    for row, (val, text) in sorted(ups.items()):
        if text is None:
            ws.update(range_name=f"F{row}", values=[[val]], value_input_option="RAW")
        else:
            ws.update(range_name=f"E{row}:F{row}", values=[[text, val]], value_input_option="RAW")
    print(f"Clerk: cleared from waiting in rows {', '.join(map(str, sorted(ups)))}" if ups else "Clerk: nothing waiting to clear")


def _ws(write=False):
    return open_book(write).worksheet(TAB)


def opt(argv, flag, default=""):
    return argv[argv.index(flag) + 1] if flag in argv else default


def main(argv):
    cmd = argv[0] if argv else ""
    at = now()
    if cmd == "setup":
        apply = "--apply" in argv
        book = open_book(apply)
        if TAB in [w.title for w in book.worksheets()]:
            sys.exit(f"{TAB} already exists")
        print(f"[{book.title}] {'APPLY' if apply else 'dry run'}: add tab {TAB}: lock in A1:C1, header row 3: {' | '.join(HEADER)}")
        if apply:
            ws = book.add_worksheet(TAB, rows=1000, cols=len(HEADER))
            ws.update(range_name="A1", values=[["Lock", "", ""], [], HEADER], value_input_option="RAW")
            ws.freeze(rows=3)
            print("  written")
    elif cmd == "lock":
        who = argv[1] if len(argv) > 1 else "Claude"
        ws = _ws(True)
        state, holder, since = lock_state(ws.get("A1:C1")[0] if ws.get("A1:C1") else [], at)
        if state == "busy":
            print(f"BUSY: {holder} since {since:%H:%M} PHT")
            sys.exit(2)
        ws.update(range_name="B1:C1", values=[[who, at.strftime(FMT)]], value_input_option="RAW")
        print(f"LOCKED by {who}" + (f" (took over a stale lock from {holder})" if state == "stale" else ""))
    elif cmd == "unlock":
        _ws(True).update(range_name="B1:C1", values=[["", ""]], value_input_option="RAW")
        print("UNLOCKED")
    elif cmd == "waiting":
        w = waiting(_ws().get_all_values()[FIRST - 1:])
        if not w:
            print("nothing waiting")
        for fid, (row, run_at, reminded) in sorted(w.items(), key=lambda x: x[1][0]):
            age = f"{(at - run_at).total_seconds() / 3600:.0f} h" if run_at else "?"
            print(f"{fid}  row {row}  waiting {age}{'  (reminded)' if reminded else ''}")
    elif cmd == "log":
        row = [at.strftime(FMT), opt(argv, "--by", "Claude"), opt(argv, "--seen", "0"), opt(argv, "--logged"),
               opt(argv, "--waiting"), opt(argv, "--ids"), "", opt(argv, "--link")]
        ws = _ws(True)
        n = max(FIRST, len(ws.col_values(1)) + 1)
        ws.update(range_name=f"A{n}", values=[row], value_input_option="RAW")
        print(f"logged in {TAB} row {n}")
    elif cmd == "clear":
        clear(set(argv[1:]))
    elif cmd == "logged":
        row, ids = int(argv[1]), argv[2]
        ws = _ws(True)
        cur = ws.acell(f"D{row}").value or ""
        ws.update(range_name=f"D{row}", values=[[", ".join(x for x in (cur, ids) if x)]], value_input_option="RAW")
        print(f"Clerk row {row} Logged: {', '.join(x for x in (cur, ids) if x)}")
    elif cmd == "remind":
        ws = _ws(True)
        rows = ws.get_all_values()[FIRST - 1:]
        due = due_reminders(rows, at)
        w = waiting(rows)
        for row in sorted({w[f][0] for f in due}):
            ws.update(range_name=f"G{row}", values=[[at.strftime(FMT)]], value_input_option="RAW")
        print("REMIND " + ", ".join(due) if due else "no reminders due")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
