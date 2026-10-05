"""Merge script findings with the judgement layer, number them, and write the report.

Inputs in the work directory: ``targets.json``, ``checks.json``, ``facts.json``,
``connectors.json`` (Drive and Airtable; ``--skip-connectors`` renders without it and
says so in the report) and the optional ``judgement.json`` written by Claude:

    {"dismiss":  {"org:VAGUE:1": "why this is not a problem"},
     "edits":    {"org:CANON-black:1": {"find": "exact old text", "replace": "new text"}},
     "findings": [{"target": "pkg", "severity": "trim", "line": 41,
                   "title": "...", "detail": "...",
                   "edit": [{"find": "...", "replace": "..."}]}]}

An edit is one ``{find, replace}`` or a list of them; ``find`` must occur exactly once in
the file, or this script stops and names the edit to fix. Writes ``plan.json`` (every
finding with its ID, e.g. ``O3``, and its edits) and ``REPORT.md``, and prints the
report path.

Usage:
    python render_report.py [--work /tmp/org_context] [--today YYYY-MM-DD]
        [--skip-connectors]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from _common import (
    MARKERS,
    REFS,
    SEVERITIES,
    WORK_DIR,
    die,
    load_work,
    read_json,
    write_json,
)


def as_list(edit) -> list[dict]:
    """Normalise one edit or a list of edits to a list."""
    if not edit:
        return []
    return edit if isinstance(edit, list) else [edit]


def validate(item: dict, text: str) -> list[str]:
    """Return problems with an item's edits against the file text."""
    problems = []
    for e in item["edits"]:
        if not isinstance(e, dict) or "find" not in e or "replace" not in e:
            problems.append(f"{item['key']}: edit needs 'find' and 'replace'")
            continue
        count = text.count(e["find"]) if e["find"] else 0
        if count != 1:
            problems.append(
                f"{item['key']}: 'find' occurs {count} times (must be exactly once): "
                f"{e['find'][:60]!r}"
            )
    return problems


def diff_block(edits: list[dict]) -> list[str]:
    """Render edits as a fenced diff."""
    out = ["```diff"]
    for e in edits:
        out += [f"- {line}" for line in e["find"].splitlines()]
        out += [f"+ {line}" for line in e["replace"].splitlines()]
    out.append("```")
    return out


def main(argv: list[str] | None = None) -> int:
    """Build plan.json and REPORT.md."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--today", default=date.today().isoformat())
    p.add_argument("--skip-connectors", action="store_true")
    args = p.parse_args(argv)
    work = Path(args.work)
    targets, texts = load_work(work)
    rules = read_json(REFS / "rules.json")
    judgement = read_json(work / "judgement.json") or {}
    dismiss = judgement.get("dismiss", {})
    edits = judgement.get("edits", {})

    connectors = read_json(work / "connectors.json")
    if connectors is None and not args.skip_connectors:
        die(
            "connectors.json is missing: verify Drive and Airtable (Step 3) or pass "
            "--skip-connectors, which the report then states"
        )
    raw = (
        (read_json(work / "checks.json") or [])
        + (read_json(work / "facts.json") or [])
        + (connectors or [])
    )
    known = {i["key"] for i in raw}
    unknown = [k for k in list(dismiss) + list(edits) if k not in known]
    if unknown:
        die(f"judgement.json names keys no script produced: {', '.join(unknown)}")
    if not (work / "facts.json").exists():
        die("facts.json is missing: run verify_facts.py before rendering")

    items = []
    for i in raw:
        if i["key"] in dismiss:
            continue
        items.append({**i, "edits": as_list(edits.get(i["key"])), "source": "script"})
    for n, j in enumerate(judgement.get("findings", []), 1):
        if j.get("severity") not in SEVERITIES or j.get("target") not in texts:
            die(f"judgement finding {n} needs a valid 'target' and 'severity'")
        items.append(
            {
                "key": f"{j['target']}:JUDGEMENT:{n}",
                "target": j["target"],
                "check": "JUDGEMENT",
                "severity": j["severity"],
                "line": j.get("line"),
                "title": j["title"],
                "detail": j.get("detail", ""),
                "edits": as_list(j.get("edit")),
                "source": "judgement",
            }
        )

    problems = [m for i in items for m in validate(i, texts[i["target"]])]
    if problems:
        die("fix these edits in judgement.json:\n  " + "\n  ".join(problems))

    order = {s: k for k, s in enumerate(SEVERITIES)}
    plan_targets = []
    for t in targets:
        mine = sorted(
            (i for i in items if i["target"] == t["id"]),
            key=lambda i: (order[i["severity"]], i["line"] or 0),
        )
        for n, i in enumerate(mine, 1):
            i["id"] = f"{t['prefix']}{n}"
        plan_targets.append({**t, "items": mine})
    write_json(
        work / "plan.json",
        {"date": args.today, "targets": plan_targets, "dismissed": dismiss},
    )

    count = {s: sum(i["severity"] == s for i in items) for s in SEVERITIES}
    n_edits = sum(bool(i["edits"]) for i in items)
    md = [
        f"# CLAUDE.md review · {args.today}",
        "",
        f"{len(targets)} files · {MARKERS['fix']} {count['fix']} fix · "
        f"{MARKERS['trim']} {count['trim']} trim · {MARKERS['consider']} "
        f"{count['consider']} consider · {n_edits} with a proposed edit (✎)"
        + (f" · {len(dismiss)} dismissed" if dismiss else ""),
        "",
        "Nothing changes until you approve IDs, e.g. *apply O1, O3* or *apply all ✎ in P*.",
    ]
    if connectors is None:
        md += [
            "",
            "**Google Drive and Airtable references were not checked in this run.**",
        ]
    for t in plan_targets:
        budget = rules["budgets"][t["role"]]["max_lines"]
        md += [
            "",
            f"## {t['label']} · `{t['repo']}/{t['path']}`",
            "",
            f"{t['lines']} lines (budget {budget}) · {t.get('status', '')}",
            "",
        ]
        if not t["items"]:
            md.append("No findings.")
            continue
        md += ["| ID | | Line | Finding |", "|---|---|---|---|"]
        for i in t["items"]:
            mark = " ✎" if i["edits"] else ""
            md.append(
                f"| {i['id']} | {MARKERS[i['severity']]} | {i['line'] or ''} | "
                f"{i['title'].replace('|', '/')}{mark} |"
            )
        # A note shared by several findings without edits is printed once, for all.
        shared: dict[str, list[str]] = {}
        for i in t["items"]:
            if i["detail"] and not i["edits"]:
                shared.setdefault(i["detail"], []).append(i["id"])
        done = set()
        for i in t["items"]:
            if i["edits"]:
                md += ["", f"**{i['id']}** {i['detail']}".rstrip()]
                md += diff_block(i["edits"])
            elif i["detail"] and i["detail"] not in done:
                done.add(i["detail"])
                md += ["", f"**{', '.join(shared[i['detail']])}** {i['detail']}"]
    if dismiss:
        md += ["", "## Dismissed", ""]
        md += [f"- `{k}`: {why}" for k, why in dismiss.items()]

    out = work / "REPORT.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(items)} findings, {n_edits} with edits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
