"""Shared helpers for the event-discovery scripts.

Standard library only — no third-party imports. Mirrors the pattern of
literature-digest/scripts/_common.py.
"""

import json
import sys
from datetime import date, datetime

# Fields every event object must carry to be kept (see references/event-sources.md).
REQUIRED_EVENT_FIELDS = ("name", "start_date", "location", "url", "source")


def warn(message):
    """Print a WARNING to stderr (stdout is reserved for machine-readable output)."""
    print(f"WARNING: {message}", file=sys.stderr)


def parse_date(value):
    """Parse an ISO ``YYYY-MM-DD`` string into a ``date``.

    Returns ``None`` for empty/None input or anything that does not parse, so
    callers can decide how to handle a missing or malformed date.
    """
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def read_json(path):
    """Load a JSON file, exiting the process with code 1 if it cannot be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read JSON from {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def write_json(path, data):
    """Write ``data`` as pretty UTF-8 JSON (keeps non-ASCII event names intact)."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


# Country -> continent, for the optional `--group-by continent` report view.
# Lowercased country names (and common aliases). Unlisted -> "Other"; virtual -> "Global / Virtual".
CONTINENTS = {
    # Africa
    "south africa": "Africa", "nigeria": "Africa", "uganda": "Africa", "kenya": "Africa",
    "rwanda": "Africa", "ghana": "Africa", "senegal": "Africa", "tanzania": "Africa",
    "ethiopia": "Africa", "morocco": "Africa", "egypt": "Africa", "tunisia": "Africa",
    "cameroon": "Africa", "zambia": "Africa", "zimbabwe": "Africa", "botswana": "Africa",
    "malawi": "Africa", "mozambique": "Africa", "mali": "Africa", "burkina faso": "Africa",
    "cote d'ivoire": "Africa", "côte d'ivoire": "Africa", "benin": "Africa", "gambia": "Africa",
    "gabon": "Africa", "namibia": "Africa", "sudan": "Africa", "angola": "Africa",
    "democratic republic of the congo": "Africa",
    # Europe
    "united kingdom": "Europe", "uk": "Europe", "germany": "Europe", "switzerland": "Europe",
    "italy": "Europe", "spain": "Europe", "sweden": "Europe", "france": "Europe",
    "netherlands": "Europe", "ireland": "Europe", "belgium": "Europe", "portugal": "Europe",
    "austria": "Europe", "denmark": "Europe", "norway": "Europe", "finland": "Europe",
    "poland": "Europe", "czech republic": "Europe", "czechia": "Europe", "greece": "Europe",
    "hungary": "Europe", "ukraine": "Europe", "turkey": "Europe", "türkiye": "Europe",
    "latvia": "Europe", "lithuania": "Europe", "estonia": "Europe", "slovenia": "Europe",
    "slovakia": "Europe", "croatia": "Europe", "romania": "Europe", "bulgaria": "Europe",
    # North America
    "united states": "North America", "usa": "North America",
    "united states of america": "North America", "canada": "North America", "mexico": "North America",
    # South America
    "brazil": "South America", "argentina": "South America", "colombia": "South America",
    "peru": "South America", "chile": "South America", "uruguay": "South America",
    "ecuador": "South America",
    # Asia
    "india": "Asia", "china": "Asia", "japan": "Asia", "singapore": "Asia", "south korea": "Asia",
    "thailand": "Asia", "vietnam": "Asia", "pakistan": "Asia", "bangladesh": "Asia",
    "indonesia": "Asia", "malaysia": "Asia", "philippines": "Asia", "israel": "Asia",
    "united arab emirates": "Asia", "uae": "Asia", "sri lanka": "Asia", "nepal": "Asia",
    # Oceania
    "australia": "Oceania", "new zealand": "Oceania",
}


def continent_of(event):
    """Map an event to a continent from its country.

    Virtual/online events -> "Global / Virtual". ``country`` is optional, so an
    in-person event that only carries a ``location`` (required) with no country
    is classified as "Other" rather than being misfiled as virtual.
    """
    country = str(event.get("country") or "").strip().lower()
    location = str(event.get("location") or "").strip().lower()
    if country in ("virtual", "online", "n/a") or location in ("virtual", "online"):
        return "Global / Virtual"
    if not country:
        return "Other"
    return CONTINENTS.get(country, "Other")


# Continent names are themselves valid `focus_region` values — an event can be about a
# whole continent, not only a country — so accept them alongside country names.
CONTINENT_NAMES = {c.lower(): c for c in set(CONTINENTS.values())}


def continent_of_region(region):
    """Resolve a ``focus_region`` string to a continent name, or ``None``.

    Accepts a country (``"Kenya"``) or a continent (``"Africa"``), case-insensitive.
    Returns ``None`` for empty or unrecognised input so callers can fall back to the
    physical location instead of silently bucketing the event into "Other".
    """
    key = str(region or "").strip().lower()
    if not key:
        return None
    if key in CONTINENT_NAMES:
        return CONTINENT_NAMES[key]
    return CONTINENTS.get(key)


def focus_continent_of(event):
    """The continent an event is *about*, falling back to where it is *held*.

    ``focus_region`` is optional — most events are simply about the place they happen
    — so when it is absent or unrecognised this returns ``continent_of(event)``.
    That fallback is load-bearing: without it the majority of events, which declare no
    explicit focus, would vanish from any focus-based count or marker.
    """
    return continent_of_region(event.get("focus_region")) or continent_of(event)


def validate_event(event):
    """Return a list of missing required fields for ``event`` (empty = valid).

    ``start_date`` is waived for **team-shared** events (``shared_by`` set). SKILL.md
    Step 2a promises a colleague's contribution is kept even when it cannot be verified
    at all — but a conference whose page has not published dates yet is precisely that
    case, and requiring ``start_date`` made the promise undeliverable: the event was
    silently dropped as invalid. Such events are routed to their own report section
    rather than being given an invented date.

    The waiver is deliberately narrow. A machine-discovered event with no date is still
    dropped, because "no date found on the official page" means the sweep failed to
    establish it, whereas for a shared event a human has already vouched for it.
    """
    if not isinstance(event, dict):
        return list(REQUIRED_EVENT_FIELDS)
    waived = {"start_date"} if str(event.get("shared_by") or "").strip() else set()
    missing = []
    for field in REQUIRED_EVENT_FIELDS:
        if field in waived:
            continue
        value = event.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing
