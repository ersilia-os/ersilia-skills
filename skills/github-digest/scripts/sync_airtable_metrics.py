"""Sync GitHub repo metrics into the Airtable "Repositories" table (GitHub → Airtable only).

This is the **one write path** in the github-digest skill. Everything else is report-only;
this script refreshes the cron-maintained metric columns (Stars, Forks, Open Issues,
Subscribers, Total Commits, Contributors, Contributor Names) from live GitHub state. It is
strictly **unidirectional** — GitHub is the source of truth, Airtable is the sink. It never
touches the human-curated columns (Status, Type, Projects, Title).

The Airtable MCP cannot be called from a Python subprocess, so this script does not write to
Airtable itself. It produces an **update plan** (`--out`, default `/tmp/airtable_updates.json`)
that the skill then applies via the MCP `update_records_for_table` (records keyed by field ID,
≤ 50 per request). The plan contains only records/fields whose value actually changed, plus a
summary of what was (to be) acted on for the digest's sync note.

Inputs:
- `--github`   : `fetch_github.py` output (provides the repo inventory + cheap metrics
  stargazers/forks already fetched, and the open-issue snapshot used for a true open-issue
  count that excludes PRs).
- `--airtable` : the normalised Airtable dump, which **must include each record's `id`**
  (see references/airtable-schema.md) so updates can target the right row.

The expensive per-repo metrics (subscribers, contributors, total commits, contributor names)
are fetched here via the `gh` CLI, one set of calls per trackable repo. Use `--max-repos` to
cap that during testing.

Field-name → Airtable field ID map is fixed below (verified 2026-06-18). Re-confirm with
`list_tables_for_base` if the references freshness gate is overdue.

Exit codes: 0 when a plan was written (even an empty one — "nothing to update" is a valid
result); 1 if an input is missing/malformed or the GitHub inventory is unusable.

Usage:
    python sync_airtable_metrics.py --github /tmp/github.json \
        --airtable /tmp/airtable_repos.json --out /tmp/airtable_updates.json
"""

from __future__ import annotations

import argparse
import sys

from _common import is_trackable, read_json, run_gh_json, warn, write_json

# Airtable field IDs for the metric columns (Repositories table tbluZtI3W9pseCSPH).
FIELD_IDS = {
    "Stars": "fldbQUSKXf0ncJtTH",
    "Forks": "fld54Du5w2IapXZOQ",
    "Open Issues": "fldcw1u9DyOzs54tx",
    "Subscribers": "fld43sjGwxLYjrb5q",
    "Total Commits": "fldySp7DgJPKq7I93",
    "Contributors": "fldznty61FrXKeIhl",
    "Contributor Names": "fldL50bcwVxhl889c",
}
# Contributor Names is a singleLineText cell — cap the joined logins so it stays sane.
MAX_CONTRIB_NAMES = 20


def true_open_issue_counts(gh: dict) -> dict[str, int]:
    """Per-repo count of genuinely-open *issues* (not PRs) from the open snapshot.

    `open_snapshot.open_issues` already excludes PRs and model repos, so counting by repo
    gives an accurate Open Issues figure — better than the REST `open_issues_count`, which
    folds PRs into the number.
    """
    counts: dict[str, int] = {}
    for it in (gh.get("open_snapshot") or {}).get("open_issues") or []:
        repo = it.get("repo")
        if repo:
            counts[repo] = counts.get(repo, 0) + 1
    return counts


def fetch_repo_metrics(owner: str, name: str) -> dict:
    """Per-repo metrics that the org inventory does not carry: subscribers, contributors,
    contributor names, and total commits (≈ sum of contributor contributions on the default
    branch). Returns a dict with None for any metric that could not be fetched (so the sync
    leaves that Airtable cell untouched rather than zeroing it)."""
    out = {"subscribers": None, "contributors": None,
           "contributor_names": None, "total_commits": None}

    repo, err = run_gh_json(["api", f"repos/{owner}/{name}"])
    if isinstance(repo, dict):
        out["subscribers"] = repo.get("subscribers_count")
    elif err:
        warn(f"{name}: repo metadata fetch failed: {err}")

    contribs, err = run_gh_json([
        "api", "--paginate", f"repos/{owner}/{name}/contributors?per_page=100&anon=false",
    ])
    if isinstance(contribs, list):
        logins = [c.get("login") for c in contribs if isinstance(c, dict) and c.get("login")]
        out["contributors"] = len(contribs)
        out["total_commits"] = sum(
            c.get("contributions", 0) for c in contribs if isinstance(c, dict)
        )
        if logins:
            names = ", ".join(logins[:MAX_CONTRIB_NAMES])
            if len(logins) > MAX_CONTRIB_NAMES:
                names += f", +{len(logins) - MAX_CONTRIB_NAMES} more"
            out["contributor_names"] = names
        else:
            out["contributor_names"] = ""
    elif err:
        warn(f"{name}: contributors fetch failed: {err}")
    return out


