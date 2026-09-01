#!/usr/bin/env python3
"""make_og_image.py — screenshot an HTML page into a social-preview image.

    python make_og_image.py index.html --out og-image.png --zoom 1.4

Produces one 1200x630 PNG (the 1.91:1 card every platform crops to) from the top of
the page, using headless Chrome. Point apply_theme.py --og-image at the URL the file
will be served from, and the LinkedIn/Slack/X card becomes a picture of the page.

Two things this script does on purpose:

* It SERVES the page's directory over a local HTTP port instead of opening file://.
  Sibling assets then resolve exactly as they do when hosted — a page that loads
  data/foo.js gets its data, so the screenshot shows a populated table rather than an
  empty shell.
* It ZOOMS. LinkedIn renders the card a few hundred pixels wide, so a true 1200x630
  viewport crop turns 13px table text into mush. --zoom captures fewer CSS pixels and
  scales them up: the wordmark, the title and the first rows fill the card and stay
  legible. 1.3-1.5 suits a dense data page; 1.0 is the honest full-viewport crop.

Deterministic (no datetime.now(), no random) and standard library only.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

# Where Chrome lives, in the order we try. Chrome and Chromium share the flags used here.
CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)
CHROME_ON_PATH = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def find_chrome(explicit: str | None = None) -> str:
    """Locate a Chrome/Chromium binary, or fail with something actionable."""
    if explicit:
        if not Path(explicit).exists():
            raise SystemExit(f"ERROR: no such browser binary: {explicit}")
        return explicit
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    for name in CHROME_ON_PATH:
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit(
        "ERROR: no Chrome/Chromium found. Install Google Chrome, or pass --chrome "
        "with the path to a Chrome, Chromium or Edge binary."
    )


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler without the per-request logging on stderr."""

    def log_message(self, fmt, *args):  # noqa: D102 - silencing the base class
        pass


def serve(directory: Path) -> tuple[socketserver.TCPServer, int]:
    """Start a throwaway HTTP server on an ephemeral port; return (server, port)."""
    handler = functools.partial(_QuietHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


_POLL_SECONDS = 0.25


def _await_screenshot(proc: subprocess.Popen, out: Path, timeout: int) -> str:
    """Wait for the PNG, then stop Chrome; return whatever it said on stderr.

    Polls for the file rather than just waiting on the process, because headless Chrome
    often lingers long after the screenshot is on disk. The size has to be unchanged
    across two polls before we kill it, so a half-written PNG is never accepted.
    """
    last_size = -1
    for _ in range(int(timeout / _POLL_SECONDS)):
        if proc.poll() is not None:  # exited on its own; the file is final
            break
        if out.exists():
            size = out.stat().st_size
            if size > 0 and size == last_size:
                proc.kill()
                break
            last_size = size
        time.sleep(_POLL_SECONDS)
    else:
        proc.kill()
    return proc.communicate()[1] or ""


def capture(
    page: Path,
    out: Path,
    width: int = 1200,
    height: int = 630,
    zoom: float = 1.0,
    retina: int = 2,
    wait_ms: int = 2000,
    chrome: str | None = None,
    timeout: int = 60,
) -> None:
    """Write a width*retina x height*retina PNG of the top of `page`.

    The zoom maths: to fill a WxH card at zoom z, capture round(W/z) x round(H/z) CSS
    pixels and render them at a device scale factor of z*retina. Chrome multiplies the
    window size by the scale factor, so the PNG comes out at W*retina x H*retina
    whatever the zoom — the zoom only changes how much of the page is in frame.

    `--headless=new` writes the screenshot and then, on some builds, declines to exit;
    so the process is given `timeout` seconds and then killed, and the run counts as a
    success if the PNG landed. The stale output is deleted first, so a leftover file
    from an earlier run can never be mistaken for a fresh capture.
    """
    binary = find_chrome(chrome)
    css_w, css_h = round(width / zoom), round(height / zoom)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)

    httpd, port = serve(page.parent)
    try:
        with tempfile.TemporaryDirectory(prefix="og-image-chrome-") as profile:
            cmd = [
                binary,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-color-profile=srgb",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={profile}",
                f"--window-size={css_w},{css_h}",
                f"--force-device-scale-factor={zoom * retina:g}",
                f"--virtual-time-budget={wait_ms}",
                f"--screenshot={out}",
                f"http://127.0.0.1:{port}/{page.name}",
            ]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            err = _await_screenshot(proc, out, timeout)
    finally:
        httpd.shutdown()
        httpd.server_close()

    if not out.exists():
        raise SystemExit(
            f"ERROR: Chrome wrote no screenshot within {timeout}s.\n"
            + (err or "").strip()[-2000:]
        )
    print(
        f"wrote {out} ({out.stat().st_size:,} bytes, "
        f"{width * retina}x{height * retina} px, zoom {zoom:g})",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("html_file", help="page to screenshot (served from its own directory)")
    p.add_argument("--out", default="og-image.png", help="output PNG (default: og-image.png)")
    p.add_argument("--width", type=int, default=1200, help="card width in CSS px (default: 1200)")
    p.add_argument("--height", type=int, default=630, help="card height in CSS px (default: 630)")
    p.add_argument(
        "--zoom", type=float, default=1.0, metavar="Z",
        help="scale the page up so text survives the small card; 1.3-1.5 suits a dense "
             "data page (default: 1.0, the true viewport crop)",
    )
    p.add_argument(
        "--retina", type=int, default=2, metavar="N",
        help="pixel density of the PNG (default: 2, i.e. 2400x1260 for a 1200x630 card)",
    )
    p.add_argument(
        "--wait-ms", type=int, default=2000,
        help="virtual time given to scripts and fonts before the capture (default: 2000)",
    )
    p.add_argument(
        "--timeout", type=int, default=60,
        help="seconds to wait for the PNG before giving up on Chrome (default: 60)",
    )
    p.add_argument("--chrome", help="path to a Chrome/Chromium/Edge binary (default: autodetect)")
    args = p.parse_args(argv)

    page = Path(args.html_file).expanduser().resolve()
    if not page.is_file():
        raise SystemExit(f"ERROR: no such page: {page}")
    if args.zoom <= 0 or args.retina <= 0:
        p.error("--zoom and --retina must be positive")

    capture(
        page,
        Path(args.out).expanduser().resolve(),
        width=args.width,
        height=args.height,
        zoom=args.zoom,
        retina=args.retina,
        wait_ms=args.wait_ms,
        chrome=args.chrome,
        timeout=args.timeout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
