"""Read-only health check of the Obsidian vault (run any time, e.g. weekly).

    py vault_doctor.py            -> jobs/vault_report.md  (+ jobs/vault_report.json)
    py vault_doctor.py --snapshot -> also jobs/vault_snapshot.zip (all .md notes, for review)

It never changes the vault. It reports:
  - broken links      [[X]] where no note or file X exists
  - orphan notes      concept/case/reference notes that no other note links to
  - near-duplicates   notes whose titles mean the same thing
  - missing frontmatter / unreviewed notes
"""

import argparse
import itertools
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

LINK = re.compile(r"\[\[([^\]|#^]+)(?:[#^][^\]|]*)?(?:\|[^\]]*)?\]\]")
STOP = {"a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "vs", "versus", "with", "as", "by", "is"}
SKIP_ORPHAN = ("journal", "quiz", "practice", "phrasebook", "assignment")


def frontmatter(text: str) -> dict:
    m = re.match(r"\A---\n(.*?)\n---\n", text.replace("\r\n", "\n"), re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def words(title: str) -> frozenset:
    t = re.sub(r"[^a-z0-9 ]", " ", title.lower().replace("&", " and "))
    out = set()
    for w in t.split():
        if w in STOP:
            continue
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return frozenset(out)


def scan(vault: Path) -> dict:
    notes = {}
    names = set()
    for p in vault.rglob("*"):
        rel = p.relative_to(vault)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if p.is_file():
            names.add(p.stem.lower())
            names.add(p.name.lower())
        if p.suffix.lower() != ".md" or not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        notes[rel.as_posix()] = {"title": p.stem, "fm": frontmatter(text),
                                 "links": [l.strip() for l in LINK.findall(text)],
                                 "words": len(text.split())}
    return {"notes": notes, "names": names}


def check(vault: Path) -> dict:
    data = scan(vault)
    notes, names = data["notes"], data["names"]
    by_title = defaultdict(list)
    for rel, n in notes.items():
        by_title[n["title"].lower()].append(rel)

    broken = defaultdict(list)                     # target -> notes linking to it
    incoming = Counter()
    for rel, n in notes.items():
        for t in set(n["links"]):
            key = t.split("/")[-1].lower()
            if key.endswith(".md"):
                key = key[:-3]
            if key in names:
                incoming[key] += 1
            else:
                broken[t].append(rel)

    orphans = []
    for rel, n in notes.items():
        kind = (n["fm"].get("type") or "").lower()
        low = rel.lower()
        if any(s in low for s in SKIP_ORPHAN) or kind in ("quiz", "theme", "journal"):
            continue
        if incoming[n["title"].lower()] == 0:
            orphans.append(rel)

    same_title = {t: r for t, r in by_title.items() if len(r) > 1}
    near = []
    concept = [(rel, n["title"], words(n["title"])) for rel, n in notes.items()
               if (n["fm"].get("type") or "").lower() in ("core", "case", "framework-note", "concept", "")
               and not any(s in rel.lower() for s in SKIP_ORPHAN)]
    for (r1, t1, w1), (r2, t2, w2) in itertools.combinations(concept, 2):
        if t1.lower() == t2.lower() or not w1 or not w2:
            continue
        j = len(w1 & w2) / len(w1 | w2)
        if j >= 0.6 or (len(w1) >= 2 and (w1 <= w2 or w2 <= w1)):
            near.append({"a": r1, "b": r2, "score": round(j, 2)})
    near.sort(key=lambda x: -x["score"])

    no_fm = [rel for rel, n in notes.items() if not n["fm"].get("type") and not rel.endswith("Phrasebook.md")]
    unreviewed = [rel for rel, n in notes.items() if n["fm"].get("status") == "unreviewed"]
    per_course = Counter(rel.split("/")[0] if "/" in rel else "(top level)" for rel in notes)
    kinds = Counter((n["fm"].get("type") or "none") for n in notes.values())
    return {"notes": len(notes), "per_course": per_course, "kinds": kinds,
            "broken": {k: v for k, v in sorted(broken.items(), key=lambda kv: -len(kv[1]))},
            "orphans": sorted(orphans), "same_title": same_title, "near_duplicates": near,
            "no_frontmatter": sorted(no_fm), "unreviewed": len(unreviewed)}


def report_md(r: dict) -> str:
    L = ["# Vault health report", "",
         f"- Notes: **{r['notes']}**  " + ", ".join(f"{c.split(' - ')[0]}: {n}" for c, n in r["per_course"].items()),
         f"- Types: " + ", ".join(f"{k} {v}" for k, v in r["kinds"].most_common()),
         f"- Broken link targets: **{len(r['broken'])}** (links to notes that do not exist)",
         f"- Orphan notes: **{len(r['orphans'])}** (no other note links to them)",
         f"- Same title in more than one place: **{len(r['same_title'])}**",
         f"- Near-duplicate title pairs: **{len(r['near_duplicates'])}**",
         f"- Notes without frontmatter: **{len(r['no_frontmatter'])}**",
         f"- Unreviewed notes: **{r['unreviewed']}**", ""]
    L += ["## Broken links (target  <-  linked from)", ""]
    L += [f"- [[{t}]]  <-  {len(v)} note(s), e.g. {Path(v[0]).stem}" for t, v in r["broken"].items()]
    L += ["", "## Same title", ""] + [f"- {t}: {', '.join(v)}" for t, v in r["same_title"].items()]
    L += ["", "## Near-duplicate titles", ""] + [f"- {Path(x['a']).stem}  ~  {Path(x['b']).stem}  ({x['score']})"
                                               for x in r["near_duplicates"]]
    L += ["", "## Orphans", ""] + [f"- {o}" for o in r["orphans"]]
    L += ["", "## No frontmatter", ""] + [f"- {o}" for o in r["no_frontmatter"]]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--snapshot", action="store_true", help="also zip all notes into jobs/vault_snapshot.zip")
    a = ap.parse_args(argv)
    here = Path(__file__).resolve().parent
    cfg = json.loads((here / a.config).read_text(encoding="utf-8"))
    vault = Path(os.path.expanduser(cfg["vault_path"]))
    jobs = Path(os.path.expandvars(os.path.expanduser(cfg.get("jobs_root", "~/mytutor/jobs"))))
    jobs.mkdir(parents=True, exist_ok=True)
    r = check(vault)
    (jobs / "vault_report.md").write_text(report_md(r), encoding="utf-8")
    (jobs / "vault_report.json").write_text(json.dumps(r, indent=1, default=dict), encoding="utf-8")
    print(report_md(r).split("## Broken")[0])
    print(f"Report: {jobs / 'vault_report.md'}")
    if a.snapshot:
        z = jobs / "vault_snapshot.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
            for p in vault.rglob("*.md"):
                rel = p.relative_to(vault)
                if not any(x.startswith(".") for x in rel.parts):
                    f.write(p, rel.as_posix())
        print(f"Snapshot: {z}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
