"""myTutor one-command run: find day folders with new files and process them.

This is what n8n (or Windows Task Scheduler) calls:
    cd /d C:\\path\\to\\mytutor && py run.py --file --sample 10

For every <course>/<day> folder under synced_inbox that has files not retrieved before:
    1 retrieve -> 2 extract -> 3 generate (Claude) -> 4 file into Obsidian (with --file) -> 5 rebuild the practice page
Without --file, step 4 stays manual (py file.py --day "Day 1") so you can spot-check first.

Safe to run as often as you like:
    - files already retrieved are skipped, so Claude is never paid twice for a source
    - a folder with a file changed in the last few minutes is left for the next run (still syncing)
    - a lock stops two runs overlapping (n8n can fire again while one is running)

Options
    py run.py --dry-run      list the day folders that would be processed, do nothing
    py run.py --file         also file the notes into the vault and pick a spot-check sample
Output
    one line per day, then a final line starting "SUMMARY " with JSON (for n8n to read)
    <jobs_root>/run_log.csv  one row per run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LOCK_MAX_AGE = 2 * 3600          # a lock older than this is from a crashed run: ignore it
RUN_FIELDS = ["finished", "days_found", "days_processed", "sources", "notes", "cost_usd", "failed", "seconds", "detail"]


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def day_folders(inbox: Path) -> list[tuple[str, Path]]:
    """('<course folder>/<day folder>', path) for every second-level folder under the inbox."""
    out = []
    if not inbox.is_dir():
        return out
    for course in sorted(p for p in inbox.iterdir() if p.is_dir() and not p.name.startswith(".")):
        for day in sorted(p for p in course.iterdir() if p.is_dir() and not p.name.startswith(".")):
            out.append((f"{course.name}/{day.name}", day))
    return out


DATE_IN_NAME = re.compile(r"\d{4}-\d{2}-\d{2}")


def sort_dated_files(inbox: Path, courses: list, settle_minutes: float, dry_run: bool = False,
                     mtime_courses: list | None = None) -> list:
    """For reading courses: move files saved straight into the course folder into a folder per date
    (e.g. 2026-11-04_..._Notes.md -> <course>/2026-11-04/). Files still syncing are left for the next run."""
    wanted = {str(c).upper() for c in courses or []}
    by_mtime = {str(c).upper() for c in mtime_courses or []}      # e.g. LinkedIn posts saved without a date in the name
    moved = []
    if not wanted or not inbox.is_dir():
        return moved
    for course in sorted(p for p in inbox.iterdir() if p.is_dir()):
        if re.split(r"[_\s-]", course.name)[0].upper() not in wanted:
            continue
        undated_ok = re.split(r"[_\s-]", course.name)[0].upper() in by_mtime
        for f in sorted(p for p in course.iterdir() if p.is_file()):
            m = DATE_IN_NAME.search(f.name)
            if f.name.startswith((".", "~$")) or time.time() - f.stat().st_mtime < settle_minutes * 60:
                continue
            day = m.group(0) if m else (datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d") if undated_ok else "")
            if not day:
                continue
            dest = course / day / f.name
            if dest.exists():
                continue
            if not dry_run:
                dest.parent.mkdir(exist_ok=True)
                f.rename(dest)
            moved.append(f"{course.name}/{day}/{f.name}")
    return moved


def failed_jobs(jobs_root: Path, max_age_days: int = 30) -> list:
    """Job folders where note writing failed for at least one source (e.g. the API key was rejected),
    newest job per day folder only, from the last `max_age_days`. Those days are retried by the next run."""
    latest: dict = {}
    for job in sorted(p for p in jobs_root.iterdir() if p.is_dir()) if jobs_root.is_dir() else []:
        if time.time() - job.stat().st_mtime > max_age_days * 86400:
            continue
        try:
            folder = json.loads((job / "manifest.json").read_text(encoding="utf-8")).get("folder")
        except (OSError, ValueError):
            continue
        if folder:
            latest[folder] = job                     # sorted by name = by time, so the newest wins
    out = []
    for folder, job in sorted(latest.items()):
        try:
            rep = json.loads((job / "generate.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if any(r.get("status") == "failed" for r in rep.get("sources", {}).values()):
            out.append((folder, job))
    return out


def key_rejected(rep: dict) -> bool:
    return any(str(r.get("error", "")).startswith(("AuthenticationError", "PermissionDeniedError"))
               for r in rep.get("sources", {}).values())


def folder_status(day: Path, extensions: set, known_sha: set, settle_minutes: float) -> tuple[str, int]:
    """'new' (with count), 'syncing', or 'done'."""
    from retrieve import is_ignored
    files = [p for p in day.rglob("*") if p.is_file() and not is_ignored(p.name) and p.suffix.lower() in extensions]
    if not files:
        return "done", 0
    newest = max(p.stat().st_mtime for p in files)
    if time.time() - newest < settle_minutes * 60:
        return "syncing", 0
    new = sum(1 for p in files if file_sha(p) not in known_sha)
    return ("new", new) if new else ("done", 0)


class Lock:
    def __init__(self, path: Path):
        self.path = path
        self.held = False

    def __enter__(self):
        if self.path.exists() and time.time() - self.path.stat().st_mtime < LOCK_MAX_AGE:
            return self
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(f"{os.getpid()} {datetime.now().isoformat()}", encoding="utf-8")
        self.held = True
        return self

    def __exit__(self, *exc):
        if self.held:
            self.path.unlink(missing_ok=True)


def run(cfg: dict, client=None, dry_run: bool = False, log=print, after_day=None) -> dict:
    """after_day(day) is called right after each day is generated, e.g. to file it into the vault
    before the next day starts, so later days can link to its notes instead of writing them again."""
    import extract
    import generate
    import practice
    import retrieve

    jobs_root = Path(os.path.expandvars(os.path.expanduser(cfg.get("jobs_root", "~/mytutor/jobs"))))
    inbox = Path(os.path.expandvars(os.path.expanduser(cfg["synced_inbox"])))
    extensions = {e.lower() for e in cfg.get("extensions", retrieve.DEFAULT_EXTENSIONS)}
    index = retrieve.load_json(jobs_root / "index.json", {"sha256": {}})
    known = set(index.get("sha256", {}))
    summary = {"days_found": 0, "days_processed": 0, "sources": 0, "notes": 0, "cost_usd": 0.0,
               "failed": 0, "days": [], "status": "ok"}
    t0 = time.perf_counter()

    with Lock(jobs_root / ".run.lock") as lock:
        if not lock.held:
            summary["status"] = "already running"
            log("Another myTutor run is in progress: nothing to do.")
            return summary
        dated = list(cfg.get("reading_courses") or []) + list(cfg.get("post_courses", ["LinkedIn"]))   # sorted into date folders
        for rel in sort_dated_files(inbox, dated, float(cfg.get("settle_minutes", 3)), dry_run,
                                    mtime_courses=cfg.get("post_courses", ["LinkedIn"])):
            log(f"sorted     {rel}")
        todo = []
        for label, path in day_folders(inbox):
            status, new = folder_status(path, extensions, known, float(cfg.get("settle_minutes", 3)))
            summary["days_found"] += 1
            if status == "new":
                todo.append(label)
                log(f"new        {label}: {new} new file(s)")
            elif status == "syncing":
                log(f"waiting    {label}: files changed in the last few minutes, next run will take it")
        retry = [(f, j) for f, j in failed_jobs(jobs_root) if f not in todo]
        for f, j in retry:
            log(f"retry      {f}: note writing failed last time ({j.name})")
        if not todo and not retry:
            log("No new files.")
        if dry_run or not (todo or retry):
            summary["seconds"] = round(time.perf_counter() - t0, 1)
            return summary

        if client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                summary["status"] = "no api key"
                log("ANTHROPIC_API_KEY is not set for this process.")
                return summary
            import anthropic
            client = anthropic.Anthropic(max_retries=3)

        def record(day, label, job_dir, rep):
            done = [r for r in rep["sources"].values() if r.get("status") == "done"]
            bad = [r for r in rep["sources"].values() if r.get("status") == "failed"]
            day.update(job=job_dir.name, sources=len(done), failed=len(bad),
                       notes=sum(r.get("notes_written", 0) for r in done),
                       cost_usd=round(sum(r.get("cost_usd", 0) for r in done), 3),
                       practice_set=bool(rep.get("practice_set")))
            summary["days_processed"] += 1
            summary["sources"] += day["sources"]
            summary["notes"] += day["notes"]
            summary["cost_usd"] = round(summary["cost_usd"] + day["cost_usd"], 3)
            summary["failed"] += day["failed"]
            log(f"done       {label}: {day['sources']} sources, {day['notes']} notes, "
                f"US${day['cost_usd']:.2f}, {day['failed']} failed")
            if after_day and day["sources"]:
                after_day(day)

        # first, days whose notes failed last time (only the failed sources are redone; nothing is charged twice)
        for label, job_dir in retry:
            day = {"folder": label, "retried": True}
            try:
                rep = generate.generate_job(job_dir, client, cfg, log_path=jobs_root / "generate_runs.csv")
                record(day, label, job_dir, rep)
                if key_rejected(rep):
                    summary["status"] = "api key rejected"
                    log("API KEY REJECTED by Claude (401). Set the new key with setx, then Stop all, close and reopen "
                        "the Control Centre, and Start all. Stopping here; the waiting days will be retried next run.")
                    summary["days"].append(day)
                    summary["seconds"] = round(time.perf_counter() - t0, 1)
                    return summary
            except Exception as exc:
                day["error"] = f"{type(exc).__name__}: {exc}"
                summary["failed"] += 1
                log(f"FAILED     {label}: {day['error']}")
            summary["days"].append(day)

        source = retrieve.SyncedSource(inbox, settle_seconds=float(cfg.get("settle_seconds", 1.0)))
        for label in todo:
            day = {"folder": label}
            try:
                res = retrieve.retrieve(source, label, jobs_root, extensions=cfg.get("extensions"),
                                        max_file_mb=float(cfg.get("max_file_mb", 100)))
                if res.count("retrieved") == 0 or res.job_dir is None:
                    day["note"] = "nothing new after all"
                    summary["days"].append(day)
                    continue
                extract.extract_job(res.job_dir)
                rep = generate.generate_job(res.job_dir, client, cfg, log_path=jobs_root / "generate_runs.csv")
                record(day, label, res.job_dir, rep)
                if key_rejected(rep):
                    summary["status"] = "api key rejected"
                    log("API KEY REJECTED by Claude (401). Set the new key with setx, then Stop all, close and reopen "
                        "the Control Centre, and Start all. Stopping here; this day will be retried next run.")
                    summary["days"].append(day)
                    break
            except Exception as exc:                 # one bad day must not stop the others
                day["error"] = f"{type(exc).__name__}: {exc}"
                summary["failed"] += 1
                log(f"FAILED     {label}: {day['error']}")
            summary["days"].append(day)

        if summary["days_processed"]:
            vault = Path(os.path.expanduser(cfg["vault_path"])) if cfg.get("vault_path") else None
            payload = practice.collect(jobs_root, vault, cfg.get("obsidian_vault_name", ""))
            payload["count"] = int(cfg.get("practice_questions", 20))
            (jobs_root / "practice.html").write_text(practice.build_html(payload), encoding="utf-8")
            log("Practice page rebuilt.")
    summary["seconds"] = round(time.perf_counter() - t0, 1)
    if summary["failed"] and summary["status"] == "ok":
        summary["status"] = "some failed"
    return summary


def file_day(day: dict, here: Path, cfg_path: Path, sample: int) -> bool:
    """Run file.py for one processed day (notes into the vault, spot-check sample picked)."""
    import subprocess
    cmd = [sys.executable, str(here / "file.py"), "--config", str(cfg_path), "--job", day["job"],
           "--sample", str(sample)]
    res = subprocess.run(cmd, cwd=str(here), capture_output=True, text=True)
    print(res.stdout.rstrip())
    day["filed"] = res.returncode == 0
    if not day["filed"]:
        day["file_error"] = (res.stderr.strip().splitlines() or ["file.py failed"])[-1]
        print(f"FAILED     filing {day['folder']}: {day['file_error']}")
    return day["filed"]


def file_new_days(summary: dict, here: Path, cfg_path: Path, sample: int) -> None:
    """File every processed day not filed yet (days are normally filed one by one during the run)."""
    for day in summary["days"]:
        if not day.get("job") or not day.get("sources") or "filed" in day:
            continue
        file_day(day, here, cfg_path, sample)
    bad = [d for d in summary["days"] if d.get("filed") is False]
    if bad:
        summary["failed"] += len(bad)
        summary["status"] = "some failed"
    summary["days_filed"] = sum(1 for d in summary["days"] if d.get("filed") is True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Process every day folder with new files.")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--file", action="store_true",
                        help="also file each new day's notes into the vault and pick a spot-check sample")
    parser.add_argument("--sample", type=int, default=10, help="notes to sample when --file is used")
    args = parser.parse_args(argv)
    here = Path(__file__).resolve().parent
    cfg_path = Path(args.config) if Path(args.config).is_absolute() else here / args.config
    if not cfg_path.exists():
        sys.exit(f"Config not found: {cfg_path}")
    sys.path.insert(0, str(here))
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    after = None
    if args.file and not args.dry_run:
        after = lambda day: file_day(day, here, cfg_path, args.sample)   # file each day before the next
    summary = run(cfg, dry_run=args.dry_run, after_day=after)
    if args.file and not args.dry_run:
        file_new_days(summary, here, cfg_path, args.sample)
    if not args.dry_run and summary["status"] not in ("already running",):
        jobs_root = Path(os.path.expandvars(os.path.expanduser(cfg.get("jobs_root", "~/mytutor/jobs"))))
        path = jobs_root / "run_log.csv"
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=RUN_FIELDS)
            if new:
                w.writeheader()
            w.writerow({**{k: summary.get(k, "") for k in RUN_FIELDS},
                        "finished": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                        "detail": "; ".join(d["folder"] for d in summary["days"])})
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False))
    return 1 if summary["status"] in ("some failed", "no api key", "api key rejected") else 0


if __name__ == "__main__":
    sys.exit(main())
