"""Write the multi-split plan: the document's prose as sections (S), passages (P) and
overlapping windows (W), so each detector can be asked the same question several ways
(lib/splits.py has the method).

Writes ``<work>/multi/plan.json`` ({"units": [...], "sentences": [...]}) and one text
file per unit; the sentence list (with character offsets) is what evidence.py scores.

Usage:
    python segments.py [--work /tmp/ai_text_detection] [--window 350 --stride 175]
    python segments.py --for-tool zerogpt     # the unit ids within that tool's size limits
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.common import WORK_DIR, read_json, write_json
from lib.detectors import registry
from lib.splits import build_plan, fits
from lib.text import load_text


def main(argv: list[str] | None = None) -> int:
    """Write the multi-split plan."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument("--window", type=int, default=350)
    p.add_argument("--stride", type=int, default=175)
    p.add_argument("--for-tool")
    args = p.parse_args(argv)
    work = Path(args.work)
    d = work / "multi"
    if args.for_tool:
        plan = read_json(d / "plan.json")
        tool = next(t for t in registry()["tools"] if t["id"] == args.for_tool)
        print(",".join(u["chunk"] for u in plan["units"] if fits(u, tool)))
        return 0
    plan = build_plan(load_text(work), args.window, args.stride)
    d.mkdir(parents=True, exist_ok=True)
    for u in plan["units"]:
        f = d / f"{u['chunk']}.txt"
        f.write_text(u.pop("_text"), encoding="utf-8")
        u["file"] = str(f)
    write_json(d / "plan.json", plan)
    for scale in "SPW":
        us = [u for u in plan["units"] if u["scale"] == scale]
        print(
            f"{scale}: {len(us)} units, "
            + ", ".join(f"{u['chunk']}={u['n_words']}w" for u in us)
        )
    print(f"sentences: {len(plan['sentences'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
