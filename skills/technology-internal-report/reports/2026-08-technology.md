# Ersilia technology report — August 2026

**Models incorporated:** 10 — 4 Representation, 4 Sampling, 2 Annotation
**Status:** 10 Ready
**Prepared:** 2026-09-09 from the Hub catalogue (254 models)

## Summary

| Model | Title | Task | Authors | Paper |
|---|---|---|---|---|
| [`eos5g6m`](https://github.com/ersilia-os/eos5g6m) | GLACIER Molecular Embeddings | Featurization | Emily Nguyen et al. (5) | [10.48550/arXiv.2606.11382](https://doi.org/10.48550/arXiv.2606.11382) |
| [`eos5mnx`](https://github.com/ersilia-os/eos5mnx) | SAND Shape-Aware Descriptor | Featurization | *unresolved* | [https://openreview.net/forum?id=pB6WAdnRDR](https://openreview.net/forum?id=pB6WAdnRDR) |
| [`eos6pj2`](https://github.com/ersilia-os/eos6pj2) | NaFM Natural Product Embeddings | Featurization | Yuheng Ding et al. (11) | [10.1038/s42256-026-01226-8](https://doi.org/10.1038/s42256-026-01226-8) |
| [`eos84nf`](https://github.com/ersilia-os/eos84nf) | GenMol Scaffold Decoration | Generation | Seul Lee et al. (9) | [10.48550/arXiv.2501.06158](https://doi.org/10.48550/arXiv.2501.06158) |
| [`eos8zvb`](https://github.com/ersilia-os/eos8zvb) | PyMolGen Drug-Like Molecule Generation | Generation | Bruno N. Falcone et al. (11) | [10.1021/acs.jcim.6c00689](https://doi.org/10.1021/acs.jcim.6c00689) |
| [`eos19dk`](https://github.com/ersilia-os/eos19dk) | MolCompass Chemical Space Projection | Projection | Sergey Sosnin | [10.1186/s13321-024-00888-z](https://doi.org/10.1186/s13321-024-00888-z) |
| [`eos3f8h`](https://github.com/ersilia-os/eos3f8h) | Antimicrobial activity prediction from EU OpenScreen data | Activity prediction | Ctibor Škuta et al. (11) | [10.1093/nar/gkae904](https://doi.org/10.1093/nar/gkae904) |
| [`eos3xhm`](https://github.com/ersilia-os/eos3xhm) | HADES Oral Drug-Likeness | Property calculation or prediction | Narek Petrosyan et al. (8) | [10.1021/acs.jcim.5c02953](https://doi.org/10.1021/acs.jcim.5c02953) |
| [`eos55vx`](https://github.com/ersilia-os/eos55vx) | CoCoGraph Formula-Preserving Generation | Generation | Manuel Ruiz-Botella et al. (3) | [10.1038/s42256-026-01229-5](https://doi.org/10.1038/s42256-026-01229-5) |
| [`eos6a1h`](https://github.com/ersilia-os/eos6a1h) | CoCoGraph Small-Fragment Inpainting | Generation | Manuel Ruiz-Botella et al. (3) | [10.1038/s42256-026-01229-5](https://doi.org/10.1038/s42256-026-01229-5) |

## The models

### `eos5g6m` · GLACIER Molecular Embeddings

**Emily Nguyen, Yongchan Hong, Harsh Toshniwal, Yan Liu and Andreas Luttens** — University of Southern California · Karolinska Institutet · 2026

A multimodal student-teacher foundation model that turns a SMILES string into a 512-dimensional embedding. It fuses three views of a molecule — a message-passing graph encoder, a SMILES transformer and physicochemical descriptors — through a geometry-aware module, distilled from larger teacher models by contrastive learning. Intended as a general-purpose featurizer for downstream property prediction.

Paper: [10.48550/arXiv.2606.11382](https://doi.org/10.48550/arXiv.2606.11382) · Authors' code: https://github.com/eemokey/glacier · Run it: `ersilia fetch glacier-embeddings` · Licence: MIT

### `eos5mnx` · SAND Shape-Aware Descriptor

***authors unresolved — see the defects section*** · preprint 2026

Turns a molecule's 2D structure into a fixed-length embedding that captures its 3D shape without generating any conformers, so cosine similarity between vectors approximates 3D shape overlap. Useful for rapid retrieval of shape-similar molecules in ligand-based virtual screening. A GINE graph encoder producing 512 dimensions, trained at Pfizer and presented at ICML 2026.

Paper: [https://openreview.net/forum?id=pB6WAdnRDR](https://openreview.net/forum?id=pB6WAdnRDR) · Authors' code: https://github.com/pfizer-opensource/SAND · Run it: `ersilia fetch sand-shape-descriptor` · Licence: Apache-2.0

### `eos6pj2` · NaFM Natural Product Embeddings

**Yuheng Ding, Zhenmin Liu and 9 colleagues** — Peking University · University of Washington · Chinese University of Hong Kong · Nature Machine Intelligence 2026

A scaffold-aware graph foundation model for natural products, turning a SMILES string into a 1024-dimensional embedding. Pretrained on the COCONUT natural-product database with contrastive and masked-graph learning, it retains scaffold and side-chain information that general-purpose featurizers tend to lose. The authors apply it to taxonomy classification, genome mining and virtual screening.

Paper: [10.1038/s42256-026-01226-8](https://doi.org/10.1038/s42256-026-01226-8) · Authors' code: https://github.com/TomAIDD/NaFM-Official · Run it: `ersilia fetch nafm-embeddings` · Licence: MIT

### `eos84nf` · GenMol Scaffold Decoration

**Seul Lee, Arash Vahdat and 7 colleagues** · preprint 2025

Given a scaffold with attachment points, decorates it with novel side fragments to produce new drug-like molecules, using masked discrete diffusion over the fragment-based SAFE representation. Trained on ZINC and UniChem. The authors report better validity, quality and diversity than the earlier autoregressive SAFE-GPT, and substantially faster sampling through non-autoregressive parallel decoding — aimed at hit-to-lead exploration around a known scaffold.

Paper: [10.48550/arXiv.2501.06158](https://doi.org/10.48550/arXiv.2501.06158) · Authors' code: https://github.com/NVIDIA-Digital-Bio/genmol · Run it: `ersilia fetch genmol-scaffold-decoration` · Licence: Apache-2.0

### `eos8zvb` · PyMolGen Drug-Like Molecule Generation

**Bruno N. Falcone, Jonathan D. Hirst and 9 colleagues** — University of Nottingham · University of Strathclyde · GlaxoSmithKline (Spain) · Journal of Chemical Information
and Modeling 2026

Generates analogues of a parent compound by deriving fragment-combination rules from ChEMBL: starting from a core structure, new molecules are sampled according to the database's fragment-bond frequencies, deduplicated and checked for RDKit validity. A deliberately simple, database-driven alternative to a learned generative model.

Paper: [10.1021/acs.jcim.6c00689](https://doi.org/10.1021/acs.jcim.6c00689) · Authors' code: https://github.com/HirstGroup/PyMolGen · Run it: `ersilia fetch pymolgen` · Licence: MIT

### `eos19dk` · MolCompass Chemical Space Projection

**Sergey Sosnin** — University of Vienna · BOKU University · Journal of Cheminformatics 2024

Projects a SMILES string onto a 2D map of chemical space with a pretrained parametric t-SNE network, deterministically — structurally similar compounds land together every run. Built on 2048-bit ECFP fingerprints and trained on 1.56 million ChEMBL v23 structures. The authors intend it for exploring chemical space, checking a QSAR model's applicability domain, and spotting activity cliffs where similar compounds get inconsistent predictions.

Paper: [10.1186/s13321-024-00888-z](https://doi.org/10.1186/s13321-024-00888-z) · Authors' code: https://github.com/sergsb/molcomplib · Run it: `ersilia fetch molcompass` · Licence: MIT

### `eos3f8h` · Antimicrobial activity prediction from EU OpenScreen data

**Ctibor Škuta, Petr Bartůněk and 9 colleagues** — Czech Academy of Sciences, Institute of Molecular Genetics · Fraunhofer Institute for Translational Medicine and Pharmacology · Nucleic Acids Research 2024

Predicts activity against seven reference pathogens — *A. baumannii*, *C. albicans*, *E. coli*, *E. faecalis*, *K. pneumoniae*, *P. aeruginosa* and *S. aureus* — from single-point inhibition screens of the ~100,000-compound EU OpenScreen library, taken from the European Chemical Biology Database. The credit here is for the **screening data**, not the model: Skuta and colleagues produced the database, and Ersilia trained these classifiers on it with LazyQSAR v3, reporting a mean AUROC of 0.94 across 5-fold cross-validation. Any announcement must say so rather than implying the authors built the model.

Paper: [10.1093/nar/gkae904](https://doi.org/10.1093/nar/gkae904) · Authors' code: https://github.com/ersilia-os/eu-openscreen-antimicrobial-tasks · Run it: `ersilia fetch eu-openscreen-hts` · Licence: GPL-3.0-or-later

### `eos3xhm` · HADES Oral Drug-Likeness

**Narek Petrosyan, Hovakim Zakaryan and 6 colleagues** — Denovo Sciences Inc (Yerevan) · Institute of Molecular Biology of NAS (Yerevan) · Journal of Chemical Information
and Modeling 2026

Scores how closely a compound resembles an approved oral drug, with 0.63 as the authors' recommended cut-off. Averages probabilities from five tree and boosting classifiers over 298 features combining Mordred descriptors, ADMET-AI predictions and QED terms, trained on 1,177 approved oral drugs against 5,307 non-drugs from ChEMBL, ZINC and GDB. The authors show scores rising across clinical phases and falling for orally toxic and chemically implausible structures.

Paper: [10.1021/acs.jcim.5c02953](https://doi.org/10.1021/acs.jcim.5c02953) · Authors' code: https://github.com/Narek-Petros-yan/HADES · Run it: `ersilia fetch hades-oral-druglikeness` · Licence: MIT

### `eos55vx` · CoCoGraph Formula-Preserving Generation

**Manuel Ruiz-Botella, Marta Sales‐Pardo and Roger Guimerà** — Universitat Rovira i Virgili · Institució Catalana de Recerca i Estudis Avançats · Institut Català de Ciències del Clima · Nature Machine Intelligence 2026

Generates 100 chemically valid molecules sharing the exact atomic composition of an input compound, via a constrained graph diffusion trained on 2.25 million molecules from PubChem, ChEMBL, ZINC and NIST. Validity is guaranteed by construction rather than learned: every diffusion step swaps bonds while preserving atom valences. In a blind test, 121 organic chemists distinguished generated from real molecules only 62% of the time. Restricted to molecules of 5–70 atoms including hydrogens.

Paper: [10.1038/s42256-026-01229-5](https://doi.org/10.1038/s42256-026-01229-5) · Authors' code: https://doi.org/10.5281/zenodo.18940151 · Run it: `ersilia fetch cocograph-formula` · Licence: MIT

### `eos6a1h` · CoCoGraph Small-Fragment Inpainting

**Manuel Ruiz-Botella, Marta Sales‐Pardo and Roger Guimerà** — Universitat Rovira i Virgili · Institució Catalana de Recerca i Estudis Avançats · Institut Català de Ciències del Clima · Nature Machine Intelligence 2026

The inpainting counterpart to the formula-preserving model above: it attaches a small fragment of 2–5 heavy atoms, drawn from a library of frequent substructures, then refines the result with the same constrained graph diffusion. Bond-pair swapping keeps every intermediate valence-valid, so chemical validity is guaranteed rather than filtered for afterwards.

Paper: [10.1038/s42256-026-01229-5](https://doi.org/10.1038/s42256-026-01229-5) · Authors' code: https://doi.org/10.5281/zenodo.18940151 · Run it: `ersilia fetch cocograph-small` · Licence: MIT

## Metadata to fix

Each of these is a `/model-incorporation-metadata` gap in a model already marked live. They are listed here because whoever reads this report can go and fix them.

- **`eos5g6m`** — Publication cites the arXiv preprint (10.48550/arXiv.2606.11382) but a peer-reviewed version exists — KDD 2026, 10.1145/3770855.3819032 — which is what Publication and Publication Type should carry
- **`eos5mnx`** — Publication is not a DOI URL and no DOI could be derived (https://openreview.net/forum?id=pB6WAdnRDR)
- **`eos3xhm`** — OpenAlex mis-resolves this paper's affiliations, returning 'Institute of Molecular Biology of the Slovak Academy of Sciences' and 'Denso (United States)'; the paper says Denovo Sciences and the Armenian NAS. Institutions here were taken from the paper

## Draft LinkedIn round-up

Lint it with `scripts/check_post.py` before anyone posts it.

```text
New in the Ersilia Model Hub: nine models from August

We are very excited to announce nine new models incorporated last month — molecular featurizers, generative models and an antimicrobial activity predictor.

With thanks to the authors of each:

GLACIER — Emily Nguyen and colleagues at USC and Karolinska Institutet — multimodal embeddings distilled from larger teacher models: https://doi.org/10.48550/arXiv.2606.11382

NaFM — Yuheng Ding and colleagues at Peking University — scaffold-aware embeddings for natural products: https://doi.org/10.1038/s42256-026-01226-8

MolCompass — Sergey Sosnin, University of Vienna — deterministic 2D projection of chemical space: https://doi.org/10.1186/s13321-024-00888-z

GenMol — Seul Lee and colleagues — scaffold decoration by masked discrete diffusion: https://doi.org/10.48550/arXiv.2501.06158

PyMolGen — Bruno N. Falcone and colleagues at Nottingham — analogue generation from ChEMBL fragment statistics: https://doi.org/10.1021/acs.jcim.6c00689

CoCoGraph — Manuel Ruiz-Botella and colleagues at Universitat Rovira i Virgili — graph diffusion where chemical validity is guaranteed by construction, in two variants: https://doi.org/10.1038/s42256-026-01229-5

HADES — Narek Petrosyan and colleagues — oral drug-likeness scoring across 298 features: https://doi.org/10.1021/acs.jcim.5c02953

EU OpenScreen antimicrobials — Ctibor Škuta and colleagues at the Czech Academy of Sciences built the screening database of ~100,000 compounds against seven pathogens; these classifiers were trained on it: https://doi.org/10.1093/nar/gkae904

Every one runs in one command, with no need to rebuild the original environment.

Full catalogue: https://github.com/ersilia-os/ersilia

#DrugDiscovery #MachineLearning #OpenScience #Cheminformatics
```

## Profiles to tag

Authors only — Ersilia does not tag institutions. Tag by typing the name into the composer and picking the profile; never tag a row marked `ambiguous` or `unverified`.

| Author | Model | Profile | Status |
|---|---|---|---|
| Emily Nguyen | `eos5g6m` | *none found* | **unverified** — no profile surfaced, including a linkedin.com-restricted search. Her site `eemokey.github.io` matches the model's own source repo (`github.com/eemokey/glacier`), and she is at USC Computer Science, but that is identity, not a profile |
| Yuheng Ding | `eos6pj2` | `in/yuheng-ding-374398226` (NVIDIA) **or** `in/yuheng-ding` (CMU) | **ambiguous** — neither title matches Peking University, and the name is common. Do not tag |
| Sergey Sosnin | `eos19dk` | `in/serg-sosnin` | **corroborated** — the title shows his current employer (Elpisor Ltd), not the paper's Vienna affiliation; ResearchGate confirms Senior Scientist at the University of Vienna, Dept of Pharmaceutical Sciences, and the GitHub handle behind MolCompass (`github.com/sergsb`) matches the profile slug |
| Seul Lee | `eos84nf` | `in/seul-lee-408a69309` | **corroborated** — title 'Research Intern — NVIDIA'; a KAIST PhD student and GenMol's first author, with NVIDIA co-authors on the paper |
| Bruno N. Falcone | `eos8zvb` | *none found* | **unverified** — the only 'Bruno Falcone' is a Honeywell marketing profile, a different person. The paper's last author Jonathan Hirst is on the platform (`in/jonathan-hirst-13b2354`, University of Nottingham) if this model needs a taggable name |
| Manuel Ruiz-Botella | `eos55vx / eos6a1h` | `in/manuel-ruiz-botella` | **corroborated** — title 'Universitat Rovira i Virgili', and the profile's own content describes CoCoGraph's result (a public database of 8.2 million synthetic molecules, fewer parameters than existing methods) |
| Narek Petrosyan | `eos3xhm` | `in/narek-petrosyan-02632232a` | **corroborated** — title 'American University of Armenia, Yerevan'; `aua.academia.edu/NarekPetrosyan` and the JCIM author list agree |
| Ctibor Škuta | `eos3f8h` | *none found* | **unverified** — only the Institute of Molecular Genetics company page surfaced; no personal profile |

