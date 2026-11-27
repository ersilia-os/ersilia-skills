"""Check the Ersilia Book and repo READMEs against the live code and org.

Deterministic checks only; the judgement pass is done by the agent (see SKILL.md).
Reads `fetch_sources.py` output and writes findings (no IDs yet; `render_report.py`
numbers them).

Checks (details and severities in `references/checks.md`):
- `cli-command`, `cli-flag`: `ersilia ...` commands in code that the CLI no longer has.
- `repo-missing`, `repo-renamed`, `repo-archived`: links to `github.com/ersilia-os/<repo>`.
- `repo-file-missing`, `repo-branch-missing`: `/blob/` and `/tree/` links whose file or
  branch is gone.
- `python-version`: `conda create ... python=X.Y` outside the package's `requires-python`.
- Book only: `summary-missing`, `orphan-page`, `hidden-in-summary`, `broken-placeholder`,
  `relative-link`.
- `external-link` (opt-in, `--check-external`): other URLs answering 404/410 or not resolving.

Read-only, apart from GitHub API reads. Exit codes: 0 on success, 2 on bad input.

Usage:
    python check_drift.py --sources /tmp/docs-drift/sources.json --out /tmp/docs-drift/findings.json
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import shlex
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from _common import ORG, read_json, run_gh_json, write_json

SEVERITY = {
    "cli-command": "high",
    "cli-flag": "high",
    "repo-missing": "high",
    "repo-file-missing": "high",
    "summary-missing": "high",
    "broken-placeholder": "high",
    "relative-link": "high",
    "repo-branch-missing": "medium",
    "python-version": "medium",
    "orphan-page": "medium",
    "hidden-in-summary": "medium",
    "external-link": "medium",
    "repo-archived": "low",
    "repo-renamed": "low",
}

REPO_LINK = re.compile(
    r"github\.com/ersilia-os/([A-Za-z0-9_.-]+)"
    r"(?:/(blob|tree)/([^\s)\"'<>`\]]+))?"
)
MD_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_REF = re.compile(r"""(?:src|href|url)=["']([^"']+)["']""")
URL = re.compile(r"https?://[^\s)\"'<>`\]]+")
INLINE_CODE = re.compile(r"`([^`]+)`")
CONDA_CREATE = re.compile(
    r"conda create\b[^`\n]*?-n\s+([A-Za-z0-9_.-]+)[^`\n]*?python=(3\.\d+)"
)
FENCE = re.compile(r"^\s*(```|~~~)")
# Template examples, not real repos: eosXabc, my-ersilia-python-package, your-repo.
PLACEHOLDER_REPO = re.compile(
    r"^(eos[0-9a-z]*X|my[-_]|your[-_]|example)", re.IGNORECASE
)
BROKEN = re.compile(r"\[([^\]]*)\]\(/broken/pages/[^)]*\)")
SUMMARY_ENTRY = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)\)")


# ---------------------------------------------------------------- helpers


def finding(src: dict, line: int, check: str, claim: str, evidence: str, fix: str):
    return {
        "source": src["source"],
        "repo": src["repo"],
        "path": src["path"],
        "page": src.get("page") or src["path"],
        "line": line,
        "check": check,
        "severity": SEVERITY[check],
        "claim": claim.strip()[:200],
        "evidence": evidence,
        "suggestion": fix,
    }


def code_snippets(text: str):
    """Yield (line_no, snippet) for fenced code lines and inline code spans."""
    fenced = False
    for no, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            yield no, line
        else:
            for m in INLINE_CODE.finditer(line):
                yield no, m.group(1)


def norm_opt(opt: str) -> str:
    """Click here treats `-` and `_` alike after the leading dashes."""
    opt = opt.split("=", 1)[0]
    body = opt.lstrip("-")
    return opt[: len(opt) - len(body)] + body.replace("-", "_")


def is_placeholder(tok: str) -> bool:
    return tok.startswith(("<", "[", "{", "$")) or tok.isupper() or tok == "..."


# ---------------------------------------------------------------- CLI


def check_cli(src: dict, text: str, cli: dict, out: list) -> None:
    commands = cli["commands"]
    known = {c: {norm_opt(o) for o in opts} for c, opts in commands.items()}
    global_flags = {norm_opt(o) for o in cli["global_flags"]}
    for no, snippet in code_snippets(text):
        for part in re.split(r"&&|\|\||;|\|", snippet):
            part = re.sub(r"^\s*(\$|>|#)?\s*", "", part).strip()
            if not re.match(r"ersilia(\s|$)", part):
                continue
            try:
                toks = shlex.split(part, comments=True)
            except ValueError:
                toks = part.split()
            i = 1
            while i < len(toks) and toks[i].startswith("-"):
                if norm_opt(toks[i]) not in global_flags:
                    out.append(
                        finding(
                            src,
                            no,
                            "cli-flag",
                            part,
                            f"`ersilia` has no global option `{toks[i]}`",
                            "Use a current option (see `ersilia --help`).",
                        )
                    )
                i += 1
            if i >= len(toks) or is_placeholder(toks[i]):
                continue
            cmd = toks[i]
            if not re.fullmatch(r"[a-z][a-z_-]*", cmd):
                continue
            if cmd not in known:
                out.append(
                    finding(
                        src,
                        no,
                        "cli-command",
                        part,
                        f"`ersilia {cmd}` is not a command; current commands: "
                        + ", ".join(sorted(known)),
                        "Replace with the current command or remove the line.",
                    )
                )
                continue
            for tok in toks[i + 1 :]:
                if not tok.startswith("-") or tok in ("-", "--"):
                    continue
                if norm_opt(tok) not in known[cmd]:
                    out.append(
                        finding(
                            src,
                            no,
                            "cli-flag",
                            part,
                            f"`ersilia {cmd}` has no option `{tok}`; it has "
                            + ", ".join(o for o in commands[cmd] if o.startswith("--")),
                            "Use a current option or remove it.",
                        )
                    )


# ---------------------------------------------------------------- repo links


class RepoResolver:
    """Answers questions about org repos, caching every API call."""

    def __init__(self, repos: dict):
        self.repos = repos
        self.lower = {n.lower(): n for n in repos}
        self.cache: dict = {}

    def canonical(self, name: str) -> tuple[str | None, str]:
        """(current name or None, how): how is 'ok', 'renamed' or 'missing'."""
        if name.lower() in self.lower:
            return self.lower[name.lower()], "ok"
        key = ("repo", name.lower())
        if key not in self.cache:
            data, _ = run_gh_json(["api", f"repos/{ORG}/{name}", "--jq", "{name}"])
            new = data.get("name") if isinstance(data, dict) else None
            self.cache[key] = (new, "renamed") if new else (None, "missing")
        return self.cache[key]

    def path_state(self, repo: str, ref: str, path: str) -> str:
        """'ok', 'file-missing' or 'branch-missing' for a blob/tree link."""
        key = ("path", repo, ref, path)
        if key in self.cache:
            return self.cache[key]
        q = urllib.parse.quote(path)
        data, err = run_gh_json(
            ["api", f"repos/{ORG}/{repo}/contents/{q}?ref={ref}", "--jq", "{x: 1}"]
        )
        if data is not None:
            state = "ok"
        elif "404" not in err and "Not Found" not in err:
            state = "ok"  # rate limit or network: do not guess
        else:
            ok, _ = run_gh_json(
                ["api", f"repos/{ORG}/{repo}/branches/{ref}", "--jq", "{x: 1}"]
            )
            commit, _ = run_gh_json(
                ["api", f"repos/{ORG}/{repo}/commits/{ref}", "--jq", "{x: 1}"]
            )
            state = "file-missing" if (ok or commit) else "branch-missing"
        self.cache[key] = state
        return state


def check_repo_links(
    src: dict, text: str, resolver: RepoResolver, out: list, deep: bool
) -> None:
    seen: set = set()
    for no, line in enumerate(text.splitlines(), 1):
        for m in REPO_LINK.finditer(line):
            raw = m.group(1)
            name = re.sub(r"\.git$", "", raw.rstrip(".,;:"))
            if not name or name == ".github" or PLACEHOLDER_REPO.search(name):
                continue
            if (no, name) in seen:
                continue
            seen.add((no, name))
            current, how = resolver.canonical(name)
            url = f"github.com/{ORG}/{name}"
            if how == "missing":
                out.append(
                    finding(
                        src,
                        no,
                        "repo-missing",
                        url,
                        f"`{ORG}/{name}` does not exist (deleted, or private)",
                        "Remove the link or point it to the repo that replaced it.",
                    )
                )
                continue
            if how == "renamed":
                out.append(
                    finding(
                        src,
                        no,
                        "repo-renamed",
                        url,
                        f"`{name}` was renamed to `{current}` (the link still redirects)",
                        f"Link to `{ORG}/{current}`.",
                    )
                )
            elif resolver.repos[current]["archived"]:
                out.append(
                    finding(
                        src,
                        no,
                        "repo-archived",
                        url,
                        f"`{current}` is archived",
                        "Check the text still makes sense for an archived repo; "
                        "say it is archived, or link its replacement.",
                    )
                )
            if not deep or not m.group(2):
                continue
            rest = m.group(3).split("#")[0].split("?")[0].rstrip(".,;:")
            ref, _, path = rest.partition("/")
            if not path:
                continue
            state = resolver.path_state(current, ref, urllib.parse.unquote(path))
            if state == "file-missing":
                out.append(
                    finding(
                        src,
                        no,
                        "repo-file-missing",
                        f"{url}/{m.group(2)}/{rest}",
                        f"`{path}` no longer exists on `{ref}` in `{current}`",
                        "Point the link to the file's new location, or remove it.",
                    )
                )
            elif state == "branch-missing":
                out.append(
                    finding(
                        src,
                        no,
                        "repo-branch-missing",
                        f"{url}/{m.group(2)}/{rest}",
                        f"`{current}` has no branch or commit `{ref.split('/')[0]}`",
                        "Link to the default branch (or a tag) instead.",
                    )
                )


# ---------------------------------------------------------------- python version


def _ver(s: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", s)[:2])


def satisfies(version: str, spec: str) -> bool | None:
    """Whether X.Y meets a requires-python spec; None if the spec is not understood."""
    v = _ver(version)
    ok = True
    for clause in spec.split(","):
        clause = clause.strip()
        m = re.fullmatch(r"(>=|<=|==|!=|~=|>|<|\^)?\s*(\d+(?:\.\d+)*)(?:\.\*)?", clause)
        if not m:
            return None
        op, ref = m.group(1) or "==", _ver(m.group(2))
        ref = ref + (0,) * (2 - len(ref))
        if op == "^":
            ok &= v >= ref and v[0] == ref[0]
        elif op in ("~=", ">="):
            ok &= v >= ref
        elif op == ">":
            ok &= v > ref
        elif op == "<=":
            ok &= v <= ref
        elif op == "<":
            ok &= v < ref
        elif op == "==":
            ok &= v[: len(ref)] == ref
        elif op == "!=":
            ok &= v != ref
    return ok


def _norm(name: str) -> str:
    return name.lower().replace("_", "-")


def check_python(src: dict, text: str, pyprojects: dict, out: list) -> None:
    for no, line in enumerate(text.splitlines(), 1):
        for m in CONDA_CREATE.finditer(line):
            env, version = m.group(1), m.group(2)
            # The env must be the package's own: same name as the repo or package.
            # Other envs (e.g. a separate `tmap-env`) have their own requirements.
            repo = env
            if src["source"] == "readme":
                own = pyprojects.get(src["repo"]) or {}
                names = {src["repo"], own.get("package") or ""}
                if _norm(env) not in {_norm(n) for n in names if n}:
                    continue
                repo = src["repo"]
            spec = (pyprojects.get(repo) or {}).get("requires_python")
            if not spec or satisfies(version, spec) is not False:
                continue
            out.append(
                finding(
                    src,
                    no,
                    "python-version",
                    m.group(0),
                    f"`{repo}` requires Python `{spec}` (pyproject.toml)",
                    "Use a Python version inside that range.",
                )
            )


# ---------------------------------------------------------------- Book structure


def frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    block = text[3:end] if end > 0 else ""
    pairs = (ln.partition(":") for ln in block.splitlines())
    return {k.strip(): v.strip() for k, _, v in pairs if k.strip()}


def check_book_structure(book: Path, pages: dict, out: list) -> dict[str, str]:
    """Structure checks; returns {page path: sidebar title}."""
    summary = (book / "SUMMARY.md").read_text(encoding="utf-8")
    titles: dict[str, str] = {}
    src = {"source": "book", "repo": "ersilia-book", "path": "book/SUMMARY.md"}
    for no, line in enumerate(summary.splitlines(), 1):
        for title, target in SUMMARY_ENTRY.findall(line):
            target = urllib.parse.unquote(target)
            titles[target] = title
            if not (book / target).exists():
                out.append(
                    finding(
                        src,
                        no,
                        "summary-missing",
                        f"[{title}]({target})",
                        f"`book/{target}` does not exist",
                        "Fix the path in SUMMARY.md or remove the entry.",
                    )
                )
            elif frontmatter(pages.get(target, "")).get("hidden") == "true":
                out.append(
                    finding(
                        src,
                        no,
                        "hidden-in-summary",
                        f"[{title}]({target})",
                        "the page has `hidden: true` but is listed in the sidebar",
                        "Remove it from SUMMARY.md or drop `hidden: true`.",
                    )
                )
    for rel, text in pages.items():
        if rel in titles or rel == "README.md":
            continue
        if frontmatter(text).get("hidden") == "true":
            continue
        out.append(
            finding(
                {"source": "book", "repo": "ersilia-book", "path": f"book/{rel}"},
                1,
                "orphan-page",
                rel,
                "the page is not in SUMMARY.md, so readers cannot reach it",
                "Add it to SUMMARY.md, mark it `hidden: true`, or delete it.",
            )
        )
    return titles


def check_book_links(book: Path, rel: str, text: str, src: dict, out: list) -> None:
    here = (book / rel).parent
    fenced = False
    for no, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        for m in BROKEN.finditer(line):
            out.append(
                finding(
                    src,
                    no,
                    "broken-placeholder",
                    m.group(0)[:120],
                    "GitBook left a `/broken/pages/...` link: its target was deleted",
                    f"Link “{m.group(1)}” to the page that replaced it, or remove it.",
                )
            )
        if fenced:
            continue
        # Code spans hold SMILES such as `[N+](=O)`, which look like links.
        prose = INLINE_CODE.sub("", line)
        targets = MD_LINK.findall(prose) + HTML_REF.findall(prose)
        for t in targets:
            if re.match(r"^(https?:|mailto:|#|/|tel:)", t) or "{{" in t:
                continue
            path = urllib.parse.unquote(t.split("#")[0].split("?")[0])
            if path and not (here / path).exists():
                out.append(
                    finding(
                        src,
                        no,
                        "relative-link",
                        t,
                        f"`{path}` does not exist relative to `book/{rel}`",
                        "Fix the path (the target was probably moved or renamed).",
                    )
                )


# ---------------------------------------------------------------- external links


# Org repos are checked by check_repo_links; the rest are examples, not real links.
SKIP_URL = re.compile(
    r"github\.com/ersilia-os/|localhost|127\.0\.0\.1|://(my|your)[-_.]|"
    r"github\.com/(user|username|org|owner|your[-_]?\w*)/|example\.(com|org)"
)


def clean_url(u: str) -> str:
    """Undo Markdown escapes and drop trailing punctuation or pip's `.git@<ref>`."""
    u = u.replace("\\", "")
    u = re.sub(r"\.git@\S*$", ".git", u)
    return u.rstrip(".,;:*_}'")


