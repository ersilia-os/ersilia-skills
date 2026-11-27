#!/usr/bin/env python3
"""ci_status.py — is every workflow green for the current state of a model repo?

    python ci_status.py eos88ir

Reads the repo's Actions runs and prints one JSON verdict for the **real HEAD** of
main: the newest commit without a CI-skip token (``[skip ci]``, ``[ci skip]``,
``[no ci]``, ``[skip actions]``, ``[actions skip]`` or a ``skip-checks: true``
trailer). Such commits never trigger CI: the ersilia-bot metadata and README
refreshes, and maintainers' Hub-wide CI updates (the wrapper and Slack-workflow
changes pushed to every model repo in November 2026), so judging the literal HEAD
would report "missing". A person's skipped commit that changes only CI or editor
files is listed under ``warnings``. One that changes anything else was never tested,
so the verdict cannot be ``green``: it becomes ``untested``.

How runs are paired, and why:

* "Test and upload model" runs on the real HEAD (push or ``workflow_dispatch``); the
  newest such run wins, so a manual re-run supersedes an earlier failure.
* "Test model image" is triggered by ``workflow_run`` and records whatever main's HEAD
  was when it started. By then the upload run has already pushed bot commits, so its
  ``head_sha`` usually differs (eos88ir: upload 146d02c, image 53d8304). It is paired by
  time instead: the first image run created after the upload run, and before the next
  upload run.
* The "Initial commit" failure that every new repo shows is template noise and is
  reported under ``noise``, never as a failure.

Exit code 0 always when the repo could be read; the verdict is in ``overall``:
``green`` | ``running`` | ``failed`` | ``missing`` | ``untested`` | ``not_merged``. Non-blocking
oddities (an architecture that failed inside a green image run, a PR merged on a red
test) go to ``warnings``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BOT_COMMITTER,
    NO_EFFECT_LABEL,
    OWNER,
    WF_IMAGE,
    WF_PR,
    WF_RETAG,
    WF_UPLOAD,
    check_model_id,
    emit,
    gh_api,
    gh_text,
    model_files_changed,
    skips_ci,
)

# GitHub kills a job after 6 h; an image test cancelled near that mark timed out.
TIMEOUT_SECONDS = 5.75 * 3600

# resolve-release releases a dispatched run only when the repo has no tags yet.
DISPATCH_NOTE = (
    "On a model that already has a release, a dispatched run rebuilds and tests the model "
    "but releases nothing, so the release then has to be made by hand (release_state.py)."
)

# Log fragments with a known diagnosis. The hint text is what the skill tells the user;
# references/lessons-learned.md has the full story behind each.
LOG_PATTERNS = [
    (
        "failed to push some refs",
        "push_rejected",
        "The workflow could not push its metadata commit to main, because main moved past "
        "the commit it checked out. For a retag run this means the release tag is behind "
        "main HEAD: recreate the release at main HEAD (lessons-learned: stale tag).",
    ),
    (
        "manifest unknown",
        "image_missing",
        "DockerHub has no image for the tag. The pack build probably did not finish; "
        "re-run 'Test and upload model'.",
    ),
    (
        "No space left on device",
        "runner_disk_full",
        "The runner ran out of disk building or testing the image. Re-run once; if it "
        "recurs, the image is too large and needs slimming (hand off to model-fixing).",
    ),
]


def parse_time(value):
    """Parse a GitHub ISO timestamp, or return ``None``."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def real_head(model_id):
    """Return ``(literal_head, real_head, skipped_by_people, untested)`` for main.

    ``skipped_by_people`` holds a person's CI-skipped commits that change only CI or
    editor files; ``untested`` holds those that change anything else.
    """
    commits = gh_api(f"repos/{OWNER}/{model_id}/commits?sha=main&per_page=30") or []
    if not commits:
        return None, None, [], []

    def describe(commit):
        message = commit["commit"]["message"].split("\n")[0]
        author = (commit.get("author") or {}).get("login") or commit["commit"]["author"]["name"]
        return {"sha": commit["sha"], "message": message, "author": author}

    # Walk main's first-parent chain, so the commits of a merged PR's branch, which never
    # ran on main themselves, are not mistaken for main's head (eos8bpb).
    by_sha = {c["sha"]: c for c in commits}
    chain, commit = [], commits[0]
    while commit is not None:
        chain.append(commit)
        parents = commit.get("parents") or []
        commit = by_sha.get(parents[0]["sha"]) if parents else None

    literal = describe(commits[0])
    skipped_by_people, untested = [], []
    for commit in chain:
        message = commit["commit"]["message"]
        author_name = commit["commit"]["author"]["name"]
        if skips_ci(message):
            if author_name != BOT_COMMITTER:
                files = model_files_changed(model_id, commit["sha"])
                if files == []:
                    skipped_by_people.append(describe(commit))
                else:
                    untested.append(dict(describe(commit), files=files or "unknown"))
            continue
        return literal, describe(commit), skipped_by_people, untested
    return literal, literal, skipped_by_people, untested


