---
name: repository-auditing
description: >
  Audit an ersilia-os repository against the Ersilia house standard and produce a
  severity-tiered, report-only findings document. Checks documentation (README brevity and
  shape, the canonical About-Ersilia footer with its logo, LICENSE, CLAUDE.md), code quality
  (ruff against the canonical config, NumPy-convention docstrings, stale variables, unused
  imports, dead module-level names), hygiene (datasets or secrets in git, junk files,
  eosvc/access.json, stale .gitkeep), and repository metadata (GitHub description and topics,
  CI that actually runs lint and tests, semver tags matching the declared version, Airtable
  registry consistency). The checklist adapts to the repository Type from Airtable — Package,
  Analysis, Automation, App, Workshop or Documentation. Use this skill whenever the user
  wants a repository reviewed, tidied up, or checked against Ersilia conventions. Triggers
  include: "audit this repo", "audit the repository", "/repository-auditing", "is this repo
  up to standard", "check the repo conventions", "review the README and code quality",
  "does this repo have everything in place", "clean up this repository", "check docstrings
  and CLAUDE.md", "repo health check". Always use this skill for repository-audit requests
  even if the ask seems simple.
argument-hint: <repo-name|url|path> [--type <Type>] [--out <dir>]
allowed-tools: [Read, Bash, Write, Grep, Glob, AskUserQuestion]
---

# Repository auditing

You audit **one** ersilia-os repository against the Ersilia house standard and hand the
maintainer a findings document they can work down. The standard is not invented here — it is
versioned in `references/`, distilled from the `CLAUDE.md` files shipped by
`eos-python-package`, `eos-analysis-template` and `eos-template`, plus the working practice
of `ersilia-os/ersilia`.

This skill **finds and explains; it does not fix**. You never edit source, commit, branch,
push, or open a PR or issue. The single file you write is the report — `AUDIT.md` — and every
finding in it carries a concrete suggested fix, because the report's job is to be the input to
a later fixing session or plan. **Do not start fixing things in the same turn.** If the user
asks for fixes, treat it as a fresh request with its own plan.

This is an **interactive** skill. Ask before you assume — see *Questions you must ask* below.

Two properties matter more than coverage:

- **A skipped check is never a pass.** When `ruff` is missing, `gh` is unauthenticated, or a
  repo has no Python, the check goes in the report's *Checks not run* section. Silence must
  never read as a clean bill of health.
- **Suppression is always visible.** The target repo's own `CLAUDE.md` outranks the profile
  where it explicitly differs, but every suppressed finding is listed under *Accepted
  deviations* with the quote that justifies it.

Expect long reports on real repos. Of 16 surveyed, 3 have a `CLAUDE.md`, 4 have a `ruff.toml`,
4 have tests, and only `ersilia` uses NumPy docstrings. That is the actual state of the
codebase, not a miscalibration — report it plainly and let the maintainer choose the order.

---

## Inputs

- **`<repo-name|url|path>`** (required) — a bare name (`eosquality`), a GitHub URL, or a local
  path. Resolution prefers a clone that already exists under `~/Documents/GitHub/<name>`.
- **`--type <Type>`** — override the Airtable Type. Only use this when Airtable is wrong or
  absent; otherwise let Step 2 resolve it.
- **`--out <path>`** — where the report goes. Default is `AUDIT.md` at the **root of the
  audited repository** — always confirm this with the user (see below).

Never invent missing inputs, and never guess the repository type — the profile determines most
of the report, so a wrong type makes the whole audit misleading.

---

## Questions you must ask

Ask these with `AskUserQuestion`. Batch the ones you can into a single call rather than
interrogating one at a time, and ask them **before** running the checkers so the run is shaped
correctly the first time.

**1. Where does the report go?** Always ask — this is the one file written outside the skill,
and writing it into the repo root means it appears in that repo's `git status`. Options:

- `AUDIT.md` at the repository root (the default). Say plainly that this creates an untracked
  file in their working tree.
- `AUDIT.md` in this skill's `audits/` directory, leaving the target untouched.
- A path they name.

If a report already exists at the chosen path, say so and confirm the overwrite.

**2. The repository type**, whenever Airtable is silent, carries two types, or disagrees with
what the repo looks like. Never guess.

**3. Depth**, when the repo is large or the user has not said what they want:

