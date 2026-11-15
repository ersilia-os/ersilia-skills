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

from _common import WORK_DIR, die, unligature, warn, words, write_json

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
    if NUM_PREFIX.match(s) and len(s.split()) <= 8 and not s.endswith("."):
        rest = NUM_PREFIX.sub("", s).strip()
        if (
            len(rest) >= 3
            and rest[0].isupper()
            and not re.search(r"\d", rest)
            and rest[-1:].isalpha()
        ):
            return rest
    return None


def clean_block(text: str) -> str:
    """Join hyphenated line breaks and unwrap lines within one paragraph."""
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", unligature(text))
    return re.sub(r"\s*\n\s*", " ", text).strip()


def _prose(text: str) -> bool:
    """Whether hidden text reads as words (an instruction), not a stamp or digits."""
    t = re.sub(r"https?://\S+|\S+@\S+", " ", text)
    return len(re.findall(r"[A-Za-z]{3,}", t)) >= 3


def _figure_like(block: str) -> bool:
    """Labels and axis ticks from figures: few words, or mostly non-alphabetic tokens."""
    toks = block.split()
    if not toks:
        return True
    alpha = sum(1 for t in toks if re.search(r"[A-Za-z]{2,}", t))
    return len(toks) <= 3 or alpha / len(toks) < 0.5


def _on_colour(page, box, cache: dict) -> bool:
    """Whether the rendered page under ``box`` is mostly non-white (white text on a figure)."""
    if "pix" not in cache:
        cache["pix"] = page.get_pixmap(dpi=60)
    pix, k = cache["pix"], 60 / 72
    x0, y0 = max(0, int(box.x0 * k)), max(0, int(box.y0 * k))
    x1, y1 = min(pix.width - 1, int(box.x1 * k)), min(pix.height - 1, int(box.y1 * k))
    total = dark = 0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            total += 1
            if min(pix.pixel(x, y)[:3]) < 235:
                dark += 1
    return total > 0 and dark / total > 0.3


def from_pdf(path: Path) -> tuple[list[tuple[int, str]], list[dict], dict]:
    """(page, paragraph) blocks, hidden text and metadata from a PDF.

    Text is rebuilt from word boxes, so PDFs that position words without space characters
    still give spaced text. Text counts as hidden when it is white over a white page (not
    white lettering on a coloured figure), under 2 pt, or off the page, and only when it
    reads as words: publisher stamps and stray digits are ignored.
    """
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
        backgrounds = [
            fitz.Rect(dr["rect"])
            for dr in page.get_drawings()
            if dr.get("fill") is not None and min(dr["fill"]) < 0.94
        ] + [fitz.Rect(i["bbox"]) for i in page.get_image_info()]
        hidden_boxes = []
        cache: dict = {}
        for b in page.get_text("dict").get("blocks", []):
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for sp in line.get("spans", []):
                    t = sp.get("text", "")
                    if not t.strip():
                        continue
                    box = fitz.Rect(sp["bbox"])
                    color = sp.get("color", 0)
                    r, g, bl = (color >> 16) & 255, (color >> 8) & 255, color & 255
                    why = None
                    if min(r, g, bl) >= 245:
                        centre = fitz.Point(
                            (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
                        )
                        if not any(
                            centre in bg for bg in backgrounds
                        ) and not _on_colour(page, box, cache):
                            why = "white or near-white text"
                    elif sp.get("size", 10) < 2:
                        why = f"tiny text ({sp.get('size', 0):.1f} pt)"
                    elif (
                        box.x1 < rect.x0
                        or box.x0 > rect.x1
                        or box.y1 < rect.y0
                        or box.y0 > rect.y1
                    ):
                        why = "text placed outside the page"
                    if why:
                        hidden.append({"page": pno, "text": t.strip(), "why": why})
                        hidden_boxes.append(box)
        lines: dict[tuple[int, int], list[str]] = {}
        order: list[tuple[int, int]] = []
        for x0, y0, x1, y1, w, bno, lno, _ in page.get_text("words", sort=False):
            centre = fitz.Point((x0 + x1) / 2, (y0 + y1) / 2)
            if any(centre in hb for hb in hidden_boxes):
                continue
            key = (bno, lno)
            if key not in lines:
                lines[key] = []
                order.append(key)
            lines[key].append(w)
        by_block: dict[int, list[str]] = {}
        border: list[int] = []
        for bno, lno in order:
            if bno not in by_block:
                by_block[bno] = []
                border.append(bno)
            by_block[bno].append(" ".join(lines[(bno, lno)]))
        for bno in border:
            raw = "\n".join(by_block[bno])
            first, _, rest = raw.partition("\n")
            if rest and is_heading(first):
                blocks.append((pno, first.strip()))
                raw = rest
            if is_heading(raw):
                blocks.append((pno, raw.strip()))
            elif not _figure_like(raw):
                blocks.append((pno, clean_block(raw)))
    meta = {k: v for k, v in (doc.metadata or {}).items() if v}
    merged: list[dict] = []
    for h in hidden:
        if merged and merged[-1]["page"] == h["page"] and merged[-1]["why"] == h["why"]:
            merged[-1]["text"] += " " + h["text"]
        else:
            merged.append(dict(h))
    return blocks, [h for h in merged if _prose(h["text"])], meta


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
