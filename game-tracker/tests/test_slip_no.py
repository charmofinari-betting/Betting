import unittest

from slip_no import check, describe, guess, is_own_key, learn, own_key, shape

ACCOUNTS = {"bet88": ("bet88", "PHP"), "bet88 Tish": ("bet88", "PHP"), "Solaire": ("Solaire", "PHP"),
            "BingoPlus": ("BingoPlus", "PHP"), "msw.ph Pat": ("msw.ph", "PHP"), "Okada": ("Okada", "PHP"),
            "1xbet PHP": ("1xbet", "PHP")}


def row(acct, no):
    return ["S-0001", "", acct] + [""] * 16 + [no]


BETS = ([row("bet88", "2719626337345221478")] * 4 + [row("bet88 Tish", "2725052303013974159")] * 2
        + [row("bet88", "bet88-combo-1019-2027"), row("bet88", "")]
        + [row("Solaire", "899622966726983681")] * 21 + [row("Solaire", "8996712640908083320")]
        + [row("BingoPlus", "581262517158805507")] * 2
        + [row("msw.ph Pat", "XX1-G6F-SRW-CHS"), row("msw.ph Pat", "PY1-06R-T83-PUG")] * 3
        + [row("Okada", "123")] * 2 + [row("1xbet PHP", "88399886893")] * 6)


class ShapeTest(unittest.TestCase):
    def test_shapes(self):
        self.assertEqual(shape("2719626337345221478"), "D19")
        self.assertEqual(shape("XX1-G6F-SRW-CHS"), "X3-X3-X3-X3")
        self.assertEqual(describe("D19"), "19 digits")
        self.assertEqual(describe("X3-X3-X3-X3"), "4 groups of 3 letters/digits")

    def test_own_keys_are_lowercase(self):
        self.assertTrue(is_own_key("msw.ph-pat-system-2-5-1022-2208"))
        self.assertFalse(is_own_key("XX1-G6F-SRW-CHS"))


class LearnTest(unittest.TestCase):
    F = learn(BETS, ACCOUNTS)

    def test_learns_each_book_skips_own_keys_and_outliers(self):
        self.assertEqual(self.F["bet88"], ({"D19"}, True))
        self.assertEqual(self.F["Solaire"], ({"D18"}, True))  # the one 19-digit number is not learned
        self.assertEqual(self.F["msw.ph"], ({"X3-X3-X3-X3"}, True))
        self.assertEqual(self.F["1xbet"], ({"D11"}, True))
        self.assertEqual(self.F["BingoPlus"], ({"D18"}, False))  # 2 slips: used for guessing, not checked

    def test_check(self):
        self.assertIsNone(check("2725056282284409779", "bet88", self.F))
        self.assertIsNone(check("581262517158805507", "BingoPlus", self.F))  # not checked yet
        self.assertIsNone(check("msw.ph-pat-double-1022-2208", "msw.ph", self.F))
        p = check("8996712640908083320", "Solaire", self.F)
        self.assertIn("doesn't look like a Solaire number (usually 18 digits)", p)
        self.assertIn("it fits bet88", p)
        self.assertIn("usually 11 digits", check("8839988689", "1xbet", self.F))

    def test_guess(self):
        self.assertEqual(guess("2724974928796459412", self.F), ["bet88"])
        self.assertEqual(guess("901302727425581056", self.F), ["BingoPlus", "Solaire"])
        self.assertEqual(guess("PY1-D6R-3J3-PUC", self.F), ["msw.ph"])
        self.assertEqual(guess("12", self.F), [])


class OwnKeyTest(unittest.TestCase):
    def test_own_key(self):
        self.assertEqual(own_key("msw.ph Pat", "System 2/5", "2026-10-22 22:08"), "msw.ph-pat-system-2-5-1022-2208")
        self.assertEqual(own_key("Solaire", "Single", "2026-10-23 10:55"), "solaire-single-1023-1055")


if __name__ == "__main__":
    unittest.main()
