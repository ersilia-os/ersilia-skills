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

A ``choice`` item needs a side, named after the value the user says is right:
``--choose <n>:use-airtable`` keeps Airtable's value and writes it to GitHub;
``--choose <n>:use-github`` takes GitHub's value and writes it to Airtable.

Every select value is checked against `_common.CHOICES` before anything is built, so
``typecast`` is only ever needed, and only set, for a Publication Year that has no
option yet.

Usage:
    python build_writes.py --approve 3,4,9-11 [--choose 13:use-airtable] [--judgements j.json] \
        [--reject 12,13 --reason "not Ersilia work"] [--plan ...] [--out ...]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from _common import (
    BASE_ID,
    CHOICES,
    KNOWN_YEARS,
    SKILL_DIR,
    TABLES,
    WORK_DIR,
    die,
    read_json,
    write_json,
)

SIDES = ("use-airtable", "use-github")


def parse_numbers(spec: str | None) -> list[int]:
    """Parse '3,4,9-11' into [3, 4, 9, 10, 11], without repeats, in order."""
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
    return list(dict.fromkeys(out))


def parse_choices(spec: str) -> dict[int, str]:
    """Parse '13:github,17:airtable' into {13: 'github', 17: 'airtable'}."""
    out: dict[int, str] = {}
    for part in (spec or "").split(","):
        if not part.strip():
            continue
        n, sep, side = part.partition(":")
        if not sep or side.strip() not in SIDES:
            die(f"bad --choose entry {part!r}: use <n>:use-airtable or <n>:use-github")
        out[int(n)] = side.strip()
    return out


def to_field_ids(table: str, fields: dict, n: int) -> dict:
    """Map field keys to Airtable field IDs, refusing unknown keys and select values."""
    known = TABLES[table]["fields"]
    unknown = [k for k in fields if k not in known]
    if unknown:
        die(f"item {n}: {table} has no field {', '.join(unknown)}")
    for key, value in fields.items():
        allowed = CHOICES.get((table, key))
        values = value if isinstance(value, list) else [value]
        bad = [v for v in values if allowed is not None and v not in allowed]
        if bad:
            die(f"item {n}: {bad} is not a {table}.{key} option ({sorted(allowed)})")
        if (table, key) == ("publications", "year") and not str(value).isdigit():
            die(f"item {n}: year {value!r} is not a year")
    return {known[k][0]: v for k, v in fields.items()}


def needs_typecast(table: str, fields: dict) -> bool:
    """Only a Publication Year without an existing option needs Airtable typecast."""
    return table == "publications" and str(fields.get("year") or "") not in (
        KNOWN_YEARS | {""}
    )


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
    unknown = sorted(n for n in [*approve, *reject] if n not in by_n)
    if unknown:
        die(f"no such item(s): {unknown}")
    not_new = [n for n in reject if by_n[n]["action"] != "create"]
    if not_new:
        die(f"only new rows can be rejected; skip these instead: {not_new}")

    def save_rejections() -> None:
        if not reject:
            return
        ignore = read_json(args.ignore) or {"entries": []}
        known = {e["key"] for e in ignore["entries"]}
        for n in reject:
            item = by_n[n]
            if item["ignore_key"] and item["ignore_key"] not in known:
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

    # Rejections are saved only at the end, once every approval has been validated,
    # so a refused run leaves the ignore list untouched.

    choose = parse_choices(args.choose)
    groups: dict[tuple, list] = {}
    gh_calls: list[dict] = []
    for n in approve:
        item = by_n[n]
        action = item["action"]
        if action == "flag":
            die(f"item {n} is report-only (flag) and cannot be written")
        if action == "choice":
            if n not in choose:
                die(
                    f"item {n} is a choice: pass --choose {n}:use-airtable or {n}:use-github"
                )
            side = choose[n]
            opt = item["options"][side]
            if side == "use-airtable":
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
        record = {"fields": to_field_ids(item["table"], fields, n)}
        if action == "update":
            record["id"] = item["record_id"]
        typecast = needs_typecast(item["table"], fields)
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
    save_rejections()
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