def run_summary(run, jobs=None):
    """Reduce a run (and optionally its jobs) to the fields the skill reports."""
    started, updated = parse_time(run.get("run_started_at")), parse_time(run.get("updated_at"))
    summary = {
        "workflow": run["name"],
        "run_id": run["id"],
        "event": run["event"],
        "head_sha": run["head_sha"],
        "title": run.get("display_title"),
        "status": run["status"],
        "conclusion": run.get("conclusion"),
        "created_at": run["created_at"],
        "url": run["html_url"],
    }
    if started and updated and run["status"] == "completed":
        summary["duration_min"] = round((updated - started).total_seconds() / 60)
    if jobs is not None:
        summary["jobs"] = [
            {
                "name": job["name"],
                "status": job["status"],
                "conclusion": job.get("conclusion"),
                "duration_min": _job_minutes(job),
            }
            for job in jobs
        ]
    return summary


def _job_minutes(job):
    start, end = parse_time(job.get("started_at")), parse_time(job.get("completed_at"))
    if start and end and end >= start:
        return round((end - start).total_seconds() / 60)
    return None


def run_jobs(model_id, run_id):
    """Return the jobs of a run."""
    payload = gh_api(f"repos/{OWNER}/{model_id}/actions/runs/{run_id}/jobs?per_page=100") or {}
    return payload.get("jobs", [])


def diagnose(model_id, run, jobs):
    """Classify a failed or cancelled run against the known failure patterns."""
    findings = []
    for job in jobs:
        if job.get("conclusion") == "cancelled":
            minutes = _job_minutes(job) or 0
            if minutes * 60 >= TIMEOUT_SECONDS:
                findings.append(
                    {
                        "job": job["name"],
                        "pattern": "job_timeout_6h",
                        "hint": "The job hit GitHub's 6 h limit (image tests run amd64 then "
                        "arm64, so a slow model can need ~12 h). Re-run with "
                        f"`gh workflow run upload-model.yml -R {OWNER}/{model_id}` after "
                        "checking that inference on examples/run_input.csv is not "
                        "pathologically slow. " + DISPATCH_NOTE,
                    }
                )
    if run.get("conclusion") == "failure":
        log = gh_text(["run", "view", str(run["id"]), "-R", f"{OWNER}/{model_id}", "--log-failed"])
        for needle, pattern, hint in LOG_PATTERNS:
            if needle.lower() in log.lower():
                findings.append({"job": None, "pattern": pattern, "hint": hint})
        if not findings:
            failed = [j["name"] for j in jobs if j.get("conclusion") == "failure"]
            findings.append(
                {
                    "job": ", ".join(failed) or None,
                    "pattern": "unknown",
                    "hint": f"Read `gh run view {run['id']} -R {OWNER}/{model_id} --log-failed`. "
                    "If the model itself fails (install, inference, output columns), hand "
                    "off to ersilia-model-test, then model-fixing.",
                }
            )
    return findings


