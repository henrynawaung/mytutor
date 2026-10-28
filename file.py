"""myTutor stage 4: copy the staged notes into your Obsidian vault, then pick a sample to spot-check.

Usage
    py file.py --day "Day 1" --dry-run      # show where every note would go, change nothing
    py file.py --day "Day 1"                # file the notes
    py file.py --day "Day 1" --sample 10    # file, then pick 10 random notes for the quality check
    py file.py --day "Day 1" --sample 10 --no-file   # only pick a sample (notes already filed)

Where notes go
    <vault>/<course folder>/<Day N>/Ref | Core | Cases | Quizzes, and the journal in <Day N> itself
    (set "day_folders": false in config.json for one set of folders per course instead)
    The course folder is the existing one starting with the course code (e.g. "MBAM601-..."),
    or "course_folders" in config.json, or a new "<code>-<term_label> - <course name>" folder.

Never overwrites your edits
    A note already in the vault is replaced only if it is still exactly what myTutor filed last time.
    If you have changed it (or wrote it yourself), it is kept and reported as "kept yours".

Writes
    <jobs_root>/filed.json          what was filed where, with a fingerprint of each file
    <jobs_root>/file_runs.csv       one row per run
    <jobs_root>/quality_audit.csv   the sample: automatic checks filled in, "accurate" left for you
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

DEFAULT_FOLDERS = {"reference": "Ref", "core": "Core", "cases": "Cases", "quizzes": "Quizzes", "theme": ""}
# "" = straight into the day folder. Layout: <vault>/<course folder>/<Day N>/<folder>/<note>.md
SMALL_WORDS = {"and", "of", "the", "in", "for", "to", "a", "an", "on", "with"}
AUDIT_FIELDS = ["date", "job", "note", "folder", "in_right_folder", "frontmatter_complete",
                "links_to_source", "links_to_existing_note", "accurate", "comment"]
RUN_FIELDS = ["finished", "job", "course_folder", "filed", "updated", "unchanged", "kept_yours", "sampled"]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pretty_course_name(inbox_folder: str) -> str:
    """'MBAM601_DigitalTransformationAndTechnologyPreparedness' -> 'Digital Transformation and Technology Preparedness'."""
    tail = inbox_folder.split("_", 1)[1] if "_" in inbox_folder else ""
    words = re.findall(r"[A-Z][a-z]*|[a-z]+|\d+", tail)
    out = [w if i == 0 or w.lower() not in SMALL_WORDS else w.lower() for i, w in enumerate(words)]
    return " ".join(out)


def course_folder(vault: Path, course: str, inbox_folder: str, cfg: dict) -> Path:
    named = (cfg.get("course_folders") or {}).get(course)
    if named:
        return vault / named
    if vault.exists():
        existing = sorted(p for p in vault.iterdir() if p.is_dir() and p.name.upper().startswith(course.upper()))
        if existing:
            return existing[0]
    label = cfg.get("term_label", "")
    name = f"{course}-{label}" if label else course
    pretty = pretty_course_name(inbox_folder)
    return vault / (f"{name} - {pretty}" if pretty else name)


def frontmatter_complete(text: str) -> bool:
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if not m:
        return False
    keys = {ln.split(":", 1)[0].strip() for ln in m.group(1).splitlines() if ":" in ln}
    return {"type", "course", "created"} <= keys or {"type", "course"} <= keys and "tags" in keys


def links_in(text: str) -> list[str]:
    return [t.split("|")[0].split("#")[0].strip() for t in re.findall(r"\[\[([^\]]+)\]\]", text)]


def file_job(job_dir: Path, vault: Path, cfg: dict, jobs_root: Path, dry_run: bool = False) -> dict:
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    parts = [x for x in manifest.get("folder", "").replace("\\", "/").split("/") if x]
    inbox_folder = parts[0] if parts else ""
    day = parts[-1] if len(parts) > 1 else ""
    course = re.split(r"[_\s-]", inbox_folder)[0] if inbox_folder else "COURSE"
    target = course_folder(vault, course, inbox_folder, cfg)
    folders = {**DEFAULT_FOLDERS, **(cfg.get("vault_folders") or {})}
    index_path = jobs_root / "filed.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}

    result = {"course_folder": str(target), "filed": [], "updated": [], "unchanged": [], "kept_yours": []}
    notes_dir = job_dir / "notes"
    for src in sorted(notes_dir.rglob("*.md")):
        kind = src.parent.name
        if kind not in folders:
            continue
        sub = folders[kind]
        dest = target / day / sub / src.name if sub else target / day / src.name
        if not cfg.get("day_folders", True):
            dest = target / sub / src.name if sub else target / src.name
        rel = dest.relative_to(vault).as_posix()
        new = src.read_text(encoding="utf-8")
        if dest.exists():
            current = dest.read_text(encoding="utf-8")
            if current == new:
                result["unchanged"].append(rel)
                continue
            if index.get(rel, {}).get("sha") != sha(current):
                result["kept_yours"].append(rel)          # edited by you, or not ours: never overwrite
                continue
            bucket = "updated"
        else:
            bucket = "filed"
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(new, encoding="utf-8")
            index[rel] = {"sha": sha(new), "job": job_dir.name, "kind": kind,
                          "filed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
        result[bucket].append(rel)
    if not dry_run:
        index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def pick_sample(job_dir: Path, vault: Path, jobs_root: Path, n: int, seed: int | None = None,
                by_type: bool = False) -> list[dict]:
    """Random notes from this job (journal excluded), with the automatic checks filled in.

    by_type=True spreads the sample across note types (reference, core, case, ...) as evenly
    as the job allows, so an accuracy audit is not dominated by one type."""
    index_path = jobs_root / "filed.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    mine = [rel for rel, v in index.items() if v.get("job") == job_dir.name and v.get("kind") != "theme"
            and (vault / rel).exists()]
    if not mine:
        return []
    rng = random.Random(seed)
    if by_type:
        groups: dict[str, list] = {}
        for rel in sorted(mine):
            groups.setdefault(index[rel]["kind"], []).append(rel)
        for g in groups.values():
            rng.shuffle(g)
        picked, kinds = [], sorted(groups)
        while len(picked) < min(n, len(mine)):
            for k in kinds:
                if groups[k] and len(picked) < n:
                    picked.append(groups[k].pop())
        picked = sorted(picked)
    else:
        picked = sorted(rng.sample(mine, min(n, len(mine))))
    from generate import vault_titles  # titles in the vault, excluding this job's own notes
    own = {Path(r).stem for r in mine}
    other_titles = vault_titles(vault) - own
    rows = []
    for rel in picked:
        text = (vault / rel).read_text(encoding="utf-8")
        kind = index[rel]["kind"]
        links = links_in(text)
        if kind == "reference":
            to_source = "file:///" in text or "http" in text
        else:
            to_source = any(l in {Path(r).stem for r in mine if index[r]["kind"] == "reference"} for l in links)
        rows.append({
            "date": datetime.now().date().isoformat(), "job": job_dir.name, "note": Path(rel).stem, "folder": rel,
            "in_right_folder": "yes",
            "frontmatter_complete": "yes" if frontmatter_complete(text) else "no",
            "links_to_source": "yes" if to_source else "no",
            "links_to_existing_note": "yes" if any(l in other_titles for l in links) else "no",
            "accurate": "", "comment": "",
        })
    return rows


def append_csv(path: Path, fields: list, rows: list) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def obsidian_root(vault: Path) -> Path:
    """The real Obsidian vault folder: the nearest folder (vault_path or above) that has .obsidian in it."""
    for folder in [vault, *vault.parents]:
        if (folder / ".obsidian").is_dir():
            return folder
    return vault


def obsidian_link(vault_name: str, rel: str, prefix: str = "") -> str:
    path = f"{prefix}/{rel}" if prefix else rel
    return f"obsidian://open?vault={quote(vault_name)}&file={quote(path[:-3] if path.endswith('.md') else path)}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="File staged notes into the Obsidian vault.")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--job")
    parser.add_argument("--day", help='e.g. "Day 1"')
    parser.add_argument("--course", help="e.g. MBAM601")
    parser.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    parser.add_argument("--sample", type=int, default=0, help="pick N random notes to spot-check")
    parser.add_argument("--seed", type=int, help="repeat the same sample")
    parser.add_argument("--by-type", action="store_true", help="spread the sample evenly across note types")
    parser.add_argument("--no-file", action="store_true", help="only pick a sample")
    args = parser.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8")) if Path(args.config).exists() else {}
    if not cfg.get("vault_path"):
        sys.exit('Set "vault_path" in config.json first')
    vault = Path(os.path.expanduser(cfg["vault_path"]))
    if not vault.exists():
        sys.exit(f"Vault folder not found: {vault}")
    jobs_root = Path(os.path.expandvars(os.path.expanduser(cfg.get("jobs_root", "~/mytutor/jobs"))))
    from jobs import find_job
    job_dir = find_job(jobs_root, args.job, args.day, args.course, needs="generate.json")
    print(f"Job: {job_dir.name}")

    res = None
    if not args.no_file:
        res = file_job(job_dir, vault, cfg, jobs_root, dry_run=args.dry_run)
        print(f"Course folder: {res['course_folder']}{'  (dry run: nothing written)' if args.dry_run else ''}\n")
        for label, key in [("filed", "filed"), ("updated", "updated"), ("unchanged", "unchanged"), ("KEPT YOURS", "kept_yours")]:
            for rel in res[key]:
                print(f"{label:<11} {rel}")
        print(f"\n{len(res['filed'])} filed, {len(res['updated'])} updated, {len(res['unchanged'])} unchanged, "
              f"{len(res['kept_yours'])} kept as you edited them")

    rows = []
    if args.sample and not args.dry_run:
        rows = pick_sample(job_dir, vault, jobs_root, args.sample, args.seed, args.by_type)
        if rows:
            append_csv(jobs_root / "quality_audit.csv", AUDIT_FIELDS, rows)
            root = obsidian_root(vault)
            vault_name = cfg.get("obsidian_vault_name") or root.name
            prefix = vault.relative_to(root).as_posix() if root != vault else ""
            print(f"\nSpot-check these {len(rows)} notes (automatic checks already in quality_audit.csv;"
                  " you fill in 'accurate'):")
            for r in rows:
                auto = all(r[k] == "yes" for k in ("frontmatter_complete", "links_to_source"))
                print(f"  {'ok ' if auto else 'chk'}  {r['note']}\n       {obsidian_link(vault_name, r['folder'], prefix)}")
            print(f"\nAudit sheet: {jobs_root / 'quality_audit.csv'}  (opens in Excel)")
        else:
            print("\nNothing filed from this job yet, so there is nothing to sample.")

    if not args.dry_run and res is not None:
        append_csv(jobs_root / "file_runs.csv", RUN_FIELDS, [{
            "finished": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "job": job_dir.name, "course_folder": res["course_folder"], "filed": len(res["filed"]),
            "updated": len(res["updated"]), "unchanged": len(res["unchanged"]),
            "kept_yours": len(res["kept_yours"]), "sampled": len(rows)}])
    return 0


if __name__ == "__main__":
    sys.exit(main())
