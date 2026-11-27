"""Split the document for the detectors: its prose as sections (S), passages (P) and
overlapping windows (W), so each detector can be asked the same question several ways
(lib/splits.py has the method). The passages are the unit the report shows.

Writes ``<work>/plan.json`` ({"units": [...], "sentences": [...]}) and one text file per
unit in ``<work>/units/``; the sentence list (with character offsets) is what evidence.py
scores. Results recorded against an earlier, different split are set aside.

Usage:
    python segments.py [--work /tmp/ai_text_detection] [--window 350 --stride 175]
    python segments.py --for-tool zerogpt     # the unit ids within that tool's size limits
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.common import WORK_DIR, die, read_json, write_json
from lib.detectors import fits, results_path, tool, unattended
from lib.splits import build_plan
from lib.text import load_text


def write_plan(work: Path, plan: dict) -> None:
    """Write plan.json and the unit files. When the units differ from an earlier plan's,
    that plan's results no longer line up: they are kept aside, not pooled."""
    for u in plan["units"]:
        f = work / "units" / f"{u['chunk']}.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(u.pop("_text"), encoding="utf-8")
        u["file"] = str(f)
    old = read_json(work / "plan.json")
    results = results_path(work / "plan.json")
    if old and old["units"] != plan["units"] and results.exists():
        results.rename(results.with_name("plan.results.previous.jsonl"))
        print(
            "the split changed: earlier results set aside in plan.results.previous.jsonl"
        )
    write_json(work / "plan.json", plan)


def main(argv: list[str] | None = None) -> int:
    """Write the plan, or list the units that fit a tool."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument("--window", type=int, default=350)
    p.add_argument("--stride", type=int, default=175)
    p.add_argument("--for-tool")
    args = p.parse_args(argv)
    work = Path(args.work)
    if args.for_tool:
        plan = read_json(work / "plan.json") or die("run `segments.py` first")
        limits = tool(args.for_tool) or die(f"unknown tool {args.for_tool}")
        print(",".join(u["chunk"] for u in plan["units"] if fits(u, limits)))
        return 0
    plan = build_plan(load_text(work), args.window, args.stride)
    write_plan(work, plan)
    for scale in "SPW":
        us = [u for u in plan["units"] if u["scale"] == scale]
        print(
            f"{scale}: {len(us)} units, "
            + ", ".join(f"{u['chunk']}={u['n_words']}w" for u in us)
        )
    for u in plan["units"]:
        if u["scale"] == "P":
            print(f"  {u['chunk']}: {', '.join(u['sections'])} -> {u['file']}")
    print(f"sentences: {len(plan['sentences'])}")
    print("unattended tools: " + ", ".join(unattended()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
