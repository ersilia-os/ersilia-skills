---
name: org-context
description: >
  Keep Ersilia's agent-context files up to date, clean and useful: the org orientation
  file (config/CLAUDE.md in ersilia-skills) and the CLAUDE.md files shipped by the
  eos-python-package and eos-analysis-template repository templates. Checks length
  budgets, stale dates, contradictions with the Ersilia standard (e.g. ruff only),
  repetition and vague instructions; verifies every skill, repository and URL the files
  mention, and the Google Drive shared drives and Airtable bases the org file points to
  (read-only connectors); adds a judgement pass on usefulness; and produces a short,
  ID-numbered report with proposed edits. Changes nothing until the user approves
  specific IDs, then applies them on a branch and opens a PR on confirmation. Learns
  from the user's feedback on every run. Triggers include: "org context", "/org-context",
  "review the CLAUDE.md files", "update CLAUDE.md", "is our CLAUDE.md up to date",
  "clean up the org CLAUDE.md", "revise the template CLAUDE.md", "check the agent
  instructions", "are the Drive references in CLAUDE.md right". Always use this skill
  for these requests, even if the ask seems simple.
argument-hint: "[--only org,pkg,ana] [--local pkg=<path-to-clone>/CLAUDE.md]"
allowed-tools: [Read, Bash, Write, Edit, AskUserQuestion, mcp__claude_ai_Google_Drive__search_files, mcp__claude_ai_Google_Drive__get_file_metadata, mcp__claude_ai_Airtable__list_bases]
---

# Org context

You review the three CLAUDE.md files that give agents their Ersilia context:

| ID prefix | File | Role |
|---|---|---|
| `O` | `ersilia-os/ersilia-skills/config/CLAUDE.md` | Org orientation layer |
| `P` | `ersilia-os/eos-python-package/CLAUDE.md` | Seed for every new package repo |
| `A` | `ersilia-os/eos-analysis-template/CLAUDE.md` | Seed for every new analysis repo |

A good CLAUDE.md is short (it loads into every session), true (every name and link
resolves), consistent (the org file and the templates never disagree) and useful (every
line changes what an agent does). The templates matter more than their size suggests:
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
| `fetch_targets.py` | Reads the three files (read-only); says what changed since the last review; `--mark-reviewed` records the review |
| `check_claude_md.py` | Budgets, dates, sections, placeholders, vague phrases, malformed links, emoji, canonical rules, duplication → `checks.json` |
| `verify_facts.py` | Skills, repos (exist, not archived), repo links, URLs → `facts.json` |
| `connector_claims.py` | `extract` the shared drives and Airtable bases the org file names; `compare` them with what you observed through the connectors → `connectors.json`; `map` caches a confirmed drive root |
| `render_report.py` | Merges all three with your `judgement.json`, numbers findings (`O1`, `P2`...), validates every edit → `plan.json`, `REPORT.md` |
| `apply_edits.py` | Applies approved IDs to one file, bumps the "Last updated" line, prints the diff |
| `selftest.py` | Offline regression cases in `examples/cases/` |

## Workflow

### Step 0 — Pre-flight

```bash
cd skills/org-context/scripts
python record_feedback.py list
```

Apply every lesson in this run. If the user named only some files, pass `--only` below.

### Step 1 — Fetch

```bash
python fetch_targets.py            # add --local pkg=<clone>/CLAUDE.md to review a local edit
```

Note each file's status line (first review, unchanged, changed). An unchanged file still
gets checked: the world around it (skills, repos, practice) may have moved.

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
  the cached `signature`; set `matches_description`.
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

**Drive and Airtable details are internal.** ersilia-skills is public. Folder names, file
names and IDs go in the local report only: never in `judgement.json` edits, commits, PR
text or any file in the repository. A finding may name a shared drive the org file
already names; nothing deeper.

### Step 4 — Judgement pass

Read the three files in full (`/tmp/org_context/files/<id>.md`), `checks.json`,
`facts.json` and `connectors.json`. Then write `/tmp/org_context/judgement.json` (format in the
`render_report.py` docstring):

1. **Edits for script findings.** For each finding with an obvious fix, add an entry under
   `edits`, keyed by the finding `key`. `find` is exact text from the file, unique in it;
   keep it as short as uniqueness allows. `replace` is the new text (`""` deletes).
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
   - **Wrong layer.** The org file is an orientation layer, not a runbook: code-level rules
     belong in the templates. A template rule that only repeats general behaviour may go,
     but templates must stand alone for people who never load the org file, so say which.
   - **Contradictions in substance** that differ in wording (e.g. one file mandates plan
     mode and another only suggests it).
   - **Missing guidance** an agent working in a fresh repo from that template would need.
   - **Repetition within a file** that the script missed (two bullets saying the same thing
     in different sections).

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

Finally run `python fetch_targets.py --mark-reviewed` so the next run can tell what
changed. This edits `references/_state.json`; include it in the skill's next commit or
the org-file PR.

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
- **Drive and Airtable are read-only and internal.** No writes through either connector,
  and no Drive or Airtable detail beyond what the org file already says in anything
  that leaves this machine.
- **Never fabricate.** No invented skills, repos, URLs or rules. A claim you cannot check
  is a finding without an edit.
