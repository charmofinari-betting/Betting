import unittest

from month_close import month_figures, month_of

ACC = [["Account", "Book", "Holder", "Currency", "Status", "Notes"],
       ["Solaire", "", "Paolo", "PHP", "Active", ""], ["1xbet USDT", "", "Paolo", "USDT", "Active", ""],
       ["msw.ph Pat", "", "Pat", "PHP", "Active", ""], ["bet88 Tish", "", "Tish", "PHP", "Active", ""]]


def bet(account, placed, result, pl):
    r = [""] * 25
    r[0], r[1], r[2], r[7], r[18] = "S-x", placed, account, result, pl
    return r


class MonthCloseTest(unittest.TestCase):
    def test_month_of(self):
        self.assertEqual(month_of("31 Oct 2026 23:50"), "Oct 2026")
        self.assertEqual(month_of("Oct 2026"), "Oct 2026")
        self.assertEqual(month_of(""), "")

    def test_same_rules_as_the_dashboard(self):
        bets = [["h"] * 25, bet("msw.ph Pat", "31 Oct 2026 23:00", "Won", "+500.00"),
                bet("msw.ph Pat", "1 Nov 2026 0:10", "Lost", "-100.00"), bet("Solaire", "30 Oct 2026 9:00", "Open", ""),
                bet("1xbet USDT", "30 Oct 2026 9:00", "Won", "+60.00")]
        ledger = [["h"] * 6, ["31 Oct 2026", "msw.ph Pat", "Adjustment", "-250.00", "Paolo", ""],
                  ["31 Oct 2026", "msw.ph Pat", "Withdrawal", "1,000.00", "Paolo", ""]]
        costs = [["h"] * 6, ["8 Oct 2026", "Claude Pro subscription", "20", "USD", "1,420.04", ""],
                 ["31 Oct 2026", "Holder bonus (Pat and Tish)", "5,000.00", "PHP", "5,000.00", ""]]
        f = month_figures(ACC, bets, ledger, costs, "Oct 2026")
        self.assertEqual(f["Pat"], {"result": 250.0, "costs": 2500.0})
        self.assertEqual(f["Tish"], {"result": 0.0, "costs": 2500.0})
        self.assertEqual(f["Mine"], {"result": 0.0, "costs": 1420.04})


if __name__ == "__main__":
    unittest.main()
