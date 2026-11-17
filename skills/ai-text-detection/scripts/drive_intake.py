"""Bring a Google Drive document into the analysis.

The user often shares a Drive link. Three helpers, used together with the Google Drive /
Google Docs connectors (see SKILL.md, Intake):

    id <url>                  print the file ID from any Drive or Docs link
    local <file name>         find the file in the locally mounted Google Drive
                              (~/Library/CloudStorage/GoogleDrive-*). A PDF or DOCX found
                              here is analysed from disk at full fidelity, hidden text included.
                              Google-native Docs appear only as .gdoc stubs: use the connector.
    revisions <file.json>     summarise a Google Doc's revision history, written by Claude
                              from the connector as JSON: [{"time": ISO, "author": "...",
                              "words": int or null}, ...] in time order. Writes
                              <work>/revisions.json: how the text grew, and whether most of it
                              arrived in one edit (pasted in).

A text pasted in one block proves only that it was written elsewhere, which is also how
people move their own drafts. It is reported as weak context, never on its own.

Usage:
    python drive_intake.py id "https://docs.google.com/document/d/1AbC.../edit"
    python drive_intake.py local "Grant draft v3.pdf"
    python drive_intake.py revisions /tmp/ai_text_detection/revlist.json
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from lib.common import WORK_DIR, die, read_json, write_json

ID_PATTERNS = [
    r"/d/([A-Za-z0-9_-]{20,})",
    r"[?&]id=([A-Za-z0-9_-]{20,})",
    r"/folders/([A-Za-z0-9_-]{20,})",
]
MOUNTS = Path.home() / "Library" / "CloudStorage"


def file_id(url: str) -> str | None:
    """The Drive file ID in a link (or the string itself if it already is one)."""
    for p in ID_PATTERNS:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return url if re.fullmatch(r"[A-Za-z0-9_-]{20,}", url) else None


def find_local(name: str) -> list[Path]:
    """Paths of files with this exact name in the mounted Google Drives.

    Uses the Spotlight index (instant); walking the mount instead can take many minutes,
    because Drive for desktop streams folders on demand. Falls back to a shallow walk
    when Spotlight finds nothing.
    """
    hits: list[Path] = []
    if not MOUNTS.exists():
        return hits
    try:
        out = subprocess.run(
            ["mdfind", "-onlyin", str(MOUNTS), "-name", name],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
        hits = [
            Path(x)
            for x in out.splitlines()
            if Path(x).name == name and Path(x).is_file()
        ]
    except (OSError, subprocess.TimeoutExpired):
        hits = []
    if hits:
        return hits
    for mount in MOUNTS.glob("GoogleDrive-*"):
        if "(" in mount.name:  # stale duplicate mounts
            continue
        for base in (mount / "My Drive", *(mount / "Shared drives").glob("*")):
            try:
                hits += [p for p in base.glob(f"*/{name}") if p.is_file()] + [
                    p for p in base.glob(name) if p.is_file()
                ]
            except OSError:
                continue
    return hits


def summarise_revisions(revs: list[dict]) -> dict:
    """How the document grew across its revisions."""
    out = {
        "n_revisions": len(revs),
        "authors": sorted({r.get("author") or "?" for r in revs}),
    }
    if revs:
        out["first"] = revs[0].get("time")
        out["last"] = revs[-1].get("time")
    sized = [r for r in revs if isinstance(r.get("words"), int)]
    if len(sized) >= 1:
        final = sized[-1]["words"] or 0
        prev, jumps = 0, []
        for r in sized:
            jumps.append(
                {
                    "time": r.get("time"),
                    "author": r.get("author"),
                    "added": r["words"] - prev,
                }
            )
            prev = r["words"]
        big = max(jumps, key=lambda j: j["added"])
        out.update(
            {
                "final_words": final,
                "largest_addition": big,
                "largest_share": round(big["added"] / final, 2) if final else None,
                "pasted_in_one_block": bool(
                    final >= 500 and big["added"] >= 0.7 * final
                ),
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    """Dispatch."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("id")
    a.add_argument("url")
    b = sub.add_parser("local")
    b.add_argument("name")
    c = sub.add_parser("revisions")
    c.add_argument("path")
    c.add_argument("--work", default=str(WORK_DIR))
    args = p.parse_args(argv)

    if args.cmd == "id":
        fid = file_id(args.url)
        if not fid:
            die("no Drive file ID in that link")
        print(fid)
    elif args.cmd == "local":
        hits = find_local(args.name)
        if not hits:
            print(
                "not in the mounted Drive (shared files appear only once added to My Drive); use the connector"
            )
            return 1
        for h in hits:
            print(h)
    else:
        revs = read_json(args.path) or die(f"cannot read {args.path}")
        s = summarise_revisions(revs)
        write_json(Path(args.work) / "revisions.json", s)
        print(
            f"revisions: {s['n_revisions']} by {len(s['authors'])} author(s)"
            + (
                f"; largest single addition {s['largest_addition']['added']} of {s['final_words']} words"
                if "final_words" in s
                else ""
            )
            + (
                "; most of the text arrived in one edit"
                if s.get("pasted_in_one_block")
                else ""
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
