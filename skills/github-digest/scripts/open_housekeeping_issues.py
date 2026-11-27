"""Propose, then open or update, housekeeping issues from `fetch_housekeeping.py` output.

One issue per non-model repo with stale branches, opened in that repo. Stale branches in
model repos (`eosXXXX`) go into one roll-up issue in `--model-rollup-repo`
(default `ersilia-os/ersilia-maintenance`). Org-owned forks get a roll-up issue only when
`--org-forks-repo` is given. Personal forks are not issues; they go into Slack nudges.

Each proposal has a stable ID (H1, H2, ...) for a given input file. The script never acts
without explicit IDs:

    python open_housekeeping_issues.py --input /tmp/housekeeping.json --plan
    python open_housekeeping_issues.py --input /tmp/housekeeping.json --apply --ids H1,H4

There is no approve-all switch, on purpose. Issues carry a hidden marker; if an open issue
with the same marker exists, its body is updated instead of opening a duplicate. Nothing
is ever deleted or closed.

Exit codes: 0 on success, 1 if any approved action failed, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from _common import read_json, run_gh_json, warn
from _owners import choose_assignees

LABEL = "housekeeping"
LABEL_COLOR = "c5def5"
LABEL_DESCRIPTION = "Clean-up flagged by the weekly GitHub digest"
MARKER_BRANCHES = "<!-- github-digest:housekeeping:stale-branches -->"
MARKER_MODEL = "<!-- github-digest:housekeeping:model-branches -->"
MARKER_FORKS = "<!-- github-digest:housekeeping:org-forks -->"


REASON_TEXT = {
    "merged": "PR merged",
    "closed": "PR closed without merging",
    "idle": "no PR, no recent commits",
}

FOOTER = (
    "\n\n---\n"
    "Opened by the housekeeping check of the weekly "
    "[GitHub digest](https://ersilia-os.github.io/digests/). "
    "Nothing is deleted automatically. Delete what is no longer needed (or say why it "
    "should stay), then close this issue. If the list changes before then, the next run "
    "updates this issue instead of opening a new one."
)


def plural(n: int, one: str, many: str) -> str:
    """'1 stale branch' / '3 stale branches'."""
    return f"{n} {one if n == 1 else many}"


def _pr_cell(b: dict) -> str:
    pr = b.get("pr")
    return f"[#{pr['number']}]({pr['url']})" if pr else "-"


def _who(b: dict) -> str:
    # Backticks, not @mentions: the issue should not notify everyone who ever pushed.
    login = b.get("author_login")
    return f"`{login}`" if login else (b.get("author_name") or "-")


def branches_body(repo: str, branches: list[dict], org: str) -> str:
    """Issue body for one repo's stale branches."""
    lines = [
        MARKER_BRANCHES,
        f"These branches in `{repo}` look finished or abandoned:",
        "",
        "| Branch | Why | Last commit | PR | Last author |",
        "|---|---|---|---|---|",
    ]
    for b in branches:
        lines.append(
            f"| [`{b['branch']}`]({b['url']}) | {REASON_TEXT[b['reason']]} "
            f"| {b['last_commit'] or '-'} | {_pr_cell(b)} | {_who(b)} |"
        )
    merged = [b["branch"] for b in branches if b["reason"] in ("merged", "closed")]
    if merged:
        lines += [
            "",
            "Branches whose PR is merged or closed can be deleted safely:",
            "",
            "```bash",
            *(f"git push origin --delete {name}" for name in merged),
            "```",
        ]
    lines.append(
        "\nTo stop GitHub keeping merged branches in future, turn on "
        f"[Automatically delete head branches](https://github.com/{org}/{repo}/settings)."
    )
    return "\n".join(lines) + FOOTER


def model_body(branches: list[dict]) -> str:
    """Roll-up issue body for stale branches in model repos."""
    lines = [
        MARKER_MODEL,
        (
            f"{plural(len(branches), 'stale branch', 'stale branches')} across "
            f"{plural(len({b['repo'] for b in branches}), 'model repository', 'model repositories')}:"
        ),
        "",
        "| Model | Branch | Why | Last commit | PR |",
        "|---|---|---|---|---|",
    ]
    for b in branches:
        lines.append(
            f"| `{b['repo']}` | [`{b['branch']}`]({b['url']}) | {REASON_TEXT[b['reason']]} "
            f"| {b['last_commit'] or '-'} | {_pr_cell(b)} |"
        )
    return "\n".join(lines) + FOOTER


