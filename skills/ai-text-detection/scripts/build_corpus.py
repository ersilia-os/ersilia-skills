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
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lib.common import REFS, warn, write_jsonl
from lib.europepmc import (
    OPEN_BEFORE_CHATGPT,
    base_meta,
    fulltext_windows,
    search,
    windows,
)
from lib.http import post_json
from lib.text import words

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


def abstracts(n: int, rng: random.Random) -> list[dict]:
    """One window per CC-BY abstract (2015-2021), spread over the topics."""
    out: list[dict] = []
    per = max(1, n // len(TOPICS))
    for topic in TOPICS:
        q = f'"{topic}" AND {OPEN_BEFORE_CHATGPT} AND HAS_ABSTRACT:y'
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


def articles_and_reviews(
    n_articles: int, n_reviews: int, rng: random.Random
) -> list[dict]:
    """Full-text windows of CC-BY papers and of eLife decision letters, fetched in parallel."""
    cands: list[tuple[dict, str]] = []
    for topic in TOPICS:
        q = f'"{topic}" AND {OPEN_BEFORE_CHATGPT} AND HAS_FT:y AND NOT JOURNAL:"eLife"'
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


GRANT_TERMS = [
    "antimicrobial resistance",
    "malaria",
    "tuberculosis drug",
    "drug discovery machine learning",
    "neglected tropical disease",
    "antibiotic",
    "global health",
    "cheminformatics",
]
GRANT_HEADING = re.compile(
    r"^\s*(PROJECT SUMMARY(?:/ABSTRACT)?|SUMMARY|ABSTRACT|Project Summary/Abstract|DESCRIPTION \(provided by applicant\))[:\s]*",
    re.IGNORECASE,
)
ENGLISH_SPEAKING = ("UNITED STATES", "USA", "UNITED KINGDOM", "CANADA", "AUSTRALIA")


def reporter_projects(term: str, limit: int) -> list[dict]:
    """NIH RePORTER projects (fiscal years 2015-2021) whose abstract matches ``term``."""
    query = {
        "criteria": {
            "advanced_text_search": {
                "operator": "and",
                "search_field": "abstracttext",
                "search_text": term,
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
        "limit": limit,
    }
    try:
        data = post_json("https://api.reporter.nih.gov/v2/projects/search", query)
    except Exception as e:  # noqa: BLE001 - network: skip this term
        warn(f"RePORTER {term}: {e}")
        return []
    return data.get("results", [])


def grants(n: int) -> list[dict]:
    """Windows from NIH RePORTER abstracts, fiscal years 2015-2021."""
    out: list[dict] = []
    for term in GRANT_TERMS:
        for p in reporter_projects(term, max(1, n // len(GRANT_TERMS))):
            text = GRANT_HEADING.sub("", (p.get("abstract_text") or "").strip())
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
                    in ENGLISH_SPEAKING,
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
    write_jsonl(out, rows)
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