- Baseline only (T0) — the fast pass, docs and hygiene.
- T0 + the type profile (the default).
- Everything including the aspirational Tier 2.
- Add the external-link check (`--check-external`) — needs the network and takes a while.

**4. Anything the checks flag that only they can resolve.** The clearest cases: a `T0-SECRETS`
hit needs them to confirm whether the credential was rotated; `PKG-DEP-UNUSED` and
`PKG-DEAD-MODULE-NAME` need them to say whether a name is public API; `T0-DEFAULT-BRANCH` on a
repo with external consumers is a deliberate choice. Ask rather than guessing in the report.

**5. Before writing, if the audit turned up something alarming** — a live credential, a
committed dataset, a repo that looks abandoned. Surface it in chat immediately; do not let it
sit only in a file they might not read.

---

## Workflow

Run the steps in order. Every step names the artifact it produces.

### Step 0 — Gates

```bash
gh auth status
git --version
python3 --version
command -v ruff || ls ~/miniconda3/bin/ruff
```

- **`git` missing** → stop. Nothing works without it.
- **`gh` missing or unauthenticated** → continue. The GitHub-side checks record themselves as
  skipped. Tell the user which checks that costs them.
- **`ruff` missing** → continue. The lint, formatting and docstring-presence checks record
  themselves as skipped; the AST-based checks still run. `which_ruff()` in `_common.py` finds
  ruff inside `~/miniconda3/bin` as well as on `PATH`.
- **Python version** — the scripts are stdlib-only and run on 3.9+. TOML parsing falls back to
  a subset reader in `_common.py` when `tomllib` (3.11+) and `tomli` are both unavailable, so
  do not go hunting for a newer interpreter.

### Step 1 — Resolve the target

```bash
python scripts/resolve_target.py <target> --out /tmp/repo_audit_target.json
```

Writes the target document: resolved path, how it was found, worktree state (branch, HEAD,
dirty, behind), and GitHub metadata.

- **Exit code 3 means the target is a model repo** (`eosNxxx`). Stop and point the user at
  `ersilia-model-test` and the `model-incorporation-*` skills. Model repos are generated from
  `eos-template` and their structure is not this skill's business.
- If the worktree is **dirty or behind upstream**, say so to the user now as well as in the
  report — findings describe the tree on disk, not `main`.
- Use `--no-clone` if the user wants to audit only what is already local.

### Step 2 — Determine the type

Read the Airtable `Repositories` record via the **MCP** — never from a Python script, which
cannot reach it. `references/airtable-repositories.md` has the base and table IDs, the exact
`list_records_for_table` call, and the fallback order.

Resolution order: Airtable → GitHub org custom properties → file-based inference. Then:

Four things to record, all of which are findings no script can produce because Python cannot
reach the MCP. Append them to `/tmp/repo_audit_docs.json`'s `findings` array by hand, using the
same shape as the scripts emit:

- `T0-AIRTABLE-MISSING` — no row for this repo at all.
- `T0-AIRTABLE-INCOMPLETE` — the row is missing `Status`, `Type`, `Title` or a description.
- `T0-AIRTABLE-NO-PROJECT` — the row links to no `Projects` record, so the repo cannot be
  traced to the work that funded it.
- `T0-AIRTABLE-TYPE-MISMATCH` — the declared `Type` does not match what you can see. A row
  saying `Package` on a repo with no `pyproject.toml`, or `Analysis` on one with no `data/` or
  `notebooks/`, means either the registry is stale or the repo drifted. **Always compare
  explicitly** rather than taking the row on trust; say which one you think is wrong.
- **If the record carries two types, or the fallbacks disagree, use `AskUserQuestion`.**
  Several repos are genuinely dual-typed (`gradi-target-prioritization` is Analysis + App).
- Keep hold of the `Status` values — `ANA-BADGE-PENDING` and `PKG-NO-RELEASE` depend on them.
- Note how the type was decided; it goes in the report header so the reader knows how much to
  trust the profile choice.

Then read the matching profile before interpreting any findings:
`references/profile-package.md`, `profile-analysis.md`, `profile-automation-app.md`, or
`profile-workshop-docs.md`. For anything CLI-shaped, `references/canonical-cli.md` carries the
canonical verbs, the `-i/--input` pair and the kebab-case ruling.

### Step 3 — Read the target's own `CLAUDE.md`

Read it in full. Extract only rules that **explicitly contradict** the profile, and write them
to `/tmp/repo_audit_overrides.json`:

