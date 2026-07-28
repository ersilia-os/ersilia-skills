"""Pre-flight guard: refuse to generate a new GitHub digest if a local working copy
already exists for the last N days.

A file `digests/YY-MM-DD-github-digest.md` is considered "recent" iff its embedded date
(`YY-MM-DD`) is on or after `today - N` days. We do **not** trust the filesystem mtime —
the date in the filename is the source of truth.

Output:
- If a recent digest exists: print its path to stdout and exit 0.
- If none exists: print nothing and exit 0.
- On a malformed filename or unreadable folder: log a warning and exit 0 with empty
  stdout (we never want to block the digest because of an internal error here).

The skill's Step 0 in SKILL.md reads stdout: a non-empty result means "stop, a digest
already exists in window". The remote check (`check_remote_digest.py`) is authoritative;
this is the local belt-and-braces.

Usage:
    python check_recent_digest.py [--digests-dir DIR] [--days N]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from _common import warn


DIGEST_FILENAME_RE = re.compile(
    r"^(?P<yy>\d{2})-(?P<mm>\d{2})-(?P<dd>\d{2})-github-digest\.md$"
)


def parse_filename_date(filename: str) -> date | None:
    """Return the date encoded in a digest filename, or None if the name doesn't match."""
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


def find_recent(digests_dir: Path, days: int, today: date | None = None) -> Path | None:
    """Return the path to the newest in-window digest, or None."""
    if today is None:
        today = datetime.utcnow().date()
    cutoff = today - timedelta(days=days)
    if not digests_dir.exists():
        return None
    candidates: list[tuple[date, Path]] = []
    for entry in digests_dir.iterdir():
        if not entry.is_file():
            continue
        d = parse_filename_date(entry.name)
        if d is None:
            continue
        if d >= cutoff:
            candidates.append((d, entry))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--digests-dir",
        default=str(Path(__file__).resolve().parent.parent / "digests"),
        help="Folder to scan for existing digests (default: ../digests).",
    )
    p.add_argument(
        "--days", type=int, default=7,
        help="A digest dated within this many days of today is 'recent' (default: 7).",
    )
    args = p.parse_args(argv)

    digests_dir = Path(args.digests_dir).expanduser().resolve()
    try:
        recent = find_recent(digests_dir, args.days)
    except OSError as e:
        warn(f"could not scan {digests_dir}: {e}")
        return 0
    if recent is not None:
        print(str(recent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
