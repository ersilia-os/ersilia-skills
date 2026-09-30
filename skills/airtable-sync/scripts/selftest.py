"""Offline regression test for plan_sync.py and build_writes.py. No network, no Airtable.

Each file in `examples/cases/*.json` is one case:

    {"about": "...",
     "inputs": {"repositories": [...], "github": {...}, "publications": [...], ...},
     "expect": [{"table", "action", "label"?, "reason_has"?, "field"?, "value"?}],
     "expect_absent": [{...same matcher...}]}

``inputs`` are written as the work-directory files plan_sync.py reads; ``rules`` and
``ignore`` in inputs override the real references for that case. Every expected item
must appear in the plan and no ``expect_absent`` item may. When feedback changes
behaviour, add a case here that reproduces it (see record_feedback.py).

A final check confirms build_writes.py refuses flags, unfilled judgement fields,
choices without a side, unknown items or fields, and rejections of existing rows.

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

import build_writes
import plan_sync
from _common import SKILL_DIR, read_json, write_json

CASES = SKILL_DIR / "examples" / "cases"


def matches(item: dict, m: dict) -> bool:
    """True if a plan item satisfies a case matcher."""
    if item["table"] != m["table"] or item["action"] != m["action"]:
        return False
    if "label" in m and m["label"] != item["label"]:
        return False
    if "reason_has" in m and m["reason_has"].lower() not in item["reason"].lower():
        return False
    if "field" in m:
        if m["field"] not in item["fields"]:
            return False
        if "value" in m and item["fields"][m["field"]] != m["value"]:
            return False
    return True


def run_case(path: Path) -> list[str]:
    """Run one case; return failure messages."""
    case = json.loads(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        inputs = dict(case["inputs"])
        rules = SKILL_DIR / "references" / "rules.json"
        if "rules" in inputs:
            base = read_json(rules)
            for table, over in inputs.pop("rules").items():
                base[table].update(over)
            rules = work / "rules.json"
            write_json(rules, base)
        ignore = work / "ignore.json"
        write_json(ignore, inputs.pop("ignore", {"entries": []}))
        for name, data in inputs.items():
            write_json(work / f"{name}.json", data)
        with contextlib.redirect_stdout(io.StringIO()):
            plan_sync.main(
                ["--work", str(work), "--rules", str(rules), "--ignore", str(ignore)]
            )
        plan = read_json(work / "plan.json")
    fails = []
    for m in case.get("expect", []):
        if not any(matches(i, m) for i in plan["items"]):
            fails.append(f"expected {m}")
    for m in case.get("expect_absent", []):
        hit = [i for i in plan["items"] if matches(i, m)]
        if hit:
            fails.append(f"unexpected {m}: got [{hit[0]['n']}] {hit[0]['reason']}")
    return fails


def check_build_writes_guards() -> list[str]:
    """build_writes must refuse anything that is not a clean, approved, known write."""
    plan = {
        "items": [
            {
                "n": 1,
                "table": "repositories",
                "action": "flag",
                "record_id": "recAAAAAAAAAAAAAA",
                "label": "x",
                "fields": {},
                "judgement": [],
                "ignore_key": None,
            },
            {
                "n": 2,
                "table": "blogposts",
                "action": "create",
                "record_id": None,
                "label": "y",
                "fields": {"title": "y"},
                "judgement": ["category"],
                "ignore_key": "medium:abc",
            },
            {
                "n": 3,
                "table": "repositories",
                "action": "choice",
                "record_id": "recBBBBBBBBBBBBBB",
                "label": "z",
                "fields": {},
                "judgement": [],
                "ignore_key": None,
                "options": {"use-github": {"fields": {"status": ["Idle"]}}},
            },
            {
                "n": 4,
                "table": "publications",
                "action": "create",
                "record_id": None,
                "label": "p",
                "fields": {"title": "p", "year": "2026", "status": "Preprint"},
                "judgement": ["topic"],
                "ignore_key": "doi:10.1/p",
            },
        ]
    }
    refusals = (
        (["--approve", "1"], "a flag"),
        (["--approve", "2"], "a create without its category"),
        (["--approve", "3"], "a choice without --choose"),
        (["--approve", "3", "--choose", "3"], "a malformed --choose"),
        (["--approve", "9"], "an unknown item number"),
        (["--reject", "1"], "rejecting an item that is not a new row"),
        (["--approve", "2", "--judgements", "{tmp}/j.json"], "an unknown field name"),
        (["--approve", "4", "--judgements", "{tmp}/typo.json"], "a select typo"),
        (
            ["--reject", "2", "--approve", "1"],
            "a run with a refusal (and saves nothing)",
        ),
    )
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        write_json(Path(tmp) / "plan.json", plan)
        write_json(Path(tmp) / "j.json", {"2": {"category": ["News"], "colour": "red"}})
        write_json(Path(tmp) / "typo.json", {"4": {"topic": "Chemoinformatic"}})
        for extra, why in refusals:
            args = [a.replace("{tmp}", tmp) for a in extra]
            try:
                with (
                    contextlib.redirect_stderr(io.StringIO()),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    build_writes.main(
                        [
                            "--plan",
                            f"{tmp}/plan.json",
                            "--out",
                            f"{tmp}/w.json",
                            "--ignore",
                            f"{tmp}/i.json",
                            *args,
                        ]
                    )
                fails.append(f"build_writes accepted {why}")
            except SystemExit as exc:
                if exc.code == 0:
                    fails.append(f"build_writes accepted {why}")
        if (Path(tmp) / "i.json").exists():
            fails.append("a refused run still wrote the ignore list")

        # A repeated number is one write; a known year needs no typecast, a new one does.
        write_json(Path(tmp) / "t.json", {"4": {"topic": "Chemoinformatics"}})
        for year, want in (("2026", False), ("2031", True)):
            plan["items"][3]["fields"]["year"] = year
            write_json(Path(tmp) / "plan.json", plan)
            with contextlib.redirect_stdout(io.StringIO()):
                build_writes.main(
                    [
                        "--plan",
                        f"{tmp}/plan.json",
                        "--approve",
                        "4,4",
                        "--judgements",
                        f"{tmp}/t.json",
                        "--out",
                        f"{tmp}/w.json",
                        "--ignore",
                        f"{tmp}/i.json",
                    ]
                )
            call = read_json(Path(tmp) / "w.json")["calls"][0]
            if len(call["records"]) != 1:
                fails.append("a repeated item number was written twice")
            if call["typecast"] is not want:
                fails.append(
                    f"year {year}: typecast {call['typecast']}, expected {want}"
                )

        # And a clean approval must still go through, mapped to field IDs.
        write_json(Path(tmp) / "ok.json", {"2": {"category": ["News"]}})
        with contextlib.redirect_stdout(io.StringIO()):
            build_writes.main(
                [
                    "--plan",
                    f"{tmp}/plan.json",
                    "--approve",
                    "2",
                    "--judgements",
                    f"{tmp}/ok.json",
                    "--out",
                    f"{tmp}/w.json",
                    "--ignore",
                    f"{tmp}/i.json",
                ]
            )
        call = read_json(Path(tmp) / "w.json")["calls"][0]
        wanted = {"fldy4IdDdGDlvusvx": "y", "fld5t5MIGbE6e8G2B": ["News"]}
        if (
            call["tool"] != "create_records_for_table"
            or call["records"][0]["fields"] != wanted
        ):
            fails.append(
                f"build_writes built the wrong call for a valid approval: {call}"
            )
    return fails


def main(argv: list[str] | None = None) -> int:
    """Run every case and report."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("-k", default="")
    args = p.parse_args(argv)

    total_fail = 0
    for path in sorted(CASES.glob("*.json")):
        if args.k not in path.stem:
            continue
        fails = run_case(path)
        total_fail += len(fails)
        print(f"{'ok  ' if not fails else 'FAIL'} {path.stem}")
        for f in fails:
            print(f"     {f}")
    guard = check_build_writes_guards()
    total_fail += len(guard)
    print(f"{'ok  ' if not guard else 'FAIL'} build-writes-guards")
    for f in guard:
        print(f"     {f}")
    print("all passed" if not total_fail else f"{total_fail} failure(s)")
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
