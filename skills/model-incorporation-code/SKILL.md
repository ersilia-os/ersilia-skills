---
name: model-incorporation-code
description: >
  Integrate the code of a new ML model into an Ersilia model template repository.
  Use this skill whenever the user has: (1) a source model repository with the
  original ML code, (2) an ersilia-model-template repository (already forked/cloned),
  and (3) optionally a PDF of the scientific article — and needs to wire up the
  actual model code. The skill handles all coding steps: copying checkpoints into
  the repo (eosvc only for a folder with a file of 100 MiB or more; fit/ to eosvc once it holds training code or data), adapting main.py (its load_tool() and run_tool() functions) to
  replace the molecular-weight placeholder with real inference, creating run_columns.csv, updating install.yml with pinned versions,
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
Open the template's `model/framework/code/main.py` to see its two functions, `load_tool()` and `run_tool()`, and the placeholder they wrap.
Also read `install.yml`, `.gitattributes` (if present), and `model/framework/run.sh` so you understand
the wiring before writing anything.

---

## Phase 2 – Handle Checkpoints

### Step 1 — Detect whether checkpoints exist

Search the source repo for checkpoint / weight files. Look for files with these extensions:
`.pt`, `.pth`, `.ckpt`, `.pkl`, `.joblib`, `.h5`, `.hdf5`, `.bin`, `.npy`, `.npz`,
`.safetensors`, `.weights`. Also check for external links (Zenodo, Figshare, HuggingFace,
Google Drive, direct URL) in the README.

**If checkpoints are found** → proceed to Step 2 (normal flow).

