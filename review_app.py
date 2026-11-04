"""myTutor Review: a lightweight web app on your laptop for reviewing your vault, with a login.

First time:   py -m pip install flask
              py review_app.py --create-user you@example.com   (your email; asks for a password, min 12 characters)
Every time:   py review_app.py                           (opens http://127.0.0.1:5057 in your browser)

- Markdown notes stay the master copy; Obsidian keeps working.
- A local SQLite database (<jobs_root>/mytutor.db) holds the note index, your login and every action.
- Listens on this laptop only (127.0.0.1). Passwords are stored as salted scrypt hashes, never in clear.
- 5 wrong passwords lock the account for 10 minutes. Sessions end after 8 hours.
- Every change needs a CSRF token, so other websites cannot act on your notes.
"""

import argparse
import getpass
import json
import os
import re
import secrets
import sys
import webbrowser
from datetime import date, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import review_core as core

HERE = Path(__file__).resolve().parent
DUMMY_HASH = generate_password_hash("not-a-real-password")
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def load_config(name="config.json"):
    cfg = json.loads((HERE / name).read_text(encoding="utf-8"))
    vault = Path(os.path.expanduser(cfg["vault_path"]))
    jobs = Path(os.path.expandvars(os.path.expanduser(cfg.get("jobs_root", "~/mytutor/jobs"))))
    return cfg, vault, jobs


def secret_key(jobs: Path) -> bytes:
    f = jobs / ".review_secret"
    if not f.exists():
        jobs.mkdir(parents=True, exist_ok=True)
        f.write_bytes(secrets.token_bytes(32))
    return f.read_bytes()


