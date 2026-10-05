"""Shared helpers for the org-context scripts.

Standard library only. Every script works in ``WORK_DIR``: ``targets.json`` lists the
files under review with their metadata, ``files/<id>.md`` holds their text, and the
check, fact and judgement outputs sit next to them.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

WORK_DIR = "/tmp/org_context"
SKILL_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SKILL_DIR.parent.parent  # the ersilia-skills checkout
REFS = SKILL_DIR / "references"

SEVERITIES = ("fix", "trim", "consider")
MARKERS = {"fix": "🔴", "trim": "🟡", "consider": "⚪"}

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
URL_RE = re.compile(r"https?://[^\s)\]>`\"']+")


def warn(message: str) -> None:
    """Print a warning to stderr."""
    print(f"WARNING: {message}", file=sys.stderr, flush=True)


def die(message: str) -> None:
    """Print an error to stderr and exit 1."""
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


def read_json(path: str | Path) -> Any:
    """Read JSON from ``path``; return None if the file is missing or empty."""
    p = Path(path).expanduser()
    if not p.exists() or p.stat().st_size == 0:
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    """Write ``data`` as indented JSON, creating parent directories."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def sha256(text: str) -> str:
    """Return the hex SHA-256 of ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_gh(args: list[str]) -> tuple[str | None, str]:
    """Run ``gh <args>``. Returns (stdout or None, error message)."""
    if not shutil.which("gh"):
        return None, "gh CLI is not on PATH"
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout).strip()[:500]
    return proc.stdout, ""


def load_work(work: str | Path) -> tuple[list[dict], dict[str, str]]:
    """Return (targets, {target id: text}) from a work directory."""
    work = Path(work)
    targets = read_json(work / "targets.json")
    if not targets:
        die(f"{work}/targets.json is missing: run fetch_targets.py first")
    texts = {
        t["id"]: (work / "files" / f"{t['id']}.md").read_text(encoding="utf-8")
        for t in targets
    }
    return targets, texts


def deep_merge(base: dict, over: dict) -> dict:
    """Return ``base`` updated recursively with ``over`` (dicts merge, others replace)."""
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def prose_lines(text: str) -> list[tuple[int, str]]:
    """Return (1-based line number, line) for every line outside fenced code blocks."""
    out, in_fence = [], False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append((n, line))
    return out


def sections(text: str) -> list[dict]:
    """Split ``text`` into heading-delimited sections.

    Each section is ``{"level", "title", "start", "end"}`` with 1-based inclusive line
    numbers. Text before the first heading is a level-0 section titled ``(preamble)``.
    Headings inside fenced code are ignored.
    """
    lines = text.splitlines()
    heads = []
    for n, line in prose_lines(text):
        m = HEADING_RE.match(line)
        if m:
            heads.append((n, len(m.group(1)), m.group(2)))
    out = []
    if not heads or heads[0][0] > 1:
        out.append(
            {
                "level": 0,
                "title": "(preamble)",
                "start": 1,
                "end": heads[0][0] - 1 if heads else len(lines),
            }
        )
    for i, (n, level, title) in enumerate(heads):
        end = len(lines)
        for m, lv, _ in heads[i + 1 :]:
            if lv <= level:
                end = m - 1
                break
        out.append({"level": level, "title": title, "start": n, "end": end})
    return out


def units(text: str) -> list[dict]:
    """Return the prose units of ``text``: each bullet item and each plain paragraph.

    A unit is ``{"line", "text", "lead"}``; ``lead`` is the bold lead-in of a bullet
    such as ``**Ask, don't assume.**``, or ``""``.
    """
    out, buf, start = [], [], 0

    def flush() -> None:
        if buf:
            joined = " ".join(s.strip() for s in buf)
            lead = re.match(r"^\*\*(.+?)\*\*", joined)
            out.append(
                {"line": start, "text": joined, "lead": lead.group(1) if lead else ""}
            )
            buf.clear()

    for n, line in prose_lines(text):
        stripped = line.strip()
        bullet = re.match(r"^\s*(?:[-*+]|\d+\.)\s+(.*)$", line)
        if not stripped or HEADING_RE.match(line) or stripped.startswith("|"):
            flush()
        elif bullet:
            flush()
            buf.append(bullet.group(1))
            start = n
        else:
            if not buf:
                start = n
            buf.append(stripped)
    flush()
    return out


STOPWORDS = frozenset(
    """a an and are as at be before by do does for from has have if in into is it its
    not of on or so than that the then there these this to too use when which while
    with without you your any all only also can must should every each""".split()
)


def content_words(text: str) -> set[str]:
    """Lowercased content words of ``text``, contractions expanded, crude plural strip.

    Link targets and bare URLs are dropped first: ``github.com/ersilia-os`` appears in
    most lines and would make unrelated instructions look alike.
    """
    text = LINK_RE.sub(r"\1", text)
    text = URL_RE.sub(" ", text)
    text = text.lower().replace("’", "'").replace("n't", " not")
    words = re.findall(r"[a-z0-9][a-z0-9_-]*", text)
    out = set()
    for w in words:
        if w in STOPWORDS or len(w) < 3:
            continue
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out
