"""Shared helpers for the docs-drift scripts (gh calls, JSON files, repo names)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ORG = "ersilia-os"
MODEL_REPO_RE = re.compile(r"^eos[0-9a-z]{4}$", re.IGNORECASE)
BOT_LOGINS = {"ersilia-bot"}


def warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


def is_model_repo(name: str) -> bool:
    """True if `name` is an Ersilia Model Hub model repo (eosXXXX)."""
    return bool(MODEL_REPO_RE.match((name or "").strip()))


def is_person(login: str | None, members: set[str]) -> bool:
    """True for an org member who is a human (not a bot account)."""
    if not login or login in BOT_LOGINS:
        return False
    if login.endswith(("[bot]", "-bot")):
        return False
    return login in members


def run_gh_json(args: list[str]) -> tuple[object | None, str]:
    """Run `gh <args>` expecting JSON on stdout.

    Parameters
    ----------
    args : list of str
        Arguments after `gh`.

    Returns
    -------
    tuple
        (parsed JSON or None, error message or "").
    """
    if not shutil.which("gh"):
        return None, "gh CLI is not on PATH; install it and authenticate"
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout).strip()[:500]
    out = proc.stdout.strip()
    if not out:
        return [], ""
    try:
        return json.loads(out), ""
    except json.JSONDecodeError:
        # `gh --paginate` may print one JSON array per page back to back.
        dec, pos, parts = json.JSONDecoder(), 0, []
        while pos < len(out):
            val, pos = dec.raw_decode(out, pos)
            parts.append(val)
            while pos < len(out) and out[pos].isspace():
                pos += 1
        if all(isinstance(p, list) for p in parts):
            return [x for p in parts for x in p], ""
        return parts, ""


def read_json(path: str | Path) -> object | None:
    p = Path(path).expanduser()
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, data: object) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def org_members(org: str = ORG) -> set[str]:
    """Logins of the org's members (empty set if the call fails)."""
    data, err = run_gh_json(
        ["api", "--paginate", f"orgs/{org}/members?per_page=100", "--jq", "[.[].login]"]
    )
    if not isinstance(data, list):
        warn(f"could not list org members: {err}")
        return set()
    return set(data)
