---
name: github-digest
description: >
  Produce the periodic Ersilia GitHub digest — a curated, publicly-hosted markdown report
  of issue and pull-request activity across the ersilia-os organisation, the items that need
  attention (stale PRs, long-open issues), and a health check of the Airtable Repositories
  registry. Use this skill whenever the user asks to prepare, run, or refresh the GitHub
  digest, the repo/issue/PR digest, or the "what happened on GitHub this week" report.
  Triggers include: "github digest", "weekly github digest", "/github-digest",
  "issue tracking digest", "what changed in the repos this week", "check the repositories
  Airtable is up to date". Always use this skill for GitHub-digest requests even if the ask
  seems simple.
---

# Ersilia GitHub Digest

You produce the periodic GitHub digest for **Ersilia Open Source Initiative** — a curated
markdown file covering issue / PR activity across the `ersilia-os` org, items that need
attention, and the health of the Airtable Repositories registry. As part of the run the skill
also refreshes the registry's metric columns from GitHub (Step 4, one-directional write-back).

The digest is read by the Ersilia engineering team and is **publicly hosted** on
`ersilia-os/digests` (it auto-builds a GitHub Pages site at `ersilia-os.github.io/digests`).
Write factually. GitHub usernames are already public on the repos, so attributing activity
to a handle is fine; never paste anything not already visible on GitHub and never name an
internal Slack channel in the digest body.

This skill is the sibling of `literature-digest` and follows the same shape: deterministic
scripts do the fetch / reconcile / upload; the reference files carry the format and rules;
the LLM does triage and composition. When in doubt about a convention, mirror
`literature-digest`.

---

## Inputs

The user will invoke this skill with:

- (optional) a date range, e.g. `--from 2026-06-09 --to 2026-06-16`. Default: the last 7
  days ending today.
- (optional) `--out <path>` to override the local staging path. Default:
  `digests/YY-MM-DD-github-digest.md` (end date of the window, 2-digit year) relative to this
  skill folder. The local file is a working copy; the canonical home is the remote repo
  `ersilia-os/digests` at `github/YY-MM-DD-github-digest.md` (Step 8).
- (optional) `--force` to override the recent-digest guards in Step 0.
- (optional) `--dry-run` to fetch, reconcile, and compute the metric-sync plan but **not**
  apply it to Airtable, and not write or upload the digest file.

If anything is unclear, ask one focused question before proceeding. Never invent missing
inputs.

---

## Workflow

Run the steps in order. Track progress with `TaskCreate` / `TaskUpdate` if the run is
non-trivial.

### Step 0 — Pre-flight checks (three gates)

**Gate A — required tools.** Both must be available:

- `gh` CLI, authenticated. Verify with `gh auth status`. If it fails, **STOP** — the entire
  fetch and the upload depend on it.
- The **Airtable MCP**. Verify with a cheap read: `search_bases "Ersilia Content"`. If it
  errors with "MCP not available" / "tool not found", **STOP** and tell the user the registry
  health check cannot run. (Do not silently skip the Registry alignment chapter — it is a
  core deliverable.)

**Gate B — references not stale (non-fatal).**

```bash
python scripts/check_references_freshness.py
```

- `OK` → continue. `DUE` → the references are past their 90-day cadence (the Airtable
  base/table IDs or the repo taxonomy may have drifted). **Pause** and tell the user; offer to
  (a) re-verify `references/airtable-schema.md` and `references/scope.md` against the live
  Airtable + org now, or (b) defer and proceed, recording the deferral in
  `references/_state.json`'s `refresh_log`. Never refresh silently. Exit 1 means the state
  file is broken — fix it before continuing.

**Gate C — no recent digest (remote first, then local).** The canonical home is the remote
`ersilia-os/digests` repo, so the remote is authoritative. Run both, **remote first**:

```bash
python scripts/check_remote_digest.py --days 7
python scripts/check_recent_digest.py --days 7
```

