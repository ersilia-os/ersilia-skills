#!/usr/bin/env python3
"""GitHub-side checks: description, topics, default branch, CI, releases, workflows.

Everything here comes from the `gh` CLI or from `.github/` on disk. When `gh` is
unavailable or unauthenticated the GitHub-dependent checks are recorded as skipped — an
unreachable API is not a pass.

Exit codes
----------
0   ran to completion
2   bad usage or unreadable target

Usage
-----
    python check_repo_meta.py --target /tmp/repo_audit_target.json \\
                              [--type Package] [--status "In progress"] \\
                              [--out /tmp/repo_audit_meta.json]
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from _common import (
    TomlError,
    emit,
    finding,
    load_target,
    load_toml,
    plural,
    read_text,
    rollup,
    run,
    run_gh_json,
    skipped,
    verb,
)

SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")

# Actions maintained inside the org. `@main` on these is the house pattern — every model
# repo calls ersilia-model-workflows at @main so workflow fixes propagate without a
# fleet-wide bump. Reported as informational, never as a finding.
FIRST_PARTY_ACTION = re.compile(r"^ersilia-os/")

# Widely-audited actions where a floating major tag is normal practice.
WELL_KNOWN_ACTION = re.compile(r"^(actions|github|docker|astral-sh|conda-incubator)/")

CI_QUALITY_MARKERS = {
    "ruff": re.compile(r"\bruff\b"),
    "pytest": re.compile(r"\bpytest\b|\bnox\b|\bpython -m unittest\b"),
}


def workflows(repo: Path) -> list[Path]:
    """Workflow YAML files, sorted."""
    wdir = repo / ".github" / "workflows"
    if not wdir.is_dir():
        return []
    return sorted(p for p in wdir.iterdir() if p.suffix in (".yml", ".yaml"))


def workflow_name(text: str, fallback: str) -> str:
    """The workflow's `name:` value, or the filename."""
    m = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else fallback


def check_repo_name(name: str, findings: list) -> None:
    """The repository name is lowercase alphanumeric with hyphens only.

    Hyphen is the only permitted non-alphanumeric character. Underscores in particular are
    not allowed — they read badly in URLs, are easy to mistype, and split inconsistently
    from the hyphens used everywhere else in the org. Of 179 repos in the registry, zero
    currently use an underscore and only `ersilia.io` deviates at all, so this is a rule the
    org already follows and worth keeping that way.
    """
    if not name:
        return
    bad = sorted(
        {
            c
            for c in name
            if not (c.isascii() and (c.isalnum() and not c.isupper() or c == "-"))
        }
    )
    if not bad:
        return
    has_underscore = "_" in bad
    findings.append(
        finding(
            "T0-REPO-NAME",
            "T0",
            "Should-fix",
            f"The repository name `{name}` uses "
            + ", ".join(f"`{c}`" for c in bad)
            + "; only lowercase letters, digits and `-` are allowed.",
            "Rename the repository to lowercase-with-hyphens"
            + (
                ". Underscores are not permitted — replace `_` with `-`."
                if has_underscore
                else "."
            )
            + " GitHub sets up a redirect from the old name, so existing clones and links keep "
            "working; update the Airtable `Name` field to match.",
        )
    )


