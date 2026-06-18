# Airtable "Repositories" registry — schema and reconciliation

The digest cross-checks GitHub against the **Repositories** table and reports drift. It is
**report-only**: the skill never writes to Airtable. (The table is maintained by a nightly
cron; the digest's job is to catch when that cron has gaps or when human-curated fields are
missing.)

## Locating the table (verified 2026-06-16)

- Base: **Ersilia Content** — `app1iYv78K6xbHkmL`
- Table: **Repositories** — `tbluZtI3W9pseCSPH` (≈181 records)
- Table description in Airtable: *"GitHub repositories. This table is automatically
  completed with a nightly cron action."*

Resolve these IDs at run time with the Airtable MCP rather than trusting the constants above
forever (a base/table can be renamed or rebuilt — that is exactly the kind of drift the
quarterly references refresh exists to catch). Find the base with
`search_bases "Ersilia Content"`, then `list_tables_for_base` to confirm the table ID.

## Fields

| Field | Type | Maintained by | Use in reconciliation |
|---|---|---|---|
| `Name` | singleLineText (primary) | cron | **Join key.** Repo slug → `github.com/ersilia-os/<Name>`. |
| `Title` | singleLineText | human | — |
| `Description` | multilineText | cron | — |
| `URL` | formula | cron | `https://github.com/ersilia-os/<Name>` |
| `Status` | singleSelect | **human** | Flag empty (`missing_status`). Choices: Todo, In progress, Completed, Archived, Discontinued, Idle. |
| `Type` | multipleSelects | **human** | Flag empty (`missing_type`). Choices: Workshop, Package, Analysis, Automation, Template, App, Documentation. |
| `Visibility` | singleSelect | cron | Public / Private. |
| `Projects` | multipleRecordLinks | **human** | Flag empty (`missing_projects`, informational). |
| `Stars`, `Forks`, `Open Issues`, `Subscribers`, `Total Commits`, `Contributors`, `Contributor Names` | number / text | cron | `Open Issues` feeds the soft `metric_drift` check. |
| `Creation Date` | date | cron | — |

`Status` values **Idle / Completed / Discontinued / Archived** are the "parked" set — a parked
repo with fresh activity in the window is surfaced as `active_but_parked`.

## Airtable ↔ GitHub value mapping (for the alignment check)

The same Status/Type are also exposed as **GitHub org custom properties** (`status`, `type`),
mirrored from this table by the nightly cron — see `scope.md`. `reconcile_airtable.py`
compares the two **strictly** and reports both values on a difference (`status_mismatch`,
`type_mismatch`). A mismatch means the mirror lagged or a side was hand-edited. The
vocabularies **match 1:1** (verified live 2026-06-18), so the mirror should be exact:

| Field | Airtable values | GitHub property values |
|---|---|---|
| Status | Todo, In progress, Completed, Archived, Discontinued, Idle | same |
| Type | Workshop, Package, Analysis, Automation, Template, App, Documentation | same **+ `Model`** |

`Model` exists only on GitHub (model repos are tracked in a separate Airtable base), so it
never appears in the Repositories-table comparison. There is no expected systematic mismatch
noise — any mismatch is a real drift to reconcile.

## Dumping records for the reconcile script

The Airtable MCP cannot be called from a Python subprocess, so the **skill itself** reads
the table via the MCP and writes a normalised JSON list to `/tmp/airtable_repos.json`, which
`reconcile_airtable.py` then consumes. Page through all records (use `list_records_for_table`
with a cursor; ~181 records ≈ 1 page at the default page size). Normalise each record to this
flat shape — **plain strings, not the `{id,name,color}` select objects**:

```json
[
  {
    "id": "recXXXXXXXXXXXXXX",
    "name": "ersilia",
    "title": "Ersilia Model Hub",
    "status": "In progress",
    "type": ["Package"],
    "projects": ["Ersilia Model Hub"],
    "stars": 210,
    "forks": 45,
    "open_issues": 42,
    "subscribers": 12,
    "total_commits": 1234,
    "contributors": 18,
    "contributor_names": "miquelduranfrigola, GemmaTuron, ...",
    "visibility": "Public",
    "creation_date": "2020-07-23"
  }
]
```

- `id` is the record's top-level `rec…` id from the MCP result — **required** so the metric
  sync (`sync_airtable_metrics.py`, SKILL Step 4) can target the right row. Records without an
  `id` are skipped by the sync.
- `name` is required (the join key). Records with no `Name` are counted as `airtable_unnamed`
  and skipped by reconcile.
