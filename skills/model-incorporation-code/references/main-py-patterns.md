# main.py Patterns by Model Type

> **IMPORTANT — new models must use `ersilia_pack_utils` for all CSV I/O.**
> Do not use manual `csv.reader` / `csv.writer`. The standard read/write pattern is:
>
> ```python
> from ersilia_pack_utils.core import read_smiles, write_out
> import numpy as np
>
> _, smiles_list = read_smiles(input_file)   # reads the smiles column
> # ... run inference, build outputs list ...
> write_out(outputs, headers, output_file, np.float32)
> ```
>
> Some older models in this file predate `ersilia_pack_utils` and use manual CSV
> operations — treat those as historical reference only. **All new incorporations
> must use `ersilia_pack_utils` regardless of what the source model does.**

> **Prefer the `feat_` prefix for representation/featurisation output columns** (e.g.
> `feat_000` for 512 dims, `feat_0000` for 2048 dims), zero-padding the index to the width
> of the total dimension count. Older models in this file use `dim_0000` / `dim_000`. This
> is a convention, not an enforced rule — nothing in the `ersilia` codebase checks the
> prefix and `dim_` remains the plurality among existing featurizers. See
> `references/template-structure.md` and ersilia-os/ersilia#1901.

Two things consistent across all patterns:
- Input/output files come from `sys.argv[1]` and `sys.argv[2]`
- `root = os.path.dirname(os.path.abspath(__file__))` gives the script location

---

## Annotation

### eos3b5e — Molecular Weight (pure algorithmic, no checkpoints)

```python
# imports
import os
import csv
import sys
from rdkit import Chem
from rdkit.Chem.Descriptors import MolWt

# parse arguments
input_file = sys.argv[1]
output_file = sys.argv[2]

# current file directory
root = os.path.dirname(os.path.abspath(__file__))

# my model
def my_model(smiles_list):
    return [MolWt(Chem.MolFromSmiles(smi)) for smi in smiles_list]

# read SMILES from .csv file, assuming one column with header
with open(input_file, "r") as f:
    reader = csv.reader(f)
    next(reader)  # skip header
    smiles_list = [r[0] for r in reader]

# run model
outputs = my_model(smiles_list)

# check input and output have the same length
assert len(smiles_list) == len(outputs)

# write output in a .csv file
with open(output_file, "w") as f:
    writer = csv.writer(f)
    writer.writerow(["mol_weight"])  # header — match run_columns.csv name(s)
    for o in outputs:
        writer.writerow([o])
```

---

### eos7d58 — ADMET-AI (library-based, DataFrame output)

```python
# imports
import os
import csv
import sys

from admet_ai import ADMETModel

# parse arguments
input_file = sys.argv[1]
output_file = sys.argv[2]

# current file directory
root = os.path.dirname(os.path.abspath(__file__))

# my model
def my_model(smiles_list):
    model = ADMETModel()
    preds = model.predict(smiles=smiles_list)
    return preds

# read SMILES from .csv file, assuming one column with header
with open(input_file, "r") as f:
    reader = csv.reader(f)
    next(reader)  # skip header
    smiles_list = [r[0] for r in reader]

# run model
outputs = my_model(smiles_list)

# check input and output have the same length
assert len(smiles_list) == len(outputs)

rename_map = {c: c.lower().replace("-", "_") for c in outputs.columns}
outputs = outputs.rename(columns=rename_map)
outputs.to_csv(output_file, index=False)
```

---

### eos7ike — Property filters (subprocess, temp files, multi-output)

