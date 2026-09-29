---
name: model-incorporation-metadata
description: Fills in the required metadata fields for an Ersilia Model Hub model, given the metadata.yml file and the original publication PDF. Reads the source code URL directly from the metadata file — no need to provide it separately. Use this skill whenever a user wants to populate, complete, or update a metadata.yml file for an Ersilia model, mentions an Ersilia model contribution, or is working on model metadata for the Ersilia Model Hub. Trigger even if the user just says "fill in the metadata" or "help me with the metadata.yml" in any Ersilia context.
---

# Ersilia Model Metadata Filler

Your job is to fill in specific fields of an Ersilia model's `metadata.yml` file using information extracted from the original publication (PDF) and the original source code repository.

## What you receive

The user will provide:
1. A path to the `metadata.yml` file (already partially filled from the model request)
2. A path or URL to the original publication PDF

The source code repository URL and publication URL are already in `metadata.yml` — read them from the file in Step 1 rather than asking the user. Only ask if those fields are empty or still contain placeholder text.

## What you must fill in

Fill **only** these fields — leave everything else exactly as it is:

| Field | Type | Accepted values |
|-------|------|-----------------|
| `Deployment` | list | see `deployment.txt` |
| `Source` | string | see `source.txt` |
| `Source Type` | string | see `source_type.txt` |
| `Task` | string | see `task.txt` |
| `Subtask` | string | see `subtask.txt` |
| `Output` | list | see `output.txt` |
| `Output Dimension` | integer | number of output values per input compound |
| `Output Consistency` | string | see `output_consistency.txt` |
| `Description` | string | one paragraph, 200–600 **characters** (enforced) |
| `Interpretation` | string | one sentence, max 20 words |
| `Tag` | list | see `tag.txt` |
| `Biomedical Area` | list | see `biomedical_area.txt` |
| `Target Organism` | list | see `target_organism.txt` |
| `Publication` | string | must be a DOI URL: `https://doi.org/...` |
| `Publication Type` | string | see `publication_type.txt` |
| `Publication Year` | integer | year |

`Description` is drafted at model-request time against the GitHub form. You **refine** it
here, once you have read the paper and the code and know more than the form did. Leave it
alone only if it already meets the standard in `references/writing-descriptions.md`.

**Never modify**: Identifier, Slug, Status, Title, Source Code, License, Contributor, and any auto-populated fields (Incorporation Date, S3, DockerHub, Model Size, etc.)

Four fields you do not write are nonetheless **controlled vocabularies, not free text**:
`License` (`license.txt`), `Status` (`status.txt`), `Input` (`input.txt`) and
`Docker Architecture` (`docker_architecture.txt`). If one of them looks wrong, raise it
with the user rather than editing it here.

## Reference documents

Read these when the judgement call is not obvious — they carry the reasoning and the
worked examples that do not fit here:

- `references/writing-descriptions.md` — how to write the Description and the Interpretation
- `references/field-semantics.md` — `Score` vs `Value`, `Output Consistency`, the
  `Output Dimension` invariant, publication rules, subtask edge cases

## Step-by-step workflow

### 0. Load allowed values from GitHub

Before filling anything, fetch all eleven controlled-vocabulary files directly from GitHub:

```
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/tag.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/biomedical_area.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/target_organism.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/task.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/subtask.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/output.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/output_consistency.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/source.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/source_type.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/deployment.txt
https://raw.githubusercontent.com/ersilia-os/ersilia/master/ersilia/hub/content/metadata/publication_type.txt
```

Each file is newline-separated. Fetch all eleven now and keep the lists in memory — you will validate every value you write against them.

These eleven cover the fields you write. The directory holds **fifteen** files in total;
the other four (`license.txt`, `status.txt`, `input.txt`, `docker_architecture.txt`)
constrain fields you must not modify.

### 1. Read the existing metadata.yml

Note the Source Code URL and Publication URL — you will need them. Confirm which fields still need filling (they may have template placeholder text like "Biomedical Area 1" or multiple values comma-separated).

