"""Aggregate fetched items across sources, deduplicate, score, and emit a top-N pool
for LLM triage.

Inputs:
    --in PATH        repeatable; one JSON file per source (output of fetch_*.py)
    --seen PATH      newline-delimited list of DOIs/arXiv IDs/URLs to exclude
    --landscape PATH path to references/search-landscape.md
    --lmic PATH      path to references/lmic-countries.md
    --out PATH       where to write the ranked pool
    --top-n N        how many items to keep (default 50)

Each output item has the same schema as input, plus a `score` field:

    "score": {
        "total": 9,
        "breakdown": {
            "author_match": 4,
            "journal_tier": 3,
            "topic_hits": 2,
            "lmic_bonus": 0,
            "recency": 0
        },
        "matched_authors": ["Kelly Chibale"],
        "matched_keywords": ["antimalarial", "machine learning"],
        "matched_journal_tier": 1,
        "seen": false
    }

The LLM triage step in SKILL.md consumes the ranked pool and picks the final 20–30.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from _common import (
    extract_arxiv_ids,
    extract_dois,
    normalise_doi,
    normalise_title,
    normalise_url,
    parse_date,
    read_json,
    title_similarity,
    warn,
    write_json,
)


# -----------------------------------------------------------------------------
# Reference parsing
# -----------------------------------------------------------------------------


@dataclass
class Landscape:
    """Parsed view of references/search-landscape.md."""
    methods: list[str] = field(default_factory=list)
    endpoints: list[str] = field(default_factory=list)
    diseases: list[str] = field(default_factory=list)
    modality: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    open_science: list[str] = field(default_factory=list)

    # Authors by tier (lowercased surname-or-full-name keys).
    authors_grant: dict[str, str] = field(default_factory=dict)  # +5
    authors_core: dict[str, str] = field(default_factory=dict)  # +4 (IRB/Ersilia)
    authors_external: dict[str, str] = field(default_factory=dict)  # +3

    # Journals by tier. Keys are lowercased venue names.
    journals_tier1: set[str] = field(default_factory=set)
    journals_tier2: set[str] = field(default_factory=set)
    journals_tier3: set[str] = field(default_factory=set)

    def all_keywords(self) -> list[str]:
        out: list[str] = []
        for bucket in (self.methods, self.endpoints, self.diseases, self.modality,
                       self.datasets, self.open_science):
            out.extend(bucket)
        return out


# Section headers we care about in search-landscape.md.
# Map: lowercased header text → attribute name on Landscape.
_KEYWORD_SECTIONS = {
    "methods (how the model works)": "methods",
    "endpoints (what the model predicts)": "endpoints",
    "diseases / pathogens (where the model applies)": "diseases",
    "modality / mechanism (load-bearing in 2026)": "modality",
    "dataset / benchmark anchors (useful standalone terms)": "datasets",
    "open-science anchors": "open_science",
}

_AUTHOR_SECTIONS = {
    "core irb / ersilia network (closest collaborators)": "core",
    "active grant co-pis and partner institutions": "grant",
    "external topical anchors (boost +3)": "external",
}

_JOURNAL_TIERS = {
    "tier 1 — set alerts (+3 in ranking)": "tier1",
    "tier 2 — scan tables of contents (+2 in ranking)": "tier2",
    "tier 3 — opportunistic / global-health adjuncts (+1 in ranking)": "tier3",
}

_BOLD_AUTHOR_RE = re.compile(r"^\s*-\s*\*\*(?P<name>[^*]+?)\*\*\s*(?:—|-)\s*(?P<rest>.+)$")
_ITALIC_JOURNAL_RE = re.compile(r"\*(?P<j>[^*]+?)\*")


def _split_keyword_line(text: str) -> list[str]:
    """Keyword paragraphs in search-landscape.md use `·` or `•` as separators.

    Tolerates inconsistent whitespace (e.g. `·` at end of line) and mixed bullets.
    """
    # Normalise separators to a single sentinel before splitting.
    normalised = re.sub(r"[·•]+", "|", text)
    parts = re.split(r"\s*\|\s*", normalised)
    out: list[str] = []
    for p in parts:
        p = p.strip().rstrip(".,;").strip()
        # Strip leading/trailing markdown emphasis.
        p = re.sub(r"^[*_]+|[*_]+$", "", p).strip()
        if p:
            out.append(p)
    return out


def parse_landscape(path: str) -> Landscape:
    """Parse the bits of search-landscape.md the ranker actually uses.

    Tolerates document drift: unknown sections are ignored.
    """
    landscape = Landscape()
    p = Path(path).expanduser().resolve()
    if not p.exists():
        warn(f"landscape file not found: {path}")
        return landscape

    text = p.read_text(encoding="utf-8")
    lines = text.split("\n")

    current_kw_attr: str | None = None
    current_author_tier: str | None = None
    current_journal_tier: str | None = None

    def header_key(line: str) -> str | None:
        m = re.match(r"^\s*#{2,4}\s+(.+?)\s*$", line)
        if not m:
            return None
        return m.group(1).strip().lower()

    for raw in lines:
        line = raw.rstrip()
        hk = header_key(line)
        if hk is not None:
            # Reset everything on any header; only one mode active at a time.
            current_kw_attr = _KEYWORD_SECTIONS.get(hk)
            current_author_tier = _AUTHOR_SECTIONS.get(hk)
            current_journal_tier = _JOURNAL_TIERS.get(hk)
            continue

        # Keyword paragraphs are plain prose under their header.
        if current_kw_attr and line.strip() and not line.startswith("#"):
            existing = getattr(landscape, current_kw_attr)
            existing.extend(_split_keyword_line(line))
            continue

        # Author bullets.
        if current_author_tier and line.lstrip().startswith("- **"):
            m = _BOLD_AUTHOR_RE.match(line)
            if m:
                name = m.group("name").strip()
                rest = m.group("rest").strip()
                target = {
                    "core": landscape.authors_core,
                    "grant": landscape.authors_grant,
                    "external": landscape.authors_external,
                }[current_author_tier]
                target[name.lower()] = rest
            continue

        # Journal bullets: each bullet may name 1+ italicised journals.
        if current_journal_tier and line.lstrip().startswith("-"):
            for jm in _ITALIC_JOURNAL_RE.finditer(line):
                name = jm.group("j").strip().rstrip(".").lower()
                if not name:
                    continue
                bucket = {
                    "tier1": landscape.journals_tier1,
                    "tier2": landscape.journals_tier2,
                    "tier3": landscape.journals_tier3,
                }[current_journal_tier]
                bucket.add(name)
            continue

    return landscape


@dataclass
class LMICTable:
    """Country-name → tier map plus a set of aliases."""
    by_name: dict[str, str] = field(default_factory=dict)  # lowercased name → "low"/"lower-middle"
    aliases: dict[str, str] = field(default_factory=dict)  # alias name → canonical name (lowercased)


_LMIC_ROW_RE = re.compile(r"^([A-Z]{2})\t([^\t]+)\t(low|lower-middle)\s*$")
_BUILTIN_ALIASES = {
    "burma": "myanmar",
    "zaire": "democratic republic of the congo",
    "drc": "democratic republic of the congo",
    "dr congo": "democratic republic of the congo",
    "congo-kinshasa": "democratic republic of the congo",
    "congo-brazzaville": "republic of the congo",
    "ivory coast": "côte d'ivoire",
    "cote d'ivoire": "côte d'ivoire",
    "swaziland": "eswatini",
    "viet nam": "vietnam",
    "syria": "syrian arab republic",
    "tanzania, united republic of": "tanzania",
    "kyrgyzstan": "kyrgyz republic",
    "laos": "lao pdr",
    "cape verde": "cabo verde",
}


def parse_lmic(path: str) -> LMICTable:
    lmic = LMICTable(aliases=dict(_BUILTIN_ALIASES))
    p = Path(path).expanduser().resolve()
    if not p.exists():
        warn(f"lmic file not found: {path}")
        return lmic
    text = p.read_text(encoding="utf-8")
    in_code = False
    for raw in text.split("\n"):
        if raw.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            continue
        if raw.startswith("#") or not raw.strip():
            continue
        m = _LMIC_ROW_RE.match(raw)
        if not m:
            continue
        name = m.group(2).strip().lower()
        tier = m.group(3).strip().lower()
        lmic.by_name[name] = tier
    return lmic


def country_from_affiliation(aff: str | None, lmic: LMICTable) -> tuple[str | None, str | None]:
    """Best-effort affiliation → (canonical country name, tier).
    Returns (None, None) if no LMIC match.
    """
    if not aff:
        return None, None
    text = aff.lower()
    # Direct match (longest-first to prefer "democratic republic of the congo" over "congo").
    for name in sorted(lmic.by_name, key=len, reverse=True):
        # Word-boundary-ish match.
        if re.search(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", text):
            return name, lmic.by_name[name]
    for alias, canonical in lmic.aliases.items():
        if re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", text):
            if canonical in lmic.by_name:
                return canonical, lmic.by_name[canonical]
    return None, None


# -----------------------------------------------------------------------------
# Dedup
# -----------------------------------------------------------------------------


def _make_arxiv_key(item: dict[str, Any]) -> str | None:
    aid = item.get("arxiv_id")
    if aid:
        return aid.lower()
    # Look in URL.
    for u in (item.get("url"),):
        if not u:
            continue
        ids = extract_arxiv_ids(u)
        if ids:
            return ids[0]
    return None


def dedup_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """DOI exact → arXiv ID → normalised URL → fuzzy title."""
    by_doi: dict[str, dict[str, Any]] = {}
    by_arxiv: dict[str, dict[str, Any]] = {}
    by_url: dict[str, dict[str, Any]] = {}
    remaining: list[dict[str, Any]] = []

    def _prefer(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        """When two records collide, keep the more informative one.

        Preference: has abstract > has affiliations > more authors > later date.
        """
        a_score = (
            int(bool(existing.get("abstract"))) * 4
            + sum(1 for a in existing.get("authors") or [] if a.get("affiliation")) * 2
            + len(existing.get("authors") or [])
        )
        b_score = (
            int(bool(new.get("abstract"))) * 4
            + sum(1 for a in new.get("authors") or [] if a.get("affiliation")) * 2
            + len(new.get("authors") or [])
        )
        if b_score > a_score:
            return new
        if b_score == a_score and (new.get("date") or "") > (existing.get("date") or ""):
            return new
        return existing

    for it in items:
        doi = normalise_doi(it.get("doi"))
        if doi:
            if doi in by_doi:
                by_doi[doi] = _prefer(by_doi[doi], it)
            else:
                by_doi[doi] = it
            continue

        arxiv_id = _make_arxiv_key(it)
        if arxiv_id:
            if arxiv_id in by_arxiv:
                by_arxiv[arxiv_id] = _prefer(by_arxiv[arxiv_id], it)
            else:
                by_arxiv[arxiv_id] = it
            continue

        url = normalise_url(it.get("url"))
        if url:
            if url in by_url:
                by_url[url] = _prefer(by_url[url], it)
            else:
                by_url[url] = it
            continue

        remaining.append(it)

    survivors = list(by_doi.values()) + list(by_arxiv.values()) + list(by_url.values())

    # Fuzzy title pass over the survivors and the un-keyed remaining items.
    final: list[dict[str, Any]] = []
    for it in survivors + remaining:
        merged = False
        for existing in final:
            if title_similarity(it.get("title", ""), existing.get("title", "")) >= 0.92:
                # Merge into the more-informative one.
                better = _prefer(existing, it)
                final[final.index(existing)] = better
                merged = True
                break
        if not merged:
            final.append(it)
    return final


# -----------------------------------------------------------------------------
# Scoring
# -----------------------------------------------------------------------------


def _author_matches(item: dict[str, Any], landscape: Landscape) -> tuple[int, list[str]]:
    """Return (max_bonus, matched_names). Multiple matches still cap at the highest tier's bonus."""
    names = [a.get("name", "") for a in item.get("authors") or []]
    matched: list[str] = []
    best = 0
    for n in names:
        nl = (n or "").strip().lower()
        if not nl:
            continue
        # Tier match: grant > core > external.
        if any(nl == k or nl.endswith(" " + k.split()[-1]) for k in landscape.authors_grant):
            for k in landscape.authors_grant:
                if nl == k or nl.endswith(" " + k.split()[-1]):
                    matched.append(k)
                    best = max(best, 5)
        elif any(nl == k or nl.endswith(" " + k.split()[-1]) for k in landscape.authors_core):
            for k in landscape.authors_core:
                if nl == k or nl.endswith(" " + k.split()[-1]):
                    matched.append(k)
                    best = max(best, 4)
        elif any(nl == k or nl.endswith(" " + k.split()[-1]) for k in landscape.authors_external):
            for k in landscape.authors_external:
                if nl == k or nl.endswith(" " + k.split()[-1]):
                    matched.append(k)
                    best = max(best, 3)
    return best, sorted(set(matched))


