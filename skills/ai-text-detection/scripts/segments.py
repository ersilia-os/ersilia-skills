"""Split the document several ways, so a detector's verdict can be checked for stability.

One split is one opinion about where a "passage" begins and ends. A detector's score can
change with the split (what text sits next to what), so the skill asks each detector the
same question several ways and keeps what is stable:

    S  sections      each section's prose as a whole (for tools that do better on long text)
    P  passages      whole paragraphs from one section, ~250-500 words (build_passages)
    W  windows       ~350 words, moving forward ~175 words at a time along sentence
                     boundaries within a section: every sentence sits in two windows
                     with different neighbours

Only prose is ever included (web_detectors.is_prose): no title page, captions, equations
or reference lists. Each tool receives only the segments that fit its size range
(``min_words`` / ``max_words`` in references/web_detectors.json).

Writes ``<work>/multi/plan.json`` ({"units": [...], "sentences": [...]}) and one text
file per segment. The sentence list (with character offsets) is what evidence.py scores.

Usage:
    python segments.py [--work /tmp/ai_text_detection] [--window 350 --stride 175]
    python segments.py --for-tool binoculars     # prints the unit ids that fit that tool
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _common import (
    SENT_RE,
    SKIP_SECTIONS,
    WORK_DIR,
    load_text,
    read_json,
    words,
    write_json,
)
from web_detectors import build_passages, is_prose, registry


def prose_paragraphs(doc: dict) -> list[dict]:
    """Prose paragraphs with section and character span, in reading order."""
    text = doc["text"]
    out = []
    for sec in doc.get("sections") or [
        {"title": "(whole text)", "start": 0, "end": len(text)}
    ]:
        if sec["title"].lower() in SKIP_SECTIONS:
            continue
        found: list[dict] = []
        pos = sec["start"]
        for m in [*re.finditer(r"\n\s*\n", text[sec["start"] : sec["end"]]), None]:
            end = sec["start"] + m.start() if m else sec["end"]
            raw = text[pos:end]
            a = pos + (len(raw) - len(raw.lstrip()))
            b = a + len(raw.strip())
            if is_prose(raw):
                found.append({"section": sec["title"], "start": a, "end": b})
            pos = sec["start"] + m.end() if m else sec["end"]
        # The text before the first heading is front matter unless it holds real prose
        # (a document without headings): the same rule as build_passages.
        if sec["title"] == "(start)" and (
            sum(len(words(text[x["start"] : x["end"]])) for x in found) < 150
        ):
            continue
        out.extend(found)
    return out


def sentence_spans(text: str, paras: list[dict]) -> list[dict]:
    """Sentences (character spans) of the prose paragraphs."""
    out = []
    for pi, p in enumerate(paras):
        seg = text[p["start"] : p["end"]]
        starts = [0] + [m.end() for m in SENT_RE.finditer(seg)]
        for i, s0 in enumerate(starts):
            s1 = starts[i + 1] if i + 1 < len(starts) else len(seg)
            raw = seg[s0:s1]
            a = p["start"] + s0 + (len(raw) - len(raw.lstrip()))
            b = p["start"] + s0 + len(raw.rstrip())
            if b > a:
                out.append(
                    {
                        "id": f"s{len(out) + 1}",
                        "section": p["section"],
                        "para": pi,
                        "start": a,
                        "end": b,
                        "n_words": len(words(text[a:b])),
                    }
                )
    return out


def build(doc: dict, window: int, stride: int) -> dict:
    """All units at the three scales, plus the sentence list."""
    text = doc["text"]
    paras = prose_paragraphs(doc)
    sents = sentence_spans(text, paras)
    units: list[dict] = []

    def add(scale: str, spans: list[tuple[int, int]], sections: list[str]) -> None:
        body = "\n\n".join(text[a:b] for a, b in spans)
        units.append(
            {
                "chunk": f"{scale}{sum(1 for u in units if u['scale'] == scale) + 1}",
                "scale": scale,
                "spans": [list(x) for x in spans],
                "start": spans[0][0],
                "end": spans[-1][1],
                "sections": sections,
                "n_words": len(words(body)),
                "_text": body,
            }
        )

    # S: sections (prose only); a tiny section joins the previous one.
    by_sec: dict[str, list[dict]] = {}
    for p in paras:
        by_sec.setdefault(p["section"], []).append(p)
    for sec, ps in by_sec.items():
        spans = [(p["start"], p["end"]) for p in ps]
        n = sum(len(words(text[a:b])) for a, b in spans)
        if n < 150 and units:
            last = units.pop()
            spans = [tuple(x) for x in last["spans"]] + spans
            add("S", spans, last["sections"] + [sec])
        else:
            add("S", spans, [sec])
    # P: the passages the report is organised by.
    for p in build_passages(doc):
        add("P", [tuple(x) for x in p["paras"]], p["sections"])
    # W: windows of ~`window` words starting every ~`stride` words, snapped to sentence
    # boundaries, within a section (a section under 150 words joins the previous one).
    groups: list[tuple[list[str], list[dict]]] = []
    for sec in by_sec:
        ss = [x for x in sents if x["section"] == sec]
        if groups and sum(x["n_words"] for x in ss) < 150:
            groups[-1][0].append(sec)
            groups[-1][1].extend(ss)
        else:
            groups.append(([sec], ss))
    for secs, ss in groups:
        cum, c = [], 0
        for x in ss:
            cum.append(c)
            c += x["n_words"]
        total = c
        wlen = window if total > 1.2 * window else max(150, int(total * 0.6))
        step = max(60, stride if wlen == window else wlen // 2)
        made: list[tuple[int, int]] = []
        start = 0
        while start < total:
            i = next(k for k in range(len(ss)) if cum[k] + ss[k]["n_words"] > start)
            j = max(k for k in range(len(ss)) if cum[k] < start + wlen)
            if total - (cum[j] + ss[j]["n_words"]) < step * 0.5:
                j = len(ss) - 1  # do not leave a scrap at the end
            if (i, j) not in made:
                made.append((i, j))
                spans: list[tuple[int, int]] = []
                last_para = None
                for x in ss[
                    i : j + 1
                ]:  # one span per paragraph: never sweep in text between
                    if spans and x.get("para") == last_para:
                        spans[-1] = (spans[-1][0], x["end"])
                    else:
                        spans.append((x["start"], x["end"]))
                    last_para = x.get("para")
                add("W", spans, secs)
            if j == len(ss) - 1:
                break
            start += step
    p_spans = [u["spans"] for u in units if u["scale"] == "P"]
    # Ids stay as numbered (a gap where an S was dropped), so results recorded against
    # them never point at a different unit.
    units = [u for u in units if not (u["scale"] == "S" and u["spans"] in p_spans)]
    return {"units": units, "sentences": sents}


def fits(unit: dict, tool: dict) -> bool:
    """Whether a unit is within the tool's size range."""
    lo = tool.get("min_words") or 80
    hi = tool.get("max_words") or 2000
    return lo <= unit["n_words"] <= hi


def main(argv: list[str] | None = None) -> int:
    """Write the multi-split plan."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument("--window", type=int, default=350)
    p.add_argument("--stride", type=int, default=175)
    p.add_argument("--for-tool")
    args = p.parse_args(argv)
    work = Path(args.work)
    d = work / "multi"
    if args.for_tool:
        plan = read_json(d / "plan.json")
        tool = next(t for t in registry()["tools"] if t["id"] == args.for_tool)
        print(",".join(u["chunk"] for u in plan["units"] if fits(u, tool)))
        return 0
    plan = build(load_text(work), args.window, args.stride)
    d.mkdir(parents=True, exist_ok=True)
    for u in plan["units"]:
        f = d / f"{u['chunk']}.txt"
        f.write_text(u.pop("_text"), encoding="utf-8")
        u["file"] = str(f)
    write_json(d / "plan.json", plan)
    for scale in "SPW":
        us = [u for u in plan["units"] if u["scale"] == scale]
        print(
            f"{scale}: {len(us)} units, "
            + ", ".join(f"{u['chunk']}={u['n_words']}w" for u in us)
        )
    print(f"sentences: {len(plan['sentences'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
