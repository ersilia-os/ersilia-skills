#!/usr/bin/env python3
"""check_pdf.py — is this file really the model's paper?

    python check_pdf.py paper.pdf --model-id eos88ir
    python check_pdf.py paper.pdf --title "Chemical Dice ..." --doi 10.1038/...

Checks, in order:

1. the file starts with ``%PDF-``, which rules out the HTML error pages and paywall stubs
   that publishers serve with a ``.pdf`` name (the 425-byte files in an earlier
   assessment's pdfs/ folder were exactly that);
2. it is at least ``--min-kb`` (default 30) KB, since a real article is not smaller;
3. ``pdfinfo`` can read a page count, so the file is not truncated;
4. the text of the first two pages (``pdftotext``) contains the DOI, or most of the
   Title's distinctive words, so it is this model's paper and not a neighbour's.

Exit codes: 0 = the paper is valid and identified; 1 = not a usable PDF (refetch or ask
the user); 3 = a valid PDF whose identity could not be confirmed (show the user the
first-page text and ask). Prints a JSON report either way.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import check_model_id, emit, normalise_doi, remote_metadata  # noqa: E402

STOPWORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "is", "of", "on",
    "or", "the", "to", "using", "via", "with", "model", "models", "molecular", "prediction",
}


def title_words(title):
    """The distinctive lower-case words of a title (3+ letters, no stopwords)."""
    words = re.findall(r"[a-z0-9]+", (title or "").lower())
    return [w for w in words if len(w) >= 3 and w not in STOPWORDS]


def first_pages_text(path):
    """Text of pages 1-2 via pdftotext, or ``""`` if it is unavailable or fails."""
    if not shutil.which("pdftotext"):
        return ""
    result = subprocess.run(
        ["pdftotext", "-f", "1", "-l", "2", "-q", str(path), "-"], capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else ""


def page_count(path):
    """Page count via pdfinfo, or ``None`` if it cannot be read."""
    if not shutil.which("pdfinfo"):
        return None
    result = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True)
    match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.M)
    return int(match.group(1)) if match else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("pdf")
    parser.add_argument("--model-id", help="read Title and Publication from metadata.yml on main")
    parser.add_argument("--title")
    parser.add_argument("--doi")
    parser.add_argument("--min-kb", type=int, default=30)
    args = parser.parse_args()

    title, doi = args.title, normalise_doi(args.doi) if args.doi else None
    if args.model_id:
        metadata = remote_metadata(check_model_id(args.model_id))
        title = title or metadata.get("Title")
        doi = doi or normalise_doi(metadata.get("Publication"))

    path = Path(args.pdf)
    report = {"path": str(path), "ok": False, "problems": []}
    if not path.is_file():
        report["problems"].append("file does not exist")
        emit(report)
        sys.exit(1)

    data = path.read_bytes()
    report["size_kb"] = round(len(data) / 1024, 1)
    if not data.startswith(b"%PDF-"):
        head = data[:80].decode("latin-1", "replace").strip()
        report["problems"].append(f"not a PDF: the file starts with {head!r}")
    if len(data) < args.min_kb * 1024:
        report["problems"].append(f"only {report['size_kb']} KB; a real article is at least {args.min_kb} KB")
    report["pages"] = page_count(path)
    if report["pages"] is None and data.startswith(b"%PDF-"):
        report["problems"].append("pdfinfo could not read a page count (truncated or damaged file?)")
    if report["problems"]:
        emit(report)
        sys.exit(1)

    text = first_pages_text(path)
    flat = re.sub(r"\s+", " ", text.lower())
    report["doi_found"] = bool(doi) and doi in flat.replace("doi.org/", "")
    wanted = title_words(title)
    found = [w for w in wanted if w in flat]
    report["title_word_coverage"] = round(len(found) / len(wanted), 2) if wanted else None
    report["first_page_excerpt"] = " ".join(text.split())[:300]

    identified = report["doi_found"] or (report["title_word_coverage"] or 0) >= 0.6
    report["ok"] = identified
    if not identified:
        report["problems"].append(
            "valid PDF, but neither the DOI nor most of the title appears on its first pages; "
            "show the excerpt to the user and ask"
        )
    emit(report)
    sys.exit(0 if identified else 3)


if __name__ == "__main__":
    main()
