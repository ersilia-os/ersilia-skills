#!/usr/bin/env python3
"""Bad practices, modularity and general messiness.

The checks here answer the questions a reviewer asks that no linter covers: does this feel
messy, is it modular enough, are there habits that will bite someone later. All are AST- or
pattern-based and stdlib-only.

Several are deliberately blunt instruments with thresholds rather than judgement — a
600-line module is not automatically wrong, so they are reported with the number attached
and left for the reader to weigh. The `confidence` field marks the ones most likely to have
a defensible exception.

Exit codes
----------
0   ran to completion
2   bad usage or unreadable target

Usage
-----
    python check_practices.py --target /tmp/repo_audit_target.json \\
                              [--type Package] [--out /tmp/repo_audit_practices.json]
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

from _common import (
    emit,
    finding,
    load_target,
    plural,
    read_text,
    rollup,
    skipped,
    tracked_files,
    verb,
)

VENDOR_DIRS = re.compile(
    r"(^|/)(\.git|\.venv|venv|env|node_modules|build|dist|site-packages|"
    r"__pycache__|\.eggs|[^/]*\.egg-info|\.ruff_cache|\.mypy_cache|\.pytest_cache)(/|$)"
)
TEST_PATH = re.compile(r"(^|/)(tests?|test)(/|$)")
SCRIPT_PATH = re.compile(r"(^|/)(scripts?|bin|notebooks?)(/|$)")

# Thresholds. Chosen from the org's own code: ersilia's largest core module is ~900 lines
# and is genuinely doing too much; most well-factored modules there sit under 400.
GOD_MODULE_LINES = 600
LONG_FUNCTION_LINES = 80
DEEP_NESTING = 5
FLAT_NAMESPACE_LINES = 800
MAX_ROOT_FILES = 18
TODO_PER_KLOC = 4.0

# A hardcoded home directory is the one path issue that is always wrong: it cannot work on
# anyone else's machine, or in CI.
ABSOLUTE_PATH_RE = re.compile(
    r"[\"'](?:/Users/|/home/|C:\\\\Users\\\\|/Volumes/)[^\"'\n]{3,}[\"']"
)

# Roll-up of commented-out code: a run of consecutive comment lines that parse as Python.
COMMENTED_CODE_RUN = 4


def python_files(repo: Path, tracked: list[str]) -> list[str]:
    """Tracked `.py` paths that are the repo's own source."""
    return [r for r in tracked if r.endswith(".py") and not VENDOR_DIRS.search(r)]


def nesting_depth(node: ast.AST) -> int:
    """Maximum control-flow nesting depth inside a function body."""
    best = 0

    def walk(n: ast.AST, depth: int) -> None:
        nonlocal best
        best = max(best, depth)
        for child in ast.iter_child_nodes(n):
            if isinstance(
                child,
                (
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.With,
                    ast.AsyncWith,
                    ast.Try,
                ),
            ):
                walk(child, depth + 1)
            elif isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            else:
                walk(child, depth)

    walk(node, 0)
    return best


def looks_like_code(comment: str) -> bool:
    """True if a stripped comment body parses as a Python statement.

    Used to tell commented-out code from prose. Prose almost never parses; `x = foo(1)`
    and `return None` always do.
    """
    body = comment.lstrip("#").strip()
    if not body or len(body) < 4:
        return False
    if body[0].isupper() and " " in body and not re.search(r"[=(\[:]", body):
        return False  # reads like a sentence
    if not re.search(
        r"[=(\[]|^(return|import|from|if|for|while|def|class|print|pass|raise)\b", body
    ):
        return False
    try:
        ast.parse(body)
        return True
    except SyntaxError:
        return False


