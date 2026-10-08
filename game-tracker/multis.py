"""Multis builder: propose doubles / trebles / system bets from the open tips. Never places bets.

Usage:
  python multis.py --plan double:8000 --plan treble:6000 --plan system3/5:4000 [--day 2026-10-10]
                   [--unit 1000] [--tickets double:6] [--no-jitter] [--seed N] [--seen seen.tsv]
                   [--exclude T-0412,T-0409] [--only-leagues "Ligue 2,J1 League"] [--min-odds 1.5]
                   [--max-matches N] [--exclude-held] [--rung rotate|first|lowest|highest]
                   [--drift-threshold 0.05] [--odds-floor 1.85] [--buffer 15] [--skip-flagged]
                   [--now "2026-10-09 18:00"] [--apply]

Prints a proposal; --apply writes it to a "Multis plan" tab of the PRIVATE sheet (replaced each run).
Reads only: the shared Sheet1 (tips) and the private book (Accounts, Bets, Legs, Balances).
See SPEC-multis-builder.md.
"""
import argparse
import math
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from itertools import combinations
from math import comb, prod

from log_bets import system_return
from log_picks import SHEETS
from setup_book import BOOK_KEY

KICKOFF_FMT = "%d %B %Y %H:%M"
DAY_START_HOUR = 12
RESULTS = ("Won", "Lost", "Half Won", "Half Lost", "Void")
SCENARIO_SAMPLES = 20000
LEGS = {"double": 2, "treble": 3}


class PlanError(Exception):
    pass


# --------------------------------------------------------------------------- data

@dataclass
class Tip:
    id: str
    kickoff: datetime | None
    sport: str
    league: str
    match: str
    label: str       # "Selection (as sent)", e.g. OVER 2.5
    odds: float
    result: str


@dataclass
class Leg:
    tip: Tip
    seen: float | None = None

    @property
    def odds(self):
        return self.tip.odds

    @property
    def odds_seen(self):
        return self.seen if self.seen is not None else self.tip.odds


@dataclass
class Ticket:
    plan: str                 # "double", "treble", "system3/5", ...
    legs: list
    stake: float
    sys_k: int | None = None  # k of a system k/n
    book: str = ""            # not assigned yet (spec §4)
    place_by: datetime | None = None

    @property
    def is_system(self):
        return self.sys_k is not None

    @property
    def keys(self):
        return [l.tip.match for l in self.legs]

    def payout(self, seen=False):
        f = [(l.odds_seen if seen else l.odds) for l in self.legs]
        if self.is_system:
            return system_return(f, self.sys_k, self.stake)
        return round(self.stake * prod(f), 2)

    def total_odds(self, seen=False):
        return prod((l.odds_seen if seen else l.odds) for l in self.legs)


def parse_plan(text):
    """'double:8000' -> ('double', 2, None, 8000.0); 'system3/5:4000' -> ('system3/5', 5, 3, 4000.0)."""
    m = re.fullmatch(r"\s*(double|treble|(\d+)fold|system\s*(\d+)\s*/\s*(\d+))\s*:\s*([\d.,]+)\s*", text, re.I)
    if not m:
        raise PlanError(f"cannot read plan '{text}' (use double:8000, treble:6000, 4fold:3000, system3/5:4000)")
    name = m.group(1).lower().replace(" ", "")
    total = float(m.group(5).replace(",", ""))
    if m.group(3):
        k, n = int(m.group(3)), int(m.group(4))
        if not 1 <= k < n:
            raise PlanError(f"system {k}/{n}: k must be between 1 and n-1")
        return name, n, k, total
    if name in LEGS:
        return name, LEGS[name], None, total
    return name, int(m.group(2)), None, total


def tips_from_sheet(values):
    out = []
    for r in values[2:]:
        if not r or not r[0]:
            continue
        r = r + [""] * (20 - len(r))
        try:
            odds = float(r[13])
        except ValueError:
            continue
        ko = datetime.strptime(r[1], KICKOFF_FMT) if r[1] else None
        out.append(Tip(r[0], ko, r[2], r[4], r[5], r[12], odds, r[15]))
    return out


