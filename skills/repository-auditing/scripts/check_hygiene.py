#!/usr/bin/env python3
"""Repository hygiene: gitignore, eosvc/access.json, junk, datasets, secrets, layout.

Everything here reads the git index rather than the working tree, so a file that is
ignored-but-present does not trip a check while a file that is tracked-but-deleted still
does. The distinction matters: the finding is "git carries this", not "this is on disk".

Exit codes
----------
0   ran to completion
2   bad usage or unreadable target

Usage
-----
    python check_hygiene.py --target /tmp/repo_audit_target.json \\
                            [--type Package] [--out /tmp/repo_audit_hygiene.json]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _common import (
    emit,
    finding,
    lfs_paths,
    load_target,
    plural,
    read_text,
    rollup,
    skipped,
    tracked_files,
    tracked_sizes,
    verb,
    warn,
)

# --------------------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------------------

JUNK_PATTERNS = [
    (r"(^|/)\.DS_Store$", "macOS Finder metadata"),
    (r"(^|/)__pycache__/", "Python bytecode cache"),
    (r"\.pyc$", "compiled Python"),
    (r"(^|/)\.ipynb_checkpoints/", "Jupyter checkpoint"),
    (r"(^|/)tmp/", "temporary directory — gitignored by convention"),
    (
        r"\.old\.(md|py|txt|csv|json|ya?ml)$",
        "superseded file kept alongside the current one",
    ),
    (r"\.(orig|rej|bak|swp)$", "merge or editor leftover"),
    (r"(^|/)\.vscode/", "editor settings"),
    (r"(^|/)\.idea/", "editor settings"),
    (r"(^|/)Thumbs\.db$", "Windows thumbnail cache"),
    (r"(^|/)\.jupyter_ystore\.db$", "Jupyter collaboration store"),
]

DATA_EXTS = {
    ".csv",
    ".tsv",
    ".parquet",
    ".h5",
    ".hdf5",
    ".pkl",
    ".pickle",
    ".joblib",
    ".npy",
    ".npz",
    ".sqlite",
    ".db",
    ".feather",
    ".arrow",
    ".sdf",
    ".mol2",
}
DATA_DIRS = ("data/", "output/", "outputs/", "results/")

# Paths where a data file is shipped payload rather than a committed dataset: package
# example inputs, test fixtures, reference tables the code loads at runtime.
FIXTURE_DIRS = re.compile(
    r"(^|/)(examples?|fixtures?|tests?|test|assets|templates?)(/|$)"
)

# Files whose mere presence in the index is a leak.
SECRET_NAMES = [
    (r"(^|/)\.env$", ".env file"),
    (r"(^|/)\.env\.[^/]*$", ".env variant"),
    (r"\.pem$", "PEM key material"),
    (r"\.p12$", "PKCS#12 keystore"),
    (r"\.pfx$", "PKCS#12 keystore"),
    (r"(^|/)id_rsa$", "private SSH key"),
    (r"(^|/)id_ed25519$", "private SSH key"),
    (r"(^|/)credentials\.json$", "credentials file"),
    (r"(^|/)service[-_]account[^/]*\.json$", "GCP service-account key"),
    (r"(^|/)\.npmrc$", "npm auth config"),
    (r"(^|/)\.pypirc$", "PyPI auth config"),
    (r"(^|/)\.netrc$", "netrc credentials"),
]

# Credential-shaped literals. Deliberately narrow — a broad entropy heuristic on a
# scientific codebase produces mostly false positives on hashes and SMILES strings.
SECRET_CONTENT = [
    (r"gh[pousr]_[A-Za-z0-9]{36,}", "GitHub token"),
    (r"github_pat_[A-Za-z0-9_]{22,}", "GitHub fine-grained PAT"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key id"),
    (r"\bASIA[0-9A-Z]{16}\b", "AWS temporary access key id"),
    (r"\bsk-[A-Za-z0-9]{32,}\b", "OpenAI-style secret key"),
    (r"\bsk-ant-[A-Za-z0-9_-]{20,}", "Anthropic API key"),
    (r"\bxox[abposr]-[A-Za-z0-9-]{10,}", "Slack token"),
    (r"\bkey[A-Za-z0-9]{14}\b", "Airtable API key (legacy)"),
    (r"\bpat[A-Za-z0-9]{14}\.[A-Za-z0-9]{40,}", "Airtable personal access token"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----", "inline private key"),
    (
        r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*[\"'][^\"'\s${}]{12,}[\"']",
        "hardcoded credential assignment",
    ),
]

# Files that legitimately contain credential-shaped example text.
SECRET_SCAN_SKIP = re.compile(
    r"(^|/)(\.gitignore|\.gitattributes|LICENSE|poetry\.lock|uv\.lock|"
    r"package-lock\.json|yarn\.lock|Pipfile\.lock)$|"
    r"(^|/)(tests?|test)/|\.lock$"
)

# The closed set of root-level directories an Analysis repo may have. The analysis
# template's CLAUDE.md states this as a prohibition, which is why a breach is a Blocker.
ANALYSIS_ROOT_DIRS = {
    "data",
    "scripts",
    "notebooks",
    "assets",
    "output",
    "src",
    "tools",
    "docs",
    "tmp",
}
# Tolerated everywhere regardless of type.
ALWAYS_OK_ROOT_DIRS = {".github", ".git", "figures", "img", "images"}

MAX_TRACKED_BYTES = 5 * 1024 * 1024
MAX_DATA_BYTES = 1024 * 1024
# Below this, a tracked data file is a convention breach rather than bloat.
SMALL_DATA_BYTES = 64 * 1024


# --------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------


def gitignore_entries(repo: Path) -> list[str]:
    """Non-comment lines of the root `.gitignore`."""
    text = read_text(repo / ".gitignore")
    return [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]


def is_ignored(repo: Path, path: str) -> bool:
    """True if git would ignore `path`. Uses `git check-ignore`, the authoritative answer."""
    from _common import run

    proc = run(["git", "-C", str(repo), "check-ignore", "-q", path])
    return proc.returncode == 0


def is_ignored_dir(repo: Path, directory: str) -> bool:
    """True if git would ignore the *contents* of `directory`.

    `git check-ignore data` reports "not ignored" even when `.gitignore` contains `data/`,
    because the bare directory name is not itself an ignorable path. Probing a
    hypothetical file inside gives the answer that actually matters — whether a dataset
    dropped in there would be picked up by git.
    """
    return is_ignored(repo, f"{directory.rstrip('/')}/.repo-audit-probe")


def has_real_content(path: Path) -> bool:
    """True if `path` holds anything other than placeholder `.gitkeep` files.

    A `data/` whose only contents are `raw/.gitkeep` and `processed/.gitkeep` is still an
    empty scaffold, so its own `.gitkeep` is not stale.
    """
    if not path.is_dir():
        return False
    for child in path.iterdir():
        if child.name in (".gitkeep", ".gitignore.keep", ".DS_Store"):
            continue
        if child.is_dir():
            if has_real_content(child):
                return True
            continue
        return True
    return False


def check_gitignore(repo: Path, findings: list) -> None:
    """A root .gitignore exists."""
    if not (repo / ".gitignore").is_file():
        findings.append(
            finding(
                "T0-GITIGNORE-MISSING",
                "T0",
                "Blocker",
                "The repository has no .gitignore.",
                "Add one from the GitHub Python template, with the Ersilia block on top: "
                "`data/`, `output/`, `tmp/`, `.DS_Store`.",
            )
        )


def check_junk(repo: Path, tracked: list[str], findings: list) -> None:
    """Editor, OS and build detritus carried in the index."""
    hits: dict[str, list[str]] = {}
    for rel in tracked:
        # A tracked `.gitkeep` is how the templates preserve an otherwise-empty directory,
        # including inside `tmp/`. Staleness is judged separately, by check_stale_gitkeep.
        if Path(rel).name in (".gitkeep", ".gitignore.keep"):
            continue
        for pattern, what in JUNK_PATTERNS:
            if re.search(pattern, rel):
                hits.setdefault(what, []).append(rel)
                break
    if hits:
        detail = "; ".join(f"{what}: {rollup(paths)}" for what, paths in hits.items())
        total = sum(len(v) for v in hits.values())
        findings.append(
            finding(
                "T0-JUNK-TRACKED",
                "T0",
                "Should-fix",
                f"git tracks {plural(total, 'file')} that should be ignored.",
                "`git rm --cached` them and add the matching patterns to `.gitignore`.",
                detail=detail,
            )
        )


def check_data_in_git(repo: Path, sizes: dict[str, int], findings: list) -> None:
    """Datasets and large binaries in the index.

    `data/` is gitignored on purpose across the org and eosvc backs it with S3, so a
    tracked dataset means either the ignore rule is missing or someone forced an add.
    """
    lfs = lfs_paths(repo)

    def is_lfs(rel: str) -> bool:
        return any(
            rel == pat or rel.endswith(pat.lstrip("*")) or Path(rel).match(pat)
            for pat in lfs
        )

    datasets: list[str] = []
    large: list[str] = []
    for rel, size in sizes.items():
        ext = Path(rel).suffix.lower()
        in_data_dir = rel.startswith(DATA_DIRS)
        # A data-extension file inside a package's own examples/fixtures is shipped
        # payload, not a committed dataset — `ersilia/io/types/examples/protein.tsv` is a
        # 2.5 MB reference input the package needs at runtime. Only flag those once they
        # cross the hard size ceiling, which `T0-LARGE-FILE` handles.
        shipped = bool(FIXTURE_DIRS.search(rel))
        if ext in DATA_EXTS and (
            in_data_dir or (size > MAX_DATA_BYTES and not shipped)
        ):
            datasets.append(f"{rel} ({size // 1024} KB)")
        elif size > MAX_TRACKED_BYTES and not is_lfs(rel):
            large.append(f"{rel} ({size // (1024 * 1024)} MB)")

    if datasets:
        # Severity scales with size. A real dataset in git is a Blocker; a tiny example CSV
        # under `data/` breaches the convention without bloating anything, so it is a
        # Should-fix. `ersilia-app`'s 0 KB `data/example.csv` is the case that matters here —
        # reporting it at the same severity as a 50 MB dump would be misleading.
        big = any(
            sizes.get(d.rsplit(" (", 1)[0], 0) > SMALL_DATA_BYTES for d in datasets
        )
        severity = "Blocker" if big else "Should-fix"
        findings.append(
            finding(
                "T0-DATA-TRACKED",
                "T0",
                severity,
                f"git tracks {plural(len(datasets), 'dataset file')} in a data or output directory.",
                "Remove them from the index and back the directory with `eosvc` instead. "
                'The rule is explicit: "Do not commit datasets, model artefacts, or large '
                'binaries to git."'
                + (
                    ""
                    if big
                    else " These are all small, so nothing is bloated — but `data/` is "
                    "gitignored by convention across the org, and a tracked file there means "
                    "the convention has been bypassed. If these are fixtures the code needs at "
                    "runtime, move them out of `data/` into an `examples/` directory."
                ),
                detail=rollup(datasets),
            )
        )
    if large:
        findings.append(
            finding(
                "T0-LARGE-FILE",
                "T0",
                "Blocker",
                f"git tracks {plural(len(large), 'file')} over 5 MB without git-lfs.",
                "Move them to eosvc/S3, or track them with git-lfs if they genuinely belong "
                "in the repo (e.g. model checkpoints).",
                detail=rollup(large),
            )
        )


def check_secrets(
    repo: Path, tracked: list[str], sizes: dict[str, int], findings: list
) -> None:
    """Credential files and credential-shaped literals in the index."""
    by_name: list[str] = []
    for rel in tracked:
        for pattern, what in SECRET_NAMES:
            if re.search(pattern, rel):
                by_name.append(f"`{rel}` ({what})")
                break

    by_content: list[str] = []
    for rel in tracked:
        if SECRET_SCAN_SKIP.search(rel):
            continue
        if sizes.get(rel, 0) > 512_000:
            continue
        fp = repo / rel
        if not fp.is_file() or fp.suffix.lower() in (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".pdf",
            ".ico",
            ".woff",
            ".woff2",
            ".so",
            ".dylib",
        ):
            continue
        text = read_text(fp)
        if not text:
            continue
        for pattern, what in SECRET_CONTENT:
            m = re.search(pattern, text)
            if m:
                line_no = text[: m.start()].count("\n") + 1
                by_content.append(f"`{rel}:{line_no}` ({what})")
                break

    hits = by_name + by_content
    if hits:
        findings.append(
            finding(
                "T0-SECRETS",
                "T0",
                "Blocker",
                f"git tracks {plural(len(hits), 'file')} that {verb(len(hits), 'appears', 'appear')} "
                "to carry credentials.",
                "Treat every one as compromised: rotate the credential first, then purge it "
                "from history (`git filter-repo`) — deleting the file in a new commit is not "
                "enough. Add the path to `.gitignore`.",
                detail="; ".join(hits[:40])
                + (f" (+{len(hits) - 40} more)" if len(hits) > 40 else ""),
            )
        )


def check_access_json(repo: Path, rtype: str, findings: list, skips: list) -> None:
    """eosvc's access.json exists and matches the gitignored data directories."""
    ignored_data = [
        d
        for d in ("data", "output", "outputs")
        if (repo / d).exists() and is_ignored_dir(repo, d)
    ]
    path = repo / "access.json"

    if not path.is_file():
        if ignored_data:
            check_id = (
                "ANA-NO-ACCESS-JSON" if rtype == "Analysis" else "PKG-NO-ACCESS-JSON"
            )
            findings.append(
                finding(
                    check_id,
                    "T1",
                    "Should-fix",
                    f"`{'`, `'.join(ignored_data)}` is gitignored but there is no access.json.",
                    "Add `access.json` declaring each eosvc-backed directory, e.g. "
                    '`{"data": "public"}`, so the bucket visibility is recorded.',
                )
            )
        else:
            skips.append(
                skipped("ANA-NO-ACCESS-JSON", "no gitignored data directory to declare")
            )
        return

    try:
        decl = json.loads(read_text(path))
    except json.JSONDecodeError as e:
        findings.append(
            finding(
                "ANA-ACCESS-JSON-MISMATCH",
                "T1",
                "Should-fix",
                f"access.json is not valid JSON ({e.msg} at line {e.lineno}).",
                "Fix the syntax — eosvc cannot read it as it stands.",
                file="access.json",
            )
        )
        return
    if not isinstance(decl, dict):
        findings.append(
            finding(
                "ANA-ACCESS-JSON-MISMATCH",
                "T1",
                "Should-fix",
                "access.json is not a JSON object.",
                'It maps directory name to visibility, e.g. `{"data": "public"}`.',
                file="access.json",
            )
        )
        return

    problems: list[str] = []
    for key, value in decl.items():
        if value not in ("public", "private"):
            problems.append(
                f"`{key}` has visibility `{value}` (expected `public` or `private`)"
            )
        if not (repo / key).exists():
            problems.append(f"`{key}` is declared but does not exist in the repo")
    for d in ignored_data:
        if d not in decl:
            problems.append(f"`{d}` is gitignored but not declared")
    if problems:
        findings.append(
            finding(
                "ANA-ACCESS-JSON-MISMATCH",
                "T1",
                "Should-fix",
                f"access.json does not match the repository ({plural(len(problems), 'issue')}).",
                "Align the keys with the eosvc-backed directories. Note the template uses "
                "`output` (singular) — `outputs` is drift.",
                file="access.json",
                detail="; ".join(problems),
            )
        )


