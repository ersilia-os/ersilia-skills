"""Shared utilities for the html-formatting skill scripts.

Standard library only — no lxml/bs4. HTML is parsed with `html.parser`, which is
enough for the mechanical jobs here (locate <head>/<body>, pull <style> blocks and
inline style="" attributes, enumerate colours / fonts / external refs / headings).
The findings model is the same shape as `repository-auditing/scripts/_common.py`
(copy-and-adapt is the repo convention — there is no shared lib/), so `check_html.py`
reports read like an AUDIT.md.
"""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------------------


def warn(msg: str) -> None:
    """Log a warning to stderr; scripts call this on partial trouble."""
    print(f"WARNING: {msg}", file=sys.stderr, flush=True)


def die(msg: str, code: int = 2) -> None:
    """Print an error to stderr and exit with `code`."""
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def read_text(path: str | Path) -> str:
    """Read a text file, tolerating encoding problems. Returns '' if unreadable."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return ""


# --------------------------------------------------------------------------------------
# Findings model  (mirrors repository-auditing so reports look the same)
# --------------------------------------------------------------------------------------

SEVERITIES = ("Blocker", "Should-fix", "Nice-to-have")
TIERS = ("T0", "T1", "T2")


def finding(
    check_id: str,
    tier: str,
    severity: str,
    summary: str,
    fix: str,
    detail: str | None = None,
    confidence: str = "high",
) -> dict:
    """Build one finding record. `check_id` is a stable id from references/checks.md."""
    if tier not in TIERS:
        raise ValueError(f"bad tier {tier!r}")
    if severity not in SEVERITIES:
        raise ValueError(f"bad severity {severity!r}")
    out = {
        "id": check_id,
        "tier": tier,
        "severity": severity,
        "summary": summary,
        "fix": fix,
        "confidence": confidence,
    }
    if detail:
        out["detail"] = detail
    return out


def skipped(check_id: str, reason: str) -> dict:
    """Record a check that could not run, so the report can say so explicitly."""
    return {"id": check_id, "reason": reason}


def write_json(path: str, data: Any) -> None:
    """Write `data` as JSON to `path`, creating parent dirs as needed."""
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------------------
# Skill-relative paths
# --------------------------------------------------------------------------------------

SKILL_DIR = Path(__file__).resolve().parent.parent


def asset(name: str) -> Path:
    """Absolute path to a file in the skill's assets/ directory."""
    return SKILL_DIR / "assets" / name


def reference(name: str) -> Path:
    """Absolute path to a file in the skill's references/ directory."""
    return SKILL_DIR / "references" / name


# --------------------------------------------------------------------------------------
# The canonical palette & type tokens (parsed once from assets/ersilia.css)
# --------------------------------------------------------------------------------------

# Hex colours that are legitimately "Ersilia" even when written as a literal rather
# than a var(). Sourced from assets/ersilia.css :root plus the brand red. Anything
# outside this set (and not a var()) is flagged by the colour check.
BRAND_HEX = {
    # brand
    "#50285a", "#aa96fa", "#bee6b4", "#8cc8fa", "#fad782", "#dca0dc", "#faa08c", "#d2d2d0",
    # data / axis hues
    "#e63946", "#f4845f", "#fcbf49", "#6bbf59", "#2ec4b6", "#457b9d", "#6c5ce7", "#b05cc8",
    "#e91e8c", "#a0a0a0",
    # neutrals / surfaces
    "#2c3e50", "#6b6675", "#9a93a6", "#fafafc", "#ffffff", "#f4f4f8", "#e6e6ee",
    # semantic
    "#3f9d6b", "#c98a1e", "#d9534f",
    # Ersilia red (brand accent; was the old favicon's centre dot) + plain
    # white/black shorthands that are unavoidable
    "#d8412f", "#fff", "#000",
}

# Substrings that mark a NON-Ersilia font stack (the GitHub / generic defaults).
FOREIGN_FONT_HINTS = ("segoe ui", "-apple-system", "helvetica", "arial", "roboto")
# The two Ersilia families that should appear if the page sets a font at all.
ERSILIA_FONT_HINTS = ("inter", "ui-monospace", "sfmono")

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def hexes_in(text: str) -> list[str]:
    """All hex colour literals in a blob of CSS/markup, lower-cased."""
    return [h.lower() for h in HEX_RE.findall(text or "")]


