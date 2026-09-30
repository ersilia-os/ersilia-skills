"""Compare the Airtable tables with their sources and write a numbered change plan.

Deterministic: every decision comes from `references/rules.json` and
`references/ignore-list.json`, never from the model. Inputs are the files the other
scripts leave in the work directory:

    repositories.json publications.json blogposts.json community.json   (normalise_airtable.py)
    github.json openalex.json medium.json                                (fetch_*.py)

community.json is optional: authors already linked on Blogposts rows are used first.
A table whose inputs are missing is skipped and listed under ``skipped``. Output:

    {"items": [{"n", "table", "action", "record_id", "label", "fields", "current",
                "judgement", "reason", "priority", "ignore_key", ...}],
     "gaps": [{"table", "record_id", "label", "missing"}],
     "skipped": [...], "counts": {...}}

``action`` is one of:

    update  change fields of a row            create  add a row
    choice  Airtable and GitHub disagree:     github  a gh command (``command``)
            the user picks a side (``options``)
    delete  the row's repo is gone             flag    report only, never written

Everything except ``flag`` is written only after the user approves it.
``fields`` and ``current`` use the keys of `_common.TABLES`, not field IDs;
`build_writes.py` maps them. ``judgement`` lists fields the model must fill before a
create is written. ``priority`` 1 means "fix first".

Usage:
    python plan_sync.py [--work /tmp/airtable_sync] [--rules ...] [--ignore ...] \
        [--out /tmp/airtable_sync/plan.json]
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from datetime import date
from pathlib import Path

from _common import (
    AFRICA_ISO2,
    SKILL_DIR,
    STATS_FIELDS,
    WORK_DIR,
    clean_url,
    doi_url,
    medium_post_id,
    medium_slug,
    norm_name,
    norm_title,
    normalise_doi,
    read_json,
    write_json,
)


def _empty(value) -> bool:
    return value in (None, "", []) or (isinstance(value, list) and not any(value))


def _same(a, b) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return set(a or []) == set(b or [])
    return (a or None) == (b or None)


def decide(policy: str, current, proposed, subset_ok: bool = False) -> str | None:
    """Return 'update', 'flag' or None for one field under a rules.json policy.

    ``subset_ok`` treats a multi-select source whose values are all in Airtable as
    agreeing (GitHub often mirrors only part of a multi-value Status or Type).
    """
    if _empty(proposed) or _same(current, proposed):
        return None
    if subset_ok and isinstance(proposed, list) and set(proposed) <= set(current or []):
        return None
    if _empty(current):
        return "flag" if policy == "flag" else "update"
    if policy == "overwrite":
        return "update"
    if policy == "flag":
        return "flag"
    return None  # fill_empty never overrides a value a person chose


def similar(a: str, b: str, threshold: float) -> bool:
    """True if two titles are the same work, allowing punctuation and small edits."""
    na, nb = norm_title(a), norm_title(b)
    if not na or not nb:
        return False
    if na == nb or (min(len(na), len(nb)) > 40 and (na in nb or nb in na)):
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= threshold


def african_collaboration(work: dict) -> str | None:
    """Yes/No from the author institution countries OpenAlex recorded, or None."""
    if "countries" not in work:
        return None
    return "Yes" if set(work["countries"]) & AFRICA_ISO2 else "No"


def _surnames(authors) -> set[str]:
    return {norm_title(a).split()[-1] for a in authors or [] if norm_title(a)}


def same_work(a: dict, b: dict, rules: dict) -> bool:
    """True if two OpenAlex works are versions of one paper (preprint and article).

    Titles often change between a preprint and its published version, so a strong
    author overlap within a couple of years also counts, when at least one of the two
    is a preprint or a repository record.
    """
    if similar(a.get("title"), b.get("title"), rules["title_match_threshold"]):
        return True
    sa, sb = _surnames(a.get("authors")), _surnames(b.get("authors"))
    if min(len(sa), len(sb)) < rules["version_min_authors"]:
        return False
    overlap = len(sa & sb) / len(sa | sb)
    years = abs((a.get("year") or 0) - (b.get("year") or 0))
    loose = {a.get("type"), b.get("type")} & {"preprint"} or "repository" in {
        a.get("source_type"),
        b.get("source_type"),
    }
    return bool(
        loose
        and overlap >= rules["version_author_overlap"]
        and years <= rules["version_max_years"]
    )


class Planner:
    """Accumulates plan items across tables."""

    def __init__(self, ignore: set[str]):
        self.items: list[dict] = []
        self.gaps: list[dict] = []
        self.skipped: list[str] = []
        self.ignore = ignore

    def add(
        self,
        table,
        action,
        label,
        reason,
        *,
        record_id=None,
        fields=None,
        current=None,
        judgement=None,
        priority=2,
        ignore_key=None,
        extra=None,
    ):
        """Append one plan item, unless its candidate key is on the ignore list.

        ``extra`` carries action-specific keys: ``command`` for a ``github`` item,
        ``options`` for a ``choice`` item.
        """
        if ignore_key and ignore_key in self.ignore:
            return
        self.items.append(
            {
                "table": table,
                "action": action,
                "record_id": record_id,
                "label": label,
                "fields": fields or {},
                "current": current or {},
                "judgement": judgement or [],
                "reason": reason,
                "priority": priority,
                "ignore_key": ignore_key,
                **(extra or {}),
            }
        )

    def field_changes(
        self, table, row, label, proposals, policies, reasons, subset_ok=()
    ):
        """Group every 'update' into one item per record; emit one flag per 'flag'."""
        updates = {}
        for key, proposed in proposals.items():
            verdict = decide(
                policies.get(key, "flag"), row.get(key), proposed, key in subset_ok
            )
            if verdict == "update":
                updates[key] = proposed
            elif verdict == "flag":
                self.add(
                    table,
                    "flag",
                    label,
                    f"{key}: Airtable {row.get(key)!r}, source {proposed!r}",
                    record_id=row["id"],
                )
        if updates:
            why = "; ".join(reasons.get(k, f"{k} from source") for k in updates)
            urgent = any(reasons.get(k, "").endswith("!") for k in updates)
            self.add(
                table,
                "update",
                label,
                why,
                record_id=row["id"],
                fields=updates,
                current={k: row.get(k) for k in updates},
                priority=1 if urgent else 2,
            )

    def gap_check(self, table, rows, label_key):
        """Record rows missing a field the stats site reads that no update will fill."""
        pending = {
            (i["record_id"], k)
            for i in self.items
            if i["action"] == "update"
            for k in i["fields"]
        }
        for row in rows:
            missing = [
                k
                for k in STATS_FIELDS[table]
                if _empty(row.get(k)) and (row["id"], k) not in pending
            ]
            if missing:
                self.gaps.append(
                    {
                        "table": table,
                        "record_id": row["id"],
                        "label": row.get(label_key) or row["id"],
                        "missing": missing,
                    }
                )


def check_description(pl: Planner, row, repo, rules):
    """Every Ersilia repository needs a description, on GitHub and in Airtable.

    Airtable is filled from GitHub by the normal field policy. When only Airtable has
    one, rules decide: ``github_description_action: "propose"`` offers a ``github``
    item (a ``gh repo edit`` run only if approved); anything else just flags it.
    """
    name = row.get("name") or repo["name"]
    at_desc = (row.get("description") or "").strip()
    if repo["description"]:
        return
    if repo.get("archived") and rules.get("description_skip_archived"):
        return  # archived repos are read-only on GitHub; the user chose to ignore them
    if at_desc:
        command = ["gh", "repo", "edit", f"ersilia-os/{name}", "--description", at_desc]
        if rules.get("github_description_action") == "propose":
            pl.add(
                "repositories",
                "github",
                name,
                "no description on GitHub; copy the Airtable one to GitHub",
                record_id=row.get("id"),
                current={"github description": None},
                fields={"github description": at_desc},
                extra={"command": command},
            )
        else:
            pl.add(
                "repositories",
                "flag",
                name,
                "no description on GitHub; Airtable has one: " + " ".join(command),
                record_id=row.get("id"),
            )
    else:
        pl.add(
            "repositories",
            "flag",
            name,
            "no description on GitHub or in Airtable: every repository needs one",
            record_id=row.get("id"),
            priority=1,
        )


def ask_which_side(pl: Planner, row, name, key, gh_value, rules):
    """Turn a real Status/Type disagreement into a choice: which side is right?

    Both sides are writable: Airtable through the connector, GitHub through the org
    custom property. A GitHub value that is a subset of Airtable's is not a
    disagreement (the mirror often carries only part of a multi-value field).
    """
    at_value = row.get(key) or []
    subset_ok = key in rules.get("subset_ok_fields", [])
    if _empty(gh_value) or _same(at_value, gh_value):
        return
    if subset_ok and set(gh_value) <= set(at_value):
        return
    if _empty(at_value):
        pl.add(
            "repositories",
            "update",
            name,
            f"{key} empty in Airtable, GitHub property says {', '.join(gh_value)}",
            record_id=row["id"],
            fields={key: gh_value},
            current={key: at_value},
        )
        return
    body = {"properties": [{"property_name": key, "value": at_value}]}
    pl.add(
        "repositories",
        "choice",
        name,
        f"{key} disagrees: Airtable {', '.join(at_value)}; GitHub {', '.join(gh_value)}",
        record_id=row["id"],
        extra={
            "options": {
                "use-github": {
                    "label": f"GitHub is right: set Airtable {key} to {', '.join(gh_value)}",
                    "fields": {key: gh_value},
                    "current": {key: at_value},
                },
                "use-airtable": {
                    "label": f"Airtable is right: set GitHub {key} to {', '.join(at_value)}",
                    "command": [
                        "gh",
                        "api",
                        "-X",
                        "PATCH",
                        f"repos/ersilia-os/{name}/properties/values",
                        "--input",
                        "-",
                    ],
                    "stdin": json.dumps(body),
                    "check": {"property": key, "value": at_value},
                },
            }
        },
    )


def infer_renames(rows, all_gh, tracked, by_name, known) -> dict[str, str]:
    """Pair a row whose repo is gone with an untracked repo that is clearly the same.

    GitHub only redirects a renamed repository; one that was recreated under a new
    name has no redirect. Same creation date plus the same description (or one name
    extending the other) is treated as a rename, so the curated row is kept rather
    than deleted and duplicated. Each repo is paired at most once.
    """
    untracked = {n: x for n, x in tracked.items() if n not in by_name}
    taken = set(known.values())
    out: dict[str, str] = {}
    for row in rows:
        old = row.get("name") or ""
        if not old or old in all_gh or old in known:
            continue
        for name, repo in sorted(untracked.items()):
            if name in taken or repo["created_at"] != row.get("creation_date"):
                continue
            same_desc = (
                repo["description"]
                and repo["description"] == (row.get("description") or "").strip()
            )
            if same_desc or name.startswith(old) or old.startswith(name):
                out[old] = name
                taken.add(name)
                break
    return out


def plan_repositories(pl: Planner, rows, gh, rules):
    """Repositories vs the GitHub org inventory."""
    r = rules["repositories"]
    policy = r["field_policy"]
    skip = set(r.get("skip_names", []))
    all_gh = {x["name"]: x for x in gh["repos"]}
    tracked = {
        n: x
        for n, x in all_gh.items()
        if not x["is_model"]
        and n not in skip
        and not (r.get("skip_forks") and x["fork"])
    }
    by_name = {row["name"]: row for row in rows if row.get("name")}
    renames = {
        old: new for old, new in (gh.get("renames") or {}).items() if new in all_gh
    }
    if r.get("infer_renames"):
        renames.update(infer_renames(rows, all_gh, tracked, by_name, renames))
    renamed_to = set(renames.values())
    props_ok = gh.get("properties_ok", True)
    if not props_ok:
        pl.skipped.append(
            "repositories: GitHub custom properties unavailable, Status/Type not compared"
        )

    for name, repo in sorted(tracked.items()):
        if name in by_name or name in renamed_to:
            continue
        vis = "Private" if repo["private"] else "Public"
        fields = {
            "name": name,
            "description": repo["description"],
            "visibility": vis,
            "creation_date": repo["created_at"],
            "status": repo["gh_status"],
            "type": [t for t in repo["gh_type"] if t != "Model"],
        }
        fields = {
            k: v for k, v in fields.items() if k in r["create_with"] and not _empty(v)
        }
        pl.add(
            "repositories",
            "create",
            name,
            f"on GitHub ({vis.lower()}), missing from Airtable",
            fields=fields,
            ignore_key=f"repo:{name}",
        )
        if r.get("require_description") and not repo["description"]:
            check_description(pl, {"name": name}, repo, r)

    for row in rows:
        name = row.get("name") or ""
        repo = all_gh.get(name)
        if repo is None and name in renames:
            new = renames[name]
            if new in by_name:
                pl.add(
                    "repositories",
                    "flag",
                    name,
                    f"renamed on GitHub to {new}, which already has its own row:"
                    " one of the two rows is a duplicate",
                    record_id=row["id"],
                )
                continue
            pl.add(
                "repositories",
                "update",
                name,
                f"renamed on GitHub: {name} is now {new}"
                + (
                    ""
                    if name in (gh.get("renames") or {})
                    else " (no redirect; same creation date and description)"
                ),
                record_id=row["id"],
                fields={"name": new},
                current={"name": name},
                priority=1,
            )
            repo = all_gh[new]
            row = {**row, "name": new}
            name = new
        if repo is None:
            gone = "no such repository on GitHub, and GitHub has no redirect for it"
            if r.get("gone_repo_action") == "propose_delete":
                pl.add(
                    "repositories",
                    "delete",
                    name or row["id"],
                    gone + ": delete the Airtable row",
                    record_id=row["id"],
                    current={"title": row.get("title"), "status": row.get("status")},
                )
            else:
                pl.add(
                    "repositories",
                    "flag",
                    name or row["id"],
                    gone,
                    record_id=row["id"],
                    priority=1 if row.get("visibility") == "Public" else 2,
                )
            continue
        if repo["is_model"]:
            pl.add(
                "repositories",
                "flag",
                name,
                "model repository: belongs in the Model Hub base",
                record_id=row["id"],
            )
            continue
        vis = "Private" if repo["private"] else "Public"
        reasons = {
            "visibility": f"GitHub says {vis}",
            "creation_date": "GitHub created_at",
            "description": "empty in Airtable, taken from GitHub",
        }
        if row.get("visibility") == "Public" and vis == "Private":
            reasons["visibility"] = (
                "private on GitHub but Public in Airtable: stats site would publish the name!"
            )
        proposals = {
            "visibility": vis,
            "creation_date": repo["created_at"],
            "description": repo["description"],
        }
        if props_ok:
            proposals["status"] = repo["gh_status"]
            proposals["type"] = [t for t in repo["gh_type"] if t != "Model"]
            if r.get("status_type_mismatch") == "ask":
                for key in ("status", "type"):
                    ask_which_side(pl, row, name, key, proposals.pop(key), r)
        pl.field_changes(
            "repositories",
            row,
            name,
            proposals,
            policy,
            reasons,
            subset_ok=set(r.get("subset_ok_fields", [])),
        )
        if r.get("require_description"):
            check_description(pl, row, repo, r)
        if (
            r.get("flag_archived_without_status")
            and repo["archived"]
            and "Archived" not in (row.get("status") or [])
        ):
            pl.add(
                "repositories",
                "flag",
                name,
                f"archived on GitHub, Airtable Status is {row.get('status') or 'empty'}",
                record_id=row["id"],
            )
    pl.gap_check("repositories", rows, "name")


def _pub_fields(work: dict, rules: dict, team_ids: set[str] = frozenset()) -> dict:
    authors = work["authors"]
    author_text = ", ".join(authors) if len(authors) <= 25 else f"{authors[0]} et al."
    status = rules["status_by_source_type"].get(
        work.get("source_type") or "", rules["status_default"]
    )
    link = doi_url(work["doi"]) if work.get("doi") else None
    fields = {
        "title": work["title"],
        "authors": author_text,
        "journal": work.get("source_name"),
        "doi": link,
        "url": work.get("landing_url") or link,
        "year": str(work["year"]) if work.get("year") else None,
        "status": status,
        "type": rules["type_map"].get(work.get("type") or "", "Research"),
        "affiliation": "Yes" if work.get("institution_hit") else "No",
    }
    fields["african_collaboration"] = african_collaboration(work)
    if "senior_author_ids" in work:
        ours = team_ids | set(work.get("ersilia_author_ids") or [])
        fields["senior"] = "Yes" if ours & set(work["senior_author_ids"]) else "No"
    return {k: v for k, v in fields.items() if not _empty(v)}


def published_version(pl: Planner, row, label, oa, r, by_doi_row) -> bool:
    """Propose the journal version of a Preprint row, if OpenAlex found one.

    Returns True when an item was added for this row (an update, or a flag when the
    published DOI already belongs to another row), so the caller skips the ordinary
    fill-ins that would otherwise compete with it for DOI, journal and year.
    """
    for cand in oa.get("title_matches", {}).get(row["id"], []):
        if not (
            cand.get("source_type") == "journal"
            and cand.get("doi")
            and cand["doi"] != normalise_doi(row.get("doi"))
            and similar(cand["title"], row.get("title"), r["title_match_threshold"])
        ):
            continue
        owner = by_doi_row.get(cand["doi"])
        if owner is not None:
            pl.add(
                "publications",
                "flag",
                label,
                f"published version {cand['doi']} is already the row"
                f" {owner.get('slug') or owner['id']}: one of the two is a duplicate",
                record_id=row["id"],
            )
            return True
        fields = {
            k: v
            for k, v in _pub_fields(cand, r).items()
            if k in ("doi", "url", "journal", "year", "status")
        }
        pl.add(
            "publications",
            "update",
            label,
            f"published version found in {cand.get('source_name')}",
            record_id=row["id"],
            fields=fields,
            current={k: row.get(k) for k in fields},
            priority=1,
        )
        return True
    return False


def plan_publications(pl: Planner, rows, oa, rules, sources):
    """Publications vs OpenAlex."""
    r = rules["publications"]
    thr = r["title_match_threshold"]
    team = {a["id"]: a["name"] for a in sources["openalex"]["authors"]}
    by_doi_row = {
        normalise_doi(row.get("doi")): row
        for row in rows
        if normalise_doi(row.get("doi"))
    }

    for row in rows:
        label = row.get("slug") or row.get("title") or row["id"]
        if published_version(pl, row, label, oa, r, by_doi_row):
            continue  # that update sets DOI, journal and year; don't propose rivals
        work = oa["by_doi"].get(normalise_doi(row.get("doi")) or "")
        if work is None and not row.get("doi"):
            work = next(
                (
                    w
                    for w in oa["works"]
                    if w.get("doi") and similar(w["title"], row.get("title"), thr)
                ),
                None,
            )
        if work:
            proposals = {
                "year": str(work["year"]) if work.get("year") else None,
                "journal": work.get("source_name"),
                "doi": doi_url(work["doi"]) if work.get("doi") else None,
                "african_collaboration": african_collaboration(work),
            }
            countries = ", ".join(work.get("countries") or []) or "none recorded"
            pl.field_changes(
                "publications",
                row,
                label,
                proposals,
                r["field_policy"],
                {
                    "year": "OpenAlex year",
                    "journal": "OpenAlex source",
                    "doi": "matched by title in OpenAlex",
                    "african_collaboration": f"author countries in OpenAlex: {countries}",
                },
            )
            if (
                r.get("flag_year_mismatch")
                and row.get("year")
                and work.get("year")
                and str(work["year"]) != str(row["year"])
            ):
                pl.add(
                    "publications",
                    "flag",
                    label,
                    f"Year {row['year']} in Airtable, {work['year']} in OpenAlex",
                    record_id=row["id"],
                )

    # Existing rows as works: their titles, plus the OpenAlex record behind each DOI,
    # which carries the author list needed to spot a preprint under another title.
    existing = [{"title": row.get("title") or ""} for row in rows]
    existing += list(oa["by_doi"].values())
    chosen: list[dict] = []
    # Sorted by DOI so ties (Zenodo concept vs version DOI) resolve the same way every run.
    for w in sorted(oa["works"], key=lambda x: x.get("doi") or ""):
        if w.get("doi") and w["doi"] in by_doi_row:
            continue
        if r.get("skip_versions_of_existing") and any(
            same_work(w, e, r) for e in existing
        ):
            continue
        rank = (
            w.get("source_type") == "journal",
            w.get("type") != "preprint",
            -(len(w.get("doi") or "")),
        )
        prev = next((c for c in chosen if same_work(c, w, r)), None)
        if prev is None:
            chosen.append({**w, "_rank": rank})
        elif rank > prev["_rank"]:
            chosen[chosen.index(prev)] = {**w, "_rank": rank}
    for w in chosen:
        hits = [team[a] for a in w["author_ids"] if a in team]
        evidence = (
            "Ersilia affiliation"
            if w["institution_hit"]
            else f"team author {', '.join(hits)}"
        )
        pl.add(
            "publications",
            "create",
            w["title"][:90],
            f"{w.get('year')} {w.get('type')} in {w.get('source_name') or 'unknown venue'} ({evidence})",
            fields=_pub_fields(w, r, set(team)),
            judgement=list(r["judgement_fields"]),
            ignore_key=f"doi:{w['doi']}"
            if w.get("doi")
            else f"openalex:{w['openalex_id']}",
        )
    pl.gap_check("publications", rows, "slug")


def resolve_author(name: str, community: list[dict], aliases: dict) -> dict | None:
    """Match a Medium author name to exactly one Community record."""
    target = aliases.get(name, name)
    exact = [c for c in community if norm_title(c.get("name")) == norm_title(target)]
    if len(exact) == 1:
        return exact[0]
    tokens = norm_name(target)
    loose = [
        c
        for c in community
        if tokens
        and (tokens <= norm_name(c.get("name")) or norm_name(c.get("name")) <= tokens)
        and norm_name(c.get("name"))
    ]
    return loose[0] if len(loose) == 1 else None


def plan_blogposts(pl: Planner, rows, medium, community, rules):
    """Blogposts vs Medium RSS."""
    r = rules["blogposts"]
    tol = r["date_tolerance_days"]
    # Authors already linked on existing rows are Community records too, so a full
    # Community read is only needed for someone who has never blogged before.
    known = {a["id"]: a for row in rows for a in row.get("author") or [] if a.get("id")}
    known.update({c["id"]: c for c in community or []})
    community = list(known.values())
    by_id = {
        medium_post_id(row.get("url")): row
        for row in rows
        if medium_post_id(row.get("url"))
    }
    by_url = {clean_url(row.get("url")): row for row in rows if row.get("url")}

    for post in medium["posts"]:
        row = by_id.get(post["post_id"]) or by_url.get(post["url"])
        if row is None:
            author = resolve_author(post["author"], community, r["author_aliases"])
            fields = {
                "title": post["title"],
                "date": post["date"],
                "url": post["url"],
                "slug": medium_slug(post["url"]),
                "publisher": r["default_publisher"],
            }
            if author:
                fields["author"] = [author["id"]]
            reason = f"on Medium {post['date']}, missing from Airtable"
            judgement = list(r["judgement_fields"])
            if not author:
                reason += (
                    f"; author {post['author']!r} not linked yet, look up in Community"
                )
                judgement.append("author")
            pl.add(
                "blogposts",
                "create",
                post["title"][:90],
                reason,
                fields=fields,
                judgement=judgement,
                ignore_key=f"medium:{post['post_id'] or post['url']}",
            )
            continue
        label = row.get("slug") or row.get("title") or row["id"]
        updates, why = {}, []
        if (
            r.get("prefer_publication_url")
            and post["in_publication"]
            and "/ersiliaio/" not in (row.get("url") or "")
        ):
            updates["url"] = post["url"]
            why.append("post is now in the Ersilia publication")
        elif (
            r.get("prefer_feed_url")
            and clean_url(row.get("url")) != post["url"]
            and medium_slug(post["url"]) != post["post_id"]
            # never trade a publication URL for a personal-feed one
            and (post["in_publication"] or "/ersiliaio/" not in (row.get("url") or ""))
        ):
            updates["url"] = post["url"]
            why.append("use the full URL from the feed")
        if _empty(row.get("date")) and post["date"]:
            updates["date"] = post["date"]
            why.append("date from Medium")
        elif row.get("date") and post["date"]:
            delta = abs(
                (
                    date.fromisoformat(row["date"]) - date.fromisoformat(post["date"])
                ).days
            )
            if delta > tol:
                pl.add(
                    "blogposts",
                    "flag",
                    label,
                    f"Date {row['date']} in Airtable, {post['date']} on Medium",
                    record_id=row["id"],
                )
        if _empty(row.get("author")):
            author = resolve_author(post["author"], community, r["author_aliases"])
            if author:
                updates["author"] = [author["id"]]
                why.append(f"author {author['name']}")
        if updates:
            pl.add(
                "blogposts",
                "update",
                label,
                "; ".join(why),
                record_id=row["id"],
                fields=updates,
                current={k: row.get(k) for k in updates},
            )

    if r.get("strip_medium_tracking"):
        planned = {
            i["record_id"]
            for i in pl.items
            if i["action"] == "update" and "url" in i["fields"]
        }
        for row in rows:
            url = row.get("url") or ""
            if row["id"] not in planned and clean_url(url) != url.strip():
                pl.add(
                    "blogposts",
                    "update",
                    row.get("slug") or row["id"],
                    "strip Medium tracking query",
                    record_id=row["id"],
                    fields={"url": clean_url(url)},
                    current={"url": url},
                )
    pl.gap_check("blogposts", rows, "slug")


def main(argv: list[str] | None = None) -> int:
    """Build the plan from whatever inputs are present."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--rules", default=str(SKILL_DIR / "references" / "rules.json"))
    p.add_argument("--sources", default=str(SKILL_DIR / "references" / "sources.json"))
    p.add_argument(
        "--ignore", default=str(SKILL_DIR / "references" / "ignore-list.json")
    )
    p.add_argument("--out")
    args = p.parse_args(argv)

    work = Path(args.work)
    rules, sources = read_json(args.rules), read_json(args.sources)
    ignore = {e["key"] for e in (read_json(args.ignore) or {}).get("entries", [])}
    pl = Planner(ignore)

    def load(name):
        return read_json(work / f"{name}.json")

    repos, gh = load("repositories"), load("github")
    if repos is not None and gh is not None:
        plan_repositories(pl, repos, gh, rules)
    else:
        pl.skipped.append("repositories: Airtable dump or github.json missing")

    pubs, oa = load("publications"), load("openalex")
    if pubs is not None and oa is not None:
        plan_publications(pl, pubs, oa, rules, sources)
        pl.skipped += [f"publications: {e}" for e in oa.get("errors", [])]
    else:
        pl.skipped.append("publications: Airtable dump or openalex.json missing")

    blogs, medium, community = load("blogposts"), load("medium"), load("community")
    if blogs is not None and medium is not None:
        plan_blogposts(pl, blogs, medium, community or [], rules)
        pl.skipped += [f"blogposts: {e}" for e in medium.get("errors", [])]
    else:
        pl.skipped.append("blogposts: Airtable dump or medium.json missing")

    order = {"repositories": 0, "publications": 1, "blogposts": 2}
    act = {"update": 0, "create": 1, "choice": 2, "github": 3, "delete": 4, "flag": 5}
    pl.items.sort(
        key=lambda i: (order[i["table"]], i["priority"], act[i["action"]], i["label"])
    )
    for n, item in enumerate(pl.items, 1):
        item["n"] = n
    counts = {}
    for i in pl.items:
        counts.setdefault(i["table"], {}).setdefault(i["action"], 0)
        counts[i["table"]][i["action"]] += 1
    out = args.out or str(work / "plan.json")
    write_json(
        out,
        {"items": pl.items, "gaps": pl.gaps, "skipped": pl.skipped, "counts": counts},
    )
    print(f"plan: {len(pl.items)} items, {len(pl.gaps)} rows with gaps -> {out}")
    for t, c in counts.items():
        print(f"  {t}: " + ", ".join(f"{v} {k}" for k, v in sorted(c.items())))
    for s in pl.skipped:
        print(f"  skipped: {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
