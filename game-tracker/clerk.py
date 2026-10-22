"""Inbox clerk bookkeeping (SPEC-inbox-clerk.md): the `Clerk` tab in the private book.

Usage:
  python clerk.py setup [--apply]               add the Clerk tab
  python clerk.py lock "<who>"                  take the lock; exit 2 = busy (another run started < 30 min ago)
  python clerk.py unlock
  python clerk.py waiting                        files waiting for Paolo's answer (Drive ids), with age
  python clerk.py log --by "<who>" --seen N [--logged "S-0270, T-1650"] [--waiting "<file>: <question>; ..."]
                      [--ids id1,id2] [--link <run url>]
  python clerk.py clear <id>...                  answered: drop these ids from the waiting list
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
        ids = set(argv[1:])
        ws = _ws(True)
        rows = ws.get_all_values()[FIRST - 1:]
        hits = {fid: v for fid, v in waiting(rows).items() if fid in ids}
        for fid in ids - set(hits):
            print(f"SKIP {fid}: not waiting")
        for row in sorted({v[0] for v in hits.values()}):
            cur = [i.strip() for i in rows[row - FIRST][5].split(",") if i.strip()]
            ws.update(range_name=f"F{row}", values=[[", ".join(i for i in cur if i not in ids)]], value_input_option="RAW")
            print(f"cleared row {row}: {', '.join(i for i in cur if i in ids)}")
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
