---
name: model-incorporation-reproduce
description: >
  Reproduce the key performance metrics or outputs reported in a paper for an Ersilia Model Hub
  model. Detects the model type (Annotation, Representation, or Sampling) from metadata and applies
  the appropriate workflow: benchmarking against paper metrics (Annotation), output equivalence of
  embeddings against the original code (Representation), or distribution comparison of generated
  molecules against the training set (Sampling). Use this skill whenever a user wants to verify
  that an incorporated model performs as described in its paper, after running
  model-incorporation-code. Trigger on phrases like "reproduce the results", "check model
  performance", "validate the model against the paper", "does the model match what the paper
  reports", "benchmark the model", or any request to verify an incorporated Ersilia model against
  its publication.
allowed-tools: [Bash, Read, Write, WebFetch, WebSearch, AskUserQuestion]
---

# Model Incorporation — Reproduce

Your job is to verify that an incorporated Ersilia model performs as reported in its paper. The
exact verification strategy depends on the model type. You detect the type automatically and branch
into the appropriate workflow. The process is **guided** — you propose at each step and wait for
the user to confirm before proceeding.

## Parse Arguments

- `--template <path>` (required): local path to the incorporated model repository (eosXXXX)
- `--paper <path>` (required): local path to the publication PDF
- `--model-id <id>` (optional): model ID; inferred from the folder name if not given

If any required argument is missing, ask the user before proceeding. Infer `<model-id>` from
the last component of `--template` path if `--model-id` is omitted.

---

## Phase 0 — Model Type Detection

1. Read `<template>/metadata.yml` and extract the `Task` field.
   - `Annotation` → the model assigns a score or label to each input molecule.
   - `Representation` → the model encodes each molecule into a numerical vector.
   - `Sampling` → the model generates or retrieves new molecules.
2. Tell the user: *"Detected model type: [X]. I will use the [X] reproduction workflow."*
3. Branch into the appropriate section:
   - **Annotation** → Branch A
   - **Representation** → Branch R
   - **Sampling** → Branch S

---

## Branch A — Annotation Workflow

### Phase A0 — Output Equivalence Check

Before reproducing paper metrics, verify the Ersilia wrapper produces the same raw outputs as the
original code. This catches wrapping bugs (wrong preprocessing, wrong model weights, wrong output
column) before spending time on benchmarking.

**Step 1 — Find the reference implementation**

Check in this order:
1. `<template>/metadata.yml`: look for a `GitHub`, `Source`, or `BibTeX` field with a repo URL.
2. The paper PDF: search for "Code availability", "Software availability", or any GitHub/GitLab URL.
3. `<template>/README.md`: look for a "Source code" or "Original implementation" link.

**Step 2 — Clone and install**

If a repository URL is found:
```bash
git clone <url> /tmp/<model_id>_original
cd /tmp/<model_id>_original
pip install -r requirements.txt   # try conda env create -f environment.yml if pip fails
```

On install failure: tell the user what failed, and ask:
> "I could not install the original implementation ([error]). Would you like to skip the
> equivalence check, or provide a reference prediction file yourself (a CSV with `smiles` and
> `<score>` columns)?"

**Step 3 — Run equivalence test**

If installable (or if user provides reference predictions):
1. Write the 20 test molecules from `references/test_molecules.csv` to
   `/tmp/<model_id>_eq_input.csv` (single `smiles` column).
2. Run through the original code → `/tmp/<model_id>_eq_reference.csv`.
   Ask the user for the exact invocation command if not obvious from the repo's README.
3. Run the same molecules through the Ersilia wrapper:
   ```bash
   bash model/framework/run.sh model/framework \
       /tmp/<model_id>_eq_input.csv \
       /tmp/<model_id>_eq_ersilia.csv
   ```
4. Align both outputs by SMILES. Compare the score column:
   - Compute Spearman rank correlation (r) and mean absolute difference.
   - **EQUIVALENT** — r ≥ 0.999
   - **APPROXIMATE** — 0.990 ≤ r < 0.999
   - **DIVERGENT** — r < 0.990 → warn the user that the wrapper may be broken

Record result; include it in the Phase A6 report.

---

### Phase A1 — Extract Reported Performance Metrics

Read the PDF carefully. Focus on:
- Abstract (headline metric)
- Results section and performance tables
- Columns labelled "Test set", "Hold-out", or "External validation" (prefer test over validation)
- Figures that include quantitative values

