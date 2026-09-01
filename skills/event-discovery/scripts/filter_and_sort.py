#!/usr/bin/env python3
"""Normalise and order the classified event pool.

Reads the JSON array Claude assembled in Step 5, then deterministically:
  * drops events missing any required field (WARNING, continues);
  * drops events whose start_date is before the window start (today by default)
    or after the window end;
  * de-duplicates recurring series by normalised (name-without-year, location);
  * flags whether each event's deadline falls within the window (sets the 🗓️ marker);
  * sorts by start_date, then name.

Usage:
  python scripts/filter_and_sort.py --in pool.json --from 2026-07-11 --to 2027-04-11 --out clean.json

Exit code 0 on success (even if everything is dropped); 1 only on an unreadable
input file (handled in _common.read_json).
"""

import argparse
import json
import os
import re
import sys

from _common import parse_date, read_json, validate_event, warn, write_json

DEADLINE_MARKER = "🗓️"
BURSARY_MARKER = "💰"
# Set by Claude in Step 5 for Slack-sourced events; re-applied here when a duplicate
# merge carries a teammate's credit onto an already-kept copy.
SHARED_MARKER = "💬"
# The documented ribbon order (references/classification.md). Markers arrive from three
# places — Claude's ⭐🌍🎓💻💬, this script's 💰🗓️, and a 💬 carried over by a duplicate
# merge — so the string is only in the right order if it is explicitly sorted.
MARKER_ORDER = ("⭐", "🌍", "🎓", "💻", "💬", "💰", "🗓️")


def order_markers(markers):
    """Return the ribbon in the documented fixed order.

    Anything unrecognised is preserved at the end rather than dropped: a marker written
    without its variation selector, or a new one added to classification.md before this
    tuple is updated, must not silently vanish from a published report.
    """
    text = str(markers or "")
    ordered = [m for m in MARKER_ORDER if m in text]
    leftover = text
    for m in ordered:
        leftover = leftover.replace(m, "")
    return "".join(ordered) + leftover
# Ledger schema version. v1 keyed on (name-without-year, location); v2 appends the
# event's start-date year so a new edition of a recurring series is a distinct key.
# Bump this whenever series_key_str's output format changes — load_ledger warns on
# an older file so the one-time re-show of seen events isn't a mystery.
LEDGER_VERSION = 2
# bursary field values that mean "no real support" (so no 💰 marker)
NO_BURSARY_VALUES = {"", "none", "no", "n/a", "na", "unknown"}


def has_bursary(event):
    """True when the bursary field names real financial aid / travel support."""
    value = str(event.get("bursary", "") or "").strip().lower()
    return value not in NO_BURSARY_VALUES


# Recognised deadline types, in the order we surface same-date entries.
DEADLINE_TYPES = ("abstract", "early_bird", "registration", "bursary")


def collect_in_window_deadlines(event, window_start, window_end):
    """Return the event's in-window typed deadlines as [{"type", "date"}], date-sorted.

    Accepts the typed ``deadlines`` object; falls back to a legacy flat ``deadline``
    string (treated as a ``registration`` deadline) so older pools still work.
    """
    raw = event.get("deadlines")
    if not isinstance(raw, dict):
        raw = {}
        if event.get("deadline"):
            raw = {"registration": event.get("deadline")}

    found = []
    for dtype, dvalue in raw.items():
        parsed = parse_date(dvalue)
        if parsed is not None and in_window(parsed, window_start, window_end):
            found.append({"type": dtype, "date": parsed.isoformat()})
    order = {t: i for i, t in enumerate(DEADLINE_TYPES)}
    found.sort(key=lambda d: (d["date"], order.get(d["type"], len(order))))
    return found


def normalise_series_key(event):
    """Build a within-run dedup key that ignores the year, so 'Indaba 2026' and
    'Deep Learning Indaba' (mentioned without a year in a different search hit)
    collapse to the same specific event. Used only to catch the same single
    event surfacing twice in one sweep — NOT for cross-run ledger identity
    (see ``series_key_str``), where a new year must stay distinguishable.
    """
    name = str(event.get("name", "")).lower()
    name = re.sub(r"\b(19|20)\d{2}\b", "", name)        # strip 4-digit years
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()      # collapse punctuation
    location = str(event.get("location", "")).lower().strip()
    return (name, location)


def series_key_str(event):
    """Stable string form of the CROSS-RUN ledger key.

    Includes the event's start-date year on top of the year-stripped
    name+location: the ledger exists to stop the *same* edition from being
    re-shown in a later report, not to hide next year's edition just because
    an earlier year's was already reported. A recurring series (e.g. "GCC
    2026") must always show again once "GCC 2027" rolls around, even at the
    same venue.
    """
    name, location = normalise_series_key(event)
    start = parse_date(event.get("start_date"))
    year = start.year if start is not None else "unknown"
    return f"{name}||{location}||{year}"