**If no checkpoints are found** → proceed to the [Missing checkpoints](#missing-checkpoints) branch below, then return here to continue once the checkpoint is in place.

### Step 2 — Copy / download checkpoints (normal flow)

1. Copy checkpoint files into `<template-repo-path>/model/checkpoints/`. If they are linked
   externally, download them now using `wget`, `curl`, or the appropriate Python client
   (e.g. `huggingface_hub`, `gdown`), and pin the exact version (e.g. a Hugging Face
   revision). The model must never download weights at run time: `load_tool()` in `main.py` loads them from
   `model/checkpoints/` (for Hugging Face, `local_files_only=True`). Weights never live in
   `model/framework/code/`; update the paths in the copied code instead.
2. Store them following the Ersilia storage rule ([Checkpoints and storage](https://ersilia.gitbook.io/ersilia-book/ersilia-model-hub/model-contribution/model-template#checkpoints-and-storage)).
   Do not ask how to store them, and never offer Git LFS.
   - `model/checkpoints/` goes to git if every file is under 100 MiB (104,857,600 bytes,
     GitHub's limit). Check from the model repo root:
     ```bash
     find model/checkpoints -type f -size +104857599c
     ```
     **No output** (the usual case): the folder is committed with the rest of the model.
     **A file is listed**: the whole folder goes to eosvc, never part of it.
   - `model/framework/fit/` always goes to eosvc when it holds anything beyond the template
     skeleton (`README.md` and the `.gitkeep` files), whatever its size.
   - For each folder on eosvc: add it to `.gitignore` under a `#eosvc managed` block
     (`model/checkpoints/*`, `model/framework/fit/*`), name it in `access.json` (e.g.
     `{"checkpoints": "public", "fit": "public"}`), and upload only that folder (requires the
     `eosvc` conda environment and AWS credentials configured in `.env` or `.config`):
     ```bash
     conda run -n eosvc eosvc upload --path checkpoints    # or --path fit
     ```
     Never `--path .`: it uploads both folders, and a folder kept in both git and S3 has its
     git copy overwritten by the S3 one in CI.
     Leaving a folder out of `access.json` does not protect it: eosvc treats a missing key as
     public, and CI runs `eosvc download --path .` whenever `access.json` exists.
   - If `.gitignore` or `access.json` list a folder that now goes to git (forks made before
     the rule changed), remove it from both, and delete `access.json` if no folder is left in
     it. If that folder still has a copy on S3 (`conda run -n eosvc eosvc view --path
     model/checkpoints`), tell the user it must be removed from S3: while `access.json`
     exists, CI's `eosvc download --path .` would put the stale S3 copy over the git one.

3. If no checkpoints are needed (pure algorithmic model), note this explicitly and
   leave the directory empty.
4. **Cleanup — always run this:**
   ```bash
   rm -f <template-repo-path>/mock.txt <template-repo-path>/.gitattributes
   rm -rf <template-repo-path>/.eosvc
   ```
   The current template ships neither file, but repositories created from older versions
   may hold a `mock.txt` and a `.gitattributes` with Git LFS rules only; Ersilia models do not
   use Git LFS. `.eosvc/` is a lock file that any eosvc command leaves
   in the repository root; it is not gitignored, so it would show up as untracked.

---

### Missing checkpoints

Only enter this branch if Step 1 found no checkpoints. Search the source repo and paper for:
- Training scripts (files named `train.py`, `fit.py`, `train_model.py`, or similar; scripts containing `model.fit(`, `trainer.train(`, or `train(` calls)
- Dataset download scripts or links to publicly available training data (supplementary materials, Zenodo/Figshare DOIs, S3 links)
- A README section describing how to reproduce training (hyperparameters, data sources)

**Outcome A — Training code and data both available**

The template already contains `model/framework/fit/` with three subdirectories: `src/` for
training code, `data/` for training data, and `results/` for output checkpoints.

1. Copy the training script(s) into `model/framework/fit/src/`.
2. If a data download script exists in the source repo, copy it into `model/framework/fit/data/`.
3. Write `model/framework/fit/README.md` with:
   - Data source and exact download instructions
   - Exact training command and hyperparameters (from paper / source repo)
   - Expected output file(s) — note they should be saved to `model/framework/fit/results/`
   - Instructions to copy the final checkpoint from `results/` to `model/checkpoints/`
   - Estimated training time / hardware requirements if mentioned in the paper
4. Tell the user:
   > "No pre-trained checkpoints are available. I've populated `model/framework/fit/` with
   > the training code and instructions. Run the training as described in
   > `model/framework/fit/README.md`, copy the output checkpoint to `model/checkpoints/`,
   > then let me know and I'll continue."
5. **Pause here.** When the user confirms the checkpoint is in `model/checkpoints/`, return to Step 2 above.

**Outcome B — Training code available but data is not public**

1. Copy the training scripts into `model/framework/fit/src/`.
2. Write `model/framework/fit/README.md` documenting the situation.
3. Tell the user:
   > "No checkpoints found. Training code is in `model/framework/fit/src/`, but the training
   > dataset is not publicly accessible. Options: (1) contact the original authors for the
   > dataset, (2) check whether a public proxy dataset could be used for retraining,
   > (3) skip this model for now."
4. **Stop** — do not proceed to Phase 3 until the user resolves the data access issue.

**Outcome C — No checkpoints and no training code found**

Tell the user openly and stop:
> "No pre-trained checkpoints were found, and I could not locate training code or public
> training data in the source repository. This model cannot be incorporated without further
> investigation. Suggested next steps: (1) check the paper's supplementary materials for a
> data/code deposit link, (2) contact the original authors to request the checkpoint,
> (3) check HuggingFace or Zenodo for a related pre-trained model."

Do not create any files. Do not proceed to Phase 3.

---

## Phase 3 – Adapt main.py

Open `<template-repo-path>/model/framework/code/main.py`. The template splits it into two
top-level functions, so that Ersilia can serve the model warm (loaded once and kept in memory
between batches):

- **`load_tool()`** does everything slow and independent of the batch: heavy imports, reading
  the checkpoints from `model/checkpoints/`, building the model. It returns the loaded model.
  In the template it returns the molecular-weight placeholder `MolWt`.
- **`run_tool(model, input_file, output_file)`** processes one batch: `read_smiles`, predict,
  `write_out`. It must not reload anything and must not depend on state left over from an
  earlier batch.

Replace the placeholder (the `MolWt` import, the body of `load_tool()`, and the prediction and
header in `run_tool()`) and keep the rest of the template, including the `__main__` block:

```python
if __name__ == "__main__":
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    run_tool(load_tool(), input_file, output_file)
```

`run.sh`, `ersilia test` and CI still run `main.py` as a script, so the model must work both
ways. `run.sh` passes only the input and output paths, so there is no room for extra
command-line arguments or flags.

Rules (the reasons are in `references/main-py-patterns.md`, "How Ersilia calls main.py"):

1. **Define both functions at the top level of `main.py` itself.** Warm serving parses
   `main.py` and looks for top-level `def load_tool` and `def run_tool`; importing them from a
   helper module is not enough.
2. **Do not edit `run.sh`.** Warm serving is used only when `run.sh` is the default single line
   `python $1/code/main.py $2 $3`. With any other `run.sh`, or when `load_tool()` fails, the
   model runs once per batch.
3. **No work at module level.** The warm worker imports `main.py` as a module called `main`,
   with `sys.argv` cut down to the script path and the `__main__` block skipped. Reading
   `sys.argv[1]`, reading the input or running inference at module level breaks that import.
   Constants and cheap imports are fine.
4. **`load_tool()` returns everything `run_tool()` needs**, as one object, a tuple or a dict
   (for example a network, its tokenizer and a scaler). Keep nothing between batches.
5. **Load the checkpoints in `load_tool()`**, from `model/checkpoints/`, with a path built from
   `os.path.dirname(os.path.abspath(__file__))` (`"..", "..", "checkpoints"`). Never use an
   absolute path and never download weights.
6. **Use `ersilia_pack_utils` for CSV I/O** — do not use manual `csv.reader` / `csv.writer`:

   ```python
   from ersilia_pack_utils.core import read_smiles, write_out
   _, smiles_list = read_smiles(input_file)
   # ... run inference ...
   write_out(outputs, header, output_file, np.float32)
   ```

   `read_smiles` returns `(header, smiles_list)` and reads `.csv` and `.bin` inputs.
   `write_out` writes `.csv` outputs as they are and `.bin` outputs as `np.float32` or `np.int32`
   only (NaN and inf are clipped). The `header` must match the `name` column of
   `run_columns.csv` exactly (Phase 4).
7. **Keep `main.py` minimal.** Logic beyond a few lines — model class definitions,
   preprocessing, postprocessing, custom tokenisation — belongs in dedicated helper modules
   (e.g. `predict.py`, `preprocess.py`) in `model/framework/code/`, imported by `main.py` and
   called from the two functions. Create these helper files yourself when needed; do not wait for
   them to exist in the source model, and copy any helper `.py` files from the source model that
   are needed into `<template-repo-path>/model/framework/code/`.

See `references/main-py-patterns.md` for annotated patterns organised by model type.

**Important checks before finishing main.py:**
- Test that `main.py` runs without errors on a single SMILES first.
- Confirm outputs are in the correct order (same order as input SMILES).
- Handle invalid / unparseable SMILES gracefully (return `None` or a sentinel value for that row).
- Confirm the loaded model can be reused: Phase 6 calls `run_tool()` twice on one loaded model.

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
  `logp` or `activity_score`.

  Prefer `feat_` and `smi_` for new incorporations — but these are **conventions, not
  enforced rules**, and the hub is genuinely split. Among existing featurizers `dim_`
  is the plurality (13 models against 10 using `feat_`, plus 7 `feature_` and 1
  `dimension_`), and `smi_` leads `smiles_` only 14 to 8. Nothing in the `ersilia`
  codebase checks any prefix, and no Ersilia documentation deprecates `dim_`. Do not
  "correct" an existing model's columns on the strength of this preference alone; see
  ersilia-os/ersilia#1901.
- **type**: `float`, `integer`, or `string` — nothing else.
- **direction**: `high` or `low` — whether a larger value means **more of the modelled
  property**. `high` means higher output values correspond to more of the property
  (e.g. a higher probability score means the molecule is more likely to have that
  activity). `low` means lower values correspond to more of the property (e.g.
  hydration free energy in kcal/mol, where more negative = more solvated). Leave
  **empty** (not the word "none") for sampling models and for representation models
  with abstract latent dimensions (e.g. neural embeddings like UniMol) where
  individual dimensions have no interpretable direction. For fingerprint-based
  representations (e.g. Morgan counts), use `high` since a higher value means more of
  that structural feature is present.

  **`direction` is magnitude, not desirability.** It says nothing about what is wanted
  in a drug candidate. A cardiotoxicity score is `high` because the number rises with
  cardiotoxicity, even though *less* cardiotoxicity is what you want. Two things push
  readers towards the wrong reading and should be ignored: the vocabulary file is named
  `desired_directions.txt`, and it offers `intermediate`, a value that only makes sense
  under a desirability reading and which no model in the hub uses.

  This was applied inconsistently across the hub before a 2026 sweep corrected 51
  models: hERG blockade was `high` in four models while cardiotoxicity and
  cytotoxicity were `low`, and synthetic accessibility was `high` in two models and
  `low` in a third. All of those describe rising property magnitude and should have
  agreed.
- **description**: one plain-English sentence, no commas.

The row count of this file is not free: **`Output Dimension` in `metadata.yml` must
equal the number of data rows here**, and `/model-incorporation-metadata` relies on it.
If you change the number of output columns, update the metadata to match.

Examples from real Ersilia models. These are shown **as they exist in the hub**, which is
why two of them use `dim_` and `smiles_` rather than the preferred `feat_` and `smi_` —
the preference is recent, the models are not:

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
  - ["pip", "torch", "2.0.1+cpu", "--index-url", "https://download.pytorch.org/whl/cpu"]
  - ["conda", "rdkit", "2023.09.1", "conda-forge"]
  - ["pip", "git+https://github.com/org/repo.git@v1.2.3"]
  - "some-shell-command --if-needed"
```

Rules:
- Pin every version. Check the source model's requirements file for exact versions;
  if a range is given, use the upper bound or the version the model was tested on.
- **CPU-only packages**: Ersilia models run on CPU. Always install CPU-only builds of
  GPU packages — never include CUDA, GPU, or `cudatoolkit` entries:
  - PyTorch: use the `+cpu` suffix and the CPU wheel index:
    `["pip", "torch", "2.0.1+cpu", "--index-url", "https://download.pytorch.org/whl/cpu"]`
  - TensorFlow: use `tensorflow-cpu` instead of `tensorflow`.
  - JAX: use `jax[cpu]` instead of `jax`.
  - Do not add any `cudatoolkit`, `cuda-toolkit`, or `nvidia-*` conda packages.
- Use `conda` entries for packages best installed via conda (e.g. `rdkit`, `openbabel`).
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
5. Check that one loaded model can be reused, the way warm serving calls it. From the same
   environment and repo root, call `run_tool()` twice on one `load_tool()` result:
   ```bash
   python - <<'EOF'
   import sys
   sys.path.insert(0, "model/framework/code")
   sys.argv = ["main.py"]
   import main
   model = main.load_tool()
   inp = "model/framework/examples/run_input.csv"
   main.run_tool(model, inp, "/tmp/run_output_1.csv")
   main.run_tool(model, inp, "/tmp/run_output_2.csv")
   EOF
   diff /tmp/run_output_1.csv /tmp/run_output_2.csv && echo identical
   ```
   Both runs must succeed and give the same output. A difference means something is kept
   between batches (or, for a model with `Variable` output consistency, that it is stochastic:
   then only check that both runs succeed and have 3 rows).
6. Copy the output of step 3 to `<template-repo-path>/model/framework/examples/run_output.csv`.

If the model fails, debug the environment (missing package, wrong path, CUDA issue)
before writing the file. DO NOT FABRICATE OUTPUT VALUES.

---

## Final Checklist

Before declaring the work done, verify:

- [ ] `model/checkpoints/` contains all required files, and `main.py` loads them from there (no downloads at run time). It is committed to git unless a file is 100 MiB or larger; then it is gitignored, named in `access.json` and uploaded with eosvc. A populated `model/framework/fit/` is always on eosvc
- [ ] `mock.txt`, `.gitattributes` and `.eosvc/` deleted from the template root
- [ ] `model/framework/code/main.py` defines top-level `load_tool()` and `run_tool(model, input_file, output_file)`, keeps the template's `__main__` block, does no work at module level, and runs end-to-end without errors; `run.sh` is unchanged (the default single line)
- [ ] `model/framework/columns/run_columns.csv` has correct headers and follows naming rules
- [ ] `install.yml` has all dependencies pinned to exact versions
- [ ] `model/framework/examples/run_input.csv` has 3 SMILES rows
- [ ] `model/framework/examples/run_output.csv` was produced by actually running the model
- [ ] No hardcoded absolute paths anywhere in the code
- [ ] `metadata.yml` is consistent with the files produced: model type (Task field)
  matches the outputs and output column names match what is declared

---

## Next steps

> **Remaining steps:**
> 1. Run `/ersilia-model-test` to validate the model runs correctly
> 2. Optional: run `/model-incorporation-reproduce` to verify the model performs as reported in the paper
> 3. Run `/model-incorporation-pr` to commit, push, open the pull request and, with your approval, merge it once every check is green
> 4. Run `/model-incorporation-release` to confirm CI is green, check the release, deposit the paper and close the request
