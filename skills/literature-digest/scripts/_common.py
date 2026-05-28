"""Shared utilities for literature-digest fetchers and ranker.

Keep this module dependency-free apart from the standard library — fetchers can layer on
`requests`, but `_common.py` must remain importable everywhere.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse


# Required fields per `references/source-catalogue.md`.
REQUIRED_ITEM_FIELDS = ("title", "authors", "venue", "date", "url", "source")


def warn(msg: str) -> None:
    """Log a warning to stderr; fetchers and the ranker call this on partial failure."""
    print(f"WARNING: {msg}", file=sys.stderr, flush=True)


def parse_date(s: str) -> date:
    """Accept YYYY-MM-DD or YYYY/MM/DD and return a `date`."""
    s = s.strip().replace("/", "-")
    return datetime.strptime(s, "%Y-%m-%d").date()


def normalise_doi(raw: str | None) -> str | None:
    """Strip URL prefix, lowercase, no trailing punctuation. Return None for empty input."""
    if not raw:
        return None
    s = raw.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    s = s.rstrip(".,;)")
    return s or None


# Matches a DOI anywhere in a string. Conservative: requires the `10.` prefix and a slash.
# Terminating characters include whitespace, common punctuation, and markdown delimiters.
DOI_REGEX = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>`]+?)(?=[\s\"<>`.,;)\]]|$)", re.IGNORECASE)


def extract_dois(text: str) -> list[str]:
    """All DOIs found in `text`, normalised and deduplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for match in DOI_REGEX.findall(text or ""):
        d = normalise_doi(match)
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out


# arXiv IDs: new format (2403.12345 or 2403.12345v2) or old format (q-bio.BM/0501001).
ARXIV_REGEX = re.compile(
    r"\b(?:arXiv:)?(?P<id>(\d{4}\.\d{4,5})(v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(v\d+)?)\b",
    re.IGNORECASE,
)


def extract_arxiv_ids(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in ARXIV_REGEX.finditer(text or ""):
        aid = m.group("id").lower()
        # Strip version suffix for canonical matching.
        aid = re.sub(r"v\d+$", "", aid)
        if aid not in seen:
            seen.add(aid)
            out.append(aid)
    return out


def normalise_url(url: str | None) -> str | None:
    """Lowercase scheme/host, drop fragment + tracking query params."""
    if not url:
        return None
    try:
        p = urlparse(url.strip())
    except ValueError:
        return None
    if not p.scheme or not p.netloc:
        return None
    drop_params = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}
    query = "&".join(
        kv for kv in (p.query or "").split("&")
        if kv and kv.split("=", 1)[0] not in drop_params
    )
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path, p.params, query, ""))


def normalise_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace. Used for fuzzy dedup."""
    if not title:
        return ""
    s = re.sub(r"[\s ]+", " ", title.lower())
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return s.strip()


def title_similarity(a: str, b: str) -> float:
    """Bag-of-words Jaccard over normalised titles. Good enough for dedup at 0.92 threshold."""
    ta = set(normalise_title(a).split())
    tb = set(normalise_title(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def validate_item(item: dict[str, Any]) -> list[str]:
    """Return a list of validation errors. Empty list means the item is well-formed."""
    errs: list[str] = []
    for field in REQUIRED_ITEM_FIELDS:
        if field not in item or item[field] in (None, "", []):
            errs.append(f"missing or empty required field: {field}")
    if "authors" in item and not isinstance(item["authors"], list):
        errs.append("authors must be a list")
    elif "authors" in item:
        for i, a in enumerate(item["authors"]):
            if not isinstance(a, dict) or not a.get("name"):
                errs.append(f"authors[{i}] missing name")
    if "date" in item and item["date"]:
        try:
            parse_date(item["date"])
        except ValueError:
            errs.append(f"date not YYYY-MM-DD: {item['date']!r}")
    return errs


def write_json(path: str, items: Iterable[dict[str, Any]]) -> None:
    """Write a JSON array of items to `path`, creating parent dirs as needed."""
    items_list = list(items)
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(items_list, f, indent=2, ensure_ascii=False)


def read_json(path: str) -> list[dict[str, Any]]:
    """Read a JSON array of items. Returns `[]` if the file is missing or empty."""
    p = Path(path).expanduser().resolve()
    if not p.exists() or p.stat().st_size == 0:
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list, got {type(data).__name__}")
    return data
