"""Tests for jobs.find_job."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jobs  # noqa: E402


class FindJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for i, (name, folder) in enumerate([("a", "MBAM601_Digital/Day 1"), ("b", "MBAM601_Digital/Day 2"),
                                            ("c", "MBAM622_Marketing/Day 1"), ("d", "MBAM601_Digital/Day 1")]):
            d = self.root / name
            d.mkdir()
            (d / "manifest.json").write_text(json.dumps({"folder": folder}))
            os.utime(d / "manifest.json", (time.time() + i, time.time() + i))

    def tearDown(self):
        self.tmp.cleanup()

    def test_by_day_and_course_picks_newest(self):
        self.assertEqual(jobs.find_job(self.root, day="Day 1", course="mbam601").name, "d")
        self.assertEqual(jobs.find_job(self.root, day="day 2").name, "b")

    def test_same_day_in_two_courses_needs_course(self):
        with self.assertRaises(SystemExit) as cm:
            jobs.find_job(self.root, day="Day 1")
        self.assertIn("--course", str(cm.exception))

    def test_unknown_day_lists_known_ones(self):
        with self.assertRaises(SystemExit) as cm:
            jobs.find_job(self.root, day="Day 9")
        self.assertIn("MBAM601 Day 2", str(cm.exception))

    def test_job_name_and_newest(self):
        self.assertEqual(jobs.find_job(self.root, job="b").name, "b")
        self.assertEqual(jobs.find_job(self.root).name, "d")