```python
# imports
import os
import csv
import sys
import subprocess
import tempfile
import shutil

# get path of current python executable
python_executable = sys.executable

# parse arguments
input_file = sys.argv[1]
output_file = sys.argv[2]

# current file directory
root = os.path.dirname(os.path.abspath(__file__))

# read SMILES from .csv file, assuming one column with header
with open(input_file, "r") as f:
    reader = csv.reader(f)
    next(reader)  # skip header
    smiles_list = [r[0] for r in reader]

tmp_folder = tempfile.mkdtemp()
os.makedirs(tmp_folder, exist_ok=True)
input_tmp = os.path.join(tmp_folder, "input.smi")
with open(input_tmp, "w") as f:
    for i, smi in enumerate(smiles_list):
        f.write(f"{smi} mol_{i}\n")

output_tmp = os.path.join(tmp_folder, "output.csv")

bash_file = os.path.join(tmp_folder, "run_model.sh")
bash_content = f"""
PATCHDIR="{tmp_folder}"
cat > "$PATCHDIR/sitecustomize.py" <<'PY'
try:
    from openbabel import openbabel as ob
    if not hasattr(ob, "OBForceField_FindType") and hasattr(ob, "OBForceField"):
        if hasattr(ob.OBForceField, "FindType"):
            ob.OBForceField_FindType = ob.OBForceField.FindType
        elif hasattr(ob.OBForceField, "FindForceField"):
            ob.OBForceField_FindType = ob.OBForceField.FindForceField
except Exception:
    pass
PY
export PYTHONPATH="$PATCHDIR:$PYTHONPATH"
{python_executable} {root}/entry-cli/calc_props.py -b {input_tmp} -o {output_tmp}
"""

with open(bash_file, "w") as f:
    f.write(bash_content.strip())

process = subprocess.Popen(f"bash {bash_file}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
stdout, stderr = process.communicate()
if stdout:
    print("Subprocess output:")
    print(stdout)
if stderr:
    print("Subprocess errors:")
    print(stderr)

rb = []
glob = []
primary_amine = []

with open(output_tmp, "r") as f:
    reader = csv.reader(f)
    next(reader)
    for r in reader:
        if r[3] is None or str(r[3]) == "":
            rb += [None]
            glob += [None]
            primary_amine += [None]
        else:
            rb_ = int(r[3])
            glob_ = float(r[4])
            pa_ = str(r[6])
            rb += [1 if rb_ <= 5 else 0]
            glob += [1 if glob_ <= 0.25 else 0]
            primary_amine += [1 if pa_ == "True" else 0]

outputs = [[rb[i], glob[i], primary_amine[i]] for i in range(len(smiles_list))]

assert len(smiles_list) == len(outputs)

with open(output_file, "w") as f:
    writer = csv.writer(f)
    writer.writerow(["rb", "glob", "primary_amine"])
    for o in outputs:
        writer.writerow(o)

shutil.rmtree(tmp_folder)
```

---

## Representation

### eos5axz — ECFP Morgan Fingerprints (ersilia_pack_utils)

```python
import csv, json, os, struct, sys, time
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator
import numpy as np
from ersilia_pack_utils.core import write_out, read_smiles

input_file = sys.argv[1]
output_file = sys.argv[2]

root = os.path.dirname(os.path.abspath(__file__))

RADIUS = 3
NBITS = 2048
mfpgen = rdFingerprintGenerator.GetMorganGenerator(radius=RADIUS, fpSize=NBITS)

def clip_sparse(vect, nbits):
    l = [0] * nbits
    for i, v in vect.GetNonzeroElements().items():
        l[i] = v if v < 255 else 255
    return l

def morganfp(mol):
    v = mfpgen.GetCountFingerprint(mol)
    return clip_sparse(v, NBITS)

outputs = []
empty_output = [None] * NBITS
_, smiles_list = read_smiles(input_file)
for smiles in smiles_list:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        outputs += [empty_output]
        continue
    fp = morganfp(mol)
    fp = np.array(fp, dtype=int)
    outputs += [fp]

assert len(smiles_list) == len(outputs)

headers = ["dim_{0}".format(str(i).zfill(4)) for i in range(len(outputs[0]))]
write_out(outputs, headers, output_file, np.float32)
```

---

### eos9o72 — CheMeleon Fingerprint (ersilia_pack_utils)

```python
# imports
import os
import sys
import numpy as np
from chemeleon_fingerprint import CheMeleonFingerprint
from ersilia_pack_utils.core import read_smiles, write_out

# parse arguments
input_file = sys.argv[1]
output_file = sys.argv[2]

# current file directory
root = os.path.dirname(os.path.abspath(__file__))

# read input
_, smiles_list = read_smiles(input_file)

# Run model
chemeleon_fingerprint = CheMeleonFingerprint()
outputs = chemeleon_fingerprint(smiles_list)

assert len(smiles_list) == len(outputs)

header = [f"dim_{str(i).zfill(4)}" for i in range(2048)]

write_out(outputs, header, output_file, np.float32)
```

---

### eos39co — UniMol Representations (batched, timeout handling, temp dir)

