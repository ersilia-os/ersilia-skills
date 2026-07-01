# Common Benchmark Datasets for Ersilia Model Reproduction

This file covers the datasets most frequently used in cheminformatics/drug-discovery papers that
Ersilia models are trained on. For each dataset: how to download it, expected columns, and how to
extract SMILES + labels for the test split.

---

## MoleculeNet Datasets

MoleculeNet is the single most common source. All datasets below can be fetched via DeepChem or
directly from the CSV files hosted on GitHub. The preferred method is direct CSV download (no
DeepChem installation required).

### ESOL (aqueous solubility, regression)

```bash
wget -O esol.csv "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/delaney-processed.csv"
```

Columns: `smiles`, `measured log solubility in mols per litre`  
Label column: `measured log solubility in mols per litre`  
Task: regression (log mol/L)  
Size: 1128 molecules — use full dataset (no official split; use random 80/10/10).

### FreeSolv (hydration free energy, regression)

```bash
wget -O freesolv.csv "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/SAMPL.csv"
```

Columns: `smiles`, `expt`  
Label column: `expt`  
Task: regression (kcal/mol)  
Size: 642 molecules.

### Lipophilicity (logD, regression)

```bash
wget -O lipophilicity.csv "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/Lipophilicity.csv"
```

Columns: `smiles`, `exp`  
Label column: `exp`  
Task: regression (logD at pH 7.4)  
Size: 4200 molecules.

### BACE (β-secretase inhibition, classification)

```bash
wget -O bace.csv "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/bace.csv"
```

Columns: `mol`, `Class`, `pIC50`  
SMILES column: `mol`  
Label column (classification): `Class` (1 = active, 0 = inactive)  
Label column (regression): `pIC50`  
Task: binary classification or regression  
Size: 1513 molecules.

### BBBP (blood-brain barrier permeability, classification)

```bash
wget -O bbbp.csv "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/BBBP.csv"
```

Columns: `name`, `p_np`, `smiles`  
SMILES column: `smiles`  
Label column: `p_np` (1 = permeable, 0 = not)  
Task: binary classification  
Size: 2039 molecules.

### HIV (HIV replication inhibition, classification)

```bash
wget -O hiv.csv "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/HIV.csv"
```

Columns: `smiles`, `activity`, `HIV_active`  
Label column: `HIV_active` (1 = active, 0 = inactive)  
Task: binary classification  
Size: 41127 molecules — large, consider sampling 1000 for speed.

### Tox21 (12 toxicity assays, multi-label classification)

```bash
wget -O tox21.csv "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/tox21.csv.gz"
gunzip tox21.csv.gz
```

Columns: `smiles`, plus 12 assay columns (NR-AR, NR-AR-LBD, NR-AhR, NR-Aromatase, NR-ER,
NR-ER-LBD, NR-PPAR-gamma, SR-ARE, SR-ATAD5, SR-HSE, SR-MMP, SR-p53)  
Many NaN values (assay not measured for that molecule) — filter to rows where label column is not NaN.  
Task: binary classification per assay  
Size: ~7831 molecules per assay (after NaN filtering).

### ClinTox (clinical trial toxicity, classification)

```bash
wget -O clintox.csv "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/clintox.csv.gz"
gunzip clintox.csv.gz
```

Columns: `smiles`, `FDA_APPROVED`, `CT_TOX`  
Label column: `CT_TOX` (1 = toxic in clinical trials)  
Task: binary classification  
Size: 1478 molecules.

### SIDER (drug side effects, multi-label classification)

```bash
wget -O sider.csv "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/sider.csv.gz"
gunzip sider.csv.gz
```

Columns: `smiles` + 27 side-effect columns  
Task: binary classification per side effect  
Size: 1427 molecules.

### MUV (maximum unbiased validation, classification)

```bash
wget -O muv.csv "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/muv.csv.gz"
gunzip muv.csv.gz
```

17 assay columns. Very imbalanced (active compounds ~0.2%).  
Size: 93087 molecules — always sample or use the test split only.

