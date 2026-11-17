"""Build the public demonstration case: a published, human-written paper with known
contamination.

The paper is Turon et al., Nature Communications 2023 (CC BY 4.0), fetched from Europe
PMC. ``examples/demo/contamination.json`` lists every change and is the answer key:
paragraphs rewritten by an AI ("ai-polished": same content, reworded) or replaced by AI
text ("ai-written"), leftover chatbot text inside them, swapped references, and a hidden
instruction. A replacement is never longer than the paragraph it replaces. Everything
else is the authors' text.

Writes ``examples/demo/turon2023_contaminated.docx`` (python-docx: run in the conda env)
and prints what changed. Then run the skill on it with ``--work <another folder>``.

Usage:
    conda run -n ai-text-detection python build_demo.py [--out <file.docx>]
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from lib.common import ENV_NAME, EXAMPLES, die, read_json
from lib.europepmc import EPMC
from lib.http import get_text
from lib.text import words

DEMO = EXAMPLES / "demo"
SECTIONS = ("Introduction", "Results", "Discussion", "Methods")
SKIP = {"fig", "table-wrap", "disp-formula", "inline-formula", "supplementary-material"}
NOTICE = (
    "Demonstration copy, deliberately altered to test AI-text detection. It is not the "
    "published article. Original: {citation} Licensed CC BY 4.0. The changes are listed "
    "in contamination.json."
)


def inline_text(el: ET.Element) -> str:
    """The text of a paragraph, with citation superscripts as bracketed numbers and
    figures, tables and formulas left out."""
    if el.tag in SKIP:
        return el.tail or ""
    inner = (el.text or "") + "".join(inline_text(c) for c in el)
    if el.tag == "sup" and el.find("xref[@ref-type='bibr']") is not None:
        inner = f" [{inner.strip()}]"
    return inner + (el.tail or "")


def clean(text: str) -> str:
    """One line, single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def paragraph(el: ET.Element) -> str:
    """A paragraph element as plain text (its own tail left out)."""
    return clean(inline_text(el).removesuffix(el.tail or ""))


def blocks_of(sec: ET.Element, section: str) -> list[dict]:
    """A section as blocks in reading order: headings, paragraphs and figure captions."""
    out = []
    for child in sec:
        if child.tag == "title":
            out.append(
                {
                    "kind": "heading",
                    "section": section,
                    "text": clean("".join(child.itertext())),
                }
            )
        elif child.tag == "p":
            out.append({"kind": "p", "section": section, "text": paragraph(child)})
        elif child.tag == "sec":
            out += blocks_of(child, section)
        elif child.tag == "fig":
            caption = clean("".join(child.find("caption").itertext()))
            out.append(
                {
                    "kind": "caption",
                    "section": section,
                    "text": f"{child.findtext('label')}. {caption}",
                }
            )
    return out


def reference(ref: ET.Element) -> str:
    """One reference as a line: number, citation and its DOI."""
    text = clean("".join(ref.find("mixed-citation").itertext()))
    doi = ref.find(".//ext-link[@ext-link-type='doi']")
    href = (
        next((v for k, v in doi.attrib.items() if k.endswith("href")), "")
        if doi is not None
        else ""
    )
    if href and href not in text:
        text += f" https://doi.org/{href}"
    return f"{ref.findtext('label')} {text}"


def read_paper(pmcid: str) -> tuple[dict, list[dict], list[str]]:
    """(title and authors, blocks of the abstract and the main sections, references)."""
    xml = get_text(f"{EPMC}/{pmcid}/fullTextXML") or die(f"could not fetch {pmcid}")
    root = ET.fromstring(xml)
    meta = root.find("front/article-meta")
    authors = [
        f"{c.findtext('name/given-names')} {c.findtext('name/surname')}"
        for c in meta.iter("contrib")
        if c.get("contrib-type") == "author"
    ]
    head = {
        "title": clean("".join(meta.find(".//article-title").itertext())),
        "authors": authors,
    }
    abstract = meta.find("abstract").find("p")
    blocks = [
        {"kind": "heading", "section": "Abstract", "text": "Abstract"},
        {"kind": "p", "section": "Abstract", "text": paragraph(abstract)},
    ]
    for sec in root.find("body").findall("sec"):
        name = sec.findtext("title")
        if name in SECTIONS:
            blocks += blocks_of(sec, name)
    return head, blocks, [reference(r) for r in root.iter("ref")]


