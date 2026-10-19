import unittest

from bets_refresh import BEFORE, refresh_plan

NOW = "19 Oct 2026 14:05"


def bet(sid, kind, stake, result="Open", acct="1xbet PHP"):
    r = [""] * 25
    r[0], r[2], r[3], r[4], r[7], r[16] = sid, acct, kind, stake, result, "1.0000"
    return r


def leg(sid, odds):
    return [sid, "1", "", "", "", "", odds]


class BetsRefreshTest(unittest.TestCase):
    def test_open_ticket_gets_max_return_and_stamp(self):
        plan = refresh_plan([bet("S-1", "Double", "1,000.00")], [leg("S-1", "2.0"), leg("S-1", "3.0")], NOW, False)
        self.assertEqual(plan, [(2, "6000.00", NOW, "")])

    def test_newly_settled_ticket_gets_settled_at_and_loses_max(self):
        b = bet("S-1", "Double", "1,000.00", result="Won")
        b[22], b[23] = "6000.00", "18 Oct 2026 09:00"
        self.assertEqual(refresh_plan([b], [], NOW, False), [(2, "", "", NOW)])

    def test_first_run_marks_old_settled_tickets_before_tracking(self):
        plan = refresh_plan([bet("S-1", "Single", "500", result="Lost")], [], NOW, True)
        self.assertEqual(plan, [(2, "", "", BEFORE)])

    def test_reopened_ticket_clears_settled_at(self):
        b = bet("S-1", "Single", "500")
        b[24] = "18 Oct 2026 22:10"
        self.assertEqual(refresh_plan([b], [leg("S-1", "1.9")], NOW, False), [(2, "950.00", NOW, "")])

    def test_unchanged_rows_are_not_rewritten(self):
        b = bet("S-1", "Single", "500", result="Lost")
        b[24] = "18 Oct 2026 22:10"
        self.assertEqual(refresh_plan([b], [], NOW, False), [])

    def test_unchanged_open_ticket_keeps_its_stamp(self):
        b = bet("S-1", "Single", "500")
        b[22], b[23] = "950.00", "18 Oct 2026 09:00"
        self.assertEqual(refresh_plan([b], [leg("S-1", "1.9")], NOW, False), [])

    def test_short_rows_and_blank_rows_are_safe(self):
        short = bet("S-1", "Single", "500", result="Lost")[:22]
        self.assertEqual(refresh_plan([short, []], [], NOW, True), [(2, "", "", BEFORE)])


if __name__ == "__main__":
    unittest.main()