---

## ChEMBL

Use the ChEMBL REST API when a paper reports results on a specific ChEMBL assay ID.

```python
import requests, pandas as pd

assay_id = "CHEMBL1909203"  # replace with the assay from the paper
url = f"https://www.ebi.ac.uk/chembl/api/data/activity?assay_chembl_id={assay_id}&limit=1000&format=json"
resp = requests.get(url).json()
records = [{"smiles": a["canonical_smiles"], "value": a["standard_value"], "units": a["standard_units"]}
           for a in resp["activities"] if a.get("canonical_smiles")]
df = pd.DataFrame(records)
df.to_csv("chembl_activity.csv", index=False)
```

For larger assays, paginate using `resp["page_meta"]["next"]`.  
Label transformation: papers often report pIC50 = -log10(IC50 in nM). Convert:
```python
df["pIC50"] = -np.log10(df["value"].astype(float) * 1e-9)
```

---

## BindingDB

Download the full tab-separated dump (large, ~2 GB) or use the targeted API:

```bash
# Targeted: search by target name
wget -O bindingdb.tsv "https://www.bindingdb.org/bind/downloads/BindingDB_All_2D_202X.tsv.zip"
```

Columns of interest: `Ligand SMILES`, `Ki (nM)`, `IC50 (nM)`, `Kd (nM)`, `EC50 (nM)`,
`Target Name`, `UniProt (SwissProt) Entry Name of Target Chain`

For a specific target:
```python
df = pd.read_csv("BindingDB_All.tsv", sep="\t", low_memory=False)
target_df = df[df["Target Name"].str.contains("BACE", case=False, na=False)]
```

---

## ZINC

For papers using ZINC subsets (e.g., ZINC-250k for generative models):

```bash
wget -O zinc250k.csv "https://raw.githubusercontent.com/aspuru-guzik-group/chemical_vae/master/models/zinc_properties/250k_rndm_zinc_drugs_clean_3.csv"
```

Columns: `smiles`, `logP`, `qed`, `SAS`  
Commonly used for generative model evaluation — metrics are property distributions, not
classification/regression against a label.

---

## PubChem BioAssay

For papers reporting results on PubChem AID (assay ID):

```bash
# Download activity data for assay AID=1851
wget -O pubchem_aid1851.csv "https://pubchem.ncbi.nlm.nih.gov/assay/assay.cgi?aid=1851&q=entrezquery&format=csv"
```

Or via PUG REST:
```bash
curl "https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/1851/CSV" -o pubchem_aid1851.csv
```

Then fetch SMILES for the active/inactive CIDs:
```python
import requests
cids = ",".join(str(c) for c in df["PUBCHEM_CID"].dropna().astype(int).tolist()[:100])
url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cids}/property/IsomericSMILES/CSV"
smiles_df = pd.read_csv(io.StringIO(requests.get(url).text))
```

---

## Supplementary Data (Zenodo / Figshare / OSF)

Many papers deposit their exact train/test splits as supplementary files. Check:

1. **Paper supplementary section**: look for "Data availability" or "Supplementary Table S1"
2. **GitHub repository**: check `data/`, `datasets/`, or `splits/` folders
3. **Zenodo DOI**: `https://zenodo.org/record/<id>/files/<filename>` — direct download
4. **Figshare DOI**: `https://figshare.com/articles/dataset/<id>` — use the download URL from the Files section
5. **OSF**: `https://osf.io/<id>/files/` — navigate to the file and use the direct download link

When the paper provides the exact test split (e.g., `test.csv` with SMILES + labels), use it directly —
this gives the most faithful comparison.

---

## Handling Splits

When no official split is provided, apply the same strategy the paper describes:

| Split type | How to reproduce |
|---|---|
| Random 80/10/10 | `sklearn.model_selection.train_test_split` with `random_state=42` (common default) |
| Scaffold split | Use `deepchem.splits.ScaffoldSplitter` or the RDKit-based implementation in the source repo |
| Temporal split | Sort by date column, use last N% as test |
| 5-fold CV | Report mean ± std across all folds |

