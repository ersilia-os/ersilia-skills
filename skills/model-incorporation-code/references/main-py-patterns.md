# main.py Patterns by Model Type

Every pattern below has the shape of the current `eos-template` `main.py`: a `load_tool()` for
the one-time setup and a `run_tool(model, input_file, output_file)` for each batch. They are
adapted from the hub models named in the titles, so the model in the hub may differ in detail.

## How Ersilia calls main.py

The template's `main.py` looks like this. Replace the placeholder, keep the structure:

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

There are two ways in, and the model has to work with both:

- **As a script.** `run.sh` runs `python $1/code/main.py $2 $3`, and so do `ersilia test` and CI.
  The `__main__` block calls `run_tool(load_tool(), ...)` once.
- **Warm serving.** A long-lived worker imports `main.py` as a module called `main` (the
  `__main__` block does not run, and `sys.argv` holds only the script path), calls `load_tool()`
  once, then calls `run_tool(model, input, output)` for every batch, one batch after the other.
  The folder of `main.py` is first on `sys.path`, so helper modules next to it import as usual.
  Printed output goes to the server log, and a `SystemExit` raised by the model counts as a failed
  batch.

Warm serving is used only when both of these hold:

1. `main.py` defines `load_tool` and `run_tool` as top-level `def`s (it is parsed, so importing
   them from another module does not count), and
2. `run.sh` is the default single line `python $1/code/main.py $2 $3`.

Otherwise the model runs once per batch. If `load_tool()` fails the model also falls back to
`run.sh`, and if the worker dies during a batch that batch is rerun with `run.sh`.
`ERSILIA_WARM=0` turns warm serving off.

What follows for the code:

- Do the slow, batch-independent work in `load_tool()`: heavy imports, reading
  `model/checkpoints/`, building the model. Return everything `run_tool()` needs as one object,
  a tuple or a dict.
- Keep nothing between batches: no caches that grow, no accumulated lists, no temp files that
  outlive the call. Each batch must give the same result whatever ran before it.
- Do no work at module level: no `sys.argv[1]`, no reading the input, no inference. Constants
  and cheap imports are fine.
- Do not call `sys.exit()` or parse arguments inside the functions. `run.sh` passes only the
  input and output paths, so extra flags (a debug switch, say) cannot reach the model.

## Conventions shared by all patterns

> **New models use `ersilia_pack_utils` for all CSV I/O.** Do not use manual `csv.reader` /
> `csv.writer` for Ersilia's own input and output.
>
> - `read_smiles(input_file)` returns `(header, smiles_list)` and reads `.csv` and `.bin` inputs.
> - `write_out(outputs, header, output_file, dtype)` writes `.csv` outputs as they are, and `.bin`
>   outputs as `np.float32` or `np.int32` only (NaN and inf are clipped, and a `None` becomes
>   NaN with `np.float32`, but cannot be stored with `np.int32`). The `header` must match the
>   `name` column of `run_columns.csv` exactly.

> **Prefer the `feat_` prefix for representation/featurisation output columns** (e.g.
> `feat_000` for 512 dims, `feat_0000` for 2048 dims), zero-padding the index to the width
> of the total dimension count. Older hub models use `dim_0000` / `dim_000`. This is a
> convention, not an enforced rule — nothing in the `ersilia` codebase checks the prefix and
> `dim_` remains the plurality among existing featurizers. See `references/template-structure.md`
> and ersilia-os/ersilia#1901.

Also true of every pattern:
- `root = os.path.dirname(os.path.abspath(__file__))` gives the script location, and
  `os.path.join(root, "..", "..", "checkpoints")` the checkpoints folder. Never use an absolute path.
- An invalid or unparseable SMILES gives an empty row (`None`), never an exception that stops the batch.
- `assert len(smiles_list) == len(outputs)` before writing.

---

## Annotation

### Pure algorithmic, no checkpoints — adapted from eos3b5e (molecular weight)