def check_github_metadata(gh: dict, findings: list, skips: list) -> None:
    """Description, topics and default branch."""
    if not gh:
        for cid in ("T0-GH-DESC-MISSING", "T0-GH-TOPICS-FEW", "T0-DEFAULT-BRANCH"):
            skips.append(
                skipped(cid, "GitHub metadata unavailable (gh not authenticated?)")
            )
        return

    if not (gh.get("description") or "").strip():
        findings.append(
            finding(
                "T0-GH-DESC-MISSING",
                "T0",
                "Should-fix",
                "The GitHub repository description is empty.",
                "Set a one-line description — it is what people see in search results and in "
                "the org listing.",
            )
        )

    topics = gh.get("topics") or []
    if len(topics) < 3:
        findings.append(
            finding(
                "T0-GH-TOPICS-FEW",
                "T0",
                "Should-fix",
                f"The repository has {plural(len(topics), 'GitHub topic')}; at least 3 are expected.",
                "Add topics so the repo is discoverable — e.g. `drug-discovery`, "
                "`machine-learning`, `global-health`, plus the pathogen or method.",
                detail=("current: " + ", ".join(topics)) if topics else None,
            )
        )

    branch = gh.get("default_branch") or ""
    if branch and branch != "main":
        findings.append(
            finding(
                "T0-DEFAULT-BRANCH",
                "T0",
                "Should-fix",
                f"The default branch is `{branch}`, not `main`.",
                "Rename it, unless the repo has external consumers pinned to the old name — "
                "`ersilia` itself is on `master` for exactly that reason.",
            )
        )


def check_ci(repo: Path, rtype: str, findings: list, skips: list) -> None:
    """CI presence and whether any workflow enforces lint and tests."""
    wfs = workflows(repo)
    if not wfs:
        if rtype in ("Package", "Automation"):
            findings.append(
                finding(
                    "PKG-NO-CI" if rtype == "Package" else "AUT-NO-WORKFLOWS",
                    "T1",
                    "Should-fix",
                    "There are no GitHub Actions workflows.",
                    "Add one that runs `ruff check` and `pytest` on push and pull request, "
                    "mirroring `ersilia`'s `tests_and_cleanup.yml`."
                    if rtype == "Package"
                    else "An Automation repo with no workflows is not automating anything — "
                    "confirm the type is right.",
                )
            )
        else:
            skips.append(
                skipped(
                    "PKG-CI-NO-QUALITY",
                    f"no workflows, and {rtype} repos do not require CI",
                )
            )
        return

    if rtype != "Package":
        skips.append(skipped("PKG-CI-NO-QUALITY", f"not a Package repo (type={rtype})"))
        return

    has_lint = has_tests = False
    for wf in wfs:
        text = read_text(wf)
        if CI_QUALITY_MARKERS["ruff"].search(text):
            has_lint = True
        if CI_QUALITY_MARKERS["pytest"].search(text):
            has_tests = True

    missing = [n for n, ok in (("ruff", has_lint), ("pytest", has_tests)) if not ok]
    if missing:
        findings.append(
            finding(
                "PKG-CI-NO-QUALITY",
                "T1",
                "Should-fix",
                f"No workflow runs {' or '.join(missing)}.",
                "Add a quality job. A publish-only workflow does not count — `lazy-qsar` and "
                "`stylia` both have CI that only pushes to PyPI, so nothing catches a "
                "regression before release.",
                detail="workflows: " + rollup([w.name for w in wfs]),
            )
        )