### 2. Read the publication

Use the PDF reading tools to extract:
- What the model predicts (property, activity, representation, etc.)
- Number of endpoints/outputs (crucial for Output Dimension)
- Training dataset and target organisms
- Disease or application area
- Whether outputs are probabilities, measured values, or generated structures
- Year of publication and publication venue (journal vs preprint) — and, if it is a
  preprint, whether a published version now exists
- Any experimental validation the authors performed, and the stated limitations — both
  belong in the Description

### 3. Fetch the source code repository

Use WebFetch on the **remote GitHub repository** (the `Source Code` URL from `metadata.yml`). Do not read any local template files — `run_output.csv`, `run_columns.csv`, and `model/framework/` do not exist yet at this stage of the pipeline. Fetch only remote content:
- The repository README
- The repository file tree (to understand project structure)
- Specific remote source files only if needed to clarify output dimension or deployment type

From this, determine:
- Number of model endpoints / output columns (cross-check with paper)
- Whether the model calls an external API or runs locally
- Whether the license/code is from external authors, the Ersilia team, or re-trained

### 4. Fill in each field

Work through the fields systematically:

**Deployment + Source**
Use only values from the `deployment.txt` and `source.txt` lists fetched in Step 0.
- `Deployment: [Local]` and `Source: Local` for the vast majority of models — the model runs in Ersilia's infrastructure.
- Use `Online` only if the model posts predictions to an external third-party server/API that Ersilia does not control.
- `Deployment` is a list; `Source` is a single string.

**Source Type**
Use only values from the `source_type.txt` list fetched in Step 0.
- `External`: the model was developed by third-party authors (most models incorporated from published papers).
- `Internal`: developed by the Ersilia team themselves.
- `Replicated`: Ersilia re-trained the model following the original authors' methodology.

**Task + Subtask**
Use only values from the `task.txt` and `subtask.txt` lists fetched in Step 0. Choose Task first, then the corresponding Subtask:
- `Annotation` → model assigns a label or score to a molecule
  - `Activity prediction` if the output is biological/pharmacological activity
  - `Property calculation or prediction` if the output is a physicochemical or ADMET property
- `Representation` → model encodes a molecule into a numerical vector or projection
  - `Featurization` if it produces a fixed-length embedding/descriptor vector
  - `Projection` if it projects molecules into 2D/3D space
  - Models that return a **non-numeric** representation — a format conversion, a
    tokenisation, an IUPAC name, a natural-language description — also go under
    `Featurization`. The vocabulary has no better value, so this is a convention rather
    than a description. See `references/field-semantics.md`.
- `Sampling` → model generates or retrieves molecules
  - `Generation` if it generates new molecules
  - `Similarity search` if it retrieves similar molecules from a database

**Output**
Use only values from the `output.txt` list fetched in Step 0. Can be a list if the model has mixed output types.
- `Score`: a probability or likelihood (0–1 range, binary classification output)
- `Value`: a numerical measurement (IC50, logP, pKa, molecular weight, descriptors, embeddings…)
- `Compound`: a generated or retrieved molecule (SMILES or InChI)
- `Text`: natural language output
- Example: a model returning both a probability and an associated value would be `[Score, Value]`.

The line between the first two: **a score relates to a label; a value has a direct
interpretation of its own.** A column named `*_score` does not settle it — three hub models
emit computed descriptors or plain counts whose names say "score". Read the columns, not
their names (`references/field-semantics.md`).

**Output Dimension**
The number of output values produced per input compound. Only count continuous numeric outputs (scores, values) — do not count binary class labels separately. So a model with 6 endpoints each returning one probability score has Output Dimension 6, not 12.

**Invariant:** once `model/framework/columns/run_columns.csv` exists, `Output Dimension`
must equal its number of data rows. That file is written later by
`/model-incorporation-code` (Phase 4), so at this stage you are predicting its row count —
but if the paper and the repository disagree, the repository wins, because that is what the
served model returns.

