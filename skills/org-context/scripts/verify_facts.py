"""Check what the CLAUDE.md files claim against live sources. Read-only.

- Skills named as `/skill-name` or "the `skill-name` skill" must exist in this
  ersilia-skills checkout.
- ersilia-os repositories, linked or named in backticks, must exist and not be archived.
- A link whose text names a repository must point at that repository, not the org root.
- Every other URL must answer (HTTP status below 400).

Writes ``facts.json`` in the same finding format as ``check_claude_md.py``.

Usage:
    python verify_facts.py [--work /tmp/org_context] [--offline] [--repos-json path]
        [--skills-dir path]

``--offline`` skips URL requests; ``--repos-json`` supplies ``{"name": archived}`` instead
of asking GitHub (both used by selftest.py).
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from _common import (
    LINK_RE,
    REFS,
    REPO_ROOT,
    URL_RE,
    WORK_DIR,
    die,
    load_work,
    prose_lines,
    read_json,
    run_gh,
    write_json,
)
from check_claude_md import Findings

SKILL_REF_RES = (
    re.compile(r"`/([a-z][a-z0-9-]+)`"),
    re.compile(r"`([a-z][a-z0-9-]+)`\s+skill\b"),
)
CODE_SPAN_RE = re.compile(r"`([^`]+)`")


def org_repos(org: str) -> dict[str, bool]:
    """Return {repo name: archived} for every repository in ``org``."""
    out, err = run_gh(
        [
            "api",
            "--paginate",
            f"orgs/{org}/repos?per_page=100",
            "--jq",
            '.[] | "\\(.name)\\t\\(.archived)"',
        ]
    )
    if out is None:
        die(f"could not list {org} repositories: {err}")
    repos = {}
    for row in out.splitlines():
        name, archived = row.split("\t")
        repos[name] = archived == "true"
    return repos


def url_status(url: str, timeout: int) -> str | int:
    """Return the HTTP status of ``url``, or an error string."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (ersilia-skills)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return str(getattr(exc, "reason", exc))


def template_reality(repo: str, config_files: list[str]) -> dict:
    """The default-branch file tree of ``repo`` and the text of its config files."""
    out, err = run_gh(
        ["api", f"repos/{repo}/git/trees/HEAD?recursive=1", "--jq", ".tree[].path"]
    )
    if out is None:
        die(f"could not list {repo}: {err}")
    tree = out.split()
    files = {}
    for name in config_files:
        if name in tree:
            body, _ = run_gh(
                [
                    "api",
                    f"repos/{repo}/contents/{name}",
                    "-H",
                    "Accept: application/vnd.github.raw",
                ]
            )
            files[name] = body or ""
    return {"tree": tree, "files": files}


def check_reality(f, t: dict, text: str, real: dict, rule: dict) -> None:
    """Paths and tools a template's CLAUDE.md names must exist in that template."""
    tree = real["tree"]
    path_re, skip = (
        re.compile(rule["path_pattern"]),
        re.compile(rule["skip_line"], re.I),
    )
    missing = []
    skip_span = re.compile(rule["skip_span"])
    for n, line in prose_lines(text):
        if skip.search(line):
            continue
        # A path inside a link label names a file in the linked repository, not here.
        line = LINK_RE.sub("", line)
        for span in CODE_SPAN_RE.findall(line):
            if skip_span.search(span):
                continue
            path = span.strip().rstrip("/")
            if not path_re.match(path) or path.startswith(("http", "~", "/", "$")):
                continue
            if any(p == path or p.endswith("/" + path) for p in tree):
                continue
            missing.append((n, path))
    if missing:
        f.add(
            t["id"],
            "REALITY-PATH",
            "consider",
            missing[0][0],
            f"{len({p for _, p in missing})} path(s) named but not in {t['repo']}: "
            + ", ".join(sorted({p for _, p in missing})),
            "Either the template should ship them, or the file should say when they are "
            "created.",
        )
    declared = "\n".join(real["files"].values()).lower()
    for tool in rule["tools"].get(t["role"], []):
        if re.search(rf"\b{re.escape(tool)}\b", text, re.I) and tool not in declared:
            f.add(
                t["id"],
                "REALITY-TOOL",
                "consider",
                None,
                f"'{tool}' is required by the file but not declared in "
                + (
                    ", ".join(real["files"])
                    or "any of " + ", ".join(rule["config_files"])
                ),
                "Declare it so a fresh repo built from the template already has it.",
            )