def create_app(vault_root: Path, jobs: Path, obsidian_vault: str = "", testing: bool = False) -> Flask:
    app = Flask(__name__, template_folder=str(HERE / "review_web" / "templates"),
                static_folder=str(HERE / "review_web" / "static"))
    app.config.update(SECRET_KEY=secret_key(jobs), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8), TESTING=testing)
    vault = core.Vault(vault_root, jobs, obsidian_vault)
    store = core.Store(jobs / "mytutor.db")
    store.sync(vault)
    app.vault, app.store = vault, store

    @app.after_request
    def headers(r):
        r.headers["X-Frame-Options"] = "DENY"
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["Cache-Control"] = "no-store"
        r.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        return r

    def csrf_ok() -> bool:
        sent = request.headers.get("X-CSRF") or request.form.get("csrf", "")
        return bool(session.get("csrf")) and secrets.compare_digest(sent, session["csrf"])

    def login_required(fn):
        @wraps(fn)
        def wrap(*a, **k):
            if not session.get("user"):
                if request.path.startswith("/api/"):
                    return jsonify(error="Please log in again."), 401
                return redirect(url_for("login"))
            if request.method == "POST" and not csrf_ok():
                abort(403)
            return fn(*a, **k)
        return wrap

    # ---------------------------------------------------------------- auth
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if store.users() == 0:
            return render_template("login.html", error="No user yet. In the mytutor folder run: "
                                   "py review_app.py --create-user <your email>", csrf="", disabled=True)
        session.setdefault("csrf", secrets.token_urlsafe(24))
        error = ""
        if request.method == "POST":
            if not csrf_ok():
                abort(403)
            name = request.form.get("username", "").strip().lower()
            pw = request.form.get("password", "")
            u = store.user(name)
            if store.locked(u):
                error = "Too many attempts. Try again in a few minutes."
            elif u and check_password_hash(u["pw_hash"], pw):
                store.login_ok(name)
                session.clear()
                session.permanent = True
                session.update(user=name, csrf=secrets.token_urlsafe(24))
                return redirect(url_for("home"))
            else:
                if not u:
                    check_password_hash(DUMMY_HASH, pw)       # same time whether or not the user exists
                store.login_failed(name)
                error = "Wrong email or password."
        return render_template("login.html", error=error, csrf=session["csrf"], disabled=False)

    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ---------------------------------------------------------------- pages
    @app.get("/")
    @login_required
    def home():
        return render_template("app.html", csrf=session["csrf"], user=session["user"])

    # ---------------------------------------------------------------- API
    @app.get("/api/summary")
    @login_required
    def summary():
        rows = store.q("SELECT rel,title,course,type,status,day,created FROM notes "
                       "WHERE status != '' AND type IN ('core','case','hub','reference') "
                       "ORDER BY created, course, day, title")
        courses = {}
        for r in rows:
            c = courses.setdefault(r["course"] or "other", {"reviewed": 0, "total": 0})
            c["total"] += 1
            c["reviewed"] += r["status"] == "reviewed"
        journals = []
        for r in store.q("SELECT rel,title,course,day FROM notes WHERE type='theme' ORDER BY rel DESC"):
            try:
                n = sum(1 for x in core.prompts(core.read(vault.path(r["rel"]))) if not x["answer"])
            except (OSError, ValueError):
                continue
            if n:
                journals.append({**r, "open": n})
        return jsonify(items=rows, journals=journals, courses=courses, stats=store.stats())

    @app.get("/api/note")
    @login_required
    def note():
        try:
            return jsonify(vault.note(request.args["rel"]))
        except (KeyError, ValueError, OSError):
            return jsonify(error="Note not found."), 404

    @app.get("/api/find")
    @login_required
    def find():
        r = store.q("SELECT rel FROM notes WHERE lower(title)=lower(?) LIMIT 1", (request.args.get("title", ""),))
        return jsonify(rel=r[0]["rel"] if r else None)

    @app.get("/api/days")
    @login_required
    def days():
        return jsonify(days=store.days(vault=vault), stats=store.stats())

    @app.get("/api/day")
    @login_required
    def day():
        d = request.args.get("d", "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            return jsonify(error="Bad date."), 400
        return jsonify(store.day(d, vault=vault))

    @app.get("/api/recent")
    @login_required
    def recent():
        return jsonify(store.recent())

    @app.post("/api/sync")
    @login_required
    def sync():
        return jsonify(changed=store.sync(vault))

    def change(fn, action, detail=""):
        d = request.get_json(silent=True) or {}
        try:
            r = vault.change(d["rel"], d["mtime"], fn, action, detail, store=store, user=session["user"])
        except (KeyError, ValueError, OSError) as e:
            return jsonify(ok=False, error=str(e)), 400
        return jsonify(r), (200 if r["ok"] else 409)

    @app.post("/api/approve")
    @login_required
    def approve():
        today = date.today().isoformat()
        return change(lambda t: core.set_props(t, {"status": "reviewed", "reviewed_on": today}), "approve")

    @app.post("/api/undo")
    @login_required
    def undo():
        prev = str((request.get_json(silent=True) or {}).get("status", "unreviewed"))
        if prev not in ("unreviewed", "reviewed", "needs-fix"):
            return jsonify(ok=False, error="Unknown status."), 400
        return change(lambda t: core.set_props(core.drop_props(t, ["reviewed_on", "fix_note"]), {"status": prev}),
                      "undo", prev)

    @app.post("/api/needs-fix")
    @login_required
    def needs_fix():
        why = " ".join(str((request.get_json(silent=True) or {}).get("why", "")).split()).replace('"', "'")
        return change(lambda t: core.set_props(t, {"status": "needs-fix", "fix_note": f'"{why}"'}), "needs-fix", why)

    @app.post("/api/take")
    @login_required
    def take():
        text = str((request.get_json(silent=True) or {}).get("take", "")).strip()
        if not text:
            return jsonify(ok=False, error="Nothing to save."), 400
        today = date.today().isoformat()
        return change(lambda t: core.add_take(t, text, today), "my-take", text)

    @app.post("/api/answer")
    @login_required
    def answer():
        d = request.get_json(silent=True) or {}
        text = str(d.get("answer", "")).strip()
        if not text:
            return jsonify(ok=False, error="Nothing to save."), 400
        return change(lambda t: core.answer_prompt(t, int(d.get("i", -1)), text), "answer", text)

    return app


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="myTutor Review web app")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--port", type=int, default=5057)
    ap.add_argument("--create-user", metavar="EMAIL", help="create a login with your email (or reset its password)")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args(argv)
    cfg, vault, jobs = load_config(a.config)
    if a.create_user:
        email = a.create_user.strip().lower()
        if not EMAIL.fullmatch(email):
            print("Please use an email address as the username, e.g. name@example.com")
            return 1
        pw = getpass.getpass("New password (min 12 characters, not shown): ")
        if len(pw) < 12:
            print("Too short: use at least 12 characters.")
            return 1
        if pw != getpass.getpass("Type it again: "):
            print("The two passwords did not match.")
            return 1
        core.Store(jobs / "mytutor.db").add_user(email, generate_password_hash(pw))
        print(f"Login for {email} is ready (password stored as a one-way scrypt hash). Now run: py review_app.py")
        return 0
    app = create_app(vault, jobs, cfg.get("obsidian_vault_name", ""))
    url = f"http://127.0.0.1:{a.port}/"
    print(f"myTutor Review: {url}   (this laptop only; close this window or press Ctrl+C to stop)")
    if not a.no_open:
        webbrowser.open(url)
    app.run(host="127.0.0.1", port=a.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
