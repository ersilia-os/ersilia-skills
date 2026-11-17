"""Offline regression test of the markers, the grading and the report. No network.

1. Every pattern in references/markers.json matches each of its positive examples and none
   of its negative examples.
2. Every case in examples/cases/*.json goes through extract -> scan -> grade, with any
   prebuilt inputs it gives, and must land in its expected tier, with the expected separate
   findings and markers. Cases with ``"report": true`` also build the report and check it.

A case file (every key but "text" and "expect" optional):
    {"about": "what the case pins down", "text": "...", "kind": "article", "format": "txt",
     "references": {...references.json...}, "stylometry": {...}, "judgements": {...},
     "web_detectors": {...}, "evidence": {...evidence.json...},
     "expect": {"tier": "moderate", "tier_not": ["strong"], "separate": ["manipulation"],
                "markers": ["oaicite"], "markers_not": ["..."], "report": true}}

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

from lib.common import EXAMPLES, REFS, read_json, write_json
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


def check_units() -> list[str]:
    """Small checks of helpers that the case files don't reach."""
    errors = []
    from drive_intake import file_id
    from extract_text import is_heading

    for url, want in (
        (
            "https://docs.google.com/document/d/1uimSQfhV-QJ4FWz6a5pcxeiwoZWRo63r/edit",
            "1uimSQfhV-QJ4FWz6a5pcxeiwoZWRo63r",
        ),
        (
            "https://drive.google.com/file/d/1ZyXwVuTsRqPoNmLkJiHgFeDcBa98765/view?usp=sharing",
            "1ZyXwVuTsRqPoNmLkJiHgFeDcBa98765",
        ),
        (
            "https://drive.google.com/open?id=1ZyXwVuTsRqPoNmLkJiHgFeDcBa98765",
            "1ZyXwVuTsRqPoNmLkJiHgFeDcBa98765",
        ),
    ):
        if file_id(url) != want:
            errors.append(f"drive_intake.file_id({url!r}) = {file_id(url)!r}")
    for line, want in (
        ("Reference", "Reference"),
        ("References", "References"),
        ("2.3 Data collection", "Data collection"),
        ("100 200 300 400 Compounds", None),
        ("A. h", None),
    ):
        if is_heading(line) != want:
            errors.append(
                f"extract_text.is_heading({line!r}) = {is_heading(line)!r}, expected {want!r}"
            )
    return errors


def check_docx_original() -> list[str]:
    """A DOCX with tracked changes gives the author's original text with --original."""
    import zipfile

    errors = []
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        '<w:p><w:r><w:t xml:space="preserve">The author wrote this </w:t></w:r>'
        '<w:del w:id="1" w:author="Reviewer"><w:r><w:delText>original phrase</w:delText></w:r></w:del>'
        '<w:ins w:id="2" w:author="Reviewer"><w:r><w:t>REVIEWER INSERTION</w:t></w:r></w:ins>'
        '<w:r><w:t xml:space="preserve"> and kept going.</w:t></w:r></w:p></w:body></w:document>'
    )
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "tracked.docx"
        with zipfile.ZipFile(src, "w") as z:
            z.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
            )
            z.writestr(
                "_rels/.rels",
                '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
            )
            z.writestr("word/document.xml", doc_xml)
        from extract_text import docx_original

        out = Path(tmp) / "orig.docx"
        authors = docx_original(src, out)
        with zipfile.ZipFile(out) as z:
            xml = z.read("word/document.xml").decode()
        if (
            "REVIEWER INSERTION" in xml
            or "original phrase" not in xml
            or authors != {"Reviewer": {"ins": 1, "del": 1}}
        ):
            errors.append(
                "extract_text.docx_original did not restore the author's text"
            )
    return errors