For **each metric that belongs to the model being incorporated** (ignore baseline comparisons),
capture:

| Field | What to record |
|---|---|
| metric | AUC-ROC, RMSE, R², accuracy, MCC, F1, MAE, AUC-PRC, … |
| value | The reported numeric value |
| dataset | Name of the benchmark used |
| split | train / val / test — always prefer the test set |
| task | classification or regression |
| notes | "5-fold CV average", "scaffold split", "external set", etc. |

Present the full table to the user and ask:

> "These are the performance metrics I found for this model in the paper. Please remove any you
> don't want to reproduce and confirm the rest."

---

### Phase A2 — Assess Reproducibility

For each confirmed metric, investigate before attempting anything:

1. Check the source code repository (use `--template` repo's README and any `data/` folder) for
   dataset files, download scripts, or supplementary links.
2. Search the paper for a "Data availability" statement, supplementary tables, or DOI links to
   Zenodo / Figshare / OSF.
3. Search the web for the dataset by name to find the canonical download location.

Classify each metric:
- **Reproducible** — dataset and split are publicly available
- **Partial** — dataset available but exact split or random seed is unknown (results may differ
  slightly from the paper)
- **Not reproducible** — proprietary dataset or no public download found

Never silently skip a metric. Present the full classification table and ask:

> "Here is my assessment of what can be reproduced. I will proceed with Reproducible and Partial
> items. Confirm, or remove any you'd like to skip."

If **nothing** is reproducible, say so clearly and stop — do not invent datasets.

---

### Phase A3 — Dataset Acquisition

For each selected metric, download the dataset. Search the web for the canonical source if not
already identified in Phase A2.

For each dataset:
1. Download it and extract SMILES + ground-truth labels for the **test split**.
2. Validate: count rows, count valid SMILES, check label distribution (class balance for
   classification, value range for regression).
3. Show the user a 5-row preview and the total count, then ask:

   > "This is the test set I will use for [metric] on [dataset] (N molecules). Proceed?"

If the dataset cannot be downloaded automatically, tell the user explicitly:

> "I could not automatically retrieve the [dataset name] dataset. Please provide the test set as
> a CSV with columns `smiles` and `<label_column>`, or skip this metric."

**Fallback — eosbench:** When a dataset overlaps with eosbench's catalog (ames, herg, hia_hou,
dili, bbb_martins, clintox, cyp* variants, bioavailability_ma, carcinogens_lagunin,
pgp_broccatelli, skin_reaction, chembl4649948, chembl4659961), eosbench can supply SMILES +
labels even when no official split is available. Before proceeding, inform the user:

> "The [dataset] is available via eosbench, but eosbench uses arbitrary CV splits that differ
> from the paper's protocol. I can run the model on an eosbench fold and give you an indicative
> result, but the status will be capped at **APPROXIMATE†** regardless of how close the numbers
> are. Proceed?"

Only proceed if the user confirms. Install and use eosbench:

```bash
pip install git+https://github.com/ersilia-os/eosbench.git
```

```python
from eosbench import load_dataset
import pandas as pd

dataset = load_dataset("tdc", "ames", featurization=None)
train_idx, test_idx = dataset.split[0]
df = pd.DataFrame({
    "smiles": [dataset.X[i] for i in test_idx],
    "label": dataset.y[test_idx]
})
df.to_csv("/tmp/<model_id>_eosbench_<dataset>.csv", index=False)
```

Track internally that eosbench was used for this metric — you will need this in Phase A6.

If N > 1000 molecules, warn the user and offer to sample (suggest n = 500 for speed):

> "This dataset has N molecules — running the model will take several minutes. Proceed with the
> full set, or shall I sample 500 molecules?"

---

### Phase A4 — Run the Model

For each acquired dataset:

1. Write `/tmp/<model_id>_reproduce_input.csv` (single `smiles` column, N rows).

2. Run the model from the template repository:
   ```bash
   bash model/framework/run.sh model/framework \
       /tmp/<model_id>_reproduce_input.csv \
       /tmp/<model_id>_reproduce_output.csv
   ```

3. On failure: report the error clearly and mark the metric as "Run failed — not reproducible".
   Do not retry automatically.

4. If the model has multiple output columns and it is unclear which one corresponds to the
   reported metric, ask the user:
   > "The model outputs columns: [list]. Which column should I compare against the reported
   > [metric name]?"

