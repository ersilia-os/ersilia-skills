"""Run Claude Code's own ``/doctor prompt-audit`` on each file. Optional, read-only.

The audit checks an instruction file against the repository it lives in (outdated
wording, rules the repo already breaks, broken references), which the scripts here
cannot do. Each template is shallow-cloned into a throwaway directory under the work
directory and audited there, so nothing it does can reach a real repository; the org
file is audited on its own in an empty directory. Output goes to ``audit-<id>.md`` for
the judgement step (SKILL.md, Step 4). Costs one headless Claude Code run per file.

Usage:
    python run_prompt_audit.py [--work /tmp/org_context] [--only pkg,ana] [--timeout 600]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from _common import WORK_DIR, load_work, run_gh, warn


def prepare(t: dict, text: str, base: Path) -> Path | None:
    """A throwaway directory holding the file in its repository context."""
    target = base / t["id"]
    shutil.rmtree(target, ignore_errors=True)
    if t["role"] == "org":
        target.mkdir(parents=True)
        (target / "CLAUDE.md").write_text(text, encoding="utf-8")
        return target
    _, err = run_gh(
        ["repo", "clone", t["repo"], str(target), "--", "--depth", "1", "-q"]
    )
    if err:
        warn(f"could not clone {t['repo']}: {err}")
        return None
    return target


def main(argv: list[str] | None = None) -> int:
    """Audit each fetched file and save the output next to the other findings."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--only", help="comma-separated target ids")
    p.add_argument("--timeout", type=int, default=600)
    args = p.parse_args(argv)
    if not shutil.which("claude"):
        print(
            "SKIPPED claude CLI not on PATH; the report will say the audit did not run"
        )
        return 0
    work = Path(args.work)
    targets, texts = load_work(work)
    keep = set(args.only.split(",")) if args.only else None
    for t in targets:
        if keep and t["id"] not in keep:
            continue
        where = prepare(t, texts[t["id"]], work / "audit")
        if where is None:
            continue
        try:
            proc = subprocess.run(
                ["claude", "-p", "/doctor prompt-audit"],
                cwd=where,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=args.timeout,
            )
            out = proc.stdout.strip() or proc.stderr.strip()
        except subprocess.TimeoutExpired:
            out = f"(audit timed out after {args.timeout}s)"
        (work / f"audit-{t['id']}.md").write_text(out + "\n", encoding="utf-8")
        print(f"{t['id']:4} audit-{t['id']}.md ({len(out.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
