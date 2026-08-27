#!/usr/bin/env python3
"""Normalise, screen and rank the classified partner pool.

Reads the JSON array Claude assembled during the sweep, then deterministically:
  * drops partners missing any required field (WARNING, continues);
  * rejects values outside the controlled vocabularies;
  * enforces the contact policy — forbidden channel kinds are stripped, not kept;
  * drops partners already in the known-partners list (an existing relationship is
    not a new opportunity);
  * de-duplicates within the run by (org domain or name, person);
  * tags or drops partners seen in an earlier run, via the ledger;
  * derives the marker ribbon;
  * ranks by priority, then warmth, then reach, then name.

Usage:
  python scripts/filter_and_sort.py --in pool.json --out clean.json \
      --known references/known-partners.md \
      --ledger ~/.ersilia/partners_seen.json --hide-seen

Exit code 0 on success (even if everything is dropped); 1 only on an unreadable or
malformed input file.
"""

import argparse
import json
import os
import re
import sys
from datetime import date

from _common import (
    ALLOWED_CONTACT_KINDS,
    FORBIDDEN_CONTACT_KINDS,
    PRIORITY_VALUES,
    REACH_VALUES,
    RESTRICTED_CONTACT_KINDS,
    WARMTH_VALUES,
    check_vocabulary,
    domain_of,
    normalise_name,
    parse_date,
    partner_key,
    read_json,
    validate_partner,
    warn,
    write_json,
)

# Ledger schema version. v1 keys on (org domain or name, person) with NO date component
# — deliberately unlike event-discovery's v2 key, which appends the event year. A
# conference has editions; a journalist does not. Bump this only if partner_key changes.
LEDGER_VERSION = 1

# Contact-by is inside the urgency window (campaign mode). U+23F1 is a BMP character,
# so unlike 🏠🌍💻📣🤝 it survives the Drive Doc conversion — see render_sweep.py.
CLOCK_MARKER = "⏱️"
URGENT_WINDOW_DAYS = 14
HIGH_MARKER = "⭐"
LOCAL_MARKER = "🏠"
SOUTH_MARKER = "🌍"
OSS_MARKER = "💻"
REACH_MARKER = "📣"
WARM_MARKER = "🤝"
CONTACT_MARKER = "✉️"
# The documented ribbon order (references/classification.md). Markers come from Claude's
# classification and from this script, so the string is only in the right order if it is
# explicitly sorted.
# ⏱️ leads the ribbon: in campaign mode urgency outranks every other signal, and a
# reader scanning the left edge of the page should hit it first.
MARKER_ORDER = (CLOCK_MARKER, HIGH_MARKER, LOCAL_MARKER, SOUTH_MARKER, OSS_MARKER,
                REACH_MARKER, WARM_MARKER, CONTACT_MARKER)

# Rank orders. Lower index sorts first.
PRIORITY_RANK = {v: i for i, v in enumerate(PRIORITY_VALUES)}
WARMTH_RANK = {v: i for i, v in enumerate(reversed(WARMTH_VALUES))}
REACH_RANK = {v: i for i, v in enumerate(reversed(REACH_VALUES))}


def order_markers(markers):
    """Return the ribbon in the documented fixed order.

    Anything unrecognised is preserved at the end rather than dropped: a marker written
    without its variation selector, or a new one added to classification.md before this
    tuple is updated, must not silently vanish from a report.
    """
    text = str(markers or "")
    ordered = [m for m in MARKER_ORDER if m in text]
    leftover = text
    for m in ordered:
        leftover = leftover.replace(m, "")
    return "".join(ordered) + leftover


