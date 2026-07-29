"""Shared utilities for the repository-auditing checker scripts.

Standard library only. The checkers shell out to `git`, `gh` and `ruff` rather than
importing anything heavy, so this module must stay importable in any interpreter on the
host. Forked from `skills/github-digest/scripts/_common.py` (copy-and-adapt is the
convention in this repo — there is no shared `lib/`), with the findings model and the
tracked-file helpers added.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

# --------------------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------------------


def warn(msg: str) -> None:
    """Log a warning to stderr; scripts call this on partial failure."""
    print(f"WARNING: {msg}", file=sys.stderr, flush=True)


def die(msg: str, code: int = 2) -> None:
    """Print an error to stderr and exit with `code`."""
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(code)


# --------------------------------------------------------------------------------------
# Findings model
# --------------------------------------------------------------------------------------

SEVERITIES = ("Blocker", "Should-fix", "Nice-to-have")
TIERS = ("T0", "T1", "T2")


def finding(
    check_id: str,
    tier: str,
    severity: str,
    summary: str,
    fix: str,
    file: str | None = None,
    line: int | None = None,
    detail: str | None = None,
    confidence: str = "high",
) -> dict:
    """Build one finding record.

    Parameters
    ----------
    check_id : str
        Stable id from `references/checks.md`, e.g. `T0-FOOTER-DRIFT`.
    tier : str
        One of `T0`, `T1`, `T2`.
    severity : str
        One of `Blocker`, `Should-fix`, `Nice-to-have`.
    summary : str
        One sentence stating the defect, in the repo's own terms.
    fix : str
        What to do about it, concretely.
    file : str, optional
        Repo-relative path the finding anchors to.
    line : int, optional
        1-indexed line number within `file`.
    detail : str, optional
        Evidence — a quoted line, a diff, a list of offenders.
    confidence : str
        `high` for tool-derived findings, `medium` for heuristics that can be fooled
        (e.g. the AST dead-name pass). Rendered so a reader can weight it.

    Returns
    -------
    dict
        The finding, ready to be JSON-serialised.
    """
    if tier not in TIERS:
        raise ValueError(f"bad tier {tier!r}")
    if severity not in SEVERITIES:
        raise ValueError(f"bad severity {severity!r}")
    out = {
        "id": check_id,
        "tier": tier,
        "severity": severity,
        "summary": summary,
        "fix": fix,
        "confidence": confidence,
    }
    if file:
        out["file"] = file
    if line is not None:
        out["line"] = line
    if detail:
        out["detail"] = detail
    return out


def skipped(check_id: str, reason: str) -> dict:
    """Record a check that could not run, so the report can say so explicitly."""
    return {"id": check_id, "reason": reason}


def emit(out_path: str, findings: list[dict], skips: list[dict], **extra: Any) -> None:
    """Write a checker's result document and print a one-line summary to stderr."""
    doc = {"findings": findings, "skipped": skips, **extra}
    write_json(out_path, doc)
    blockers = sum(1 for f in findings if f["severity"] == "Blocker")
    print(
        f"{Path(out_path).name}: {len(findings)} findings "
        f"({blockers} blockers), {len(skips)} skipped",
        file=sys.stderr,
        flush=True,
    )


# --------------------------------------------------------------------------------------
# Subprocess helpers
# --------------------------------------------------------------------------------------


def run(args: list[str], cwd: str | Path | None = None, timeout: int = 120):
    """Run a command, capturing output. Returns the CompletedProcess.

    Never raises on a non-zero exit — callers inspect `returncode`. A timeout or a
    missing binary is surfaced as a synthetic returncode 127 with the reason on stderr.
    """
    try:
        return subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", f"{args[0]}: not found")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args, 127, "", f"{' '.join(args[:3])}: timed out after {timeout}s"
        )


def _loads_gh(out: str) -> object:
    """Parse gh stdout, tolerating `--paginate` output that concatenates JSON values.

    Older `gh` (pre-2.28) does not merge paginated array responses — it emits one JSON
    array per page back-to-back (`[...][...]`), which is not valid JSON. We decode each
    top-level value in turn; if they are all arrays we concatenate them into one list,
    otherwise we return the list of decoded values.
    """
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    values, idx, n = [], 0, len(out)
    while idx < n:
        while idx < n and out[idx].isspace():
            idx += 1
        if idx >= n:
            break
        obj, end = decoder.raw_decode(out, idx)
        values.append(obj)
        idx = end
    if values and all(isinstance(v, list) for v in values):
        merged: list = []
        for v in values:
            merged.extend(v)
        return merged
    return values


