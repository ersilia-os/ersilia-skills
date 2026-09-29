"""Shared helpers for the airtable-sync scripts.

Standard library only. The Airtable field IDs live here, once, because every script
needs them and a field *name* can be renamed in the Airtable UI while its ID cannot.
`references/airtable-tables.md` documents the same map for humans; keep them in step.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

BASE_ID = "app1iYv78K6xbHkmL"  # Ersilia Content
WORK_DIR = "/tmp/airtable_sync"
POLITE_MAILTO = "miquel@ersilia.io"
SKILL_DIR = Path(__file__).resolve().parent.parent

# Per table: Airtable table ID, and field key -> (field ID, kind). `kind` tells the
# normaliser how to flatten the connector's cell value.
TABLES: dict[str, dict] = {
    "repositories": {
        "id": "tbluZtI3W9pseCSPH",
        "fields": {
            "name": ("fldtnOlLM2rqUZQpr", "text"),
            "title": ("fldYNOnc9KYHcQb7B", "text"),
            "description": ("fldBrXumaKuyUcgnH", "text"),
            "status": ("fldbqy6izSeIK4L7M", "multi"),
            "type": ("fldaYAL5URJa3gnRB", "multi"),
            "visibility": ("fldXhoqkmBs6ZRhnn", "single"),
            "projects": ("fldLxYAsHn1MDlOh4", "links"),
            "creation_date": ("fldBH2270474FY9XW", "text"),
        },
    },
    "publications": {
        "id": "tbljYubYjWAtO1ab8",
        "fields": {
            "slug": ("fldBcOxnF9AnbzfAA", "text"),
            "scholar_id": ("fldGKuzyPoWBt3ZBn", "text"),
            "authors": ("fldFQp6L6ErpBSTyS", "text"),
            "title": ("flddeYa3EUx5eWVXL", "text"),
            "journal": ("fldmvLkFLT7v3qrew", "text"),
            "url": ("fldMEidEAHAQEyrDr", "text"),
            "doi": ("fldHf5iG5y5Ub4Cym", "text"),
            "status": ("fldAvDFvtrpgNgcIo", "single"),
            "year": ("fldP37UlUVMWE9y2M", "single"),
            "affiliation": ("fldpo1rqH3ALxm4J0", "single"),
            "senior": ("fldSjwNhFJonAK04F", "single"),
            "topic": ("fldM4DFkZnjxP9e6o", "single"),
            "type": ("fldfcaghlytTH0AOU", "single"),
            "african_collaboration": ("fldLFGg2jkcP0IfGR", "single"),
        },
    },
    "blogposts": {
        "id": "tblsBj6ZoDNMlmrzm",
        "fields": {
            "slug": ("fldXbpkgq9bE5lQSL", "text"),
            "title": ("fldy4IdDdGDlvusvx", "text"),
            "date": ("fldiJWivfdBCU0EBb", "text"),
            "url": ("fldx3jkvfVcjP7Akv", "text"),
            "author": ("fldsEdAuhkSboI9kU", "links"),
            "publisher": ("fld8HeAV2SiYL7vLw", "single"),
            "category": ("fld5t5MIGbE6e8G2B", "multi"),
        },
    },
    "community": {
        "id": "tblS9TeBRYUpLwSCk",
        "fields": {
            "name": ("fldMkjzLdEO4gNnZo", "text"),
        },
    },
}

# Fields the ersilia-stats site reads from each table. An empty one silently drops the
# row out of a chart, so it is reported as a gap for a person to fill.
STATS_FIELDS: dict[str, list[str]] = {
    "repositories": ["status", "type", "visibility", "creation_date"],
    "publications": [
        "year",
        "journal",
        "doi",
        "status",
        "type",
        "affiliation",
        "topic",
        "african_collaboration",
    ],
    "blogposts": ["date", "publisher", "category"],
}

# ISO 3166-1 alpha-2 codes of African countries, for the Publications field
# "African collaboration" (any author at an institution in one of these).
AFRICA_ISO2 = frozenset(
    """
    DZ AO BJ BW BF BI CV CM CF TD KM CD CG CI DJ EG GQ ER SZ ET GA GM GH GN GW KE LS LR
    LY MG MW ML MR MU MA MZ NA NE NG RW ST SN SC SL SO ZA SS SD TZ TG TN UG ZM ZW EH
    """.split()
)

# Model repositories live in the "Ersilia Model Hub" base, never in Repositories.
# Stricter than ^eos[0-9a-z]{4}$ on purpose: eosvc, eosbench, eosdev... are not models.
MODEL_REPO_RE = re.compile(r"^eos[0-9][0-9a-z]{3}$")


def field_id(table: str, key: str) -> str:
    """Return the Airtable field ID for ``key`` in ``table``."""
    return TABLES[table]["fields"][key][0]


def warn(message: str) -> None:
    """Print a warning to stderr."""
    print(f"WARNING: {message}", file=sys.stderr, flush=True)


def die(message: str) -> None:
    """Print an error to stderr and exit 1."""
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


def read_json(path: str | Path) -> Any:
    """Read JSON from ``path``; return None if the file is missing or empty."""
    p = Path(path).expanduser()
    if not p.exists() or p.stat().st_size == 0:
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    """Write ``data`` as indented JSON, creating parent directories."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def fetch(url: str, timeout: int = 30) -> str | None:
    """GET ``url`` and return the body as text, or None on any network error."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (ersilia-skills)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        warn(f"fetch failed for {url}: {exc}")
        return None


def fetch_json(url: str, timeout: int = 30) -> Any:
    """GET ``url`` and parse JSON, or None on failure."""
    body = fetch(url, timeout)
    if body is None:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        warn(f"non-JSON response from {url}")
        return None


def run_gh_json(args: list[str]) -> tuple[Any, str]:
    """Run ``gh <args>`` and parse stdout as JSON. Returns (data or None, error)."""
    if not shutil.which("gh"):
        return None, "gh CLI is not on PATH"
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout).strip()[:500]
    out = proc.stdout.strip()
    if not out:
        return [], ""
    try:
        return json.loads(out), ""
    except json.JSONDecodeError:
        pass
    # Older gh concatenates one JSON array per page under --paginate.
    decoder, values, idx = json.JSONDecoder(), [], 0
    while idx < len(out):
        while idx < len(out) and out[idx].isspace():
            idx += 1
        if idx >= len(out):
            break
        obj, idx = decoder.raw_decode(out, idx)
        values.append(obj)
    if values and all(isinstance(v, list) for v in values):
        return [x for v in values for x in v], ""
    return values, ""


ARXIV_URL_RE = re.compile(
    r"arxiv\.org/(?:abs|pdf)/(?P<id>\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?",
    re.I,
)


def normalise_doi(value: Any) -> str | None:
    """Reduce any DOI form (bare, ``doi:``, ``https://doi.org/``) to lowercase ``10.x/y``.

    An arXiv abs/pdf URL maps to its minted ``10.48550/arxiv.<id>`` DOI. Returns None
    when no DOI is recognisable.
    """
    text = str(value or "").strip()
    arxiv = ARXIV_URL_RE.search(text)
    if arxiv:
        return f"10.48550/arxiv.{arxiv.group('id')}".lower()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "doi:",
    ):
        if text.lower().startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.strip().rstrip(".").lower()
    return text if text.startswith("10.") and "/" in text else None


def doi_url(doi: str) -> str:
    """Return the ``https://doi.org/`` form the Publications table stores."""
    return f"https://doi.org/{doi}"


def norm_title(value: Any) -> str:
    """Lowercase, strip accents and punctuation, collapse spaces: for title matching."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def norm_name(value: Any) -> set[str]:
    """Tokenise a person's name, accent- and hyphen-insensitive, for fuzzy matching."""
    return set(norm_title(value).split())


# Medium post URLs end in a 10-12 hex-digit post id: /slug-words-<id> or /<id>.
MEDIUM_ID_RE = re.compile(r"(?:^|[-/])([0-9a-f]{10,12})$")


def medium_post_id(url: Any) -> str | None:
    """Return the Medium post id from a medium.com URL, or None."""
    parts = urlsplit(str(url or "").strip())
    if "medium.com" not in parts.netloc:
        return None
    m = MEDIUM_ID_RE.search(parts.path.rstrip("/"))
    return m.group(1) if m else None


def clean_url(url: Any) -> str:
    """Drop the query string and fragment from a medium.com URL; leave others alone.

    Medium appends tracking parameters (``?source=rss...``, ``?sharedUserId=...``,
    ``?postPublishedType=...``) that carry no meaning. Other hosts may need their query
    (``?id=`` on journal sites), so they are returned trimmed but otherwise unchanged.
    """
    text = str(url or "").strip()
    parts = urlsplit(text)
    if "medium.com" not in parts.netloc:
        return text
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def medium_slug(url: Any) -> str:
    """Return the readable slug of a Medium URL, without its trailing post id."""
    path = urlsplit(str(url or "")).path.rstrip("/").split("/")[-1]
    return re.sub(r"-?[0-9a-f]{10,12}$", "", path) or path
