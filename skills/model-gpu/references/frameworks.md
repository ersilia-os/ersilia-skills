# Frameworks: what changes in main_gpu.py and in `gpu:`

Match the version the CPU env really installs (Step 4 of SKILL.md). If that version has
no CUDA build, stop and ask the user — do not upgrade on your own.

## install.yml: CPU line → GPU line

| In `commands:` | In `gpu:` |
|---|---|
| `torch==X+cpu` / `torch X` with `.../whl/cpu` index, or plain `torch X` | `["pip", "torch", "X", "--index-url", "https://download.pytorch.org/whl/<cu>"]` |
| **any other line** using `--index-url` / `--extra-index-url .../whl/cpu` (torchvision, torchaudio, torchdata, …) | same package and version, same `<cu>` index as torch (else it reinstalls a CPU torch) |
| `tensorflow X` / `tensorflow-cpu X` (X ≥ 2.14) | `["pip", "tensorflow[and-cuda]", "X"]` |
| `tensorflow` < 2.14 | stop: needs system CUDA libraries in the image; ask |
| `jax[cpu]` / `jax X` (X ≥ 0.4.26) | `["pip", "jax[cuda12]", "X"]` |
| `onnxruntime X` | `["pip", "onnxruntime-gpu", "X"]` (CUDA 12 build is the default from 1.19) |
| `dgl X` pip wheel from a CPU URL | only if graphs go to the GPU: same version, `-f https://data.dgl.ai/wheels/torch-<T>/<cu>/repo.html` |
| `conda install -c dglteam dgl=X` | only if graphs go to the GPU: `["conda", "install", "-c", "dglteam/label/<cu>", "dgl=X", "-y"]` |
| `torch-scatter` / `torch-sparse` / `torch-cluster` / `pyg-lib` with `-f .../torch-<T>+cpu.html` | same version without the `+ptXXXcpu` suffix, `-f https://data.pyg.org/whl/torch-<T>+<cu>.html` |
| conda `pytorch` + `cpuonly` | the pip torch line above; drop `cpuonly` |
| everything else (transformers, rdkit, pandas, numpy, torch_geometric, lightning, chemprop, dgllife, ersilia-pack-utils, …) | unchanged |

**DGL / PyG used only for featurization.** If graphs are built on CPU and only plain
tensors reach the model (e.g. eos8aa5), keep the CPU build — it works with a CUDA torch
and avoids CUDA-tag conflicts. Change it only when DGL/PyG objects are moved `.to(DEVICE)`.

### PyTorch CUDA tags

| torch | CUDA wheel tags (prefer bold) |
|---|---|
| ≥ 2.6 | **cu126** (also cu118/cu124/cu128 depending on minor) |
| 2.4 – 2.5 | **cu124**, cu121, cu118 |
| 2.2 – 2.3 | **cu121**, cu118 |
| 2.1 | **cu121**, cu118 |
| 2.0 | **cu118**, cu117 |
| 1.13 | **cu117**, cu116 |
| 1.12 | **cu116**, cu113 |
| older | stop and ask |

When DGL or PyG must be CUDA builds too, choose a tag all of them have. DGL CUDA builds
only exist for some tags (DGL 2.0.0: cu117/cu118/cu121, no cu124).

### Checking a build exists (list, don't download)

```bash
curl -s https://download.pytorch.org/whl/<cu>/torch/ | grep -o "torch-<ver>+<cu>-cp<py>[^\"<]*" | sort -u
curl -s https://download.pytorch.org/whl/<cu>/<pkg>/ | grep -o "<pkg>-<ver>[^\"<]*cp<py>[^\"<]*" | sort -u
curl -s "https://data.pyg.org/whl/torch-<T>+<cu>.html" | grep -o "torch_scatter-<ver>[^\"<]*cp<py>[^\"<]*"
curl -s https://data.dgl.ai/wheels/torch-<T>/<cu>/repo.html | grep -o "dgl-<ver>[^\"<]*cp<py>[^\"<]*"
conda search -c dglteam/label/<cu> "dgl=<ver>"
```

`pip download` pulls the whole wheel (0.8–2.5 GB): avoid it.

## main_gpu.py edits by framework

### PyTorch / Hugging Face (eos3wac pattern)

