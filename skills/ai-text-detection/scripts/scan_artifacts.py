"""Scan the document for graded artefacts listed in references/markers.json.

Every hit is quoted with its context and location, so it can be checked by anyone.
Searches the body, the reference list (chatbot links and citation tokens hide there)
and any hidden text found by extract_text.py. Hidden text is reported on its own: any
hidden instruction is a finding even when no pattern matches it.

A conclusive hit is a *candidate* until Claude confirms in context that it is not a
quotation, an example, or a discussion of AI (a paper about ChatGPT may legitimately
contain "As an AI language model"). Claude records that in judgements.json
(``{"artifacts": {"<hit id>": {"confirmed": false, "why": "..."}}}``) and grade.py honours it.

Writes ``<work>/artifacts.json``: {"hits": [...], "hidden": [...], "counts": {...}}

Usage:
    python scan_artifacts.py [--work /tmp/ai_text_detection]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _common import REFS, WORK_DIR, context, load_text, locate, read_json, write_json

FLAG_MAP = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}


def compile_pattern(p: dict) -> re.Pattern | None:
    """The compiled regex of a marker (None for lexicon-based markers)."""
    if "regex" in p:
        flags = 0
        for ch in p.get("flags", ""):
            flags |= FLAG_MAP[ch]
        return re.compile(p["regex"], flags)
    if p.get("lexicon") == "tortured_phrases.json":
        phrases = read_json(REFS / "tortured_phrases.json")["phrases"]
        alt = "|".join(re.escape(k) for k in sorted(phrases, key=len, reverse=True))
        return re.compile(rf"\b(?:{alt})\b", re.IGNORECASE)
    return None


def load_markers() -> list[dict]:
    """Patterns with their compiled regex."""
    markers = read_json(REFS / "markers.json")["patterns"]
    for m in markers:
        m["_re"] = compile_pattern(m)
    return markers


def scan(text: str, markers: list[dict], fmt: str, where: str) -> list[dict]:
    """All hits of all markers in ``text``."""
    hits = []
    tortured = None
    for m in markers:
        if m["_re"] is None:
            continue
        if m.get("formats") and fmt not in m["formats"]:
            continue
        for mt in m["_re"].finditer(text):
            hit = {
                "marker": m["id"],
                "tier": m["tier"],
                "category": m["category"],
                "shows": m["shows"],
                "match": mt.group(0).strip(),
                "quote": context(text, mt.start(), mt.end()),
                "in": where,
                "offset": mt.start(),
                "source": m.get("source"),
            }
            if m["id"] == "tortured-phrase":
                tortured = tortured or {
                    k.lower(): v
                    for k, v in read_json(REFS / "tortured_phrases.json")[
                        "phrases"
                    ].items()
                }
                hit["established_term"] = tortured.get(mt.group(0).lower())
            hits.append(hit)
    return hits


def main(argv: list[str] | None = None) -> int:
    """Scan and write artifacts.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    args = p.parse_args(argv)
    work = Path(args.work)
    doc = load_text(work)
    markers = load_markers()

    hits = scan(doc["text"], markers, doc["format"], "body")
    for h in hits:
        h.update(locate(doc, h["offset"]))
    hits += scan(doc.get("references_text", ""), markers, doc["format"], "references")
    # Link addresses (PDF and Word): utm_source=chatgpt.com usually sits in the address.
    hits += scan("\n".join(doc.get("links", [])), markers, doc["format"], "links")
    hidden = []
    for i, h in enumerate(doc.get("hidden", [])):
        inner = scan(h["text"], markers, doc["format"], "hidden")
        hidden.append(
            {**h, "id": f"hidden-{i + 1}", "matches": [x["marker"] for x in inner]}
        )
        for x in inner:
            x["page"] = h["page"]
            x["hidden_why"] = h["why"]
        hits += inner
    for i, h in enumerate(hits, 1):
        h["id"] = f"a{i}"

    counts: dict[str, int] = {}
    for h in hits:
        counts[h["marker"]] = counts.get(h["marker"], 0) + 1
    write_json(
        work / "artifacts.json", {"hits": hits, "hidden": hidden, "counts": counts}
    )
    if not hits and not hidden:
        print("artifacts: none found")
    for h in hits:
        loc = h.get("section") or h["in"]
        page = f", p.{h['page']}" if h.get("page") else ""
        print(
            f"[{h['id']}] {h['tier'].upper():<10} {h['marker']:<20} ({loc}{page}): {h['quote'][:150]}"
        )
    for h in hidden:
        print(f"[{h['id']}] HIDDEN ({h['why']}, p.{h['page']}): {h['text'][:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