def run_gh_json(args: list[str]) -> tuple[object | None, str]:
    """Run `gh <args>` expecting JSON on stdout. Returns (parsed_or_None, error_str)."""
    if not shutil.which("gh"):
        return None, "gh CLI is not on PATH; install it and authenticate"
    proc = run(["gh", *args], timeout=180)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout).strip()[:500]
    out = proc.stdout.strip()
    if not out:
        return [], ""
    try:
        return _loads_gh(out), ""
    except (json.JSONDecodeError, ValueError) as e:
        return None, f"non-JSON from gh: {e}"


def which_ruff() -> str | None:
    """Locate a ruff executable.

    `ruff` is often only inside a conda env rather than on the login PATH, so fall back
    to the known conda locations before giving up. Returns the path, or None.
    """
    found = shutil.which("ruff")
    if found:
        return found
    for cand in (
        Path.home() / "miniconda3" / "bin" / "ruff",
        Path.home() / "anaconda3" / "bin" / "ruff",
        Path.home() / ".local" / "bin" / "ruff",
    ):
        if cand.is_file():
            return str(cand)
    return None


# --------------------------------------------------------------------------------------
# Git / repository helpers
# --------------------------------------------------------------------------------------

# A model repo on the Ersilia Model Hub is named `eos` followed by 4 base-36-ish chars,
# e.g. `eos6tg8`, `eos43d6`. They have a rigidly generated structure and their own
# skills (ersilia-model-test, model-incorporation-*), so this skill refuses them.
MODEL_REPO_RE = re.compile(r"^eos[0-9a-z]{4}$", re.IGNORECASE)


def is_model_repo(name: str) -> bool:
    """True if `name` is an Ersilia Model Hub model repo (eosXXXX)."""
    return bool(MODEL_REPO_RE.match((name or "").strip()))


# The repos new projects are generated from. Placeholder names, an unadapted CLAUDE.md and
# a `pending` status badge are their *purpose*, so the checks that hunt for those are
# suppressed here — visibly, via the report's Checks-not-run section.
TEMPLATE_NAMES = {"eos-python-package", "eos-analysis-template", "eos-template"}


def is_template_repo(target: dict) -> bool:
    """True if the audit target is one of the Ersilia template repositories.

    Trusts GitHub's `is_template` flag first, then the known names, then an
    `eos-*-template` naming pattern for templates added later.
    """
    name = (target.get("name") or "").strip()
    if (target.get("github") or {}).get("is_template"):
        return True
    if name in TEMPLATE_NAMES:
        return True
    return name.startswith("eos-") and name.endswith("-template")


def tracked_files(repo: Path) -> list[str]:
    """Repo-relative paths of every file git tracks. Empty list on failure."""
    proc = run(["git", "-C", str(repo), "ls-files", "-z"])
    if proc.returncode != 0:
        warn(f"git ls-files failed in {repo}: {proc.stderr.strip()[:200]}")
        return []
    return [p for p in proc.stdout.split("\0") if p]


def tracked_sizes(repo: Path) -> dict[str, int]:
    """Map repo-relative path -> blob size in bytes, for tracked files.

    Uses `git ls-files -s` plus `git cat-file --batch-check` so the sizes come from the
    index rather than the working tree — this stays correct in a `--filter=blob:none`
    partial clone where blobs may not be local. Falls back to stat() on the working
    tree if the batch call fails.
    """
    ls = run(["git", "-C", str(repo), "ls-files", "-s", "-z"])
    if ls.returncode != 0:
        return {}
    entries: list[tuple[str, str]] = []
    for rec in ls.stdout.split("\0"):
        if not rec:
            continue
        # `<mode> <sha> <stage>\t<path>`
        meta, _, path = rec.partition("\t")
        parts = meta.split()
        if len(parts) >= 2 and path:
            entries.append((parts[1], path))
    if not entries:
        return {}
    # cat-file --batch-check reads object names on stdin, one per line.
    by_sha: dict[str, int] = {}
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "cat-file",
                "--batch-check=%(objectname) %(objectsize)",
            ],
            input="\n".join(sha for sha, _ in entries) + "\n",
            capture_output=True,
            text=True,
            timeout=180,
        )
        for line in proc.stdout.splitlines():
            bits = line.split()
            if len(bits) == 2 and bits[1].isdigit():
                by_sha[bits[0]] = int(bits[1])
    except (OSError, subprocess.SubprocessError) as e:
        warn(f"git cat-file failed in {repo}: {e}")

    sizes: dict[str, int] = {}
    for sha, path in entries:
        if sha in by_sha:
            sizes[path] = by_sha[sha]
        else:
            # Fall back to the working tree (e.g. blob absent in a partial clone).
            fp = repo / path
            if fp.is_file():
                try:
                    sizes[path] = fp.stat().st_size
                except OSError:
                    pass
    return sizes


