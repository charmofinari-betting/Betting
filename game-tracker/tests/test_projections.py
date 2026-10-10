import unittest

from projections import system_outcomes


class ProjectionsTest(unittest.TestCase):
    def test_locked_and_best(self):
        # 2/3 system, stake 300 (3 combos x 100); legs A, B won, C open
        o = system_outcomes([2.0, 3.0, 4.0], ["Won", "Won", ""], 2, 300, margin=0.0)
        self.assertEqual(o["locked"], 600.0)                 # A+B only: 100 x 2 x 3
        self.assertEqual(o["best"], 100 * (6 + 8 + 12))      # C wins: all three pairs pay
        self.assertEqual(o["open_legs"], 1)

    def test_expected_between_locked_and_best(self):
        o = system_outcomes([2.0, 3.0, 4.0], ["Won", "Won", ""], 2, 300, margin=0.0)
        self.assertGreater(o["expected"], o["locked"])
        self.assertLess(o["expected"], o["best"])

    def test_lost_legs_cut_pairs(self):
        o = system_outcomes([2.0, 3.0, 4.0], ["Lost", "Won", ""], 2, 300, margin=0.0)
        self.assertEqual(o["locked"], 0.0)
        self.assertEqual(o["best"], 100 * 3 * 4)


if __name__ == "__main__":
    unittest.main()
