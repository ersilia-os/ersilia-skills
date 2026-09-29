"""Turn the items the user approved into Airtable connector calls. Writes nothing itself.

Only item numbers passed in ``--approve`` are included, and only after the user said
yes to them in this run. There is no "approve everything" switch on purpose. Flags are
refused: they are report-only.

Judgement fields (Slug, Topic, Category...) come from ``--judgements``, a JSON object
``{"<n>": {"<field key>": value}}`` the model writes and the user has seen. A create
whose judgement fields are not all present is refused (a value of null means "leave it
empty", which is allowed).

``--reject`` adds rejected create candidates to `references/ignore-list.json` so they
are not proposed again.

Output ``writes.json``: ``{"calls": [...]}``. Airtable calls carry ``tool``
(`create_records_for_table`, `update_records_for_table` or `delete_records_for_table`),
``baseId``, ``tableId``, ``items`` and ``records`` (or ``recordIds`` for a delete), at
most 50 per call. GitHub calls carry ``tool: "gh"`` and are run by `apply_github.py`,
never by hand.

A ``choice`` item needs ``--choose <n>:airtable`` (the GitHub value is right, so update
Airtable) or ``<n>:github`` (the Airtable value is right, so update GitHub).

Usage:
    python build_writes.py --approve 3,4,9-11 [--choose 13:github] [--judgements j.json] \
        [--reject 12,13 --reason "not Ersilia work"] [--plan ...] [--out ...]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from _common import (
    BASE_ID,
    SKILL_DIR,
    TABLES,
    WORK_DIR,
    die,
    field_id,
    read_json,
    write_json,
)

# Publication Year is a single select whose options are added one year at a time, so
# writing a new year must be allowed to create the option. Every other select is
# written strictly: an unknown option is an error, not a silent new choice.
TYPECAST_FIELDS = {("publications", "year")}


def parse_numbers(spec: str | None) -> list[int]:
    """Parse '3,4,9-11' into [3, 4, 9, 10, 11]."""
    out: list[int] = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main(argv: list[str] | None = None) -> int:
    """Build writes.json for the approved items and record rejections."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--plan", default=f"{WORK_DIR}/plan.json")
    p.add_argument("--approve", default="")
    p.add_argument("--judgements")
    p.add_argument("--reject", default="")
    p.add_argument(
        "--choose", default="", help="for choice items: 13:airtable,17:github"
    )
    p.add_argument("--reason", default="rejected during review")
    p.add_argument(
        "--ignore", default=str(SKILL_DIR / "references" / "ignore-list.json")
    )
    p.add_argument("--out", default=f"{WORK_DIR}/writes.json")
    args = p.parse_args(argv)

    plan = read_json(args.plan)
    if plan is None:
        die(f"missing {args.plan}")
    by_n = {i["n"]: i for i in plan["items"]}
    judgements = (
        {int(k): v for k, v in (read_json(args.judgements) or {}).items()}
        if args.judgements
        else {}
    )
    approve, reject = parse_numbers(args.approve), parse_numbers(args.reject)
    if set(approve) & set(reject):
        die(f"items both approved and rejected: {sorted(set(approve) & set(reject))}")

    if reject:
        ignore = read_json(args.ignore) or {"entries": []}
        known = {e["key"] for e in ignore["entries"]}
        for n in reject:
            item = by_n.get(n) or die(f"no item {n}")
            if (
                item["action"] == "create"
                and item["ignore_key"]
                and item["ignore_key"] not in known
            ):
                ignore["entries"].append(
                    {
                        "key": item["ignore_key"],
                        "label": item["label"],
                        "reason": args.reason,
                        "date": date.today().isoformat(),
                    }
                )
                known.add(item["ignore_key"])
        write_json(args.ignore, ignore)
        print(f"ignore-list: {len(ignore['entries'])} entries")

    choose = dict(
        (int(a), b.strip())
        for a, b in (x.split(":") for x in args.choose.split(",") if x)
    )
    groups: dict[tuple, list] = {}
    gh_calls: list[dict] = []
    for n in approve:
        item = by_n.get(n) or die(f"no item {n}")
        action = item["action"]
        if action == "flag":
            die(f"item {n} is report-only (flag) and cannot be written")
        if action == "choice":
            side = choose.get(n) or die(
                f"item {n} is a choice: pass --choose {n}:airtable|github"
            )
            opt = item["options"].get(side) or die(f"item {n} has no option {side!r}")
            if side == "github":
                gh_calls.append(
                    {
                        "tool": "gh",
                        "items": [n],
                        "command": opt["command"],
                        "stdin": opt.get("stdin"),
                        "check": opt.get("check"),
                        "repo": item["label"],
                    }
                )
                continue
            item = {**item, "action": "update", "fields": opt["fields"]}
            action = "update"
        if action == "github":
            gh_calls.append(
                {
                    "tool": "gh",
                    "items": [n],
                    "command": item["command"],
                    "stdin": None,
                    "check": {"description": item["fields"]["github description"]},
                    "repo": item["label"],
                }
            )
            continue
        if action == "delete":
            groups.setdefault((item["table"], "delete", False), []).append(
                (n, item["record_id"])
            )
            continue
        fields = dict(item["fields"])
        if action == "create":
            given = judgements.get(n, {})
            missing = [k for k in item["judgement"] if k not in given]
            if missing:
                die(
                    f"item {n} still needs: {', '.join(missing)} (add them to --judgements)"
                )
            fields.update({k: v for k, v in given.items() if v not in (None, "", [])})
        else:
            fields.update(judgements.get(n, {}))
        record = {"fields": {field_id(item["table"], k): v for k, v in fields.items()}}
        if action == "update":
            record["id"] = item["record_id"]
        typecast = any((item["table"], k) in TYPECAST_FIELDS for k in fields)
        groups.setdefault((item["table"], action, typecast), []).append((n, record))

    tools = {
        "create": "create_records_for_table",
        "update": "update_records_for_table",
        "delete": "delete_records_for_table",
    }
    calls = []
    for (table, action, typecast), recs in groups.items():
        for k in range(0, len(recs), 50):
            chunk = recs[k : k + 50]
            call = {
                "tool": tools[action],
                "baseId": BASE_ID,
                "tableId": TABLES[table]["id"],
                "items": [n for n, _ in chunk],
            }
            if action == "delete":
                call["recordIds"] = [r for _, r in chunk]
            else:
                call["typecast"] = typecast
                call["records"] = [r for _, r in chunk]
            calls.append(call)
    calls += gh_calls
    write_json(args.out, {"calls": calls})
    total = sum(len(c["items"]) for c in calls)
    print(f"writes: {total} record(s) in {len(calls)} call(s) -> {args.out}")
    for c in calls:
        print(
            f"  {c['tool']} {c.get('tableId', c.get('repo'))}: items {','.join(map(str, c['items']))}"
            f"{' (typecast)' if c.get('typecast') else ''}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
