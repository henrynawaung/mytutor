"""Tests for review_core.py and review_app.py (Flask test client, temporary vault)."""

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import review_core as core  # noqa: E402

try:
    import flask  # noqa: F401
    from werkzeug.security import generate_password_hash
    import review_app  # noqa: E402
    HAVE_FLASK = True
except ImportError:
    HAVE_FLASK = False

CORE = "---\ntype: core\ncourse: MBAM601\ncreated: 2026-10-01\nstatus: unreviewed\n---\n# Disruption\nText [[Kodak]].\n"
HUB = CORE.replace("# Disruption", "# Hub").replace("type: core", "type: hub") + "\n## My take\n\n**In my own words:**\n\n## Next\nx\n"
JOURNAL = ("---\ntype: theme\ncourse: BusinessMentor\n---\n# J\n\n**1. Where is silence hiding disagreement?**\n\n"
           "My answer:\n\n**2. Second?**\n\nMy answer:\n")


class CoreTests(unittest.TestCase):
    def test_set_props_keeps_other_lines(self):
        t = core.set_props(CORE, {"status": "reviewed", "reviewed_on": "2026-11-04"})
        self.assertIn("status: reviewed\n", t)
        self.assertIn("reviewed_on: 2026-11-04\n---", t)
        self.assertIn("created: 2026-10-01", t)
        self.assertTrue(t.endswith("Text [[Kodak]].\n"))

    def test_take_goes_under_existing_section_or_new_one(self):
        t = core.add_take(HUB, "Seen this at work", "2026-11-04")
        self.assertIn("**In my own words:**\n\n### 2026-11-04\n\nSeen this at work\n\n## Next", t)
        t2 = core.add_take(CORE, "First para.\r\n\r\n- point one\n- point two\n1. step", "2026-11-04")
        self.assertTrue(t2.endswith("## My take\n\n### 2026-11-04\n\nFirst para.\n\n- point one\n- point two\n1. step\n"))

    def test_list_edit_and_delete_takes(self):
        t = core.add_take(core.add_take(HUB, "First\n- a", "2026-11-04"), "Second", "2026-11-05")
        ts = core.list_takes(t)
        self.assertEqual([(x["date"], x["body"]) for x in ts], [("2026-11-04", "First\n- a"), ("2026-11-05", "Second")])
        t2 = core.replace_take(t, 0, "First, improved")
        self.assertEqual([x["body"] for x in core.list_takes(t2)], ["First, improved", "Second"])
        self.assertIn("## Next\nx", t2)                                   # the section after stays
        t3 = core.replace_take(t2, 1, "")
        self.assertEqual([x["date"] for x in core.list_takes(t3)], ["2026-11-04"])
        self.assertNotIn("My take", core.strip_take_section(t3))
        self.assertIn("## Next", core.strip_take_section(t3))
        bare = core.replace_take(core.add_take(CORE, "Only one", "2026-11-04"), 0, "")
        self.assertNotIn("## My take", bare)                                # empty section removed
        self.assertTrue(bare.startswith(CORE.rstrip("\n")))

    def test_big_headings_inside_a_take_do_not_break_the_section(self):
        take = "Intro\n\n## **Classify → Align**\n\n### **1. Classify**\ntext\n\n#### 🧠 Memory line\nLine"
        t = core.add_take(HUB, take, "2026-11-12")
        ts = core.list_takes(t)
        self.assertEqual(len(ts), 1)
        self.assertIn("#### **Classify → Align**", ts[0]["body"])
        self.assertIn("### **1. Classify**", ts[0]["body"])
        self.assertIn("## Next\nx", t)

    def test_week_streak(self):
        from datetime import date
        thu = date(2026, 11, 12)                       # Thursday
        self.assertEqual(core.week_streak({"2026-11-10", "2026-11-04", "2026-10-28"}, thu), 3)
        self.assertEqual(core.week_streak({"2026-11-04", "2026-10-28"}, thu), 2)      # quiet week so far: not broken
        self.assertEqual(core.week_streak({"2026-10-28"}, thu), 0)                    # a whole week missed
        self.assertEqual(core.week_streak(set(), thu), 0)

    def test_prompts_and_answer(self):
        ps = core.prompts(JOURNAL)
        self.assertEqual([p["question"] for p in ps], ["Where is silence hiding disagreement?", "Second?"])
        t = core.answer_prompt(JOURNAL, 1, "Only in budget meetings")
        self.assertEqual([p["answer"] for p in core.prompts(t)], ["", "Only in budget meetings"])
        with self.assertRaises(ValueError):
            core.answer_prompt(JOURNAL, 5, "x")

    def test_multi_line_answer_kept_and_counted(self):
        t = core.answer_prompt(JOURNAL, 0, "Two things:\n\n- budget meetings\n- board prep")
        self.assertIn("My answer:\n\nTwo things:\n\n- budget meetings\n- board prep\n\n**2. Second?**", t)
        ps = core.prompts(t)
        self.assertEqual(ps[0]["answer"], "Two things:\n\n- budget meetings\n- board prep")
        self.assertEqual(ps[1]["answer"], "")
        t = core.answer_prompt(t, 0, "Changed my mind")           # re-answering replaces, not appends
        self.assertEqual([p["answer"] for p in core.prompts(t)], ["Changed my mind", ""])
        self.assertIn("**2. Second?**", t)


