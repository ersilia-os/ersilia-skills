"""Fetch what the drift checks compare: the docs and the live code they describe.

- Clones `ersilia-book` (full history, blobless, for page owners) and `ersilia`
  (shallow) into `--workdir`, replacing any earlier copy.
- Lists every repo in the org (name, archived, default branch).
- Reads `README.md` and `pyproject.toml` of every non-archived, non-model repo through
  batched GraphQL (25 repos per query). Workshop repos (name contains `workshop`) are
  skipped: they are event material, kept as they were on the day.
- Parses the `ersilia` CLI source (click decorators in `ersilia/cli/commands/`) into
  commands and their options, without installing anything.

Read-only. Writes `--out` (default `<workdir>/sources.json`).

Exit codes: 0 on success, 1 if a required source could not be fetched.

Usage:
    python fetch_sources.py --workdir /tmp/docs-drift
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import tomllib

from _common import ORG, is_model_repo, run_gh_json, warn, write_json

BATCH = 25
GLOBAL_FLAGS = ["-v", "--verbose", "--version", "-h", "--help"]


def is_workshop(name: str) -> bool:
    return "workshop" in name.lower()


def clone(repo: str, dest: Path, full_history: bool) -> bool:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    extra = ["--filter=blob:none"] if full_history else ["--depth", "1"]
    proc = subprocess.run(
        ["git", "clone", "-q", *extra, f"https://github.com/{ORG}/{repo}", str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        warn(f"clone {repo} failed: {proc.stderr.strip()[:300]}")
    return proc.returncode == 0


def list_repos() -> dict[str, dict] | None:
    data, err = run_gh_json(
        [
            "repo",
            "list",
            ORG,
            "--limit",
            "2000",
            "--json",
            "name,isArchived,defaultBranchRef",
        ]
    )
    if not isinstance(data, list):
        warn(f"repo list failed: {err}")
        return None
    return {
        r["name"]: {
            "archived": r["isArchived"],
            "default_branch": (r.get("defaultBranchRef") or {}).get("name") or "main",
        }
        for r in data
    }


def python_requirement(doc: dict) -> str | None:
    project = doc.get("project") or {}
    if project.get("requires-python"):
        return project["requires-python"]
    poetry = ((doc.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
    py = poetry.get("python")
    return py if isinstance(py, str) else None


def package_name(doc: dict) -> str | None:
    return (doc.get("project") or {}).get("name") or (
        ((doc.get("tool") or {}).get("poetry") or {}).get("name")
    )


def fetch_files(names: list[str]) -> tuple[dict, dict, list[str]]:
    """README text and pyproject facts per repo, via batched GraphQL."""
    readmes: dict[str, str] = {}
    pyprojects: dict[str, dict] = {}
    errors: list[str] = []
    for start in range(0, len(names), BATCH):
        chunk = names[start : start + BATCH]
        parts = [
            f'r{i}: repository(owner: "{ORG}", name: "{n}") {{ name '
            'readme: object(expression: "HEAD:README.md") { ... on Blob { text } } '
            'pyproject: object(expression: "HEAD:pyproject.toml") '
            "{ ... on Blob { text } } }"
            for i, n in enumerate(chunk)
        ]
        query = "query {" + " ".join(parts) + "}"
        data, err = run_gh_json(["api", "graphql", "-f", f"query={query}"])
        if not isinstance(data, dict) or "data" not in data:
            errors.append(f"files for {chunk[0]}..{chunk[-1]}: {err}")
            continue
        for node in (data.get("data") or {}).values():
            if not node:
                continue
            name = node["name"]
            if (node.get("readme") or {}).get("text"):
                readmes[name] = node["readme"]["text"]
            text = (node.get("pyproject") or {}).get("text")
            if text:
                try:
                    doc = tomllib.loads(text)
                except tomllib.TOMLDecodeError:
                    continue
                pyprojects[name] = {
                    "package": package_name(doc),
                    "requires_python": python_requirement(doc),
                }
    return readmes, pyprojects, errors


def _strings(node: ast.AST) -> list[str]:
    return [
        a.value
        for a in getattr(node, "args", [])
        if isinstance(a, ast.Constant) and isinstance(a.value, str)
    ]


def parse_cli(commands_dir: Path) -> dict[str, list[str]]:
    """Map each `ersilia` command to its option strings, from the click decorators."""
    commands: dict[str, list[str]] = {}
    for py in sorted(commands_dir.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            name, options = None, []
            for dec in fn.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                target = ast.unparse(dec.func)
                if target.endswith("ersilia_cli.command"):
                    name = fn.name.replace("_", "-")
                    for kw in dec.keywords:
                        if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                            name = kw.value.value
                elif target.endswith(".option"):
                    for s in _strings(dec):
                        # "--enable_cache/--disable_cache" declares two flags.
                        options += [o for o in s.split("/") if o.startswith("-")]
            if name:
                commands[name] = sorted(set(options) | {"-h", "--help"})
    return commands


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--workdir", default="/tmp/docs-drift")
    p.add_argument("--out", default=None)
    p.add_argument("--skip-readmes", action="store_true", help="only the Book (faster)")
    args = p.parse_args(argv)
    work = Path(args.workdir).expanduser()
    out = Path(args.out) if args.out else work / "sources.json"

    ok_book = clone("ersilia-book", work / "src" / "ersilia-book", full_history=True)
    ok_cli = clone("ersilia", work / "src" / "ersilia", full_history=False)
    repos = list_repos()
    if not (ok_book and ok_cli and repos):
        print(
            "ERROR: could not fetch the Book, the CLI or the repo list", file=sys.stderr
        )
        return 1

    cli = parse_cli(work / "src" / "ersilia" / "ersilia" / "cli" / "commands")
    readmes, pyprojects, errors = {}, {}, []
    if not args.skip_readmes:
        names = sorted(
            n
            for n, r in repos.items()
            if not r["archived"] and not is_model_repo(n) and not is_workshop(n)
        )
        readmes, pyprojects, errors = fetch_files(names)
    else:
        # The python-version check still needs the main packages' requirements.
        _, pyprojects, errors = fetch_files(["ersilia"])

    write_json(
        out,
        {
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "org": ORG,
            "workdir": str(work),
            "book_dir": str(work / "src" / "ersilia-book"),
            "repos": repos,
            "cli": {"commands": cli, "global_flags": GLOBAL_FLAGS},
            "readmes": readmes,
            "pyprojects": pyprojects,
            "errors": errors,
        },
    )
    print(
        json.dumps(
            {
                "repos": len(repos),
                "cli_commands": sorted(cli),
                "readmes": len(readmes),
                "pyprojects": len(pyprojects),
                "errors": errors,
                "out": str(out),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
