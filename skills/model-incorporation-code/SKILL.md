---
name: model-incorporation-code
description: >
  Integrate the code of a new ML model into an Ersilia model template repository.
  Use this skill whenever the user has: (1) a source model repository with the
  original ML code, (2) an ersilia-model-template repository (already forked/cloned),
  and (3) optionally a PDF of the scientific article — and needs to wire up the
  actual model code. The skill handles all coding steps: copying checkpoints with
  git-lfs tracking, adapting main.py to replace the molecular-weight placeholder with
  real inference, creating run_columns.csv, updating install.yml with pinned versions,
  and producing run_input.csv and run_output.csv by actually running the model.
  Trigger on phrases like "incorporate model code", "fill in the template", "adapt
  main.py", "add checkpoints", "create run_columns", "create install.yml for ersilia",
  "generate example files for ersilia model", or any request to wire a source model
  into the eos-template format.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch, AskUserQuestion]
---

# Model Incorporation – Code Phase

You integrate a published computational model into an Ersilia model template by
reading the source code, understanding the inference pipeline, and producing all
the required files. Ersilia supports three model types:

- **Annotation** — predicts properties or activities for a molecule (e.g. toxicity probability, pKa, ADMET endpoints).
- **Representation** — generates a molecular descriptor, fingerprint, or embedding (e.g. Morgan fingerprints, graph embeddings).
- **Sampling** — generates new molecules given a seed molecule (e.g. analogues, optimised compounds).

See `references/template-structure.md` for detailed specs on each file, and
`references/main-py-patterns.md` for annotated main.py examples by model type.

## Parse Arguments

- `--template <template-repo-path>` (required): local path to the cloned ersilia-model-template fork
- `--source <source-model-repo-path>` (required): local path to the cloned source model repository
- `--paper <pdf-path>` (optional): path to the PDF of the scientific article

If arguments are missing, ask the user to provide them before proceeding.

---

## Phase 1 – Read and Understand

Read everything before touching a file. The goal is to build a complete mental model
of what the source model does and how to run it.

### 1a. Read the PDF (if provided)
Extract:
- What the model predicts / outputs (property name, units, range)
- Model type: annotation, representation, or sampling
- Model architecture (neural net, random forest, SMILES transformer, cheminformatics method…)
- Performance metrics (AUROC, RMSE, etc.) — useful for the run_columns description

### 1b. Read the source model repository

This is the most important phase. A thorough understanding of the source code is the
foundation for everything that follows — shortcuts here cause every subsequent step
to go wrong.

Systematically explore:
1. `README.md` — usage instructions, CLI entry point, example commands
2. `requirements.txt` / `setup.py` / `pyproject.toml` / `environment.yml` — dependencies
3. Main inference script(s) — find the function/class that takes a molecule as input
   and returns a prediction. Look for argparse, `predict()`, `__call__()`, `forward()`
4. Checkpoint files — note their names, sizes, and formats (`.pt`, `.pkl`, `.h5`, `.joblib`, `.ckpt`)
5. Any preprocessing steps (tokenisation, featurisation, normalisation)

Ask the user whenever something is ambiguous or unclear — better to clarify early
than to make wrong assumptions that affect the whole integration.

### 1c. Read the template repository
Open the template's `model/framework/code/main.py` to see the placeholder structure.
Also read `install.yml`, `.gitattributes`, and `model/framework/run.sh` so you understand
the wiring before writing anything.

---

## Phase 2 – Handle Checkpoints

1. Identify all checkpoint / weight files from the source model repo.
2. Copy them into `<template-repo-path>/model/checkpoints/`. If they are not in the repo
   but linked externally (Zenodo, Figshare, HuggingFace, Google Drive, direct URL),
   download them using `wget`, `curl`, or the appropriate Python client
   (e.g. `huggingface_hub`, `gdown`).
3. For each checkpoint file **≥ 100 MB**, ask the user how they want to store it:
   - **Git LFS** — file stays in the repository, tracked via Git LFS.
   - **eosvc** — file is hosted externally on the Ersilia volume cloud storage; do not
     commit it to the repository.

   Wait for the user's answer before proceeding. If the user chooses **Git LFS**:
   - Run `git lfs install` once if not already done.
   - Add a tracking line to `.gitattributes` (e.g. `*.pt filter=lfs diff=lfs merge=lfs -text`).
   - Run `git lfs track "<pattern>"` or manually add the entry.
   - Stage `.gitattributes` with `git add .gitattributes`.

   If the user chooses **eosvc**, do not add the file to git at all — note that it will
   be fetched at runtime from eosvc and document this in the code comments of `main.py`.

