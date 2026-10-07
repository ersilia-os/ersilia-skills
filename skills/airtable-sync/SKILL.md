---
name: airtable-sync
description: >
  Keep the Ersilia Content Airtable base in step with reality, so the ersilia-stats site
  (ersilia-os.github.io/ersilia-stats) reports true numbers. Compares the Repositories
  table with the ersilia-os GitHub org, Publications with OpenAlex, Blogposts with
  Medium, Events with the Presentations and Photos Drive folders (plus the
  Trainings drive, the workshops GitBook and the calendar), and Grants with the
  Grants Drive; proposes new rows,
  corrections and missing fields; and walks the user through
  every proposed change, writing to Airtable only what the user approves, step by step.
  Learns from the user's feedback on every run. Triggers include: "sync Airtable",
  "airtable sync", "/airtable-sync", "is Airtable up to date", "update the stats data",
  "check the Airtable content", "are all our repos/papers/blog posts/events/grants in Airtable",
  "which events are missing", "check the grants table".
  Always use this skill for these requests, even if the ask seems simple.
---

# Airtable sync

You bring the **Ersilia Content** base (`app1iYv78K6xbHkmL`) in line with what exists:

| Table | Checked against |
|---|---|
| Repositories | the `ersilia-os` GitHub org (repos, visibility, dates, descriptions, custom properties) |
| Publications | OpenAlex (Ersilia institution `I4394709285` and the team authors) |
| Blogposts | Medium RSS (the `ersiliaio` publication and personal feeds) |
| Events | dated folders in the Presentations and Photos shared drives; the Trainings drive, the workshops GitBook and the calendar by hand |
| Grants | one folder per application in the Grants shared drive, inside year folders |

The ersilia-stats site reads these tables, so a missing row or empty field makes a chart wrong without anyone noticing.

## The one rule

**Never write to Airtable, or to GitHub, without the user's explicit permission for those items, in this run, given after they have seen them.** This holds in auto mode too. A plan, an earlier approval, or "it's obviously right" is not permission. Flags are never written. Deleting a row and running a `gh` command are writes too, and need the same approval.

## How the work is split

Scripts decide; you explain, fill the judgement fields and ask. Everything deterministic is in `scripts/`, and every policy is data in `references/rules.json`. Don't re-derive in your head what a script already computed. If a script gets something wrong, fix the script or the rule (Step 8) rather than working around it.

Scripts run from `scripts/` with the Python 3 standard library only, and work in `/tmp/airtable_sync/`.

| Script | Does |
|---|---|
| `check_references_freshness.py` | Says whether the reference files are due for a re-check |
| `record_feedback.py` | Lists the lessons (`list`) or logs a new one (`add`) |
| `normalise_airtable.py` | Turns connector dumps into one clean JSON list per table |
| `fetch_github.py`, `fetch_openalex.py`, `fetch_medium.py` | Read the sources (read-only) |
| `collect_event_folders.py` | Turns Drive folder listings into dated event candidates |
| `collect_grant_folders.py` | Turns the Grants drive listings into grant candidates (year from the parent folder) |
| `plan_sync.py` | Compares tables with sources and writes the numbered plan |
| `render_plan.py` | Shows the plan as review steps (`--steps`, `--step k`, `--gaps`) |
| `build_writes.py` | Turns approved item numbers into connector calls; records rejections |
| `apply_github.py` | Runs approved `gh` commands and reads the values back |
| `verify_writes.py` | Checks re-read records against what was written |
| `selftest.py` | Offline regression test over `examples/cases/` |

## Workflow

### 0. Pre-flight

1. `python check_references_freshness.py`. If it says `DUE`, ask the user whether to re-verify the field IDs in `references/airtable-tables.md` now or defer. Log the answer in `references/_state.json`.
2. `python record_feedback.py list`. Read every lesson and apply them this run. They explain why the rules are what they are.
3. Check the Airtable connector: `list_bases` must show "Ersilia Content". Check `gh auth status`. If either fails, stop and say which.
4. `rm -rf /tmp/airtable_sync && mkdir -p /tmp/airtable_sync/raw`.

