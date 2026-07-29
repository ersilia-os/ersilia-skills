# Airtable — Repositories table

The audit reads one record: the row for the repo being audited. It needs the `Type` (to pick a
profile) and the `Status` (a few checks depend on it, e.g. `ANA-BADGE-PENDING`,
`PKG-NO-RELEASE`). It **never writes**.

## IDs

| | |
|---|---|
| Base | **Ersilia Content** = `app1iYv78K6xbHkmL` |
| Table | **Repositories** = `tbluZtI3W9pseCSPH` |
| Records | ~179 (141 Public, 38 Private) |

The table is maintained by a nightly cron action, so metric columns are usually fresh and the
human-curated ones are not. Field IDs (verified 2026-07-28):

| Field | Field ID | Type |
|---|---|---|
| Name | `fldtnOlLM2rqUZQpr` | singleLineText — the join key, equals the GitHub repo name |
| Title | `fldYNOnc9KYHcQb7B` | singleLineText |
| Description | `fldBrXumaKuyUcgnH` | multilineText |
| Status | `fldbqy6izSeIK4L7M` | multipleSelects |
| Type | `fldaYAL5URJa3gnRB` | multipleSelects |
| Visibility | `fldXhoqkmBs6ZRhnn` | singleSelect |
| Projects | `fldLxYAsHn1MDlOh4` | multipleRecordLinks |
| Creation Date | `fldBH2270474FY9XW` | date |

## Vocabularies

**Status** — `Todo`, `In progress`, `Completed`, `Archived`, `Discontinued`, `Idle`.
**Type** — `Workshop`, `Package`, `Analysis`, `Automation`, `Template`, `App`, `Documentation`.

Both match the GitHub org custom properties 1:1, except that GitHub adds `Model` (model repos
live in a separate Airtable base and are out of scope for this skill).

Current type distribution, useful for calibration: Package 71, Analysis 69, Automation 14,
Workshop 11, App 8, Template 5, Documentation 3. Several repos carry two types
(`gradi-target-prioritization` is Analysis + App; `anpdb-annotation` is Analysis + Workshop).

## Reading the record

**Airtable is read by the LLM via MCP, never from a Python script** — the MCP is not reachable
from a subprocess. Fetch one record directly rather than dumping the table:

```
list_records_for_table(
  baseId  = "app1iYv78K6xbHkmL",
  tableId = "tbluZtI3W9pseCSPH",
  fieldIds = ["Name", "Title", "Description", "Status", "Type", "Visibility", "Creation Date"],
  filters = {"operands": [{"operator": "=", "operands": ["fldtnOlLM2rqUZQpr", "<repo-name>"]}]}
)
```

Multi-select cells come back as arrays of `{id, name, color}` objects — take the `.name`
strings. Write the result to `/tmp/repo_audit_type.json` in this shape:

```json
{
  "name": "eosquality",
  "title": "Quality of Ersilia predictions",
  "description": "...",
  "status": ["Todo"],
  "type": ["Package"],
  "visibility": "Public",
  "creation_date": "2026-04-16",
  "airtable_record_found": true,
  "type_source": "airtable"
}
```

Set `airtable_record_found: false` and keep `type` empty when there is no row — that is a real
finding (`T0-AIRTABLE-MISSING`), not an error. `type_source` records how the type was decided:
`airtable`, `github-properties`, `inferred`, or `user`.

## Fallbacks when Airtable has no answer

1. **GitHub org custom properties** — the cron mirrors Airtable into them, so they are a decent
   second source:
   ```bash
   gh api "orgs/ersilia-os/properties/values?per_page=100" --paginate \
     --jq '.[] | select(.repository_name=="<repo>") | .properties'
   ```
2. **File-based inference** — `pyproject.toml` or `setup.py` → Package; `notebooks/` or
   `data/raw/` → Analysis; only `.github/workflows/` and no package → Automation;
   `Dockerfile` plus a web framework → App; `SUMMARY.md` → Documentation.
3. **Ask.** If the record carries two types, or the fallbacks disagree, use `AskUserQuestion`.
   Do not guess — the profile determines most of the report, and a wrong profile makes the whole
   audit misleading.

Whatever the source, name it in the report header so the reader knows how much to trust the
profile choice.
