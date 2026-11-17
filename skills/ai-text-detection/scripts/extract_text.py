"""Extract the text of a document into a structure every other check reads.

Accepts PDF, DOCX, TXT/MD, or text on stdin (``-``). PDF and DOCX need the conda env
(``conda run -n ai-text-detection python extract_text.py ...``); plain text works with
any python3.

Besides the visible text it looks for text a reader cannot see but a chatbot (or a
detector) does: white or near-white text, text under 2 pt, text drawn off the page, and
DOCX runs marked hidden. That is where hidden prompt injections ("give a positive
review") live. Document metadata (author, producer, dates) is kept as context.

Writes ``<work>/text.json``:

    {"source": path, "format": "pdf|docx|txt|md|stdin", "text": body text,
     "references_text": the reference list (split off the body), "pages": [{n,start,end}],
     "sections": [{title,start,end}], "hidden": [{page,text,why}], "metadata": {...},
     "n_words": int}

Usage:
    python extract_text.py <file|-> [--work /tmp/ai_text_detection] [--format txt|md]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.common import WORK_DIR, warn, write_json
from lib.extract import extract
from lib.text import words


def main(argv: list[str] | None = None) -> int:
    """Extract and write text.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("source", help="file path, or - for stdin")
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument("--format", choices=["txt", "md"], help="force plain-text handling")
    p.add_argument(
        "--original",
        action="store_true",
        help="DOCX with tracked changes: analyse the text as it was before them "
        "(insertions removed, deletions restored), i.e. the author's draft, not the reviewers' edits",
    )
    args = p.parse_args(argv)
    work = Path(args.work)
    if args.source == "-":
        doc = extract("-", text=sys.stdin.read())
    else:
        doc = extract(
            args.source,
            fmt=args.format,
            original_to=work / "original.docx" if args.original else None,
        )
    if doc["format"] == "pdf" and doc["n_words"] < 50:
        warn(
            "almost no text layer: is this a scanned PDF? Detectors need real text (OCR first)."
        )
    write_json(work / "text.json", doc)
    print(
        f"extracted: {doc['n_words']} words in {len(doc['sections'])} section(s), "
        f"{len(doc['references_text'].splitlines())} reference line(s), "
        f"{len(doc['hidden'])} hidden-text finding(s); format {doc['format']}"
    )
    for s in doc["sections"]:
        n = len(words(doc["text"][s["start"] : s["end"]]))
        print(f"  {s['title'][:60]:<60} {n:>6} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