This is often explicit in the paper ("6 endpoints", "512-dimensional vector"). If not stated directly:
- Count the number of prediction tasks/endpoints described
- Check the repository: look at model output shapes, column headers in example outputs, or README tables
- For embedding models, look for the vector size (e.g., 512, 1024, 2048)
- If the vector size is configurable (e.g., `n_components` is a user parameter), **ask the user** — do not guess a default from examples in the docs

**Output Consistency**
Use only values from the `output_consistency.txt` list fetched in Step 0.
- `Fixed`: the model always returns the same output for the same input (most QSAR models, classifiers, regression models)
- `Variable`: the model is stochastic and may return different outputs on repeated runs (generative models, models with dropout at inference, sampling-based methods)

**This field describes the code, not the subtask.** You can only answer it by reading the
inference path — look for unseeded `random` / `numpy.random` / `torch` sampling, a PyTorch
model served without `.eval()`, and whether a sequence model uses beam search (deterministic)
or sampling. A generator can legitimately be `Fixed`: one hub model runs OpenNMT with a fixed
beam size and never calls its own randomisation helper.

**If the model is stochastic because of a bug rather than by design** — most commonly a
missing `.eval()` leaving dropout active — write `Variable`, but say so explicitly to the
user. That value becomes wrong the moment the bug is fixed. See
`references/field-semantics.md`.

**Description**
One paragraph, **200–600 characters** — the limit is in characters, not words, and it is
enforced by `ersilia test`. Cover what the model does, the context of the original study,
how it was trained, any experimental validation the authors performed, known limitations,
and anything Ersilia changed. Never open with "This model…", never invent data, and never
reference another Ersilia model by identifier.

Full guidance, prohibitions and worked examples: **`references/writing-descriptions.md`**.
Read it before writing — this is the field users read first, and the one where generic text
is most obvious.

**Interpretation**
Write **exactly one sentence**. Hard limit: 20 words. Do not write two sentences. Do not start with "The model" — start with the output itself.

**Never use a colon (`:`) in the interpretation text.** Colons break YAML parsing unless the
whole value is quoted. (Strictly this is a `metadata.yml` hazard — JSON quotes every value,
so `metadata.json` models are unaffected — but keep the habit, since a model may be
converted.) Use a semicolon (`;`) or rephrase instead.

Four further requirements, each of which caught real errors:

- the interpretation must be **coherent with `run_columns.csv`** — exactly those columns
- regressions state the value **and its unit** ("logD at pH 7.4", "log mol/L")
- classifiers state the **cut-off** — the assay threshold behind the labels, and any
  recommended decision threshold
- similarity search names the **reference library** being searched

Do not reproduce column names verbatim from `run_columns.csv`; say what they mean.

Good examples:
- `Higher score indicates greater predicted probability of anti-malarial activity.`
- `100 features encoding molecular structure from a pretrained MACAW autoencoder.`
- `Predicted probability of AMES mutagenicity; values closer to 1 indicate higher risk.`
- `Binary indicators (1 = substructure present, 0 = absent) and total hit count.`
- `Predicted log10 Caco-2 permeability and efflux ratios across Caco-2 and MDCK assays.`

**Tag**
Choose one or more values from the list you read in Step 0 (`tag.txt`). Every value you write must appear verbatim in that file. If no tag fits well, pick the closest match — do not invent new tags.

**Biomedical Area**
Choose one or more values from the list you read in Step 0 (`biomedical_area.txt`). Every value must appear verbatim in that file. Use `Any` only if the model is truly domain-agnostic (e.g., a general-purpose molecular featurizer with no disease focus).

**Target Organism**
Choose one or more values from the list you read in Step 0 (`target_organism.txt`). Every value must appear verbatim in that file. Use `Any` if the model is not organism-specific.

**Publication**
The `Publication` field must be a DOI URL in the format `https://doi.org/...`. This applies to both peer-reviewed articles and preprints (bioRxiv, ChemRxiv, and arXiv all issue DOIs). If the existing metadata contains a PubMed URL, abstract page, or journal landing page, locate and substitute the DOI. If genuinely no DOI exists, use the most stable URL available and note this to the user.

