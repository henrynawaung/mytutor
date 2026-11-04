"""Apply a reviewed set of vault changes (jobs/vault_changes.json), with a backup and an undo.

    py apply_vault_changes.py             apply, after backing up every file it touches
    py apply_vault_changes.py --dry-run   show what would change, write nothing
    py apply_vault_changes.py --undo      put the vault back as it was before the last apply

Safety: a note is only changed if it is still exactly as it was when the changes were prepared
(checked with a sha256 fingerprint). Anything you edited since then is skipped and listed.
"""

import argparse
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_cfg(here: Path, name: str):
    cfg = json.loads((here / name).read_text(encoding="utf-8"))
    vault = Path(os.path.expanduser(cfg["vault_path"]))
    jobs = Path(os.path.expandvars(os.path.expanduser(cfg.get("jobs_root", "~/mytutor/jobs"))))
    return vault, jobs


def plan(vault: Path, ch: dict):
    ok, skipped = {"renames": [], "edits": [], "new": []}, []
    renamed_ok = set()
    for r in ch.get("renames", []):
        src, dst = vault / r["from"], vault / r["to"]
        if dst.exists() and not src.exists():
            skipped.append(f"already renamed  {r['to']}")
        elif not src.exists() or sha(src) != r["sha256"] or dst.exists():
            skipped.append(f"changed since    {r['from']}")
        else:
            ok["renames"].append(r)
            renamed_ok.add(r["to"])
    for e in ch.get("edits", []):
        p = vault / e["path"]
        if e["path"] in renamed_ok:
            ok["edits"].append(e)
        elif not p.exists():
            skipped.append(f"missing          {e['path']}")
        elif p.read_text(encoding="utf-8") == e["content"]:
            skipped.append(f"already done     {e['path']}")
        elif e.get("sha256") and sha(p) != e["sha256"]:
            skipped.append(f"changed since    {e['path']}  (your edit kept)")
        else:
            ok["edits"].append(e)
    for n in ch.get("new", []):
        p = vault / n["path"]
        if p.exists():
            same = p.read_text(encoding="utf-8") == n["content"]
            skipped.append(f"{'already done' if same else 'exists, kept'}     {n['path']}")
        else:
            ok["new"].append(n)
    return ok, skipped


def apply(vault: Path, jobs: Path, ch: dict, dry_run: bool = False) -> dict:
    ok, skipped = plan(vault, ch)
    for s in skipped:
        print("skip  " + s)
    for r in ok["renames"]:
        print(f"rename  {r['from']}  ->  {Path(r['to']).name}")
    for e in ok["edits"]:
        print(f"edit    {e['path']}")
    for n in ok["new"]:
        print(f"new     {n['path']}")
    counts = {k: len(v) for k, v in ok.items()} | {"skipped": len(skipped)}
    if dry_run or not any(ok.values()):
        print(f"\n{'Dry run: ' if dry_run else ''}{counts}")
        return counts
    backup = jobs / f"vault_backup_{datetime.now():%Y%m%d_%H%M%S}.zip"
    with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as z:
        for r in ok["renames"]:
            z.write(vault / r["from"], "files/" + r["from"])
        for e in ok["edits"]:
            src = next((r["from"] for r in ok["renames"] if r["to"] == e["path"]), e["path"])
            if src == e["path"]:
                z.write(vault / e["path"], "files/" + e["path"])
        z.writestr("manifest.json", json.dumps({
            "renames": [[r["from"], r["to"]] for r in ok["renames"]],
            "edited": [e["path"] for e in ok["edits"]],
            "new": [n["path"] for n in ok["new"]]}, ensure_ascii=False, indent=1))
    for r in ok["renames"]:
        (vault / r["from"]).rename(vault / r["to"])
    for item in ok["edits"] + ok["new"]:
        p = vault / item["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(item["content"], encoding="utf-8", newline="\n")
    print(f"\nDone: {counts}\nBackup: {backup}\nTo undo: py apply_vault_changes.py --undo")
    return counts


def undo(vault: Path, jobs: Path) -> int:
    backups = sorted(jobs.glob("vault_backup_*.zip"))
    if not backups:
        print("No backup found.")
        return 1
    b = backups[-1]
    with zipfile.ZipFile(b) as z:
        m = json.loads(z.read("manifest.json"))
        for rel in m["new"]:
            (vault / rel).unlink(missing_ok=True)
        for src, dst in m["renames"]:
            if (vault / dst).exists():
                (vault / dst).unlink()
        for name in z.namelist():
            if name.startswith("files/"):
                p = vault / name[len("files/"):]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(z.read(name))
        for rel in m["new"]:                       # tidy folders left empty
            d = (vault / rel).parent
            while d != vault and d.exists() and not any(d.iterdir()):
                d.rmdir()
                d = d.parent
    b.rename(b.with_suffix(".undone.zip"))
    print(f"Restored the vault from {b.name}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--changes", default=None, help="default: <jobs_root>/vault_changes.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--undo", action="store_true")
    a = ap.parse_args(argv)
    here = Path(__file__).resolve().parent
    vault, jobs = load_cfg(here, a.config)
    if a.undo:
        return undo(vault, jobs)
    path = Path(a.changes) if a.changes else jobs / "vault_changes.json"
    ch = json.loads(path.read_text(encoding="utf-8"))
    apply(vault, jobs, ch, a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