# --------------------------------------------------------------------------- candidates

def day_window(day):
    start = datetime.strptime(day, "%Y-%m-%d").replace(hour=DAY_START_HOUR)
    return start, start + timedelta(days=1)


def candidates(tips, now, day, buffer_min=15, exclude=(), leagues=None, min_odds=None, include_no_kickoff=True):
    """Open tips whose kickoff is in the betting day and later than now + buffer."""
    lo, hi = day_window(day)
    earliest = now + timedelta(minutes=buffer_min)
    skip = set(exclude)
    keep = {l.lower() for l in leagues} if leagues else None
    out = []
    for t in tips:
        if t.result or t.id in skip:
            continue
        if t.kickoff is None:
            if not include_no_kickoff:
                continue
        elif not (lo <= t.kickoff < hi and t.kickoff > earliest):
            continue
        if keep and t.league.lower() not in keep:
            continue
        if min_odds and t.odds < min_odds:
            continue
        out.append(t)
    return out


def positions(tips):
    """One position per match: {match: [rung tips]} (rungs ordered by tip ID)."""
    pos = defaultdict(list)
    for t in sorted(tips, key=lambda t: t.id):
        pos[t.match].append(t)
    return dict(pos)


def pick_rung(rungs, used, mode="rotate"):
    if mode == "first" or len(rungs) == 1:
        return rungs[0]
    if mode == "lowest":
        return min(rungs, key=lambda t: t.odds)
    if mode == "highest":
        return max(rungs, key=lambda t: t.odds)
    return rungs[used % len(rungs)]


# --------------------------------------------------------------------------- held exposure