def add_to_ledger(ledger, events, first_seen):
    """Record `events` in `ledger` (in place). Returns how many were new.

    Lives here beside the key function so ``update_ledger.py`` records events exactly the
    way ``--hide-seen`` later looks them up; two implementations would drift and the
    symptom would be events silently repeating or silently vanishing.
    """
    added = 0
    for event in events:
        kstr = series_key_str(event)
        if kstr in ledger:
            continue
        start = parse_date(event.get("start_date"))
        ledger[kstr] = {
            "name": event.get("name"),
            "url": event.get("url"),
            "year": start.year if start is not None else None,
            "first_seen": first_seen,
        }
        added += 1
    return added


def load_ledger(path):
    """Load the seen-events ledger (key_str -> record). Missing/invalid file -> {}."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        warn(f"could not read ledger {path} ({exc}); treating all events as new")
        return {}
    if not isinstance(data, dict):
        return {}
    version = data.get("version", 1)
    if version < LEDGER_VERSION:
        warn(f"ledger {path} is v{version}; keys now carry the event year "
             f"(v{LEDGER_VERSION}), so none of its entries will match. Previously-seen "
             "editions re-appear once in this run, then are recorded under the new "
             "format and suppressed again from the next run on.")
    return data.get("events", {})


def save_ledger(path, events_map):
    """Write the ledger back as {'version': LEDGER_VERSION, 'events': {...}}.

    Creates the parent directory if needed. SKILL.md passes
    ``--ledger ~/.ersilia/events_seen.json`` on *every* run, and that directory does
    not exist on a fresh machine — without this the first run crashes here, after the
    cleaned output is already written, so the report succeeds while the ledger is
    silently never recorded and the next run re-shows everything.
    """
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"version": LEDGER_VERSION, "events": events_map}, handle,
                  ensure_ascii=False, indent=2)
        handle.write("\n")


def in_window(event_date, start, end):
    return start <= event_date <= end


def main(argv=None):
    parser = argparse.ArgumentParser(description="Filter, dedup and sort the event pool.")
    parser.add_argument("--in", dest="infile", required=True, help="input pool JSON")
    parser.add_argument("--out", dest="outfile", required=True, help="output cleaned JSON")
    parser.add_argument("--from", dest="date_from", required=True, help="window start YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, help="window end YYYY-MM-DD")
    parser.add_argument("--ledger", default=None,
                        help="path to a seen-events ledger JSON; events already in it are "
                             "tagged '(seen)'. READ-ONLY unless --update-ledger is passed")
    parser.add_argument("--update-ledger", dest="update_ledger", action="store_true",
                        help="also WRITE this run's events into --ledger. Do not use in the "
                             "normal flow: rendering happens before the Step 7a approval "
                             "gate, so writing here marks events seen even when the report "
                             "is never published, and they never resurface. Step 8 calls "
                             "update_ledger.py after a successful push instead.")
    parser.add_argument("--hide-seen", dest="hide_seen", action="store_true",
                        help="drop events already in the --ledger instead of tagging them "
                             "(for a 'what's new since last run' report)")
    args = parser.parse_args(argv)

    window_start = parse_date(args.date_from)
    window_end = parse_date(args.date_to)
    if window_start is None or window_end is None:
        print("ERROR: --from and --to must be ISO dates (YYYY-MM-DD)", file=sys.stderr)
        sys.exit(1)
    if window_start > window_end:
        print("ERROR: --from is after --to", file=sys.stderr)
        sys.exit(1)

    pool = read_json(args.infile)
    if not isinstance(pool, list):
        print("ERROR: input JSON must be an array of event objects", file=sys.stderr)
        sys.exit(1)

    ledger = load_ledger(args.ledger) if args.ledger else {}

    kept = []
    seen_series = {}
    counts = {"input": len(pool), "invalid": 0, "out_of_window": 0,
              "duplicate": 0, "beyond_window": 0, "seen": 0}

    for event in pool:
        missing = validate_event(event)
        if missing:
            counts["invalid"] += 1
            name = event.get("name", "<unnamed>") if isinstance(event, dict) else "<non-object>"
            warn(f"dropping '{name}': missing required field(s): {', '.join(missing)}")
            continue

        start = parse_date(event.get("start_date"))
        if start is None:
            # A team-shared event whose official page has not announced dates yet is
            # kept and flagged, per SKILL.md Step 2a. It cannot be window-filtered or
            # date-sorted, so it bypasses both and renders in its own section. Everything
            # else with an unusable date is still dropped — never date-guessed.
            if str(event.get("shared_by") or "").strip():
                event["undated"] = True
                key = normalise_series_key(event)
                if key in seen_series:
                    counts["duplicate"] += 1
                    warn(f"dropping duplicate undated '{event['name']}'")
                    continue
                seen_series[key] = event
                kept.append(event)
                warn(f"keeping undated team-shared '{event['name']}' "
                     f"(shared by {event['shared_by']}) — no dates on the official page")
                continue
            counts["invalid"] += 1
            warn(f"dropping '{event['name']}': unparseable start_date {event.get('start_date')!r}")
            continue

        # Collect typed deadlines that fall in-window (legacy flat `deadline` still works).
        in_window_deadlines = collect_in_window_deadlines(event, window_start, window_end)
        event_in_window = in_window(start, window_start, window_end)

        # Past events (start before the window) are always excluded, even if some
        # deadline field is (spuriously) in-window. A future event beyond the window
        # is kept ONLY if a deadline still lands inside it — otherwise a far-off event
        # with an imminent deadline would vanish.
        if start < window_start:
            counts["out_of_window"] += 1
            warn(f"dropping '{event['name']}': start_date {start} is before window start {window_start}")
            continue
        if not event_in_window and not in_window_deadlines:
            counts["out_of_window"] += 1
            warn(f"dropping '{event['name']}': start_date {start} beyond window, no in-window deadline")
            continue

        key = normalise_series_key(event)
        if key in seen_series:
            counts["duplicate"] += 1
            # Carry the teammate's credit onto the surviving copy before discarding this
            # one. An event can arrive twice — once from the web sweep, once from the
            # Slack sweep — and whichever landed first wins. Without this merge the
            # `shared_by`/💬 attribution is silently lost whenever the web sweep happened
            # to find it too, which is exactly the "don't silently discard a teammate's
            # contribution" rule the Slack step is built around.
            survivor = seen_series[key]
            if event.get("shared_by") and not survivor.get("shared_by"):
                survivor["shared_by"] = event["shared_by"]
                if SHARED_MARKER not in (survivor.get("markers") or ""):
                    survivor["markers"] = order_markers(
                        (survivor.get("markers") or "") + SHARED_MARKER)
                warn(f"duplicate '{event['name']}' also shared in Slack — "
                     f"carried shared_by={event['shared_by']!r} onto the kept copy")
            else:
                warn(f"dropping duplicate series occurrence '{event['name']}' "
                     "(kept the earlier one)")
            continue
        seen_series[key] = event

        # Cross-run ledger: tag (or, with --hide-seen, drop) events seen in a prior run.
        seen_before = args.ledger is not None and series_key_str(event) in ledger
        if seen_before and args.hide_seen:
            counts["seen"] += 1
            warn(f"hiding already-seen '{event['name']}' (--hide-seen)")
            continue
        event["seen_before"] = seen_before

        if not event_in_window:
            counts["beyond_window"] += 1

        # Append the script-derived markers in fixed order: 💰 (bursary) then 🗓️ (deadline).
        markers = str(event.get("markers", "") or "")
        bursary_available = has_bursary(event)
        if bursary_available and BURSARY_MARKER not in markers:
            markers = markers + BURSARY_MARKER
        if in_window_deadlines and DEADLINE_MARKER not in markers:
            markers = markers + DEADLINE_MARKER

        event["markers"] = order_markers(markers)
        event["bursary_available"] = bursary_available
        event["deadlines_in_window"] = in_window_deadlines
        event["deadline_within_window"] = bool(in_window_deadlines)
        event["beyond_window"] = not event_in_window
        event["_start"] = start.isoformat()  # normalised sort key, dropped before write

        kept.append(event)

    # Undated team-shared events carry no `_start`; sort them last rather than crashing.
    kept.sort(key=lambda e: (e.get("_start") or "9999-99-99", str(e.get("name", "")).lower()))
    for event in kept:
        event.pop("_start", None)

    write_json(args.outfile, kept)

    # The ledger is READ-ONLY here by default. See add_to_ledger's docstring for why.
    if args.ledger is not None and args.update_ledger:
        added = add_to_ledger(ledger, kept, args.date_from)
        save_ledger(args.ledger, ledger)
        warn(f"ledger updated: {added} new, {len(ledger)} total -> {args.ledger}")
    elif args.ledger is not None:
        warn(f"ledger read-only this run ({len(ledger)} entries); "
             "run scripts/update_ledger.py after a successful publish (SKILL.md Step 8)")
    unverified = sum(1 for e in kept if not e.get("verified", True))
    print(
        f"kept {len(kept)} / {counts['input']} events "
        f"(dropped: {counts['invalid']} invalid, "
        f"{counts['out_of_window']} out-of-window, "
        f"{counts['duplicate']} duplicate, "
        f"{counts['seen']} already-seen) -> {args.outfile}"
    )
    if counts["beyond_window"]:
        warn(f"{counts['beyond_window']} kept event(s) fall beyond the window but have an "
             "in-window deadline — shown in a separate 'beyond the window' section")
    if unverified:
        warn(f"{unverified} kept event(s) are unverified (verified=false) — flagged with † in the report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
