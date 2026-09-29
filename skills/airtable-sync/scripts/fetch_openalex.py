"""Fetch the OpenAlex works the Publications table is checked against.

Three lookups, all read-only against the public OpenAlex API:

1. **Discovery.** Every work affiliated with the Ersilia institution, plus every work
   by the team authors in `references/sources.json` from their ``since`` year. These are
   the candidates for new rows.
2. **Existing rows.** Each Airtable row with a DOI, looked up by DOI (50 per request),
   so Year and Journal can be checked and filled.
3. **Preprints.** Each Airtable row whose Status is Preprint, searched by title, so a
   published version can be proposed.

Writes ``{"works": [...], "by_doi": {doi: work}, "title_matches": {record_id: [...]},
"errors": [...]}``, where every work is reduced to the fields `plan_sync.py` uses.

Usage:
    python fetch_openalex.py --airtable /tmp/airtable_sync/publications.json \
        [--sources references/sources.json] [--out /tmp/airtable_sync/openalex.json]
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse

from _common import (
    POLITE_MAILTO,
    SKILL_DIR,
    WORK_DIR,
    die,
    fetch_json,
    normalise_doi,
    read_json,
    write_json,
)

API = "https://api.openalex.org/works"
SELECT = "id,doi,title,publication_year,type,primary_location,authorships"


def compact(work: dict, institution: str) -> dict:
    """Reduce an OpenAlex work to the fields the planner compares."""
    loc = work.get("primary_location") or {}
    src = loc.get("source") or {}
    inst_url = f"https://openalex.org/{institution}"
    authors, inst_hit, author_ids, ersilia_ids, senior_ids = [], False, [], [], []
    countries: set[str] = set()
    ships = work.get("authorships") or []
    for k, a in enumerate(ships):
        aid = ((a.get("author") or {}).get("id") or "").rsplit("/", 1)[-1]
        authors.append((a.get("author") or {}).get("display_name") or "")
        author_ids.append(aid)
        insts = a.get("institutions") or []
        countries.update(i.get("country_code") for i in insts if i.get("country_code"))
        if any(i.get("id") == inst_url for i in insts):
            inst_hit = True
            ersilia_ids.append(aid)
        last = a.get("author_position") == "last" or k == len(ships) - 1
        if last or a.get("is_corresponding"):
            senior_ids.append(aid)
    return {
        "openalex_id": (work.get("id") or "").rsplit("/", 1)[-1],
        "doi": normalise_doi(work.get("doi")),
        "title": work.get("title") or "",
        "year": work.get("publication_year"),
        "type": work.get("type"),
        "source_name": src.get("display_name"),
        "source_type": src.get("type"),
        "landing_url": loc.get("landing_page_url"),
        "authors": [a for a in authors if a],
        "author_ids": [a for a in author_ids if a],
        "institution_hit": inst_hit,
        "ersilia_author_ids": [a for a in ersilia_ids if a],
        "senior_author_ids": [a for a in senior_ids if a],
        "countries": sorted(countries),
    }


def paged(filter_expr: str, errors: list[str]) -> list[dict]:
    """Return every work matching an OpenAlex filter, following cursor pagination."""
    works, cursor = [], "*"
    while cursor:
        q = urllib.parse.urlencode(
            {
                "filter": filter_expr,
                "per_page": 200,
                "cursor": cursor,
                "select": SELECT,
                "mailto": POLITE_MAILTO,
            }
        )
        data = fetch_json(f"{API}?{q}")
        if data is None:
            errors.append(f"OpenAlex query failed: {filter_expr}")
            break
        works.extend(data.get("results") or [])
        cursor = (data.get("meta") or {}).get("next_cursor")
    return works


def main(argv: list[str] | None = None) -> int:
    """Write the OpenAlex snapshot to the work directory."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--airtable", default=f"{WORK_DIR}/publications.json")
    p.add_argument("--sources", default=str(SKILL_DIR / "references" / "sources.json"))
    p.add_argument("--out", default=f"{WORK_DIR}/openalex.json")
    args = p.parse_args(argv)

    rows = read_json(args.airtable)
    if rows is None:
        die(f"missing {args.airtable}; run normalise_airtable.py first")
    cfg = read_json(args.sources)["openalex"]
    inst = cfg["institution"]
    errors: list[str] = []

    raw: dict[str, dict] = {}
    for w in paged(f"authorships.institutions.id:{inst}", errors):
        raw[w["id"]] = w
    for a in cfg["authors"]:
        for w in paged(
            f"authorships.author.id:{a['id']},publication_year:>{a['since'] - 1}",
            errors,
        ):
            raw[w["id"]] = w
    excluded = set(cfg.get("exclude_types", []))
    works = [compact(w, inst) for w in raw.values() if w.get("type") not in excluded]

    dois = sorted({d for d in (normalise_doi(r.get("doi")) for r in rows) if d})
    by_doi: dict[str, dict] = {}
    for i in range(0, len(dois), 50):
        for w in paged("doi:" + "|".join(dois[i : i + 50]), errors):
            c = compact(w, inst)
            if c["doi"]:
                by_doi[c["doi"]] = c

    title_matches: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("status") != "Preprint" or not r.get("title"):
            continue
        q = urllib.parse.urlencode(
            {
                "search": r["title"],
                "per_page": 5,
                "select": SELECT,
                "mailto": POLITE_MAILTO,
            }
        )
        data = fetch_json(f"{API}?{q}")
        if data is None:
            errors.append(f"title search failed for {r['id']}")
            continue
        title_matches[r["id"]] = [compact(w, inst) for w in data.get("results") or []]

    write_json(
        args.out,
        {
            "works": works,
            "by_doi": by_doi,
            "title_matches": title_matches,
            "errors": errors,
        },
    )
    print(
        f"openalex: {len(works)} discovered works, {len(by_doi)}/{len(dois)} DOIs resolved, "
        f"{len(title_matches)} preprints searched -> {args.out}"
    )
    for e in errors:
        print(f"  partial: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
