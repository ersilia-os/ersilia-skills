"""Fetch the ersilia-os repository inventory that the Repositories table should mirror.

Reads every repository in the org (private ones too, so the `gh` login must be an org
member) and the org custom properties `status` and `type`, which the nightly cron
mirrors from Airtable. Writes

    {"org", "repos": [{"name", "description", "private", "fork", "archived",
                       "created_at", "gh_status", "gh_type", "is_model"}],
     "renames": {"<old Airtable name>": "<current GitHub name>"}, "errors": [...]}

When the Airtable dump is available (``--airtable``), every Airtable name that is not
in the org is looked up directly: GitHub redirects a renamed repository to its new
name, which tells a rename apart from a deletion without guessing.

Exit 1 if the repository list itself cannot be read: without it no Repositories check
is meaningful. A failed custom-property read is recorded in ``errors`` and the
Status/Type comparison is then skipped by `plan_sync.py`.

Usage:
    python fetch_github.py [--org ersilia-os] [--airtable /tmp/airtable_sync/repositories.json]
        [--out /tmp/airtable_sync/github.json]
"""

from __future__ import annotations

import argparse
import sys

from _common import MODEL_REPO_RE, WORK_DIR, die, read_json, run_gh_json, write_json


def _as_list(value) -> list[str]:
    """Normalise a custom-property value (None, str or list) to a list of strings."""
    if value in (None, ""):
        return []
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]


def main(argv: list[str] | None = None) -> int:
    """Write the org inventory to the work directory."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--org", default="ersilia-os")
    p.add_argument("--airtable", default=f"{WORK_DIR}/repositories.json")
    p.add_argument("--out", default=f"{WORK_DIR}/github.json")
    args = p.parse_args(argv)

    data, err = run_gh_json(
        ["api", "--paginate", f"orgs/{args.org}/repos?per_page=100&type=all"]
    )
    if data is None:
        die(f"could not list repositories of {args.org}: {err}")

    errors: list[str] = []
    props_raw, err = run_gh_json(
        ["api", "--paginate", f"orgs/{args.org}/properties/values?per_page=100"]
    )
    props: dict[str, dict] = {}
    if props_raw is None:
        errors.append(f"custom properties unavailable: {err}")
    else:
        for rec in props_raw:
            values = {
                x.get("property_name"): x.get("value")
                for x in rec.get("properties") or []
            }
            props[rec.get("repository_name")] = {
                "status": _as_list(values.get("status")),
                "type": _as_list(values.get("type")),
            }

    repos = []
    for r in data:
        name = r.get("name") or ""
        pr = props.get(name, {})
        repos.append(
            {
                "name": name,
                "description": (r.get("description") or "").strip(),
                "private": bool(r.get("private")),
                "fork": bool(r.get("fork")),
                "archived": bool(r.get("archived")),
                "created_at": (r.get("created_at") or "")[:10],
                "gh_status": pr.get("status", []),
                "gh_type": pr.get("type", []),
                "is_model": bool(MODEL_REPO_RE.match(name)),
            }
        )

    renames: dict[str, str] = {}
    in_org = {r["name"] for r in repos}
    for row in read_json(args.airtable) or []:
        old = row.get("name")
        if not old or old in in_org:
            continue
        hit, _ = run_gh_json(
            ["api", f"repos/{args.org}/{old}", "--jq", "{name: .name}"]
        )
        if isinstance(hit, dict) and hit.get("name") and hit["name"] != old:
            renames[old] = hit["name"]

    write_json(
        args.out,
        {
            "org": args.org,
            "repos": repos,
            "renames": renames,
            "errors": errors,
            "properties_ok": props_raw is not None,
        },
    )
    n_private = sum(r["private"] for r in repos)
    print(
        f"github: {len(repos)} repos ({n_private} private), {len(renames)} renamed"
        f" -> {args.out}"
    )
    for e in errors:
        print(f"  partial: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
