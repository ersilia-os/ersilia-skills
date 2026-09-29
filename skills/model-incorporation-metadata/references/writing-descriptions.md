# Writing the Description and the Interpretation

Two free-text fields carry most of what a user learns about a model before running it.
Both have hard limits, and both are read far more often than they are written — so they
are worth the extra minutes.

This document is the single source of truth for how to write them. `model-incorporation-request`
links here for the Description it drafts on the GitHub form.

---

## Description

**Hard limit: 200–600 characters.** This is enforced —
`BaseInformationValidator.validate_description` requires `200 <= len(d) <= 600` and
`ersilia test` fails a model outside that range.

Note that the limit is in **characters, not words**. Guidance expressed in words is a trap:
200 words is roughly 1,320 characters, more than double the ceiling. For calibration, 218
descriptions rewritten in 2026 run 446–585 characters, mean 512 — about 60–90 words, or one
solid paragraph.

**One paragraph. No headings, no lists, no line breaks.**

### What to cover

Not every model supports every point, and forcing all six into 600 characters produces a
checklist rather than prose. Cover what the paper actually supports, in roughly this order:

1. **What the model does** — the property, activity or representation it produces.
2. **The context of the original study** — what problem the authors were solving, and why
   it mattered.
3. **How it was trained** — dataset and its size, algorithm or architecture.
4. **Experimental validation** — say so explicitly when the authors tested predictions in
   the lab, and what was tested. This is one of the most useful things a reader can know
   and is usually buried in the paper.
5. **Known limitations and risks** — applicability domain, assay artefacts, organisms or
   chemistry the training data under-represents.
6. **Ersilia's modifications** — if Ersilia retrained the model, changed the featurisation,
   bundled a different checkpoint or wrote the selection logic, say so. A replicated model
   must state that Ersilia provides a replicated version.

### Prohibitions

- **Never open with "This model…".** Start with the verb or the subject: *"Predicts…"*,
  *"Estimates…"*, *"Returns…"*, *"Scores compounds for…"*, or the model's own name.
- **Never invent anything.** No made-up dataset sizes, accuracy figures, architectures or
  validation claims. If the paper does not say it, it does not go in.
- **Never reference another Ersilia model by identifier** (`eosXXXX`). Descriptions are
  read standalone, and identifiers mean nothing outside the hub.
- **Avoid generic filler** — "state-of-the-art", "powerful tool", "cutting-edge machine
  learning approach". They consume characters and say nothing.
- **Avoid repetitive, recognisable patterns.** When many models are written in one sitting
  they drift into a template — same opening verb, same clause order, same closing caveat.
  Read the neighbouring models before writing. Aim for richness and human-likeness across
  the catalogue, not a house sentence repeated 200 times.

### Models that share a publication

Several hub models are built from the same paper. Their descriptions should be **related
but not identical** — each states what *that* model returns, while the shared study context
is phrased differently rather than copy-pasted. A reader comparing two of them should
learn something from the difference.

### Models with no publication of their own

Internally built models still get a real description: what it predicts, what data Ersilia
trained it on, and how. Where an internal model draws on an assay described in another
model's paper, citing that paper is correct — do not invent a publication for the model
itself.

### Worked examples

**A pathogen activity model, with the data-scarcity limitation made explicit:**

> Estimates activity against Neisseria gonorrhoeae, an organism that has developed
> resistance to every antibiotic class used against it and now threatens to become
> untreatable. Only one usable dose-response assay pool could be assembled from ChEMBL, so
> unlike the multi-model panels for better-studied pathogens this prediction rests on a
> single classifier with no consensus to fall back on. Confidence should be read
> accordingly, and the scarcity itself reflects how little public screening this pathogen
> has received.

**A descriptor calculator, where determinism is the point:**

> Calculates 22 everyday molecular descriptors with Datamol, covering weight, calculated
> lipophilicity, hydrogen bond donors and acceptors, ring and heteroatom counts, rotatable
> bonds, topological polar surface area, drug-likeness and a synthetic accessibility
> estimate. The set is deliberately small and interpretable, intended for annotating
> compound collections or as a cheap baseline feature vector. All values follow
> deterministically from the structure, so results are exact and reproducible rather than
> predicted.

**A generative model, naming the method and the caveat:**

> Elaborates a scaffold carrying attachment points into 100 new drug-like molecules.
> GenMol, released by NVIDIA, applies masked discrete diffusion over the SAFE fragment
> representation, so generation proceeds by progressively revealing fragment blocks rather
> than emitting a string token by token. Training used ZINC and related collections. The
> diffusion process is stochastic, and generated structures still require filtering for
> synthetic accessibility and unwanted substructures.

Notice what these have in common: none opens with "This model", each names the actual
method rather than gesturing at "machine learning", and each ends on a limitation the user
needs rather than a claim of quality.

---

## Interpretation

**One sentence. Hard limit: 20 words.** It answers a single question: *what am I looking at
in the output columns?*

### Rules

- **Do not start with "The model"** — start with the output itself.
- **Never use a colon (`:`)** in `metadata.yml`. Colons break YAML parsing unless the whole
  value is quoted. (This is a YAML hazard only; models using `metadata.json` are unaffected
  because JSON quotes every value — but keep the habit, since a model may be converted.)
- **Must be coherent with `run_columns.csv`.** The interpretation describes exactly the
  columns that file declares — no more, no fewer.
- **Do not reproduce column names verbatim.** `run_columns.csv` already lists them. Say
  what they mean.

### Say the thing that makes the number usable

| Output type | What the interpretation must add |
|---|---|
| Regression | the value **and its unit** — "logD at pH 7.4", "log mol/L", "kcal/mol" |
| Classifier | the **cut-off** — both the assay threshold the labels came from and any recommended decision threshold |
| Similarity search | the **reference library** being searched |
| Featurizer | what the features encode, and how many |
| Generative | how many molecules, and what the input contributed |

### Worked examples

- `Probability of Plasmodium falciparum NF54 inhibition at 1 uM in lactate dehydrogenase and luminescence assays.`
- `Predicted log10 Caco-2 permeability and efflux ratios across Caco-2 and MDCK assays.`
- `22 basic molecular descriptors combining continuous properties with structural counts.`
- `Coordinates from PCA, UMAP and t-SNE projections against the DrugBank chemical space.`
- `Up to 100 generated molecules produced by decorating the input scaffold with new fragments.`
- `Probability of Staphylococcus aureus growth inhibition across eighteen sub-models, plus a weighted consensus.`

Each names the assay, the unit, the library or the count — the thing a user cannot recover
from the column headers alone.