### 1. Read Airtable (connector, read-only)

Call `list_records_for_table` once per table, with **only these field IDs** (from `references/airtable-tables.md`) and `pageSize: 500`:

- Repositories `tbluZtI3W9pseCSPH`: all 8 fields.
- Publications `tbljYubYjWAtO1ab8`: slug, title, journal, doi, status, year, affiliation, topic, type, african_collaboration.
- Blogposts `tblsBj6ZoDNMlmrzm`: all 7 fields.
- Events `tbltd1A9nnXy6Ug8p`: name, description, date, url, organisations, country, category, format, participants, grants, projects.
- Grants `tblBtzVd3YvE53PnJ`: name, short name, organisation, type, submission, status, description, ersilia.
- Organisations `tblxKMlzYuoSzBaDC`: name, acronym (the grant matcher uses funder acronyms). Large: pass the saved file straight to the normaliser.

Save each response to a file, then normalise it:

- A large response is saved to a `tool-results/…txt` file by the harness. Pass that path straight to the normaliser; don't read it.
- A small response comes back inline. Write it to `/tmp/airtable_sync/raw/<table>.json`. You may drop `createdTime` and reduce select objects to their `name` string; the normaliser accepts both.
- If a response has a `nextCursor`, fetch the next page too and pass every page file.

```
python normalise_airtable.py --table repositories --in <file> [<file2> ...]
python normalise_airtable.py --table publications --in /tmp/airtable_sync/raw/publications.json
python normalise_airtable.py --table blogposts   --in /tmp/airtable_sync/raw/blogposts.json
python normalise_airtable.py --table events      --in <file>
python normalise_airtable.py --table grants      --in <file>
python normalise_airtable.py --table organisations --in <file>
```

Community is **not** read up front: authors already linked on Blogposts rows are enough. Read it only if the plan asks you to (Step 4).

### 2. Fetch the sources (read-only)

```
python fetch_github.py      # org inventory + custom properties + renames (needs repositories.json)
python fetch_openalex.py    # needs publications.json
python fetch_medium.py
```

Any `partial:` line is reported in the summary. It does not stop the run.

Events have no API to fetch, so the Drive connector does it. The folder IDs are in `references/sources.json` (`events`):

1. Presentations: one `search_files` call with `mimeType = 'application/vnd.google-apps.folder' and (parentId = '<year folder>' or ...)` over every year folder (list them first with `parentId = '<drive id>'`), `excludeContentSnippets: true`, `pageSize: 300`. Folders are named `YYMMDD_Name`.
2. Photos: `parentId = '<photos folder>'`. Folders are named `YYMM_Name` (month only).
3. Pass the saved responses straight to the collector:

```
python collect_event_folders.py --source presentations --in <file> --source photos --in <file>
```

Grants: list the Grants drive root (`parentId = '<grants drive>'`, which gives the year folders), then their children in one call (`mimeType = 'application/vnd.google-apps.folder' and (parentId = '<year>' or ...)`, `pageSize: 400`), and pass both saved responses:

```
python collect_grant_folders.py --in <root file> <children file>
```

The Trainings drive, the workshops GitBook and the calendar have no dated folders. Skim them by hand (Trainings: one folder per programme; GitBook: the welcome page; calendar: `list_events` with `fullText` "seminar", "talk", "conference", "workshop" since the newest Events row) and add anything that has no row and no `calendar:`/`event:` entry in the ignore list to the Events step as an extra proposal, with the same approval.

### 3. Plan

```
python plan_sync.py
python render_plan.py --steps
```

The plan is numbered. Each item is one of:

- `update`: a field change.
- `create`: a new row.
- `choice`: Airtable and GitHub disagree, and the user says which side is right.
- `github`: a `gh` command, for example to copy a description to GitHub.
- `delete`: the row's repo is gone and GitHub has no redirect for it.
- `flag`: report only.

