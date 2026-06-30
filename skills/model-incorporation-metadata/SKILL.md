---
name: model-incorporation-metadata
description: Fills in the required metadata fields for an Ersilia Model Hub model, given the original publication as a PDF and the link to the original code repository. Use this skill whenever a user wants to populate, complete, or update a metadata.yml file for an Ersilia model, mentions an Ersilia model contribution, or is working on model metadata for the Ersilia Model Hub. Trigger even if the user just says "fill in the metadata" or "help me with the metadata.yml" in any Ersilia context.
---

# Ersilia Model Metadata Filler

Your job is to fill in specific fields of an Ersilia model's `metadata.yml` file using information extracted from the original publication (PDF) and the original source code repository.

## What you receive

The user will provide:
1. A path to the `metadata.yml` file (already partially filled from the model request)
2. A path or URL to the original publication (PDF)
3. A URL to the original source code repository (GitHub or similar)

## What you must fill in

Fill **only** these fields — leave everything else exactly as it is:

| Field | Type | Accepted values |
|-------|------|-----------------|
| `Deployment` | list | `Local`, `Online` |
| `Source` | string | `Local`, `Online` |
| `Source Type` | string | `External`, `Internal`, `Replicated` |
| `Task` | string | `Annotation`, `Representation`, `Sampling` |
| `Subtask` | string | `Property calculation or prediction`, `Activity prediction`, `Featurization`, `Projection`, `Similarity search`, `Generation` |
| `Output` | list | `Score`, `Value`, `Compound`, `Text` |
| `Output Dimension` | integer | number of output values per input compound |
| `Output Consistency` | string | `Fixed`, `Variable` |
| `Interpretation` | string | one sentence, max 20 words |
| `Tag` | list | see allowed values below |
| `Biomedical Area` | list | see allowed values below |
| `Target Organism` | list | see allowed values below |
| `Publication` | string | must be a DOI URL: `https://doi.org/...` |
| `Publication Type` | string | `Peer reviewed`, `Preprint`, `Other` |
| `Publication Year` | integer | year |

**Never modify**: Identifier, Slug, Status, Title, Description, Source Code, License, Contributor, and any auto-populated fields (Incorporation Date, S3, DockerHub, Model Size, etc.)

## Step-by-step workflow

### 0. Load allowed values from the ersilia repository

Before filling anything, read the three controlled-vocabulary files from the local ersilia repository. They live at:

```
ersilia-os/ersilia/ersilia/hub/content/metadata/tag.txt
ersilia-os/ersilia/ersilia/hub/content/metadata/biomedical_area.txt
ersilia-os/ersilia/ersilia/hub/content/metadata/target_organism.txt
```

Each file is newline-separated. Read all three now and keep the lists in memory — you will validate every value you write against them. If you cannot locate the files, ask the user for the path before proceeding.

### 1. Read the existing metadata.yml

Note the Source Code URL and Publication URL — you will need them. Confirm which fields still need filling (they may have template placeholder text like "Biomedical Area 1" or multiple values comma-separated).

### 2. Read the publication

Use the PDF reading tools to extract:
- What the model predicts (property, activity, representation, etc.)
- Number of endpoints/outputs (crucial for Output Dimension)
- Training dataset and target organisms
- Disease or application area
- Whether outputs are probabilities, measured values, or generated structures
- Year of publication and publication venue (journal vs preprint)

### 3. Fetch the source code repository

Use WebFetch on the repository URL (and its README, and key code files if needed) to understand:
- Number of model endpoints / output columns (cross-check with paper)
- Whether the model calls an external API or runs locally
- Whether the license/code is from external authors, the Ersilia team, or re-trained

### 4. Fill in each field

Work through the fields systematically:

**Deployment + Source**
- `Deployment: [Local]` and `Source: Local` for the vast majority of models — the model runs in Ersilia's infrastructure.
- Use `Online` only if the model posts predictions to an external third-party server/API that Ersilia does not control.
- `Deployment` is a list; `Source` is a single string.

**Source Type**
- `External`: the model was developed by third-party authors (most models incorporated from published papers).
- `Internal`: developed by the Ersilia team themselves.
- `Replicated`: Ersilia re-trained the model following the original authors' methodology.