Verify the URL resolves. But **HTTP 403 from ACS, RSC, Oxford, Wiley or MDPI on a
`doi.org` redirect is bot-blocking, not a dead link** — those pages open fine in a browser.
Do not "fix" them.

**Publication Type**
Use only values from the `publication_type.txt` list fetched in Step 0.
- `Peer reviewed` for articles published in journals (DOI typically starts with `10.1`, `10.3`, `10.7`, etc.)
- `Preprint` for bioRxiv (`10.1101/`), ChemRxiv (`10.26434/`), arXiv (`10.48550/`)
- `Other` only in exceptional cases (thesis, technical report, no publication)

**Before writing `Preprint`, check whether the preprint has since been published**, and cite
the published version if so. This is one lookup and it is easy to skip: in a 2026 audit,
nine of 17 cited preprints had been published since incorporation, affecting 21 models —
one arXiv entry alone is cited by 12 of them. Use the bioRxiv API (`published` field), DBLP
for ML conference papers, and Crossref or OpenAlex for journals. Do **not** trust arXiv's
`journal_ref`, which authors rarely update.

NeurIPS, ICLR, ICML and KDD papers are peer reviewed but **mint no DOI**. Convention: use
`Peer reviewed` only where the published version carries a DOI, so `Publication` and
`Publication Type` describe the same artefact.

**Publication Year**
The year of the **cited publication** — never the year the model was incorporated. This is
the field that goes wrong most often: of 26 wrong years found in the 2026 audit, 18 exactly
equalled the model's own incorporation year.

- For **internally built** models the rule still holds: if the model was trained on data
  published elsewhere, the year is that paper's, while `Incorporation Date` doubles as the
  training date.
- Where a journal gives both an **online** and an **issue** date, use the **issue year**.
- If the preprint has been published (see above), use the **published** version's year, even
  when `Publication` still points at the preprint because the venue mints no DOI. The two
  fields can legitimately disagree.

### 5. Propose all changes and ask for confirmation

Before writing anything, present every proposed value in a table:

| Field | Current value | Proposed value | Source |
|---|---|---|---|
| Deployment | … | [Local] | default |
| Source | … | Local | default |
| Task | … | Annotation | paper §2 |
| … | … | … | … |

The "Source" column should briefly indicate where the value came from (e.g. "paper §2", "repo README", "default", "user input"). Flag any field where the evidence was ambiguous with a note in the Source column (e.g. "paper unclear — assumed 512").

Then ask:

> "These are the values I propose to write to `metadata.yml`. Please confirm or correct any field before I update the file."

Only proceed to Step 6 once the user confirms. If the user corrects a value, update the table and re-show it before asking again.

### 6. Write the updated metadata.yml

Edit the file in place, replacing only the confirmed fields. Keep the YAML formatting consistent with the rest of the file (use list syntax for list fields, plain string for string fields, integer for integer fields).

**YAML safety**: any string value that contains a colon (`:`) must be wrapped in double quotes, e.g. `Interpretation: "Predicted log solubility: higher values indicate better solubility."` — otherwise the YAML is invalid. Before writing, check every string field you are changing for colons and quote it if needed.

### 7. Confirm and hand off

Print a one-line confirmation: "Done — N fields updated in `<path>/metadata.yml`."

Then list the remaining pipeline steps:

> **Remaining steps:**
> 1. Run `/model-incorporation-code` to wire up the model code into the template repository
> 2. Run `/ersilia-model-test` to validate the model runs correctly
> 3. Run `/model-incorporation-reproduce` to verify the model performs as reported in the paper
> 4. Push and open a pull request from your fork to `ersilia-os/eosXXXX`

## When you cannot determine a value

If you've read the paper and the repository and still cannot confidently determine a value (especially Output Dimension), state clearly what you found and what is unclear, and ask the user to clarify. Do not guess or leave placeholder text.