```python
import os
import sys
import numpy as np
from rdkit import Chem
from rdkit.Chem.Descriptors import MolWt
from ersilia_pack_utils.core import read_smiles, write_out

root = os.path.dirname(os.path.abspath(__file__))


def load_tool():
    # nothing to load: the "model" is a function
    return MolWt


def run_tool(model, input_file, output_file):
    _, smiles_list = read_smiles(input_file)
    outputs = []
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        outputs.append([model(mol) if mol is not None else None])
    assert len(smiles_list) == len(outputs)
    write_out(outputs, ["mol_weight"], output_file, np.float32)  # match run_columns.csv


if __name__ == "__main__":
    run_tool(load_tool(), sys.argv[1], sys.argv[2])
```

---

### Library-based, DataFrame output — adapted from eos7d58 (ADMET-AI)

```python
import os
import sys
import numpy as np
from ersilia_pack_utils.core import read_smiles, write_out

root = os.path.dirname(os.path.abspath(__file__))


def load_tool():
    # heavy import and model construction happen once
    from admet_ai import ADMETModel

    return ADMETModel()


def run_tool(model, input_file, output_file):
    _, smiles_list = read_smiles(input_file)
    preds = model.predict(smiles=smiles_list)  # a DataFrame, one row per molecule
    assert len(smiles_list) == len(preds)
    header = [c.lower().replace("-", "_") for c in preds.columns]  # match run_columns.csv
    write_out(preds.to_numpy(), header, output_file, np.float32)


if __name__ == "__main__":
    run_tool(load_tool(), sys.argv[1], sys.argv[2])
```

---

### Subprocess, temp files, multi-output — adapted from eos7ike (property filters)

The tool is a script run in a subprocess, so there is nothing slow to load. Each batch gets its
own temp folder, removed at the end. (The original also patches an OpenBabel compatibility
issue through a generated `sitecustomize.py`; that is left out here.)

```python
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import numpy as np
from ersilia_pack_utils.core import read_smiles, write_out

root = os.path.dirname(os.path.abspath(__file__))


def load_tool():
    return {
        "python": sys.executable,
        "script": os.path.join(root, "entry-cli", "calc_props.py"),
    }


def run_tool(model, input_file, output_file):
    _, smiles_list = read_smiles(input_file)
    tmp_folder = tempfile.mkdtemp()
    try:
        input_tmp = os.path.join(tmp_folder, "input.smi")
        output_tmp = os.path.join(tmp_folder, "output.csv")
        with open(input_tmp, "w") as f:
            for i, smi in enumerate(smiles_list):
                f.write(f"{smi} mol_{i}\n")

        process = subprocess.run(
            [model["python"], model["script"], "-b", input_tmp, "-o", output_tmp],
            capture_output=True,
            text=True,
        )
        if process.stdout:
            print(process.stdout)
        if process.stderr:
            print(process.stderr)

        outputs = []
        with open(output_tmp, "r") as f:  # the tool's own file, not Ersilia's I/O
            reader = csv.reader(f)
            next(reader)
            for r in reader:
                if r[3] is None or str(r[3]) == "":
                    outputs.append([None, None, None])
                else:
                    outputs.append(
                        [
                            1 if int(r[3]) <= 5 else 0,
                            1 if float(r[4]) <= 0.25 else 0,
                            1 if str(r[6]) == "True" else 0,
                        ]
                    )
    finally:
        shutil.rmtree(tmp_folder, ignore_errors=True)

    assert len(smiles_list) == len(outputs)
    # float32, not int32: a None (invalid molecule) cannot be stored as int32
    write_out(outputs, ["rb", "glob", "primary_amine"], output_file, np.float32)


if __name__ == "__main__":
    run_tool(load_tool(), sys.argv[1], sys.argv[2])
```

---

## Representation

### Fingerprint — adapted from eos5axz (ECFP Morgan)

