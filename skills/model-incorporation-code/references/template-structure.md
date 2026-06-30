# Ersilia Model Template – File Reference

## Directory Layout

```
<model-id>/
├── .gitattributes          # git-lfs tracking rules (add if large checkpoints exist)
├── install.yml             # dependency specification
├── metadata.yml            # model metadata (filled separately)
└── model/
    ├── checkpoints/        # pretrained weights / scalers (tracked by git-lfs if >100 MB)
    └── framework/
        ├── run.sh          # entry-point shell script (rarely needs editing)
        ├── code/
        │   ├── main.py     # primary inference script — THIS IS THE MAIN TARGET
        │   └── *.py        # helper scripts copied from the source model
        ├── columns/
        │   └── run_columns.csv
        ├── examples/
        │   ├── run_input.csv
        │   └── run_output.csv
        └── fit/            # training code — populated only when checkpoints are not
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
| `direction` | `high` or `low` — the direction of biological activity. `high` means higher output values correspond to more of the modelled property. `low` means lower values correspond to more of the property. Leave **empty** for sampling outputs and for representation models with abstract latent dimensions (e.g. neural embeddings) where dimensions have no interpretable direction. For fingerprint-based representations (e.g. Morgan counts), use `high` since higher = more of that structural feature present. |
| `description` | one plain-English sentence; **no commas** inside the text |

### Naming conventions by model type

| Model type | Output naming |
|------------|--------------|
| Annotation, single output | meaningful name: `mol_weight`, `logp`, `activity_score` |
| Annotation, multi-output | meaningful name per output: `rb`, `glob`, `primary_amine` |
| Representation / featurisation | `feat_` + zero-padded index sized to total dimension count: `feat_00` (100 dims), `feat_000` (512 dims), `feat_0000` (2048 dims) |
| Sampling (SMILES output) | `smi_` + zero-padded index: `smi_00` (100 outputs), `smi_000` (1000 outputs) |

> **Historical note:** Many existing Ersilia models use `dim_0000` / `dim_000` (pre-dating this convention). New model incorporations must use the `feat_` prefix.

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

> **Note:** The examples above use the historical `dim_` prefix. **New model incorporations must use `feat_`** (e.g. `feat_0000`, `feat_000`) following the current Ersilia convention.

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

## .gitattributes (git-lfs)

Add entries for every file extension that appears in `checkpoints/` and is ≥ 100 MB.
Ersilia's standard patterns:

```
*.csv filter=lfs diff=lfs merge=lfs -text
*.h5 filter=lfs diff=lfs merge=lfs -text
*.joblib filter=lfs diff=lfs merge=lfs -text
*.pkl filter=lfs diff=lfs merge=lfs -text
*.pt filter=lfs diff=lfs merge=lfs -text
*.ckpt filter=lfs diff=lfs merge=lfs -text
*.bin filter=lfs diff=lfs merge=lfs -text
*.safetensors filter=lfs diff=lfs merge=lfs -text
```

Commands:
```bash
git lfs install                  # once per repo
git lfs track "*.pt"             # adds the line to .gitattributes
git add .gitattributes
git add checkpoints/my_weights.pt
git status                       # confirm "(LFS)" appears next to tracked files
```

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

The template's `main.py` already contains boilerplate for argument parsing and CSV I/O.
The only part contributors need to replace is the `my_model` function and its imports.

```python
# ── imports ────────────────────────────────────────────────────────────────
import os, sys, csv
# ... source model imports go here ...

# ── checkpoint path helper ─────────────────────────────────────────────────
root = os.path.dirname(os.path.abspath(__file__))           # .../framework/code/
checkpoints_dir = os.path.join(root, "..", "..", "checkpoints")  # .../checkpoints/

# ── model loading (done once at import time or inside my_model) ────────────
# model = load_model(os.path.join(checkpoints_dir, "weights.pt"))

# ── inference function ──────────────────────────────────────────────────────
def my_model(smiles_list):
    """
    Accept a list of SMILES strings.
    Return a list of predictions in the same order.
    Invalid / unparseable SMILES should return None (or a list of Nones for
    multi-output models) rather than raising an exception.
    """
    results = []
    for smi in smiles_list:
        try:
            # ... run inference ...
            results.append(prediction)
        except Exception:
            results.append(None)
    return results
```
