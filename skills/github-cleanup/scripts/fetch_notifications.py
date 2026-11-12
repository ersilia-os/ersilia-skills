"""Read your GitHub notifications inbox for ersilia-os repositories (read-only).

Lists every thread still in the inbox (read or unread), keeps those whose repository
belongs to ersilia-os, and looks up whether the issue or pull request each one is about
is already closed or merged. Lookups are de-duplicated by subject and capped by
``notifications.max_subject_lookups`` in rules.json.

Writes ``<work>/notifications.json``:

    {"login": ..., "fetched_at": ..., "threads": [
       {"id", "reason", "unread", "updated_at", "repo", "title", "type",
        "number", "key", "state", "merged", "html_url"}], "partial": [...]}

Usage:
    python fetch_notifications.py [--work /tmp/github_cleanup]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime

from _common import ORG, WORK_DIR, gh_login, load_rules, run_gh_json, warn, write_json

SUBJECT_RE = re.compile(r"/repos/([^/]+)/([^/]+)/(issues|pulls)/(\d+)$")


def subject_ref(url: str | None) -> tuple[str, str, int] | None:
    """(repo, kind, number) from a notification subject API url."""
    m = SUBJECT_RE.search(url or "")
    if not m:
        return None
    kind = "pr" if m.group(3) == "pulls" else "issue"
    return m.group(2), kind, int(m.group(4))


def main(argv: list[str] | None = None) -> int:
    """Fetch and annotate the inbox."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    args = p.parse_args(argv)
    rules = load_rules()["notifications"]
    partial: list[str] = []

    login = gh_login()
    raw, err = run_gh_json(["api", "--paginate", "notifications?all=true&per_page=50"])
    if raw is None:
        warn(f"notifications: {err}")
        raw, partial = [], [f"notifications: {err}"]
    if len(raw) > rules["max_threads"]:
        partial.append(
            f"notifications: only the newest {rules['max_threads']} of {len(raw)} threads read"
        )
        raw = raw[: rules["max_threads"]]

    threads = []
    for t in raw:
        repo = t.get("repository") or {}
        if (repo.get("owner") or {}).get("login") != ORG:
            continue
        subj = t.get("subject") or {}
        ref = subject_ref(subj.get("url"))
        threads.append(
            {
                "id": t["id"],
                "reason": t.get("reason"),
                "unread": t.get("unread"),
                "updated_at": t.get("updated_at"),
                "repo": repo.get("name"),
                "title": subj.get("title"),
                "type": subj.get("type"),
                "number": ref[2] if ref else None,
                "key": f"{ref[1]}:{ref[0]}#{ref[2]}" if ref else None,
                "state": None,
                "merged": None,
                "html_url": None,
            }
        )

    # One lookup per subject, newest first, up to the cap.
    states: dict[str, dict] = {}
    for th in threads:
        key = th["key"]
        if not key or key in states:
            continue
        if len(states) >= rules["max_subject_lookups"]:
            partial.append(
                f"notifications: state not looked up beyond {len(states)} subjects"
            )
            break
        endpoint = "pulls" if key.startswith("pr:") else "issues"
        data, err = run_gh_json(
            ["api", f"repos/{ORG}/{th['repo']}/{endpoint}/{th['number']}"]
        )
        if data is None:
            warn(f"{key}: {err}")
            states[key] = {}
            continue
        states[key] = {
            "state": data.get("state"),
            "merged": data.get("merged") if endpoint == "pulls" else None,
            "html_url": data.get("html_url"),
        }
    for th in threads:
        th.update({k: v for k, v in states.get(th["key"] or "", {}).items()})

    write_json(
        f"{args.work}/notifications.json",
        {
            "login": login,
            "fetched_at": datetime.now(UTC).isoformat(),
            "threads": threads,
            "partial": partial,
        },
    )
    for line in partial:
        print(f"partial: {line}")
    print(
        f"notifications: {len(threads)} ersilia-os thread(s) of {len(raw)} in the inbox"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