def check_bad_practices(repo: Path, pyfiles: list[str], findings: list) -> None:
    """Habits that will cost someone later: bare excepts, prints, absolute paths, shells."""
    bare_except: list[str] = []
    prints: dict[str, int] = {}
    abs_paths: list[str] = []
    shell_use: list[str] = []
    wildcard: list[str] = []
    mutable_default: list[str] = []
    commented_code: list[str] = []
    todos = 0
    total_lines = 0

    for rel in pyfiles:
        text = read_text(repo / rel)
        if not text:
            continue
        lines = text.splitlines()
        total_lines += len(lines)
        is_test = bool(TEST_PATH.search(rel))
        is_script = bool(SCRIPT_PATH.search(rel))

        todos += len(re.findall(r"#\s*(TODO|FIXME|HACK|XXX)\b", text))

        for m in ABSOLUTE_PATH_RE.finditer(text):
            abs_paths.append(
                f"{rel}:{text[: m.start()].count(chr(10)) + 1} {m.group(0)[:60]}"
            )

        for m in re.finditer(r"\bos\.system\s*\(|\bshell\s*=\s*True\b", text):
            shell_use.append(f"{rel}:{text[: m.start()].count(chr(10)) + 1}")

        # Commented-out code, in runs so a single explanatory line is not flagged.
        run = 0
        for i, line in enumerate(lines, start=1):
            s = line.strip()
            if s.startswith("#") and looks_like_code(s):
                run += 1
                if run == COMMENTED_CODE_RUN:
                    commented_code.append(f"{rel}:{i - run + 1}")
            else:
                run = 0

        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                bare_except.append(f"{rel}:{node.lineno}")
            elif isinstance(node, ast.Try):
                for h in node.handlers:
                    # `except Exception: pass` swallows everything just as effectively.
                    if (
                        isinstance(h.type, ast.Name)
                        and h.type.id in ("Exception", "BaseException")
                        and len(h.body) == 1
                        and isinstance(h.body[0], ast.Pass)
                    ):
                        bare_except.append(f"{rel}:{h.lineno}")
            elif isinstance(node, ast.ImportFrom) and any(
                a.name == "*" for a in node.names
            ):
                wildcard.append(
                    f"{rel}:{node.lineno} `from {node.module or '.'} import *`"
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defaults = list(node.args.defaults) + [
                    d for d in node.args.kw_defaults if d
                ]
                for d in defaults:
                    if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                        mutable_default.append(f"{rel}:{node.lineno} `{node.name}`")
                        break
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
                and not is_test
                and not is_script
            ):
                prints[rel] = prints.get(rel, 0) + 1

    if bare_except:
        findings.append(
            finding(
                "PKG-BARE-EXCEPT",
                "T1",
                "Should-fix",
                f"{plural(len(bare_except), 'bare or silently-swallowing `except` clause')}.",
                "Catch the specific exception. A bare `except:` also swallows "
                "`KeyboardInterrupt` and `SystemExit`; `except Exception: pass` hides the bug "
                "you will later need to find.",
                detail=rollup(bare_except),
            )
        )
    if abs_paths:
        findings.append(
            finding(
                "PKG-ABSOLUTE-PATH",
                "T1",
                "Blocker",
                f"{plural(len(abs_paths), 'hardcoded absolute path')} to a home or volume directory.",
                "Derive paths from `__file__` or a config value. These cannot work on anyone "
                "else's machine or in CI.",
                detail=rollup(abs_paths),
            )
        )
    if shell_use:
        findings.append(
            finding(
                "PKG-SHELL-INJECTION",
                "T1",
                "Should-fix",
                f"{plural(len(shell_use), 'use')} of `os.system` or `shell=True`.",
                "Use `subprocess.run([...])` with an argument list. With `shell=True`, any "
                "filename containing a space or a semicolon becomes a command.",
                detail=rollup(shell_use),
            )
        )
    if wildcard:
        findings.append(
            finding(
                "PKG-WILDCARD-IMPORT",
                "T1",
                "Should-fix",
                f"{plural(len(wildcard), 'wildcard import')}.",
                "Import the names you use. A wildcard makes it impossible to tell where a name "
                "came from, and defeats ruff's unused-import detection.",
                detail=rollup(wildcard),
            )
        )
    if mutable_default:
        findings.append(
            finding(
                "PKG-MUTABLE-DEFAULT",
                "T1",
                "Should-fix",
                f"{plural(len(mutable_default), 'function')} with a mutable default argument.",
                "Use `None` and build the container inside the function. A list or dict "
                "default is created once and shared across every call.",
                detail=rollup(mutable_default),
            )
        )
    if prints:
        total = sum(prints.values())
        findings.append(
            finding(
                "PKG-PRINT-IN-LIB",
                "T1",
                "Should-fix",
                f"{plural(total, '`print()` call')} in library code across "
                f"{plural(len(prints), 'module')}.",
                "Use the logger singleton so output can be silenced, redirected and levelled: "
                "`from <package>.utils.logging import logger`.",
                detail=rollup(
                    [
                        f"{k} ({v})"
                        for k, v in sorted(prints.items(), key=lambda x: -x[1])
                    ],
                    8,
                ),
            )
        )
    if commented_code:
        findings.append(
            finding(
                "PKG-COMMENTED-CODE",
                "T1",
                "Nice-to-have",
                f"{plural(len(commented_code), 'block')} of commented-out code "
                f"({COMMENTED_CODE_RUN}+ consecutive lines).",
                "Delete them — git remembers. Commented-out code goes stale silently and "
                "misleads the next reader.",
                detail=rollup(commented_code),
                confidence="medium",
            )
        )
    if total_lines and todos:
        per_kloc = todos * 1000.0 / total_lines
        if per_kloc > TODO_PER_KLOC:
            findings.append(
                finding(
                    "PKG-TODO-DENSITY",
                    "T1",
                    "Nice-to-have",
                    f"{plural(todos, 'TODO/FIXME/HACK comment')} — {per_kloc:.1f} per 1000 lines.",
                    "Move the real ones to GitHub issues and delete the rest. In-code TODOs are "
                    "invisible to everyone not reading that file.",
                )
            )