**Non-deterministic models**: if the model shows stochastic behaviour (e.g. dropout at
inference), run it 3 times and report mean ± std. Compare the mean against the reported value.

---

### Phase A5 — Compute and Compare Metrics

Use `scripts/compute_metrics.py` (bundled with this skill):

```bash
python <skill_scripts_path>/compute_metrics.py \
    --predictions /tmp/<model_id>_reproduce_output.csv --pred-col <column> \
    --labels <labels_file>.csv --label-col <label_column> \
    --metric <metric>
```

Supported metric names: `auc-roc`, `auc-prc`, `accuracy`, `mcc`, `f1`, `rmse`, `mae`, `r2`.

**Tolerance definitions** (always show in the final report):

| Metric type | Tolerance | 2× tolerance |
|---|---|---|
| AUC-ROC, AUC-PRC | ±0.03 absolute | ±0.06 |
| Accuracy, MCC, F1 | ±0.03 absolute | ±0.06 |
| RMSE, MAE | ±10% relative | ±20% relative |
| R² | ±0.05 absolute | ±0.10 |

**Status per metric:**
- **REPRODUCED** — within tolerance
- **APPROXIMATE** — within 2× tolerance (expected from environment / dependency drift)
- **DIVERGENT** — beyond 2× tolerance (something materially differs — worth investigating)
- **NOT REPRODUCIBLE** — dataset unavailable, run failed, or split unrecoverable

---

### Phase A6 — Summary Report

```
Overall verdict: PASS / PARTIAL / FAIL

Equivalence check (raw output): EQUIVALENT (Spearman r = 0.9997, MAD = 0.0002)
  ← or: APPROXIMATE / DIVERGENT / SKIPPED

Metric   | Dataset | Reported | Reproduced | Delta   | Status
---------|---------|----------|------------|---------|-------
AUC-ROC  | BACE    | 0.867    | 0.854      | −0.013  | REPRODUCED
RMSE     | ESOL    | 0.58     | 0.63       | +0.050  | APPROXIMATE
AUC-ROC  | ames    | 0.901    | 0.887      | −0.014  | APPROXIMATE†
Accuracy | HIV     | 0.976    | 0.891      | −0.085  | DIVERGENT
AUC-ROC  | Tox21   | 0.849    | —          | —       | NOT REPRODUCIBLE

† eosbench split used — not the paper's original split; result is indicative only
```

If any metric used eosbench, always include the `†` marker and footnote — even if the status
would otherwise be REPRODUCED. The cap is unconditional.

For each **DIVERGENT** metric, add a short note on likely causes:
- Different train/test split or scaffold vs random split
- Different random seed or non-deterministic model
- Different SMILES standardisation (RDKit version, sanitisation settings)
- Different dependency version (RDKit, PyTorch, scikit-learn)
- Reported value is averaged over CV folds, not a single test set

**Overall verdict:**
- **PASS** — all attempted metrics are REPRODUCED or APPROXIMATE
- **PARTIAL** — mixed results (some DIVERGENT)
- **FAIL** — majority DIVERGENT or most metrics NOT REPRODUCIBLE

---

## Branch R — Representation Workflow

### Phase R1 — Find Reference Implementation

Check in this order:
1. `<template>/metadata.yml`: look for a `GitHub`, `Source`, or `BibTeX` field with a repo URL.
2. The paper PDF: search for "Code availability", "Software availability", or any GitHub/GitLab URL.
3. `<template>/README.md`: look for a "Source code" or "Original implementation" link.

If found: attempt to clone and install.

If **not found or not installable**: ask the user:

> "I could not find or run the original implementation. How would you like to proceed?
> (a) Skip the equivalence check and go straight to optional downstream analyses
> (b) Run a determinism check — I'll run the Ersilia wrapper twice on the same molecules and
>     verify the outputs are identical
> (c) I'll provide a reference embedding file myself — it should be a CSV with a `smiles` column
>     and one column per embedding dimension"

Proceed according to the user's choice.

---

### Phase R2 — Output Equivalence Check

*Skip this phase if the user chose option (a) in Phase R1.*

**If reference implementation is available or user provided reference embeddings:**

1. Write the 20 test molecules from `references/test_molecules.csv` to
   `/tmp/<model_id>_eq_input.csv`.
2. Run through the original code → `/tmp/<model_id>_reference_embeddings.csv`
   (one row per molecule, one column per embedding dimension, plus a `smiles` column).
   Ask the user for the exact run command if not obvious from the repo's README.