def check_stale_gitkeep(repo: Path, tracked: list[str], findings: list) -> None:
    """A .gitkeep left behind in a directory that now has real content."""
    keeps = [r for r in tracked if Path(r).name in (".gitkeep", ".gitignore.keep")]
    stale: list[str] = []
    for keep in keeps:
        parent = Path(keep).parent
        # Real content includes untracked files: an eosvc-backed directory holds data git
        # never sees, and the .gitkeep is redundant there too.
        if has_real_content(repo / parent):
            stale.append(keep)
    if stale:
        findings.append(
            finding(
                "ANA-STALE-GITKEEP",
                "T1",
                "Should-fix",
                f"{plural(len(stale), '`.gitkeep` file')} {verb(len(stale), 'sits', 'sit')} in "
                "directories that now have content.",
                'Delete them. The rule: "As soon as a folder contains data or files, remove '
                'the `.gitkeep` since it is no longer needed."',
                detail=rollup(stale),
            )
        )


def check_analysis_layout(repo: Path, findings: list) -> None:
    """The closed set of root-level directories for an Analysis repo."""
    extras: list[str] = []
    for child in sorted(repo.iterdir()):
        if not child.is_dir():
            continue
        n = child.name
        if n.startswith(".") or n in ALWAYS_OK_ROOT_DIRS or n in ANALYSIS_ROOT_DIRS:
            continue
        if n in (
            "__pycache__",
            "node_modules",
            "venv",
            ".venv",
            "build",
            "dist",
            "egg-info",
        ):
            continue
        extras.append(n + "/")
    if extras:
        findings.append(
            finding(
                "ANA-EXTRA-ROOT-DIR",
                "T1",
                "Blocker",
                f"{plural(len(extras), 'root-level directory', 'root-level directories')} "
                f"{verb(len(extras), 'falls', 'fall')} outside the analysis template set.",
                "Fold them into `src/`, `scripts/`, `tools/` or `docs/`. The template is "
                'explicit: "Do not create new folders at the root level outside the ones '
                'listed above." Ask before deleting anything.',
                detail=rollup(extras),
            )
        )


