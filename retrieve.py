"""myTutor stage 1: retrieve a course folder from OneDrive into a local job folder.

Usage
    python retrieve.py --config config.json --folder "Day 1"
    python retrieve.py --config config.json --folder "Day 1" --dry-run
    python retrieve.py --config config.json --folder "Day 1" --force

Two modes, set by "mode" in config.json:
    synced  copy from the OneDrive folder the OneDrive app keeps on this PC (no sign-in needed here)
    graph   download straight from OneDrive through Microsoft Graph (needs an app registration)

Each run creates  <jobs_root>/<timestamp>_<folder-slug>/
    source/          the retrieved files, keeping their sub-folders
    manifest.json    one entry per file: path, size, sha256, link to the original, status
and updates
    <jobs_root>/index.json   every file already retrieved, so re-runs skip duplicates
    <jobs_root>/runs.csv     one row per run (timing and counts, for the KPI log)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import quote

DEFAULT_EXTENSIONS = [".pdf", ".pptx", ".docx", ".txt", ".md"]
IGNORED_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
IGNORED_PREFIXES = ("~$", ".~", "._")
CHUNK = 1024 * 1024

RUN_LOG_FIELDS = [
    "run_id", "mode", "folder", "started", "finished", "seconds",
    "found", "retrieved", "skipped_duplicate", "skipped_type",
    "skipped_size", "failed", "bytes",
]


# ---------------------------------------------------------------- data types

@dataclass
class SourceFile:
    """A file found at the source, before it is copied."""
    rel_path: str               # path inside the requested folder, with forward slashes
    size: int
    modified: str               # ISO 8601
    origin: str                 # local path (synced) or web link (graph)
    remote_id: str = ""         # graph item id
    remote_tag: str = ""        # graph cTag, changes when the content changes
    download_url: str = ""      # graph only


@dataclass
class ManifestEntry:
    rel_path: str
    status: str                 # retrieved | skipped_duplicate | skipped_type | skipped_size | failed
    size: int = 0
    sha256: str = ""
    modified: str = ""
    origin: str = ""
    note: str = ""


@dataclass
class RunResult:
    run_id: str
    job_dir: Optional[Path]
    entries: list = field(default_factory=list)
    seconds: float = 0.0

    def count(self, status: str) -> int:
        return sum(1 for e in self.entries if e.status == status)


# ---------------------------------------------------------------- helpers

def slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return slug or "folder"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def is_ignored(name: str) -> bool:
    lower = name.lower()
    return lower in IGNORED_NAMES or name.startswith(IGNORED_PREFIXES)


def safe_rel_path(rel: str) -> Path:
    """Reject paths that would escape the job folder."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError(f"unsafe path: {rel}")
    return Path(*parts)


