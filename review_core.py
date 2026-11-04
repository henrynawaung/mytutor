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


def drop_props(text: str, keys) -> str:
    """Remove frontmatter keys (used by Undo)."""
    m = FM.match(text)
    if not m:
        return text
    fm = "\n".join(l for l in m.group(1).splitlines() if l.split(":", 1)[0].strip() not in set(keys))
    return f"---\n{fm}\n---\n" + text[m.end():]


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


def clean_block(t: str) -> str:
    """Keep the writer's paragraphs, bullets and numbering; just tidy line endings and blank runs."""
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = "\n".join(line.rstrip() for line in t.split("\n")).strip("\n")
    return re.sub(r"\n{3,}", "\n\n", t)


def add_take(text: str, take: str, today: str) -> str:
    """Add a dated entry (### date + the take, formatting kept) at the end of '## My take'."""
    entry = f"### {today}\n\n{clean_block(take)}\n"
    m = re.search(r"^## My take[ \t]*$", text, re.M)
    if not m:
        return text.rstrip("\n") + f"\n\n## My take\n\n{entry}"
    nxt = re.search(r"^## ", text[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(text)
    section = text[m.end():end].rstrip("\n")
    return text[:m.end()] + section + f"\n\n{entry}" + ("\n" + text[end:] if nxt else "")


BOUNDARY = re.compile(r"^(?:\*\*\d+\.|## |My answer:)", re.M)


def _answer_end(text: str, m) -> int:
    """Where the answer after 'My answer:' stops: the next prompt, section or answer line."""
    b = BOUNDARY.search(text, m.end())
    return b.start() if b else len(text)


def prompts(text: str) -> list:
    """Reflection prompts in a journal: [{i, question, answer}] (answers may be several lines)."""
    out = []
    for i, m in enumerate(ANSWER.finditer(text)):
        before = text[:m.start()].rstrip().splitlines()
        q = next((l.strip("* ").strip() for l in reversed(before) if l.strip()), "")
        answer = (m.group(1) + text[m.end():_answer_end(text, m)]).strip()
        out.append({"i": i, "question": re.sub(r"^\d+\.\s*", "", q), "answer": answer})
    return out


def answer_prompt(text: str, i: int, answer: str) -> str:
    ms = list(ANSWER.finditer(text))
    if i < 0 or i >= len(ms):
        raise ValueError("no such prompt")
    m = ms[i]
    a = clean_block(answer)
    block = f"My answer: {a}\n" if "\n" not in a and not re.match(r"[-*+>#]|\d+\.", a) else f"My answer:\n\n{a}\n"
    end = _answer_end(text, m)
    rest = text[end:]
    return text[:m.start()] + block + ("\n" + rest if rest else "")


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
               (now(), user, action, rel, (detail or "")[:20000]))

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

    WORK = ("approve", "needs-fix", "my-take", "answer", "undo")

    def has_take(self, vault, rel: str) -> bool:
        """A take saved in the app at any time, or one written straight into the note in Obsidian."""
        if self.q("SELECT 1 FROM activity WHERE rel=? AND action='my-take' LIMIT 1", (rel,)):
            return True
        try:
            t = read(vault.path(rel))
        except (OSError, ValueError):
            return False
        m = re.search(r"^## My take[ \t]*\n(.*?)(?=^## |\Z)", t, re.M | re.S)
        if m and re.sub(r"\*\*[^*]+:\*\*|\s", "", m.group(1)):
            return True
        return "Where I came across this" in t

    def days(self, n: int = 60, vault=None) -> list:
        """One summary row per day: counts by action and by note type."""
        rows = self.q("SELECT substr(a.at,1,10) d, a.action, a.rel, COALESCE(n.type,'') type FROM activity a "
                      "LEFT JOIN notes n ON n.rel=a.rel WHERE a.action IN (%s) ORDER BY a.id" % ",".join("?" * len(self.WORK)),
                      self.WORK)
        out = {}
        for r in rows:
            d = out.setdefault(r["d"], {"day": r["d"], "approve": 0, "needs-fix": 0, "my-take": 0, "answer": 0,
                                        "notes": set(), "types": {}})
            seen = d.setdefault("_seen", set())
            if r["action"] in d and (r["action"] == "my-take" or (r["action"], r["rel"]) not in seen):
                d[r["action"]] += 1                 # a note approved twice in a day counts once
                seen.add((r["action"], r["rel"]))
            if r["rel"] not in d["notes"]:
                d["notes"].add(r["rel"])
                t = "reflection" if r["type"] == "theme" else (r["type"] or "other")
                d["types"][t] = d["types"].get(t, 0) + 1
        days = sorted(out.values(), key=lambda x: x["day"], reverse=True)[:n]
        approved = {}
        for r in rows:
            if r["action"] == "approve" and r["type"] != "theme":
                approved.setdefault(r["d"], set()).add(r["rel"])
        for d in days:
            d.pop("_seen", None)
            d["notes"] = len(d["notes"])
            d["no_take"] = sum(1 for rel in approved.get(d["day"], ()) if vault and not self.has_take(vault, rel))
        return days

    def day(self, day: str, vault=None) -> list:
        """Everything done on one day, grouped by note: title, type, course and each action with its text."""
        rows = self.q("SELECT a.at, a.action, a.rel, a.detail, n.title, n.type, n.course FROM activity a "
                      "LEFT JOIN notes n ON n.rel=a.rel WHERE substr(a.at,1,10)=? AND a.action IN (%s) ORDER BY a.id"
                      % ",".join("?" * len(self.WORK)), (day, *self.WORK))
        notes = {}
        for r in rows:
            n = notes.setdefault(r["rel"], {"rel": r["rel"], "title": r["title"] or Path(r["rel"]).stem,
                                            "type": r["type"] or "", "course": r["course"] or "", "actions": []})
            n["actions"].append({"at": r["at"][11:16], "action": r["action"], "detail": r["detail"] or ""})
        for n in notes.values():
            n["has_take"] = n["type"] == "theme" or (vault is not None and self.has_take(vault, n["rel"]))
        return list(notes.values())

    def recent(self, n: int = 30) -> list:
        return self.q("SELECT at, action, rel, detail FROM activity WHERE action NOT LIKE 'login%' "
                      "ORDER BY id DESC LIMIT ?", (n,))


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")
