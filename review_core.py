"""Core of the myTutor Review app: read and change vault notes, and keep a local SQLite database.

The Markdown notes stay the master copy (Obsidian keeps working). The database holds an index of
the notes plus everything you do in the app: reviews, your takes, answers to reflection prompts.
"""

import re
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

REVIEW_TYPES = ("core", "case", "hub", "reference")
FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)
ANSWER = re.compile(r"^My answer:[ \t]*(.*)$", re.M)


# ------------------------------------------------------------------ note helpers

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def props(text: str) -> dict:
    m = FM.match(text)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith((" ", "-")):
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip().strip('"')
    return out


def body(text: str) -> str:
    m = FM.match(text)
    return text[m.end():] if m else text


def set_props(text: str, values: dict) -> str:
    """Set or add frontmatter keys, keeping every other line as it is."""
    m = FM.match(text)
    fm, rest = (m.group(1), text[m.end():]) if m else ("", text)
    for k, v in values.items():
        line = f"{k}: {v}"
        if re.search(rf"^{re.escape(k)}:.*$", fm, re.M):
            fm = re.sub(rf"^{re.escape(k)}:.*$", lambda _: line, fm, count=1, flags=re.M)
        else:
            fm = (fm + "\n" + line).strip("\n")
    return f"---\n{fm}\n---\n{rest}"


