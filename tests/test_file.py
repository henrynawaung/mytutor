"""Tests for file.py."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import file as filer  # noqa: E402


def write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


REF = "---\ntype: reference\ncourse: MBAM601\ncreated: 2026-10-17\n---\n# Kodak\nOriginal document: [x](file:///C:/x.pdf)\n"
CORE = "---\ntype: core\ncourse: MBAM601\ncreated: 2026-10-17\n---\n# Disruption\n**Source:** [[MBAM601 Day 1 - Kodak]] [[Value proposition]]\n"


class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.jobs = root / "jobs"
        self.job = self.jobs / "job1"
        (self.job).mkdir(parents=True)
        (self.job / "manifest.json").write_text(json.dumps(
            {"folder": "MBAM601_DigitalTransformationAndTechnologyPreparedness/Day 1"}))
        (self.job / "generate.json").write_text("{}")
        n = self.job / "notes"
        write(n / "reference" / "MBAM601 Day 1 - Kodak.md", REF)
        write(n / "core" / "Disruption.md", CORE)
        write(n / "quizzes" / "Quiz - MBAM601 Day 1 - Kodak.md", "---\ntype: quiz\ncourse: MBAM601\ncreated: x\n---\nQ")
        write(n / "theme" / "MBAM601 Day 1 - Journal.md", "journal")
        self.vault = root / "MBA"
        write(self.vault / "MBAM622-26T3 - Marketing and Strategic Intelligence" / "Day 2" / "Core" / "Value proposition.md", "vp")
        self.cfg = {"term_label": "26T3"}

    def tearDown(self):
        self.tmp.cleanup()

    def target(self):
        return self.vault / "MBAM601-26T3 - Digital Transformation and Technology Preparedness"

    def test_course_folder_name_and_vault_folders(self):
        res = filer.file_job(self.job, self.vault, self.cfg, self.jobs)
        self.assertEqual(Path(res["course_folder"]), self.target())
        day = self.target() / "Day 1"
        self.assertTrue((day / "Ref" / "MBAM601 Day 1 - Kodak.md").exists())
        self.assertTrue((day / "Core" / "Disruption.md").exists())
        self.assertTrue((day / "Quizzes" / "Quiz - MBAM601 Day 1 - Kodak.md").exists())
        self.assertTrue((day / "MBAM601 Day 1 - Journal.md").exists())
        self.assertEqual(len(res["filed"]), 4)

    def test_existing_course_folder_is_reused(self):
        (self.vault / "MBAM601 Digital").mkdir()
        res = filer.file_job(self.job, self.vault, self.cfg, self.jobs)
        self.assertEqual(Path(res["course_folder"]).name, "MBAM601 Digital")

    def test_dry_run_writes_nothing(self):
        res = filer.file_job(self.job, self.vault, self.cfg, self.jobs, dry_run=True)
        self.assertEqual(len(res["filed"]), 4)
        self.assertFalse(self.target().exists())
        self.assertFalse((self.jobs / "filed.json").exists())

    def test_edits_are_never_overwritten(self):
        filer.file_job(self.job, self.vault, self.cfg, self.jobs)
        mine = self.target() / "Day 1" / "Core" / "Disruption.md"
        mine.write_text(CORE + "\nMy own thoughts.", encoding="utf-8")
        write(self.job / "notes" / "core" / "Disruption.md", CORE + "\nregenerated")
        write(self.job / "notes" / "reference" / "MBAM601 Day 1 - Kodak.md", REF + "\nregenerated")
        res = filer.file_job(self.job, self.vault, self.cfg, self.jobs)
        self.assertIn("My own thoughts.", mine.read_text(encoding="utf-8"))
        self.assertEqual([Path(r).name for r in res["kept_yours"]], ["Disruption.md"])
        self.assertEqual([Path(r).name for r in res["updated"]], ["MBAM601 Day 1 - Kodak.md"])
        self.assertEqual(len(res["unchanged"]), 2)

    def test_note_you_wrote_yourself_is_kept(self):
        write(self.target() / "Day 1" / "MBAM601 Day 1 - Journal.md", "my real journal")
        res = filer.file_job(self.job, self.vault, self.cfg, self.jobs)
        self.assertEqual(len(res["kept_yours"]), 1)
        self.assertEqual((self.target() / "Day 1" / "MBAM601 Day 1 - Journal.md").read_text(), "my real journal")

    def test_sample_with_automatic_checks(self):
        filer.file_job(self.job, self.vault, self.cfg, self.jobs)
        rows = filer.pick_sample(self.job, self.vault, self.jobs, n=10, seed=1)
        self.assertEqual(len(rows), 3)                                   # journal excluded
        core = next(r for r in rows if r["note"] == "Disruption")
        self.assertEqual((core["frontmatter_complete"], core["links_to_source"], core["links_to_existing_note"]),
                         ("yes", "yes", "yes"))
        self.assertEqual(core["accurate"], "")
        ref = next(r for r in rows if r["note"] == "MBAM601 Day 1 - Kodak")
        self.assertEqual(ref["links_to_source"], "yes")
        self.assertEqual(len(filer.pick_sample(self.job, self.vault, self.jobs, n=2, seed=1)), 2)

    def test_sample_by_type_covers_each_type_and_repeats(self):
        filer.file_job(self.job, self.vault, self.cfg, self.jobs)
        index = json.loads((self.jobs / "filed.json").read_text())
        kinds = {v["kind"] for v in index.values() if v["kind"] != "theme"}
        rows = filer.pick_sample(self.job, self.vault, self.jobs, n=len(kinds), seed=7, by_type=True)
        self.assertEqual({index[r["folder"]]["kind"] for r in rows}, kinds)   # one of each type
        again = filer.pick_sample(self.job, self.vault, self.jobs, n=len(kinds), seed=7, by_type=True)
        self.assertEqual([r["note"] for r in rows], [r["note"] for r in again])  # same seed, same sample

    def test_cli_files_and_samples(self):
        cfg = Path(self.tmp.name) / "config.json"
        cfg.write_text(json.dumps({"vault_path": str(self.vault), "jobs_root": str(self.jobs), "term_label": "26T3"}))
        self.assertEqual(filer.main(["--config", str(cfg), "--job", "job1", "--sample", "2", "--seed", "3"]), 0)
        with (self.jobs / "quality_audit.csv").open(newline="", encoding="utf-8") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 2)
        with (self.jobs / "file_runs.csv").open(newline="", encoding="utf-8") as f:
            self.assertEqual(list(csv.DictReader(f))[0]["filed"], "4")

    def test_one_folder_set_per_course_option(self):
        self.cfg["day_folders"] = False
        self.cfg["vault_folders"] = {"theme": "Theme"}
        filer.file_job(self.job, self.vault, self.cfg, self.jobs)
        self.assertTrue((self.target() / "Core" / "Disruption.md").exists())
        self.assertTrue((self.target() / "Theme" / "MBAM601 Day 1 - Journal.md").exists())

    def test_obsidian_link_includes_subfolder_of_real_vault(self):
        (self.vault.parent / ".obsidian").mkdir()
        root = filer.obsidian_root(self.vault)
        self.assertEqual(root, self.vault.parent)
        link = filer.obsidian_link("henry_mba", "MBAM601 X/Day 1/Core/A.md", self.vault.relative_to(root).as_posix())
        self.assertEqual(link, "obsidian://open?vault=henry_mba&file=MBA/MBAM601%20X/Day%201/Core/A")

    def test_pretty_course_name(self):
        self.assertEqual(filer.pretty_course_name("MBAM601_DigitalTransformationAndTechnologyPreparedness"),
                         "Digital Transformation and Technology Preparedness")


if __name__ == "__main__":
    unittest.main()
