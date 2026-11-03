---
name: model-gpu
description: Adapts an Ersilia Model Hub model so it can also run on a GPU, without touching its CPU behaviour or eos-template. The user names the model (ID and local path). On a `gpu` branch of the model repo, the skill makes exactly three changes: replaces model/framework/run.sh with the fixed template that runs main_gpu.py when ERSILIA_DEVICE=gpu (set by ersilia-pack in GPU images) and main.py otherwise; writes model/framework/code/main_gpu.py, a copy of main.py that loads the model and its inputs on CUDA and fails loudly when no GPU is visible; and adds a `gpu:` section to install.yml with the same pins as `commands:` but CUDA builds of the GPU frameworks (torch cu126 wheels, tensorflow[and-cuda], jax[cuda12], onnxruntime-gpu, DGL/PyG CUDA wheels). Stops and reports when the model has nothing that runs on a GPU (scikit-learn, RDKit-only, XGBoost/LightGBM inference). Verifies that the CPU path is unchanged, smoke-tests main_gpu.py on CPU, and compares GPU against CPU outputs when a GPU is available. Does not commit or push. Triggers include "make eosXXXX run on GPU", "add GPU support to eosXXXX", "gpu version of this model", "create main_gpu.py", "add the gpu section to install.yml", "adapt eosXXXX for gpu", "/model-gpu".
argument-hint: <model_id> <model_path>
---

# Ersilia Model GPU adaptation

GPU support lives in each model, not in eos-template. **Never edit eos-template for
GPU.** A model supports GPU when it has three things:

1. `model/framework/run.sh` — the fixed template in `assets/run.sh`. It picks
   `main_gpu.py` when the env var `ERSILIA_DEVICE` is `gpu` and `main.py` otherwise.
   ersilia-pack sets `ERSILIA_DEVICE` in the images it builds with `--device gpu`.
2. `model/framework/code/main_gpu.py` — `main.py` running on CUDA.
3. A `gpu:` section in `install.yml`, same format as `commands:`. `ersilia_pack
   --device gpu` installs `gpu:` instead of `commands:`; without the section it refuses
   to build. A model with a `Dockerfile` instead of `install.yml` cannot be built for GPU.

