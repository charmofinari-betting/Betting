import unittest

from month_close import HEADER, close_rows, month_of, pairs

ACCOUNTS = [["Account", "Book", "Holder", "Currency"],
            ["1xbet PHP", "1xbet", "Paolo", "PHP"],
            ["1xbet USDT", "1xbet", "Paolo", "USDT"],
            ["msw.ph Pat", "msw.ph", "Pat", "PHP"],
            ["bet88 Tish", "bet88", "Tish", "PHP"]]


def bet(placed, account, stake, result, pnl, cur="PHP"):
    r = [""] * 26
    r[0], r[1], r[2], r[4], r[7], r[9], r[15] = "S-1", placed, account, stake, result, pnl, cur
    return r


BETS = [["header"],
        bet("31 Oct 2026 10:00", "1xbet PHP", "1,000.00", "Won", "+500.00"),
        bet("2 Oct 2026 9:00", "1xbet PHP", "2,000.00", "Lost", "-2,000.00"),
        bet("1 Nov 2026 9:00", "1xbet PHP", "9,999.00", "Won", "+9,999.00"),  # November: left out
        bet("15 Oct 2026 9:00", "1xbet USDT", "10.00", "Won", "+5.00", "USDT"),
        bet("20 Oct 2026 9:00", "msw.ph Pat", "3,000.00", "Open", "")]
LEDGER = [["Date", "Account", "Type", "Amount"],
          ["5 Oct 2026", "1xbet PHP", "Bonus", "100.00"],
          ["6 Oct 2026", "msw.ph Pat", "Adjustment", "-250.00"],
          ["6 Oct 2026", "msw.ph Pat", "Deposit", "5,000.00"],  # not P&L
          ["2 Nov 2026", "1xbet PHP", "Bonus", "77.00"]]
COSTS = [["Date", "Item", "Amount", "Currency", "₱ charged"],
         ["8 Oct 2026", "Claude Pro subscription", "20", "USD", "1,420.04"],
         ["31 Oct 2026", "Holder commission (Pat, msw.ph)", "5,000.00", "PHP", "5,000.00"],
         ["31 Oct 2026", "Holder bonus (Pat and Tish)", "1,000.00", "PHP", "1,000.00"],
         ["8 Nov 2026", "Claude Pro subscription", "20", "USD", "1,400.00"]]


class TestMonthClose(unittest.TestCase):
    def setUp(self):
        rows = close_rows("Oct 2026", ACCOUNTS, BETS, LEDGER, COSTS, {"Pat": 4499.95, "Mine": 0.0},
                          {"Pat": "agreed"}, "2 Nov 2026")
        self.by = {r[1]: r for r in rows}
        self.rows = rows

    def test_month_of_reads_the_date_cell(self):
        self.assertEqual(month_of("31 Oct 2026 10:32"), "Oct 2026")
        self.assertEqual(month_of("Oct 2026"), "Oct 2026")
        self.assertEqual(month_of("before tracking"), "")

    def test_rows_have_the_columns_the_dashboard_reads(self):
        self.assertEqual(HEADER[7], "Result")
        self.assertEqual(HEADER[10], "Next month opening")
        self.assertTrue(all(len(r) == len(HEADER) for r in self.rows))

    def test_mine_counts_tickets_placed_in_the_month(self):
        # tickets, open, staked, P&L, bonus, result, costs (Claude Pro only), net, opening
        self.assertEqual(self.by["Mine"][2:11], [2, 0, 3000.0, -1500.0, 100.0, -1400.0, 1420.04, -2820.04, 0.0])

    def test_result_is_pnl_plus_bonus(self):
        for r in self.rows[:-4]:
            self.assertEqual(r[7], round(r[5] + r[6], 2))

    def test_crypto_stays_in_its_own_units_and_out_of_the_peso_total(self):
        self.assertEqual(self.by["Mine USDT"][7], 5.0)
        self.assertEqual(self.by["Mine USDT"][11], "USDT")
        self.assertEqual(self.by["All PHP before costs"][7], -1400.0 + -250.0)

    def test_open_tickets_are_flagged_and_notes_kept(self):
        r = self.by["Pat"]
        self.assertEqual(r[2:4], [0, 1])
        self.assertIn("open", r[13])
        self.assertIn("agreed", r[13])

    def test_holder_costs_split_between_named_holders(self):
        self.assertEqual(self.by["Pat"][8], 5500.0)
        self.assertEqual(self.by["Tish"][8], 500.0)

    def test_no_opening_given_stays_blank(self):
        self.assertEqual(self.by["Tish"][10], "")
        self.assertEqual(self.by["Pat"][10], 4499.95)

    def test_summary_costs_and_net(self):
        self.assertEqual(self.by["Holder costs"][8], 6000.0)
        self.assertEqual(self.by["Project costs"][8], 1420.04)
        self.assertEqual(self.by["Net PHP"][9], -1650.0 - 6000.0 - 1420.04)

    def test_pairs(self):
        self.assertEqual(pairs(["--open", "Pat=1.5", "--note", "Tish=a=b"], "--note"), {"Tish": "a=b"})


if __name__ == "__main__":
    unittest.main()
