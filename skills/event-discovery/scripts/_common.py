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
    """Map an event to a continent from its country; virtual/unknown -> Global / Other."""
    country = str(event.get("country") or "").strip().lower()
    location = str(event.get("location") or "").strip().lower()
    if not country or country in ("virtual", "online", "n/a"):
        return "Global / Virtual"
    if country in ("virtual", "online") or location in ("virtual", "online"):
        return "Global / Virtual"
    return CONTINENTS.get(country, "Other")


def validate_event(event):
    """Return a list of missing required fields for ``event`` (empty = valid)."""
    if not isinstance(event, dict):
        return list(REQUIRED_EVENT_FIELDS)
    missing = []
    for field in REQUIRED_EVENT_FIELDS:
        value = event.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing
