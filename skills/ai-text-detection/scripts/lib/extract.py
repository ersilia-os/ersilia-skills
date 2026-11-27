"""Read a document into the structure every check uses: body text with section and page
offsets, the reference list split off, hidden text, and metadata (extract_text.py).

``extract`` is the entry point. PDF needs pymupdf and DOCX needs python-docx (the conda
env); plain text needs nothing.

Hidden text is text a reader cannot see but a chatbot (or a detector) does: white or
near-white text, text under 2 pt, text drawn off the page, and DOCX runs marked hidden.
That is where hidden prompt injections ("give a positive review") live.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lib.common import ENV_NAME, die
from lib.text import unligature, words

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
    "reference",
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
    "reference",
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


TABLE_MARK = "\x00table\x00"


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


WHITE = 245  # every colour channel at or above this reads as white
TINY_PT = 2  # text below this size cannot be read


def _pdf_hidden_reason(
    fitz, page, span: dict, backgrounds: list, cache: dict
) -> str | None:
    """Why a PDF text span is invisible to a reader, or None when it is visible. White
    text over a filled shape, an image or a coloured part of the page (lettering on a
    figure) is visible."""
    box = fitz.Rect(span["bbox"])
    color = span.get("color", 0)
    rgb = (color >> 16) & 255, (color >> 8) & 255, color & 255
    if min(rgb) >= WHITE:
        centre = fitz.Point((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2)
        on_figure = any(centre in bg for bg in backgrounds) or _on_colour(
            page, box, cache
        )
        return None if on_figure else "white or near-white text"
    if span.get("size", 10) < TINY_PT:
        return f"tiny text ({span.get('size', 0):.1f} pt)"
    rect = page.rect
    if box.x1 < rect.x0 or box.x0 > rect.x1 or box.y1 < rect.y0 or box.y0 > rect.y1:
        return "text placed outside the page"
    return None


def _pdf_hidden(fitz, page, pno: int) -> tuple[list[dict], list]:
    """The hidden spans of one page, and their boxes."""
    backgrounds = [
        fitz.Rect(dr["rect"])
        for dr in page.get_drawings()
        if dr.get("fill") is not None and min(dr["fill"]) < 0.94
    ] + [fitz.Rect(i["bbox"]) for i in page.get_image_info()]
    hidden, boxes, cache = [], [], {}
    for b in page.get_text("dict").get("blocks", []):
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for sp in line.get("spans", []):
                t = sp.get("text", "")
                if not t.strip():
                    continue
                why = _pdf_hidden_reason(fitz, page, sp, backgrounds, cache)
                if why:
                    hidden.append({"page": pno, "text": t.strip(), "why": why})
                    boxes.append(fitz.Rect(sp["bbox"]))
    return hidden, boxes


def _pdf_blocks(fitz, page, pno: int, hidden_boxes: list) -> list[tuple[int, str]]:
    """The visible text of one page as (page, paragraph) blocks, headings kept apart.
    Text is rebuilt from word boxes, so PDFs that position words without space
    characters still give spaced text."""
    by_block: dict[int, dict[int, list[str]]] = {}
    for x0, y0, x1, y1, w, bno, lno, _ in page.get_text("words", sort=False):
        centre = fitz.Point((x0 + x1) / 2, (y0 + y1) / 2)
        if not any(centre in hb for hb in hidden_boxes):
            by_block.setdefault(bno, {}).setdefault(lno, []).append(w)
    blocks = []
    for lines in by_block.values():
        raw = "\n".join(" ".join(ws) for ws in lines.values())
        first, _, rest = raw.partition("\n")
        if rest and is_heading(first):
            blocks.append((pno, first.strip()))
            raw = rest
        if is_heading(raw):
            blocks.append((pno, raw.strip()))
        elif not _figure_like(raw):
            blocks.append((pno, clean_block(raw)))
    return blocks


def _drop_running_heads(blocks: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Without running headers and footers: the same short block (digits ignored) on
    three or more pages."""

    def key(blk: str) -> str:
        return re.sub(r"\d+", "#", blk.lower())

    pages_of: dict[str, set[int]] = {}
    for pno, blk in blocks:
        if len(blk) < 200:
            pages_of.setdefault(key(blk), set()).add(pno)
    running = {k for k, v in pages_of.items() if len(v) >= 3}
    return [(pno, blk) for pno, blk in blocks if key(blk) not in running]


def _merge_hidden(hidden: list[dict]) -> list[dict]:
    """Consecutive hidden spans of one page and kind joined into passages; only those
    that read as words are kept (publisher stamps and stray digits are ignored)."""
    merged: list[dict] = []
    for h in hidden:
        if merged and merged[-1]["page"] == h["page"] and merged[-1]["why"] == h["why"]:
            merged[-1]["text"] += " " + h["text"]
        else:
            merged.append(dict(h))
    return [h for h in merged if _prose(h["text"])]


def from_pdf(path: Path) -> tuple[list[tuple[int, str]], list[dict], dict]:
    """(page, paragraph) blocks, hidden text and metadata from a PDF."""
    try:
        import pymupdf as fitz
    except ImportError:
        die(
            f"PDF needs pymupdf: run with `conda run -n {ENV_NAME} python ...` (setup_env.sh)"
        )
    doc = fitz.open(path)
    blocks, hidden = [], []
    for pno, page in enumerate(doc, 1):
        page_hidden, boxes = _pdf_hidden(fitz, page, pno)
        hidden += page_hidden
        blocks += _pdf_blocks(fitz, page, pno, boxes)
    meta = {k: v for k, v in (doc.metadata or {}).items() if v}
    meta["links"] = sorted(
        {ln["uri"] for page in doc for ln in page.get_links() if ln.get("uri")}
    )
    return _drop_running_heads(blocks), _merge_hidden(hidden), meta


