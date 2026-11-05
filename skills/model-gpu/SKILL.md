---
name: model-gpu
description: Adapts the code of an Ersilia Model Hub model so it can also run on a GPU, without touching its CPU behaviour or eos-template. The user names the model (ID and local path). On a `gpu` branch of the model repo, the skill makes exactly three changes: replaces model/framework/run.sh with the fixed template that runs main_gpu.py when ERSILIA_DEVICE=gpu (set by Ersilia's GPU Dockerfiles) and main.py otherwise; writes model/framework/code/main_gpu.py, a copy of main.py that runs the model on CUDA and fails loudly when no GPU is visible or a CUDA error occurs; and adds a `gpu:` section to install.yml with the same packages as `commands:` but CUDA builds of the GPU frameworks (torch CUDA wheels, tensorflow[and-cuda], jax[cuda12], onnxruntime-gpu, DGL/PyG CUDA builds). Handles the hard cases: traced TorchScript checkpoints with a hard-coded CPU device, inference inside forked worker pools, broad try/except that would hide CUDA errors, and torch pins overridden by other packages. Stops and reports when the model has nothing that runs on a GPU (scikit-learn, RDKit-only, XGBoost/LightGBM inference). Runs tests only when the machine has a GPU (GPU output compared with CPU output); without a GPU it builds and runs nothing and says the change is untested. Self-contained. Does not commit or push. Triggers include "make eosXXXX run on GPU", "add GPU support to eosXXXX", "gpu version of this model", "create main_gpu.py", "add the gpu section to install.yml", "adapt eosXXXX for gpu", "/model-gpu".
argument-hint: <model_id> <model_path>
---

# Ersilia Model GPU adaptation

This skill adapts a model's code to run on a GPU, and nothing more. GPU support lives in
each model, not in eos-template. **Never edit eos-template for GPU.** A model supports
GPU when it has three things:

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

1. **Adapt the code, nothing more.** Three files change: run.sh, main_gpu.py (new) and
   install.yml (`gpu:` appended). `main.py`, `commands:`, checkpoints, `metadata.yml`,
   `run_columns.csv` and the examples stay byte-identical, so the CPU model is unchanged.
2. **No GPU, no tests.** Check `nvidia-smi` once at the start. Without a GPU, do not
   build envs, install packages or run the model — anything run there would fail or
   prove nothing about the GPU. Say the change is untested on GPU.
3. **Same science on both devices.** Same checkpoints and weights, same preprocessing,
   same batch size, same output header and order. No `half()`, AMP or `torch.compile`.
4. **Fail loudly, never fall back.** `main_gpu.py` raises when CUDA is not visible, and
   a CUDA error during inference must stop the run — never become blank rows.
5. **Smallest diff that really runs on the GPU.** Start from a copy of `main.py` and
   change device lines. Restructure only when the model cannot run on CUDA otherwise
   (traced TorchScript, forked workers — see `references/frameworks.md`), and explain
   why in a comment.
6. **Shared code keeps its CPU default.** If the device is hard-coded in the model's own
   package, add a `device="cpu"` parameter and pass `DEVICE` from `main_gpu.py`. Never
   change what `main.py` gets by default.
7. **Do not commit or push.** Leave the changes on the `gpu` branch for the user.

## Workflow

### Step 0: Read the model

```bash
nvidia-smi -L            # GPU present? decides whether Step 5 runs
cd $REPO && git status && git branch -a && git log --oneline -3
cat model/framework/run.sh install.yml model/framework/code/main.py
ls model/framework/code model/checkpoints
```

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
- Is the checkpoint a TorchScript file (`torch.jit.load`)? If so, does its code have a
  hard-coded CPU device? (Read it from the zip, no torch needed — see frameworks.md. If
  `model/checkpoints/` is empty after a clone, `eosvc download --path model/checkpoints`
  first; leave the `.eosvc/` folder it creates untracked.)
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

- After the imports and path setup, add:
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

Review the result by reading it (no execution). Each hit must be a CPU tensor or fixed:

```bash
python -m py_compile model/framework/code/main_gpu.py
grep -n "\.numpy()" model/framework/code/main_gpu.py | grep -v "\.cpu()"
grep -n '"cpu"\|torch.device(' model/framework/code/main_gpu.py
```

### Step 4: install.yml `gpu:` section

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
- **Is the torch pin what really gets installed?** A later line can require another
  torch and silently replace it (eos8aa5: `torchdata 0.7.1` needs `torch>=2`, so the
  `torch 1.13.1` pin ends up as 2.4.1). For every package in `commands:` that depends on
  torch, read its requirement without installing it:
  `curl -s https://pypi.org/pypi/<pkg>/<ver>/json | python -c "import json,sys; print([r for r in json.load(sys.stdin)['info']['requires_dist'] or [] if r.startswith('torch')])"`.
  If it conflicts with the pin, stop and ask the user which torch version `gpu:` should
  use, and mention that the CPU pin is ineffective.
- Pick one CUDA tag that exists for **every** CUDA package of the model (torch, DGL,
  PyG extensions). Tags per version: `references/frameworks.md`.
- Check each CUDA package exists **by listing the index**, not by downloading it:
  `curl -s https://download.pytorch.org/whl/<cu>/torch/ | grep -o "torch-<ver>+<cu>-cp<py>[^\"<]*" | sort -u`.
- Write changed lines in list form. Keep `python:` and `commands:` untouched.

### Step 5: Test — only with a GPU

**No GPU** (`nvidia-smi` failed in Step 0): skip this step entirely. Do not build envs,
install packages or run the model. Go to the report and say the change is untested.

**GPU present:**

1. Build two scratch envs (never start the name with the model ID: `ersilia delete`
   removes those):
   ```bash
   for s in commands gpu; do
     conda create -y -n gpu_${MODEL}_$s python=<python:>
     python $SKILL_DIR/scripts/render_install.py install.yml $s <env_$s>/bin/python gpu_${MODEL}_$s | bash -e
   done
   ```
   In the `gpu` env check that CUDA builds were kept:
   `python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"`.
2. Input: `model/framework/examples/run_input.csv` plus a file of at least 2–3 batches
   (repeat the example rows, add an invalid SMILES) as `$WORK/input.csv`.
3. Run both devices through run.sh:
   ```bash
   env -u ERSILIA_DEVICE PATH=<env_commands>/bin:$PATH bash model/framework/run.sh model/framework $WORK/input.csv $WORK/cpu.csv
   ERSILIA_DEVICE=gpu    PATH=<env_gpu>/bin:$PATH      bash model/framework/run.sh model/framework $WORK/input.csv $WORK/gpu.csv
   ```
   While the GPU run is going, `nvidia-smi` must show the process.
4. Compare:
   `python $SKILL_DIR/scripts/compare.py $WORK/cpu.csv $WORK/gpu.csv --atol 1e-4`
   (float noise allowed; blanks, header and row count must match). Report `match` and
   `max_abs_diff`. More blanks on GPU than on CPU means errors are being swallowed.
5. Delete the scratch envs.

### Step 6: Report

Short, to the user:

- changed files (`git diff --stat`) and the `gpu:` section, with how each CUDA package
  was checked to exist;
- main_gpu.py changes, one line per kind of edit, and why any restructuring was needed;
- tests: GPU vs CPU `match` / `max_abs_diff`, or **"not tested: no GPU on this machine"**
  plus the Step 5 commands to run on a GPU machine;
- issues found in the CPU model (ineffective pins) — report, don't fix;
- suggested commit message: `Add GPU install and main_gpu.py, selected by ERSILIA_DEVICE=gpu`.

## Do not

- Edit eos-template, `main.py`, `commands:`, `metadata.yml`, checkpoints or examples.
- Run, install or build anything to test when there is no GPU.
- Re-export or convert checkpoints.
- Hand-write or "improve" run.sh — copy `assets/run.sh`.
- Add a CPU fallback, or let `except` blocks swallow CUDA errors.
- Change batch sizes or precision for speed — that is a separate task.
- Commit, push or open a PR without the user asking.
