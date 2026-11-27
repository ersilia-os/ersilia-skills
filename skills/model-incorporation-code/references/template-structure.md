# Ersilia Model Template – File Reference

## Directory Layout

```
<model-id>/
├── install.yml             # dependency specification
├── metadata.yml            # model metadata (filled separately)
└── model/
    ├── checkpoints/        # pretrained weights / scalers (in git; eosvc if a file is ≥ 100 MiB)
    └── framework/
        ├── run.sh          # entry-point shell script (rarely needs editing)
        ├── code/
        │   ├── main.py     # load_tool() + run_tool() — THIS IS THE MAIN TARGET
        │   └── *.py        # helper scripts copied from the source model
        ├── columns/
        │   └── run_columns.csv
        ├── examples/
        │   ├── run_input.csv
        │   └── run_output.csv
        └── fit/            # training code (eosvc once populated) — populated only when checkpoints are not
            ├── README.md   #   publicly available and retraining is needed
            ├── data/       # training data or download scripts
            ├── results/    # output checkpoints from training (copy to model/checkpoints/)
            └── src/        # training scripts copied from the source repo
```

---

## run_columns.csv

**Location:** `model/framework/columns/run_columns.csv`

Four required columns, no extras. Write it with Python or a plain text editor without BOM encoding:

| Column | Rules |
|--------|-------|
| `name` | lowercase letters and underscores only; no spaces, hyphens, or special chars |
| `type` | exactly one of: `float`, `integer`, `string` |
| `direction` | `high` or `low` — whether a larger value means **more of the modelled property**, never whether it is desirable. `high` means higher output values correspond to more of the modelled property. `low` means lower values correspond to more of the property. Leave **empty** for sampling outputs and for representation models with abstract latent dimensions (e.g. neural embeddings) where dimensions have no interpretable direction. For fingerprint-based representations (e.g. Morgan counts), use `high` since higher = more of that structural feature present. |
| `description` | one plain-English sentence; **no commas** inside the text |

> **`direction` is magnitude, not desirability.** A cardiotoxicity score is `high` because
> the number rises with cardiotoxicity, even though less cardiotoxicity is preferable. The
> vocabulary file's name (`desired_directions.txt`) and its unused `intermediate` value both
> suggest otherwise; ignore them. A 2026 sweep corrected 51 models that had read the field
> as desirability.

### Naming conventions by model type

| Model type | Output naming |
|------------|--------------|
| Annotation, single output | meaningful name: `mol_weight`, `logp`, `activity_score` |
| Annotation, multi-output | meaningful name per output: `rb`, `glob`, `primary_amine` |
| Representation / featurisation | `feat_` + zero-padded index sized to total dimension count: `feat_00` (100 dims), `feat_000` (512 dims), `feat_0000` (2048 dims) |
| Sampling (SMILES output) | `smi_` + zero-padded index: `smi_00` (100 outputs), `smi_000` (1000 outputs) |

> **These are preferences, not enforced rules.** Nothing in the `ersilia` codebase checks any
> prefix, and no Ersilia documentation deprecates the alternatives. The hub is genuinely split:
> among existing featurizers `dim_` is the plurality (13 models against 10 using `feat_`, plus
> 7 `feature_` and 1 `dimension_`), and `smi_` leads `smiles_` only 14 to 8. Use `feat_` and
> `smi_` for new incorporations, but do not rewrite an existing model's columns on the strength
> of this preference alone. See ersilia-os/ersilia#1901.

### Examples from real Ersilia models

**eos3b5e — annotation, single output:**
```csv
name,type,direction,description
mol_weight,float,high,The calculated molecular weight of the molecule in g/mol
```

**eos7ike — annotation, multi-output:**
```csv
name,type,direction,description
rb,integer,high,Low flexibility (rotatable bonds lower or equal than 5)
glob,integer,high,Low globularity (lower or equal than 0.25)
primary_amine,integer,high,Determines if a molecule has a primary amine
```

**eos5axz — fingerprint representation (first 2 of 2048):**
```csv
name,type,direction,description
dim_0000,integer,high,Morgan count fingerprint dimension 0 with radius 3 and 2048 bits
dim_0001,integer,high,Morgan count fingerprint dimension 1 with radius 3 and 2048 bits
```

**eos39co — abstract neural embedding (first 2 of 512):**
```csv
name,type,direction,description
dim_000,float,,UniMol molecular representation dimension 000
dim_001,float,,UniMol molecular representation dimension 001
```

> **Note:** The examples above are shown as they exist in the hub, which is why they use the
> `dim_` prefix. Prefer `feat_` (e.g. `feat_0000`, `feat_000`) for new incorporations.

**eos2hzy — sampling (first 2 of 100):**
```csv
name,type,direction,description
smiles_00,string,,Compound index 0 queried with the PubChem API
smiles_01,string,,Compound index 1 queried with the PubChem API
```

**eos6ost — sampling (first 2 of 1000):**
```csv
name,type,direction,description
smi_000,string,,Generated compound index 0 using pre-trained LibInvent model
smi_001,string,,Generated compound index 1 using pre-trained LibInvent model
```

Key patterns to notice:
- Most probability outputs (0–1 scale) are `high` — a higher score means more of that property
- Physical quantities where lower values reflect more of the property are `low` (e.g. free energy, LD50 in log(1/(mol/kg)))
- Fingerprint-based representation outputs use `high` — a higher value means more of that structural feature is present
- Abstract neural embedding outputs leave `direction` empty — individual dimensions have no interpretable direction
- Sampling outputs always leave `direction` empty

