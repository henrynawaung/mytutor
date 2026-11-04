"""Tests for apply_vault_changes.py."""
import hashlib, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import apply_vault_changes as av  # noqa: E402


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name)
        self.vault, self.jobs = r / "MBA", r / "jobs"
        (self.vault / "C").mkdir(parents=True); self.jobs.mkdir()
        (self.vault / "C" / "a.md").write_text("old a", encoding="utf-8")
        (self.vault / "C" / "b .md").write_text("old b", encoding="utf-8")
        h = lambda t: hashlib.sha256(t.encode()).hexdigest()
        self.ch = {"renames": [{"from": "C/b .md", "to": "C/b.md", "sha256": h("old b")}],
                   "edits": [{"path": "C/a.md", "sha256": h("old a"), "content": "new a"},
                             {"path": "C/b.md", "sha256": None, "content": "new b"}],
                   "new": [{"path": "Hubs/h.md", "content": "hub"}]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_then_undo(self):
        c = av.apply(self.vault, self.jobs, self.ch)
        self.assertEqual(c, {"renames": 1, "edits": 2, "new": 1, "skipped": 0})
        self.assertEqual((self.vault / "C" / "b.md").read_text(), "new b")
        self.assertEqual((self.vault / "Hubs" / "h.md").read_text(), "hub")
        self.assertEqual(av.apply(self.vault, self.jobs, self.ch)["skipped"], 4)   # second run does nothing
        av.undo(self.vault, self.jobs)
        self.assertEqual((self.vault / "C" / "a.md").read_text(), "old a")
        self.assertEqual((self.vault / "C" / "b .md").read_text(), "old b")
        self.assertFalse((self.vault / "C" / "b.md").exists())
        self.assertFalse((self.vault / "Hubs").exists())

    def test_note_edited_since_is_kept(self):
        (self.vault / "C" / "a.md").write_text("my edit", encoding="utf-8")
        c = av.apply(self.vault, self.jobs, self.ch)
        self.assertEqual(c["skipped"], 1)
        self.assertEqual((self.vault / "C" / "a.md").read_text(), "my edit")

    def test_dry_run_writes_nothing(self):
        av.apply(self.vault, self.jobs, self.ch, dry_run=True)
        self.assertFalse((self.vault / "Hubs").exists())
        self.assertEqual(list(self.jobs.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
