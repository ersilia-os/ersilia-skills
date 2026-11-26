"""Who owns a repo or a piece of work: shared by the housekeeping and nudge scripts.

The rules (see references/scope.md, *Who is assigned*): people who did the work and are
current org members first; else the repo's CODEOWNERS; else the member with most commits
on the default branch in the last year; else nobody. Bots are never owners.
"""

from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime, timedelta, timezone

from _common import run_gh_json

# At most this many owners per item, so ownership stays clear on big repos.
MAX_ASSIGNEES = 3
# Machine accounts that are org members but cannot act on anything.
BOT_LOGINS = {"ersilia-bot"}
CODEOWNERS_PATHS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")
MAINTAINER_WINDOW_DAYS = 365

_maintainer_cache: dict[str, tuple[list[str], str]] = {}


def is_person(login: str | None, members: set[str]) -> bool:
    """True for an org member who is a person, not a bot account."""
    return bool(
        login
        and login in members
        and login not in BOT_LOGINS
        and not login.endswith("[bot]")
        and not login.endswith("-bot")
    )


def codeowners(repo: str, members: set[str]) -> list[str]:
    """Org members named as individual owners in the repo's CODEOWNERS file."""
    for path in CODEOWNERS_PATHS:
        data, _ = run_gh_json(["api", f"repos/{repo}/contents/{path}"])
        if not isinstance(data, dict) or "content" not in data:
            continue
        text = base64.b64decode(data["content"]).decode("utf-8", "replace")
        owners: list[str] = []
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            for token in line.split()[1:]:
                login = token.lstrip("@")
                # Team owners (org/team) cannot be assigned; skip them.
                if (
                    "/" not in login
                    and is_person(login, members)
                    and login not in owners
                ):
                    owners.append(login)
        if owners:
            return owners
    return []


def top_committer(repo: str, members: set[str]) -> str | None:
    """The org member with most commits on the default branch in the last year."""
    since = datetime.now(timezone.utc) - timedelta(days=MAINTAINER_WINDOW_DAYS)
    data, _ = run_gh_json(
        [
            "api",
            "--paginate",
            f"repos/{repo}/commits?since={since:%Y-%m-%dT%H:%M:%SZ}&per_page=100",
        ]
    )
    if not isinstance(data, list):
        return None
    counts = Counter(
        (c.get("author") or {}).get("login")
        for c in data
        if is_person((c.get("author") or {}).get("login"), members)
    )
    return counts.most_common(1)[0][0] if counts else None


def choose_assignees(
    repo: str, branches: list[dict], members: set[str]
) -> tuple[list[str], str]:
    """Who should own a housekeeping issue, and why.

    Branch authors who are org members come first (most branches first, at most
    MAX_ASSIGNEES). Otherwise the repo maintainer: CODEOWNERS, then the member with most
    commits in the last year. Otherwise nobody, and the digest lists the issue as unowned.
    """
    counts = Counter(
        b["author_login"] for b in branches if is_person(b["author_login"], members)
    )
    if counts:
        ranked = sorted(counts, key=lambda login: (-counts[login], login.lower()))
        return ranked[:MAX_ASSIGNEES], "branch authors"
    return repo_maintainer(repo, members)


def repo_maintainer(repo: str, members: set[str]) -> tuple[list[str], str]:
    """CODEOWNERS, else the most active member this year, else nobody. Cached per repo."""
    if repo not in _maintainer_cache:
        owners = codeowners(repo, members)
        if owners:
            result = (owners[:MAX_ASSIGNEES], "CODEOWNERS")
        else:
            committer = top_committer(repo, members)
            result = (
                ([committer], "most active member this year")
                if committer
                else ([], "unowned")
            )
        _maintainer_cache[repo] = result
    return _maintainer_cache[repo]
