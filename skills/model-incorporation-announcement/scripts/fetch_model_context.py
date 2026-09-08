#!/usr/bin/env python3
"""fetch_model_context.py — assemble everything an announcement needs, from an eos id.

    python fetch_model_context.py eos4e40 --out context.json

Reads the model's own metadata from GitHub, then resolves its publication DOI against
Crossref (title, journal, funders) and OpenAlex (the *ordered* author list, with
institutions and countries). The ordering is the point: OpenAlex tags each author
first/middle/last, which turns "always name the first and last author" from a
judgement call into a lookup.

Nothing is invented. Every field that could not be resolved is emitted as null and
reported on stderr, so the post is written from what is known rather than from what
would have been convenient.

Deterministic apart from the network, and standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    LMIC_ISO2,
    POLITE_MAILTO,
    die,
    fetch,
    fetch_json,
    normalise_doi,
    warn,
    write_json,
)

IDENTIFIER_RE = re.compile(r"^eos[1-9][a-z0-9]{3}$")

# Model repos live on either default branch, and carry either metadata form.
METADATA_CANDIDATES = (
    ("main", "metadata.json"),
    ("master", "metadata.json"),
    ("main", "metadata.yml"),
    ("master", "metadata.yml"),
)

RAW_TEMPLATE = "https://raw.githubusercontent.com/ersilia-os/{ident}/{branch}/{filename}"


def parse_simple_yaml(text):
    """Parse the flat ``Key: value`` / ``Key:``+``- item`` subset used by metadata.yml.

    Model metadata is a flat mapping of scalars and string lists — no nesting, no
    anchors — so a 20-line parser covers it and keeps the script dependency-free.
    Anything unexpected is skipped rather than guessed at.
    """
    data = {}
    current_list_key = None
    current_scalar_key = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s*-\s*(.*)$", line)
        if item and current_list_key:
            data[current_list_key].append(_scalar(item.group(1)))
            continue
        # Keys sit at column 0; an indented line that is not a list item continues the
        # previous scalar. Real metadata.yml files wrap long Descriptions and
        # Interpretations this way, and dropping the continuation silently truncates the
        # sentence mid-clause.
        pair = re.match(r"^([A-Za-z][A-Za-z0-9 _/-]*):\s*(.*)$", line)
        if not pair:
            if current_scalar_key and raw_line[:1].isspace():
                data[current_scalar_key] = f"{data[current_scalar_key]} {line.strip()}".strip()
            continue
        key, value = pair.group(1).strip(), pair.group(2).strip()
        current_list_key = current_scalar_key = None
        if value == "":
            current_list_key = key
            data[key] = []
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [_scalar(v) for v in inner.split(",")] if inner else []
        else:
            data[key] = _scalar(value)
            # Only strings can be continued; an int has nothing to fold onto.
            if isinstance(data[key], str):
                current_scalar_key = key
    return data


def _scalar(value):
    """Strip quotes and coerce bare integers, leaving everything else as a string."""
    text = str(value).strip().strip('"').strip("'").strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def load_model_metadata(identifier):
    """Fetch a model's metadata from GitHub, trying both branches and both formats.

    Returns ``(metadata_dict, source_url)``. Exits if no candidate resolves — without
    metadata there is no model to announce.
    """
    for branch, filename in METADATA_CANDIDATES:
        url = RAW_TEMPLATE.format(ident=identifier, branch=branch, filename=filename)
        body = fetch(url)
        if body is None:
            continue
        try:
            if filename.endswith(".json"):
                import json

                return json.loads(body), url
            return parse_simple_yaml(body), url
        except ValueError as exc:
            warn(f"{url} did not parse: {exc}")
    die(
        f"no readable metadata for {identifier} — checked metadata.json and metadata.yml "
        f"on main and master. Is the model repository public and merged?"
    )


def fetch_crossref(doi):
    """Return the Crossref record for ``doi``, or ``None``."""
    url = f"https://api.crossref.org/works/{doi}?mailto={POLITE_MAILTO}"
    payload = fetch_json(url)
    if not payload or "message" not in payload:
        warn(f"no Crossref record for {doi}")
        return None
    return payload["message"]


def fetch_openalex(doi):
    """Return the OpenAlex record for ``doi``, or ``None``."""
    url = f"https://api.openalex.org/works/doi:{doi}?mailto={POLITE_MAILTO}"
    payload = fetch_json(url)
    if not payload or "authorships" not in payload:
        warn(f"no OpenAlex record for {doi}")
        return None
    return payload


def reconstruct_abstract(openalex, crossref):
    """Rebuild the paper abstract, so the method paragraph can be fact-checked against it.

    OpenAlex stores abstracts as an inverted index (word -> positions); Crossref, when it
    has one at all, stores JATS XML. Both are handled, and ``None`` is returned when
    neither source carries one — patchy coverage is normal (publishers deposit abstracts
    inconsistently, and OpenAlex has none for many journal articles), so the caller must
    fall back to the paper itself rather than treating absence as "nothing to check".
    """
    inverted = (openalex or {}).get("abstract_inverted_index")
    if inverted:
        positions = {}
        for word, places in inverted.items():
            for place in places:
                positions[place] = word
        text = " ".join(positions[key] for key in sorted(positions))
    else:
        text = (crossref or {}).get("abstract") or ""
        text = re.sub(r"<[^>]+>", " ", text)

    if not text.strip():
        return None
    # Abstracts arrive with LaTeX and JATS debris that would confuse a fact-check.
    text = re.sub(r"\\(?:textbf|textit|emph|texttt|mathrm)\{([^}]*)\}", r"\1", text)
    text = text.replace("\\%", "%").replace("$", "")
    text = re.sub(r"^\s*Abstract[:\s]*", "", text, flags=re.I)
    return " ".join(text.split()) or None


def build_credit(openalex, crossref):
    """Assemble the author-credit block the post is written from.

    OpenAlex is preferred because it labels author position and carries institutions
    and countries; Crossref is the fallback for the name list alone. When neither
    resolves, every field is null and the skill must ask the user for the author list
    rather than proceeding.
    """
    credit = {
        "authors": [],
        "first_author": None,
        "last_author": None,
        "n_authors": 0,
        "lead_institutions": [],
        "countries": [],
        "has_global_south_author": False,
        "global_south_institutions": [],
        "source": None,
    }

    if openalex:
        credit["source"] = "openalex"
        for entry in openalex.get("authorships", []):
            author = entry.get("author") or {}
            institutions = [
                inst.get("display_name")
                for inst in entry.get("institutions", [])
                if inst.get("display_name")
            ]
            countries = [c for c in entry.get("countries", []) if c]
            credit["authors"].append(
                {
                    "name": author.get("display_name"),
                    "position": entry.get("author_position"),
                    "orcid": author.get("orcid"),
                    "institutions": institutions,
                    "countries": countries,
                    "is_corresponding": bool(entry.get("is_corresponding")),
                }
            )
    elif crossref:
        credit["source"] = "crossref"
        raw = crossref.get("author", []) or []
        for index, author in enumerate(raw):
            name = " ".join(p for p in (author.get("given"), author.get("family")) if p)
            position = "first" if index == 0 else ("last" if index == len(raw) - 1 else "middle")
            credit["authors"].append(
                {
                    "name": name or None,
                    "position": position,
                    "orcid": author.get("ORCID"),
                    "institutions": [
                        a.get("name") for a in author.get("affiliation", []) if a.get("name")
                    ],
                    "countries": [],
                    "is_corresponding": False,
                }
            )

    authors = credit["authors"]
    credit["n_authors"] = len(authors)
    if authors:
        credit["first_author"] = authors[0]["name"]
        credit["last_author"] = authors[-1]["name"] if len(authors) > 1 else None

    # Institutions in first/last-author order — the lab that owns the work leads the
    # sentence, so ordering here is editorial, not cosmetic.
    seen_inst = []
    for author in authors:
        for institution in author["institutions"]:
            if institution not in seen_inst:
                seen_inst.append(institution)
    credit["lead_institutions"] = seen_inst

    seen_country = []
    for author in authors:
        for country in author["countries"]:
            if country not in seen_country:
                seen_country.append(country)
    credit["countries"] = seen_country

    global_south = []
    for author in authors:
        if any(c in LMIC_ISO2 for c in author["countries"]):
            for institution in author["institutions"]:
                if institution not in global_south:
                    global_south.append(institution)
    credit["global_south_institutions"] = global_south
    credit["has_global_south_author"] = bool(global_south)

    corresponding = [a for a in authors if a.get("is_corresponding")]
    credit["corresponding_authors"] = [a["name"] for a in corresponding] or None

    return credit


def first_or_none(value):
    """Return the first element of a list-ish value, or the value itself, or None."""
    if isinstance(value, list):
        return value[0] if value else None
    return value or None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("identifier", help="Ersilia model identifier, e.g. eos4e40")
    parser.add_argument("--out", required=True, help="path to write the context JSON")
    args = parser.parse_args(argv)

    identifier = args.identifier.strip().lower()
    if not IDENTIFIER_RE.match(identifier):
        die(f"{args.identifier!r} is not an Ersilia model identifier (expected eosXXXX)")

    metadata, metadata_url = load_model_metadata(identifier)

    doi = normalise_doi(metadata.get("Publication"))
    if not doi:
        warn(
            f"Publication field {metadata.get('Publication')!r} carries no DOI — the author "
            f"list cannot be resolved automatically; ask the user for it"
        )
    crossref = fetch_crossref(doi) if doi else None
    openalex = fetch_openalex(doi) if doi else None

    publication = {
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}" if doi else None,
        "title": first_or_none((crossref or {}).get("title"))
        or ((openalex or {}).get("title")),
        "journal": first_or_none((crossref or {}).get("container-title"))
        or ((openalex or {}).get("host_venue") or {}).get("display_name"),
        "year": metadata.get("Publication Year"),
        "type": metadata.get("Publication Type"),
        "funders": [f.get("name") for f in (crossref or {}).get("funder", []) if f.get("name")],
        "open_access": ((openalex or {}).get("open_access") or {}).get("oa_status"),
        "open_access_url": ((openalex or {}).get("open_access") or {}).get("oa_url"),
        "cited_by_count": (openalex or {}).get("cited_by_count"),
        "abstract": reconstruct_abstract(openalex, crossref),
    }

    context = {
        "identifier": identifier,
        "metadata_url": metadata_url,
        "model": {
            "slug": metadata.get("Slug"),
            "title": metadata.get("Title"),
            "description": metadata.get("Description"),
            "interpretation": metadata.get("Interpretation"),
            "task": metadata.get("Task"),
            "subtask": metadata.get("Subtask"),
            "output": metadata.get("Output"),
            "output_dimension": metadata.get("Output Dimension"),
            "tags": metadata.get("Tag"),
            "biomedical_area": metadata.get("Biomedical Area"),
            "target_organism": metadata.get("Target Organism"),
            "license": metadata.get("License"),
            "status": metadata.get("Status"),
            "contributor": metadata.get("Contributor"),
            "incorporation_date": metadata.get("Incorporation Date"),
            "source_code": metadata.get("Source Code"),
            "source_type": metadata.get("Source Type"),
            "dockerhub": metadata.get("DockerHub"),
            "github": f"https://github.com/ersilia-os/{identifier}",
        },
        "publication": publication,
        "credit": build_credit(openalex, crossref),
    }

    write_json(args.out, context)
    credit = context["credit"]
    print(
        f"{identifier}: {credit['n_authors']} authors via {credit['source'] or 'no source'}; "
        f"wrote {args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
