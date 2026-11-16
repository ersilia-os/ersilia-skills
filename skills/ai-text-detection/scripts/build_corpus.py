"""Build the human calibration corpus: openly licensed scientific text written before ChatGPT.

Thresholds are only honest if they are measured on text like the text being judged. Three
kinds of human text, all published 2015-2021 (before ChatGPT's release on 30 Nov 2022):

    abstract  abstracts of CC-BY open-access papers (Europe PMC), one window each
    article   Introduction / Discussion paragraphs of CC-BY open-access papers (Europe PMC)
              in the fields Ersilia reads: drug discovery, AMR, malaria, TB, NTDs, global
              health, cheminformatics, machine learning in biology.
    review    eLife decision letters (reviewers' consolidated reports, CC-BY), from the
              same Europe PMC full texts.
    grant     NIH RePORTER project abstracts (public domain, US government works).

Each source document is cut into the same ~300-word windows as the documents under test.
The first author's affiliation country is kept, so the false-positive rate can be
reported separately for authors from non-English-speaking countries (the group detectors
are known to wrong, Liang et al. 2023).

Writes ``references/calibration/human.jsonl`` (one window per line:
{id, doc_id, kind, year, country, native_english, source_url, license, text}).

Usage:
    python build_corpus.py [--abstracts 600] [--articles 60] [--reviews 60] [--grants 300] [--out ...]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from lib.common import REFS, USER_AGENT, warn
from lib.text import chunks, words

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
TOPICS = [
    "antimicrobial resistance",
    "malaria drug discovery",
    "tuberculosis drug",
    "neglected tropical disease",
    "antibiotic discovery",
    "virtual screening",
    "QSAR machine learning",
    "cheminformatics",
    "global health",
    "drug repurposing",
    "deep learning molecules",
    "antiviral compounds",
]
NATIVE = re.compile(
    r"\b(USA|U\.S\.A|United States|UK|U\.K\.|United Kingdom|England|Scotland|Wales|Australia|Canada|New Zealand|Ireland)\b"
)
COUNTRY = re.compile(r",\s*([A-Z][A-Za-z .'-]{2,40})\.?\s*(?:[;.]|$)")


def get_json(url: str) -> dict | None:
    """GET JSON with retries."""
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - network: retry then give up
            if attempt == 2:
                warn(f"{url[:100]}: {e}")
                return None
            time.sleep(3)
    return None


def get_text(url: str) -> str | None:
    """GET text with retries."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                warn(f"{url[:100]}: {e}")
                return None
            time.sleep(3)
    return None


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
        for c in chunks(doc)
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