- If `check_remote_digest.py` exits non-zero, the remote was unreachable. **STOP** — do not
  fall through to the local check (a local run could clobber published work on retry).
- If either prints a path, **STOP**. A digest already exists for this window. Tell the user
  the path (and html URL on stderr from the remote check) and ask whether to override with
  `--force`. Do not assume yes.
- Only if **both** come back empty, continue.

### Step 1 — Load context

Read these reference files into context before fetching. Quote them; do not paraphrase:

- `references/scope.md` — model vs non-model split, exclusions, activity windows, label hints.
- `references/airtable-schema.md` — base/table/field IDs, auto-vs-curated fields, the exact
  normalised JSON shape to dump, and what each finding means.
- `references/output-template.md` — exact digest structure (chapters, semaphore, legend,
  per-item lines, caps, footer).

### Step 2 — Fetch GitHub

```bash
python scripts/fetch_github.py --from {start} --to {end} --out /tmp/github.json
```

This lists every `ersilia-os` repo (tagging `eosXXXX` model repos), pulls issue/PR activity
in the window via `gh search`, and snapshots open PRs/issues with staleness annotations.
Model-repo activity is aggregated into `model_summary`; non-model activity is itemised.
It also reads the org **custom properties** (`status`/`type`, mirrored from Airtable),
attaching `gh_status`/`gh_type` to each repo and computing `repos.by_type` / `repos.by_status`
(the Repository overview) and a `highlights` payload. Open issues are pre-flagged as easy-win
candidates (`easy_candidate` + `easy_reasons`).
Note the printed `connector_status` — it drives the GitHub semaphore. If a search bucket or
the custom-property read fails the status is `partial`; render 🔴 and disclose the impact in
the digest only if it materially affects coverage (e.g. the Registry alignment is thin).

### Step 3 — Read the Airtable registry (you, via the MCP)

The Airtable MCP cannot be called from a Python subprocess, so **you** read the table and
dump normalised records for the reconcile script:

