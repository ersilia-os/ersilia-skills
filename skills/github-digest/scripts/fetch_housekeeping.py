"""Find stale branches and forks across the `ersilia-os` org for the digest.

Collects, via the authenticated `gh` CLI (GraphQL, about 25 repos per call):

1. **Stale branches** in every non-archived repo, model repos included. The default branch,
   protected branches and branches with an open pull request are skipped. A branch is
   - `merged` / `closed` when the pull request it backed was merged or closed at least
     `--merged-grace-days` days ago (safe to delete), or
   - `idle` when it has no pull request and no commit for `--branch-idle-days` days.
2. **Org-owned forks**: repos under the org that are forks, with their parent, last push and
   how far they are ahead of / behind the parent.
3. **Personal forks of team members**: forks of org repos owned by an org member, with no
   push for `--fork-idle-days` days. Forks by people outside the team are ignored, since
   nobody at Ersilia can act on them.

Nothing is changed on GitHub. The output is one JSON document written to `--out` (default
`/tmp/housekeeping.json`), read by the skill when composing the Housekeeping chapter and by
`open_housekeeping_issues.py`.

Exit codes:
- 0 if the repo sweep finished (individual fork or compare calls may degrade; each failure
  is logged and `connector_status` becomes "partial").
- 1 if the repo sweep itself failed.

Usage:
    python fetch_housekeeping.py --out /tmp/housekeeping.json
    python fetch_housekeeping.py --branch-idle-days 90 --fork-idle-days 180
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from _common import is_model_repo, run_gh_json, warn, write_json

# Repos per GraphQL page. Each repo asks for up to 100 branches with one PR each, so
# larger pages risk GitHub's resource limits on repos with many branches.
REPO_PAGE = 25

# GitHub Apps and bots own branches too (e.g. dependabot); they are not people to nudge.
BOT_SUFFIX = "[bot]"

REPOS_QUERY = """
query($org: String!, $first: Int!, $after: String) {
  organization(login: $org) {
    repositories(first: $first, after: $after, isArchived: false,
                 orderBy: {field: NAME, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        url
        isFork
        pushedAt
        parent { nameWithOwner url defaultBranchRef { name } }
        defaultBranchRef { name }
        forks(first: 100, orderBy: {field: PUSHED_AT, direction: DESC}) {
          totalCount
          nodes { nameWithOwner url pushedAt owner { login } }
        }
        refs(refPrefix: "refs/heads/", first: 100) {
          totalCount
          nodes {
            name
            branchProtectionRule { id }
            target {
              ... on Commit {
                committedDate
                author { name user { login } }
              }
            }
            associatedPullRequests(first: 1, orderBy: {field: UPDATED_AT, direction: DESC}) {
              nodes { number state url mergedAt closedAt }
            }
          }
        }
      }
    }
  }
}
"""

FORKS_QUERY = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    forks(first: 100, after: $after, orderBy: {field: PUSHED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { nameWithOwner url pushedAt owner { login } }
    }
  }
}
"""


def graphql(query: str, **variables) -> tuple[dict | None, str]:
    """Run a GraphQL query through `gh api graphql`. Returns (data, error)."""
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if value is None:
            continue
        flag = "-F" if isinstance(value, int) else "-f"
        args += [flag, f"{key}={value}"]
    data, err = run_gh_json(args)
    if data is None:
        return None, err
    if isinstance(data, dict) and data.get("errors"):
        return None, json.dumps(data["errors"])[:500]
    return (data or {}).get("data"), ""


def fetch_members(org: str) -> set[str]:
    """Logins of org members. An empty set means the call failed (logged)."""
    data, err = run_gh_json(["api", "--paginate", f"orgs/{org}/members?per_page=100"])
    if data is None:
        warn(f"could not list members of {org!r}: {err}")
        return set()
    return {m.get("login") for m in data if m.get("login")}