def check_workflow_hygiene(repo: Path, rtype: str, findings: list, skips: list) -> None:
    """Automation-profile workflow checks: documented, pinned, scheduled, no secrets inline."""
    wfs = workflows(repo)
    if not wfs:
        for cid in (
            "AUT-WORKFLOW-UNDOCUMENTED",
            "AUT-ACTION-UNPINNED",
            "AUT-SCHEDULE-UNDOCUMENTED",
        ):
            skips.append(skipped(cid, "no workflows"))
        return

    readme = read_text(repo / "README.md")
    undocumented: list[str] = []
    unpinned: list[str] = []
    first_party_floating: list[str] = []
    scheduled_undocumented: list[str] = []
    secret_names: set[str] = set()

    for wf in wfs:
        text = read_text(wf)
        name = workflow_name(text, wf.name)
        if wf.name not in readme and name not in readme:
            undocumented.append(f'{wf.name} ("{name}")')

        for m in re.finditer(r"uses:\s*([^\s@]+)@([^\s#]+)", text):
            action, ref = m.group(1), m.group(2).strip().strip("\"'")
            floating = ref in ("main", "master", "HEAD")
            if not floating:
                continue
            if FIRST_PARTY_ACTION.match(action):
                first_party_floating.append(f"{wf.name}: {action}@{ref}")
            else:
                unpinned.append(f"{wf.name}: {action}@{ref}")

        if re.search(r"^\s*schedule:", text, re.MULTILINE):
            crons = re.findall(r"cron:\s*[\"']([^\"']+)[\"']", text)
            documented = any(c in readme for c in crons) or "schedule" in readme.lower()
            if not documented:
                scheduled_undocumented.append(
                    f"{wf.name} ({', '.join(crons) or 'schedule'})"
                )

        secret_names.update(re.findall(r"secrets\.([A-Z0-9_]+)", text))

    if undocumented:
        findings.append(
            finding(
                "AUT-WORKFLOW-UNDOCUMENTED",
                "T1",
                "Should-fix",
                f"{len(undocumented)} of {plural(len(wfs), 'workflow')} not mentioned in the README.",
                "List each workflow and when it runs. Someone debugging a failure should not "
                "have to read `.github/workflows/` to find out what exists.",
                detail=rollup(undocumented),
            )
        )
    if unpinned:
        findings.append(
            finding(
                "AUT-ACTION-UNPINNED",
                "T1",
                "Should-fix",
                f"{plural(len(unpinned), 'third-party action reference')} "
                f"{verb(len(unpinned), 'floats', 'float')} on a branch.",
                "Pin to a release tag or a commit SHA. A floating third-party action is "
                "arbitrary code that can change under you.",
                detail=rollup(unpinned),
            )
        )
    if first_party_floating:
        findings.append(
            finding(
                "AUT-ACTION-UNPINNED",
                "T1",
                "Nice-to-have",
                f"{plural(len(first_party_floating), 'first-party `ersilia-os/*` reference')} "
                "use `@main`.",
                "This is the established house pattern — model repos pick up workflow fixes "
                "without a fleet-wide bump. Noted for awareness only; no action needed unless "
                "you want reproducible CI.",
                detail=rollup(first_party_floating),
                confidence="medium",
            )
        )
    if scheduled_undocumented:
        findings.append(
            finding(
                "AUT-SCHEDULE-UNDOCUMENTED",
                "T1",
                "Should-fix",
                f"{plural(len(scheduled_undocumented), 'scheduled workflow')} "
                f"{verb(len(scheduled_undocumented), 'has', 'have')} no documented cadence.",
                "State the schedule in the README. An undocumented cron is invisible "
                "infrastructure.",
                detail=rollup(scheduled_undocumented),
            )
        )
    if secret_names:
        findings.append(
            finding(
                "AUT-SECRETS-USED",
                "T1",
                "Nice-to-have",
                f"The workflows consume {plural(len(secret_names), 'secret')}.",
                "Informational: confirm each is still needed and still set at the repo or org "
                "level. This skill cannot read secret values and does not verify they exist.",
                detail=", ".join(f"`{s}`" for s in sorted(secret_names)),
            )
        )


def check_app(repo: Path, rtype: str, findings: list, skips: list) -> None:
    """App-profile checks: a runnable entry point, and docs for running it."""
    if rtype != "App":
        skips.append(skipped("APP-NO-ENTRYPOINT", f"not an App repo (type={rtype})"))
        return

    entry = [
        n
        for n in (
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
            "Procfile",
            "Makefile",
        )
        if (repo / n).is_file()
    ]
    readme = read_text(repo / "README.md")
    documented = bool(
        re.search(
            r"(?i)```[a-z]*\s*\n[^`]*\b(docker (run|compose)|npm (run|start)|yarn|streamlit run|"
            r"uvicorn|gunicorn|flask run|python -m|make)\b",
            readme,
        )
    )

    if not entry and not documented:
        findings.append(
            finding(
                "APP-NO-ENTRYPOINT",
                "T1",
                "Should-fix",
                "There is no Dockerfile, compose file, Procfile or Makefile, and the README "
                "documents no start command.",
                "Add whichever fits, so the app can be run without reverse-engineering it.",
            )
        )
    if not documented:
        findings.append(
            finding(
                "APP-NO-RUN-DOCS",
                "T1",
                "Should-fix",
                "The README does not show how to run the app locally.",
                "Add a short fenced block with the actual command."
                + (f" The repo has {rollup(entry)} to build on." if entry else ""),
                file="README.md",
            )
        )


