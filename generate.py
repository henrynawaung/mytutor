"""myTutor stage 3: turn extracted texts into Obsidian notes with Claude.

Usage
    py generate.py --only "Short Case"        # test on one source first (cheap)
    py generate.py                            # every source in the newest job
    py generate.py --estimate                 # tokens and cost estimate, no API call
    py generate.py --day "Day 1" --force      # redo every source of Day 1 (add --course if needed)
    py generate.py --day "Day 1" --only "Short" --force   # redo one source of Day 1
    py generate.py --rebuild-set              # replace the day's fixed practice set (no API call)

Reads   <job>/extract.json, <job>/text/*.md, existing note titles in your vault
Writes  <job>/notes/reference|core|cases|quizzes|theme/*.md   (staged; file.py copies them into the vault)
        <job>/quiz/*.json                                    quiz data for each source
        <job>/quiz/practice-set.json + notes/quizzes/Practice - <Course> <Day>.md
                                                             the day's fixed practice set, built ONCE
        <job>/generate.json                                  tokens, cost, seconds, notes per source
        <jobs_root>/generate_runs.csv                        one row per source, for the KPI log

Needs   ANTHROPIC_API_KEY set (setx ANTHROPIC_API_KEY "...") and:  py -m pip install anthropic
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

VAULT_FOLDERS = ["reference", "core", "cases", "quizzes", "theme"]
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_PRICES = {"input": 2.0, "output": 10.0}   # US$ per million tokens; check the Console
MAX_SOURCE_WORDS = 40000
RUN_LOG_FIELDS = ["job", "source", "source_title", "kind", "model", "input_tokens", "output_tokens",
                  "cost_usd", "seconds", "notes_written", "links_to_existing", "status", "finished"]

SYSTEM_PROMPT = """You are myTutor, a study assistant that turns MBA course material into Obsidian notes \
for a student's long-term knowledge base. You write in clear, plain English for a busy manager.

You receive ONE source (lecture slides, a reading, or a case) and return notes through the save_notes tool.

NOTES TO WRITE
1. ONE reference note (folder "reference") for the source:
   - overview of 3 sentences; 5 to 8 key points in the source's order; frameworks or models named in the source,
     each linked to its core note; 3 "Questions I should be able to answer"; a Related section linking every
     core and case note from this run, the quiz note "Quiz - <Course> <Day> - <Source title>", and the journal note.
2. THREE TO SIX core notes (folder "core"), one per important concept, model or framework:
   - Definition (plain words), Why it matters, Example from the source, Related concepts, Cases that illustrate it,
     Source link to the reference note. Under 200 words each. For slides, focus on the concepts the lecture teaches.
3. ONE case note per real organisation discussed as a case (folder "cases"), ONLY if the source contains one:
   - Context, Problem, What they did, Outcome (figures only if the source gives them), Concepts illustrated, Source.
4. FIVE quiz questions in the "quiz" field (not as a note): multiple choice, testing understanding and
   application, not wording; 4 options each with exactly one correct. Wrong options must be plausible: closely related theories,
   reasonable managerial decisions or common misunderstandings, similar in length, detail and tone to the
   right answer, so it cannot be found by elimination; no absurd options. Mix difficulty: 2 recall, 2 applied
   to a scenario, 1 combining two concepts. Vary which option (0-3) is correct; never refer to options by letter. For each give a
   one- or two-sentence explanation of why the answer is right, and "concept" = the exact title of the core or
   reference note the question comes from. The quiz note is built from this data automatically.

LINKING
- EXISTING NOTE TITLES lists notes already in the vault or created earlier in this run. When a concept or case
  matches one, link it with [[Exact Title]] and DO NOT write a new note for it.
- Link concepts to each other where the source connects them. Link each case to the concepts it illustrates.
- Never link to a title that is neither in EXISTING NOTE TITLES nor written in this response.

ACCURACY
- Use only the source text. No outside facts. If something is unclear, write "Unclear in source".
- Keep the source's own names for models and frameworks. Do not invent statistics or quotes.

