"""Paths, constants, messages and JSON files shared by every step.

Four places hold state:

* ``WORK_DIR`` (/tmp/ai_text_detection): one analysis at a time, reset per run.
* ``CONTROLS_DIR`` (/tmp/ai_text_detection_controls): the public texts of known origin
  the web detectors are tested on, and their results. Kept between runs.
* ``REFS`` (references/ in the repo): markers, grading rules, calibration. Shared and
  versioned; improved through feedback and pull requests. Never holds anyone's text.
* ``LOCAL`` (~/.ai-text-detection): the user's private case ledger (numbers only),
  approvals and the Chrome profile. Never committed.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[2]
REFS = SKILL_DIR / "references"
ASSETS = SKILL_DIR / "assets"
EXAMPLES = SKILL_DIR / "examples"
WORK_DIR = Path("/tmp/ai_text_detection")
CONTROLS_DIR = Path("/tmp/ai_text_detection_controls")
LOCAL = Path.home() / ".ai-text-detection"
ENV_NAME = "ai-text-detection"
USER_AGENT = "ai-text-detection/1.0 (reference checker; https://github.com/ersilia-os/ersilia-skills)"

TIERS = ["conclusive", "strong", "moderate", "weak", "none"]
KINDS = ["article", "grant", "review", "response-letter", "email", "other"]
CONTEXTS = [
    "collaborator-draft",
    "reviewer-of-my-paper",
    "manuscript-i-review",
    "grant-i-review",
    "other",
]


def today() -> str:
    """Today's date as YYYY-MM-DD."""
    return date.today().isoformat()


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


def read_jsonl(path: str | Path) -> list[dict]:
    """Read a JSON-lines file; [] when missing."""
    p = Path(path).expanduser()
    if not p.exists():
        return []
    return [
        json.loads(line)
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    """Write rows as a JSON-lines file, creating parent folders."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


def append_jsonl(path: str | Path, row: dict) -> None:
    """Append one row to a JSON-lines file."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
