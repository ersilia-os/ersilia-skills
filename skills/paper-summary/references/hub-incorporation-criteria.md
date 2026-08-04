# Hub incorporation criteria — empirical priors

Derived from `ersilia-os/ersilia-maintenance/files/repo_info.json` (full Hub
catalogue, 254 entries; 189 "Ready") and `ErsiliaModelsDOI.csv` (per-model
publication metadata, 207 entries). Snapshot date: 2026-05-21. Refresh
quarterly.

These are **empirical priors** for assigning the 🤖 marker and for ranking
candidates inside their chapter (see `output-template.md` for chapter layout
and 🤖-first ordering rules). A paper that "looks like the Hub" is a paper
that resembles what has historically made it in.

## Model status values

`ersilia_search` tags every model with one of four statuses. The default search (no
`--all-statuses` flag) returns **Ready only** — always pass `--all-statuses` when checking
for overlap with a paper, or a model already in the incorporation pipeline or a past
incorporation attempt will be invisible to the search.

| Status | Meaning | How it affects a paper's verdict |
|---|---:|---|
| **Ready** | Fully incorporated, available in the Hub today | Standard overlap check — flag as **Potential overlap** |
| **In progress** | Actively being incorporated right now | The team already knows about this method — flag as **Already in Hub pipeline**, overriding the base eligibility verdict |
| **In maintenance** | Incorporated, currently being reworked/fixed | Same treatment as In progress — **Already in Hub pipeline** |
| **Archived** | Was incorporated, later removed | Does not override the verdict; surface as context (possible revival candidate, or superseded) — do not speculate on the reason unless documented |

`In progress` entries are frequently metadata-thin (title + GitHub link only, no
Description/Task/Subtask yet), so they can be missed by keyword-relevance ranking even
with `--all-statuses` set. When a paper's method name is distinctive, cross-check directly:
`ersilia_search --status "In progress" --status "In maintenance" --status "Archived" --limit 200 --csv`
and grep for the name.

## Subtask distribution (Ready models)

| Subtask | Models | Share |
|---|---:|---:|
| Activity prediction | 77 | 41 % |
| Featurization | 48 | 25 % |
| Property calculation or prediction | 38 | 20 % |
| Similarity search | 11 | 6 % |
| Generation | 9 | 5 % |
| Projection | 6 | 3 % |

**Interpretation.** The Hub is dominated by **activity prediction** and
**featurization** — together two-thirds of all Ready models. A paper that
releases a new activity model on a Hub-relevant endpoint (AMR, antimalarial,
ADMET, toxicity) is the single most likely candidate for incorporation. A new
featurizer (foundation model, descriptor, embedding) is the second most likely.
Generation and projection are smaller buckets and have a higher bar to clear.

## Source type

| Source | Models | Share |
|---|---:|---:|
| External (incorporated from a public paper/repo) | 149 | 79 % |
| Internal (Ersilia-developed) | 33 | 17 % |
| Replicated (re-implemented from a paper) | 7 | 4 % |

**Interpretation.** ~80 % of the Hub is external incorporations. The 🤖 marker
exists to flag candidates for that pipeline. Internal and replicated models do
not need the marker — they're already inside the Hub by other means.

## Where Hub publications actually live (top venues among 207 catalogued models)

| Venue | Models | Notes |
|---|---:|---|
| Journal of Cheminformatics | 29 | Dominant. Always check JCheminform issues. |
| arXiv | 25 | Preprints are first-class; 12 % of catalogued models are preprints. |
| Journal of Chemical Information and Modeling (JCIM) | 13 | |
| Nature Machine Intelligence | 11 | Highest-impact venue with serial incorporation. |
| Nature Communications | 9 | |
| Nucleic Acids Research | 6 | Web-server papers especially — NAR's web-server issue. |
| Nature family (other) | 6 | |
| chemRxiv | 3 | Preprints. |
| Cell family | 3 | |
| Bioinformatics | 3 | |
| J Med Chem | 2 | |
| ACS Omega | 2 | |
| ACS Infect Dis · ACS Med Chem Lett · Molecular Informatics | 1 each | Long tail of single-paper venues. |

**Interpretation.** Six venues account for over 80 % of catalogued Hub
publications. When ranking candidate models, treat **J Cheminform, JCIM, arXiv,
Nature Machine Intelligence, Nature Communications, and Nucleic Acids Research**
as the highest-prior venues. NAR is especially important for **web-server
papers** — `DeepCYP`, ADMETLab-style tools — which are a recurring incorporation
pattern.

## Publication type

| Type | Share |
|---|---:|
| Peer-reviewed | 79 % |
| Preprint | 12 % |
| Other (web servers, code releases) | 8 % |

**Interpretation.** Preprints are routinely incorporated. The 🤖 marker does not
require peer review.

## What "Hub-worthy" looks like, in one paragraph

