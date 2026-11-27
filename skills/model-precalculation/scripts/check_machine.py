"""Check that this computer can run precalculations before anything is claimed.

Checks Docker, free disk space, the ``ersilia`` CLI and the ``isaura`` CLI.
A calculation that is marked Ongoing in Airtable and then fails at minute one
because Docker is off wastes everyone's time, so the skill runs this first.

Exit code 0 when every required check passes, 1 otherwise.

Usage:
    python check_machine.py
    python check_machine.py --path /data/precalc --min-free-gb 100
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

MONITORING_SCRIPTS = (
    Path(__file__).resolve().parents[2] / "model-monitoring" / "scripts"
)
sys.path.insert(0, str(MONITORING_SCRIPTS))


def check_docker() -> tuple[bool, str]:
    """Return whether the Docker daemon answers."""
    docker = shutil.which("docker")
    if not docker:
        return False, "docker not on PATH"
    try:
        proc = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, "docker info timed out"
    if proc.returncode != 0:
        return False, "daemon not running (start Docker Desktop)"
    return True, f"server {proc.stdout.strip()}"


def check_disk(path: str, min_free_gb: float) -> tuple[bool, str]:
    """Return whether ``path`` has at least ``min_free_gb`` free."""
    free_gb = shutil.disk_usage(path).free / 1e9
    return (
        free_gb >= min_free_gb,
        f"{free_gb:,.0f} GB free at {path} (need {min_free_gb:,.0f})",
    )


def check_tool(exe: str, explicit: str | None) -> tuple[bool, str]:
    """Locate ``exe`` with the model-monitoring resolver, without exiting on failure."""
    try:
        from _common import resolve_tool
    except ImportError:
        found = explicit or shutil.which(exe)
        return bool(found), found or "not found"
    try:
        return True, resolve_tool(exe, explicit=explicit)
    except SystemExit as exc:
        return False, str(exc).splitlines()[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--path", default=os.getcwd(), help="Where outputs will be written")
    ap.add_argument("--min-free-gb", type=float, default=50)
    ap.add_argument("--isaura-bin", default=os.environ.get("ISAURA_BIN"))
    ap.add_argument("--ersilia-bin", default=os.environ.get("ERSILIA_BIN"))
    args = ap.parse_args()

    checks = [
        ("docker", *check_docker()),
        ("disk", *check_disk(args.path, args.min_free_gb)),
        ("ersilia", *check_tool("ersilia", args.ersilia_bin)),
        ("isaura", *check_tool("isaura", args.isaura_bin)),
    ]
    for name, ok, detail in checks:
        print(f"[{'ok' if ok else 'FAIL'}] {name:<8} {detail}")
    sys.exit(0 if all(ok for _, ok, _ in checks) else 1)


if __name__ == "__main__":
    main()
