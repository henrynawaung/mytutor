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


def run(cfg: dict, client=None, dry_run: bool = False, log=print) -> dict:
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
        todo = []
        for label, path in day_folders(inbox):
            status, new = folder_status(path, extensions, known, float(cfg.get("settle_minutes", 3)))
            summary["days_found"] += 1
            if status == "new":
                todo.append(label)
                log(f"new        {label}: {new} new file(s)")
            elif status == "syncing":
                log(f"waiting    {label}: files changed in the last few minutes, next run will take it")
        if not todo:
            log("No new files.")
        if dry_run or not todo:
            summary["seconds"] = round(time.perf_counter() - t0, 1)
            return summary

        if client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                summary["status"] = "no api key"
                log("ANTHROPIC_API_KEY is not set for this process.")
                return summary
            import anthropic
            client = anthropic.Anthropic(max_retries=3)

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
                done = [r for r in rep["sources"].values() if r.get("status") == "done"]
                bad = [r for r in rep["sources"].values() if r.get("status") == "failed"]
                day.update(job=res.job_dir.name, sources=len(done), failed=len(bad),
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
    if summary["failed"]:
        summary["status"] = "some failed"
    return summary


def file_new_days(summary: dict, here: Path, cfg_path: Path, sample: int) -> None:
    """Run file.py for every day processed in this run (notes into the vault, spot-check sample picked)."""
    import subprocess
    filed = 0
    for day in summary["days"]:
        if not day.get("job") or not day.get("sources"):
            continue
        cmd = [sys.executable, str(here / "file.py"), "--config", str(cfg_path), "--job", day["job"],
               "--sample", str(sample)]
        res = subprocess.run(cmd, cwd=str(here), capture_output=True, text=True)
        print(res.stdout.rstrip())
        if res.returncode == 0:
            day["filed"] = True
            filed += 1
        else:
            day["filed"] = False
            day["file_error"] = (res.stderr.strip().splitlines() or ["file.py failed"])[-1]
            summary["failed"] += 1
            summary["status"] = "some failed"
            print(f"FAILED     filing {day['folder']}: {day['file_error']}")
    summary["days_filed"] = filed


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
    summary = run(cfg, dry_run=args.dry_run)
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
    return 1 if summary["status"] in ("some failed", "no api key") else 0


if __name__ == "__main__":
    sys.exit(main())