```python
model = AutoModel.from_pretrained(checkpoints_dir).to(DEVICE)
inputs = tokenizer(batch, ..., return_tensors="pt").to(DEVICE)
embeddings = out.last_hidden_state[:, 0, :].cpu().numpy()
```

- `torch.load(path, map_location="cpu")` → `map_location=DEVICE`.
- `torch.tensor(x)` / `torch.from_numpy(x)` fed to the model → `.to(DEVICE)`.
- Hidden `.numpy()` calls in helper functions also need `.cpu()`.

### TorchScript checkpoints (`torch.jit.load`)

A **scripted** module moves to CUDA with `.to(DEVICE)`. A **traced** module may have
the export device baked into its graph (`torch.zeros(..., device=torch.device("cpu"))`),
and `map_location` / `.to()` do not change it. Check:

```bash
python -c "import torch; m=torch.jit.load('<ckpt>', map_location='cpu'); print(m.code)" | grep -n 'device("cpu")'
```

No hit → `torch.jit.load(path, map_location=DEVICE)` is enough. Hit → do **not**
re-export the checkpoint (checkpoints stay unchanged). Instead, in main_gpu.py, build
the eager module from the model's own source code with the same config the export
script used, `load_state_dict(ts.state_dict(), strict=True)`, `.eval().to(DEVICE)`.
Before relying on it, check on CPU that the eager module gives exactly the trace's
output (the Step 5.3 smoke test does this). Comment why.

### Worker pools (multiprocessing / ProcessPoolExecutor, fork)

CUDA cannot be used in a forked child, and a CUDA context created before forking breaks
the children. If main.py runs inference inside pool workers:

- keep the pool for CPU work (parsing, featurization) and have workers return inputs
  as NumPy arrays, inside the original per-molecule `try/except`;
- run the model in the parent process on `DEVICE`, without a per-molecule try/except
  (or with `_is_device_error` re-raised);
- keep worker count, start method and batch logic as they were.

Do not switch to `spawn` with a model per worker: every worker would load the model on
the GPU.

### PyTorch Geometric / DGL on the GPU

`batch = batch.to(DEVICE)` (PyG `Data`/`Batch`), `g = g.to(DEVICE)` (DGL graph), plus
separately built feature tensors. Then the DGL/PyG line in `gpu:` must be a CUDA build.

### Chemprop

- v1 (`chemprop.args.PredictArgs`, `make_predictions`): drop `--no_cuda` / set
  `no_cuda=False`, add `--gpu 0` if args are built as a list.
- v2 (Lightning): `Trainer(accelerator="gpu", devices=1, ...)`; load with
  `map_location=DEVICE` or let Lightning move it.

### PyTorch Lightning generally

`Trainer(accelerator="cpu")` → `accelerator="gpu", devices=1`. Keep everything else.

### TensorFlow / Keras

TF uses the GPU automatically when one is visible. main_gpu.py usually only adds:

```python
gpus = tf.config.list_physical_devices("GPU")
if not gpus:
    raise RuntimeError("main_gpu.py requires a CUDA device, but TensorFlow cannot see one")
```

and removes CPU pinning from the copy (`os.environ["CUDA_VISIBLE_DEVICES"] = "-1"`,
`with tf.device("/CPU:0")`). Smoke test: run the copy with `CUDA_VISIBLE_DEVICES=-1`
and the check replaced by `if False:`.

### JAX

Raise unless `jax.default_backend() == "gpu"`; remove `JAX_PLATFORM_NAME=cpu` /
`JAX_PLATFORMS=cpu` from the copy.

### ONNX Runtime

`ort.InferenceSession(path, providers=["CUDAExecutionProvider"])`; raise if
`"CUDAExecutionProvider" not in ort.get_available_providers()`.

### Subprocess-based models

If main.py shells out to the original repo's script, flip its device flag in the
command main_gpu.py builds (`--device cuda`, `--gpu 0`, removing `--cpu`), and make
main_gpu.py fail when the subprocess fails. Do not edit the original script unless the
device is hard-coded there (Principle 5).

## No GPU benefit — stop and report

scikit-learn, RDKit / Mordred / descriptor-only models, XGBoost / LightGBM / CatBoost
inference, KNN over small reference sets, pure NumPy. Tell the user which framework it
is and that a GPU image would not make it faster.
