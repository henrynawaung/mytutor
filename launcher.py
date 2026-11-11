"""myTutor Control Centre: a dashboard + console page that starts, runs and checks everything.

    Double-click "myTutor Control Centre.bat"   (or: pyw launcher.py)
    It opens http://127.0.0.1:5056/ in your browser.

- Start everything: n8n (with the settings myTutor needs) + the Review app.
- Live status, a dashboard of your second brain (today, streak, courses, days, sources, concepts, cases,
  quizzes, journals, hubs, last run and cost) and a console that shows what each job is doing.
- One click: run myTutor now, dry run, vault check, practice quizzes, open Review app / n8n / Obsidian / inbox.
- Stop everything, optional start with Windows, desktop shortcut.

Safety: it listens on this laptop only, every action needs a token from the page, only the fixed actions
below can run (no free-form commands), and it never changes your notes.
"""

import csv
import json
import os
import re
import secrets
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
N8N_PORT, REVIEW_PORT = 5678, 5057
REVIEW_URL, N8N_URL = f"http://127.0.0.1:{REVIEW_PORT}/", f"http://localhost:{N8N_PORT}/"
STARTUP = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/myTutor Control Centre.bat"
DESKTOP = Path.home() / "Desktop" / "myTutor Control Centre.bat"


# ------------------------------------------------------------------ helpers (no GUI, tested)