```json
{
  "overrides": [
    {
      "check": "PKG-DEP-UNPINNED",
      "quote": "<verbatim sentence from the repo's CLAUDE.md that permits the divergence>",
      "note": "<one line on why this is reasonable here>"
    }
  ]
}
```

Rules:

- An override **requires a verbatim quote**. Without one it is discarded — the point is that
  the suppression traces to something the repo actually wrote down.
- A **stale `CLAUDE.md` grants no overrides.** If `check_docs.py` reported
  `T0-CLAUDEMD-STALE`, write `{"overrides": []}` and move on. An inherited template that was
  never adapted cannot authorise anything; `eosquality` would otherwise use the package
  template's own text to excuse itself.
- Do not invent overrides to shrink the report. A rule the repo merely fails to mention is not
  a deviation — it is a finding.

### Step 4 — Run the checkers

Pass the type and status through to all four. Substitute `{type}` and `{status}` from Step 2.

```bash
for c in docs code hygiene repo_meta practices; do
  python scripts/check_$c.py --target /tmp/repo_audit_target.json \
    --type "{type}" --status "{status}" --out /tmp/repo_audit_$c.json
done
```

All five take the same flags, so the loop above is the whole step. Add `--check-external` to
`check_docs.py` only if the user opted into external-link checking.

Each writes `{"findings": [...], "skipped": [...]}`. Each finding carries `id`, `tier`,
`severity`, `summary`, `fix`, and optionally `file`, `line`, `detail`, `confidence`. All four
exit 0 even when they find things — the findings are in the documents, not the exit codes. A
non-zero exit means the script itself failed; report that rather than proceeding as if the
checks passed.

### Step 5 — Judgement pass

Only for what the scripts cannot decide. Read the README and a representative sample of the
code, then:

- **README verbosity and filler.** The scripts count lines; you judge whether the content
  earns them. `stylia`'s 290 lines are mostly colour-reference tables and are defensible;
  `olinda`'s 295 are not. Add `PKG-README-FILLER` for empty
  Installation/Contributing/License/Acknowledgements boilerplate or AI-style restatements.
- **Whether the README reads as human.** `T0-README-AI-TONE` is a word-counting heuristic and
  is deliberately conservative — it will miss generated prose that avoids the obvious
  vocabulary. Read the README yourself and say plainly whether it sounds like a colleague
  explaining their work or like filler. Confirm or drop the script's verdict either way.
- **Whether the title is self-explanatory.** `T0-H1-IS-NAME` and `T0-H1-NOT-DESCRIPTIVE` catch
  the obvious cases; a three-word title can still say nothing. Suggest a concrete replacement
  rather than just flagging it.
- **Whether it is clear what the repo does and how it fits.** The scripts can only check that
  *something* is there. You judge whether a newcomer would actually understand the purpose,
  and whether the repo's place in Ersilia's work is stated.
- **Whether it feels messy.** `T0-ROOT-CLUTTER` counts files; you weigh the overall impression
  — half-finished directories, two scripts doing the same thing, naming that changed
  mid-project. Say so in one honest sentence.
- **Docstring quality.** A docstring with a `Parameters` section that restates the parameter
  names adds nothing. Note it; do not raise a separate finding per function.
- **Naming.** Misleading or stale names — a `tmp_` prefix on something permanent, a function
  whose name no longer matches what it does.
- **False positives.** `PKG-DEAD-MODULE-NAME` is a heuristic and says so; verify a few before
  passing them on. A name reached through `getattr`, a plugin registry, or a string import
  looks dead and is not.
- **Type-specific judgement** the profiles call for: `WSH-NO-AUDIENCE` and `DOC-BROKEN-NAV`
  are yours to assess, not any script's.

You may **downgrade** a finding, never silently. Add `downgraded_from` and
`downgrade_reason` to it so the report shows the original severity and your reasoning.

### Step 6 — Render

**Write the verdict first.** Two or three sentences, in your own words, saved to a file you
pass via `--verdict`. It is the only part of the report a person is guaranteed to read.

- Name the single biggest problem, and say what kind of work this is — scaffolding, repair,
  a rewrite, or nothing much.
- Say plainly when a repo is in good shape. "Solid, well-documented package" is a useful
  sentence; refusing to say it because there are 25 should-fix items is not.
- Do **not** restate the counts — the table right below already has them.
- No hedging, no "consider", no listing what you are about to list anyway.

