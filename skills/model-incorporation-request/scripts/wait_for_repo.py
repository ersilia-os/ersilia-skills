#!/usr/bin/env python3
"""wait_for_repo.py — wait for the approval bot to announce a model repository.

    python wait_for_repo.py <issue-number> [--timeout 600] [--interval 20]

Run it after commenting ``/approve`` on a ``new-model`` request. It polls the issue and
prints one JSON object, ``status`` being one of:

    created        {"status": "created", "repo": "eos80sj"}
    failed         {"status": "failed", "workflow_url": "https://github.com/.../runs/..."}
    timeout        the bot has not answered within --timeout seconds
    not_approved   the issue has no /approve comment at all
    error          gh failed three times in a row; ``detail`` has the message

Only bot comments posted after the *latest* ``/approve`` count, so retrying after a failure
works and the old failure comment is ignored. Approval normally takes about two minutes.
Never post ``/approve`` again because of a timeout: a second run creates a second repository.

The failure comment names a repository too, so "Workflow Failure" is checked first.
Exit status is 0 only for ``created``.
"""
import argparse
import json
import re
import subprocess
import sys
import time

REPO = "ersilia-os/ersilia"
BOT = "github-actions"
BOT_REPO_RE = re.compile(r"ersilia-os/(eos[0-9a-z]{4})")
RUN_RE = re.compile(r"https://github\.com/[^/\s)]+/[^/\s)]+/actions/runs/\d+")


def classify(comments):
    """Status of the latest approval, from the issue's comments, oldest first."""
    approve_at = None
    for c in comments:
        if (c.get("body") or "").lstrip().startswith("/approve"):
            approve_at = c["createdAt"]          # the latest one wins
    if approve_at is None:
        return {"status": "not_approved"}
    for c in comments:
        if c["createdAt"] <= approve_at or (c.get("author") or {}).get("login") != BOT:
            continue
        body = c.get("body") or ""
        if "Workflow Failure" in body:
            m = RUN_RE.search(body)
            return {"status": "failed", "workflow_url": m.group(0) if m else None}
        if "New Model Repository Created" in body:
            m = BOT_REPO_RE.search(body)
            return {"status": "created", "repo": m.group(1) if m else None}
    return {"status": "pending"}


def fetch(number, repo):
    p = subprocess.run(["gh", "issue", "view", str(number), "--repo", repo,
                        "--json", "comments"], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:300] or f"gh exited {p.returncode}")
    return json.loads(p.stdout)["comments"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("issue", type=int, help="the new-model request's issue number")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--timeout", type=int, default=600, help="seconds to wait (default 600)")
    ap.add_argument("--interval", type=int, default=20, help="seconds between polls (default 20)")
    a = ap.parse_args()

    start = time.monotonic()
    errors, result = 0, {"status": "pending"}
    while True:
        try:
            result, errors = classify(fetch(a.issue, a.repo)), 0
        except Exception as e:  # noqa: BLE001 - transient gh/network failures are retried
            errors += 1
            result = {"status": "error", "detail": str(e)}
            if errors >= 3:
                break
        else:
            if result["status"] != "pending":
                break
        if time.monotonic() - start >= a.timeout:
            break
        time.sleep(a.interval)
    if result["status"] == "pending":
        result = {"status": "timeout"}
    result["waited_s"] = round(time.monotonic() - start)
    print(json.dumps(result))
    return 0 if result["status"] == "created" else 1


if __name__ == "__main__":
    sys.exit(main())
