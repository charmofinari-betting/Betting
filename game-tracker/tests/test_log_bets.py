import unittest
from datetime import datetime

from log_bets import SlipParseError, TipRow, find_tip, parse_slip_market, plan, to_pht
from parse import Selection


class SlipMarketTest(unittest.TestCase):
    def test_1xbet_markets(self):
        cases = [
            ("1X2: W2: Botosani - UTA Arad", "Football", Selection("Handicap", "FT", "Away", -0.5)),
            ("1X2: W1: Daniel Rincon - Pedro Martinez Portero", "Tennis", Selection("Moneyline", "FT", "Home")),
            ("Handicap 1 (-8.5): Aris Thessaloniki - Burgos (Including Overtime)", "Basketball",
             Selection("Handicap", "FT", "Home", -8.5)),
            ("Asian Handicap 2 (+0.25): A - B", "Football", Selection("Handicap", "FT", "Away", 0.25)),
            ("Total Over (170.5): Bayern Munich - Virtus (Including Overtime)", "Basketball", Selection("Total", "FT", "Over", 170.5)),
            ("Total Under (2.75): A - B", "Football", Selection("Total", "FT", "Under", 2.75)),
            ("1st Half Total Over (1.5): A - B", "Football", Selection("Total", "1H", "Over", 1.5)),
            ("Individual Total 1 Over (1.5): A - B", "Football", Selection("Home team total", "FT", "Over", 1.5)),
            ("Both Teams To Score - Yes: A - B", "Football", Selection("BTTS", "FT", "Yes")),
        ]
        for text, sport, want in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_slip_market(text, sport), want)

    def test_unknown_and_draw_raise(self):
        for text in ("1X2: X: A - B", "Double Chance 1X: A - B", "Correct Score 2-1"):
            with self.subTest(text=text), self.assertRaises(SlipParseError):
                parse_slip_market(text, "Football")

    def test_1xbet_time_to_pht(self):
        self.assertEqual(to_pht("2026-10-08 00:00", "1xbet"), datetime(2026, 10, 8, 1, 0))


KO = datetime(2026, 10, 9, 2, 0)
TIPS = [TipRow("T-0497", KO, "Basketball", "Bayern München", "Virtus Bologna", Selection("Total", "FT", "Over", 168.5), 1.85, "", "m"),
        TipRow("T-0499", KO, "Basketball", "Bayern München", "Virtus Bologna", Selection("Total", "FT", "Over", 169.5), 1.83, "", "m"),
        TipRow("T-0436", KO, "Football", "Náutico", "Grêmio Novorizontino", Selection("Handicap", "FT", "Away", -0.5), 2.40, "", "m"),
        TipRow("T-0577", KO, "Football", "Náutico", "Grêmio Novorizontino", Selection("Handicap", "FT", "Away", 0.0), 1.87, "", "m")]


class FindTipTest(unittest.TestCase):
    def test_exact_line(self):
        t, note = find_tip(Selection("Total", "FT", "Over", 169.5), "Basketball", "Bayern Munich", "Virtus Granarolo Bologna", KO, TIPS)
        self.assertEqual((t.id, note), ("T-0499", ""))

    def test_line_moved_links_nearest(self):
        t, note = find_tip(Selection("Total", "FT", "Over", 170.5), "Basketball", "Bayern Munich", "Virtus Granarolo Bologna", KO, TIPS)
        self.assertEqual(t.id, "T-0499")
        self.assertIn("line moved", note)

    def test_w2_links_ah_minus_half_not_dnb(self):
        t, note = find_tip(Selection("Handicap", "FT", "Away", -0.5), "Football", "Clube Nautico Capibaribe", "Novorizontino", KO, TIPS)
        self.assertEqual((t.id, note), ("T-0436", ""))

    def test_other_match_or_far_kickoff(self):
        self.assertIsNone(find_tip(Selection("Total", "FT", "Over", 169.5), "Basketball", "Real Madrid", "Virtus Bologna", KO, TIPS)[0])
        far = datetime(2026, 10, 20)
        self.assertIsNone(find_tip(Selection("Total", "FT", "Over", 169.5), "Basketball", "Bayern Munich", "Virtus Bologna", far, TIPS)[0])


SLIP = {"book_slip_no": "1", "placed": "2026-10-07 18:34", "account": "1xbet PHP", "stake": 1000, "total_odds": 3.532,
        "potential": 3531.9, "opening": True, "legs": [
            {"sport": "Football", "home": "Clube Nautico Capibaribe", "away": "Novorizontino", "market": "1X2: W2: x", "odds": 1.83, "kickoff": "2026-10-09 01:00"},
            {"sport": "Basketball", "home": "Bayern Munich", "away": "Virtus Bologna", "market": "Total Over (169.5): x", "odds": 1.93, "kickoff": "2026-10-09 01:00", "status": "Win"}]}
ACCOUNTS = {"1xbet PHP": ("1xbet", "PHP")}


class PlanTest(unittest.TestCase):
    def test_ticket_legs_and_opening_line(self):
        p = plan([SLIP], TIPS, {}, 1, {"PHP": 1.0}, ACCOUNTS)
        self.assertEqual(p.problems, [])
        self.assertEqual(p.bets[0][0], "S-0001")
        self.assertEqual([l[2] for l in p.legs], ["T-0436", "T-0499"])
        self.assertEqual(p.legs[1][8], "Won")
        self.assertEqual(p.ledger[0][2:4], ["Opening balance", 1000])

    def test_duplicate_slip_skipped(self):
        p = plan([SLIP], TIPS, {"1": "S-0007"}, 8, {"PHP": 1.0}, ACCOUNTS)
        self.assertEqual(p.bets, [])

    def test_bad_totals_and_unmatched_leg_are_problems(self):
        bad = dict(SLIP, total_odds=4.0, legs=SLIP["legs"] + [{"sport": "Football", "home": "Nobody", "away": "Else",
                                                               "market": "1X2: W1: x", "odds": 1.0, "kickoff": "2026-10-09 01:00"}])
        p = plan([bad], TIPS, {}, 1, {"PHP": 1.0}, ACCOUNTS)
        self.assertTrue(any("multiply" in x for x in p.problems))
        self.assertTrue(any("Own pick?" in x for x in p.problems))

    def test_own_pick_accepted(self):
        own = dict(SLIP, total_odds=3.532 * 1.5, potential=None,
                   legs=SLIP["legs"] + [{"sport": "Football", "home": "Nobody", "away": "Else", "market": "1X2: W1: x",
                                         "odds": 1.5, "kickoff": "2026-10-09 01:00", "own": True}])
        p = plan([own], TIPS, {}, 1, {"PHP": 1.0}, ACCOUNTS)
        self.assertEqual(p.problems, [])
        self.assertEqual(p.legs[2][3], "Yes")


if __name__ == "__main__":
    unittest.main()
