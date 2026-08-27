"""Shared helpers for the partner-profiling scripts.

Standard library only — no third-party imports. Mirrors the pattern of
event-discovery/scripts/_common.py.

The contact-policy constants here are the *mechanical* half of
``references/data-handling.md``. Ersilia is a Spanish foundation, so recording a
named journalist's details is GDPR-relevant processing; a rule that lives only in
prose gets applied case-by-case and drifts. Encoding the allowed channel kinds in
code means a disallowed one is stripped by ``filter_and_sort.py`` on every run,
whether or not anyone re-read the reference file.
"""

import json
import re
import sys
from datetime import date, datetime

# Fields every partner object must carry to be kept (see references/partner-sources.md).
# `hook` and `next_step` are required, not optional: a row without them is a phone-book
# entry, and the whole point of the sweep is to produce a work queue.
REQUIRED_PARTNER_FIELDS = ("name", "class", "url", "source", "hook", "next_step")

# Controlled vocabularies. These are the ONLY allowed values — the renderers group and
# sort on them verbatim (see references/classification.md).
CLASS_VALUES = ("Media", "Open-source", "Institution", "Comms-team", "Community", "Creative")
SCOPE_VALUES = ("Local", "Regional", "Global-South", "International")
REACH_VALUES = ("Niche", "Field", "Broad")
WARMTH_VALUES = ("Cold", "Shared network", "Warm intro", "Existing contact")
PRIORITY_VALUES = ("High", "Medium", "Low")
ACTION_VALUES = ("pitch", "introduce", "invite", "nurture", "watch", "commission")

# Classes for which `reach` is not a meaningful axis. You do not borrow a photographer's
# audience — you buy a skill — so `reach` is left empty for them and the renderers omit
# it rather than printing a misleading "reach Niche". `reach` is optional for every class
# (it is not in REQUIRED_PARTNER_FIELDS); this tuple documents where its absence is
# *expected* rather than an oversight, and the campaign renderer uses it to decide which
# fields to show.
REACHLESS_CLASSES = ("Creative",)

# --- Contact policy -------------------------------------------------------------
# Channel kinds that may be recorded. These are addresses an organisation publishes
# *for the purpose of being contacted* about coverage or collaboration.
ALLOWED_CONTACT_KINDS = {
    "outlet_pitch",       # a desk / tips / pitch address the outlet publishes
    "press_office",       # institutional press or comms office
    "institutional",      # a role address on an institution's own site
    "public_form",        # a "contact us" / pitch web form (record the URL)
    "none",               # explicitly no contact channel recorded
}

# Recorded, but NOT a pitch channel. A corresponding-author address is published for
# scientific correspondence; using it for outreach is off-purpose, so it is kept with a
# warning label and the renderers mark it as such rather than listing it as a way in.
RESTRICTED_CONTACT_KINDS = {"scientific_correspondence"}

# Never recorded. The value is stripped and the run warns.
FORBIDDEN_CONTACT_KINDS = {
    "personal_email",
    "personal_handle",
    "phone",
    "scraped",
    "inferred",
}


# --- Cost -----------------------------------------------------------------------
# `cost` is free text, not a vocabulary: "Free", "EUR 800-1,500 full day", "Venue hire —
# quote needed". Any class can carry it — editorial coverage is free, a photographer and a
# venue are not — so it is a shared column rather than a Creative-only field.
#
# An ABSENT cost renders as "—" meaning **not established**, never "free". Treating
# unknown as free is how a campaign budget gets a surprise in it, so the renderers say
# "not established" and the reference docs say so too.
COST_UNKNOWN = "—"


def cost_of(partner):
    """The cost of engaging this partner, or None when it was never established.

    ``rate_note`` is the legacy Creative-only name and is accepted as an alias, the same
    way event-discovery accepts a flat ``deadline`` alongside typed ``deadlines``.
    """
    for field in ("cost", "rate_note"):
        value = partner.get(field)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


# Cost values that mean "no money changes hands". Matched on the FIRST word, because a
# cost is almost always qualified — "Free — editorial", "Free (member rate)" — and an
# exact-match check put those in the paid column of the budget.
FREE_COST_WORDS = {"free", "none", "no", "gratis", "n/a", "na", "nil", "zero"}


def is_free(value):
    """True when a cost string means nothing is payable. False for None (unknown != free)."""
    if value is None:
        return False
    words = str(value).strip().lower().replace("—", " ").replace("-", " ").split()
    return bool(words) and words[0].strip("().,:;") in FREE_COST_WORDS


def warn(message):
    """Print a WARNING to stderr (stdout is reserved for machine-readable output)."""
    print(f"WARNING: {message}", file=sys.stderr)


