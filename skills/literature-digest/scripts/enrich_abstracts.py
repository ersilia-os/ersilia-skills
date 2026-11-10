"""Fill in missing titles and abstracts before ranking.

Gmail alert and Slack items arrive with a title (often generic for Slack) and no abstract,
so the ranker scores them on a few title words. This step resolves each item's DOI or
arXiv ID and fills the abstract from arXiv, Crossref or Europe PMC, in that order. Slack
items with a placeholder title also get the resolved title.

Usage:
    python scripts/enrich_abstracts.py --in /tmp/gmail.json --in /tmp/slack.json \\
        --out /tmp/enriched.json [--cache /tmp/abstract_cache.json]

Network failures are non-fatal: an item that cannot be resolved is passed through
unchanged. Lookups are cached so a re-run does not repeat them.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from _common import (
    extract_arxiv_ids,
    http_get_json,
    http_get_text,
    normalise_doi,
    read_json,
    warn,
    write_json,
)

_PLACEHOLDER_TITLE_RE = re.compile(r"^(shared link|looks |important for|from [A-Z])", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_ATOM = "{http://www.w3.org/2005/Atom}"

# One lookup returns ``{"title": str | None, "abstract": str | None}`` or None.
Lookup = Callable[[str], "dict[str, str | None] | None"]


def strip_markup(text: str) -> str:
    """Remove JATS / HTML tags and entities from a Crossref or Europe PMC abstract.

    Parameters
    ----------
    text : str
        Abstract text that may contain ``<jats:p>``-style tags and entities.

    Returns
    -------
    str
        Plain text with collapsed whitespace and no leading "Abstract" label.
    """
    out = html.unescape(_TAG_RE.sub(" ", text))
    out = re.sub(r"\s+", " ", out).strip()
    return re.sub(r"^abstract[:.\s]+", "", out, flags=re.IGNORECASE)


def doi_candidates(doi: str) -> list[str]:
    """Return the DOI and progressively shorter forms with trailing path segments removed.

    Publisher URLs often append a page id and a title slug, which the normaliser keeps
    (``10.1039/d6dd00444j/1373125/metapli-...``). A real DOI suffix can contain a slash,
    so each shorter form is tried only after the longer one fails.
    """
    parts = doi.split("/")
    return ["/".join(parts[:n]) for n in range(len(parts), 1, -1)][:3]


def lookup_arxiv(arxiv_id: str) -> dict[str, str | None] | None:
    """Fetch title and abstract for an arXiv ID from the arXiv API."""
    text = http_get_text("http://export.arxiv.org/api/query", {"id_list": arxiv_id})
    entry = ET.fromstring(text).find(f"{_ATOM}entry")
    if entry is None:
        return None
    title = (entry.findtext(f"{_ATOM}title") or "").strip()
    summary = (entry.findtext(f"{_ATOM}summary") or "").strip()
    if not title or title.lower() == "error":
        return None
    return {"title": re.sub(r"\s+", " ", title), "abstract": re.sub(r"\s+", " ", summary) or None}


def lookup_crossref(doi: str) -> dict[str, str | None] | None:
    """Fetch title and abstract for a DOI from Crossref (abstracts are often missing)."""
    payload = http_get_json(f"https://api.crossref.org/works/{quote(doi, safe='/')}")
    msg = payload.get("message") or {}
    titles = msg.get("title") or []
    abstract = strip_markup(msg["abstract"]) if msg.get("abstract") else None
    if not titles and not abstract:
        return None
    return {"title": strip_markup(titles[0]) if titles else None, "abstract": abstract}


def lookup_europepmc(doi: str) -> dict[str, str | None] | None:
    """Fetch title and abstract for a DOI from Europe PMC."""
    payload = http_get_json(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        {"query": f'DOI:"{doi}"', "format": "json", "resultType": "core", "pageSize": 1},
    )
    results = (payload.get("resultList") or {}).get("result") or []
    if not results:
        return None
    rec = results[0]
    abstract = strip_markup(rec["abstractText"]) if rec.get("abstractText") else None
    title = strip_markup(rec["title"]) if rec.get("title") else None
    return {"title": title, "abstract": abstract} if (title or abstract) else None


def resolve(
    item: dict[str, Any],
    arxiv: Lookup = lookup_arxiv,
    crossref: Lookup = lookup_crossref,
    europepmc: Lookup = lookup_europepmc,
) -> dict[str, str | None] | None:
    """Look an item up by arXiv ID, then by DOI (Crossref, then Europe PMC).

    Returns the first result that carries an abstract, else the first with a title.
    Network and parsing errors are swallowed so one bad lookup never stops a run.
    """
    best: dict[str, str | None] | None = None
    attempts: list[tuple[Lookup, str]] = []
    aid = item.get("arxiv_id") or next(iter(extract_arxiv_ids(item.get("url") or "")), None)
    if aid:
        attempts.append((arxiv, aid))
    doi = normalise_doi(item.get("doi"))
    if doi:
        for cand in doi_candidates(doi):
            attempts += [(crossref, cand), (europepmc, cand)]
    for fn, key in attempts:
        try:
            res = fn(key)
        except (OSError, ValueError, ET.ParseError):
            continue
        if not res:
            continue
        if res.get("abstract"):
            return res
        best = best or res
    return best


def enrich(
    items: list[dict[str, Any]],
    cache: dict[str, Any],
    workers: int = 4,
    lookup: Callable[[dict[str, Any]], dict[str, str | None] | None] = resolve,
) -> int:
    """Fill missing abstracts in place; return how many items gained one.

    A Slack item with a placeholder title also takes the resolved title; its original
    text is kept in ``title_original``.
    """
    todo = [it for it in items if not it.get("abstract") and (it.get("doi") or it.get("arxiv_id") or it.get("url"))]

    def key(it: dict[str, Any]) -> str:
        return it.get("arxiv_id") or it.get("doi") or it.get("url") or ""

    def run(it: dict[str, Any]) -> None:
        k = key(it)
        if k not in cache:
            cache[k] = lookup(it)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(run, todo))

    gained = 0
    for it in todo:
        res = cache.get(key(it))
        if not res:
            continue
        if res.get("abstract"):
            it["abstract"] = res["abstract"]
            it["abstract_source"] = "enriched"
            gained += 1
        title = res.get("title")
        if title and it.get("source") == "slack" and _PLACEHOLDER_TITLE_RE.match(it.get("title") or ""):
            it["title_original"] = it["title"]
            it["title"] = title
    return gained


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--in", dest="ins", action="append", required=True, help="Input items JSON (repeatable).")
    p.add_argument("--out", required=True, help="Output JSON (all inputs, enriched).")
    p.add_argument("--cache", default="/tmp/abstract_cache.json", help="Lookup cache, reused across runs.")
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args(argv)

    items: list[dict[str, Any]] = []
    for src in args.ins:
        items.extend(read_json(src))

    cache_path = Path(args.cache)
    cache: dict[str, Any] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except ValueError:
            warn(f"ignoring unreadable cache {cache_path}")

    missing = sum(1 for it in items if not it.get("abstract"))
    gained = enrich(items, cache, workers=args.workers)

    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    write_json(args.out, items)
    print(f"enrich_abstracts: {len(items)} items, {missing} without abstract, {gained} filled", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
