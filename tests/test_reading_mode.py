"""Tests for reading mode (daily leadership readings such as BusinessMentor): no API calls, no cost."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import file as filer  # noqa: E402
import generate  # noqa: E402
import run  # noqa: E402
from tests.test_generate import FakeClient, tool_response, note  # noqa: E402


def make_reading_job(root: Path) -> Path:
    job = root / "jobs" / "job1"
    (job / "text").mkdir(parents=True)
    files = [("2026-11-03_Executive_Leadership_Brief.pptx", "slides", "slide text"),
             ("2026-11-03_Executive_Leadership_Notes.md", "reading", "Constructive dissent notes."),
             ("2026-11-03_Executive_Leadership_Brief_Alternative-A.pptx", "slides", "alt slides only")]
    extract, manifest = [], []
    for rel, kind, text in files:
        tp = f"text/{Path(rel).stem}.md"
        (job / tp).write_text(text, encoding="utf-8")
        extract.append({"rel_path": rel, "status": "extracted", "text_path": tp, "kind_guess": kind})
        manifest.append({"rel_path": rel, "status": "retrieved", "origin": f"C:\\x\\{rel}"})
    (job / "extract.json").write_text(json.dumps({"files": extract}))
    (job / "manifest.json").write_text(json.dumps({"folder": "BusinessMentor_DailyLeadershipReadings/2026-11-03",
                                                   "files": manifest}))
    return job


def reading_response(title, phrases=(), prompts=()):
    return tool_response({"source_title": title, "kind": "reading",
                          "notes": [note("reference", title), note("core", f"{title} concept")],
                          "quiz": [], "phrases": list(phrases), "reflection_prompts": list(prompts)})


class ReadingGenerateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.job = make_reading_job(self.root)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.cfg = {"vault_path": str(self.vault), "reading_courses": ["BusinessMentor"],
                    "no_quiz_courses": ["BusinessMentor"]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_notes_preferred_over_matching_slides(self):
        client = FakeClient([reading_response("Constructive Dissent", phrases=[{"phrase": "Evidence threshold",
                                                                                "meaning": "minimum proof"}],
                                              prompts=["When does silence hide disagreement?"]),
                             reading_response("Alternative A")])
        report = generate.generate_job(self.job, client, self.cfg)
        done = set(report["sources"])
        self.assertIn("2026-11-03_Executive_Leadership_Notes.md", done)
        self.assertNotIn("2026-11-03_Executive_Leadership_Brief.pptx", done)            # has matching .md
        self.assertIn("2026-11-03_Executive_Leadership_Brief_Alternative-A.pptx", done)  # no .md: still used
        self.assertEqual(len(client.calls), 2)

    def test_reading_message_phrases_and_journal_prompts(self):
        client = FakeClient([reading_response("Constructive Dissent",
                                              phrases=[{"phrase": "Evidence threshold", "meaning": "minimum proof"},
                                                       {"phrase": "evidence threshold"}],
                                              prompts=["When does silence hide disagreement?"]),
                             reading_response("Alternative A")])
        generate.generate_job(self.job, client, self.cfg)
        self.assertTrue(client.calls[0]["messages"][0]["content"].startswith("MODE: LEADERSHIP READING"))
        phrases = json.loads((self.job / "phrases.json").read_text(encoding="utf-8"))
        self.assertEqual([p["phrase"] for p in phrases], ["Evidence threshold"])           # duplicate dropped
        self.assertEqual(phrases[0]["day"], "2026-11-03")
        journal = next((self.job / "notes" / "theme").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("## Reflection prompts from the brief", journal)
        self.assertIn("**1. When does silence hide disagreement?**", journal)

    def test_lecture_courses_unchanged(self):
        self.assertFalse(generate.reading_mode("MBAM601", self.cfg))
        msg = generate.build_user_message("MBAM601", "Day 1", "2026-11-04", "a.pdf", "", "slides", set(), "text")
        self.assertTrue(msg.startswith("COURSE: MBAM601"))


    def test_linkedin_post_notes_are_filed_as_reviewed(self):
        m = json.loads((self.job / "manifest.json").read_text())
        m["folder"] = "LinkedIn_Posts/08_Nov_2026 Why Good Marketing"
        (self.job / "manifest.json").write_text(json.dumps(m))
        client = FakeClient([reading_response("My post - Good Marketing")] * 3)
        generate.generate_job(self.job, client, self.cfg)
        notes = list((self.job / "notes").rglob("*.md"))
        self.assertTrue(notes)
        for n in notes:
            t = n.read_text(encoding="utf-8")
            if "status:" in t:
                self.assertIn("status: reviewed\nreviewed_on:", t, n.name)


class PhrasebookTests(unittest.TestCase):
    def test_append_only_and_no_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            job, target = root / "job", root / "vault" / "BusinessMentor - Daily Leadership Readings"
            job.mkdir()
            (job / "phrases.json").write_text(json.dumps([
                {"phrase": "Evidence threshold", "meaning": "minimum proof", "day": "2026-11-04", "source": "Ref"}]))
            self.assertEqual(filer.append_phrasebook(job, target), 1)
            book = target / filer.PHRASEBOOK
            book.write_text(book.read_text(encoding="utf-8") + "My practice: used it on Monday.\n", encoding="utf-8")
            (job / "phrases.json").write_text(json.dumps([
                {"phrase": "evidence threshold", "day": "2026-11-05"},
                {"phrase": "Material bottleneck", "meaning": "a constraint that matters", "day": "2026-11-05"}]))
            self.assertEqual(filer.append_phrasebook(job, target), 1)
            text = book.read_text(encoding="utf-8")
            self.assertIn("My practice: used it on Monday.", text)                    # your edits kept
            self.assertEqual(text.lower().count("**evidence threshold**"), 1)
            self.assertIn("- **Material bottleneck**: a constraint that matters *(2026-11-05)*", text)


class SortDatedFilesTests(unittest.TestCase):
    def test_loose_dated_files_sorted_for_reading_courses_only(self):
        with tempfile.TemporaryDirectory() as d:
            inbox = Path(d)
            bm = inbox / "BusinessMentor_DailyLeadershipReadings"
            mba = inbox / "MBAM601_X"
            bm.mkdir(), mba.mkdir()
            old = time.time() - 3600
            for f in (bm / "2026-11-04_Executive_Leadership_Notes.md", bm / "notes.txt",
                      mba / "2026-11-04_lecture.pdf"):
                f.write_text("x")
                os.utime(f, (old, old))
            fresh = bm / "2026-11-05_Executive_Leadership_Notes.md"
            fresh.write_text("still syncing")
            moved = run.sort_dated_files(inbox, ["BusinessMentor"], settle_minutes=3)
            self.assertEqual(moved, ["BusinessMentor_DailyLeadershipReadings/2026-11-04/"
                                     "2026-11-04_Executive_Leadership_Notes.md"])
            self.assertTrue((bm / "2026-11-04" / "2026-11-04_Executive_Leadership_Notes.md").exists())
            self.assertTrue((bm / "notes.txt").exists())                     # no date: left alone
            self.assertTrue(fresh.exists())                                  # still syncing: next run
            self.assertTrue((mba / "2026-11-04_lecture.pdf").exists())       # lecture course untouched


    def test_linkedin_posts_sorted_by_date_in_name_or_file_date(self):
        with tempfile.TemporaryDirectory() as d:
            inbox = Path(d)
            li = inbox / "LinkedIn_MyPosts"
            li.mkdir()
            old = time.mktime((2026, 11, 3, 12, 0, 0, 0, 0, -1))
            for f in (li / "2026-11-01_ai-risk.md", li / "board post.md"):
                f.write_text("x")
                os.utime(f, (old, old))
            moved = run.sort_dated_files(inbox, ["LinkedIn"], 3, mtime_courses=["LinkedIn"])
            self.assertEqual(sorted(moved), ["LinkedIn_MyPosts/2026-11-01/2026-11-01_ai-risk.md",
                                             "LinkedIn_MyPosts/2026-11-03/board post.md"])

    def test_post_mode_prompt_and_no_quiz(self):
        cfg = {}
        self.assertTrue(generate.post_mode("LINKEDIN", cfg))
        self.assertFalse(generate.post_mode("BUSINESSMENTOR", cfg))
        msg = generate.build_user_message("LINKEDIN", "2026-11-14", "2026-11-14", "post.md", "", "reading", set(), "text",
                                          quiz=False, reading=False, post=True)
        self.assertIn("MODE: MY LINKEDIN POST", msg)
        self.assertIn("My public position", msg)


if __name__ == "__main__":
    unittest.main()
