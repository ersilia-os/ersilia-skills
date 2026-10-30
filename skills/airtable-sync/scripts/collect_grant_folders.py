"""Turn the Grants shared drive's folder listings into grant candidates.

The Grants drive has one folder per year (``2020`` ... ``2026``) and, inside each, one
folder per application, named after the funder or the call (``CZI_EOSS``,
``BMGF_GrandChallenges_Boyom``). Names carry no date, so the year comes from the parent
folder. Pass every Drive connector dump that covers the drive: the root listing (which
holds the year folders) and the listing of their children; the order does not matter.
Dumps may be wrapped by the harness as ``[{"type": "text", "text": "<json>"}]``.

Output:

    [{"key": "grant:<year>/<title>", "title", "name", "year": 2023, "folder_id"}, ...]

``name`` is the title with underscores and CamelCase split into words.

Usage:
    python collect_grant_folders.py --in root.json children.json \
        [--out /tmp/airtable_sync/grant_folders.json]
"""

from __future__ import annotations

import argparse
import re
import sys

from _common import WORK_DIR, write_json
from collect_event_folders import FOLDER_MIME, _load, split_words

YEAR = re.compile(r"^(19|20)\d{2}$")


def collect(files: list[dict]) -> list[dict]:
    """Folders whose parent is a year folder, tagged with that year."""
    folders = [f for f in files if f.get("mimeType") == FOLDER_MIME]
    years = {
        f["id"]: int(f["title"].strip())
        for f in folders
        if YEAR.match((f.get("title") or "").strip())
    }
    out = {}
    for f in folders:
        year = years.get(f.get("parentId"))
        if year is None or f["id"] in years:
            continue
        title = f["title"].strip()
        key = f"grant:{year}/{title}"
        out.setdefault(
            key,
            {
                "key": key,
                "title": title,
                "name": split_words(title),
                "year": year,
                "folder_id": f["id"],
            },
        )
    return sorted(out.values(), key=lambda r: (r["year"], r["title"].lower()))


def main(argv: list[str] | None = None) -> int:
    """Collect grant folders from every dump passed."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--in", dest="inputs", nargs="+", required=True)
    p.add_argument("--out", default=f"{WORK_DIR}/grant_folders.json")
    args = p.parse_args(argv)

    files: list[dict] = []
    for path in args.inputs:
        files.extend(_load(path))
    rows = collect(files)
    write_json(args.out, rows)
    years = sorted({r["year"] for r in rows})
    span = f"{years[0]}-{years[-1]}" if years else "no year folders found"
    print(f"grant folders: {len(rows)} ({span}) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
