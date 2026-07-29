#!/usr/bin/env python3
"""Code checks: ruff, docstrings, dead names, packaging, and per-type script rules.

Real tools first. `ruff` does the lint work — unused imports and variables, undefined
names, formatting, and (with the canonical config) the NumPy docstring convention. The
stdlib `ast` module covers what ruff cannot: docstring *section* structure, module-level
names that nothing references, and the Analysis-profile script conventions.

Where a tool is unavailable the check is recorded in `skipped` rather than passed over, so
the report can never imply a clean bill of health it did not verify.

Exit codes
----------
0   ran to completion
2   bad usage or unreadable target

Usage
-----
    python check_code.py --target /tmp/repo_audit_target.json \\
                         [--type Package] [--out /tmp/repo_audit_code.json]
                         [--no-ruff]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

from _common import (
    TomlError,
    emit,
    finding,
    is_template_repo,
    load_target,
    load_toml,
    plural,
    read_text,
    reference,
    rollup,
    run,
    skipped,
    tracked_files,
    verb,
    warn,
    which_ruff,
)

# --------------------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------------------

# Directories whose contents are not the repo's own source.
VENDOR_DIRS = re.compile(
    r"(^|/)(\.git|\.venv|venv|env|node_modules|build|dist|site-packages|"
    r"__pycache__|\.eggs|[^/]*\.egg-info|\.ruff_cache|\.mypy_cache|\.pytest_cache)(/|$)"
)

# ruff codes we surface individually, with the check id and severity each maps to.
RUFF_MAP = {
    "F401": ("PKG-UNUSED-IMPORT", "Blocker", "unused import"),
    "F811": ("PKG-UNUSED-IMPORT", "Blocker", "redefinition of unused name"),
    "F841": ("PKG-UNUSED-VAR", "Blocker", "assigned but never used"),
    "F821": ("PKG-UNDEFINED-NAME", "Blocker", "undefined name"),
    "E999": ("PKG-SYNTAX-ERROR", "Blocker", "syntax error"),
}

CANONICAL_RUFF_KEYS = {
    "line-length": 88,
    "indent-width": 4,
    "target-version": "py310",
}

COMPETING_LINTERS = {
    "black": ("[tool.black]", "pyproject.toml"),
    "flake8": (".flake8", "setup.cfg / tox.ini / .flake8"),
    "isort": ("[tool.isort]", "pyproject.toml"),
    "pylint": ("[tool.pylint", "pyproject.toml / .pylintrc"),
    "darglint": (".darglint", ".darglint"),
}

STOCHASTIC_MARKERS = (
    "train_test_split",
    "np.random",
    "numpy.random",
    "random.",
    ".sample(",
    ".shuffle(",
    "KFold",
    "StratifiedKFold",
    "RandomForest",
)
SEED_MARKERS = (
    "random_state",
    "RANDOM_SEED",
    "np.random.seed",
    "random.seed",
    "torch.manual_seed",
    "seed=",
)

PROVENANCE_SOURCES = (
    "chembl",
    "pubchem",
    "tdcommons",
    "pytdc",
    "zinc",
    "drugbank",
    "uniprot",
    "bindingdb",
)
PROVENANCE_MARKERS = re.compile(
    r"(?i)(version|release|snapshot|downloaded|accessed|retrieved|v?\d{2,}(?:\.\d+)?|\d{4}-\d{2}-\d{2})"
)

TEST_PATH_RE = re.compile(r"(^|/)(tests?|test)(/|$)")

SYSPATH_PREAMBLE = re.compile(
    r"sys\.path\.append\(\s*os\.path\.join\(\s*root\s*,\s*[\"']\.\.[\"']\s*,\s*[\"']src[\"']"
)

# Near-synonym → canonical verb, from `ersilia`'s eleven commands. Only words that mean the
# same thing as a canonical verb appear here; domain verbs with no canonical equivalent
# (`fit`, `build`, `train`, `embed`, `score`) are deliberately absent and never flagged.
# Full rationale in `references/canonical-cli.md`.
CANONICAL_VERB = {
    "download": "fetch",
    "get": "fetch",
    "pull": "fetch",
    "execute": "run",
    "predict": "run",
    "infer": "run",
    "apply": "run",
    "start": "serve",
    "up": "serve",
    "host": "serve",
    "remove": "delete",
    "rm": "delete",
    "del": "delete",
    "list": "catalog",
    "ls": "catalog",
    "index": "catalog",
    "browse": "catalog",
    "describe": "info",
    "show": "info",
    "about": "info",
    "card": "info",
    "check": "test",
    "validate": "test",
    "verify": "test",
    "sample": "example",
    "demo": "example",
}

# Long-option names for file I/O that fragment the vocabulary. Normalised to kebab before
# lookup, so `--out_file` and `--out-file` both match.
IO_MISNAMES = {
    "infile",
    "in",
    "in-file",
    "source",
    "from",
    "inputfile",
    "input-path",
    "in-path",
    "outfile",
    "out",
    "out-file",
    "dest",
    "destination",
    "target",
    "result",
    "results",
    "output-file",
    "output-path",
    "out-path",
    "savepath",
    "save-path",
}

# Import name -> distribution name, for the cases where they differ. Covers the scientific
# Python stack Ersilia actually uses; anything not here is assumed to match its import name
# and reported at medium confidence.
IMPORT_TO_DIST = {
    "sklearn": "scikit-learn",
    "skimage": "scikit-image",
    "cv2": "opencv-python",
    "PIL": "pillow",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "dateutil": "python-dateutil",
    "dotenv": "python-dotenv",
    "rdkit": "rdkit-pypi",
    "Bio": "biopython",
    "tables": "pytables",
    "OpenSSL": "pyopenssl",
    "jwt": "pyjwt",
    "attr": "attrs",
    "pkg_resources": "setuptools",
    "google": "google-api-python-client",
    "tdc": "pytdc",
    "torch": "torch",
    "torch_geometric": "torch-geometric",
    "matplotlib": "matplotlib",
    "mpl_toolkits": "matplotlib",
    "griddata": "scipy",
    "usearch": "usearch",
    "FPSim2": "fpsim2",
    "h5py": "h5py",
    "serial": "pyserial",
    "zmq": "pyzmq",
    "docker": "docker",
    "git": "gitpython",
    "IPython": "ipython",
    "nbformat": "nbformat",
    "pytest": "pytest",
}

# Distributions that are tooling rather than imports — declared on purpose, never imported.
TOOLING_DISTS = {
    "ruff",
    "black",
    "flake8",
    "isort",
    "mypy",
    "pylint",
    "pre-commit",
    "nox",
    "tox",
    "build",
    "twine",
    "setuptools",
    "wheel",
    "pip",
    "hatchling",
    "poetry-core",
    "pytest",
    "pytest-cov",
    "pytest-xdist",
    "coverage",
    "sphinx",
    "mkdocs",
    "sphinx-rtd-theme",
    "myst-parser",
    "bump2version",
    "nbstripout",
    "darglint",
}

# The standard library, for telling a third-party import from a builtin one. Built from
# `sys.stdlib_module_names` where available (3.10+) with a fallback list for 3.9.
try:  # pragma: no cover — version-dependent
    import sys as _sys

    STDLIB_MODULES = set(_sys.stdlib_module_names) | {"__future__"}
except AttributeError:  # pragma: no cover
    STDLIB_MODULES = {
        "abc",
        "argparse",
        "ast",
        "asyncio",
        "base64",
        "collections",
        "concurrent",
        "configparser",
        "contextlib",
        "copy",
        "csv",
        "ctypes",
        "dataclasses",
        "datetime",
        "decimal",
        "difflib",
        "enum",
        "functools",
        "glob",
        "gzip",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "importlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "mmap",
        "multiprocessing",
        "operator",
        "os",
        "pathlib",
        "pickle",
        "platform",
        "pprint",
        "queue",
        "random",
        "re",
        "shlex",
        "shutil",
        "signal",
        "site",
        "socket",
        "sqlite3",
        "statistics",
        "string",
        "struct",
        "subprocess",
        "sys",
        "tarfile",
        "tempfile",
        "textwrap",
        "threading",
        "time",
        "traceback",
        "types",
        "typing",
        "unittest",
        "urllib",
        "uuid",
        "warnings",
        "weakref",
        "xml",
        "zipfile",
        "zlib",
        "__future__",
    }


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def python_files(repo: Path, tracked: list[str]) -> list[str]:
    """Tracked `.py` paths that are the repo's own source."""
    return [r for r in tracked if r.endswith(".py") and not VENDOR_DIRS.search(r)]


