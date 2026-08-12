#!/usr/bin/env python3
"""apply_theme.py — assemble a self-contained, Ersilia-styled HTML page.

Two modes:

  new       Scaffold a fresh page from a starter archetype (app|document|dashboard).
              python apply_theme.py --mode new --archetype dashboard \
                  --out demo.html --title "GRAND" --eyebrow "Target Selector"

  retrofit  Wrap an EXISTING page: swap in the canonical <head> (inlined ersilia.css
            + SVG favicon), keep the page's own <style> blocks (cascading AFTER ours so
            the Ersilia tokens are available and page rules still apply), strip external
            CSS/font <link>s (they break under the Artifact CSP), and append the credit
            footer.
              python apply_theme.py --mode retrofit page.html --out page.ersilia.html

The template is assembled with str.replace on __TOKENS__ (never str.format), the same
convention as molecule-auditing/make_visualizer.py, so any embedded JSON/braces in a
retrofitted page survive untouched. Standard library only.

External references found during a retrofit are reported on stderr — self-containment is
the caller's to fix (inline the asset or embed as a data: URI); this script never fetches.
"""

from __future__ import annotations

import argparse
import hashlib
import random
import re
import sys
from pathlib import Path

from _common import asset, parse_html, read_text, warn

ARCHETYPES = ("app", "document", "dashboard")
_EYEBROW_DEFAULT = {"app": "Explorer", "document": "Report", "dashboard": "Dashboard"}

# The official Ersilia brand colours (assets/ersilia.css :root, "from stylia").
# The favicon is a plain disc in one of these — see resolve_favicon().
FAVICON_COLOURS = {
    "plum": "#50285A",
    "purple": "#AA96FA",
    "mint": "#BEE6B4",
    "blue": "#8CC8FA",
    "yellow": "#FAD782",
    "pink": "#DCA0DC",
    "orange": "#FAA08C",
    "egray": "#D2D2D0",
}
# egray is selectable by name but kept out of the shuffle: a grey dot in a tab
# strip reads as a disabled or still-loading icon rather than as a brand mark.
_SHUFFLE_POOL = tuple(name for name in FAVICON_COLOURS if name != "egray")
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

_STYLE_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.I | re.S)
_BODY_RE = re.compile(r"<body\b[^>]*>(.*?)</body>", re.I | re.S)
_HEAD_RE = re.compile(r"<head\b[^>]*>.*?</head>", re.I | re.S)
_CREDIT_RE = re.compile(r'class\s*=\s*["\'][^"\']*\bcredit\b', re.I)


def resolve_favicon(spec: str, title: str) -> str:
    """Resolve a --favicon spec to a hex colour.

    Accepts a brand colour name, a literal hex, `auto`, or `random`.

    `auto` is the default and is deliberately NOT random: it hashes the page
    title, so one page keeps one icon across rebuilds while different pages get
    different ones. A genuinely random pick would give the same page a new tab
    icon on every build, which is how users lose track of a tab — and it would
    make the build non-reproducible, which these scripts otherwise avoid (the
    same reason none of them call datetime.now()). Pass `random` if you want the
    dice anyway.
    """
    if spec in FAVICON_COLOURS:
        return FAVICON_COLOURS[spec]
    if _HEX_RE.match(spec):
        return spec.upper()
    if spec == "random":
        return FAVICON_COLOURS[random.choice(_SHUFFLE_POOL)]
    if spec == "auto":
        digest = hashlib.sha256(title.encode("utf-8")).digest()
        return FAVICON_COLOURS[_SHUFFLE_POOL[digest[0] % len(_SHUFFLE_POOL)]]
    raise ValueError(
        f"unknown --favicon {spec!r}: use a hex, 'auto', 'random', or one of "
        + ", ".join(FAVICON_COLOURS)
    )


def build_head(title: str, extra_css: str = "", favicon: str = "auto") -> str:
    """Canonical <head> inner HTML with ersilia.css (and any extra CSS) inlined."""
    css = read_text(asset("ersilia.css"))
    if extra_css.strip():
        css = css + "\n\n/* ---- page-specific styles (retrofit; cascade after theme) ---- */\n" + extra_css
    head = read_text(asset("head.html"))
    # Drop the leading HTML comment block for a clean document.
    head = re.sub(r"^<!--.*?-->\s*", "", head, count=1, flags=re.S)
    # The hex sits inside a data: URI, so its '#' must be percent-encoded.
    colour = resolve_favicon(favicon, title).replace("#", "%23")
    return (head.replace("__TITLE__", _escape(title))
                .replace("__FAVICON__", colour)
                .replace("__STYLE__", css))