If you have nothing honest to say, pass no `--verdict` and the section is omitted. Never
synthesise it from the counts.

**Then confirm the output path** (question 1) and render:

```bash
python scripts/render_report.py \
  --target /tmp/repo_audit_target.json \
  --findings /tmp/repo_audit_docs.json /tmp/repo_audit_code.json \
             /tmp/repo_audit_hygiene.json /tmp/repo_audit_repo_meta.json \
             /tmp/repo_audit_practices.json \
  --overrides /tmp/repo_audit_overrides.json \
  --verdict /tmp/repo_audit_verdict.txt \
  --start-here '<first thing>' --start-here '<second>' --start-here '<third>' \
  --type "{type}" --type-source "{airtable|github-properties|inferred|user}" \
  --date {YYYY-MM-DD} \
  --out "{confirmed path}"
```

`--date` is the real session date — the scripts never call `datetime.now()`, so pass it
explicitly. Omitting `--out` writes `AUDIT.md` at the audited repo's root. Exit code 1 means
Blockers were found; that is information, not a failure.

`--start-here` is your ordering of what to do first, in plain language. Without it the report
falls back to the first three fix-plan entries, which is correct but blunt.

The report has three parts plus a trail: **Verdict** (your prose, the area status table, start
here), **Findings** grouped by area — one line each, what is wrong and where — and the **Fix
plan**, a checklist tagged `AUTO` / `EDIT` / `ASK` saying what to do. Accepted deviations,
hand-verified checks and skipped checks are collapsed into an audit trail at the end.

Findings and the Fix plan deliberately carry *different* content for the same finding:
diagnosis in one, prescription in the other. Do not "improve" this by repeating the fix text in
Findings — that duplication is what made the first version of this report twice as long as it
needed to be.

Two things happen automatically and need no flag:

- **A repeat audit opens with a delta** — "Since the 2026-07-21 audit: 2 fixed, 1 no longer
  checked, 1 new". It reads the previous report at `--out`, so point `--out` at the same path
  to get it. A check that was gated out this run reports as *no longer checked*, never as
  fixed.
- **Evidence beyond two items moves to a collapsed appendix** keyed by check ID. Findings stay
  one line each; nothing is silently dropped.

### Step 7 — Report back

Keep the terminal output **short** — the report is the deliverable.

- Your verdict sentence.
- Every Blocker, one line each.
- Any check that did not run and matters (no `ruff`, no `gh`).
- The report path.

That is all. The counts, the areas and the fix plan are in the file; repeating them in chat
wastes the reader's attention twice. Do not offer to fix things unless the user asks — and if
they do, treat it as a fresh request with its own plan.

---

## Scripts

- **`_common.py`** — findings model (`finding`, `skipped`, `emit`), `run_gh_json`,
  `which_ruff`, tracked-file and blob-size helpers, `load_toml` with a stdlib subset fallback.
  Stdlib only.
- **`resolve_target.py`** — locates or blobless-clones the repo, refuses `eosNxxx`, describes
  the worktree. Exit 3 = model repo.
- **`check_docs.py`** — README shape and length, footer wording/position/logo, LICENSE,
  `CLAUDE.md` presence and staleness, relative-link resolution, placeholder text.
- **`check_code.py`** — `ruff check` and `ruff format --check` against
  `references/canonical-ruff.toml`, NumPy docstring sections via AST, dead module-level names,
  dependency pinning, competing linters, pre-commit, tests, CLI, and the Analysis-profile
  script conventions.
- **`check_hygiene.py`** — `.gitignore`, junk, datasets and large files in the index, secrets,
  `access.json`, stale `.gitkeep`, Analysis root-layout, notebook outputs.
- **`check_repo_meta.py`** — repo naming (hyphens only), GitHub description/topics/default
  branch, CI quality jobs, workflow documentation and pinning, App entry points, semver and
  version agreement, and **maturity-gated Tier 2** (pass `--backs-paper` when Airtable links
  the repo to a publication, which enables the `CITATION.cff` check).
- **`check_practices.py`** — bad practices (bare excepts, `print` in library code, hardcoded
  absolute paths, `shell=True`, wildcard imports, mutable defaults, commented-out code, TODO
  density), modularity (god modules, long functions, deep nesting, flat namespace), root
  clutter and file naming, eosvc appropriateness.
Two committed example reports live in `examples/` — one busy, one near-clean — with a README
explaining what each section demonstrates. Read them before changing the output format.