def load_pyproject(repo: Path) -> dict:
    """Parse `pyproject.toml`. Returns {} when absent or malformed."""
    path = repo / "pyproject.toml"
    if not path.is_file():
        return {}
    try:
        return load_toml(read_text(path))
    except TomlError as e:
        warn(f"pyproject.toml is not valid TOML: {e}")
        return {}


def ruff_config(repo: Path) -> tuple[dict, str | None]:
    """Locate the effective ruff config. Returns (config_dict, source_path_or_None)."""
    for name in ("ruff.toml", ".ruff.toml"):
        path = repo / name
        if path.is_file():
            try:
                return load_toml(read_text(path)), name
            except TomlError:
                return {}, name
    pp = load_pyproject(repo)
    tool_ruff = (pp.get("tool") or {}).get("ruff")
    if isinstance(tool_ruff, dict):
        return tool_ruff, "pyproject.toml [tool.ruff]"
    return {}, None


def canonical_ruff() -> dict:
    """Parse the skill's canonical ruff config."""
    try:
        return load_toml(read_text(reference("canonical-ruff.toml")))
    except (TomlError, OSError):
        warn("could not parse references/canonical-ruff.toml")
        return {}


def is_public(name: str) -> bool:
    """True for a name the template's docstring rule applies to.

    Private helpers are exempt: *"For private helpers, only add a docstring when the
    intent isn't obvious from the name and signature."* Dunders are exempt too — the
    canonical ruff config ignores `D105` (magic method) and `D107` (`__init__`).
    """
    return not name.startswith("_")


def numpy_sections(doc: str) -> set[str]:
    """Section headers present in a NumPy-style docstring.

    A section is a header line followed by a run of `-` at least as long as the header.
    """
    found: set[str] = set()
    lines = doc.splitlines()
    for i in range(len(lines) - 1):
        header = lines[i].strip()
        rule = lines[i + 1].strip()
        if header and rule and set(rule) == {"-"} and len(rule) >= len(header):
            found.add(header.lower())
    return found


