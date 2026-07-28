"""Shared utilities for the github-digest fetch and reconcile scripts.

Keep this module dependency-free apart from the standard library — `fetch_github.py`
shells out to the `gh` CLI rather than importing anything heavy, so `_common.py` must
remain importable everywhere.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


def warn(msg: str) -> None:
    """Log a warning to stderr; scripts call this on partial failure."""
    print(f"WARNING: {msg}", file=sys.stderr, flush=True)


def _loads_gh(out: str) -> object:
    """Parse gh stdout, tolerating `--paginate` output that concatenates JSON values.

    Older `gh` (pre-2.28) does not merge paginated array responses — it emits one JSON
    array per page back-to-back (`[...][...]`), which is not valid JSON. We decode each
    top-level value in turn; if they are all arrays we concatenate them into one list
    (the merge newer gh does itself), otherwise we return the list of decoded values.
    A single well-formed value parses on the first pass and is returned as-is.
    """
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
        obj, end = decoder.raw_decode(out, idx)
        values.append(obj)
        idx = end
    if values and all(isinstance(v, list) for v in values):
        merged: list = []
        for v in values:
            merged.extend(v)
        return merged
    return values


def run_gh_json(args: list[str]) -> tuple[object | None, str]:
    """Run `gh <args>` expecting JSON on stdout. Returns (parsed_or_None, error_str)."""
    if not shutil.which("gh"):
        return None, "gh CLI is not on PATH; install it and authenticate"
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout).strip()[:500]
    out = proc.stdout.strip()
    if not out:
        return [], ""
    try:
        return _loads_gh(out), ""
    except (json.JSONDecodeError, ValueError) as e:
        return None, f"non-JSON from gh: {e}"


def parse_date(s: str) -> date:
    """Accept YYYY-MM-DD or YYYY/MM/DD and return a `date`."""
    s = s.strip().replace("/", "-")
    return datetime.strptime(s, "%Y-%m-%d").date()


def parse_iso_datetime(s: str | None) -> datetime | None:
    """Parse a GitHub ISO-8601 timestamp (e.g. '2026-06-10T14:22:01Z') to a naive UTC datetime.

    Returns None for empty/None/unparseable input.
    """
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    # Normalise to naive UTC so arithmetic with datetime.utcnow() is consistent.
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


# A model repo on the Ersilia Model Hub is named `eos` followed by 4 base-36-ish chars,
# e.g. `eos6tg8`, `eos43d6`, `eos8vud`. These live in a separate Airtable base and have
# their own incorporation flow, so the digest summarises them rather than detailing them.
MODEL_REPO_RE = re.compile(r"^eos[0-9a-z]{4}$", re.IGNORECASE)


def is_model_repo(name: str) -> bool:
    """True if `name` is an Ersilia Model Hub model repo (eosXXXX)."""
    return bool(MODEL_REPO_RE.match((name or "").strip()))


def is_trackable(repo: dict) -> bool:
    """True if `repo` belongs in the Airtable Repositories registry.

    Trackable = first-party, non-model repos. Forks are not first-party; model repos
    (`eosXXXX`) live in a separate Airtable base; org-infrastructure dot-repos
    (`.github`, `.github-private`) are out of scope. Archived repos stay trackable —
    they should still be catalogued. `repo` is a dict from `fetch_github.py`'s inventory
    (keys: `name`, `is_model`, `fork`).
    """
    name = (repo.get("name") or "").strip()
    return bool(
        name
        and not repo.get("is_model")
        and not repo.get("fork")
        and not name.startswith(".")
    )


def write_json(path: str, data: Any) -> None:
    """Write `data` as JSON to `path`, creating parent dirs as needed."""
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def read_json(path: str) -> Any:
    """Read JSON from `path`. Returns `None` if the file is missing or empty."""
    p = Path(path).expanduser().resolve()
    if not p.exists() or p.stat().st_size == 0:
        return None
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)
