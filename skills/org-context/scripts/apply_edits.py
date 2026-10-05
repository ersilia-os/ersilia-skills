"""Apply approved edits from plan.json to one CLAUDE.md file, and show the diff.

Only the IDs passed with ``--ids`` are applied, and they must all belong to one file.
There is no approve-all switch: list the IDs the user approved in this run. The file
must still match what was reviewed (same SHA-256), so an edit never lands on text the
user has not seen. When rules.json says so, the "Last updated" line is set to the
current month.

The script edits the file only. Branching, committing and opening the PR are separate
steps the user confirms (see SKILL.md, Step 7).

Usage:
    python apply_edits.py --ids O1,O3 --file /path/to/CLAUDE.md [--dry-run]
        [--work /tmp/org_context]
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from datetime import date
from pathlib import Path

from _common import (
    REFS,
    WORK_DIR,
    die,
    format_month_year,
    read_json,
    sha256,
    write_json,
)


def apply(text: str, items: list[dict], last_updated: dict, today: date) -> str:
    """Return ``text`` with every edit of ``items`` applied in order."""
    for i in items:
        for e in i["edits"]:
            count = text.count(e["find"])
            if count != 1:
                die(
                    f"{i['id']}: 'find' occurs {count} times after earlier edits: "
                    f"{e['find'][:60]!r}"
                )
            text = text.replace(e["find"], e["replace"], 1)
    if last_updated.get("bump_on_apply"):
        m = re.search(last_updated["pattern"], text)
        if m:
            stamp = format_month_year(today)
            text = text[: m.start(1)] + stamp + text[m.end(1) :]
    return text


def main(argv: list[str] | None = None) -> int:
    """Apply the approved IDs and print a unified diff."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--ids", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--today", default=date.today().isoformat())
    args = p.parse_args(argv)

    plan = read_json(Path(args.work) / "plan.json")
    if not plan:
        die("plan.json is missing: run render_report.py first")
    wanted = [x.strip() for x in args.ids.split(",") if x.strip()]
    by_id = {i["id"]: (t, i) for t in plan["targets"] for i in t["items"]}
    missing = [x for x in wanted if x not in by_id]
    if missing:
        die(f"unknown IDs: {', '.join(missing)}")
    owners = {by_id[x][0]["id"] for x in wanted}
    if len(owners) != 1:
        die(
            f"IDs span several files ({', '.join(sorted(owners))}); apply one file at a time"
        )
    target = by_id[wanted[0]][0]
    no_edit = [x for x in wanted if not by_id[x][1]["edits"]]
    if no_edit:
        die(
            f"no proposed edit for {', '.join(no_edit)}: add one to judgement.json, "
            "re-render, and show it to the user first"
        )

    path = Path(args.file).expanduser()
    before = path.read_text(encoding="utf-8")
    if sha256(before) != target["sha256"]:
        die(
            f"{path} differs from the reviewed version of {target['id']}; "
            "re-run the review on the current file"
        )
    rules = read_json(REFS / "rules.json")
    after = apply(
        before,
        [by_id[x][1] for x in wanted],
        rules["last_updated"],
        date.fromisoformat(args.today),
    )

    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{target['path']}",
        tofile=f"b/{target['path']}",
    )
    sys.stdout.writelines(diff)
    if args.dry_run:
        print(f"\n(dry run: {path} not written)")
        return 0
    path.write_text(after, encoding="utf-8")
    log = Path(args.work) / f"applied-{target['id']}.json"
    write_json(log, {"file": str(path), "ids": wanted, "date": args.today})
    print(f"\napplied {', '.join(wanted)} to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