def normalise_contacts(partner):
    """Apply the contact policy in place. Returns a list of policy notes for warnings.

    Accepts either a single ``contact`` object or a ``contacts`` list of
    ``{"kind": ..., "value": ...}``. An unrecognised kind is treated as forbidden —
    **fail closed**. A new channel kind must be added to ``ALLOWED_CONTACT_KINDS``
    deliberately, after someone has decided it is a channel published for the purpose
    of being contacted; the default for anything unreviewed is to strip it.
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


def load_known(path):
    """Load the known-partners exclusion list.

    Only **bullet lines inside the `## Entries` section** are treated as entries. That
    restriction is deliberate and was added after the first real run: an earlier version
    parsed every line that was not blank, not a heading and not fenced, which turned the
    file's own explanatory prose into 26 "organisation name" entries. Nothing collided by
    luck — a whole sentence never equals an organisation name — but a short prose bullet
    would, and it would suppress a real candidate silently, which is the worst failure
    mode this file has.

    Within `## Entries`: fenced blocks are skipped (the file documents its format with an
    example), HTML comments are skipped, `**bold**` is stripped, and text after an em dash
    or a double-space `#` is a per-entry comment. An entry is matched as either a domain
    (contains a `.`, no spaces) or an organisation name.
    """
    names, domains = set(), set()
    if not path:
        return names, domains
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        warn(f"known-partners file {path} not found; treating every partner as new")
        return names, domains
    except OSError as exc:
        warn(f"could not read known-partners file {path} ({exc}); treating every partner as new")
        return names, domains

    in_entries = False
    in_fence = False
    saw_section = False
    for line in lines:
        entry = line.strip()

        if entry.startswith("```") or entry.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        if entry.startswith("#"):
            # A heading either opens the entries section or closes it.
            in_entries = entry.lower().lstrip("# ").startswith("entries")
            saw_section = saw_section or in_entries
            continue
        if not in_entries or not entry:
            continue
        # Only bullets are entries; prose inside the section is ignored.
        if not re.match(r"^[-*]\s+", entry):
            continue
        entry = re.sub(r"^[-*]\s+", "", entry)
        entry = re.split(r"\s+\u2014|\s{2}#", entry)[0].strip()
        entry = entry.replace("**", "").replace("`", "").strip()
        if not entry or entry.startswith("<!--"):
            continue
        if "." in entry and " " not in entry:
            domains.add(domain_of(entry))
        else:
            names.add(normalise_name(entry))

    if not saw_section:
        warn(f"known-partners file {path} has no '## Entries' section; nothing was "
             "loaded, so every partner is treated as new")
    return names, domains


def is_known(partner, known_names, known_domains):
    """True when this partner is already a relationship listed in known-partners."""
    host = domain_of(partner.get("org_url") or partner.get("url"))
    if host and host in known_domains:
        return True
    for field in ("org", "name"):
        if normalise_name(partner.get(field)) in known_names:
            return True
    return False


def load_ledger(path):
    """Load the seen-partners ledger (key -> record). Missing/invalid file -> {}."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        warn(f"could not read ledger {path} ({exc}); treating all partners as new")
        return {}
    if not isinstance(data, dict):
        return {}
    version = data.get("version", 1)
    if version < LEDGER_VERSION:
        warn(f"ledger {path} is v{version}; the key format has changed (v{LEDGER_VERSION}), "
             "so previously-seen partners re-appear once in this run, then are recorded "
             "under the new format and suppressed again from the next run on.")
    return data.get("partners", {})


def save_ledger(path, partners_map):
    """Write the ledger back as {'version': LEDGER_VERSION, 'partners': {...}}.

    Creates the parent directory if needed: SKILL.md passes
    ``--ledger ~/.ersilia/partners_seen.json`` on every run and that directory does not
    exist on a fresh machine. Without this the first run crashes here, *after* the
    cleaned output is written — so the sweep looks successful while the ledger is
    silently never recorded and the next run re-shows everything.
    """
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"version": LEDGER_VERSION, "partners": partners_map}, handle,
                  ensure_ascii=False, indent=2)
        handle.write("\n")


# Fields that carry information worth preserving across a duplicate merge.
MERGEABLE_FIELDS = ("person", "role", "org", "org_url", "hook", "next_step",
                    "recent_work", "warm_paths", "priorities")