The reference implementation is `eos3wac`, branch `gpu`
(https://github.com/ersilia-os/eos3wac/tree/gpu). Its diff against `main` is the
whole change for a typical torch model.

## What you receive

- The **model ID** (`eos` + 4 characters).
- The **local path** to the cloned model repo. If it is missing, clone
  `https://github.com/ersilia-os/<model_id>` into the current directory.

## Principles

1. **The CPU model does not change.** `main.py`, the `commands:` section, checkpoints,
   `metadata.yml`, `run_columns.csv` and the example files stay byte-identical. With
   `ERSILIA_DEVICE` unset, the model must produce exactly the output it produced before.
   (The eos3wac branch also reformatted `metadata.yml` and moved `Release` back to
   v1.0.0 — that was accidental; do not reproduce it.)
2. **Same science on both devices.** `main_gpu.py` differs from `main.py` only in
   *where* tensors live: same checkpoints, same preprocessing, same batch size, same
   output header and order. GPU outputs are allowed float noise, nothing more.
3. **Fail loudly, never fall back.** `main_gpu.py` raises when CUDA is not visible.
   A GPU image silently running on CPU hides a broken deployment.
4. **Smallest diff.** Copy `main.py` and change only device lines. Each change is
   readable at a glance; add a short comment only where the reason is not obvious.
5. **Shared code keeps its CPU default.** If the device is hard-coded inside the
   model's own package (e.g. `device = torch.device("cpu")` in `code/<pkg>/model.py`),
   add a `device="cpu"` parameter and pass `DEVICE` from `main_gpu.py`. Never change
   what `main.py` gets by default.
6. **Do not commit or push.** Leave the changes on the `gpu` branch for the user.

## Workflow

### Step 0: Read the model

```bash
cd $REPO && git status && git log --oneline -3
cat model/framework/run.sh install.yml model/framework/code/main.py
ls model/framework/code model/checkpoints
```

Stop and report to the user, without changing anything, when:

- the repo has a `Dockerfile` and no `install.yml` (ersilia-pack refuses GPU there);
- `run.sh` is not the standard one-liner `python $1/code/main.py $2 $3` (ask how to
  handle it; the template assumes it);
- **nothing in the model runs on a GPU** — the inference is scikit-learn, RDKit/Mordred
  descriptors, XGBoost/LightGBM/CatBoost on a few thousand rows, or similar. Say which
  framework it uses and that a GPU image would cost more and run no faster;
- a `gpu:` section or `main_gpu.py` already exists (show it and ask).

Find the framework and every place a device is set. Search the entry point **and** the
model's own code it imports, and any subprocess it calls:

```bash
grep -rnE "torch|tensorflow|keras|jax|onnxruntime|dgl|torch_geometric|chemprop|lightning|device|cuda|map_location|no_cuda|--gpu|accelerator" model/framework/code
```

Read `references/frameworks.md` for the framework found.

### Step 1: Branch

```bash
git checkout -b gpu      # or `git checkout gpu` if it exists and is clean
```

### Step 2: run.sh

Copy the template, do not write it by hand:

```bash
cp $SKILL_DIR/assets/run.sh $REPO/model/framework/run.sh
```

### Step 3: main_gpu.py

`cp main.py main_gpu.py`, then edit only what puts work on the GPU. For torch:

- After the imports and path setup, add:
  ```python
  DEVICE = "cuda"

  # fail loudly instead of silently running on CPU
  if not torch.cuda.is_available():
      raise RuntimeError("main_gpu.py requires a CUDA device, but torch cannot see one")
  ```
- Model to device: `model = ....to(DEVICE)`; keep `model.eval()`.
- `torch.load(..., map_location="cpu")` → `map_location=DEVICE` (or keep CPU and
  `.to(DEVICE)` the module afterwards).
- Inputs to device: tokenizer outputs `.to(DEVICE)`, tensors built from features
  `.to(DEVICE)`, graph batches `.to(DEVICE)`.
- Outputs back: every `.numpy()` on a model tensor becomes `.cpu().numpy()`
  (`.detach().cpu().numpy()` if it requires grad). `float(t)` / `t.item()` already work.
- Hard-coded devices in the model's package: see Principle 5.
- CLI-style models (argparse namespaces, `no_cuda=True`, `--gpu`, Lightning
  `accelerator="cpu"`): flip only those flags.
- Keep `BATCH_SIZE`, thread settings, seeds and everything else as in `main.py`.

Other frameworks: `references/frameworks.md`. Use the `DEVICE` constant (not
`"cuda"` repeated) so the Step 5 smoke test can swap it with one `sed`.

### Step 4: install.yml `gpu:` section

Append a `gpu:` section after `commands:`, same list, same order, same pins. Change only
the packages that have a CUDA build (table in `references/frameworks.md`). For torch:

```yaml
commands:
    - "pip install torch==2.7.1+cpu --index-url https://download.pytorch.org/whl/cpu"
    - ["pip", "transformers", "4.56.2"]
gpu:
    - ["pip", "torch", "2.7.1", "--index-url", "https://download.pytorch.org/whl/cu126"]
    - ["pip", "transformers", "4.56.2"]
```

- Same torch version; drop the `+cpu` suffix; index `cu126` (torch ≥ 2.6). Older torch
  has no cu126 wheels: use the CUDA tag listed in `references/frameworks.md`.
- Write the changed lines in list form `["pip", pkg, version, extra args...]`.
- Keep `python:` and `commands:` untouched. Leave everything else verbatim, including
  string commands.
- Packages that only depend on torch (transformers, torch-free libraries) stay as they are.

### Step 5: Verify

Build a scratch env from the `commands:` section (CPU) — `conda create -n gpu_$MODEL_tmp
python=<python:>` then the pinned installs. Do not start the env name with the model ID
(`ersilia delete` removes those). Use `model/framework/examples/run_input.csv` as input.

1. **CPU path unchanged** (required). With `ERSILIA_DEVICE` unset:
   ```bash
   env -u ERSILIA_DEVICE PATH=<env>/bin:$PATH bash model/framework/run.sh model/framework \
       model/framework/examples/run_input.csv $WORK/cpu.csv
   python $SKILL_DIR/scripts/compare.py model/framework/examples/run_output.csv $WORK/cpu.csv
   ```
   `scripts/compare.py` prints a JSON report (`match`, `max_abs_diff`); default is exact
   equality, `--atol` allows float noise. The new run.sh
   still runs the untouched main.py, so a difference here means run.sh is wrong — or
   the model already differed from its `run_output.csv` before (check with
   `git stash`, rerun, `git stash pop`, and report it as pre-existing).
2. **GPU switch fails loudly without a GPU** (when the machine has none):
   `ERSILIA_DEVICE=gpu bash model/framework/run.sh ...` must stop with the RuntimeError
   from main_gpu.py, proving run.sh selected it.
3. **CPU smoke test of main_gpu.py** — checks the `.cpu()` / `.to()` edits:
   ```bash
   sed -e 's/^DEVICE = "cuda"/DEVICE = "cpu"/' \
       -e 's/if not torch.cuda.is_available():/if False:/' \
       model/framework/code/main_gpu.py > model/framework/code/_main_gpu_cpu.py
   <env>/bin/python model/framework/code/_main_gpu_cpu.py <input> $WORK/gpu_on_cpu.csv
   rm model/framework/code/_main_gpu_cpu.py
   ```
   `python $SKILL_DIR/scripts/compare.py $WORK/cpu.csv $WORK/gpu_on_cpu.csv` should match
   exactly. Adapt the `sed` for TF/JAX checks.
4. **On a GPU** (`nvidia-smi` works): build a second env from the `gpu:` section, run
   with `ERSILIA_DEVICE=gpu`, confirm with `nvidia-smi` that the process used the GPU,
   and compare with `python $SKILL_DIR/scripts/compare.py $WORK/cpu.csv $WORK/gpu.csv --atol 1e-4`
   (float32 noise on embeddings and probabilities; blanks, header and row count must
   still match). Report `max_abs_diff`.
   If no GPU is available, say so plainly in the report — the GPU run is unverified.
5. Delete the scratch env(s).

Optional, ask first: `ersilia test $MODEL --shallow --from_dir $REPO` to confirm the
served CPU model still passes.

### Step 6: Report

Short, to the user:

- the three changed files with the key lines (`git diff --stat` and the `gpu:` section);
- what was changed in main_gpu.py (one line per kind of edit) and any shared-code
  parameter added;
- verification results: CPU unchanged (yes/no), smoke test, GPU comparison with
  `max_abs_diff` or "not run: no GPU here";
- suggested commit message: `Add GPU install and main_gpu.py, selected by ERSILIA_DEVICE=gpu`;
- how to build the GPU image: `ersilia_pack --repo_path $REPO --bundles_repo_path <dir> --device gpu`.

## Do not

- Edit eos-template, `main.py`, `commands:`, `metadata.yml`, checkpoints or examples.
- Hand-write or "improve" run.sh — copy `assets/run.sh`.
- Add a CPU fallback to `main_gpu.py`, or `torch.cuda.is_available()` switches to `main.py`.
- Change batch sizes, precision (no `half()`/AMP), or add `torch.compile` — that changes
  outputs; speed work is a separate task.
- Commit, push or open a PR without the user asking.
