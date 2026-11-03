# Frameworks: what changes in main_gpu.py and in `gpu:`

Keep the version pinned in `commands:` in every case. If the pinned version has no CUDA
build, stop and ask the user — do not upgrade on your own (it would change the CPU
science the GPU output is compared against).

## install.yml: CPU line → GPU line

| Package in `commands:` | Line in `gpu:` |
|---|---|
| `torch==X+cpu --index-url .../whl/cpu`, or plain `torch X` | `["pip", "torch", "X", "--index-url", "https://download.pytorch.org/whl/<cu>"]` |
| `torchvision` / `torchaudio` from the CPU index | same version, same `<cu>` index as torch |
| `tensorflow X` / `tensorflow-cpu X` (X ≥ 2.14) | `["pip", "tensorflow[and-cuda]", "X"]` |
| `tensorflow` < 2.14 | stop: needs system CUDA libraries in the image; ask |
| `jax[cpu]` / `jax X` (X ≥ 0.4.26) | `["pip", "jax[cuda12]", "X"]` |
| `onnxruntime X` | `["pip", "onnxruntime-gpu", "X"]` (CUDA 12 build is the default from 1.19) |
| `dgl X` from a CPU wheel URL | same version, `-f https://data.dgl.ai/wheels/torch-<T>/<cu>/repo.html` matching the torch minor version |
| `torch-scatter` / `torch-sparse` / `torch-cluster` / `pyg-lib` | same version, `-f https://data.pyg.org/whl/torch-<torch>+<cu>.html` |
| conda `pytorch` + `cpuonly` | replace with the pip torch line above; drop `cpuonly` |
| everything else (transformers, rdkit, pandas, numpy, torch_geometric, lightning, chemprop, ersilia-pack-utils, …) | unchanged |

PyTorch CUDA tag `<cu>` by torch version (use the one in bold):

| torch | CUDA wheel tags |
|---|---|
| ≥ 2.6 | **cu126** (also cu118/cu124/cu128 depending on minor) |
| 2.4 – 2.5 | **cu124**, cu121, cu118 |
| 2.2 – 2.3 | **cu121**, cu118 |
| 2.1 | **cu121**, cu118 |
| 2.0 | **cu118**, cu117 |
| 1.13 | **cu117**, cu116 |
| 1.12 | **cu116**, cu113 |
| older | stop and ask |

Check the wheel exists before writing it:
`pip download --no-deps -d /tmp/x "torch==X" --index-url https://download.pytorch.org/whl/<cu> --python-version <py> --only-binary=:all: --platform manylinux_2_28_x86_64`
(or open `https://download.pytorch.org/whl/<cu>/torch/` and look for `X+<cu>`).

## main_gpu.py edits by framework

### PyTorch / Hugging Face (eos3wac pattern)

```python
DEVICE = "cuda"
if not torch.cuda.is_available():
    raise RuntimeError("main_gpu.py requires a CUDA device, but torch cannot see one")

model = AutoModel.from_pretrained(checkpoints_dir).to(DEVICE)
inputs = tokenizer(batch, ..., return_tensors="pt").to(DEVICE)
embeddings = out.last_hidden_state[:, 0, :].cpu().numpy()
```

- `torch.load(path, map_location="cpu")` → `map_location=DEVICE`.
- `torch.tensor(x)` / `torch.from_numpy(x)` fed to the model → add `.to(DEVICE)`.
- Hidden `.numpy()` calls in helper functions also need `.cpu()`.
- Models built in the model's own package with `device` attributes: pass `DEVICE` in.

### PyTorch Geometric / DGL

- `batch = batch.to(DEVICE)` (PyG `Data`/`Batch`), `g = g.to(DEVICE)` (DGL graph),
  node/edge feature tensors too if built separately.
- DGL CPU wheels cannot run CUDA graphs: the `gpu:` dgl line must be the CUDA wheel.

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

and removes CPU pinning from the copy: `os.environ["CUDA_VISIBLE_DEVICES"] = "-1"`,
`with tf.device("/CPU:0")`. Smoke test: run the copy with `CUDA_VISIBLE_DEVICES=-1`
and the check replaced by `if False:`.

### JAX

Check `jax.default_backend() == "gpu"` (raise otherwise); remove
`JAX_PLATFORM_NAME=cpu` / `JAX_PLATFORMS=cpu` from the copy.

### ONNX Runtime

`ort.InferenceSession(path, providers=["CUDAExecutionProvider"])` and raise if
`"CUDAExecutionProvider" not in ort.get_available_providers()`.

### Subprocess-based models

If main.py shells out to the original repo's script, flip its device flag in the
command built by main_gpu.py (`--device cuda`, `--gpu 0`, removing `--cpu`). Do not
edit the original script unless the device is hard-coded there (Principle 5).

## No GPU benefit — stop and report

scikit-learn, RDKit / Mordred / descriptor-only models, XGBoost / LightGBM / CatBoost
inference, KNN over small reference sets, pure NumPy. Tell the user which framework
it is and that a GPU image would not make it faster.