A paper that's a good Hub incorporation candidate (1) targets one of the six
subtasks — most often **activity prediction**, **featurization**, or **property
prediction**; (2) addresses an Ersilia-priority endpoint (AMR / Plasmodium / TB /
ADMET / toxicity / kinetoplastid) or a generic chemistry endpoint with broad
utility (CYP, hERG, solubility, drug-likeness); (3) ships **open-source or
openly-distributable** code, ideally with weights — proprietary models can be
"online-mode" entries but they're a fall-back; (4) lives in J Cheminform, JCIM,
arXiv, NMI, Nat Comms, or NAR — or, less often, a Nature/Cell-family
high-impact venue when the work is foundational.

## How this translates to the 🤖 marker

Apply 🤖 when **all of the following hold**:

1. **The model takes small molecules as its primary input.** The Hub's current
   incorporation surface is small-molecule-only: SMILES / InChI / molfile.
   That means the following are explicitly **not** 🤖-eligible, no matter how
   relevant they look otherwise:
   - protein-sequence input (e.g. solubility, secondary structure, pLM
     interpretability)
   - RNA-sequence or RNA-structure input
   - peptide-sequence input (AMP optimisers, peptide generators)
   - gene / genome input (resistance-gene annotators)
   - bulk or single-cell transcriptomic input (signature-based prioritisers)
   - cell-image / phenotypic-image input
   - pocket-tensor or protein-pocket conditioning
   - multi-omics target-ID pipelines

   Compound–protein interaction models are 🤖-eligible because the *primary*
   user-facing input is the small molecule; the protein is a condition the Hub
   handles as a fixed target argument. Generative models that emit small
   molecules are 🤖-eligible even when they have no molecule input, *provided*
   they do not require a non-molecule conditioning input (e.g. a pocket
   tensor) the Hub's generator interface cannot currently supply.

   For models that are clearly important but fall outside this surface — surface
   them as context items without 🤖, with a one-liner stating "Out of the
   current Hub small-molecule-input surface" so the team knows to revisit when
   the Hub interface expands.

2. The paper introduces or releases a model / tool, not just an analysis.
3. The model performs one of the six Hub subtasks (use this file as the
   reference taxonomy). Map ambiguous tasks to the most specific subtask, and
   only call it "Generation" if the headline contribution is generative.
4. The model is **openly available** — code or weights or web server. Mark 🤖
   even for online-only services (ADMETLab-style entries are a Hub pattern), but
   prefer code-bearing entries when triaging.
5. The endpoint is plausibly Hub-relevant. Cardiology-only or plant-only
   models, for instance, do not fit unless they generalise.

When 🤖 is applied, the item stays in the topical chapter it would have
landed in anyway (per `output-template.md` placement rules), but is sorted
above non-🤖 entries inside that chapter so candidate Hub models are visible
at a glance.

## How this translates to the 🗃️ marker

Apply 🗃️ when the paper releases a dataset that **could** be used to train a
Hub model the team hasn't built yet — i.e. there is no model in the paper, OR
the dataset is bigger / cleaner / more diverse than what the paper's own model
was trained on. The presence of bioactivity (IC50/MIC), ADMET, or phenotypic
endpoint data on Hub-priority pathogens is the strongest signal.

When 🗃️ is the *only* marker (no 🤖), the item still stays in its topical
chapter — the marker alone tells the reader the dataset is Hub-trainable.
When a paper carries **both** 🤖 and 🗃️, the model is the primary contribution
and the dataset gets a mention in the body sentence.

## Conditional incorporation routes (🤖❓)

The 🤖 marker fires only when a paper's *own model* can be directly wrapped.
But ~21 % of the Hub (Internal + Replicated source types) reached the Hub via an
**intermediate step** — encoder extraction, fine-tuning, surrogate distillation,
or data-to-model training. Papers enabling one of these routes are Hub candidates
too, just conditional ones.

In the paper-summary skill, these papers receive the **Conditional candidate** verdict
instead of a direct Strong candidate / Candidate verdict. A paper receives either
Conditional candidate or a direct eligibility verdict — never both.

### Six trigger questions (C1–C6)

Ask these *before* running the standard eligibility checklist in Step 3. Fire
**Conditional candidate** on the first trigger that matches.