@unittest.skipUnless(HAVE_FLASK, "needs flask")
class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name)
        self.vault, self.jobs = r / "MBA", r / "jobs"
        for rel, text in {"C/Day 1/Core/Disruption.md": CORE, "C/Day 1/Core/Kodak.md": CORE.replace("Disruption", "Kodak"),
                          "B/2026-11-01/J.md": JOURNAL}.items():
            p = self.vault / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        core.Store(self.jobs / "mytutor.db").add_user("henry@example.com", generate_password_hash("correct horse battery"))
        self.app = review_app.create_app(self.vault, self.jobs, "henry_mba", testing=True)
        self.c = self.app.test_client()

    def tearDown(self):
        self.app.store.db.close()
        self.tmp.cleanup()

    def csrf(self, path="/login"):
        return re.search(r'name="csrf" (?:value|content)="([^"]+)"', self.c.get(path).get_data(as_text=True)).group(1)

    def login(self, pw="correct horse battery"):
        return self.c.post("/login", data={"username": "Henry@Example.com", "password": pw, "csrf": self.csrf()})

    def api_csrf(self):
        return re.search(r'<meta name="csrf" content="([^"]+)"', self.c.get("/").get_data(as_text=True)).group(1)

    def test_stretch_endpoint(self):
        self.login(); tok = self.api_csrf()
        self.assertEqual(self.c.get("/api/summary").get_json()["weekly_extra"], 0)
        r = self.c.post("/api/stretch", json={"step": 5}, headers={"X-CSRF": tok})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["weekly_extra"], 5)
        self.assertEqual(self.c.get("/api/summary").get_json()["weekly_extra"], 5)
        r = self.c.post("/api/prefs", json={"weekly_goal": 30}, headers={"X-CSRF": tok})
        self.assertEqual(r.status_code, 200)

    def test_pages_need_login(self):
        self.assertEqual(self.c.get("/").status_code, 302)
        self.assertEqual(self.c.get("/api/summary").status_code, 401)

    def test_login_without_csrf_is_refused(self):
        self.assertEqual(self.c.post("/login", data={"username": "henry@example.com", "password": "x"}).status_code, 403)

    def test_wrong_password_and_lockout(self):
        for _ in range(5):
            self.assertIn(b"Wrong email or password", self.login("nope").data)
        r = self.login()                                     # right password, but locked now
        self.assertIn(b"Too many attempts", r.data)

    def test_review_flow_writes_markdown_and_db(self):
        self.assertEqual(self.login().status_code, 302)
        tok = self.api_csrf()
        s = self.c.get("/api/summary").get_json()
        self.assertEqual(s["courses"]["MBAM601"], {"reviewed": 0, "total": 2})
        self.assertEqual(s["journals"][0]["open"], 2)
        n = self.c.get("/api/note?rel=C/Day 1/Core/Disruption.md").get_json()
        self.assertEqual(self.c.post("/api/approve", json={"rel": n["rel"], "mtime": n["mtime"]}).status_code, 403)  # no CSRF
        r = self.c.post("/api/approve", json={"rel": n["rel"], "mtime": n["mtime"]}, headers={"X-CSRF": tok})
        self.assertEqual(r.status_code, 200)
        text = (self.vault / n["rel"]).read_text(encoding="utf-8")
        self.assertIn("status: reviewed", text)
        self.assertEqual(self.app.store.q("SELECT status FROM notes WHERE rel=?", (n["rel"],))[0]["status"], "reviewed")
        # stale mtime -> conflict, nothing overwritten
        r = self.c.post("/api/take", json={"rel": n["rel"], "mtime": n["mtime"], "take": "x"}, headers={"X-CSRF": tok})
        self.assertEqual(r.status_code, 409)
        n2 = r.get_json()
        n2 = self.c.get("/api/note?rel=C/Day 1/Core/Disruption.md").get_json()
        r = self.c.post("/api/take", json={"rel": n2["rel"], "mtime": n2["mtime"], "take": "My view"}, headers={"X-CSRF": tok})
        self.assertIn("My view", (self.vault / n["rel"]).read_text(encoding="utf-8"))
        j = self.c.get("/api/note?rel=B/2026-11-01/J.md").get_json()
        r = self.c.post("/api/answer", json={"rel": j["rel"], "mtime": j["mtime"], "i": 0, "answer": "Budget talks"},
                        headers={"X-CSRF": tok})
        self.assertIn("My answer: Budget talks", (self.vault / j["rel"]).read_text(encoding="utf-8"))
        acts = [a["action"] for a in self.c.get("/api/recent").get_json()]
        self.assertEqual(acts, ["answer", "my-take", "approve"])
        self.assertEqual(self.c.get("/api/summary").get_json()["stats"]["today"], 3)

    def test_timestamp_survives_a_browser_round_trip(self):
        # browsers turn big JSON numbers into doubles; the timestamp must travel as text
        self.login()
        n = self.c.get("/api/note?rel=C/Day 1/Core/Kodak.md").get_json()
        self.assertIsInstance(n["mtime"], str)
        r = self.c.post("/api/approve", json={"rel": n["rel"], "mtime": n["mtime"]}, headers={"X-CSRF": self.api_csrf()})
        self.assertEqual(r.status_code, 200)

    def test_undo_puts_status_back(self):
        self.login()
        tok = self.api_csrf()
        n = self.c.get("/api/note?rel=C/Day 1/Core/Kodak.md").get_json()
        n = self.c.post("/api/approve", json={"rel": n["rel"], "mtime": n["mtime"]}, headers={"X-CSRF": tok}).get_json()["note"]
        r = self.c.post("/api/undo", json={"rel": n["rel"], "mtime": n["mtime"], "status": "unreviewed"}, headers={"X-CSRF": tok})
        text = (self.vault / n["rel"]).read_text(encoding="utf-8")
        self.assertIn("status: unreviewed", text)
        self.assertNotIn("reviewed_on", text)
        bad = self.c.post("/api/undo", json={"rel": n["rel"], "mtime": r.get_json()["note"]["mtime"], "status": "evil"},
                          headers={"X-CSRF": tok})
        self.assertEqual(bad.status_code, 400)

    def test_days_summary_and_day_detail(self):
        self.login()
        tok = self.api_csrf()
        n = self.c.get("/api/note?rel=C/Day 1/Core/Kodak.md").get_json()
        n = self.c.post("/api/take", json={"rel": n["rel"], "mtime": n["mtime"], "take": "- my point"},
                        headers={"X-CSRF": tok}).get_json()["note"]
        self.c.post("/api/approve", json={"rel": n["rel"], "mtime": n["mtime"]}, headers={"X-CSRF": tok})
        d = self.c.get("/api/days").get_json()["days"][0]
        self.assertEqual((d["approve"], d["my-take"], d["notes"], d["types"], d["no_take"]), (1, 1, 1, {"core": 1}, 0))
        items = self.c.get("/api/day?d=" + d["day"]).get_json()
        self.assertEqual(items[0]["title"], "Kodak")
        self.assertEqual([a["action"] for a in items[0]["actions"]], ["my-take", "approve"])
        self.assertEqual(items[0]["actions"][0]["detail"], "- my point")
        self.assertTrue(items[0]["has_take"])
        k = self.c.get("/api/note?rel=C/Day 1/Core/Kodak.md").get_json()
        again = self.c.post("/api/approve", json={"rel": k["rel"], "mtime": k["mtime"]}, headers={"X-CSRF": tok}).get_json()
        self.assertTrue(again.get("already"))
        self.assertEqual(self.c.get("/api/days").get_json()["days"][0]["approve"], 1)    # approving twice counts once
        m = self.c.get("/api/note?rel=C/Day 1/Core/Disruption.md").get_json()
        self.c.post("/api/approve", json={"rel": m["rel"], "mtime": m["mtime"]}, headers={"X-CSRF": tok})
        self.assertEqual(self.c.get("/api/days").get_json()["days"][0]["no_take"], 1)
        noted = {i["title"]: i["has_take"] for i in self.c.get("/api/day?d=" + d["day"]).get_json()}
        self.assertEqual(noted, {"Kodak": True, "Disruption": False})
        self.assertEqual(self.c.get("/api/day?d=../x").status_code, 400)

    def test_journal_context(self):
        p = self.vault / "B" / "2026-11-01" / "J.md"
        p.write_text(JOURNAL.replace("# J\n", "# J\n\n## This day's notes\n- Reference: [[Kodak]]\n- Core: [[Disruption]], [[Missing One]]\n- Cases: (none)\n"),
                     encoding="utf-8")
        (self.vault / "B" / "Boardroom English Phrasebook.md").write_text(
            "# P\n- **Staged commitment**: fund in steps. *(2026-11-01, [[Kodak]])*\n- **Other**: x. *(2026-10-10, [[Y]])*\n", encoding="utf-8")
        self.app.store.sync(self.app.vault)
        self.login()
        c = self.c.get("/api/context?rel=B/2026-11-01/J.md").get_json()
        self.assertEqual(c["reference"][0]["title"], "Kodak")
        self.assertIn("Text [[Kodak]]", c["reference"][0]["body"].replace("Disruption", "Kodak"))
        self.assertEqual([x["title"] for x in c["core"]], ["Disruption", "Missing One"])
        self.assertIsNone(c["core"][1]["rel"])
        self.assertEqual(c["phrases"], [{"phrase": "Staged commitment", "meaning": "fund in steps."}])

    def test_background_photo_upload_checks_type(self):
        import io
        self.login()
        tok = self.api_csrf()
        self.assertEqual(self.c.get("/api/background").status_code, 404)
        bad = self.c.post("/api/background", data={"photo": (io.BytesIO(b"<svg>"), "x.svg")}, headers={"X-CSRF": tok},
                          content_type="multipart/form-data")
        self.assertEqual(bad.status_code, 400)
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
        ok = self.c.post("/api/background", data={"photo": (io.BytesIO(png), "family.png")}, headers={"X-CSRF": tok},
                         content_type="multipart/form-data")
        self.assertEqual(ok.status_code, 200)
        r = self.c.get("/api/background")
        self.assertEqual((r.status_code, r.mimetype, r.data), (200, "image/png", png))
        self.assertEqual(self.c.post("/api/background", data={}, content_type="multipart/form-data").status_code, 403)  # no CSRF
        self.c.post("/api/background/remove", json={}, headers={"X-CSRF": tok})
        self.assertEqual(self.c.get("/api/background").status_code, 404)

    def test_take_written_in_obsidian_is_counted_once(self):
        import os, time
        p = self.vault / "C/Day 1/Core/Kodak.md"
        p.write_text(CORE.replace("Disruption", "Kodak") + "\n## My take\n\n### 2026-11-04\n\n#### 📖 Where\nMy words\n", encoding="utf-8")
        os.utime(p, ns=(time.time_ns(), time.time_ns() + 10**9))
        store = self.app.store
        store.sync(self.app.vault)
        rows = store.q("SELECT action, detail, user FROM activity WHERE rel=?", ("C/Day 1/Core/Kodak.md",))
        self.assertEqual([(r["action"], r["user"]) for r in rows], [("my-take", "obsidian")])
        self.assertIn("My words", rows[0]["detail"])
        os.utime(p, ns=(time.time_ns(), time.time_ns() + 2 * 10**9))
        store.sync(self.app.vault)                                     # changed again, same entry: not counted twice
        self.assertEqual(len(store.q("SELECT 1 FROM activity WHERE rel=?", ("C/Day 1/Core/Kodak.md",))), 1)

    def test_existing_obsidian_take_counted_at_start_up(self):
        p = self.vault / "C/Day 1/Core/Kodak.md"
        p.write_text(CORE.replace("Disruption", "Kodak") + "\n## My take\n\n### 2026-11-04\n\nWritten in Obsidian\n", encoding="utf-8")
        self.app.store.sync(self.app.vault)                  # indexed before the import existed...
        self.app.store.x("DELETE FROM activity")
        self.assertEqual(self.app.store.import_all_takes(self.app.vault), 1)   # ...still picked up at start-up
        self.assertEqual(self.app.store.import_all_takes(self.app.vault), 0)   # and only once

    def test_edit_and_delete_take_via_api(self):
        self.login()
        tok = self.api_csrf()
        n = self.c.get("/api/note?rel=C/Day 1/Core/Kodak.md").get_json()
        n = self.c.post("/api/take", json={"rel": n["rel"], "mtime": n["mtime"], "take": "Wrong note"}, headers={"X-CSRF": tok}).get_json()["note"]
        n = self.c.post("/api/approve", json={"rel": n["rel"], "mtime": n["mtime"]}, headers={"X-CSRF": tok}).get_json()["note"]
        self.assertEqual([x["body"] for x in n["takes"]], ["Wrong note"])
        self.assertNotIn("My take", n["body"])
        e = self.c.post("/api/take-edit", json={"rel": n["rel"], "mtime": n["mtime"], "i": 0, "body": "Better"}, headers={"X-CSRF": tok}).get_json()
        self.assertEqual(e["note"]["takes"][0]["body"], "Better")
        d = self.c.post("/api/take-edit", json={"rel": n["rel"], "mtime": e["note"]["mtime"], "i": 0, "body": ""}, headers={"X-CSRF": tok}).get_json()
        self.assertEqual(d["note"]["takes"], [])
        u = self.c.post("/api/undo", json={"rel": n["rel"], "mtime": d["note"]["mtime"], "status": "unreviewed"}, headers={"X-CSRF": tok})
        day = self.c.get("/api/days").get_json()["days"][0]
        self.assertEqual((day["approve"], day["my-take"]), (0, 0))            # deleted take and undone approval no longer count

    def test_profile_photo(self):
        import io
        self.login()
        tok = self.api_csrf()
        self.assertEqual(self.c.get("/api/avatar").status_code, 404)
        jpg = b"\xff\xd8\xff\xe0" + b"0" * 50
        r = self.c.post("/api/avatar", data={"photo": (io.BytesIO(jpg), "me.jpg")}, headers={"X-CSRF": tok}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.get("/api/avatar").mimetype, "image/jpeg")
        self.assertEqual(self.c.get("/api/background").status_code, 404)          # separate from the background photo

    def test_paths_outside_vault_are_refused(self):
        self.login()
        self.assertEqual(self.c.get("/api/note?rel=../jobs/mytutor.db").status_code, 404)

    def test_create_user_needs_an_email(self):
        cfg = Path(self.tmp.name) / "config.json"
        cfg.write_text('{"vault_path": "%s", "jobs_root": "%s"}' % (self.vault.as_posix(), self.jobs.as_posix()))
        self.assertEqual(review_app.main(["--config", str(cfg), "--create-user", "henry"]), 1)

    def test_security_headers(self):
        h = self.c.get("/login").headers
        self.assertEqual(h["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", h["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()


def test_memory_lines_in():
    t = "#### 🧠 Memory line: one line to remember\n- **Culture eats strategy.**\n\n**Memory line:** Alignment before speed.\n"
    assert core.memory_lines_in(t) == ["Culture eats strategy.", "Alignment before speed."]
    assert core.memory_lines_in("#### 🧠 Memory line: one line to remember\n\n#### Next") == []


def test_best_week_streak():
    assert core.best_week_streak([]) == 0
    assert core.best_week_streak(["2026-10-20", "2026-11-02", "2026-11-10"]) == 2   # weeks 45+46 in a row
    assert core.best_week_streak(["2026-11-02", "2026-11-03"]) == 1


def test_weekly_goal_prefs(tmp_path):
    assert core.weekly_goal(tmp_path) == 25
    core.save_prefs(tmp_path, {"weekly_goal": 30})
    assert core.weekly_goal(tmp_path) == 30
    import launcher
    assert launcher.weekly_goal_of(tmp_path) == 30


def test_stretch_resets_each_week(tmp_path, monkeypatch):
    from datetime import date as _d
    assert core.weekly_extra(tmp_path) == 0
    assert core.add_stretch(tmp_path) == 5 and core.add_stretch(tmp_path) == 10
    assert core.weekly_extra(tmp_path) == 10
    core.save_prefs(tmp_path, {"stretch": {"week": "2000-W01", "extra": 10}})     # an old week
    assert core.weekly_extra(tmp_path) == 0
    import launcher
    assert launcher.weekly_extra_of(tmp_path) == 0