---

## install.yml

**Location:** `install.yml` (root of template repo)

```yaml
python: "3.10"   # minimum 3.8; use the version the source model targets

commands:
  # PyPI package with exact version
  - ["pip", "numpy", "1.24.3"]

  # conda package from conda-forge
  - ["conda", "rdkit", "2023.09.1", "conda-forge"]

  # PyTorch CPU-only build (always use this — Ersilia models run on CPU)
  - ["pip", "torch", "2.0.1+cpu", "--index-url", "https://download.pytorch.org/whl/cpu"]

  # git URL (for packages not on PyPI or needing a specific commit)
  - ["pip", "git+https://github.com/org/repo.git@v1.2.3"]

  # plain shell string for anything else
  - "pip install -e ."
```

### Tips
- **Always pin exact versions.** Ranges like `>=1.0` are not allowed.
- **Order matters**: install base libraries (numpy, torch) before downstream ones.
- **CPU only — no CUDA packages.** Ersilia models run on CPU in production. Always
  install CPU-only builds and never include `cudatoolkit`, `cuda-toolkit`, or any
  `nvidia-*` packages:
  - PyTorch: `["pip", "torch", "<version>+cpu", "--index-url", "https://download.pytorch.org/whl/cpu"]`
  - TensorFlow: use `tensorflow-cpu` (not `tensorflow`)
  - JAX: use `jax[cpu]` (not `jax`)
- Use `conda` for packages with C extensions that conda ships better
  (e.g. `rdkit`, `openbabel`, `openmm`).

---

## Checkpoints and training data (git, or eosvc)

`model/checkpoints/` is committed to git if every file is under 100 MiB (104,857,600 bytes).
If any file is 100 MiB or larger, the whole folder is gitignored and persisted with eosvc.
`model/framework/fit/`, once it holds training code or data, always goes to eosvc. From the
model repo root:

```bash
find model/checkpoints -type f -size +104857599c      # no output: checkpoints in git
conda run -n eosvc eosvc upload --path checkpoints    # only for a folder on eosvc
conda run -n eosvc eosvc upload --path fit            # whenever fit/ is populated
```

A folder on eosvc is named in `access.json`, which also sets public or private, and listed
under a `#eosvc managed` block in `.gitignore`. A model with nothing on eosvc has no
`access.json`. Never keep a folder in both places: CI downloads the S3 copy over the git one.
No Git LFS. Weights live in `model/checkpoints/` and are never downloaded at run time.
Repositories created from older templates may hold a `.gitattributes` and a `mock.txt` for a
Git LFS mock; delete both.

---

## run_input.csv

**Location:** `model/framework/examples/run_input.csv`

Exactly one column named `smiles`, exactly three rows (no header row for the index).

Sample 3 random SMILES from the Ersilia maintained inputs file:

```python
import urllib.request, csv, random
url = "https://raw.githubusercontent.com/ersilia-os/ersilia-model-hub-maintained-inputs/main/inputs/example.csv"
with urllib.request.urlopen(url) as f:
    rows = list(csv.DictReader(line.decode() for line in f))
sample = random.sample(rows, 3)
print("smiles")
for r in sample:
    print(r["input"])
```

---

## run_output.csv

**Location:** `model/framework/examples/run_output.csv`

Contains **only the output columns** — no `smiles` column, no index. Column names
must match exactly what is listed in `run_columns.csv`. Three rows corresponding to
the three inputs.

```csv
activity
0.82
0.45
0.11
```

**This file must be produced by running the model**, not fabricated. See Phase 6 of
the skill for the exact commands.

---

## main.py – skeleton reference

The template's `main.py` is split into two top-level functions: `load_tool()` for the slow,
one-time setup, and `run_tool(model, input_file, output_file)` for one batch. Contributors
replace the molecular-weight placeholder (the `MolWt` import, the body of `load_tool()`, and the
prediction and header in `run_tool()`) and keep the structure.

```python
import os
import sys
import numpy as np
from rdkit import Chem
from rdkit.Chem.Descriptors import MolWt
from ersilia_pack_utils.core import read_smiles, write_out

root = os.path.dirname(os.path.abspath(__file__))
checkpoints = os.path.join(root, "..", "..", "checkpoints")


# Load the model once. When served, Ersilia keeps the result in memory between batches.
def load_tool():
    return MolWt


# Run the model on one batch.
def run_tool(model, input_file, output_file):
    _, smiles_list = read_smiles(input_file)
    outputs = np.array([[model(Chem.MolFromSmiles(smi))] for smi in smiles_list])
    assert len(smiles_list) == len(outputs)
    header = [f"feat_{str(i).zfill(3)}" for i in range(outputs.shape[1])]
    write_out(outputs, header, output_file, np.float32)


if __name__ == "__main__":
    run_tool(load_tool(), sys.argv[1], sys.argv[2])
```

Rules that follow from how Ersilia calls these functions (details, and one pattern per model
type, in `references/main-py-patterns.md`):

- Define `load_tool` and `run_tool` as top-level `def`s in `main.py` itself, and leave `run.sh`
  as the default single line `python $1/code/main.py $2 $3`. Warm serving needs both.
- Heavy imports, reading `model/checkpoints/` and building the model go in `load_tool()`, which
  returns everything `run_tool()` needs. Nothing is kept between batches.
- No work at module level (no `sys.argv`, no inference), and no `sys.exit()` in the functions.
- Invalid or unparseable SMILES give an empty row (`None`), never an exception.
- The `header` passed to `write_out` must match the `name` column of `run_columns.csv`.
