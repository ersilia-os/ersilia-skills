"""Number the findings and write the report the user approves IDs from.

Merges `check_drift.py` output with the agent's judgement findings (optional), gives
every finding a stable ID for this run (`B1…` Book, `R1…` READMEs) and writes:

- `--report` (default `<workdir>/report.md`): grouped by page / repo, high severity first
  within each group.
- `--out` (default `<workdir>/findings_final.json`): the numbered findings, input for
  `open_drift_issues.py`.

Judgement findings file: a JSON list of objects with `source` ("book" or "readme"),
`repo`, `path`, `line`, `claim` (the doc text, quoted), `evidence` (the code or fact it
contradicts, with its location), `suggestion` and `severity`; `page` is optional.

Exit codes: 0 on success, 2 on bad input.

Usage:
    python render_report.py --findings /tmp/docs-drift/findings.json \
        --judgement /tmp/docs-drift/judgement.json
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from _common import read_json, write_json

RANK = {"high": 0, "medium": 1, "low": 2}
REQUIRED = ("source", "repo", "path", "line", "claim", "evidence", "suggestion")


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def load_judgement(path: str | None) -> list[dict]:
    if not path:
        return []
    data = read_json(path)
    if data is None:
        return []
    bad = [i for i, f in enumerate(data) if any(k not in f for k in REQUIRED)]
    if bad:
        raise ValueError(f"judgement items {bad} miss one of {REQUIRED}")
    for f in data:
        f.setdefault("severity", "medium")
        f.setdefault("page", f["path"])
        f["check"] = "judgement"
    return data


def number(findings: list[dict]) -> list[dict]:
    findings = sorted(
        findings,
        key=lambda f: (
            f["source"],
            f["repo"],
            f["path"],
            RANK[f["severity"]],
            f["line"],
        ),
    )
    counters = {"book": 0, "readme": 0}
    for f in findings:
        counters[f["source"]] += 1
        f["id"] = ("B" if f["source"] == "book" else "R") + str(counters[f["source"]])
    return findings


def line_of(f: dict) -> str:
    where = f"line {f['line']}"
    if f.get("more_lines"):  # empty when repeats were on the same line
        where += f" (also {', '.join(map(str, f['more_lines']))})"
    text = (
        f"- **{f['id']}** · {f['severity']} · `{f['check']}` · {where}: "
        f"`{f['claim']}`. {cap(f['evidence'])}. → {f['suggestion']}"
    )
    for extra in f.get("folded", []):
        text += f"\n  - {extra}"
    return text


def render(findings: list[dict], checked: dict) -> str:
    n = len(findings)
    sev = {s: sum(f["severity"] == s for f in findings) for s in RANK}
    lines = [
        f"# Docs drift: {datetime.now(timezone.utc).date().isoformat()}",
        "",
        f"{n} findings ({sev['high']} high · {sev['medium']} medium · {sev['low']} low) "
        f"from {checked.get('book_pages', 0)} Book pages and "
        f"{checked.get('readmes', 0)} READMEs"
        + ("" if checked.get("external_links") else "; external links not checked")
        + ".",
    ]
    for source, heading in (("book", "Ersilia Book"), ("readme", "READMEs")):
        group = [f for f in findings if f["source"] == source]
        lines += ["", f"## {heading}"]
        if not group:
            lines += ["", "_No drift found._"]
            continue
        current = None
        for f in group:
            key = f["path"] if source == "book" else f["repo"]
            if key != current:
                current = key
                if source != "book":
                    title = f"`{key}`"
                elif f["page"] in (f["path"], f["path"].removeprefix("book/")):
                    title = f"`{f['path']}`"
                else:
                    title = f"{f['page']} (`{f['path']}`)"
                lines += ["", f"### {title}"]
            lines.append(line_of(f))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--findings", default="/tmp/docs-drift/findings.json")
    p.add_argument("--judgement", default=None)
    p.add_argument("--report", default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    data = read_json(args.findings)
    if not isinstance(data, dict) or "findings" not in data:
        print(f"ERROR: {args.findings} is not check_drift.py output", file=sys.stderr)
        return 2
    try:
        judged = load_judgement(args.judgement)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    workdir = Path(args.findings).parent
    findings = number(data["findings"] + judged)
    report = Path(args.report or workdir / "report.md")
    report.write_text(render(findings, data.get("checked", {})), encoding="utf-8")
    write_json(args.out or workdir / "findings_final.json", {"findings": findings})
    print(f"{len(findings)} findings → {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