def add_take(text: str, take: str, today: str) -> str:
    """Add a dated line under '## My take' (creating the section if needed)."""
    entry = f"- {today}: " + " ".join(take.split())
    m = re.search(r"^## My take[ \t]*$", text, re.M)
    if not m:
        return text.rstrip("\n") + f"\n\n## My take\n\n{entry}\n"
    nxt = re.search(r"^## ", text[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(text)
    section = text[m.end():end].rstrip("\n")
    return text[:m.end()] + section + f"\n{entry}\n" + ("\n" + text[end:] if nxt else "")


def prompts(text: str) -> list:
    """Reflection prompts in a journal: [{i, question, answer}]."""
    out = []
    for i, m in enumerate(ANSWER.finditer(text)):
        before = text[:m.start()].rstrip().splitlines()
        q = next((l.strip("* ").strip() for l in reversed(before) if l.strip()), "")
        out.append({"i": i, "question": re.sub(r"^\d+\.\s*", "", q), "answer": m.group(1).strip()})
    return out


def answer_prompt(text: str, i: int, answer: str) -> str:
    ms = list(ANSWER.finditer(text))
    if i < 0 or i >= len(ms):
        raise ValueError("no such prompt")
    m = ms[i]
    return text[:m.start()] + "My answer: " + " ".join(answer.split()) + text[m.end():]


# ------------------------------------------------------------------ vault index

class Vault:
    def __init__(self, root: Path, jobs: Path, obsidian_vault: str = ""):
        self.root, self.jobs, self.obsidian_vault = root, jobs, obsidian_vault
        self.lock = threading.Lock()

    def notes(self):
        for p in self.root.rglob("*.md"):
            rel = p.relative_to(self.root)
            if not any(x.startswith(".") for x in rel.parts):
                yield p, rel

    def path(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if self.root.resolve() not in p.parents or p.suffix != ".md":
            raise ValueError("outside the vault")
        return p

    def find(self, title: str) -> str | None:
        t = title.strip().lower()
        for p, rel in self.notes():
            if p.stem.lower() == t:
                return rel.as_posix()
        return None

    def summary(self) -> dict:
        items, journals, courses = [], [], {}
        for p, rel in self.notes():
            text = read(p)
            pr = props(text)
            kind, status, course = pr.get("type", ""), pr.get("status", ""), pr.get("course", "")
            if kind == "theme":
                open_n = sum(1 for x in prompts(text) if not x["answer"])
                if open_n:
                    journals.append({"rel": rel.as_posix(), "title": p.stem, "course": course,
                                     "open": open_n, "day": rel.parts[1] if len(rel.parts) > 2 else ""})
                continue
            if kind not in REVIEW_TYPES or not status:
                continue
            c = courses.setdefault(course or "other", {"reviewed": 0, "total": 0})
            c["total"] += 1
            c["reviewed"] += status == "reviewed"
            items.append({"rel": rel.as_posix(), "title": p.stem, "type": kind, "status": status,
                          "course": course, "created": pr.get("created", ""),
                          "day": rel.parts[1] if len(rel.parts) > 2 else ""})
        items.sort(key=lambda x: (x["created"], x["course"], x["day"], x["title"]))
        journals.sort(key=lambda x: x["rel"], reverse=True)
        return {"items": items, "journals": journals, "courses": courses}

    def note(self, rel: str) -> dict:
        p = self.path(rel)
        text = read(p)
        out = {"rel": rel, "title": p.stem, "props": props(text), "body": body(text),
               "mtime": str(p.stat().st_mtime_ns), "prompts": prompts(text)}
        if self.obsidian_vault:
            vault_rel = self.root.name + "/" + rel[:-3]
            out["obsidian"] = f"obsidian://open?vault={quote(self.obsidian_vault)}&file={quote(vault_rel)}"
        return out

    def change(self, rel: str, mtime: str, fn, action: str, detail: str = "", store=None, user: str = "") -> dict:
        with self.lock:
            p = self.path(rel)
            if str(p.stat().st_mtime_ns) != str(mtime).strip():
                return {"ok": False, "error": "This note changed since you opened it (maybe in Obsidian). Reload it first."}
            new = fn(read(p))
            p.write_text(new, encoding="utf-8", newline="\n")
            note = self.note(rel)
            if store:
                store.upsert_note(note_row(rel, p, new))
                store.log(user, action, rel, detail)
            return {"ok": True, "note": note}


def note_row(rel: str, p: Path, text: str) -> dict:
    pr = props(text)
    parts = Path(rel).parts
    return {"rel": rel, "title": p.stem, "course": pr.get("course", ""), "type": pr.get("type", ""),
            "status": pr.get("status", ""), "day": parts[1] if len(parts) > 2 else "",
            "created": pr.get("created", ""), "mtime_ns": p.stat().st_mtime_ns}


# ------------------------------------------------------------------ database

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
  failed INTEGER NOT NULL DEFAULT 0, locked_until TEXT, created_at TEXT NOT NULL, last_login TEXT);
CREATE TABLE IF NOT EXISTS notes (
  rel TEXT PRIMARY KEY, title TEXT, course TEXT, type TEXT, status TEXT, day TEXT, created TEXT,
  mtime_ns INTEGER, indexed_at TEXT);
CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, user TEXT, action TEXT NOT NULL, rel TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS activity_at ON activity(at);
CREATE INDEX IF NOT EXISTS notes_status ON notes(status, course);
"""
LOCK_AFTER, LOCK_MINUTES = 5, 10


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.executescript(SCHEMA)

    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def x(self, sql, args=()):
        with self.lock:
            self.db.execute(sql, args)

    # users ---------------------------------------------------------------
    def add_user(self, username: str, pw_hash: str):
        self.x("INSERT INTO users(username, pw_hash, created_at) VALUES (?,?,?) "
               "ON CONFLICT(username) DO UPDATE SET pw_hash=excluded.pw_hash, failed=0, locked_until=NULL",
               (username, pw_hash, now()))

    def user(self, username: str):
        r = self.q("SELECT * FROM users WHERE username=?", (username,))
        return r[0] if r else None

    def users(self) -> int:
        return self.q("SELECT COUNT(*) n FROM users")[0]["n"]

    def locked(self, u) -> bool:
        return bool(u and u["locked_until"] and u["locked_until"] > now())

    def login_failed(self, username: str):
        u = self.user(username)
        if not u:
            return
        failed = u["failed"] + 1
        until = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds") \
            if failed >= LOCK_AFTER else None
        self.x("UPDATE users SET failed=?, locked_until=? WHERE id=?", (0 if until else failed, until, u["id"]))
        self.log(username, "login-failed", "", "locked" if until else "")

    def login_ok(self, username: str):
        self.x("UPDATE users SET failed=0, locked_until=NULL, last_login=? WHERE username=?", (now(), username))
        self.log(username, "login", "", "")

    # notes ---------------------------------------------------------------
    def upsert_note(self, r: dict):
        self.x("INSERT INTO notes(rel,title,course,type,status,day,created,mtime_ns,indexed_at) "
               "VALUES (:rel,:title,:course,:type,:status,:day,:created,:mtime_ns,:at) "
               "ON CONFLICT(rel) DO UPDATE SET title=excluded.title, course=excluded.course, type=excluded.type, "
               "status=excluded.status, day=excluded.day, created=excluded.created, mtime_ns=excluded.mtime_ns, "
               "indexed_at=excluded.indexed_at", {**r, "at": now()})

    def sync(self, vault) -> int:
        """Re-read the vault (only notes changed since last time). Markdown is the master copy."""
        known = {r["rel"]: r["mtime_ns"] for r in self.q("SELECT rel, mtime_ns FROM notes")}
        seen, changed = set(), 0
        for p, rel in vault.notes():
            rel = rel.as_posix()
            seen.add(rel)
            m = p.stat().st_mtime_ns
            if known.get(rel) != m:
                self.upsert_note(note_row(rel, p, read(p)))
                changed += 1
        for rel in set(known) - seen:
            self.x("DELETE FROM notes WHERE rel=?", (rel,))
            changed += 1
        return changed

    def log(self, user: str, action: str, rel: str, detail: str):
        self.x("INSERT INTO activity(at,user,action,rel,detail) VALUES (?,?,?,?,?)",
               (now(), user, action, rel, (detail or "")[:2000]))

    def stats(self) -> dict:
        today = datetime.now().date().isoformat()
        days = [r["d"] for r in self.q(
            "SELECT DISTINCT substr(at,1,10) d FROM activity WHERE action IN ('approve','needs-fix','my-take','answer') "
            "ORDER BY d DESC")]
        streak, d = 0, datetime.now().date()
        if days and days[0] != today:
            d -= timedelta(days=1)
        for x in days:
            if x == d.isoformat():
                streak += 1
                d -= timedelta(days=1)
            elif x < d.isoformat():
                break
        done = self.q("SELECT COUNT(*) n FROM activity WHERE substr(at,1,10)=? AND action IN "
                      "('approve','needs-fix','my-take','answer')", (today,))[0]["n"]
        return {"today": done, "streak": streak}

    def recent(self, n: int = 30) -> list:
        return self.q("SELECT at, action, rel, detail FROM activity WHERE action NOT LIKE 'login%' "
                      "ORDER BY id DESC LIMIT ?", (n,))


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")