def _journal_matches(venue_clean: str, journal: str) -> bool:
    """True iff `venue_clean` is the same journal as `journal` (both already lowercased).

    Allowed: exact equality, or the journal name followed by a recognised separator
    `(`, `:`, `,`, or `;`. This rejects e.g. venue "advanced science" matching journal
    "science" (no separator between them).
    """
    if venue_clean == journal:
        return True
    # Journal name as a prefix followed by a subtitle/parenthetical/abbreviation separator.
    pattern = r"^" + re.escape(journal) + r"\s*[(:,;]"
    return bool(re.match(pattern, venue_clean))


def _journal_tier(item: dict[str, Any], landscape: Landscape) -> tuple[int, int]:
    """Return (bonus, tier_number). tier_number ∈ {0,1,2,3}."""
    venue = (item.get("venue") or "").strip().lower()
    if not venue:
        return 0, 0
    # Strip trailing parenthetical / publisher detail and punctuation.
    venue_clean = re.sub(r"\s*\(.*$", "", venue).strip().rstrip(" .,;:")
    for tier_set, bonus, tier_num in (
        (landscape.journals_tier1, 3, 1),
        (landscape.journals_tier2, 2, 2),
        (landscape.journals_tier3, 1, 3),
    ):
        # Iterate longest-journal-first so e.g. "nature communications" beats "nature".
        for j in sorted(tier_set, key=len, reverse=True):
            if _journal_matches(venue_clean, j):
                return bonus, tier_num
    # Generic preprint server bonus (kept low; preprints are in scope but unranked here).
    if venue_clean in {"biorxiv", "chemrxiv", "arxiv", "medrxiv"}:
        return 1, 0
    return 0, 0


