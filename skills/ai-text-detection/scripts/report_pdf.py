"""The report as an A4 PDF, for sending or archiving.

Renders the HTML report in Chrome (Playwright) with print adjustments: the side panel
and legend are not sticky, and each close-reading note is printed in full in a box
beside its paragraph (hover does not exist on paper).

Usage (conda env, which has Playwright):
    python report_pdf.py <report.html> <out.pdf>
"""

from __future__ import annotations

import sys
from pathlib import Path

PRINT_CSS = ".side,.doclegend{position:static!important} .card{break-inside:auto} .psg{break-inside:auto} .hero{break-inside:avoid} .note{position:static} .note::after,.note:hover::after,.note:focus::after{content:attr(data-note);display:block;float:right;position:static;width:36%;margin:4px 0 8px 14px;padding:6px 10px;border:1px solid var(--accent);border-left:4px solid var(--accent);border-radius:6px;background:var(--card);color:var(--ink);font:400 .78rem/1.45 Inter,system-ui,sans-serif;box-shadow:none} .note{display:inline} .doclegend span:nth-last-child(2){display:none}"


def main(argv: list[str] | None = None) -> int:
    """Write the PDF."""
    from playwright.sync_api import sync_playwright

    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print(__doc__)
        return 2
    src, dst = Path(args[0]).resolve(), Path(args[1])
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        pg = b.new_page(color_scheme="light")
        pg.goto(src.as_uri())
        pg.wait_for_timeout(2000)  # web fonts
        pg.add_style_tag(content=PRINT_CSS)
        pg.pdf(
            path=str(dst),
            format="A4",
            print_background=True,
            margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"},
        )
        b.close()
    print(f"pdf: {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
