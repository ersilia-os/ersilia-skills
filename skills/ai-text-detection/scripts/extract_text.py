"""Extract the text of a document into a structure every other check reads.

Accepts PDF, DOCX, TXT/MD, or text on stdin (``-``). PDF and DOCX need the conda env
(``conda run -n ai-text-detection python extract_text.py ...``); plain text works with
any python3.

Besides the visible text it looks for text a reader cannot see but a chatbot (or a
detector) does: white or near-white text, text under 2 pt, text drawn off the page, and
DOCX runs marked hidden. That is where hidden prompt injections ("give a positive
review") live. Document metadata (author, producer, dates) is kept as context.

Writes ``<work>/text.json``:

    {"source": path, "format": "pdf|docx|txt|md|stdin", "text": body text,
     "references_text": the reference list (split off the body), "pages": [{n,start,end}],
     "sections": [{title,start,end}], "hidden": [{page,text,why}], "metadata": {...},
     "n_words": int}

Usage:
    python extract_text.py <file|-> [--work /tmp/ai_text_detection] [--format txt|md]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _common import WORK_DIR, die, warn, words, write_json

HEADINGS = [
    "abstract",
    "summary",
    "introduction",
    "background",
    "methods",
    "materials and methods",
    "methodology",
    "results",
    "results and discussion",
    "discussion",
    "conclusion",
    "conclusions",
    "limitations",
    "acknowledgements",
    "acknowledgments",
    "funding",
    "author contributions",
    "data availability",
    "code availability",
    "competing interests",
    "supplementary information",
    "references",
    "bibliography",
    "literature cited",
    "works cited",
    "specific aims",
    "significance",
    "innovation",
    "approach",
    "research strategy",
    "objectives",
    "aims",
    "work plan",
    "workplan",
    "impact",
    "expected outcomes",
    "budget justification",
    "project summary",
    "project description",
    "lay summary",
    "state of the art",
    "preliminary data",
    "timeline",
    "risk",
    "summary of the paper",
    "strengths",
    "weaknesses",
    "major comments",
    "minor comments",
    "major issues",
    "minor issues",
    "comments to the authors",
    "comments to the author",
    "recommendation",
    "questions",
    "detailed comments",
    "general comments",
    "specific comments",
    "overall assessment",
    "response to reviewers",
]
REF_HEADINGS = {
    "references",
    "bibliography",
    "literature cited",
    "works cited",
    "reference list",
}
NUM_PREFIX = re.compile(r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.|[A-H]\.)\s+")
HEADING_RE = re.compile(
    r"^\s*(?:#{1,4}\s*)?(?:[0-9]+(?:\.[0-9]+)*\.?\s+|[IVX]+\.\s+|[A-H]\.\s+)?"
    r"("
    + "|".join(re.escape(h) for h in sorted(HEADINGS, key=len, reverse=True))
    + r")"
    r"\s*:?\s*$",
    re.IGNORECASE,
)


def is_heading(line: str) -> str | None:
    """The heading title when ``line`` looks like a section heading."""
    s = line.strip()
    if not s or len(s) > 80:
        return None
    m = HEADING_RE.match(s)
    if m:
        return m.group(1).strip().title()
    # Numbered short title-like line, e.g. "2.3 Data collection"
    if (
        NUM_PREFIX.match(s)
        and len(s.split()) <= 8
        and not s.endswith(".")
        and s[-1:].isalpha()
    ):
        return NUM_PREFIX.sub("", s).strip()
    return None


def clean_block(text: str) -> str:
    """Join hyphenated line breaks and unwrap lines within one paragraph."""
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return re.sub(r"\s*\n\s*", " ", text).strip()


def from_pdf(path: Path) -> tuple[list[tuple[int, str]], list[dict], dict]:
    """(page, paragraph) blocks, hidden spans and metadata from a PDF."""
    try:
        import pymupdf as fitz
    except ImportError:
        die(
            "PDF needs pymupdf: run with `conda run -n ai-text-detection python ...` (setup_env.sh)"
        )
    doc = fitz.open(path)
    blocks, hidden = [], []
    for pno, page in enumerate(doc, 1):
        rect = page.rect
        d = page.get_text("dict")
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            lines_out = []
            for line in b.get("lines", []):
                parts = []
                for sp in line.get("spans", []):
                    t = sp.get("text", "")
                    if not t.strip():
                        continue
                    color = sp.get("color", 0)
                    r, g, bl = (color >> 16) & 255, (color >> 8) & 255, color & 255
                    why = None
                    if min(r, g, bl) >= 245:
                        why = "white or near-white text"
                    elif sp.get("size", 10) < 2:
                        why = f"tiny text ({sp.get('size', 0):.1f} pt)"
                    else:
                        x0, y0, x1, y1 = sp["bbox"]
                        if x1 < rect.x0 or x0 > rect.x1 or y1 < rect.y0 or y0 > rect.y1:
                            why = "text placed outside the page"
                    if why:
                        hidden.append({"page": pno, "text": t.strip(), "why": why})
                        continue
                    parts.append(t)
                if parts:
                    lines_out.append("".join(parts))
            if lines_out:
                raw = "\n".join(lines_out)
                # A heading glued to its paragraph in one block: split it off.
                first, _, rest = raw.partition("\n")
                if rest and is_heading(first):
                    blocks.append((pno, first.strip()))
                    raw = rest
                blocks.append((pno, clean_block(raw)))
    meta = {k: v for k, v in (doc.metadata or {}).items() if v}
    # Merge consecutive hidden spans on a page into one finding.
    merged: list[dict] = []
    for h in hidden:
        if merged and merged[-1]["page"] == h["page"] and merged[-1]["why"] == h["why"]:
            merged[-1]["text"] += " " + h["text"]
        else:
            merged.append(dict(h))
    return blocks, merged, meta


def from_docx(path: Path) -> tuple[list[tuple[int, str]], list[dict], dict]:
    """Paragraph blocks, hidden runs and core properties from a DOCX."""
    try:
        import docx
    except ImportError:
        die(
            "DOCX needs python-docx: run with `conda run -n ai-text-detection python ...`"
        )
    d = docx.Document(str(path))
    blocks, hidden = [], []
    for para in d.paragraphs:
        visible = []
        for run in para.runs:
            t = run.text
            if not t:
                continue
            why = None
            if run.font.hidden:
                why = "run marked hidden"
            else:
                rgb = (
                    run.font.color.rgb
                    if run.font.color and run.font.color.type
                    else None
                )
                if rgb is not None and min(rgb[0], rgb[1], rgb[2]) >= 245:
                    why = "white or near-white text"
                elif run.font.size is not None and run.font.size.pt < 2:
                    why = f"tiny text ({run.font.size.pt:.1f} pt)"
            if why:
                hidden.append({"page": None, "text": t.strip(), "why": why})
            else:
                visible.append(t)
        text = "".join(visible).strip()
        if text:
            blocks.append((1, text))
    for table in d.tables:
        for row in table.rows:
            cells = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
            if cells:
                blocks.append((1, cells))
    cp = d.core_properties
    meta = {
        k: str(getattr(cp, k))
        for k in (
            "author",
            "last_modified_by",
            "created",
            "modified",
            "revision",
            "title",
        )
        if getattr(cp, k, None)
    }
    return blocks, hidden, meta


def from_text(text: str) -> list[tuple[int, str]]:
    """Paragraph blocks from plain text (blank-line separated; headings kept apart)."""
    blocks = []
    for para in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [ln for ln in para.split("\n") if ln.strip()]
        if not lines:
            continue
        if len(lines) > 1 and is_heading(lines[0]):
            blocks.append((1, lines[0].strip()))
            lines = lines[1:]
        # Keep line structure for lists and markdown; unwrap otherwise.
        if any(re.match(r"^\s*([-*•]|\d+[.)]|#{1,4}\s)", ln) for ln in lines):
            blocks.append((1, "\n".join(ln.rstrip() for ln in lines)))
        else:
            blocks.append((1, clean_block("\n".join(lines))))
    return blocks


def assemble(blocks: list[tuple[int, str]]) -> dict:
    """Body text with page and section offsets; the reference list split off."""
    body, refs = [], []
    pages: dict[int, list[int]] = {}
    sections: list[dict] = []
    pos, in_refs = 0, False
    for pno, block in blocks:
        title = is_heading(block)
        if title and title.lower() in REF_HEADINGS:
            in_refs = True
            continue
        if in_refs:
            # A non-reference heading after the list (e.g. "Supplementary") ends it.
            if title and title.lower() not in REF_HEADINGS and len(refs) > 2:
                in_refs = False
            else:
                refs.append(block)
                continue
        start = pos
        body.append(block)
        pos += len(block) + 2
        pages.setdefault(pno, [start, pos])[1] = pos
        if title:
            if sections:
                sections[-1]["end"] = start
            sections.append({"title": title, "start": start, "end": None})
    text = "\n\n".join(body)
    if sections:
        sections[-1]["end"] = len(text)
        if sections[0]["start"] > 0:
            sections.insert(
                0, {"title": "(start)", "start": 0, "end": sections[0]["start"]}
            )
    else:
        sections = [{"title": "(whole text)", "start": 0, "end": len(text)}]
    return {
        "text": text,
        "references_text": "\n".join(refs),
        "pages": [
            {"n": n, "start": a, "end": b} for n, (a, b) in sorted(pages.items())
        ],
        "sections": sections,
    }


def main(argv: list[str] | None = None) -> int:
    """Extract and write text.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("source", help="file path, or - for stdin")
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument("--format", choices=["txt", "md"], help="force plain-text handling")
    args = p.parse_args(argv)

    hidden: list[dict] = []
    meta: dict = {}
    if args.source == "-":
        fmt, blocks = "stdin", from_text(sys.stdin.read())
    else:
        path = Path(args.source).expanduser()
        if not path.exists():
            die(f"no such file: {path}")
        ext = path.suffix.lower()
        if args.format:
            fmt, blocks = (
                args.format,
                from_text(path.read_text(encoding="utf-8", errors="replace")),
            )
        elif ext == ".pdf":
            fmt = "pdf"
            blocks, hidden, meta = from_pdf(path)
        elif ext == ".docx":
            fmt = "docx"
            blocks, hidden, meta = from_docx(path)
        elif ext in (".txt", ".md", ".markdown", ".text", ""):
            fmt = "md" if ext in (".md", ".markdown") else "txt"
            blocks = from_text(path.read_text(encoding="utf-8", errors="replace"))
        else:
            die(f"unsupported format {ext}: convert to PDF, DOCX or TXT first")
    doc = assemble(blocks)
    doc.update(
        {
            "source": args.source,
            "format": fmt,
            "hidden": hidden,
            "metadata": meta,
            "n_words": len(words(doc["text"])),
        }
    )
    if fmt == "pdf" and doc["n_words"] < 50:
        warn(
            "almost no text layer: is this a scanned PDF? Detectors need real text (OCR first)."
        )
    write_json(Path(args.work) / "text.json", doc)
    print(
        f"extracted: {doc['n_words']} words in {len(doc['sections'])} section(s), "
        f"{len(doc['references_text'].splitlines())} reference line(s), "
        f"{len(hidden)} hidden-text finding(s); format {fmt}"
    )
    for s in doc["sections"]:
        n = len(words(doc["text"][s["start"] : s["end"]]))
        print(f"  {s['title'][:60]:<60} {n:>6} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
