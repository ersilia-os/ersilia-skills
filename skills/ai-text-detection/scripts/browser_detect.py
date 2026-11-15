"""Open Chrome and run web AI detectors on the prepared chunks, at a human pace.

The skill drives the user's installed Google Chrome itself (Playwright, ``channel="chrome"``),
with a dedicated profile in ~/.ai-text-detection/chrome-profile. Logins to GPTZero, Pangram
and the like are remembered there, so the user signs in once, if a site requires it, and
never again. If Claude in Chrome is connected in the session, SKILL.md prefers that instead.

For every tool and chunk it opens the site, finds the main text box (the largest visible
textarea or editable area), pastes the chunk, presses the button that says scan, check,
detect or analyse, and waits for the result. It saves the page text and a screenshot to
<work>/web/<tool>_chunk<k>.{txt,png} and prints one JSON line per attempt. Claude then
reads each result page and records the score with ``web_detectors.py record``, so no
site-specific parsing has to keep up with redesigns. A first percentage near "AI" is
printed as ``guess``, only as a hint.

It stops using a site as soon as it sees a CAPTCHA, a login wall or a usage limit, and
reports it. It never works around them. It waits several seconds between submissions.

Run inside the env (Playwright is installed there):
    conda run -n ai-text-detection python browser_detect.py --tools pangram,gptzero [--chunks 1,2] [--login]

``--login`` only opens the sites in the dedicated profile so the user can sign in, then waits
until the window is closed.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

from _common import LOCAL, REFS, WORK_DIR, die, read_json

PROFILE = LOCAL / "chrome-profile"
BUTTON_RE = re.compile(r"\b(detect|scan|check|analy[sz]e|run|submit)\b", re.IGNORECASE)
BLOCK_RE = re.compile(
    r"verify you are human|captcha|are you a robot|unusual traffic|log ?in to continue|sign (?:up|in) to (?:continue|scan|check)|"
    r"(?:daily|monthly|free) (?:limit|quota)|limit reached|upgrade to (?:continue|scan)|out of (?:credits|words)",
    re.IGNORECASE,
)
PCT_RE = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%[^%\n]{0,40}\b(AI|machine|generated)\b|\b(AI|machine)[^%\n]{0,40}?(\d{1,3}(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)


def guess(text: str) -> float | None:
    """First percentage that sits next to 'AI' on the result page (a hint only)."""
    m = PCT_RE.search(text)
    if not m:
        return None
    v = m.group(1) or m.group(4)
    return round(float(v) / 100, 3)


def find_input(page):
    """The main text input: largest visible textarea, else largest contenteditable."""
    best, area = None, 0
    for sel in ("textarea", "[contenteditable='true']", "[contenteditable='']"):
        for el in page.query_selector_all(sel):
            try:
                if not el.is_visible():
                    continue
                box = el.bounding_box() or {}
                a = box.get("width", 0) * box.get("height", 0)
                if a > area:
                    best, area = el, a
            except Exception:  # noqa: BLE001, S112 - element detached while scanning
                continue
        if best:
            return best
    return None


def click_go(page) -> bool:
    """Press the visible button whose label says scan/check/detect."""
    for el in page.query_selector_all("button, [role='button'], input[type='submit']"):
        try:
            label = (
                el.inner_text()
                or el.get_attribute("value")
                or el.get_attribute("aria-label")
                or ""
            ).strip()
            if (
                el.is_visible()
                and el.is_enabled()
                and BUTTON_RE.search(label)
                and len(label) < 40
            ):
                el.click()
                return True
        except Exception:  # noqa: BLE001, S112 - element detached
            continue
    return False


def run_one(page, tool: dict, k: int, text: str, out: Path) -> dict:
    """One submission; saves the result page; returns a status row."""
    row = {"tool": tool["id"], "chunk": k}
    page.goto(tool["url"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    before = page.inner_text("body")
    if BLOCK_RE.search(before):
        return {**row, "status": "blocked", "why": BLOCK_RE.search(before).group(0)}
    box = find_input(page)
    if not box:
        return {
            **row,
            "status": "no-input",
            "why": "no text box found; the site may need a login",
        }
    box.click()
    if box.evaluate("e => e.tagName") == "TEXTAREA":
        box.fill(text)
    else:
        page.keyboard.insert_text(text)
    page.wait_for_timeout(800)
    if not click_go(page):
        return {**row, "status": "no-button", "why": "no scan/check button found"}
    after = before
    for _ in range(30):  # up to ~60 s for the verdict to appear
        page.wait_for_timeout(2000)
        after = page.inner_text("body")
        if BLOCK_RE.search(after):
            return {**row, "status": "blocked", "why": BLOCK_RE.search(after).group(0)}
        if after != before and guess(after) is not None:
            break
    stem = out / f"{tool['id']}_chunk{k}"
    stem.with_suffix(".txt").write_text(after, encoding="utf-8")
    page.screenshot(path=str(stem.with_suffix(".png")), full_page=True)
    return {
        **row,
        "status": "done",
        "guess": guess(after),
        "page_text": str(stem.with_suffix(".txt")),
        "screenshot": str(stem.with_suffix(".png")),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the requested tools over the requested chunks."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument(
        "--tools",
        help="comma-separated tool ids (default: the registry's default order)",
    )
    p.add_argument("--chunks", help="comma-separated chunk numbers (default: all)")
    p.add_argument(
        "--login",
        action="store_true",
        help="open the sites so the user can sign in, then wait",
    )
    args = p.parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        die(
            "needs Playwright in the env: ask the user, then `conda run -n ai-text-detection pip install playwright`"
        )
    reg = read_json(REFS / "web_detectors.json")
    tools = {t["id"]: t for t in reg["tools"]}
    order = args.tools.split(",") if args.tools else reg["default_order"]
    unknown = [t for t in order if t not in tools]
    if unknown:
        die(f"unknown tool(s): {', '.join(unknown)}")
    work = Path(args.work)
    state = read_json(work / "web_detectors.json")
    if not args.login and not state:
        die("run `web_detectors.py prepare` first")
    PROFILE.mkdir(parents=True, exist_ok=True)
    out = work / "web"
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(PROFILE),
            channel="chrome",
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if args.login:
            for tid in order:
                pg = ctx.new_page()
                pg.goto(tools[tid]["url"])
            print(
                "signed-in state is kept in the dedicated profile; close the browser window when done",
                flush=True,
            )
            try:
                ctx.wait_for_event("close", timeout=0)
            except Exception:  # noqa: BLE001, S110 - user closed the window
                pass
            return 0
        wanted = {int(x) for x in args.chunks.split(",")} if args.chunks else None
        for tid in order:
            for c in state["chunks"]:
                if wanted and c["chunk"] not in wanted:
                    continue
                text = Path(c["file"]).read_text(encoding="utf-8")
                try:
                    row = run_one(page, tools[tid], c["chunk"], text, out)
                except Exception as ex:  # noqa: BLE001 - network or page errors: report, move on
                    row = {
                        "tool": tid,
                        "chunk": c["chunk"],
                        "status": "error",
                        "why": str(ex)[:200],
                    }
                print(json.dumps(row), flush=True)
                if row["status"] in ("blocked", "no-input"):
                    break  # stop using this site; never work around a wall
                time.sleep(random.uniform(5, 9))  # human pace
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