def forks_body(forks: list[dict]) -> str:
    """Roll-up issue body for forks owned by the org."""
    lines = [
        MARKER_FORKS,
        (
            "Forks owned by the organisation. For each, decide: keep (and sync), "
            "archive, or delete."
        ),
        "",
        "| Fork | Parent | Last push | Ahead | Behind |",
        "|---|---|---|---|---|",
    ]
    for f in forks:
        lines.append(
            f"| [`{f['repo']}`]({f['url']}) | [{f['parent']}]({f['parent_url']}) "
            f"| {f['pushed_at'] or '-'} | {f.get('ahead_by', '?')} | {f.get('behind_by', '?')} |"
        )
    return "\n".join(lines) + FOOTER


def build_proposals(data: dict, model_repo: str, forks_repo: str | None) -> list[dict]:
    """All proposed issues, in a stable order, with IDs H1..Hn."""
    org = data["org"]
    proposals: list[dict] = []
    by_repo: dict[str, list[dict]] = {}
    for b in data["stale_branches"]:
        if not b["is_model"]:
            by_repo.setdefault(b["repo"], []).append(b)
    for repo in sorted(by_repo):
        branches = by_repo[repo]
        proposals.append(
            {
                "repo": f"{org}/{repo}",
                "title": "Housekeeping: stale branches",
                "marker": MARKER_BRANCHES,
                "body": branches_body(repo, branches, org),
                "branches": branches,
                "summary": plural(len(branches), "stale branch", "stale branches"),
            }
        )
    model = [b for b in data["stale_branches"] if b["is_model"]]
    if model:
        proposals.append(
            {
                "repo": model_repo,
                "title": "Housekeeping: stale branches in model repositories",
                "marker": MARKER_MODEL,
                "body": model_body(model),
                "branches": model,
                "summary": plural(len(model), "stale branch", "stale branches")
                + " in model repos (roll-up)",
            }
        )
    if forks_repo and data["org_forks"]:
        proposals.append(
            {
                "repo": forks_repo,
                "title": "Housekeeping: forks owned by the organisation",
                "marker": MARKER_FORKS,
                "body": forks_body(data["org_forks"]),
                "summary": f"{len(data['org_forks'])} org-owned forks (roll-up)",
            }
        )
    for i, prop in enumerate(proposals, 1):
        prop["id"] = f"H{i}"
    return proposals


def add_assignees(proposals: list[dict], data: dict) -> None:
    """Attach assignees to each proposal (read-only gh calls)."""
    members = set(data.get("members") or [])
    if not members:
        fetched, err = run_gh_json(
            ["api", "--paginate", f"orgs/{data['org']}/members?per_page=100"]
        )
        if fetched is None:
            warn(f"org members unavailable, issues will be unassigned: {err}")
        members = {m["login"] for m in fetched or []}
    for prop in proposals:
        if prop.get("branches") is None:
            prop["assignees"], prop["assigned_by"] = [], "roll-up"
            continue
        prop["assignees"], prop["assigned_by"] = choose_assignees(
            prop["repo"], prop["branches"], members
        )


def find_existing(repo: str, marker: str) -> tuple[int | None, str]:
    """Number of an open housekeeping issue carrying `marker`, if any.

    Uses the REST issues list, not `gh issue list --label`: the latter goes through GitHub
    search, which lags by minutes, so an issue opened moments ago would be missed and
    duplicated.
    """
    data, err = run_gh_json(
        [
            "api",
            "--paginate",
            f"repos/{repo}/issues?state=open&labels={LABEL}&per_page=100",
        ]
    )
    if data is None:
        return None, err
    matches = sorted(
        i["number"]
        for i in data
        if "pull_request" not in i and marker in (i.get("body") or "")
    )
    return (matches[0] if matches else None), ""


def gh(args: list[str]) -> tuple[bool, str]:
    """Run a mutating gh command. Returns (ok, stdout-or-error)."""
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    out = (proc.stdout or proc.stderr).strip()
    return proc.returncode == 0, out


