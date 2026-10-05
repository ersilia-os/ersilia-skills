"""Check that the org file actually reaches agents on this machine. Read-only.

``setup.sh`` adds ``@<ersilia-skills>/config/CLAUDE.md`` to ``~/.claude/CLAUDE.md``, so
every Claude Code session loads it. A review of a file nobody loads is wasted, so this
runs at pre-flight and writes ``delivery.json`` (findings in the usual format):

- ``DELIVERY-MISSING``: no import line for the org file in ``~/.claude/CLAUDE.md``.
- ``DELIVERY-BROKEN``: an import line points at a path that no longer exists.

Usage:
    python check_delivery.py [--work /tmp/org_context] [--home ~]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import WORK_DIR, write_json
from check_claude_md import Findings

ORG_FILE = "config/CLAUDE.md"


def main(argv: list[str] | None = None) -> int:
    """Inspect ~/.claude/CLAUDE.md for the org-file import."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--home", default=str(Path.home()))
    args = p.parse_args(argv)

    memory = Path(args.home) / ".claude" / "CLAUDE.md"
    lines = memory.read_text(encoding="utf-8").splitlines() if memory.exists() else []
    imports = [
        line[1:].strip()
        for line in lines
        if line.startswith("@") and line.rstrip().endswith("ersilia-skills/" + ORG_FILE)
    ]
    f = Findings()
    fix = "Run `bash setup.sh` in ersilia-skills; it adds the import line."
    if not imports:
        f.add(
            "org",
            "DELIVERY-MISSING",
            "fix",
            None,
            f"{memory} does not import the org file, so agents here never load it",
            fix,
        )
    for path in imports:
        if not Path(path).expanduser().exists():
            f.add(
                "org",
                "DELIVERY-BROKEN",
                "fix",
                None,
                f"{memory} imports {path}, which does not exist",
                fix,
            )
    write_json(Path(args.work) / "delivery.json", f.items)
    if f.items:
        for i in f.items:
            print(f"{i['check']}: {i['title']}")
    else:
        print(f"OK org file imported from {memory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
