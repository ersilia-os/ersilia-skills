---
name: org-context
description: >
  Keep Ersilia's agent-context files up to date, clean and useful: the org orientation
  file (config/CLAUDE.md in ersilia-skills) and the CLAUDE.md files shipped by the
  eos-python-package, eos-analysis-template and eos-template repository templates; also
  checks that the org file is actually loaded on this machine. Run about monthly; it says
  when a review is due. Checks length
  budgets, stale dates, contradictions with the Ersilia standard (e.g. ruff only),
  repetition, vague instructions, folder-tree and overview bloat, and rules better
  enforced by hooks; verifies every skill, repository, URL and template path or tool the
  files mention, and the Google Drive shared drives and Airtable bases the org file points to
  (read-only connectors); adds a judgement pass on usefulness; and produces a short,
  ID-numbered report with proposed edits. Changes nothing until the user approves
  specific IDs, then applies them on a branch and opens a PR on confirmation. Learns
  from the user's feedback on every run. Triggers include: "org context", "/org-context",
  "review the CLAUDE.md files", "update CLAUDE.md", "is our CLAUDE.md up to date",
  "clean up the org CLAUDE.md", "revise the template CLAUDE.md", "check the agent
  instructions", "are the Drive references in CLAUDE.md right". Always use this skill
  for these requests, even if the ask seems simple.
argument-hint: "[--only org,pkg,ana,mod] [--local pkg=<path-to-clone>/CLAUDE.md]"
allowed-tools: [Read, Bash, Write, Edit, AskUserQuestion, mcp__claude_ai_Google_Drive__search_files, mcp__claude_ai_Google_Drive__get_file_metadata, mcp__claude_ai_Google_Drive__get_file_permissions, mcp__claude_ai_Airtable__list_bases]
---

# Org context

You review the four CLAUDE.md files that give agents their Ersilia context:

| ID prefix | File | Role |
|---|---|---|
| `O` | `ersilia-os/ersilia-skills/config/CLAUDE.md` | Org orientation layer |
| `P` | `ersilia-os/eos-python-package/CLAUDE.md` | Seed for every new package repo |
| `A` | `ersilia-os/eos-analysis-template/CLAUDE.md` | Seed for every new analysis repo |
| `M` | `ersilia-os/eos-template/CLAUDE.md` | Seed for every new model repo |

The org file only helps if agents load it: `setup.sh` adds an `@import` of it to each
person's `~/.claude/CLAUDE.md`, and `check_delivery.py` confirms that on this machine.

**Cadence.** About once a month. `_state.json` keeps the due date (30 days after the last
review) and a log of past reviews; `fetch_targets.py` prints `DUE` or `OK` first.

A good CLAUDE.md is short (it loads into every session), true (every name, link, path
and tool resolves), consistent (the org file and the templates never disagree) and
useful (every line changes what an agent does). Research backs this: overviews and
folder trees don't help agents and cost tokens (Gloaguen et al. 2026, arXiv:2602.11988);
instruction-following decays as instructions pile up and favours early ones (IFScale,
arXiv:2507.11538); Anthropic advises under 200 lines, concrete instructions, and hooks for
anything that must always hold (code.claude.com/docs/en/memory). The templates matter more than their size suggests:
each new repo copies them.

This skill is independent of `repository-auditing`. Do not read or edit that skill.

## The one rule

**Report first. Never edit, commit, push or open a PR without the user's explicit
approval of those IDs, in this run, given after they have seen them.** This holds in auto
mode too. A plan, an earlier approval or "it's obviously right" is not permission.
`apply_edits.py` takes explicit IDs only and has no approve-all switch.

## How the work is split

Scripts decide; you judge, propose wording and ask. Every policy is data in
`references/rules.json`, and the files under review are listed in
`references/targets.json`. Don't re-derive what a script computed. If a script is wrong,
fix the script or the rule (Step 8) rather than working around it.

Scripts run from `scripts/` with the Python 3 standard library and `gh`, and work in
`/tmp/org_context/`.