def main(argv: list[str] | None = None) -> int:
    """Verify skills, repositories and URLs; write facts.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--rules", default=str(REFS / "rules.json"))
    p.add_argument("--offline", action="store_true")
    p.add_argument("--repos-json")
    p.add_argument("--skills-dir", default=str(REPO_ROOT / "skills"))
    p.add_argument(
        "--reality-json", help="{target id: {tree, files}} instead of GitHub"
    )
    args = p.parse_args(argv)
    rules = read_json(args.rules)["facts"]
    targets, texts = load_work(args.work)

    skills = {d.name for d in Path(args.skills_dir).iterdir() if d.is_dir()}
    repos = read_json(args.repos_json) if args.repos_json else org_repos(rules["org"])
    repo_like = re.compile(rules["repo_like"])
    org_root = re.compile(rf"^https?://github\.com/{rules['org']}/?$")
    repo_url = re.compile(rf"github\.com/{rules['org']}/([A-Za-z0-9._-]+)")

    f = Findings()
    urls: dict[str, list[tuple[str, int]]] = {}
    for t in targets:
        tid, seen = t["id"], set()
        for n, line in prose_lines(texts[t["id"]]):
            for rx in SKILL_REF_RES:
                for name in rx.findall(line):
                    if name not in skills and ("skill", name) not in seen:
                        seen.add(("skill", name))
                        f.add(
                            tid,
                            "FACT-SKILL",
                            "fix",
                            n,
                            f"Skill '{name}' does not exist in ersilia-skills",
                        )

            # A sentence can end right after a URL: drop a trailing period first.
            names = {m.rstrip(".").removesuffix(".git") for m in repo_url.findall(line)}
            names |= {
                c
                for c in CODE_SPAN_RE.findall(line)
                if repo_like.match(c) and "/" not in c
            }
            names -= set(rules["not_repos"])
            for name in sorted(names):
                if ("repo", name) in seen:
                    continue
                if name not in repos:
                    seen.add(("repo", name))
                    f.add(
                        tid,
                        "FACT-REPO",
                        "fix",
                        n,
                        f"Repository '{name}' does not exist in {rules['org']}",
                    )
                elif repos[name]:
                    seen.add(("repo", name))
                    f.add(
                        tid,
                        "FACT-ARCHIVED",
                        "fix",
                        n,
                        f"Repository '{name}' is archived",
                    )

            for text, url in LINK_RE.findall(line):
                label = text.strip("` ")
                if org_root.match(url) and label in repos:
                    f.add(
                        tid,
                        "FACT-ORG-LINK",
                        "fix",
                        n,
                        f"Link '{label}' points at the org page, not the repository",
                        f"Use https://github.com/{rules['org']}/{label}.",
                    )

            for url in URL_RE.findall(line):
                url = url.rstrip(".,;:")
                host = urlsplit(url).netloc
                if host in rules["skip_url_hosts"] or repo_url.search(url):
                    continue
                urls.setdefault(url, []).append((tid, n))

    reality = read_json(args.reality_json) if args.reality_json else {}
    full_rules = read_json(args.rules)
    for t in targets:
        if t["role"] not in full_rules["reality"]["roles"]:
            continue
        if t["id"] not in reality:
            if args.offline:
                continue
            reality[t["id"]] = template_reality(
                t["repo"], full_rules["reality"]["config_files"]
            )
        check_reality(f, t, texts[t["id"]], reality[t["id"]], full_rules["reality"])

    if not args.offline:
        for url, places in sorted(urls.items()):
            status = url_status(url, rules["url_timeout"])
            if isinstance(status, int) and status < 400:
                continue
            for tid, n in places:
                f.add(
                    tid,
                    "FACT-URL",
                    "fix" if isinstance(status, int) else "consider",
                    n,
                    f"{url} answers {status}",
                    ""
                    if isinstance(status, int)
                    else "Could not connect; check by hand.",
                )

    write_json(Path(args.work) / "facts.json", f.items)
    checked = "offline" if args.offline else f"{len(urls)} URLs"
    print(
        f"verified {len(skills)} skills, {len(repos)} repos, {checked}: "
        f"{len(f.items)} finding(s)"
    )
    for i in f.items:
        print(f"  {i['key']} line {i['line']}: {i['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