def url_state(url: str) -> str | None:
    """None if fine (or unknown), else a short reason."""
    headers = {"User-Agent": "Mozilla/5.0 (docs link check)"}
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15):
                return None
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                if method == "GET":
                    return f"HTTP {e.code}"
                continue
            if method == "GET" or e.code not in (403, 405, 501):
                return None  # 403/429/5xx: not proof the page is gone
        except urllib.error.URLError as e:
            reason = str(e.reason)
            if "Name or service not known" in reason or "nodename" in reason:
                return "domain does not resolve"
            return None
        except (OSError, ValueError, http.client.HTTPException):
            return None  # reset, TLS or timeout: unknown, not gone
    return None


def check_external(docs: list[tuple[dict, str]], out: list) -> None:
    where: dict[str, list] = {}
    for src, text in docs:
        for no, line in enumerate(text.splitlines(), 1):
            for u in URL.findall(line):
                u = clean_url(u)
                if not u or SKIP_URL.search(u):
                    continue
                where.setdefault(u, []).append((src, no))
    with ThreadPoolExecutor(max_workers=8) as pool:
        states = dict(zip(where, pool.map(url_state, where)))
    for u, state in states.items():
        if state:
            for src, no in where[u]:
                out.append(
                    finding(
                        src,
                        no,
                        "external-link",
                        u,
                        state,
                        "Update or remove the link.",
                    )
                )


