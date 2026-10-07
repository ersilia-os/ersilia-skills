"""Show the change plan as small, plain-language review steps.

The skill walks the user through the plan one step at a time and asks for approval of
each step before anything is written. This script decides the steps, so the order and
the grouping are the same on every run:

    per table (Repositories, Publications, Blogposts), in this order:
      urgent fixes          updates with priority 1 (renames, private repos shown as public)
      corrections           the other updates
      new rows              creates
      which side is right?  choices between Airtable and GitHub
      GitHub fixes          gh commands
      rows to delete        rows whose repository is gone
      for your info         flags (never written; a person decides)

At most ``--max`` items per step; a longer group is split into parts.

Usage:
    python render_plan.py --steps              # the numbered list of steps, with counts
    python render_plan.py --step 3             # one step, item by item
    python render_plan.py --gaps               # fields ersilia-stats needs that are empty
    [--plan /tmp/airtable_sync/plan.json] [--max 8]
"""

from __future__ import annotations

import argparse
import sys

from _common import WORK_DIR, die, read_json

TABLE_NAMES = {
    "repositories": "Repositories",
    "publications": "Publications",
    "blogposts": "Blogposts",
    "events": "Events",
    "grants": "Grants",
}
GROUPS = [
    ("urgent fixes", lambda i: i["action"] == "update" and i["priority"] == 1),
    ("corrections", lambda i: i["action"] == "update" and i["priority"] != 1),
    ("new rows", lambda i: i["action"] == "create"),
    ("which side is right?", lambda i: i["action"] == "choice"),
    ("GitHub fixes (gh commands)", lambda i: i["action"] == "github"),
    ("rows to delete", lambda i: i["action"] == "delete"),
    ("for your info (not written)", lambda i: i["action"] == "flag"),
]


def build_steps(items: list[dict], size: int) -> list[dict]:
    """Group plan items into ordered review steps of at most ``size`` items."""
    steps = []
    for table in TABLE_NAMES:
        for title, pred in GROUPS:
            group = [i for i in items if i["table"] == table and pred(i)]
            parts = [group[k : k + size] for k in range(0, len(group), size)]
            for p, chunk in enumerate(parts, 1):
                suffix = f" (part {p}/{len(parts)})" if len(parts) > 1 else ""
                steps.append(
                    {
                        "table": table,
                        "title": f"{TABLE_NAMES[table]}: {title}{suffix}",
                        "writable": chunk[0]["action"] != "flag",
                        "items": chunk,
                    }
                )
    for k, s in enumerate(steps, 1):
        s["k"] = k
    return steps


def _show(value) -> str:
    if value in (None, "", []):
        return "(empty)"
    if isinstance(value, list):
        return ", ".join(
            str(v.get("name", v)) if isinstance(v, dict) else str(v) for v in value
        )
    # Shown in full: the user approves exactly what is displayed, so nothing is cut.
    return str(value)


def describe(item: dict) -> list[str]:
    """Plain-language lines for one item."""
    n, label = item["n"], item["label"]
    if item["action"] == "update":
        lines = [f"[{n}] {label}: {item['reason']}"]
        for k, v in item["fields"].items():
            lines.append(f"      {k}: {_show(item['current'].get(k))}  ->  {_show(v)}")
        return lines
    if item["action"] == "create":
        lines = [f'[{n}] add "{label}": {item["reason"]}']
        for k, v in item["fields"].items():
            if k not in ("title",):
                lines.append(f"      {k}: {_show(v)}")
        if item["judgement"]:
            lines.append(f"      to decide: {', '.join(item['judgement'])}")
        return lines
    if item["action"] == "choice":
        lines = [f"[{n}] {label}: {item['reason']}"]
        for key, opt in item["options"].items():
            lines.append(f"      {key}: {opt['label']}")
        return lines
    if item["action"] == "github":
        return [
            f"[{n}] {label}: {item['reason']}",
            f"      runs: {_show(' '.join(item['command']))}",
        ]
    if item["action"] == "delete":
        cur = item["current"]
        return [
            f"[{n}] delete row {label} ({_show(cur.get('title'))}; status {_show(cur.get('status'))}): {item['reason']}"
        ]
    return [f"[{n}] {label}: {item['reason']}"]


def main(argv: list[str] | None = None) -> int:
    """Print the requested view of the plan."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--plan", default=f"{WORK_DIR}/plan.json")
    p.add_argument("--max", type=int, default=8)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--steps", action="store_true")
    g.add_argument("--step", type=int)
    g.add_argument("--gaps", action="store_true")
    args = p.parse_args(argv)

    plan = read_json(args.plan)
    if plan is None:
        die(f"missing {args.plan}; run plan_sync.py first")
    steps = build_steps(plan["items"], args.max)

    if args.steps:
        if not steps:
            print("Nothing to change: Airtable matches every source checked.")
        for s in steps:
            tag = "" if s["writable"] else "  (report only)"
            print(f"Step {s['k']}. {s['title']}: {len(s['items'])} item(s){tag}")
        if plan["gaps"]:
            print(
                f"Plus {len(plan['gaps'])} row(s) with empty fields the stats site reads (--gaps)."
            )
        for s in plan["skipped"]:
            print(f"Not checked: {s}")
        return 0

    if args.gaps:
        by_field: dict[tuple, list[str]] = {}
        for gap in plan["gaps"]:
            for field in gap["missing"]:
                by_field.setdefault((gap["table"], field), []).append(gap["label"])
        for (table, field), labels in sorted(by_field.items()):
            shown = ", ".join(labels[:6]) + (
                f" and {len(labels) - 6} more" if len(labels) > 6 else ""
            )
            print(
                f"- {TABLE_NAMES[table]}.{field} empty on {len(labels)} row(s): {shown}"
            )
        return 0

    step = next((s for s in steps if s["k"] == args.step), None)
    if step is None:
        die(f"no step {args.step}; there are {len(steps)}")
    print(f"Step {step['k']} of {len(steps)}. {step['title']}")
    for item in step["items"]:
        print("\n".join(describe(item)))
    print(f"items in this step: {','.join(str(i['n']) for i in step['items'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
