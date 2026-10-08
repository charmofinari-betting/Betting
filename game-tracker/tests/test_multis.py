import random
import unittest
from collections import Counter
from datetime import datetime, timedelta
from itertools import combinations

import multis
from log_bets import system_return
from multis import Held, Leg, PlanError, Ticket, Tip

NOW = datetime(2026, 10, 9, 18, 0)
KO = datetime(2026, 10, 10, 20, 0)


def tip(i, match=None, odds=2.0, ko=KO, label="OVER 2.5", result="", league="L"):
    return Tip(f"T-{i:04d}", ko, "Football", league, match or f"Home{i} vs Away{i}", label, odds, result)


def pool(n, per_match=1):
    tips = []
    for m in range(n):
        for r in range(per_match):
            tips.append(tip(m * 10 + r + 1, f"Home{m} vs Away{m}", 1.8 + 0.1 * r + 0.01 * m, label=f"OVER {2.5 + r}"))
    return tips


def build(n_matches, name, legs, total, n_t, seed=1, per_match=1, **kw):
    pos = multis.positions(pool(n_matches, per_match))
    return multis.build_plan(pos, name, legs, kw.pop("sys_k", None), total, n_t, random.Random(seed), **kw)


class TestPlanParsing(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(multis.parse_plan("double:8000"), ("double", 2, None, 8000.0))
        self.assertEqual(multis.parse_plan("treble:6,000"), ("treble", 3, None, 6000.0))
        self.assertEqual(multis.parse_plan("4fold:3000"), ("4fold", 4, None, 3000.0))
        self.assertEqual(multis.parse_plan("system3/5:4000"), ("system3/5", 5, 3, 4000.0))

    def test_bad(self):
        for bad in ("double", "quad:100", "system5/3:100", "double:abc"):
            with self.assertRaises(PlanError):
                multis.parse_plan(bad)


class TestCandidates(unittest.TestCase):
    def test_window_buffer_and_status(self):
        tips = [tip(1), tip(2, ko=NOW + timedelta(minutes=10)), tip(3, result="Won"),
                tip(4, ko=datetime(2026, 10, 11, 13, 0)), tip(5, ko=None), tip(6, ko=datetime(2026, 10, 10, 11, 59))]
        got = {t.id for t in multis.candidates(tips, NOW, "2026-10-10")}
        self.assertEqual(got, {"T-0001", "T-0005"})  # 0002 inside buffer/other day, 0003 settled, 0004/0006 outside 12:00-12:00

    def test_late_night_kickoff_belongs_to_the_evening_before(self):
        t = tip(1, ko=datetime(2026, 10, 11, 0, 30))
        self.assertEqual(len(multis.candidates([t], NOW, "2026-10-10")), 1)
        self.assertEqual(len(multis.candidates([t], NOW, "2026-10-11")), 0)

    def test_filters(self):
        tips = [tip(1, odds=1.5, league="A"), tip(2, odds=2.0, league="B"), tip(3, odds=2.0, league="A")]
        ids = lambda **kw: {t.id for t in multis.candidates(tips, NOW, "2026-10-10", **kw)}
        self.assertEqual(ids(exclude=["T-0003"]), {"T-0001", "T-0002"})
        self.assertEqual(ids(leagues=["a"]), {"T-0001", "T-0003"})
        self.assertEqual(ids(min_odds=1.8), {"T-0002", "T-0003"})
        self.assertEqual(ids(buffer_min=15, include_no_kickoff=False), {"T-0001", "T-0002", "T-0003"})

    def test_ladders_are_one_position(self):
        pos = multis.positions(pool(3, per_match=3))
        self.assertEqual(len(pos), 3)
        self.assertTrue(all(len(v) == 3 for v in pos.values()))


class TestTicketDrawing(unittest.TestCase):
    def check(self, tix, legs):
        for t in tix:
            self.assertEqual(len({l.tip.match for l in t.legs}), legs)  # one leg per match
        self.assertEqual(len({frozenset(t.keys) for t in tix}), len(tix))  # no identical tickets

    def test_one_leg_per_match_and_balanced(self):
        for legs, n_t, m in ((2, 8, 8), (2, 6, 7), (3, 6, 9), (3, 7, 8), (4, 5, 10)):
            tix, unc = build(m, "x", legs, 1000.0 * n_t, n_t)
            self.check(tix, legs)
            counts = Counter(k for t in tix for k in t.keys)
            if n_t * legs >= m:
                self.assertEqual(len(counts), m)
                self.assertLessEqual(max(counts.values()) - min(counts.values()), 1, (legs, n_t, m))
                self.assertEqual(unc, [])

    def test_fewer_slots_than_matches_lists_uncovered(self):
        tix, unc = build(12, "double", 2, 2000, 2)
        self.assertEqual(len({k for t in tix for k in t.keys}), 4)
        self.assertEqual(len(unc), 8)

    def test_no_repeated_pairs_when_room(self):
        tix, _ = build(8, "double", 2, 8000, 8)
        pairs = Counter(frozenset(p) for t in tix for p in combinations(t.keys, 2))
        self.assertEqual(max(pairs.values()), 1)

    def test_avoids_pairs_already_held(self):
        pos = multis.positions(pool(4))
        a, b = "Home0 vs Away0", "Home1 vs Away1"
        held = Held()
        held.pairs[frozenset((a, b))] = 3
        seen_pair = 0
        for seed in range(10):
            tix, _ = multis.build_plan(pos, "double", 2, None, 2000.0, 2, random.Random(seed), held=held)
            seen_pair += any(set(t.keys) == {a, b} for t in tix)
        self.assertEqual(seen_pair, 0)

    def test_too_few_matches(self):
        with self.assertRaises(PlanError):
            build(2, "treble", 3, 3000, 3)

    def test_held_matches_deprioritised_when_slots_short(self):
        pos = multis.positions(pool(6))
        held = Held()
        held.by_match["Home0 vs Away0"] = 5000
        tix, unc = multis.build_plan(pos, "double", 2, None, 2000.0, 2, random.Random(3), held=held)
        self.assertIn("Home0 vs Away0", unc)

    def test_exclude_held_and_max_matches(self):
        pos = multis.positions(pool(6))
        held = Held()
        held.by_match["Home0 vs Away0"] = 1
        tix, _ = multis.build_plan(pos, "double", 2, None, 3000.0, 3, random.Random(3), held=held, exclude_held=True)
        self.assertNotIn("Home0 vs Away0", {k for t in tix for k in t.keys})
        tix, _ = multis.build_plan(pos, "double", 2, None, 3000.0, 3, random.Random(3), max_matches=4)
        self.assertLessEqual(len({k for t in tix for k in t.keys}), 4)

    def test_seed_reproducible(self):
        a, _ = build(8, "treble", 3, 6000, 6, seed=5)
        b, _ = build(8, "treble", 3, 6000, 6, seed=5)
        self.assertEqual([[l.tip.id for l in t.legs] for t in a], [[l.tip.id for l in t.legs] for t in b])
        self.assertEqual([t.stake for t in a], [t.stake for t in b])

    def test_rungs_rotate_and_fixed_modes(self):
        tix, _ = build(2, "double", 2, 4000, 4, per_match=3)
        used = Counter(l.tip.id for t in tix for l in t.legs if l.tip.match == "Home0 vs Away0")
        self.assertEqual(len(used), 3)  # 4 uses over 3 rungs -> all rungs appear
        tix, _ = build(2, "double", 2, 4000, 4, per_match=3, rung="highest")
        self.assertEqual(len({l.tip.id for t in tix for l in t.legs if l.tip.match == "Home0 vs Away0"}), 1)

    def test_system_distinct_matches(self):
        tix, _ = build(7, "system3/5", 5, 4000, 2, sys_k=3)
        for t in tix:
            self.assertTrue(t.is_system)
            self.assertEqual(len({l.tip.match for l in t.legs}), 5)


class TestStakes(unittest.TestCase):
    def test_sum_exact_and_multiples_of_ten(self):
        for total, n in ((8000, 8), (6000, 7), (4010, 3), (1000, 1), (12345, 5)):
            for jitter in (True, False):
                s = multis.split_stakes(total, n, jitter, random.Random(2))
                self.assertEqual(sum(s), total // 10 * 10, (total, n, jitter))
                self.assertTrue(all(x % 10 == 0 and x > 0 for x in s))

    def test_jitter_within_ten_percent(self):
        for seed in range(20):
            s = multis.split_stakes(8000, 8, True, random.Random(seed))
            self.assertTrue(all(900 <= x <= 1100 for x in s), s)
        self.assertGreater(len(set(multis.split_stakes(8000, 8, True, random.Random(1)))), 1)

    def test_no_jitter_equal(self):
        self.assertEqual(set(multis.split_stakes(8000, 8, False, random.Random(1))), {1000.0})

    def test_plan_total_never_exceeded(self):
        tix, _ = build(8, "double", 2, 8000, 8)
        self.assertEqual(sum(t.stake for t in tix), 8000)


class TestMinOddsAndDrift(unittest.TestCase):
    def test_min_odds_rounded_down(self):
        self.assertEqual(multis.min_odds(2.40), 2.28)
        self.assertEqual(multis.min_odds(1.83), 1.73)   # 1.7385 -> 1.73
        self.assertEqual(multis.min_odds(1.85, 0.05), 1.75)

    def test_floor(self):
        self.assertEqual(multis.min_odds(1.90, 0.05, floor=1.85), 1.85)
        self.assertEqual(multis.min_odds(2.40, 0.05, floor=1.85), 2.28)
        self.assertEqual(multis.min_odds(1.70, 0.05, floor=1.85), 1.85)

    def test_parse_seen(self):
        got = multis.parse_seen("T-0412\t1.85\nT-0412 1.90 bet88\n# note\nT-0409   1.40\n")
        self.assertEqual(got, {("T-0412", None): 1.85, ("T-0412", "bet88"): 1.90, ("T-0409", None): 1.40})
        with self.assertRaises(PlanError):
            multis.parse_seen("T-0412")
        with self.assertRaises(PlanError):
            multis.parse_seen("T-0412 abc")

    def test_drift_flag_and_ticket_cost(self):
        legs = [Leg(tip(i, odds=2.0)) for i in (1, 2, 3)]
        t = Ticket("treble", legs, 1000.0)
        multis.apply_seen([t], {("T-0001", None): 1.70, ("T-0002", None): 1.70, ("T-0003", None): 1.70})
        self.assertAlmostEqual(multis.drift(legs[0]), -0.15)
        self.assertTrue(multis.drift_flagged(legs[0], 0.05))
        self.assertFalse(multis.drift_flagged(legs[0], 0.20))
        self.assertAlmostEqual(multis.ticket_drift_cost(t), 1 - 0.85 ** 3)  # 39% of the payout gone
        self.assertAlmostEqual(t.payout(), 8000)
        self.assertAlmostEqual(t.payout(seen=True), 1000 * 1.7 ** 3)

    def test_unchecked_leg_not_flagged(self):
        l = Leg(tip(1))
        self.assertIsNone(multis.drift(l))
        self.assertFalse(multis.drift_flagged(l))

    def test_alternative_rungs(self):
        pos = multis.positions([tip(1, "M", 1.9), tip(2, "M", 2.1, label="OVER 3.0")])
        alts = multis.alt_rungs(Leg(pos["M"][0]), pos, {("T-0002", None): 2.0})
        self.assertEqual(alts[0][0].id, "T-0002")
        self.assertAlmostEqual(alts[0][1], 2.0 / 2.1 - 1)


class TestExposureAndScenarios(unittest.TestCase):
    def test_exposure_counts_and_system_share(self):
        d = Ticket("double", [Leg(tip(1, "A")), Leg(tip(2, "B"))], 1000.0)
        s = Ticket("system3/5", [Leg(tip(i, f"M{i}")) for i in range(3, 8)], 4000.0, sys_k=3)
        per_tip, per_match = multis.exposure([d, s])
        self.assertEqual(per_match["A"], [1, 1000.0])
        self.assertEqual(per_match["M3"], [1, 4000 * 3 / 5])

    def test_double_scenarios_hand_computed(self):
        # two doubles over A,B,C: AB and BC, odds 2.0 each, stake 1000 each -> total stake 2000
        mk = lambda i, m: Leg(tip(i, m, 2.0))
        tix = [Ticket("double", [mk(1, "A"), mk(2, "B")], 1000.0), Ticket("double", [mk(3, "B"), mk(4, "C")], 1000.0)]
        rows = {j: r for j, *r in multis.scenario_table(tix)}
        self.assertEqual(rows[0][:3], [-2000.0, -2000.0, -2000.0])
        self.assertEqual(rows[1][:3], [-2000.0, -2000.0, -2000.0])
        # j=2: AB wins (+4000-2000 = 2000), BC wins (2000), AC wins nothing (-2000): avg 666.67
        self.assertAlmostEqual(rows[2][0], 2000 / 3)
        self.assertEqual(rows[2][1:3], [-2000.0, 2000.0])
        # j=3: both win: 8000 - 2000
        self.assertEqual(rows[3][:3], [6000.0, 6000.0, 6000.0])
        self.assertEqual(multis.break_even(multis.scenario_table(tix)), 2)

    def test_system_3_of_5_needs_four(self):
        legs = [Leg(tip(i, f"M{i}", 2.0)) for i in range(1, 6)]
        t = Ticket("system3/5", legs, 4000.0, sys_k=3)
        rows = {j: (avg, lo, hi) for j, avg, lo, hi, _ in multis.scenario_table([t])}
        self.assertAlmostEqual(rows[3][0], -800.0)   # one winning combination: 400 x 8 = 3200
        self.assertAlmostEqual(rows[4][0], 4 * 3200 - 4000)
        self.assertAlmostEqual(rows[5][0], system_return([2.0] * 5, 3, 4000.0) - 4000)
        self.assertEqual(multis.break_even(multis.scenario_table([t])), 4)

    def test_seen_odds_scenarios_and_sampling_label(self):
        legs = [Leg(tip(i, f"M{i}", 2.0), seen=1.0) for i in range(1, 3)]
        t = Ticket("double", legs, 1000.0)
        rows = multis.scenario_table([t], seen=True)
        self.assertEqual(rows[-1][1], 0.0)  # 1000 x 1.0 x 1.0 - 1000
        big = [Ticket("treble", [Leg(tip(30 * a + i, f"M{3 * a + i}", 2.0)) for i in range(3)], 1000.0)
               for a in range(8)]
        rows = multis.scenario_table(big, samples=500)
        self.assertFalse(all(r[4] for r in rows))  # C(24, 12) > 500 -> sampled
        self.assertTrue(rows[0][4])


class TestBookAndRecord(unittest.TestCase):
    def test_held_from_book(self):
        accounts = [["Account", "Book"], ["1xbet PHP", "1xbet"], ["bet88", "bet88"]]
        bets = [["Slip ID"] + [""] * 21,
                ["S-1", "7 Oct 2026 11:00", "1xbet PHP", "Double", "1,000", "", "", "Open", "", "", "", "", "", "", "",
                 "PHP", "1", "1,000", ""],
                ["S-2", "7 Oct 2026 12:00", "bet88", "System 3/5", "4,000", "", "", "Open", "", "", "", "", "", "", "",
                 "PHP", "1", "4,000", ""],
                ["S-3", "7 Oct 2026 13:00", "bet88", "Double", "500", "", "", "Lost", "", "", "", "", "", "", "",
                 "PHP", "1", "500", "-500"]]
        legs = [["Slip ID", "Leg", "Tip ID", "Own", "Match"],
                ["S-1", "1", "T-1", "No", "A v B"], ["S-1", "2", "T-2", "No", "C v D"],
                ["S-2", "1", "T-1", "No", "A v B"], ["S-2", "2", "T-3", "No", "E v F"], ["S-2", "3", "", "Yes", "G v H"],
                ["S-3", "1", "T-1", "No", "A v B"], ["S-3", "2", "T-3", "No", "E v F"]]
        h = multis.held_from_book(bets, legs, accounts, {"T-1": "A v B", "T-2": "C v D", "T-3": "E v F"},
                                  [[], ["", "", "", "", "", "", "", "", "", "", "", "", "12,345"]])
        self.assertEqual(h.by_match["A v B"], 1000 + 4000 * 3 / 5)
        self.assertEqual(h.tickets_by_match["A v B"], 2)
        self.assertEqual(h.by_match["G v H"], 4000 * 3 / 5)
        self.assertEqual(h.by_book, {"1xbet": 1000, "bet88": 4000})
        self.assertEqual(h.pairs[frozenset(("A v B", "E v F"))], 2)  # S-2 and the lost S-3 both count as history
        self.assertEqual(h.cash, 12345)

    def test_track_record(self):
        tips = [tip(1, odds=2.0, result="Won"), tip(2, odds=2.0, result="Lost"), tip(3, odds=2.0, result="Void"),
                tip(4, odds=1.5, result="Half Won"), tip(5, result="")]
        n, roi, se = multis.track_record(tips)
        self.assertEqual(n, 3)
        self.assertAlmostEqual(roi, (1 - 1 + 0.25) / 3)
        self.assertGreater(se, 0)

    def test_allocate_books_not_built(self):
        with self.assertRaises(NotImplementedError):
            multis.allocate_books([], {"1xbet": 50})
        with self.assertRaises(SystemExit):
            multis.main(["--plan", "double:1000", "--books", "1xbet:50"])

    def test_plan_required(self):
        with self.assertRaises(SystemExit):
            multis.main([])

    def test_tickets_have_empty_book_and_place_by(self):
        tix, _ = build(4, "double", 2, 2000, 2)
        self.assertTrue(all(t.book == "" for t in tix))
        self.assertTrue(all(t.place_by == KO - timedelta(minutes=15) for t in tix))

    def test_report_and_rows_smoke(self):
        tix, unc = build(6, "double", 2, 3000, 3)
        multis.apply_seen(tix, {("T-0001", None): 1.5})
        pos = multis.positions(pool(6))
        ctx = dict(day="2026-10-10", now=NOW, buffer=15, n_candidates=6, n_positions=6, threshold=0.05, floor=1.85,
                   seen_used=True, seen={("T-0001", None): 1.5}, held=Held(), uncovered=[],
                   scenarios=[("double", tix)], notes=[], seed=0, track=(100, 0.09, 0.045))
        text = multis.report(tix, pos, ctx)
        for s in ("MULTIS PLAN", "take at", "your floor", "DRIFT", "IF j OF", "EXPOSURE"):
            self.assertIn(s, text)
        rows = multis.plan_rows(tix, 0.05, None)
        self.assertEqual(len(rows), 1 + 6)


if __name__ == "__main__":
    unittest.main()