def abstracts(n: int, rng: random.Random) -> list[dict]:
    """One window per CC-BY abstract (2015-2021), spread over the topics."""
    out: list[dict] = []
    per = max(1, n // len(TOPICS))
    for topic in TOPICS:
        q = f'"{topic}" AND OPEN_ACCESS:y AND LICENSE:"cc by" AND PUB_YEAR:[2015 TO 2021] AND HAS_ABSTRACT:y'
        res = [
            r for r in search(q, 1) if len(words(r.get("abstractText") or "")) >= 150
        ]
        rng.shuffle(res)
        for r in res[:per]:
            text = re.sub(r"<[^>]+>", " ", r["abstractText"])
            text = re.sub(r"\s+", " ", text).strip()
            out += windows(
                f"abs-{r.get('pmcid') or r.get('pmid')}",
                [text],
                {**base_meta(r), "kind": "abstract"},
            )
        print(f"  abstracts {len(out)}", end="\r", flush=True)
    print()
    return out


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


def articles_and_reviews(
    n_articles: int, n_reviews: int, rng: random.Random
) -> list[dict]:
    """Full-text windows of CC-BY papers and of eLife decision letters, fetched in parallel."""
    from concurrent.futures import ThreadPoolExecutor

    cands: list[tuple[dict, str]] = []
    for topic in TOPICS:
        q = f'"{topic}" AND OPEN_ACCESS:y AND LICENSE:"cc by" AND PUB_YEAR:[2015 TO 2021] AND HAS_FT:y AND NOT JOURNAL:"eLife"'
        res = [r for r in search(q, 1) if r.get("pmcid")]
        rng.shuffle(res)
        cands += [(r, "article") for r in res[: -(-n_articles // len(TOPICS))]]
    q = '(malaria OR tuberculosis OR antibiotic OR "drug discovery" OR bacteria OR parasite) AND JOURNAL:"eLife" AND PUB_YEAR:[2015 TO 2021] AND HAS_FT:y'
    res = [r for r in search(q, 2) if r.get("pmcid")]
    rng.shuffle(res)
    cands += [(r, "review") for r in res[: int(n_reviews * 1.3) + 1]]
    out: list[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        for w in ex.map(lambda rk: fulltext_windows(*rk), cands):
            out += w
            done += 1
            print(f"  full texts {done}/{len(cands)}", end="\r", flush=True)
    print()
    return out


def grants(n: int) -> list[dict]:
    """Windows from NIH RePORTER abstracts, fiscal years 2015-2021."""
    out: list[dict] = []
    terms = [
        "antimicrobial resistance",
        "malaria",
        "tuberculosis drug",
        "drug discovery machine learning",
        "neglected tropical disease",
        "antibiotic",
        "global health",
        "cheminformatics",
    ]
    per = max(1, n // len(terms))
    for t in terms:
        body = json.dumps(
            {
                "criteria": {
                    "advanced_text_search": {
                        "operator": "and",
                        "search_field": "abstracttext",
                        "search_text": t,
                    },
                    "fiscal_years": [2015, 2016, 2017, 2018, 2019, 2020, 2021],
                },
                "include_fields": [
                    "ApplId",
                    "AbstractText",
                    "FiscalYear",
                    "Organization",
                    "ProjectTitle",
                ],
                "offset": 0,
                "limit": per,
            }
        ).encode()
        req = urllib.request.Request(
            "https://api.reporter.nih.gov/v2/projects/search",
            data=body,
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            warn(f"RePORTER {t}: {e}")
            continue
        for p in data.get("results", []):
            text = (p.get("abstract_text") or "").strip()
            text = re.sub(
                r"^\s*(PROJECT SUMMARY(?:/ABSTRACT)?|SUMMARY|ABSTRACT|Project Summary/Abstract|DESCRIPTION \(provided by applicant\))[:\s]*",
                "",
                text,
                flags=re.IGNORECASE,
            )
            org = p.get("organization") or {}
            paras = [
                x for x in re.split(r"\n\s*\n|\r\n\s*\r\n", text) if x.strip()
            ] or [text]
            out += windows(
                f"nih{p['appl_id']}",
                paras,
                {
                    "kind": "grant",
                    "year": p.get("fiscal_year"),
                    "country": org.get("org_country"),
                    "native_english": (org.get("org_country") or "").upper()
                    in (
                        "UNITED STATES",
                        "USA",
                        "UNITED KINGDOM",
                        "CANADA",
                        "AUSTRALIA",
                    ),
                    "source_url": f"https://reporter.nih.gov/project-details/{p['appl_id']}",
                    "license": "public domain (US government)",
                },
            )
        time.sleep(1)
    return out


def main(argv: list[str] | None = None) -> int:
    """Fetch the corpus and write human.jsonl."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--abstracts", type=int, default=600)
    p.add_argument("--articles", type=int, default=60)
    p.add_argument("--reviews", type=int, default=60)
    p.add_argument("--grants", type=int, default=300)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", default=str(REFS / "calibration" / "human.jsonl"))
    args = p.parse_args(argv)
    rng = random.Random(args.seed)
    rows = (
        abstracts(args.abstracts, rng)
        + articles_and_reviews(args.articles, args.reviews, rng)
        + grants(args.grants)
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    kinds: dict[str, int] = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    docs = len({r["doc_id"] for r in rows})
    nn = sum(1 for r in rows if r.get("native_english") is False)
    print(
        f"human corpus: {len(rows)} windows from {docs} documents {kinds}; {nn} windows by authors in non-English-speaking countries -> {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
