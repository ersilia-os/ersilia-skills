---
name: model-gpu
description: Adapts an Ersilia Model Hub model so it can also run on a GPU, without touching its CPU behaviour or eos-template. The user names the model (ID and local path). On a `gpu` branch of the model repo, the skill makes exactly three changes: replaces model/framework/run.sh with the fixed template that runs main_gpu.py when ERSILIA_DEVICE=gpu (set by Ersilia's GPU Dockerfiles) and main.py otherwise; writes model/framework/code/main_gpu.py, a copy of main.py that runs the model on CUDA and fails loudly when no GPU is visible or a CUDA error occurs; and adds a `gpu:` section to install.yml with the same packages as `commands:` but CUDA builds of the GPU frameworks (torch CUDA wheels, tensorflow[and-cuda], jax[cuda12], onnxruntime-gpu, DGL/PyG CUDA builds). Handles the hard cases: traced TorchScript checkpoints with a hard-coded CPU device, inference inside forked worker pools, broad try/except that would hide CUDA errors, and torch pins overridden by other packages. Stops and reports when the model has nothing that runs on a GPU (scikit-learn, RDKit-only, XGBoost/LightGBM inference). Verifies that the CPU path is unchanged, smoke-tests main_gpu.py on CPU, and compares GPU against CPU outputs when a GPU is available. Self-contained. Does not commit or push. Triggers include "make eosXXXX run on GPU", "add GPU support to eosXXXX", "gpu version of this model", "create main_gpu.py", "add the gpu section to install.yml", "adapt eosXXXX for gpu", "/model-gpu".
argument-hint: <model_id> <model_path>
---

# Ersilia Model GPU adaptation

GPU support lives in each model, not in eos-template. **Never edit eos-template for
GPU.** A model supports GPU when it has three things:

1. `model/framework/run.sh` — the fixed template in `assets/run.sh`. It runs
   `main_gpu.py` when the env var `ERSILIA_DEVICE` is `gpu` and `main.py` otherwise.
   `ERSILIA_DEVICE=gpu` is set by Ersilia's GPU Dockerfiles
   (`dockerfiles/dockerize-ersiliapack/model/Dockerfile.pip-gpu` and `Dockerfile.conda-gpu`
   in the `ersilia` repo), which build with `ersilia_model_pack ... --device gpu`.
2. `model/framework/code/main_gpu.py` — `main.py` running on CUDA.
3. A `gpu:` section in `install.yml`, same format as `commands:`. ersilia-pack with
   `--device gpu` installs `gpu:` instead of `commands:` and refuses to build without
   it. A model with a `Dockerfile` instead of `install.yml` cannot be built for GPU.

`ersilia test` (GPU-aware versions) checks the three pieces: `gpu:` present →
`main_gpu.py` must exist and run.sh must mention `ERSILIA_DEVICE` and `main_gpu.py`; it
warns when `commands:` and `gpu:` differ in lines other than GPU packages.

The reference implementation is `eos3wac`, branch `gpu`
(https://github.com/ersilia-os/eos3wac/tree/gpu). Its diff against `main` is the whole
change for a simple torch model (its metadata.yml change was accidental; ignore it).

## What you receive

- The **model ID** (`eos` + 4 characters).
- The **local path** to the cloned model repo. If it is missing, clone
  `https://github.com/ersilia-os/<model_id>` into the current directory.

`SKILL_DIR` below is this skill's folder. Scripts here use only the standard library.

## Principles

1. **The CPU model does not change.** `main.py`, the `commands:` section, checkpoints,
   `metadata.yml`, `run_columns.csv` and the example files stay byte-identical. With
   `ERSILIA_DEVICE` unset, the model produces exactly the output it produced before.
2. **Same science on both devices.** Same checkpoints and weights, same preprocessing,
   same batch size, same output header and order. GPU outputs may differ by float noise,
   nothing more. No `half()`, AMP or `torch.compile`.
3. **Fail loudly, never fall back.** `main_gpu.py` raises when CUDA is not visible, and
   a CUDA error during inference must stop the run — never become blank rows. A GPU
   image that silently writes empty or CPU results hides a broken deployment.
4. **Smallest diff that really runs on the GPU.** Start from a copy of `main.py` and
   change device lines. Restructure only when the model cannot run on CUDA otherwise
   (traced TorchScript, forked workers — see `references/frameworks.md`), and explain
   why in a comment.
5. **Shared code keeps its CPU default.** If the device is hard-coded in the model's own
   package, add a `device="cpu"` parameter and pass `DEVICE` from `main_gpu.py`. Never
   change what `main.py` gets by default.
6. **Do not commit or push.** Leave the changes on the `gpu` branch for the user.

## Workflow

### Step 0: Read the model

```bash
cd $REPO && git status && git branch -a && git log --oneline -3
cat model/framework/run.sh install.yml model/framework/code/main.py
ls model/framework/code model/checkpoints
```

**Checkpoints.** After a fresh clone, `model/checkpoints/` often holds only `.gitkeep`
(they are stored with eosvc). If it is empty, download them:
`eosvc download --path model/checkpoints` (eosvc is in the `ersilia` conda env if not on
PATH). This creates an untracked `.eosvc/` folder: leave it untracked, never commit it.

Stop and report to the user, without changing anything, when:

- the repo has a `Dockerfile` and no `install.yml`;
- `run.sh` is not the standard one-liner `python $1/code/main.py $2 $3`;
- **nothing in the model runs on a GPU** — scikit-learn, RDKit/Mordred descriptors,
  XGBoost/LightGBM/CatBoost, NumPy-only. Say which framework and that a GPU image would
  cost more and run no faster;
- a `gpu:` section, a `main_gpu.py`, or a `gpu` branch (local or `origin/gpu`) already
  exists — show it and ask.

Trace the **inference path only**: main.py, the modules it imports, the checkpoints it
loads and any subprocess it calls. Skip training/export scripts. Look for:

```bash
grep -nE "torch|tensorflow|keras|jax|onnxruntime|dgl|torch_geometric|chemprop|lightning|device|cuda|map_location|jit|no_cuda|--gpu|accelerator|Pool|ProcessPool|multiprocessing|fork|except" <files on the inference path>
```

Answer these before writing code (each has a section in `references/frameworks.md`):

- Which framework runs the model?
- Is the checkpoint a TorchScript file (`torch.jit.load`)? If so, is it traced with a
  hard-coded CPU device?
- Does inference run inside a worker pool (fork-based)? CUDA cannot run in forked children.
- Is inference wrapped in a broad `try/except` that returns blanks?

### Step 1: Branch

```bash
git checkout -b gpu
```

### Step 2: run.sh

Copy the template, do not write it by hand:

```bash
cp $SKILL_DIR/assets/run.sh $REPO/model/framework/run.sh
```

### Step 3: main_gpu.py

`cp main.py main_gpu.py`, then for torch:

- After the imports and path setup, add exactly (the smoke test in Step 5 relies on it):
  ```python
  DEVICE = "cuda"

  # fail loudly instead of silently running on CPU
  if not torch.cuda.is_available():
      raise RuntimeError("main_gpu.py requires a CUDA device, but torch cannot see one")
  ```
- Model to device: `model = ....to(DEVICE)`; keep `model.eval()`.
- `torch.load(..., map_location="cpu")` → `map_location=DEVICE`. TorchScript: see
  `references/frameworks.md` first — `map_location` does not fix a traced CPU device.
- Inputs to device: tokenizer outputs, tensors built from features, graph batches:
  `.to(DEVICE)`.
- Outputs back: every `.numpy()` on a model tensor becomes `.cpu().numpy()`
  (`.detach().cpu().numpy()` if it requires grad).
- **Errors.** If inference sits inside a `try/except` that turns failures into blank
  rows, keep that for bad inputs but let device errors through. Add once:
  ```python
  def _is_device_error(e):
      # CUDA / device errors must stop the run, not become blank rows
      return isinstance(e, torch.cuda.OutOfMemoryError) or "cuda" in str(e).lower()
  ```
  and at the top of each such `except Exception as e:` block: `if _is_device_error(e): raise`.
  (Name the exception if the original uses a bare `except Exception:`.)
- Worker pools, TorchScript, Lightning, chemprop, TF, JAX, ONNX, subprocess models:
  `references/frameworks.md`.
- Keep `BATCH_SIZE`, thread settings, seeds and everything else as in `main.py`.

Static check before running anything — each hit must be a CPU tensor or a fixed line:

```bash
grep -n "\.numpy()" model/framework/code/main_gpu.py | grep -v "\.cpu()"
grep -n '"cpu"\|torch.device(' model/framework/code/main_gpu.py
```

### Step 4: install.yml `gpu:` section

Build the CPU env first (Step 5) and read the **installed** versions:
`<env>/bin/pip list | grep -iE "torch|tensorflow|jax|onnx|dgl|scatter|sparse|cluster|pyg"`.
Another line can silently override a pin (eos8aa5: `torchdata 0.7.1` upgrades the
`torch 1.13.1` pin to 2.4.1). The `gpu:` section must reproduce what the CPU env really
runs; if installed ≠ pinned, use the installed version and tell the user the CPU pin is
ineffective.

Append `gpu:` after `commands:`: same lines, same order, copied verbatim (comments
included), except the GPU packages listed in `references/frameworks.md`. For torch ≥ 2.6:

```yaml
gpu:
    - ["pip", "torch", "2.7.1", "--index-url", "https://download.pytorch.org/whl/cu126"]
    - ["pip", "transformers", "4.56.2"]
```

- Drop the `+cpu` suffix; every line that uses the PyTorch CPU index
  (`--index-url`/`--extra-index-url .../whl/cpu`: torchvision, torchaudio, torchdata…)
  moves to the same CUDA index as torch, or it will reinstall a CPU torch.
- Pick one CUDA tag that exists for **every** CUDA package of the model (torch, DGL,
  PyG extensions). Tags per version: `references/frameworks.md`.
- Check each CUDA package exists **by listing the index**, not by downloading it
  (torch wheels are 1–2.5 GB):
  `curl -s https://download.pytorch.org/whl/<cu>/torch/ | grep -o "torch-<ver>+<cu>-cp<py>[^\"<]*" | sort -u`.
- Write changed lines in list form. Keep `python:` and `commands:` untouched.

### Step 5: Verify

**Env.** `conda create -y -n gpu_${MODEL}_tmp python=<python:>` (never start the env
name with the model ID: `ersilia delete` removes those), then:

```bash
python $SKILL_DIR/scripts/render_install.py install.yml commands <env>/bin/python gpu_${MODEL}_tmp | bash -e
```

**Input.** `model/framework/examples/run_input.csv` is often a few rows, below one batch.
Also make an input of at least 2–3 batches (repeat the example rows, add an invalid
SMILES) as `$WORK/input.csv`, and use both.

1. **CPU path unchanged** (required). Baseline = the original, not `run_output.csv`
   (that file may come from another machine):
   ```bash
   git stash -u      # back to the original (checkpoints are ignored, so they stay)
   env -u ERSILIA_DEVICE PATH=<env>/bin:$PATH bash model/framework/run.sh \
       model/framework $WORK/input.csv $WORK/orig.csv
   git stash pop     # always, even if the run failed
   env -u ERSILIA_DEVICE PATH=<env>/bin:$PATH bash model/framework/run.sh \
       model/framework $WORK/input.csv $WORK/cpu.csv
   python $SKILL_DIR/scripts/compare.py $WORK/orig.csv $WORK/cpu.csv     # must be exact
   ```
   Also compare `cpu.csv` on the examples with `run_output.csv` and report it as
   information (float noise there is pre-existing, not caused by you).
2. **run.sh selects main_gpu.py** (on a machine without GPU):
   `ERSILIA_DEVICE=gpu bash model/framework/run.sh ...` must stop with the RuntimeError
   and write no output.
3. **CPU smoke test of main_gpu.py.** Shows the copy runs and the science is unchanged
   (it cannot prove the `.to()`/`.cpu()` edits are complete — `.numpy()` works on CPU
   tensors; that is what the Step 3 static check is for):
   ```bash
   sed -e 's/^DEVICE = "cuda"/DEVICE = "cpu"/' \
       -e 's/if not torch.cuda.is_available():/if False:/' \
       model/framework/code/main_gpu.py > model/framework/code/_main_gpu_cpu.py
   <env>/bin/python model/framework/code/_main_gpu_cpu.py $WORK/input.csv $WORK/gpu_on_cpu.csv
   rm model/framework/code/_main_gpu_cpu.py
   python $SKILL_DIR/scripts/compare.py $WORK/cpu.csv $WORK/gpu_on_cpu.csv   # must be exact
   ```
   Adapt the `sed` for TF/JAX/ONNX checks.
4. **`gpu:` installs.** Build a second env from `gpu:` with `render_install.py ... gpu`
   (works without a GPU; CUDA wheels install anyway). Confirm the CUDA builds were kept
   (`python -c "import torch; print(torch.__version__, torch.version.cuda)"`) and no later
   line replaced them with a CPU build. Rerun step 3 in this env.
5. **On a GPU** (`nvidia-smi` works): with the `gpu:` env, run
   `ERSILIA_DEVICE=gpu bash model/framework/run.sh ...`, check `nvidia-smi` shows the
   process, then
   `python $SKILL_DIR/scripts/compare.py $WORK/cpu.csv $WORK/gpu.csv --atol 1e-4`
   (blanks, header and rows must still match). Report `max_abs_diff`.
   No GPU → say plainly that the GPU run is unverified.
6. Delete the scratch envs.

Optional, ask first: `ersilia test $MODEL --shallow --from_dir $REPO`.

### Step 6: Report

Short, to the user:

- changed files (`git diff --stat`) and the `gpu:` section, with how each CUDA package
  was checked to exist;
- main_gpu.py changes, one line per kind of edit, and why any restructuring was needed;
- verification: each step's result with `match` / `max_abs_diff`, or "not run: no GPU";
- issues found in the CPU model (ineffective pins, `run_output.csv` drift) — report,
  don't fix;
- suggested commit message: `Add GPU install and main_gpu.py, selected by ERSILIA_DEVICE=gpu`;
- the GPU image is built by Ersilia's `Dockerfile.pip-gpu` / `Dockerfile.conda-gpu`.

## Do not

- Edit eos-template, `main.py`, `commands:`, `metadata.yml`, checkpoints or examples.
- Re-export or convert checkpoints.
- Hand-write or "improve" run.sh — copy `assets/run.sh`.
- Add a CPU fallback, or let `except` blocks swallow CUDA errors.
- Change batch sizes or precision for speed — that is a separate task.
- Commit, push or open a PR without the user asking.
