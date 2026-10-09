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

    def test_fx_applied(self):
        rows, stake, ret = summarise([bet("S-6", "Double", "100", fx="63.03")], [leg("S-6", "2.0"), leg("S-6", "2.0")])
        self.assertEqual((stake, ret), (6303.0, 25212.0))


if __name__ == "__main__":
    unittest.main()