def load_json(path: Path, default):
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def write_stream(chunks, dest: Path) -> tuple[int, str]:
    """Write chunks to dest through a temp file; return (bytes, sha256)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total = 0
    fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=".part-")
    try:
        with os.fdopen(fd, "wb") as out:
            for chunk in chunks:
                if not chunk:
                    continue
                out.write(chunk)
                digest.update(chunk)
                total += len(chunk)
        os.replace(tmp_name, dest)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
    return total, digest.hexdigest()


# ---------------------------------------------------------------- sources

class SyncedSource:
    """Reads from the OneDrive folder the OneDrive app syncs to this PC."""

    mode = "synced"

    def __init__(self, inbox_root: Path, settle_seconds: float = 1.0):
        self.inbox_root = inbox_root
        self.settle_seconds = settle_seconds

    def list_files(self, folder: str) -> Iterator[SourceFile]:
        base = self.inbox_root / safe_rel_path(folder)
        if not base.is_dir():
            raise FileNotFoundError(
                f"Folder not found: {base}\n"
                "Check that OneDrive has finished syncing, that synced_inbox in config.json "
                "is right, and that --folder matches the folder names exactly."
            )
        for path in sorted(base.rglob("*")):
            if not path.is_file() or is_ignored(path.name):
                continue
            if any(is_ignored(p) for p in path.relative_to(base).parts[:-1]):
                continue
            stat = path.stat()
            yield SourceFile(
                rel_path=path.relative_to(base).as_posix(),
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                origin=str(path),
            )

    def fetch(self, item: SourceFile, dest: Path) -> tuple[int, str]:
        path = Path(item.origin)
        # A file still being synced changes size; wait until it settles.
        # Only recently changed files need the check, so settled folders copy at full speed.
        recent = time.time() - path.stat().st_mtime < 120
        if self.settle_seconds > 0 and recent:
            before = path.stat().st_size
            time.sleep(self.settle_seconds)
            if path.stat().st_size != before:
                raise IOError("file is still syncing; run again in a minute")

        def chunks():
            # Reading a cloud-only file makes Windows download it first.
            with path.open("rb") as f:
                while True:
                    block = f.read(CHUNK)
                    if not block:
                        break
                    yield block

        size, sha = write_stream(chunks(), dest)
        shutil.copystat(path, dest)
        return size, sha


class GraphSource:
    """Downloads from OneDrive through Microsoft Graph."""

    mode = "graph"
    API = "https://graph.microsoft.com/v1.0"

    def __init__(self, inbox_path: str, token: str, session=None, max_retries: int = 4):
        if session is None:
            import requests  # only needed in graph mode
            session = requests.Session()
        self.inbox_path = inbox_path.strip("/")
        self.session = session
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.max_retries = max_retries

    def _get(self, url: str, stream: bool = False, auth: bool = True):
        # Pre-signed download links reject an extra Authorization header, so drop it there.
        headers = None if auth else {"Authorization": None}
        for attempt in range(self.max_retries + 1):
            resp = self.session.get(url, stream=stream, timeout=60, headers=headers)
            if resp.status_code in (429, 503) and attempt < self.max_retries:
                wait = int(resp.headers.get("Retry-After", 2 ** attempt))
                time.sleep(min(wait, 60))
                continue
            if resp.status_code == 404:
                raise FileNotFoundError(f"Not found in OneDrive: {url}")
            resp.raise_for_status()
            return resp
        raise IOError("Microsoft Graph kept throttling the request")

    def _children(self, drive_path: str) -> Iterator[dict]:
        url = f"{self.API}/me/drive/root:/{quote(drive_path)}:/children"
        while url:
            data = self._get(url).json()
            yield from data.get("value", [])
            url = data.get("@odata.nextLink")

    def list_files(self, folder: str) -> Iterator[SourceFile]:
        start = "/".join(p for p in (self.inbox_path, folder.strip("/")) if p)
        yield from self._walk(start, "")

    def _walk(self, drive_path: str, rel_prefix: str) -> Iterator[SourceFile]:
        for item in self._children(drive_path):
            name = item["name"]
            if is_ignored(name):
                continue
            rel = f"{rel_prefix}{name}"
            if "folder" in item:
                yield from self._walk(f"{drive_path}/{name}", f"{rel}/")
            elif "file" in item:
                yield SourceFile(
                    rel_path=rel,
                    size=item.get("size", 0),
                    modified=item.get("lastModifiedDateTime", ""),
                    origin=item.get("webUrl", ""),
                    remote_id=item.get("id", ""),
                    remote_tag=item.get("cTag", ""),
                    download_url=item.get("@microsoft.graph.downloadUrl", ""),
                )

    def fetch(self, item: SourceFile, dest: Path) -> tuple[int, str]:
        if item.download_url:
            resp = self._get(item.download_url, stream=True, auth=False)
        else:
            resp = self._get(f"{self.API}/me/drive/items/{item.remote_id}/content", stream=True)
        return write_stream(resp.iter_content(CHUNK), dest)


def graph_token(client_id: str, tenant: str, cache_path: Path) -> str:
    """Sign in with a device code once; later runs reuse the cached token."""
    try:
        import msal
    except ImportError:
        sys.exit("Graph mode needs msal: pip install -r requirements.txt")
    cache = msal.SerializableTokenCache()
    if cache_path.exists():
        cache.deserialize(cache_path.read_text(encoding="utf-8"))
    app = msal.PublicClientApplication(
        client_id, authority=f"https://login.microsoftonline.com/{tenant}", token_cache=cache
    )
    scopes = ["Files.Read"]
    result = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(scopes, account=accounts[0])
    if not result:
        flow = app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            sys.exit(f"Could not start sign-in: {flow.get('error_description', flow)}")
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        sys.exit(f"Sign-in failed: {result.get('error_description', result)}")
    if cache.has_state_changed:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(cache.serialize(), encoding="utf-8")
    return result["access_token"]


# ---------------------------------------------------------------- the run

def retrieve(source, folder: str, jobs_root: Path, extensions=None, max_file_mb: float = 100,
             force: bool = False, dry_run: bool = False, run_id: Optional[str] = None) -> RunResult:
    extensions = {e.lower() for e in (extensions or DEFAULT_EXTENSIONS)}
    started_at = now_iso()
    t0 = time.perf_counter()
    run_id = _unique_run_id(jobs_root, run_id or f"{datetime.now():%Y-%m-%d_%H%M%S}_{slugify(folder)}")
    job_dir = None if dry_run else jobs_root / run_id
    index_path = jobs_root / "index.json"
    index = load_json(index_path, {"sha256": {}, "remote": {}})
    result = RunResult(run_id=run_id, job_dir=job_dir)

    for item in source.list_files(folder):
        entry = ManifestEntry(rel_path=item.rel_path, status="", size=item.size,
                              modified=item.modified, origin=item.origin)
        ext = Path(item.rel_path).suffix.lower()
        if ext not in extensions:
            entry.status, entry.note = "skipped_type", f"{ext or 'no extension'} is not in the extension list"
        elif item.size > max_file_mb * 1024 * 1024:
            entry.status, entry.note = "skipped_size", f"larger than {max_file_mb} MB"
        elif not force and item.remote_id and index["remote"].get(item.remote_id) == item.remote_tag:
            entry.status, entry.note = "skipped_duplicate", "unchanged since an earlier run"
        elif dry_run:
            entry.status, entry.note = "retrieved", "dry run: not copied"
        else:
            dest = job_dir / "source" / safe_rel_path(item.rel_path)
            try:
                entry.size, entry.sha256 = source.fetch(item, dest)
            except Exception as exc:  # keep going; the manifest records the failure
                entry.status, entry.note = "failed", str(exc)
            else:
                earlier = index["sha256"].get(entry.sha256)
                if earlier and not force:
                    dest.unlink()
                    entry.status = "skipped_duplicate"
                    entry.note = f"same content as {earlier['rel_path']} in {earlier['job']}"
                else:
                    entry.status = "retrieved"
                    index["sha256"][entry.sha256] = {
                        "job": run_id, "rel_path": item.rel_path, "retrieved_at": now_iso(),
                    }
                if item.remote_id:
                    index["remote"][item.remote_id] = item.remote_tag
        result.entries.append(entry)

    result.seconds = round(time.perf_counter() - t0, 2)

    if not dry_run:
        _prune_empty_dirs(job_dir / "source")
        write_json(job_dir / "manifest.json", {
            "run_id": run_id,
            "mode": source.mode,
            "folder": folder,
            "started": started_at,
            "finished": now_iso(),
            "seconds": result.seconds,
            "files": [asdict(e) for e in result.entries],
        })
        write_json(index_path, index)
        _append_run_log(jobs_root / "runs.csv", {
            "run_id": run_id, "mode": source.mode, "folder": folder,
            "started": started_at, "finished": now_iso(), "seconds": result.seconds,
            "found": len(result.entries),
            "retrieved": result.count("retrieved"),
            "skipped_duplicate": result.count("skipped_duplicate"),
            "skipped_type": result.count("skipped_type"),
            "skipped_size": result.count("skipped_size"),
            "failed": result.count("failed"),
            "bytes": sum(e.size for e in result.entries if e.status == "retrieved"),
        })
    return result


def _unique_run_id(jobs_root: Path, base: str) -> str:
    """Never reuse a job folder: two runs in the same second get -2, -3 ..."""
    run_id, n = base, 2
    while (jobs_root / run_id).exists():
        run_id, n = f"{base}-{n}", n + 1
    return run_id


def _prune_empty_dirs(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    if not any(root.iterdir()):
        root.rmdir()


def _append_run_log(path: Path, row: dict) -> None:
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_LOG_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------- command line

def build_source(cfg: dict, jobs_root: Path):
    mode = cfg.get("mode", "synced")
    if mode == "synced":
        inbox = cfg.get("synced_inbox")
        if not inbox:
            sys.exit('config.json needs "synced_inbox" for synced mode')
        return SyncedSource(Path(os.path.expandvars(os.path.expanduser(inbox))),
                            settle_seconds=float(cfg.get("settle_seconds", 1.0)))
    if mode == "graph":
        g = cfg.get("graph", {})
        if not g.get("client_id"):
            sys.exit('config.json needs graph.client_id for graph mode (see README)')
        token = graph_token(g["client_id"], g.get("tenant", "organizations"),
                            jobs_root / ".token_cache.json")
        return GraphSource(g.get("inbox_path", "myTutor/Inbox"), token)
    sys.exit(f'Unknown mode "{mode}": use "synced" or "graph"')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Retrieve a OneDrive folder into a local myTutor job.")
    parser.add_argument("--config", default="config.json", help="path to config.json")
    parser.add_argument("--folder", required=True, help='folder inside the Inbox, e.g. "Day 1"')
    parser.add_argument("--dry-run", action="store_true", help="list what would be retrieved, copy nothing")
    parser.add_argument("--force", action="store_true", help="retrieve again even if already retrieved")
    args = parser.parse_args(argv)

    cfg = load_json(Path(args.config), None)
    if cfg is None:
        sys.exit(f"Config not found: {args.config} (copy config.example.json to config.json)")
    jobs_root = Path(os.path.expandvars(os.path.expanduser(cfg.get("jobs_root", "~/mytutor/jobs"))))
    source = build_source(cfg, jobs_root)

    try:
        result = retrieve(source, args.folder, jobs_root,
                          extensions=cfg.get("extensions"),
                          max_file_mb=float(cfg.get("max_file_mb", 100)),
                          force=args.force, dry_run=args.dry_run)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2

    for e in result.entries:
        note = f"  ({e.note})" if e.note else ""
        print(f"{e.status:<18} {e.rel_path}{note}")
    print(
        f"\n{result.count('retrieved')} retrieved, {result.count('skipped_duplicate')} duplicate, "
        f"{result.count('skipped_type') + result.count('skipped_size')} skipped, "
        f"{result.count('failed')} failed in {result.seconds}s"
    )
    if result.job_dir:
        print(f"Job folder: {result.job_dir}")
    return 1 if result.count("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