def check_releases(
    repo: Path,
    owner: str,
    name: str,
    rtype: str,
    status: list[str],
    findings: list,
    skips: list,
) -> None:
    """Semver tags, and agreement between the tag, the release and the declared version."""
    if rtype != "Package":
        for cid in ("PKG-TAG-NOT-SEMVER", "PKG-VERSION-MISMATCH", "PKG-NO-RELEASE"):
            skips.append(skipped(cid, f"not a Package repo (type={rtype})"))
        return

    tags_proc = run(["git", "-C", str(repo), "tag", "--list", "--sort=-v:refname"])
    tags = (
        [t.strip() for t in tags_proc.stdout.splitlines() if t.strip()]
        if tags_proc.returncode == 0
        else []
    )

    non_semver = [t for t in tags if not SEMVER_RE.match(t)]
    if non_semver:
        findings.append(
            finding(
                "PKG-TAG-NOT-SEMVER",
                "T1",
                "Should-fix",
                f"{len(non_semver)} of {plural(len(tags), 'tag')} not semantic versions.",
                'Use `vMAJOR.MINOR.PATCH` only. "Do not use date-based, build-number, or '
                'other schemes."',
                detail=rollup(non_semver),
            )
        )

    semver_tags = [t for t in tags if SEMVER_RE.match(t)]
    latest_tag = semver_tags[0] if semver_tags else None

    declared = None
    pp_path = repo / "pyproject.toml"
    if pp_path.is_file():
        try:
            pp = load_toml(read_text(pp_path))
            declared = (pp.get("project") or {}).get("version") or (
                ((pp.get("tool") or {}).get("poetry") or {}).get("version")
            )
        except TomlError:
            pass

    release_name = None
    if shutil.which("gh"):
        data, err = run_gh_json(["api", f"repos/{owner}/{name}/releases/latest"])
        if isinstance(data, dict):
            release_name = data.get("tag_name") or data.get("name")
        elif err and "404" not in err:
            skips.append(
                skipped("PKG-NO-RELEASE", f"could not read releases: {err[:120]}")
            )
    else:
        skips.append(skipped("PKG-NO-RELEASE", "gh not on PATH"))

    def norm(v: str | None) -> str | None:
        return v.lstrip("v") if v else None

    triple = {
        "latest tag": norm(latest_tag),
        "GitHub release": norm(release_name),
        "pyproject version": norm(declared),
    }
    present = {k: v for k, v in triple.items() if v}
    if len(set(present.values())) > 1:
        findings.append(
            finding(
                "PKG-VERSION-MISMATCH",
                "T1",
                "Should-fix",
                "The tag, the GitHub release and the declared version do not agree.",
                'Bring all three into line. "The git tag, GitHub release name, and '
                '`[project].version` must all match — release is blocked otherwise."',
                detail="; ".join(f"{k}: `{v}`" for k, v in present.items()),
            )
        )

    if not release_name and any(s.lower() == "completed" for s in status):
        findings.append(
            finding(
                "PKG-NO-RELEASE",
                "T1",
                "Nice-to-have",
                "Airtable marks this repo Completed but it has no GitHub release.",
                "Cut a release so consumers have something citable to pin to."
                + (f" The latest tag is `{latest_tag}`." if latest_tag else ""),
            )
        )


