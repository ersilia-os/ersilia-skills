"""Find branches you left behind in ersilia-os repositories (read-only).

A branch is attributed to you when it was the head of a pull request you opened from the
ersilia-os repository itself (not from a fork). For every repository where you opened a
pull request within ``branches.lookback_days``, this lists your pull requests, keeps the
head branches that still exist, and records what happened to their pull request.

Branches with no pull request are not considered: nothing reliably says who owns them.

Writes ``<work>/branches.json``:

    {"login", "fetched_at", "branches": [
       {"key", "repo", "branch", "default_branch", "protected", "last_commit_at",
        "prs": [{"number", "state", "merged_at", "closed_at", "url"}]}], "partial": [...]}

Usage:
    python fetch_branches.py [--work /tmp/github_cleanup]
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from _common import ORG, WORK_DIR, gh_login, load_rules, run_gh_json, warn, write_json


def main(argv: list[str] | None = None) -> int:
    """Fetch the branch candidates."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    args = p.parse_args(argv)
    rules = load_rules()["branches"]
    partial: list[str] = []
    login = gh_login()

    since = (datetime.now(UTC) - timedelta(days=rules["lookback_days"])).date()
    data, err = run_gh_json(
        [
            "search",
            "prs",
            "--owner",
            ORG,
            "--author",
            "@me",
            "--updated",
            f">={since}",
            "--json",
            "repository",
            "--limit",
            "1000",
        ]
    )
    if data is None:
        warn(f"search: {err}")
        data, partial = [], [f"search: {err}"]
    repos = sorted({(r.get("repository") or {}).get("name") for r in data} - {None})

    branches = []
    for repo in repos:
        meta, err = run_gh_json(["api", f"repos/{ORG}/{repo}"])
        if meta is None:
            partial.append(f"{repo}: {err}")
            continue
        if meta.get("archived"):
            continue
        prs, err = run_gh_json(
            [
                "pr",
                "list",
                "-R",
                f"{ORG}/{repo}",
                "--author",
                "@me",
                "--state",
                "all",
                "--limit",
                "200",
                "--json",
                "number,state,mergedAt,closedAt,url,headRefName,isCrossRepository",
            ]
        )
        if prs is None:
            partial.append(f"{repo}: {err}")
            continue
        by_branch: dict[str, list[dict]] = {}
        for pr in prs:
            if pr.get("isCrossRepository"):
                continue
            by_branch.setdefault(pr["headRefName"], []).append(
                {
                    "number": pr["number"],
                    "state": pr["state"],
                    "merged_at": pr.get("mergedAt"),
                    "closed_at": pr.get("closedAt"),
                    "url": pr.get("url"),
                }
            )
        for name, its_prs in by_branch.items():
            info, err = run_gh_json(
                ["api", f"repos/{ORG}/{repo}/branches/{quote(name, safe='/')}"]
            )
            if info is None:
                continue  # gone already (404), or unreadable: nothing to clean
            branches.append(
                {
                    "key": f"branch:{repo}:{name}",
                    "repo": repo,
                    "branch": name,
                    "default_branch": meta.get("default_branch"),
                    "protected": bool(info.get("protected")),
                    "last_commit_at": ((info.get("commit") or {}).get("commit") or {})
                    .get("committer", {})
                    .get("date"),
                    "prs": its_prs,
                }
            )

    write_json(
        f"{args.work}/branches.json",
        {
            "login": login,
            "fetched_at": datetime.now(UTC).isoformat(),
            "branches": branches,
            "partial": partial,
        },
    )
    for line in partial:
        print(f"partial: {line}")
    print(
        f"branches: {len(branches)} of your PR branches still exist across {len(repos)} repo(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
