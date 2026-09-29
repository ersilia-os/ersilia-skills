#!/usr/bin/env python3
"""Record a published report's events in the seen-events ledger (SKILL.md Step 8).

**Run this only after Step 8's push succeeds.** The ledger's job is to stop an event that
has *already been reported* from being reported again, so the write has to happen after
publication, not before.

``filter_and_sort.py`` used to write it during Step 6 — which runs *before* the Step 7a
approval gate. Rendering a report and then declining to publish therefore marked every
event seen, and none of them ever resurfaced: the opposite of what the ledger is for, and
silent. It bit twice on 2026-09-01, once while preparing that day's own digest.

Usage:
    python update_ledger.py --in /tmp/events_clean.json \
        --ledger ~/.ersilia/events_seen.json --first-seen 2026-09-01
"""

import argparse
import os
import sys

from _common import read_json
from filter_and_sort import add_to_ledger, load_ledger, save_ledger


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add a published report's events to the ledger.")
    ap.add_argument("--in", dest="infile", required=True,
                    help="the cleaned event JSON that was rendered and published")
    ap.add_argument("--ledger", required=True, help="path to the seen-events ledger JSON")
    ap.add_argument("--first-seen", dest="first_seen", required=True,
                    help="the report's date (YYYY-MM-DD), recorded on each new entry")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be added without writing")
    args = ap.parse_args(argv)

    events = read_json(args.infile)
    if not isinstance(events, list):
        print("ERROR: --in must be a JSON array of events", file=sys.stderr)
        return 1

    path = os.path.expanduser(args.ledger)
    ledger = load_ledger(path)
    before = len(ledger)
    added = add_to_ledger(ledger, events, args.first_seen)

    if args.dry_run:
        print(f"dry run: would add {added} event(s); ledger {before} -> {before + added}")
        return 0

    save_ledger(path, ledger)
    print(f"ledger: {before} -> {len(ledger)} events (+{added} from {args.first_seen})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