def build_footer(source_url: str | None) -> str:
    """Canonical footer; drops the GitHub source line when no URL is given."""
    footer = read_text(asset("footer.html"))
    footer = re.sub(r"^<!--.*?-->\s*", "", footer, count=1, flags=re.S)
    if source_url:
        return footer.replace("__SOURCE_URL__", _escape(source_url))
    # Remove the whole "Source code" anchor line.
    return re.sub(r"\n\s*<a href=\"__SOURCE_URL__\".*?</a>", "", footer, flags=re.S)


def scaffold(archetype: str, title: str, eyebrow: str, lede: str) -> str:
    """Body fragment for `new` mode, from the archetype starter."""
    body = read_text(asset(f"starter-{archetype}.html"))
    body = re.sub(r"^<!--.*?-->\s*", "", body, count=1, flags=re.S)
    return (
        body.replace("__TITLE__", _escape(title))
        .replace("__EYEBROW__", _escape(eyebrow))
        .replace("__LEDE__", _escape(lede))
    )


def retrofit(src_html: str) -> tuple[str, str, list[tuple[str, str]]]:
    """Return (body_inner, page_styles, external_refs) extracted from an existing page."""
    styles = "\n".join(m.strip() for m in _STYLE_RE.findall(src_html))
    body_match = _BODY_RE.search(src_html)
    if body_match:
        body = body_match.group(1)
    else:
        # No <body>: treat the whole thing as a fragment, minus any <head> and <style>.
        body = _HEAD_RE.sub("", src_html)
        body = _STYLE_RE.sub("", body)
        body = re.sub(r"</?(?:html|body)\b[^>]*>", "", body, flags=re.I)
    # The page's <style> is hoisted into <head>; strip it from the body copy.
    body = _STYLE_RE.sub("", body)
    refs = parse_html(src_html).external_refs
    return body.strip(), styles, refs


def assemble(head_inner: str, body_inner: str, footer_html: str) -> str:
    """Wrap the pieces into one self-contained document."""
    if footer_html and not _CREDIT_RE.search(body_inner):
        body_inner = body_inner.rstrip() + "\n" + footer_html
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        + head_inner.strip()
        + "\n</head>\n<body>\n"
        + body_inner.strip()
        + "\n</body>\n</html>\n"
    )


def _escape(s: str) -> str:
    """Minimal HTML-attribute/text escaping for the tokens we inject."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("html_file", nargs="?", help="existing HTML file (required for retrofit)")
    p.add_argument("--mode", choices=("new", "retrofit"), help="default: retrofit if a file is given, else new")
    p.add_argument("--archetype", choices=ARCHETYPES, default="document", help="new mode only (default: document)")
    p.add_argument("--out", help="output path (default: stdout)")
    p.add_argument("--title", default="Ersilia", help="page title / wordmark")
    p.add_argument("--eyebrow", help="mono eyebrow label (default: per archetype)")
    p.add_argument("--lede", default="One-sentence summary of what this page shows.", help="new mode lede")
    p.add_argument("--source-url", help="GitHub source URL for the footer")
    p.add_argument(
        "--favicon", default="auto", metavar="COLOUR",
        help="favicon disc colour: a brand name (" + ", ".join(FAVICON_COLOURS) + "), a hex, "
             "'random', or 'auto' (default: derived from the title, so a page keeps one icon)",
    )
    args = p.parse_args(argv)

    mode = args.mode or ("retrofit" if args.html_file else "new")

    try:
        resolve_favicon(args.favicon, args.title)
    except ValueError as exc:
        p.error(str(exc))

    if mode == "retrofit":
        if not args.html_file:
            p.error("retrofit mode needs an HTML file argument")
        src = read_text(args.html_file)
        if not src.strip():
            p.error(f"could not read {args.html_file}")
        body, page_styles, _ = retrofit(src)
        head = build_head(args.title, extra_css=page_styles, favicon=args.favicon)
    else:
        eyebrow = args.eyebrow or _EYEBROW_DEFAULT[args.archetype]
        body = scaffold(args.archetype, args.title, eyebrow, args.lede)
        head = build_head(args.title, favicon=args.favicon)

    footer = build_footer(args.source_url)
    doc = assemble(head, body, footer)

    # Warn about anything that survived into the OUTPUT and would break the Artifact CSP
    # (external CSS/font <link>s are dropped during retrofit; external <img>/<script> are kept).
    surviving = parse_html(doc).external_refs
    for kind, url in surviving:
        warn(f"external {kind} in output (breaks under Artifact CSP — inline it or use a data: URI): {url}")
    if surviving:
        warn(f"{len(surviving)} external reference(s) remain; the page is NOT self-contained until they are inlined")

    if args.out:
        Path(args.out).expanduser().resolve().write_text(doc, encoding="utf-8")
        print(f"wrote {args.out} ({len(doc):,} bytes, mode={mode})", file=sys.stderr)
    else:
        sys.stdout.write(doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
