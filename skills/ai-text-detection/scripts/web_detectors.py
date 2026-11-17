"""Record what a detector said when no script could read it, and summarise the results.

The results of every scan are rows in ``<work>/plan.results.jsonl`` (lib/detectors.py);
browser_detect.py and api_detectors.py write them. This command adds the rest:

    record --tool ID --chunk P2 --score 0.93 [--label "AI"] [--note "..."]
                        a result read by eye (sites without a parser)
    skip --tool ID --why "free limit reached"
                        a site that could not be used, so the report can say so
    summary             per tool, over the passages: passages and words flagged
                        (score >= 0.5), mean score; then how many tools flag the text

Usage:
    python web_detectors.py record --tool gptzero --chunk P2 --score 0.98 --label "AI"
    python web_detectors.py summary
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.common import WORK_DIR, die
from lib.detectors import Detections, Scan, consensus, tool


def print_summary(found: Detections) -> None:
    """Per tool, the consensus, and the sites that were not run."""
    summ = found.summary()
    for s in summ.values():
        print(
            f"{s['name']:<16} [{s['weight']}] flagged {s['passages_flagged']}/{s['passages']} passages "
            f"({s['share_words_flagged']:.0%} of words scanned; covered {s['coverage']:.0%} of the text); mean {s['mean_score']}"
        )
    c = consensus(summ)
    if c:
        print(
            f"consensus: {c['flagging']} of {c['ran']} tools flag the text ({c['validated_flagging']} of {c['validated_ran']} validated); mean scores {c['min_mean']}-{c['max_mean']}"
        )
    for s in found.skipped:
        print(f"{s['tool']}: not run ({s['why']})")


def main(argv: list[str] | None = None) -> int:
    """Dispatch."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--tool", required=True)
    r.add_argument("--chunk", required=True, help="unit id, e.g. P2")
    r.add_argument("--score", type=float, required=True, help="AI likelihood, 0-1")
    r.add_argument("--label", default="")
    r.add_argument("--note", default="read by eye")
    s = sub.add_parser("skip")
    s.add_argument("--tool", required=True)
    s.add_argument("--why", required=True)
    sub.add_parser("summary")
    args = p.parse_args(argv)
    work = Path(args.work)
    if args.cmd == "summary":
        print_summary(Detections.load(work))
        return 0
    scan = Scan.load(work)
    if not tool(args.tool):
        die(f"unknown tool {args.tool}; add it to references/web_detectors.json first")
    if args.cmd == "skip":
        scan.save({"tool": args.tool, "status": "skipped", "why": args.why})
        print(f"{args.tool}: skipped ({args.why})")
        return 0
    if not 0 <= args.score <= 1:
        die("score must be between 0 and 1 (convert percentages)")
    if args.chunk not in {u["chunk"] for u in scan.units}:
        die(f"no unit {args.chunk}")
    scan.save(
        {
            "tool": args.tool,
            "chunk": args.chunk,
            "status": "done",
            "score": args.score,
            "label": args.label,
            "note": args.note,
        }
    )
    print(f"{args.tool} {args.chunk}: {args.score:.2f} {args.label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
