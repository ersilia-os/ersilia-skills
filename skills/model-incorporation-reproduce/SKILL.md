---
name: model-incorporation-reproduce
description: >
  Reproduce the key performance metrics reported in a paper for an Ersilia Model Hub model.
  Reads the publication PDF, extracts reported results (AUC, RMSE, accuracy, R², etc.),
  assesses whether each benchmark dataset is publicly available, acquires the datasets, runs
  the incorporated model, and compares reproduced vs reported metrics with tolerance-aware
  verdicts. Use this skill whenever a user wants to verify that an incorporated model performs
  as described in its paper, after running model-incorporation-code. Trigger on phrases like
  "reproduce the results", "check model performance", "validate the model against the paper",
  "does the model match what the paper reports", "benchmark the model", or any request to
  verify an incorporated Ersilia model against its publication.
allowed-tools: [Bash, Read, Write, WebFetch, WebSearch, AskUserQuestion]
---

# Model Incorporation — Reproduce

Your job is to verify that an incorporated Ersilia model performs as reported in its paper. You
do this by extracting performance metrics from the PDF, finding the benchmark datasets, running
the model, and comparing the results. The process is **guided** — you propose at each step and
wait for the user to confirm before proceeding.

## Parse Arguments

- `--template <path>` (required): local path to the incorporated model repository (eosXXXX)
- `--paper <path>` (required): local path to the publication PDF
- `--model-id <id>` (optional): model ID; inferred from the folder name if not given

If any required argument is missing, ask the user before proceeding. Infer `<model-id>` from
the last component of `--template` path if `--model-id` is omitted.

---

## Phase 1 — Extract Reported Performance Metrics

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

This step matters because you may have missed some metrics or misread a table. The user knows
the paper.

---

## Phase 2 — Assess Reproducibility

For each confirmed metric, investigate before attempting anything:

1. Check the source code repository (use `--template` repo's README and any `data/` folder) for
   dataset files, download scripts, or supplementary links.
2. Search the paper for a "Data availability" statement, supplementary tables, or DOI links to
   Zenodo / Figshare / OSF.
3. Check whether the dataset is a standard benchmark listed in
   `references/common-datasets.md`.

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

## Phase 3 — Dataset Acquisition

For each selected metric, attempt to download the dataset. See `references/common-datasets.md`
for exact download commands for standard benchmarks (ESOL, BACE, BBBP, HIV, Tox21, ChEMBL, etc.).

For each dataset:
1. Download it and extract SMILES + ground-truth labels for the **test split**.
2. Validate: count rows, count valid SMILES, check label distribution (class balance for
   classification, value range for regression).
3. Show the user a 5-row preview and the total count, then ask:

   > "This is the test set I will use for [metric] on [dataset] (N molecules). Proceed?"

If the dataset cannot be downloaded automatically, tell the user explicitly:

> "I could not automatically retrieve the [dataset name] dataset. Please provide the test set as
> a CSV with columns `smiles` and `<label_column>`, or skip this metric."

If N > 1000 molecules, warn the user and offer to sample (suggest n = 500 for speed):

> "This dataset has N molecules — running the model will take several minutes. Proceed with the
> full set, or shall I sample 500 molecules?"

---

## Phase 4 — Run the Model

For each acquired dataset:

1. Write `reproduce_input.csv` (single `smiles` column, N rows) to
   `/tmp/<model_id>_reproduce_input.csv`.

2. Run the model from the template repository:
   ```bash
   cd <template_path>
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

**Non-deterministic models**: if the model shows stochastic behaviour (e.g. generative sampling,
dropout at inference), run it 3 times and report mean ± std. Compare the mean against the
reported value.

---

## Phase 5 — Compute and Compare Metrics

Use `scripts/compute_metrics.py` (bundled with this skill). Run it from the skill's `scripts/`
directory:

```bash
python <skill_scripts_path>/compute_metrics.py \
    --predictions /tmp/<model_id>_reproduce_output.csv --pred-col <column> \
    --labels <labels_file>.csv --label-col <label_column> \
    --metric <metric>
```

Supported metric names: `auc-roc`, `auc-prc`, `accuracy`, `mcc`, `f1`, `rmse`, `mae`, `r2`.

**Tolerance definitions** (always show these in the final report so the user knows the thresholds):

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

## Phase 6 — Summary Report

Print the final table:

```
Metric   | Dataset | Reported | Reproduced | Delta   | Status
---------|---------|----------|------------|---------|-------
AUC-ROC  | BACE    | 0.867    | 0.854      | −0.013  | REPRODUCED
RMSE     | ESOL    | 0.58     | 0.63       | +0.050  | APPROXIMATE
Accuracy | HIV     | 0.976    | 0.891      | −0.085  | DIVERGENT
AUC-ROC  | Tox21   | 0.849    | —          | —       | NOT REPRODUCIBLE
```

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

The overall verdict goes at the top of the report, followed by the per-metric table.

---

## Reference Files

- `references/common-datasets.md` — download commands and column names for standard benchmarks
  (MoleculeNet, ChEMBL, BindingDB, ZINC, PubChem). Read this before attempting Phase 3.

- `scripts/compute_metrics.py` — standalone metric computation script. Run via `python
  <path>/compute_metrics.py --help` to see all options.
