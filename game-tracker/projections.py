"""Rough projections for open system tickets (read-only).

  PYTHONIOENCODING=utf-8 ../.venv/Scripts/python projections.py

For each open system k/n: the return already locked in by fully-won combinations, the worst case
(every open leg loses), the best case (every open leg wins) and a rough probability-weighted
expectation. Each open leg's win probability is 1/odds scaled down for the bookmaker margin
(default 5%), so the expectation is an estimate from the prices you took, not a model of the games."""
from itertools import combinations, product
from math import prod

from log_bets import BOOK_KEY

MARGIN = 0.05
FACTOR = {"Won": None, "Lost": 0.0, "Void": 1.0}


def system_outcomes(odds, results, k, stake, margin=MARGIN):
    """odds: leg odds; results: 'Won'/'Lost'/'Void'/'' per leg. -> dict(locked, worst, best, expected, open_legs)."""
    open_idx = [i for i, r in enumerate(results) if r not in ("Won", "Lost", "Void")]
    per = stake / len(list(combinations(range(len(odds)), k)))

    def ret(win_flags):
        total = 0.0
        for c in combinations(range(len(odds)), k):
            f = 1.0
            for i in c:
                if i in win_flags:
                    f *= odds[i] if win_flags[i] else 0.0
                else:
                    r = results[i]
                    f *= odds[i] if r == "Won" else 1.0 if r == "Void" else 0.0
            total += per * f
        return total

    p = {i: min(1.0, (1 / odds[i]) * (1 - margin)) for i in open_idx}
    expected = worst = None
    best = 0.0
    locked = ret({i: False for i in open_idx})
    exp = 0.0
    for combo in product([False, True], repeat=len(open_idx)):
        flags = dict(zip(open_idx, combo))
        prob = prod(p[i] if flags[i] else 1 - p[i] for i in open_idx)
        r = ret(flags)
        exp += prob * r
        best = max(best, r)
    return {"locked": round(locked, 2), "worst": round(locked, 2), "best": round(best, 2),
            "expected": round(exp, 2), "open_legs": len(open_idx)}


def main():
    from inspect_sheet import READONLY, client
    from positions import num
    book = client(READONLY).open_by_key(BOOK_KEY)
    bets = book.worksheet("Bets").get_all_values()[1:]
    legs = book.worksheet("Legs").get_all_values()[1:]
    print(f"{'ticket':<8}{'book':<11}{'type':<11}{'stake':>9}{'locked':>10}{'expected':>11}{'best':>11}  open legs")
    tot = [0.0, 0.0, 0.0, 0.0]
    for r in bets:
        if r[7] not in ("Open", "Partly won") or not r[3].startswith("System"):
            continue
        k = int(r[3].split()[1].split("/")[0])
        ls = [l for l in legs if l[0] == r[0]]
        fx = num(r[16]) or 1.0
        o = system_outcomes([num(l[6]) for l in ls], [l[9] for l in ls], k, num(r[4]))
        print(f"{r[0]:<8}{r[2]:<11}{r[3]:<11}{num(r[4]):>9,.0f}{o['locked']:>10,.0f}{o['expected']:>11,.0f}{o['best']:>11,.0f}  {o['open_legs']}")
        for i, v in enumerate((num(r[4]), o["locked"], o["expected"], o["best"])):
            tot[i] += v * fx
    print(f"{'TOTAL':<30}{tot[0]:>9,.0f}{tot[1]:>10,.0f}{tot[2]:>11,.0f}{tot[3]:>11,.0f}")


if __name__ == "__main__":
    main()