def non_brand_hexes(text: str) -> list[str]:
    """Hex literals that are not in the canonical palette (order-preserving, unique)."""
    seen: dict[str, None] = {}
    for h in hexes_in(text):
        if h not in BRAND_HEX and h not in seen:
            seen[h] = None
    return list(seen)


# --------------------------------------------------------------------------------------
# A tiny HTML model
# --------------------------------------------------------------------------------------


class _Doc(HTMLParser):
    """Collects the few structural facts the checks and the assembler need."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.has_head = False
        self.has_body = False
        self.has_doctype = False
        self.title: str | None = None
        self.style_blocks: list[str] = []
        self.inline_styles: list[str] = []
        self.external_refs: list[tuple[str, str]] = []  # (kind, url)
        self.headings: list[tuple[int, str]] = []  # (level, text)
        self.has_favicon = False
        # <meta> keyed by its name= or property=, so a check can ask for og:image or
        # description without re-parsing. Never a source of external_refs: a crawler
        # fetches og:image, the browser does not, so it cannot break self-containment.
        self.metas: dict[str, str] = {}
        self.emoji_headings: list[str] = []
        self.text_len = 0
        self._in_style = False
        self._in_title = False
        self._cur_heading: int | None = None
        self._heading_buf: list[str] = []

    # -- element boundaries ------------------------------------------------
    def handle_decl(self, decl: str) -> None:
        if decl.lower().startswith("doctype"):
            self.has_doctype = True

    def handle_starttag(self, tag: str, attrs_list) -> None:
        attrs = {k.lower(): (v or "") for k, v in attrs_list}
        if tag == "head":
            self.has_head = True
        elif tag == "body":
            self.has_body = True
        elif tag == "style":
            self._in_style = True
        elif tag == "title":
            self._in_title = True
            self.title = ""
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._cur_heading = int(tag[1])
            self._heading_buf = []
        if "style" in attrs and attrs["style"].strip():
            self.inline_styles.append(attrs["style"])
        if tag == "meta":
            key = (attrs.get("name") or attrs.get("property") or "").strip().lower()
            if key:
                self.metas[key] = attrs.get("content", "")
        if tag == "link":
            rel = attrs.get("rel", "").lower()
            href = attrs.get("href", "")
            if "icon" in rel:
                self.has_favicon = True
            if "stylesheet" in rel and _is_external(href):
                self.external_refs.append(("stylesheet", href))
            if href.startswith("https://fonts.googleapis") or "font" in rel:
                self.external_refs.append(("font", href))
        if tag == "script" and _is_external(attrs.get("src", "")):
            self.external_refs.append(("script", attrs["src"]))
        if tag == "img" and _is_external(attrs.get("src", "")):
            self.external_refs.append(("img", attrs["src"]))

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self._in_style = False
        elif tag == "title":
            self._in_title = False
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if self._cur_heading is not None:
                txt = " ".join(" ".join(self._heading_buf).split())
                if txt:
                    self.headings.append((self._cur_heading, txt))
                    if _EMOJI_RE.search(txt):
                        self.emoji_headings.append(txt)
            self._cur_heading = None
            self._heading_buf = []

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self.style_blocks.append(data)
            return
        if self._in_title and self.title is not None:
            self.title += data
        if self._cur_heading is not None and data.strip():
            self._heading_buf.append(data.strip())
        if data.strip():
            self.text_len += len(data.strip())


_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⌀-⏿]"
)


def _is_external(url: str) -> bool:
    """True if a URL points off-document (http(s)/protocol-relative), not data:/#/relative."""
    u = (url or "").strip().lower()
    return u.startswith(("http://", "https://", "//"))


def parse_html(text: str) -> _Doc:
    """Parse an HTML string into the small structural model above."""
    doc = _Doc()
    try:
        doc.feed(text)
    except Exception as e:  # html.parser is lenient, but never let it kill the run
        warn(f"HTML parse hiccup (continuing): {e}")
    return doc


def all_css(doc: _Doc) -> str:
    """Every scrap of CSS in the doc: <style> blocks + inline style attributes."""
    return "\n".join(doc.style_blocks + doc.inline_styles)
