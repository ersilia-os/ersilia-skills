"""Shared helpers for the model-incorporation-announcement scripts.

Standard library only — no third-party imports. Mirrors the pattern of
event-discovery/scripts/_common.py: stdout is reserved for machine-readable
output, everything advisory goes to stderr.
"""

import json
import re
import sys
import urllib.error
import urllib.request

# Crossref and OpenAlex both ask for a contact address in the polite pool. Ersilia's
# public address, not a team member's, so the scripts stay attributable to the org.
POLITE_MAILTO = "hello@ersilia.io"

USER_AGENT = f"ersilia-skills/model-incorporation-announcement (mailto:{POLITE_MAILTO})"

# ISO2 codes for World Bank low- and lower-middle-income economies, used to spot
# Global-South author institutions. The canonical list — with tiers, source URL and
# refresh cadence — lives in event-discovery/references/lmic-countries.md; refresh
# both together each July when the World Bank republishes.
LMIC_ISO2 = frozenset(
    """
    AF BF BI CF TD CD ER ET GM GW LR MG MW ML MZ NE RW SL SO SS SD SY TG UG YE
    DZ AO BD BJ BT BO CV KH CM KM CG CI DJ EG SV SZ GH GN HT HN IN IR JO KE KG
    LA LB LS MR FM MN MA MM NP NI NG PK PG PH WS ST SN SB LK TJ TZ TL TN UA UZ
    VU VN PS ZM ZW
    """.split()
)


def warn(message):
    """Print a WARNING to stderr (stdout is reserved for machine-readable output)."""
    print(f"WARNING: {message}", file=sys.stderr)


def die(message):
    """Print an ERROR to stderr and exit with code 1."""
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def read_json(path):
    """Load a JSON file, exiting the process with code 1 if it cannot be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot read JSON from {path}: {exc}")


def write_json(path, data):
    """Write ``data`` as pretty UTF-8 JSON (keeps non-ASCII author names intact)."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def fetch(url, timeout=30):
    """GET ``url`` and return the decoded body, or ``None`` on any HTTP/network error.

    Returning ``None`` rather than raising lets every caller degrade gracefully: a
    missing Crossref record must not stop the run, it must only narrow what the post
    can claim.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        warn(f"fetch failed for {url}: {exc}")
        return None


def fetch_json(url, timeout=30):
    """GET ``url`` and parse it as JSON, or return ``None`` if either step fails."""
    body = fetch(url, timeout=timeout)
    if body is None:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        warn(f"response from {url} is not JSON: {exc}")
        return None


def surname(display_name):
    """Best-effort surname from a display name, for the hook check in check_post.py.

    Takes the last whitespace-separated token, keeping particles attached when they
    are capitalised mid-name (``van der Waals`` -> ``Waals`` is wrong but harmless
    here; the check only needs a token that will appear in a correctly written hook).
    """
    parts = [p for p in str(display_name or "").replace(",", " ").split() if p]
    return parts[-1] if parts else ""


# arXiv mints a DOI for every submission, but a Publication field often carries the abs
# or pdf URL instead. The mapping is deterministic, so deriving it is a lookup rather than
# a guess — without it a live model like eos9q2i resolves zero authors.
ARXIV_URL_RE = re.compile(
    r"arxiv\.org/(?:abs|pdf)/(?P<id>\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?",
    re.I,
)


def normalise_doi(value):
    """Reduce any DOI form — bare, ``doi:``, ``https://doi.org/`` — to ``10.x/y``.

    An arXiv ``abs``/``pdf`` URL is converted to its minted ``10.48550/arXiv.<id>`` DOI.
    Returns ``None`` when the value carries no recognisable DOI.
    """
    text = str(value or "").strip()
    arxiv = ARXIV_URL_RE.search(text)
    if arxiv:
        return f"10.48550/arXiv.{arxiv.group('id')}"
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:", "DOI:"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):]
            break
    text = text.strip().rstrip(".")
    return text if text.startswith("10.") and "/" in text else None


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
