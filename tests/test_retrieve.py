"""Tests for retrieve.py. Run from the mytutor folder:  python -m unittest discover tests"""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import retrieve  # noqa: E402


def read_runs(jobs: Path) -> list:
    with (jobs / "runs.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def make_inbox(root: Path) -> Path:
    day = root / "Inbox" / "Day 1"
    (day / "Readings").mkdir(parents=True)
    (day / "Lecture 1.pdf").write_bytes(b"%PDF-1.4 lecture one")
    (day / "Readings" / "Case - Kodak.docx").write_bytes(b"docx bytes")
    (day / "slides.pptx").write_bytes(b"pptx bytes")
    (day / "~$slides.pptx").write_bytes(b"office lock file")
    (day / "desktop.ini").write_text("[.ShellClassInfo]")
    (day / "setup.exe").write_bytes(b"MZ")
    return root / "Inbox"


class SyncedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.inbox = make_inbox(root)
        self.jobs = root / "jobs"
        self.source = retrieve.SyncedSource(self.inbox, settle_seconds=0)

    def tearDown(self):
        self.tmp.cleanup()

    def run_once(self, **kw):
        return retrieve.retrieve(self.source, "Day 1", self.jobs, **kw)

    def test_first_run_copies_supported_files_and_keeps_subfolders(self):
        r = self.run_once(run_id="run1")
        self.assertEqual(r.count("retrieved"), 3)
        self.assertEqual(r.count("skipped_type"), 1)              # setup.exe
        names = {e.rel_path for e in r.entries}
        self.assertNotIn("~$slides.pptx", names)                  # lock files ignored
        self.assertNotIn("desktop.ini", names)
        copied = self.jobs / "run1" / "source" / "Readings" / "Case - Kodak.docx"
        self.assertEqual(copied.read_bytes(), b"docx bytes")

    def test_manifest_index_and_run_log(self):
        self.run_once(run_id="run1")
        manifest = json.loads((self.jobs / "run1" / "manifest.json").read_text())
        self.assertEqual(manifest["mode"], "synced")
        pdf = next(f for f in manifest["files"] if f["rel_path"] == "Lecture 1.pdf")
        self.assertEqual(len(pdf["sha256"]), 64)
        self.assertTrue(pdf["origin"].endswith("Lecture 1.pdf"))
        index = json.loads((self.jobs / "index.json").read_text())
        self.assertEqual(len(index["sha256"]), 3)
        rows = read_runs(self.jobs)
        self.assertEqual(rows[0]["retrieved"], "3")

    def test_second_run_skips_duplicates(self):
        self.run_once(run_id="run1")
        r = self.run_once(run_id="run2")
        self.assertEqual(r.count("retrieved"), 0)
        self.assertEqual(r.count("skipped_duplicate"), 3)
        self.assertFalse((self.jobs / "run2" / "source").exists())
        rows = read_runs(self.jobs)
        self.assertEqual(len(rows), 2)

    def test_changed_file_is_retrieved_again(self):
        self.run_once(run_id="run1")
        (self.inbox / "Day 1" / "slides.pptx").write_bytes(b"pptx bytes v2")
        r = self.run_once(run_id="run2")
        self.assertEqual([e.rel_path for e in r.entries if e.status == "retrieved"], ["slides.pptx"])

    def test_force_and_dry_run(self):
        self.run_once(run_id="run1")
        self.assertEqual(self.run_once(run_id="run2", force=True).count("retrieved"), 3)
        dry = self.run_once(run_id="run3", dry_run=True)
        self.assertFalse((self.jobs / "run3").exists())
        self.assertEqual(dry.count("retrieved"), 3)

    def test_runs_in_the_same_second_get_separate_job_folders(self):
        first = self.run_once(run_id="same")
        second = self.run_once(run_id="same")
        self.assertEqual(second.run_id, "same-2")
        manifest = json.loads((self.jobs / "same" / "manifest.json").read_text())
        self.assertEqual(sum(f["status"] == "retrieved" for f in manifest["files"]), 3)
        self.assertEqual(first.count("retrieved"), 3)

    def test_size_limit(self):
        r = self.run_once(run_id="run1", max_file_mb=0.000001)
        self.assertEqual(r.count("skipped_size"), 3)

    def test_missing_folder_explains(self):
        with self.assertRaises(FileNotFoundError):
            retrieve.retrieve(self.source, "Day 9", self.jobs)

    def test_unsafe_folder_rejected(self):
        with self.assertRaises(ValueError):
            retrieve.retrieve(self.source, "../secrets", self.jobs)


# ---------------------------------------------------------------- graph mode, with a fake API

class FakeResponse:
    def __init__(self, status=200, payload=None, body=b"", headers=None):
        self.status_code = status
        self._payload = payload
        self._body = body
        self.headers = headers or {}

    def json(self):
        return self._payload

    def iter_content(self, size):
        yield self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise IOError(f"HTTP {self.status_code}")


class FakeSession:
    API = retrieve.GraphSource.API

    def __init__(self):
        self.headers = {}
        self.calls = []
        self.throttled_once = False
        day = f"{self.API}/me/drive/root:/myTutor/Inbox/Day%201:/children"
        sub = f"{self.API}/me/drive/root:/myTutor/Inbox/Day%201/Readings:/children"
        self.routes = {
            day: FakeResponse(payload={
                "value": [
                    {"name": "Lecture 1.pdf", "id": "A", "cTag": "c1", "size": 9, "file": {},
                     "webUrl": "https://uc.sharepoint.com/lecture1",
                     "@microsoft.graph.downloadUrl": "https://dl/A"},
                    {"name": "Readings", "id": "F", "folder": {}},
                ],
                "@odata.nextLink": "https://next-page",
            }),
            "https://next-page": FakeResponse(payload={"value": [
                {"name": "notes.exe", "id": "X", "cTag": "cx", "size": 2, "file": {}},
            ]}),
            sub: FakeResponse(payload={"value": [
                {"name": "Case.docx", "id": "B", "cTag": "c2", "size": 4, "file": {},
                 "webUrl": "https://uc.sharepoint.com/case"},
            ]}),
            "https://dl/A": FakeResponse(body=b"lecture1!"),
            f"{self.API}/me/drive/items/B/content": FakeResponse(body=b"case"),
        }

    def get(self, url, stream=False, timeout=None, headers=None):
        self.calls.append((url, headers))
        if url == "https://dl/A" and not self.throttled_once:
            self.throttled_once = True
            return FakeResponse(status=429, headers={"Retry-After": "0"})
        return self.routes.get(url, FakeResponse(status=404))


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.jobs = Path(self.tmp.name) / "jobs"
        self.session = FakeSession()
        self.source = retrieve.GraphSource("myTutor/Inbox", "TOKEN", session=self.session)

    def tearDown(self):
        self.tmp.cleanup()

    def test_walks_pages_and_folders_and_downloads(self):
        r = retrieve.retrieve(self.source, "Day 1", self.jobs, run_id="g1")
        self.assertEqual(r.count("retrieved"), 2)
        self.assertEqual(r.count("skipped_type"), 1)
        self.assertEqual((self.jobs / "g1" / "source" / "Readings" / "Case.docx").read_bytes(), b"case")
        manifest = json.loads((self.jobs / "g1" / "manifest.json").read_text())
        lecture = next(f for f in manifest["files"] if f["rel_path"] == "Lecture 1.pdf")
        self.assertEqual(lecture["origin"], "https://uc.sharepoint.com/lecture1")
        self.assertEqual(self.session.headers["Authorization"], "Bearer TOKEN")

    def test_presigned_link_sent_without_token(self):
        retrieve.retrieve(self.source, "Day 1", self.jobs, run_id="g1")
        dl_headers = [h for url, h in self.session.calls if url == "https://dl/A"]
        self.assertTrue(all(h == {"Authorization": None} for h in dl_headers))

    def test_unchanged_remote_files_are_not_downloaded_again(self):
        retrieve.retrieve(self.source, "Day 1", self.jobs, run_id="g1")
        self.session.calls.clear()
        r = retrieve.retrieve(self.source, "Day 1", self.jobs, run_id="g2")
        self.assertEqual(r.count("skipped_duplicate"), 2)
        downloaded = [u for u, _ in self.session.calls if u.startswith("https://dl") or u.endswith("/content")]
        self.assertEqual(downloaded, [])


class CliTests(unittest.TestCase):
    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inbox = make_inbox(root)
            cfg = root / "config.json"
            cfg.write_text(json.dumps({
                "mode": "synced", "synced_inbox": str(inbox),
                "jobs_root": str(root / "jobs"), "settle_seconds": 0,
            }))
            self.assertEqual(retrieve.main(["--config", str(cfg), "--folder", "Day 1"]), 0)
            self.assertEqual(len(list((root / "jobs").glob("*/manifest.json"))), 1)
            self.assertEqual(retrieve.main(["--config", str(cfg), "--folder", "Day 2"]), 2)


if __name__ == "__main__":
    unittest.main()
