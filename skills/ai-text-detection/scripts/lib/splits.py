"""The units the detectors see.

* **Passages** (``build_passages``): whole prose paragraphs from one section, 250-600
  words. The unit the report shows and the reader thinks in.
* **The plan** (``build_plan``): the same text split three ways, so a detector's verdict
  can be checked for stability across cuts:

      S  sections   each section's prose as a whole (for tools that do better on long text)
      P  passages   as above
      W  windows    ~350 words, moving forward half a window along sentence boundaries
                    within a section: every sentence sits in two windows with different
                    neighbours

  Only prose is included (``text.is_prose``): no title page, captions, equations or
  references.
"""

from __future__ import annotations

from lib.text import SENT_RE, checked_sections, is_prose, paragraph_spans, words

SMALL = 150  # a section with fewer words joins the previous one


def build_passages(doc: dict, lo: int = 250, hi: int = 600) -> list[dict]:
    """Passages a detector can judge: runs of whole prose paragraphs from one section,
    aiming at (lo+hi)/2 words. Paragraphs that are not prose (is_prose) are left out; the
    title page is never included; a section under ~150 words joins the previous passage
    when the result stays under ``hi`` words, and the label names both sections."""

    text = doc["text"]
    passages: list[dict] = []
    for sec in checked_sections(doc):
        cur: dict | None = None
        for pos, end in paragraph_spans(text, sec["start"], sec["end"]):
            par = text[pos:end]
            p0 = pos + (len(par) - len(par.lstrip()))
            if not is_prose(par):
                continue
            n = len(words(par))
            if cur and cur["n_words"] + n > (lo + hi) // 2 and cur["n_words"] >= lo:
                passages.append(cur)
                cur = None
            if cur is None:
                cur = {
                    "sections": [sec["title"]],
                    "start": p0,
                    "end": end,
                    "n_words": 0,
                    "paras": [],
                }
            cur["paras"].append([p0, end])
            cur["end"] = end
            cur["n_words"] += n
        if cur:
            if sec["title"] == "(start)" and cur["n_words"] < SMALL:
                continue  # front matter (title page): never sent
            if (
                cur["n_words"] < SMALL
                and passages
                and passages[-1]["n_words"] + cur["n_words"] <= hi
            ):
                prev = passages[-1]
                prev["paras"] += cur["paras"]
                prev["end"] = cur["end"]
                prev["n_words"] += cur["n_words"]
                if cur["sections"][0] not in prev["sections"]:
                    prev["sections"].append(cur["sections"][0])
            else:
                passages.append(cur)
    return passages


def prose_paragraphs(doc: dict) -> list[dict]:
    """Prose paragraphs with section and character span, in reading order."""
    text = doc["text"]
    out = []
    for sec in checked_sections(doc):
        found: list[dict] = []
        for pos, end in paragraph_spans(text, sec["start"], sec["end"]):
            raw = text[pos:end]
            a = pos + (len(raw) - len(raw.lstrip()))
            b = a + len(raw.strip())
            if is_prose(raw):
                found.append({"section": sec["title"], "start": a, "end": b})
        # The text before the first heading is front matter unless it holds real prose
        # (a document without headings): the same rule as build_passages.
        if sec["title"] == "(start)" and (
            sum(len(words(text[x["start"] : x["end"]])) for x in found) < SMALL
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


def _unit(
    units: list[dict], scale: str, spans: list, sections: list[str], text: str
) -> None:
    """Append the unit made of ``spans`` (character ranges), numbered within its scale."""
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


def _section_units(units: list[dict], by_sec: dict[str, list[dict]], text: str) -> None:
    """S: each section's prose as one unit; a small section joins the previous one."""
    for sec, paras in by_sec.items():
        spans = [(p["start"], p["end"]) for p in paras]
        n = sum(len(words(text[a:b])) for a, b in spans)
        if n < SMALL and units:
            last = units.pop()
            spans = [tuple(x) for x in last["spans"]] + spans
            _unit(units, "S", spans, last["sections"] + [sec], text)
        else:
            _unit(units, "S", spans, [sec], text)


def _window_spans(sents: list[dict], i: int, j: int) -> list[tuple[int, int]]:
    """Sentences i..j as one span per paragraph, so no text between paragraphs is swept in."""
    spans: list[tuple[int, int]] = []
    last_para = None
    for x in sents[i : j + 1]:
        if spans and x.get("para") == last_para:
            spans[-1] = (spans[-1][0], x["end"])
        else:
            spans.append((x["start"], x["end"]))
        last_para = x.get("para")
    return spans


def _window_units(
    units: list[dict],
    secs: list[str],
    sents: list[dict],
    window: int,
    stride: int,
    text: str,
) -> None:
    """W: windows of ~``window`` words starting every ~``stride`` words, snapped to
    sentence boundaries, over the sentences of one group of sections. A short group gets
    shorter windows, so every sentence still sits in two of them."""
    cum, total = [], 0
    for x in sents:
        cum.append(total)
        total += x["n_words"]
    wlen = window if total > 1.2 * window else max(SMALL, int(total * 0.6))
    step = max(60, stride if wlen == window else wlen // 2)
    made: list[tuple[int, int]] = []
    start, last = 0, len(sents) - 1
    while start < total:
        i = next(k for k in range(len(sents)) if cum[k] + sents[k]["n_words"] > start)
        j = max(k for k in range(len(sents)) if cum[k] < start + wlen)
        if total - (cum[j] + sents[j]["n_words"]) < step * 0.5:
            j = last  # do not leave a scrap at the end
        if (i, j) not in made:
            made.append((i, j))
            _unit(units, "W", _window_spans(sents, i, j), secs, text)
        if j == last:
            break
        start += step


def build_plan(doc: dict, window: int = 350, stride: int = 175) -> dict:
    """All units at the three scales, plus the sentence list."""
    text = doc["text"]
    paras = prose_paragraphs(doc)
    sents = sentence_spans(text, paras)
    by_sec: dict[str, list[dict]] = {}
    for p in paras:
        by_sec.setdefault(p["section"], []).append(p)
    units: list[dict] = []
    _section_units(units, by_sec, text)
    for p in build_passages(doc):  # P: the passages the report is organised by
        _unit(units, "P", [tuple(x) for x in p["paras"]], p["sections"], text)
    # W: within a section; a small section joins the previous group.
    groups: list[tuple[list[str], list[dict]]] = []
    for sec in by_sec:
        ss = [x for x in sents if x["section"] == sec]
        if groups and sum(x["n_words"] for x in ss) < SMALL:
            groups[-1][0].append(sec)
            groups[-1][1].extend(ss)
        else:
            groups.append(([sec], ss))
    for secs, ss in groups:
        _window_units(units, secs, ss, window, stride, text)
    # A section that is exactly one passage is dropped. Ids stay as numbered (a gap where
    # an S was dropped), so results recorded against them never point at a different unit.
    p_spans = [u["spans"] for u in units if u["scale"] == "P"]
    units = [u for u in units if not (u["scale"] == "S" and u["spans"] in p_spans)]
    return {"units": units, "sentences": sents}
