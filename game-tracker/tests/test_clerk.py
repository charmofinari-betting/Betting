import unittest
from datetime import datetime

from clerk import clear_updates, due_reminders, lock_state, waiting

AT = datetime(2026, 10, 22, 18, 7)


class LockTest(unittest.TestCase):
    def test_free_busy_stale(self):
        self.assertEqual(lock_state(["Lock", "", ""], AT)[0], "free")
        self.assertEqual(lock_state(["Lock"], AT)[0], "free")
        self.assertEqual(lock_state(["Lock", "clerk", "22 Oct 2026 17:50"], AT)[0], "busy")
        self.assertEqual(lock_state(["Lock", "clerk", "22 Oct 2026 17:30"], AT)[0], "stale")
        self.assertEqual(lock_state(["Lock", "clerk", "garbled"], AT)[0], "stale")


class WaitingTest(unittest.TestCase):
    ROWS = [
        ["21 Oct 2026 17:07", "clerk", "3", "S-0270", "slip cut off", "idA, idB", "", "link"],
        ["22 Oct 2026 09:07", "clerk", "1", "", "new wording", "idC", "", "link"],
        ["20 Oct 2026 10:07", "clerk", "1", "", "old", "idD", "21 Oct 2026 08:07", "link"],
        ["22 Oct 2026 10:07", "laptop", "2", "T-1650", "", "", "", ""],
    ]

    def test_ids_with_rows(self):
        w = waiting(self.ROWS)
        self.assertEqual(sorted(w), ["idA", "idB", "idC", "idD"])
        self.assertEqual(w["idC"][0], 5)

    def test_clear_hits_every_row(self):
        rows = [["", "", "", "", "q1", "idA, idB"], ["", "", "", "", "q2", "idA"], ["", "", "", "", "", "idC"]]
        self.assertEqual(clear_updates(rows, {"idA"}), {4: ("idB", None), 5: ("", "answered: q2")})

    def test_answered_marked_once(self):
        rows = [["", "", "", "", "answered: q", "idA"]]
        self.assertEqual(clear_updates(rows, {"idA"}), {4: ("", None)})

    def test_reminders_after_a_day_once(self):
        self.assertEqual(due_reminders(self.ROWS, AT), ["idA", "idB"])


if __name__ == "__main__":
    unittest.main()
