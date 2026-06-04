# Ersilia Model Hub — checkmol functional-group detector

Draft metadata and model description for incorporating **checkmol** (Haider 2010) as an Ersilia model. Schema follows `ersilia-metadata-guide.md`.

## Description (human-readable)

checkmol is an open-source command-line tool that analyses a molecule for the presence of functional groups and structural elements, recognising approximately **204 distinct functional-group types** — alcohols, carbonyls, carboxylic acids, amines, halides, heterocycles, and many more. For each input compound it returns a fixed-length vector of functional-group counts, providing an **interpretable, rule-based molecular descriptor** (in contrast to abstract learned embeddings). This Ersilia model wraps the original Pascal program behind a Python interface: input SMILES are converted to MDL molfiles with RDKit, passed to checkmol, and its functional-group codes are parsed into named output columns. It is useful as a transparent featuriser for SAR/ML, and as a neutral functional-group "census" alongside structural-alert models.

## Draft `metadata.json`

```json
{
    "Identifier": "eosXXXX",
    "Slug": "checkmol-functional-groups",
    "Status": "In progress",
    "Title": "Functional group detection with checkmol",
    "Description": "checkmol analyses a molecule for the presence of functional groups and structural elements, recognising ~204 distinct functional-group types and returning a fixed-length vector of counts. It provides an interpretable, rule-based molecular descriptor. This model wraps the original Pascal program (Haider 2010): SMILES are converted to MDL molfiles with RDKit, passed to checkmol, and its functional-group codes are parsed into named output columns.",
    "Deployment": ["Local"],
    "Source": "Local",
    "Source Type": "External",
    "Task": "Annotation",
    "Subtask": "Featurization",
    "Input": ["Compound"],
    "Input Dimension": 1,
    "Output": ["Descriptor"],
    "Output Dimension": 204,
    "Output Consistency": "Fixed",
    "Interpretation": "Each output column corresponds to one checkmol functional-group type; the value is the count of that group in the molecule (0 = absent). Group definitions and codes are listed by `checkmol -l`. A rule-based descriptor, not a probability.",
    "Tag": ["Functional groups", "Descriptor", "Fingerprint", "Substructure"],
    "Biomedical Area": ["Any"],
    "Target Organism": ["Not Applicable"],
    "Publication Type": "Peer reviewed",
    "Publication Year": 2010,
    "Publication": "https://doi.org/10.3390/molecules15085079",
    "Source Code": "https://homepage.univie.ac.at/norbert.haider/cheminf/cmmm.html",
    "License": "GPL-3.0-only",
    "Contributor": "miquelduranfrigola",
    "Incorporation Date": "2026-06-02",
    "Release": "v1.0.0"
}
```

## `run_columns.csv` (format + how to generate all 204)

Each of checkmol's functional groups becomes one column. Counts are non-directional (a census, not a desirability score), so `direction` is left empty.

```csv
name,type,direction,description
cation,integer,,Number of cationic groups
anion,integer,,Number of anionic groups
carbonyl,integer,,Number of carbonyl groups
carboxylic_acid,integer,,Number of carboxylic acid groups
ester,integer,,Number of ester groups
...
```

Generate the full 204-row file directly from the tool so the column set is authoritative, not hand-typed:

```bash
checkmol -l        # prints every functional-group code + its description
```

Map each `code → (slug, description)` row; that guarantees the columns match exactly what the compiled binary emits.

## Build notes (for the model's Dockerfile / conda env)

- **Dependencies (conda, no root):** `conda install -c conda-forge fpc rdkit`
- **Compile:** `fpc checkmol.pas -S2 -O3 -Op3` → `checkmol` binary (source: Haider homepage, GPL).
- **Wrap:** Python entrypoint converts SMILES → MDL molfile (RDKit) → `checkmol -c` (or `-b`/`-s` bitstring) → parse to the fixed 204-column vector. The **pyCheckmol** repo (github.com/jeffrichardchemistry/pyCheckmol) is a working reference for this wrapping pattern.

## Fields to confirm before submission

- **`Identifier`** — assigned by Ersilia on incorporation (placeholder `eosXXXX`).
- **`Task` / `Subtask` / `Output` / `Biomedical Area`** — must match Ersilia's current controlled vocabularies; "Annotation/Featurization" and "Descriptor" are the best fit for a functional-group counter but verify against the live schema.
- **`License`: GPL-3.0** — checkmol is GPL, so the model repo must be GPL-compatible. This is the one hard constraint to flag (the alert-catalog models from RDKit/Brenk are more permissive; checkmol is not).
- **`Output Dimension`: 204** — confirm against `checkmol -l` count for the exact version compiled (the homepage says "approx. 200"; fgtable.pdf lists 204).