def lfs_paths(repo: Path) -> set[str]:
    """Paths matched by a git-lfs filter in `.gitattributes`, as literal patterns."""
    ga = repo / ".gitattributes"
    if not ga.is_file():
        return set()
    out: set[str] = set()
    for line in read_text(ga).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "filter=lfs" not in line:
            continue
        out.add(line.split()[0])
    return out


def git_head(repo: Path) -> str:
    """Short HEAD sha, or `unknown`."""
    proc = run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"])
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


# --------------------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------------------


def read_text(path: str | Path) -> str:
    """Read a text file, tolerating encoding problems. Returns '' if unreadable."""
    p = Path(path)
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return ""


def plural(n: int, singular: str, plural_form: str | None = None) -> str:
    """Render a count with a correctly inflected noun: `3 files`, `1 dependency`.

    Exists because `f"{n} dependency(ies)"` is the most visible sign a sentence was generated
    rather than written, and this skill asks other people's READMEs to read as human work.
    Returns count and noun together, since every call site wants both.

    Parameters
    ----------
    n : int
        The count.
    singular : str
        The noun in its singular form.
    plural_form : str, optional
        The plural, when adding `s` is wrong (`dependency` → `dependencies`).

    Returns
    -------
    str
        e.g. `"1 dependency"`, `"13 dependencies"`.
    """
    if n == 1:
        return f"1 {singular}"
    return f"{n} {plural_form or singular + 's'}"


def verb(n: int, singular: str = "is", plural_form: str = "are") -> str:
    """Agreeing verb for a count, so `plural()` call sites read correctly.

    `f"{plural(n, 'file')} {verb(n)} tracked"` gives "1 file is tracked" and "3 files are
    tracked". Defaults to is/are; pass both forms for anything else (`has`/`have`).
    """
    return singular if n == 1 else plural_form


def non_blank_lines(text: str) -> int:
    """Count lines with any non-whitespace content."""
    return sum(1 for line in text.splitlines() if line.strip())


def normalise_prose(text: str) -> str:
    """Collapse whitespace and strip trailing punctuation noise, for prose diffing.

    Used to compare a repo's About-Ersilia paragraph against the canonical one without
    tripping over a rewrapped line.
    """
    return re.sub(r"\s+", " ", text).strip()


def first_line(text: str, limit: int = 160) -> str:
    """First non-blank line of `text`, truncated — for use as finding evidence."""
    for line in text.splitlines():
        if line.strip():
            s = line.strip()
            return s if len(s) <= limit else s[: limit - 1] + "…"
    return ""


def rollup(paths: Iterable[str], limit: int = 40) -> str:
    """Render a list of paths as evidence, truncating with a count.

    The limit is deliberately generous. Display truncation is the renderer's job now — it
    teases two items on the finding line and puts the rest in the Evidence appendix — so a
    checker that trimmed to 8 here made the appendix claim "full detail" while quietly
    holding back 48 paths. Only a pathological case should ever hit this cap.
    """
    items = list(dict.fromkeys(paths))
    shown = items[:limit]
    out = ", ".join(f"`{p}`" for p in shown)
    if len(items) > limit:
        out += f" (+{len(items) - limit} more)"
    return out


# --------------------------------------------------------------------------------------
# TOML
# --------------------------------------------------------------------------------------


class TomlError(Exception):
    """Raised when a TOML document cannot be parsed."""


def load_toml(text: str) -> dict:
    """Parse TOML, preferring a real parser and falling back to a subset reader.

    `tomllib` is only in the standard library from Python 3.11, and neither interpreter on
    a typical Ersilia host has it (system Python is 3.9, the conda one 3.10). Rather than
    add a dependency, fall through to `tomli` if it happens to be installed and otherwise
    to `_toml_subset`, which handles everything `pyproject.toml` and `ruff.toml` use.

    Parameters
    ----------
    text : str
        The document source.

    Returns
    -------
    dict
        The parsed document.

    Raises
    ------
    TomlError
        If the document is malformed.
    """
    try:
        import tomllib  # noqa: PLC0415 — optional, version-dependent

        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError as e:
            raise TomlError(str(e)) from e
    except ImportError:
        pass
    try:
        import tomli  # noqa: PLC0415 — optional third-party fallback

        try:
            return tomli.loads(text)
        except tomli.TOMLDecodeError as e:
            raise TomlError(str(e)) from e
    except ImportError:
        pass
    return _toml_subset(text)


