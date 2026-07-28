"""Reconcile the Airtable "Repositories" registry against live GitHub state.

The Airtable Repositories table (base "Ersilia Content") is *supposed* to be kept current
by a nightly cron. This script does **not** write to Airtable — it only detects drift and
emits findings for the digest's "Repository registry health" chapter (report-only, per the
skill's design).

Inputs:
- `--airtable`  JSON list of normalised Airtable records (the skill dumps these via the
  Airtable MCP; see references/airtable-schema.md for the expected shape). Each record:
    {"name": "ersilia", "title": "...", "status": "In progress", "type": ["Package"],
     "projects": ["Ersilia Model Hub"], "open_issues": 42, "total_commits": 100,
     "visibility": "Public", "creation_date": "2020-07-23"}
  Missing keys are tolerated.
- `--github`    the JSON written by `fetch_github.py`.

Findings (all report-only):
- missing_from_airtable : trackable org repos (non-model, non-fork) with no Airtable record
  — the strongest cron-gap / new-repo signal.
- stale_in_airtable     : Airtable records whose repo no longer exists in the org (renamed,
  deleted, or transferred).
- status_mismatch / type_mismatch : the Airtable Status/Type disagrees (strict string
  compare) with the GitHub custom property mirrored from it. Both values are reported.
  Airtable and GitHub share the same Status/Type vocabulary, so the mirror should match
  exactly; a mismatch means the nightly cron lagged or a side was hand-edited. Only flagged
  when both sides carry a value (an empty side is a curation finding instead).
- missing_status / missing_type / missing_projects : human-curated fields left empty.
- active_but_parked      : records marked Idle / Completed / Discontinued / Archived that
  nonetheless saw issue/PR activity in the window — the status probably needs revisiting.
- metric_drift           : heuristic — Airtable `open_issues` differs from the live GitHub
  count by more than `--drift-threshold`. Soft signal only (the GitHub REST count folds in
  PRs, so small diffs are expected); a large gap can indicate the cron has not run.

Output: a JSON document to `--out` (default `/tmp/health.json`).

Exit codes: 0 always when inputs parse (an out-of-date registry is a finding, not an error);
1 only if an input file is missing or malformed.

Usage:
    python reconcile_airtable.py --airtable /tmp/airtable_repos.json \
        --github /tmp/github.json --out /tmp/health.json
"""

from __future__ import annotations

import argparse
import sys

from _common import is_trackable, read_json, warn, write_json

# "Parked" = a repo not expected to see active work. A parked repo with fresh activity in
# the window is surfaced as active_but_parked. These match the live Airtable/GitHub status
# vocabulary (Todo, In progress, Completed, Archived, Discontinued, Idle).
PARKED_STATUSES = {"Idle", "Completed", "Discontinued", "Archived"}


def _as_list(v) -> list:
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return [x for x in v if x not in (None, "")]
    return [v]