3. Run the same molecules through the Ersilia wrapper:
   ```bash
   bash model/framework/run.sh model/framework \
       /tmp/<model_id>_eq_input.csv \
       /tmp/<model_id>_ersilia_embeddings.csv
   ```
4. Run the similarity script:
   ```bash
   python <skill_scripts_path>/compute_embeddings_similarity.py \
       --reference /tmp/<model_id>_reference_embeddings.csv \
       --ersilia /tmp/<model_id>_ersilia_embeddings.csv \
       --smiles-col smiles
   ```
5. Report the verdict:
   - **EQUIVALENT** — mean cosine similarity ≥ 0.999
   - **APPROXIMATE** — 0.990–0.999
   - **DIVERGENT** — < 0.990 (flag loudly — the wrapper is likely broken)

**If determinism check was chosen (option b):**

Run the Ersilia wrapper twice on the same 20 molecules. Compare both output CSVs column-by-column.
If any value differs beyond floating-point epsilon (1e-6), report **DIVERGENT** and note which
molecules and columns differ.

---

### Phase R3 — Optional Downstream Analyses

Always offer these after Phase R2, even if the equivalence check was skipped. Ask the user before
running each one:

> "Would you like me to run [analysis]? This validates that chemical information is preserved in
> the embeddings. (optional)"

**PCA**
- Run 200 molecules through the Ersilia wrapper. Use the 20 test molecules plus additional
  molecules from ESOL (download: `https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/delaney-processed.csv`)
  to reach 200 if needed.
- Fit `sklearn.decomposition.PCA(n_components=2)`.
- Report: variance explained by PC1 and PC2.
- Flag if PC1 explains < 5% variance (possible degenerate output).

**Clustering**
- K-means (k=5) on the 200-molecule embeddings.
- Report silhouette score. Score > 0.2 indicates meaningful structure.
- Report the SMILES of the molecule nearest to each cluster centroid.

**QSAR**
- Use the 200-molecule embeddings as features; compute RDKit `Descriptors.MolLogP` as labels.
- Train a ridge regression with 80/20 split. Report R² on the holdout.
- R² > 0.5 suggests the embeddings capture physicochemical information.

---

### Phase R4 — Summary Report

```
Overall verdict: PASS / PARTIAL / FAIL / NOT REPRODUCIBLE

Model type:         Representation
Equivalence check:  EQUIVALENT
  mean cosine sim:  0.9997
  min cosine sim:   0.9981
  std:              0.0008
  count < 0.999:    3 / 20
  ← or: APPROXIMATE / DIVERGENT / SKIPPED (reason) / DETERMINISM — identical / DIVERGENT

Downstream analyses:
  PCA (n=200):      PC1=32.4%, PC2=18.1% — DONE / SKIPPED
  Clustering (k=5): silhouette=0.63 — DONE / SKIPPED
  QSAR (logP):      R²=0.81 — DONE / SKIPPED
```

**Overall verdict logic:**
- **PASS** — EQUIVALENT or APPROXIMATE equivalence
- **PARTIAL** — APPROXIMATE equivalence + at least one downstream check flagged a problem
- **FAIL** — DIVERGENT equivalence
- **NOT REPRODUCIBLE** — equivalence skipped and no downstream analyses run

---

## Branch S — Sampling Workflow

### Phase S1 — Extract from Paper

Read the paper PDF and extract:

| Field | What to record |
|---|---|
| validity | % valid SMILES reported |
| uniqueness | % unique among generated |
| novelty | % not in training set |
| N_generated | Number of molecules generated for evaluation |
| conditioning | None / seed SMILES / property target |
| property stats | Any reported mean/std of QED, SA score, MW, logP, etc. |

If N_generated is not stated: ask the user, suggesting N = 100.

---

### Phase S2 — Acquire Training Set

The training set is needed for novelty computation and distribution comparison.

1. Check `<template>/data/` and any subdirectories for a training set file.
2. Check `<template>/README.md` and `<template>/metadata.yml` for training data references or links.
3. Check the paper's "Data availability" section for a download link.
4. Search the web for the named training set if a name is mentioned in the paper.

If training set found: download or use it directly, extract the SMILES column.

If **not found**: tell the user and ask how to proceed:

> "I could not locate the training set used by this model. Without it I cannot compute novelty or
> compare distributions. Would you like to provide the training set path or URL, or shall I skip
> those checks and only report validity and uniqueness?"

