"""Run web AI detectors in Chrome on the prepared text, at a human pace.

Drives the user's installed Google Chrome (Playwright, ``channel="chrome"``) with a
dedicated profile in ~/.ai-text-detection/chrome-profile, so a site the user signs in to
once stays signed in. For each tool and unit of the plan (segments.py) it:

1. opens the site, declines non-essential cookies (accepts only where the user approved it
   for that site: ``"cookies": "accept"`` in references/web_detectors.json);
2. finds the main text box, also inside embedded frames, clicking ``input_click`` first
   for editors that only appear on click;
3. pastes the text, presses the nearest scan / check / detect button, and waits up to
   ~90 s for a verdict;
4. saves the page text, the new result text, the sentences the site highlighted and a
   screenshot under <work>/plan/ (<work>/<plan name>/ with --plan), appends a row to
   the plan's results (lib/detectors.py) and prints it as one JSON line.

Scores are read with the site's parser in web_detectors.json when it has one; check a
sample of pages by eye after every run. Without a parser the
printed ``guess`` is only a hint: read the page and use ``web_detectors.py record``.

It stops on a site as soon as it sees a CAPTCHA a person would have to answer, a login
wall or a free-use limit, and reports it; it never works around them. Sites whose terms
forbid automation (``"terms": "no-automation"``) are skipped.

Usage (inside the conda env, which has Playwright):
    python browser_detect.py                              # unattended tools, the passages
    python browser_detect.py --tools zerogpt --chunks S,W # the other splits (or ids: S1,W3)
    python browser_detect.py --plan <controls>/controls.json --tools zerogpt
    python browser_detect.py --login --tools gptzero      # let the user sign in once
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

from lib.common import ENV_NAME, LOCAL, WORK_DIR, die
from lib.detectors import (
    Scan,
    is_ai_colour,
    parse_score,
    report_left_out,
    tool,
    unattended,
)

PROFILE = LOCAL / "chrome-profile"
BUTTON_RE = re.compile(
    r"\b(detect\w*|scan\w*|check\w*|analy[sz]\w*|test|run|submit)\b", re.IGNORECASE
)
BLOCK_RE = re.compile(
    r"verify you are human|(?<![a-z])captcha|are you a robot|unusual traffic|log ?in to continue|sign (?:up|in) to (?:continue|scan|check)|"
    # A limit that was hit, not marketing copy such as "no daily limit".
    r"(?:daily|monthly|free) (?:limit|quota) (?:reached|exceeded|hit|used)|"
    r"(?:reached|exceeded|hit|used up) (?:your|the) (?:daily |monthly |free )*(?:limit|quota|scans|credits)|"
    r"limit reached|upgrade to (?:continue|scan)|out of (?:credits|words)|"
    r"sign up with google|for free to get more|create (?:a )?free account to (?:continue|scan)",
    re.IGNORECASE,
)
PCT_RE = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%[^%]{0,40}?\b(AI|machine|generated|GPT)\b|\b(AI|machine|generated|GPT)[^%]{0,40}?(\d{1,3}(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)


SCORE_LINE_RE = re.compile(
    r"^\s*(\d{1,3}(?:\.\d+)?)\s*%?\s*\n\s*(?:%\s*)?AI\s+(?:score|probability)\b",
    re.IGNORECASE | re.MULTILINE,
)


def guess(text: str) -> float | None:
    """The AI score on the result page (a hint only): a number on the line above
    'AI Score' / '% AI probability', else the first percentage next to 'AI'."""
    m = SCORE_LINE_RE.search(text)
    if m:
        return round(float(m.group(1)) / 100, 3)
    m = PCT_RE.search(text)
    if not m:
        return None
    v = m.group(1) or m.group(4)
    return round(float(v) / 100, 3)


PCT_ANY = re.compile(r"\d{1,3}(?:\.\d+)?\s*%")
COOKIE_RE = re.compile(
    r"^(decline( all)?|reject( all| non-essential)?( cookies)?|reject non-essential cookies|"
    r"(use )?(only|strictly) (necessary|essential|functional)( cookies)?( only)?|necessary only|deny( all)?|refuse( all)?)$",
    re.IGNORECASE,
)
ACCEPT_RE = re.compile(
    r"^(accept( all)?( cookies)?|allow( all)?( cookies)?|agree|i agree|got it)$",
    re.IGNORECASE,
)


CAPTCHA_FRAME = re.compile(
    r"hcaptcha|recaptcha|challenges\.cloudflare|turnstile|arkoselabs|funcaptcha",
    re.IGNORECASE,
)


def _challenge_frame(f) -> bool:
    """A CAPTCHA frame a person would have to answer: not the invisible reCAPTCHA
    badge many sites load on every page (``size=invisible``, nothing to solve unless
    a challenge frame then appears on screen)."""
    url = f.url or ""
    if not CAPTCHA_FRAME.search(url) or "size=invisible" in url:
        return False
    try:
        el = f.frame_element()
        box = el.bounding_box() or {}
        return el.is_visible() and box.get("height", 0) > 40
    except Exception:  # noqa: BLE001 - frame detached
        return False


def all_text(page) -> str:
    """Visible text of the page and of its embedded frames (some sites show the
    detector, and its verdict, inside a frame)."""
    parts = []
    for f in page.frames:
        try:
            parts.append(f.inner_text("body", timeout=2000))
        except Exception:  # noqa: BLE001, S112 - frame without body or detached
            continue
    return "\n".join(parts)


def captcha_shown(page) -> bool:
    """Whether a CAPTCHA widget or a human-verification wall is on the page."""
    try:
        frames = any(_challenge_frame(f) for f in page.frames if f != page.main_frame)
        return frames or bool(BLOCK_RE.search(all_text(page)[:3000]))
    except Exception:  # noqa: BLE001 - page navigating
        return False


def wait_for_human(page, seconds: int) -> bool:
    """Let the user solve a CAPTCHA in the open window; never solve it automatically."""
    print(
        json.dumps(
            {
                "status": "waiting-for-user",
                "why": "CAPTCHA shown; solve it in the Chrome window",
                "seconds": seconds,
            }
        ),
        flush=True,
    )
    for _ in range(seconds // 2):
        page.wait_for_timeout(2000)
        if not captcha_shown(page):
            page.wait_for_timeout(3000)
            return True
    return False


def new_lines(before: str, after: str) -> str:
    """Lines of the page that were not there before the scan (the result, not the marketing)."""
    seen = set(before.splitlines())
    return "\n".join(ln for ln in after.splitlines() if ln.strip() and ln not in seen)


def dismiss_cookies(page, accept: bool = False) -> None:
    """Close a cookie banner by declining non-essential cookies, if one is shown.

    Only when the site offers no way to decline and the user approved accepting for that
    site ("cookies": "accept" in references/web_detectors.json) is "Accept" clicked.
    """
    for pattern in (COOKIE_RE, ACCEPT_RE) if accept else (COOKIE_RE,):
        for el in page.query_selector_all("button, [role='button'], a"):
            try:
                label = (el.inner_text() or "").strip()
                if el.is_visible() and pattern.match(label):
                    el.click()
                    page.wait_for_timeout(500)
                    return
            except Exception:  # noqa: BLE001, S112 - element detached
                continue


def find_input(page):
    """The main text input: largest visible textarea, else largest contenteditable."""
    best, area = None, 0
    frames = [page.main_frame] + [f for f in page.frames if f != page.main_frame]
    for sel in ("textarea", "[contenteditable='true']", "[contenteditable='']"):
        for el in [x for fr in frames for x in fr.query_selector_all(sel)]:
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


# Buttons, including the links and inputs some sites style as buttons.
BUTTONS = (
    "button, [role='button'], input[type='submit'], input[type='button'], "
    "a[class*='btn'], a[class*='button'], div[class*='btn']"
)
MODE_RE = re.compile(
    r"\b(deep|plagiarism|grammar|upload|sample|example|humani[sz]e|paraphras|translate|upgrade|sign|log ?in)\w*",
    re.IGNORECASE,
)
ACTION_RE = re.compile(
    r"^(run|start)?\s*(scan|check|detect|analy[sz]|test)\w*\b", re.IGNORECASE
)


def click_go(page, box, accept_cookies: bool = False) -> bool:
    """Press the scan/check/detect button nearest to the text box (as a person would)."""
    tb = box.bounding_box() or {"x": 0, "y": 0, "width": 0, "height": 0}
    cx, cy = tb["x"] + tb["width"] / 2, tb["y"] + tb["height"]
    best, dist = None, float("inf")
    scope = box.owner_frame() or page.main_frame
    candidates = scope.query_selector_all(BUTTONS)
    if scope != page.main_frame:
        candidates += page.query_selector_all(BUTTONS)
    for el in candidates:
        try:
            label = (
                el.inner_text()
                or el.get_attribute("value")
                or el.get_attribute("aria-label")
                or ""
            ).strip()
            if not (
                el.is_visible()
                and el.is_enabled()
                and BUTTON_RE.search(label)
                and len(label) < 40
                and "?"
                not in label  # an FAQ entry ("What does it check?"), not an action
            ):
                continue
            bb = el.bounding_box()
            if not bb:
                continue
            d = abs(bb["x"] + bb["width"] / 2 - cx) + abs(
                bb["y"] + bb["height"] / 2 - cy
            )
            # Mode tabs and side tools ("Deep AI Scan", "Plagiarism", "Upload") are not the action.
            if MODE_RE.search(label):
                d += 2000
            if ACTION_RE.search(label):
                d -= 150
            if d < dist:
                best, dist = el, d
        except Exception:  # noqa: BLE001, S112 - element detached
            continue
    if best is None:
        return False
    best.scroll_into_view_if_needed()
    for attempt in range(3):
        try:
            best.click(timeout=5000)
            break
        except Exception:
            dismiss_cookies(page, accept_cookies)
            page.keyboard.press("Escape")
            if attempt == 2:
                raise
    return True


HIGHLIGHT_JS = """() => { const out = [];
  for (const el of document.querySelectorAll('body *')) {
    const t = (el.innerText || '').trim();
    if (t.length < 25 || t.length > 1500) continue;
    const bg = getComputedStyle(el).backgroundColor;
    if (!bg || bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') continue;
    const m = (bg.match(/[\\d.]+/g) || []).map(Number);
    if (m.length >= 3 && m[0] > 240 && m[1] > 240 && m[2] > 240) continue;
    out.push({text: t, bg});
  }
  return out; }"""


def norm_ws(t: str) -> str:
    """Collapse whitespace, for matching page text against the chunk."""
    return re.sub(r"\s+", " ", t).strip()


def highlights(page, chunk_text: str) -> list[dict]:
    """Sentences the site marked (coloured background) that come from the chunk itself.

    Page furniture (buttons, banners) is excluded because it is not part of the chunk.
    Nested duplicates are removed, keeping the innermost element.
    """
    try:
        cands = page.evaluate(HIGHLIGHT_JS)
    except Exception:  # noqa: BLE001 - page navigating
        return []
    src = norm_ws(chunk_text)
    keep = []
    for c in cands:
        t = norm_ws(c["text"])
        if t in src and len(t) < 0.8 * len(src) and is_ai_colour(c["bg"]):
            keep.append({"text": t, "bg": c["bg"]})
    keep = [
        k
        for k in keep
        if not any(k["text"] != o["text"] and o["text"] in k["text"] for o in keep)
    ]
    seen, out = set(), []
    for k in keep:
        if k["text"] not in seen:
            seen.add(k["text"])
            out.append(k)
    return out


CAPTCHA_LEFT = "CAPTCHA (left for the user; never solved automatically)"
WORKING_RE = re.compile(
    r"\b(checking|analy[sz]ing|processing|scanning|loading)\b", re.IGNORECASE
)
VERDICT_WORD_RE = re.compile(r"\b(AI|human|generated|written)\b", re.IGNORECASE)


def open_input(page, tool: dict):
    """The site's text box, or None. Editors that appear only on a click
    (``input_click``) or once the page has finished loading are waited for."""
    accept = tool.get("cookies") == "accept"
    box = find_input(page)
    if not box and tool.get("input_click"):
        try:
            page.click(tool["input_click"], timeout=8000)
            page.wait_for_timeout(1000)
        except Exception:  # noqa: BLE001, S110 - fall through to the retry below
            pass
        box = find_input(page)
    if not box:
        page.wait_for_timeout(5000)
        dismiss_cookies(page, accept)
        box = find_input(page)
    return box


def has_verdict(tool: dict, fresh: str) -> bool:
    """Whether the new text on the page holds the site's verdict. With a parser, only
    the verdict it knows counts: marketing text such as "99% accurate" on a freshly
    opened result tab must not end the wait."""
    if tool.get("parse"):
        return parse_score(tool["id"], fresh)[0] is not None
    return bool(PCT_ANY.search(fresh) and VERDICT_WORD_RE.search(fresh))


def wait_for_verdict(page, tool: dict, pasted: str, human_wait: int) -> str | None:
    """The page text once the verdict shows (or after ~90 s); None when a CAPTCHA
    appears that the user does not answer."""
    after = pasted
    for _ in range(45):
        page.wait_for_timeout(2000)
        after = all_text(page)
        if captcha_shown(page) and not (
            human_wait and wait_for_human(page, human_wait)
        ):
            return None
        fresh = new_lines(pasted, after)
        if WORKING_RE.search(fresh[:300]):
            continue
        if has_verdict(tool, fresh):
            page.wait_for_timeout(2000)  # let the numbers settle
            return all_text(page)
    return after


def save_pages(page, stem: Path, after: str, fresh: str, text: str) -> dict:
    """Write the page text, the result text, the highlighted sentences and a screenshot
    next to ``stem``; return where they are."""
    stem.with_suffix(".txt").write_text(after, encoding="utf-8")
    result = stem.with_name(stem.name + "_result.txt")
    result.write_text(fresh, encoding="utf-8")
    marks = highlights(page, text)
    stem.with_name(stem.name + "_highlights.json").write_text(
        json.dumps(marks, ensure_ascii=False), encoding="utf-8"
    )
    # The visible viewport, where results show.
    page.screenshot(path=str(stem.with_suffix(".png")))
    return {
        "result_text": str(result),
        "highlighted_sentences": len(marks),
        "page_text": str(stem.with_suffix(".txt")),
        "screenshot": str(stem.with_suffix(".png")),
    }


def run_one(
    page, tool: dict, k: int, text: str, out: Path, human_wait: int = 0
) -> dict:
    """One submission; saves the result page; returns a status row."""
    row = {"tool": tool["id"], "chunk": k}
    accept = tool.get("cookies") == "accept"
    page.goto(tool["url"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    dismiss_cookies(page, accept)
    if captcha_shown(page) and human_wait:
        wait_for_human(page, human_wait)
    wall = BLOCK_RE.search(all_text(page))
    if wall:
        return {**row, "status": "blocked", "why": wall.group(0)}
    box = open_input(page, tool)
    if not box:
        return {
            **row,
            "status": "no-input",
            "why": "no text box found; the site may need a login",
        }
    box.focus()
    if box.evaluate("e => e.tagName") == "TEXTAREA":
        box.fill(text)
    else:
        page.keyboard.insert_text(text)
    page.wait_for_timeout(800)
    pasted = all_text(page)
    n_tabs = len(page.context.pages)
    dismiss_cookies(page, accept)  # banners that appeared late
    if not click_go(page, box, accept):
        return {**row, "status": "no-button", "why": "no scan/check button found"}
    # Some sites open the result in a new tab: follow it.
    page.wait_for_timeout(2500)
    if len(page.context.pages) > n_tabs:
        page = page.context.pages[-1]
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)
        pasted = ""
    if captcha_shown(page) and not (human_wait and wait_for_human(page, human_wait)):
        return {**row, "status": "blocked", "why": CAPTCHA_LEFT}
    after = wait_for_verdict(page, tool, pasted, human_wait)
    if after is None:
        return {**row, "status": "blocked", "why": CAPTCHA_LEFT}
    fresh = new_lines(pasted, after)
    saved = save_pages(page, out / f"{tool['id']}_chunk{k}", after, fresh, text)
    return {
        **row,
        "status": "done" if fresh else "no-result",
        "guess": guess(fresh),
        **saved,
    }


def scan_unit(ctx, tool: dict, unit: dict, out: Path, human_wait: int) -> dict:
    """Run one tool on one unit and read its score; errors become a status row."""
    text = Path(unit["file"]).read_text(encoding="utf-8")
    try:
        row = run_one(ctx.pages[0], tool, unit["chunk"], text, out, human_wait)
        for extra in ctx.pages[1:]:  # close result tabs between submissions
            extra.close()
    except Exception as ex:  # noqa: BLE001 - network or page errors: report, move on
        return {
            "tool": tool["id"],
            "chunk": unit["chunk"],
            "status": "error",
            "why": str(ex)[:200],
        }
    if row.get("result_text"):
        score, label = parse_score(
            tool["id"], Path(row["result_text"]).read_text(encoding="utf-8")
        )
        row.update({"score": score, "label": label, "parsed": score is not None})
    return row


def login(ctx, urls: list[str]) -> None:
    """Open the sites and wait until the user closes the window."""
    for url in urls:
        ctx.new_page().goto(url)
    print(
        "signed-in state is kept in the dedicated profile; close the browser window when done",
        flush=True,
    )
    try:
        ctx.wait_for_event("close", timeout=0)
    except Exception:  # noqa: BLE001, S110 - user closed the window
        pass


def main(argv: list[str] | None = None) -> int:
    """Run the requested tools over the requested chunks."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument(
        "--tools",
        help="comma-separated tool ids (default: the tools that run unattended)",
    )
    p.add_argument(
        "--chunks",
        help="comma-separated unit ids or scales (P, S, W); default: the passages",
    )
    p.add_argument(
        "--plan",
        help="JSON {units: [{chunk, file}]} to scan instead of the document's plan",
    )
    p.add_argument(
        "--log",
        help="JSONL to append parsed results to (default: <plan>.results.jsonl)",
    )
    p.add_argument(
        "--pace",
        type=float,
        nargs=2,
        default=[5, 9],
        help="seconds to wait between submissions",
    )
    p.add_argument(
        "--login",
        action="store_true",
        help="open the sites so the user can sign in, then wait",
    )
    p.add_argument(
        "--human-wait",
        type=int,
        default=0,
        help="seconds to wait for the user to solve a CAPTCHA in the open window (0: stop at once)",
    )
    args = p.parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        die(
            f"needs Playwright in the env: ask the user, then `conda run -n {ENV_NAME} pip install playwright`"
        )
    # By default, the unattended tools that run in a browser (not through an API).
    order = (
        args.tools.split(",")
        if args.tools
        else [t for t in unattended() if tool(t).get("route") != "api"]
    )
    unknown = [t for t in order if not tool(t)]
    if unknown:
        die(f"unknown tool(s): {', '.join(unknown)}")
    work = Path(args.work)
    scan = None if args.login else Scan.load(work, args.plan, args.log)
    PROFILE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(PROFILE),
            channel="chrome",
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        if not ctx.pages:
            ctx.new_page()
        if scan is None:
            login(ctx, [tool(t)["url"] for t in order])
            return 0
        scan.pages.mkdir(parents=True, exist_ok=True)
        for tid in order:
            if tool(tid).get("terms") == "no-automation":
                print(
                    json.dumps(
                        {
                            "tool": tid,
                            "status": "skipped",
                            "why": "the site's terms forbid automated use; use it by hand",
                        }
                    ),
                    flush=True,
                )
                continue
            report_left_out(scan, args.chunks, tid)
            for unit in scan.select(args.chunks, tool(tid)):
                row = scan_unit(ctx, tool(tid), unit, scan.pages, args.human_wait)
                scan.save(row)
                print(json.dumps(row), flush=True)
                if row["status"] in ("blocked", "no-input"):
                    break  # stop using this site; never work around a wall
                time.sleep(random.uniform(*args.pace))  # human pace
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
