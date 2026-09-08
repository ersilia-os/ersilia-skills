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
