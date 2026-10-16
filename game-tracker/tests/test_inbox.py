import unittest
from pathlib import Path

import os
import tempfile

from inbox import check_done, local_name, plan_pull
from sync import in_reach

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

    def test_plan_pull_new_and_updated_only(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d)
            old = cache / "football" / "2026-10-12.json"
            old.parent.mkdir()
            old.write_text("{}")
            ts = 1_760_000_000
            os.utime(old, (ts, ts))
            files = [
                {"id": "1", "name": "football_2026-10-12.json", "modifiedTime": "2025-10-09T08:53:20Z"},  # = ts
                {"id": "2", "name": "football_2026-10-13.json", "modifiedTime": "2026-10-13T06:00:00Z"},
                {"id": "3", "name": "_status.json", "modifiedTime": "2026-10-13T06:00:00Z"},
            ]
            self.assertEqual([f["id"] for f, _, _ in plan_pull(files, cache)], ["2"])
            files[0]["modifiedTime"] = "2026-10-13T06:00:00Z"  # Drive copy updated since
            self.assertEqual([p.name for _, p, _ in plan_pull(files, cache)], ["2026-10-12.json", "2026-10-13.json"])

    def test_in_reach_window_or_saved_day(self):
        days = ["2026-10-15", "2026-10-16", "2026-10-17"]
        cached = {"Football": {"2026-10-12"}, "Basketball": set()}
        self.assertTrue(in_reach("Football", "2026-10-16", days, cached))
        self.assertTrue(in_reach("Football", "2026-10-12", days, cached))
        self.assertFalse(in_reach("Basketball", "2026-10-12", days, cached))


if __name__ == "__main__":
    unittest.main()
