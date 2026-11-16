"""Write the evidence report: one self-contained HTML page, ready to publish as a private
Artifact (the page is a fragment, as the Artifact tool expects: <title>, <style>, content).

The layout follows the web detectors people already know (report_html.py): the share of
the prose that reads as AI-written, the verdict tier and the non-statistical checks at the
top; the text with AI-like sentences highlighted and close-reading notes as tags; a side
panel with each passage's combined score and each detector's scores and track record.

Needs grade.json in the work folder (run grade.py first). For a PDF, see report_pdf.py.

Usage:
    python build_report.py --case "2026-11-draft-1" --kind article --context collaborator-draft
        [--work /tmp/ai_text_detection] [--out report.html]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import WORK_DIR, die
from report_html import render

KINDS = ["article", "grant", "review", "response-letter", "email", "other"]
CONTEXTS = [
    "collaborator-draft",
    "reviewer-of-my-paper",
    "manuscript-i-review",
    "grant-i-review",
    "other",
]


def main(argv: list[str] | None = None) -> int:
    """Write report.html."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument(
        "--case", required=True, help="a neutral label, never a person's name"
    )
    p.add_argument("--kind", default="article", choices=KINDS)
    p.add_argument("--context", default="other", choices=CONTEXTS)
    p.add_argument("--out", help="default: <work>/report.html")
    args = p.parse_args(argv)
    work = Path(args.work)
    if not (work / "grade.json").exists():
        die(f"no grade.json in {work}: run grade.py first")
    out = Path(args.out) if args.out else work / "report.html"
    out.write_text(render(work, args.case, args.kind, args.context), encoding="utf-8")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
