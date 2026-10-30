"""Turn Google Drive folder listings into dated event candidates for the Events check.

Talks and visits leave a dated folder behind: the Presentations shared drive has one
per event inside its year folders (``YYMMDD_Name``), and the Photos folder of the
Communication drive has one per trip (``YYMM_Name``). The Drive connector
(`search_files`) returns ``{"files": [...]}``; the harness may save a large response to
a file, sometimes wrapped as ``[{"type": "text", "text": "<json>"}]``. This script takes
any number of such dumps, keeps the folders whose title starts with a date, and writes

    [{"key": "event:<title>", "title", "name", "date": "YYYY-MM-DD",
      "precision": "day"|"month", "source", "folder_id"}, ...]

``name`` is the title without its date prefix, with underscores and CamelCase split
into words. Folders with no date prefix, or an impossible date, are ignored.

Usage:
    python collect_event_folders.py --source presentations --in dump1.json [dump2.json] \
        [--source photos --in photos.json] [--out /tmp/airtable_sync/event_folders.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from _common import WORK_DIR, die, write_json

FOLDER_MIME = "application/vnd.google-apps.folder"
DATED = re.compile(r"^(\d{6}|\d{4})_(.+)$")


def _load(path: str) -> list[dict]:
    """Return the ``files`` list from one connector dump, unwrapping text blocks."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and "text" in data[0]
    ):
        data = json.loads("".join(block.get("text", "") for block in data))
    if isinstance(data, dict) and "files" in data:
        return data["files"]
    if isinstance(data, list):
        return data
    die(f"{path}: no 'files' list found")
    return []


def split_words(text: str) -> str:
    """'TechSpirit_Debate' -> 'Tech Spirit Debate'; 'ERCStarting' -> 'ERC Starting'."""
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    return re.sub(r"[_\-]+", " ", text).strip()


def parse_folder(title: str) -> tuple[str, str, str] | None:
    """Return (iso date, precision, name) for a dated folder title, else None."""
    m = DATED.match(title.strip())
    if not m:
        return None
    digits, rest = m.groups()
    year, month = 2000 + int(digits[:2]), int(digits[2:4])
    day = int(digits[4:6]) if len(digits) == 6 else 1
    try:
        when = date(year, month, day)
    except ValueError:
        return None
    precision = "day" if len(digits) == 6 else "month"
    return when.isoformat(), precision, split_words(rest)


def collect(files: list[dict], source: str) -> list[dict]:
    """Dated folders from one source, as event candidates."""
    out = []
    for f in files:
        if f.get("mimeType") != FOLDER_MIME:
            continue
        parsed = parse_folder(f.get("title") or "")
        if parsed is None:
            continue
        when, precision, name = parsed
        out.append(
            {
                "key": f"event:{f['title'].strip()}",
                "title": f["title"].strip(),
                "name": name,
                "date": when,
                "precision": precision,
                "source": source,
                "folder_id": f.get("id"),
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    """Collect dated folders from every --source/--in group."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--source", action="append", required=True)
    p.add_argument("--in", dest="inputs", action="append", nargs="+", required=True)
    p.add_argument("--out", default=f"{WORK_DIR}/event_folders.json")
    args = p.parse_args(argv)
    if len(args.source) != len(args.inputs):
        die("pass one --in group after each --source")

    rows: dict[str, dict] = {}
    for source, paths in zip(args.source, args.inputs):
        for path in paths:
            for row in collect(_load(path), source):
                rows.setdefault(row["key"], row)
    out = sorted(rows.values(), key=lambda r: r["date"])
    write_json(args.out, out)
    by = {}
    for r in out:
        by[r["source"]] = by.get(r["source"], 0) + 1
    print(
        f"event folders: {len(out)} -> {args.out} ("
        + ", ".join(f"{k} {v}" for k, v in by.items())
        + ")"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
