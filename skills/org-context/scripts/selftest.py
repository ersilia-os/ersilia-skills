"""Offline regression test for the checks, the fact verifier and apply_edits.py.

Each file in ``examples/cases/*.json`` is one case:

    {"about": "...",
     "today": "2026-10-05",
     "files": {"org": "...markdown...", "pkg": "..."},
     "rules": {...partial rules.json override...},
     "skills": ["stylia-plotting"],
     "repos": {"eosvc": false, "old-repo": true},
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
import connector_claims
import render_report
import verify_facts
from _common import REFS, SKILL_DIR, deep_merge, read_json, sha256, write_json

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
    for name, test in (("apply-edits", test_apply), ("connectors", test_connectors)):
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