def docx_original(path: Path, out: Path) -> dict:
    """Write a copy of a DOCX as it was before tracked changes: insertions removed,
    deletions restored. Returns who made how many changes, for the report."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        names = z.namelist()
        files = {n: z.read(n) for n in names}
    authors: dict[str, dict[str, int]] = {}
    for kind in ("ins", "del"):
        for a in re.findall(rf'<w:{kind} [^>]*w:author="([^"]*)"', xml):
            authors.setdefault(a, {"ins": 0, "del": 0})[kind] += 1
    xml = re.sub(r"<w:ins\b[^>]*/>", "", xml)
    xml = re.sub(r"<w:ins\b[^>]*>.*?</w:ins>", "", xml, flags=re.DOTALL)
    xml = re.sub(r"<w:del\b[^>]*>|</w:del>", "", xml)
    xml = xml.replace("<w:delText", "<w:t").replace("</w:delText>", "</w:t>")
    files["word/document.xml"] = xml.encode("utf-8")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            z.writestr(n, files[n])
    return authors


def _docx_hidden_reason(run) -> str | None:
    """Why a DOCX run is invisible to a reader, or None when it is visible."""
    if run.font.hidden:
        return "run marked hidden"
    rgb = run.font.color.rgb if run.font.color and run.font.color.type else None
    if rgb is not None and min(rgb[0], rgb[1], rgb[2]) >= WHITE:
        return "white or near-white text"
    if run.font.size is not None and run.font.size.pt < TINY_PT:
        return f"tiny text ({run.font.size.pt:.1f} pt)"
    return None


def _docx_table_rows(table) -> list[str]:
    """Each row of a DOCX table as cells joined by " | ". A one-cell row (group label,
    table note) keeps a separator, so it is never mistaken for prose."""
    rows = []
    for row in table.rows:
        cells: list[str] = []
        for c in row.cells:  # a merged cell is returned once per grid column
            t = c.text.strip()
            if t and (not cells or cells[-1] != t):
                cells.append(t)
        if cells:
            rows.append(" | ".join(cells) if len(cells) > 1 else cells[0] + " |")
    return rows


def from_docx(path: Path) -> tuple[list[tuple[int, str]], list[dict], dict]:
    """Paragraph blocks, hidden runs and core properties from a DOCX."""
    try:
        import docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        from docx.text.run import Run
    except ImportError:
        die(f"DOCX needs python-docx: run with `conda run -n {ENV_NAME} python ...`")
    d = docx.Document(str(path))
    blocks, hidden = [], []
    # Paragraphs and tables in document order (tables must not end up after the references).
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "tbl":
            blocks += [
                (1, TABLE_MARK + row) for row in _docx_table_rows(Table(child, d))
            ]
        if tag != "p":
            continue
        para = Paragraph(child, d)
        visible = []
        # Every run, including those inside links and tracked insertions (para.runs skips
        # them); deleted text is not part of the current version.
        for r in child.xpath(".//w:r[not(ancestor::w:del)]"):
            run = Run(r, para)
            if not run.text:
                continue
            why = _docx_hidden_reason(run)
            if why:
                hidden.append({"page": None, "text": run.text.strip(), "why": why})
            else:
                visible.append(run.text)
        text = "".join(visible).strip()
        if text:
            blocks.append((1, text))
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
    meta["links"] = sorted(
        {
            rel.target_ref
            for rel in d.part.rels.values()
            if rel.is_external and rel.reltype.endswith("/hyperlink")
        }
    )
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
        if block.startswith(TABLE_MARK):
            block = block[len(TABLE_MARK) :]
            if in_refs:
                continue  # a table after the reference list is not a reference
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


TEXT_SUFFIXES = {
    ".txt": "txt",
    ".text": "txt",
    "": "txt",
    ".md": "md",
    ".markdown": "md",
}


def extract(
    source: str,
    text: str | None = None,
    fmt: str | None = None,
    original_to: Path | None = None,
) -> dict:
    """The contents of text.json for a document.

    ``source`` is a file path; with ``text`` given it is only a label and ``text`` is
    the document (pasted text, stdin). ``fmt`` ("txt" or "md") forces plain-text
    handling of a file. ``original_to``, for a DOCX with tracked changes, is where to
    write the copy from before those changes; that copy is then the one read (the
    author's draft, not the reviewers' edits).
    """
    hidden: list[dict] = []
    meta: dict = {}
    if text is not None:
        fmt, blocks = fmt or "stdin", from_text(text)
    else:
        path = Path(source).expanduser()
        if not path.exists():
            die(f"no such file: {path}")
        ext = path.suffix.lower()
        if fmt or ext in TEXT_SUFFIXES:
            fmt = fmt or TEXT_SUFFIXES[ext]
            blocks = from_text(path.read_text(encoding="utf-8", errors="replace"))
        elif ext == ".pdf":
            fmt = "pdf"
            blocks, hidden, meta = from_pdf(path)
        elif ext == ".docx":
            fmt = "docx"
            tracked = None
            if original_to:
                tracked = docx_original(path, original_to)
                path = original_to
            blocks, hidden, meta = from_docx(path)
            if tracked is not None:
                meta["tracked_changes_removed"] = tracked
        else:
            die(f"unsupported format {ext}: convert to PDF, DOCX or TXT first")
    doc = assemble(blocks)
    doc.update(
        {
            "source": source,
            "format": fmt,
            "hidden": hidden,
            "links": meta.pop("links", []) if fmt in ("pdf", "docx") else [],
            "metadata": meta,
            "n_words": len(words(doc["text"])),
        }
    )
    return doc