def _value_set(v) -> set[str]:
    """Normalise an Airtable/GitHub Status or Type value to a set of trimmed strings."""
    return {str(x).strip() for x in _as_list(v) if str(x).strip()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--airtable", required=True, help="normalised Airtable records JSON")
    p.add_argument("--github", required=True, help="fetch_github.py output JSON")
    p.add_argument("--out", default="/tmp/health.json", help="output JSON path")
    p.add_argument("--drift-threshold", type=int, default=15,
                   help="abs open-issues diff above which metric_drift is flagged")
    args = p.parse_args(argv)

    at_records = read_json(args.airtable)
    gh = read_json(args.github)
    if at_records is None:
        warn(f"airtable input not found or empty: {args.airtable}")
        return 1
    if not isinstance(at_records, list):
        warn(f"airtable input must be a JSON list, got {type(at_records).__name__}")
        return 1
    if gh is None or not isinstance(gh, dict):
        warn(f"github input not found or malformed: {args.github}")
        return 1

    repos = (gh.get("repos") or {}).get("list") or []
    # Trackable = first-party, non-model repos. Archived repos stay trackable (they should
    # still be catalogued). Forks, model repos, and org-infrastructure dot-repos
    # (e.g. `.github`, `.github-private`) are out of scope for this table.
    trackable = {r["name"]: r for r in repos if is_trackable(r)}
    org_repo_names = {r["name"] for r in repos}

    # Repos with issue/PR activity in the window (non-model already, from fetch_github).
    activity = gh.get("activity") or {}
    active_repos: set[str] = set()
    for bucket in activity.values():
        for it in bucket or []:
            if it.get("repo"):
                active_repos.add(it["repo"])

    # Index Airtable records by repo slug.
    at_by_name: dict[str, dict] = {}
    unnamed = 0
    for rec in at_records:
        name = (rec.get("name") or "").strip()
        if not name:
            unnamed += 1
            continue
        at_by_name[name] = rec
    at_names = set(at_by_name)

    missing_from_airtable = [
        {"name": n, "url": trackable[n].get("url"), "archived": trackable[n].get("archived")}
        for n in sorted(trackable)
        if n not in at_names
    ]
    stale_in_airtable = [
        {"name": n, "status": at_by_name[n].get("status")}
        for n in sorted(at_names)
        if n not in org_repo_names
    ]

    missing_status, missing_type, missing_projects = [], [], []
    active_but_parked, metric_drift = [], []
    status_mismatch, type_mismatch = [], []

    for name in sorted(at_names):
        rec = at_by_name[name]
        if not _value_set(rec.get("status")):
            missing_status.append(name)
        if not _as_list(rec.get("type")):
            missing_type.append(name)
        if not _as_list(rec.get("projects")):
            missing_projects.append(name)

        status_set = _value_set(rec.get("status"))
        if (status_set & PARKED_STATUSES) and name in active_repos:
            active_but_parked.append({"name": name, "status": ", ".join(sorted(status_set))})

        # Alignment (strict compare) against the GitHub custom properties mirrored from
        # Airtable. Only for repos present on both sides, and only when *both* sides carry a
        # value — an empty side is already reported as a curation/missing finding, not a
        # mismatch. Both values are surfaced so the finding is actionable.
        gh_repo = trackable.get(name) or {}
        at_status = _value_set(rec.get("status"))
        gh_status = _value_set(gh_repo.get("gh_status"))
        if name in trackable and at_status and gh_status and at_status != gh_status:
            status_mismatch.append({
                "name": name,
                "airtable": sorted(at_status),
                "github": sorted(gh_status),
            })
        at_type = _value_set(rec.get("type"))
        gh_type = _value_set(gh_repo.get("gh_type"))
        if name in trackable and at_type and gh_type and at_type != gh_type:
            type_mismatch.append({
                "name": name,
                "airtable": sorted(at_type),
                "github": sorted(gh_type),
            })

        at_oi = rec.get("open_issues")
        gh_oi = gh_repo.get("open_issues_count")
        if isinstance(at_oi, (int, float)) and isinstance(gh_oi, (int, float)):
            if abs(int(at_oi) - int(gh_oi)) > args.drift_threshold:
                metric_drift.append({
                    "name": name,
                    "airtable_open_issues": int(at_oi),
                    "github_open_issues_count": int(gh_oi),
                })

    doc = {
        "totals": {
            "org_trackable": len(trackable),
            "org_total": len(repos),
            "airtable_records": len(at_records),
            "airtable_unnamed": unnamed,
        },
        "summary": {
            "missing_from_airtable": len(missing_from_airtable),
            "stale_in_airtable": len(stale_in_airtable),
            "status_mismatch": len(status_mismatch),
            "type_mismatch": len(type_mismatch),
            "missing_status": len(missing_status),
            "missing_type": len(missing_type),
            "missing_projects": len(missing_projects),
            "active_but_parked": len(active_but_parked),
            "metric_drift": len(metric_drift),
        },
        "missing_from_airtable": missing_from_airtable,
        "stale_in_airtable": stale_in_airtable,
        "status_mismatch": status_mismatch,
        "type_mismatch": type_mismatch,
        "missing_status": missing_status,
        "missing_type": missing_type,
        "missing_projects": missing_projects,
        "active_but_parked": active_but_parked,
        "metric_drift": metric_drift,
    }

    write_json(args.out, doc)
    s = doc["summary"]
    print(f"wrote {args.out}: "
          f"{s['missing_from_airtable']} missing, {s['stale_in_airtable']} stale, "
          f"{s['status_mismatch']} status-mismatch, {s['type_mismatch']} type-mismatch, "
          f"{s['missing_status']} no-status, {s['missing_type']} no-type, "
          f"{s['active_but_parked']} active-but-parked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