def _num(v) -> int | None:
    return int(v) if isinstance(v, (int, float)) else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--github", required=True, help="fetch_github.py output JSON")
    p.add_argument("--airtable", required=True,
                   help="normalised Airtable dump JSON (must include each record's `id`)")
    p.add_argument("--out", default="/tmp/airtable_updates.json", help="update-plan output")
    p.add_argument("--max-repos", type=int, default=0,
                   help="cap trackable repos processed (0 = all); for testing")
    args = p.parse_args(argv)

    gh = read_json(args.github)
    at_records = read_json(args.airtable)
    if gh is None or not isinstance(gh, dict):
        warn(f"github input not found or malformed: {args.github}")
        return 1
    if not isinstance(at_records, list):
        warn(f"airtable input must be a JSON list: {args.airtable}")
        return 1

    org = gh.get("org") or "ersilia-os"
    repos = (gh.get("repos") or {}).get("list") or []
    trackable = {r["name"]: r for r in repos if is_trackable(r)}
    open_issues = true_open_issue_counts(gh)

    # Index Airtable records (with their record id and current metric values) by repo name.
    at_by_name = {}
    no_id = 0
    for rec in at_records:
        name = (rec.get("name") or "").strip()
        if not name:
            continue
        if not rec.get("id"):
            no_id += 1
            continue
        at_by_name[name] = rec
    if no_id:
        warn(f"{no_id} Airtable record(s) had no `id` and were skipped — re-dump including id")

    # Only sync repos that are both trackable on GitHub and present in Airtable.
    names = sorted(n for n in trackable if n in at_by_name)
    if args.max_repos > 0:
        names = names[: args.max_repos]

    updates = []
    by_field: dict[str, int] = {}
    notable = []
    fetch_failures = 0

    for name in names:
        gh_repo = trackable[name]
        m = fetch_repo_metrics(org, name)
        if m["contributors"] is None and m["subscribers"] is None:
            fetch_failures += 1
        # Desired values from GitHub. None means "could not determine" → skip that field.
        desired = {
            "Stars": _num(gh_repo.get("stargazers_count")),
            "Forks": _num(gh_repo.get("forks_count")),
            "Open Issues": open_issues.get(name, 0),
            "Subscribers": _num(m["subscribers"]),
            "Total Commits": _num(m["total_commits"]),
            "Contributors": _num(m["contributors"]),
            "Contributor Names": m["contributor_names"],
        }
        rec = at_by_name[name]
        # Current Airtable values use the same human field names in the normalised dump.
        current = {
            "Stars": _num(rec.get("stars")),
            "Forks": _num(rec.get("forks")),
            "Open Issues": _num(rec.get("open_issues")),
            "Subscribers": _num(rec.get("subscribers")),
            "Total Commits": _num(rec.get("total_commits")),
            "Contributors": _num(rec.get("contributors")),
            "Contributor Names": rec.get("contributor_names"),
        }

        changed = {}
        for field, want in desired.items():
            if want is None:
                continue  # couldn't determine — leave the cell as-is
            have = current.get(field)
            if field == "Contributor Names":
                if (have or "") == (want or ""):
                    continue
            elif have == want:
                continue
            changed[FIELD_IDS[field]] = want
            by_field[field] = by_field.get(field, 0) + 1
            # Record a few notable numeric deltas for the digest's acted-on note.
            if field != "Contributor Names" and isinstance(have, int) and isinstance(want, int):
                if abs(want - have) >= 1:
                    notable.append({"name": name, "field": field, "from": have, "to": want})

        if changed:
            updates.append({"recordId": rec["id"], "name": name, "fields": changed})

    # Sort notable by absolute delta, keep the top few for a compact summary.
    notable.sort(key=lambda d: -abs(d["to"] - d["from"]))

    doc = {
        "base_id": "app1iYv78K6xbHkmL",
        "table_id": "tbluZtI3W9pseCSPH",
        "direction": "github->airtable",
        "summary": {
            "repos_considered": len(names),
            "records_to_update": len(updates),
            "fields_changed": sum(by_field.values()),
            "by_field": dict(sorted(by_field.items(), key=lambda kv: (-kv[1], kv[0]))),
            "fetch_failures": fetch_failures,
            "notable": notable[:8],
        },
        "updates": updates,
    }
    write_json(args.out, doc)
    s = doc["summary"]
    print(f"wrote {args.out}: {s['records_to_update']} records to update "
          f"({s['fields_changed']} field changes across {s['repos_considered']} repos; "
          f"{fetch_failures} fetch failures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
