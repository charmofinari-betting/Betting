import unittest
from pathlib import Path

from inbox import check_done, local_name

F = {"id": "abc123", "name": "Screenshot_20261016.jpg", "mimeType": "image/jpeg",
     "createdTime": "2026-10-16T09:41:07.123Z", "folder": "Slips"}


class TestInbox(unittest.TestCase):
    def test_local_name_sortable_and_unique(self):
        self.assertEqual(local_name(F), Path("Slips") / "20261016-094107_abc123.jpg")

    def test_local_name_falls_back_to_file_suffix(self):
        f = dict(F, mimeType="application/octet-stream", name="x.png")
        self.assertEqual(local_name(f).suffix, ".png")

    def test_check_done_only_moves_inbox_files(self):
        move, unknown = check_done([F], ["abc123", "zzz"])
        self.assertEqual([f["id"] for f in move], ["abc123"])
        self.assertEqual(unknown, ["zzz"])


if __name__ == "__main__":
    unittest.main()