# ---------------------------------------------------------------- main


def fold_orphans(findings: list[dict]) -> list[dict]:
    """Readers cannot reach an orphan page, so its other findings become one note."""
    orphans = {f["path"]: f for f in findings if f["check"] == "orphan-page"}
    kept = []
    for f in findings:
        o = orphans.get(f["path"])
        if o is not None and f is not o:
            o.setdefault("folded", []).append(
                f"{f['check']} (line {f['line']}): {f['claim']}"
            )
            continue
        kept.append(f)
    for o in orphans.values():
        if o.get("folded"):
            o["evidence"] += (
                f"; it also has {len(o['folded'])} other problem(s), listed below"
            )
    return kept


def dedupe(findings: list[dict]) -> list[dict]:
    """One finding per (page, check, claim); later lines are listed, not repeated."""
    merged: dict[tuple, dict] = {}
    for f in findings:
        key = (f["repo"], f["path"], f["check"], f["claim"], f["evidence"])
        if key in merged:
            first = merged[key]
            extra = first.setdefault("more_lines", [])
            if f["line"] != first["line"] and f["line"] not in extra:
                extra.append(f["line"])
        else:
            merged[key] = f
    return sorted(
        merged.values(), key=lambda f: (f["source"], f["repo"], f["path"], f["line"])
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sources", default="/tmp/docs-drift/sources.json")
    p.add_argument("--out", default=None)
    p.add_argument("--only", choices=["book", "readmes"], default=None)
    p.add_argument(
        "--check-external", action="store_true", help="also test other URLs (slow)"
    )
    p.add_argument(
        "--no-deep-links",
        action="store_true",
        help="skip /blob/ and /tree/ path checks (fewer API calls)",
    )
    args = p.parse_args(argv)

    s = read_json(args.sources)
    if not isinstance(s, dict) or "cli" not in s:
        print(f"ERROR: {args.sources} is not fetch_sources.py output", file=sys.stderr)
        return 2
    out_path = args.out or str(Path(s["workdir"]) / "findings.json")
    resolver = RepoResolver(s["repos"])
    findings: list[dict] = []
    docs: list[tuple[dict, str]] = []

    if args.only != "readmes":
        book = Path(s["book_dir"]) / "book"
        pages = {
            str(f.relative_to(book)): f.read_text(encoding="utf-8")
            for f in sorted(book.rglob("*.md"))
            if ".gitbook" not in f.parts and f.name != "SUMMARY.md"
        }
        titles = check_book_structure(book, pages, findings)
        for rel, text in pages.items():
            src = {
                "source": "book",
                "repo": "ersilia-book",
                "path": f"book/{rel}",
                "page": titles.get(rel, rel),
            }
            docs.append((src, text))
            check_book_links(book, rel, text, src, findings)

    if args.only != "book":
        for repo, text in sorted(s["readmes"].items()):
            if repo == "ersilia-book":
                continue
            docs.append(({"source": "readme", "repo": repo, "path": "README.md"}, text))

    for src, text in docs:
        check_cli(src, text, s["cli"], findings)
        check_repo_links(src, text, resolver, findings, deep=not args.no_deep_links)
        check_python(src, text, s["pyprojects"], findings)
    if args.check_external:
        check_external(docs, findings)

    findings = fold_orphans(dedupe(findings))
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["check"]] = counts.get(f["check"], 0) + 1
    write_json(
        out_path,
        {
            "sources_fetched_at": s["fetched_at"],
            "checked": {
                "book_pages": sum(1 for d, _ in docs if d["source"] == "book"),
                "readmes": sum(1 for d, _ in docs if d["source"] == "readme"),
                "external_links": args.check_external,
            },
            "counts": counts,
            "findings": findings,
        },
    )
    print(
        json.dumps(
            {"findings": len(findings), "by_check": counts, "out": out_path}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
