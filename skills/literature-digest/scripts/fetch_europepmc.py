"""Fetch Europe PMC records in a date range, filtered by Ersilia-relevant keywords.

API: https://www.ebi.ac.uk/europepmc/webservices/rest/search
Docs: https://europepmc.org/RestfulWebService

The keyword query is composed from `references/search-landscape.md`. We don't parse that
file here — the keywords are duplicated below as a sealed v1 set; refresh manually when the
landscape changes. (Phase 2: read keywords from search-landscape.md at runtime.)

Usage:
    python fetch_europepmc.py --from 2026-05-13 --to 2026-05-20 --out /tmp/epmc.json
    python fetch_europepmc.py --from 2026-05-13 --to 2026-05-20 --out /tmp/epmc.json --max-pages 5
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import requests

from _common import (
    normalise_doi,
    parse_date,
    validate_item,
    warn,
    write_json,
)

# v1 sealed keyword set. One term per OR clause; the three groups are AND-joined.
METHODS = [
    "machine learning", "deep learning", "neural network", "generative model",
    "diffusion model", "graph neural network", "foundation model", "language model",
    "QSAR", "cheminformatics", "virtual screening", "molecular generation",
    "de novo design", "active learning", "knowledge graph", "embedding",
    "transformer", "docking", "free energy", "AlphaFold", "Boltz",
]

DISEASES_AND_ENDPOINTS = [
    "drug discovery", "drug design", "antimalarial", "antimicrobial",
    "antibiotic", "antiviral", "antiparasitic", "ADMET", "toxicity",
    "Plasmodium", "Mycobacterium tuberculosis", "tuberculosis", "malaria",
    "Klebsiella", "Acinetobacter", "ESKAPE", "neglected tropical disease",
    "schistosomiasis", "leishmaniasis", "trypanosomiasis", "Chagas",
    "antimicrobial resistance", "AMR", "molecular glue", "PROTAC",
    "targeted protein degradation", "hit identification", "lead optimization",
]


def build_query(start: str, end: str) -> str:
    def or_join(terms: list[str]) -> str:
        return "(" + " OR ".join(f"\"{t}\"" for t in terms) + ")"
    return (
        f"FIRST_PDATE:[{start} TO {end}] "
        f"AND {or_join(METHODS)} "
        f"AND {or_join(DISEASES_AND_ENDPOINTS)}"
    )


def fetch_page(query: str, cursor_mark: str) -> dict[str, Any]:
    params = {
        "query": query,
        "format": "json",
        "resultType": "core",
        "pageSize": 100,
        "cursorMark": cursor_mark,
    }
    headers = {"User-Agent": "ersilia-literature-digest/1.0"}
    resp = requests.get(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params=params,
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def extract_authors(rec: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    author_list = (rec.get("authorList") or {}).get("author") or []
    for a in author_list:
        name = a.get("fullName") or a.get("collectiveName") or ""
        if not name:
            continue
        # `affiliation` is a string; some records carry `authorAffiliationDetailsList`.
        aff = a.get("affiliation")
        if not aff:
            details = (a.get("authorAffiliationDetailsList") or {}).get("authorAffiliation") or []
            if details and isinstance(details, list):
                aff = details[0].get("affiliation")
        out.append({"name": name, "affiliation": aff or None, "country": None})
    return out


def normalise_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    title = (rec.get("title") or "").strip().rstrip(".")
    if not title:
        return None
    authors = extract_authors(rec)
    if not authors:
        return None
    doi = normalise_doi(rec.get("doi"))
    pmid = rec.get("pmid")
    if doi:
        url = f"https://doi.org/{doi}"
    elif pmid:
        url = f"https://europepmc.org/article/MED/{pmid}"
    elif rec.get("pmcid"):
        url = f"https://europepmc.org/article/PMC/{rec['pmcid']}"
    else:
        return None

    # Prefer the structured journal title; fall back through the chain.
    journal_info = (rec.get("journalInfo") or {}).get("journal") or {}
    venue = (
        journal_info.get("title")
        or rec.get("journalTitle")
        or rec.get("bookOrReportDetails", {}).get("publisher")
        or rec.get("source")
        or "Europe PMC"
    )

    return {
        "title": title,
        "authors": authors,
        "venue": venue,
        "date": rec.get("firstPublicationDate") or rec.get("electronicPublicationDate") or "",
        "doi": doi,
        "url": url,
        "abstract": (rec.get("abstractText") or "").strip() or None,
        "source": "europepmc",
        "source_subtype": rec.get("pubType") or rec.get("source") or None,
        "raw": rec,
    }


def fetch_range(start_date: str, end_date: str, max_pages: int) -> list[dict[str, Any]]:
    query = build_query(start_date, end_date)
    items: list[dict[str, Any]] = []
    cursor_mark = "*"
    seen_cursor: set[str] = set()
    for page in range(max_pages):
        try:
            payload = fetch_page(query, cursor_mark)
        except requests.RequestException as e:
            warn(f"europepmc request failed at page={page}: {e}")
            break
        records = (payload.get("resultList") or {}).get("result") or []
        for rec in records:
            normalised = normalise_record(rec)
            if not normalised:
                continue
            errs = validate_item(normalised)
            if errs:
                warn(f"europepmc item dropped: {'; '.join(errs)} — {normalised.get('title','?')[:80]}")
                continue
            items.append(normalised)
        next_cursor = payload.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor_mark or next_cursor in seen_cursor:
            break
        seen_cursor.add(cursor_mark)
        cursor_mark = next_cursor
        time.sleep(0.2)  # 10 req/s permitted; stay well under.
    return items


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from", dest="dfrom", required=True, help="Start date YYYY-MM-DD (inclusive).")
    p.add_argument("--to", dest="dto", required=True, help="End date YYYY-MM-DD (inclusive).")
    p.add_argument("--out", required=True, help="Output JSON path.")
    p.add_argument("--max-pages", type=int, default=10,
                   help="Hard cap on pages to fetch (default: 10 = up to 1000 items).")
    args = p.parse_args(argv)

    try:
        start = parse_date(args.dfrom)
        end = parse_date(args.dto)
    except ValueError as e:
        warn(f"bad date: {e}")
        write_json(args.out, [])
        return 0

    if start > end:
        warn(f"--from ({start}) is after --to ({end}); emitting empty result")
        write_json(args.out, [])
        return 0

    items = fetch_range(start.isoformat(), end.isoformat(), args.max_pages)
    write_json(args.out, items)
    print(f"europepmc: wrote {len(items)} items to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