def _strip_comment(line: str) -> str:
    """Remove a trailing `#` comment, respecting quoted strings."""
    out, quote = [], None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\" and quote == '"':
                out.append(line[i : i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def _toml_value(raw: str):
    """Parse a single TOML value: string, number, bool, array or inline table."""
    raw = raw.strip()
    if not raw:
        return ""
    if raw.startswith(('"""', "'''")):
        q = raw[:3]
        return raw[3:-3] if raw.endswith(q) and len(raw) >= 6 else raw[3:]
    if raw[0] in "\"'":
        q = raw[0]
        body = raw[1:-1] if raw.endswith(q) and len(raw) >= 2 else raw[1:]
        return body.replace('\\"', '"').replace("\\'", "'") if q == '"' else body
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if raw.startswith("["):
        return _toml_array(raw)
    if raw.startswith("{"):
        return _toml_inline_table(raw)
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _split_top_level(body: str) -> list[str]:
    """Split a bracketed body on commas that are not nested or quoted."""
    parts, depth, quote, buf = [], 0, None, []
    for ch in body:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _toml_array(raw: str) -> list:
    """Parse a TOML array literal."""
    body = raw.strip()
    if body.startswith("["):
        body = body[1:]
    if body.endswith("]"):
        body = body[:-1]
    return [_toml_value(p) for p in _split_top_level(body)]


def _toml_inline_table(raw: str) -> dict:
    """Parse a TOML inline table literal."""
    body = raw.strip()
    if body.startswith("{"):
        body = body[1:]
    if body.endswith("}"):
        body = body[:-1]
    out: dict = {}
    for part in _split_top_level(body):
        k, _, v = part.partition("=")
        if _:
            out[k.strip().strip("\"'")] = _toml_value(v)
    return out


def _descend(root: dict, path: list[str]) -> dict:
    """Walk (creating as needed) a dotted table path, returning the leaf table."""
    node = root
    for part in path:
        key = part.strip().strip("\"'")
        nxt = node.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            node[key] = nxt
        node = nxt
    return node


def _toml_subset(text: str) -> dict:
    """Parse the subset of TOML that `pyproject.toml` and `ruff.toml` actually use.

    Handles tables and dotted table headers, arrays of tables, dotted keys, multi-line
    arrays, inline tables, and the scalar types. It does not handle multi-line inline
    tables or date/time literals — neither appears in the files this skill reads.
    """
    root: dict = {}
    current = root
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = _strip_comment(lines[i]).strip()
        i += 1
        if not line:
            continue

        if line.startswith("[["):
            name = line[2:].split("]]")[0]
            parts = name.split(".")
            parent = _descend(root, parts[:-1])
            key = parts[-1].strip().strip("\"'")
            bucket = parent.setdefault(key, [])
            if not isinstance(bucket, list):
                bucket = []
                parent[key] = bucket
            current = {}
            bucket.append(current)
            continue

        if line.startswith("["):
            name = line[1:].split("]")[0]
            current = _descend(root, name.split("."))
            continue

        key, sep, value = line.partition("=")
        if not sep:
            continue
        key, value = key.strip(), value.strip()

        # A multi-line array or inline table: keep consuming until brackets balance.
        if value.startswith(("[", "{")):
            opener, closer = ("[", "]") if value.startswith("[") else ("{", "}")
            depth = value.count(opener) - value.count(closer)
            while depth > 0 and i < len(lines):
                nxt = _strip_comment(lines[i])
                i += 1
                value += " " + nxt.strip()
                depth += nxt.count(opener) - nxt.count(closer)
        elif value.startswith(('"""', "'''")) and not value.endswith(value[:3]):
            q = value[:3]
            while i < len(lines) and q not in lines[i]:
                value += "\n" + lines[i]
                i += 1
            if i < len(lines):
                value += "\n" + lines[i]
                i += 1

        target = current
        parts = [p for p in key.split(".") if p]
        if len(parts) > 1:
            target = _descend(current, parts[:-1])
        target[parts[-1].strip().strip("\"'")] = _toml_value(value)
    return root


# --------------------------------------------------------------------------------------
# JSON I/O
# --------------------------------------------------------------------------------------


def write_json(path: str, data: Any) -> None:
    """Write `data` as JSON to `path`, creating parent dirs as needed."""
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def read_json(path: str) -> Any:
    """Read JSON from `path`. Returns `None` if the file is missing or empty."""
    p = Path(path).expanduser().resolve()
    if not p.exists() or p.stat().st_size == 0:
        return None
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_target(path: str) -> dict:
    """Read the target document written by `resolve_target.py`, or exit.

    Every checker starts here, so a missing or malformed target is a hard stop rather
    than a silently empty audit.
    """
    doc = read_json(path)
    if not isinstance(doc, dict) or not doc.get("path"):
        die(f"{path} is missing or has no `path`; run resolve_target.py first")
    repo = Path(doc["path"])
    if not repo.is_dir():
        die(f"target path does not exist: {repo}")
    return doc


# --------------------------------------------------------------------------------------
# Skill-relative paths
# --------------------------------------------------------------------------------------

SKILL_DIR = Path(__file__).resolve().parent.parent


def reference(name: str) -> Path:
    """Absolute path to a file in the skill's `references/` directory."""
    return SKILL_DIR / "references" / name
