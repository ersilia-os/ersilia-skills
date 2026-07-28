"""Pre-flight check: are the skill's references stale?

The skill's reference files (`scope.md`, `airtable-schema.md`, `output-template.md`)
should be revisited periodically — by default every 90 days — so that the repo
taxonomy, the Airtable base/table/field IDs, and the digest format track reality.
The Airtable schema in particular drifts when new `Type` options or fields are added.

This script reads `references/_state.json`, compares `next_refresh_due` to today, and:

- prints `OK` and exits 0 when the references are current,
- prints a `DUE` line on stdout naming `last_refresh_date` and `next_refresh_due`
  and exits 0 when a refresh is due (the skill decides whether to block, warn, or
  prompt — exit code is non-fatal so a digest can still ship if the user defers),
- prints a `WARNING` on stderr and exits 1 if the state file is missing or malformed.

The script does **not** perform the refresh itself. It only flags the state.

Usage:
    python check_references_freshness.py [--state references/_state.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from _common import warn


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--state",
        default=str(Path(__file__).resolve().parent.parent / "references" / "_state.json"),
        help="Path to references/_state.json",
    )
    args = p.parse_args(argv)

    state_path = Path(args.state).expanduser().resolve()
    if not state_path.exists():
        warn(f"references state file not found: {state_path}")
        return 1

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        warn(f"could not parse {state_path}: {e}")
        return 1

    last = state.get("last_refresh_date")
    nxt = state.get("next_refresh_due")
    if not last or not nxt:
        warn("state file is missing last_refresh_date or next_refresh_due")
        return 1

    try:
        last_d = datetime.strptime(last, "%Y-%m-%d").date()
        next_d = datetime.strptime(nxt, "%Y-%m-%d").date()
    except ValueError as e:
        warn(f"bad date in state file: {e}")
        return 1

    today = datetime.utcnow().date()
    if today < next_d:
        days_left = (next_d - today).days
        print(f"OK references last refreshed {last_d.isoformat()}; "
              f"next due {next_d.isoformat()} ({days_left} days)")
        return 0

    days_overdue = (today - next_d).days
    print(f"DUE references last refreshed {last_d.isoformat()}; "
          f"next refresh was due {next_d.isoformat()} "
          f"({days_overdue} day(s) overdue)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
