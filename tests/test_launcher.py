"""Tests for launcher.py helpers (the window itself needs Windows + Tk)."""
import json
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launcher  # noqa: E402

NETSTAT = """
  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:5678           0.0.0.0:0              LISTENING       4120
  TCP    127.0.0.1:5057         0.0.0.0:0              LISTENING       7788
  TCP    127.0.0.1:50570        0.0.0.0:0              LISTENING       9999
  TCP    127.0.0.1:5057         127.0.0.1:61000        ESTABLISHED     7788
  TCP    [::]:5678              [::]:0                 LISTENING       4120
"""


class LauncherTests(unittest.TestCase):
    def test_pids_on_port_only_listeners_on_exact_port(self):
        self.assertEqual(launcher.pids_on_port(NETSTAT, 5678), {4120})
        self.assertEqual(launcher.pids_on_port(NETSTAT, 5057), {7788})
        self.assertEqual(launcher.pids_on_port(NETSTAT, 1234), set())

    def test_port_open(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        self.assertTrue(launcher.port_open(port))
        s.close()
        self.assertFalse(launcher.port_open(port))

    def test_port_open_sees_ipv6_only_listener(self):
        try:
            s = socket.socket(socket.AF_INET6)
            s.bind(("::1", 0))
        except OSError:
            self.skipTest("no IPv6 here")
        s.listen()
        self.assertTrue(launcher.port_open(s.getsockname()[1]))
        s.close()

    def test_shortcut_bat_points_at_the_folder(self):
        bat = launcher.shortcut_bat(Path("C:/Users/henry/mytutor"), autostart=True)
        self.assertIn('cd /d "C:', bat)
        self.assertIn("launcher.py --autostart", bat)
        self.assertTrue(bat.startswith("@echo off\r\n"))


class DashboardTests(unittest.TestCase):
    def test_dashboard_reads_db_and_run_log(self):
        import tempfile, datetime as dt
        import review_core as core
        with tempfile.TemporaryDirectory() as d:
            jobs = Path(d)
            st = core.Store(jobs / "mytutor.db")
            for rel, course, day, kind, status in [
                    ("A/Day 1/Core/x.md", "MBAM601", "Day 1", "core", "reviewed"),
                    ("A/Day 2/Cases/y.md", "MBAM601", "Day 2", "case", "unreviewed"),
                    ("A/Day 2/Ref/z.md", "MBAM601", "Day 2", "reference", "unreviewed"),
                    ("A/Day 2/Quizzes/q.md", "MBAM601", "Day 2", "quiz", ""),
                    ("B/2026-11-01/J.md", "BusinessMentor", "2026-11-01", "theme", ""),
                    ("Hubs/H.md", "MBAM601", "", "hub", "unreviewed")]:
                st.upsert_note({"rel": rel, "title": Path(rel).stem, "course": course, "type": kind, "status": status,
                                "day": day, "created": "", "mtime_ns": 1})
            st.x("INSERT INTO activity(at,user,action,rel,detail) VALUES ('2026-11-09T10:00:00','u','approve','A/Day 1/Core/x.md','')")
            st.x("INSERT INTO activity(at,user,action,rel,detail) VALUES ('2026-11-08T10:00:00','u','my-take','A/Day 1/Core/x.md','t')")
            st.db.close()
            (jobs / "run_log.csv").write_text("finished,days_found,days_processed,sources,notes,cost_usd,failed,seconds,detail\n"
                                              "2026-11-09T09:00:00+13:00,3,1,2,14,0.25,0,40,x\n", encoding="utf-8")
            out = launcher.dashboard_data(jobs, today=dt.date(2026, 11, 9))
        self.assertEqual((out["approved_today"], out["streak"], out["hubs"]), (1, 2, 1))
        a = next(c for c in out["inventory"] if c["course"] == "MBAM601")
        self.assertEqual((a["days"], a["sources"], a["core"], a["cases"], a["quizzes"]), (2, 1, 1, 1, 1))
        self.assertEqual(next(c for c in out["inventory"] if c["course"] == "BusinessMentor")["journals"], 1)
        self.assertEqual([(h["day"], h["approved"], h["takes"]) for h in out["history"]], [("2026-11-09", 1, 0), ("2026-11-08", 0, 1)])
        self.assertEqual((out["last_run"]["notes"], round(out["month_cost"], 2), out["month_runs"]), ("14", 0.25, 1))


class CentreTests(unittest.TestCase):
    def setUp(self):
        import tempfile, threading
        from http.server import ThreadingHTTPServer
        self.tmp = tempfile.TemporaryDirectory()
        cfg = {"jobs_root": self.tmp.name}
        self.opened = []
        self.c = launcher.Centre(cfg, opener=self.opened.append)
        py = [sys.executable, "-u", "-c"]
        self.c.jobs.commands = lambda: {k: (py + [f"print('hello from {k}')"], {}) for k in
                                         ("n8n", "review", "run", "dry-run", "vault-check", "practice")}
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), launcher.make_handler(self.c))
        self.port = self.srv.server_address[1]
        launcher.ALLOWED_HOSTS.add(f"127.0.0.1:{self.port}")
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.tmp.cleanup()

    def req(self, path, body=None, token=True, host=None):
        import http.client
        h = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        hdr = {"Content-Type": "application/json", "Host": host or f"127.0.0.1:{self.port}"}
        if token:
            hdr["X-Token"] = self.c.token
        h.request("POST" if body is not None else "GET", path, body=json.dumps(body) if body is not None else None, headers=hdr)
        r = h.getresponse()
        return r.status, r.read()

    def test_page_has_token_and_api_needs_it(self):
        st, page = self.req("/", token=False)
        self.assertEqual(st, 200)
        self.assertIn(self.c.token.encode(), page)
        self.assertEqual(self.req("/api/state", token=False)[0], 403)
        self.assertEqual(self.req("/", token=False, host="evil.example:5056")[0], 403)
        self.assertEqual(self.req("/api/action", {"action": "run"}, token=False)[0], 403)

    def test_actions_run_whitelisted_jobs_into_console(self):
        import time
        st, body = self.req("/api/action", {"action": "vault-check"})
        self.assertEqual(st, 200)
        for _ in range(50):
            lines = json.loads(self.req("/api/console?since=0")[1])["lines"]
            if any("exit code" in x["text"] for x in lines):
                break
            time.sleep(0.1)
        texts = [x["text"] for x in lines if x["job"] == "vault-check"]
        self.assertIn("hello from vault-check", texts)
        self.assertEqual(self.req("/api/action", {"action": "rm -rf"})[0], 400)
        self.req("/api/action", {"action": "open-review"})
        self.assertEqual(self.opened, [launcher.REVIEW_URL])
        self.assertEqual(self.req("/practice")[0], 404)                 # not built yet
        (Path(self.tmp.name) / "practice.html").write_text("<html><body>Q1</body></html>", encoding="utf-8")
        st, page = self.req("/practice")
        self.assertEqual(st, 200)
        self.assertIn(b"Control Centre", page)
        state = json.loads(self.req("/api/state")[1])
        self.assertIn("dashboard", state)


if __name__ == "__main__":
    unittest.main()
