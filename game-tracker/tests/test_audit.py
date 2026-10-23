import unittest
from datetime import datetime

from audit import candidates, logged_ids

ROWS = [
    ["22 Oct 2026 22:12", "clerk", "4", "S-0270, S-0271 (Tish bet88), S-0272 (Paolo bet88 6-fold)", "", "", "", ""],
    ["22 Oct 2026 21:37", "laptop", "10", "78 tips (Sheet1 rows 1651-1728), 12 held tips T-1727..T-1738", "", "", "", ""],
    ["23 Oct 2026 11:08", "clerk", "1", "S-0277, T-1700..T-1702", "", "", "", ""],
    ["15 Oct 2026 11:08", "clerk", "1", "S-0100", "", "", "", ""],
    ["23 Oct 2026 12:08", "clerk", "1", "", "", "", "", ""],
]


class AuditTest(unittest.TestCase):
    def test_logged_ids_clerk_rows_in_window_with_ranges(self):
        ids = logged_ids(ROWS, datetime(2026, 10, 16))
        self.assertEqual(sorted(ids), ["S-0270", "S-0271", "S-0272", "S-0277", "T-1700", "T-1701", "T-1702"])
        self.assertEqual(ids["S-0277"], datetime(2026, 10, 23, 11, 8))

    def test_candidates_uploaded_before_the_run(self):
        done = [{"id": "a", "createdTime": "2026-10-23T02:49:13.000Z"},   # 10:49 PHT
                {"id": "b", "createdTime": "2026-10-21T02:49:13.000Z"},   # two days earlier
                {"id": "c", "createdTime": "2026-10-23T04:00:00.000Z"}]   # after the run
        self.assertEqual([f["id"] for f in candidates(done, datetime(2026, 10, 23, 11, 8))], ["a"])


if __name__ == "__main__":
    unittest.main()
