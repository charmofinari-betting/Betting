import unittest

from funds import label, parse_balances, pots, tab_values, totals

HEAD = [["Account"], ["TOTAL in ₱"]]
# Account, Opening, Deposits, Withdrawals, Transfers, Bonus, Staked, Returned, Balance, Open, Cur, FX, Bal ₱, Open ₱, Holder
ROWS = HEAD + [
    ["1xbet PHP", "1,000.00", "500.00", "300.00", "0", "1.00", "2,000", "2,100", "1,301.00", "0", "PHP", "1.0000", "", "", "Paolo"],
    ["1xbet USDT", "100.00", "0", "50.00", "0", "0", "100", "120", "70.00", "0", "USDT", "60.0000", "", "", "Paolo"],
    ["msw.ph Pat", "0", "5,000.00", "0", "0", "0", "5,000", "0", "0", "1,000.00", "PHP", "1.0000", "", "", "Pat"],
    ["bet88", "0", "2,000.00", "0", "0", "0", "0", "0", "2,000.00", "0", "PHP", "1.0000", "", "", "Paolo"],
]


class TestFunds(unittest.TestCase):
    def setUp(self):
        self.acc = parse_balances(ROWS)

    def test_pots_own_php_first_then_crypto_then_holders(self):
        self.assertEqual(pots(self.acc), [("Paolo", "PHP"), ("Paolo", "USDT"), ("Pat", "PHP")])
        self.assertEqual([label(p) for p in pots(self.acc)], ["Own PHP", "Own USDT", "Pat"])

    def test_crypto_stays_in_native_units(self):
        t = totals(self.acc, ("Paolo", "USDT"))
        self.assertEqual((t["capital"], t["withdrawn"], t["cash"]), (100, 50, 70))

    def test_own_php_sums_books_and_check_line_is_settled_pnl(self):
        t = totals(self.acc, ("Paolo", "PHP"))
        self.assertEqual(t["capital"], 3500)
        # cash 1301+2000 + withdrawn 300 - capital 3500 - bonus 1 = returned - staked = 100
        self.assertAlmostEqual(t["pnl"], 100)

    def test_holder_pot_kept_apart(self):
        t = totals(self.acc, ("Pat", "PHP"))
        self.assertEqual((t["capital"], t["open"], t["pnl"]), (5000, 1000, -4000))

    def test_tab_formulas_reference_criteria_rows(self):
        rows = tab_values(pots(self.acc))
        self.assertEqual(rows[1], ["Pot", "Own PHP", "Own USDT", "Pat"])
        self.assertIn("Balances!$O$3:$O,B$3,Balances!$K$3:$K,B$4", rows[4][1])
        self.assertTrue(rows[12][3].startswith("=D10+D6-D5-D11-D12"))


if __name__ == "__main__":
    unittest.main()