def fetch_repo_pages(org: str) -> list[dict]:
    """All non-archived repos with branches and forks. Raises on failure."""
    repos: list[dict] = []
    after = None
    while True:
        data, err = graphql(REPOS_QUERY, org=org, first=REPO_PAGE, after=after)
        if data is None:
            raise RuntimeError(f"repo sweep failed after {len(repos)} repos: {err}")
        conn = data["organization"]["repositories"]
        repos.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            return repos
        after = conn["pageInfo"]["endCursor"]


def fetch_all_forks(org: str, name: str) -> tuple[list[dict], str]:
    """Every fork of one repo, for repos with more than one page of forks."""
    forks: list[dict] = []
    after = None
    while True:
        data, err = graphql(FORKS_QUERY, owner=org, name=name, after=after)
        if data is None:
            return forks, err
        conn = data["repository"]["forks"]
        forks.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            return forks, ""
        after = conn["pageInfo"]["endCursor"]


def days_since(ts: str | None, now: datetime) -> int | None:
    """Whole days between a GitHub timestamp and `now`, or None if unknown."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, (now - dt).days)


def classify_branch(
    node: dict, idle_days: int, grace_days: int, now: datetime
) -> dict | None:
    """Return a stale-branch record, or None if the branch should be left alone."""
    if node.get("branchProtectionRule"):
        return None
    commit = node.get("target") or {}
    age = days_since(commit.get("committedDate"), now)
    prs = (node.get("associatedPullRequests") or {}).get("nodes") or []
    pr = prs[0] if prs else None
    author = commit.get("author") or {}
    record = {
        "branch": node["name"],
        "last_commit": (commit.get("committedDate") or "")[:10] or None,
        "days_since_commit": age,
        "author_login": (author.get("user") or {}).get("login"),
        "author_name": author.get("name"),
        "pr": None,
    }
    if pr:
        if pr["state"] == "OPEN":
            return None
        ended = days_since(pr.get("mergedAt") or pr.get("closedAt"), now)
        if ended is not None and ended < grace_days:
            return None
        record["pr"] = {"number": pr["number"], "state": pr["state"], "url": pr["url"]}
        record["reason"] = "merged" if pr["state"] == "MERGED" else "closed"
        return record
    if age is not None and age >= idle_days:
        record["reason"] = "idle"
        return record
    return None


def compare_fork(org: str, repo: dict) -> dict:
    """Ahead/behind counts of an org-owned fork against its parent's default branch."""
    parent = repo["parent"]["nameWithOwner"]
    base = (repo["parent"].get("defaultBranchRef") or {}).get("name")
    head = (repo.get("defaultBranchRef") or {}).get("name")
    if not (base and head):
        return {"error": "missing default branch"}
    data, err = run_gh_json(
        ["api", f"repos/{parent}/compare/{base}...{org}:{repo['name']}:{head}"]
    )
    if data is None:
        return {"error": err}
    return {"ahead_by": data.get("ahead_by"), "behind_by": data.get("behind_by")}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--org", default="ersilia-os")
    p.add_argument(
        "--branch-idle-days",
        type=int,
        default=90,
        help="branch with no PR and no commit in this many days is flagged idle",
    )
    p.add_argument(
        "--merged-grace-days",
        type=int,
        default=14,
        help="wait this many days after a PR is merged or closed before flagging",
    )
    p.add_argument(
        "--fork-idle-days",
        type=int,
        default=180,
        help="team member's fork with no push in this many days is flagged",
    )
    p.add_argument("--out", default="/tmp/housekeeping.json")
    args = p.parse_args(argv)

    now = datetime.now(timezone.utc)
    status = "ok"
    errors: list[str] = []

    members = fetch_members(args.org)
    if not members:
        status = "partial"
        errors.append("org members unavailable: personal forks not checked")

    try:
        repos = fetch_repo_pages(args.org)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    stale_branches: list[dict] = []
    org_forks: list[dict] = []
    personal_forks: list[dict] = []
    truncated_branches: list[str] = []

    for repo in repos:
        name = repo["name"]
        default = (repo.get("defaultBranchRef") or {}).get("name")
        refs = repo.get("refs") or {"nodes": [], "totalCount": 0}
        if refs["totalCount"] > len(refs["nodes"]):
            truncated_branches.append(name)
        for node in refs["nodes"]:
            if node["name"] == default:
                continue
            rec = classify_branch(
                node, args.branch_idle_days, args.merged_grace_days, now
            )
            if rec:
                rec.update(
                    {
                        "repo": name,
                        "is_model": is_model_repo(name),
                        "url": f"{repo['url']}/tree/{node['name']}",
                    }
                )
                stale_branches.append(rec)

        if repo.get("isFork") and repo.get("parent"):
            org_forks.append(
                {
                    "repo": name,
                    "url": repo["url"],
                    "parent": repo["parent"]["nameWithOwner"],
                    "parent_url": repo["parent"]["url"],
                    "pushed_at": (repo.get("pushedAt") or "")[:10] or None,
                    "days_since_push": days_since(repo.get("pushedAt"), now),
                    **compare_fork(args.org, repo),
                }
            )

        if not members:
            continue
        forks = repo["forks"]
        fork_nodes = forks["nodes"]
        if forks["totalCount"] > len(fork_nodes):
            fork_nodes, err = fetch_all_forks(args.org, name)
            if err:
                status = "partial"
                errors.append(f"{name}: forks incomplete ({err[:120]})")
        for f in fork_nodes:
            owner = (f.get("owner") or {}).get("login") or ""
            if owner not in members or owner.endswith(BOT_SUFFIX):
                continue
            age = days_since(f.get("pushedAt"), now)
            if age is not None and age >= args.fork_idle_days:
                personal_forks.append(
                    {
                        "owner": owner,
                        "fork": f["nameWithOwner"],
                        "url": f["url"],
                        "parent": name,
                        "is_model": is_model_repo(name),
                        "pushed_at": (f.get("pushedAt") or "")[:10] or None,
                        "days_since_push": age,
                    }
                )

    if truncated_branches:
        status = "partial"
        errors.append(
            f"{len(truncated_branches)} repos have more than 100 branches; "
            f"only the first 100 were checked: {', '.join(truncated_branches)}"
        )
    for f in org_forks:
        if f.get("error"):
            status = "partial"
            errors.append(
                f"{f['repo']}: compare with parent failed ({f['error'][:120]})"
            )

    stale_branches.sort(
        key=lambda b: (b["is_model"], b["repo"], -(b["days_since_commit"] or 0))
    )
    personal_forks.sort(key=lambda f: (f["owner"], -f["days_since_push"]))

    nonmodel = [b for b in stale_branches if not b["is_model"]]
    model = [b for b in stale_branches if b["is_model"]]
    out = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "org": args.org,
        "params": {
            "branch_idle_days": args.branch_idle_days,
            "merged_grace_days": args.merged_grace_days,
            "fork_idle_days": args.fork_idle_days,
        },
        "connector_status": status,
        "errors": errors,
        "counts": {
            "repos_checked": len(repos),
            "members": len(members),
            "stale_branches": len(stale_branches),
            "stale_branches_nonmodel": len(nonmodel),
            "stale_branches_model": len(model),
            "repos_with_stale_branches": len({b["repo"] for b in stale_branches}),
            "by_reason": {
                r: sum(1 for b in stale_branches if b["reason"] == r)
                for r in ("merged", "closed", "idle")
            },
            "org_forks": len(org_forks),
            "personal_forks": len(personal_forks),
        },
        "stale_branches": stale_branches,
        "org_forks": org_forks,
        "personal_forks": personal_forks,
    }
    write_json(args.out, out)
    print(f"connector_status={status}", file=sys.stderr)
    print(json.dumps(out["counts"], indent=2))
    for e in errors:
        warn(e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
