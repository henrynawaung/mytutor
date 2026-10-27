"""Find a myTutor job folder by name, by day/course, or the newest one."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def job_label(job: Path) -> tuple[str, str]:
    """(course, day) of a job, from the folder it was retrieved from."""
    try:
        folder = json.loads((job / "manifest.json").read_text(encoding="utf-8")).get("folder", "")
    except (OSError, ValueError):
        return "", ""
    parts = [p for p in folder.replace("\\", "/").split("/") if p]
    course = parts[0].split("_")[0] if parts else ""
    day = parts[-1] if len(parts) > 1 else ""
    return course, day


def find_job(jobs_root: Path, job: str | None = None, day: str | None = None, course: str | None = None,
             needs: str = "manifest.json") -> Path:
    """--job wins; else the newest job matching --day/--course; else the newest job with `needs`."""
    if job:
        path = jobs_root / job
        if not (path / needs).exists():
            sys.exit(f"Job {job} has no {needs} yet")
        return path
    candidates = [p for p in jobs_root.glob("*") if (p / needs).exists()] if jobs_root.exists() else []
    if day or course:
        def matches(p: Path) -> bool:
            c, d = job_label(p)
            return ((not day or d.lower() == day.strip().lower())
                    and (not course or c.lower() == course.strip().lower()))
        picked = [p for p in candidates if matches(p)]
        if not picked:
            known = sorted({" ".join(job_label(p)).strip() for p in candidates} - {""})
            sys.exit(f"No job for {course or ''} {day or ''}".replace("  ", " ").strip()
                     + (f". Jobs found: {', '.join(known)}" if known else ". Run the earlier stages first."))
        labels = {job_label(p) for p in picked}
        if len(labels) > 1 and not course:
            sys.exit(f"More than one course has {day}: {', '.join(c for c, _ in sorted(labels))}. "
                     f'Add --course, e.g. --course {sorted(labels)[0][0]}')
        candidates = picked
    if not candidates:
        sys.exit(f"No job with {needs} in {jobs_root}: run the earlier stages first")
    return max(candidates, key=lambda p: (p / needs).stat().st_mtime)
