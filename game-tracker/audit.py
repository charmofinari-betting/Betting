"""Weekly QA audit of the inbox clerk (SPEC-inbox-clerk.md; agreed 22 Oct 2026 for the first 2 weeks).

Usage:
  python audit.py sample [--days 7] [--n 10] [--seed N]   pick N random items the clerk logged in the last
                                                          days; print their sheet fields and the Done
                                                          screenshots that could hold them (read-only)
  python audit.py pull <drive id>...                      download Done screenshots to out/audit/ (read-only)

The audit run then reads each screenshot, compares it field by field with the printed sheet values, and
logs one line: `clerk.py log --by audit --seen <n> --logged "<result>"`.
"""
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from clerk import FIRST, now, parse_time

IDS = re.compile(r"\b([ST])-(\d{4})(?:\s*(?:\.\.|–|-)\s*(?:[ST]-)?(\d{4}))?")
OUT = Path(__file__).resolve().parent / "out" / "audit"
WINDOW = timedelta(hours=26)  # a screenshot is uploaded before the run that logs it (waiting ones up to a day)


def logged_ids(rows, since, by="clerk"):
    """{item id: run time} for IDs in the Logged cell of `by` rows run at or after `since`.
    rows = Clerk tab values from row FIRST. Ranges like "T-1727..T-1738" are expanded."""
    out = {}
    for r in rows:
        r = list(r) + [""] * 4
        at = parse_time(r[0])
        if r[1].strip() != by or not at or at < since:
            continue
        for kind, a, b in IDS.findall(r[3]):
            for n in range(int(a), int(b or a) + 1):
                out.setdefault(f"{kind}-{n:04d}", at)
    return out


def candidates(done, run_at, limit=8):
    """Done files uploaded in the WINDOW before the run, newest first (Drive createdTime is UTC; runs are PHT).
    The screenshot is usually the newest; waiting ones are older."""
    out = []
    for f in done:
        up = datetime.strptime(f["createdTime"][:19], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=8)
        if run_at - WINDOW <= up <= run_at + timedelta(minutes=5):
            out.append(f)
    return sorted(out, key=lambda f: f["createdTime"], reverse=True)[:limit]


def opt(argv, flag, default):
    return type(default)(argv[argv.index(flag) + 1]) if flag in argv else default


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "sample":
        from inbox import DONE, children, session
        from inspect_sheet import client
        from log_picks import SHEETS
        from setup_book import BOOK_KEY
        days, n, seed = opt(argv, "--days", 7), opt(argv, "--n", 10), opt(argv, "--seed", 0)
        c = client()
        book = c.open_by_key(BOOK_KEY)
        items = logged_ids(book.worksheet("Clerk").get_all_values()[FIRST - 1:], now() - timedelta(days=days))
        if not items:
            print(f"nothing logged by the clerk in the last {days} days")
            return
        pick = sorted(random.Random(seed or None).sample(sorted(items), min(n, len(items))))
        print(f"{len(pick)} of {len(items)} clerk-logged items (last {days} days)")
        bets, legs = book.worksheet("Bets").get_all_values(), book.worksheet("Legs").get_all_values()
        tips = c.open_by_key(SHEETS["live"]).worksheet("Sheet1").get_all_values()
        tip_head = tips[1]
        done = children(session(), DONE)
        for i in pick:
            print(f"\n== {i} (logged {items[i]:%d %b %H:%M} PHT)")
            if i.startswith("S-"):
                b = next((r for r in bets if r and r[0] == i), None)
                if not b:
                    print("   not in Bets (undone?)")
                    continue
                print("   " + " | ".join(f"{h}: {v}" for h, v in zip(bets[0], b) if v and h in (
                    "Placed (PHT)", "Account", "Type", "Stake", "Total odds", "Legs", "Placed by", "Book slip №")))
                for l in (r for r in legs if r and r[0] == i):
                    print(f"   leg {l[1]}: {l[4]} | {l[5]} @ {l[6]} | tip {l[2] or '-'} | own {l[3]} | kickoff {l[10]}")
            else:
                t = next((r for r in tips if r and r[0] == i), None)
                print("   " + (" | ".join(f"{h}: {v}" for h, v in zip(tip_head, t) if v and h in (
                    "Kickoff (PHT)", "League", "Match", "Selection (as sent)", "Tip odds")) if t else "not in Sheet1"))
            for f in candidates(done, items[i]):
                print(f"   screenshot? {f['id']}  {f['name']}  uploaded {f['createdTime'][:16]}Z")
    elif cmd == "pull":
        from inbox import API, EXT, session
        s = session()
        OUT.mkdir(parents=True, exist_ok=True)
        for fid in argv[1:]:
            meta = s.get(f"{API}/{fid}", params={"fields": "id,name,mimeType"}).json()
            path = OUT / f"{fid}{EXT.get(meta.get('mimeType'), Path(meta.get('name', '')).suffix or '.bin')}"
            if not path.exists():
                r = s.get(f"{API}/{fid}", params={"alt": "media"})
                r.raise_for_status()
                path.write_bytes(r.content)
            print(f"{fid} {meta.get('name')} -> {path}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