def community_gate(gh: dict) -> tuple[bool, str]:
    """Whether community files are a fair expectation of this repository.

    CONTRIBUTING, a code of conduct and issue templates matter for a repo other people
    build on. On a 7-commit script they are noise, and `ersilia` is not the bar every
    package should be held to. Verified against live GitHub data across the surveyed
    packages: this threshold closes for `eosquality` (1 contributor, 1 release, 1 star) and
    opens for every other one.

    The `>= 2 releases` term is deliberate. An earlier draft used `>= 1`, which let a single
    `v0.0.1` tag on an early-stage repo open the gate — the opposite of the intent.

    Returns
    -------
    tuple
        `(open, reason)`. `reason` states the actual numbers so a closed gate is auditable.
    """
    contributors = gh.get("contributors") or 0
    stars = gh.get("stars") or 0
    releases = gh.get("releases") or 0
    if contributors >= 3 or stars >= 5 or releases >= 2:
        return True, ""
    return False, (
        f"early-stage repo ({plural(contributors, 'contributor')}, "
        f"{plural(releases, 'release')}, {plural(stars, 'star')}); community files are not "
        "a fair expectation yet"
    )


def cites_a_paper(repo: Path) -> bool:
    """True if the README cites a DOI or an arXiv id.

    The stronger signal is an Airtable link to a Publications record, which the LLM
    supplies in Step 2 — Python cannot reach the MCP.
    """
    readme = read_text(repo / "README.md")
    return bool(
        re.search(r"\b10\.\d{4,9}/\S+", readme)
        or re.search(r"arxiv\.org/abs/\S+", readme, re.IGNORECASE)
    )


def check_tier2(
    repo: Path, findings: list, skips: list, gh: dict, backs_paper: bool = False
) -> None:
    """The flagship-only community and packaging files, gated on repo maturity.

    Nothing here is unconditional. Each item fires only when it is a fair expectation of
    this particular repository, and when it is gated out the skip records the numbers that
    closed it — so a missing finding is never mistaken for a pass.
    """
    gate_open, gate_reason = community_gate(gh)
    releases = gh.get("releases") or 0
    backs_paper = backs_paper or cites_a_paper(repo)

    # id -> (fires?, why not)
    gated = {
        "T2-NO-CONTRIBUTING": (gate_open, gate_reason),
        "T2-NO-COC": (gate_open, gate_reason),
        "T2-NO-ISSUE-TEMPLATE": (gate_open, gate_reason),
        "T2-NO-PR-TEMPLATE": (gate_open, gate_reason),
        "T2-NO-DEPENDABOT": (gate_open, gate_reason),
        "T2-NO-CHANGELOG": (
            releases >= 2,
            f"only {plural(releases, 'release')}; a changelog earns its keep once there are versions "
            "to compare",
        ),
        "T2-NO-CITATION": (
            backs_paper,
            "no linked publication and no DOI or arXiv id in the README",
        ),
    }

    wants = [
        (
            "T2-NO-CONTRIBUTING",
            ["CONTRIBUTING.md", "CONTRIBUTING.rst", ".github/CONTRIBUTING.md"],
            "CONTRIBUTING.md",
            "it tells a newcomer how to set up, test and submit a change",
        ),
        (
            "T2-NO-COC",
            ["CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md"],
            "CODE_OF_CONDUCT.md",
            "there are no org-level defaults — `ersilia-os/.github` holds only a LICENSE and a "
            "profile README, so nothing is inherited",
        ),
        (
            "T2-NO-ISSUE-TEMPLATE",
            [".github/ISSUE_TEMPLATE", ".github/ISSUE_TEMPLATE.md"],
            "issue template",
            "so bug reports arrive with the information you need",
        ),
        (
            "T2-NO-PR-TEMPLATE",
            [".github/PULL_REQUEST_TEMPLATE.md", ".github/pull_request_template.md"],
            "pull-request template",
            "so PRs state what changed and how it was verified",
        ),
        (
            "T2-NO-DEPENDABOT",
            [".github/dependabot.yml", ".github/dependabot.yaml"],
            "dependabot config",
            "to get dependency and action updates proposed automatically",
        ),
        (
            "T2-NO-CITATION",
            ["CITATION.cff", "CITATION.bib"],
            "CITATION.cff",
            "so the work can be cited correctly",
        ),
        (
            "T2-NO-CHANGELOG",
            ["CHANGELOG.md", "CHANGES.md", "HISTORY.md"],
            "CHANGELOG.md",
            "so consumers can see what changed between releases",
        ),
        (
            "T2-NO-DOCS-DIR",
            ["docs"],
            "docs/ directory",
            "to hold the long-form content the README should not carry",
        ),
    ]
    for check_id, candidates, what, why in wants:
        fires, why_not = gated.get(check_id, (True, ""))
        if not fires:
            skips.append(skipped(check_id, why_not))
            continue
        if any((repo / c).exists() for c in candidates):
            continue
        findings.append(
            finding(
                check_id,
                "T2",
                "Nice-to-have",
                f"There is no {what}.",
                f"Add one — {why}.",
            )
        )

    readme = read_text(repo / "README.md")
    if readme:
        head = "\n".join(readme.splitlines()[:15])
        if not re.search(r"!\[[^\]]*\]\(|<img", head):
            findings.append(
                finding(
                    "T2-NO-BANNER",
                    "T2",
                    "Nice-to-have",
                    "The README has no banner logo or badge row under the title.",
                    "Add one. `ersilia-pack` has the best-structured example: a centred logo "
                    "plus badges plus inline nav links.",
                    file="README.md",
                )
            )
        lines = len([ln for ln in readme.splitlines() if ln.strip()])
        if lines > 120 and not re.search(
            r"(?i)^#+\s*(table of contents|contents)\b", readme, re.MULTILINE
        ):
            findings.append(
                finding(
                    "T2-NO-TOC",
                    "T2",
                    "Nice-to-have",
                    f"The README is {lines} lines with no table of contents.",
                    "Add one, or better, move content into `docs/` until it does not need one.",
                    file="README.md",
                )
            )


