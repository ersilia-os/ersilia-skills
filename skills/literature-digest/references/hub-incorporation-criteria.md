# Hub incorporation criteria — empirical priors

Derived from `ersilia-os/ersilia-maintenance/files/repo_info.json` (full Hub
catalogue, 254 entries; 189 "Ready") and `ErsiliaModelsDOI.csv` (per-model
publication metadata, 207 entries). Snapshot date: 2026-05-21. Refresh
quarterly.

These are **empirical priors** for assigning the 🤖 marker and for ranking
candidates inside their chapter (see `output-template.md` for chapter layout
and 🤖-first ordering rules). A paper that "looks like the Hub" is a paper
that resembles what has historically made it in.

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
