"""Combine the detectors' results across every split into calibrated evidence.

Writes ``<work>/evidence.json``: per sentence, passage and document, how much more likely
the text is under AI-written than under human text, with each detector weighted by its
results on known texts. The method is in lib/evidence.py.

Usage:
    python evidence.py [--work /tmp/ai_text_detection]
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from lib.common import WORK_DIR, write_json
from lib.evidence import combine


def main(argv: list[str] | None = None) -> int:
    """Compute, write and summarise evidence.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    work = Path(p.parse_args(argv).work)
    out = combine(work)
    if out is None:
        print("no plan (run segments.py); nothing to combine")
        return 0
    write_json(work / "evidence.json", out)
    print(
        f"tools counted: {', '.join(out['used']) or 'none (none tested well enough yet)'}"
    )
    for t, w in out["tools"].items():
        if not w["used"]:
            print(f"  not counted: {t}: {w['why']}")
    ev = out["document"]["evidence"]
    if ev is not None:
        print(
            f"document: {ev:+.2f} (about {math.exp(ev):.2f} times as likely under AI as under human)"
        )
    for pa in out["passages"]:
        if pa["evidence"] is not None:
            print(f"  {pa['chunk']}: {pa['evidence']:+.2f}")
    print(
        "share of sentences whose verdict depends on the split: "
        + ", ".join(
            f"{t} {v:.0%}" for t, v in out["stability"].items() if v is not None
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
