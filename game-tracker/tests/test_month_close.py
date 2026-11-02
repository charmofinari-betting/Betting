import unittest

from month_close import close_rows, month_of

ACCOUNTS = [["Account", "Book", "Holder", "Currency"],
            ["1xbet PHP", "1xbet", "Paolo", "PHP"],
            ["1xbet USDT", "1xbet", "Paolo", "USDT"],
            ["msw.ph Pat", "msw.ph", "Pat", "PHP"]]


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
         ["8 Nov 2026", "Claude Pro subscription", "20", "USD", "1,400.00"]]


class TestMonthClose(unittest.TestCase):
    def setUp(self):
        rows = close_rows("Oct 2026", ACCOUNTS, BETS, LEDGER, COSTS)
        self.by = {r[1]: r for r in rows}

    def test_month_of_reads_the_date_cell(self):
        self.assertEqual(month_of("31 Oct 2026 10:32"), "Oct 2026")
        self.assertEqual(month_of("before tracking"), "")

    def test_own_php_counts_tickets_placed_in_the_month(self):
        r = self.by["Own PHP"]
        self.assertEqual(r[2:8], [2, 0, 3000.0, -1500.0, 100.0, -1400.0])

    def test_crypto_stays_in_its_own_units_and_out_of_the_peso_total(self):
        self.assertEqual(self.by["Own USDT"][5], 5.0)
        self.assertEqual(self.by["Own USDT"][8], "USDT")
        self.assertEqual(self.by["All PHP before costs"][7], -1400.0 + -250.0)

    def test_open_tickets_are_counted_and_flagged(self):
        r = self.by["Pat"]
        self.assertEqual(r[2:8], [0, 1, 0.0, 0.0, -250.0, -250.0])
        self.assertIn("open", r[9])

    def test_costs_split_holder_and_project_and_net(self):
        self.assertEqual(self.by["Holder costs"][7], -5000.0)
        self.assertEqual(self.by["Project costs"][7], -1420.04)
        self.assertEqual(self.by["Net PHP"][7], -1650.0 - 5000.0 - 1420.04)


if __name__ == "__main__":
    unittest.main()
