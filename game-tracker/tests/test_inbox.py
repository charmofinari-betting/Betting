import unittest
from pathlib import Path

import os
import tempfile

from inbox import FOLDER_MIME, balances_folder, capture_time, check_done, local_name, pht_from_created, plan_pull, tag
from sync import in_reach

F = {"id": "abc123", "name": "Screenshot_20261016.jpg", "mimeType": "image/jpeg",
     "createdTime": "2026-10-16T09:41:07.123Z", "folder": "Slips"}


class TestBalancesInbox(unittest.TestCase):
    def test_created_time_to_pht(self):
        self.assertEqual(pht_from_created("2026-10-19T06:05:07.123Z"), "19 Oct 2026 14:05")
        self.assertEqual(pht_from_created("2026-10-08T17:30:00Z"), "9 Oct 2026 01:30")

    def test_capture_time_prefers_screenshot_name_then_photo_metadata(self):
        f = {"name": "Screenshot_20261019-140512_1xbet.jpg", "createdTime": "2026-10-19T09:00:00Z"}
        self.assertEqual(capture_time(f), ("19 Oct 2026 14:05", "file name"))
        f = {"name": "IMG.jpg", "createdTime": "2026-10-19T09:00:00Z", "imageMediaMetadata": {"time": "2026:10:19 13:58:07"}}
        self.assertEqual(capture_time(f), ("19 Oct 2026 13:58", "photo metadata"))
        f = {"name": "x.jpg", "createdTime": "2026-10-19T06:05:07.123Z"}
        self.assertEqual(capture_time(f), ("19 Oct 2026 14:05", "upload time"))

    def test_balances_folder_found_by_name(self):
        kids = [{"id": "f1", "name": "Tips", "mimeType": FOLDER_MIME},
                {"id": "f9", "name": "Balances", "mimeType": FOLDER_MIME},
                {"id": "x", "name": "Balances", "mimeType": "image/png"}]
        self.assertEqual(balances_folder(kids), "f9")
        self.assertIsNone(balances_folder(kids[:1]))


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

    def test_holder_subfolder_tags_placed_by_and_skips_folders(self):
        files = [dict(F, folder=None), {"id": "sub", "name": "Pat", "mimeType": FOLDER_MIME, "createdTime": "x"}]
        tagged = tag(files, "Slips/Pat", "pat-folder-id", "Pat")
        self.assertEqual([(f["id"], f["placed_by"], f["parent"]) for f in tagged], [("abc123", "Pat", "pat-folder-id")])
        self.assertEqual(local_name(tagged[0]), Path("Slips/Pat") / "20261016-094107_abc123.jpg")

    def test_in_reach_window_or_saved_day(self):
        days = ["2026-10-15", "2026-10-16", "2026-10-17"]
        cached = {"Football": {"2026-10-12"}, "Basketball": set()}
        self.assertTrue(in_reach("Football", "2026-10-16", days, cached))
        self.assertTrue(in_reach("Football", "2026-10-12", days, cached))
        self.assertFalse(in_reach("Basketball", "2026-10-12", days, cached))


if __name__ == "__main__":
    unittest.main()