def check_library() -> list[str]:
    """The shared library on small inputs: splits, detector rules, evidence arithmetic."""
    import math

    from extract_text import assemble, from_text
    from lib.detectors import marks_ai
    from lib.evidence import combine, combine_tools
    from lib.splits import build_plan
    from lib.text import is_prose

    errors = []
    para = (
        "We measured the effect of the intervention in three cohorts recruited from "
        "rural clinics. Adherence was lower in the second cohort, which travelled further "
        "to reach the clinic. The difference persisted after adjusting for age and sex. "
    )
    # Prose before the first heading (a review's opening summary) is scored, not taken
    # for a title page.
    doc = assemble(from_text((para * 3 + "\n\n") * 4 + "Major comments\n\n" + para * 3))
    first = doc["sections"][0]
    plan = build_plan(doc)
    if first["title"] != "(start)" or not any(
        x["section"] == "(start)" for x in plan["sentences"]
    ):
        errors.append("splits: prose before the first heading is not scored")
    # A section that is a single passage is not also a section unit (no double counting).
    doc = assemble(from_text("Introduction\n\n" + (para * 2 + "\n\n") * 3))
    spans = [(u["scale"], u["spans"]) for u in build_plan(doc)["units"]]
    if any(sc == "S" and ("P", sp) in spans for sc, sp in spans):
        errors.append("splits: a section identical to a passage is counted twice")
    # Highlight rules: a site whose shading carries no verdict, a human green, an AI yellow.
    for tool, css, want in (
        ("aidetector_review", "rgba(249, 112, 21, 0.22)", False),
        ("zerogpt", "rgb(255, 255, 0)", True),
        ("zerogpt", "rgb(120, 200, 120)", False),
    ):
        if marks_ai(tool, css) != want:
            errors.append(f"detectors.marks_ai({tool!r}, {css!r}) is not {want}")
    # One-cell table rows never pass as prose.
    long_note = "Values are medians with interquartile ranges from the full virtual population of adults |"
    if is_prose("Physico-chemistry |") or is_prose(long_note):
        errors.append("text.is_prose accepts a one-cell table row")
    # The combination rule: independent tools add up; copies of one tool count once; a
    # tool that carries no information changes nothing.
    w = {"log_flag": 2.0, "log_clear": -1.0}
    weights = {"a": w, "b": dict(w), "u": {"log_flag": 0.0, "log_clear": 0.0}}
    independent = {"a|b": {"rho": 0.0}, "a|u": {"rho": 0.0}, "b|u": {"rho": 0.0}}
    copies = {"a|b": {"rho": 1.0}, "a|u": {"rho": 1.0}, "b|u": {"rho": 1.0}}
    for label, got, want in (
        (
            "independent tools add up",
            combine_tools({"a": 2.0, "b": 2.0}, weights, independent),
            4.0,
        ),
        (
            "copies count once",
            combine_tools({"a": 2.0, "b": 2.0}, weights, copies),
            2.0,
        ),
        (
            "an uninformative tool changes nothing",
            combine_tools({"a": 2.0, "u": 0.0}, weights, copies),
            2.0,
        ),
    ):
        if abs(got - want) > 1e-9:
            errors.append(
                f"evidence.combine_tools: {label} (got {got}, expected {want})"
            )
    # Evidence: one sentence, one unit, one tool scoring it AI -> log of its LR if flagged.
    cal = (
        (read_json(REFS / "web_calibration.json") or {}).get("tools", {}).get("zerogpt")
    )
    if cal:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            sent = {
                "id": "s1",
                "section": "x",
                "para": 0,
                "start": 0,
                "end": 50,
                "n_words": 9,
            }
            unit = {"chunk": "P1", "scale": "P", "spans": [[0, 50]]}
            write_json(
                work / "multi" / "plan.json", {"units": [unit], "sentences": [sent]}
            )
            write_json(
                work / "web_detectors.json",
                {"results": [{"tool": "zerogpt", "chunk": 1, "score": 0.9}]},
            )
            out = combine(work)
            want = round(math.log(cal["lr_flag"]), 3)
            if not out or out["sentences"][0]["evidence"] != want:
                errors.append(
                    f"evidence.combine: expected {want} for one flagging tool"
                )
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
        for name in (
            "references",
            "stylometry",
            "judgements",
            "web_detectors",
            "evidence",
        ):
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
            page = (
                (work / "report.html").read_text()
                if (work / "report.html").exists()
                else ""
            )
            if not page:
                errors.append(f"{path.stem}: report not written")
            for needle in (
                "<!-- section: answer -->",
                "<!-- section: text -->",
            ):
                if needle not in page:
                    errors.append(f"{path.stem}: raw report lacks {needle}")
            if not case.get("web_detectors") and not case.get("evidence"):
                if "no detector was run" not in page:
                    errors.append(
                        f"{path.stem}: report does not say that no detector ran"
                    )
            elif "<!-- section: glance -->" not in page or 'class="prow"' not in page:
                errors.append(f"{path.stem}: report lacks the passage panel")
            if (
                exp.get("markers") and page.count('<mark class="art"') < 2
            ):  # the legend has one
                errors.append(
                    f"{path.stem}: artefacts are not highlighted in the report text"
                )
    return errors


def main(argv: list[str] | None = None) -> int:
    """Run all checks."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--case")
    args = p.parse_args(argv)
    errors = check_markers()
    units = check_units() + check_docx_original()
    print(
        f"{'ok  ' if not units else 'FAIL'} units (Drive links, headings, tracked-changes DOCX)"
    )
    lib_errors = check_library()
    print(
        f"{'ok  ' if not lib_errors else 'FAIL'} library (splits, detector rules, evidence)"
    )
    units += lib_errors
    errors += units
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