def check_modularity(repo: Path, pyfiles: list[str], findings: list) -> None:
    """God modules, long functions, deep nesting, flat namespaces."""
    god: list[str] = []
    long_fns: list[str] = []
    deep: list[str] = []
    total_lines = 0
    top_level_modules = 0

    for rel in pyfiles:
        text = read_text(repo / rel)
        if not text or TEST_PATH.search(rel):
            continue
        n_lines = len(text.splitlines())
        total_lines += n_lines
        if rel.count("/") <= 1:
            top_level_modules += 1
        if n_lines > GOD_MODULE_LINES:
            god.append(f"{rel} ({n_lines} lines)")

        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            end = getattr(node, "end_lineno", None)
            if end and end - node.lineno > LONG_FUNCTION_LINES:
                long_fns.append(
                    f"{rel}:{node.lineno} `{node.name}` ({end - node.lineno} lines)"
                )
            d = nesting_depth(node)
            if d >= DEEP_NESTING:
                deep.append(f"{rel}:{node.lineno} `{node.name}` (depth {d})")

    if god:
        findings.append(
            finding(
                "PKG-GOD-MODULE",
                "T1",
                "Should-fix",
                f"{plural(len(god), 'module')} {verb(len(god), 'exceeds', 'exceed')} "
                f"{GOD_MODULE_LINES} lines.",
                'Split them into submodules. The rule: "Favour submodules (`io/`, `utils/`, '
                '`cli/`, ...) instead of a single flat file."',
                detail=rollup(god),
                confidence="medium",
            )
        )
    if long_fns:
        findings.append(
            finding(
                "PKG-LONG-FUNCTION",
                "T1",
                "Should-fix",
                f"{plural(len(long_fns), 'function')} {verb(len(long_fns), 'exceeds', 'exceed')} "
                f"{LONG_FUNCTION_LINES} lines.",
                "Extract the steps into named helpers. A function that does not fit on a screen "
                "cannot be reviewed properly.",
                detail=rollup(long_fns),
                confidence="medium",
            )
        )
    if deep:
        findings.append(
            finding(
                "PKG-DEEP-NESTING",
                "T1",
                "Nice-to-have",
                f"{plural(len(deep), 'function')} {verb(len(deep), 'nests', 'nest')} control flow "
                f"{DEEP_NESTING} levels or deeper.",
                "Use early returns and guard clauses to flatten the body.",
                detail=rollup(deep),
                confidence="medium",
            )
        )

    # A large codebase living entirely in top-level modules has no structure at all.
    nested = len([r for r in pyfiles if r.count("/") > 1 and not TEST_PATH.search(r)])
    if total_lines > FLAT_NAMESPACE_LINES and nested == 0 and top_level_modules > 1:
        findings.append(
            finding(
                "PKG-FLAT-NAMESPACE",
                "T1",
                "Should-fix",
                f"{total_lines} lines across {plural(top_level_modules, 'module')} with no submodules.",
                'Group the code into submodules. The rule is explicit: "Avoid a flat namespace."',
            )
        )


