# Ersilia Model Optimization Patterns

The trained weights are usually a small part of a model's footprint. Most of it is Python and its libraries: packages the model never imports, and GPU builds installed for models that only run on CPU. This file lists the changes that make a model lighter, from safest to riskiest, and how to write each one in `install.yml` (or a legacy Dockerfile). Try them in this order and keep a change only if it passes the gates in SKILL.md. Tier 3 (runtime) is documented for a future speed pass; the size skill skips it.

Every pattern has to leave the output identical. If a change needs a different library version, different numerics or new weights, it does not belong here.

---

## Tier 1: CPU-only builds of the same version (install.yml)

This is usually the biggest saving and the least risky, because the version and the numerics stay the same. Ersilia models run on CPU. A default PyPI `torch` wheel on Linux bundles CUDA inside `torch/lib` and also pulls several GB of `nvidia-*` and `triton` wheels.

### PyTorch

Pin the `+cpu` local version and add the PyTorch CPU index as an **extra** index, so every other package still comes from PyPI:

```yaml
# Before
- ["pip", "torch", "2.2.2"]
- ["pip", "torchvision", "0.17.2"]
# After
- ["pip", "torch", "2.2.2+cpu", "--extra-index-url", "https://download.pytorch.org/whl/cpu"]
- ["pip", "torchvision", "0.17.2+cpu", "--extra-index-url", "https://download.pytorch.org/whl/cpu"]
```

- Use `--extra-index-url`, not `--index-url`. With `--index-url` pip looks **only** at the PyTorch index, and the install fails for any dependency that index doesn't mirror.
- The `+cpu` suffix is required. Without it, pip may resolve the CUDA wheel from PyPI anyway.
- Every package in the torch family (`torch`, `torchvision`, `torchaudio`) must use the same CPU build. If you mix a CPU torch with a CUDA torchvision, pip reinstalls CUDA torch.
- macOS wheels are CPU-only already and have no `+cpu` tag. The pin above targets Linux, which is what CI and the hub build on. On a macOS host, check the gate on Linux CI or in a Linux container.
- Older versions have no `+cpu` wheel for some Python versions. Check the index first (`pip download torch==X+cpu --no-deps --extra-index-url ... -d /tmp/x`). If there is no wheel, skip this pattern. Don't change the version.

### Orphaned CUDA wheels from install order

torch can already be a `+cpu` build and the env still carry GBs of `nvidia-*` and `triton` wheels. That happens when a package that depends on torch (`pytorch-lightning`, `torchmetrics`, `chemprop`, …) is installed **before** the torch line: pip pulls the latest CUDA torch from PyPI for it, and the later CPU torch line downgrades torch but leaves the CUDA wheels behind, used by nothing. `deps.py summary` still shows them in `gpu_payload` even though `pip freeze` shows `torch==X+cpu`.

Fix it by moving the torch-family lines **before** every line that depends on torch, so pip finds torch already satisfied. Check that the dependent package's torch requirement (e.g. `torch>=2.1.0`) is satisfied by the pinned version, otherwise pip upgrades torch again.

Once torch goes first, its own dependencies (`fsspec`, `filelock`, `jinja2`/`MarkupSafe`, `sympy`, `networkx`) are resolved by the torch line. With `--index-url https://download.pytorch.org/whl/cpu` pip can only see the PyTorch index, which mirrors older versions of them, so they drift from the baseline and the behaviour gate fails. Use `--extra-index-url` instead (pip still picks `X+cpu`, and takes the rest from PyPI), then compare the inventories: no version may change.

### PyTorch Geometric extensions

`torch-scatter`, `torch-sparse`, `torch-cluster` and `torch-spline-conv` must match the CPU torch build. Use the PyG wheel page for that torch version:

```yaml
- ["pip", "torch-scatter", "2.1.0+pt112cpu", "-f", "https://data.pyg.org/whl/torch-1.12.1+cpu.html"]
```

### Other frameworks

| Heavy | CPU equivalent (same version) | Notes |
|---|---|---|
| `tensorflow` ≥ 2.x on Linux (`tensorflow[and-cuda]`) | `tensorflow-cpu` | Same version string, same ops. Imports as `tensorflow`. |
| `onnxruntime-gpu` | `onnxruntime` | Same version. |
| `jax[cuda*]` | `jax[cpu]` / plain `jax` + `jaxlib` | Same version. |
| `paddlepaddle-gpu` | `paddlepaddle` | Same version. |
| `cupy-*` | remove, if the code falls back to NumPy | Only if the code doesn't import cupy. |
| `dgl` CUDA builds (`-f .../cu118/repo.html`) | `-f https://data.dgl.ai/wheels/repo.html` (CPU) | Same version. |

