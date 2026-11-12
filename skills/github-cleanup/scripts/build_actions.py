"""Turn the item numbers the user approved into the exact gh commands to run.

Only items named with ``--approve`` become commands, so nothing is written that the user
has not approved in this run. The action of each item is the plan's ``proposed`` value,
or the ``action`` in the judgements file (Claude's proposal the user agreed to, or the
user's own choice). Comment text also comes from the judgements file:

    {"<n>": {"action": "close-not-planned", "comment": "Closing: superseded by #12.",
             "why": "one line shown to the user"}}

``--reject`` marks items as "keep, never propose again": their key goes to
references/ignore-list.json with the reason. Nothing is written to GitHub for them.

Refuses: unknown or already-applied items, flags, an action the item does not allow,
a comment action with no comment, and anything the apply_actions.py whitelist rejects.

Usage:
    python build_actions.py --approve 1,2,5,10-40 [--judgements /tmp/github_cleanup/judgements.json]
    python build_actions.py --reject 7 --reason "long-running tracking issue"
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from urllib.parse import quote

from _common import ORG, REFS, WORK_DIR, die, read_json, write_json
from apply_actions import allowed

ISSUE_REASONS = {"close-completed": "completed", "close-not-planned": "not planned"}


def _nums(text: str | None) -> list[int]:
    """Parse "1,3,10-25" into a sorted list of item numbers."""
    out: set[int] = set()
    for part in (text or "").replace(" ", "").split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return sorted(out)


def commands_for(item: dict, action: str, comment: str | None) -> list[dict]:
    """The gh call(s) for one approved item, each with how to check it took effect."""
    repo = f"{ORG}/{item.get('repo')}"
    num = str(item.get("number"))
    if item["kind"] == "notification":
        tid = item["thread_id"]
        done = {
            "command": ["gh", "api", "-X", "DELETE", f"notifications/threads/{tid}"],
            "check": None,
        }
        if action == "unsubscribe":
            unsub = {
                "command": [
                    "gh",
                    "api",
                    "-X",
                    "DELETE",
                    f"notifications/threads/{tid}/subscription",
                ],
                "check": {
                    "type": "gone",
                    "api": f"notifications/threads/{tid}/subscription",
                },
            }
            return [unsub, done]
        return [done]
    if item["kind"] == "branch":
        ref = quote(item["branch"], safe="/")
        return [
            {
                "command": [
                    "gh",
                    "api",
                    "-X",
                    "DELETE",
                    f"repos/{repo}/git/refs/heads/{ref}",
                ],
                "check": {"type": "gone", "api": f"repos/{repo}/branches/{ref}"},
            }
        ]
    sub = item["kind"]  # "pr" or "issue"
    api = f"repos/{repo}/issues/{num}"
    if action == "comment":
        return [
            {
                "command": ["gh", sub, "comment", num, "-R", repo, "--body", comment],
                "check": None,
            }
        ]
    if action == "close":
        cmd = ["gh", "pr", "close", num, "-R", repo]
        if comment:
            cmd += ["--comment", comment]
        return [{"command": cmd, "check": {"type": "closed", "api": api}}]
    if action in ISSUE_REASONS:
        cmd = [
            "gh",
            "issue",
            "close",
            num,
            "-R",
            repo,
            "--reason",
            ISSUE_REASONS[action],
        ]
        if comment:
            cmd += ["--comment", comment]
        return [{"command": cmd, "check": {"type": "closed", "api": api}}]
    if action == "remove-reviewer":
        return [
            {
                "command": [
                    "gh",
                    "pr",
                    "edit",
                    num,
                    "-R",
                    repo,
                    "--remove-reviewer",
                    item["login"],
                ],
                "check": {
                    "type": "not_in",
                    "api": f"repos/{repo}/pulls/{num}",
                    "field": "requested_reviewers",
                    "login": item["login"],
                },
            }
        ]
    if action == "unassign":
        return [
            {
                "command": [
                    "gh",
                    "issue",
                    "edit",
                    num,
                    "-R",
                    repo,
                    "--remove-assignee",
                    item["login"],
                ],
                "check": {
                    "type": "not_in",
                    "api": api,
                    "field": "assignees",
                    "login": item["login"],
                },
            }
        ]
    die(f"[{item['n']}] no command for action {action!r}")
    return []


def main(argv: list[str] | None = None) -> int:
    """Write actions.json for the approved items; record rejections."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--approve")
    p.add_argument("--reject")
    p.add_argument("--reason")
    p.add_argument("--judgements", default=f"{WORK_DIR}/judgements.json")
    p.add_argument("--plan", default=f"{WORK_DIR}/plan.json")
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--ignore-file", default=str(REFS / "ignore-list.json"))
    args = p.parse_args(argv)

    plan = read_json(args.plan) or die(f"missing {args.plan}")
    by_n = {i["n"]: i for i in plan["items"]}
    judgements = read_json(args.judgements) or {}
    applied = set((read_json(f"{args.work}/applied.json") or {}).get("items", []))
    approve, reject = _nums(args.approve), _nums(args.reject)
    if not approve and not reject:
        die("nothing to do: pass --approve and/or --reject")
    if set(approve) & set(reject):
        die("an item cannot be both approved and rejected")

    for n in approve + reject:
        if n not in by_n:
            die(f"[{n}] is not in the plan")
        if n in applied:
            die(f"[{n}] was already applied in this run")
        if by_n[n]["category"] == "flags":
            die(f"[{n}] is a flag: report only, nothing to write")

    if reject:
        if not args.reason:
            die("--reject needs --reason")
        ignore = read_json(args.ignore_file) or {"entries": []}
        known = {e["key"] for e in ignore["entries"]}
        for n in reject:
            item = by_n[n]
            if item["kind"] == "notification" and not item["key"].startswith(
                ("notif:issue:", "notif:pr:")
            ):
                die(
                    f"[{n}] this notification has no issue or PR to remember; just skip it"
                )
            if item["key"] not in known:
                ignore["entries"].append(
                    {
                        "key": item["key"],
                        "label": item["label"],
                        "reason": args.reason,
                        "date": date.today().isoformat(),
                    }
                )
        write_json(args.ignore_file, ignore)
        print(f"kept for good: {', '.join(map(str, reject))}")

    calls = []
    for n in approve:
        item = by_n[n]
        j = judgements.get(str(n)) or {}
        action = j.get("action") or item.get("proposed")
        if not action:
            die(f"[{n}] has no action: add one to the judgements file first")
        if action not in item["actions"]:
            die(
                f"[{n}] action {action!r} not allowed here; allowed: {', '.join(item['actions'])}"
            )
        comment = (j.get("comment") or "").strip() or None
        if action == "comment" and not comment:
            die(f"[{n}] a comment action needs comment text in the judgements file")
        for c in commands_for(item, action, comment):
            problem = allowed(c["command"])
            if problem:
                die(f"[{n}] refused: {problem}")
            calls.append(
                {
                    "item": n,
                    "key": item["key"],
                    "label": item["label"],
                    "action": action,
                    **c,
                }
            )

    if approve:
        write_json(f"{args.work}/actions.json", {"calls": calls})
        print(
            f"actions.json: {len(calls)} command(s) for item(s) {', '.join(map(str, approve))}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
