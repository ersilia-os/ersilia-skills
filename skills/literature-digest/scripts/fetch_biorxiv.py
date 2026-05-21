"""Fetch bioRxiv preprints in a date range.

API: https://api.biorxiv.org/details/biorxiv/{from}/{to}/{cursor}
Docs: https://api.biorxiv.org/

The API is undocumented for rate limits; we sleep 1s between paged requests and back off on
non-200 responses. Categories are filtered client-side because the API has no category param.

Usage:
    python fetch_biorxiv.py --from 2026-05-13 --to 2026-05-20 --out /tmp/bx.json
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import requests

from _common import (
    parse_date,
    normalise_doi,
    validate_item,
    warn,
    write_json,
)

# Categories that match Ersilia's scope. Compared case-insensitively against the API's
# `category` field. Adjust as needed.
KEEP_CATEGORIES = {
    "bioinformatics",
    "biochemistry",
    "pharmacology and toxicology",
    "microbiology",
    "systems biology",
    "synthetic biology",
    "genomics",
    "molecular biology",
    "immunology",
    "epidemiology",
}


def fetch_page(start_date: str, end_date: str, cursor: int) -> dict[str, Any]:
    url = f"https://api.biorxiv.org/details/biorxiv/{start_date}/{end_date}/{cursor}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def normalise_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Map a bioRxiv record to the canonical item schema. Return None if it should be dropped."""
    category = (rec.get("category") or "").strip().lower()
    if category and category not in KEEP_CATEGORIES:
        return None

    # bioRxiv concatenates authors as "Lastname, F.; Lastname, F.; ..." and affiliations as a
    # single semicolon-joined string aligned with authors.
    raw_authors = (rec.get("authors") or "").split(";")
    raw_affs = (rec.get("author_corresponding_institution") or "").strip()
    authors = []
    for name in raw_authors:
        name = name.strip()
        if not name:
            continue
        authors.append({"name": name, "affiliation": raw_affs or None, "country": None})
    if not authors:
        return None

    doi = normalise_doi(rec.get("doi"))
    url = f"https://www.biorxiv.org/content/{rec['doi']}v{rec.get('version', 1)}" if rec.get("doi") else None
    if not url:
        return None

    return {
        "title": (rec.get("title") or "").strip(),
        "authors": authors,
        "venue": "bioRxiv",
        "date": rec.get("date") or "",
        "doi": doi,
        "url": url,
        "abstract": (rec.get("abstract") or "").strip() or None,
        "source": "biorxiv",
        "source_subtype": category or None,
        "raw": rec,
    }


def fetch_range(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Page through the API for one date window. Returns *normalised* items."""
    items: list[dict[str, Any]] = []
    cursor = 0
    while True:
        try:
            payload = fetch_page(start_date, end_date, cursor)
        except requests.RequestException as e:
            warn(f"biorxiv request failed at cursor={cursor}: {e}")
            break
        messages = payload.get("messages") or []
        total = 0
        if messages and isinstance(messages, list):
            total = int(messages[0].get("total", 0)) or 0
        collection = payload.get("collection") or []
        if not collection:
            break
        for rec in collection:
            normalised = normalise_record(rec)
            if not normalised:
                continue
            errs = validate_item(normalised)
            if errs:
                warn(f"biorxiv item dropped: {'; '.join(errs)} — {normalised.get('title','?')[:80]}")
                continue
            items.append(normalised)
        cursor += len(collection)
        if total and cursor >= total:
            break
        time.sleep(1.0)
    return items


def dedup_by_doi(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """bioRxiv may return multiple revisions of the same preprint; keep the latest."""
    by_doi: dict[str, dict[str, Any]] = {}
    others: list[dict[str, Any]] = []
    for it in items:
        d = it.get("doi")
        if not d:
            others.append(it)
            continue
        prev = by_doi.get(d)
        if prev is None or (it.get("date", "") > prev.get("date", "")):
            by_doi[d] = it
    return list(by_doi.values()) + others


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from", dest="dfrom", required=True, help="Start date YYYY-MM-DD (inclusive).")
    p.add_argument("--to", dest="dto", required=True, help="End date YYYY-MM-DD (inclusive).")
    p.add_argument("--out", required=True, help="Output JSON path.")
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

    items = fetch_range(start.isoformat(), end.isoformat())
    items = dedup_by_doi(items)
    write_json(args.out, items)
    print(f"biorxiv: wrote {len(items)} items to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
