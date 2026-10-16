#!/usr/bin/env python3
"""release_state.py — what release does a model have, and what should happen next?

    python release_state.py eos88ir

Prints one JSON object describing the latest GitHub release, where its tag points,
whether DockerHub, metadata.yml and the Hub catalogue agree with it, and a single
recommended ``action``. Run it only after ci_status.py reports ``green``: it does not
look at CI, and creating a release on a red or running pipeline is the eos8gop mistake.

Two kinds of release behave differently, which is why ``released_by`` matters:

* **Bot release** (``github-actions[bot]``). post-upload creates ``v1.0.0`` itself when
  the repo has no tags, at the upload run's commit, and retags the image in the same
  job. Releases made with the workflow token trigger no other workflow, so "Retag image
  on release" never runs and the tag sitting behind main's later bot commits is normal.
* **Manual release** (a person). Publishing it triggers "Retag image on release", which
  checks out the tag, edits metadata.yml and **pushes to main**. That push is rejected
  unless the tag is main's HEAD, so a manual release must target main HEAD after the
  bot's final "updating readme" commit has landed.

``action`` is one of: ``verified``, ``create_release``, ``wait_for_bot_commits``,
``wait_for_retag``, ``recreate_release_at_head``, ``unreleased_changes``,
``investigate``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BOT_COMMITTER,
    BOT_RELEASER,
    OWNER,
    WF_RETAG,
    catalog_entry,
    check_model_id,
    emit,
    fetch_json,
    gh_api,
    remote_metadata,
)

SEMVER_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def tag_commit(model_id, tag):
    """Return the commit SHA a tag points at, dereferencing annotated tags."""
    ref = gh_api(f"repos/{OWNER}/{model_id}/git/ref/tags/{tag}", allow_404=True)
    if not ref:
        return None
    obj = ref["object"]
    if obj["type"] == "tag":
        obj = gh_api(f"repos/{OWNER}/{model_id}/git/tags/{obj['sha']}")["object"]
    return obj["sha"]


def docker_digest(model_id, tag):
    """Return the DockerHub digest of ``ersiliaos/<model_id>:<tag>``, or ``None``."""
    data = fetch_json(f"https://hub.docker.com/v2/repositories/ersiliaos/{model_id}/tags/{tag}")
    return (data or {}).get("digest")


def is_bot_commit(commit):
    return commit["commit"]["author"]["name"] == BOT_COMMITTER and "[skip ci]" in commit["commit"]["message"]


def next_versions(tag):
    """Return the candidate patch/minor/major bumps of a ``vX.Y.Z`` tag."""
    match = SEMVER_RE.match(tag or "")
    if not match:
        return None
    major, minor, patch = (int(x) for x in match.groups())
    return {
        "patch": f"v{major}.{minor}.{patch + 1}",
        "minor": f"v{major}.{minor + 1}.0",
        "major": f"v{major + 1}.0.0",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("model_id")
    args = parser.parse_args()
    model_id = check_model_id(args.model_id)

    head_commit = gh_api(f"repos/{OWNER}/{model_id}/commits/main")
    head = {
        "sha": head_commit["sha"],
        "message": head_commit["commit"]["message"].split("\n")[0],
        "author": head_commit["commit"]["author"]["name"],
    }
    head_is_bot_final = head["author"] == BOT_COMMITTER and head["message"].startswith("updating readme")

    releases = [r for r in (gh_api(f"repos/{OWNER}/{model_id}/releases?per_page=100") or []) if not r.get("draft")]
    tags = [t["name"] for t in (gh_api(f"repos/{OWNER}/{model_id}/tags?per_page=100") or [])]
    metadata = remote_metadata(model_id)
    catalog = catalog_entry(model_id) or {}

    shown = ("Status", "Release", "DockerHub", "Docker Architecture")
    result = {
        "model_id": model_id,
        "main_head": head,
        "head_is_bot_final": head_is_bot_final,
        "tags": tags,
        "release": None,
        "docker": None,
        "metadata": {k: metadata.get(k) for k in shown},
        "catalog": {k: catalog.get(k) for k in shown} if catalog else None,
        "action": None,
        "reasons": [],
        "warnings": [],
    }

    if not releases:
        if not head_is_bot_final:
            result["action"] = "wait_for_bot_commits"
            result["reasons"].append(
                "No release yet, and main's HEAD is not the bot's final 'updating readme' "
                "commit, so post-upload has not finished. Wait, then re-check."
            )
        else:
            result["action"] = "create_release"
            why = (
                f"tags already exist ({', '.join(tags)}), so post-upload skipped its automatic v1.0.0"
                if tags
                else "post-upload finished without creating v1.0.0"
            )
            result["reasons"].append(f"No published release: {why}.")
            result["proposed"] = {
                "tag": "v1.0.0" if "v1.0.0" not in tags else None,
                "target": head["sha"],
                "command": (
                    f"gh release create v1.0.0 -R {OWNER}/{model_id} --target {head['sha']} "
                    '--title "Release v1.0.0" --generate-notes'
                ),
            }
            if "v1.0.0" in tags:
                result["warnings"].append(
                    "A v1.0.0 tag exists without a release. Creating the release would reuse "
                    "that tag where it points now, which may be behind main HEAD; delete the "
                    "stale tag first (needs explicit confirmation)."
                )
        emit(result)
        return

    release = releases[0]
    tag = release["tag_name"]
    commit = tag_commit(model_id, tag)
    released_by = (release.get("author") or {}).get("login")
    result["release"] = {
        "tag": tag,
        "name": release.get("name"),
        "url": release["html_url"],
        "published_at": release.get("published_at"),
        "released_by": released_by,
        "by_bot": released_by == BOT_RELEASER,
        "tag_commit": commit,
        "tag_is_head": commit == head["sha"],
        "next_versions": next_versions(tag),
    }

    latest_digest, tag_digest = docker_digest(model_id, "latest"), docker_digest(model_id, tag)
    result["docker"] = {
        "repo": f"https://hub.docker.com/r/ersiliaos/{model_id}",
        "latest": latest_digest,
        tag: tag_digest,
        "match": bool(latest_digest) and latest_digest == tag_digest,
    }

    # Commits after the tag that a person made mean the release no longer matches main.
    compare = gh_api(f"repos/{OWNER}/{model_id}/compare/{tag}...main", allow_404=True) or {}
    human_commits = [c for c in compare.get("commits", []) if not is_bot_commit(c)]
    result["release"]["unreleased_commits"] = [
        {"sha": c["sha"][:7], "message": c["commit"]["message"].split("\n")[0]} for c in human_commits
    ]

    if not result["release"]["by_bot"]:
        retags = [
            r for r in (gh_api(f"repos/{OWNER}/{model_id}/actions/runs?per_page=100") or {}).get("workflow_runs", [])
            if r["name"] == WF_RETAG
        ]
        latest_retag = retags[0] if retags else None
        result["release"]["retag_run"] = (
            {"run_id": latest_retag["id"], "status": latest_retag["status"],
             "conclusion": latest_retag.get("conclusion"), "url": latest_retag["html_url"]}
            if latest_retag else None
        )
        if latest_retag and latest_retag["status"] != "completed":
            result["action"] = "wait_for_retag"
            result["reasons"].append("The release's retag workflow is still running.")
            emit(result)
            return
        if latest_retag and latest_retag.get("conclusion") != "success":
            result["action"] = "recreate_release_at_head"
            result["reasons"].append(
                f"The manual release {tag} failed to retag (run {latest_retag['id']}). If its log "
                "says 'failed to push some refs', the tag is behind main HEAD: delete the "
                f"release and tag, then recreate {tag} at {head['sha'][:7]}. Destructive; "
                "needs explicit confirmation."
            )
            emit(result)
            return

    if human_commits:
        result["action"] = "unreleased_changes"
        result["reasons"].append(
            f"{len(human_commits)} non-bot commit(s) landed after {tag}. A new release needs a "
            "version bump, which the user must choose (MAJOR/MINOR/PATCH rules in the model "
            "repo's CLAUDE.md)."
        )
        emit(result)
        return

    problems = []
    if not result["docker"]["match"]:
        problems.append(f"DockerHub 'latest' and '{tag}' digests differ or one is missing.")
    if metadata.get("Release") != tag:
        problems.append(f"metadata.yml Release is {metadata.get('Release')!r}, expected {tag!r}.")
    if metadata.get("Status") != "Ready":
        problems.append(f"metadata.yml Status is {metadata.get('Status')!r}, expected 'Ready'.")
    if not metadata.get("DockerHub"):
        problems.append("metadata.yml has no DockerHub field.")

    if problems:
        result["action"] = "investigate"
        result["reasons"] += problems
    else:
        result["action"] = "verified"
        result["reasons"].append(f"{tag} is published, the image is retagged, and metadata.yml agrees.")

    # The catalogue is synced by a later job and can lag; never block on it.
    if not catalog:
        result["warnings"].append("The model is not in the Hub catalogue (models.json) yet.")
    elif catalog.get("Status") != "Ready" or catalog.get("Release") != tag:
        result["warnings"].append(
            f"Hub catalogue shows Status={catalog.get('Status')!r}, Release={catalog.get('Release')!r}; "
            "it is synced after metadata and may lag."
        )

    emit(result)


if __name__ == "__main__":
    main()
