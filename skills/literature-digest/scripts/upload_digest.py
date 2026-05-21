"""Upload a generated literature digest to the canonical remote location.

Default destination: `ersilia-os/digests` repo, path
`literature/YY-MM-DD-literature-digest.md`. Uses the GitHub contents API via `gh`
so no `git clone` is needed.

After a successful upload, the script also updates the repo's `README.md` to add
the new digest under the `## Literature digests` section, formatted as:

    - [YYYY-MM-DD](literature/YY-MM-DD-literature-digest.md)

The README update is idempotent: if the entry is already present, it is left as
is. Entries are kept in date-descending order (newest first).

The script refuses to overwrite an existing digest file unless `--force` is
passed.

Exit codes:
- 0 on successful upload + README update; the GitHub `html_url` of the digest
  and the README are printed to stdout, one per line, so the skill can hand the
  user clickable links.
- 2 if the remote digest file already exists and `--force` was not passed.
- 1 on any other error (auth, network, malformed input). If the file upload
  succeeded but the README update failed, exit code is also 1 and the failure
  reason is on stderr — the digest will already be visible at its `html_url`.

Usage:
    python upload_digest.py --digest digests/26-05-21-literature-digest.md
    python upload_digest.py --digest digests/26-05-21-literature-digest.md \
                            --message "literature digest for week ending 2026-05-21"
    python upload_digest.py --digest digests/X-literature-digest.md --force
    python upload_digest.py --digest digests/X-literature-digest.md --no-readme
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from _common import warn


FILENAME_RE = re.compile(
    r"^(?P<yy>\d{2})-(?P<mm>\d{2})-(?P<dd>\d{2})-literature-digest\.md$"
)

# Heading inside the README under which literature-digest entries live.
README_SECTION_HEADING = "## Literature digests"

# Existing list entries that look like one of our digests. Match the
# `- [YYYY-MM-DD](literature/YY-MM-DD-literature-digest.md)` shape.
README_ENTRY_RE = re.compile(
    r"^-\s*\[(?P<full>\d{4}-\d{2}-\d{2})\]\((?P<href>literature/[^)]+)\)\s*$"
)


def gh(args: list[str], stdin: bytes | None = None) -> subprocess.CompletedProcess:
    if not shutil.which("gh"):
        raise RuntimeError("gh CLI is not on PATH; install it and authenticate")
    return subprocess.run(
        ["gh", *args],
        input=stdin,
        capture_output=True,
    )


def get_existing_sha(repo: str, remote_path: str, ref: str) -> str | None:
    """Return the blob sha if the file already exists, else None.

    Raises RuntimeError on any error other than HTTP 404.
    """
    proc = gh([
        "api", "-H", "Accept: application/vnd.github+json",
        f"repos/{repo}/contents/{remote_path}?ref={ref}",
    ])
    if proc.returncode == 0:
        try:
            data = json.loads(proc.stdout.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"gh returned non-JSON on existence check: {e}") from None
        sha = data.get("sha") if isinstance(data, dict) else None
        return sha
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    if "HTTP 404" in stderr or "Not Found" in stderr:
        return None
    raise RuntimeError(
        f"gh api failed during existence check (exit {proc.returncode}): "
        f"{stderr.strip()[:400]}"
    )


def put_file(
    repo: str, remote_path: str, content_bytes: bytes, message: str, sha: str | None,
    branch: str | None,
) -> dict:
    """PUT the file via the contents API. Returns the JSON response on success."""
    payload: dict = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("ascii"),
    }
    if sha is not None:
        payload["sha"] = sha
    if branch is not None:
        payload["branch"] = branch
    proc = gh(
        ["api", "-X", "PUT",
         "-H", "Accept: application/vnd.github+json",
         "--input", "-",
         f"repos/{repo}/contents/{remote_path}"],
        stdin=json.dumps(payload).encode("utf-8"),
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        raise RuntimeError(
            f"gh api PUT failed (exit {proc.returncode}): {stderr.strip()[:600]}"
        )
    try:
        return json.loads(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"gh PUT returned non-JSON: {e}") from None


def get_file(repo: str, path: str, ref: str) -> dict | None:
    """Fetch a remote file's full record (sha, content_b64, ...) or None on 404."""
    proc = gh([
        "api", "-H", "Accept: application/vnd.github+json",
        f"repos/{repo}/contents/{path}?ref={ref}",
    ])
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        if "HTTP 404" in stderr or "Not Found" in stderr:
            return None
        raise RuntimeError(
            f"gh api fetch failed (exit {proc.returncode}): {stderr.strip()[:400]}"
        )
    return json.loads(proc.stdout.decode("utf-8"))