# Fields whose completeness decides which copy becomes the merge base. `hook` and
# `next_step` are weighted: they are the two fields that make a row actionable, so a copy
# that researched them properly should win even if it is otherwise sparser.
COMPLETENESS_WEIGHTS = {
    "hook": 3, "next_step": 3, "role": 1, "org_url": 1,
    "recent_work": 2, "warm_paths": 2, "contacts": 2, "priorities": 1,
}


def _is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict)):
        return not value
    return False


def completeness(partner):
    """Score how much usable information a partner row carries.

    Used to pick the base copy when the same partner arrives twice. Longer lists score
    higher, capped, so one well-researched row beats one with a single token entry
    without letting a list of ten thin items dominate.
    """
    score = 0
    for field, weight in COMPLETENESS_WEIGHTS.items():
        value = partner.get(field)
        if _is_empty(value):
            continue
        if isinstance(value, (list, tuple)):
            score += weight * min(len(value), 3)
        else:
            score += weight
    return score


def merge_duplicate(base, other):
    """Fold ``other`` into ``base`` in place. Returns notes on what changed.

    Dedup cannot simply keep whichever copy was written first: the same outlet arrives
    from a byline page and a tag page in either order, and the richer copy is not
    reliably the earlier one. The caller therefore picks the more *complete* copy as
    ``base`` (see ``completeness``) and folds the other into it — so a thin row can never
    overwrite a researched ``hook`` just by arriving first. What remains here is filling
    genuinely empty fields, upgrading the ranked axes, and unioning the contacts.

    event-discovery learned the same lesson with a teammate's `shared_by` credit; the
    shape of the fix is the same, but the stakes are higher for a partner row, where the
    hook *is* the deliverable.
    """
    notes = []
    for field in MERGEABLE_FIELDS:
        if _is_empty(base.get(field)) and not _is_empty(other.get(field)):
            base[field] = other[field]
            notes.append(f"filled empty {field}")

    # Lower rank index is the stronger value for all three ranked axes.
    for field, ranks in (("warmth", WARMTH_RANK), ("priority", PRIORITY_RANK),
                         ("reach", REACH_RANK)):
        current, incoming = base.get(field), other.get(field)
        if incoming is None or incoming == current:
            continue
        if ranks.get(incoming, len(ranks)) < ranks.get(current, len(ranks)):
            base[field] = incoming
            notes.append(f"upgraded {field} {current!r} -> {incoming!r}")

    # Contacts are additive: two pages can publish two different legitimate channels.
    incoming_contacts = other.get("contacts") or []
    if incoming_contacts:
        existing = {(c.get("kind"), c.get("value")) for c in (base.get("contacts") or [])}
        added = [c for c in incoming_contacts if (c.get("kind"), c.get("value")) not in existing]
        if added:
            base["contacts"] = (base.get("contacts") or []) + added
            base["has_contact"] = any(not c.get("restricted") for c in base["contacts"])
            notes.append(f"added {len(added)} contact channel(s)")

    # An unverified copy must never launder a verified one into looking confirmed, and a
    # verified copy should not be demoted by a sloppier duplicate: keep the strictest
    # claim only when the base is the one lacking verification.
    if base.get("verified", True) and not other.get("verified", True):
        notes.append("kept base's verified=true (duplicate was unverified)")

    return notes


# --- Link freshness ------------------------------------------------------------
# A recurring series keeps a generic landing page ("/opentechweek") that renders whichever
# edition the site currently shows, and year-specific pages that never move. Citing either
# the wrong year, or a generic page as if it were verified for this year, produces a link a
# reader clicks and lands on LAST year's event — worse than no link, because it looks
# checked. Flagged in a real report by a reader, which is exactly the wrong way to find it.
#
# Scope note: only the PRIMARY link is checked. `recent_work` is *supposed* to carry older
# items — that is what makes it evidence — so a 2024 byline there is correct, not stale.
YEAR_RE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


