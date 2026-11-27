"""Work out who needs a nudge about open issues, stale branches and forks.

Reads every open issue in non-archived `ersilia-os` repos (model repos included), finds
its owner, and flags it when someone should act:

- `needs_reply`: the last word (latest comment, or the issue itself if there are none) is
  from someone outside the team, and nobody has answered for `--reply-days` days.
- `stale_assigned`: assigned, and no activity for `--stale-days` days.
- `quiet_own`: unassigned, opened by a team member, no activity for `--quiet-days` days.
  The author should carry on with it or close it.
- `housekeeping`: an open housekeeping issue; always listed for its assignees.

Owner = assignees (members only) → else the author if a member → else the repo maintainer
(`_owners.repo_maintainer`). Then, using `fetch_housekeeping.py` output, each person also
gets their own stale branches and idle personal forks.

Read-only. Writes `--out` (default `/tmp/nudges.json`) with `issues` (all flagged issues)
and `people` (one bundle per GitHub login, plus `UNOWNED`). `send_nudges.py` renders and
sends the messages.

Exit codes: 0 on success, 1 if the issue search failed, 2 on bad input.

Usage:
    python fetch_nudges.py --housekeeping /tmp/housekeeping.json --out /tmp/nudges.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from _common import read_json, run_gh_json, warn, write_json
from _owners import is_person, repo_maintainer

ISSUES_QUERY = """
query($q: String!, $after: String) {
  search(query: $q, type: ISSUE, first: 100, after: $after) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Issue {
        number title url createdAt updatedAt
        repository { name }
        author { login }
        assignees(first: 10) { nodes { login } }
        comments(last: 1) { totalCount nodes { author { login } createdAt } }
      }
    }
  }
}
"""

HOUSEKEEPING_PREFIX = "Housekeeping:"


def fetch_issues(org: str) -> list[dict]:
    """All open issues in non-archived repos of `org`. Raises on failure."""
    issues: list[dict] = []
    after = None
    query = f"org:{org} is:issue is:open archived:false"
    while True:
        args = ["api", "graphql", "-f", f"query={ISSUES_QUERY}", "-f", f"q={query}"]
        if after:
            args += ["-f", f"after={after}"]
        data, err = run_gh_json(args)
        if data is None or (isinstance(data, dict) and data.get("errors")):
            raise RuntimeError(err or json.dumps(data.get("errors"))[:300])
        conn = data["data"]["search"]
        issues.extend(n for n in conn["nodes"] if n)
        if conn["issueCount"] >= 1000:
            warn("issue search hit GitHub's 1000-result cap; some issues are missing")
        if not conn["pageInfo"]["hasNextPage"]:
            return issues
        after = conn["pageInfo"]["endCursor"]


def days_since(ts: str, now: datetime) -> int:
    return max(0, (now - datetime.fromisoformat(ts.replace("Z", "+00:00"))).days)


def classify(
    raw: dict, members: set[str], org: str, args, now: datetime
) -> dict | None:
    """Owner and flags for one issue; None if nobody needs to act."""
    repo = raw["repository"]["name"]
    author = (raw.get("author") or {}).get("login")
    assignees = [
        a["login"] for a in raw["assignees"]["nodes"] if is_person(a["login"], members)
    ]
    last = (raw["comments"]["nodes"] or [None])[0]
    last_by = ((last or {}).get("author") or {}).get("login") if last else author
    last_at = last["createdAt"] if last else raw["createdAt"]
    quiet = days_since(last_at, now)
    idle = days_since(raw["updatedAt"], now)

    is_bot = (last_by or "").endswith("[bot]")
    flags = []
    if raw["title"].startswith(HOUSEKEEPING_PREFIX) and assignees:
        flags.append("housekeeping")
    elif not is_person(last_by, members) and not is_bot and quiet >= args.reply_days:
        flags.append("needs_reply")
    elif assignees and idle >= args.stale_days:
        flags.append("stale_assigned")
    elif not assignees and is_person(author, members) and idle >= args.quiet_days:
        flags.append("quiet_own")
    if not flags:
        return None

    if assignees:
        owners, how = assignees, "assignee"
    elif is_person(author, members):
        owners, how = [author], "author"
    else:
        owners, how = repo_maintainer(f"{org}/{repo}", members)
    return {
        "repo": repo,
        "number": raw["number"],
        "title": raw["title"],
        "url": raw["url"],
        "flag": flags[0],
        "owners": owners,
        "owner_rule": how,
        "author": author,
        "last_by": last_by,
        "days_quiet": quiet,
        "days_idle": idle,
        "age_days": days_since(raw["createdAt"], now),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--org", default="ersilia-os")
    p.add_argument(
        "--housekeeping",
        default="/tmp/housekeeping.json",
        help="fetch_housekeeping.py output (members, branches, forks)",
    )
    p.add_argument("--reply-days", type=int, default=7)
    p.add_argument("--stale-days", type=int, default=30)
    p.add_argument("--quiet-days", type=int, default=90)
    p.add_argument("--out", default="/tmp/nudges.json")
    args = p.parse_args(argv)

    hk = read_json(args.housekeeping)
    if not hk or "members" not in hk:
        print(
            f"ERROR: run fetch_housekeeping.py first ({args.housekeeping})",
            file=sys.stderr,
        )
        return 2
    members = set(hk["members"])
    now = datetime.now(timezone.utc)

    try:
        raw = fetch_issues(args.org)
    except RuntimeError as e:
        print(f"ERROR: issue search failed: {e}", file=sys.stderr)
        return 1

    issues = [c for r in raw if (c := classify(r, members, args.org, args, now))]
    issues.sort(key=lambda i: (i["flag"], -i["days_quiet"]))

    people: dict[str, dict] = {}

    def bundle(login: str) -> dict:
        return people.setdefault(login, {"issues": [], "branches": [], "forks": []})

    for issue in issues:
        for login in issue["owners"] or ["UNOWNED"]:
            bundle(login)["issues"].append(issue)
    for b in hk["stale_branches"]:
        if is_person(b.get("author_login"), members):
            bundle(b["author_login"])["branches"].append(b)
    for f in hk["personal_forks"]:
        bundle(f["owner"])["forks"].append(f)

    counts = {
        login: {k: len(v) for k, v in b.items()} for login, b in sorted(people.items())
    }
    write_json(
        args.out,
        {
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "org": args.org,
            "params": {
                "reply_days": args.reply_days,
                "stale_days": args.stale_days,
                "quiet_days": args.quiet_days,
            },
            "open_issues": len(raw),
            "issues": issues,
            "people": people,
        },
    )
    print(
        json.dumps(
            {"open_issues": len(raw), "flagged": len(issues), "people": counts},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
