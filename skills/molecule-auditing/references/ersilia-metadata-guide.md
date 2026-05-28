# Ersilia Model Metadata Guide

This file documents how to fetch and interpret metadata for Ersilia models directly from GitHub, with no CLI installation required.

> **Helper script.** For a batch fetch in one call, use `scripts/fetch_model_metadata.py <eos_id> [<eos_id> ...] --output <path>`. It implements the URL patterns below, including the `metadata.json` → `metadata.yml` fallback, and returns per-model `metadata` + `columns` + `source` + `errors` in a single JSON. The URL patterns in this file remain authoritative — the script just automates them.

---

## URL Patterns

Every Ersilia model has its own public GitHub repository under the `ersilia-os` organisation. Two files are always present:

### `metadata.json`
```
https://raw.githubusercontent.com/ersilia-os/{model_id}/main/metadata.json
```

### `run_columns.csv`
```
https://raw.githubusercontent.com/ersilia-os/{model_id}/main/model/framework/columns/run_columns.csv
```

**Version-pinned fetch** (use the `Release` field from metadata.json to find the tag):
```
https://raw.githubusercontent.com/ersilia-os/{model_id}/{version_tag}/metadata.json
https://raw.githubusercontent.com/ersilia-os/{model_id}/{version_tag}/model/framework/columns/run_columns.csv
```
Example: `https://raw.githubusercontent.com/ersilia-os/eos4e40/v1.0.0/metadata.json`

**Fallback**: Some older models may have `metadata.yml` instead of `metadata.json`. If the `.json` fetch returns 404, try:
```
https://raw.githubusercontent.com/ersilia-os/{model_id}/main/metadata.yml
```

---

## `metadata.json` — Structure and Key Fields

Full example for `eos4e40` (broad-spectrum antibiotic activity predictor):

```json
{
    "Identifier": "eos4e40",
    "Slug": "chemprop-antibiotic",
    "Status": "Ready",
    "Title": "Broad spectrum antibiotic activity",
    "Description": "Based on a simple E.coli growth inhibition assay, the authors trained a model capable of identifying antibiotic potential in compounds structurally divergent from conventional antibiotic drugs.",
    "Deployment": ["Local"],
    "Source": "Local",
    "Source Type": "External",
    "Task": "Annotation",
    "Subtask": "Activity prediction",
    "Input": ["Compound"],
    "Input Dimension": 1,
    "Output": ["Score"],
    "Output Dimension": 1,
    "Output Consistency": "Fixed",
    "Interpretation": "Probability that a compound inhibits E.coli growth. The inhibition threshold was set at 80% growth inhibition in the training set.",
    "Tag": ["E.coli", "IC50", "Antimicrobial activity"],
    "Biomedical Area": ["Antimicrobial resistance"],
    "Target Organism": ["Escherichia coli"],
    "Publication Type": "Peer reviewed",
    "Publication Year": 2020,
    "Publication": "https://pubmed.ncbi.nlm.nih.gov/32084340/",
    "License": "MIT",
    "Contributor": "miquelduranfrigola",
    "Incorporation Date": "2020-11-04",
    "Last Packaging Date": "2025-08-27",
    "Release": "v1.0.0"
}
```

### Fields most useful for molecule auditing

| Field | Use |
|---|---|
| `Title` | Human-readable model name for the report header |
| `Interpretation` | How to read the model's output values — always cite this |
| `Biomedical Area` | Disease/application context |
| `Target Organism` | What organism the model was trained on |
| `Task` / `Subtask` | Type of prediction (Activity prediction, Property calculation, Featurization…) |
| `Output` | What kind of output: Score, Value, Compound, Text |
| `Output Dimension` | Number of output columns |
| `Release` | Version tag for pinned fetching |

---

## `run_columns.csv` — Structure and Key Fields

This file defines each output column for the model.

```csv
name,type,direction,description
inhibition_50um,float,high,Probability of inhibiting the growth (80%) of E.coli at 50 uM
```

### Schema

| Field | Values | Meaning |
|---|---|---|
| `name` | lowercase with underscores | Column identifier — matches the `{feature}` part of `{feature}.{model_id}` in the CSV |
| `type` | `float`, `integer`, `string` | Data type of the output |
| `direction` | `high`, `low`, or empty | **Value-concept relationship**: `high` means a higher value corresponds to more of the concept (e.g. higher AMES value = more mutagenicity); `low` means a lower value corresponds to more of the concept (e.g. lower IC50 = more potent). Empty means the output is not a directional quantity (e.g. featurisation or text). Do NOT confuse this with drug-discovery desirability — see "Scoring role and desirability" section. |
| `description` | short string | One-sentence explanation of what the column measures |

