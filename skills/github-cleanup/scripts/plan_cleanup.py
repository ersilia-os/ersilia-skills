"""Turn the fetched GitHub state into a numbered cleanup plan.

Reads ``notifications.json``, ``mine.json`` and ``branches.json`` from the work folder,
applies ``references/rules.json`` and drops anything in ``references/ignore-list.json``.
Every item lands in exactly one category, in this order:

    notif_closed     notification about an issue/PR that is already closed or merged
    notif_noise      notification that is noise (reason, title pattern, or too old)
    review_requests  pull requests waiting for your review
    stale_prs        your open pull requests with no activity for a while
    stale_issues     open issues you opened or are assigned to, with no activity for a while
    branches         your PR branches whose PR was merged, or closed and abandoned
    flags            report only (for example your PR has merge conflicts)

``proposed`` is the action the script suggests; ``None`` means Claude reads the thread
and proposes one (a judgement), which the user then approves. ``actions`` lists what may
be done to the item; build_actions.py refuses anything else.

Writes ``<work>/plan.json``.

Usage:
    python plan_cleanup.py [--work /tmp/github_cleanup] [--now 2026-11-12T00:00:00Z]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from fnmatch import fnmatch

from _common import (
    ORG,
    WORK_DIR,
    days_since,
    die,
    load_ignore,
    load_rules,
    parse_ts,
    read_json,
    write_json,
)

CATEGORIES = [
    "notif_closed",
    "notif_noise",
    "review_requests",
    "stale_prs",
    "stale_issues",
    "branches",
    "flags",
]


def _ago(days: int | None) -> str:
    return "unknown time" if days is None else f"{days} day(s)"


def plan_notifications(
    data: dict, rules: dict, ignore: set[str], now: datetime
) -> tuple[list[dict], int]:
    """Notification items, plus the number of active threads left alone."""
    items, active = [], 0
    patterns = [re.compile(p, re.IGNORECASE) for p in rules["noise_title_patterns"]]
    for th in data.get("threads", []):
        if th.get("key") and f"notif:{th['key']}" in ignore:
            continue
        base = {
            "key": f"notif:{th.get('key') or th['id']}",
            "thread_id": th["id"],
            "repo": th["repo"],
            "label": f"{th['repo']}: {th['title']}",
            "url": th.get("html_url") or f"https://github.com/{ORG}/{th['repo']}",
            "kind": "notification",
        }
        age = days_since(th.get("updated_at"), now)
        if th.get("state") == "closed":
            what = "merged" if th.get("merged") else "closed"
            items.append(
                {
                    **base,
                    "category": "notif_closed",
                    "proposed": "done",
                    "actions": ["done", "unsubscribe"],
                    "reason": f"the {th['type']} is already {what} ({th['reason']})",
                }
            )
            continue
        why = None
        if th.get("reason") in rules["noise_reasons"]:
            why = f"reason is '{th['reason']}'"
        elif any(p.search(th.get("title") or "") for p in patterns):
            why = "title matches a noise pattern in rules.json"
        elif age is not None and age > rules["old_after_days"]:
            why = f"no activity for {age} days ({th['reason']})"
        if why:
            proposed = (
                "unsubscribe"
                if th.get("reason") in rules["unsubscribe_reasons"]
                else "done"
            )
            items.append(
                {
                    **base,
                    "category": "notif_noise",
                    "proposed": proposed,
                    "actions": ["done", "unsubscribe"],
                    "reason": why,
                }
            )
        else:
            active += 1
    return items, active


def plan_mine(data: dict, rules: dict, ignore: set[str], now: datetime) -> list[dict]:
    """Review requests, stale PRs, stale issues and PR flags."""
    items = []
    login = data.get("login")
    pr_rules, issue_rules = rules["prs"], rules["issues"]

    def base(row: dict, kind: str) -> dict:
        return {
            "key": row["key"],
            "repo": row["repo"],
            "number": row["number"],
            "label": f"{row['repo']}#{row['number']} {row['title']}",
            "url": row["url"],
            "kind": kind,
            "login": login,
        }

    for row in data.get("review_requests", []):
        if row["key"] in ignore:
            continue
        age = days_since(row.get("updated_at"), now)
        waited = age is not None and age > pr_rules["review_request_flag_after_days"]
        items.append(
            {
                **base(row, "pr"),
                "category": "review_requests",
                "proposed": None,
                "actions": ["comment", "remove-reviewer"],
                "reason": f"by {row['author']}, last update {_ago(age)} ago"
                + (" (waiting a long time)" if waited else "")
                + (", draft" if row.get("draft") else ""),
            }
        )

    for row in data.get("my_prs", []):
        if row["key"] in ignore:
            continue
        age = days_since(row.get("updated_at"), now)
        limit = (
            pr_rules["draft_stale_after_days"]
            if row.get("draft")
            else pr_rules["stale_after_days"]
        )
        conflicts = row.get("mergeable_state") == "dirty"
        if age is not None and age > limit:
            extra = []
            if row.get("draft"):
                extra.append("draft")
            if conflicts:
                extra.append("has merge conflicts")
            if row.get("requested_reviewers"):
                extra.append("waiting on " + ", ".join(row["requested_reviewers"]))
            items.append(
                {
                    **base(row, "pr"),
                    "category": "stale_prs",
                    "proposed": None,
                    "actions": ["close", "comment"],
                    "reason": f"no activity for {age} days"
                    + (f" ({'; '.join(extra)})" if extra else ""),
                }
            )
        elif conflicts:
            items.append(
                {
                    **base(row, "pr"),
                    "category": "flags",
                    "proposed": None,
                    "actions": [],
                    "reason": "your open PR has merge conflicts",
                }
            )

    for row in data.get("issues", []):
        if row["key"] in ignore:
            continue
        age = days_since(row.get("updated_at"), now)
        if age is None or age <= issue_rules["stale_after_days"]:
            continue
        roles = [
            r
            for r, on in (
                ("assigned to you", row.get("assigned")),
                ("opened by you", row.get("authored")),
            )
            if on
        ]
        actions = ["close-completed", "close-not-planned", "comment"]
        if row.get("assigned"):
            actions.append("unassign")
        items.append(
            {
                **base(row, "issue"),
                "category": "stale_issues",
                "proposed": None,
                "actions": actions,
                "reason": f"{' and '.join(roles)}; no activity for {age} days",
            }
        )
    return items


def plan_branches(
    data: dict, rules: dict, ignore: set[str], now: datetime
) -> list[dict]:
    """Branches whose PR was merged, or closed and left alone."""
    items = []
    for b in data.get("branches", []):
        if b["key"] in ignore:
            continue
        name = b["branch"]
        if b.get("protected") or name == b.get("default_branch"):
            continue
        if any(fnmatch(name, pat) for pat in rules["protected_patterns"]):
            continue
        prs = b.get("prs") or []
        if any(p["state"] == "OPEN" for p in prs):
            continue
        merged = [p for p in prs if p.get("merged_at")]
        age = days_since(b.get("last_commit_at"), now)
        if merged:
            reason = "PR " + ", ".join(f"#{p['number']}" for p in merged) + " merged"
            if age is not None:
                reason += f"; last commit {age} days ago"
        elif age is not None and age > rules["abandoned_after_days"]:
            reason = (
                "PR "
                + ", ".join(f"#{p['number']}" for p in prs)
                + f" closed without merging; last commit {age} days ago"
            )
        else:
            continue
        items.append(
            {
                "key": b["key"],
                "repo": b["repo"],
                "branch": name,
                "label": f"{b['repo']}: {name}",
                "url": f"https://github.com/{ORG}/{b['repo']}/tree/{name}",
                "kind": "branch",
                "category": "branches",
                "proposed": "delete",
                "actions": ["delete"],
                "reason": reason,
                "merged": bool(merged),
            }
        )
    # Merged first: those are the safe ones.
    items.sort(key=lambda i: (not i["merged"], i["label"]))
    return items


def build_plan(
    notifs: dict,
    mine: dict,
    branches: dict,
    rules: dict,
    ignore: set[str],
    now: datetime,
) -> dict:
    """The whole plan, numbered in category order."""
    n_items, active = plan_notifications(notifs, rules["notifications"], ignore, now)
    items = (
        n_items
        + plan_mine(mine, rules, ignore, now)
        + plan_branches(branches, rules["branches"], ignore, now)
    )
    # Notifications sorted by repo and proposal so each repo is one contiguous range.
    items.sort(
        key=lambda i: (
            CATEGORIES.index(i["category"]),
            (i["repo"], i["proposed"] or "")
            if i["kind"] == "notification"
            else ("", ""),
        )
    )
    for n, item in enumerate(items, 1):
        item["n"] = n
    skipped = [
        *notifs.get("partial", []),
        *mine.get("partial", []),
        *branches.get("partial", []),
    ]
    return {
        "generated_at": now.isoformat(),
        "login": mine.get("login") or notifs.get("login"),
        "items": items,
        "active_notifications": active,
        "skipped": skipped,
    }


def main(argv: list[str] | None = None) -> int:
    """Read the work files and write plan.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--now", help="pretend it is this time (ISO), for tests")
    args = p.parse_args(argv)

    now = parse_ts(args.now) if args.now else datetime.now(UTC)
    inputs = {}
    for name in ("notifications", "mine", "branches"):
        data = read_json(f"{args.work}/{name}.json")
        if data is None:
            die(f"missing {args.work}/{name}.json; run fetch_{name}.py first")
        inputs[name] = data
    plan = build_plan(
        inputs["notifications"],
        inputs["mine"],
        inputs["branches"],
        load_rules(),
        load_ignore(),
        now,
    )
    write_json(f"{args.work}/plan.json", plan)
    counts = {
        c: sum(1 for i in plan["items"] if i["category"] == c) for c in CATEGORIES
    }
    print(
        "plan: " + ", ".join(f"{c} {k}" for c, k in counts.items() if k)
        if plan["items"]
        else "plan: nothing to clean"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
