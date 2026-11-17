"""Open-access scientific text from Europe PMC, cut into the windows the style score uses.

Shared by build_corpus.py (the human calibration corpus) and web_controls.py (human
control texts from a document's own field). Only CC BY text published before ChatGPT is
asked for; the queries say so.
"""

from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET

from lib.http import get_json, get_text
from lib.text import style_windows, words

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
NATIVE = re.compile(
    r"\b(USA|U\.S\.A|United States|UK|U\.K\.|United Kingdom|England|Scotland|Wales|Australia|Canada|New Zealand|Ireland)\b"
)
COUNTRY = re.compile(r",\s*([A-Z][A-Za-z .'-]{2,40})\.?\s*(?:[;.]|$)")
# Published under CC BY before ChatGPT's release (30 Nov 2022).
OPEN_BEFORE_CHATGPT = 'OPEN_ACCESS:y AND LICENSE:"cc by" AND PUB_YEAR:[2015 TO 2021]'


def para_text(el: ET.Element) -> str:
    """Plain text of an XML element, citations and formulas dropped."""
    for tag in ("xref", "inline-formula", "disp-formula", "table-wrap", "fig"):
        for x in el.iter(tag):
            x.clear()
    t = "".join(el.itertext())
    t = re.sub(r"\[\s*[,–\-\s]*\]|\(\s*[,;–\-\s]*\)", "", t)
    return re.sub(r"\s+", " ", t).strip()


def windows(doc_id: str, paras: list[str], meta: dict) -> list[dict]:
    """Cut paragraphs into ~300-word windows with the shared chunker."""
    text = "\n\n".join(p for p in paras if len(words(p)) >= 25)
    if len(words(text)) < 120:
        return []
    doc = {
        "text": text,
        "sections": [{"title": meta["kind"], "start": 0, "end": len(text)}],
    }
    return [
        {
            "id": f"{doc_id}:{c['id']}",
            "doc_id": doc_id,
            **meta,
            "n_words": c["n_words"],
            "text": c["text"],
        }
        for c in style_windows(doc)
    ]


def country_of(affiliation: str | None) -> tuple[str | None, bool | None]:
    """(country guess, native-English country?) from an affiliation string."""
    if not affiliation:
        return None, None
    # Drop e-mail addresses and anything after them ("... Pretoria. joanne@x.ac.za").
    affiliation = re.split(r"\S+@\S+|Electronic address", affiliation)[0].strip(" .;,")
    if NATIVE.search(affiliation):
        return NATIVE.search(affiliation).group(1), True
    m = COUNTRY.findall(affiliation)
    return (m[-1].strip() if m else None), (False if m else None)


def search(query: str, pages: int) -> list[dict]:
    """Europe PMC 'core' search results (with abstracts), cursor-paginated."""
    out, cursor = [], "*"
    for _ in range(pages):
        url = (
            f"{EPMC}/search?query={urllib.parse.quote(query)}&resultType=core&format=json"
            f"&pageSize=100&cursorMark={urllib.parse.quote(cursor)}"
        )
        data = get_json(url)
        if not data:
            break
        out += data.get("resultList", {}).get("result", [])
        nxt = data.get("nextCursorMark")
        if not nxt or nxt == cursor:
            break
        cursor = nxt
    return out


def base_meta(r: dict) -> dict:
    """Year, first-author country and source of a Europe PMC record."""
    aff = None
    for a in r.get("authorList", {}).get("author", [])[:1]:
        det = a.get("authorAffiliationDetailsList", {}).get("authorAffiliation", [])
        aff = det[0].get("affiliation") if det else None
    country, native = country_of(aff or r.get("affiliation"))
    ident = r.get("pmcid") or r.get("pmid")
    return {
        "year": int(r.get("pubYear", 0)),
        "country": country,
        "native_english": native,
        "source_url": f"https://europepmc.org/article/{'PMC' if r.get('pmcid') else 'MED'}/{ident}",
        "license": "CC BY",
    }


def fulltext_windows(r: dict, kind: str) -> list[dict]:
    """Intro/discussion windows (kind 'article') or the decision letter (kind 'review')."""
    xml = get_text(f"{EPMC}/{r['pmcid']}/fullTextXML")
    if not xml:
        return []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    meta = {**base_meta(r), "kind": kind}
    if kind == "article":
        paras = []
        body = root.find("body")
        for sec in body.findall("sec") if body is not None else []:
            title = (sec.findtext("title") or "").lower()
            if any(
                k in title
                for k in ("introduction", "background", "discussion", "conclusion")
            ):
                paras += [para_text(p) for p in sec.iter("p")]
        return windows(f"{r['pmcid']}-a", paras, meta)
    for sub in root.iter("sub-article"):
        if sub.get("article-type") in ("decision-letter", "referee-report"):
            paras = [para_text(p) for p in sub.iter("p")]
            paras = [p for p in paras if not p.startswith("Thank you for submitting")]
            return windows(f"{r['pmcid']}-r", paras, meta)
    return []