def num(s):
    s = str(s).replace(",", "").replace("₱", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


@dataclass
class Held:
    by_match: Counter = field(default_factory=Counter)      # ₱ staked on open tickets
    tickets_by_match: Counter = field(default_factory=Counter)
    by_book: Counter = field(default_factory=Counter)
    pairs: Counter = field(default_factory=Counter)         # frozenset({match, match}) -> tickets (any result)
    cash: float | None = None


def held_from_book(bets, legs, accounts, tip_match, balances=None):
    """bets/legs/accounts: sheet values incl. header. tip_match: {tip id: match}."""
    h = Held()
    book_of = {r[0]: r[1] for r in accounts[1:] if r and r[0]}
    legs_by = defaultdict(list)
    for r in legs[1:]:
        r = r + [""] * (5 - len(r))
        if r[0]:
            legs_by[r[0]].append(tip_match.get(r[2]) or r[4])
    for r in bets[1:]:
        r = r + [""] * (18 - len(r))
        if not r[0]:
            continue
        ms = [m for m in legs_by.get(r[0], []) if m]
        for a, b in combinations(sorted(set(ms)), 2):
            h.pairs[frozenset((a, b))] += 1
        if r[7] != "Open":
            continue
        stake = num(r[17]) or num(r[4])
        share = 1.0
        sm = re.match(r"System (\d+)/(\d+)", r[3])
        if sm:
            share = int(sm.group(1)) / int(sm.group(2))
        for m in set(ms):
            h.by_match[m] += stake * share
            h.tickets_by_match[m] += 1
        h.by_book[book_of.get(r[2], r[2])] += stake
    if balances and len(balances) > 1 and len(balances[1]) > 12:
        h.cash = num(balances[1][12])
    return h


def daily_history(bets, today):
    """(avg daily stake ₱ over the days he bet, yesterday's settled P&L ₱ or None, n days)."""
    per, pnl = defaultdict(float), defaultdict(float)
    for r in bets[1:]:
        r = r + [""] * (19 - len(r))
        if not r[0] or not r[1]:
            continue
        try:
            d = datetime.strptime(r[1], "%d %b %Y %H:%M").date()
        except ValueError:
            continue
        per[d] += num(r[17]) or num(r[4])
        if r[18] != "":
            pnl[d] += num(r[18])
    if not per:
        return 0.0, None, 0
    return sum(per.values()) / len(per), pnl.get(today - timedelta(days=1)), len(per)


def track_record(tips):
    """Flat 1u stake on every settled tip: (n, ROI, standard error)."""
    xs = []
    for t in tips:
        x = {"Won": t.odds - 1, "Lost": -1, "Half Won": (t.odds - 1) / 2, "Half Lost": -0.5}.get(t.result)
        if x is not None:
            xs.append(x)
    n = len(xs)
    if n < 2:
        return n, 0.0, 0.0
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return n, mean, math.sqrt(var / n)


# --------------------------------------------------------------------------- stakes and min odds

def min_odds(tip_odds, threshold=0.05, floor=None):
    m = math.floor(tip_odds * (1 - threshold) * 100 + 1e-9) / 100
    return max(m, floor) if floor else m


def split_stakes(total, n, jitter, rng):
    """n stakes in whole ₱10 summing to total (rounded down to ₱10). Jitter: within ±10% of the mean."""
    units = int(total // 10)
    if n == 1 or not jitter:
        base, extra = divmod(units, n)
        return [(base + (1 if i < extra else 0)) * 10.0 for i in range(n)]
    mean = units / n
    lo, hi = max(1, math.ceil(mean * 0.9)), max(1, math.floor(mean * 1.1))
    lo, hi = min(lo, units // n), max(hi, math.ceil(units / n))
    s = [min(hi, max(lo, round(mean * (1 + rng.uniform(-0.1, 0.1))))) for _ in range(n)]
    diff = units - sum(s)
    order = list(range(n))
    while diff:
        moved = False
        rng.shuffle(order)
        for i in order:
            if diff > 0 and s[i] < hi:
                s[i] += 1; diff -= 1; moved = True
            elif diff < 0 and s[i] > lo:
                s[i] -= 1; diff += 1; moved = True
            if not diff:
                break
        if not moved:
            lo, hi = lo - 1, hi + 1  # cannot happen for sane inputs; keep the sum exact anyway
    return [x * 10.0 for x in s]


# --------------------------------------------------------------------------- ticket drawing

def _pair_cost(plan_pairs, hist, prior):
    c = 0
    for p, n in plan_pairs.items():
        c += 10 * max(0, n + (1 if prior.get(p) else 0) - 1) + 3 * min(hist.get(p, 0), 3)
    return c


def _penalty(tickets, hist, prior):
    pairs = Counter(frozenset(p) for t in tickets for p in combinations(t, 2))
    dup = len(tickets) - len({frozenset(t) for t in tickets})
    return 1000 * dup + _pair_cost(pairs, hist, prior)


def draw_tickets(pool, k, n_tickets, rng, priority, hist=None, prior=None, iters=4000):
    """Choose which positions go in which ticket.
    pool: list of position keys; priority: key -> sort value (lower = used first, e.g. low held exposure).
    Each key appears floor or ceil of the same number of times; no key twice in a ticket."""
    hist, prior = hist or {}, prior or {}
    m = len(pool)
    if m < k:
        raise PlanError(f"needs {k} different matches per ticket but only {m} are available")
    slots = n_tickets * k
    order = sorted(pool, key=lambda p: (priority.get(p, 0), rng.random()))
    base, extra = divmod(slots, m)
    if slots < m:
        count = {p: (1 if i < slots else 0) for i, p in enumerate(order)}
    else:
        count = {p: base + (1 if i < extra else 0) for i, p in enumerate(order)}
    remaining = dict(count)
    tickets = []
    for _ in range(n_tickets):
        chosen = []
        for _ in range(k):
            cand = [p for p in pool if remaining[p] > 0 and p not in chosen]
            top = max(remaining[p] for p in cand)
            cand = [p for p in cand if remaining[p] == top]
            cand.sort(key=lambda p: (sum(10 * (prior.get(frozenset((p, c)), 0) > 0) + hist.get(frozenset((p, c)), 0)
                                         for c in chosen), rng.random()))
            chosen.append(cand[0])
            remaining[cand[0]] -= 1
        tickets.append(chosen)
    best = _penalty(tickets, hist, prior)
    for _ in range(iters if n_tickets > 1 else 0):
        if best == 0:
            break
        x, y = rng.sample(range(n_tickets), 2)
        i, j = rng.randrange(k), rng.randrange(k)
        a, b = tickets[x][i], tickets[y][j]
        if a == b or a in tickets[y] or b in tickets[x]:
            continue
        tickets[x][i], tickets[y][j] = b, a
        cost = _penalty(tickets, hist, prior)
        if cost <= best:
            best = cost
        else:
            tickets[x][i], tickets[y][j] = a, b
    return tickets, [p for p in pool if count.get(p, 0) == 0]


def build_plan(pos, name, n_legs, sys_k, total, n_tickets, rng, *, jitter=True, rung="rotate", held=None,
               exclude_held=False, max_matches=None, rung_used=None, prior=None, buffer_min=15):
    """One plan -> (Tickets, uncovered match keys). rung_used / prior are shared across plans of one run."""
    held = held or Held()
    rung_used = rung_used if rung_used is not None else Counter()
    prior = prior if prior is not None else Counter()
    keys = list(pos)
    if exclude_held:
        keys = [k for k in keys if not held.by_match.get(k)]
    keys.sort(key=lambda k: (held.by_match.get(k, 0), min((t.kickoff or datetime.max) for t in pos[k])))
    if max_matches:
        keys = keys[:max_matches]
    priority = {k: (held.by_match.get(k, 0), rung_used[k]) for k in keys}  # held first, then already used today
    hist = held.pairs
    drawn, uncovered = draw_tickets(keys, n_legs, n_tickets, rng, priority, hist, prior)
    stakes = split_stakes(total, n_tickets, jitter, rng)
    out = []
    for keys_in, stake in zip(drawn, stakes):
        legs = []
        for k in keys_in:
            legs.append(Leg(pick_rung(pos[k], rung_used[k], rung)))
            rung_used[k] += 1
        legs.sort(key=lambda l: (l.tip.kickoff or datetime.max, l.tip.id))
        kos = [l.tip.kickoff for l in legs if l.tip.kickoff]
        place_by = min(kos) - timedelta(minutes=buffer_min) if kos else None
        out.append(Ticket(name, legs, stake, sys_k, "", place_by))
        for p in combinations(keys_in, 2):
            prior[frozenset(p)] += 1
    return out, uncovered


def allocate_books(tickets, shares):
    """Placeholder (spec §4): Paolo picks the book per ticket himself for now."""
    raise NotImplementedError("--books is not built yet: tickets carry an empty 'book' field")


# --------------------------------------------------------------------------- seen odds and drift

def parse_seen(text):
    """Lines 'T-0412<TAB or spaces>1.85[ book]' -> {(tip id, book or None): odds}."""
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts or parts[0].startswith("#") or parts[0].lower() in ("tip", "id"):
            continue
        if len(parts) < 2:
            raise PlanError(f"seen odds: cannot read line '{line}'")
        try:
            out[(parts[0], parts[2] if len(parts) > 2 else None)] = float(parts[1])
        except ValueError:
            raise PlanError(f"seen odds: cannot read line '{line}'")
    return out


def apply_seen(tickets, seen):
    for t in tickets:
        for l in t.legs:
            l.seen = seen.get((l.tip.id, t.book or None)) or seen.get((l.tip.id, None))


def drift(leg):
    return None if leg.seen is None else leg.seen / leg.tip.odds - 1


def drift_flagged(leg, threshold=0.05):
    d = drift(leg)
    return d is not None and d < -threshold


def ticket_drift_cost(ticket):
    """Share of the tip-odds payout lost to drift on the legs with seen odds (0.39 = 39% gone)."""
    ratio = prod(l.odds_seen / l.odds for l in ticket.legs)
    return 1 - ratio


def alt_rungs(leg, pos, seen):
    """Other rungs of the same match, with drift if seen."""
    out = []
    for t in pos.get(leg.tip.match, []):
        if t.id != leg.tip.id:
            s = seen.get((t.id, None))
            out.append((t, None if s is None else s / t.odds - 1))
    return out


# --------------------------------------------------------------------------- exposure and scenarios

def exposure(tickets):
    """Per tip and per match: (tickets, ₱). A system leg carries stake × k/n."""
    per_tip, per_match = defaultdict(lambda: [0, 0.0]), defaultdict(lambda: [0, 0.0])
    for t in tickets:
        share = (t.sys_k / len(t.legs)) if t.is_system else 1.0
        for l in t.legs:
            for d, key in ((per_tip, l.tip.id), (per_match, l.tip.match)):
                d[key][0] += 1
                d[key][1] += t.stake * share
    return dict(per_tip), dict(per_match)


def scenario_table(tickets, seen=False, rng=None, samples=SCENARIO_SAMPLES):
    """If j of the M matches win (a match's rungs win together): rows (j, avg, worst, best, exact)."""
    rng = rng or random.Random(0)
    keys = sorted({k for t in tickets for k in t.keys})
    idx = {k: i for i, k in enumerate(keys)}
    m = len(keys)
    stake = sum(t.stake for t in tickets)
    prep = [([idx[l.tip.match] for l in t.legs], [(l.odds_seen if seen else l.odds) for l in t.legs], t)
            for t in tickets]

    def pnl(win):
        ret = 0.0
        for ids, odds, t in prep:
            if t.is_system:
                ret += system_return([o if i in win else 0 for i, o in zip(ids, odds)], t.sys_k, t.stake)
            elif all(i in win for i in ids):
                ret += t.stake * prod(odds)
        return ret - stake

    rows = []
    for j in range(m + 1):
        if comb(m, j) <= samples:
            subsets, exact = combinations(range(m), j), True
        else:
            subsets, exact = (rng.sample(range(m), j) for _ in range(samples)), False
        vals = [pnl(set(s)) for s in subsets]
        rows.append((j, sum(vals) / len(vals), min(vals), max(vals), exact))
    return rows


def break_even(rows):
    return next((j for j, avg, *_ in rows if avg >= 0), None)


# --------------------------------------------------------------------------- report

def fmt_ko(dt):
    return dt.strftime("%a %d %b %H:%M") if dt else "no kickoff"


def peso(x):
    return f"₱{x:,.0f}"


def report(tickets, pos, ctx):
    L = []
    add = L.append
    thr, floor = ctx["threshold"], ctx["floor"]
    seen_on = ctx["seen_used"]
    total = sum(t.stake for t in tickets)
    n, roi, se = ctx["track"]
    add(f"MULTIS PLAN  betting day {ctx['day']} (12:00 -> 12:00 PHT), now {ctx['now']:%d %b %H:%M} PHT, "
        f"buffer {ctx['buffer']} min")
    add(f"  {ctx['n_candidates']} open tips -> {ctx['n_positions']} matches (one position each); "
        f"{len(tickets)} tickets, total stake {peso(total)}")
    if n >= 2:
        z = roi / se if se else 0
        add(f"  Tip track record, flat 1u on {n} settled tips: ROI {roi:+.1%} ± {se:.1%} (1 s.e.), about {z:.1f} s.e. "
            f"{'above zero' if z >= 0 else 'below zero'}. " + ("Thin sample: treat as a hint, not proof." if z < 3 else ""))
    add("")
    add("TICKETS  (min odds = tip × (1 - %d%%), rounded down%s)" %
        (round(thr * 100), f", never below your floor {floor}" if floor else ""))
    for i, t in enumerate(tickets, 1):
        if t.is_system:
            head = f"#{i} {t.plan.upper()}  {len(t.legs)} legs, {comb(len(t.legs), t.sys_k)} combos of {t.sys_k} at " \
                   f"{peso(t.stake / comb(len(t.legs), t.sys_k))}"
            pays = f"max return {peso(t.payout())}" + (f" (seen {peso(t.payout(True))})" if seen_on else "")
        else:
            head = f"#{i} {t.plan.upper()}  total odds {t.total_odds():.2f}" + \
                   (f" (seen {t.total_odds(True):.2f})" if seen_on else "")
            pays = f"pays if all win {peso(t.payout())}" + (f" (seen {peso(t.payout(True))})" if seen_on else "")
        add(f"{head}  stake {peso(t.stake)}  {pays}")
        add(f"   book: {t.book or '(you choose)'}   place by: {fmt_ko(t.place_by) if t.place_by else 'no kickoff known'}")
        for l in t.legs:
            tip = l.tip
            lo = min_odds(tip.odds, thr, floor)
            line = f"   {tip.id}  {tip.match} | {tip.label}  tip {tip.odds:.2f}  take at {lo:.2f} or better"
            notes = []
            if floor and tip.odds < floor:
                notes.append(f"below your floor {floor}")
            if tip.kickoff is None:
                notes.append("no kickoff")
            if seen_on:
                if l.seen is None:
                    notes.append("tip odds (not checked)")
                else:
                    d = drift(l)
                    notes.append(f"seen {l.seen:.2f} ({d:+.1%})" + (" DRIFT" if drift_flagged(l, thr) else ""))
                    if drift_flagged(l, thr):
                        alts = alt_rungs(l, pos, ctx["seen"])
                        if alts:
                            notes.append("other rungs: " + ", ".join(
                                f"{a.id} {a.label} {a.odds:.2f}" + (f" ({d2:+.1%})" if d2 is not None else "")
                                for a, d2 in alts))
            add(line + ("   [" + "; ".join(notes) + "]" if notes else ""))
        if seen_on and any(l.seen is not None for l in t.legs):
            add(f"   ticket drift cost: {ticket_drift_cost(t):.0%} of the tip-odds payout gone")
    add("")
    per_tip, per_match = exposure(tickets)
    held = ctx["held"]
    counts = [per_match[k][0] for k in per_match]
    add("EXPOSURE")
    add(f"  matches used: {len(per_match)}; tickets per match min-max: {min(counts)}-{max(counts)}")
    for k, (c, s) in sorted(per_match.items(), key=lambda kv: -kv[1][1]):
        h = held.by_match.get(k, 0)
        add(f"  {k:<48} {c} tickets  {peso(s):>9}" + (f"   (already held {peso(h)})" if h else ""))
    add("  by selection: " + ", ".join(f"{k} x{c}" for k, (c, s) in sorted(per_tip.items())))
    if ctx["uncovered"]:
        add(f"  not covered by this plan ({len(ctx['uncovered'])}): " + "; ".join(ctx["uncovered"][:12])
            + (" ..." if len(ctx["uncovered"]) > 12 else ""))
    if held.by_book:
        add("  already held per book (open tickets): " + ", ".join(f"{b} {peso(s)}" for b, s in held.by_book.items()))
    add("")
    add("IF j OF THE M MATCHES WIN -> P&L  (a match's rungs are treated as winning together; "
        "~ = random sample)")
    for label, tix in ctx["scenarios"]:
        for seen in ([False, True] if seen_on else [False]):
            rows = scenario_table(tix, seen, random.Random(ctx["seed"]))
            be = break_even(rows)
            add(f"  {label}{' at seen odds' if seen else ''}: M={rows[-1][0]}, stake {peso(sum(t.stake for t in tix))}, "
                f"break-even at j={be if be is not None else 'never'}")
            add("     j    average      worst       best")
            for j, avg, lo, hi, exact in rows:
                add(f"    {j:>2}  {avg:>9,.0f}  {lo:>9,.0f}  {hi:>9,.0f}{'' if exact else '  ~'}")
    notes = list(ctx["notes"])
    if notes:
        add("")
        add("NOTES")
        for x in notes:
            add("  - " + x)
    return "\n".join(L)


def plan_rows(tickets, thr, floor):
    """Rows for the 'Multis plan' tab."""
    rows = [["#", "Plan", "Book", "Place by", "Stake", "Total odds", "Pays if all win", "Tip ID", "Match",
             "Selection", "Tip odds", "Min odds"]]
    for i, t in enumerate(tickets, 1):
        for n, l in enumerate(t.legs):
            rows.append([i, t.plan, t.book, fmt_ko(t.place_by) if t.place_by else "", t.stake,
                         round(t.total_odds(), 3) if not t.is_system else "", t.payout(),
                         l.tip.id, l.tip.match, l.tip.label, l.tip.odds, min_odds(l.tip.odds, thr, floor)]
                        if n == 0 else
                        ["", "", "", "", "", "", "", l.tip.id, l.tip.match, l.tip.label, l.tip.odds,
                         min_odds(l.tip.odds, thr, floor)])
    return rows


# --------------------------------------------------------------------------- CLI

def pht_now():
    return (datetime.now(timezone.utc) + timedelta(hours=8)).replace(tzinfo=None, second=0, microsecond=0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", action="append", default=[], help="FORMAT:TOTAL_STAKE, repeatable (required)")
    ap.add_argument("--day")
    ap.add_argument("--unit", type=float, default=1000)
    ap.add_argument("--tickets", action="append", default=[], help="FORMAT:N overrides the ticket count")
    ap.add_argument("--no-jitter", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seen")
    ap.add_argument("--exclude", default="")
    ap.add_argument("--only-leagues", default="")
    ap.add_argument("--min-odds", type=float)
    ap.add_argument("--max-matches", type=int)
    ap.add_argument("--exclude-held", action="store_true")
    ap.add_argument("--rung", default="rotate", choices=["rotate", "first", "lowest", "highest"])
    ap.add_argument("--drift-threshold", type=float, default=0.05)
    ap.add_argument("--odds-floor", type=float, default=None)
    ap.add_argument("--buffer", type=int, default=15)
    ap.add_argument("--skip-flagged", action="store_true")
    ap.add_argument("--skip-no-kickoff", action="store_true")
    ap.add_argument("--books", help="not built yet")
    ap.add_argument("--now", help='"YYYY-MM-DD HH:MM" PHT (default: the clock)')
    ap.add_argument("--apply", action="store_true", help="write the 'Multis plan' tab in the private sheet")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.books:
        sys.exit("--books is not built yet: you choose the book per ticket (spec §4).")
    if not a.plan:
        sys.exit("a daily total stake is required: give at least one --plan, e.g. --plan double:8000")

    now = datetime.strptime(a.now, "%Y-%m-%d %H:%M") if a.now else pht_now()
    day = a.day or now.strftime("%Y-%m-%d")
    try:
        plans = [parse_plan(p) for p in a.plan]
        overrides = {}
        for o in a.tickets:
            name, _, cnt = o.partition(":")
            overrides[name.strip().lower().replace(" ", "")] = int(cnt)
    except (PlanError, ValueError) as e:
        sys.exit(str(e))

    from inspect_sheet import READONLY, READWRITE, client
    c = client(READWRITE if a.apply else READONLY)
    tips = tips_from_sheet(c.open_by_key(SHEETS["live"]).worksheet("Sheet1").get_all_values())
    book = c.open_by_key(BOOK_KEY)
    bets, legs, accts, bal = (book.worksheet(n).get_all_values() for n in ("Bets", "Legs", "Accounts", "Balances"))
    tip_match = {t.id: t.match for t in tips}
    held = held_from_book(bets, legs, accts, tip_match, bal)

    seen = {}
    if a.seen:
        seen = parse_seen(open(a.seen, encoding="utf-8").read())
    excluded = [x.strip() for x in a.exclude.split(",") if x.strip()]
    if a.skip_flagged:
        by_id = {t.id: t for t in tips}
        excluded += [i for (i, b), s in seen.items() if i in by_id and s / by_id[i].odds - 1 < -a.drift_threshold]
    cands = candidates(tips, now, day, a.buffer, excluded,
                       [x.strip() for x in a.only_leagues.split(",") if x.strip()] or None,
                       a.min_odds, not a.skip_no_kickoff)
    pos = positions(cands)
    rng = random.Random(a.seed)
    tickets, scenarios, rung_used, prior, notes, uncovered = [], [], Counter(), Counter(), [], None
    for (name, n_legs, sys_k, total), raw in zip(plans, a.plan):
        n_t = overrides.get(name) or (1 if sys_k else max(1, round(total / a.unit)))
        try:
            tix, unc = build_plan(pos, name, n_legs, sys_k, total, n_t, rng, jitter=not a.no_jitter, rung=a.rung,
                             held=held, exclude_held=a.exclude_held, max_matches=a.max_matches,
                             rung_used=rung_used, prior=prior, buffer_min=a.buffer)
        except PlanError as e:
            notes.append(f"plan {raw} skipped: {e}")
            continue
        got = set(unc)
        uncovered = got if uncovered is None else uncovered & got
        tickets += tix
        scenarios.append((raw.split(":")[0], tix))
    if not tickets:
        print("\n".join(["No tickets could be built."] + notes + [f"({len(cands)} open tips in the window)"]))
        return 1
    if len(scenarios) > 1:
        scenarios.append(("whole day", tickets))
    apply_seen(tickets, seen)
    total = sum(t.stake for t in tickets)
    if held.cash is not None and total > held.cash:
        notes.append(f"plan {peso(total)} is more than the cash across all accounts ({peso(held.cash)}).")
    avg, yesterday, ndays = daily_history(bets, now.date())
    if ndays >= 5:
        notes.append(f"planned {peso(total)} vs your average day {peso(avg)} over {ndays} days.")
        if yesterday is not None and yesterday < 0:
            notes.append(f"yesterday's tickets are at {peso(yesterday)}: worth a pause before sizing up (your call).")
    over = [m for m in {k for t in tickets for k in t.keys} if held.by_match.get(m)]
    if over:
        notes.append(f"{len(over)} matches in this plan are already held in open tickets (shown in EXPOSURE).")
    if any(l.tip.kickoff is None for t in tickets for l in t.legs):
        notes.append("some legs have no kickoff yet: check they have not started.")
    ctx = dict(day=day, now=now, buffer=a.buffer, n_candidates=len(cands), n_positions=len(pos),
               threshold=a.drift_threshold, floor=a.odds_floor, seen_used=bool(seen), seen=seen, held=held,
               uncovered=sorted(uncovered or []), scenarios=scenarios, notes=notes, seed=a.seed,
               track=track_record(tips))
    print(report(tickets, pos, ctx))
    rows = plan_rows(tickets, a.drift_threshold, a.odds_floor)
    if a.apply:
        import gspread
        try:
            ws = book.worksheet("Multis plan")
        except gspread.WorksheetNotFound:
            ws = book.add_worksheet("Multis plan", rows=max(200, len(rows) + 20), cols=len(rows[0]))
        ws.clear()
        ws.update(range_name="A1", values=rows, value_input_option="RAW")
        print(f"\nwritten: 'Multis plan' tab, {len(rows) - 1} leg rows")
    else:
        print(f"\ndry run: would write {len(rows) - 1} leg rows to the 'Multis plan' tab of the private sheet "
              f"(use --apply).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