| Script | Does |
|---|---|
| `record_feedback.py` | Lists the lessons (`list`) or logs one (`add`) |
| `fetch_targets.py` | Reads the four files from their default branch (read-only); prints `DUE`/`OK`; says what changed since the last review; `--mark-reviewed` records the review and the next due date |
| `check_delivery.py` | Is the org file imported in `~/.claude/CLAUDE.md`? → `delivery.json` |
| `check_claude_md.py` | Budgets, dates, sections, placeholders, vague phrases, malformed links, emoji, canonical rules, duplication, folder trees and overviews (`BLOAT-*`), prohibitions a hook could enforce (`HOOK-CANDIDATE`) → `checks.json` |
| `verify_facts.py` | Skills, repos (exist, not archived), repo links, URLs; for templates, paths and tools the file names against the template's tree and config (`REALITY-*`) → `facts.json` |
| `connector_claims.py` | `extract` the shared drives and Airtable bases the org file names (drive roots come from the org file's links); `compare` them with what you observed through the connectors → `connectors.json`; `map` caches a confirmed root for a drive the file doesn't link |
| `run_prompt_audit.py` | Runs Claude Code's `/doctor prompt-audit` on each file in a throwaway clone → `audit-<id>.md` (optional input to Step 4) |
| `render_report.py` | Merges every findings file with your `judgement.json`, numbers findings (`O1`, `P2`...) and keeps their IDs across re-renders, validates every edit → `plan.json`, `REPORT.md` |
| `apply_edits.py` | Applies approved IDs to one file, bumps the "Last updated" line, prints the diff |
| `selftest.py` | Offline regression cases in `examples/cases/` |

## Workflow

### Step 0 — Pre-flight

```bash
cd skills/org-context/scripts
python record_feedback.py list
python check_delivery.py
```

Apply every lesson in this run. If `check_delivery.py` reports `DELIVERY-*`, tell the
user first: agents on this machine aren't loading the org file, and `bash setup.sh` fixes
it. If the user named only some files, pass `--only` below.

### Step 1 — Fetch

```bash
python fetch_targets.py            # add --local pkg=<clone>/CLAUDE.md to review a local edit
```

Note the `DUE`/`OK` line and each file's status (first review, unchanged, changed). An
unchanged file still gets checked: the world around it (skills, repos, practice) may have
moved. Files come from the default branch, so a stale local checkout never matters.

### Step 2 — Run the checks

```bash
python check_claude_md.py
python verify_facts.py
```

### Step 3 — Google Drive and Airtable

The org file tells agents where internal material lives. Check that it is still true,
with the **read-only** Drive and Airtable connectors. Never create, move, share or edit
anything in Drive or Airtable.

```bash
python connector_claims.py extract
```

It prints each shared drive and Airtable base the org file names, with the cached root
of each drive (from `~/.claude/org-context/drive-map.json`).

- **Airtable.** Call `list_bases` and record every base name verbatim.
- **Drive, local sync.** If `extract` found a Google Drive for desktop sync, the drive
  names come from disk and nothing else is needed for existence; still check that each
  description fits (below).
- **Drive, cached root.** For each drive with a root ID: `search_files` with
  `parentId = '<root>'`, `excludeContentSnippets: true`, `pageSize: 20`. The drive is
  `found` if the root answers. Compare its top level with the org file's description and
  the cached `signature`; set `matches_description`. Then `get_file_permissions` on the
  root: set `shared_publicly: true` if any permission has type `anyone` or `domain`.
- **Drive, no cached root.** The connector shows every shared-drive root as "Drive", so a
  name cannot be looked up. Find candidate roots: `search_files` for folders modified in
  the last 90 days (`excludeContentSnippets: true`, `pageSize: 100`), keep the
  `parentId`s that start with `0A`, and list each root's top level as above. Propose a
  mapping from drive name to root, citing the folders that support it, and ask the user
  to confirm it (one AskUserQuestion, at most four drives per question). The user's own
  My Drive is also a `0A` root: folders it holds carry `owner`; skip it. For each
  confirmed drive run
  `python connector_claims.py map --drive "<name>" --root <id> --signature "<top-level gist>"`.
  An unconfirmed drive is `unverified`, never guessed.
- A `0A` root that matches no named drive goes under `unlisted` only if its contents
  suggest a shared organisational drive.

Write `/tmp/org_context/observed.json` (format in the `connector_claims.py` docstring),
then:

```bash
python connector_claims.py compare
```

If the connectors are unavailable, skip this step and pass `--skip-connectors` to
`render_report.py`; the report then says these references were not checked.

**Drive and Airtable details are internal.** ersilia-skills is public. The one exception
is a link to a shared drive's **root** in the org file (`https://drive.google.com/drive/folders/<root>`),
and only when that root is user-confirmed and its permissions are limited to named people
(`shared_publicly` false). An outsider who opens it sees a request-access page. Everything
else (folder and file names, sub-folder IDs, who has access) stays in the local report:
never in `judgement.json` edits, commits, PR text or any file in the repository.
`compare` flags a link below a root, a link that is not the confirmed root, and a root
open beyond named people.

### Step 4 — Judgement pass

Read the four files in full (`/tmp/org_context/files/<id>.md`), `checks.json`,
`facts.json`, `connectors.json` and `delivery.json`. Then write `/tmp/org_context/judgement.json` (format in the
`render_report.py` docstring):

1. **Edits for script findings.** For each finding with an obvious fix, add an entry under
   `edits`, keyed by the finding `key`. `find` is exact text from the file, unique in it;
   keep it as short as uniqueness allows. `replace` is the new text (`""` deletes).
   Every finding gets a proposed fix where one is possible; don't leave a file's
   findings as notes:
   - `LEN-FILE` / `LEN-SECTION`: propose concrete cuts, as edits, that bring the file or
     section under budget, counting any lines your other edits add. Cut repetition,
     examples an agent doesn't need, and prose that restates a rule; keep every rule.
   - `DUP-ORG`: keep the rule in the template (templates stand alone) but condense the
     template's copy to one short line.
   - `CANON-*` with `require`: write the missing sentence in the section where it fits.
   - `BLOAT-TREE`: replace the tree with the few folder rules an agent can't infer by
     listing the repo (e.g. "numbered scripts in `scripts/`; data lives in eosvc, not git").
     `BLOAT-OVERVIEW`: cut the sentence, or keep only the part that changes behaviour.
   - `HOOK-CANDIDATE`: no edit to CLAUDE.md. Name the hook or permission that would
     enforce each rule, so the user can decide whether to add it to the template's
     `.claude/settings.json`. Never add hooks or settings yourself.
   - `REALITY-PATH`: either reword the file ("create `src/default.py` when first needed")
     or, if the template should ship it, say so as a finding without an edit.
     `REALITY-TOOL`: the fix is in the template's config (e.g. add `ruff` to
     `requirements.txt`), not in CLAUDE.md: report it with the exact line to add; it goes
     in the same PR only if the user approves it explicitly.
