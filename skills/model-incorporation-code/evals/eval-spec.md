# Evaluation — model-incorporation-code

Run the skill on each model below, then manually verify the checklist.
Ground truth is the real incorporated repo on GitHub.

---

## eos2r5a — Retrosynthetic Accessibility Score

| | |
|---|---|
| Type | Annotation, 1 output |
| Source repo | https://github.com/reymond-group/RAscore |
| Ground truth | https://github.com/ersilia-os/eos2r5a |

**Verify:**
- [ ] `main.py` runs on 3 SMILES without error
- [ ] `ra_score` output values match ground truth `run_output.csv` within 1%
- [ ] `run_columns.csv`: column `ra_score`, type `float`, direction `high`
- [ ] `ersilia_pack_utils` used in `main.py`
- [ ] `model/checkpoints/` contains the XGB model files
- [ ] `install.yml` has all deps pinned

---

## eos6oli — Aqueous Solubility

| | |
|---|---|
| Type | Annotation, 1 output |
| Source repo | https://github.com/gnina/SolTranNet |
| Ground truth | https://github.com/ersilia-os/eos6oli |

**Verify:**
- [ ] `main.py` runs on 3 SMILES without error
- [ ] `solubility` output values match ground truth `run_output.csv` within 1%
- [ ] `run_columns.csv`: column `solubility`, type `float`, direction `low`
- [ ] `ersilia_pack_utils` used in `main.py`
- [ ] No checkpoints needed — `model/checkpoints/` left empty
- [ ] `install.yml` has all deps pinned

---

## eos4ywv — MACAW Molecular Representation

| | |
|---|---|
| Type | Representation, 100 dims |
| Source repo | https://github.com/RekerLab/MACAW |
| Ground truth | https://github.com/ersilia-os/eos4ywv |

**Verify:**
- [ ] `main.py` runs on 3 SMILES without error
- [ ] Output values match ground truth `run_output.csv` within 1% (100 floats × 3 rows)
- [ ] `run_columns.csv`: 100 columns named `feat_00`…`feat_99`, type `float`, direction empty
  _(ground truth uses `dim_`; `feat_` is the preferred prefix for new work, so either is
  acceptable here — do not fail the eval on the prefix alone)_
- [ ] `ersilia_pack_utils` used in `main.py`
- [ ] `model/checkpoints/macaw_chembl_trained.joblib` present and LFS-tracked
- [ ] `install.yml` has all deps pinned