The `direction` field records the **value-concept relationship** (encoding convention), not the drug-discovery objective. A higher value means more of the concept; a lower value means less of the concept. This does NOT tell you whether you want more or less of the concept.

See the "Scoring role and desirability (want_high)" section below for how to determine the actual scoring direction.

---

## Parsing Workflow

1. **Fetch `metadata.json`** for each model ID found in the CSV column names.
2. **Fetch `run_columns.csv`** for the same model ID.
3. **Build column lookup**: for each row in `run_columns.csv`, map `name → {direction, description}`.
4. **Join with CSV columns**: the column `{feature}.{model_id}` in the CSV corresponds to the `run_columns.csv` row where `name == feature`.

### Handling failures

- If `metadata.json` returns 404, try `metadata.yml`. If both fail, mark the model as "metadata unavailable" and include its columns in the audit table without interpretation.
- If `run_columns.csv` returns 404, the column directions are unknown. Include the raw values but exclude them from aggregate scoring. Note this in caveats.
- Network errors should not stop the audit — catch exceptions and continue.

---

## Column Naming in eosframes CSVs

Ersilia screening CSVs produced by [eosframes](https://github.com/ersilia-os/eosframes) name feature columns as:

```
{feature_name}.{model_id}
```

For example, `inhibition_50um.eos4e40` means the `inhibition_50um` output from model `eos4e40`.

To extract model IDs programmatically:
```python
import re
pattern = re.compile(r'^(.+)\.(eos[0-9a-z]{4})$')
for col in df.columns:
    m = pattern.match(col)
    if m:
        feature, model_id = m.group(1), m.group(2)
```

Columns named `key`, `input`, or `smiles` are metadata columns and should not be parsed as model outputs.

---

## Scoring Role and Desirability (`want_high`)

When building the column metadata JSON for the processing script, you must add two fields that go beyond what `run_columns.csv` provides:

### `direction` vs `want_high`

| Field | What it encodes | Who determines it |
|---|---|---|
| `direction` | Value-concept relationship (encoding convention) | Ersilia model metadata |
| `want_high` | Is a higher value of the concept desirable in drug discovery? | You, from the concept description |

These are related but not equivalent. Example: `ames` has `direction=high` (higher value = more mutagenicity). But we **do not want** more mutagenicity, so `want_high = false`. Another example: `inhibition_50um` has `direction=high` (higher value = more inhibition). We **do want** more inhibition, so `want_high = true`.

### How to assign `want_high`

Ask: "If this column's value were higher for a molecule, would that be good or bad for drug discovery in this context?"

| Concept type | Typical `want_high` | Examples |
|---|---|---|
| Activity / inhibition probability | `true` | `inhibition_50um`, `activity_80` |
| Oral bioavailability, absorption | `true` | `bioavailability_ma`, `hia_hou` |
| Membrane permeability (PAMPA, Caco-2) | `true` | `pampa_ncats`, `caco2_wang` |
| BBB penetration (CNS targets) | `true` | `bbb_martins` |
| Aqueous solubility | `true` | `solubility_aqsoldb` |
| Drug half-life | context-dependent | `half_life_obach` (longer usually better) |
| Mutagenicity, carcinogenicity | `false` | `ames`, `carcinogens_lagunin` |
| Hepatotoxicity, DILI | `false` | `dili`, `clintox` |
| hERG channel blockade (cardiac risk) | `false` | `herg`, `activity_80` |
| Nuclear receptor toxicity (Tox21) | `false` | `nr_ar`, `nr_er`, `sr_are`, etc. |
| Skin sensitisation | `false` | `skin_reaction` |
| Molecular weight, TPSA, rotatable bonds | `null` (range-filtered) | `molecular_weight`, `tpsa` |
| LogP, lipophilicity | `null` (range-filtered) | `logp`, `lipophilicity_astrazeneca` |
| Stereocentres, structural descriptors | `null` | `stereo_centers` |
| Featurisation outputs | `null` | embeddings, fingerprints |
| Metabolic clearance | context-dependent | `clearance_microsome_az` (lower = more stable, so `false`) |
| P-gp substrate/inhibitor | context-dependent | `pgp_broccatelli` |

When in doubt, read the column description and the model's `Interpretation` field carefully and reason about whether more is better, less is better, or it depends on a range constraint.

### `scoring_role`

| Role | Meaning | Effect in script |
|---|---|---|
| `"efficacy"` | Primary activity/potency — the thing you're optimising for | Used in aggregate score (`want_high` must be non-null) |
| `"safety_flag"` | Toxicity or safety concern (probability) | Flagged when value > `flag_threshold` (usually 0.5); NOT used in score |
| `"beneficial_admet"` | Positive ADMET property (bioavailability, permeability) | Noted in report; not mixed with activity score |
| `"physicochemical"` | MW, LogP, TPSA, etc. | Handled via Lipinski/Veber rules; not scored |
| `"info"` | Featurisation, text, or ambiguous output | Excluded from scoring |

The `Task`/`Subtask` from `metadata.json` helps:
- `"Activity prediction"` → most columns are `"efficacy"`
- `"Property calculation"` → columns are `"physicochemical"`, `"safety_flag"`, or `"beneficial_admet"` depending on the concept

---

## Common Ersilia ADMET column patterns

The table above is the *concept-type* mapping — use it when you have to reason from scratch about a column you have not seen before. The table below is the *column-name pattern* lookup — use it when a column matches a common ADMET feature naming. The two are complementary; cross-check both when in doubt.

Always confirm `direction` against the actual `run_columns.csv`; the values here are a guide for the common cases.

| Feature name pattern | `direction` | `scoring_role` | `want_high` | What it measures |
|---|---|---|---|---|
| `inhibition_50um` | `high` | `efficacy` | `true` | Probability of inhibiting a target at 50 µM — primary activity signal |
| `bioavailability_ma` | `high` | `beneficial_admet` | `true` | Oral bioavailability probability |
| `hia_hou` | `high` | `beneficial_admet` | `true` | Human intestinal absorption probability |
| `pampa_ncats` | `high` | `beneficial_admet` | `true` | PAMPA membrane permeability |
| `caco2_wang` | `high` | `beneficial_admet` | `true` | Caco-2 permeability (log cm/s) |
| `bbb_martins` | `high` | `beneficial_admet` | `true` | Blood-brain barrier penetration (CNS targets) |
| `solubility_aqsoldb` | `high` | `beneficial_admet` | `true` | Aqueous solubility (log mol/L) |
| `ames` | `high` | `safety_flag` | `false` | Ames mutagenicity probability — high is a red flag |
| `herg` / `activity_80` | `high` | `safety_flag` | `false` | hERG channel blockade (cardiac risk) — flag > 0.5 |
| `dili` | `high` | `safety_flag` | `false` | Drug-induced liver injury probability |
| `clintox` | `high` | `safety_flag` | `false` | Clinical toxicity probability |
| `carcinogens_lagunin` | `high` | `safety_flag` | `false` | Carcinogenicity probability |
| `nr_*` / `sr_*` | `high` | `safety_flag` | `false` | Tox21 nuclear receptor / stress response endpoints |
| `skin_reaction` | `high` | `safety_flag` | `false` | Skin sensitisation probability |
| `pgp_broccatelli` | `high` | `safety_flag` | `false` | P-gp inhibition / efflux risk |
| `cyp*_veith` | `high` | `safety_flag` | `false` | CYP inhibition (drug-drug interaction risk) |
| `clearance_*` | `high` | `beneficial_admet` | `false` | Metabolic clearance — lower is better (more stable) |
| `half_life_obach` | `high` | `beneficial_admet` | `true` | Half-life — longer is generally better |
| `molecular_weight` | `high` | `physicochemical` | `null` | MW — filter via Lipinski (≤500) |
| `logp` / `lipophilicity_*` | varies | `physicochemical` | `null` | LogP — filter via Lipinski (≤5) |
| `tpsa` | `high` | `physicochemical` | `null` | TPSA — filter via Veber (≤140) |
| `hydrogen_bond_*` | `high` | `physicochemical` | `null` | HBD/HBA — Lipinski filters |
| `qed` | `high` | `beneficial_admet` | `true` | Quantitative drug-likeness (0–1, higher = more drug-like) |

> **Key distinction**: `direction` and `want_high` are not the same. `direction=high` for `ames` means higher value = more mutagenicity. `want_high=false` means we don't want mutagenicity. Always reason from the concept, not from `direction` alone.

### hERG interpretation note

hERG blockade is a cardiac safety concern regardless of how it is encoded. Flag any molecule with hERG probability > 0.5 as a `safety_flag`. This applies whether the column is `herg`, `activity_80`, or a similarly named variant — the script enforces this fallback when no explicit `safety_flag` metadata is present.
