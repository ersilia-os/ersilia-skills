"""Shared helpers for the model-monitoring scripts.

The two CLIs this skill depends on (`isaura`, `ersilia_search`) are often in
conda environments that are not on PATH, and each machine installs them
differently, so every script needs a reliable way to find them without
hard-coded paths. Resolving the executable directly from the environment prefix
is more robust than `conda run`, which wraps stdout and can swallow exit codes.
"""

import csv
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Number of molecules in the full isaura reference collection. A model is only
# "complete" when it has a prediction for every one of these.
FULL_COUNT = 1_355_109

# ersilia_search caps --limit at 500 server-side; anything larger returns
# HTTP 422. The hub is far smaller than this today, but we assert on it so a
# growing hub surfaces as a loud error rather than a silently truncated report.
SEARCH_LIMIT = 500

# Common conda install locations. These are only a fallback for when the
# `conda` executable itself cannot be found; people install conda in different
# places, so nothing here is assumed to exist.
CONDA_ROOTS = [
    Path.home() / "anaconda3",
    Path.home() / "miniconda3",
    Path.home() / "miniforge3",
    Path.home() / "mambaforge",
    Path("/opt/conda"),
]


def _is_exe(path):
    return path.is_file() and os.access(path, os.X_OK)


def list_conda_envs():
    """Return the prefixes of every conda environment on this machine.

    Asks conda itself first (`conda env list --json`), because that is the only
    source that knows about custom install locations and env directories. The
    `conda` shell function is not visible to subprocesses, so the executable is
    taken from CONDA_EXE or PATH. Falls back to scanning the common roots.
    """
    prefixes = []
    conda_exe = os.environ.get("CONDA_EXE") or shutil.which("conda")
    if conda_exe:
        try:
            proc = subprocess.run(
                [conda_exe, "env", "list", "--json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode == 0:
                prefixes = [Path(p) for p in json.loads(proc.stdout).get("envs", [])]
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            prefixes = []
    for root in CONDA_ROOTS:
        if root.is_dir():
            prefixes.append(root)
            envs_dir = root / "envs"
            if envs_dir.is_dir():
                prefixes.extend(p for p in envs_dir.iterdir() if p.is_dir())
    seen, unique = set(), []
    for p in prefixes:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def resolve_tool(exe, env_name=None, explicit=None):
    """Locate the `exe` CLI without assuming where it is installed.

    Resolution order:

    1. `explicit`: a path given by the user (a `--*-bin` flag or env variable).
    2. The conda environment named `env_name`, if one with that name exists.
    3. PATH.
    4. Every conda environment on the machine. One match is used; several
       matches stop the run, because they may be different versions and the
       user should choose which one is authoritative.

    Raises SystemExit with an actionable message when the tool cannot be
    resolved unambiguously: a monitoring run that silently uses the wrong
    install, or skips half its data, is worse than one that stops and asks.
    """
    flag = f"--{exe.replace('_', '-')}-bin"
    if explicit:
        path = Path(explicit).expanduser()
        if _is_exe(path):
            return str(path)
        sys.exit(f"ERROR: `{explicit}` (given for `{exe}`) is not an executable file.")

    envs = list_conda_envs()
    if env_name:
        for prefix in envs:
            if prefix.name == env_name and _is_exe(prefix / "bin" / exe):
                return str(prefix / "bin" / exe)

    on_path = shutil.which(exe)
    if on_path:
        return on_path

    matches = [str(p / "bin" / exe) for p in envs if _is_exe(p / "bin" / exe)]
    if len(matches) == 1:
        print(f"[resolve] using {exe} from {matches[0]}", file=sys.stderr)
        return matches[0]
    if matches:
        sys.exit(
            f"ERROR: found `{exe}` in several conda environments:\n  "
            + "\n  ".join(matches)
            + f"\nAsk the user which one to use and pass it with {flag} <path>."
        )
    sys.exit(
        f"ERROR: could not find `{exe}` on PATH or in any conda environment "
        f"({len(envs)} checked).\nAsk the user where `{exe}` is installed and pass "
        f"it with {flag} <path>, or install it."
    )


def run(cmd, timeout=1800, check=True):
    """Run a command, returning CompletedProcess. Captures both streams."""
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        sys.exit(
            f"ERROR: command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"--- stdout ---\n{proc.stdout[-3000:]}\n"
            f"--- stderr ---\n{proc.stderr[-3000:]}"
        )
    return proc


def parse_hub_csv(text):
    """Parse ersilia_search CSV output into a list of dicts.

    Model descriptions contain embedded newlines, so the byte stream has many
    more physical lines than records. Anything that counts lines (wc -l, split
    on "\\n") over-counts badly — 247 models look like 500 lines. Always go
    through the csv module.
    """
    return [row for row in csv.DictReader(io.StringIO(text)) if row.get("Identifier")]
