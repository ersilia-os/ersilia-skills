"""Write the formal assessment: the evidence as a procedure that follows the official
rules and guidance, step by step, for showing an editor, a programme officer or the
author that the assessment was done properly (lib/formal.py; references/formal-assessment.md).

It is aligned with the sources it cites (references/frameworks.json), never certified by
them: no official EU guideline for detecting AI-written text exists. Needs grade.json
(run grade.py first). For a PDF: report_pdf.py formal.html <out.pdf>.

Usage:
    python formal_report.py --case "2026-11-draft-1" --kind article --context collaborator-draft
        [--assessor "Name"] [--policy "Journal X: authors must disclose AI use in Methods"]
        [--date 2026-11-17] [--work /tmp/ai_text_detection] [--out formal.html]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from build_report import CONTEXTS, KINDS
from lib.common import WORK_DIR, die
from lib.formal import render


def main(argv: list[str] | None = None) -> int:
    """Write formal.html."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument(
        "--case", required=True, help="a neutral label, never a person's name"
    )
    p.add_argument("--kind", default="article", choices=KINDS)
    p.add_argument("--context", default="other", choices=CONTEXTS)
    p.add_argument("--assessor", default="", help="who reviewed the findings and signs")
    p.add_argument(
        "--policy",
        default="",
        help="the journal, funder or institution rule that applies",
    )
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--out", help="default: <work>/formal.html")
    args = p.parse_args(argv)
    work = Path(args.work)
    if not (work / "grade.json").exists():
        die(f"no grade.json in {work}: run grade.py first")
    out = Path(args.out) if args.out else work / "formal.html"
    out.write_text(
        render(
            work,
            args.case,
            args.kind,
            args.context,
            args.date,
            args.assessor,
            args.policy,
        ),
        encoding="utf-8",
    )
    print(f"formal assessment: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
