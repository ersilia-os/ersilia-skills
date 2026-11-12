"""Shared helpers for the github-cleanup scripts.

Standard library only. Every GitHub call goes through the ``gh`` CLI, so the user's own
authentication is used and nothing else needs installing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
REFS = SKILL_DIR / "references"
WORK_DIR = "/tmp/github_cleanup"
ORG = "ersilia-os"


def warn(message: str) -> None:
    """Print a warning to stderr; the run continues."""
    print(f"WARNING: {message}", file=sys.stderr, flush=True)


def die(message: str) -> None:
    """Print an error and exit 1."""
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


def read_json(path: str | Path) -> Any:
    """Read JSON from ``path``; None when the file is missing or empty."""
    p = Path(path).expanduser()
    if not p.exists() or p.stat().st_size == 0:
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    """Write ``data`` as indented JSON, creating parent folders."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _loads_gh(out: str) -> Any:
    """Parse gh stdout, merging the back-to-back arrays older ``--paginate`` emits."""
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    values, idx, n = [], 0, len(out)
    while idx < n:
        while idx < n and out[idx].isspace():
            idx += 1
        if idx >= n:
            break
        obj, idx = decoder.raw_decode(out, idx)
        values.append(obj)
    if values and all(isinstance(v, list) for v in values):
        return [x for v in values for x in v]
    return values


def run_gh_json(args: list[str]) -> tuple[Any, str]:
    """Run ``gh <args>`` expecting JSON. Returns (parsed or None, error text)."""
    if not shutil.which("gh"):
        return None, "gh CLI is not on PATH; install it and run `gh auth login`"
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip()
        if "rate limit" in err.lower():
            # Partial data would make a wrong plan: stop the whole run instead.
            die(
                f"GitHub API rate limit reached; {rate_limit_status()}. Re-run after the reset."
            )
        return None, err[:500]
    out = proc.stdout.strip()
    if not out:
        return [], ""
    try:
        return _loads_gh(out), ""
    except ValueError as e:
        return None, f"non-JSON from gh: {e}"


def rate_limit_status() -> str:
    """'N calls left, resets at HH:MM UTC' for the core API (this call is free)."""
    proc = subprocess.run(
        [
            "gh",
            "api",
            "rate_limit",
            "--jq",
            ".resources.core | [.remaining, .reset] | @tsv",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        remaining, reset = proc.stdout.split()
        at = datetime.fromtimestamp(int(reset), UTC).strftime("%H:%M UTC")
        return f"{remaining} calls left, resets at {at}"
    except ValueError:
        return "status unknown"


def gh_login() -> str:
    """The authenticated GitHub login, or exit."""
    data, err = run_gh_json(["api", "user"])
    if not data:
        die(f"cannot read the GitHub user: {err}")
    return data["login"]


def parse_ts(value: str | None) -> datetime | None:
    """Parse a GitHub ISO timestamp to an aware UTC datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def days_since(value: str | None, now: datetime) -> int | None:
    """Whole days between a GitHub timestamp and ``now``."""
    dt = parse_ts(value)
    return None if dt is None else (now - dt).days


def load_rules() -> dict:
    """references/rules.json."""
    return read_json(REFS / "rules.json") or die("missing references/rules.json")


def load_ignore() -> set[str]:
    """Keys the user chose to keep forever."""
    data = read_json(REFS / "ignore-list.json") or {"entries": []}
    return {e["key"] for e in data["entries"]}
