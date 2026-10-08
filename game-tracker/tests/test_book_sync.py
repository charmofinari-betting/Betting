import unittest
from datetime import datetime

from book_sync import factor, parse_score, plan_legs, plan_systems
from log_bets import TipRow
from parse import Selection

KO = datetime(2026, 10, 9, 2, 0)
TIPS = {
    "T-0499": TipRow("T-0499", KO, "Basketball", "Bayern München", "Virtus Bologna", Selection("Total", "FT", "Over", 169.5), 1.83, "Won", "m"),
    "T-0436": TipRow("T-0436", KO, "Football", "Náutico", "Grêmio Novorizontino", Selection("Handicap", "FT", "Away", -0.5), 2.40, "Won", "m"),
    "T-0502": TipRow("T-0502", KO, "Tennis", "Fajing Sun", "Kasidit Samrej", Selection("Moneyline", "FT", "Home"), 1.64, "Won", "m"),
    "T-0601": TipRow("T-0601", KO, "Tennis", "Daniel Rincon", "Pedro Martinez", Selection("Moneyline", "FT", "Home"), 1.83, "", "m"),
}
SCORES = {"T-0499": "90-80", "T-0436": "0-1 (HT 0-0)"}


def leg(slip, tip, match, sel, odds, tip_odds="", result=""):
    return [slip, "1", tip, "No", match, sel, str(odds), str(tip_odds), "", result]


class BookSyncTest(unittest.TestCase):
    def test_parse_score(self):
        self.assertEqual(parse_score("2-1 (HT 1-0)"), ((2, 1), (1, 0)))
        self.assertEqual(parse_score("85-80"), ((85, 80), None))
        self.assertEqual(parse_score(""), (None, None))

    def test_leg_settles_on_its_own_line(self):
        legs = [leg("S-1", "T-0499", "Bayern Munich vs Virtus Granarolo Bologna", "Total Over (170.5): x", 1.93),
                leg("S-2", "T-0499", "Bayern Munich vs Virtus Bologna", "Total Points Over (168.5)", 1.74)]
        updates, _, asks = plan_legs(legs, TIPS, SCORES)
        self.assertEqual(updates, {2: "Lost", 3: "Won"})  # 170 points: 170.5 loses, 168.5 wins

    def test_1x2_w2_settles_from_score(self):
        legs = [leg("S-1", "T-0436", "Clube Nautico Capibaribe vs Novorizontino", "1X2: W2: x", 1.94)]
        self.assertEqual(plan_legs(legs, TIPS, SCORES)[0], {2: "Won"})

    def test_no_score_copies_only_same_line(self):
        legs = [leg("S-1", "T-0502", "Fajing Sun vs Kasidit Samrej", "Match Winner Fajing Sun", 1.42)]
        updates, lines, _ = plan_legs(legs, TIPS, SCORES)
        self.assertEqual(updates, {2: "Won"})
        self.assertIn("copied", lines[0])

    def test_unsettled_tip_waits_and_own_pick_asks(self):
        legs = [leg("S-1", "T-0601", "Daniel Rincon vs Pedro Martinez Portero", "1X2: W1: x", 1.7),
                ["S-1", "2", "", "Yes", "A vs B", "1X2: W1: x", "1.5", "", "", ""]]
        updates, _, asks = plan_legs(legs, TIPS, SCORES)
        self.assertEqual(updates, {})
        self.assertEqual(len(asks), 1)

    def test_already_settled_leg_untouched(self):
        legs = [leg("S-1", "T-0499", "Bayern Munich vs Virtus Bologna", "Total Over (170.5): x", 1.93, result="Won")]
        self.assertEqual(plan_legs(legs, TIPS, SCORES)[0], {})

    def test_system_completes_when_all_legs_settled(self):
        bets = [["S-9", "", "1xbet PHP", "System 2/3", "300", ""]]
        legs = [leg("S-9", "T-1", "a", "x", 2.0, 2.2, "Won"), leg("S-9", "T-2", "b", "x", 3.0, "", "Lost"),
                leg("S-9", "T-3", "c", "x", 1.5)]
        self.assertEqual(plan_systems(bets, legs, {}), [])          # one leg still open
        out = plan_systems(bets, legs, {4: "Void"})                   # last leg settles Void
        self.assertEqual(out[0][:3], (2, "S-9", 100 * 2.0 * 1))     # only the 1-3 double pays
        self.assertAlmostEqual(out[0][3], 220.0)

    def test_factor(self):
        self.assertEqual([factor(r, 2.0) for r in ("Won", "Lost", "Void", "Half Won", "Half Lost")], [2.0, 0, 1, 1.5, 0.5])


if __name__ == "__main__":
    unittest.main()