If the paper does not specify a split and no split file is available, use a random 80/10/10 and
note in the report that the split may differ from the paper's.

---

## Ersilia eosbench

eosbench is Ersilia's own standardised benchmark suite. It covers 20 molecular activity datasets
(18 TDC ADMET + 2 ChEMBL), fetches data from S3 on first use, and caches at `~/.cache/eosbench/`.

> **⚠ Critical caveat:** eosbench splits are **arbitrary** and were explicitly designed to NOT
> reproduce published benchmarks (TDC, MoleculeNet, or paper-specific protocols). Never use
> eosbench results to claim REPRODUCED. Any metric computed on eosbench splits is at best
> **APPROXIMATE** and must be labelled "eosbench split — not paper's original split" in the report.

### Install

```bash
pip install git+https://github.com/ersilia-os/eosbench.git
```

### Check available datasets

```bash
eosbench catalog --source tdc
```

### Extract raw SMILES + labels

Use `featurization=None` to get SMILES strings instead of fingerprints:

```python
from eosbench import load_dataset
import pandas as pd

dataset = load_dataset("tdc", "ames", featurization=None)
# dataset.X → list of SMILES strings
# dataset.y → numpy array of binary labels (0/1 for classification)

# Export one fold's test set as a CSV
train_idx, test_idx = dataset.split[0]
df = pd.DataFrame({
    "smiles": [dataset.X[i] for i in test_idx],
    "label": dataset.y[test_idx]
})
df.to_csv("/tmp/eosbench_test.csv", index=False)
```

### Available TDC datasets (classification)

| Dataset | Description |
|---|---|
| ames | Mutagenicity (Ames test) |
| bbb_martins | Blood-brain barrier permeability |
| bioavailability_ma | Oral bioavailability |
| carcinogens_lagunin | Carcinogenicity |
| clintox | Clinical trial toxicity |
| cyp1a2_veith | CYP1A2 inhibition |
| cyp2c19_veith | CYP2C19 inhibition |
| cyp2c9_substrate_carbonmangels | CYP2C9 substrate |
| cyp2c9_veith | CYP2C9 inhibition |
| cyp2d6_substrate_carbonmangels | CYP2D6 substrate |
| cyp2d6_veith | CYP2D6 inhibition |
| cyp3a4_substrate_carbonmangels | CYP3A4 substrate |
| cyp3a4_veith | CYP3A4 inhibition |
| dili | Drug-induced liver injury |
| herg | hERG channel blockade |
| hia_hou | Human intestinal absorption |
| pgp_broccatelli | P-glycoprotein inhibition |
| skin_reaction | Skin sensitisation |

### Available ChEMBL datasets

| Dataset | Notes |
|---|---|
| chembl4649948 | Large-scale bioactivity |
| chembl4659961 | Large-scale bioactivity |

---

## Quick Reference

| Dataset | Task | Size | Download | Split warning |
|---|---|---|---|---|
| ESOL | Regression | 1128 | S3 direct | |
| FreeSolv | Regression | 642 | S3 direct | |
| Lipophilicity | Regression | 4200 | S3 direct | |
| BACE | Class/Reg | 1513 | S3 direct | |
| BBBP | Classification | 2039 | S3 direct | |
| HIV | Classification | 41127 | S3 direct | |
| Tox21 | Multi-label | ~7831/assay | S3 gz | |
| ClinTox | Classification | 1478 | S3 gz | |
| SIDER | Multi-label | 1427 | S3 gz | |
| ZINC-250k | Property | 250000 | GitHub | |
| ChEMBL assay | Class/Reg | varies | REST API | |
| BindingDB | Regression | varies | Bulk download | |
| PubChem BioAssay | Classification | varies | PUG REST | |
| eosbench (TDC) | Classification | 18 datasets | pip install | ⚠ arbitrary splits |
| eosbench (ChEMBL) | Classification | 2 datasets | pip install | ⚠ arbitrary splits |