```python
import os
import sys
import numpy as np
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator
from ersilia_pack_utils.core import read_smiles, write_out

root = os.path.dirname(os.path.abspath(__file__))

RADIUS = 3
NBITS = 2048


def clip_sparse(vect, nbits):
    l = [0] * nbits
    for i, v in vect.GetNonzeroElements().items():
        l[i] = v if v < 255 else 255
    return l


def load_tool():
    return rdFingerprintGenerator.GetMorganGenerator(radius=RADIUS, fpSize=NBITS)


def run_tool(model, input_file, output_file):
    _, smiles_list = read_smiles(input_file)
    outputs = []
    empty_output = [None] * NBITS
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            outputs.append(empty_output)
            continue
        outputs.append(clip_sparse(model.GetCountFingerprint(mol), NBITS))
    assert len(smiles_list) == len(outputs)
    header = [f"feat_{str(i).zfill(4)}" for i in range(NBITS)]  # eos5axz itself uses dim_
    write_out(outputs, header, output_file, np.float32)


if __name__ == "__main__":
    run_tool(load_tool(), sys.argv[1], sys.argv[2])
```

---

### Pretrained embedding from a library — adapted from eos9o72 (CheMeleon)

```python
import os
import sys
import numpy as np
from ersilia_pack_utils.core import read_smiles, write_out

root = os.path.dirname(os.path.abspath(__file__))


def load_tool():
    from chemeleon_fingerprint import CheMeleonFingerprint

    return CheMeleonFingerprint()


def run_tool(model, input_file, output_file):
    _, smiles_list = read_smiles(input_file)
    outputs = np.asarray(model(smiles_list))
    assert len(smiles_list) == len(outputs)
    header = [f"feat_{str(i).zfill(4)}" for i in range(outputs.shape[1])]
    write_out(outputs, header, output_file, np.float32)


if __name__ == "__main__":
    run_tool(load_tool(), sys.argv[1], sys.argv[2])
```

---

### Checkpoint copied to a temp folder, batching and timeouts — adapted from eos39co (UniMol)

The library reads its weights from a writable folder, so `load_tool()` copies the checkpoint
into a temp folder. That folder is removed when the process ends (`atexit`), because a warm
worker lives across batches. The batching and timeouts stay in `run_tool()`.

```python
import atexit
import os
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import numpy as np
from ersilia_pack_utils.core import read_smiles, write_out

root = os.path.dirname(os.path.abspath(__file__))
checkpoints = os.path.join(root, "..", "..", "checkpoints")

WEIGHT_FILE = "mol_pre_all_h_220816.pt"
BATCH_SIZE = 100
BATCH_TIMEOUT = 1000
MOL_TIMEOUT = 10
N_DIMS = 512


def load_tool():
    tmp_dir = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, tmp_dir, ignore_errors=True)
    os.environ["UNIMOL_WEIGHT_DIR"] = tmp_dir
    os.environ["HF_HOME"] = tmp_dir

    orig_dir = os.getcwd()
    os.chdir(tmp_dir)
    try:
        from unimol_tools import UniMolRepr

        for m in list(sys.modules.values()):
            if "unimol_tools" in getattr(m, "__name__", "") and hasattr(m, "WEIGHT_DIR"):
                m.WEIGHT_DIR = tmp_dir
    finally:
        os.chdir(orig_dir)

    shutil.copy2(os.path.join(checkpoints, WEIGHT_FILE), os.path.join(tmp_dir, WEIGHT_FILE))
    return UniMolRepr(data_type="molecule", remove_hs=False, use_gpu=False)


def run_tool(model, input_file, output_file):
    _, smiles_list = read_smiles(input_file)

    def get_repr(smiles):
        result = model.get_repr(smiles, return_atomic_reprs=False)
        return np.array(result["cls_repr"])

    nan_row = [None] * N_DIMS
    rows = []
    for i in range(0, len(smiles_list), BATCH_SIZE):
        batch = smiles_list[i : i + BATCH_SIZE]
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(get_repr, batch)
            try:
                rows.extend(future.result(timeout=BATCH_TIMEOUT).tolist())
            except TimeoutError:
                for smi in batch:  # retry one molecule at a time
                    with ThreadPoolExecutor(max_workers=1) as ex:
                        f = ex.submit(get_repr, [smi])
                        try:
                            rows.append(f.result(timeout=MOL_TIMEOUT)[0].tolist())
                        except TimeoutError:
                            rows.append(nan_row)

    X = np.array(rows, dtype=float)  # a None becomes NaN
    assert len(smiles_list) == X.shape[0]
    header = [f"feat_{str(i).zfill(3)}" for i in range(X.shape[1])]
    write_out(X, header, output_file, np.float32)


if __name__ == "__main__":
    run_tool(load_tool(), sys.argv[1], sys.argv[2])
```