NAMING (match the student's existing vault)
- Reference notes are named after the source itself, e.g. "Peter Fader - Customer Centricity and CLV" or
  "Digital Does Not Have to Be Disruptive". Case notes start with "Case - ", e.g. "Case - Kodak".
- Core notes are named after the concept in title case, e.g. "Category Entry Points".

FORMAT
- Each note is Markdown with YAML frontmatter, following the templates below exactly (fill the <...> parts).
- filename = the note title + ".md". Titles must not contain / \\ : * ? " < > |
- Put the ORIGINAL LINK exactly as given in the reference note's frontmatter and its first body line.
- Use the course, day and date values given. Never write insights, opinions or lessons learnt: those are the
  student's own, in the journal.

TEMPLATES
reference/<Source title>.md   (a book: "Book - <Author> - <Title>.md")
---
type: reference
course: <course>
day: <day>
kind: <slides|reading|case|summary>
source: "<source file name>"
original: "<ORIGINAL LINK>"
created: <date>
status: unreviewed
tags: [mytutor, reference]
---
# <Source title>
Original document: [<source file name>](<ORIGINAL LINK>)
## Overview
## Key points
## Frameworks and models
## Questions I should be able to answer
## Related

core/<Concept name>.md
---
type: core
course: <course>
first_seen: "<source file name>"
created: <date>
status: unreviewed
tags: [mytutor, core]
---
# <Concept name>
**Definition:**
**Why it matters:**
**Example from the source:**
**Related concepts:**
**Cases that illustrate it:**
**Source:** [[<reference note title>]]

cases/Case - <Organisation>.md   (two cases on one organisation: "Case - <Organisation> - <topic>.md")
---
type: case
course: <course>
day: <day>
organisation: "<name>"
source: "<source file name>"
created: <date>
status: unreviewed
tags: [mytutor, case]
---
# Case - <Organisation>
**Context:**
**Problem:**
**What they did:**
**Outcome:**
**Concepts illustrated:**
**Source:** [[<reference note title>]]

"""

SAVE_NOTES_TOOL = {
    "name": "save_notes",
    "description": "Save the notes written for this source.",
    "input_schema": {
        "type": "object",
        "properties": {
            "source_title": {"type": "string", "description": "The real title of the source, from its content."},
            "kind": {"type": "string", "enum": ["slides", "reading", "case", "summary"]},
            "notes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "folder": {"type": "string", "enum": ["reference", "core", "cases"]},
                        "filename": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["folder", "filename", "content"],
                },
            },
            "quiz": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "options": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                        "answer": {"type": "integer", "minimum": 0, "maximum": 3,
                                   "description": "index of the correct option, 0 to 3"},
                        "explanation": {"type": "string"},
                        "concept": {"type": "string", "description": "exact title of the note it tests"},
                    },
                    "required": ["question", "options", "answer", "explanation", "concept"],
                },
            },
        },
        "required": ["source_title", "kind", "notes", "quiz"],
    },
}


# ---------------------------------------------------------------- helpers

def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", name).strip().rstrip(".")
    name = re.sub(r"\s{2,}", " ", name)
    if not name.lower().endswith(".md"):
        name += ".md"
    return name[:150]


def file_link(path: str) -> str:
    """A link Obsidian can open: file:///C:/Users/...  (spaces encoded)."""
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    return "file:///" + quote(path.replace("\\", "/"), safe="/:")


def parse_folder(folder: str) -> tuple[str, str]:
    """'MBAM601_DigitalTransformation.../Day 1' -> ('MBAM601', 'Day 1')."""
    parts = [p for p in folder.replace("\\", "/").split("/") if p]
    course = re.split(r"[_\s-]", parts[0])[0] if parts else "COURSE"
    day = parts[-1] if len(parts) > 1 else ""
    return course, day


NOTE_FOLDERS = {"reference", "ref", "core", "cases", "quizzes", "quiz", "theme"}


def vault_titles(vault: Path | None) -> set[str]:
    """Note titles in any reference/core/cases/quizzes/theme folder, at any depth.

    Works for one shared set of folders and for one set per course
    (e.g. 'MBAM622-26T3 - Marketing.../core'), so new notes can link across courses.
    """
    titles = set()
    if vault and vault.exists():
        for p in vault.rglob("*.md"):
            parts = {x.lower() for x in p.relative_to(vault).parts[:-1]}
            if ".obsidian" in parts or ".trash" in parts:
                continue
            if parts & NOTE_FOLDERS:
                titles.add(p.stem)
    return titles


def estimate_tokens(words: int) -> int:
    return int(words * 1.35) + 3500   # source text + prompt and templates


def cost_usd(inp: int, out: int, prices: dict) -> float:
    return round(inp / 1e6 * prices["input"] + out / 1e6 * prices["output"], 4)


def append_csv(path: Path, fields: list, row: dict) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow(row)


# ---------------------------------------------------------------- one source

def build_user_message(course, day, today, src, origin_link, kind_guess, titles, text) -> str:
    title_list = "\n".join(f"- {t}" for t in sorted(titles)) or "- (none yet)"
    return (
        f"COURSE: {course}\nDAY: {day}\nDATE: {today}\n"
        f"SOURCE FILE: {Path(src).name}\nORIGINAL LINK: {origin_link}\n"
        f"KIND GUESS (check it against the content): {kind_guess}\n"
        f"JOURNAL NOTE TITLE: {course} {day} - Journal\n\n"
        f"EXISTING NOTE TITLES:\n{title_list}\n\n"
        f"SOURCE TEXT:\n<source>\n{text}\n</source>"
    )


def _json_from_text(text: str):
    """Fallback: notes returned as JSON text instead of a tool call."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) and "notes" in data else None


def call_claude(client, model, user_message, max_tokens=12000, tool_choice=None):
    # Some models do not allow a forced tool choice, so "auto" is the default; the prompt asks for the tool.
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT + "\nAlways return your answer by calling the save_notes tool exactly once.",
        tools=[SAVE_NOTES_TOOL],
        tool_choice=tool_choice or {"type": "auto"},
        messages=[{"role": "user", "content": user_message}],
    )
    if getattr(resp, "stop_reason", "") == "max_tokens":
        raise ValueError("response was cut off (max_tokens); try again or split the source")
    block = next((b for b in resp.content if getattr(b, "type", "") == "tool_use"), None)
    if block is not None:
        result = block.input
    else:
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        result = _json_from_text(text)
        if result is None:
            raise ValueError("Claude did not return notes in the expected format")
    return normalise_result(result), resp.usage.input_tokens, resp.usage.output_tokens


def _maybe_json(value):
    """Tool input fields sometimes arrive as JSON text instead of a list or object."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def normalise_result(result) -> dict:
    """Accept the shapes Claude occasionally returns: the whole input, or its notes/quiz, as JSON text."""
    result = _maybe_json(result)
    if not isinstance(result, dict):
        raise ValueError("Claude did not return notes in the expected format")
    for key in ("notes", "quiz"):
        value = _maybe_json(result.get(key))
        if isinstance(value, dict):          # a single note or question instead of a list
            value = [value]
        items = value if isinstance(value, list) else []
        result[key] = [_maybe_json(i) for i in items]
        result[key] = [i for i in result[key] if isinstance(i, dict)]
    if not result["notes"]:
        raise ValueError("Claude returned no usable notes; run this source again")
    return result


def write_notes(notes_dir: Path, result: dict, known_titles: set, origin_link: str) -> tuple[list, int]:
    written, links_existing = [], 0
    existing_before = set(known_titles)
    for note in result.get("notes", []):
        folder = note.get("folder")
        if folder not in VAULT_FOLDERS:
            continue
        fname = safe_filename(note.get("filename", ""))
        title = fname[:-3]
        if folder in ("core", "cases") and title in existing_before:
            continue                      # already in the vault: link, don't duplicate
        content = note.get("content", "").strip() + "\n"
        if folder == "reference" and origin_link and origin_link not in content:
            content += f"\nOriginal document: [{Path(origin_link).name}]({origin_link})\n"
        dest = notes_dir / folder / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        written.append(f"{folder}/{fname}")
        known_titles.add(title)
        links_existing += sum(1 for t in re.findall(r"\[\[([^\]|#]+)", content) if t.strip() in existing_before)
    return written, links_existing


def valid_quiz(items) -> list:
    out = []
    for q in items or []:
        opts = q.get("options") or []
        if len(opts) == 4 and isinstance(q.get("answer"), int) and 0 <= q["answer"] <= 3 and q.get("question"):
            out.append({"question": q["question"].strip(), "options": [str(o).strip() for o in opts],
                        "answer": q["answer"], "explanation": str(q.get("explanation", "")).strip(),
                        "concept": str(q.get("concept", "")).strip()})
    return out


def write_quiz(notes_dir: Path, quiz_dir: Path, course: str, day: str, today: str, source_file: str,
               source_title: str, reference_title: str, quiz: list, known_titles: set) -> list:
    """Quiz note for Obsidian + quiz data for the practice page."""
    if not quiz:
        return []
    title = f"Quiz - {course} {day} - {source_title}".strip()
    letters = "ABCD"
    lines = ["---", "type: quiz", f"course: {course}", f"day: {day}", f'source: "{source_file}"',
             f"created: {today}", "taken_on:", "score:", "tags: [mytutor, quiz]", "---", "",
             f"# Quiz: {source_title}", ""]
    if reference_title:
        lines += [f"Source: [[{reference_title}]]", ""]
    for i, q in enumerate(quiz, start=1):
        lines.append(f"{i}. {q['question']}")
        lines += [f"   - {letters[j]}. {o}" for j, o in enumerate(q["options"])]
        lines.append("")
    lines.append("> [!success]- Answers")
    for i, q in enumerate(quiz, start=1):
        target = q["concept"] if q["concept"] in known_titles else reference_title
        see = f" See [[{target}]]." if target else ""
        lines.append(f"> {i}. {letters[q['answer']]}. {q['explanation']}{see}")
    note = notes_dir / "quizzes" / safe_filename(title)
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("\n".join(lines) + "\n", encoding="utf-8")
    known_titles.add(note.stem)
    data = {"course": course, "day": day, "source": source_file, "source_title": source_title,
            "reference": reference_title, "questions": quiz}
    quiz_dir.mkdir(parents=True, exist_ok=True)
    (quiz_dir / (note.stem + ".json")).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return [f"quizzes/{note.name}"]


def write_journal_stub(notes_dir: Path, course: str, day: str, term: str, today: str, written: list,
                       known_titles: set) -> str | None:
    title = f"{course} {day} - Journal".strip()
    if title in known_titles:
        return None

    def links(folder):
        items = [w.split("/", 1)[1][:-3] for w in written if w.startswith(folder + "/")]
        return ", ".join(f"[[{t}]]" for t in items) or "(none)"

    body = f"""---
type: theme
level: day
term: {term}
course: {course}
day: {day}
created: {today}
tags: [journal, reflection]
---

# {course} {day} journal

## This day's notes
- Reference: {links('reference')}
- Core: {links('core')}
- Cases: {links('cases')}
- Quizzes: {links('quizzes')}

## Lesson: {today} <topic>

**What stood out:**

**How it connects to my own experience:**

**What I disagree with or doubt:**

**Lesson learnt, in one sentence:**

## Reflection

**The idea I will keep using:**

**What changed in how I think:**

**What I will do differently:**

**Questions still open:**
"""
    dest = notes_dir / "theme" / safe_filename(title)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")
    known_titles.add(title)
    return f"theme/{dest.name}"


PRACTICE_SET = "practice-set.json"


def same_day_jobs(job_dir: Path) -> list:
    """Other job folders for the same course/day folder (files added to a day later get a new job)."""
    try:
        folder = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8")).get("folder", "")
    except (OSError, ValueError):
        return []
    out = []
    for other in sorted(job_dir.parent.glob("*")):
        if other == job_dir or not (other / "manifest.json").exists():
            continue
        try:
            if json.loads((other / "manifest.json").read_text(encoding="utf-8")).get("folder", "") == folder:
                out.append(other)
        except (OSError, ValueError):
            continue
    return out


def build_practice_set(job_dir: Path, notes_dir: Path, course: str, day: str, today: str,
                       source_order: list, size: int = 20, other_jobs: list = ()) -> str | None:
    """Pick a fixed practice set once per day: spread across sources, as many different concepts as possible.
    Draws on this job and on earlier jobs for the same day."""
    quiz_dir = job_dir / "quiz"
    pools = []
    def pool_of(data):
        return [{**q, "source": data.get("source_title", ""), "reference": data.get("reference", "")}
                for q in data.get("questions", [])]
    for rel in source_order:                       # slides first, then readings, then cases
        for f in sorted(quiz_dir.glob("*.json")):
            if f.name == PRACTICE_SET:
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("source") == Path(rel).name:
                pools.append(pool_of(data))
    for other in other_jobs:
        for f in sorted((Path(other) / "quiz").glob("*.json")):
            if f.name == PRACTICE_SET:
                continue
            try:
                pools.append(pool_of(json.loads(f.read_text(encoding="utf-8"))))
            except (OSError, ValueError):
                continue
    pools = [pl for pl in pools if pl]
    if not pools:
        return None
    chosen, concepts = [], set()
    for unique_only in (True, False):              # first pass: new concepts only; second: fill up
        progress = True
        while len(chosen) < size and progress:
            progress = False
            for pool in pools:
                for q in list(pool):
                    if unique_only and q["concept"] in concepts:
                        continue
                    chosen.append(q)
                    concepts.add(q["concept"])
                    pool.remove(q)
                    progress = True
                    break
                if len(chosen) >= size:
                    break
    title = f"Practice - {course} {day}".strip()
    data = {"course": course, "day": day, "built": today, "title": title, "questions": chosen}
    quiz_dir.mkdir(parents=True, exist_ok=True)
    (quiz_dir / PRACTICE_SET).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    letters = "ABCD"
    lines = ["---", "type: practice", f"course: {course}", f"day: {day}", f"created: {today}",
             f"questions: {len(chosen)}", "taken_on:", "score:", "tags: [mytutor, quiz, practice]", "---", "",
             f"# {title}", "", f"{len(chosen)} questions across this day's sources. Answers at the end.", ""]
    for i, q in enumerate(chosen, start=1):
        lines.append(f"{i}. {q['question']}")
        lines += [f"   - {letters[j]}. {o}" for j, o in enumerate(q["options"])]
        lines.append("")
    lines.append("> [!success]- Answers")
    for i, q in enumerate(chosen, start=1):
        see = q["concept"] or q["reference"]
        lines.append(f"> {i}. {letters[q['answer']]}. {q['explanation']}" + (f" See [[{see}]]." if see else ""))
    note = notes_dir / "quizzes" / safe_filename(title)
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"quizzes/{note.name}"


# ---------------------------------------------------------------- the run

def generate_job(job_dir: Path, client, cfg: dict, only: str | None = None, force: bool = False,
                 estimate: bool = False, log_path: Path | None = None, rebuild_set: bool = False) -> dict:
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    extract = json.loads((job_dir / "extract.json").read_text(encoding="utf-8"))
    origins = {f["rel_path"]: f.get("origin", "") for f in manifest["files"]}
    course, day = parse_folder(manifest.get("folder", ""))
    model = cfg.get("model", DEFAULT_MODEL)
    prices = cfg.get("price_per_mtok", DEFAULT_PRICES)
    today = date.today().isoformat()
    vault = Path(os.path.expanduser(cfg["vault_path"])) if cfg.get("vault_path") else None
    notes_dir = job_dir / "notes"
    report_path = job_dir / "generate.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {"sources": {}}

    known = vault_titles(vault) | vault_titles(notes_dir)
    sources = [e for e in extract["files"] if e["status"] == "extracted"]
    if only:
        sources = [e for e in sources if only.lower() in e["rel_path"].lower()]
    # Slides first: the lecture defines the core concepts that readings and cases then link to.
    order = {"slides": 0, "reading": 1, "case": 2}
    sources.sort(key=lambda e: (order.get(e.get("kind_guess"), 1), e["rel_path"]))

    all_written = []
    for e in sources:
        rel = e["rel_path"]
        prev = report["sources"].get(rel)
        if prev and prev.get("status") == "done" and not force:
            print(f"skipped    {rel}  (already generated; --force to redo)")
            all_written += prev.get("notes", [])
            continue
        if prev and force and not estimate:
            for n in prev.get("notes", []):          # replace this source's earlier notes cleanly
                (notes_dir / n).unlink(missing_ok=True)
                known.discard(Path(n).stem)
                if n.startswith("quizzes/"):
                    (job_dir / "quiz" / (Path(n).stem + ".json")).unlink(missing_ok=True)
        text = (job_dir / e["text_path"]).read_text(encoding="utf-8")
        words = len(text.split())
        if words > MAX_SOURCE_WORDS:
            text = " ".join(text.split()[:MAX_SOURCE_WORDS]) + "\n\n[Source truncated by myTutor]"
        if estimate:
            est_in = estimate_tokens(min(words, MAX_SOURCE_WORDS))
            est_out = 5000
            print(f"estimate   {rel}: ~{est_in:,} in + ~{est_out:,} out = ~US${cost_usd(est_in, est_out, prices):.2f}")
            continue

        origin_link = file_link(origins.get(rel, ""))
        msg = build_user_message(course, day, today, rel, origin_link, e.get("kind_guess", ""), known, text)
        t0 = time.perf_counter()
        row = {"job": job_dir.name, "source": rel, "model": model, "status": "failed",
               "input_tokens": 0, "output_tokens": 0, "cost_usd": 0, "notes_written": 0,
               "links_to_existing": 0, "source_title": "", "kind": ""}
        try:
            result, tin, tout = call_claude(client, model, msg, max_tokens=int(cfg.get("max_output_tokens", 12000)),
                                            tool_choice=cfg.get("tool_choice"))
            written, linked = write_notes(notes_dir, result, known, origin_link)
            ref_title = next((w.split("/", 1)[1][:-3] for w in written if w.startswith("reference/")), "")
            quiz = valid_quiz(result.get("quiz"))
            written += write_quiz(notes_dir, job_dir / "quiz", course, day, today, Path(rel).name,
                                  result.get("source_title", Path(rel).stem), ref_title, quiz, known)
            row.update(status="done", input_tokens=tin, output_tokens=tout,
                       cost_usd=cost_usd(tin, tout, prices), notes_written=len(written),
                       links_to_existing=linked, source_title=result.get("source_title", ""),
                       kind=result.get("kind", ""))
            report["sources"][rel] = {**row, "notes": written}
            all_written += written
            print(f"done       {rel}: {len(written)} notes, {tin:,}+{tout:,} tokens, US${row['cost_usd']:.3f}")
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            report["sources"][rel] = {**row, "notes": []}
            print(f"FAILED     {rel}: {row['error']}")
        row["seconds"] = round(time.perf_counter() - t0, 1)
        report["sources"][rel]["seconds"] = row["seconds"]
        row["finished"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        if log_path:
            append_csv(log_path, RUN_LOG_FIELDS, {k: row.get(k, "") for k in RUN_LOG_FIELDS})
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if not estimate:
        # The staged journal stub lists every note made for the day so far (all runs, not just this one).
        # It is rewritten each run; it is skipped only if a journal with that title is already in the vault.
        day_notes = [n for r in report["sources"].values() if r.get("status") == "done" for n in r.get("notes", [])]
        for other in same_day_jobs(job_dir):          # files added to the day earlier, in other jobs
            try:
                prev_report = json.loads((other / "generate.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            day_notes += [n for r in prev_report.get("sources", {}).values() if r.get("status") == "done"
                          for n in r.get("notes", []) if n not in day_notes]
        if day_notes:
            stub = write_journal_stub(notes_dir, course, day, cfg.get("term", ""), today, day_notes,
                                      vault_titles(vault))
            if stub:
                report["journal"] = stub

    # The day's practice set is built once, when every source of the day has its notes.
    if not estimate:
        every = [e for e in extract["files"] if e["status"] == "extracted"]
        every.sort(key=lambda e: (order.get(e.get("kind_guess"), 1), e["rel_path"]))
        all_done = every and all(report["sources"].get(e["rel_path"], {}).get("status") == "done" for e in every)
        siblings = same_day_jobs(job_dir)
        exists = any((j / "quiz" / PRACTICE_SET).exists() for j in [job_dir, *siblings])
        if all_done and (rebuild_set or not exists):
            note = build_practice_set(job_dir, notes_dir, course, day, today, [e["rel_path"] for e in every],
                                      size=int(cfg.get("practice_questions", 20)), other_jobs=siblings)
            if note:
                report["practice_set"] = note
                print(f"\nPractice set built once for {course} {day}: {note}")
        elif exists:
            print("\nPractice set already exists: kept as it is (use --rebuild-set to replace it).")
        elif not all_done:
            missing = sum(report["sources"].get(e["rel_path"], {}).get("status") != "done" for e in every)
            print(f"\nPractice set: waiting for {missing} more source(s) to finish.")
    if not estimate:
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate Obsidian notes for a myTutor job.")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--job", help="job folder name (default: the newest)")
    parser.add_argument("--day", help='e.g. "Day 1": the newest job for that day')
    parser.add_argument("--course", help="e.g. MBAM601, when several courses have the same day")
    parser.add_argument("--only", help="only sources whose file name contains this text")
    parser.add_argument("--force", action="store_true", help="redo sources already generated")
    parser.add_argument("--estimate", action="store_true", help="show token and cost estimate only")
    parser.add_argument("--rebuild-set", action="store_true", help="replace the day's fixed practice set")
    args = parser.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8")) if Path(args.config).exists() else {}
    jobs_root = Path(os.path.expandvars(os.path.expanduser(cfg.get("jobs_root", "~/mytutor/jobs"))))
    from jobs import find_job
    job_dir = find_job(jobs_root, args.job, args.day, args.course, needs="extract.json")
    if not (job_dir / "extract.json").exists():
        sys.exit(f"Run extract.py on {job_dir.name} first")
    if not cfg.get("vault_path"):
        print('Note: "vault_path" is not set in config.json, so links to notes already in your vault '
              "cannot be made. Notes from this run still link to each other.\n")

    client = None
    if not args.estimate:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit('ANTHROPIC_API_KEY is not set. Run: setx ANTHROPIC_API_KEY "..." and open a new window.')
        import anthropic
        client = anthropic.Anthropic(max_retries=3)

    print(f"Job: {job_dir.name}\n")
    report = generate_job(job_dir, client, cfg, only=args.only, force=args.force, estimate=args.estimate,
                          log_path=None if args.estimate else jobs_root / "generate_runs.csv",
                          rebuild_set=args.rebuild_set)
    if args.estimate:
        return 0
    rows = report["sources"].values()
    done = [r for r in rows if r.get("status") == "done"]
    print(f"\n{len(done)} sources done, {sum(r['notes_written'] for r in done)} notes, "
          f"US${sum(r['cost_usd'] for r in done):.3f} in total (estimate at configured prices)")
    if report.get("journal"):
        print(f"Journal stub: {report['journal']}")
    print(f"Notes staged in: {job_dir / 'notes'}")
    return 1 if any(r.get("status") == "failed" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