1. Resolve the base and table at run time (don't trust hard-coded IDs blindly):
   `search_bases "Ersilia Content"` → base `app1iYv78K6xbHkmL`; `list_tables_for_base` →
   confirm the **Repositories** table `tbluZtI3W9pseCSPH`.
2. Read **all** records with `list_records_for_table`, requesting the fields in
   `references/airtable-schema.md`: Name, Title, Status, Type, Projects, **Stars, Forks,
   Open Issues, Subscribers, Total Commits, Contributors, Contributor Names**, Visibility,
   Creation Date. The full table is too large for one MCP response, so the harness saves the
   raw result to a `tool-results/…txt` file and returns its path — this is expected (see
   `airtable-schema.md` for the field-ID map).
3. Transform the saved raw file into the flat JSON shape in `airtable-schema.md` (plain
   strings, not select objects; `type`/`projects` as lists) and write the list to
   `/tmp/airtable_repos.json` — a short Python script reading the saved file is the reliable
   path. **Include each record's `id`** (the top-level `rec…` id) — the metric sync in Step 4
   needs it to target rows, and include the current metric values so the sync only pushes
   changes.

If the MCP read fails mid-way, that is an Airtable-connector failure: render the Airtable
semaphore 🔴 and have the Registry alignment chapter say the registry check could not run —
do not show partial findings.

### Step 4 — Sync GitHub metrics to Airtable (write-back; GitHub → Airtable only)

This is the **one write path** in the skill, and it is strictly unidirectional: GitHub is the
source of truth, Airtable the sink. It refreshes only the cron-maintained metric columns
(Stars, Forks, Open Issues, Subscribers, Total Commits, Contributors, Contributor Names) and
**never** the human-curated columns (Status, Type, Projects, Title). Run it after the fetch
and **before** reconcile so the digest reflects the just-synced numbers.

```bash
python scripts/sync_airtable_metrics.py \
  --github /tmp/github.json \
  --airtable /tmp/airtable_repos.json \
  --out /tmp/airtable_updates.json
```

The script fetches the per-repo metrics (subscribers/contributors/commits) via `gh`, diffs
against the current Airtable values, and writes an **update plan** containing only the records
and fields that changed, each `fields` object keyed by **Airtable field ID**, plus a `summary`
(counts + a few notable deltas) for the digest's sync note. Then **you apply it via the MCP**:

- For each entry in `updates`, call `update_records_for_table(baseId, tableId, records=[{id:
  recordId, fields}])`. **Batch ≤ 50 records per request.**
- On `--dry-run`, do **not** apply — just read the summary for the digest.
- If some batches fail, note how many records were written vs intended; the digest's sync note
  must reflect what actually happened, not the plan. Never write curated fields.

### Step 5 — Reconcile

```bash
python scripts/reconcile_airtable.py \
  --airtable /tmp/airtable_repos.json \
  --github /tmp/github.json \
  --out /tmp/health.json
```

This is **report-only** — it never writes to Airtable. Read `/tmp/health.json`: it carries
the missing / stale / **status_mismatch / type_mismatch** / needs-curation / active-but-parked
/ metric-drift findings that become the Registry alignment chapter. The mismatch findings
compare Airtable Status and Type against the GitHub custom properties (strict compare; both
values reported). Airtable and GitHub share the same vocabulary, so mismatches are real drift
and normally few (see `airtable-schema.md`).

### Step 6 — Compose the digest

Read `/tmp/github.json`, `/tmp/health.json`, and `/tmp/airtable_updates.json`. Compose the
file following `references/output-template.md` exactly. **Keep it succinct, scannable,
high-signal** — a 30-second read. **Action-needed items come before completed activity**, and
emoji section headers are used for readability. Order:

- H1 + connector semaphore + marker legend.
- **✨ Highlights** — 2–4 sentences from the `highlights` payload: busiest repos, the single
  most important change, one health clause, and (if anything was synced) one clause on it.
- **⚠️ Needs attention** (ACTION, first) — capped lists of stale PRs (most stale first),
  long-open issues (oldest first), and **💡 Easy wins**. For easy wins, judge the
  `easy_candidate` set: keep genuinely small work, drop false positives (model requests, vague
  discussions), cap at 5, with a short stand-behind reason each.
- **🔧 Registry alignment** (ACTION) — verdict line + finding subsections (missing / ghost /
  status·type mismatches / needs curation / possibly out of date), capped.
- **📊 Repository overview** (context) — totals · by type · by status from the stratification.
- **✅ Recent activity** (completed) — itemise non-model issues/PRs (merged/opened/closed),
  then the model-repo summary line from `model_summary`.
- **🔄 Airtable sync** (completed, small) — the acted-on note from the `airtable_updates.json`
  summary: how many records/fields were updated and a couple of notable deltas.

Composition rules:
- Apply a work-type emoji only when the label/title makes it obvious; otherwise omit.
- Respect the caps (top 10 attention items, 5 easy wins, ~15 alignment lines) and always state
  the totals for what was truncated. Silent truncation is forbidden.
- Be factual and neutral. No internal channel names, no invented labels, no padding.

### Step 7 — Render

Write to the default local staging path unless `--out` was given:

`skills/github-digest/digests/{YY}-{MM}-{DD}-github-digest.md`

(2-digit year, end date of the window.) The `digests/` folder is `.gitignored` — the file
lives locally and is not committed by default. **If `--dry-run`, stop here** and show the
user the local path and the key counts; do not upload or post to Slack.

### Step 8 — Upload to the canonical remote

```bash
python scripts/upload_digest.py --digest digests/{YY}-{MM}-{DD}-github-digest.md
```

- Uses `gh`; uploads to `ersilia-os/digests` at `github/{YY}-{MM}-{DD}-github-digest.md` and
  updates the repo `README.md` under `## GitHub digests` (idempotent, date-descending).
- **Refuses to overwrite** an existing remote file unless `--force` (belt-and-braces with
  Gate C). On exit code 2 (already exists), surface the message and ask before `--force`.
- On success it prints the digest `html_url` (and README `html_url`) on stdout. Hand those to
  the user as the digest location — the **remote is canonical**, not the local path.
- If upload fails for a recoverable reason (network, gh auth lapsed), keep the local file and
  tell the user how to re-run just the upload. Never delete the local file before success.

**One-time setup (first GitHub digest only):** the Jekyll site needs the `github/` category
registered once in `ersilia-os/digests` `website/_config.yml`:

```yaml
defaults:
  - scope: { path: "literature" }
    values: { layout: digest }
  - scope: { path: "github" }        # add this block once
    values: { layout: digest }
```

The Pages workflow already copies every top-level category folder into the site, so no
workflow change is needed. Until this scope block exists the page still uploads and renders,
just without the shared digest layout. Make this change via a small PR to the digests repo.

### Step 9 — Post the Slack alert (only on successful push)

After (and **only** after) `upload_digest.py` exits 0, post a single notification using
`references/slack-alert-template.md`:

```text
slack_send_message(channel_id = "C01JL4SDKSL", message = <rendered template>)
```

- Post to **`#coding`** (`C01JL4SDKSL`) — see `references/slack-alert-template.md` for the
  message format and field rules.
- Do **not** post on `--dry-run`, on any non-zero upload exit, or if the digest was generated
  but not pushed. Post exactly once per push (including `--force` re-pushes).

### Step 10 — Remove the local staging copy

The canonical home is the remote `ersilia-os/digests` repo; the local file is only a staging
area and is **not** kept. **Only after** the upload succeeded (Step 8 exit 0) *and* the Slack
alert was posted, delete the local digest file:

```bash
rm -f digests/{YY}-{MM}-{DD}-github-digest.md
```

- Do this **only** on a confirmed successful push — never on `--dry-run`, never if the upload
  failed (in that case keep the file so the user can re-run just the upload), and never before
  the Slack post. The remote URL from Step 8 is the digest's location to hand back to the user.

---

## Things to avoid

- Do not itemise model-repo (`eosXXXX`) issues/PRs — summarise them in one line.
- Do not write curated Airtable fields. Only the metric columns are synced (Step 4,
  GitHub→Airtable); Status/Type/Projects/Title are read-only. The reconcile is report-only.
- Do not silently truncate the attention or health lists — always state the totals.
- Keep Highlights to ≤4 sentences and Easy wins to ≤5 items. The digest is a fast read, not a report.
- Do not list every easy_candidate verbatim — judge them; drop model requests and vague items.
- Do not invent labels, work-types, dates, or authors. If a field is unknown, omit it.
- Do not name internal Slack channels in the digest body. GitHub handles are fine (public).
- Do not commit the digest to this repo's git — `digests/` is gitignored; the canonical home
  is the remote `ersilia-os/digests`.
- Keep emojis purposeful: chapter-heading emojis (per `output-template.md`), the work-type
  markers (🐛 ✨ 📄 🔧 🕒), and 🟢/🔴 in the semaphore — never sprinkled mid-prose.

---

## Scheduling

Invoked manually by default. To run it weekly:

```text
/schedule create github-digest --cron "0 9 * * 1" --command "/github-digest"
```

(Monday 09:00 local.) Self-scheduling is intentionally not built in — the run needs the
`gh` CLI and the Airtable MCP live in the session, easier to guarantee for a manual run.

---

## Future work (documented, not implemented)

- **Per-author or per-project rollups** as an optional chapter.
- **PR review latency** metrics (time-to-first-review) for the attention chapter.
- **Trend deltas** vs the previous digest (activity up/down, registry drift closing or
  growing) by parsing the last published github digest.
- **Curated-field write-back** (Status/Type) behind an explicit `--fix` flag. Note: *metric*
  write-back is already implemented (Step 4); the curated columns remain report-only by design.
