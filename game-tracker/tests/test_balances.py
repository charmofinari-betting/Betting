import unittest

from balances import expected_as_of, fmt_pht, parse_pht, plan_check, resolve_account
from bets_refresh import BEFORE

AT = parse_pht("19 Oct 2026 14:00")


def bet(sid, placed, acct, stake, ret="", settled="", result=None):
    r = [""] * 25
    r[0], r[1], r[2], r[4], r[8], r[24] = sid, placed, acct, stake, ret, settled
    r[7] = result or ("Won" if settled else "Open")
    return r


def leg(sid, kickoff=""):
    r = [""] * 14
    r[0], r[1], r[10] = sid, "1", kickoff
    return r


class ParseTest(unittest.TestCase):
    def test_parse_pht_time_and_date(self):
        self.assertEqual(parse_pht("7 Oct 2026 11:59").strftime("%Y-%m-%d %H:%M"), "2026-10-07 11:59")
        self.assertEqual(parse_pht("19 Oct 2026").strftime("%Y-%m-%d %H:%M"), "2026-10-19 00:00")
        self.assertIsNone(parse_pht(""))
        self.assertIsNone(parse_pht("tomorrow"))


class ExpectedAsOfTest(unittest.TestCase):
    def test_bet_placed_after_check_adds_stake_back(self):
        e, _, asks = expected_as_of("bet88", AT, 1000.0, [bet("S-1", "19 Oct 2026 15:00", "bet88", "200")], [], set())
        self.assertEqual((e, asks), (1200.0, []))

    def test_bet_placed_before_check_changes_nothing(self):
        e, _, _ = expected_as_of("bet88", AT, 1000.0, [bet("S-1", "19 Oct 2026 13:00", "bet88", "1,200.00")], [], set())
        self.assertEqual(e, 1000.0)

    def test_ticket_settled_after_check_removes_return(self):
        b = bet("S-1", "18 Oct 2026 10:00", "bet88", "200", ret="500", settled="19 Oct 2026 16:00")
        self.assertEqual(expected_as_of("bet88", AT, 1000.0, [b], [], set())[0], 500.0)

    def test_kickoff_estimate_beats_late_stamp(self):
        # book paid at ~13:00 (kickoff 10:00 + 3h), sheet only learned at 20:00: settled before the 14:00 check
        b = bet("S-1", "19 Oct 2026 09:00", "bet88", "200", ret="500", settled="19 Oct 2026 20:00")
        legs = [leg("S-1", kickoff="19 Oct 2026 10:00")]
        self.assertEqual(expected_as_of("bet88", AT, 1000.0, [b], [], set(), legs)[0], 1000.0)

    def test_late_leg_kickoff_keeps_ticket_after_check(self):
        b = bet("S-1", "19 Oct 2026 09:00", "bet88", "200", ret="500", settled="19 Oct 2026 20:00")
        legs = [leg("S-1", kickoff="19 Oct 2026 10:00"), leg("S-1", kickoff="19 Oct 2026 13:30")]
        self.assertEqual(expected_as_of("bet88", AT, 1000.0, [b], [], set(), legs)[0], 500.0)

    def test_ticket_placed_after_check_cannot_have_settled_before_it(self):
        b = bet("S-1", "19 Oct 2026 15:00", "bet88", "200", ret="500", settled=BEFORE)
        self.assertEqual(expected_as_of("bet88", AT, 1000.0, [b], [], set())[0], 700.0)   # +200 stake, -500 return

    def test_before_tracking_counts_as_settled_before(self):
        b = bet("S-1", "10 Oct 2026 10:00", "bet88", "200", ret="500", settled=BEFORE)
        e, trace, _ = expected_as_of("bet88", AT, 1000.0, [b], [], set())
        self.assertEqual(e, 1000.0)

    def test_ledger_next_day_undone_same_day_asked(self):
        led = [["20 Oct 2026", "bet88", "Deposit", "300", "Paolo", ""],
               ["19 Oct 2026", "bet88", "Withdrawal", "100", "Paolo", ""]]
        e, _, asks = expected_as_of("bet88", AT, 1000.0, [], led, set())
        self.assertEqual(e, 700.0)
        self.assertEqual(len(asks), 1)
        self.assertEqual(expected_as_of("bet88", AT, 1000.0, [], led, {3})[0], 800.0)   # row 3 = 2nd line, marked after

    def test_other_accounts_ignored(self):
        bets = [bet("S-1", "19 Oct 2026 15:00", "bet88 Tish", "200")]
        led = [["20 Oct 2026", "bet88 Tish", "Deposit", "300", "Tish", ""]]
        self.assertEqual(expected_as_of("bet88", AT, 1000.0, bets, led, set())[0], 1000.0)

    def test_unparseable_placed_time_is_asked(self):
        _, _, asks = expected_as_of("bet88", AT, 1000.0, [bet("S-1", "", "bet88", "200")], [], set())
        self.assertEqual(len(asks), 1)


class CheckTest(unittest.TestCase):
    def test_unknown_account_refused(self):
        with self.assertRaises(SystemExit) as e:
            resolve_account("msw", ["msw.ph Pat", "msw.ph Grace"])
        self.assertIn("msw.ph Pat", str(e.exception))
        self.assertIn("msw.ph Grace", str(e.exception))

    def test_exact_account_accepted(self):
        self.assertEqual(resolve_account("msw.ph Pat", ["msw.ph Pat", "msw.ph Grace"]), "msw.ph Pat")

    def test_checked_at_is_written_in_the_sheet_format(self):
        self.assertEqual(fmt_pht(parse_pht("19 oct 2026 9:05")), "19 Oct 2026 09:05")
        self.assertEqual(fmt_pht(parse_pht("07 Oct 2026 11:59")), "7 Oct 2026 11:59")

    def test_plan_check_row(self):
        row, gap = plan_check("bet88", 9500.0, "19 Oct 2026 14:00", 9000.12, "abc", "")
        self.assertEqual(row, ["19 Oct 2026 14:00", "bet88", "9500.00", "9000.12", "499.88", "abc", ""])
        self.assertAlmostEqual(gap, 499.88)


if __name__ == "__main__":
    unittest.main()
