#!/usr/bin/env python3
"""fetch_month_models.py — everything a month's report needs, from a YYYY-MM.

    python fetch_month_models.py 2026-08 --out month-context.json

Reads the Hub's own catalogue (a single JSON on S3 carrying all 254+ models with their
metadata), keeps the models whose ``Incorporation Date`` falls in the month, then resolves
each one's publication against Crossref and OpenAlex for the ordered author list and the
abstract.

It also records **who the authors are, in order**. OpenAlex tags first/middle/last, which is
what lets the digest credit the right people without guessing.

Deterministic apart from the network, and standard library only.
"""

from __future__ import annotations

import argparse
import calendar
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    build_credit,
    die,
    fetch_crossref,
    fetch_json,
    fetch_openalex,
    normalise_doi,
    reconstruct_abstract,
    warn,
    write_json,
)

# The Hub publishes its whole catalogue here — one request instead of one per repository.
CATALOG_URL = "https://ersilia-model-hub.s3.eu-central-1.amazonaws.com/models.json"

MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


def parse_month(value):
    """Validate a ``YYYY-MM`` string and return ``(year, month, label)``."""
    match = MONTH_RE.match(str(value).strip())
    if not match:
        die(f"{value!r} is not a month (expected YYYY-MM, e.g. 2026-08)")
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        die(f"{value!r} has no such month")
    return year, month, f"{calendar.month_name[month]} {year}"


def previous_month(today=None):
    """Return the last complete month as ``YYYY-MM`` — the report's default scope."""
    today = today or date.today()
    year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    return f"{year:04d}-{month:02d}"


def resolve_one(entry):
    """Build the report's per-model record: metadata, publication and ordered credit."""
    identifier = entry.get("Identifier")
    doi = normalise_doi(entry.get("Publication"))
    crossref = fetch_crossref(doi) if doi else None
    openalex = fetch_openalex(doi) if doi else None
    if not doi:
        warn(f"{identifier}: no DOI resolvable from {entry.get('Publication')!r}")

    publication = {
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}" if doi else None,
        "raw_publication_field": entry.get("Publication"),
        "title": (crossref or {}).get("title", [None])[0]
        or (openalex or {}).get("title"),
        "journal": (crossref or {}).get("container-title", [None])[0],
        "year": entry.get("Publication Year"),
        "type": entry.get("Publication Type"),
        "open_access": ((openalex or {}).get("open_access") or {}).get("oa_status"),
        "cited_by_count": (openalex or {}).get("cited_by_count"),
        "abstract": reconstruct_abstract(openalex, crossref),
    }

    return {
        "identifier": identifier,
        "model": {
            "slug": entry.get("Slug"),
            "title": entry.get("Title"),
            "description": entry.get("Description"),
            "interpretation": entry.get("Interpretation"),
            "task": entry.get("Task"),
            "subtask": entry.get("Subtask"),
            "output_dimension": entry.get("Output Dimension"),
            "tags": entry.get("Tag"),
            "biomedical_area": entry.get("Biomedical Area"),
            "target_organism": entry.get("Target Organism"),
            "license": entry.get("License"),
            "status": entry.get("Status"),
            "source_type": entry.get("Source Type"),
            "source_code": entry.get("Source Code"),
            "incorporation_date": entry.get("Incorporation Date"),
            "github": entry.get("GitHub") or f"https://github.com/ersilia-os/{identifier}",
            "dockerhub": entry.get("DockerHub"),
        },
        "publication": publication,
        "credit": build_credit(openalex, crossref),
    }


def hub_size_at(catalog, last_day):
    """How many models had been incorporated by ``last_day`` (a ``YYYY-MM-DD`` string).

    Not ``len(catalog)``. That counts every row — models still in progress, models since
    archived — and it is a snapshot of whenever the fetch ran, so it drifts every time the
    same month is re-rendered. A digest reports on a month, so its total is the month's:
    a historical count from the incorporation dates, which does not move.

    Deliberately not filtered by `Status`, which is a *current* field. "Incorporated by 31
    August and Ready today" mixes two points in time and would quietly shrink as models are
    archived.
    """
    return sum(
        1
        for entry in catalog
        if entry.get("Incorporation Date")
        and str(entry["Incorporation Date"])[:10] <= last_day
    )


def tally(models, key):
    """Count models by a `model` sub-key, for the report's summary line."""
    counts = {}
    for record in models:
        value = record["model"].get(key) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "month", nargs="?", help="month to report on as YYYY-MM (default: last complete month)"
    )
    parser.add_argument("--out", required=True, help="path to write the month context JSON")
    args = parser.parse_args(argv)

    month = args.month or previous_month()
    year, month_num, label = parse_month(month)
    last_day = f"{year:04d}-{month_num:02d}-{calendar.monthrange(year, month_num)[1]:02d}"

    catalog = fetch_json(CATALOG_URL)
    if not isinstance(catalog, list):
        die(f"catalogue at {CATALOG_URL} did not return a list of models")

    entries = [
        e for e in catalog if str(e.get("Incorporation Date") or "").startswith(month)
    ]
    entries.sort(key=lambda e: (str(e.get("Incorporation Date")), str(e.get("Identifier"))))

    print(
        f"{label}: {len(entries)} of {len(catalog)} catalogued models incorporated; "
        f"resolving publications…",
        file=sys.stderr,
    )

    models = []
    for entry in entries:
        record = resolve_one(entry)
        models.append(record)
        print(
            f"  {record['identifier']}  {record['credit']['n_authors']:>2} authors",
            file=sys.stderr,
        )

    context = {
        "month": month,
        "month_label": label,
        "catalog_url": CATALOG_URL,
        "catalog_size": len(catalog),          # every row today, in-progress ones included
        "hub_size_at_month_end": hub_size_at(catalog, last_day),
        "month_last_day": last_day,
        "n_models": len(models),
        "by_task": tally(models, "task"),
        "by_status": tally(models, "status"),
        "n_global_south": sum(1 for m in models if m["credit"]["has_global_south_author"]),
        "models": models,
    }
    write_json(args.out, context)
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