After the change, check that `build_env.py --report-only` shows `gpu_payload_mb` at or near 0.

---

## Tier 2: remove what the model doesn't need (install.yml)

`deps.py summary` gives the evidence from the traced baseline runs (see SKILL.md, Step 3). It works at the level of installed distributions, not import names, so the `sklearn`→`scikit-learn`, `cv2`→`opencv-python`, `PIL`→`Pillow` mapping is already done. A distribution counts as **needed** if any of these is true:

- one of its files was loaded as a module, opened, or mapped into memory (shared libraries) by any Python process of the run
- one of its executables was started

Reading only its `*.dist-info` (METADATA, `entry_points.txt`) does **not** count: libraries scan the metadata of every installed package to find plugins or versions. The summary marks those packages `metadata`; they can go, and must never be pinned.
- `code/` imports it on a line the inputs never reached (kept as `unexercised` until an input reaches it)
- it is `ersilia-pack-utils`, `pip`, `setuptools` or `wheel`

Everything else that the install spec brings in, **directly or as a dependency of something else**, is weight. There are three ways to remove it:

1. **Delete the line** of a declared package that isn't needed (`remove`). If it was the only source of a needed dependency, pin that dependency instead (`replace`).
2. **`--no-deps`** on a needed package whose dependency tree carries unneeded packages (see below).
3. **Dead imports.** A package that `code/` imports, that runs no code after the import (call trace), and whose imported names are used on no line that ran (coverage), is loaded only because of the import. Delete the import statement and the package (`dead-import`). Typical cases are training utilities that a shared module imports at the top: hyperparameter search, tensorboard writers, metrics. Names used in a function annotation count as used, because annotations are evaluated when the `def` runs (unless the file has `from __future__ import annotations`).

Common dead weight:
- **Training-only tools**: `wandb`, `tensorboard`, `pytorch-lightning` (when only used for `Trainer.fit`), `optuna`, `ray`, `mlflow`, `hydra-core`.
- **Notebook and plotting tools**: `jupyter`, `ipykernel`, `matplotlib`, `seaborn`, `plotly`.
- **Leftovers from the source repo's `requirements.txt`** that the inference path never touches.

**Do not remove:**
- `ersilia-pack-utils`: the serving layer uses it, even when `main.py` doesn't import it.
- A package imported lazily inside a function that the test inputs don't reach (`unexercised_imports` in the plan). Find an input that reaches it, or keep it. Also check for `importlib.import_module` and `__import__` with computed names, which no static analysis sees.
- A package whose removal changes which implementation another library picks. For example, removing `numba` can make a library fall back to a slower pure-Python path that gives slightly different floats. The exact gate catches this when the floats change; the behaviour gate (`deps.py diff`) catches it even when they don't, as a new failed import of a module that was loaded at baseline.
- An import with side effects, even if the trace makes it look dead: plugin registration, monkey-patching, setting a backend, `warnings` filters.

### `--no-deps` for heavy optional dependency trees

Some packages declare heavy dependencies that the code paths used here never touch. `torch-geometric` pulling in the full scientific stack is a typical case. Install such a package with `--no-deps` and pin the dependencies it really needs as separate lines:

```yaml
- ["pip", "torch-geometric", "2.0.4", "--no-deps"]
- ["pip", "scikit-learn", "1.7.2"]   # really used by torch_geometric.nn in this model
```

Only do this when the runtime trace shows exactly which dependencies are loaded: in the summary, `declared_lines` lists, for each line, the dependencies only it installs that were used (pin exactly those, at the listed versions) and the unused ones it would drop. A missing one shows up as an `ImportError` on the example run, so the gate catches it.

**Put every `--no-deps` line last, after all the normal installs.** Once a package has been installed without its declared dependencies, every later `pip install` prints a "X requires Y, which is not installed" block to stderr. ersilia-pack runs the whole install script reading stdout to EOF before it reads stderr (`ersilia_pack/utils.py`). Once stderr passes the ~64 KB pipe buffer, pip blocks forever at 0% CPU, and `ersilia fetch` (and so the shallow test) hangs. Your scratch env builds fine, because `build_env.py` doesn't have this bug, so only the shallow test catches it. With the `--no-deps` lines at the end, `grep -c "which is not installed" env-cand-<n>.log` should be close to 0.

**Don't pin packages the serving layer already provides at a different version.** ersilia-pack installs `packaging`, `numpy`, `psutil`, `typing-extensions`, `wrapt` and others into the model env before your lines run, and some of its own dependencies cap them (e.g. `limits` needs `packaging<25`). If the original install never pinned such a package, the served env kept ersilia-pack's version. When a `--no-deps` change means you have to list it, pin that same version, not the one the scratch env resolved. Check with `<model env>/bin/pip freeze` after a shallow test.