def check_clutter(repo: Path, tracked: list[str], findings: list) -> None:
    """Root-level clutter and inconsistent file naming — the "does it feel messy" signals."""
    root_files = [r for r in tracked if "/" not in r and not r.startswith(".")]
    if len(root_files) > MAX_ROOT_FILES:
        findings.append(
            finding(
                "T0-ROOT-CLUTTER",
                "T0",
                "Should-fix",
                f"{len(root_files)} files sit at the repository root.",
                "Move code into a package or `src/`, docs into `docs/`, and scripts into "
                "`scripts/`. A crowded root is the first thing that makes a repo feel "
                "unmaintained.",
                detail=rollup(sorted(root_files), 12),
            )
        )

    # Mixed naming conventions across the Python sources of one repo.
    py = [
        Path(r).stem
        for r in tracked
        if r.endswith(".py")
        and not VENDOR_DIRS.search(r)
        and not Path(r).name.startswith("__")
    ]
    if len(py) >= 5:
        kebab = [n for n in py if "-" in n]
        camel = [n for n in py if re.search(r"[a-z][A-Z]", n)]
        offenders = kebab + camel
        if offenders:
            findings.append(
                finding(
                    "T0-NAMING-INCONSISTENT",
                    "T0",
                    "Nice-to-have",
                    f"{plural(len(offenders), 'Python file')} {verb(len(offenders))} not snake_case.",
                    "Rename to snake_case. A kebab-case module cannot even be imported.",
                    detail=rollup(offenders),
                )
            )


def check_eosvc(repo: Path, rtype: str, findings: list, skips: list) -> None:
    """Whether eosvc is used where it should be, and not where it should not.

    Three failure modes: data directories that exist but are neither gitignored nor
    declared; an `access.json` declaring directories that no longer exist; and a repo that
    clearly handles datasets but has no eosvc setup at all.
    """
    access = repo / "access.json"
    data_dirs = [
        d for d in ("data", "output", "outputs", "results") if (repo / d).is_dir()
    ]

    if not data_dirs and not access.is_file():
        skips.append(
            skipped("EOSVC-NOT-USED", "no data directories and no access.json")
        )
        return

    # A repo that reads or writes datasets but never set up eosvc.
    if data_dirs and not access.is_file():
        # Already reported as ANA-NO-ACCESS-JSON / PKG-NO-ACCESS-JSON by check_hygiene when
        # the directory is gitignored. This catches the other case: not even gitignored.
        skips.append(
            skipped(
                "EOSVC-NOT-USED", "access.json absence is reported by check_hygiene"
            )
        )
        return

    if access.is_file() and not data_dirs:
        findings.append(
            finding(
                "EOSVC-STALE-DECL",
                "T1",
                "Should-fix",
                "`access.json` exists but the repository has no data or output directory.",
                "Either create the directories eosvc is meant to back, or remove "
                "`access.json` — as it stands it describes storage that is not there.",
                file="access.json",
            )
        )


def main() -> int:
    """Run the practice, modularity and clutter checks."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default="/tmp/repo_audit_target.json")
    ap.add_argument("--type", default="Package")
    ap.add_argument(
        "--status",
        default="",
        help="comma-separated Airtable Status values; accepted for a uniform call shape "
        "across all checkers even where unused",
    )
    ap.add_argument("--out", default="/tmp/repo_audit_practices.json")
    args = ap.parse_args()

    target = load_target(args.target)
    repo = Path(target["path"])
    rtype = args.type or "Package"

    tracked = tracked_files(repo)
    pyfiles = python_files(repo, tracked)

    findings: list[dict] = []
    skips: list[dict] = []

    if pyfiles:
        check_bad_practices(repo, pyfiles, findings)
        # Workshop material is deliberately simple and linear; modularity rules would only
        # produce noise there.
        if rtype == "Workshop":
            for cid in ("PKG-GOD-MODULE", "PKG-LONG-FUNCTION", "PKG-FLAT-NAMESPACE"):
                skips.append(
                    skipped(cid, "Workshop repo — teaching code is linear by design")
                )
        else:
            check_modularity(repo, pyfiles, findings)
    else:
        for cid in (
            "PKG-BARE-EXCEPT",
            "PKG-PRINT-IN-LIB",
            "PKG-ABSOLUTE-PATH",
            "PKG-GOD-MODULE",
            "PKG-LONG-FUNCTION",
            "PKG-FLAT-NAMESPACE",
        ):
            skips.append(skipped(cid, "no tracked Python files"))

    check_clutter(repo, tracked, findings)
    check_eosvc(repo, rtype, findings, skips)

    emit(args.out, findings, skips, type=rtype, python_files=len(pyfiles))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
