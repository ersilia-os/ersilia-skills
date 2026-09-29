"""Run the approved GitHub changes from writes.json, then check each one took effect.

Only ``tool: "gh"`` calls are run, and they exist in writes.json only because the user
approved those item numbers in this run (see build_writes.py). Two kinds:

- a repository description: ``gh repo edit ersilia-os/<name> --description ...``
- an org custom property (Status/Type): ``gh api -X PATCH .../properties/values``

After each command the value is read back from GitHub and compared. Exit 1 if any
command fails or any value does not match.

Usage:
    python apply_github.py [--writes /tmp/airtable_sync/writes.json]
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from _common import WORK_DIR, die, read_json, run_gh_json


def check(call: dict) -> str | None:
    """Return a problem description, or None if GitHub now holds the approved value."""
    repo, want = call["repo"], call.get("check") or {}
    if "description" in want:
        data, err = run_gh_json(["api", f"repos/ersilia-os/{repo}"])
        got = (data or {}).get("description")
        return None if got == want["description"] else f"description is {got!r}"
    if "property" in want:
        data, err = run_gh_json(["api", f"repos/ersilia-os/{repo}/properties/values"])
        values = {p.get("property_name"): p.get("value") for p in data or []}
        got = values.get(want["property"])
        got = got if isinstance(got, list) else [got] if got else []
        return (
            None if set(got) == set(want["value"]) else f"{want['property']} is {got}"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    """Run and verify every approved gh call."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--writes", default=f"{WORK_DIR}/writes.json")
    args = p.parse_args(argv)

    writes = read_json(args.writes) or die(f"missing {args.writes}")
    calls = [c for c in writes["calls"] if c["tool"] == "gh"]
    problems = 0
    for call in calls:
        n = ",".join(map(str, call["items"]))
        proc = subprocess.run(
            call["command"], input=call.get("stdin"), capture_output=True, text=True
        )
        if proc.returncode != 0:
            problems += 1
            print(f"[{n}] {call['repo']}: FAILED {proc.stderr.strip()[:300]}")
            continue
        issue = check(call)
        if issue:
            problems += 1
            print(f"[{n}] {call['repo']}: ran, but {issue}")
        else:
            print(f"[{n}] {call['repo']}: done and verified")
    print(f"github: {len(calls)} change(s), {problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
