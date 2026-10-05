"""Offline regression test for the checks, the fact verifier and apply_edits.py.

Each file in ``examples/cases/*.json`` is one case:

    {"about": "...",
     "today": "2026-10-05",
     "files": {"org": "...markdown...", "pkg": "..."},
     "rules": {...partial rules.json override...},
     "skills": ["stylia-plotting"],
     "repos": {"eosvc": false, "old-repo": true},
     "reality": {"ana": {"tree": ["scripts/x.py"], "files": {"requirements.txt": ""}}},
     "expect": [{"target": "org", "check": "CANON-black", "title_has": "..."}],
     "expect_absent": [{...same matcher...}]}

``files`` keys are target ids from references/targets.json. ``skills`` and ``repos``
stand in for the skills directory and the GitHub org, so no network is used. When
feedback changes behaviour, add a case here that reproduces it (see record_feedback.py).

A final block checks apply_edits.py: it applies only listed IDs, refuses IDs from two
files, IDs without an edit, an ambiguous ``find`` and a file that changed since review,
and bumps the "Last updated" line.

Usage:
    python selftest.py [-k name-substring]
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

import apply_edits
import check_claude_md
import check_delivery
import fetch_targets
import connector_claims
import render_report
import verify_facts
from _common import (
    REFS,
    SKILL_DIR,
    deep_merge,
    format_month_year,
    parse_month_year,
    read_json,
    sha256,
    write_json,
)

CASES = SKILL_DIR / "examples" / "cases"


def setup_work(work: Path, files: dict[str, str]) -> None:
    """Write targets.json and files/ for the given {target id: text}."""
    config = {t["id"]: t for t in read_json(REFS / "targets.json")["targets"]}
    targets = []
    for tid, text in files.items():
        (work / "files").mkdir(parents=True, exist_ok=True)
        (work / "files" / f"{tid}.md").write_text(text, encoding="utf-8")
        targets.append(
            {
                **config[tid],
                "sha256": sha256(text),
                "lines": len(text.splitlines()),
                "status": "first review",
            }
        )
    write_json(work / "targets.json", targets)


def matches(item: dict, m: dict) -> bool:
    """True if a finding satisfies a case matcher."""
    if m.get("target") and item["target"] != m["target"]:
        return False
    if item["check"] != m["check"]:
        return False
    return m.get("title_has", "").lower() in item["title"].lower()


def run_case(path: Path) -> list[str]:
    """Run one case; return failure messages."""
    case = json.loads(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        setup_work(work, case["files"])
        rules = deep_merge(read_json(REFS / "rules.json"), case.get("rules", {}))
        write_json(work / "rules.json", rules)
        skills = work / "skills"
        for name in case.get("skills", []):
            (skills / name).mkdir(parents=True)
        skills.mkdir(exist_ok=True)
        write_json(work / "repos.json", case.get("repos", {}))
        write_json(work / "reality.json", case.get("reality", {}))
        with contextlib.redirect_stdout(io.StringIO()):
            check_claude_md.main(
                [
                    "--work",
                    str(work),
                    "--rules",
                    str(work / "rules.json"),
                    "--today",
                    case.get("today", "2026-10-05"),
                ]
            )
            verify_facts.main(
                [
                    "--work",
                    str(work),
                    "--rules",
                    str(work / "rules.json"),
                    "--offline",
                    "--repos-json",
                    str(work / "repos.json"),
                    "--skills-dir",
                    str(skills),
                    "--reality-json",
                    str(work / "reality.json"),
                ]
            )
        found = read_json(work / "checks.json") + read_json(work / "facts.json")
    fails = [
        f"expected {m}"
        for m in case.get("expect", [])
        if not any(matches(i, m) for i in found)
    ]
    fails += [
        f"unexpected {m}"
        for m in case.get("expect_absent", [])
        if any(matches(i, m) for i in found)
    ]
    if fails:
        fails.append("found: " + "; ".join(f"{i['key']} {i['title']}" for i in found))
    return fails


def refuses(argv: list[str]) -> bool:
    """True if apply_edits.main exits with an error for ``argv``."""
    with (
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        try:
            apply_edits.main(argv)
        except SystemExit as exc:
            return exc.code != 0
    return False


def test_apply() -> list[str]:
    """apply_edits.py safety rails and date bump."""
    org = "# Org\n\nUse black and ruff.\n\nSay it twice. Say it twice.\n\n*Last updated: May 2026.*\n"
    pkg = "# Pkg\n\nRun ruff.\n"
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        setup_work(work, {"org": org, "pkg": pkg})
        for name in ("checks.json", "facts.json"):
            write_json(work / name, [])
        write_json(
            work / "judgement.json",
            {
                "findings": [
                    {
                        "target": "org",
                        "severity": "fix",
                        "title": "black",
                        "edit": {"find": "Use black and ruff.", "replace": "Use ruff."},
                    },
                    {"target": "org", "severity": "consider", "title": "no edit"},
                    {
                        "target": "pkg",
                        "severity": "fix",
                        "title": "x",
                        "edit": {"find": "Run ruff.", "replace": "Run ruff check."},
                    },
                ]
            },
        )
        with contextlib.redirect_stdout(io.StringIO()):
            render_report.main(
                ["--work", str(work), "--today", "2026-10-05", "--skip-connectors"]
            )
        target = work / "org.md"
        target.write_text(org, encoding="utf-8")
        base = ["--work", str(work), "--file", str(target), "--today", "2026-10-05"]
        if not refuses(["--ids", "O1,P1", *base]):
            fails.append("apply: accepted IDs from two files")
        if not refuses(["--ids", "O2", *base]):
            fails.append("apply: accepted an ID without an edit")
        if not refuses(["--ids", "O9", *base]):
            fails.append("apply: accepted an unknown ID")
        target.write_text(org + "drift\n", encoding="utf-8")
        if not refuses(["--ids", "O1", *base]):
            fails.append("apply: accepted a file that changed since review")
        target.write_text(org, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            apply_edits.main(["--ids", "O1", *base])
        after = target.read_text(encoding="utf-8")
        if "Use ruff." not in after or "black" in after:
            fails.append("apply: O1 not applied")
        if "Last updated: October 2026" not in after:
            fails.append("apply: Last updated line not bumped")

        write_json(
            work / "judgement.json",
            {
                "findings": [
                    {
                        "target": "org",
                        "severity": "fix",
                        "title": "ambiguous",
                        "edit": {"find": "Say it twice.", "replace": "Once."},
                    }
                ]
            },
        )
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            try:
                render_report.main(["--work", str(work), "--skip-connectors"])
                fails.append("render: accepted an ambiguous 'find'")
            except SystemExit:
                pass
    return fails


def test_connectors() -> list[str]:
    """connector_claims.py: extraction from the org file and comparison."""
    org = (
        "# Org\n\n## Internal resources\n\n### Google Drive\n\n"
        "- **Grants:** submitted grants by year.\n"
        "- **Legal:** contracts.\n- **Platform:** roadmaps.\n- **Trainings:** courses.\n\n"
        "### Airtable\n\n- **Ersilia Content:** registry.\n"
        "- **Old Base:** gone.\n\n## Agent behaviour\n\nAsk.\n"
    )
    observed = {
        "drive": {
            "method": "connector",
            "drives": {
                "Grants": {"status": "found", "matches_description": True},
                "Legal": {"status": "missing", "evidence": "no root holds contracts"},
                "Platform": {"status": "found", "matches_description": False},
                "Trainings": {"status": "unverified"},
            },
            "unlisted": ["Docs"],
        },
        "airtable": {"bases": ["Ersilia Content", "Partner Tracker"]},
    }
    want = {
        ("FACT-DRIVE", "Legal"),
        ("FACT-DRIVE-DESC", "Platform"),
        ("FACT-DRIVE-UNLISTED", "Docs"),
        ("FACT-DRIVE-UNVERIFIED", "Trainings"),
        ("FACT-AIRTABLE", "Old Base"),
        ("FACT-AIRTABLE-UNLISTED", "Partner Tracker"),
    }
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        setup_work(work, {"org": org})
        with contextlib.redirect_stdout(io.StringIO()):
            connector_claims.main(["extract", "--work", str(work)])
            claims = read_json(work / "claims.json")
            names = [c["name"] for c in claims["drive"]]
            if names != ["Grants", "Legal", "Platform", "Trainings"]:
                fails.append(f"connectors: extracted drives {names}")
            write_json(work / "observed.json", observed)
            connector_claims.main(["compare", "--work", str(work)])
        found = read_json(work / "connectors.json")
    for check, name in want:
        if not any(i["check"] == check and name in i["title"] for i in found):
            fails.append(f"connectors: expected {check} for {name}")
    if any("Grants" in i["title"] for i in found):
        fails.append("connectors: flagged Grants, which was found and matches")
    return fails


def test_drive_links() -> list[str]:
    """Published drive links must be confirmed roots of drives closed to outsiders."""
    url = "https://drive.google.com/drive/folders/"
    org = (
        "# Org\n\n### Google Drive\n\n"
        f"- **[Grants]({url}0AGRANTS):** grants.\n"
        f"- **[Platform]({url}1SUBFOLDER):** roadmaps.\n"
        f"- **[Trainings]({url}0AOTHER):** courses.\n"
        f"- **[Content]({url}0ACONTENT):** brand.\n"
        "\n## Agent behaviour\n\nAsk.\n"
    )
    cache = {
        "drives": {
            "Grants": {"root_id": "0AGRANTS"},
            "Platform": {"root_id": "0APLATFORM"},
            "Trainings": {"root_id": "0ATRAININGS"},
            "Content": {"root_id": "0ACONTENT"},
        }
    }
    found = {"status": "found", "matches_description": True}
    observed = {
        "drive": {
            "drives": {
                "Grants": found,
                "Platform": found,
                "Trainings": found,
                "Content": {**found, "shared_publicly": True},
            }
        },
        "airtable": {"bases": []},
    }
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        setup_work(work, {"org": org})
        write_json(work / "map.json", cache)
        write_json(work / "observed.json", observed)
        with contextlib.redirect_stdout(io.StringIO()):
            connector_claims.main(["extract", "--work", str(work)])
            connector_claims.main(
                ["compare", "--work", str(work), "--drive-map", str(work / "map.json")]
            )
        items = read_json(work / "connectors.json")
        names = [c["name"] for c in read_json(work / "claims.json")["drive"]]
    fails = []
    if names != ["Grants", "Platform", "Trainings", "Content"]:
        fails.append(f"drive links: names parsed as {names}")
    want = [
        ("FACT-DRIVE-LINK", "Platform", "below the drive root"),
        ("FACT-DRIVE-LINK", "Trainings", "not its confirmed root"),
        ("FACT-DRIVE-PUBLIC", "Content", "open beyond"),
    ]
    for check, name, text in want:
        if not any(
            i["check"] == check and name in i["title"] and text in i["title"]
            for i in items
        ):
            fails.append(f"drive links: expected {check} for {name}")
    if any("Grants" in i["title"] for i in items):
        fails.append("drive links: flagged Grants, whose link is its confirmed root")
    return fails


def test_stable_ids() -> list[str]:
    """An approved ID keeps pointing at the same finding after a new finding appears."""
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        setup_work(work, {"org": "# Org\n\nRule one.\n\nRule two.\n"})
        for name in ("checks.json", "facts.json"):
            write_json(work / name, [])

        def render(findings):
            write_json(work / "judgement.json", {"findings": findings})
            with contextlib.redirect_stdout(io.StringIO()):
                render_report.main(["--work", str(work), "--skip-connectors"])
            plan = read_json(work / "plan.json")
            return {i["title"]: i["id"] for t in plan["targets"] for i in t["items"]}

        late = {"target": "org", "severity": "consider", "line": 5, "title": "late"}
        first = render([late])
        early = {"target": "org", "severity": "fix", "line": 1, "title": "early"}
        second = render([late, early])
        if second.get("late") != first.get("late"):
            fails.append(f"stable ids: 'late' moved from {first} to {second}")
        if second.get("early") in first.values():
            fails.append("stable ids: a new finding reused an existing ID")
    return fails


def test_delivery_and_dates() -> list[str]:
    """check_delivery.py finds a missing or broken import; month names ignore locale."""
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / ".claude").mkdir()
        memory = home / ".claude" / "CLAUDE.md"

        def run():
            with contextlib.redirect_stdout(io.StringIO()):
                check_delivery.main(["--work", tmp, "--home", tmp])
            return {i["check"] for i in read_json(home / "delivery.json")}

        memory.write_text("My own rule.\n", encoding="utf-8")
        if run() != {"DELIVERY-MISSING"}:
            fails.append("delivery: missing import not reported")
        memory.write_text("@/gone/ersilia-skills/config/CLAUDE.md\n", encoding="utf-8")
        if run() != {"DELIVERY-BROKEN"}:
            fails.append("delivery: broken import not reported")
        real = home / "ersilia-skills" / "config"
        real.mkdir(parents=True)
        (real / "CLAUDE.md").write_text("# Org\n", encoding="utf-8")
        memory.write_text(f"@{real / 'CLAUDE.md'}\n", encoding="utf-8")
        if run():
            fails.append("delivery: a working import was reported")
    day = parse_month_year("october 2026")
    if (day.year, day.month) != (2026, 10) or format_month_year(day) != "October 2026":
        fails.append("dates: month names are not parsed or written in English")
    return fails


def test_due_line() -> list[str]:
    """The monthly due date: DUE with no history or when past due, OK otherwise."""
    from datetime import date

    today = date(2026, 11, 10)
    cases = [
        ({}, "DUE"),
        ({"last_review": "2026-10-05", "next_review_due": "2026-11-04"}, "DUE"),
        ({"last_review": "2026-11-01", "next_review_due": "2026-12-01"}, "OK"),
    ]
    return [
        f"due: {state} gave '{fetch_targets.due_line(state, today)}'"
        for state, want in cases
        if not fetch_targets.due_line(state, today).startswith(want)
    ]


def main(argv: list[str] | None = None) -> int:
    """Run every case and the apply checks; exit 1 on any failure."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-k", default="")
    args = p.parse_args(argv)
    failed = 0
    for path in sorted(CASES.glob("*.json")):
        if args.k not in path.stem:
            continue
        fails = run_case(path)
        print(f"{'FAIL' if fails else 'ok  '} {path.stem}")
        for msg in fails:
            print(f"     {msg}")
        failed += bool(fails)
    tests = (
        ("apply-edits", test_apply),
        ("connectors", test_connectors),
        ("drive-links", test_drive_links),
        ("stable-ids", test_stable_ids),
        ("delivery-and-dates", test_delivery_and_dates),
        ("due-line", test_due_line),
    )
    for name, test in tests:
        if args.k not in name:
            continue
        fails = test()
        print(f"{'FAIL' if fails else 'ok  '} {name}")
        for msg in fails:
            print(f"     {msg}")
        failed += bool(fails)
    print(f"{failed} failure(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
