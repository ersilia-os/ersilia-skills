"""Fetch the CLAUDE.md files under review into the work directory. Read-only.

The org file is read from this ersilia-skills checkout; template files are read from
GitHub's default branch with ``gh api`` unless ``--local id=path`` points at a clone.
Prints one line per file: size, and whether it changed since the last review recorded
in ``references/_state.json``.

``--mark-reviewed`` (run at the end of a review) records today's date and each file's
hash in ``_state.json``, so the next run can say what changed.

Usage:
    python fetch_targets.py [--work /tmp/org_context] [--local pkg=../eos-python-package/CLAUDE.md]
    python fetch_targets.py --mark-reviewed
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from _common import (
    REFS,
    REPO_ROOT,
    WORK_DIR,
    die,
    read_json,
    run_gh,
    sha256,
    warn,
    write_json,
)

STATE = REFS / "_state.json"


def fetch_remote(repo: str, path: str) -> tuple[str, str]:
    """Return (text, blob sha) of ``path`` on the default branch of ``repo``."""
    out, err = run_gh(["api", f"repos/{repo}/contents/{path}"])
    if out is None:
        die(f"could not read {repo}/{path}: {err}")
    data = json.loads(out)
    return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]


def local_dirty(path: Path) -> bool:
    """True if ``path`` has uncommitted changes in the ersilia-skills checkout."""
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--", str(path)],
        capture_output=True,
        text=True,
    )
    return bool(proc.stdout.strip())


def mark_reviewed(work: Path) -> int:
    """Record today's review of the fetched files in _state.json."""
    targets = read_json(work / "targets.json")
    if not targets:
        die("nothing fetched in this work directory; run fetch_targets.py first")
    state = read_json(STATE) or {"files": {}}
    today = date.today().isoformat()
    for t in targets:
        state["files"][t["id"]] = {"sha256": t["sha256"], "reviewed": today}
    state["last_review"] = today
    write_json(STATE, state)
    print(f"recorded review of {len(targets)} file(s) on {today}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Fetch every target and print a one-line status per file."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--local", action="append", default=[], metavar="ID=PATH")
    p.add_argument("--only", help="comma-separated target ids")
    p.add_argument("--mark-reviewed", action="store_true")
    args = p.parse_args(argv)
    work = Path(args.work)
    if args.mark_reviewed:
        return mark_reviewed(work)

    overrides = dict(item.split("=", 1) for item in args.local)
    config = read_json(REFS / "targets.json")["targets"]
    if args.only:
        keep = set(args.only.split(","))
        config = [t for t in config if t["id"] in keep]
    state = (read_json(STATE) or {}).get("files", {})

    out = []
    for t in config:
        meta = dict(t)
        if t["id"] in overrides:
            path = Path(overrides[t["id"]]).expanduser().resolve()
            text, meta["source"] = path.read_text(encoding="utf-8"), str(path)
        elif t.get("local"):
            path = REPO_ROOT / t["path"]
            text, meta["source"] = path.read_text(encoding="utf-8"), str(path)
            if local_dirty(path):
                warn(f"{t['path']} has uncommitted changes; reviewing the working copy")
        else:
            text, blob = fetch_remote(t["repo"], t["path"])
            meta["source"], meta["blob_sha"] = f"github:{t['repo']}/{t['path']}", blob
        meta["sha256"] = sha256(text)
        meta["lines"] = len(text.splitlines())
        (work / "files").mkdir(parents=True, exist_ok=True)
        (work / "files" / f"{t['id']}.md").write_text(text, encoding="utf-8")
        out.append(meta)

        prev = state.get(t["id"])
        if not prev:
            status = "first review"
        elif prev["sha256"] == meta["sha256"]:
            status = f"unchanged since review on {prev['reviewed']}"
        else:
            status = f"changed since review on {prev['reviewed']}"
        meta["status"] = status
        print(f"{t['id']:4} {t['repo']}/{t['path']}: {meta['lines']} lines, {status}")

    write_json(work / "targets.json", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
