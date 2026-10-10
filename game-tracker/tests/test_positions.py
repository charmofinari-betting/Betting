import unittest

from positions import summarise


def bet(sid, kind, stake, fx="1.0000", result="Open", acct="1xbet PHP"):
    r = [""] * 22
    r[0], r[2], r[3], r[4], r[7], r[16] = sid, acct, kind, stake, result, fx
    return r


def leg(sid, odds):
    return [sid, "1", "", "", "", "", odds]


class PositionsTest(unittest.TestCase):
    def test_accumulator_and_system(self):
        bets = [bet("S-1", "Treble", "1,000.00"), bet("S-2", "System 2/3", "300.00"), bet("S-3", "Double", "500", result="Lost")]
        legs = [leg("S-1", "2.0"), leg("S-1", "2.0"), leg("S-1", "2.5"),
                leg("S-2", "2.0"), leg("S-2", "3.0"), leg("S-2", "4.0"), leg("S-3", "2.0")]
        rows, stake, ret = summarise(bets, legs)
        self.assertEqual([r[0] for r in rows], ["S-1", "S-2"])
        self.assertEqual(rows[0][4], 10000.0)
        self.assertEqual(rows[1][4], 2600.0)     # 100 x (2*3 + 2*4 + 3*4)
        self.assertEqual((stake, ret), (1300.0, 12600.0))

    def test_lost_leg_cuts_the_ceiling(self):
        dead = ["S-9", "2", "", "", "", "", "2.0", "", "", "Lost", "", "0"]
        bets = [bet("S-9", "System 2/3", "300")]
        legs = [leg("S-9", "2.0"), dead, leg("S-9", "4.0")]
        rows, stake, ret = summarise(bets, legs)
        self.assertEqual(rows[0][4], 300 / 3 * 2.0 * 4.0)  # only the pair without the dead leg pays

    def test_combo_boost_counts(self):
        b = bet("S-8", "Double", "1000")
        b[5] = "5.5"                     # slip odds 5.5 vs legs 2.0 x 2.5 = 5.0 -> boost 1.1
        rows, stake, ret = summarise([b], [leg("S-8", "2.0"), leg("S-8", "2.5")])
        self.assertEqual(rows[0][4], 5500.0)

    def test_fx_applied(self):
        rows, stake, ret = summarise([bet("S-6", "Double", "100", fx="63.03")], [leg("S-6", "2.0"), leg("S-6", "2.0")])
        self.assertEqual((stake, ret), (6303.0, 25212.0))


if __name__ == "__main__":
    unittest.main()
