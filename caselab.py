"""Case Lab: turn a situation into a board-ready case with a model answer, grounded in your own notes.

    Used by the Review app (🧭 Case Lab tab). Steps:
      1. find the notes in your vault that matter for the situation (concepts, cases, sources and your takes)
      2. one Claude call writes the case and the model answer, using those notes first and a few web
         searches of reputable sources for key points your notes do not cover (each with its source)
      3. the result is saved as a note in <vault>/Case Lab/<date>/<title>.md, so it appears in the Library

    Needs ANTHROPIC_API_KEY. Cost: roughly US$0.10-0.20 per case (tokens + up to 4 searches at US$0.01 each).
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import review_core as core

CASE_FOLDER = "Case Lab"
STOP = set("""a an the and or but if of to in on at for from by with about into over under is are was were be been
being this that these those it its as we our you your they their them he she his her i me my not no so than then
there here what which who whom how why when where will would should could can may might must do does did done
have has had more most less very also just only any some such each other own same too up down out off again""".split())

SYSTEM = """You are a board-level strategy adviser and case writer for an Executive MBA student who is a project
manager in Singapore healthcare IT and is preparing for C-suite and board roles.
Write in clear, plain British English. Be specific and practical. Never invent facts about real organisations or people;
when the input gives no figures, say what data a board would ask for instead of making numbers up.
Use the student's own notes first. Quote the student's own takes where they fit (mark them "Your take:").
Link to a note with Obsidian links like [[Note Title]], using only titles given in the notes below.
Use web search only for key points the notes do not cover, prefer reputable sources (HBR, MIT Sloan, McKinsey,
BCG, Deloitte, OECD, WHO, government and academic sources), and keep searches to what is needed."""

FORMAT = """Write the whole answer as Markdown with exactly these sections, in this order:

# <a short case title, max 8 words>

## The case
Context, the decision to be made, stakeholders and their interests, constraints, key facts (from the input only).

## Model answer
### Recommendation
### Options considered
(2-4 options, each with pros, cons and when it would be the right choice)
### Rationale
### Risks and how to reduce them
### First 90 days

## Questions the board will ask
(5-7 tough questions, each followed by a strong, concise answer)