4. If no checkpoints are needed (pure algorithmic model), note this explicitly and
   leave the directory empty.
5. **Cleanup — always run these two commands regardless of which storage option was chosen:**
   ```bash
   rm -f <template-repo-path>/mock.txt
   ```
   Then, if **no files are tracked by Git LFS** (either no large checkpoints, or all
   large checkpoints are stored on eosvc), also delete:
   ```bash
   rm -f <template-repo-path>/.gitattributes
   ```
   Keep `.gitattributes` only when at least one file is actually tracked by Git LFS.

---

## Phase 3 – Adapt main.py

Open `<template-repo-path>/model/framework/code/main.py`. Replace the `my_model`
placeholder function (which calculates molecular weight) with a function that:

1. Loads the model/checkpoints from the relative path
   `../../checkpoints/` (relative to the script location — do NOT use absolute paths).
2. Accepts a list of SMILES strings.
3. Returns a list of predictions in the same order.

All new models must use `ersilia_pack_utils` for CSV I/O — do not use manual
`csv.reader` / `csv.writer`. The standard pattern is:

```python
from ersilia_pack_utils.core import read_smiles, write_out
_, smiles_list = read_smiles(input_file)
# ... run inference ...
write_out(outputs, headers, output_file, np.float32)
```

Copy any additional helper `.py` files from the source model that are needed (e.g.
preprocessing utilities, model class definitions) into
`<template-repo-path>/model/framework/code/`.

See `references/main-py-patterns.md` for annotated patterns organised by model type.

**Important checks before finishing main.py:**
- Test that `main.py` runs without errors on a single SMILES first.
- Confirm outputs are in the correct order (same order as input SMILES).
- Handle invalid / unparseable SMILES gracefully (return `None` or a sentinel value).

---

## Phase 4 – Create run_columns.csv

Create `<template-repo-path>/model/framework/columns/run_columns.csv`.

Write it with Python or a plain text editor without BOM encoding. The file must have exactly these four columns (no extras):

```
name,type,direction,description
```

Rules (details in `references/template-structure.md`):
- **name**: lowercase, underscores only (no spaces, no hyphens). Generative outputs:
  `smi_` + zero-padded index (padding width = digit count of the maximum index, i.e.
  total count − 1; e.g. `smi_00` for 100 outputs since max index = 99 has 2 digits,
  `smi_000` for 1000 outputs since max index = 999 has 3 digits); representation/featurisation
  outputs: `feat_` + zero-padded index using the same padding rule (e.g. `feat_00` for
  100 dims, `feat_000` for 512 dims, `feat_0000` for 2048 dims); single-value predictors: a meaningful name like
  `logp` or `activity_score`. Note: many older Ersilia models use `dim_` instead of
  `feat_` — that is historical; all new incorporations must use `feat_`.
- **type**: `float`, `integer`, or `string` — nothing else.
- **direction**: `high` or `low` — the direction of biological activity. `high`
  means higher output values correspond to more of the modelled property (e.g. a
  higher probability score means the molecule is more likely to have that activity).
  `low` means lower values correspond to more of the property (e.g. hydration free
  energy in kcal/mol, where more negative = more solvated). Leave **empty** (not
  the word "none") for sampling models and for representation models with abstract
  latent dimensions (e.g. neural embeddings like UniMol) where individual dimensions
  have no interpretable direction. For fingerprint-based representations (e.g. Morgan
  counts), use `high` since a higher value means more of that structural feature is
  present.
- **description**: one plain-English sentence, no commas.

Examples from real Ersilia models:

**eos3b5e — annotation, single output:**
```
name,type,direction,description
mol_weight,float,high,The calculated molecular weight of the molecule in g/mol
```

**eos7ike — annotation, multi-output:**
```
name,type,direction,description
rb,integer,high,Low flexibility (rotatable bonds lower or equal than 5)
glob,integer,high,Low globularity (lower or equal than 0.25)
primary_amine,integer,high,Determines if a molecule has a primary amine
```