- `type` and `projects` are lists; emit `[]` when empty. Include the **metric** fields (stars,
  forks, open_issues, subscribers, total_commits, contributors, contributor_names) with their
  current values so the sync can diff and push only what changed.
- For singleSelect/multiSelect cells the MCP returns objects — take the `.name` string.
- Omit any field that is genuinely empty rather than inventing a value.

**Large dumps are saved to a file.** Requesting all ~181 records in one call exceeds the MCP
token limit, so the harness writes the raw result to a `tool-results/…list_records_for_table…txt`
file and returns its path instead of the JSON. That is expected — do not page down to tiny
sizes to avoid it. Read that raw file and transform it: it is
`{"records": [{"id", "createdTime", "cellValuesByFieldId": {<fieldId>: value}}], "metadata": {...}}`.
Map the field IDs (verified 2026-06-18): `Name`=`fldtnOlLM2rqUZQpr`, `Title`=`fldYNOnc9KYHcQb7B`,
`Status`=`fldbqy6izSeIK4L7M`, `Type`=`fldaYAL5URJa3gnRB`, `Projects`=`fldLxYAsHn1MDlOh4`,
`Visibility`=`fldXhoqkmBs6ZRhnn`, `Creation Date`=`fldBH2270474FY9XW`, and the **metric** fields
`Stars`=`fldbQUSKXf0ncJtTH`, `Forks`=`fld54Du5w2IapXZOQ`, `Open Issues`=`fldcw1u9DyOzs54tx`,
`Subscribers`=`fld43sjGwxLYjrb5q`, `Total Commits`=`fldySp7DgJPKq7I93`,
`Contributors`=`fldznty61FrXKeIhl`, `Contributor Names`=`fldL50bcwVxhl889c`. (Re-confirm IDs with
`list_tables_for_base` if the freshness gate is overdue.) A short Python transform that reads the
saved file and writes `/tmp/airtable_repos.json` is the reliable path.

## Metric sync (GitHub → Airtable, the one write path)

`sync_airtable_metrics.py` refreshes the cron-maintained **metric** columns from live GitHub
state — strictly one-directional (GitHub is source of truth). It writes **only** these fields
and never the human-curated ones (Status, Type, Projects, Title):

| Airtable field | Field ID | GitHub source |
|---|---|---|
| Stars | `fldbQUSKXf0ncJtTH` | `stargazers_count` (from `fetch_github.py`) |
| Forks | `fld54Du5w2IapXZOQ` | `forks_count` (from `fetch_github.py`) |
| Open Issues | `fldcw1u9DyOzs54tx` | count of genuinely-open issues (PRs excluded), from the open snapshot |
| Subscribers | `fld43sjGwxLYjrb5q` | `subscribers_count` (per-repo `gh api repos/…`) |
| Total Commits | `fldySp7DgJPKq7I93` | ≈ sum of contributor `contributions` on the default branch |
| Contributors | `fldznty61FrXKeIhl` | count from `gh api repos/…/contributors` |
| Contributor Names | `fldL50bcwVxhl889c` | contributor logins, joined (capped, `+N more`) |

The script emits an **update plan** (`/tmp/airtable_updates.json`) with only changed
records/fields, each `fields` object keyed by the field IDs above, plus a `summary` for the
digest's sync note. The skill applies it via the MCP `update_records_for_table` (≤ 50 records
per request). A metric whose GitHub value can't be determined is left untouched, not zeroed.

## What the reconciliation reports

`reconcile_airtable.py` emits `/tmp/health.json` with these findings (all report-only):

- **`missing_from_airtable`** — trackable org repos (non-model, non-fork) absent from the
  table. Strongest signal: either a brand-new repo the cron hasn't picked up, or a cron gap.
- **`stale_in_airtable`** — table records whose repo no longer exists in the org (renamed,
  deleted, transferred).
- **`status_mismatch` / `type_mismatch`** — Airtable Status/Type disagrees (strict compare)
  with the GitHub custom property mirrored from it; both values reported. Only when **both**
  sides carry a value. The vocabularies match 1:1 (see mapping above), so a mismatch is real
  drift (cron lagged or a side hand-edited), not expected noise.
- **`missing_status` / `missing_type` / `missing_projects`** — human-curated fields left
  empty. These never get auto-filled, so they are the human to-do list.
- **`active_but_parked`** — records marked Idle/Completed/Discontinued/Archived that saw
  issue/PR activity this window; the status likely needs revisiting.
- **`metric_drift`** — *heuristic, soft signal, now largely moot.* Since Step 4 syncs Open
  Issues from GitHub, this should be ~0; a residual gap (the REST `open_issues_count` folds in
  PRs) is worth a glance, never a hard error. Surface only when non-empty.