2. **Dismissals.** A script finding that is wrong in context goes under `dismiss` with a
   one-line reason. The report lists dismissals, so nothing disappears silently. A
   dismissal that would recur is a rule change: raise it in Step 8.
3. **Your own findings**, at most five per file, each with a concrete edit where one
   exists. Look for what scripts cannot see:
   - **Stale practice.** Compare against the live state: the skills in `skills/` and the
     README table, the template repo's real tree
     (`gh api 'repos/ersilia-os/<repo>/git/trees/main?recursive=1' --jq '.tree[].path'`), its
     `pyproject.toml` or `requirements.txt`, its CI. A rule about a folder, file or tool
     the template no longer has is wrong.
   - **Instructions an agent cannot act on**, or would follow the same way without being told.
   - **Wrong layer.** The org file is an orientation layer, not a runbook: detailed,
     template-specific rules (layout, CLI structure, release steps) belong in the templates.
     The org file **keeps its short Coding section**: work often happens outside a template,
     so general coding guidance must stay there. Never propose removing or moving it; check
     only that it agrees with the templates. A template rule that only repeats general
     behaviour may go, but templates must stand alone for people who never load the org
     file, so say which.
   - **Contradictions in substance** that differ in wording (e.g. one file mandates plan
     mode and another only suggests it).
   - **Missing guidance** an agent working in a fresh repo from that template would need.
   - **Repetition within a file** that the script missed (two bullets saying the same thing
     in different sections).
   - **Ordering.** Models follow early instructions more reliably (IFScale). If a file's
     must-follow rules ("Hard requirements", "Human sign-off", "Don't touch", "never")
     sit below long descriptive sections, propose moving that section up.
