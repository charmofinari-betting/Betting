import unittest

from parse import parse_selection
from settle import settle


def S(text, ft, ht=None, sport="Football"):
    return settle(parse_selection(text), sport, ft, ht)


class AsianHandicapTest(unittest.TestCase):
    def test_lines(self):
        cases = [  # (selection, FT score, expected)
            ("HOME -0.5", (1, 0), "Won"), ("HOME -0.5", (1, 1), "Lost"),
            ("HOME 0.0", (1, 1), "Void"), ("AWAY 0.0", (1, 2), "Won"),
            ("HOME -0.25", (1, 1), "Half Lost"), ("HOME -0.25", (2, 1), "Won"),
            ("AWAY -0.25", (1, 1), "Half Lost"), ("AWAY 0.25", (1, 1), "Half Won"),
            ("HOME -0.75", (2, 1), "Half Won"), ("HOME -0.75", (3, 1), "Won"), ("HOME -0.75", (1, 1), "Lost"),
            ("HOME -1.0", (2, 1), "Void"), ("HOME -1.0", (3, 1), "Won"),
            ("HOME -1.25", (2, 1), "Half Lost"), ("AWAY 1.5", (2, 1), "Won"), ("AWAY 1.5", (3, 1), "Lost"),
            ("HOME -4.5", (5, 0), "Won"), ("HOME -4.0", (4, 0), "Void"),
        ]
        for text, ft, want in cases:
            with self.subTest(text=text, ft=ft):
                self.assertEqual(S(text, ft), want)


class TotalsTest(unittest.TestCase):
    def test_lines(self):
        cases = [
            ("OVER 2.5", (2, 1), "Won"), ("OVER 2.5", (1, 1), "Lost"), ("UNDER 2.5", (1, 1), "Won"),
            ("OVER 2.0", (1, 1), "Void"), ("UNDER 3.0", (2, 1), "Void"),
            ("OVER 2.25", (1, 1), "Half Lost"), ("OVER 2.25", (2, 1), "Won"),
            ("OVER 2.75", (2, 1), "Half Won"), ("UNDER 2.75", (2, 1), "Half Lost"), ("UNDER 2.75", (1, 1), "Won"),
            ("UNDER 1.5", (1, 1), "Lost"), ("UNDER 2.0", (1, 0), "Won"),
        ]
        for text, ft, want in cases:
            with self.subTest(text=text, ft=ft):
                self.assertEqual(S(text, ft), want)

    def test_basketball_points_and_first_half(self):
        self.assertEqual(S("OVER 167.5", (85, 83), sport="Basketball"), "Won")
        self.assertEqual(S("UNDER 171.5", (90, 82), sport="Basketball"), "Lost")
        self.assertEqual(S("HT HOME -4.5", (80, 78), ht=(45, 40), sport="Basketball"), "Won")
        self.assertEqual(S("HOME -2.5", (80, 78), sport="Basketball"), "Lost")

    def test_first_half_total_needs_ht(self):
        self.assertEqual(S("OVER 1.5 FH", (3, 0), ht=(1, 0)), "Lost")
        self.assertIsNone(S("OVER 1.5 FH", (3, 0)))


class OtherMarketsTest(unittest.TestCase):
    def test_markets(self):
        cases = [
            ("ML HOME", (1, 0), None, "Won"), ("ML HOME", (1, 1), None, "Lost"), ("ML AWAY", (0, 2), None, "Won"),
            ("BTTS YES", (1, 1), None, "Won"), ("BTTS YES", (2, 0), None, "Lost"), ("BTTS NO", (2, 0), None, "Won"),
            ("BTTS YES 2H", (2, 1), (1, 0), "Won"), ("BTTS YES 2H", (2, 1), (1, 1), "Lost"),
            ("HOME TEAM OVER 1.5", (2, 3), None, "Won"), ("AWAY TEAM OVER 1.5", (2, 1), None, "Lost"),
            ("HOME TEAM UNDER 0.5", (0, 2), None, "Won"), ("AWAY TEAM OVER 0.5 FH", (1, 1), (1, 0), "Lost"),
            ("HOME TEAM TO WIN EITHER HALF", (1, 1), (1, 0), "Won"), ("HOME TEAM TO WIN EITHER HALF", (1, 1), (0, 0), "Lost"),
            ("AWAY TEAM TO WIN BOTH HALVES", (0, 2), (0, 1), "Won"), ("AWAY TEAM TO WIN BOTH HALVES", (0, 1), (0, 1), "Lost"),
            ("HOME TEAM TO SCORE IN BOTH HALVES", (2, 0), (1, 0), "Won"), ("HOME TEAM TO SCORE IN BOTH HALVES", (2, 0), (2, 0), "Lost"),
            ("BOTH HALVES OVER 1.5", (4, 0), (2, 0), "Won"), ("BOTH HALVES OVER 1.5", (3, 0), (2, 0), "Lost"),
        ]
        for text, ft, ht, want in cases:
            with self.subTest(text=text, ft=ft, ht=ht):
                self.assertEqual(S(text, ft, ht), want)

    def test_needs_paolo(self):
        self.assertIsNone(S("CORNERS UNDER 9.5", (1, 0), (0, 0)))
        self.assertIsNone(S("CARDS UNDER 4.5", (1, 0), (0, 0)))
        for text in ("CARDS HOME OVER 1.5", "CARDS AWAY UNDER 2.5", "CARDS AWAY -0.5", "SET HANDICAP +1.5 HOME"):
            self.assertIsNone(S(text, (1, 0), (0, 0)))
        self.assertIsNone(S("HOME TEAM TO WIN EITHER HALF", (1, 0)))  # no HT score


if __name__ == "__main__":
    unittest.main()