def main() -> int:
    """Run the GitHub-side checks and write the findings document."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default="/tmp/repo_audit_target.json")
    ap.add_argument("--type", default="Package")
    ap.add_argument(
        "--status", default="", help="comma-separated Airtable Status values"
    )
    ap.add_argument(
        "--backs-paper",
        action="store_true",
        help="the repo is linked to a Publications record in Airtable. Supplied by the LLM "
        "in Step 2 since Python cannot reach the MCP; enables the CITATION.cff check.",
    )
    ap.add_argument("--out", default="/tmp/repo_audit_meta.json")
    args = ap.parse_args()

    target = load_target(args.target)
    repo = Path(target["path"])
    rtype = args.type or "Package"
    status = [s.strip() for s in args.status.split(",") if s.strip()]
    gh = target.get("github") or {}

    findings: list[dict] = []
    skips: list[dict] = []

    check_repo_name(target["name"], findings)
    check_github_metadata(gh, findings, skips)
    check_ci(repo, rtype, findings, skips)
    if rtype in ("Automation", "App"):
        check_workflow_hygiene(repo, rtype, findings, skips)
    else:
        for cid in ("AUT-WORKFLOW-UNDOCUMENTED", "AUT-SCHEDULE-UNDOCUMENTED"):
            skips.append(skipped(cid, f"not an Automation repo (type={rtype})"))
    check_app(repo, rtype, findings, skips)
    check_releases(
        repo,
        target.get("owner") or "ersilia-os",
        target["name"],
        rtype,
        status,
        findings,
        skips,
    )
    check_tier2(repo, findings, skips, gh, backs_paper=args.backs_paper)

    emit(args.out, findings, skips, type=rtype)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
