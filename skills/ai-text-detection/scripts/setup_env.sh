#!/usr/bin/env bash
# One-time setup for the model-based detectors of ai-text-detection.
# Creates the conda env `ai-text-detection` and downloads the two models (about 6 GB; resumes if interrupted).
# Run only after the user has agreed to the download (SKILL.md, pre-flight step 4).
# Idempotent: re-running only fills in what is missing. Nothing is uploaded anywhere.
set -euo pipefail
ENV=ai-text-detection
CONDA_BASE=$(conda info --base)
# shellcheck disable=SC1091
source "$CONDA_BASE/etc/profile.d/conda.sh"
if ! conda env list | awk '{print $1}' | grep -qx "$ENV"; then
  conda create -y -q -n "$ENV" -c conda-forge --override-channels python=3.11
fi
conda activate "$ENV"
pip install -q --upgrade pip
pip install -q "torch>=2.3" "transformers>=4.45,<5" "accelerate>=0.30" "huggingface_hub>=0.24" \
  safetensors numpy requests pymupdf python-docx
HF_HUB_DISABLE_XET=1 python - <<'PY'
from huggingface_hub import snapshot_download
for repo in ("Qwen/Qwen2.5-1.5B", "Qwen/Qwen2.5-1.5B-Instruct"):
    path = snapshot_download(repo, allow_patterns=["*.json", "*.safetensors", "*.txt", "merges.txt", "vocab.json"])
    print("model ready:", repo, path)
import torch
print("torch", torch.__version__, "mps", torch.backends.mps.is_available())
PY
echo "env ready: conda run -n $ENV python ..."