def parse_date(value):
    """Parse an ISO ``YYYY-MM-DD`` string into a ``date``.

    Returns ``None`` for empty/None input or anything that does not parse, so callers
    can decide how to handle a missing or malformed date.
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
    """Write ``data`` as pretty UTF-8 JSON (keeps non-ASCII partner names intact)."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def normalise_name(value):
    """Lowercase, strip punctuation and collapse whitespace, for identity comparison.

    Unlike event-discovery's equivalent this does NOT strip years: a partner is a
    persistent entity, not a dated edition, so there is no year to remove and a digit
    in a name (``Nature Africa 2.0``) is part of the name.
    """
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def domain_of(url):
    """Extract a bare lowercase hostname from a URL, without importing urllib.

    Drops scheme, credentials, port, path and a leading ``www.``. Returns "" when the
    input has no recognisable host, so callers can fall back to name-based identity.
    """
    text = str(url or "").strip().lower()
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    text = text.split("/")[0].split("?")[0].split("#")[0]
    text = text.split("@")[-1].split(":")[0]
    if text.startswith("www."):
        text = text[4:]
    return text


def partner_key(partner):
    """Stable identity for a partner, used for both in-run and cross-run dedup.

    Prefers the organisation domain — the same outlet reached via two different byline
    URLs is one partner — and falls back to the normalised name when no host parses.
    A person is keyed within their organisation, so two journalists at the same outlet
    stay distinct.
    """
    org = normalise_name(partner.get("org") or partner.get("name"))
    host = domain_of(partner.get("org_url") or partner.get("url"))
    person = normalise_name(partner.get("person"))
    base = host or org
    return f"{base}||{person}"


def check_vocabulary(partner):
    """Return a list of human-readable vocabulary errors (empty = all values allowed)."""
    checks = (
        ("class", CLASS_VALUES),
        ("scope", SCOPE_VALUES),
        ("reach", REACH_VALUES),
        ("warmth", WARMTH_VALUES),
        ("priority", PRIORITY_VALUES),
        ("action", ACTION_VALUES),
    )
    errors = []
    for field, allowed in checks:
        value = partner.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue  # absence is handled by validate_partner / defaults, not here
        if value not in allowed:
            errors.append(f"{field}={value!r} not in {list(allowed)}")
    return errors


def validate_partner(partner):
    """Return a list of missing required fields for ``partner`` (empty = valid)."""
    if not isinstance(partner, dict):
        return list(REQUIRED_PARTNER_FIELDS)
    missing = []
    for field in REQUIRED_PARTNER_FIELDS:
        value = partner.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing

def screen_contacts(partner):
    """Apply the contact policy to ``partner['contacts']`` in place; return warning notes.

    **This lives here, not in filter_and_sort.py, so that every path which RENDERS a
    contact can enforce it.** It used to live in the screening script alone, which meant
    `render_dossier.py` printed a hand-written target's contacts verbatim — a forbidden
    `personal_email` reached the page, and a `scientific_correspondence` address rendered
    without its "not a pitch channel" label — while `data-handling.md` claimed the policy
    was enforced "on every run". A policy that only one of three entry points applies is
    prose with extra steps.

    Accepts either a single ``contact`` object or a ``contacts`` list of
    ``{"kind": ..., "value": ...}``. An unrecognised kind is treated as forbidden —
    **fail closed**. A new channel kind must be added to ``ALLOWED_CONTACT_KINDS``
    deliberately, after someone has decided it is a channel published for the purpose of
    being contacted; the default for anything unreviewed is to strip it.

    Idempotent: re-screening an already-screened list is a no-op, so piping a pool through
    the screening script and then rendering it does not double-warn.
    """
    raw = partner.get("contacts")
    if raw is None and partner.get("contact") is not None:
        raw = [partner["contact"]]
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raw = []

    notes = []
    cleaned = []
    for entry in raw:
        if not isinstance(entry, dict):
            notes.append(f"discarded a non-object contact entry ({entry!r})")
            continue
        kind = str(entry.get("kind") or "").strip().lower()
        value = str(entry.get("value") or "").strip()
        if kind == "none" or not value:
            continue
        if kind in FORBIDDEN_CONTACT_KINDS:
            notes.append(f"stripped a {kind} contact (forbidden by the contact policy)")
            continue
        if kind not in ALLOWED_CONTACT_KINDS and kind not in RESTRICTED_CONTACT_KINDS:
            notes.append(
                f"stripped an unrecognised contact kind {kind!r} — the policy fails "
                "closed; add it to ALLOWED_CONTACT_KINDS only after review"
            )
            continue
        cleaned.append({
            "kind": kind,
            "value": value,
            "restricted": kind in RESTRICTED_CONTACT_KINDS,
        })

    partner["contacts"] = cleaned
    partner.pop("contact", None)
    partner["has_contact"] = any(not c["restricted"] for c in cleaned)
    return notes
