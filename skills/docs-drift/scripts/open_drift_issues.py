"""Open or update `docs-drift` issues for the findings the user approved.

Approved findings are grouped into one issue per Book page (in `ersilia-os/ersilia-book`)
and one issue per README (in that repo). Each issue carries a hidden marker for its page;
if an open issue with that marker exists, the new items are added to its checklist and
items already there (ticked or not) are kept. Nothing is ever closed.

Each issue is assigned to the org member who last edited the page, else to the member
with the most recent commit in the repo. If nobody qualifies it is left unassigned and
reported.

    python open_drift_issues.py --input /tmp/docs-drift/findings_final.json --plan --ids B1,B4,R2
    python open_drift_issues.py --input /tmp/docs-drift/findings_final.json --apply --ids B1,B4,R2

There is no approve-all switch. Issues are opened as the person running the script.

Exit codes: 0 on success, 1 if any issue failed, 2 on bad input.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from datetime import datetime, timezone

from _common import ORG, is_person, org_members, read_json, run_gh_json, warn

LABEL = "docs-drift"
LABEL_COLOR = "5319e7"
MARKER = "<!-- docs-drift:{path} -->"
ITEM_KEY = re.compile(r"<!-- k:([0-9a-f]{10}) -->")


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def key(f: dict) -> str:
    raw = f"{f['check']}|{f['claim']}|{f['evidence']}"
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def item(f: dict) -> str:
    url = f"https://github.com/{ORG}/{f['repo']}/blob/HEAD/{f['path']}#L{f['line']}"
    text = (
        f"- [ ] [Line {f['line']}]({url}) (`{f['check']}`): `{f['claim']}`. "
        f"{cap(f['evidence'])}. **Fix:** {f['suggestion']} <!-- k:{key(f)} -->"
    )
    for extra in f.get("folded", []):
        text += f"\n  - {extra}"
    return text


def group(findings: list[dict]) -> dict[tuple[str, str], list[dict]]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for f in findings:
        groups.setdefault((f["repo"], f["path"]), []).append(f)
    return groups


def title(fs: list[dict]) -> str:
    f = fs[0]
    if f["source"] == "book":
        return f"Docs drift: {f['page']}"
    return "Docs drift: README"


def body(path: str, items: list[str]) -> str:
    return "\n".join(
        [
            MARKER.format(path=path),
            (
                f"Parts of `{path}` no longer match the code or the GitHub "
                "organisation. Each item says what the text claims, what is true "
                "now, and a suggested fix."
            ),
            "",
            *items,
            "",
            (
                "Edit the text, then tick the item. Close the issue when every item "
                "is ticked; reply here if an item is wrong."
            ),
            "",
            f"_Found by the `docs-drift` skill, last updated {datetime.now(timezone.utc).date().isoformat()}._",
        ]
    )


def owner(repo: str, path: str, members: set[str]) -> tuple[str | None, str]:
    """(login, why): last member to edit the page, else last member to commit."""
    for scope, extra in (
        ("last edited the page", f"&path={path}"),
        ("recent committer", ""),
    ):
        data, _ = run_gh_json(
            [
                "api",
                f"repos/{ORG}/{repo}/commits?per_page=30{extra}",
                "--jq",
                "[.[].author.login]",
            ]
        )
        for login in data or []:
            if is_person(login, members):
                return login, scope
    return None, "unowned"


def existing(repo: str, path: str) -> tuple[int | None, str]:
    """(number, body) of an open issue with this page's marker."""
    data, err = run_gh_json(
        [
            "api",
            "--paginate",
            f"repos/{ORG}/{repo}/issues?state=open&labels={LABEL}&per_page=100",
        ]
    )
    if data is None:
        warn(f"{repo}: could not list issues: {err}")
        return None, ""
    marker = MARKER.format(path=path)
    hits = sorted(
        (i["number"], i.get("body") or "")
        for i in data
        if "pull_request" not in i and marker in (i.get("body") or "")
    )
    return hits[0] if hits else (None, "")


def gh(args: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    return proc.returncode == 0, (proc.stdout or proc.stderr).strip()


def merged_items(old_body: str, new: list[dict]) -> list[str]:
    """Old checklist items first (ticked state kept), then items not already there."""
    have = set()
    lines: list[str] = []
    old_lines = old_body.splitlines()
    for i, ln in enumerate(old_lines):
        m = ITEM_KEY.search(ln)
        if m and ln.startswith("- ["):
            have.add(m.group(1))
            lines.append(ln)
            # keep indented sub-bullets that belong to this item
            for sub in old_lines[i + 1 :]:
                if not sub.startswith("  - "):
                    break
                lines.append(sub)
    lines += [item(f) for f in new if key(f) not in have]
    return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", default="/tmp/docs-drift/findings_final.json")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    p.add_argument("--ids", required=True, help="comma-separated finding IDs")
    p.add_argument("--show-body", action="store_true")
    args = p.parse_args(argv)

    data = read_json(args.input)
    if not isinstance(data, dict) or "findings" not in data:
        print(f"ERROR: {args.input} is not render_report.py output", file=sys.stderr)
        return 2
    by_id = {f["id"]: f for f in data["findings"]}
    wanted = [i.strip().upper() for i in args.ids.split(",") if i.strip()]
    unknown = [i for i in wanted if i not in by_id]
    if not wanted or unknown:
        print(f"ERROR: unknown or missing IDs {unknown or wanted}", file=sys.stderr)
        return 2

    members = org_members()
    if not members:
        print("ERROR: org member list unavailable", file=sys.stderr)
        return 2
    failed = 0
    for (repo, path), fs in group([by_id[i] for i in wanted]).items():
        ids = ",".join(f["id"] for f in fs)
        login, why = owner(repo, path, members)
        number, old = existing(repo, path)
        text = body(path, merged_items(old, fs))
        action = f"update #{number}" if number else "open"
        print(f"{ids}\t{repo}\t{path}\t{action}\tassign: {login or '-'} ({why})")
        if args.show_body:
            print(text, end="\n\n")
        if args.plan:
            continue
        gh(
            [
                "label",
                "create",
                LABEL,
                "-R",
                f"{ORG}/{repo}",
                "--color",
                LABEL_COLOR,
                "--description",
                "Documentation that no longer matches the code",
            ]
        )
        if number:
            ok, out = gh(
                ["issue", "edit", str(number), "-R", f"{ORG}/{repo}", "--body", text]
            )
            url = f"https://github.com/{ORG}/{repo}/issues/{number}"
        else:
            ok, out = gh(
                [
                    "issue",
                    "create",
                    "-R",
                    f"{ORG}/{repo}",
                    "--title",
                    title(fs),
                    "--body",
                    text,
                    "--label",
                    LABEL,
                ]
            )
            url = out.splitlines()[-1] if ok and out else ""
            number = url.rsplit("/", 1)[-1] if ok else None
        if not ok:
            failed += 1
            print(f"\tFAILED: {out[:300]}")
            continue
        note = url
        if login:
            ok_a, _ = gh(
                [
                    "issue",
                    "edit",
                    str(number),
                    "-R",
                    f"{ORG}/{repo}",
                    "--add-assignee",
                    login,
                ]
            )
            note += f" · assigned {login}" if ok_a else f" · could not assign {login}"
        print(f"\t{note}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
