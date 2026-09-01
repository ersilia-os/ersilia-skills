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

### 1c. Fetch the valid tag and license lists

Fetch both files at runtime:
```
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/tag.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/license.txt
```
Both are newline-separated. Keep both lists in memory — you will validate tags and the license against them.

---

## Phase 2 – Propose All Fields and Confirm

Present all proposed values in a single table and wait for the user's feedback before proceeding. Do not open the issue until the user explicitly confirms.

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
Use only values from the `license.txt` list fetched in Phase 1c. Use `None` if no LICENSE file is found.

After presenting the table, ask: *"Does this look correct? Let me know any changes and I'll open the issue."*

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

---

## Phase 4 – Tell the User What Happens Next

After the issue is opened, print the issue URL and explain the next steps:

1. An Ersilia admin will review and approve the request
2. Once approved, a new model repository (`eosXXXX`) is created under `ersilia-os`
3. Fork that repository and clone it locally
4. Run `/model-incorporation-metadata` to fill in the metadata
5. Run `/model-incorporation-code` to wire up the model code
6. Run `/ersilia-model-test` to validate the model runs correctly before submitting a PR
7. Run `/model-incorporation-reproduce` to verify the model performs as reported in the paper
