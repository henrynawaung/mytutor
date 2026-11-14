"""Tests for caselab.py and the Case Lab endpoints (fake Claude client, temporary vault)."""

import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import caselab  # noqa: E402
import review_core as core  # noqa: E402

try:
    from werkzeug.security import generate_password_hash
    import review_app  # noqa: E402
    HAVE_FLASK = True
except ImportError:
    HAVE_FLASK = False

NOTE = "---\ntype: core\ncourse: MBAM601\ncreated: 2026-10-01\nstatus: {st}\n---\n# {t}\n{body}\n"
MD = ("Let me search first.# AI Triage Adoption\n\n## The case\nA hospital group.\n\n## Model answer\n### Recommendation\nPilot first.\n\n"
      "## Questions the board will ask\nQ1\n\n## From your notes\n[[Change Resistance]]\n\n## Additional key points\nX (HBR)\n\n"
      "## Gaps to study\nY\n")


class FakeClient:
    def __init__(self):
        self.calls = []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.calls.append(kw)
        cite = SimpleNamespace(url="https://hbr.org/x", title="HBR on adoption")
        return SimpleNamespace(content=[SimpleNamespace(type="server_tool_use"),
                                        SimpleNamespace(type="text", text=MD, citations=[cite])],
                               usage=SimpleNamespace(input_tokens=12000, output_tokens=3000))


def make_vault(root: Path, reviewed: int, total: int = 4):
    titles = ["Change Resistance", "Clinician Adoption of AI", "Kodak", "Platform Strategy"][:total]
    bodies = ["People resist change when AI triage threatens clinicians' roles.", "Clinicians adopt AI tools when trust is built.",
              "Film camera disruption.", "Two-sided markets."]
    for k, (t, b) in enumerate(zip(titles, bodies)):
        p = root / "MBAM601" / "Day 1" / "Core" / f"{t}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        text = NOTE.format(st="reviewed" if k < reviewed else "unreviewed", t=t, body=b)
        if k == 0:
            text = core.add_take(text, "At Synapxe, resistance dropped once nurses co-designed the workflow.", "2026-11-10")
        p.write_text(text, encoding="utf-8")


SITUATION = "Our hospital group wants to roll out AI triage; senior clinicians resist adoption and worry about their roles."


class CaseLabCore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "MBA"
        make_vault(self.root, 4)
        self.vault = core.Vault(self.root, Path(self.tmp.name) / "jobs")

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_relevant_notes_with_takes(self):
        notes = caselab.relevant_notes(self.vault, SITUATION)
        titles = [n["title"] for n in notes]
        self.assertIn("Change Resistance", titles)
        self.assertNotIn("Platform Strategy", titles)
        cr = next(n for n in notes if n["title"] == "Change Resistance")
        self.assertIn("co-designed", cr["takes"][0])

    def test_prompt_uses_notes_and_case_is_saved(self):
        notes = caselab.relevant_notes(self.vault, SITUATION)
        client = FakeClient()
        res = caselab.run_case(client, "m", SITUATION, notes)
        self.assertEqual(client.calls[0]["tools"][0]["type"], "web_search_20250305")
        self.assertIn("Student's take on this note", client.calls[0]["messages"][0]["content"])
        self.assertTrue(res["markdown"].startswith("# AI Triage Adoption"))       # search preamble dropped
        rel = caselab.save_case(self.root, SITUATION, res, notes)
        self.assertTrue(rel.startswith("Case Lab/"))
        text = (self.root / rel).read_text(encoding="utf-8")
        self.assertIn("type: case\nstatus: unreviewed\ncourse: Case Lab", text)
        self.assertIn("[HBR on adoption](https://hbr.org/x)", text)
        self.assertIn("## Model answer", text)
        # an earlier case is never fed back in as one of "your notes"
        self.assertNotIn("Case Lab", " ".join(n["rel"] for n in caselab.relevant_notes(self.vault, SITUATION + " triage adoption")))
        self.assertAlmostEqual(caselab.cost_usd(res["usage"]), 0.036 + 0.045 + 0.01, places=3)

    def test_no_web_search_when_turned_off(self):
        client = FakeClient()
        caselab.run_case(client, "m", SITUATION, [], web_search=False)
        self.assertNotIn("tools", client.calls[0])


@unittest.skipUnless(HAVE_FLASK, "needs flask")
class CaseLabApp(unittest.TestCase):
    def go(self, reviewed):
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name)
        make_vault(r / "MBA", reviewed)
        core.Store(r / "jobs" / "mytutor.db").add_user("henry@example.com", generate_password_hash("correct horse battery"))
        self.client = FakeClient()
        self.app = review_app.create_app(r / "MBA", r / "jobs", "v", testing=True, case_client=self.client)
        self.c = self.app.test_client()
        page = self.c.get("/login").get_data(as_text=True)
        tok = re.search(r'name="csrf" (?:value|content)="([^"]+)"', page).group(1)
        self.c.post("/login", data={"username": "henry@example.com", "password": "correct horse battery", "csrf": tok})
        self.tok = re.search(r'<meta name="csrf" content="([^"]+)"', self.c.get("/").get_data(as_text=True)).group(1)

    def tearDown(self):
        self.app.store.db.close()
        self.tmp.cleanup()

    def test_locked_until_half_reviewed(self):
        self.go(reviewed=1)
        s = self.c.get("/api/case-status").get_json()
        self.assertEqual((s["unlocked"], s["reviewed"], s["total"], s["needed"]), (False, 1, 4, 1))
        r = self.c.post("/api/case", json={"situation": SITUATION}, headers={"X-CSRF": self.tok})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.calls, [])                       # no API call while locked

    def test_creates_a_case_when_unlocked(self):
        self.go(reviewed=2)
        self.assertTrue(self.c.get("/api/case-status").get_json()["unlocked"])
        r = self.c.post("/api/case", json={"situation": SITUATION}, headers={"X-CSRF": self.tok})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        res = self.c.get("/api/case/" + r.get_json()["id"]).get_json()
        self.assertEqual(res["state"], "done", res)
        self.assertTrue(res["rel"].startswith("Case Lab/"))
        self.assertEqual(self.c.get("/api/note?rel=" + res["rel"]).get_json()["props"]["type"], "case")
        self.assertEqual(self.c.post("/api/case", json={"situation": "too short"}, headers={"X-CSRF": self.tok}).status_code, 400)


    def test_draft_linkedin_post_from_a_take(self):
        self.go(reviewed=1)
        rel = "MBAM601/Day 1/Core/Change Resistance.md"
        r = self.c.post("/api/draft-post", json={"rel": rel}, headers={"X-CSRF": self.tok})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        msg = self.client.calls[-1]["messages"][0]["content"]
        self.assertIn("co-designed", msg)                              # your take is the heart of the post
        self.assertTrue(r.get_json()["text"])
        r = self.c.post("/api/draft-post", json={"rel": "MBAM601/Day 1/Core/Kodak.md"}, headers={"X-CSRF": self.tok})
        self.assertEqual(r.status_code, 400)                           # no take yet
        r = self.c.post("/api/draft-post", json={"rel": "../x.md"}, headers={"X-CSRF": self.tok})
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
