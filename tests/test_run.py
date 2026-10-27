"""Tests for run.py with a fake Claude client and fake PDFs."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run  # noqa: E402
from tests.test_generate import FakeClient, tool_response, note, quiz  # noqa: E402

try:
    import pymupdf  # noqa: F401
    HAVE_PDF = True
except ImportError:
    HAVE_PDF = False


def make_pdf(path: Path, text: str):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 80, 545, 760), text, fontsize=11)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    old = time.time() - 3600
    os.utime(path, (old, old))                     # "synced an hour ago"


def answer(title):
    return tool_response({"source_title": title, "kind": "reading",
                          "notes": [note("reference", title), note("core", f"Concept from {title}")],
                          "quiz": quiz(f"Concept from {title}")})


@unittest.skipUnless(HAVE_PDF, "needs pymupdf")
class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.inbox = root / "MyTutor"
        make_pdf(self.inbox / "MBAM601_Digital" / "Day 1" / "a.pdf", "Platforms create value. " * 40)
        make_pdf(self.inbox / "MBAM601_Digital" / "Day 1" / "b.pdf", "Disruption starts small. " * 40)
        self.cfg = {"synced_inbox": str(self.inbox), "jobs_root": str(root / "jobs"),
                    "settle_seconds": 0, "settle_minutes": 3}
        self.logs = []

    def tearDown(self):
        self.tmp.cleanup()

    def go(self, client, **kw):
        return run.run(self.cfg, client=client, log=self.logs.append, **kw)

    def test_new_day_is_processed_end_to_end(self):
        s = self.go(FakeClient([answer("A"), answer("B")]))
        self.assertEqual((s["days_processed"], s["sources"], s["status"]), (1, 2, "ok"))
        self.assertTrue((Path(self.cfg["jobs_root"]) / "practice.html").exists())

    def test_second_run_finds_nothing_and_calls_no_one(self):
        self.go(FakeClient([answer("A"), answer("B")]))
        client = FakeClient([])
        s = self.go(client)
        self.assertEqual((s["days_processed"], client.calls), (0, []))
        self.assertIn("No new files.", self.logs)

    def test_file_added_later_is_processed_alone(self):
        self.go(FakeClient([answer("A"), answer("B")]))
        make_pdf(self.inbox / "MBAM601_Digital" / "Day 1" / "c.pdf", "Ecosystems matter. " * 40)
        client = FakeClient([answer("C")])
        s = self.go(client)
        self.assertEqual((s["days_processed"], len(client.calls)), (1, 1))

    def test_syncing_folder_waits(self):
        p = self.inbox / "MBAM601_Digital" / "Day 2" / "new.pdf"
        make_pdf(p, "Fresh. " * 40)
        os.utime(p, None)                                # changed just now
        s = self.go(FakeClient([answer("A"), answer("B")]))
        self.assertEqual(s["days_processed"], 1)          # Day 1 only
        self.assertTrue(any("waiting" in line and "Day 2" in line for line in self.logs))

    def test_dry_run_and_lock(self):
        s = self.go(None, dry_run=True)
        self.assertEqual((s["days_found"], s["days_processed"]), (1, 0))
        lock = Path(self.cfg["jobs_root"]) / ".run.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("x")
        self.assertEqual(self.go(FakeClient([]))["status"], "already running")

    def test_failed_generation_is_reported(self):
        s = self.go(FakeClient([RuntimeError("down"), answer("B")]))
        self.assertEqual((s["status"], s["failed"]), ("some failed", 1))


if __name__ == "__main__":
    unittest.main()


def test_file_new_days_runs_file_py_for_each_processed_day(monkeypatch, tmp_path):
    import subprocess, types
    import run as runmod
    calls = []
    def fake_run(cmd, cwd=None, capture_output=None, text=None):
        calls.append(cmd)
        return types.SimpleNamespace(returncode=0, stdout="filed  x", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    summary = {"failed": 0, "status": "ok", "days": [
        {"folder": "C/Day 2", "job": "j2", "sources": 3},
        {"folder": "C/Day 3", "note": "nothing new after all"}]}
    runmod.file_new_days(summary, tmp_path, tmp_path / "config.json", 10)
    assert len(calls) == 1 and "--job" in calls[0] and "j2" in calls[0]
    assert summary["days_filed"] == 1 and summary["days"][0]["filed"] is True