def check_documented_dirs(repo: Path, findings: list) -> None:
    """Directories the README or CLAUDE.md documents but that do not exist.

    `eos-analysis-template` documents `src/`, `tools/` and `output/` in both files and
    ships none of the three.
    """
    documented: set[str] = set()
    for doc in ("README.md", "CLAUDE.md"):
        text = read_text(repo / doc)
        if not text:
            continue
        # Directory names inside a fenced tree block, e.g. "├── scripts/  # comment".
        for m in re.finditer(
            r"^[│├└─\s]*([a-zA-Z][\w.-]*)/\s*(?:#.*)?$", text, re.MULTILINE
        ):
            documented.add(m.group(1))
    missing = sorted(
        d for d in documented if d in ANALYSIS_ROOT_DIRS and not (repo / d).exists()
    )
    if missing:
        findings.append(
            finding(
                "ANA-EMPTY-DOC-DIR",
                "T1",
                "Should-fix",
                f"{plural(len(missing), 'directory', 'directories')} "
                f"{verb(len(missing), 'is', 'are')} documented but do not exist: "
                + ", ".join(f"`{d}/`" for d in missing)
                + ".",
                "Either create them with a `.gitkeep`, or remove them from the documented "
                "structure so the docs match the repo.",
            )
        )


def check_notebooks(repo: Path, tracked: list[str], findings: list) -> None:
    """Committed notebooks carrying cell outputs."""
    dirty: list[str] = []
    for rel in tracked:
        if not rel.endswith(".ipynb"):
            continue
        try:
            nb = json.loads(read_text(repo / rel))
        except (json.JSONDecodeError, ValueError):
            continue
        cells = nb.get("cells") or []
        if any(c.get("outputs") or c.get("execution_count") is not None for c in cells):
            dirty.append(rel)
    if dirty:
        findings.append(
            finding(
                "ANA-NOTEBOOK-OUTPUTS",
                "T1",
                "Should-fix",
                f"{plural(len(dirty), 'committed notebook')} {verb(len(dirty), 'carries', 'carry')} "
                "cell outputs.",
                "Clear outputs before committing — they bloat diffs and can leak data. "
                "Consider an nbstripout pre-commit hook.",
                detail=rollup(dirty),
            )
        )