## From your notes
(the concepts, frameworks and cases from the notes below that apply, each as [[Note Title]] with one line on how it applies;
include the student's own takes as "Your take: ..." where relevant)

## Additional key points
(points from wider reading that the notes do not cover, each ending with its source name; leave out if none)

## Gaps to study
(2-4 topics the notes do not cover yet but this kind of situation needs)
"""


def keywords(text: str, n: int = 14) -> list:
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.lower()) if w not in STOP]
    freq: dict = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda kv: (-kv[1], -len(kv[0])))][:n]


def relevant_notes(vault, situation: str, limit: int = 12) -> list:
    """Score every note by how many of the situation's key words it contains (title hits count more).
    Returns [{rel, title, type, course, excerpt, takes}] with the best `limit` notes."""
    keys = keywords(situation)
    if not keys:
        return []
    scored = []
    for p, rel in vault.notes():
        if rel.parts and rel.parts[0] == CASE_FOLDER:
            continue                                      # don't feed earlier model answers back in
        try:
            text = core.read(p)
        except OSError:
            continue
        low, title = text.lower(), p.stem.lower()
        score = sum(3 if k in title else 1 for k in keys if k in low or k in title)
        if score >= 2:
            scored.append((score, p, rel, text))
    scored.sort(key=lambda x: -x[0])
    out = []
    for score, p, rel, text in scored[:limit]:
        pr = core.props(text)
        takes = [t["body"] for t in core.list_takes(text) if t["body"].strip()]
        excerpt = re.sub(r"\n{3,}", "\n\n", core.strip_take_section(core.body(text))).strip()[:1500]
        out.append({"rel": rel.as_posix(), "title": p.stem, "type": pr.get("type", ""), "course": pr.get("course", ""),
                    "excerpt": excerpt, "takes": [t[:1200] for t in takes[-3:]]})
    return out


def build_prompt(situation: str, notes: list) -> str:
    parts = [FORMAT, "\n## The situation (from the student)\n", situation.strip()[:12000], "\n\n## The student's notes\n"]
    if not notes:
        parts.append("(No closely matching notes were found.)\n")
    for n in notes:
        parts.append(f"\n### [[{n['title']}]]  ({n['type'] or 'note'}, {n['course'] or 'no course'})\n{n['excerpt']}\n")
        for t in n["takes"]:
            parts.append(f"\nStudent's take on this note:\n{t}\n")
    return "".join(parts)


def run_case(client, model: str, situation: str, notes: list, web_search: bool = True, max_searches: int = 4) -> dict:
    """One Claude call. Returns {markdown, sources, usage}. Web-search citations are collected into a sources list."""
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}] if web_search else []
    kw = dict(model=model, max_tokens=8000, system=SYSTEM,
              messages=[{"role": "user", "content": build_prompt(situation, notes)}])
    if tools:
        kw["tools"] = tools
    resp = client.messages.create(**kw)
    text, sources, searches = [], {}, 0
    for b in resp.content:
        t = getattr(b, "type", "")
        if t == "text":
            text.append(b.text)
            for c in getattr(b, "citations", None) or []:
                url = getattr(c, "url", "")
                if url:
                    sources[url] = getattr(c, "title", "") or url
        elif t == "server_tool_use":
            searches += 1
    md = "".join(text).strip()
    md = md[md.find("# "):] if "# " in md else md          # drop any "let me search" preamble before the title
    u = getattr(resp, "usage", None)
    usage = {"input_tokens": getattr(u, "input_tokens", 0) or 0, "output_tokens": getattr(u, "output_tokens", 0) or 0,
             "searches": searches}
    return {"markdown": md, "sources": sources, "usage": usage}


def title_of(md: str, situation: str) -> str:
    m = re.search(r"^#\s+(.+)$", md, re.M)
    t = (m.group(1) if m else " ".join(situation.split()[:8])).strip()
    return core.safe_title(t)[:80] or "Case"


def save_case(vault_root: Path, situation: str, result: dict, notes: list, today: date | None = None) -> str:
    """Write the case note into <vault>/Case Lab/<date>/. Returns its vault-relative path."""
    today = today or date.today()
    md = result["markdown"]
    title = title_of(md, situation)
    body = re.sub(r"^#\s+.+\n", "", md, count=1, flags=re.M).strip()
    folder = vault_root / CASE_FOLDER / today.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    p, k = folder / f"{title}.md", 2
    while p.exists():
        p, k = folder / f"{title} ({k}).md", k + 1
    src = "\n".join(f"- [{t}]({u})" for u, t in result["sources"].items())
    used = ", ".join(f"[[{n['title']}]]" for n in notes)
    situation_q = "\n".join("> " + line for line in situation.strip().splitlines()[:40])
    text = (f"---\ntype: case\nstatus: unreviewed\ncourse: {CASE_FOLDER}\ncreated: {today.isoformat()}\n"
            f"source: Case Lab\n---\n"
            f"**Situation given:**\n{situation_q}\n\n{body}\n")
    if src:
        text += f"\n## Sources (web)\n{src}\n"
    if used:
        text += f"\n**Notes used:** {used}\n"
    u = result["usage"]
    text += (f"\n*Made by myTutor Case Lab on {today.isoformat()} · {u['input_tokens']:,} in / {u['output_tokens']:,} out tokens"
             f" · {u['searches']} web search{'es' if u['searches'] != 1 else ''}. A model answer to guide you: check facts before using them in a real board.*\n")
    p.write_text(text, encoding="utf-8")
    return p.relative_to(vault_root).as_posix()


def cost_usd(usage: dict, in_per_m: float = 3.0, out_per_m: float = 15.0) -> float:
    return round(usage["input_tokens"] / 1e6 * in_per_m + usage["output_tokens"] / 1e6 * out_per_m + usage["searches"] * 0.01, 3)


# ---------------- LinkedIn: draft a post from one of your takes, in your own voice (you edit and post it yourself)
POST_SYSTEM = """You help an Executive MBA student (project manager in Singapore healthcare IT, building a leadership
network) turn one of his own takes into a LinkedIn post. Keep HIS view and examples; do not add claims, numbers or
stories he did not give. Plain, confident British English, no hype, at most 3 relevant hashtags at the end,
no emojis unless his own posts use them. Post: 120-220 words: a strong first line, the idea, his example, one practical
takeaway for leaders, and a closing question to invite discussion.

Return ONLY one JSON object (no code fence) with these keys:
"post": the post text;
"headline": a title for the post, max 12 words;
"points": 3 or 4 key points, each {"label": max 3 words, "line": max 12 words};
"takeaway": one sentence for leaders, max 18 words;
"question": the closing question;
"topic": one of risk, people, growth, strategy, data, innovation, health, leadership, change, time;
"title_prompt": a detailed prompt for an image generator (ChatGPT, Gemini, Copilot, Midjourney) for a photo-realistic
 16:9 title image: a Southeast Asian male executive in a navy suit presenting to a boardroom or conference audience,
 seen from behind the audience, natural light, a large screen showing the headline in clean bold text and 4-5 simple
 icons with short labels from the points, professional, warm, no company logos or real brand names;
"ending_prompt": a detailed prompt for a clean 4:5 infographic ending image: the headline at the top, the points as
 numbered steps with simple icons along a path, the takeaway in a highlighted box, the closing question at the bottom,
 the small signature "Henry N. Aung", light background, modern corporate style, no logos."""


def my_posts(vault, limit: int = 3) -> list:
    """Your recent LinkedIn posts (notes titled 'My post - ...'), newest first, to match your voice."""
    found = []
    for p, rel in vault.notes():
        if p.stem.startswith("My post"):
            found.append((p.stat().st_mtime, p))
    out = []
    for _, p in sorted(found, reverse=True)[:limit]:
        t = core.body(core.read(p))
        m = re.search(r"## My post\s*\n(.+?)(?:\n## |\Z)", t, re.S)
        out.append((m.group(1) if m else t)[:1500].strip())
    return out


def _json_obj(text: str) -> dict:
    import json
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    i, j = t.find("{"), t.rfind("}")
    try:
        return json.loads(t[i:j + 1]) if i >= 0 and j > i else {}
    except ValueError:
        return {}


TOPICS = {"risk", "people", "growth", "strategy", "data", "innovation", "health", "leadership", "change", "time"}


def draft_post(client, model: str, title: str, note_text: str, take: str, examples: list) -> dict:
    voice = "\n\n---\n\n".join(examples) or "(no earlier posts yet)"
    msg = (f"## My earlier posts (match this voice)\n{voice}\n\n## The concept note: {title}\n"
           f"{core.strip_take_section(core.body(note_text))[:2500]}\n\n## My take (the heart of the post)\n{take[:3000]}")
    resp = client.messages.create(model=model, max_tokens=2500, system=POST_SYSTEM,
                                  messages=[{"role": "user", "content": msg}])
    raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    d = _json_obj(raw)
    post = str(d.get("post") or raw).strip()
    pts = [{"label": str(p.get("label", ""))[:40], "line": str(p.get("line", ""))[:140]}
           for p in (d.get("points") or []) if isinstance(p, dict) and p.get("label")][:4]
    u = getattr(resp, "usage", None)
    usage = {"input_tokens": getattr(u, "input_tokens", 0) or 0, "output_tokens": getattr(u, "output_tokens", 0) or 0, "searches": 0}
    return {"text": post, "cost_usd": cost_usd(usage),
            "card": {"headline": str(d.get("headline") or title)[:120], "points": pts,
                     "takeaway": str(d.get("takeaway", ""))[:200], "question": str(d.get("question", ""))[:200],
                     "topic": d.get("topic") if d.get("topic") in TOPICS else "leadership"},
            "title_prompt": str(d.get("title_prompt", "")).strip(), "ending_prompt": str(d.get("ending_prompt", "")).strip()}
