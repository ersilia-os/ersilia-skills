"""Run the approved commands in actions.json, then check each one took effect.

Every command is checked against a whitelist before it runs, whatever actions.json says:

    gh api -X DELETE notifications/threads/<id>[/subscription]
    gh api -X DELETE repos/ersilia-os/<repo>/git/refs/heads/<branch>
        (and only if, read live just before, the branch is not protected, not the
         default branch, and matches no protected pattern in rules.json)
    gh pr close|comment|edit <n> -R ersilia-os/<repo> [--comment|--body|--remove-reviewer ...]
    gh issue close|comment|edit <n> -R ersilia-os/<repo> [--reason|--comment|--body|--remove-assignee ...]

After each command the state is read back from GitHub. Applied items are recorded in
``<work>/applied.json`` so they are never run twice. Exit 1 on any failure.

Usage:
    python apply_actions.py [--work /tmp/github_cleanup]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from fnmatch import fnmatch
from urllib.parse import unquote

from _common import (
    ORG,
    WORK_DIR,
    die,
    load_rules,
    rate_limit_status,
    read_json,
    run_gh_json,
    write_json,
)

REPO = re.escape(ORG) + r"/[A-Za-z0-9._-]+"
FLAGS = {
    ("pr", "close"): {"--comment"},
    ("pr", "comment"): {"--body"},
    ("pr", "edit"): {"--remove-reviewer"},
    ("issue", "close"): {"--reason", "--comment"},
    ("issue", "comment"): {"--body"},
    ("issue", "edit"): {"--remove-assignee"},
}
API_DELETE = [
    re.compile(r"notifications/threads/\d+(/subscription)?"),
    re.compile(rf"repos/{REPO}/git/refs/heads/.+"),
]


def allowed(cmd: list[str]) -> str | None:
    """None if ``cmd`` is on the whitelist, else why not."""
    if len(cmd) < 3 or cmd[0] != "gh":
        return "not a gh command"
    if cmd[1] == "api":
        if (
            len(cmd) == 5
            and cmd[2:4] == ["-X", "DELETE"]
            and any(r.fullmatch(cmd[4]) for r in API_DELETE)
        ):
            return None
        return f"api call not whitelisted: {' '.join(cmd[1:])}"
    key = (cmd[1], cmd[2])
    if key not in FLAGS:
        return f"gh {cmd[1]} {cmd[2]} is not whitelisted"
    if (
        len(cmd) < 6
        or not cmd[3].isdigit()
        or cmd[4] != "-R"
        or not re.fullmatch(REPO, cmd[5])
    ):
        return "expected: <number> -R ersilia-os/<repo>"
    rest = cmd[6:]
    if len(rest) % 2:
        return "flags must come in flag/value pairs"
    for flag in rest[::2]:
        if flag not in FLAGS[key]:
            return f"flag {flag} not allowed for gh {cmd[1]} {cmd[2]}"
    if key == ("issue", "close"):
        reasons = [v for f, v in zip(rest[::2], rest[1::2]) if f == "--reason"]
        if any(r not in ("completed", "not planned") for r in reasons):
            return "issue close reason must be 'completed' or 'not planned'"
    return None


def branch_safe(path: str) -> str | None:
    """Re-read a branch live before deleting it. None if it is safe to delete."""
    m = re.fullmatch(rf"repos/({REPO})/git/refs/heads/(.+)", path)
    if not m:
        return None
    repo, branch = m.group(1), unquote(m.group(2))
    if any(fnmatch(branch, p) for p in load_rules()["branches"]["protected_patterns"]):
        return f"{branch} matches a protected pattern"
    meta, err = run_gh_json(["api", f"repos/{repo}"])
    if meta is None:
        return f"cannot read {repo}: {err}"
    if meta.get("default_branch") == branch:
        return f"{branch} is the default branch"
    info, err = run_gh_json(["api", f"repos/{repo}/branches/{m.group(2)}"])
    if info is None:
        return f"cannot read the branch: {err}"
    if info.get("protected"):
        return f"{branch} is protected"
    return None


def check(spec: dict | None) -> str | None:
    """None if GitHub now shows the expected state, else what it shows."""
    if not spec:
        return None
    data, err = run_gh_json(["api", spec["api"]])
    if spec["type"] == "gone":
        return None if data is None else "still there"
    if data is None:
        return f"cannot read back: {err}"
    if spec["type"] == "closed":
        return (
            None if data.get("state") == "closed" else f"state is {data.get('state')}"
        )
    if spec["type"] == "not_in":
        logins = [u.get("login") for u in data.get(spec["field"]) or []]
        return (
            None
            if spec["login"] not in logins
            else f"{spec['login']} still in {spec['field']}"
        )
    return f"unknown check {spec['type']}"


def main(argv: list[str] | None = None) -> int:
    """Run, verify and record every approved command."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    args = p.parse_args(argv)

    actions = read_json(f"{args.work}/actions.json") or die(
        "missing actions.json; run build_actions.py"
    )
    applied = read_json(f"{args.work}/applied.json") or {"items": [], "log": []}
    # Each call is a write plus up to three reads; never start what cannot finish.
    status = rate_limit_status()
    left = int(status.split()[0]) if status[0].isdigit() else 0
    if left < 4 * len(actions["calls"]) + 20:
        die(
            f"not enough GitHub API calls for {len(actions['calls'])} command(s): {status}"
        )
    failed_items: set[int] = set()
    problems = 0

    for call in actions["calls"]:
        n, cmd = call["item"], call["command"]
        tag = f"[{n}] {call['label']} ({call['action']})"
        if n in applied["items"]:
            print(f"{tag}: already applied, skipped")
            continue
        if n in failed_items:
            continue
        refusal = allowed(cmd) or (
            branch_safe(cmd[4]) if cmd[1] == "api" and "/git/refs/" in cmd[4] else None
        )
        if refusal:
            problems += 1
            failed_items.add(n)
            print(f"{tag}: REFUSED {refusal}")
            continue
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            problems += 1
            failed_items.add(n)
            print(f"{tag}: FAILED {(proc.stderr or proc.stdout).strip()[:300]}")
            continue
        issue = check(call.get("check"))
        if issue:
            problems += 1
            failed_items.add(n)
            print(f"{tag}: ran, but {issue}")
        else:
            print(f"{tag}: done" + (" and verified" if call.get("check") else ""))

    done = {c["item"] for c in actions["calls"]} - failed_items - set(applied["items"])
    applied["items"] = sorted(set(applied["items"]) | done)
    first = {c["item"]: c for c in reversed(actions["calls"])}  # one log line per item
    applied["log"] += [
        {"item": n, "key": c["key"], "label": c["label"], "action": c["action"]}
        for n, c in sorted(first.items())
        if n in done
    ]
    write_json(f"{args.work}/applied.json", applied)
    print(f"applied: {len(done)} item(s), {problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