def port_open(port: int, host: str | None = None, timeout: float = 0.3) -> bool:
    """True if something is listening on this port. Checks IPv4 and IPv6, because newer Node.js
    (and so n8n) may listen only on ::1 / localhost, not on 127.0.0.1."""
    for h in ([host] if host else ["127.0.0.1", "::1"]):
        try:
            with socket.create_connection((h, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def pids_on_port(netstat_output: str, port: int) -> set:
    """PIDs listening on a port, from `netstat -ano` output (Windows)."""
    pids = set()
    for line in netstat_output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING" \
                and re.search(rf":{port}$", parts[1]) and parts[4].isdigit() and int(parts[4]) > 0:
            pids.add(int(parts[4]))
    return pids


def console_python() -> str:
    """python.exe next to the pythonw.exe this window runs on (so console jobs show their output)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return sys.executable


def windowed_python() -> str:
    exe = Path(sys.executable)
    w = exe.parent / "pythonw.exe"
    return str(w) if w.exists() else sys.executable


def shortcut_bat(folder: Path, autostart: bool = False) -> str:
    """A .bat that opens the Control Centre from anywhere (desktop or Windows Startup)."""
    extra = " --autostart" if autostart else ""
    return (f'@echo off\r\nrem myTutor Control Centre\r\ncd /d "{folder}"\r\n'
            f'start "" "{windowed_python()}" launcher.py{extra}\r\n')


def load_cfg() -> dict:
    try:
        return json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def inbox_folder(cfg: dict) -> Path | None:
    p = cfg.get("synced_inbox") or cfg.get("inbox_path")
    return Path(os.path.expandvars(os.path.expanduser(p))) if p else None


def jobs_folder(cfg: dict) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(cfg.get("jobs_root", "~/mytutor/jobs"))))


ACT_NAMES = {"approve": "approved", "my-take": "take", "answer": "reflection", "needs-fix": "needs fix",
             "undo": "undo", "edit-take": "edited take", "delete-take": "deleted take"}


def dashboard_data(jobs: Path, today: date | None = None) -> dict:
    """Numbers for the dashboard. Reads the Review app's database read-only and the run log; never writes."""
    today = today or date.today()
    t = today.isoformat()
    out = {"approved_today": 0, "takes_today": 0, "answers_today": 0, "streak": 0, "to_review": 0,
           "approved_week": 0, "active_days_week": 0,
           "courses": [], "recent": [], "last_run": None, "month_cost": 0.0, "month_runs": 0,
           "inventory": [], "hubs": 0, "history": []}
    db = jobs / "mytutor.db"
    if db.exists():
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=2)
        try:
            q = lambda sql, a=(): con.execute(sql, a).fetchall()   # noqa: E731
            out["approved_today"] = q("SELECT COUNT(DISTINCT rel) FROM activity WHERE substr(at,1,10)=? AND action='approve'", (t,))[0][0]
            out["takes_today"] = q("SELECT COUNT(*) FROM activity WHERE substr(at,1,10)=? AND action='my-take'", (t,))[0][0]
            out["answers_today"] = q("SELECT COUNT(*) FROM activity WHERE substr(at,1,10)=? AND action='answer'", (t,))[0][0]
            days = {r[0] for r in q("SELECT DISTINCT substr(at,1,10) FROM activity WHERE action IN "
                                    "('approve','my-take','answer','needs-fix')")}
            from review_core import week_streak
            out["streak"] = week_streak(days, today)
            monday = (today - timedelta(days=today.weekday())).isoformat()
            out["approved_week"] = q("SELECT COUNT(DISTINCT rel) FROM activity WHERE substr(at,1,10)>=? AND action='approve'",
                                     (monday,))[0][0]
            out["active_days_week"] = sum(1 for d in days if d >= monday)
            rows = q("SELECT course, SUM(status='reviewed'), COUNT(*) FROM notes WHERE status != '' AND "
                     "type IN ('core','case','hub','reference') GROUP BY course ORDER BY course")
            out["courses"] = [(c or "other", int(r or 0), int(n)) for c, r, n in rows]
            out["to_review"] = sum(n - r for _, r, n in out["courses"])
            # what is in the second brain, per course: days, source files, concepts, cases, quizzes, journals
            inv = {}
            for course, day, kind, n in q("SELECT COALESCE(NULLIF(course,''),'other'), day, type, COUNT(*) FROM notes "
                                          "WHERE rel LIKE '%/%/%' GROUP BY 1, 2, 3"):
                c = inv.setdefault(course, {"course": course, "days": set(), "sources": 0, "core": 0, "cases": 0,
                                            "quizzes": 0, "journals": 0})
                if day:
                    c["days"].add(day)
                key = {"reference": "sources", "core": "core", "case": "cases", "quiz": "quizzes",
                       "theme": "journals"}.get(kind)
                if key:
                    c[key] += n
            for c in inv.values():
                c["days"] = len(c["days"])
            out["inventory"] = sorted(inv.values(), key=lambda c: c["course"])
            out["hubs"] = q("SELECT COUNT(*) FROM notes WHERE type='hub'")[0][0]
            # review history: one row per day with activity (last 10 days with work)
            out["history"] = [{"day": d, "approved": a or 0, "takes": tk or 0, "reflections": rf or 0, "notes": n or 0}
                              for d, a, tk, rf, n in q(
                "SELECT substr(at,1,10) d, COUNT(DISTINCT CASE WHEN action='approve' THEN rel END), "
                "SUM(action='my-take'), SUM(action='answer'), COUNT(DISTINCT rel) FROM activity "
                "WHERE action IN ('approve','my-take','answer','needs-fix') GROUP BY d ORDER BY d DESC LIMIT 10")]
            for at, action, rel in q("SELECT at, action, rel FROM activity WHERE action NOT LIKE 'login%' "
                                     "AND action != 'background' ORDER BY id DESC LIMIT 4"):
                out["recent"].append((at[5:16].replace("T", " "), ACT_NAMES.get(action, action),
                                      Path(rel or "").stem or "-"))
        except sqlite3.Error:
            pass
        finally:
            con.close()
    log = jobs / "run_log.csv"
    if log.exists():
        try:
            with log.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except OSError:
            rows = []
        month = t[:7]
        for r in rows:
            if r.get("finished", "")[:7] == month:
                out["month_runs"] += 1
                try:
                    out["month_cost"] += float(r.get("cost_usd") or 0)
                except ValueError:
                    pass
        if rows:
            r = rows[-1]
            out["last_run"] = {"finished": r.get("finished", "")[:16].replace("T", " "), "sources": r.get("sources", "0"),
                               "notes": r.get("notes", "0"), "cost": r.get("cost_usd", "0"), "failed": r.get("failed", "0")}
    return out


# ------------------------------------------------------------------ jobs and console

IS_WIN = os.name == "nt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class Console:
    """The last few thousand lines printed by the jobs this page started."""

    def __init__(self, keep: int = 4000):
        self.lines, self.n, self.keep, self.lock = [], 0, keep, threading.Lock()

    def add(self, job: str, text: str):
        with self.lock:
            self.n += 1
            self.lines.append({"n": self.n, "job": job, "t": datetime.now().strftime("%H:%M:%S"), "text": text.rstrip()})
            del self.lines[:-self.keep]

    def since(self, n: int) -> list:
        with self.lock:
            return [x for x in self.lines if x["n"] > n]


class Jobs:
    """Starts the fixed set of myTutor jobs and pipes their output into the console."""

    def __init__(self, console: Console, cfg: dict, popen=subprocess.Popen):
        self.console, self.cfg, self.popen = console, cfg, popen
        self.procs = {}                              # name -> Popen
        self.started = {}                            # name -> start time
        self.lock = threading.Lock()

    def py(self, *args) -> list:
        return [console_python(), "-u", *args]

    def commands(self) -> dict:
        n8n = ["cmd", "/c", "n8n", "start"] if IS_WIN else ["n8n", "start"]
        return {
            "n8n": (n8n, {"NODES_EXCLUDE": "[]"}),                 # n8n 2.x hides Execute Command without this
            "review": (self.py("review_app.py", "--no-open"), {}),
            "run": (self.py("run.py"), {}),
            "dry-run": (self.py("run.py", "--dry-run"), {}),
            "vault-check": (self.py("vault_doctor.py"), {}),
            "practice": (self.py("practice.py", "--open"), {}),
        }

    def running(self, name: str) -> bool:
        p = self.procs.get(name)
        return bool(p and p.poll() is None)

    def start(self, name: str) -> str:
        with self.lock:
            if self.running(name):
                if name in ("n8n", "review") and not port_open(N8N_PORT if name == "n8n" else REVIEW_PORT):
                    secs = int(time.time() - self.started.get(name, time.time()))
                    return (f"{name} is still starting ({secs}s). Watch the console (filter: {name}); "
                            "if nothing changes after 2 minutes, click Restart.")
                return f"{name} is already running."
            argv, extra = self.commands()[name]
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", **extra)
            shown = argv[2:] if argv[:2] == [console_python(), "-u"] else argv
            self.console.add(name, "$ " + " ".join(shown))
            p = self.popen(argv, cwd=str(HERE), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
            self.procs[name] = p
            self.started[name] = time.time()
        threading.Thread(target=self._pump, args=(name, p), daemon=True).start()
        return f"Started {name}."

    def _pump(self, name, p):
        for raw in iter(p.stdout.readline, b""):
            self.console.add(name, raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
        code = p.wait()
        self.console.add(name, f"[{name} finished, exit code {code}]")

    def stop(self, name: str) -> bool:
        p = self.procs.get(name)
        if not (p and p.poll() is None):
            return False
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        else:
            p.terminate()
        self.console.add(name, f"[{name} stopped]")
        return True

    def status(self) -> list:
        return [{"name": k, "running": self.running(k), "exit": (None if p.poll() is None else p.returncode)}
                for k, p in self.procs.items()]


def stop_port(port: int) -> int:
    if not IS_WIN:
        return 0
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    n = 0
    for pid in pids_on_port(out, port):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        n += 1
    return n


def open_target(url_or_path: str):
    if IS_WIN and not url_or_path.startswith(("http", "obsidian:")):
        os.startfile(url_or_path)  # noqa: S606
    else:
        webbrowser.open(url_or_path)


# ------------------------------------------------------------------ web page + API

CONTROL_PORT = 5056
ALLOWED_HOSTS = {f"127.0.0.1:{CONTROL_PORT}", f"localhost:{CONTROL_PORT}"}


class Centre:
    def __init__(self, cfg: dict, jobs=None, console=None, opener=open_target):
        self.cfg, self.token = cfg, secrets.token_urlsafe(24)
        self.console = console or Console()
        self.jobs = jobs or Jobs(self.console, cfg)
        self.open = opener

    def action(self, name: str) -> str:
        c, j = self.cfg, self.jobs
        if name == "start-all":
            msgs = []
            if not port_open(N8N_PORT):
                msgs.append(j.start("n8n"))
            if not port_open(REVIEW_PORT):
                msgs.append(j.start("review"))
            return " ".join(msgs) or "Everything is already running."
        if name in ("stop-n8n", "stop-review"):
            key = name.split("-", 1)[1]
            n = int(j.stop(key)) + stop_port(N8N_PORT if key == "n8n" else REVIEW_PORT)
            label = "n8n" if key == "n8n" else "the Review app"
            return f"Stopped {label}." if n else f"{label[0].upper() + label[1:]} was not running."
        if name in ("start-n8n", "start-review"):
            key = name.split("-", 1)[1]
            return "Already running." if port_open(N8N_PORT if key == "n8n" else REVIEW_PORT) else j.start(key)
        if name == "stop-all":
            n = sum(j.stop(k) for k in list(j.procs))
            n += stop_port(N8N_PORT) + stop_port(REVIEW_PORT)
            return f"Stopped {n} program(s)." if n else "Nothing was running."
        if name in ("run", "dry-run", "vault-check", "practice"):
            return j.start(name)
        if name == "open-review":
            self.open(REVIEW_URL); return "Opening the Review app."
        if name == "open-days":
            self.open(REVIEW_URL + "#days"); return "Opening your review history (My days)."
        if name == "open-n8n":
            self.open(N8N_URL); return "Opening n8n."
        if name == "open-obsidian":
            self.open(f"obsidian://open?vault={quote(c.get('obsidian_vault_name') or 'henry_mba')}"); return "Opening Obsidian."
        if name == "open-inbox":
            p = inbox_folder(c)
            if p and p.exists():
                self.open(str(p)); return "Opening the inbox folder."
            return "Inbox folder not found: check synced_inbox in config.json."
        if name == "autostart-on":
            STARTUP.write_text(shortcut_bat(HERE, autostart=True), encoding="utf-8"); return "myTutor will start when you sign in to Windows."
        if name == "autostart-off":
            if STARTUP.exists():
                STARTUP.unlink()
            return "Automatic start is off."
        if name == "desktop-shortcut":
            DESKTOP.write_text(shortcut_bat(HERE), encoding="utf-8"); return "Shortcut added to your desktop."
        if name in ("restart-n8n", "restart-review", "restart-all"):
            keys = ["n8n", "review"] if name == "restart-all" else [name.split("-", 1)[1]]
            threading.Thread(target=self._restart, args=(keys,), daemon=True).start()
            return "Restarting " + " and ".join("n8n" if k == "n8n" else "the Review app" for k in keys) + "…"
        if name == "restart-centre":
            DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen([windowed_python(), str(HERE / "launcher.py"), "--after-restart"], cwd=str(HERE),
                             creationflags=DETACHED, close_fds=True)
            threading.Timer(0.5, lambda: os._exit(0)).start()
            return "Restarting the Control Centre… the page reloads by itself."
        if name == "quit":
            threading.Timer(0.5, lambda: os._exit(0)).start()     # close this page's helper; services keep running
            return "Control Centre closed. Double-click 'myTutor Control Centre.bat' to open it again."
        raise KeyError(name)

    def _restart(self, keys):
        import time
        for k in keys:
            port = N8N_PORT if k == "n8n" else REVIEW_PORT
            self.jobs.stop(k)
            stop_port(port)
            for _ in range(40):                      # wait until the old copy has let go of its port
                if not port_open(port):
                    break
                time.sleep(0.25)
            self.console.add("control", self.jobs.start(k))

    def state(self) -> dict:
        jobs = self.jobs.status()
        mine = {j["name"] for j in jobs if j["running"]}
        services = [{"key": k, "name": nm, "port": port, "up": port_open(port), "detail": det,
                     "here": k in mine, "starting": k in mine and not port_open(port),
                     "since": int(time.time() - self.jobs.started.get(k, time.time()))} for k, nm, port, det in (
            ("n8n", "n8n automation", N8N_PORT, "runs myTutor every 15 min"),
            ("review", "Review app", REVIEW_PORT, "notes, takes, My days"))]
        return {"n8n": services[0]["up"], "review": services[1]["up"], "services": services, "jobs": jobs,
                "autostart": STARTUP.exists(), "goal": int(self.cfg.get("weekly_goal", 20) or 20),
                "dashboard": dashboard_data(jobs_folder(self.cfg))}


def make_handler(centre: Centre):
    from http.server import BaseHTTPRequestHandler
    from urllib.parse import parse_qs, urlparse
    page_path = HERE / "control_web" / "index.html"
    static = HERE / "review_web" / "static"

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            raw = body if isinstance(body, bytes) else (body.encode() if isinstance(body, str) else json.dumps(body).encode())
            self.send_response(code)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("text", "application/json")) else ""))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                             "style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def ok_host(self):
            return self.headers.get("Host", "") in ALLOWED_HOSTS          # blocks DNS-rebinding tricks

        def authed(self):
            return self.ok_host() and secrets.compare_digest(self.headers.get("X-Token", ""), centre.token)

        def do_GET(self):
            u = urlparse(self.path)
            if not self.ok_host():
                return self.send(403, {"error": "forbidden"})
            if u.path == "/":
                html = page_path.read_text(encoding="utf-8").replace("__TOKEN__", centre.token)
                return self.send(200, html, "text/html")
            if u.path == "/logo.png":
                return self.send(200, (static / "logo64.png").read_bytes(), "image/png")
            if not self.authed():
                return self.send(403, {"error": "forbidden"})
            if u.path == "/api/state":
                return self.send(200, centre.state())
            if u.path == "/api/console":
                since = int((parse_qs(u.query).get("since") or ["0"])[0] or 0)
                return self.send(200, {"lines": centre.console.since(since)})
            return self.send(404, {"error": "not found"})

        def do_POST(self):
            if not self.authed():
                return self.send(403, {"error": "forbidden"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)) or b"{}")
                msg = centre.action(str(body.get("action", "")))
                centre.console.add("control", msg)
                return self.send(200, {"ok": True, "message": msg})
            except KeyError:
                return self.send(400, {"ok": False, "message": "Unknown action."})
            except OSError as e:
                return self.send(500, {"ok": False, "message": str(e)})

    return H


def main(argv=None) -> int:
    from http.server import ThreadingHTTPServer
    argv = sys.argv[1:] if argv is None else argv
    url = f"http://127.0.0.1:{CONTROL_PORT}/"
    if "--after-restart" in argv:                     # wait for the old copy to close its port
        import time
        for _ in range(40):
            if not port_open(CONTROL_PORT):
                break
            time.sleep(0.25)
    elif port_open(CONTROL_PORT):                     # already open: just show it
        webbrowser.open(url)
        return 0
    centre = Centre(load_cfg())
    srv = ThreadingHTTPServer(("127.0.0.1", CONTROL_PORT), make_handler(centre))
    if "--autostart" in argv:
        centre.console.add("control", centre.action("start-all"))
    elif "--after-restart" in argv:
        centre.console.add("control", "Control Centre restarted.")
    else:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
