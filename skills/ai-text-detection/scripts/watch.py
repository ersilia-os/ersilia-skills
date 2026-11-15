"""Keep looking for new tools, markers, datasets and policies.

Detection is a moving target: assistants change their leftovers, new detectors appear,
policies change. ``references/watchlist.json`` lists what to watch and where. This script
only does the bookkeeping; Claude runs the searches (WebSearch, WebFetch), compares what it
finds with what the skill has, and proposes concrete changes through the Learn step.

    due                 exit 0 and list the topics when a scan is due (every
                        ``interval_days``), exit 1 when not. Run at every pre-flight.
    record --topic ID --found "..." [--change "..."]
                        log what a scan found (or "nothing new") and what was changed.
    done                mark today's scan complete.
    history             print past scans.

Usage:
    python watch.py due
    python watch.py record --topic leak-tokens --found "Gemini now adds [cite_end]" --change "markers.json gemini-cite"
    python watch.py done
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from _common import REFS, die, read_json, write_json

WATCH = REFS / "watchlist.json"


def main(argv: list[str] | None = None) -> int:
    """Dispatch."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("due")
    r = sub.add_parser("record")
    r.add_argument("--topic", required=True)
    r.add_argument("--found", required=True)
    r.add_argument("--change", default="")
    sub.add_parser("done")
    sub.add_parser("history")
    args = p.parse_args(argv)
    w = read_json(WATCH) or die("missing references/watchlist.json")
    today = date.today()

    if args.cmd == "due":
        last = w.get("last_scan")
        age = (today - date.fromisoformat(last)).days if last else None
        if age is not None and age < w["interval_days"]:
            print(
                f"watch: last scan {last} ({age} days ago); next in {w['interval_days'] - age} days"
            )
            return 1
        print(
            f"watch: scan due (last: {last or 'never'}). For each topic, search, compare with the skill, propose changes:"
        )
        for t in w["topics"]:
            print(f"\n[{t['id']}] {t['goal']}\n  searches: {' | '.join(t['queries'])}")
            if t["feeds"]:
                print(f"  check: {' | '.join(t['feeds'])}")
            print(f"  lands in: {t['lands_in']}")
        return 0
    if args.cmd == "record":
        if args.topic not in {t["id"] for t in w["topics"]}:
            die(f"unknown topic {args.topic}")
        w["history"].append(
            {
                "date": today.isoformat(),
                "topic": args.topic,
                "found": args.found,
                "change": args.change,
            }
        )
        write_json(WATCH, w)
        print(f"recorded for {args.topic}")
    elif args.cmd == "done":
        w["last_scan"] = today.isoformat()
        write_json(WATCH, w)
        print(f"scan marked done on {w['last_scan']}")
    else:
        for h in w["history"] or []:
            print(
                f"{h['date']} [{h['topic']}] {h['found']}"
                + (f" -> {h['change']}" if h["change"] else "")
            )
        if not w["history"]:
            print("no scans yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
