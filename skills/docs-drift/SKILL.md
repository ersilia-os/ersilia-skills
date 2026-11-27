---
name: docs-drift
description: >
  Find documentation that no longer matches the code: the Ersilia Book (GitBook, source in
  ersilia-os/ersilia-book) and the READMEs of non-model ersilia-os repositories. Checks
  `ersilia` CLI commands and options against the live CLI source, links to org repos
  (deleted, renamed, archived, moved files, gone branches), Python versions in install
  commands against each package's requires-python, the Book's structure (SUMMARY.md
  entries, orphan and hidden pages, GitBook /broken/pages/ links, relative links) and,
  optionally, external links; then a capped judgement pass reads pages that describe
  workflows next to the code they describe. Produces an ID-numbered report (B1… Book,
  R1… READMEs) and opens one `docs-drift` issue per page only for IDs the user approves.
  Never edits documentation. Run about monthly; it says when a run is due. Triggers
  include: "docs drift", "/docs-drift", "is the Ersilia Book up to date", "check the
  docs against the code", "outdated documentation", "stale READMEs", "broken links in
  the Book", "does the Book still match the CLI". Always use this skill for these
  requests, even if the ask seems simple.
argument-hint: "[--only book|readmes] [--check-external] [--no-judgement]"
allowed-tools: [Read, Bash, Write, AskUserQuestion, mcp__gitbook__list_sites, mcp__gitbook__get_site_structure]
---

# Docs drift

Documentation drifts as code moves: commands get renamed, repos get archived, files move.
This skill finds the places where the Ersilia Book and the READMEs say something the code
or the GitHub organisation no longer supports, and turns the ones the user approves into
GitHub issues in the repository where the text lives, assigned to the person who last
edited it.

**The one rule:** the skill reports and opens issues; it never edits documentation. The
user (or the page owner) writes the fix. Opening issues is outward-facing, so it happens
only for IDs the user approves in this run, never unattended.

## How the work is split

| Part | Who | What |
|---|---|---|
| Fetch | `scripts/fetch_sources.py` | Clones the Book and the `ersilia` CLI, lists org repos, reads READMEs and `pyproject.toml` files, parses the CLI's click options. |
| Checks | `scripts/check_drift.py` | Deterministic checks, listed in `references/checks.md`. |
| Judgement | you | Read a few workflow pages next to their code; flag only statements the code contradicts. |
| Report | `scripts/render_report.py` | Numbers every finding and writes the report. |
| Issues | `scripts/open_drift_issues.py` | One issue per page for approved IDs; updates instead of duplicating. |

Work in `/tmp/docs-drift` (the scripts' default `--workdir`).

## Workflow

### Step 0: Pre-flight

1. `gh auth status` must succeed; `git` must be on PATH.
2. Read `references/_state.json`. If `next_run_due` is in the future and the user did not
   ask for a run anyway, say when it is due and stop.

### Step 1: Fetch

```bash
python scripts/fetch_sources.py --workdir /tmp/docs-drift
```

Add `--skip-readmes` when the user asked for the Book only. If it exits 1, report which
source failed and stop: checking against a partial picture produces false findings.

### Step 2: Run the checks

```bash
python scripts/check_drift.py --sources /tmp/docs-drift/sources.json [--only book|readmes] [--check-external]
```

`--check-external` tests every other URL (slow, about a minute); offer it, do not default
to it. The script prints counts per check.

### Step 3: Published structure (optional)

If the GitBook connector is available, compare `get_site_structure` for the Ersilia Book
with `book/SUMMARY.md`. A page that is published but missing from `SUMMARY.md`, or the other
way round, means Git Sync is out of step: add it as a judgement finding on `book/SUMMARY.md`.
Skip silently if the connector is not connected.

### Step 4: Judgement pass (skip with `--no-judgement`)

The checks catch broken references; they cannot tell when a sentence describes behaviour
that changed. Read, side by side with the code they describe, **at most 5 pages per run**,
choosing first the pages edited least recently among:

- `book/ersilia-model-hub/developer-docs/interfaces/*` (CLI and Python API) against
  `ersilia/cli/commands/` and `ersilia/api/` in `/tmp/docs-drift/src/ersilia`;
- the model-contribution pages against `eos-template` and the model-incorporation skills;
- `book/ersilia-model-hub/developer-docs/maintenance/*` and `book/agentic-ai/*` against the
  `skills/` folder of `ersilia-skills`;
- chemistry-tools pages against the README and `pyproject.toml` of the tool they describe.

Rules for a judgement finding:
- It quotes the doc line and names the code it contradicts (file and line, or the command
  output). No quote, no finding.
- A **contradiction**, not an omission. Options declared `hidden=True` in click, private
  functions and internal details are left out of user docs on purpose.
- Not style, tone or wording: that is not drift.
- At most 10 judgement findings per run, most serious first.

Write them to `/tmp/docs-drift/judgement.json` as a list of objects with `source`,
`repo`, `path`, `line`, `claim`, `evidence`, `suggestion`, `severity` (and `page` for Book
pages: the sidebar title). An empty list is a valid result; say so in the report.

### Step 5: Render and report

```bash
python scripts/render_report.py --findings /tmp/docs-drift/findings.json --judgement /tmp/docs-drift/judgement.json
```

Show the user the summary line and the findings, high severity first. Point out patterns
rather than repeating them (for example, one repo renamed and linked from 12 places). Then
ask which IDs to turn into issues. Suggest the high-severity ones; low-severity ones
(renamed repos that still redirect, archived repos) are usually worth batching only when
the page has other findings.

### Step 6: Open issues for approved IDs

Preview first, then apply with the **same** IDs and the same `findings_final.json`:

```bash
python scripts/open_drift_issues.py --input /tmp/docs-drift/findings_final.json --plan --ids B1,B4,R2
python scripts/open_drift_issues.py --input /tmp/docs-drift/findings_final.json --apply --ids B1,B4,R2
```

One issue per page (Book pages in `ersilia-os/ersilia-book`, READMEs in their own repo),
label `docs-drift`, assigned to the member who last edited the page. An open issue for the
same page gets the new items added; ticked items are kept. Report each issue URL and
assignee, and list any unassigned ones so the user can pick an owner.

### Step 7: Record the run

Update `references/_state.json`: set `last_run` to today, `next_run_due` to today plus
`run_interval_days`, and append to `run_log` the date, counts per severity, and the IDs that
became issues. Commit it only if the user asks; the state file is not worth a PR on its own.

## Rules

- Never edit documentation, close issues or delete anything.
- Never open an issue without IDs the user approved in this run. No approve-all.
- Do not report a finding you could not verify; drop it and say why.
- Model repos' READMEs are generated from their metadata and are out of scope.
- Relative links inside a single repo's README are `repository-auditing`'s job; this skill
  checks what crosses repos or depends on the live code.
- The Book and READMEs are public. Findings quote public text only; never paste anything
  from Drive, Slack or Airtable into an issue.