```python
import os
import csv
import sys
import shutil
import tempfile
import numpy as np
from concurrent.futures import ThreadPoolExecutor, TimeoutError

input_file = os.path.abspath(sys.argv[1])
output_file = os.path.abspath(sys.argv[2])

_tmp_dir = tempfile.mkdtemp()
os.environ['UNIMOL_WEIGHT_DIR'] = _tmp_dir
os.environ['HF_HOME'] = _tmp_dir

_orig_dir = os.getcwd()
os.chdir(_tmp_dir)
from unimol_tools import UniMolRepr
for _m in list(sys.modules.values()):
    if 'unimol_tools' in getattr(_m, '__name__', '') and hasattr(_m, 'WEIGHT_DIR'):
        _m.WEIGHT_DIR = _tmp_dir
os.chdir(_orig_dir)

with open(input_file, "r") as f:
    reader = csv.reader(f)
    next(reader)
    smiles_list = [r[0] for r in reader]

root = os.path.dirname(os.path.abspath(__file__))
_weight_file = 'mol_pre_all_h_220816.pt'
_weight_src = os.path.join(root, '..', '..', 'checkpoints', _weight_file)
shutil.copy2(_weight_src, os.path.join(_tmp_dir, _weight_file))

clf = UniMolRepr(data_type='molecule', remove_hs=False, use_gpu=False)

BATCH_SIZE = 100
BATCH_TIMEOUT = 1000
MOL_TIMEOUT = 10
N_DIMS = 512
nan_row = [''] * N_DIMS

def get_repr(smiles):
    result = clf.get_repr(smiles, return_atomic_reprs=False)
    return np.array(result['cls_repr'])

rows = []
for i in range(0, len(smiles_list), BATCH_SIZE):
    batch = smiles_list[i:i + BATCH_SIZE]
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(get_repr, batch)
        try:
            batch_repr = future.result(timeout=BATCH_TIMEOUT)
            rows.extend(batch_repr.tolist())
        except TimeoutError:
            for smi in batch:
                with ThreadPoolExecutor(max_workers=1) as ex:
                    f = ex.submit(get_repr, [smi])
                    try:
                        mol_repr = f.result(timeout=MOL_TIMEOUT)
                        rows.append(mol_repr[0].tolist())
                    except TimeoutError:
                        rows.append(nan_row)

X = np.array(rows)
assert len(smiles_list) == X.shape[0]

header = ["dim_{0}".format(str(i).zfill(3)) for i in range(X.shape[1])]

with open(output_file, "w") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    for row in X:
        writer.writerow(row.tolist())

shutil.rmtree(_tmp_dir, ignore_errors=True)
```

---

## Sampling

### eos2hzy — PubChem Sampler (simple, local sampler class)

```python
# imports
import os
import csv
import sys
from tqdm import tqdm
from sampler import PubChemSampler

# parse arguments
input_file = sys.argv[1]
output_file = sys.argv[2]

# current file directory
root = os.path.dirname(os.path.abspath(__file__))

# read SMILES from .csv file, assuming one column with header
with open(input_file, "r") as f:
    reader = csv.reader(f)
    next(reader)  # skip header
    smiles_list = [r[0] for r in reader]

# run model
sampler = PubChemSampler()
outputs = []
for smi in tqdm(smiles_list, desc="Sampling"):
    o = sampler.sample(smi)
    outputs += [o]

# write output in a .csv file
with open(output_file, "w") as f:
    writer = csv.writer(f)
    writer.writerow([f"smiles_{i:02d}" for i in range(100)])  # header
    for o in outputs:
        writer.writerow(o)
```

---

### eos6ost — LibInvent (batch sampling, debug mode, JSON logging)

```python
# imports
import sys
import os
import csv
import json

import click
from reinvent.config_parse import read_smiles_csv_file

from libinvent_sampler import LibinventSampler

# parse arguments
input_file = sys.argv[1]
output_file = sys.argv[2]

is_debug = sys.argv[3] == "True" if len(sys.argv) > 3 else False
log_file = output_file + ".json"

batch_size = 1000
input_smiles = None

if os.path.exists(input_file):
    input_smiles = read_smiles_csv_file(input_file, columns=0, header=True)
else:
    click.echo(click.style(f"[INPUT_FILE]: {input_file} doesn't exist.", fg="red"))

libinvent_sampler = LibinventSampler(batch_size=batch_size, is_debug=is_debug)

outputs, _, log_libinvent = libinvent_sampler.generate(input_smiles=input_smiles)

assert len(input_smiles) == len(outputs)

HEADER = ["smi_{0}".format(str(x).zfill(3)) for x in range(batch_size)]

with open(output_file, "w", newline="") as fp:
    csv_writer = csv.writer(fp)
    csv_writer.writerows([HEADER])
    csv_writer.writerows(outputs)

if is_debug:
    log = {
        "start": log_libinvent["start"],
        "end": log_libinvent["end"],
        "input_smiles": log_libinvent["input_smiles"],
        "total": log_libinvent["total"],
        "expected": batch_size * len(input_smiles),
    }
    with open(os.path.abspath(log_file), "w", newline="\n") as fp:
        json.dump(log, fp)
```

---

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Hardcoded absolute path to checkpoints | Use `os.path.join(root, "..", "..", "checkpoints")` |
| Model loaded inside the loop (slow) | Load once at module level, reuse per SMILES |
| Exception crashes the whole batch | Wrap per-molecule inference in `try/except`, return `None` |
| Output length != input length | Always `assert len(smiles_list) == len(outputs)` |
| GPU not available in Docker | Default to CPU (`map_location="cpu"`) |
| Missing helper `.py` from source repo | Copy into `model/framework/code/` and `sys.path.insert(0, root)` |
| Column names don't match run_columns.csv | Header row in `writerow` must exactly match `name` column |
