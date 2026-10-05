"""Fetch the CLAUDE.md files under review into the work directory. Read-only.

Every file is read from its repository's default branch on GitHub, the org file
included, so a review never sees an out-of-date local checkout. ``--local id=path``
reviews a working copy instead (an edit not yet pushed). Prints whether a review is
due, then one line per file: size, and whether it changed since the last review.

``--mark-reviewed`` (run at the end of a review) records today's date and each file's
hash in ``references/_state.json``, appends to its ``review_log`` and sets the next due
date, so the next run can say what changed.

Usage:
    python fetch_targets.py [--work /tmp/org_context] [--local pkg=<clone>/CLAUDE.md]
    python fetch_targets.py --mark-reviewed [--applied O1,P2] [--prs <url>,<url>]
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import date, timedelta
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


def due_line(state: dict, today: date) -> str:
    """``DUE ...`` or ``OK ...`` for the monthly review."""
    due = state.get("next_review_due")
    if not due:
        return "DUE no review recorded yet"
    due = date.fromisoformat(due)
    last = state.get("last_review")
    if today >= due:
        return f"DUE last review {last}; next was due {due} ({(today - due).days} day(s) ago)"
    return f"OK last review {last}; next due {due} (in {(due - today).days} days)"


def mark_reviewed(work: Path, applied: str, prs: str, today: date) -> int:
    """Record today's review of the fetched files in _state.json."""
    targets = read_json(work / "targets.json")
    if not targets:
        die("nothing fetched in this work directory; run fetch_targets.py first")
    state = read_json(STATE) or {}
    state.setdefault("files", {})
    for t in targets:
        state["files"][t["id"]] = {"sha256": t["sha256"], "reviewed": today.isoformat()}
    interval = state.setdefault("review_interval_days", 30)
    state["last_review"] = today.isoformat()
    state["next_review_due"] = (today + timedelta(days=interval)).isoformat()
    state.setdefault("review_log", []).append(
        {
            "date": today.isoformat(),
            "files": [t["id"] for t in targets],
            "applied": [x for x in applied.split(",") if x],
            "prs": [x for x in prs.split(",") if x],
        }
    )
    write_json(STATE, state)
    print(
        f"recorded review of {len(targets)} file(s) on {today}; "
        f"next due {state['next_review_due']}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Fetch every target and print the due status and a line per file."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--local", action="append", default=[], metavar="ID=PATH")
    p.add_argument("--only", help="comma-separated target ids")
    p.add_argument("--mark-reviewed", action="store_true")
    p.add_argument("--applied", default="")
    p.add_argument("--prs", default="")
    p.add_argument("--today", default=date.today().isoformat())
    args = p.parse_args(argv)
    work, today = Path(args.work), date.fromisoformat(args.today)
    if args.mark_reviewed:
        return mark_reviewed(work, args.applied, args.prs, today)

    overrides = dict(item.split("=", 1) for item in args.local)
    config = read_json(REFS / "targets.json")["targets"]
    if args.only:
        keep = set(args.only.split(","))
        config = [t for t in config if t["id"] in keep]
    state = read_json(STATE) or {}
    seen = state.get("files", {})
    print(due_line(state, today))

    out = []
    for t in config:
        meta = dict(t)
        if t["id"] in overrides:
            path = Path(overrides[t["id"]]).expanduser().resolve()
            text, meta["source"] = path.read_text(encoding="utf-8"), str(path)
        else:
            text, blob = fetch_remote(t["repo"], t["path"])
            meta["source"], meta["blob_sha"] = f"github:{t['repo']}/{t['path']}", blob
            # The org file also lives in this checkout: say if it is behind or ahead.
            local = REPO_ROOT / t["path"] if t.get("local") else None
            if local and local.exists() and local.read_text(encoding="utf-8") != text:
                warn(
                    f"{t['path']} in this checkout differs from the default branch; "
                    "reviewing the default branch (use --local to review the checkout)"
                )
        meta["sha256"] = sha256(text)
        meta["lines"] = len(text.splitlines())
        (work / "files").mkdir(parents=True, exist_ok=True)
        (work / "files" / f"{t['id']}.md").write_text(text, encoding="utf-8")
        out.append(meta)

        prev = seen.get(t["id"])
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
