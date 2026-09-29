# Ersilia Model Fix Patterns

Correct, idiomatic ways to *apply* the most common fixes. `ersilia-model-test`'s `troubleshooting.md` explains *why* a check fails; this file shows *what the corrected code/config should look like* so your edits match how working Ersilia models are actually written. Read the section for the fix you're applying.

---

## 1. Run failures (`simple_model_run: false`) — fix these first

A run failure cascades: when the model can't execute, consistency, output, and format checks all fail downstream. Fixing the run usually clears most of them at once.

### Import paths
`main.py` is called from the framework root, so package-relative imports break.

```python
# Broken
from ..utils import featurize
# Fixed — anchor to the code package
from code.utils import featurize
```

### Locating checkpoints and files
`run.sh` calls `python $1/code/main.py $2 $3`, so Python only receives `$2` (input CSV) and `$3` (output CSV). The framework dir is NOT in `sys.argv`. Anchor paths to `__file__`:

```python
import sys, os

input_file = sys.argv[1]   # input CSV
output_file = sys.argv[2]  # output CSV

root = os.path.dirname(os.path.abspath(__file__))          # the code/ dir
ckpt = os.path.join(root, "..", "..", "checkpoints", "model.pkl")
```

### Reading the input CSV
Input has a lowercase `smiles` header, one column:

```python
import csv
with open(input_file) as f:
    reader = csv.reader(f)
    next(reader)                       # skip header
    smiles_list = [row[0] for row in reader]
```

### Missing dependency
If the import works locally but not in the `ersilia` env, add the package to `install.yml` (see §4) rather than patching `main.py`.

---

## 2. Metadata fixes (`metadata.yml`)

- **Description too long**: the `Description` field must be ≤ 600 characters. Trim wording, keep the key facts — don't drop what the model does or what it predicts.
- **Field formats are case-sensitive**: `Local`, `Online`, `Fixed`, `Variable`, `Score`, `Value` must match exactly.
- **List-vs-string**: fields like `Deployment` and `Output` are YAML lists even with one item:
  ```yaml
  Deployment:
    - Local
  Output:
    - Value
  ```
- **Placeholder text**: replace leftover template values (e.g. `Biomedical Area 1`) with real content.
- **Leave `"not present"` fields alone**: `S3`, `DockerHub`, `Model Size`, `Incorporation Date`, etc. are auto-populated after merge. They are not failures to fix.

---

## 3. Column file fixes (`run_columns.csv`)

One row per output column, fields: `key`, `type`, `direction`, `description`.

- `key`: lowercase, underscore-separated (`pIC50_mpro`, `feat_00`)
- `type`: `Float`, `Integer`, or `String`
- `direction`: `high`, `low`, or `unknown`
- `description`: short human-readable label

**The keys must exactly match the column headers `main.py` writes to the output CSV.** When they diverge, prefer editing `run_columns.csv` to match the code's actual output — unless the diagnosis says the code's column names are themselves wrong, in which case fix `main.py`.

---

## 4. Dependency / install fixes (`install.yml`)

Commands use list-of-lists syntax with **pinned exact versions** (no ranges — reproducibility depends on it):

```yaml
python: "3.10"
commands:
  - ["pip", "rdkit", "2023.3.1"]
  - ["conda", "openjdk", "8.0.412", "conda-forge"]
```

- Not `pip install rdkit` as a string — always `["pip", "package", "version"]`.
- Some packages (e.g. `rdkit`) install more reliably via conda than pip; use the conda 4-element form with the channel.
- Legacy models using PaDEL-Descriptor need Java: add `["conda", "openjdk", "8.0.412", "conda-forge"]`.
- If a package needs a newer Python than declared, bump `python:` (check the package's PyPI compatibility first).

---

## 5. Consistency / output fixes

The consistency check requires: same input → same output across runs, CLI run == direct `bash run.sh`, and output columns matching `run_columns.csv`.

- **Stochastic output on a `Fixed` model**: set a random seed at the top of `main.py`; disable inference-time dropout; avoid timestamped/random temp filenames.
  ```python
  import random, numpy as np
  random.seed(42)
  np.random.seed(42)
  # torch: torch.manual_seed(42); model.eval()
  ```
- **Column mismatch**: reconcile `main.py` headers and `run_columns.csv` keys (see §3).
- **NaN / empty rows**: if specific example SMILES yield NaN or empty output, handle them gracefully in `main.py` (sentinel value or documented skip) so all 3 example molecules produce valid rows.

---

## 6. The lazyqsar rdkit/chemprop cycle (empty output, "works once")

Diagnosis and confirmation steps are in `ersilia-model-test`'s `troubleshooting.md` §6. Apply this fix when a model installs `lazyqsar[descriptors]==2.3.0` + `lazyqsar-setup` and `simple_model_run` fails with empty (`''`) actual values.

Pin chemprop to the last release that does not drag rdkit forward, and re-pin rdkit afterwards.

**Newer template (`install.yml`)**

```yaml
python: "3.12"
commands:
    - ["pip", "lazyqsar[descriptors]", "2.3.0"]
    - ["pip", "chemprop", "2.2.0"]
    - ["lazyqsar-setup"]
    - ["pip", "rdkit", "2025.9.1"]
```

**Legacy template (`Dockerfile`)** — same packages, same order. Legacy models have no `install.yml`; the `Dockerfile` *is* the dependency spec, so it is the file to edit. Change only the dependency lines, never `FROM`, `WORKDIR`, or `COPY`.

```dockerfile
RUN pip install lazyqsar[descriptors]==2.3.0
RUN pip install chemprop==2.2.0
RUN lazyqsar-setup
RUN pip install rdkit==2025.9.1
```

Why the order matters:

- chemprop **2.2.0** is the last release depending on `rdkit` **without** `cuik_molmaker_pin`.
- Installing it **before** `lazyqsar-setup` means `ensure_chemprop()`'s `import chemprop` succeeds, so it returns early and never pip-installs chemprop 2.3.x. `cuik_molmaker_pin` never enters the environment at all.
- The trailing `rdkit==2025.9.1` re-pin is insurance in case an earlier step moved it.

**Do not pin rdkit alone.** With `cuik_molmaker_pin` present, `import chemprop` under rdkit 2025.9.1 fails with `ImportError: libRDKitAbbreviations-*.so: cannot open shared object file`, which re-triggers `ensure_chemprop()` and restores the cycle. The constraint is genuinely circular — chemprop must be downgraded to break it.

Verify with the normal shallow test: it rebuilds the environment from scratch, and `simple_model_run` executes the model *after* fetch has already run it once, so passing that check is direct proof the "works once" cycle is broken.

**Do not commit `install.sh`.** Ersilia writes an `install.sh` into the model directory while building the env locally; it contains hardcoded absolute paths (`/home/<user>/anaconda3/envs/<model_id>/bin/python -m pip install ...`) and is meaningless on a CI runner. Editing it does not change what CI builds — only `install.yml` (or the `Dockerfile`) does.

---

## Verifying manually (optional, when the test error is opaque)

Reproduce the run outside the test harness to see the raw error:

```bash
conda activate ersilia
cd <model_path>/model/framework
bash run.sh . examples/run_input.csv /tmp/test_output.csv
cat /tmp/test_output.csv
```

If the direct run works but the Ersilia test still fails, the issue is in how Ersilia reads the output — recheck column names, types, and format against `run_columns.csv`.
