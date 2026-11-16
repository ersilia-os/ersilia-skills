"""The report as an A4 PDF, for sending or archiving.

Renders the HTML report in Chrome (Playwright) with the print adjustments in
``assets/report-print.css``: nothing sticky, and each close-reading note printed in full in
a box beside its paragraph (hover does not exist on paper).

Usage (in the conda env, which has Playwright):
    python report_pdf.py <report.html> <out.pdf>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import SKILL_DIR

PRINT_CSS = SKILL_DIR / "assets" / "report-print.css"
MARGIN = {"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"}


def main(argv: list[str] | None = None) -> int:
    """Write the PDF."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("report", type=Path)
    p.add_argument("out", type=Path)
    args = p.parse_args(argv)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(color_scheme="light")
        page.goto(args.report.resolve().as_uri())
        page.wait_for_timeout(2000)  # web fonts
        page.add_style_tag(content=PRINT_CSS.read_text(encoding="utf-8"))
        page.pdf(path=str(args.out), format="A4", print_background=True, margin=MARGIN)
        browser.close()
    print(f"pdf: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