Do not fall back to a generic dataset — only use the actual training data or skip.

---

### Phase S3 — Generate Molecules

1. **Determine input format:**
   - *Unconditional*: check the template's README for the expected input format; write a minimal
     dummy input CSV.
   - *Conditional (seed SMILES)*: ask the user for seed SMILES, or offer to use molecules from
     `references/test_molecules.csv` as seeds.
   - *Conditional (property target)*: ask the user what conditioning values to use.

2. Run the model:
   ```bash
   bash model/framework/run.sh model/framework \
       /tmp/<model_id>_sampling_input.csv \
       /tmp/<model_id>_generated.csv
   ```

3. Read the output. Report: N_generated (rows), N_valid (valid SMILES by RDKit), % valid.

4. If N_valid < 50:
   > "Only N_valid valid molecules were generated. Distribution metrics may be unreliable.
   > Proceed?"

---

### Phase S4 — Compute Generative Metrics

Run `scripts/compute_generative_metrics.py`:

```bash
python <skill_scripts_path>/compute_generative_metrics.py \
    --generated /tmp/<model_id>_generated.csv \
    --smiles-col <col> \
    [--training <training_set.csv> --training-smiles-col <col>]
```

Parse the JSON output. Then:

**Rate metrics** (validity, uniqueness, novelty):
If the paper reports these: compare against paper values using ±0.03 absolute tolerance.
Status: REPRODUCED / APPROXIMATE / DIVERGENT / NOT REPRODUCIBLE.

**Property distributions** (QED, SA score, MW, logP, HBD, HBA, TPSA):
For each property: show mean ± std for (a) generated molecules and (b) training set.
Run a KS test (`scipy.stats.ks_2samp`). Flag with "⚠ KS p<0.05" if distributions differ
significantly — this means generated molecules have a different property profile from training.

If SA score is unavailable (sascorer not found), note: "SA Score: not computed — sascorer not
found; install from RDKit Contrib (`$RDBASE/Contrib/SA_Score/sascorer.py`) to enable."

---

### Phase S5 — Summary Report

```
Overall verdict: PASS / PARTIAL / FAIL / NOT REPRODUCIBLE

Model type:  Sampling
Generated:   N=1000 | Valid: 987 (98.7%) | Unique: 951 (95.1%) | Novel: 743 (74.3%)

Rate metrics:
Metric       | Generated   | Paper       | Delta   | Status
-------------|-------------|-------------|---------|----------
Validity     | 98.7%       | 98.0%       | +0.7%   | REPRODUCED
Uniqueness   | 95.1%       | 95.0%       | +0.1%   | REPRODUCED
Novelty      | 74.3%       | —           | —       | NOT REPRODUCIBLE (no training set)

Property distributions  (reference: training set):
Property   | Generated       | Training set    | KS p-value
-----------|-----------------|-----------------|-------------
QED        | 0.61 ± 0.14     | 0.58 ± 0.15     | 0.31
logP       | 2.8 ± 1.2       | 2.9 ± 1.3       | 0.44
SA Score   | 2.4 ± 0.6       | 2.5 ± 0.7       | 0.21
MW         | 312 ± 68        | 298 ± 72        | 0.08
HBD        | 1.4 ± 0.9       | 1.3 ± 0.8       | 0.62
HBA        | 4.2 ± 1.6       | 4.0 ± 1.5       | 0.55
TPSA       | 72 ± 28         | 70 ± 26         | 0.49
```

**Overall verdict logic:**
- **PASS** — all attempted rate metrics are REPRODUCED or APPROXIMATE, and no property KS p < 0.05
- **PARTIAL** — mixed rate metrics, or some properties flagged (KS p < 0.05)
- **FAIL** — majority of rate metrics DIVERGENT, or most properties significantly differ
- **NOT REPRODUCIBLE** — model failed to generate valid molecules, or no metrics available to compare

---

## Reference Files

- `references/test_molecules.csv` — 20 diverse drug-like molecules for equivalence checks
- `scripts/compute_metrics.py` — annotation metric computation
- `scripts/compute_embeddings_similarity.py` — cosine similarity for representation models
- `scripts/compute_generative_metrics.py` — generative metrics and property distributions

---

## Next steps

> **Remaining step:**
> 1. Push and open a pull request from your fork to `ersilia-os/eosXXXX`
