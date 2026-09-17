#!/usr/bin/env python3
"""fetch_month_models.py — everything a month's report needs, from a YYYY-MM.

    python fetch_month_models.py 2026-08 --out month-context.json

Reads the Hub's own catalogue (a single JSON on S3 carrying all 254+ models with their
metadata), keeps the models whose ``Incorporation Date`` falls in the month, then resolves
each one's publication against Crossref and OpenAlex for the ordered author list and the
abstract.

Two things it does beyond fetching:

* It records **who the authors are, in order**. OpenAlex tags first/middle/last, which is
  what lets the digest credit the right people without guessing.
* It records **metadata defects** per model — a placeholder Interpretation, a Publication
  field that is not a DOI, a Description outside the enforced length, and a Publication
  Type that disagrees with what the publication record actually says. An internal report
  is the right place for these to surface, because someone reading it can go and fix them.

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

# Text the eos template ships with. A model still carrying it was never filled in.
PLACEHOLDER_MARKERS = (
    "should be interpreted like this",
    "this template model",
    "interpretation 1",
    "description 1",
    "biomedical area 1",
)

# `ersilia test` enforces this range on Description; see model-incorporation-metadata.
DESCRIPTION_MIN, DESCRIPTION_MAX = 200, 600

# arXiv mints a DOI under this prefix. A model citing one is citing a preprint, which is
# fine until the paper is published — and nobody goes back to update the metadata, so the
# scan says so every month until it is fixed.
ARXIV_DOI_PREFIX = "10.48550/arxiv"


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


def find_defects(entry, openalex=None):
    """List the metadata problems worth raising for one model.

    Every check here corresponds to a rule in `/model-incorporation-metadata`, so a defect
    is a bug in that step rather than a judgement call about this one.

    ``openalex`` is the resolved publication record, when there is one. It carries the
    publisher's own view of what the paper is, which is the only way to check the
    `Publication Type` field against anything other than itself.
    """
    defects = []

    status = str(entry.get("Status") or "").strip()
    if status != "Ready":
        defects.append(f"Status is {status or 'empty'}, not Ready")

    interpretation = str(entry.get("Interpretation") or "").strip()
    if not interpretation:
        defects.append("Interpretation is empty")
    elif any(marker in interpretation.lower() for marker in PLACEHOLDER_MARKERS):
        defects.append("Interpretation still carries the template placeholder text")
    elif ":" in interpretation:
        # A colon breaks metadata.yml parsing unless the value is quoted.
        defects.append("Interpretation contains a colon, which is a metadata.yml hazard")

    description = str(entry.get("Description") or "").strip()
    if not description:
        defects.append("Description is empty")
    elif any(marker in description.lower() for marker in PLACEHOLDER_MARKERS):
        defects.append("Description still carries the template placeholder text")
    elif not DESCRIPTION_MIN <= len(description) <= DESCRIPTION_MAX:
        defects.append(
            f"Description is {len(description)} characters, outside the enforced "
            f"{DESCRIPTION_MIN}–{DESCRIPTION_MAX}"
        )

    publication = str(entry.get("Publication") or "").strip()
    if not publication:
        defects.append("Publication is empty")
    elif not publication.startswith(("https://doi.org/", "http://doi.org/")):
        derived = normalise_doi(publication)
        if derived:
            defects.append(
                f"Publication is not a DOI URL ({publication}); it resolves to "
                f"https://doi.org/{derived}, which is what the field should hold"
            )
        else:
            defects.append(f"Publication is not a DOI URL and no DOI could be derived ({publication})")

    if not entry.get("Output Dimension"):
        defects.append("Output Dimension is missing")

    defects.extend(_publication_defects(entry, openalex))

    return defects


def _publication_defects(entry, openalex):
    """Check `Publication Type` against what the publication record actually says.

    Both of these were found by hand before they were checks. August 2026 is the worked
    case: eos5g6m's metadata claimed `Peer reviewed` over an arXiv DOI that OpenAlex
    reports as a preprint, and a peer-reviewed version had in fact appeared.
    """
    defects = []
    doi = normalise_doi(entry.get("Publication")) or ""
    declared = str(entry.get("Publication Type") or "").strip()
    actual = (openalex or {}).get("type")

    if doi.lower().startswith(ARXIV_DOI_PREFIX):
        defects.append(
            f"Publication cites an arXiv preprint ({doi}) — check whether a peer-reviewed "
            f"version has appeared since, and cite that instead"
        )

    if actual and declared:
        is_preprint = actual == "preprint"
        says_preprint = declared.lower() == "preprint"
        if is_preprint and not says_preprint:
            defects.append(
                f"Publication Type is {declared!r} but the publication record reports a "
                f"preprint — one of the two is wrong"
            )
        elif says_preprint and not is_preprint:
            defects.append(
                f"Publication Type is 'Preprint' but the publication record reports "
                f"{actual!r} — the published version is what the field should carry"
            )

    return defects


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
        "defects": find_defects(entry, openalex),
    }


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
    _, _, label = parse_month(month)

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
            f"  {record['identifier']}  {record['credit']['n_authors']:>2} authors  "
            f"{len(record['defects'])} defect(s)",
            file=sys.stderr,
        )

    context = {
        "month": month,
        "month_label": label,
        "catalog_url": CATALOG_URL,
        "catalog_size": len(catalog),
        "n_models": len(models),
        "by_task": tally(models, "task"),
        "by_status": tally(models, "status"),
        "n_with_defects": sum(1 for m in models if m["defects"]),
        "n_global_south": sum(1 for m in models if m["credit"]["has_global_south_author"]),
        "models": models,
    }
    write_json(args.out, context)
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
