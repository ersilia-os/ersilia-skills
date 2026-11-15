"""Offline regression test: markers and grading, no models and no network.

1. Every pattern in references/markers.json matches each of its positive examples and none
   of its negative examples.
2. Every case in examples/cases/*.json is run through extract -> scan -> (prebuilt
   references, detectors, stylometry if given) -> grade, and must land in its expected tier
   (and produce the expected separate findings).

A case file:
    {"about": "...", "text": "...", "kind": "article",
     "judgements": {...}, "references": {...references.json...},
     "detectors": {...detectors.json...}, "stylometry": {...stylometry.json...},
     "expect": {"tier": "strong", "separate": ["manipulation"], "markers": ["oaicite"]}}

Run after every change to markers.json, grading.json or a script. Exit 1 on any failure.

Usage:
    python selftest.py [--case name]
"""

from __future__ import annotations

import argparse
import contextlib
import io
import subprocess
import sys
import tempfile
from pathlib import Path

from _common import EXAMPLES, REFS, read_json, write_json
from scan_artifacts import compile_pattern

HERE = Path(__file__).resolve().parent


def check_markers() -> list[str]:
    """Positive/negative examples of every marker."""
    errors = []
    for m in read_json(REFS / "markers.json")["patterns"]:
        rx = compile_pattern(m)
        if rx is None:
            errors.append(f"marker {m['id']}: no regex or lexicon")
            continue
        for s in m.get("examples", {}).get("pos", []):
            if not rx.search(s):
                errors.append(f"marker {m['id']}: misses positive example {s!r}")
        for s in m.get("examples", {}).get("neg", []):
            if rx.search(s):
                errors.append(f"marker {m['id']}: matches negative example {s!r}")
    return errors


def run(script: str, *args: str) -> str:
    """Run a sibling script; return its stdout (raise on failure)."""
    p = subprocess.run(
        [sys.executable, str(HERE / script), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"{script} failed: {p.stderr.strip()[:400]}")
    return p.stdout


def check_case(path: Path) -> list[str]:
    """Run one case end to end in a temporary work folder."""
    case = read_json(path)
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        src = work / "doc.txt"
        src.write_text(case["text"], encoding="utf-8")
        run("extract_text.py", str(src), "--work", tmp)
        if case.get("format"):
            doc = read_json(work / "text.json")
            doc["format"] = case["format"]
            write_json(work / "text.json", doc)
        run("scan_artifacts.py", "--work", tmp)
        for name in ("references", "detectors", "stylometry", "judgements"):
            if case.get(name) is not None:
                write_json(work / f"{name}.json", case[name])
        run("grade.py", "--work", tmp)
        g = read_json(work / "grade.json")
        arts = read_json(work / "artifacts.json")
        exp = case["expect"]
        if "tier" in exp and g["tier"] != exp["tier"]:
            errors.append(
                f"{path.stem}: tier {g['tier']}, expected {exp['tier']} (rules met: {g['rules_met']})"
            )
        if "tier_not" in exp and g["tier"] in exp["tier_not"]:
            errors.append(
                f"{path.stem}: tier {g['tier']} must not be one of {exp['tier_not']}"
            )
        got_sep = sorted({s["kind"] for s in g["separate"]})
        if "separate" in exp and got_sep != sorted(exp["separate"]):
            errors.append(
                f"{path.stem}: separate findings {got_sep}, expected {sorted(exp['separate'])}"
            )
        got_m = {h["marker"] for h in arts["hits"]}
        for m in exp.get("markers", []):
            if m not in got_m:
                errors.append(
                    f"{path.stem}: marker {m} did not fire (fired: {sorted(got_m)})"
                )
        for m in exp.get("markers_not", []):
            if m in got_m:
                errors.append(f"{path.stem}: marker {m} fired but must not")
        if exp.get("report"):
            with contextlib.redirect_stdout(io.StringIO()):
                run(
                    "build_report.py",
                    "--work",
                    tmp,
                    "--case",
                    path.stem,
                    "--kind",
                    case.get("kind", "article"),
                )
            if not (work / "report.html").exists():
                errors.append(f"{path.stem}: report not written")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Run all checks."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--case")
    args = p.parse_args(argv)
    errors = check_markers()
    print(
        f"{'ok  ' if not errors else 'FAIL'} markers ({len(read_json(REFS / 'markers.json')['patterns'])} patterns)"
    )
    for f in sorted((EXAMPLES / "cases").glob("*.json")):
        if args.case and f.stem != args.case:
            continue
        try:
            errs = check_case(f)
        except RuntimeError as ex:
            errs = [f"{f.stem}: {ex}"]
        print(f"{'ok  ' if not errs else 'FAIL'} {f.stem}")
        errors += errs
    for e in errors:
        print("  " + e)
    print("all passed" if not errors else f"{len(errors)} failure(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