def _topic_hits(item: dict[str, Any], landscape: Landscape) -> tuple[int, list[str]]:
    text = " ".join([
        item.get("title") or "",
        item.get("abstract") or "",
    ]).lower()
    matches: list[str] = []
    for kw in landscape.all_keywords():
        kw_norm = kw.strip().lower()
        if not kw_norm or len(kw_norm) < 3:
            continue
        if re.search(r"(?<![a-z])" + re.escape(kw_norm) + r"(?![a-z])", text):
            matches.append(kw)
    # Score capped at +4 per the ranking table.
    bonus = min(len(matches), 4)
    return bonus, matches[:10]  # keep the top 10 in the explanation


def _lmic_bonus(item: dict[str, Any], lmic: LMICTable) -> tuple[int, list[str]]:
    """+2 if the first or senior (last) author affiliation maps to a WB LMIC country."""
    authors = item.get("authors") or []
    if not authors:
        return 0, []
    first = authors[0]
    last = authors[-1] if len(authors) > 1 else None
    matched_countries: list[str] = []
    for who in (first, last):
        if who is None:
            continue
        country, _tier = country_from_affiliation(who.get("affiliation"), lmic)
        if country:
            matched_countries.append(country)
            who["country"] = country  # mutate; downstream uses this for the 🌍 marker
    return (2 if matched_countries else 0), matched_countries