def main() -> int:
    """Run the hygiene checks and write the findings document."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default="/tmp/repo_audit_target.json")
    ap.add_argument("--type", default="Package")
    ap.add_argument(
        "--status",
        default="",
        help="comma-separated Airtable Status values; accepted for a uniform call shape "
        "across all checkers even where unused",
    )
    ap.add_argument("--out", default="/tmp/repo_audit_hygiene.json")
    args = ap.parse_args()

    target = load_target(args.target)
    repo = Path(target["path"])
    rtype = args.type or "Package"

    tracked = tracked_files(repo)
    if not tracked:
        warn("git tracks no files; hygiene checks will be vacuous")
    sizes = tracked_sizes(repo)

    findings: list[dict] = []
    skips: list[dict] = []

    check_gitignore(repo, findings)
    check_junk(repo, tracked, findings)
    check_data_in_git(repo, sizes, findings)
    check_secrets(repo, tracked, sizes, findings)
    check_access_json(repo, rtype, findings, skips)
    check_stale_gitkeep(repo, tracked, findings)

    if rtype == "Analysis":
        check_analysis_layout(repo, findings)
        check_documented_dirs(repo, findings)
        for d in ("data", "output"):
            if (repo / d).exists() and not is_ignored_dir(repo, d):
                findings.append(
                    finding(
                        "ANA-DATA-NOT-IGNORED",
                        "T1",
                        "Blocker",
                        f"`{d}/` exists but is not gitignored.",
                        f"Add `{d}/` to `.gitignore` and back it with eosvc. Git tracks code "
                        "only; eosvc tracks data.",
                    )
                )
    else:
        for cid in ("ANA-EXTRA-ROOT-DIR", "ANA-EMPTY-DOC-DIR", "ANA-DATA-NOT-IGNORED"):
            skips.append(skipped(cid, f"not an Analysis repo (type={rtype})"))

    # Teaching material is meant to ship with outputs visible.
    if rtype == "Workshop":
        skips.append(
            skipped(
                "ANA-NOTEBOOK-OUTPUTS",
                "Workshop repo — saved notebook outputs are the point",
            )
        )
    else:
        check_notebooks(repo, tracked, findings)

    emit(args.out, findings, skips, type=rtype, tracked_count=len(tracked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
