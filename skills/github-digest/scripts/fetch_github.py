"""Sweep the `ersilia-os` GitHub org for the digest.

Collects three things, all via the authenticated `gh` CLI:

1. The full repo inventory (`orgs/<org>/repos`), tagging each repo as a model repo
   (`eosXXXX`, summarised in the digest) or a non-model repo (detailed in the digest).
2. Issue / PR **activity** inside the date window: issues opened, issues closed, PRs
   opened, PRs merged — via `gh search`.
3. An **open-item snapshot** for the "Needs attention" chapter: currently-open PRs and
   issues, annotated with age and days-since-last-update so the skill can flag stale ones.
   Open issues are also pre-flagged as easy-win candidates (`easy_candidate` + reasons).

It also reads the org **custom properties** (`status`, `type`, mirrored from Airtable by the
nightly cron), attaching `gh_status`/`gh_type` to each repo and computing `by_type` /
`by_status` stratification over trackable repos. A `highlights` block summarises the busiest
repos / notable merges as structured input for the digest's narrative.

Model-repo activity is aggregated into a single `model_summary` block; non-model activity
is kept itemised. The output is a single JSON document written to `--out` (default
`/tmp/github.json`), consumed by `reconcile_airtable.py` and by the skill when composing
the digest.

`gh search` caps results at 1000 per query. ersilia-os weekly volume is far below that,
but if any query returns >= 1000 rows the script logs a WARNING so the skill can disclose
the truncation rather than silently under-report.

Exit codes:
- 0 if the repo inventory was fetched (activity queries may individually degrade — each
  failure is logged and that bucket is left empty; `connector_status` records "partial").
- 1 if the repo inventory itself could not be fetched (hard failure — without it nothing
  downstream is meaningful).

Usage:
    python fetch_github.py --from 2026-06-09 --to 2026-06-16 --out /tmp/github.json
    python fetch_github.py --from 2026-06-09 --to 2026-06-16 --org ersilia-os --stale-days 30
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from _common import (
    is_model_repo,
    is_trackable,
    parse_date,
    parse_iso_datetime,
    run_gh_json,
    warn,
    write_json,
)


SEARCH_CAP = 1000

# Open issues with one of these labels are pre-flagged as easy-win candidates. The org
# barely uses good-first-issue conventions, so this is a soft hint — the skill makes the
# final call (see references/scope.md). Matched case-insensitively.
EASY_LABELS = {
    "good first issue", "good-first-issue", "help wanted", "help-wanted",
    "documentation", "docs", "low priority", "low-priority", "question", "typo",
}
# A short title is a weak signal of a small, well-scoped issue.
EASY_TITLE_MAXLEN = 60
# Only recently-touched issues are realistic quick wins; ancient ones rarely are.
EASY_MAX_AGE_DAYS = 120


def fetch_repos(org: str) -> list[dict]:
    """Full repo inventory via the REST API (paginated). Raises on failure."""
    data, err = run_gh_json([
        "api", "--paginate",
        "-H", "Accept: application/vnd.github+json",
        f"orgs/{org}/repos?per_page=100&type=all",
    ])
    if data is None:
        raise RuntimeError(f"could not list repos for org {org!r}: {err}")
    repos: list[dict] = []
    for r in data:
        name = r.get("name") or ""
        repos.append({
            "name": name,
            "description": r.get("description"),
            "url": r.get("html_url"),
            "private": bool(r.get("private")),
            "fork": bool(r.get("fork")),
            "archived": bool(r.get("archived")),
            "open_issues_count": r.get("open_issues_count"),  # NB: issues + PRs (REST quirk)
            "stargazers_count": r.get("stargazers_count"),
            "forks_count": r.get("forks_count"),
            "pushed_at": r.get("pushed_at"),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "default_branch": r.get("default_branch"),
            "is_model": is_model_repo(name),
        })
    return repos


def fetch_properties(org: str) -> dict[str, dict]:
    """Org custom-property values per repo, keyed by repo name.

    `ersilia-os` mirrors the Airtable Status/Type onto each repo as org custom properties
    (`status`, `type`), maintained by the nightly cron. Returns
    `{repo_name: {"status": [...], "type": [...]}}`. On failure returns `{}` and logs a
    warning — alignment then degrades gracefully (the caller marks the connector partial).
    """
    data, err = run_gh_json([
        "api", "--paginate",
        "-H", "Accept: application/vnd.github+json",
        f"orgs/{org}/properties/values?per_page=100",
    ])
    if data is None:
        warn(f"could not read org custom properties for {org!r}: {err}")
        return {}
    props: dict[str, dict] = {}
    for rec in data:
        name = rec.get("repository_name") or ""
        if not name:
            continue
        by_name = {p.get("property_name"): p.get("value") for p in (rec.get("properties") or [])}
        props[name] = {
            "status": _as_str_list(by_name.get("status")),
            "type": _as_str_list(by_name.get("type")),
        }
    return props


def _as_str_list(v) -> list[str]:
    """Normalise a custom-property value (None | str | list) to a list of non-empty strings."""
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x not in (None, "")]
    return [str(v)]


def stratify(repos: list[dict]) -> dict:
    """Counts of trackable repos by GitHub `type` and `status`, plus the archived list.

    Stratification covers trackable repos only (first-party, non-model, non-fork, non-dot)
    so the table reflects the curated estate the Repositories registry is meant to mirror.
    Repos with no value for a property land in an `<unset>` bucket.
    """
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    archived: list[str] = []
    n = 0
    for r in repos:
        if not is_trackable(r):
            continue
        n += 1
        for v in (r.get("gh_type") or ["<unset>"]):
            by_type[v] = by_type.get(v, 0) + 1
        for v in (r.get("gh_status") or ["<unset>"]):
            by_status[v] = by_status.get(v, 0) + 1
        if r.get("archived"):
            archived.append(r["name"])
    # Sort buckets by descending count for readable rendering.
    order = lambda d: dict(sorted(d.items(), key=lambda kv: (-kv[1], kv[0])))
    return {
        "trackable": n,
        "by_type": order(by_type),
        "by_status": order(by_status),
        "archived_list": sorted(archived),
    }


def flag_easy(items: list[dict]) -> list[dict]:
    """Annotate open issues with `easy_candidate` + `easy_reasons` (soft pre-filter).

    The skill makes the final easy-win call; this only narrows the field to a bounded,
    reason-tagged candidate set. Model-repo items are never candidates (they are not
    itemised in the digest). PRs are excluded by the caller (issues only).
    """
    for it in items:
        if it.get("is_model_repo"):
            it["easy_candidate"] = False
            it["easy_reasons"] = []
            continue
        reasons: list[str] = []
        labels = {(l or "").lower() for l in (it.get("labels") or [])}
        hit = sorted(labels & EASY_LABELS)
        if hit:
            reasons.append("label: " + ", ".join(hit))
        title = it.get("title") or ""
        if 0 < len(title) <= EASY_TITLE_MAXLEN:
            reasons.append("short title")
        age = it.get("age_days")
        if isinstance(age, int) and age <= EASY_MAX_AGE_DAYS:
            reasons.append("recent")
        if it.get("unassigned"):
            reasons.append("unassigned")
        # Require a label hit OR (short title AND recent) to qualify — keeps the set tight.
        qualifies = bool(hit) or ("short title" in reasons and "recent" in reasons)
        it["easy_candidate"] = qualifies and not it.get("stale")
        it["easy_reasons"] = reasons if it["easy_candidate"] else []
    return items


def build_highlights(activity: dict, counts: dict, model_summary: dict) -> dict:
    """Structured input for the skill's narrative 'Highlights' block (no prose here).

    Surfaces the busiest non-model repos in the window and a few notable items so the LLM
    can write 2-4 factual sentences without re-deriving them.
    """
    repo_counts: dict[str, int] = {}
    for bucket in activity.values():
        for it in bucket or []:
            repo = it.get("repo")
            if repo:
                repo_counts[repo] = repo_counts.get(repo, 0) + 1
    busiest = sorted(repo_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    notable = [
        {"repo": it.get("repo"), "number": it.get("number"), "title": it.get("title"),
         "url": it.get("url"), "kind": "pr_merged"}
        for it in (activity.get("prs_merged") or [])[:3]
    ]
    return {
        "busiest_repos": [{"repo": r, "events": c} for r, c in busiest],
        "notable_merges": notable,
        "totals": counts,
        "model_summary": model_summary,
    }


def _norm_item(raw: dict, *, is_pr: bool) -> dict:
    repo_full = (raw.get("repository") or {}).get("nameWithOwner") or ""
    repo_name = repo_full.split("/", 1)[1] if "/" in repo_full else repo_full
    # gh emits a zero-value timestamp for not-yet-closed items; normalise to None.
    closed_at = raw.get("closedAt")
    if closed_at and closed_at.startswith("0001-01-01"):
        closed_at = None
    return {
        "repo": repo_name,
        "repo_full": repo_full,
        "number": raw.get("number"),
        "title": raw.get("title"),
        "url": raw.get("url"),
        "state": raw.get("state"),
        "is_pr": is_pr,
        "is_draft": bool(raw.get("isDraft")) if is_pr else False,
        "created_at": raw.get("createdAt"),
        "updated_at": raw.get("updatedAt"),
        "closed_at": closed_at,
        "labels": [l.get("name") for l in (raw.get("labels") or []) if l.get("name")],
        "author": (raw.get("author") or {}).get("login"),
        "assignees": [a.get("login") for a in (raw.get("assignees") or []) if a.get("login")],
        "is_model_repo": is_model_repo(repo_name),
    }


def search(kind: str, owner: str, flag: str, window: str, extra: list[str],
           fields: str) -> tuple[list[dict], str]:
    """Run `gh search <kind>` with one date flag. Returns (items, error_str)."""
    args = [
        "search", kind,
        "--owner", owner,
        flag, window,
        "--limit", str(SEARCH_CAP),
        "--json", fields,
        *extra,
    ]
    data, err = run_gh_json(args)
    if data is None:
        return [], err
    is_pr = kind == "prs"
    items = [_norm_item(r, is_pr=is_pr) for r in data]
    if len(items) >= SEARCH_CAP:
        warn(f"gh search {kind} {flag} {window} hit the {SEARCH_CAP}-row cap — results truncated")
    return items, ""


ISSUE_FIELDS = "number,title,repository,url,state,createdAt,updatedAt,closedAt,labels,author,assignees"
PR_FIELDS = "number,title,repository,url,state,createdAt,updatedAt,closedAt,labels,author,assignees,isDraft"


def annotate_open(items: list[dict], now: datetime, stale_days: int) -> list[dict]:
    """Add age_days, days_since_update, and stale flag to open-item snapshots."""
    for it in items:
        created = parse_iso_datetime(it.get("created_at"))
        updated = parse_iso_datetime(it.get("updated_at"))
        # Clamp to >= 0: minor clock skew between this host and GitHub can otherwise
        # produce small negative ages for items updated seconds ago.
        it["age_days"] = max(0, (now - created).days) if created else None
        it["days_since_update"] = max(0, (now - updated).days) if updated else None
        it["stale"] = bool(it["days_since_update"] is not None and it["days_since_update"] >= stale_days)
        it["unlabelled"] = not it.get("labels")
        it["unassigned"] = not it.get("assignees")
    return items


def summarise_model(*buckets: list[dict]) -> dict:
    """Aggregate model-repo items across buckets into counts."""
    keys = ("issues_opened", "issues_closed", "prs_opened", "prs_merged",
            "open_prs", "open_issues")
    summary = {k: 0 for k in keys}
    repos_touched: set[str] = set()
    for key, bucket in zip(keys, buckets):
        for it in bucket:
            if it.get("is_model_repo"):
                summary[key] += 1
                if it.get("repo"):
                    repos_touched.add(it["repo"])
    summary["repos_touched"] = len(repos_touched)
    return summary


def nonmodel(items: list[dict]) -> list[dict]:
    return [it for it in items if not it.get("is_model_repo")]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from", dest="dfrom", required=True, help="window start YYYY-MM-DD")
    p.add_argument("--to", dest="dto", required=True, help="window end YYYY-MM-DD")
    p.add_argument("--org", default="ersilia-os", help="GitHub org (default: ersilia-os)")
    p.add_argument("--out", default="/tmp/github.json", help="output JSON path")
    p.add_argument("--stale-days", type=int, default=30,
                   help="open PR/issue with no update in this many days is flagged stale")
    args = p.parse_args(argv)

    # Validate window.
    d_from = parse_date(args.dfrom)
    d_to = parse_date(args.dto)
    if d_from > d_to:
        warn(f"--from {d_from} is after --to {d_to}")
        return 1
    window = f"{d_from.isoformat()}..{d_to.isoformat()}"
    now = datetime.utcnow()

    # 1. Repo inventory (hard requirement).
    try:
        repos = fetch_repos(args.org)
    except RuntimeError as e:
        warn(str(e))
        return 1

    status = "ok"

    # 1b. Org custom properties (status/type), mirrored from Airtable by the nightly cron.
    #     Soft requirement: failure degrades alignment but does not abort the run.
    props = fetch_properties(args.org)
    if not props:
        status = "partial"
    for r in repos:
        pr = props.get(r["name"], {})
        r["gh_status"] = pr.get("status", [])
        r["gh_type"] = pr.get("type", [])

    def grab(label, kind, flag, extra):
        nonlocal status
        fields = PR_FIELDS if kind == "prs" else ISSUE_FIELDS
        items, err = search(kind, args.org, flag, window, extra, fields)
        if err:
            warn(f"{label} query failed: {err}")
            status = "partial"
        return items

    # 2. Activity in window.
    issues_opened = grab("issues opened", "issues", "--created", [])
    issues_closed = grab("issues closed", "issues", "--closed", ["--state", "closed"])
    prs_opened = grab("PRs opened", "prs", "--created", [])
    # NB: `--merged` is a boolean flag in `gh search prs`; the date-range flag is
    # `--merged-at`. Passing the window to `--merged` silently returns nothing.
    prs_merged = grab("PRs merged", "prs", "--merged-at", [])

    # 3. Open-item snapshot (no date window — current state). We reuse search() by
    #    passing the `--state open` filter as the (flag, window) pair.
    open_prs, err = search("prs", args.org, "--state", "open", [], PR_FIELDS)
    if err:
        warn(f"open PRs query failed: {err}")
        status = "partial"
    open_issues, err = search("issues", args.org, "--state", "open", [], ISSUE_FIELDS)
    if err:
        warn(f"open issues query failed: {err}")
        status = "partial"

    open_prs = annotate_open(open_prs, now, args.stale_days)
    open_issues = annotate_open(open_issues, now, args.stale_days)

    model_summary = summarise_model(
        issues_opened, issues_closed, prs_opened, prs_merged, open_prs, open_issues,
    )

    n_model = sum(1 for r in repos if r["is_model"])
    n_archived = sum(1 for r in repos if r["archived"])

    # Non-model activity / snapshots (itemised in the digest).
    nm_activity = {
        "issues_opened": nonmodel(issues_opened),
        "issues_closed": nonmodel(issues_closed),
        "prs_opened": nonmodel(prs_opened),
        "prs_merged": nonmodel(prs_merged),
    }
    nm_open_prs = nonmodel(open_prs)
    nm_open_issues = flag_easy(nonmodel(open_issues))

    counts = {
        "issues_opened": len(nm_activity["issues_opened"]),
        "issues_closed": len(nm_activity["issues_closed"]),
        "prs_opened": len(nm_activity["prs_opened"]),
        "prs_merged": len(nm_activity["prs_merged"]),
        "open_prs": len(nm_open_prs),
        "open_issues": len(nm_open_issues),
        "easy_candidates": sum(1 for it in nm_open_issues if it.get("easy_candidate")),
    }

    strat = stratify(repos)

    doc = {
        "window": {"from": d_from.isoformat(), "to": d_to.isoformat()},
        "org": args.org,
        "stale_days": args.stale_days,
        "connector_status": {"github": status},
        "repos": {
            "total": len(repos),
            "model": n_model,
            "nonmodel": len(repos) - n_model,
            "archived": n_archived,
            "trackable": strat["trackable"],
            "by_type": strat["by_type"],
            "by_status": strat["by_status"],
            "archived_list": strat["archived_list"],
            "list": repos,
        },
        "activity": nm_activity,
        "open_snapshot": {
            "open_prs": nm_open_prs,
            "open_issues": nm_open_issues,
        },
        "model_summary": model_summary,
        "counts": counts,
        "highlights": build_highlights(nm_activity, counts, model_summary),
    }

    write_json(args.out, doc)
    print(f"wrote {args.out}: {doc['repos']['total']} repos "
          f"({n_model} model), connector_status={status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
