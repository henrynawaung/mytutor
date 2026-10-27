"""Tests for generate.py with a fake Claude client (no API calls, no cost)."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate  # noqa: E402


def tool_response(payload, tin=1000, tout=500, stop="tool_use"):
    block = SimpleNamespace(type="tool_use", input=payload)
    return SimpleNamespace(content=[block], usage=SimpleNamespace(input_tokens=tin, output_tokens=tout),
                           stop_reason=stop)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.calls.append(kw)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def note(folder, title, body="", links=()):
    content = f"---\ntype: {folder}\n---\n# {title}\n{body}\n" + " ".join(f"[[{l}]]" for l in links)
    return {"folder": folder, "filename": f"{title}.md", "content": content}


def quiz(concept, n=5):
    return [{"question": f"Q{i} about {concept}?", "options": ["a", "b", "c", "d"], "answer": i % 4,
             "explanation": f"Because of {concept}.", "concept": concept} for i in range(n)]


def make_job(root: Path) -> Path:
    job = root / "jobs" / "job1"
    (job / "text").mkdir(parents=True)
    files = [
        ("Session 1 Slides Final.pdf", "slides", "Digital transformation means rethinking the business model."),
        ("Short Case.pdf", "case", "Kodak invented the digital camera but failed to adapt."),
    ]
    extract_files, manifest_files = [], []
    for rel, kind, text in files:
        tp = f"text/{Path(rel).stem}.md"
        (job / tp).write_text(text, encoding="utf-8")
        extract_files.append({"rel_path": rel, "status": "extracted", "text_path": tp, "kind_guess": kind})
        manifest_files.append({"rel_path": rel, "status": "retrieved",
                               "origin": f"C:\\Users\\henry\\OneDrive\\MyTutor\\MBAM601_X\\Day 1\\{rel}"})
    (job / "extract.json").write_text(json.dumps({"files": extract_files}))
    (job / "manifest.json").write_text(json.dumps({"folder": "MBAM601_DigitalTransformation/Day 1",
                                                   "files": manifest_files}))
    return job


class HelperTests(unittest.TestCase):
    def test_safe_filename(self):
        self.assertEqual(generate.safe_filename('What is DT? A "guide": part 1/2'), "What is DT A guide part 1 2.md")

    def test_file_link(self):
        self.assertEqual(generate.file_link(r"C:\Users\henry\OneDrive\My Tutor\a b.pdf"),
                         "file:///C:/Users/henry/OneDrive/My%20Tutor/a%20b.pdf")
        self.assertEqual(generate.file_link("https://x/y"), "https://x/y")

    def test_parse_folder(self):
        self.assertEqual(generate.parse_folder("MBAM601_DigitalTransformationAndTechnologyPreparedness/Day 1"),
                         ("MBAM601", "Day 1"))


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.job = make_job(self.root)
        self.vault = self.root / "vault"
        (self.vault / "core").mkdir(parents=True)
        (self.vault / "core" / "Business model.md").write_text("# Business model")
        self.cfg = {"vault_path": str(self.vault), "term": "T3"}
        self.log = self.root / "jobs" / "generate_runs.csv"

    def tearDown(self):
        self.tmp.cleanup()

    def responses(self):
        slides = tool_response({"source_title": "Session 1: What is digital transformation", "kind": "slides",
                                "notes": [
                                    note("reference", "MBAM601 Day 1 - Session 1"),
                                    note("core", "Digital transformation", links=["Business model"]),
                                    note("core", "Business model"),          # already in vault: must be skipped
                                ], "quiz": quiz("Digital transformation")}, tin=3000, tout=2000)
        case = tool_response({"source_title": "Kodak", "kind": "case", "notes": [
            note("reference", "MBAM601 Day 1 - Kodak"),
            note("cases", "Kodak - Missing the digital shift", links=["Digital transformation"]),
        ], "quiz": quiz("Not a real note", n=4) + [{"question": "bad", "options": ["x"], "answer": 9,
                                                    "explanation": "", "concept": ""}]}, tin=1500, tout=1200)
        return [slides, case]

    def run_job(self, client, **kw):
        return generate.generate_job(self.job, client, self.cfg, log_path=self.log, **kw)

    def test_full_run_writes_notes_links_and_logs(self):
        client = FakeClient(self.responses())
        report = self.run_job(client)
        notes = self.job / "notes"
        self.assertTrue((notes / "core" / "Digital transformation.md").exists())
        self.assertFalse((notes / "core" / "Business model.md").exists())       # no duplicate of vault note
        self.assertTrue((notes / "cases" / "Kodak - Missing the digital shift.md").exists())
        ref = (notes / "reference" / "MBAM601 Day 1 - Session 1.md").read_text(encoding="utf-8")
        self.assertIn("file:///C:/Users/henry/OneDrive/MyTutor/MBAM601_X/Day%201/Session%201%20Slides%20Final.pdf", ref)
        journal = (notes / "theme" / "MBAM601 Day 1 - Journal.md").read_text(encoding="utf-8")
        self.assertIn("term: T3", journal)
        self.assertIn("[[Kodak - Missing the digital shift]]", journal)
        slides = report["sources"]["Session 1 Slides Final.pdf"]
        self.assertEqual((slides["status"], slides["notes_written"], slides["links_to_existing"]), ("done", 3, 1))
        self.assertAlmostEqual(slides["cost_usd"], 3000 / 1e6 * 2 + 2000 / 1e6 * 10)
        with self.log.open(newline="", encoding="utf-8") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 2)

    def test_quiz_note_and_quiz_data(self):
        self.run_job(FakeClient(self.responses()))
        qnote = self.job / "notes" / "quizzes" / "Quiz - MBAM601 Day 1 - Session 1 What is digital transformation.md"
        text = qnote.read_text(encoding="utf-8")
        self.assertIn("   - D. d", text)
        self.assertIn("> 2. B. Because of Digital transformation. See [[Digital transformation]].", text)
        data = json.loads((self.job / "quiz" / (qnote.stem + ".json")).read_text(encoding="utf-8"))
        self.assertEqual(len(data["questions"]), 5)
        self.assertEqual(data["reference"], "MBAM601 Day 1 - Session 1")
        kodak = (self.job / "notes" / "quizzes" / "Quiz - MBAM601 Day 1 - Kodak.md").read_text(encoding="utf-8")
        self.assertIn("See [[MBAM601 Day 1 - Kodak]]", kodak)          # unknown concept -> reference note
        self.assertNotIn("bad", kodak)                                   # malformed question dropped

    def test_practice_set_built_once_when_day_complete(self):
        report = self.run_job(FakeClient(self.responses()))
        set_path = self.job / "quiz" / "practice-set.json"
        data = json.loads(set_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["questions"]), 9)                     # 5 + 4 valid, fewer than 20
        self.assertEqual({q["concept"] for q in data["questions"][:2]}, {"Digital transformation", "Not a real note"})
        self.assertEqual(report["practice_set"], "quizzes/Practice - MBAM601 Day 1.md")
        note = (self.job / "notes" / "quizzes" / "Practice - MBAM601 Day 1.md").read_text(encoding="utf-8")
        self.assertIn("questions: 9", note)
        before = set_path.read_text(encoding="utf-8")
        self.run_job(FakeClient(self.responses()), force=True)          # regenerating keeps the set
        self.assertEqual(set_path.read_text(encoding="utf-8"), before)
        self.run_job(FakeClient([]), rebuild_set=True)                  # only an explicit rebuild replaces it
        self.assertTrue(set_path.exists())

    def test_practice_set_waits_for_all_sources(self):
        self.run_job(FakeClient(self.responses()[1:]), only="short case")
        self.assertFalse((self.job / "quiz" / "practice-set.json").exists())
        self.run_job(FakeClient(self.responses()[:1]))
        self.assertTrue((self.job / "quiz" / "practice-set.json").exists())

    def test_practice_set_size_from_config(self):
        self.cfg["practice_questions"] = 3
        self.run_job(FakeClient(self.responses()))
        data = json.loads((self.job / "quiz" / "practice-set.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["questions"]), 3)

    def test_slides_go_first_and_later_sources_see_earlier_titles(self):
        client = FakeClient(self.responses())
        self.run_job(client)
        first, second = client.calls
        self.assertIn("SOURCE FILE: Session 1 Slides Final.pdf", first["messages"][0]["content"])
        self.assertIn("- Digital transformation", second["messages"][0]["content"])
        self.assertIn("- Business model", first["messages"][0]["content"])
        self.assertEqual(first["tool_choice"], {"type": "auto"})

    def test_only_rerun_and_force(self):
        client = FakeClient(self.responses()[1:])
        self.run_job(client, only="short case")
        self.assertEqual(len(client.calls), 1)
        again = FakeClient([])
        self.run_job(again, only="short case")                  # already done: no API call
        self.assertEqual(again.calls, [])
        forced = FakeClient(self.responses()[1:])
        self.run_job(forced, only="short case", force=True)
        self.assertEqual(len(forced.calls), 1)
        self.assertTrue((self.job / "notes" / "cases" / "Kodak - Missing the digital shift.md").exists())

    def test_failure_is_recorded_and_others_continue(self):
        client = FakeClient([RuntimeError("overloaded"), self.responses()[1]])
        report = self.run_job(client)
        self.assertEqual(report["sources"]["Session 1 Slides Final.pdf"]["status"], "failed")
        self.assertEqual(report["sources"]["Short Case.pdf"]["status"], "done")

    def test_cut_off_response_is_a_failure(self):
        r = tool_response({"source_title": "x", "kind": "case", "notes": [], "quiz": []}, stop="max_tokens")
        report = self.run_job(FakeClient([r]), only="short case")
        self.assertIn("cut off", report["sources"]["Short Case.pdf"]["error"])

    def test_vault_titles_found_in_course_folders(self):
        course = self.vault / "MBAM622-26T3 - Marketing and Strategic Intelligence"
        (course / "Core").mkdir(parents=True)
        (course / "Ref").mkdir()
        (course / "Ref" / "Kotler Ch1.md").write_text("x")
        (course / "Core" / "Value proposition.md").write_text("# Value proposition")
        (course / "theme").mkdir()
        (course / "theme" / "Week 1 journal.md").write_text("x")
        (self.vault / ".obsidian").mkdir()
        (self.vault / ".obsidian" / "core").mkdir()
        (self.vault / ".obsidian" / "core" / "Plugin.md").write_text("x")
        (self.vault / "Inbox scratch.md").write_text("x")
        titles = generate.vault_titles(self.vault)
        self.assertIn("Value proposition", titles)
        self.assertIn("Kotler Ch1", titles)
        self.assertIn("Business model", titles)
        self.assertIn("Week 1 journal", titles)
        self.assertNotIn("Plugin", titles)
        self.assertNotIn("Inbox scratch", titles)

    def test_journal_lists_notes_from_every_run(self):
        self.run_job(FakeClient(self.responses()[1:]), only="short case")
        self.run_job(FakeClient(self.responses()[:1]), only="slides")
        journal = (self.job / "notes" / "theme" / "MBAM601 Day 1 - Journal.md").read_text(encoding="utf-8")
        self.assertIn("[[Kodak - Missing the digital shift]]", journal)
        self.assertIn("[[Digital transformation]]", journal)

    def test_json_text_fallback(self):
        payload = {"source_title": "Kodak", "kind": "case",
                   "notes": [note("reference", "MBAM601 Day 1 - Kodak")], "quiz": quiz("Kodak")}
        text = SimpleNamespace(type="text", text="Here are the notes:\n```json\n" + json.dumps(payload) + "\n```")
        r = SimpleNamespace(content=[text], usage=SimpleNamespace(input_tokens=10, output_tokens=10), stop_reason="end_turn")
        report = self.run_job(FakeClient([r]), only="short case")
        self.assertEqual(report["sources"]["Short Case.pdf"]["status"], "done")

    def test_no_notes_at_all_is_a_failure(self):
        text = SimpleNamespace(type="text", text="I cannot do that.")
        r = SimpleNamespace(content=[text], usage=SimpleNamespace(input_tokens=10, output_tokens=10), stop_reason="end_turn")
        report = self.run_job(FakeClient([r]), only="short case")
        self.assertIn("expected format", report["sources"]["Short Case.pdf"]["error"])

    def test_estimate_makes_no_calls(self):
        client = FakeClient([])
        self.run_job(client, estimate=True)
        self.assertEqual(client.calls, [])
        self.assertFalse((self.job / "notes").exists())


if __name__ == "__main__":
    unittest.main()


def test_normalise_result_accepts_json_text_fields():
    import json as _j
    from generate import normalise_result
    note = {"folder": "core", "filename": "A.md", "content": "x"}
    q = {"question": "Q?", "options": ["a", "b", "c", "d"], "answer": 0}
    r = normalise_result({"notes": _j.dumps([note]), "quiz": _j.dumps([q]), "source_title": "S"})
    assert r["notes"] == [note] and r["quiz"] == [q]
    r = normalise_result(_j.dumps({"notes": [note, "junk"], "quiz": "not json"}))
    assert r["notes"] == [note] and r["quiz"] == []
    r = normalise_result({"notes": note})
    assert r["notes"] == [note]


def test_normalise_result_rejects_empty():
    import pytest
    from generate import normalise_result
    with pytest.raises(ValueError):
        normalise_result({"notes": "nothing useful"})


def test_practice_set_draws_on_earlier_jobs_for_same_day(tmp_path):
    import json as _j
    from generate import build_practice_set, same_day_jobs
    def job(name, src):
        d = tmp_path / name
        (d / "quiz").mkdir(parents=True)
        (d / "manifest.json").write_text(_j.dumps({"folder": "MBAM601/Day 9"}))
        qs = [{"question": f"{src} q{i}", "options": ["a", "b", "c", "d"], "answer": 0,
               "explanation": "", "concept": f"{src}-c{i}"} for i in range(5)]
        (d / "quiz" / f"{src}.json").write_text(_j.dumps({"source": f"{src}.pdf", "source_title": src, "questions": qs}))
        return d
    first, second = job("a", "Old"), job("b", "New")
    other = tmp_path / "c"; (other / "quiz").mkdir(parents=True)
    (other / "manifest.json").write_text(_j.dumps({"folder": "MBAM601/Day 1"}))
    assert same_day_jobs(second) == [first]
    build_practice_set(second, second / "notes", "MBAM601", "Day 9", "2026-10-22", ["New.pdf"], size=10,
                       other_jobs=same_day_jobs(second))
    data = _j.loads((second / "quiz" / "practice-set.json").read_text())
    assert {q["source"] for q in data["questions"]} == {"Old", "New"}


def test_quiz_note_always_links_its_reference(tmp_path):
    from generate import write_quiz
    q = [{"question": "Q?", "options": ["a", "b", "c", "d"], "answer": 0, "explanation": "x", "concept": "Core A"}]
    out = write_quiz(tmp_path, tmp_path / "quiz", "MBAM601", "Day 2", "2026-10-25", "f.pdf", "Title", "Ref Title",
                     q, {"Core A"})
    text = (tmp_path / out[0]).read_text(encoding="utf-8")
    assert "Source: [[Ref Title]]" in text and "See [[Core A]]" in text