def update_readme_index(
    repo: str, branch: str, remote_path: str, filename: str,
) -> str | None:
    """Update the README so it lists the just-uploaded digest. Idempotent.

    `remote_path` is the on-repo path of the digest (e.g.
    `literature/26-05-21-literature-digest.md`); `filename` is just the basename
    used to derive the human-friendly YYYY-MM-DD date.

    Returns the README's html_url on success, or None if the README already
    listed this digest (no commit was made).

    Raises RuntimeError on any failure that should be surfaced to the caller.
    """
    m = FILENAME_RE.match(filename)
    if not m:
        raise RuntimeError(f"cannot derive date from filename: {filename!r}")
    yy, mm, dd = int(m.group("yy")), int(m.group("mm")), int(m.group("dd"))
    year = 2000 + yy if yy <= 80 else 1900 + yy
    iso_date = f"{year:04d}-{mm:02d}-{dd:02d}"

    new_entry = f"- [{iso_date}]({remote_path})"

    record = get_file(repo, "README.md", branch)
    if record is None:
        # First-time setup: create a minimal README.
        readme_text = (
            "# Periodic Ersilia digests\n"
            "Digests of relevance to the Ersilia Open Source Initiative\n\n"
            f"{README_SECTION_HEADING}\n\n"
            f"{new_entry}\n"
        )
        response = put_file(
            repo, "README.md", readme_text.encode("utf-8"),
            f"Initialise README with {filename}", None, branch,
        )
        return (response.get("content") or {}).get("html_url")

    sha = record["sha"]
    text = base64.b64decode(record["content"]).decode("utf-8", errors="replace")

    new_text, changed = _insert_or_skip_readme_entry(text, new_entry, iso_date)
    if not changed:
        return None  # already listed; nothing to do

    response = put_file(
        repo, "README.md", new_text.encode("utf-8"),
        f"Index {filename} in README", sha, branch,
    )
    return (response.get("content") or {}).get("html_url")


def _insert_or_skip_readme_entry(
    readme_text: str, new_entry: str, iso_date: str,
) -> tuple[str, bool]:
    """Return (new_readme_text, changed).

    Behaviour:
    - If the README already has a `- [YYYY-MM-DD](literature/...)` line with the
      same date, return (text, False) — nothing to change.
    - Otherwise locate `## Literature digests`, insert the new entry in
      date-descending order under it, and return (new_text, True).
    - If the heading is absent, append it at the end of the file and add the
      entry.
    """
    lines = readme_text.split("\n")
    # Idempotency check.
    for ln in lines:
        m = README_ENTRY_RE.match(ln.strip())
        if m and m.group("full") == iso_date:
            return readme_text, False

    # Find the heading.
    try:
        heading_idx = next(
            i for i, ln in enumerate(lines)
            if ln.strip() == README_SECTION_HEADING
        )
    except StopIteration:
        # Append a new section at the end.
        appended = readme_text.rstrip() + (
            f"\n\n{README_SECTION_HEADING}\n\n{new_entry}\n"
        )
        return appended, True

    # Walk forward from the heading to find the end of its bullet list.
    i = heading_idx + 1
    # Skip blank lines immediately after the heading.
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    block_start = i
    existing_dates: list[tuple[str, int]] = []
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            # blank line ends the block
            break
        if s.startswith("#"):
            # next heading ends the block
            break
        m = README_ENTRY_RE.match(s)
        if m:
            existing_dates.append((m.group("full"), i))
        i += 1
    block_end = i  # exclusive

    if existing_dates:
        # Insert before the first existing entry whose date < iso_date
        insert_at = block_end
        for d, idx in existing_dates:
            if iso_date > d:
                insert_at = idx
                break
        lines.insert(insert_at, new_entry)
    else:
        # Empty section — insert right at block_start, ensuring a blank line
        # after the heading is preserved.
        lines.insert(block_start, new_entry)

    return "\n".join(lines), True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--digest", required=True,
                   help="Local path to the digest markdown file to upload.")
    p.add_argument("--repo", default="ersilia-os/digests",
                   help="Remote repository (owner/name).")
    p.add_argument("--remote-dir", default="literature",
                   help="Path inside the repo where digests live.")
    p.add_argument("--branch", default="main",
                   help="Branch to commit to. Default: main.")
    p.add_argument("--message", default=None,
                   help="Commit message. Default derived from the filename.")
    p.add_argument("--force", action="store_true",
                   help="Overwrite the remote file if it already exists.")
    p.add_argument("--no-readme", action="store_true",
                   help="Skip the README index update step.")
    args = p.parse_args(argv)

    local = Path(args.digest).expanduser().resolve()
    if not local.exists():
        warn(f"digest file not found: {local}")
        return 1
    if not FILENAME_RE.match(local.name):
        warn(
            f"digest filename {local.name!r} does not match "
            f"YY-MM-DD-literature-digest.md — refusing to upload to a non-canonical name"
        )
        return 1

    content_bytes = local.read_bytes()
    remote_path = f"{args.remote_dir.strip('/')}/{local.name}"
    commit_message = args.message or f"Add {local.name} (literature digest)"

    try:
        existing_sha = get_existing_sha(args.repo, remote_path, args.branch)
    except RuntimeError as e:
        warn(str(e))
        return 1

    if existing_sha is not None and not args.force:
        warn(
            f"remote file already exists: https://github.com/{args.repo}/blob/{args.branch}/{remote_path}"
        )
        warn("refusing to overwrite without --force")
        return 2

    try:
        response = put_file(
            args.repo, remote_path, content_bytes,
            commit_message, existing_sha if args.force else None,
            args.branch,
        )
    except RuntimeError as e:
        warn(str(e))
        return 1

    # The contents API returns content.html_url and content.download_url.
    content = response.get("content") or {}
    html_url = content.get("html_url") or f"https://github.com/{args.repo}/blob/{args.branch}/{remote_path}"
    download_url = content.get("download_url") or ""
    print(html_url)
    if download_url:
        print(download_url)

    if args.no_readme:
        return 0

    try:
        readme_url = update_readme_index(
            args.repo, args.branch, remote_path, local.name,
        )
    except RuntimeError as e:
        warn(f"digest uploaded, but README index update failed: {e}")
        return 1
    if readme_url:
        print(readme_url)
    else:
        warn(f"README already listed {local.name}; left unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