---

## Sampling

Generators write strings (SMILES). `write_out` writes any values to a `.csv` output path, but a
`.bin` output path accepts only `np.float32` / `np.int32`. `ersilia-pack` can use either format,
so check with an Ersilia maintainer how a model with string output columns is served before
relying on `write_out` for it.

### Simple sampler class — adapted from eos2hzy (PubChem sampler)

`sampler.py` is a helper module in `model/framework/code/`.

```python
import os
import sys
from tqdm import tqdm
from ersilia_pack_utils.core import read_smiles, write_out
from sampler import PubChemSampler

root = os.path.dirname(os.path.abspath(__file__))

N_SAMPLES = 100


def load_tool():
    return PubChemSampler()


def run_tool(model, input_file, output_file):
    _, smiles_list = read_smiles(input_file)
    outputs = [model.sample(smi) for smi in tqdm(smiles_list, desc="Sampling")]
    assert len(smiles_list) == len(outputs)
    header = [f"smi_{i:02d}" for i in range(N_SAMPLES)]  # eos2hzy itself uses smiles_
    write_out(outputs, header, output_file)


if __name__ == "__main__":
    run_tool(load_tool(), sys.argv[1], sys.argv[2])
```

---

### Batch sampling — adapted from eos6ost (LibInvent)

The original also takes a debug flag as a third argument and writes a JSON log next to the
output. Neither fits `run_tool(model, input_file, output_file)`, so both are left out.

```python
import os
import sys
from ersilia_pack_utils.core import read_smiles, write_out
from libinvent_sampler import LibinventSampler

root = os.path.dirname(os.path.abspath(__file__))

BATCH_SIZE = 1000  # molecules sampled per input


def load_tool():
    return LibinventSampler(batch_size=BATCH_SIZE, is_debug=False)


def run_tool(model, input_file, output_file):
    _, input_smiles = read_smiles(input_file)
    outputs, _, _ = model.generate(input_smiles=input_smiles)
    assert len(input_smiles) == len(outputs)
    header = [f"smi_{str(i).zfill(3)}" for i in range(BATCH_SIZE)]
    write_out(outputs, header, output_file)


if __name__ == "__main__":
    run_tool(load_tool(), sys.argv[1], sys.argv[2])
```

---

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| `load_tool` / `run_tool` imported from a helper module, or defined inside `if __name__ == "__main__"` | Define both as top-level `def`s in `main.py`; warm serving parses `main.py` for them |
| Edited `run.sh` | Keep the default single line `python $1/code/main.py $2 $3`; any other `run.sh` runs the model once per batch |
| Model loaded inside `run_tool()` or inside the per-SMILES loop (reloaded every batch) | Load once in `load_tool()`, return it, reuse it in `run_tool()` |
| `sys.argv[1]`, reading the input or running inference at module level | Only inside `run_tool()` or the `__main__` block; the warm worker imports `main.py` with `sys.argv` cut down to the script path |
| State kept between batches (caches, appended lists, temp files left behind) | Build it per batch and clean it up; each batch must give the same result whatever ran before it |
| `sys.exit()` or argument parsing inside the functions | Remove it; `run.sh` passes only the input and output paths, and a `SystemExit` fails the batch |
| Hardcoded absolute path to checkpoints | Use `os.path.join(root, "..", "..", "checkpoints")` |
| Exception crashes the whole batch | Wrap per-molecule inference in `try/except`, return `None` for that row |
| Output length != input length | Always `assert len(smiles_list) == len(outputs)` |
| `np.int32` with missing rows | `None` cannot be stored as `int32`; use `np.float32` when rows can be empty |
| GPU not available in Docker | Default to CPU (`map_location="cpu"`) |
| Missing helper `.py` from source repo | Copy into `model/framework/code/`; that folder is first on `sys.path` both as a script and under warm serving |
| Column names don't match run_columns.csv | The `header` passed to `write_out` must exactly match the `name` column |
