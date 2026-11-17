#!/usr/bin/env bash
# One-time setup of the small conda env `ai-text-detection` (a few tens of MB):
# pymupdf and python-docx to read PDF and Word files, Playwright to drive the user's
# installed Google Chrome for the web detectors. No language models are downloaded.
# Run only after the user has agreed (SKILL.md, pre-flight). Idempotent.
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
pip install -q pymupdf python-docx playwright
python -c "import pymupdf, docx, playwright; print('env ready: pymupdf, python-docx, playwright (uses the installed Google Chrome)')"
