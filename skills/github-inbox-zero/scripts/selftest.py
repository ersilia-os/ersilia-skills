"""Offline regression test for plan_cleanup.py and the command whitelist. No network.

Each file in ``examples/cases/*.json`` is one case:

    {"about": "...", "now": "2026-11-12T00:00:00Z",
     "inputs": {"notifications": {...}, "mine": {...}, "branches": {...}},
     "ignore": ["issue:repo#1", ...],              # optional
     "rules": {"prs": {"stale_after_days": 10}},   # optional, merged over rules.json
     "expect": [{"key": ..., "category": ..., "proposed"?: ...}],
     "expect_absent": ["<key>", ...]}

Then a fixed set of checks confirms the whitelist in apply_actions.py refuses anything
outside it, and build_actions.commands_for produces whitelisted commands.

Usage:
    python selftest.py [-k name-substring]
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

from _common import SKILL_DIR, load_rules, parse_ts
from apply_actions import allowed
from build_actions import commands_for
from plan_cleanup import build_plan

CASES = SKILL_DIR / "examples" / "cases"


def merged_rules(override: dict | None) -> dict:
    """rules.json with a case's overrides applied one section deep."""
    rules = copy.deepcopy(load_rules())
    for section, values in (override or {}).items():
        rules.setdefault(section, {}).update(values)
    return rules


def run_case(path: Path) -> list[str]:
    """Run one case; return failure messages."""
    case = json.loads(path.read_text(encoding="utf-8"))
    inp = case["inputs"]
    now: datetime = parse_ts(case["now"])
    plan = build_plan(
        inp.get("notifications", {}),
        inp.get("mine", {}),
        inp.get("branches", {}),
        merged_rules(case.get("rules")),
        set(case.get("ignore", [])),
        now,
    )
    by_key = {i["key"]: i for i in plan["items"]}
    fails = []
    for m in case.get("expect", []):
        item = by_key.get(m["key"])
        if item is None:
            fails.append(f"missing {m['key']}")
        elif item["category"] != m["category"]:
            fails.append(
                f"{m['key']}: category {item['category']}, expected {m['category']}"
            )
        elif "proposed" in m and item["proposed"] != m["proposed"]:
            fails.append(
                f"{m['key']}: proposed {item['proposed']}, expected {m['proposed']}"
            )
    for key in case.get("expect_absent", []):
        if key in by_key:
            fails.append(
                f"{key} should not be proposed (got {by_key[key]['category']})"
            )
    return fails


def whitelist_checks() -> list[str]:
    """The whitelist must refuse writes outside the skill's scope."""
    fails = []
    refused = [
        ["gh", "repo", "delete", "ersilia-os/ersilia"],
        ["gh", "api", "-X", "DELETE", "repos/ersilia-os/ersilia"],
        ["gh", "api", "-X", "DELETE", "repos/other-org/x/git/refs/heads/feat"],
        ["gh", "api", "-X", "PATCH", "notifications/threads/1"],
        ["gh", "pr", "merge", "1", "-R", "ersilia-os/x"],
        ["gh", "pr", "close", "1", "-R", "other-org/x"],
        ["gh", "pr", "close", "1", "-R", "ersilia-os/x", "--delete-branch", "yes"],
        ["gh", "issue", "close", "1", "-R", "ersilia-os/x", "--reason", "duplicate"],
        ["gh", "issue", "edit", "1", "-R", "ersilia-os/x", "--add-assignee", "someone"],
    ]
    for cmd in refused:
        if allowed(cmd) is None:
            fails.append(f"whitelist accepted: {' '.join(cmd)}")
    items = [
        ({"kind": "notification", "thread_id": "123", "n": 1}, "unsubscribe", None),
        ({"kind": "branch", "repo": "x", "branch": "feat/a b", "n": 2}, "delete", None),
        (
            {"kind": "pr", "repo": "x", "number": 4, "login": "me", "n": 3},
            "close",
            "Superseded.",
        ),
        (
            {"kind": "pr", "repo": "x", "number": 4, "login": "me", "n": 4},
            "remove-reviewer",
            None,
        ),
        (
            {"kind": "issue", "repo": "x", "number": 5, "login": "me", "n": 5},
            "close-not-planned",
            None,
        ),
        (
            {"kind": "issue", "repo": "x", "number": 5, "login": "me", "n": 6},
            "unassign",
            None,
        ),
        (
            {"kind": "issue", "repo": "x", "number": 5, "login": "me", "n": 7},
            "comment",
            "Still relevant?",
        ),
    ]
    for item, action, comment in items:
        for c in commands_for(item, action, comment):
            why = allowed(c["command"])
            if why:
                fails.append(f"{action}: built a refused command ({why})")
    return fails


def main(argv: list[str] | None = None) -> int:
    """Run every case and the whitelist checks."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("-k", default="")
    args = p.parse_args(argv)
    total = 0
    for path in sorted(CASES.glob("*.json")):
        if args.k not in path.stem:
            continue
        fails = run_case(path)
        total += len(fails)
        print(f"{'ok  ' if not fails else 'FAIL'} {path.stem}")
        for f in fails:
            print(f"     {f}")
    fails = whitelist_checks()
    total += len(fails)
    print(f"{'ok  ' if not fails else 'FAIL'} whitelist")
    for f in fails:
        print(f"     {f}")
    print("all passed" if not total else f"{total} failure(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
