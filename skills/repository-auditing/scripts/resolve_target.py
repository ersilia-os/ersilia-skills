#!/usr/bin/env python3
"""Locate the repository to audit and describe its state.

Accepts a bare repo name, a GitHub URL, or a local path. Prefers a clone that already
exists on this machine (so the audit sees the tree the user actually works in); otherwise
makes a blobless partial clone into a working directory.

Refuses Ersilia Model Hub repos (`eosXXXX`) — they have a rigidly generated structure and
their own skills.

Exit codes
----------
0   target resolved; document written
2   bad usage, or the repo could not be found or cloned
3   the target is a model repo — use ersilia-model-test / model-incorporation-* instead

Usage
-----
    python resolve_target.py <name|url|path> [--out /tmp/repo_audit_target.json]
                             [--workdir DIR] [--no-clone] [--refresh]
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path

from _common import (
    die,
    git_head,
    is_model_repo,
    run,
    run_gh_json,
    warn,
    write_json,
)

ORG = "ersilia-os"

# Where clones of ersilia repos already live on a maintainer's machine. Checked in order.
LOCAL_ROOTS = [
    Path.home() / "Documents" / "GitHub",
    Path.home() / "GitHub",
    Path.home() / "git",
    Path.home() / "repos",
    Path.home() / "code",
]

URL_RE = re.compile(
    r"^(?:https?://github\.com/|git@github\.com:)(?P<owner>[^/]+)/(?P<name>[^/.]+)",
    re.IGNORECASE,
)


def parse_arg(raw: str) -> tuple[str, str, Path | None]:
    """Interpret the target argument.

    Returns
    -------
    tuple
        `(owner, name, explicit_path)`. `explicit_path` is set only when the argument
        pointed at a directory on disk.
    """
    raw = raw.strip().rstrip("/")
    if not raw:
        die("no target given")

    m = URL_RE.match(raw)
    if m:
        return m.group("owner"), m.group("name"), None

    candidate = Path(raw).expanduser()
    if candidate.is_dir():
        resolved = candidate.resolve()
        return ORG, resolved.name, resolved

    if "/" in raw:
        owner, _, name = raw.partition("/")
        return owner or ORG, name, None

    return ORG, raw, None


def find_local(name: str) -> Path | None:
    """Look for an existing clone of `name` under the known local roots."""
    for root in LOCAL_ROOTS:
        cand = root / name
        if (cand / ".git").exists():
            return cand.resolve()
    return None


def clone(owner: str, name: str, workdir: Path, refresh: bool) -> Path | None:
    """Make (or refresh) a blobless partial clone of `owner/name` under `workdir`.

    Blobless keeps the clone cheap while leaving full history available, so tag and
    tracked-path checks stay correct. Blobs for files the checkers actually open are
    fetched on demand.
    """
    dest = workdir / name
    if dest.exists():
        if refresh:
            shutil.rmtree(dest, ignore_errors=True)
        else:
            proc = run(
                ["git", "-C", str(dest), "fetch", "--tags", "--quiet"], timeout=300
            )
            if proc.returncode != 0:
                warn(f"could not fetch in existing clone: {proc.stderr.strip()[:200]}")
            return dest.resolve()

    workdir.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{owner}/{name}.git"
    proc = run(
        ["git", "clone", "--filter=blob:none", "--no-single-branch", url, str(dest)],
        timeout=600,
    )
    if proc.returncode != 0:
        warn(f"clone failed: {(proc.stderr or proc.stdout).strip()[:300]}")
        return None
    run(["git", "-C", str(dest), "fetch", "--tags", "--quiet"], timeout=300)
    return dest.resolve()


def describe_worktree(repo: Path) -> dict:
    """Report how far the working tree has drifted from its remote.

    The audit describes what is on disk, not what is on `main`. When those differ the
    report has to say so, or a finding could be blamed on a commit nobody pushed.
    """
    info: dict = {
        "head": git_head(repo),
        "dirty": False,
        "untracked": 0,
        "behind": None,
    }

    status = run(["git", "-C", str(repo), "status", "--porcelain"])
    if status.returncode == 0:
        lines = [ln for ln in status.stdout.splitlines() if ln.strip()]
        info["dirty"] = any(not ln.startswith("??") for ln in lines)
        info["untracked"] = sum(1 for ln in lines if ln.startswith("??"))

    branch = run(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"])
    info["branch"] = branch.stdout.strip() if branch.returncode == 0 else "unknown"

    # `@{u}` fails when the branch has no upstream — that is normal, not an error.
    counts = run(
        ["git", "-C", str(repo), "rev-list", "--left-right", "--count", "@{u}...HEAD"]
    )
    if counts.returncode == 0:
        bits = counts.stdout.split()
        if len(bits) == 2 and all(b.isdigit() for b in bits):
            info["behind"], info["ahead"] = int(bits[0]), int(bits[1])
    return info


def gh_maturity(owner: str, name: str) -> dict:
    """Signals for whether a repo is externally consumed, for the Tier 2 gate.

    Tier 2 asks for CONTRIBUTING, a code of conduct, issue templates and so on. Those are
    reasonable for a repo other people build on and pure noise for a 7-commit script, so
    the gate needs to know which this is. Counts degrade to 0 rather than failing the audit.
    """
    out = {"releases": 0, "contributors": 0}
    releases, err = run_gh_json(["api", f"repos/{owner}/{name}/releases?per_page=100"])
    if isinstance(releases, list):
        out["releases"] = len(releases)
    elif err:
        warn(f"could not count releases for {owner}/{name}: {err[:120]}")

    contributors, err = run_gh_json(
        ["api", f"repos/{owner}/{name}/contributors?per_page=100&anon=false"]
    )
    if isinstance(contributors, list):
        out["contributors"] = len(contributors)
    elif err:
        # A repo with no commits 204s here; that is not an error worth reporting.
        if "204" not in err:
            warn(f"could not count contributors for {owner}/{name}: {err[:120]}")
    return out


def gh_metadata(owner: str, name: str) -> dict:
    """Fetch the handful of GitHub facts the checks need. Degrades to {} on failure."""
    data, err = run_gh_json(["api", f"repos/{owner}/{name}"])
    if err or not isinstance(data, dict):
        warn(
            f"could not read GitHub metadata for {owner}/{name}: {err or 'unexpected shape'}"
        )
        return {}
    return {
        **gh_maturity(owner, name),
        "description": data.get("description") or "",
        "topics": data.get("topics") or [],
        "default_branch": data.get("default_branch") or "",
        "license": ((data.get("license") or {}) or {}).get("spdx_id") or "",
        "archived": bool(data.get("archived")),
        "is_template": bool(data.get("is_template")),
        "fork": bool(data.get("fork")),
        "language": data.get("language") or "",
        "pushed_at": data.get("pushed_at") or "",
        "open_issues": data.get("open_issues_count"),
        "stars": data.get("stargazers_count"),
    }


def main() -> int:
    """Resolve the target and write the target document."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", help="repo name, GitHub URL, or local path")
    ap.add_argument("--out", default="/tmp/repo_audit_target.json")
    ap.add_argument(
        "--workdir",
        default=os.environ.get("REPO_AUDIT_WORKDIR", "/tmp/repo-audit-clones"),
        help="where to place a clone when no local one exists",
    )
    ap.add_argument("--no-clone", action="store_true", help="fail rather than clone")
    ap.add_argument(
        "--refresh", action="store_true", help="re-clone even if one exists"
    )
    args = ap.parse_args()

    owner, name, explicit = parse_arg(args.target)

    if is_model_repo(name):
        print(
            f"{name} is an Ersilia Model Hub model repository.\n"
            "This skill does not audit model repos: their structure is generated from "
            "eos-template and is already covered by the `ersilia-model-test` and "
            "`model-incorporation-*` skills. Use those instead.",
            flush=True,
        )
        return 3

    source = "explicit-path"
    repo = explicit
    if repo is None:
        repo = find_local(name)
        source = "local-clone"
    if repo is None:
        if args.no_clone:
            die(f"no local clone of {name} found and --no-clone was given")
        repo = clone(owner, name, Path(args.workdir).expanduser(), args.refresh)
        source = "fresh-clone"
    if repo is None:
        die(f"could not resolve {owner}/{name}: not found locally and clone failed")

    if not (repo / ".git").exists():
        die(f"{repo} is not a git repository")

    # Re-derive the name from the resolved directory, then re-check: an explicit path
    # could still point at a model repo.
    name = repo.name
    if is_model_repo(name):
        print(
            f"{repo} is a model repository (eosXXXX); refusing. See ersilia-model-test."
        )
        return 3

    doc = {
        "name": name,
        "owner": owner,
        "path": str(repo),
        "source": source,
        "worktree": describe_worktree(repo),
        "github": gh_metadata(owner, name),
        "tools": {
            "git": bool(shutil.which("git")),
            "gh": bool(shutil.which("gh")),
        },
    }
    write_json(args.out, doc)

    wt = doc["worktree"]
    caveats = []
    if wt.get("dirty"):
        caveats.append("uncommitted changes")
    if wt.get("behind"):
        caveats.append(f"{wt['behind']} commits behind upstream")
    if doc["github"].get("archived"):
        caveats.append("archived on GitHub")
    suffix = f" [{'; '.join(caveats)}]" if caveats else ""
    print(f"{name}: {repo} ({source}, {wt['branch']}@{wt['head']}){suffix}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
