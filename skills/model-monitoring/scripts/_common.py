"""Shared helpers for the model-monitoring scripts.

The two data sources this skill depends on live in *different* conda environments
and neither is on the default PATH, so every script needs a reliable way to find
them. Resolving the executable directly from the environment prefix is more
robust than `conda run`, which wraps stdout and can swallow exit codes.
"""

import csv
import io
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

CONDA_ROOTS = [
    Path.home() / "anaconda3",
    Path.home() / "miniconda3",
    Path.home() / "miniforge3",
    Path("/opt/conda"),
]


def find_in_conda_env(env_name, exe):
    """Return the path to `exe` inside conda env `env_name`, or None.

    Checks the standard conda roots, then falls back to CONDA_PREFIX's sibling
    envs directory so unusual installs still work.
    """
    candidates = []
    for root in CONDA_ROOTS:
        candidates.append(root / "envs" / env_name / "bin" / exe)
    prefix = os.environ.get("CONDA_PREFIX")
    if prefix:
        candidates.append(Path(prefix).parent / env_name / "bin" / exe)
        candidates.append(Path(prefix) / "envs" / env_name / "bin" / exe)
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


def resolve_tool(exe, env_name):
    """Locate `exe`, preferring conda env `env_name`, then PATH.

    Raises SystemExit with an actionable message when the tool is missing —
    a monitoring run that silently skips half its data is worse than one that
    stops and says what to install.
    """
    found = find_in_conda_env(env_name, exe)
    if found:
        return found
    on_path = shutil.which(exe)
    if on_path:
        return on_path
    sys.exit(
        f"ERROR: could not find `{exe}`. Expected it in the `{env_name}` conda "
        f"environment (e.g. ~/anaconda3/envs/{env_name}/bin/{exe}) or on PATH.\n"
        f"Checked conda roots: {', '.join(str(r) for r in CONDA_ROOTS)}"
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
