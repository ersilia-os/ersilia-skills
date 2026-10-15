---
name: model-incorporation-request
description: >
  Open a model request issue on ersilia-os/ersilia for a new model to be incorporated
  into the Ersilia Model Hub. Use this skill whenever a user wants to request a new
  model, open a model request, or start the model incorporation pipeline. The skill
  reads the publication PDF and source code repository to propose all required fields,
  asks the user to confirm, then opens the GitHub issue mimicking the official
  ersilia-os/ersilia model request form. Trigger on phrases like "request a model",
  "open a model request", "add a new model to the hub", "start model incorporation",
  or "open an issue for a new model".
allowed-tools: [Bash, Read, WebFetch, WebSearch, AskUserQuestion]
---

# Model Incorporation Request

Your job is to open a model request issue on [ersilia-os/ersilia](https://github.com/ersilia-os/ersilia) that exactly mirrors the official model request form, using information extracted from the publication and source code repository.

## Parse Arguments

- `--pdf <pdf-path>` (required): local path to the publication PDF
- `--publication <url>` (required): URL to the publication (DOI, arXiv, journal)
- `--source <url>` (required): URL to the source code repository (GitHub, GitLab, Zenodo, etc.)
- `--no-approve` (optional): do not post `/approve`; leave approval to someone else
- `--clone-dir <path>` (optional): where to clone the fork (default `~/Desktop`)

If any argument is missing, ask the user before proceeding.

---

## Phase 1 – Extract Information

### 1a. Read the PDF

Extract:
- Model name / what it does (for Title and Name)
- What the model predicts or computes — in plain language (for Description)
- Application areas and relevant keywords (for Tags)

### 1b. Fetch the source code repository

Use WebFetch on the repository URL (README and root files) to extract:
- License — look for a LICENSE file or license field in pyproject.toml / setup.py / package.json
- Any additional context for the description or tags

**Verify the licence at the source rather than trusting the README.** For a GitHub
repository, ask the API what it detected:

```bash
gh api repos/<owner>/<repo>/license --jq '.license.spdx_id'
```

- an id that appears in `license.txt` → use it.
- `GPL-3.0`, `AGPL-3.0` or `LGPL-3.0` → GitHub uses these older ids, but `license.txt` only has
  the `-only` and `-or-later` forms. The LICENSE file does not say which, so read the README or
  a source-file header: "either version 3 or any later version" means `-or-later`, version 3
  alone means `-only`. If neither says, ask the user.
- any other id missing from `license.txt` (for example `GPL-2.0` or `Unlicense`) → ask the user
  which value fits; never invent one.
- `NOASSERTION` or `Other` → GitHub found a licence file it cannot classify, which is what
  custom and non-commercial terms look like. Read the text
  (`gh api repos/<owner>/<repo>/license --jq .content | base64 -d | head -40`), name the
  licence, and take the closest `license.txt` value (`Non-commercial` for any
  non-commercial terms).
- the command fails with `404` → there is no licence file, so the value is `None`.

For GitLab, Zenodo or a package page, read the licence from that page instead.

The Hub already holds models under all three situations, so none of them blocks a request.
They are still worth raising before the user confirms, because they are cheapest to decide now:

- `None` — code with no licence is all-rights-reserved by default, so redistributing it rests
  on the authors' goodwill. Suggest the user ask them to add one.
- non-commercial — quote the terms, since they bind everyone who runs the model.
- checkpoints on different terms from the code — check the README or model card for a separate
  licence on the weights, and say so.

### 1c. Fetch the valid tag and license lists

Fetch both files at runtime:
```
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/tag.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/license.txt
```
Both are newline-separated. Keep both lists in memory — you will validate tags and the license against them.


### 1d. Check whether the model is already requested or in the Hub

Do this before drafting. A duplicate request costs an approval, a repository and an Airtable
row. Scripts live in `scripts/` next to this file; run them by full path. This one prints JSON.

```bash
python scripts/check_duplicates.py --publication "<publication-url>" --source "<source-url>" \
  --name "<tool name used in the paper>" --query "<task> <endpoint>"
```

It runs two checks. **exact**: the DOI, arXiv id or source repository already appears in a
`new-model` request (open or closed) or in the published-models list. **similar**:
`ersilia_search` by tool name and by task and endpoint across every status, plus a scan of the
non-Ready models, whose empty descriptions a text query misses. `related_requests` mention the
tool name but share no identifier.

Report what it found at the top of Phase 2, before the table:

| Finding | Say |
|---|---|
| exact, request open | Already requested as #N (repo eosXXXX if created) |
| exact, request closed with a repo, or in the published list | Already in the Hub as eosXXXX |
| exact, request closed with no repo | Requested as #N and closed without a repository |
| similar, Ready | Potential overlap with eosXXXX |
| similar, In progress or In maintenance | Already in the pipeline as eosXXXX |
| similar, Archived | Previously incorporated, now archived as eosXXXX |
| related request | Possibly related request #N |

Do not decide for the user. An exact match is a reason to stop and ask, not to refuse: the Hub
deliberately deploys one paper as several entries (CReM mutate and grow, the four MolGrad
models), so ask what this request adds. Never guess why a request was closed. If nothing is
found, say so in one line and carry on. If the script reports a note, such as `ersilia_search`
missing, pass it on instead of presenting the result as clean. Limits and how to read the
output: `references/duplicate-check.md`.

---

## Phase 2 – Propose All Fields and Confirm

Present all proposed values in a single table and wait for the user's feedback before proceeding. Do not open the issue until the user explicitly confirms. If Phase 1d found an exact match, stop and ask whether to continue before building the table.

| Field | Proposed value |
|---|---|
| Title | `🦠 Model Request: <Name>` |
| Name | ... |
| Slug | ... |
| Description | ... |
| Tags | ... |
| Publication | (from --publication argument) |
| Source Code | (from --source argument) |
| License | ... |

Field rules:

**Title / Name**
`<Name>` should be concise (2–5 words), title-case, describing what the model does. The Name field is the same `<Name>` without the emoji prefix.

**Slug**
Lowercase, hyphens only, **2–4 words maximum**. Keep it short and memorable — it becomes part of the model's permanent identifier. Propose a single best option (e.g. `morgan-fingerprints`, `tb-growth-inhibition`). If you find yourself using more than 4 words, trim ruthlessly. Drop a task-type word (`-gen`, `-pred`, etc.) once another word already disambiguates the slug. Prefer a word naming the model's **use case or target** over one naming the underlying ML method/architecture (`-xgboost`, `-gnn`, `-transformer`) — the method is an implementation detail, not something a hub user searches for. Exception: when the method itself is the deliverable and there's no separate use case to name, such as a general-purpose featurizer (`morgan-fingerprints`), keep it.

These rules are **not enforced anywhere**. `BaseInformation.slug` and
`BaseInformationValidator` check only that the value is lowercase and 5–60 characters long,
so spaces, underscores and punctuation all pass validation cleanly (ersilia-os/ersilia#1899).
Getting the slug right is manual — nothing downstream will catch it.

**Description**
200–600 characters (hard limits from the GitHub form, and enforced later by `ersilia test`).
Plain English, focused on what a user gets from running this model on a molecule. Do not
start with "This model...". Do not include a character count in the table — just show the
description text.

**This limit is enforced server-side, not just by convention.** The `/approve` GitHub
Actions workflow that a maintainer triggers on the issue runs
`update_metadata_from_model_request.py`, which raises `ValueError` and fails the whole
workflow if the description is outside 200–600 characters. Never eyeball the length —
after drafting the description (and after any later edit to it, including one made in
response to user feedback), count it explicitly, e.g.:
```bash
python3 -c "print(len('''<description text>'''))"
```
If it's out of range, shorten/lengthen and recount before presenting the table. Do not
present or submit a description you have not just counted.

For structure, prohibitions and worked examples, read
`model-incorporation-metadata/references/writing-descriptions.md` — the single source of
truth for this field. The description written here is a first draft;
`/model-incorporation-metadata` refines it once the paper and the code have been read.

**Tags**
Pick only from the tag list fetched in Phase 1c. Choose **2–4 tags maximum** — only the most directly relevant ones. Do not tag everything that loosely applies; prefer precision over coverage. At least one is required.

**Source Code**
Must point at **code** — a repository, a package page, an archived release — not at the
paper. Three URL forms rot and should be avoided:

- **a bare IP address** (one hub model points at `http://130.92.106.217:8080/...`, which no
  longer responds and has no hostname to fall back on)
- **a deep file path inside a repository** (`.../blob/main/pkg/module/file.py`). Two hub
  models broke when the upstream repo was refactored; the repository root would have
  survived. Link the root.
- **an academic project page** on a university host. Several have disappeared entirely.

Where the upstream repository may not last — a personal account, an unreleased project —
prefer a DOI (Zenodo) or a package page (PyPI, Conda), which are archived.

**License**
Use the value established in Phase 1b, and only values from the `license.txt` list fetched in Phase 1c. Use `None` if no LICENSE file is found. Under the table, say in one line how the licence was verified, and add any flag raised in Phase 1b.

Before asking, run `gh api repos/ersilia-os/ersilia --jq .permissions.push`. `/approve` only
works for users with write access, so this decides whether Phase 3 can post it. Then, after
presenting the table, ask: *"Does this look correct? Let me know any changes and I'll open the issue."*
and say what else confirming will do: assign the user to the issue and, when the check printed
`true` and `--no-approve` was not passed, post `/approve` to create the model repository, then fork it and clone it into the clone
directory. If the check printed anything else, say that an admin will need to approve it.

---

## Phase 3 – Open the GitHub Issue

Use `gh issue create` to open the issue on `ersilia-os/ersilia`. Format the body to match exactly what the GitHub form produces when submitted — each field as a level-3 heading followed by its value:

```
### Model Name

<name>

### Model Description

<description>

### Slug

<slug>

### Tag

<tag1>, <tag2>

### Publication

<publication-url>

### Source Code

<source-url>

### License

<license>
```

Use a HEREDOC to pass the body:

```bash
gh issue create \
  --repo ersilia-os/ersilia \
  --title "<title>" \
  --label "new-model" \
  --body "$(cat <<'EOF'
<body>
EOF
)"
```

Keep the issue number from the URL that `gh issue create` prints, then:

**Assign the user.** Do it as a separate call, because an assignee GitHub rejects would make
`gh issue create` fail and open nothing:

```bash
gh issue edit <number> --repo ersilia-os/ersilia --add-assignee "@me"
```

If it fails, say so and carry on.

**Approve.** Skip this if `--no-approve` was passed or the Phase 2 check printed anything other
than `true`: `/approve` is ignored for users without write access, and the skill would wait for a
bot comment that never comes. Otherwise post it. The issue body must already be final, because
approval reads it to build the repository and to sync Airtable and S3.

```bash
gh issue comment <number> --repo ersilia-os/ersilia --body "/approve"
```

Then wait for the bot, with the Bash timeout raised to 10 minutes (600000 ms), since approval
normally takes about two minutes:

```bash
python scripts/wait_for_repo.py <number>
```

It prints JSON, `status` being `created` (with `repo`, the eosXXXX name), `failed` (with the
`workflow_url`), `timeout`, `not_approved` or `error`. On `failed`, go to Phase 3.5. On
`timeout` or `error`, give the user the issue link and stop. Do not post `/approve` again, since
a second run would create a second repository.

**Fork and clone.** Only when the status is `created`; otherwise there is no repository yet.
Take `<id>` from the `repo` the script printed, and `<dir>` from `--clone-dir` (default
`~/Desktop`). Never overwrite: if `<dir>/<id>` already exists, say so and stop here.

```bash
gh repo fork ersilia-os/<id> --clone=false --remote=false
gh repo clone "$(gh api user --jq .login)/<id>" <dir>/<id>
```

Forking is safe to repeat: if the user already has the fork, `gh` says so and carries on. Because
the repository is a fork, `gh repo clone` also adds `upstream` pointing at `ersilia-os/<id>`.
If the clone fails straight after the fork was created, wait a few seconds and retry, since a new
fork takes a moment to become ready. Finish by checking `git -C <dir>/<id> remote -v`: `origin`
should be the user's fork and `upstream` should be `ersilia-os/<id>`.

---

## Phase 3.5 – If `/approve` Fails

Commenting `/approve` on the issue, whether the skill does it or a maintainer, triggers
the `Approve Command Dispatch` workflow. If that workflow fails (a `github-actions` bot
comment appears saying "Workflow Failure ❌", which `wait_for_repo.py` reports as `failed`),
do this:

1. **Read the actual error**, don't guess. Get the run ID from the bot comment's log link
   or from `gh issue view <n> --repo ersilia-os/ersilia --json comments`, then:
   ```bash
   gh run view <run-id> --repo ersilia-os/ersilia --log-failed
   ```
   The most common cause is exactly the description-length check above — the traceback
   ends in `ValueError: Model description is N characters, which exceeds the 600-character
   limit.` Fix by editing the issue body (`gh issue edit <n> --repo ersilia-os/ersilia
   --body "..."`, same heading format as Phase 3) with a re-counted description, then
   comment `/approve` again and run `python scripts/wait_for_repo.py <n>` again; it reads
   only the bot comments after the latest `/approve`, so the earlier failure is ignored.
2. **Don't assume the failure-notice repo was actually created.** The bot's failure
   comment says "you may need to delete the following repo... since the run was not fully
   successful" *unconditionally* — it does not know whether repo creation itself
   succeeded before the later step failed. Check before doing anything about it:
   ```bash
   gh api repos/ersilia-os/<mentioned-repo> --jq '{created_at}'
   ```
   A 404 means it was never created (nothing to clean up). Only if it returns real data
   should you consider deleting it — and deleting a repo under the `ersilia-os` org is a
   destructive, shared-system action, so confirm with the user first regardless.
3. After a successful re-run, confirm the new repo by reading the issue's latest comment
   (`gh issue view <n> --repo ersilia-os/ersilia --json comments --jq '.comments[-1]'`) —
   the success comment names the new `eosXXXX` repo directly.

---

## Phase 4 – Tell the User What Happens Next

After the issue is opened, print the issue URL, say whether the user was assigned, whether
`/approve` was posted and where the fork was cloned, and explain the next steps:

1. If `/approve` was posted and the bot answered, the model repository (`eosXXXX`, the `repo`
   the script printed) now exists under `ersilia-os`. Otherwise an admin comments `/approve` on
   the issue and the bot announces the repository there
2. The skill forked it to the user's account and cloned it to `<dir>/<id>`, with `upstream` set. If it did not, fork and clone it by hand
3. Run `/model-incorporation-metadata` to fill in the metadata
4. Run `/model-incorporation-code` to wire up the model code
5. Run `/ersilia-model-test` to validate the model runs correctly before submitting a PR
6. Run `/model-incorporation-reproduce` to verify the model performs as reported in the paper