def returns_a_value(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if the function has a `return <expr>` or a `yield`, ignoring nested defs."""
    for child in ast.walk(node):
        if (
            isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            and child is not node
        ):
            continue
        if isinstance(child, ast.Return) and child.value is not None:
            return True
        if isinstance(child, (ast.Yield, ast.YieldFrom)):
            return True
    if node.returns is not None:
        # An explicit `-> None` annotation means no value.
        return not (
            isinstance(node.returns, ast.Constant) and node.returns.value is None
        )
    return False


def real_params(
    node: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool
) -> list[str]:
    """Parameter names that a docstring should document."""
    a = node.args
    names = [p.arg for p in (*a.posonlyargs, *a.args)]
    if is_method and names and names[0] in ("self", "cls"):
        names = names[1:]
    if a.vararg:
        names.append(a.vararg.arg)
    names += [p.arg for p in a.kwonlyargs]
    if a.kwarg:
        names.append(a.kwarg.arg)
    return names


# --------------------------------------------------------------------------------------
# ruff
# --------------------------------------------------------------------------------------


def run_ruff(repo: Path, ruff: str, findings: list, skips: list) -> None:
    """Run `ruff check` with the canonical config and `ruff format --check`.

    The repo's own config is deliberately bypassed by passing `--config <canonical>`,
    which makes ruff use that file exclusively: the point is to measure against the org
    standard, not against whatever the repo has settled for. (`--isolated` cannot be
    combined with `--config` — ruff rejects the pair.)
    Findings are rolled up per rule so a repo with 400 missing docstrings produces one
    finding, not 400.
    """
    cfg = reference("canonical-ruff.toml")
    proc = run(
        [
            ruff,
            "check",
            "--config",
            str(cfg),
            "--output-format",
            "json",
            "--no-cache",
            ".",
        ],
        cwd=repo,
        timeout=300,
    )
    if proc.returncode == 127:
        skips.append(skipped("PKG-RUFF-CHECK-FAILS", proc.stderr.strip()[:200]))
        return
    try:
        violations = json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError:
        skips.append(
            skipped(
                "PKG-RUFF-CHECK-FAILS",
                f"ruff produced unparseable output: {(proc.stderr or proc.stdout).strip()[:200]}",
            )
        )
        return

    by_code: dict[str, list[str]] = {}
    for v in violations:
        code = v.get("code") or "?"
        loc = v.get("filename") or ""
        try:
            loc = str(Path(loc).relative_to(repo))
        except ValueError:
            pass
        line = (v.get("location") or {}).get("row")
        by_code.setdefault(code, []).append(f"{loc}:{line}" if line else loc)

    # The individually-mapped codes get their own finding.
    for code, (check_id, severity, what) in RUFF_MAP.items():
        places = by_code.pop(code, [])
        if places:
            findings.append(
                finding(
                    check_id,
                    "T1",
                    severity,
                    f"{len(places)} × ruff {code} ({what}).",
                    f"Run `ruff check --fix` — most {code} violations are auto-fixable.",
                    detail=rollup(places),
                )
            )

    # Docstring rules (D...) roll up into the two docstring checks.
    doc_missing = [p for c, ps in by_code.items() if c.startswith("D1") for p in ps]
    doc_style = [
        p
        for c, ps in by_code.items()
        if c.startswith("D") and not c.startswith("D1")
        for p in ps
    ]
    if doc_missing:
        findings.append(
            finding(
                "PKG-DOCSTRING-MISSING",
                "T1",
                "Should-fix",
                f"{plural(len(doc_missing), 'public class or method', 'public classes and methods')} "
                f"{verb(len(doc_missing), 'has', 'have')} no docstring.",
                'Add succinct NumPy-style docstrings. The rule covers "every public class, '
                'function, and method"; private helpers are exempt.',
                detail=rollup(doc_missing),
            )
        )
    if doc_style:
        findings.append(
            finding(
                "PKG-DOCSTRING-NOT-NUMPY",
                "T1",
                "Should-fix",
                f"{plural(len(doc_style), 'docstring')} "
                f"{verb(len(doc_style), 'violates', 'violate')} the NumPy convention.",
                "Fix formatting: summary on one line, blank line before the closing quotes "
                "where required, sections underlined with `-`.",
                detail=rollup(doc_style),
            )
        )

    # The residual codes are Should-fix, not Blocker. The Blocker-worthy failures —
    # syntax errors, unused imports and variables, undefined names — are already reported
    # individually above via RUFF_MAP. What is left here is style: import ordering,
    # whitespace, line length. Calling an unsorted import block a Blocker would drown the
    # findings that genuinely stop the code working.
    remaining = {c: ps for c, ps in by_code.items() if not c.startswith("D")}
    if remaining:
        summary = ", ".join(
            f"{c}×{len(ps)}" for c, ps in sorted(remaining.items())[:10]
        )
        findings.append(
            finding(
                "PKG-RUFF-CHECK-FAILS",
                "T1",
                "Should-fix",
                f"`ruff check` reports "
                f"{plural(sum(len(p) for p in remaining.values()), 'style violation')} "
                "against the canonical config.",
                "Run `ruff check --fix` — most are auto-fixable — then fix what remains by "
                'hand. The rule is "`ruff check` and `ruff format` must both pass" before '
                "every commit.",
                detail=summary,
            )
        )

    fmt = run(
        [ruff, "format", "--check", "--config", str(cfg), "--no-cache", "."],
        cwd=repo,
        timeout=300,
    )
    if fmt.returncode == 1:
        dirty = [
            ln.split("Would reformat: ", 1)[-1]
            for ln in fmt.stdout.splitlines()
            if "Would reformat" in ln
        ]
        findings.append(
            finding(
                "PKG-RUFF-FORMAT-DIRTY",
                "T1",
                "Should-fix",
                f"{plural(len(dirty), 'file') if dirty else 'Some files'} not `ruff format` clean.",
                "Run `ruff format`.",
                detail=rollup(dirty) if dirty else None,
            )
        )
    elif fmt.returncode not in (0, 1):
        skips.append(
            skipped(
                "PKG-RUFF-FORMAT-DIRTY",
                (fmt.stderr or "ruff format failed").strip()[:200],
            )
        )


# --------------------------------------------------------------------------------------
# AST passes
# --------------------------------------------------------------------------------------


def check_docstring_sections(repo: Path, pyfiles: list[str], findings: list) -> None:
    """Docstring gaps ruff's canonical config does not cover.

    Two distinct gaps:

    1. **Missing docstrings on public functions.** The canonical config selects `D101`
       (class) and `D102` (method) but not `D103` (function), so a bare public function
       slips past ruff entirely — while the template rule covers "every public class,
       *function*, and method". This pass catches those.
    2. **Docstrings with no sections.** ruff checks that a docstring exists and is
       formatted correctly, not that a function taking six arguments documents any of them.
    """
    no_docstring: list[str] = []
    no_sections: list[str] = []

    for rel in pyfiles:
        text = read_text(repo / rel)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue  # reported as PKG-SYNTAX-ERROR by ruff

        # Map each function node to its enclosing class, so `self`/`cls` can be dropped
        # and methods can be told apart from module-level functions.
        method_of: dict[int, str] = {}
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                for child in parent.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_of[id(child)] = parent.name

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not is_public(node.name):
                continue
            is_method = id(node) in method_of
            doc = ast.get_docstring(node)
            if not doc:
                # Methods are ruff's D102; only report the functions it misses.
                if not is_method:
                    no_docstring.append(f"{rel}:{node.lineno} `{node.name}`")
                continue
            sections = numpy_sections(doc)
            params = real_params(node, is_method)
            missing: list[str] = []
            if params and "parameters" not in sections:
                missing.append(f"Parameters ({len(params)} args)")
            if (
                returns_a_value(node)
                and "returns" not in sections
                and "yields" not in sections
            ):
                missing.append("Returns")
            if missing:
                no_sections.append(
                    f"{rel}:{node.lineno} `{node.name}` — no {', '.join(missing)}"
                )

    if no_docstring:
        findings.append(
            finding(
                "PKG-DOCSTRING-MISSING",
                "T1",
                "Should-fix",
                f"{plural(len(no_docstring), 'public function')} "
                f"{verb(len(no_docstring), 'has', 'have')} no docstring.",
                "Add succinct NumPy-style docstrings. Note these are invisible to `ruff "
                "check`: the canonical config selects `D101` and `D102` but not `D103`, so "
                "public functions are not covered by the linter even though the template rule "
                "covers them.",
                detail="; ".join(no_docstring[:40])
                + (
                    f" (+{len(no_docstring) - 8} more)" if len(no_docstring) > 8 else ""
                ),
            )
        )
    if no_sections:
        findings.append(
            finding(
                "PKG-DOCSTRING-NOT-NUMPY",
                "T1",
                "Should-fix",
                f"{plural(len(no_sections), 'public function')} "
                f"{verb(len(no_sections), 'has', 'have')} a docstring with no "
                "`Parameters`/`Returns` section.",
                "Add the sections. NumPy style: the header, then a rule of `-` the same "
                "length, then one entry per parameter.",
                detail="; ".join(no_sections[:40])
                + (
                    f" (+{len(no_sections) - 40} more)" if len(no_sections) > 40 else ""
                ),
            )
        )


def check_dead_names(
    repo: Path, pyfiles: list[str], pyproject: dict, findings: list
) -> None:
    """Module-level names that nothing in the repo references.

    A heuristic, and reported as such — a name reached only through `getattr`, a plugin
    registry, or a string-based import will be flagged wrongly. Names exported via
    `__all__` or declared as a console-script entry point are excluded, as is anything
    in a package `__init__.py` (re-exports are the point there).
    """
    defined: dict[str, list[str]] = {}
    exported: set[str] = set()
    all_text: list[str] = []

    for rel in pyfiles:
        text = read_text(repo / rel)
        all_text.append(text)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        # `__init__.py` re-exports on purpose. Test modules are discovered by *name* by
        # pytest, so a `test_*` function is never referenced from anywhere and would always
        # look dead — flagging `test_hello` in the package template was the giveaway.
        if Path(rel).name == "__init__.py" or TEST_PATH_RE.search(rel):
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if is_public(node.name):
                    defined.setdefault(node.name, []).append(f"{rel}:{node.lineno}")
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(
                                    elt.value, str
                                ):
                                    exported.add(elt.value)

    entry_points = set()
    for section in ("scripts", "gui-scripts", "entry-points"):
        ep = (pyproject.get("project") or {}).get(section) or {}
        if isinstance(ep, dict):
            for value in ep.values():
                if isinstance(value, str) and ":" in value:
                    entry_points.add(value.rsplit(":", 1)[-1])

    corpus = "\n".join(all_text)
    dead: list[str] = []
    for name, places in defined.items():
        if name in exported or name in entry_points or name == "main":
            continue
        # Count references outside the definition line itself.
        hits = len(re.findall(rf"\b{re.escape(name)}\b", corpus))
        if hits <= len(places):
            dead.append(f"{places[0]} `{name}`")
    if dead:
        findings.append(
            finding(
                "PKG-DEAD-MODULE-NAME",
                "T1",
                "Should-fix",
                f"{plural(len(dead), 'module-level name')} {verb(len(dead))} defined but never "
                "referenced.",
                "Delete them, or export them via `__all__` if they are public API. Verify "
                "each one first — a name reached through `getattr` or a string import will "
                "look dead here.",
                detail="; ".join(dead[:40])
                + (f" (+{len(dead) - 40} more)" if len(dead) > 40 else ""),
                confidence="medium",
            )
        )


def declared_dependencies(repo: Path, pyproject: dict) -> set[str]:
    """Normalised distribution names declared anywhere in the repo's dependency files."""
    names: set[str] = set()

    def add(spec: str) -> None:
        base = re.split(r"[<>=!~;\[\s@]", spec.strip(), maxsplit=1)[0]
        if base:
            names.add(base.lower().replace("_", "-").replace(".", "-"))

    project = pyproject.get("project") or {}
    poetry = ((pyproject.get("tool") or {}).get("poetry")) or {}
    for spec in project.get("dependencies") or []:
        if isinstance(spec, str):
            add(spec)
    for group in (project.get("optional-dependencies") or {}).values():
        for spec in group or []:
            if isinstance(spec, str):
                add(spec)
    deps = poetry.get("dependencies")
    if isinstance(deps, dict):
        for key in deps:
            add(key)

    for fname in (
        "requirements.txt",
        "requirements-dev.txt",
        "environment.yml",
        "env.yml",
        "install.yml",
    ):
        text = read_text(repo / fname)
        for line in text.splitlines():
            line = line.strip().lstrip("-").strip()
            if not line or line.startswith("#"):
                continue
            # environment.yml entries look like `- numpy=1.26` or `- pip:`
            if line.endswith(":"):
                continue
            add(line.split("=")[0] if "=" in line and "==" not in line else line)
    return names


def check_declared_deps(
    repo: Path, pyfiles: list[str], pyproject: dict, findings: list, skips: list
) -> None:
    """Third-party imports that no dependency file declares, and the reverse.

    An undeclared import means `pip install <package>` produces something that crashes on
    first use. The mapping from import name to distribution name is not mechanical
    (`sklearn` ships as `scikit-learn`), so a table covers the common scientific-Python
    cases and anything unresolved is reported at medium confidence.
    """
    declared = declared_dependencies(repo, pyproject)
    if not declared:
        skips.append(
            skipped(
                "PKG-DEP-UNDECLARED", "no dependency file to compare imports against"
            )
        )
        return

    # Local package names are not dependencies of themselves.
    local: set[str] = (
        {p.name for p in (repo / "src").iterdir() if p.is_dir()}
        if (repo / "src").is_dir()
        else set()
    )
    for rel in pyfiles:
        top = rel.split("/")[0]
        if top not in ("src", "tests", "test", "scripts", "docs"):
            local.add(top)
        if rel.startswith("src/"):
            local.add(rel.split("/")[1])
    local |= {Path(r).stem for r in pyfiles if "/" not in r}

    imported: dict[str, str] = {}
    for rel in pyfiles:
        text = read_text(repo / rel)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imported.setdefault(a.name.split(".")[0], f"{rel}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # relative import — always internal
                    continue
                if node.module:
                    imported.setdefault(
                        node.module.split(".")[0], f"{rel}:{node.lineno}"
                    )

    missing: list[str] = []
    for mod, where in sorted(imported.items()):
        if mod in STDLIB_MODULES or mod in local or mod.startswith("_"):
            continue
        dist = IMPORT_TO_DIST.get(mod, mod).lower().replace("_", "-")
        if dist in declared or mod.lower().replace("_", "-") in declared:
            continue
        missing.append(f"`{mod}` (imported at {where}, expected dist `{dist}`)")

    if missing:
        findings.append(
            finding(
                "PKG-DEP-UNDECLARED",
                "T1",
                "Should-fix",
                f"{plural(len(missing), 'third-party import')} {verb(len(missing))} not declared as "
                "dependencies.",
                "Add them to `pyproject.toml` (or `requirements.txt`) with an exact pin. As it "
                "stands a fresh install of this package imports modules it never asked for. "
                "Check each one — a conditional or optional import may be deliberate.",
                detail="; ".join(missing[:40])
                + (f" (+{len(missing) - 40} more)" if len(missing) > 40 else ""),
                confidence="medium",
            )
        )

    # Declared but never imported: dead weight in the install.
    imported_dists = {
        IMPORT_TO_DIST.get(m, m).lower().replace("_", "-") for m in imported
    } | {m.lower().replace("_", "-") for m in imported}
    unused = sorted(
        d
        for d in declared
        if d not in imported_dists and d not in TOOLING_DISTS and d != "python"
    )
    if unused:
        findings.append(
            finding(
                "PKG-DEP-UNUSED",
                "T1",
                "Nice-to-have",
                f"{plural(len(unused), 'declared dependency', 'declared dependencies')} "
                f"{verb(len(unused))} never imported.",
                "Remove them, or confirm they are needed at runtime rather than at import time "
                "(a CLI plugin or a backend driver would be). Every dependency is a long-term "
                'cost — "only add a new package when the benefit is clear".',
                detail=rollup(unused),
                confidence="medium",
            )
        )


def check_logging(repo: Path, pyfiles: list[str], findings: list) -> None:
    """`logging.getLogger` in feature code instead of the module-level singleton."""
    offenders: list[str] = []
    for rel in pyfiles:
        if (
            re.search(r"(^|/)(utils/)?logging\.py$", rel)
            or "/tests/" in rel
            or rel.startswith("tests/")
        ):
            continue
        text = read_text(repo / rel)
        for m in re.finditer(r"logging\.getLogger\(", text):
            offenders.append(f"{rel}:{text[: m.start()].count(chr(10)) + 1}")
            break
    if offenders:
        findings.append(
            finding(
                "PKG-BARE-LOGGER",
                "T1",
                "Should-fix",
                f"{plural(len(offenders), 'module')} {verb(len(offenders), 'calls', 'call')} "
                "`logging.getLogger` directly.",
                "Import the package's logger singleton instead: "
                "`from <package>.utils.logging import logger`. The rule is explicit — "
                '"do not call `logging.getLogger(...)` directly in feature code".',
                detail=rollup(offenders),
            )
        )


def check_cli(
    repo: Path, pyfiles: list[str], readme: str, findings: list, skips: list
) -> None:
    """A CLI is built with Click and its commands are documented as a README table."""
    uses_click = False
    uses_argparse = False
    for rel in pyfiles:
        text = read_text(repo / rel)
        if re.search(r"^\s*import click|^\s*from click", text, re.MULTILINE):
            uses_click = True
        if re.search(r"^\s*import argparse|^\s*from argparse", text, re.MULTILINE) and (
            "/cli" in rel or rel.endswith("cli.py") or "__main__" in rel
        ):
            uses_argparse = True

    if not (uses_click or uses_argparse):
        skips.append(skipped("PKG-CLI-NOT-CLICK", "no CLI detected"))
        skips.append(skipped("PKG-CLI-NOT-TABLED", "no CLI detected"))
        return

    if uses_argparse and not uses_click:
        findings.append(
            finding(
                "PKG-CLI-NOT-CLICK",
                "T1",
                "Should-fix",
                "The CLI is built with argparse rather than Click.",
                "Port to Click, organised as `src/<package>/cli/commands/` with one file per "
                "command and a small `create_cli.py`, mirroring `ersilia-os/ersilia`.",
            )
        )

    if not re.search(r"^\s*\|.*\|.*\|", readme, re.MULTILINE):
        findings.append(
            finding(
                "PKG-CLI-NOT-TABLED",
                "T1",
                "Should-fix",
                "The package ships a CLI but the README has no command table.",
                "Add a compact two-column table (command → one-line description). Do not "
                "reproduce `--help` output in Markdown.",
                file="README.md",
            )
        )

    check_cli_vocabulary(repo, pyfiles, findings)


def cli_surface(
    repo: Path, pyfiles: list[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Extract the CLI's option flags and command names.

    Reads both dialects: Click's `@click.option("--flag", "-f")` / `@click.command("name")`
    and argparse's `add_argument("--flag", "-f")` / `add_parser("name")`. Returns
    `({flag: where}, {command: where})`.
    """
    options: dict[str, str] = {}
    commands: dict[str, str] = {}
    for rel in pyfiles:
        text = read_text(repo / rel)
        if not text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            literals = [
                a.value
                for a in node.args
                if isinstance(a, ast.Constant) and isinstance(a.value, str)
            ]
            where = f"{rel}:{node.lineno}"
            if fname in ("option", "add_argument", "argument"):
                for lit in literals:
                    if lit.startswith("-"):
                        options.setdefault(lit, where)
            elif fname in ("command", "add_parser", "group"):
                for lit in literals:
                    if lit and not lit.startswith("-"):
                        commands.setdefault(lit, where)
                        break
    return options, commands


def check_cli_vocabulary(repo: Path, pyfiles: list[str], findings: list) -> None:
    """Whether the CLI's names agree with the canonical vocabulary.

    See `references/canonical-cli.md` for the canon and the kebab-case ruling. A user who
    has learned `ersilia` should be able to guess the next tool's flags; every divergence
    costs that.
    """
    cli_files = [
        r
        for r in pyfiles
        if "/cli" in r or r.endswith(("cli.py", "__main__.py", "main.py"))
    ]
    options, commands = cli_surface(repo, cli_files or pyfiles)
    if not options and not commands:
        return

    longs = {o: w for o, w in options.items() if o.startswith("--")}
    shorts = {o for o in options if re.fullmatch(r"-[a-zA-Z]", o)}

    # Separator: kebab-case is canonical.
    snake = {o: w for o, w in longs.items() if "_" in o.lstrip("-")}
    kebab = {o for o in longs if "-" in o.lstrip("-")}
    if snake:
        findings.append(
            finding(
                "PKG-CLI-OPT-SEPARATOR",
                "T1",
                "Should-fix",
                f"{plural(len(snake), 'CLI option')} {verb(len(snake), 'uses', 'use')} `_` "
                "instead of `-`.",
                "Rename to kebab-case. Click maps `--batch-size` to a `batch_size` parameter "
                "automatically, so only the flag string changes. See "
                "`references/canonical-cli.md`.",
                detail=rollup([f"{o} ({w})" for o, w in sorted(snake.items())], 8),
            )
        )
        if kebab:
            findings.append(
                finding(
                    "PKG-CLI-INCONSISTENT",
                    "T1",
                    "Should-fix",
                    "This CLI mixes `_` and `-` in its option names.",
                    "Pick one — kebab-case — and apply it throughout. Mixing is worse than "
                    "either convention.",
                    detail=f"{len(snake)} snake_case, {len(kebab)} kebab-case",
                )
            )

    # Command verbs: prefer the canonical word for a thing that already has one.
    divergent = [
        (cmd, CANONICAL_VERB[cmd], where)
        for cmd, where in sorted(commands.items())
        if cmd in CANONICAL_VERB
    ]
    if divergent:
        findings.append(
            finding(
                "PKG-CLI-VERB-DIVERGENT",
                "T1",
                "Should-fix",
                f"{plural(len(divergent), 'command')} {verb(len(divergent))} "
                f"{'a near-synonym' if len(divergent) == 1 else 'near-synonyms'} of a "
                "canonical verb.",
                "Rename to the canonical verb so the vocabulary matches every other Ersilia "
                "CLI. Weigh it against breaking existing usage — a deprecation alias is fine.",
                detail="; ".join(
                    f"`{c}` → `{canon}` ({w})" for c, canon, w in divergent[:40]
                ),
            )
        )

    # File I/O naming.
    misnamed = [
        (o, w)
        for o, w in sorted(longs.items())
        if o.lstrip("-").replace("_", "-") in IO_MISNAMES
    ]
    if misnamed:
        findings.append(
            finding(
                "PKG-CLI-IO-NAMING",
                "T1",
                "Should-fix",
                f"{plural(len(misnamed), 'file argument')} "
                f"{verb(len(misnamed), 'does', 'do')} not use `--input`/`--output`.",
                "Rename to `-i/--input` and `-o/--output`, matching `ersilia run`.",
                detail=rollup([f"{o} ({w})" for o, w in misnamed], 6),
            )
        )

    # Short forms for the canonical I/O pair.
    for long_flag, short in (("--input", "-i"), ("--output", "-o")):
        if long_flag in longs and short not in shorts:
            findings.append(
                finding(
                    "PKG-CLI-NO-SHORT-IO",
                    "T1",
                    "Nice-to-have",
                    f"`{long_flag}` has no `{short}` short form.",
                    f"Add `{short}` — `ersilia run` exposes both, and the short forms are what "
                    "people actually type.",
                    file=longs[long_flag].split(":")[0],
                )
            )


# --------------------------------------------------------------------------------------
# Packaging
# --------------------------------------------------------------------------------------


def check_packaging(repo: Path, pyproject: dict, findings: list, skips: list) -> None:
    """pyproject presence, pinning, requires-python, pytest config."""
    if not pyproject:
        if (repo / "setup.py").is_file():
            findings.append(
                finding(
                    "PKG-SETUP-PY",
                    "T1",
                    "Should-fix",
                    "Packaging uses `setup.py` rather than `pyproject.toml`.",
                    "Migrate to `pyproject.toml` with the setuptools backend, matching "
                    "`eos-python-package`.",
                    file="setup.py",
                )
            )
        else:
            findings.append(
                finding(
                    "PKG-NO-PYPROJECT",
                    "T1",
                    "Should-fix",
                    "There is no `pyproject.toml`.",
                    "Add one declaring name, version, `requires-python`, and exactly pinned "
                    "dependencies.",
                )
            )
        return

    project = pyproject.get("project") or {}
    if not project and (pyproject.get("tool") or {}).get("poetry"):
        project = (pyproject["tool"]["poetry"]) or {}

    if not project.get("requires-python") and not project.get("python"):
        findings.append(
            finding(
                "PKG-NO-REQUIRES-PYTHON",
                "T1",
                "Should-fix",
                "`requires-python` is not declared.",
                'Add `requires-python = ">=3.10"` to `[project]`.',
                file="pyproject.toml",
            )
        )

    def unpinned(specs) -> list[str]:
        out: list[str] = []
        if isinstance(specs, dict):  # poetry style
            for name, spec in specs.items():
                if name.lower() == "python":
                    continue
                text = spec if isinstance(spec, str) else str(spec)
                if not re.match(r"^==?\d", text.strip()):
                    out.append(f"{name} {text}")
            return out
        for spec in specs or []:
            if not isinstance(spec, str):
                continue
            base = spec.split(";")[0].strip()
            if base.startswith(("http", "git+", "file:")) or "@" in base:
                continue  # direct reference — pinned by URL
            if "==" not in base:
                out.append(base)
        return out

    bad = unpinned(project.get("dependencies"))
    if bad:
        findings.append(
            finding(
                "PKG-DEP-UNPINNED",
                "T1",
                "Should-fix",
                f"{plural(len(bad), 'runtime dependency', 'runtime dependencies')} "
                f"{verb(len(bad))} not pinned to an exact version.",
                'Use `==X.Y.Z` for every entry. The rule leaves no room: "No floors (`>=`), '
                'no ranges."',
                file="pyproject.toml",
                detail=rollup(bad),
            )
        )

    extras = project.get("optional-dependencies") or {}
    bad_dev: list[str] = []
    for group, specs in extras.items():
        for spec in unpinned(specs):
            bad_dev.append(f"[{group}] {spec}")
    if bad_dev:
        findings.append(
            finding(
                "PKG-DEV-DEP-UNPINNED",
                "T1",
                "Should-fix",
                f"{plural(len(bad_dev), 'optional/dev dependency', 'optional/dev dependencies')} "
                f"{verb(len(bad_dev))} unpinned.",
                "Pin these too — an unpinned `ruff` or `black` means the lint result depends "
                "on when you installed.",
                file="pyproject.toml",
                detail=rollup(bad_dev),
            )
        )

    pytest_cfg = ((pyproject.get("tool") or {}).get("pytest") or {}).get(
        "ini_options"
    ) or {}
    has_ini = any((repo / n).is_file() for n in ("pytest.ini", "tox.ini", "setup.cfg"))
    if not pytest_cfg.get("testpaths") and not has_ini:
        findings.append(
            finding(
                "PKG-NO-PYTEST-CONFIG",
                "T1",
                "Should-fix",
                "No `[tool.pytest.ini_options]` with `testpaths`.",
                'Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, as in '
                "`eos-python-package`.",
                file="pyproject.toml",
            )
        )


def _named_linters(competing: list[str]) -> str:
    """Name the competing linters rather than counting them.

    "black is configured alongside ruff" tells the reader more than "1 non-ruff linter is",
    and is shorter. Falls back to a count past three, where naming stops helping.
    """
    names = []
    for item in competing:
        for known in ("black", "flake8", "isort", "pylint", "darglint"):
            if known in item and known not in names:
                names.append(known)
    if not names:
        return plural(len(competing), "non-ruff linter")
    if len(names) > 3:
        return plural(len(names), "non-ruff linter")
    if len(names) == 1:
        return f"`{names[0]}`"
    return ", ".join(f"`{n}`" for n in names[:-1]) + f" and `{names[-1]}`"


def check_linters(repo: Path, pyproject: dict, findings: list, skips: list) -> None:
    """ruff config presence, drift from canonical, and competing linters."""
    cfg, source = ruff_config(repo)
    if source is None:
        findings.append(
            finding(
                "PKG-NO-RUFF-CONFIG",
                "T1",
                "Should-fix",
                "There is no ruff configuration.",
                "Copy `references/canonical-ruff.toml` to `ruff.toml`. It is the only dialect "
                "in the org that enforces the NumPy docstring convention the template "
                "mandates.",
            )
        )
        skips.append(skipped("PKG-RUFF-CONFIG-DRIFT", "no ruff config to compare"))
    else:
        canon = canonical_ruff()
        diffs: list[str] = []
        for key, want in CANONICAL_RUFF_KEYS.items():
            got = cfg.get(key, canon.get(key))
            if key in cfg and cfg[key] != want:
                diffs.append(f"`{key}` is {got!r}, canonical is {want!r}")
        got_lint = cfg.get("lint") or {}
        if isinstance(
            cfg.get("lint.select"), list
        ):  # flat-key style, as in ersilia-pack
            got_select = cfg["lint.select"]
        else:
            got_select = got_lint.get("select")
        want_select = ((canon.get("lint") or {}).get("select")) or []
        if got_select is not None and set(got_select) != set(want_select):
            missing = sorted(set(want_select) - set(got_select))
            if missing:
                diffs.append(f"`lint.select` is missing {', '.join(missing)}")
        convention = (got_lint.get("pydocstyle") or {}).get("convention")
        if convention != "numpy":
            diffs.append(
                f"`lint.pydocstyle.convention` is {convention!r}, canonical is 'numpy'"
            )
        if diffs:
            findings.append(
                finding(
                    "PKG-RUFF-CONFIG-DRIFT",
                    "T1",
                    "Should-fix",
                    f"The ruff config in {source} diverges from the org standard.",
                    "Replace it with `references/canonical-ruff.toml`. The tinygrad-derived "
                    "dialect used by `ersilia-pack`, `isaura` and `olinda` enforces no "
                    "docstring rules and still carries tinygrad-specific excludes.",
                    file=source,
                    detail="; ".join(diffs),
                )
            )

    competing: list[str] = []
    tool = pyproject.get("tool") or {}
    for name, (marker, where) in COMPETING_LINTERS.items():
        if name in tool:
            competing.append(f"`[tool.{name}]` in pyproject.toml")
        elif (repo / f".{name}").is_file():
            competing.append(f"`.{name}`")
    for cfg_file in ("setup.cfg", "tox.ini"):
        text = read_text(repo / cfg_file)
        if re.search(r"^\[flake8\]", text, re.MULTILINE):
            competing.append(f"`[flake8]` in {cfg_file}")
    if competing:
        findings.append(
            finding(
                "PKG-COMPETING-LINTERS",
                "T1",
                "Should-fix",
                _named_linters(competing)
                + f" {verb(len(competing))} configured alongside ruff.",
                "The canonical toolchain is ruff-only — `ruff check` plus `ruff format` "
                "replace black, flake8 and isort. Remove the others so there is one source "
                "of truth.",
                detail=", ".join(competing),
            )
        )

    pc = None
    for name in (".pre-commit-config.yaml", ".pre-commit-config.yml"):
        if (repo / name).is_file():
            pc = name
            break
    if pc is None:
        findings.append(
            finding(
                "PKG-NO-PRECOMMIT",
                "T1",
                "Should-fix",
                "There is no pre-commit config.",
                "Add `.pre-commit-config.yaml` with the `ruff` and `ruff-format` hooks at a "
                "pinned `rev`, matching `ersilia-os/ersilia`.",
            )
        )
    else:
        text = read_text(repo / pc)
        missing = [h for h in ("ruff", "ruff-format") if f"id: {h}" not in text]
        if missing:
            findings.append(
                finding(
                    "PKG-NO-PRECOMMIT",
                    "T1",
                    "Should-fix",
                    f"The pre-commit config is missing the {', '.join(missing)} "
                    f"{plural(len(missing), 'hook').split(' ', 1)[1]}.",
                    "Add them from the ruff-pre-commit mirror at a pinned `rev`.",
                    file=pc,
                )
            )
        elif re.search(r"rev:\s*['\"]?(main|master|HEAD)", text):
            findings.append(
                finding(
                    "PKG-NO-PRECOMMIT",
                    "T1",
                    "Should-fix",
                    "The pre-commit ruff hook is pinned to a moving ref.",
                    "Pin `rev:` to a released tag so the lint result is reproducible.",
                    file=pc,
                )
            )


def check_tests(repo: Path, tracked: list[str], findings: list) -> None:
    """A test suite exists and contains at least one real test."""
    test_files = [
        r
        for r in tracked
        if re.match(r"^(tests?)/", r)
        and Path(r).name.startswith("test_")
        and r.endswith(".py")
    ]
    if not test_files:
        findings.append(
            finding(
                "PKG-NO-TESTS",
                "T1",
                "Should-fix",
                "There is no test suite.",
                "Add smoke tests for the user-facing API and CLI in `tests/`. The bar is "
                'deliberately low — "skip exhaustive unit-test coverage of internals" — but '
                "not zero.",
            )
        )
        return
    has_test_fn = any(
        re.search(r"^\s*(async\s+)?def test_", read_text(repo / r), re.MULTILINE)
        for r in test_files
    )
    if not has_test_fn:
        findings.append(
            finding(
                "PKG-NO-TESTS",
                "T1",
                "Should-fix",
                f"{plural(len(test_files), 'test file')} {verb(len(test_files), 'exists', 'exist')} "
                "but none defines a `test_*` function.",
                "Add at least one real assertion.",
                detail=rollup(test_files),
            )
        )


def check_promised_files(repo: Path, findings: list) -> None:
    """Files the repo's own CLAUDE.md or README requires but does not ship.

    `eosquality`'s CLAUDE.md mandates five `docs/` files, none of which exist. A doc that
    prescribes files it does not have is worse than no doc — it misleads.
    """
    promised: set[str] = set()
    for doc in ("CLAUDE.md", "README.md"):
        text = read_text(repo / doc)
        if not text:
            continue
        for m in re.finditer(r"`(docs/[\w./-]+\.md)`", text):
            promised.add(m.group(1))
    missing = sorted(p for p in promised if not (repo / p).exists())
    if missing:
        findings.append(
            finding(
                "PKG-DOCS-PROMISED-MISSING",
                "T1",
                "Should-fix",
                f"{plural(len(missing), 'documentation file')} {verb(len(missing))} required by the "
                "repo's own docs but "
                "do not exist.",
                "Write them, or drop the requirement from `CLAUDE.md`/README so the docs "
                "match reality.",
                detail=rollup(missing),
            )
        )


def check_placeholder_package(repo: Path, findings: list) -> None:
    """The templated package folder and an untouched `core.py`."""
    if (repo / "src" / "my_package").is_dir():
        findings.append(
            finding(
                "PKG-PLACEHOLDER-PKG",
                "T1",
                "Blocker",
                "`src/my_package/` was never renamed.",
                "Rename it to the real package name (snake_case, matching `[project].name`).",
            )
        )
    for core in repo.glob("src/*/core.py"):
        text = read_text(core).strip()
        if text == 'def hello(name: str) -> str:\n    return f"Hello, {name}!"':
            findings.append(
                finding(
                    "PKG-UNTOUCHED-CORE",
                    "T1",
                    "Should-fix",
                    "The templated `core.py` is unmodified.",
                    "Delete it — it exists only to make the layout valid. The rule: "
                    '"Remove `core.py` if untouched."',
                    file=str(core.relative_to(repo)),
                )
            )


# --------------------------------------------------------------------------------------
# Analysis-profile script checks
# --------------------------------------------------------------------------------------


def check_requirements(repo: Path, findings: list) -> None:
    """requirements.txt exists, is non-empty, and is pinned."""
    path = repo / "requirements.txt"
    if not path.is_file():
        findings.append(
            finding(
                "ANA-REQS-MISSING",
                "T1",
                "Should-fix",
                "There is no `requirements.txt`.",
                "Add one with exactly pinned versions.",
            )
        )
        return
    text = read_text(path)
    entries = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if not entries:
        findings.append(
            finding(
                "ANA-REQS-EMPTY",
                "T1",
                "Blocker",
                "`requirements.txt` is empty.",
                "List the dependencies the analysis actually needs, pinned with `==`. An "
                "empty file makes the analysis unreproducible while looking as though "
                "dependencies were declared.",
                file="requirements.txt",
            )
        )
        return
    unpinned = [
        e
        for e in entries
        if "==" not in e and not e.startswith(("-", "http", "git+", "file:"))
    ]
    if unpinned:
        findings.append(
            finding(
                "ANA-REQS-UNPINNED",
                "T1",
                "Should-fix",
                f"{plural(len(unpinned), 'requirement')} {verb(len(unpinned))} not pinned.",
                "Pin every entry with `==`.",
                file="requirements.txt",
                detail=rollup(unpinned),
            )
        )


def check_script_numbering(repo: Path, findings: list, skips: list) -> None:
    """scripts/ numbered sequentially, with output/ mirroring the numbering."""
    sdir = repo / "scripts"
    if not sdir.is_dir():
        skips.append(skipped("ANA-SCRIPT-NOT-NUMBERED", "no scripts/ directory"))
        return
    scripts = sorted(
        p.name
        for p in sdir.iterdir()
        if p.is_file() and p.suffix in (".py", ".sh", ".R", ".ipynb")
    )
    if not scripts:
        skips.append(skipped("ANA-SCRIPT-NOT-NUMBERED", "scripts/ is empty"))
        return

    unnumbered = [s for s in scripts if not re.match(r"^\d{2,}[_-]", s)]
    if unnumbered:
        findings.append(
            finding(
                "ANA-SCRIPT-NOT-NUMBERED",
                "T1",
                "Should-fix",
                f"{plural(len(unnumbered), 'script')} in `scripts/` {verb(len(unnumbered))} not "
                "sequentially numbered.",
                "Rename to `01_preprocess.py`, `02_train.py`, … so the pipeline order is "
                "readable from the directory listing.",
                detail=rollup(unnumbered),
            )
        )

    numbers = [int(m.group(1)) for s in scripts if (m := re.match(r"^(\d{2,})", s))]
    if numbers:
        seen = sorted(set(numbers))
        dupes = sorted({n for n in numbers if numbers.count(n) > 1})
        gaps = [n for n in range(seen[0], seen[-1] + 1) if n not in seen]
        problems = []
        if gaps:
            problems.append("gaps at " + ", ".join(f"{g:02d}" for g in gaps[:8]))
        if dupes:
            problems.append("duplicates at " + ", ".join(f"{d:02d}" for d in dupes[:8]))
        if problems:
            findings.append(
                finding(
                    "ANA-SCRIPT-NUMBER-GAP",
                    "T1",
                    "Should-fix",
                    f"The `scripts/` numbering is not contiguous ({'; '.join(problems)}).",
                    "Renumber so the sequence reads as the pipeline it is. A gap usually "
                    "means a step was deleted without the rest being renumbered.",
                )
            )


def check_analysis_scripts(repo: Path, findings: list, skips: list) -> None:
    """The Analysis-profile conventions for script bodies."""
    sdir = repo / "scripts"
    src = repo / "src"
    scripts = sorted(sdir.glob("*.py")) if sdir.is_dir() else []
    all_py = scripts + (sorted(src.glob("**/*.py")) if src.is_dir() else [])

    if not all_py:
        for cid in (
            "ANA-NO-SYSPATH-PREAMBLE",
            "ANA-MATPLOTLIB-NOT-STYLIA",
            "ANA-NO-RANDOM-SEED",
            "ANA-NO-PROVENANCE",
        ):
            skips.append(skipped(cid, "no Python in scripts/ or src/"))
        return

    no_preamble: list[str] = []
    bare_mpl: list[str] = []
    stochastic: list[str] = []
    unseeded: list[str] = []
    no_provenance: list[str] = []

    for path in all_py:
        rel = str(path.relative_to(repo))
        text = read_text(path)
        if not text:
            continue

        # Only scripts (not src modules) need the sys.path preamble.
        if path in scripts:
            imports_src = re.search(
                r"^\s*(?:from|import)\s+(default|utils)\b", text, re.MULTILINE
            ) or re.search(r"^\s*from\s+src\b", text, re.MULTILINE)
            if imports_src and not SYSPATH_PREAMBLE.search(text):
                no_preamble.append(rel)

        if "matplotlib" in text and "stylia" not in text:
            bare_mpl.append(rel)

        if any(m in text for m in STOCHASTIC_MARKERS):
            stochastic.append(rel)
            if not any(m in text for m in SEED_MARKERS):
                unseeded.append(rel)

        low = text.lower()
        if any(s in low for s in PROVENANCE_SOURCES) and re.search(
            r"(?i)(download|urlretrieve|requests\.get|urlopen|wget|curl|new_client|load_dataset)",
            text,
        ):
            head = "\n".join(text.splitlines()[:40])
            if not PROVENANCE_MARKERS.search(head):
                no_provenance.append(rel)

    if no_preamble:
        findings.append(
            finding(
                "ANA-NO-SYSPATH-PREAMBLE",
                "T1",
                "Should-fix",
                f"{plural(len(no_preamble), 'script')} {verb(len(no_preamble), 'imports', 'import')} "
                "from `src/` without the mandated "
                "`sys.path` preamble.",
                "Add the exact preamble from the analysis template before any `src` import:\n"
                "```python\nimport os\nimport sys\nroot = os.path.dirname(os.path.abspath(__file__))\n"
                'sys.path.append(os.path.join(root, "..", "src"))\n```',
                detail=rollup(no_preamble),
            )
        )
    if bare_mpl:
        findings.append(
            finding(
                "ANA-MATPLOTLIB-NOT-STYLIA",
                "T1",
                "Should-fix",
                f"{plural(len(bare_mpl), 'file')} {verb(len(bare_mpl), 'uses', 'use')} matplotlib "
                "without stylia.",
                "Use `stylia.create_figure()` instead of `plt.subplots()`. The rule is a hard "
                'requirement: "All Python plotting should strictly use the stylia library." '
                "The `/stylia-plotting` skill covers the API.",
                detail=rollup(bare_mpl),
            )
        )
    if stochastic:
        default_py = repo / "src" / "default.py"
        if not default_py.is_file() or "RANDOM_SEED" not in read_text(default_py):
            findings.append(
                finding(
                    "ANA-NO-RANDOM-SEED",
                    "T1",
                    "Should-fix",
                    f"{plural(len(stochastic), 'file')} {verb(len(stochastic), 'uses', 'use')} stochastic methods but no `RANDOM_SEED` is "
                    "defined in `src/default.py`.",
                    "Define a project-wide `RANDOM_SEED` in `src/default.py` and pass it "
                    "everywhere. Without it the analysis is not reproducible.",
                    detail=rollup(stochastic),
                )
            )
        if unseeded:
            findings.append(
                finding(
                    "ANA-NO-SEED-SET",
                    "T1",
                    "Should-fix",
                    f"{plural(len(unseeded), 'file')} {verb(len(unseeded), 'uses', 'use')} stochastic "
                    "methods without setting a seed.",
                    "Pass `random_state=RANDOM_SEED` (or the library equivalent) at every "
                    "call site.",
                    detail=rollup(unseeded),
                )
            )
    if no_provenance:
        findings.append(
            finding(
                "ANA-NO-PROVENANCE",
                "T1",
                "Should-fix",
                f"{plural(len(no_provenance), 'download script')} {verb(len(no_provenance), 'records', 'record')} no dataset version or "
                "snapshot date.",
                "Note the release or access date in the script header or `scripts/README.md`. "
                '"Datasets without a recorded version are not reproducible."',
                detail=rollup(no_provenance),
            )
        )


def check_default_py(repo: Path, findings: list, skips: list) -> None:
    """src/default.py holds project-wide constants in ALL_CAPS."""
    has_code = (repo / "scripts").is_dir() or (repo / "src").is_dir()
    if not has_code:
        skips.append(skipped("ANA-NO-DEFAULT-PY", "no scripts/ or src/ yet"))
        return
    path = repo / "src" / "default.py"
    if not path.is_file():
        findings.append(
            finding(
                "ANA-NO-DEFAULT-PY",
                "T1",
                "Should-fix",
                "There is no `src/default.py`.",
                "Create it and move project-wide constants there in `ALL_CAPS`, including "
                "`RANDOM_SEED`.",
            )
        )
        return
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return
    bad = [
        t.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(t, ast.Name) and not t.id.startswith("_") and t.id != t.id.upper()
    ]
    if bad:
        findings.append(
            finding(
                "ANA-CONST-NOT-CAPS",
                "T1",
                "Nice-to-have",
                f"{plural(len(bad), 'constant')} in `src/default.py` {verb(len(bad))} not ALL_CAPS.",
                "Rename them; the convention marks them as project-wide constants.",
                file="src/default.py",
                detail=rollup(bad),
            )
        )


def check_badge(repo: Path, status: list[str], findings: list, skips: list) -> None:
    """The Analysis status badge exists and reflects the Airtable Status."""
    text = read_text(repo / "README.md")
    if not text:
        skips.append(skipped("ANA-BADGE-MISSING", "no README"))
        return
    head = "\n".join(text.splitlines()[:12])
    badge = re.search(r"!\[[^\]]*\]\(https://img\.shields\.io/badge/([^)]+)\)", head)
    if not badge:
        findings.append(
            finding(
                "ANA-BADGE-MISSING",
                "T1",
                "Should-fix",
                "The README has no status badge under the title.",
                "Add the three-state badge: `pending` (red) → `in progress` (orange) → "
                "`ready` (green).",
                file="README.md",
            )
        )
        return
    label = badge.group(1).replace("%20", " ").lower()
    if "pending" in label:
        parked = {s.lower() for s in status} - {"todo"}
        if parked:
            findings.append(
                finding(
                    "ANA-BADGE-PENDING",
                    "T1",
                    "Should-fix",
                    f"The status badge still says `pending` while Airtable says "
                    f"{', '.join(status)}.",
                    "Move it to `in progress` (orange) or `ready` (green) to match.",
                    file="README.md",
                )
            )


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------


def main() -> int:
    """Run the code checks and write the findings document."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default="/tmp/repo_audit_target.json")
    ap.add_argument("--type", default="Package")
    ap.add_argument(
        "--status", default="", help="comma-separated Airtable Status values"
    )
    ap.add_argument("--out", default="/tmp/repo_audit_code.json")
    ap.add_argument(
        "--no-ruff", action="store_true", help="skip ruff even if installed"
    )
    args = ap.parse_args()

    target = load_target(args.target)
    repo = Path(target["path"])
    rtype = args.type or "Package"
    status = [s.strip() for s in args.status.split(",") if s.strip()]

    tracked = tracked_files(repo)
    pyfiles = python_files(repo, tracked)
    pyproject = load_pyproject(repo)
    readme = read_text(repo / "README.md")

    findings: list[dict] = []
    skips: list[dict] = []

    # Types where Python tooling has nothing to run against. Recorded, not assumed clean.
    python_relevant = rtype in ("Package", "Analysis", "Template") or len(pyfiles) >= 3

    if not pyfiles:
        for cid in (
            "PKG-RUFF-CHECK-FAILS",
            "PKG-DOCSTRING-MISSING",
            "PKG-DOCSTRING-NOT-NUMPY",
            "PKG-UNUSED-IMPORT",
            "PKG-UNUSED-VAR",
            "PKG-DEAD-MODULE-NAME",
            "PKG-BARE-LOGGER",
        ):
            skips.append(skipped(cid, "no tracked Python files"))
    elif not python_relevant:
        for cid in (
            "PKG-DOCSTRING-MISSING",
            "PKG-DOCSTRING-NOT-NUMPY",
            "PKG-DEAD-MODULE-NAME",
        ):
            skips.append(
                skipped(
                    cid,
                    f"{rtype} repo with {plural(len(pyfiles), 'Python file')} — not a package",
                )
            )
    else:
        ruff = None if args.no_ruff else which_ruff()
        if ruff:
            run_ruff(repo, ruff, findings, skips)
        else:
            for cid in (
                "PKG-RUFF-CHECK-FAILS",
                "PKG-RUFF-FORMAT-DIRTY",
                "PKG-DOCSTRING-MISSING",
                "PKG-UNUSED-IMPORT",
                "PKG-UNUSED-VAR",
                "PKG-UNDEFINED-NAME",
            ):
                skips.append(
                    skipped(
                        cid, "ruff is not installed — install it to run the lint checks"
                    )
                )
        check_docstring_sections(repo, pyfiles, findings)
        check_dead_names(repo, pyfiles, pyproject, findings)
        check_logging(repo, pyfiles, findings)
        check_declared_deps(repo, pyfiles, pyproject, findings, skips)

    # A template repo's placeholder package, untouched core.py and `pending` status badge
    # are its whole purpose. Suppress those three visibly; everything else still applies.
    template = is_template_repo(target)

    if rtype == "Package" or (rtype == "Template" and pyproject):
        check_packaging(repo, pyproject, findings, skips)
        check_linters(repo, pyproject, findings, skips)
        check_tests(repo, tracked, findings)
        if template:
            for cid in ("PKG-PLACEHOLDER-PKG", "PKG-UNTOUCHED-CORE"):
                skips.append(
                    skipped(
                        cid,
                        "target is a template repository — the placeholder package is its purpose",
                    )
                )
        else:
            check_placeholder_package(repo, findings)
        check_promised_files(repo, findings)
        check_cli(repo, pyfiles, readme, findings, skips)
    elif rtype == "Analysis":
        check_requirements(repo, findings)
        check_script_numbering(repo, findings, skips)
        check_analysis_scripts(repo, findings, skips)
        check_default_py(repo, findings, skips)
        if template:
            skips.append(
                skipped(
                    "ANA-BADGE-PENDING",
                    "target is a template repository — `pending` is the correct default for an "
                    "untouched template",
                )
            )
        else:
            check_badge(repo, status, findings, skips)
        check_promised_files(repo, findings)
    else:
        skips.append(
            skipped(
                "PKG-*/ANA-*",
                f"type is {rtype} — the Package and Analysis code profiles do not apply; "
                "see references/profile-automation-app.md and profile-workshop-docs.md",
            )
        )

    emit(
        args.out,
        findings,
        skips,
        type=rtype,
        python_files=len(pyfiles),
        ruff=bool(which_ruff()) and not args.no_ruff,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
