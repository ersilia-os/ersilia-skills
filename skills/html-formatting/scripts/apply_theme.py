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

Either mode takes the social-preview flags, for a page that will be HOSTED at a public URL
(--description --url --og-image --og-image-alt). They add the Open Graph / twitter card tags
that LinkedIn and Slack read; without them the head carries no social metadata, which is the
right default for an Artifact. Generate the image with make_og_image.py.

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
_ABS_URL_RE = re.compile(r"^https?://", re.I)
_SIZE_RE = re.compile(r"^(\d+)[x×](\d+)$")

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


def absolute_url(url: str, what: str) -> str:
    """Reject a relative or data: URL for a tag that a social crawler must resolve.

    LinkedIn, Slack and X fetch og:image from their own servers with no page
    context, so a relative path or a data: URI resolves to nothing and the card
    silently falls back to a bare grey box. Failing the build is far kinder than
    shipping a preview that only looks broken once it is posted.
    """
    if not _ABS_URL_RE.match(url):
        raise ValueError(
            f"{what} must be an absolute http(s) URL, got {url!r} — social crawlers "
            "fetch it without page context, so a relative path or data: URI cannot work"
        )
    return url


def build_social(
    title: str,
    description: str | None = None,
    url: str | None = None,
    image: str | None = None,
    image_alt: str | None = None,
    size: tuple[int, int] = (1200, 630),
) -> str:
    """The description / canonical / Open Graph block, or "" when nothing applies.

    Split from build_head because it is the one part of the head that is NOT
    universal: a hosted page wants it, an Artifact cannot use it. Passing only
    --description yields the plain <meta name=description> and nothing else.

    og:* is what LinkedIn reads (it ignores twitter:*); the twitter:* pair costs
    four lines and covers X, Slack and WhatsApp, which prefer them when present.
    """
    lines: list[str] = []
    if description:
        lines.append(f'<meta name="description" content="{_escape(description)}">')
    if url:
        lines.append(f'<link rel="canonical" href="{_escape(url)}">')
    if url or image:
        lines.append('<meta property="og:type" content="website">')
        lines.append('<meta property="og:site_name" content="Ersilia">')
        lines.append(f'<meta property="og:title" content="{_escape(title)}">')
        if description:
            lines.append(f'<meta property="og:description" content="{_escape(description)}">')
        if url:
            lines.append(f'<meta property="og:url" content="{_escape(url)}">')
        if image:
            w, h = size
            lines.append(f'<meta property="og:image" content="{_escape(image)}">')
            lines.append(f'<meta property="og:image:width" content="{w}">')
            lines.append(f'<meta property="og:image:height" content="{h}">')
            if image_alt:
                lines.append(f'<meta property="og:image:alt" content="{_escape(image_alt)}">')
        card = "summary_large_image" if image else "summary"
        lines.append(f'<meta name="twitter:card" content="{card}">')
        lines.append(f'<meta name="twitter:title" content="{_escape(title)}">')
        if description:
            lines.append(f'<meta name="twitter:description" content="{_escape(description)}">')
        if image:
            lines.append(f'<meta name="twitter:image" content="{_escape(image)}">')
    return "\n".join(lines)


def build_head(title: str, extra_css: str = "", favicon: str = "auto", social: str = "") -> str:
    """Canonical <head> inner HTML with ersilia.css (and any extra CSS) inlined."""
    css = read_text(asset("ersilia.css"))
    if extra_css.strip():
        css = css + "\n\n/* ---- page-specific styles (retrofit; cascade after theme) ---- */\n" + extra_css
    head = read_text(asset("head.html"))
    # Drop the leading HTML comment block for a clean document.
    head = re.sub(r"^<!--.*?-->\s*", "", head, count=1, flags=re.S)
    # The hex sits inside a data: URI, so its '#' must be percent-encoded.
    colour = resolve_favicon(favicon, title).replace("#", "%23")
    # Consume the token's own newline so an empty block leaves no blank line.
    head = head.replace("__SOCIAL__\n", social + "\n" if social.strip() else "")
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
    # Social preview — hosted pages only; an Artifact has no public URL to point at.
    p.add_argument("--description", help="one-sentence <meta description> / og:description")
    p.add_argument("--url", metavar="ABS_URL", help="canonical page URL (absolute); enables og:url")
    p.add_argument(
        "--og-image", metavar="ABS_URL",
        help="absolute URL of the 1200x630 preview image (see make_og_image.py); enables the card",
    )
    p.add_argument("--og-image-alt", help="alt text for the preview image")
    p.add_argument(
        "--og-image-size", default="1200x630", metavar="WxH",
        help="declared preview image size (default: 1200x630)",
    )
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

    size_match = _SIZE_RE.match(args.og_image_size)
    if not size_match:
        p.error(f"--og-image-size must look like 1200x630, got {args.og_image_size!r}")
    try:
        for value, what in ((args.url, "--url"), (args.og_image, "--og-image")):
            if value:
                absolute_url(value, what)
    except ValueError as exc:
        p.error(str(exc))
    social = build_social(
        args.title,
        description=args.description,
        url=args.url,
        image=args.og_image,
        image_alt=args.og_image_alt,
        size=(int(size_match.group(1)), int(size_match.group(2))),
    )

    if mode == "retrofit":
        if not args.html_file:
            p.error("retrofit mode needs an HTML file argument")
        src = read_text(args.html_file)
        if not src.strip():
            p.error(f"could not read {args.html_file}")
        body, page_styles, _ = retrofit(src)
        head = build_head(args.title, extra_css=page_styles, favicon=args.favicon, social=social)
    else:
        eyebrow = args.eyebrow or _EYEBROW_DEFAULT[args.archetype]
        body = scaffold(args.archetype, args.title, eyebrow, args.lede)
        head = build_head(args.title, favicon=args.favicon, social=social)

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