def link_year_notes(partner, reference_year):
    """Return (notes, stale) for a partner whose primary link cites an old edition.

    ``reference_year`` is the occasion year in campaign mode, else the run year. A year
    LATER than the reference is not flagged: linking next year's edition is forward
    planning, not staleness.
    """
    notes = []
    stale = False

    for field in ("url", "org_url"):
        value = str(partner.get(field) or "")
        for found in YEAR_RE.findall(value):
            year = int(found)
            if year < reference_year:
                notes.append(f"{field} points at the {year} edition, but the target year is "
                             f"{reference_year}")
                stale = True

    edition = partner.get("edition_year")
    if edition is not None:
        try:
            edition = int(edition)
        except (TypeError, ValueError):
            notes.append(f"edition_year={partner.get('edition_year')!r} is not a year")
            edition = None
        if edition is not None and edition < reference_year:
            notes.append(f"the cited page documents the {edition} edition, not {reference_year}")
            stale = True

    return notes, stale


def derive_markers(partner, today=None):
    """Build the marker ribbon from the partner's classified axes.

    ``today`` is only used for the campaign-mode ⏱️ marker; when it is None (the default,
    used by plain sweeps) no urgency marker is set even if a ``contact_by`` is present.
    """
    markers = str(partner.get("markers", "") or "")
    if today is not None:
        contact_by = parse_date(partner.get("contact_by"))
        if contact_by is not None and (contact_by - today).days <= URGENT_WINDOW_DAYS:
            markers += CLOCK_MARKER
    if partner.get("priority") == "High":
        markers += HIGH_MARKER
    if partner.get("scope") == "Local":
        markers += LOCAL_MARKER
    if partner.get("scope") == "Global-South":
        markers += SOUTH_MARKER
    if partner.get("class") == "Open-source":
        markers += OSS_MARKER
    if partner.get("reach") == "Broad":
        markers += REACH_MARKER
    if partner.get("warmth") in ("Shared network", "Warm intro", "Existing contact"):
        markers += WARM_MARKER
    if partner.get("has_contact"):
        markers += CONTACT_MARKER
    # Do NOT de-duplicate with dict.fromkeys here. It dedupes *characters*, and several
    # markers are two-codepoint sequences ending in the same variation selector U+FE0F —
    # so "⏱️…✉️" lost the envelope's selector and rendered as a bare "✉". order_markers
    # already emits each known marker at most once, which is the de-duplication needed.
    return order_markers(markers)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Screen, dedup and rank the partner pool.")
    parser.add_argument("--in", dest="infile", required=True, help="input pool JSON")
    parser.add_argument("--out", dest="outfile", required=True, help="output cleaned JSON")
    parser.add_argument("--known", default=None,
                        help="path to references/known-partners.md; listed partners are "
                             "dropped as existing relationships")
    parser.add_argument("--keep-known", dest="keep_known", action="store_true",
                        help="tag known partners instead of dropping them")
    parser.add_argument("--ledger", default=None,
                        help="path to a seen-partners ledger JSON; partners already in it "
                             "are tagged '(seen)', and the ledger is updated with this run")
    parser.add_argument("--hide-seen", dest="hide_seen", action="store_true",
                        help="drop partners already in the --ledger instead of tagging them")
    parser.add_argument("--order", choices=("priority", "deadline"), default="priority",
                        help="'priority' (default) ranks by priority/warmth/reach for a "
                             "standing sweep; 'deadline' ranks by contact_by for campaign "
                             "mode, where who-to-contact-first is the useful ordering")
    parser.add_argument("--today", default=None,
                        help="reference date YYYY-MM-DD for the ⏱️ urgency marker "
                             "(default: the system date). Only used with --order deadline")
    parser.add_argument("--occasion-date", dest="occasion_date", default=None,
                        help="the campaign's date YYYY-MM-DD; a contact_by falling after "
                             "it is warned about, since contacting someone after the event "
                             "cannot help it land")
    args = parser.parse_args(argv)

    today = parse_date(args.today) or date.today()
    occasion = parse_date(args.occasion_date)
    if args.order == "deadline":
        marker_today = today
    else:
        marker_today = None

    pool = read_json(args.infile)
    if not isinstance(pool, list):
        print("ERROR: input JSON must be an array of partner objects", file=sys.stderr)
        sys.exit(1)

    known_names, known_domains = load_known(args.known)
    ledger = load_ledger(args.ledger) if args.ledger else {}

    kept = []
    seen_keys = {}
    counts = {"input": len(pool), "invalid": 0, "vocabulary": 0, "known": 0,
              "duplicate": 0, "seen": 0, "contacts_stripped": 0, "stale_link": 0}

    # The year a link should point at: the occasion's year in campaign mode, else the run
    # year. Derived once so every row is judged against the same reference.
    reference_year = (occasion or today).year

    for partner in pool:
        missing = validate_partner(partner)
        if missing:
            counts["invalid"] += 1
            name = partner.get("name", "<unnamed>") if isinstance(partner, dict) else "<non-object>"
            warn(f"dropping '{name}': missing required field(s): {', '.join(missing)}")
            continue

        vocab_errors = check_vocabulary(partner)
        if vocab_errors:
            counts["vocabulary"] += 1
            warn(f"dropping '{partner['name']}': {'; '.join(vocab_errors)}")
            continue

        notes = normalise_contacts(partner)
        for note in notes:
            counts["contacts_stripped"] += 1
            warn(f"'{partner['name']}': {note}")

        # Link freshness. A stale primary link forces verified=false rather than merely
        # warning: a row citing last year's edition is, precisely, not verified for this
        # one, and that routes it into the report's † section where the review gate makes
        # someone decide about it.
        year_notes, stale = link_year_notes(partner, reference_year)
        for note in year_notes:
            counts["stale_link"] += 1
            warn(f"'{partner['name']}': {note}")
        if stale:
            partner["stale_link"] = True
            if partner.get("verified", True):
                partner["verified"] = False
                warn(f"'{partner['name']}': marking unverified — the link a reader clicks "
                     "does not go to the target year's edition")

        if is_known(partner, known_names, known_domains):
            if not args.keep_known:
                counts["known"] += 1
                warn(f"dropping '{partner['name']}': already in the known-partners list "
                     "(an existing relationship is not a new opportunity)")
                continue
            partner["known_partner"] = True
        else:
            partner["known_partner"] = False

        # Ledger first, dedup second. Registering a row as the dedup incumbent and *then*
        # dropping it with --hide-seen left seen_keys holding an object absent from `kept`,
        # and the merge's identity lookup crashed on it. Both copies of a duplicate share a
        # partner_key, so both are independently caught here anyway.
        key = partner_key(partner)
        seen_before = args.ledger is not None and key in ledger
        if seen_before and args.hide_seen:
            counts["seen"] += 1
            warn(f"hiding already-seen '{partner['name']}' (--hide-seen)")
            continue
        partner["seen_before"] = seen_before

        if key in seen_keys:
            counts["duplicate"] += 1
            incumbent = seen_keys[key]
            # The more complete copy becomes the base, regardless of arrival order.
            if completeness(partner) > completeness(incumbent):
                base, other, swapped = partner, incumbent, True
            else:
                base, other, swapped = incumbent, partner, False
            merge_notes = merge_duplicate(base, other)
            if swapped:
                # The same object is referenced from both `kept` and `seen_keys`, so the
                # replacement has to happen in both or the report and the ledger diverge.
                # Search by identity, not equality: `list.index` compares dict *contents*,
                # which would match a different partner that happens to look the same.
                position = next((n for n, item in enumerate(kept) if item is incumbent), None)
                if position is None:
                    # Invariant broken: the incumbent is registered but not in `kept`.
                    # Append rather than crash, and say so — a silent swallow here would
                    # hide a real ordering bug (it did once; see ROADMAP.md).
                    warn(f"internal: dedup incumbent for key={key} was not in the kept list; "
                         "appending the merged row instead")
                    kept.append(base)
                else:
                    kept[position] = base
                seen_keys[key] = base
                merge_notes.insert(0, "the later copy was more complete and became the base")
            detail = f"; merged: {', '.join(merge_notes)}" if merge_notes else ""
            warn(f"merged duplicate of '{base.get('name')}' (key={key}){detail}")
            continue
        seen_keys[key] = partner

        kept.append(partner)

    # Markers are derived here, after the loop, NOT when each partner is appended. A
    # later duplicate can merge into an already-kept copy and upgrade its priority,
    # warmth or contacts; markers computed at append time would then be stale, silently
    # dropping the ⭐ / 🤝 / ✉️ the upgrade just earned.
    for partner in kept:
        partner["markers"] = derive_markers(partner, marker_today)

    if args.order == "deadline":
        # Campaign mode. A row with no contact_by sorts last rather than first: an unknown
        # deadline is not an urgent one, and putting it at the top would bury the rows that
        # genuinely need action this week.
        for partner in kept:
            contact_by = parse_date(partner.get("contact_by"))
            partner["contact_by_parsed"] = contact_by.isoformat() if contact_by else None
            if contact_by is None:
                warn(f"'{partner['name']}' has no contact_by date — sorted last. In "
                     "campaign mode this is the field that makes the row actionable.")
            elif contact_by < today:
                warn(f"'{partner['name']}' contact_by {contact_by} has already passed "
                     "— too late for this campaign unless the date is wrong.")
            elif occasion is not None and contact_by > occasion:
                warn(f"'{partner['name']}' contact_by {contact_by} falls AFTER the "
                     f"occasion ({occasion}) — contacting them then cannot help it land.")
        kept.sort(key=lambda p: (
            p.get("contact_by_parsed") or "9999-99-99",
            PRIORITY_RANK.get(p.get("priority"), len(PRIORITY_RANK)),
            str(p.get("name", "")).lower(),
        ))
    else:
        kept.sort(key=lambda p: (
            PRIORITY_RANK.get(p.get("priority"), len(PRIORITY_RANK)),
            WARMTH_RANK.get(p.get("warmth"), len(WARMTH_RANK)),
            REACH_RANK.get(p.get("reach"), len(REACH_RANK)),
            str(p.get("name", "")).lower(),
        ))

    write_json(args.outfile, kept)

    if args.ledger is not None:
        new_to_ledger = 0
        for partner in kept:
            key = partner_key(partner)
            if key not in ledger:
                ledger[key] = {
                    "name": partner.get("name"),
                    "org": partner.get("org"),
                    "url": partner.get("url"),
                    "class": partner.get("class"),
                }
                new_to_ledger += 1
        save_ledger(args.ledger, ledger)
        warn(f"ledger updated: {new_to_ledger} new, {len(ledger)} total -> {args.ledger}")

    unverified = sum(1 for p in kept if not p.get("verified", True))
    print(
        f"kept {len(kept)} / {counts['input']} partners "
        f"(dropped: {counts['invalid']} invalid, "
        f"{counts['vocabulary']} bad-vocabulary, "
        f"{counts['known']} already-known, "
        f"{counts['duplicate']} duplicate, "
        f"{counts['seen']} already-seen) -> {args.outfile}"
    )
    if counts["stale_link"]:
        warn(f"{counts['stale_link']} link-year problem(s) found — a link pointing at an "
             "older edition sends the reader to the wrong event; see the † rows")
    if counts["contacts_stripped"]:
        warn(f"{counts['contacts_stripped']} contact entr(ies) were stripped by the "
             "contact policy — see references/data-handling.md")
    if unverified:
        warn(f"{unverified} kept partner(s) are unverified (verified=false) — flagged with † "
             "in the report; verify or drop them before sharing it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
