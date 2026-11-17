"""Grade the document: one tier and the statements the user can defend (lib/grading.py).

Reads from the work folder: text.json, artifacts.json, references.json, stylometry.json,
the detectors' plan and results, evidence.json, baseline.json (optional), and judgements.json (Claude's
own reading, plus its decisions on candidate hits and on references verified by hand).
Every threshold is in references/grading.json. The tier is the highest one whose rule is
met:

    conclusive    a confirmed artefact of an AI tool's output (chatbot leftovers, citation
                  tokens, placeholders, leaked reasoning, interface leftovers)
    strong        two or more fabricated references; a strong close-reading finding
                  (a verified false claim or invented fact); markdown or unicode
                  artefacts; or two validated web detectors flagging the document plus a
                  non-statistical finding
    moderate      one independent line: a fabricated reference; two close-reading
                  findings; the style score past its 1% threshold in most windows; one
                  validated web detector flagging the text; the calibrated combination of
                  detectors (evidence.py) at 10x for the document or 20x for one passage;
                  or a clear shift from the author's own earlier writing
    weak          context only: a single reading observation, style past 5%, unvalidated
                  detectors, a weak marker
    none          nothing found

Prompt injections and paraphraser traces are reported separately: serious, but not
evidence that an AI wrote the text. Statements never claim more than the evidence: what
was found, where, and how anyone can re-check it.

judgements.json (written by Claude, all keys optional):

    {"artifacts": {"a3": {"confirmed": false, "why": "quoted as an example in a paper on LLMs"}},
     "references": {"7": {"fabricated": true, "why": "searched Google Scholar and PubMed by title"}},
     "reading": [{"tier": "moderate", "title": "one line", "claim": "...", "quote": "...", "where": "Review, point 3",
                  "check": "how to verify"}],
     "excluded_sections": ["Methods"]}

Writes ``<work>/grade.json``.

Usage:
    python grade.py [--work /tmp/ai_text_detection]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.common import WORK_DIR, write_json
from lib.grading import grade


def main(argv: list[str] | None = None) -> int:
    """Grade and write grade.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    work = Path(p.parse_args(argv).work)
    g = grade(work)
    write_json(work / "grade.json", g)
    print(f"verdict: {g['tier'].upper()}: {g['headline']}")
    for s in g["statements"]:
        print(f"  [{s['tier']}] {s['text'][:220]}")
    for s in g["separate"]:
        print(f"  [{s['kind']}] {s['text'][:220]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