---

## Tier 3: runtime efficiency (main.py and code/)

These changes improve Computational Performance without touching the environment. They must not change the arithmetic.

| Pattern | Before → After | Why it's safe |
|---|---|---|
| Load the model once | Loading checkpoints inside the per-molecule loop → loading once at module level | Same weights, same forward pass |
| Batch inference | `for smi in smiles: model(featurize(smi))` → batch through the model in chunks | Only safe if the model has no batch-dependent layers in eval mode (BatchNorm in eval, no batch-level normalization). Verify with the exact gate on the 10-molecule set, not just the 3 examples. |
| Disable autograd | Add `torch.inference_mode()` / `torch.no_grad()` around prediction | Same forward numerics, no gradient bookkeeping |
| `model.eval()` | Add it if it's missing | **Changes outputs** if dropout/BatchNorm were active before. The reference output was produced *without* it, so this fails the gate. Don't add it. Report it as a finding instead. |
| Avoid DataFrame row loops | `df.iterrows()` / `df.apply` → work on lists or NumPy | Same values, if dtype handling is kept |
| Avoid repeated file I/O | Temp files written per molecule → one batch file | Same inputs to the same tool |
| Lazy heavy imports | Imports only used on a rare branch → import inside that branch | Faster startup (CP1) |
| Thread oversubscription | Leave thread settings alone | Changing `torch.set_num_threads` or `OMP_NUM_THREADS` can change reduction order, and so the floats. Don't touch them. |

Batching and vectorised featurisation can reorder floating-point reductions. The exact gate on the extended input set decides whether they stay. If the output is off by even one ULP, revert.

---

## Legacy Dockerfile models (BentoML template)

Legacy models have a `Dockerfile` and no `install.yml`. The same tiers apply, but you edit the `RUN pip install …` lines, and `ersilia test` enforces stricter pins (see *Dockerfile pin rules* in SKILL.md). The main difference is that **a `+cpu` tag is not allowed in the pin**, so the CPU build has to be chosen through the package source:

```dockerfile
# Before: the generic page also lists ROCm/CUDA builds, and pip picks torch 1.13.1+rocm5.2 (~7.7 GB)
RUN pip install torch==1.13.1 -f https://download.pytorch.org/whl/torch_stable.html
RUN pip install torchvision==0.14.1 -f https://download.pytorch.org/whl/torch_stable.html
# After: the CPU-only page. Same version, and pip installs 1.13.1+cpu
RUN pip install torch==1.13.1 -f https://download.pytorch.org/whl/cpu/torch_stable.html
RUN pip install torchvision==0.14.1 -f https://download.pytorch.org/whl/cpu/torch_stable.html
```

- With no `-f` at all (`RUN pip install torch==1.13.1`), pip takes the CUDA wheel from PyPI. Add `--extra-index-url https://download.pytorch.org/whl/cpu`. A plain `==X` pin still matches `X+cpu`, and pip prefers `X+cpu`. This was checked for 1.13.1 on Python 3.8 and 2.4.1 on Python 3.12.
- Never write `torch==1.13.1+cpu` in a Dockerfile. It installs fine but fails the test's dependency check, which rejects the `+`.
- Always check the result with `<cand env>/bin/pip freeze | grep -i torch`. If it doesn't show `+cpu`, the candidate hasn't done anything.
- PyG extensions: use the same `-f https://data.pyg.org/whl/torch-<ver>+cpu.html` page with a plain pin (`torch-scatter==2.1.0`). The `+` in the URL is fine, because the check skips the value after `-f`.
- `--no-deps` is allowed on a `RUN pip install` line, so the Tier 2 pattern works the same way. Put each pinned dependency on its own `RUN pip install` line.
- The environment `ersilia test` measures is the conda env built from the `RUN` lines. The BentoML base image isn't included, and this skill doesn't change it.

---

## Never allowed

- **Changing library versions** to get smaller wheels (e.g. a torch upgrade). This changes the numerics, and `install.yml` pins are part of the model's reproducibility.
- **Quantization, fp16/bf16, pruning, distillation, ONNX/TorchScript export.** These change the outputs and/or need new files in `model/checkpoints/`, which must not be touched.
- **Changing the Python version.** It is a wide change and can pull different wheels for every package.
- **Editing `run.sh`, `run_output.csv`, checkpoints, metadata or the directory structure.** Size-related metadata fields are filled in automatically after merge.
- **Changing a legacy Dockerfile's `FROM` line** (base image or Python version), `WORKDIR /repo`, `COPY . /repo`, or anything in `src/` or `pack.py`.