**eos5axz — representation (first 2 of 2048 dims shown):**
```
name,type,direction,description
dim_0000,integer,high,Morgan count fingerprint dimension 0 with radius 3 and 2048 bits
dim_0001,integer,high,Morgan count fingerprint dimension 1 with radius 3 and 2048 bits
```

**eos2hzy — sampling (first 2 of 100 shown):**
```
name,type,direction,description
smiles_00,string,,Compound index 0 queried with the PubChem API
smiles_01,string,,Compound index 1 queried with the PubChem API
```

**eos6ost — sampling (first 2 of 1000 shown):**
```
name,type,direction,description
smi_000,string,,Generated compound index 0 using pre-trained LibInvent model
smi_001,string,,Generated compound index 1 using pre-trained LibInvent model
```

---

## Phase 5 – Update install.yml

Open `<template-repo-path>/install.yml` and replace the placeholder entries with the
actual dependencies.

Format:
```yaml
python: "3.10"   # match what the source model was tested on; minimum 3.8

commands:
  - ["pip", "torch", "2.0.1"]
  - ["conda", "rdkit", "2023.09.1", "conda-forge"]
  - ["pip", "git+https://github.com/org/repo.git@v1.2.3"]
  - "some-shell-command --if-needed"
```

Rules:
- Pin every version. Check the source model's requirements file for exact versions;
  if a range is given, use the upper bound or the version the model was tested on.
- Use `conda` entries for packages best installed via conda (e.g. `rdkit`, `cudatoolkit`).
- Use `pip` entries for PyPI packages.
- Use a git URL entry for packages not on PyPI.
- Use a plain string for arbitrary shell commands (e.g. `pip install -e .`).

See `references/template-structure.md` for more examples.

---

## Phase 6 – Create Example Files

### run_input.csv
Create `<template-repo-path>/model/framework/examples/run_input.csv` with exactly
three SMILES strings. Ersilia models always take SMILES as input.

Fetch 3 random SMILES from the Ersilia maintained inputs file:

```bash
python - <<'EOF'
import urllib.request, csv, random
url = "https://raw.githubusercontent.com/ersilia-os/ersilia-model-hub-maintained-inputs/main/inputs/example.csv"
with urllib.request.urlopen(url) as f:
    rows = list(csv.DictReader(line.decode() for line in f))
sample = random.sample(rows, 3)
print("smiles")
for r in sample:
    print(r["input"])
EOF
```

Write the output to `run_input.csv`.

### run_output.csv
To produce `run_output.csv`, actually run the model:

1. Create and activate an isolated conda environment (do NOT pollute the base env):
   ```bash
   conda create -n eos-test python=<version-from-install.yml> -y
   conda activate eos-test
   ```
2. Install all dependencies listed in `install.yml` in the order they appear.
3. Run the model via `run.sh` (NOT by calling main.py directly) from the template repo root:
   ```bash
   bash model/framework/run.sh model/framework \
     model/framework/examples/run_input.csv \
     /tmp/run_output.csv
   ```
4. Inspect the output — verify row count (3), column names match run_columns.csv,
   and values are in the expected range.
5. Copy the output to `<template-repo-path>/model/framework/examples/run_output.csv`.

If the model fails, debug the environment (missing package, wrong path, CUDA issue)
before writing the file. DO NOT FABRICATE OUTPUT VALUES.

---

## Final Checklist

Before declaring the work done, verify:

- [ ] `model/checkpoints/` contains all required files; large files (≥ 100 MB) stored via Git LFS or eosvc per user choice
- [ ] `mock.txt` deleted from the template root in all cases
- [ ] If any file is tracked by Git LFS: `.gitattributes` updated and staged
- [ ] If no files are tracked by Git LFS: `.gitattributes` deleted from the template root
- [ ] `model/framework/code/main.py` runs end-to-end without errors
- [ ] `model/framework/columns/run_columns.csv` has correct headers and follows naming rules
- [ ] `install.yml` has all dependencies pinned to exact versions
- [ ] `model/framework/examples/run_input.csv` has 3 SMILES rows
- [ ] `model/framework/examples/run_output.csv` was produced by actually running the model
- [ ] No hardcoded absolute paths anywhere in the code
- [ ] `metadata.yml` is consistent with the files produced: model type (Task field)
  matches the outputs and output column names match what is declared