4. **Claude Code's own audit.** Run `python run_prompt_audit.py` (one headless run per
   file, in throwaway clones) and read `audit-<id>.md`. It checks each file against its
   repository: rules the template already breaks, outdated forceful wording, links that
   don't point where they say. Fold what the scripts missed into your own findings, with
   edits; ignore what they already cover. If it prints `SKIPPED`, say in your reply that
   the audit didn't run.

Hold the Ersilia voice in every `replace`: plain, active, concise, British or American
kept consistent with the file. Never invent repos, skills, people or policies; if a fix
needs a fact you don't have, make it a finding without an edit and say what to check.

### Step 5 — Render and report

```bash
python render_report.py
```

If it stops on an edit (its `find` is missing or not unique), fix `judgement.json` and
re-run. Then show the user the contents of `/tmp/org_context/REPORT.md` as your reply,
without retelling it. **Stop here** and wait for the user to approve IDs.

### Step 6 — Apply approved IDs

Only when the user names IDs (or "all ✎ in P", which means every `P` ID with an edit,
listed back to them). Apply one file at a time, on a branch, never on `main`:

- **Org file (`O`)**, in a worktree of this ersilia-skills checkout, so the change never
  mixes with whatever branch is checked out:
  ```bash
  git -C <repo-root> fetch origin main
  git -C <repo-root> worktree add -b claude-md/$(date +%F) /tmp/org_context/repos/ersilia-skills origin/main
  python apply_edits.py --ids O1,O3 --file /tmp/org_context/repos/ersilia-skills/config/CLAUDE.md
  ```
  Remove the worktree (`git worktree remove`) once the PR is open.
- **Templates (`P`, `A`)**, in a fresh clone:
  ```bash
  gh repo clone ersilia-os/eos-python-package /tmp/org_context/repos/eos-python-package
  git -C /tmp/org_context/repos/eos-python-package switch -c claude-md/$(date +%F)
  python apply_edits.py --ids P2 --file /tmp/org_context/repos/eos-python-package/CLAUDE.md
  ```

`apply_edits.py` refuses unknown IDs, IDs without an edit, IDs from two files, and a file
that differs from the reviewed version. Use `--dry-run` to show the diff first if the
user wants to see it before the file is written.

### Step 7 — Commit and PR, on confirmation

Show the diff, then ask once per file (AskUserQuestion) whether to commit, push and open
a PR. Only on yes:

- Commit message: `Revise CLAUDE.md: <short summary>`, plus the attribution lines the
  session requires.
- PR title the same; body lists the applied IDs with their one-line titles.
- Report the PR URL. Never merge.

### Step 8 — Feedback and record the review

Ask the user for feedback on the report. For each point:

1. Fix it where it lives: a `rules.json` value (preferred), `targets.json`, a script, or
   this file.
2. A script change needs a regression case in `examples/cases/` that reproduces it; run
   `python selftest.py`.
3. Log it: `python record_feedback.py add --text "..." --kind rule|target|code|process
   --change "..." [--fixture case-name]`.

Finally record the review, with what was applied and the PRs opened, so the next run can
tell what changed and when it is due:

```bash
python fetch_targets.py --mark-reviewed --applied O1,P2 --prs <url>,<url>
```

This edits `references/_state.json`; include it in the skill's next commit or the
org-file PR.

## Rules

- **The one rule** above. No write to any repository without approval of those IDs in
  this run.
- **Edits are exact.** Every `find` comes from the fetched file, verbatim. Never paraphrase
  the old text.
- **Keep it short.** The report is a 30-second read: tables of one-line findings, notes
  only where an edit or a reason needs them. Don't add sections to the report.
- **Prefer cutting to adding.** A proposed edit that grows a file over its budget needs a
  matching cut, or a reason in the finding.
- **Templates seed other repos.** A change to `P` or `A` affects every repo created
  afterwards, not existing ones. Say so when a finding is about content existing repos
  have already copied.
- **Drive and Airtable are read-only and internal.** No writes through either connector.
  Nothing from them leaves this machine except confirmed, closed shared-drive root links
  in the org file (Step 3).
- **Never fabricate.** No invented skills, repos, URLs or rules. A claim you cannot check
  is a finding without an edit.