| ID | Trigger | Route name | Hub precedent |
|---|---|---|---|
| C1 | The paper's main contribution is a **pretrained encoder** (molecular transformer, GNN, diffusion backbone) whose hidden-layer embeddings could be exposed as a featurizer, even if the paper does not frame it that way. | Encoder extraction | eos7w6n (GROVER), eos4rw4 (CDDD), eos9zw0 (MolPMoFiT), eos82v1 (SMI-TED), eos3wac (DeBERTaV2), eos39co (Uni-Mol) |
| C2 | The paper describes **fine-tuning a foundation model** on a new endpoint — the fine-tuning recipe is the contribution, not a new backbone. | Fine-tuned predictor | eos4cxk, eos8c0o, eos6hy3, eos93h2 (ImageMol fine-tunes); eos6m2k (MolE + XGBoost on 40 antimicrobial strains) |
| C3 | The model is **online/proprietary only**, but the API can be called in bulk to generate labels for a surrogate. Ersilia has used teacher–student distillation for models like this. | Surrogate distillation | eos2gth (MAIP surrogate via teacher–student distillation on 2M ChEMBL molecules) |
| C4 | The paper releases a **screening dataset without a model** on a Hub-priority endpoint — large enough that LazyQSAR or Chemprop could produce a useful predictor. This applies to both **experimental bioassay data** (MIC, IC50, phenotypic readouts) and **computational virtual-screening data** (docking scores, e.g. AutoDock Vina). For docking datasets, the route trains a QSAR surrogate to predict docking scores directly from SMILES, eliminating the need to run the docking pipeline per query. Scale threshold differs by data type: ~500+ compounds for bioassay endpoints; ~10 000+ per target for docking-surrogate routes (noisier labels require more data). | Data-to-model (LazyQSAR) | eos4rta, eos2l0q, eos9ivc, eos5bsw, eos7l5m (LazyQSAR models trained on published assay data) |
| C5 | The model is a **multi-task predictor** whose output vector across tasks could serve as a molecular fingerprint, independent of its primary framing. | Multi-task featurizer | eos93h2 (10 GPCR scores as bioactivity embedding); eos1vms (616 ChEMBL target probabilities as fingerprint); eos4u6p (CC Signaturizer, 3200-dim bioactivity spaces) |
| C6 | The model fails reproducibility because one component is **proprietary or unavailable**, but an open-source substitute benchmarked in the paper would yield comparable performance. | Replication with substitution | eos8d8a (MycPermCheck, replicated with LazyQSAR + Ersilia decoy sampler); eos9n1s (hemozoin inhibition, RDKit replacing proprietary ChemSpyder descriptors) |

### Conditional body-sentence template

```
Conditional Hub candidate via [Route name].
Paper contributes: {what the paper actually published — encoder, recipe, data, or API}.
Hub would do: {the intermediate step} → {expected Hub output type}.
Prerequisite: {what must exist or happen first}.
Released under {license}. Priority: {High / Medium / Low} because {specific Hub gap filled}.
```

**Priority heuristics:**
- **High** — no Hub coverage of this endpoint/task, or it is a named priority (AMR, Plasmodium, TB, ADMET).
- **Medium** — partial Hub coverage; this route adds a new organism, endpoint, or meaningfully better accuracy.
- **Low** — Hub already has adequate coverage; this would be a refinement.

### Worked examples

**C1 — Encoder extraction**

> Conditional Hub candidate via Encoder extraction.
> Paper contributes: a SMILES-based molecular transformer pretrained on 77M PubChem compounds.
> Hub would do: expose the final hidden-layer embedding as a 768-dim fingerprint → Featurization entry.
> Prerequisite: weights confirmed downloadable (verify Zenodo record resolves).
> Released under MIT. Priority: Medium because the Hub has featurizers (eos2d9a, eos5axz) but none pretrained at this scale.

**C3 — Surrogate distillation**

> Conditional Hub candidate via Surrogate distillation.
> Paper contributes: a proprietary antimalarial activity model accessible via web API (no weights or code released).
> Hub would do: call the API in bulk → train a surrogate via teacher–student distillation → Activity prediction entry.
> Prerequisite: API must remain live and allow bulk queries (~50k compounds; see eos2gth precedent).
> Released under commercial licence (API only). Priority: High because Plasmodium falciparum activity coverage remains a Hub priority.

**C4 — Data-to-model**

> Conditional Hub candidate via Data-to-model (LazyQSAR).
> Paper contributes: 23 000 MIC measurements against M. tuberculosis H37Rv (no model shipped).
> Hub would do: train a QSAR predictor with LazyQSAR → MIC/activity prediction entry for TB whole-cell.
> Prerequisite: dataset confirmed downloadable under open licence; LazyQSAR training (~1 h on CPU) is the only additional step.
> Released under CC-BY. Priority: High because TB whole-cell activity prediction is a named Hub gap.

**C4 — Data-to-model (docking surrogate)**

> Conditional Hub candidate via Data-to-model (LazyQSAR).
> Paper contributes: 48 000 AutoDock Vina docking scores against Mtb InhA (SMILES + score, supplementary CSV; no QSAR model shipped).
> Hub would do: train a QSAR surrogate on SMILES → Vina score with LazyQSAR → Activity prediction entry (docking-score proxy), so users can screen libraries without running Vina.
> Prerequisite: dataset confirmed downloadable under open licence; compound count ≥10 000 per target (check before proceeding — small docking runs are below the surrogate reliability threshold); target is Hub-priority (TB).
> Released under CC-BY. Priority: High because a SMILES-native docking proxy for a TB target fills a Hub gap and is orders of magnitude cheaper to run than the docking pipeline itself.