**Task + Subtask**
Choose Task first, then the corresponding Subtask:
- `Annotation` → model assigns a label or score to a molecule
  - `Activity prediction` if the output is biological/pharmacological activity
  - `Property calculation or prediction` if the output is a physicochemical or ADMET property
- `Representation` → model encodes a molecule into a numerical vector or projection
  - `Featurization` if it produces a fixed-length embedding/descriptor vector
  - `Projection` if it projects molecules into 2D/3D space
- `Sampling` → model generates or retrieves molecules
  - `Generation` if it generates new molecules
  - `Similarity search` if it retrieves similar molecules from a database

**Output**
- `Score`: a probability or likelihood (0–1 range, binary classification output)
- `Value`: a numerical measurement (IC50, logP, pKa, molecular weight, descriptors, embeddings…)
- `Compound`: a generated or retrieved molecule (SMILES or InChI)
- `Text`: natural language output
- Can be a list if the model has mixed output types. Example: a model returning both a probability and an associated value would be `[Score, Value]`.

**Output Dimension**
The number of output values produced per input compound. Only count continuous numeric outputs (scores, values) — do not count binary class labels separately. So a model with 6 endpoints each returning one probability score has Output Dimension 6, not 12.

This is often explicit in the paper ("6 endpoints", "512-dimensional vector"). If not stated directly:
- Count the number of prediction tasks/endpoints described
- Check the repository: look at model output shapes, column headers in example outputs, or README tables
- For embedding models, look for the vector size (e.g., 512, 1024, 2048)
- If the vector size is configurable (e.g., `n_components` is a user parameter), **ask the user** — do not guess a default from examples in the docs

**Output Consistency**
- `Fixed`: the model always returns the same output for the same input (most QSAR models, classifiers, regression models)
- `Variable`: the model is stochastic and may return different outputs on repeated runs (generative models, models with dropout at inference, sampling-based methods)

**Interpretation**
Write **exactly one sentence**. Hard limit: 20 words. Do not write two sentences. Do not start with "The model" — start with the output itself.

Good examples:
- `Higher score indicates greater predicted probability of anti-malarial activity.`
- `100 features encoding molecular structure from a pretrained MACAW autoencoder.`
- `Predicted probability of AMES mutagenicity; values closer to 1 indicate higher risk.`
- `Binary indicators (1 = substructure present, 0 = absent) and total hit count.`

**Tag**
Choose one or more values from the list you read in Step 0 (`tag.txt`). Every value you write must appear verbatim in that file. If no tag fits well, pick the closest match — do not invent new tags.

**Biomedical Area**
Choose one or more values from the list you read in Step 0 (`biomedical_area.txt`). Every value must appear verbatim in that file. Use `Any` only if the model is truly domain-agnostic (e.g., a general-purpose molecular featurizer with no disease focus).

**Target Organism**
Choose one or more values from the list you read in Step 0 (`target_organism.txt`). Every value must appear verbatim in that file. Use `Any` if the model is not organism-specific.

**Publication**
The `Publication` field must be a DOI URL in the format `https://doi.org/...`. This applies to both peer-reviewed articles and preprints (bioRxiv, ChemRxiv, and arXiv all issue DOIs). If the existing metadata contains a PubMed URL, abstract page, or journal landing page, locate and substitute the DOI. If genuinely no DOI exists, use the most stable URL available and note this to the user.

**Publication Type**
- `Peer reviewed` for articles published in journals (DOI typically starts with `10.1`, `10.3`, `10.7`, etc.)
- `Preprint` for bioRxiv (`10.1101/`), ChemRxiv (`10.26434/`), arXiv (`10.48550/`)
- `Other` only in exceptional cases (thesis, technical report, no publication)

**Publication Year**
Extract the year of publication from the paper or publication URL.

### 5. Write the updated metadata.yml

Edit the file in place, replacing only the fields listed above. Keep the YAML formatting consistent with the rest of the file (use list syntax for list fields, plain string for string fields, integer for integer fields). Do not add quotes unless the original file uses them for that field.

### 6. Show the user what you changed

Print a brief summary of the fields you filled in and the values chosen. If any field required a judgment call or the evidence was ambiguous, say so clearly and invite the user to verify.

## When you cannot determine a value

If you've read the paper and the repository and still cannot confidently determine a value (especially Output Dimension), state clearly what you found and what is unclear, and ask the user to clarify. Do not guess or leave placeholder text.