- **`render_report.py`** — merges the five documents, applies overrides, and writes the
  three-part report. Owns `AREA_OF` (check ID → area) and `AREA_TYPES` (area → applicable
  repo types); a check ID missing from `AREA_OF` lands in `Other` and logs a warning.

---

## Things to avoid

- **Never fix anything in the same turn as the audit.** The report suggests fixes; it does not
  apply them. No source edits, no `git add`, no commits, no branches, no pushes, no PRs, no
  issues. `AUDIT.md` is the only file you may write, and only at a path the user confirmed.
- **Never write the report without asking where it goes.** Writing into the repo root creates
  an untracked file in someone's working tree.
- **Never audit a model repo.** `eosNxxx` is out of scope; delegate to `ersilia-model-test`
  and `model-incorporation-*`.
- **Never let a skipped check disappear.** If a script fails, say so in the report and to the
  user. An audit that quietly covered half the checklist is worse than no audit.
- **Never suppress a finding without a quote** from the target's own `CLAUDE.md`.
- **Do not report a numeric score.** Severity tiers only; a percentage invites the wrong
  conversation.
- **Status markers only, never decorative emoji.** 🔴 🟡 ⚪ ✅ — are data. Section-heading
  emoji and decorative ones are not, and the skill flags `T0-README-EMOJI` in other people's
  repos. Obey the standard you enforce.
- **Never write `(s)` or `(ies)` in a finding.** Use `plural()` and `verb()` from
  `_common.py`. `13 dependency(ies) are unpinned` is the clearest possible signal that nobody
  wrote this sentence, in a report that asks other people's prose to read as human work.
- **Never truncate mid-string.** Evidence cuts at an item boundary, prose at a word boundary.
  Both have shipped broken before — `docs/conc…` and `mirroring \`ersilia\`'s \`tests_and_c…`.
- **Never claim ✅ for a check that did not run.** This is the invariant the whole skill rests
  on and it broke twice during development. `AREA_TYPES` in `render_report.py` decides which
  areas apply to which type; an area that does not apply is omitted, not marked clean.
- **Do not pad the report.** If a repo has four findings, the report has four findings.
- **Do not treat the templates as exempt.** `eos-analysis-template` ships an empty
  `requirements.txt` against its own rule. Being the source of a rule is not compliance —
  though genuine template placeholder text *is* suppressed, and visibly so.

---

## Edge cases

- **Non-Python repos.** Apps and Automation repos are often YAML or JavaScript. The Python
  checks record themselves as skipped rather than passing vacuously.
- **Monorepos and nested packages.** The scripts assume one package per repo. If you find
  several, say so and audit the root; do not silently pick one.
- **Archived repos.** Audited normally, with a note in the report — the effort calculus is the
  maintainer's call, not yours.
- **Private repos.** Work fine as long as `gh` is authenticated for them.
- **Template repos.** `is_template` on GitHub, or an `eos-*-template` name, suppresses the
  placeholder checks. Everything else still applies.
- **A repo with no Airtable row.** Audit proceeds on an inferred type; the missing row is
  itself a finding.
- **Type is `Template`.** Use the Package profile if a `pyproject.toml` exists, otherwise the
  Analysis profile, and say which you chose.
- **The user asks for several repos.** This skill audits one per invocation, by design. Run it
  once per repo and say that is what you are doing.

---

## Relationship to other Ersilia tooling

Checked against the Airtable registry so this skill does not duplicate existing work:

| Repo / skill | What it does | Overlap |
|---|---|---|
| `eosquality` | Scores the trustworthiness of model *predictions* | None — different subject |
| `ersilia-maintenance`, `ersilia-model-workflows` | Maintain *model* repos: metadata sync, model testing, ecosystem analytics | None — model repos are out of scope here |
| `eosvc` | Syncs large artifacts to S3 | Complementary — this skill checks that it is set up correctly |
| `eosbench` | Benchmarking datasets | None |
| `github-digest` (skill) | Org-wide registry drift, issue and PR activity | **Adjacent.** It checks the registry across all 179 repos; this skill checks one repo's contents in depth. Keep the split: org-wide registry health belongs there, per-repo file and code checks belong here. |
| `ersilia-model-test`, `model-incorporation-*` (skills) | Model repo testing and incorporation | None — `eosNxxx` is refused here and delegated to them |

Nothing in the org audits repository contents, which is why this skill exists.