def contaminate(blocks: list[dict], refs: list[str], plan: dict) -> list[dict]:
    """Apply the plan in place; return one row per change for the printed summary."""
    done = []
    for edit in plan["edits"]:
        hits = [
            b
            for b in blocks
            if b["kind"] == "p"
            and b["section"] == edit["section"]
            and b["text"].startswith(edit["anchor"])
        ]
        if len(hits) != 1:
            die(f"{edit['id']}: anchor matches {len(hits)} paragraphs")
        before, after = len(words(hits[0]["text"])), len(words(edit["text"]))
        if after > before:
            die(
                f"{edit['id']}: replacement is longer ({after} words) than the original ({before})"
            )
        hits[0].update(text=edit["text"], edit=edit["id"])
        done.append(
            {"id": edit["id"], "kind": edit["kind"], "before": before, "after": after}
        )
    for swap in plan["references"]:
        i = swap["n"] - 1
        done.append(
            {"id": f"ref{swap['n']}", "kind": swap["kind"], "original": refs[i]}
        )
        refs[i] = f"{swap['n']}. {swap['text']}"
    return done


def write_docx(
    out: Path, head: dict, blocks: list[dict], refs: list[str], plan: dict
) -> None:
    """The altered paper as a DOCX; the hidden instruction is white text."""
    try:
        import docx
        from docx.shared import Pt, RGBColor
    except ImportError:
        die(f"needs python-docx: run with `conda run -n {ENV_NAME} python ...`")
    d = docx.Document()
    d.add_paragraph(NOTICE.format(citation=plan["source"]["citation"]))
    d.add_paragraph(head["title"])
    d.add_paragraph(", ".join(head["authors"]))
    hidden = plan["hidden"]
    for b in blocks:
        para = d.add_paragraph(
            b["text"], style="Heading 2" if b["kind"] == "heading" else None
        )
        if (
            b["kind"] == "p"
            and b["section"] == hidden["after_section"]
            and not hidden.get("placed")
        ):
            run = para.add_run(" " + hidden["text"])
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            run.font.size = Pt(1)
            hidden["placed"] = True
    d.add_paragraph("References", style="Heading 2")
    for r in refs:
        d.add_paragraph(r)
    out.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(out))


def main(argv: list[str] | None = None) -> int:
    """Fetch, contaminate, write, and print the changes."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--out", default=str(DEMO / "turon2023_contaminated.docx"))
    args = p.parse_args(argv)
    plan = read_json(DEMO / "contamination.json") or die(
        "missing examples/demo/contamination.json"
    )
    head, blocks, refs = read_paper(plan["source"]["pmcid"])
    prose = sum(len(words(b["text"])) for b in blocks if b["kind"] == "p")
    done = contaminate(blocks, refs, plan)
    write_docx(Path(args.out), head, blocks, refs, plan)
    changed = 0
    for row in done:
        if "before" in row:
            changed += row["before"]
            print(
                f"{row['id']:<16} {row['kind']:<12} {row['before']:>4} -> {row['after']:>4} words"
            )
        else:
            print(f"{row['id']:<16} {row['kind']:<12} was: {row['original'][:90]}")
    after = sum(len(words(b["text"])) for b in blocks if b["kind"] == "p")
    print(
        f"prose: {prose} words before, {after} after; {changed} words ({changed / prose:.0%}) in changed paragraphs"
    )
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
