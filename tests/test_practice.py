"""Tests for practice.py."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import practice  # noqa: E402


class PracticeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.jobs = root / "jobs"
        for job, day, n in [("j1", "Day 1", 6), ("j2", "Day 10", 3), ("j3", "Day 2", 4)]:
            q = self.jobs / job / "quiz"
            q.mkdir(parents=True)
            qs = [{"question": f"{day} question number {i} with a long shared prefix that is over sixty characters",
                   "options": ["a", "b", "c", "d"], "answer": 0, "explanation": "x", "concept": "Platform"}
                  for i in range(n)]
            (q / f"Quiz {day}.json").write_text(json.dumps({"course": "MBAM601", "day": day, "questions": qs}))
        core = self.jobs / "j1" / "notes" / "core"
        core.mkdir(parents=True)
        (core / "Platform.md").write_text("# Platform\n**Definition:** A business that connects groups.\n"
                                          "**Why it matters:** Network effects.\n")
        self.vault = root / "My Vault"

    def tearDown(self):
        self.tmp.cleanup()

    def test_collect_groups_by_day_in_natural_order(self):
        payload = practice.collect(self.jobs, self.vault)
        self.assertEqual([d["label"] for d in payload["days"]], ["MBAM601 Day 1", "MBAM601 Day 2", "MBAM601 Day 10"])
        self.assertEqual(len(payload["days"][0]["questions"]), 6)       # long shared prefixes kept apart
        self.assertEqual(payload["concepts"]["Platform"]["why"], "Network effects.")
        self.assertEqual(payload["vault"], "My Vault")

    def test_rerun_of_same_quiz_is_not_duplicated(self):
        src = self.jobs / "j1" / "quiz" / "Quiz Day 1.json"
        (self.jobs / "j4" / "quiz").mkdir(parents=True)
        (self.jobs / "j4" / "quiz" / "Quiz Day 1.json").write_text(src.read_text())
        payload = practice.collect(self.jobs, None)
        self.assertEqual(len(payload["days"][0]["questions"]), 6)

    def test_fixed_set_replaces_pool_for_its_day(self):
        qs = [{"question": f"Set q{i}", "options": ["a", "b", "c", "d"], "answer": 1, "explanation": "e",
               "concept": "Platform", "source": "S", "reference": "R"} for i in range(20)]
        (self.jobs / "j1" / "quiz" / "practice-set.json").write_text(json.dumps(
            {"course": "MBAM601", "day": "Day 1", "built": "2026-10-18", "questions": qs}))
        payload = practice.collect(self.jobs, None)
        day1 = payload["days"][0]
        self.assertTrue(day1["fixed"])
        self.assertEqual([q["question"] for q in day1["questions"]][:2], ["Set q0", "Set q1"])
        self.assertEqual(len(day1["questions"]), 20)
        self.assertNotIn("fixed", payload["days"][1])                 # Day 2 still a pool

    def test_page_embeds_data_safely(self):
        payload = practice.collect(self.jobs, None)
        payload["days"][0]["questions"][0]["explanation"] = "</script><b>x</b>"
        page = practice.build_html(payload)
        self.assertNotIn("/*DATA*/null", page)
        self.assertNotIn("</script><b>", page)
        self.assertEqual(page.count("</script>"), 1)

    def test_main_writes_page(self):
        cfg = Path(self.tmp.name) / "config.json"
        cfg.write_text(json.dumps({"jobs_root": str(self.jobs)}))
        self.assertEqual(practice.main(["--config", str(cfg)]), 0)
        self.assertTrue((self.jobs / "practice.html").exists())


if __name__ == "__main__":
    unittest.main()
