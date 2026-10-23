"""Slip numbers: each book's format, learned from the Bets tab (column T), and our own keys.

- A number that doesn't fit its book's usual format is a PROBLEM (usually a transcription slip).
- A screenshot with no book name: `guess` says which books' formats the number fits ("bet88?").
- No slip number on the screenshot (msw.ph open bets, cut-off system slips): `own_key` makes one
  from the account, ticket type and placed time, e.g. "msw.ph-pat-system-2-5-1022-2208".
  Own keys are lowercase, so they never look like a book's number.
"""
import re
from collections import Counter, defaultdict

MIN_SLIPS = 5     # fewer numbered slips than this for a book: its format isn't checked yet
MIN_COUNT = 3     # a format must be seen this often ...
MIN_SHARE = 0.10  # ... and on this share of the book's slips, so one mistyped number isn't learned


def shape(no):
    """'2719626337345221478' -> 'D19'; 'XX1-G6F-SRW-CHS' -> 'X3-X3-X3-X3'."""
    no = str(no).strip()
    if no.isdigit():
        return f"D{len(no)}"
    return "-".join(f"X{len(g)}" if g.isalnum() else re.sub(r"\w", "?", g) for g in no.split("-"))


def describe(sh):
    if re.fullmatch(r"D\d+", sh):
        return f"{sh[1:]} digits"
    groups = sh.split("-")
    if len(set(groups)) == 1 and re.fullmatch(r"X\d+", groups[0]):
        return f"{len(groups)} groups of {groups[0][1:]} letters/digits"
    return sh


def is_own_key(no):
    return any(c.islower() for c in str(no))


def learn(bets, accounts):
    """{book: (usual shapes, checked?)} from Bets rows (header excluded) and {account: (book, currency)}.
    Every book's shapes count for guessing; only books with MIN_SLIPS numbered slips are checked."""
    seen = defaultdict(Counter)
    for r in bets:
        if len(r) <= 19 or not r[0]:
            continue
        no, book = r[19].strip(), accounts.get(r[2], (None,))[0]
        if no and book and not is_own_key(no):
            seen[book][shape(no)] += 1
    out = {}
    for book, c in seen.items():
        total = sum(c.values())
        checked = total >= MIN_SLIPS
        out[book] = ({s for s, n in c.items() if n / total >= MIN_SHARE and (n >= MIN_COUNT or not checked)}, checked)
    return out


def guess(no, formats):
    """Books whose usual format fits this number, sorted."""
    s = shape(no)
    return sorted(b for b, (shapes, _) in formats.items() if s in shapes)


def check(no, book, formats):
    """None when fine (or the book isn't checked yet), else the problem text."""
    shapes, checked = formats.get(book, (set(), False))
    if is_own_key(no) or not checked or shape(no) in shapes:
        return None
    usual = " or ".join(describe(s) for s in sorted(shapes))
    fits = [b for b in guess(no, formats) if b != book]
    return (f"slip № {no} ({describe(shape(no))}) doesn't look like a {book} number (usually {usual})"
            + (f"; it fits {', '.join(fits)}" if fits else "") + ": re-read it, or check the account")


def own_key(account, ttype, placed):
    """Our key for a slip with no number: account, type, placed MMDD-HHMM as the slip shows it."""
    slug = lambda t: re.sub(r"[^a-z0-9.]+", "-", t.lower()).strip("-")
    m = re.match(r"\d{4}-(\d\d)-(\d\d)[ T](\d\d):(\d\d)", placed)
    when = f"{m[1]}{m[2]}-{m[3]}{m[4]}" if m else slug(placed)
    return f"{slug(account)}-{slug(ttype)}-{when}"
