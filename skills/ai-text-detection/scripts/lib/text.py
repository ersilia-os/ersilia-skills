"""Text primitives: tokens, sentences, prose detection, where an offset sits, and the
fixed-size windows the style score and its calibration use."""

from __future__ import annotations

import itertools
import re
from pathlib import Path

from lib.common import WORK_DIR, die, read_json

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


NON_PROSE = re.compile(
    r"^(?:fig(?:ure)?\.?\s*\d|table\s*\d|eq\.?\s*\d|eq\d|supplementary|orcid|\*?corresponding author|keywords?:)",
    re.IGNORECASE,
)


def is_prose(par: str) -> bool:
    """Whether a paragraph is running prose worth sending to a detector.

    Excluded: headings, author lists and affiliations, ORCIDs and e-mails, figure and
    table captions, equation labels, table rows, and anything mostly numbers.
    """

    t = par.strip()
    w = words(t)
    if len(w) < 12 or NON_PROSE.match(t):
        return False
    if re.search(
        r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b|@|\|", t
    ):  # ORCID, e-mail, table row
        return False
    if t.count(",") > 4 and len(re.findall(r"\d", t)) > len(
        w
    ):  # author list with affiliation numbers
        return False
    if (
        len(w) < 60
        and t.count(",") >= 2
        and re.search(
            r"\b(University|Institute|Department|Centre|Center|Faculty|School of|Laboratory|Hospital)\b",
            t,
        )
    ):  # affiliation
        return False
    tokens = t.split()
    alpha = sum(1 for x in tokens if re.search(r"[A-Za-z]{3,}", x))
    return (
        alpha / max(len(tokens), 1) >= 0.6 and t[-1:] in '.?!)\u201d"' or len(w) >= 40
    )
