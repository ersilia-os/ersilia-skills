"""Keep the skill's feedback log, the memory that lets it improve run after run.

Every piece of feedback the user gives during or after a run is logged here, with what
was changed in response. The log is read at pre-flight (``list``), so earlier lessons
are applied before a new plan is shown. Each entry says where the fix lives:

    marker       references/markers.json (a new, narrowed or demoted pattern)
    grading      references/grading.json (how findings become a tier)
    calibration  thresholds re-fitted (calibrate.py), e.g. with the user's labelled cases
    code         a script; must come with a selftest fixture that reproduces the case
    process      SKILL.md (how a run is conducted)

Lesson text never contains a document's content or anyone's name.

Usage:
    python record_feedback.py add --text "what the user said" --kind marker \
        --change "markers.json: model-phrasing += 'as an AI-assisted reviewer'" \
        [--fixture case-name[,other-case]]
    python record_feedback.py list
"""

from __future__ import annotations

import argparse
import sys

from lib.common import EXAMPLES, REFS, die, read_json, today, write_json

LOG = REFS / "feedback_log.json"
CASES = EXAMPLES / "cases"
LESSON_KINDS = ("marker", "grading", "calibration", "code", "process")


def main(argv: list[str] | None = None) -> int:
    """Add to or print the feedback log."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--text", required=True)
    a.add_argument("--kind", required=True, choices=LESSON_KINDS)
    a.add_argument("--change", required=True)
    a.add_argument("--fixture")
    sub.add_parser("list")
    args = p.parse_args(argv)

    log = read_json(LOG) or {"entries": []}
    if args.cmd == "add":
        if args.kind == "code" and not args.fixture:
            die("a code change needs --fixture: add a selftest case that reproduces it")
        missing = [
            f
            for f in (args.fixture or "").split(",")
            if f.strip() and not (CASES / f"{f.strip()}.json").exists()
        ]
        if missing:
            die(f"no such selftest case in examples/cases/: {', '.join(missing)}")
        entry = {
            "n": len(log["entries"]) + 1,
            "date": today(),
            "feedback": args.text,
            "kind": args.kind,
            "change": args.change,
        }
        if args.fixture:
            entry["fixture"] = args.fixture
        log["entries"].append(entry)
        write_json(LOG, log)
        print(f"logged lesson {entry['n']} ({args.kind})")
        return 0

    if not log["entries"]:
        print("No lessons yet.")
    for e in log["entries"]:
        print(f"{e['n']}. [{e['date']}, {e['kind']}] {e['feedback']} -> {e['change']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
