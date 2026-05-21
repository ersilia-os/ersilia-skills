"""Build the seen-set of DOIs / arXiv IDs / URLs by reading prior digests from the
canonical remote repository `ersilia-os/digests` (path `literature/`).

The local `digests/` folder is just a working copy and may be missing files that
have already been published. To avoid surfacing items the team has already seen we
read the *remote* history.

Behaviour:
- Lists `literature/` in the remote repo via the `gh` CLI.
- Picks the most-recent N files by the date encoded in the filename.
- Downloads each one and extracts DOIs / arXiv IDs / URLs.
- Emits one identifier per line on stdout (or `--out`), deduplicated.

If the remote `literature/` folder does not exist (first run for the repo layout)
we emit nothing and exit 0. On any other remote error we log a WARNING and exit 1
— the skill must treat that as a hard failure (otherwise a successful seen-set
build using only local files could miss recently-published items, leading to
duplicates in the digest).

The optional `--also-local` flag also includes any files in the local
`digests/` working copy. Useful for development; not used in production runs.

Usage:
    python parse_prior_digests.py [--last N] [--out PATH] [--also-local]
                                  [--repo ersilia-os/digests] [--path literature]
                                  [--ref main]
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from _common import (
    extract_arxiv_ids,
    extract_dois,
    normalise_url,
    warn,
)

URL_REGEX_FROM_TEXT = re.compile(r"https?://[^\s\)\"<>]+")

# Tolerate both spellings of the canonical filename.
DIGEST_FILENAME_RE = re.compile(
    r"^(?P<yy>\d{2})-(?P<mm>\d{2})-(?P<dd>\d{2})-(?:literature-)?digest\.md$"
)


def parse_filename_date(filename: str) -> date | None:
    m = DIGEST_FILENAME_RE.match(filename)
    if not m:
        return None
    yy, mm, dd = int(m.group("yy")), int(m.group("mm")), int(m.group("dd"))
    year = 2000 + yy if yy <= 80 else 1900 + yy
    try:
        return date(year, mm, dd)
    except ValueError:
        return None


def collect_ids_from_text(text: str) -> set[str]:
    out: set[str] = set()
    for d in extract_dois(text):
        out.add(d)
    for a in extract_arxiv_ids(text):
        out.add(a)
    for raw_url in URL_REGEX_FROM_TEXT.findall(text or ""):
        u = normalise_url(raw_url)
        if u:
            out.add(u)
    return out


def gh(args: list[str]) -> subprocess.CompletedProcess:
    if not shutil.which("gh"):
        raise RuntimeError("gh CLI is not on PATH; install it and authenticate")
    return subprocess.run(["gh", *args], capture_output=True)


def list_remote_files(repo: str, path: str, ref: str) -> list[dict] | None:
    """Return the listing of a remote directory, or None if it doesn't exist (404)."""
    proc = gh([
        "api", "-H", "Accept: application/vnd.github+json",
        f"repos/{repo}/contents/{path}?ref={ref}",
    ])
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        if "HTTP 404" in stderr or "Not Found" in stderr:
            return None
        raise RuntimeError(
            f"gh api list failed (exit {proc.returncode}): {stderr.strip()[:400]}"
        )
    data = json.loads(proc.stdout.decode("utf-8"))
    if isinstance(data, dict):
        raise RuntimeError(f"{path!r} is a file, not a directory")
    return data


def fetch_remote_body(repo: str, file_path: str, ref: str) -> str | None:
    """Return the markdown body of a remote file, or None on 404."""
    proc = gh([
        "api", "-H", "Accept: application/vnd.github+json",
        f"repos/{repo}/contents/{file_path}?ref={ref}",
    ])
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        if "HTTP 404" in stderr or "Not Found" in stderr:
            return None
        raise RuntimeError(
            f"gh api file fetch failed (exit {proc.returncode}): "
            f"{stderr.strip()[:400]}"
        )
    data = json.loads(proc.stdout.decode("utf-8"))
    content_b64 = data.get("content") or ""
    encoding = data.get("encoding")
    if encoding != "base64":
        raise RuntimeError(f"unexpected encoding from gh contents API: {encoding!r}")
    try:
        return base64.b64decode(content_b64).decode("utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"could not decode body of {file_path}: {e}") from None


def collect_remote_seen(repo: str, path: str, ref: str, last: int) -> set[str]:
    """Build the seen-set from the most recent `last` digests in the remote repo."""
    files = list_remote_files(repo, path, ref)
    if files is None:
        return set()
    candidates: list[tuple[date, dict]] = []
    for entry in files:
        if entry.get("type") != "file":
            continue
        d = parse_filename_date(entry.get("name") or "")
        if d is None:
            continue
        candidates.append((d, entry))
    candidates.sort(key=lambda t: t[0], reverse=True)
    seen: set[str] = set()
    for _d, entry in candidates[:last]:
        body = fetch_remote_body(repo, entry["path"], ref)
        if not body:
            continue
        seen |= collect_ids_from_text(body)
    return seen


def collect_local_seen(local_dir: Path, last: int) -> set[str]:
    if not local_dir.exists():
        return set()
    files = []
    for f in local_dir.glob("*.md"):
        d = parse_filename_date(f.name)
        if d is None:
            continue
        files.append((d, f))
    files.sort(key=lambda t: t[0], reverse=True)
    seen: set[str] = set()
    for _d, f in files[:last]:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError as e:
            warn(f"could not read {f}: {e}")
            continue
        seen |= collect_ids_from_text(text)
    return seen


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default="ersilia-os/digests",
                   help="Remote repository to read prior digests from.")
    p.add_argument("--path", default="literature",
                   help="Subdirectory inside the repo.")
    p.add_argument("--ref", default="main", help="Branch/tag (default: main).")
    p.add_argument("--last", type=int, default=8,
                   help="How many of the most recent digests to scan (default: 8).")
    p.add_argument("--also-local", action="store_true",
                   help="Additionally include local digests/ working-copy files.")
    p.add_argument(
        "--local-dir",
        default=str(Path(__file__).resolve().parent.parent / "digests"),
        help="Local digests folder (used when --also-local is set).",
    )
    p.add_argument("--out", default="-", help="Output path; `-` means stdout.")
    args = p.parse_args(argv)

    try:
        remote_seen = collect_remote_seen(args.repo, args.path, args.ref, args.last)
    except RuntimeError as e:
        warn(str(e))
        return 1

    seen = set(remote_seen)
    if args.also_local:
        seen |= collect_local_seen(Path(args.local_dir).expanduser().resolve(), args.last)

    out_lines = sorted(seen)
    if args.out == "-":
        for line in out_lines:
            sys.stdout.write(line + "\n")
    else:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