def _recency_bonus(item_date_str: str, window_start: date, window_end: date) -> float:
    """Linear bonus 0 → 1 across the date window; clamped on both ends."""
    if not item_date_str:
        return 0.0
    try:
        d = parse_date(item_date_str)
    except ValueError:
        return 0.0
    if window_end == window_start:
        return 1.0
    if d < window_start:
        return 0.0
    if d > window_end:
        return 1.0
    span = (window_end - window_start).days
    return (d - window_start).days / span if span else 1.0


def score_item(
    item: dict[str, Any],
    landscape: Landscape,
    lmic: LMICTable,
    seen: set[str],
    window_start: date,
    window_end: date,
) -> dict[str, Any]:
    author_bonus, matched_authors = _author_matches(item, landscape)
    journal_bonus, journal_tier = _journal_tier(item, landscape)
    topic_bonus, matched_kw = _topic_hits(item, landscape)
    lmic_bonus, matched_countries = _lmic_bonus(item, lmic)
    recency = _recency_bonus(item.get("date") or "", window_start, window_end)

    # Seen check.
    seen_flag = False
    for key in filter(None, (
        normalise_doi(item.get("doi")),
        _make_arxiv_key(item),
        normalise_url(item.get("url")),
    )):
        if key in seen:
            seen_flag = True
            break

    breakdown = {
        "author_match": author_bonus,
        "journal_tier": journal_bonus,
        "topic_hits": topic_bonus,
        "lmic_bonus": lmic_bonus,
        "recency": round(recency, 3),
    }
    total = author_bonus + journal_bonus + topic_bonus + lmic_bonus + recency
    if seen_flag:
        total -= 999

    return {
        "total": round(total, 3),
        "breakdown": breakdown,
        "matched_authors": matched_authors,
        "matched_keywords": matched_kw,
        "matched_countries": matched_countries,
        "matched_journal_tier": journal_tier,
        "seen": seen_flag,
    }


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