def run_state(run, jobs):
    """Collapse a run plus its jobs into green / running / failed."""
    if run["status"] != "completed":
        return "running"
    if run.get("conclusion") == "success":
        # A green run can still hide a skipped post-upload; the caller checks that job.
        return "green"
    return "failed"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("model_id")
    args = parser.parse_args()
    model_id = check_model_id(args.model_id)

    literal, head, skipped_by_people, untested = real_head(model_id)
    if head is None:
        emit({"model_id": model_id, "overall": "missing", "reason": "main has no commits"})
        return

    def finish(result):
        """Emit the verdict; never report green while a newer model change is untested."""
        if untested:
            result["untested_commits"] = untested
            listed = "; ".join(
                f"{c['sha'][:7]} by {c['author']} ('{c['message']}')" for c in untested
            )
            note = (
                f"Newer commit(s) skipped CI but change files that reach the model: {listed}. "
                f"The runs above are for {head['sha'][:7]}, before them. If a commit only moves "
                "checkpoints between Git and eosvc, check that every file's sha256 is "
                "unchanged; otherwise the model on main is untested: start the chain with "
                f"`gh workflow run upload-model.yml -R {OWNER}/{model_id}`. " + DISPATCH_NOTE
            )
            if result["overall"] == "green":
                result["overall"] = "untested"
                result["reason"] = note
            else:
                result["warnings"].append(note)
        emit(result)

    runs = (gh_api(f"repos/{OWNER}/{model_id}/actions/runs?per_page=100") or {}).get(
        "workflow_runs", []
    )
    runs.sort(key=lambda r: r["created_at"])

    noise = [
        run_summary(r)
        for r in runs
        if r["name"] == WF_UPLOAD and r.get("display_title") == "Initial commit"
        and r.get("conclusion") == "failure"
    ]

    result = {
        "model_id": model_id,
        "repo": f"https://github.com/{OWNER}/{model_id}",
        "literal_head": literal,
        "real_head": head,
        "pr_test": None,
        "upload": None,
        "image": None,
        "retag": None,
        "overall": None,
        "watch": [],
        "failures": [],
        "warnings": [],
        "noise": noise,
    }
    if skipped_by_people:
        listed = "; ".join(
            f"{c['sha'][:7]} by {c['author']} ('{c['message']}')" for c in skipped_by_people
        )
        result["warnings"].append(
            f"Newer commit(s) skipped CI and change only {NO_EFFECT_LABEL}: {listed}. CI is "
            "judged on the commit before them."
        )

    pr_runs = [r for r in runs if r["name"] == WF_PR]
    if pr_runs:
        result["pr_test"] = run_summary(pr_runs[-1])

    if head["message"] == "Initial commit":
        # Nothing but the template has reached main: the incorporation PR is not merged.
        open_prs = gh_api(f"repos/{OWNER}/{model_id}/pulls?state=open&per_page=20") or []
        result["overall"] = "not_merged"
        result["open_prs"] = [{"number": p["number"], "title": p["title"], "url": p["html_url"]} for p in open_prs]
        pr_state = result["pr_test"]["conclusion"] if result["pr_test"] else "none"
        result["reason"] = (
            f"main still holds only the template's Initial commit. Open PRs: "
            f"{len(open_prs)}; latest PR test: {pr_state}. The release step starts after "
            "the incorporation PR is merged; a failing PR test goes to ersilia-model-test."
        )
        finish(result)
        return

    retag_runs = [r for r in runs if r["name"] == WF_RETAG]
    if retag_runs:
        retag = retag_runs[-1]
        retag_jobs = run_jobs(model_id, retag["id"])
        result["retag"] = run_summary(retag, retag_jobs)
        if retag["status"] == "completed" and retag.get("conclusion") != "success":
            result["retag"]["diagnosis"] = diagnose(model_id, retag, retag_jobs)

    upload_runs = [r for r in runs if r["name"] == WF_UPLOAD and r["head_sha"] == head["sha"]]
    if not upload_runs:
        result["overall"] = "missing"
        result["reason"] = (
            f"No '{WF_UPLOAD}' run for real HEAD {head['sha'][:7]}. If the PR was just "
            f"merged, wait a minute; otherwise dispatch it with `gh workflow run "
            f"upload-model.yml -R {OWNER}/{model_id}`. " + DISPATCH_NOTE
        )
        finish(result)
        return

    upload = upload_runs[-1]
    upload_jobs = run_jobs(model_id, upload["id"])
    result["upload"] = run_summary(upload, upload_jobs)
    upload_state = run_state(upload, upload_jobs)

    if upload_state == "running":
        result["overall"] = "running"
        result["watch"].append(upload["id"])
        finish(result)
        return
    if upload_state == "failed":
        result["overall"] = "failed"
        result["failures"] += [
            dict(f, workflow=WF_UPLOAD, run_id=upload["id"]) for f in diagnose(model_id, upload, upload_jobs)
        ]
        finish(result)
        return

    # Pair the image test by time: the first image run created after this upload run and
    # before the next upload run on any commit.
    later_uploads = [r for r in runs if r["name"] == WF_UPLOAD and r["created_at"] > upload["created_at"]]
    horizon = later_uploads[0]["created_at"] if later_uploads else "9999"
    image_runs = [
        r for r in runs
        if r["name"] == WF_IMAGE and upload["created_at"] < r["created_at"] < horizon
    ]
    if not image_runs:
        result["overall"] = "running"
        result["reason"] = "Upload finished; the image test has not been queued yet. Check again in a minute."
        finish(result)
        return

    image = image_runs[-1]
    image_jobs = run_jobs(model_id, image["id"])
    result["image"] = run_summary(image, image_jobs)
    image_state = run_state(image, image_jobs)

    if image_state == "running":
        result["overall"] = "running"
        result["watch"].append(image["id"])
    elif image_state == "failed":
        result["overall"] = "failed"
        result["failures"] += [
            dict(f, workflow=WF_IMAGE, run_id=image["id"]) for f in diagnose(model_id, image, image_jobs)
        ]
    else:
        post = [j for j in image_jobs if j["name"].startswith("post-upload")]
        tests = [j for j in image_jobs if j["name"] == "test-image" or j["name"].startswith("test-image /")]
        if tests and all(j.get("conclusion") == "skipped" for j in tests):
            # semver:patch and no-release do not rebuild the image, so the image test,
            # post-upload and the release jobs here are skipped by design.
            result["overall"] = "green"
            if any(j["name"].startswith("release-patch") and j.get("conclusion") == "success" for j in upload_jobs):
                result["reason"] = (
                    "semver:patch: the image was not rebuilt. The upload run released the "
                    "model (release-patch) and retagged the existing image."
                )
            elif any(j["name"].startswith("test-model-source") and j.get("conclusion") == "skipped" for j in upload_jobs):
                result["reason"] = "no-release: nothing was tested, rebuilt or released, by design."
            else:
                result["reason"] = "The image was not rebuilt (semver:patch or no-release)."
        elif post and post[0]["status"] != "completed":
            # The run can already read completed/success while post-upload is still
            # writing the release and metadata (eos3pu0).
            result["overall"] = "running"
            result["watch"].append(image["id"])
            result["reason"] = "The image test passed; post-upload is still running."
        elif post and post[0].get("conclusion") != "success":
            result["overall"] = "failed"
            result["failures"].append(
                {
                    "workflow": WF_IMAGE,
                    "run_id": image["id"],
                    "job": post[0]["name"],
                    "pattern": "post_upload_skipped",
                    "hint": "The image test passed but post-upload did not run, so no "
                    "release, metadata or catalogue update happened. Read the retag-image "
                    "job log; re-run the failed jobs with "
                    f"`gh run rerun {image['id']} -R {OWNER}/{model_id} --failed`.",
                }
            )
        else:
            result["overall"] = "green"
        # The image workflow tolerates a failed architecture (it publishes what passed),
        # so a green run can still mean an amd64-only image. Worth saying, not blocking.
        for job in image_jobs:
            if job["name"].startswith("test-image / test-image-") and job.get("conclusion") != "success":
                arch = job["name"].rsplit("-", 1)[-1]
                result["warnings"].append(
                    f"{job['name']} ended '{job.get('conclusion')}' in an otherwise green run: "
                    f"the published image probably lacks {arch}. Check 'Docker Architecture' "
                    "in metadata.yml before announcing the model."
                )

    if result["pr_test"] and result["pr_test"]["conclusion"] != "success":
        result["warnings"].append(
            f"The latest '{WF_PR}' run ended '{result['pr_test']['conclusion']}' although main "
            "was updated afterwards: the PR was merged on a red test. The main-branch runs "
            "above are what count, but say so in the summary."
        )

    finish(result)


if __name__ == "__main__":
    main()