def ensure_label(repo: str) -> None:
    """Create the housekeeping label if the repo lacks it (no-op otherwise)."""
    gh(
        [
            "label",
            "create",
            LABEL,
            "-R",
            repo,
            "--color",
            LABEL_COLOR,
            "--description",
            LABEL_DESCRIPTION,
        ]
    )


def apply(prop: dict) -> tuple[bool, str]:
    """Open or update one issue, then assign it. Returns (ok, message)."""
    number, err = find_existing(prop["repo"], prop["marker"])
    if err:
        return False, f"could not search issues: {err}"
    if number:
        ok, out = gh(
            ["issue", "edit", str(number), "-R", prop["repo"], "--body", prop["body"]]
        )
        if not ok:
            return False, out
        url = f"https://github.com/{prop['repo']}/issues/{number}"
        return (
            True,
            f"updated {url}{assign(prop['repo'], str(number), prop['assignees'])}",
        )
    ensure_label(prop["repo"])
    ok, out = gh(
        [
            "issue",
            "create",
            "-R",
            prop["repo"],
            "--title",
            prop["title"],
            "--label",
            LABEL,
            "--body",
            prop["body"],
        ]
    )
    if not ok:
        return False, out
    number = out.rstrip("/").rsplit("/", 1)[-1]
    return True, f"opened {out}{assign(prop['repo'], number, prop['assignees'])}"


def assign(repo: str, number: str, assignees: list[str]) -> str:
    """Add assignees one by one, so one unassignable login does not block the rest."""
    if not assignees:
        return " (unassigned)"
    done, failed = [], []
    for login in assignees:
        ok, _ = gh(["issue", "edit", number, "-R", repo, "--add-assignee", login])
        (done if ok else failed).append(login)
    note = f" (assigned {', '.join(done)})" if done else " (unassigned)"
    if failed:
        warn(f"{repo}#{number}: could not assign {', '.join(failed)}")
        note += f" [could not assign {', '.join(failed)}]"
    return note


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", default="/tmp/housekeeping.json")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--plan", action="store_true", help="list proposals, change nothing"
    )
    mode.add_argument("--apply", action="store_true", help="act on --ids only")
    p.add_argument("--ids", default="", help="comma-separated proposal IDs, e.g. H1,H3")
    p.add_argument("--model-rollup-repo", default="ersilia-os/ersilia-maintenance")
    p.add_argument(
        "--org-forks-repo",
        default=None,
        help="repo for the org-forks roll-up issue; omitted = no issue",
    )
    p.add_argument("--show-body", action="store_true", help="print full issue bodies")
    p.add_argument("--json-out", default=None, help="write proposals as JSON here")
    args = p.parse_args(argv)

    data = read_json(args.input)
    if not data or "stale_branches" not in data:
        print(
            f"ERROR: {args.input} is missing or not housekeeping output",
            file=sys.stderr,
        )
        return 2
    proposals = build_proposals(data, args.model_rollup_repo, args.org_forks_repo)
    add_assignees(proposals, data)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(proposals, f, indent=2)

    if args.plan:
        if not proposals:
            print("No housekeeping issues to propose.")
        for prop in proposals:
            who = ", ".join(prop["assignees"]) or "-"
            print(
                f"{prop['id']}\t{prop['repo']}\t{prop['summary']}\t"
                f"assign: {who} ({prop['assigned_by']})"
            )
            if args.show_body:
                print(prop["body"], end="\n\n")
        return 0

    wanted = [i.strip().upper() for i in args.ids.split(",") if i.strip()]
    if not wanted:
        print("ERROR: --apply needs --ids (there is no approve-all)", file=sys.stderr)
        return 2
    by_id = {prop["id"]: prop for prop in proposals}
    unknown = [i for i in wanted if i not in by_id]
    if unknown:
        print(
            f"ERROR: unknown IDs {unknown}; re-run --plan on the same input",
            file=sys.stderr,
        )
        return 2
    failed = 0
    for pid in wanted:
        ok, msg = apply(by_id[pid])
        print(f"{pid}\t{by_id[pid]['repo']}\t{msg}")
        if not ok:
            failed += 1
            warn(f"{pid} failed: {msg}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