def load_seen(path: str | None) -> set[str]:
    if not path:
        return set()
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return set()
    return {line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--in", dest="ins", action="append", required=True,
                   help="Input items JSON (repeatable).")
    p.add_argument("--seen", required=False, help="Path to seen-set text file.")
    p.add_argument("--landscape", required=True, help="references/search-landscape.md")
    p.add_argument("--lmic", required=True, help="references/lmic-countries.md")
    p.add_argument("--out", required=True, help="Output JSON.")
    p.add_argument("--top-n", type=int, default=50, help="Pool size to keep (default 50).")
    p.add_argument("--window-from", help="Date window start YYYY-MM-DD for recency score; default = earliest item date.")
    p.add_argument("--window-to", help="Date window end YYYY-MM-DD for recency score; default = today.")
    args = p.parse_args(argv)

    items: list[dict[str, Any]] = []
    for src in args.ins:
        try:
            items.extend(read_json(src))
        except (FileNotFoundError, ValueError) as e:
            warn(f"could not read {src}: {e}")

    if not items:
        warn("no input items; emitting empty pool")
        write_json(args.out, [])
        return 0

    landscape = parse_landscape(args.landscape)
    lmic = parse_lmic(args.lmic)
    seen = load_seen(args.seen)

    # Determine the window for the recency score.
    if args.window_to:
        window_end = parse_date(args.window_to)
    else:
        window_end = datetime.utcnow().date()
    if args.window_from:
        window_start = parse_date(args.window_from)
    else:
        dates = [it.get("date") for it in items if it.get("date")]
        if dates:
            window_start = min(parse_date(d) for d in dates if d)
        else:
            window_start = window_end

    deduped = dedup_items(items)
    for it in deduped:
        it["score"] = score_item(it, landscape, lmic, seen, window_start, window_end)

    # Drop seen and sort.
    surviving = [it for it in deduped if not it["score"]["seen"]]
    surviving.sort(key=lambda it: it["score"]["total"], reverse=True)
    pool = surviving[: args.top_n]

    write_json(args.out, pool)
    print(
        f"dedup_and_rank: {len(items)} input → {len(deduped)} deduped → "
        f"{len(surviving)} unseen → top {len(pool)} kept",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
