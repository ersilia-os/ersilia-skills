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
import re
import sys

from _common import parse_date, read_json, validate_event, warn, write_json

DEADLINE_MARKER = "🗓️"
BURSARY_MARKER = "💰"
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
    """Build a dedup key that ignores the year, so 'Indaba 2026' == 'Indaba 2027'."""
    name = str(event.get("name", "")).lower()
    name = re.sub(r"\b(19|20)\d{2}\b", "", name)        # strip 4-digit years
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()      # collapse punctuation
    location = str(event.get("location", "")).lower().strip()
    return (name, location)


def series_key_str(event):
    """Stable string form of the series key, for JSON ledger storage."""
    return "||".join(normalise_series_key(event))


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
    return data.get("events", {}) if isinstance(data, dict) else {}


def save_ledger(path, events_map):
    """Write the ledger back as {'version': 1, 'events': {...}}."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"version": 1, "events": events_map}, handle, ensure_ascii=False, indent=2)
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
                             "tagged '(seen)', and the ledger is updated with this run")
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
            counts["invalid"] += 1
            warn(f"dropping '{event['name']}': unparseable start_date {event.get('start_date')!r}")
            continue

        # Collect typed deadlines that fall in-window (legacy flat `deadline` still works).
        in_window_deadlines = collect_in_window_deadlines(event, window_start, window_end)
        event_in_window = in_window(start, window_start, window_end)

        # Keep an event whose date is past the window ONLY if a deadline still lands
        # inside it — otherwise a far-off event with an imminent deadline would vanish.
        if not event_in_window and not in_window_deadlines:
            counts["out_of_window"] += 1
            warn(f"dropping '{event['name']}': start_date {start} outside window, no in-window deadline")
            continue

        key = normalise_series_key(event)
        if key in seen_series:
            counts["duplicate"] += 1
            warn(f"dropping duplicate series occurrence '{event['name']}' (kept the earlier one)")
            continue
        seen_series[key] = True

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

        event["markers"] = markers
        event["bursary_available"] = bursary_available
        event["deadlines_in_window"] = in_window_deadlines
        event["deadline_within_window"] = bool(in_window_deadlines)
        event["beyond_window"] = not event_in_window
        event["_start"] = start.isoformat()  # normalised sort key, dropped before write

        kept.append(event)

    kept.sort(key=lambda e: (e["_start"], str(e.get("name", "")).lower()))
    for event in kept:
        event.pop("_start", None)

    write_json(args.outfile, kept)

    # Update the ledger with this run's surfaced events, then persist it.
    if args.ledger is not None:
        new_to_ledger = 0
        for event in kept:
            kstr = series_key_str(event)
            if kstr not in ledger:
                ledger[kstr] = {
                    "name": event.get("name"),
                    "url": event.get("url"),
                    "first_seen": args.date_from,
                }
                new_to_ledger += 1
        save_ledger(args.ledger, ledger)
        warn(f"ledger updated: {new_to_ledger} new, {len(ledger)} total -> {args.ledger}")
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
