"""Pre-flight: are the reference files due for a re-check against live Airtable?

Reads `references/_state.json` and prints ``OK ...`` or ``DUE ...`` (exit 0 either way;
the skill asks the user whether to refresh or defer). Exit 1 if the state file is
missing or malformed.

Usage:
    python check_references_freshness.py
"""

from __future__ import annotations

import sys
from datetime import date

from _common import SKILL_DIR, read_json, warn


def main() -> int:
    """Print the freshness verdict."""
    state = read_json(SKILL_DIR / "references" / "_state.json")
    try:
        last = date.fromisoformat(state["last_refresh_date"])
        due = date.fromisoformat(state["next_refresh_due"])
    except (TypeError, KeyError, ValueError) as exc:
        warn(f"references/_state.json is missing or malformed: {exc}")
        return 1
    today = date.today()
    if today < due:
        print(
            f"OK references checked {last}; next check due {due} ({(due - today).days} days)"
        )
    else:
        print(
            f"DUE references checked {last}; re-check was due {due} ({(today - due).days} day(s) ago)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