Renames are detected two ways: from GitHub's redirect, or, when a repo was recreated under a new name, from a matching creation date and description. Give the user the step list and the totals in one short message before starting the walkthrough.

### 4. Fill judgement fields

Only `create` items have a `to decide:` line. Fill those fields and nothing else:

- **Publications:** `slug` (short kebab-case, like the existing ones) and `topic` (Bioinformatics, Chemoinformatics, Medical informatics or Molecular biology). Senior and African collaboration are computed from OpenAlex author positions and countries, so don't guess them. Also say whether each paper is really Ersilia work: OpenAlex team-author matches include papers from other labs, from before someone joined Ersilia.
- **Blogposts:** `category` (one or more of Technology, Training, News, Global Health, Science). For `author`, run `list_records_for_table` on Community (`tblS9TeBRYUpLwSCk`) with a `contains` filter on the name, and use the record id.
- **Grants:** read the folder first (`parentId = '<folder_id>'`): the application, budget and any award or rejection letter give `name`, `short_name` (as in the existing rows), `organisation` (record ids from Organisations; create a missing funder only after approval), `type` (Grant, In-Kind, Donation, Program or Prize; fellowships are Program), `submission` (the deadline or submission date), `status` (To do, Pending, Rejected, Accepted, Cancelled, Won't do, To check; an explored call that was never submitted is Won't do), `ersilia_amount` (USD), `ersilia` (Spain for applications since mid-2023, UK before) and a one-line `description`. Never guess an amount or an outcome: leave it null and say so. When the reason names a closest row and the user says it is the same grant, do not create: add the pair to `rules.json` `grants.known_pairs` (Step 8).
- **Events:** `name` (short, like the existing rows), `description` (one plain sentence; say "participated" unless the folder shows a talk, and name the speaker when it was not Miquel), `url` (the event's own page, found by web search; null rather than a homepage when there is none), `organisations` and `country` (record ids, looked up in Organisations `tblxKMlzYuoSzBaDC` and Countries `tblujd4T9of8KAmP2` with a `contains` filter). `category` (Talk, Training, Conference or Other) and `format` (In person if Ersilia was there, Online otherwise) always; `participants`, `grants` and `projects` for trainings when the folder or the user knows them, null otherwise. For a month-only Photos folder, also `date`. Read the folder first (`parentId = '<folder_id>'`): slides, programmes and abstracts usually give the real date, title and host. An organisation that does not exist yet is shown in the walkthrough and, once approved, created first with one `create_records_for_table` call on Organisations (name and website); `build_writes.py` has no item for it.

Write them to `/tmp/airtable_sync/judgements.json` as `{"<n>": {"<field>": value}}`. Show them to the user in the walkthrough; they are proposals too.

### 5. Walk the user through it, one step at a time

For each step `k` in order:

1. Run `python render_plan.py --step k`.
2. Explain the step in two or three plain sentences: what the items are, why the script proposes them, and anything worth a second look. Show the items with their numbers and their from → to values, and your judgement values for new rows.
3. For a writable step, ask with `AskUserQuestion`:
   - **Approve all in this step**
   - **Approve some**: the user lists the item numbers.
   - **Skip this step**
   - **Reject** (only for new-row steps): not wanted, and never proposed again. Ask for a one-line reason.
   - For a `choice` step, ask which side is right for each item, then pass it as `--choose <n>:use-airtable` (Airtable's value is right, so GitHub is changed) or `<n>:use-github` (GitHub's value is right, so Airtable is changed). The option names say whose value survives.
   - For a `delete` step, check whether the row looks like the same thing as a new row. The planner already turns a matching creation date and description into a rename, so this is only for looser matches. If it does, offer to merge it into the curated row instead of deleting it.
4. For a report-only step (flags), there is nothing to approve. Show it and ask whether any of it should become a rule (Step 8).

Keep each message short. Don't show the next step until the current one is answered.

### 6. Write what was approved, straight after each approval

```
python build_writes.py --approve <numbers> [--choose <n>:use-airtable|use-github,...] \
    [--judgements /tmp/airtable_sync/judgements.json] [--reject <numbers> --reason "<why>"]
```

`--judgements` also overrides a field of an approved update, when the user agreed to a better value during the walkthrough.

Read `/tmp/airtable_sync/writes.json`. For each call, tell the user in one line what is about to be written (for example "Updating 2 records in Repositories"), then:

- **Airtable calls:** call the named tool with the arguments exactly as given, leaving out the `items` key. That means `baseId`, `tableId`, plus `records` and `typecast`, or `recordIds` for `delete_records_for_table`. At most 50 records per call; the script has already split them.
- **`gh` calls:** run `python apply_github.py`. It runs only these commands and reads each value back from GitHub. Never type a `gh` write command yourself.

Then verify, cheaply:

- **Preferred, a filter:** one `list_records_for_table` call that must come back empty. For example, filter `isEmpty` on the field you just filled, or `contains "?"` on URLs after a tracking cleanup. Add a `recordIds` read of one or two records to spot-check the values.
- **Otherwise, the full check:** re-read the records by `recordIds`, requesting every field that was written. New rows have no id until the create call returns one, so use the ids from its response. Write the records compacted, then run `normalise_airtable.py --out /tmp/airtable_sync/<table>.after.json` and `python verify_writes.py`. Deleted records must be absent.
- Report the result. If anything mismatches, show it and ask before any further write.

`build_writes.py` refuses:

- flags, unknown item numbers or fields, and new rows with judgement fields missing;
- a choice without a side, and rejecting anything other than a new row;
- any select value that isn't an existing option.

It sets `typecast` only for a Publication Year that has no option yet. Once that year is created, add it to `KNOWN_YEARS` in `_common.py`. Don't work around a refusal.

### 7. Summary

A few lines only:

- What was written, per table.
- What still needs a person: the flags, and `render_plan.py --gaps` (fields the stats site reads that are empty).
- What was not checked (`skipped` in the plan, and any `partial:` fetch).
- The Medium limitation: RSS only shows the latest 10 posts per feed.
- For Events, the upcoming flags (add them once they have happened) and whatever the hand-checked sources could not cover.
- For Grants, the stale-status flags (applications still Pending, To check or To do long after submission).

### 8. Learn from the feedback

Ask: "Anything I should do differently next time?" Treat every correction, during the run or after it, as a lesson:

1. **Prefer a data fix.** Change `references/rules.json` (policies, thresholds, aliases, subset rules), `references/sources.json` (feeds, authors, excluded types) or `references/ignore-list.json`.
2. **Otherwise fix the script**, and add a case to `examples/cases/` that reproduces the situation (the format is in `selftest.py`).
3. `python selftest.py` must pass.
4. `python record_feedback.py add --text "<what the user said>" --kind <rule|source|ignore|code|process> --change "<what changed>" [--fixture <case name>]`.
5. Tell the user what changed, and suggest committing it on a branch. Don't commit without being asked.

A lesson that only lives in the conversation is lost. If it matters, it goes in a file.

## Reference files

- `references/airtable-tables.md`: base, table and field IDs, select options, what may be written, and what ersilia-stats reads.
- `references/rules.json`: every decision policy the planner applies.
- `references/sources.json`: GitHub org, OpenAlex institution and authors, Medium feeds.
- `references/ignore-list.json`: rejected candidates, so they are never proposed again.
- `references/feedback-log.json`: the lessons, read at every pre-flight.
- `references/_state.json`: when the references were last verified.

## Related skills

- `github-digest` reports Repositories drift (read-only) inside the weekly digest. This skill is the one that fixes it.
- `repository-auditing` checks a single repository against the house standard.
