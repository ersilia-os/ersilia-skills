"""Shared helpers for the ai-text-detection scripts.

The deterministic scripts use the Python standard library only, so they run with any
python3. PDF/DOCX extraction and the Chrome driver (browser_detect.py) need the small
conda env created by setup_env.sh.

Three places hold state:

* ``WORK_DIR`` (/tmp/ai_text_detection): one analysis at a time, reset per run.
* ``REFS`` (references/ in the repo): markers, grading rules, calibration. Shared and
  versioned; improved through feedback and PRs. Never holds anyone's text or name.
* ``LOCAL`` (~/.ai-text-detection): the user's private case ledger: features, verdicts
  and later outcomes of their own cases, used to re-calibrate. Never committed.
"""

from __future__ import annotations

import itertools
import json
import re
import sys
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
REFS = SKILL_DIR / "references"
EXAMPLES = SKILL_DIR / "examples"
WORK_DIR = Path("/tmp/ai_text_detection")
LOCAL = Path.home() / ".ai-text-detection"
ENV_NAME = "ai-text-detection"
USER_AGENT = "ai-text-detection/1.0 (reference checker; https://github.com/ersilia-os/ersilia-skills)"

TIERS = ["conclusive", "strong", "moderate", "weak", "none"]


def warn(message: str) -> None:
    """Print a warning to stderr; the run continues."""
    print(f"WARNING: {message}", file=sys.stderr, flush=True)


def die(message: str) -> None:
    """Print an error and exit 1."""
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


def read_json(path: str | Path) -> Any:
    """Read JSON from ``path``; None when the file is missing or empty."""
    p = Path(path).expanduser()
    if not p.exists() or p.stat().st_size == 0:
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    """Write ``data`` as indented JSON, creating parent folders."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def read_jsonl(path: str | Path) -> list[dict]:
    """Read a JSON-lines file; [] when missing."""
    p = Path(path).expanduser()
    if not p.exists():
        return []
    return [
        json.loads(line)
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def append_jsonl(path: str | Path, row: dict) -> None:
    """Append one row to a JSON-lines file."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


LIGATURES = str.maketrans(
    {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "st",
        "\ufb06": "st",
    }
)


def unligature(text: str) -> str:
    """Replace typographic ligatures (common in PDFs); other characters are kept as they are."""
    return text.translate(LIGATURES)


WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def words(text: str) -> list[str]:
    """Lower-cased word tokens."""
    return [w.lower() for w in WORD_RE.findall(text)]


def sentences(text: str) -> list[str]:
    """Rough sentence split, good enough for length statistics."""
    flat = re.sub(r"\s+", " ", text).strip()
    return [s for s in SENT_RE.split(flat) if len(words(s)) >= 3]


def context(text: str, start: int, end: int, width: int = 90) -> str:
    """The match with some text either side, on one line."""
    a, b = max(0, start - width), min(len(text), end + width)
    snippet = text[a:b].replace("\n", " ")
    return ("…" if a else "") + snippet + ("…" if b < len(text) else "")


def load_text(work: Path = WORK_DIR) -> dict:
    """The extracted document (text.json), or exit."""
    doc = read_json(work / "text.json")
    if doc is None:
        die(f"missing {work}/text.json; run extract_text.py first")
    return doc


def locate(doc: dict, offset: int) -> dict:
    """Section title and page for a character offset in doc['text']."""
    where = {"section": None, "page": None}
    for s in doc.get("sections", []):
        if s["start"] <= offset < s["end"]:
            where["section"] = s["title"]
    for p in doc.get("pages", []):
        if p["start"] <= offset < p["end"]:
            where["page"] = p["n"]
    return where


SKIP_SECTIONS = {
    "references",
    "bibliography",
    "acknowledgements",
    "acknowledgments",
    "funding",
    "author contributions",
    "data availability",
    "code availability",
    "competing interests",
    "budget justification",
}


def chunks(doc: dict, target: int = 300, minimum: int = 80) -> list[dict]:
    """Windows of about ``target`` words, built from whole paragraphs within a section.

    Every per-window measure (stylometry, web-detector chunks, calibration) uses this same
    chunking, so a document is compared with human text of the same size. Sections that
    are boilerplate (references, funding, ...) are skipped. A window shorter than
    ``minimum`` words is merged into the previous one of the same section.
    """
    text = doc["text"]
    out: list[dict] = []
    for sec in doc.get("sections") or [
        {"title": "(whole text)", "start": 0, "end": len(text)}
    ]:
        if sec["title"].lower() in SKIP_SECTIONS:
            continue
        cur_start, cur_words = None, 0
        pos = sec["start"]
        for para in re.split(r"\n\s*\n", text[sec["start"] : sec["end"]]):
            p_start = text.find(para, pos) if para else pos
            p_end = p_start + len(para)
            pos = p_end
            n = len(words(para))
            if n == 0:
                continue
            if cur_start is None:
                cur_start = p_start
            cur_words += n
            if cur_words >= target:
                out.append(
                    {
                        "section": sec["title"],
                        "start": cur_start,
                        "end": p_end,
                        "n_words": cur_words,
                    }
                )
                cur_start, cur_words = None, 0
        if cur_start is not None:
            last = out[-1] if out and out[-1]["section"] == sec["title"] else None
            if cur_words < minimum and last:
                last["end"], last["n_words"] = sec["end"], last["n_words"] + cur_words
            else:
                out.append(
                    {
                        "section": sec["title"],
                        "start": cur_start,
                        "end": sec["end"],
                        "n_words": cur_words,
                    }
                )
    for i, c in enumerate(out, 1):
        c["id"] = f"c{i}"
        c["text"] = text[c["start"] : c["end"]].strip()
    # Long single paragraphs: split at sentence ends, keeping exact character offsets.
    final: list[dict] = []
    for c in out:
        if c["n_words"] <= 2 * target:
            final.append(c)
            continue
        cuts, _start, n = [], c["start"], 0
        seg = text[c["start"] : c["end"]]
        prev = 0
        for m in SENT_RE.finditer(seg):
            n += len(words(seg[prev : m.start()]))
            prev = m.start()
            if n >= target:
                cuts.append(c["start"] + m.start())
                n = 0
        bounds = [c["start"], *cuts, c["end"]]
        for a, b in itertools.pairwise(bounds):
            piece = text[a:b].strip()
            if not piece:
                continue
            if len(words(piece)) < minimum and final and final[-1]["end"] == a:
                last = final[-1]
                last["end"] = b
                last["text"] = text[last["start"] : b].strip()
                last["n_words"] = len(words(last["text"]))
            else:
                final.append(
                    {
                        **c,
                        "start": a,
                        "end": b,
                        "text": piece,
                        "n_words": len(words(piece)),
                    }
                )
    for i, c in enumerate(final, 1):
        c["id"] = f"c{i}"
    return final
