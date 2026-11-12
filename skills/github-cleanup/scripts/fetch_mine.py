"""Read your open issues and pull requests in ersilia-os (read-only).

Four searches, all limited to open items in the ersilia-os organisation:

- pull requests you opened
- pull requests where your review is requested
- issues assigned to you
- issues you opened

Your own open pull requests are then looked up one by one, for mergeability (conflicts)
and the reviewers still requested.

Writes ``<work>/mine.json``:

    {"login", "fetched_at", "my_prs": [...], "review_requests": [...],
     "issues": [... each with "assigned" and "authored" booleans], "partial": [...]}

Usage:
    python fetch_mine.py [--work /tmp/github_cleanup] [--limit 300]
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from _common import ORG, WORK_DIR, gh_login, run_gh_json, warn, write_json

PR_FIELDS = "number,title,repository,url,createdAt,updatedAt,isDraft,author,commentsCount,labels"
ISSUE_FIELDS = "number,title,repository,url,createdAt,updatedAt,author,assignees,commentsCount,labels"


def norm(raw: dict, kind: str) -> dict:
    """Flatten a gh search row."""
    repo = (raw.get("repository") or {}).get("name")
    return {
        "key": f"{kind}:{repo}#{raw['number']}",
        "repo": repo,
        "number": raw["number"],
        "title": raw.get("title"),
        "url": raw.get("url"),
        "created_at": raw.get("createdAt"),
        "updated_at": raw.get("updatedAt"),
        "draft": raw.get("isDraft", False),
        "author": (raw.get("author") or {}).get("login"),
        "assignees": [a.get("login") for a in raw.get("assignees") or []],
        "comments": raw.get("commentsCount", 0),
        "labels": [lb.get("name") for lb in raw.get("labels") or []],
    }


def search(
    kind: str, flags: list[str], fields: str, limit: int, partial: list[str]
) -> list[dict]:
    """Run one gh search; return normalised rows."""
    cmd = [
        "search",
        "prs" if kind == "pr" else "issues",
        "--owner",
        ORG,
        "--state",
        "open",
        *flags,
        "--json",
        fields,
        "--limit",
        str(limit),
    ]
    data, err = run_gh_json(cmd)
    if data is None:
        warn(f"search {' '.join(flags)}: {err}")
        partial.append(f"search {' '.join(flags)}: {err}")
        return []
    if len(data) >= limit:
        partial.append(f"search {' '.join(flags)}: hit the limit of {limit}")
    return [norm(r, kind) for r in data]


def main(argv: list[str] | None = None) -> int:
    """Fetch your open items."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--limit", type=int, default=300)
    args = p.parse_args(argv)
    partial: list[str] = []
    login = gh_login()

    my_prs = search("pr", ["--author", "@me"], PR_FIELDS, args.limit, partial)
    reviews = search(
        "pr", ["--review-requested", "@me"], PR_FIELDS, args.limit, partial
    )
    assigned = search("issue", ["--assignee", "@me"], ISSUE_FIELDS, args.limit, partial)
    authored = search("issue", ["--author", "@me"], ISSUE_FIELDS, args.limit, partial)

    issues: dict[str, dict] = {}
    for row in assigned:
        issues[row["key"]] = {
            **row,
            "assigned": True,
            "authored": row["author"] == login,
        }
    for row in authored:
        issues.setdefault(
            row["key"], {**row, "assigned": login in row["assignees"], "authored": True}
        )

    for pr in my_prs:
        data, err = run_gh_json(
            ["api", f"repos/{ORG}/{pr['repo']}/pulls/{pr['number']}"]
        )
        if data is None:
            warn(f"{pr['key']}: {err}")
            continue
        pr["mergeable_state"] = data.get("mergeable_state")
        pr["requested_reviewers"] = [
            r.get("login") for r in data.get("requested_reviewers") or []
        ]
        pr["head"] = (data.get("head") or {}).get("ref")

    # A review request on your own PR is not something to triage twice.
    mine_keys = {p_["key"] for p_ in my_prs}
    reviews = [r for r in reviews if r["key"] not in mine_keys]

    write_json(
        f"{args.work}/mine.json",
        {
            "login": login,
            "fetched_at": datetime.now(UTC).isoformat(),
            "my_prs": my_prs,
            "review_requests": reviews,
            "issues": list(issues.values()),
            "partial": partial,
        },
    )
    for line in partial:
        print(f"partial: {line}")
    print(
        f"mine: {len(my_prs)} open PR(s), {len(reviews)} review request(s), "
        f"{len(issues)} open issue(s) assigned to or opened by {login}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
