"""Pre-flight guard against overlapping a GitHub digest already published to the remote repo.

The canonical home for digests is `github.com/ersilia-os/digests` at path
`github/YY-MM-DD-github-digest.md`. Before generating a new digest the skill runs this
script to detect any existing digest dated within the last N days (default 7). If one
exists, the skill **stops**: re-running would clobber recent published work.

The script uses the `gh` CLI to query the GitHub contents API — `gh` must be on PATH
and authenticated (`gh auth status`).

Exit contract (matches `check_recent_digest.py`):
- If a recent remote digest exists: print its full GitHub path to stdout and exit 0.
- If none exists: print nothing and exit 0.
- If the remote `github/` folder does not exist yet (HTTP 404 from gh):
  print nothing and exit 0 — this is the first-ever run for the new category.
- On any other gh / network error: log a WARNING to stderr and exit 1. The skill
  must treat this as a hard failure and refuse to proceed (a run that bypasses the
  remote check could silently overlap published work).

Usage:
    python check_remote_digest.py [--repo ersilia-os/digests] [--path github]
                                  [--days 7] [--ref main]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta

from _common import warn


DIGEST_FILENAME_RE = re.compile(
    r"^(?P<yy>\d{2})-(?P<mm>\d{2})-(?P<dd>\d{2})-github-digest\.md$"
)


def parse_filename_date(filename: str) -> date | None:
    m = DIGEST_FILENAME_RE.match(filename)
    if not m:
        return None
    yy = int(m.group("yy"))
    mm = int(m.group("mm"))
    dd = int(m.group("dd"))
    year = 2000 + yy if yy <= 80 else 1900 + yy
    try:
        return date(year, mm, dd)
    except ValueError:
        return None


def gh_list_directory(repo: str, path: str, ref: str) -> list[dict] | None:
    """Return the JSON-decoded listing for `repo/path?ref=ref`, or None on 404."""
    if not shutil.which("gh"):
        raise RuntimeError("gh CLI is not on PATH; install it and authenticate")
    proc = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github+json",
         f"repos/{repo}/contents/{path}?ref={ref}"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        if "HTTP 404" in (proc.stderr or "") or "Not Found" in (proc.stderr or ""):
            return None
        raise RuntimeError(
            f"gh api failed (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()[:400]}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"gh api returned non-JSON: {e}") from None
    if isinstance(data, dict):
        raise RuntimeError(f"{path!r} is a file, not a directory")
    return data


def find_recent_remote(
    repo: str, path: str, days: int, ref: str, today: date | None = None
) -> tuple[str | None, str | None]:
    """Return (full_path_on_github, html_url) for the most recent in-window digest,
    or (None, None) if nothing in window.
    """
    if today is None:
        today = datetime.utcnow().date()
    cutoff = today - timedelta(days=days)
    entries = gh_list_directory(repo, path, ref)
    if entries is None:
        return None, None  # directory doesn't exist yet — clear to proceed
    candidates: list[tuple[date, dict]] = []
    for entry in entries:
        if entry.get("type") != "file":
            continue
        d = parse_filename_date(entry.get("name") or "")
        if d is None:
            continue
        if d >= cutoff:
            candidates.append((d, entry))
    if not candidates:
        return None, None
    candidates.sort(reverse=True)
    entry = candidates[0][1]
    return entry.get("path"), entry.get("html_url")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default="ersilia-os/digests",
                   help="owner/name of the remote digests repo")
    p.add_argument("--path", default="github",
                   help="subdirectory inside the repo")
    p.add_argument("--days", type=int, default=7,
                   help="A digest dated within this many days of today blocks a new run")
    p.add_argument("--ref", default="main",
                   help="branch or tag to query (default: main)")
    args = p.parse_args(argv)

    try:
        full_path, html_url = find_recent_remote(args.repo, args.path, args.days, args.ref)
    except RuntimeError as e:
        warn(f"remote check failed: {e}")
        return 1
    if full_path is not None:
        print(f"{args.repo}/{full_path}")
        if html_url:
            print(html_url, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
