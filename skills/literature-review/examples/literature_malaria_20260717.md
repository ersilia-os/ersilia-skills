# Literature Research: Malaria (AI/ML drug discovery focus)
*Generated: 2026-07-17 | Engines: Semantic Scholar, Google Scholar (+ PubMed, Europe PMC, PLOS, Crossref, preprints) | Papers: 13 | Hub DOIs excluded: 3 | Pipeline models excluded: 1*

## Overview
*P. falciparum* drug discovery sits on a deep phenotypic-screening data layer (ChEMBL, GSK Tres Cantos, MMV) that ML keeps mining, but the *novel* incorporable pool is modest because the Hub already holds the anchors (MAIP, ZairaChem/H3D, malaria-mam). The strongest genuinely-new, verified-available candidate is an experimentally-validated ChEMBL RF classifier ([Kore et al., 2025](https://doi.org/10.1186/s13065-025-01395-4)); the rest of the leverage is in reusing general open models (few-shot bioactivity, generative) on antimalarial endpoints. A cautionary theme: several prominent antimalarial "tools" fail an availability check (see MalariaFlow below).

## Biology / Target
Artemisinin partial resistance is driven by *Pfkelch13* propeller mutations (C580Y, R561H, R622I, P441L) altering the oxidative-stress/haemoglobin-endocytosis axis, and the field's central worry is now confirmed **spread across East Africa** ([Balmer et al., *eLife*, 2025](https://doi.org/10.7554/eLife.105544)). Validated chemically-tractable targets (PfATP4, PfDHODH, PfDHFR, PfCRT) and the lead-discovery pipeline are surveyed in [Siqueira-Neto et al., 2023](https://doi.org/10.1038/s41573-023-00772-9); structure-guided data mining is re-expanding the druggable genome ([Godínez-Macías et al., 2025](https://doi.org/10.1038/s44386-025-00006-5)).

## Drug Discovery
Antiplasmodial discovery runs mostly on whole-cell phenotypic screens across blood/liver/gametocyte stages, giving ML abundant but stage- and strain-specific labels ([Dorjsuren et al., 2021](https://doi.org/10.1038/s41598-021-81486-z)). Generative chemistry has produced synthesised, experimentally-profiled antimalarial leads ([Godinez et al., 2022](https://doi.org/10.1038/s42256-022-00448-w)).

## Models & Datasets worth integrating
*Ranked pointers to the detail tables below — no TL;DRs here.*

**Models (🤖) — most-incorporable first:**
1. [Kore et al., 2025](https://doi.org/10.1186/s13065-025-01395-4) — direct antimalarial RF activity model; code (KNIME workflow) **and** data openly shared; trivially reproducible.
2. [Feng et al., 2024](https://doi.org/10.1038/s42256-024-00876-w) — ActFound few-shot bioactivity foundation model (code + Zenodo weights); reusable for sparse antimalarial endpoints.
3. [Godinez et al., 2022](https://doi.org/10.1038/s42256-022-00448-w) — JAEGER generative antimalarial design; open Novartis code.
4. [Lamptey et al., 2025](https://doi.org/10.3390/ph18060776) — PLASMOpred AMA1–RON2 invasion-blocker model (⚠ fragile: server-only; ⚠ low-tier venue).

**Datasets (🗃️) — most-incorporable first:**
1. [Dorjsuren et al., 2021](https://doi.org/10.1038/s41598-021-81486-z) — stage-resolved qHTS blood/liver dose-response; deposited in PubChem.
2. [Kore et al., 2025](https://doi.org/10.1186/s13065-025-01395-4) — clean ~15k dose-validated ChEMBL blood-stage set (SI CSVs).

*Hub already covers:* MAIP (antimalarial enrichment), ZairaChem/H3D cascade, malaria-mam. *Still lacks:* a stage-resolved (liver/gametocyte/transmission-blocking) open model and a maintained generative antimalarial.

## Research Gaps
- **Availability is the binding constraint, not modelling.** The most-cited recent antimalarial platform, MalariaFlow ([Lin et al., 2024](https://doi.org/10.1016/j.ejmech.2024.116776)), is effectively **not incorporable** — no code (authors' CV lists "Code: TBD"), paywalled data, and its web server returns 502/expired-cert. Several other tools rest on bare-IP servers (PLASMOpred) that will rot.
- **Stage coverage is lopsided** — almost all open models predict asexual blood-stage activity; liver-stage, gametocyte and transmission-blocking models are scarce despite available screening data.
- **Venue thinness for novel ML** — beyond the two NMI papers, much antimalarial ML sits in low-tier venues (Mol Divers, MDPI *Pharmaceuticals*, IJMS, proceedings); a strong preprint would often beat them.
- **LMIC authorship is real but small** — Nigeria ([Oguike et al., 2022](https://doi.org/10.1007/s11030-022-10380-1)), Ghana ([Lamptey et al., 2025](https://doi.org/10.3390/ph18060776)), Brazil ([Neves et al., 2020](https://doi.org/10.1371/journal.pcbi.1007025)); most large screens/models remain led from HICs/China.
- **Genomic ≠ Hub-trainable** — the big open releases (Pf8 genome variation; druggable-genome mining) are sequence/structure data, outside the Hub's small-molecule input surface — useful for target choice, not directly trainable.

---

## Reviews
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
| [Siqueira-Neto et al., *Nat Rev Drug Discov*, 2023](https://doi.org/10.1038/s41573-023-00772-9) | ⭐ | **Antimalarial drug discovery: progress and approaches.** Definitive survey of validated targets (PfATP4, PfDHODH, PfDHFR, PfCRT), clinical candidates and screening strategy. The framing map for which malaria endpoints are worth modelling. |
| [Tropsha et al., *Nat Rev Drug Discov*, 2023](https://doi.org/10.1038/s41573-023-00832-0) | ⭐ | **Integrating QSAR modelling and deep learning in drug discovery.** State-of-the-art on where classical QSAR and DL each win and how to combine them. Method backbone for how Ersilia should build antimalarial activity models. |
| [Oguike et al., *Mol Divers*, 2022](https://doi.org/10.1007/s11030-022-10380-1) | 🌍 | **Systematic review of ML QSAR against *P. falciparum*.** Nigeria-led (Univ. of Nigeria, Nsukka) synthesis of descriptors, algorithms and datasets used for antiplasmodial QSAR. A ready-made benchmark/feature checklist for a Hub antimalarial model. |
| [Balmer et al., *eLife*, 2025](https://doi.org/10.7554/eLife.105544) | | **Global rise of artemisinin resistance across >100,000 *P. falciparum* samples.** Large-scale genomic account of K13 marker spread into Africa. Defines the resistance endpoints any deployed antimalarial model must stay ahead of. |
| [Turon et al., *Commun Med*, 2025](https://doi.org/10.1038/s43856-025-01211-z) | 🌍 | **Accelerating African infectious-disease drug discovery through data science.** Ersilia-authored perspective on open AI/ML for LMIC drug discovery, malaria included. States the mission and the Hub's role directly. |

## Research papers

### Targets & biology
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
| [Godínez-Macías et al., *npj Drug Discov*, 2025](https://doi.org/10.1038/s44386-025-00006-5) | ⭐ | **Revisiting the *P. falciparum* druggable genome with predicted structures + data mining.** Expands the tractable target list using AlphaFold-era structures. Target-ID (protein/genome input) — out of the small-molecule Hub surface, but guides *which* targets to build compound models against. |

### Activity prediction
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
| [Kore et al., *BMC Chem*, 2025](https://doi.org/10.1186/s13065-025-01395-4) | 🌍🤖🗃️ | **Experimentally validated RF antiplasmodial model.** RF on ~15k ChEMBL blood-stage molecules (Avalon fingerprints), predictions confirmed in vitro; ships a KNIME workflow + train/test CSVs. India-led (BITS Pilani); a clean, reproducible QSAR drop-in and a reusable dataset in one. |
| [Feng et al., *Nat Mach Intell*, 2024](https://doi.org/10.1038/s42256-024-00876-w) | ⭐🤖 | **ActFound — bioactivity foundation model via pairwise meta-learning.** General few-shot bioactivity predictor (code + Zenodo weights) trained on 1.6M ChEMBL activities. Matches Ersilia's low-data/few-shot framing; usable for sparse antimalarial endpoints. |
| [Gholami & Asadollahi-Baboli, *Mol Divers*, 2025](https://doi.org/10.1007/s11030-025-11203-9) | 🌍 | **Ensemble ML for PfPK6 inhibitors.** Target-specific kinase QSAR over 104 compounds (majority-vote accuracy ~91%). Iran-led; interesting but small, and no code/weights/server could be located (⚠ low-tier venue) — context, not an incorporation candidate as it stands. |
| [Lamptey et al., *Pharmaceuticals*, 2025](https://doi.org/10.3390/ph18060776) | 🌍🤖 | **PLASMOpred.** Web app predicting small-molecule blockers of the AMA1–RON2 invasion complex; server responding as of 2026-07-17 but on a bare IP with no code (⚠ fragile: server-only; ⚠ low-tier venue). Ghana-led (WACCBIP) — kept as the only LMIC-authored antimalarial ML web tool; small-molecule input, so Hub-eligible while it stays up. |
| [Lin et al., *Eur J Med Chem*, 2024](https://doi.org/10.1016/j.ejmech.2024.116776) | | **MalariaFlow (context only — fails availability).** Multistage FP-GNN platform reporting AUROC 0.90 over a 407k-compound benchmark. **Not incorporable:** no public code (authors' CV: "Code: TBD"), paywalled dataset, and web server returns 502 Bad Gateway with an expired certificate. Listed so the team knows the prominent option is a dead end unless the authors release artifacts. |

### Generation
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
| [Godinez et al., *Nat Mach Intell*, 2022](https://doi.org/10.1038/s42256-022-00448-w) | ⭐🤖 | **JAEGER generative chemistry for antimalarials (JT-VAE).** Designs, synthesises and experimentally profiles novel antimalarial scaffolds; code open at github.com/Novartis/JAEGER. Landmark proof that generation→synthesis closes for malaria; reference for a Hub generative model. |

### Datasets & benchmarks
| Paper | Markers | Data location | TL;DR + why for Ersilia |
|---|---|---|---|
| [Dorjsuren et al., *Sci Rep*, 2021](https://doi.org/10.1038/s41598-021-81486-z) | 🗃️ | [PubChem AID 1347417](https://pubchem.ncbi.nlm.nih.gov/bioassay/1347417) (+ 1347416, 488774) | **qHTS of blood- and liver-stage *Plasmodium*.** Dose-response chemoprotective screen across stages, deposited openly in PubChem — a stage-resolved training/benchmark set the Hub currently lacks. |

*(Kore's ChEMBL set is also openly available as SI CSVs but carries 🤖, so it is described in its Activity-prediction row rather than duplicated here.)*

---

## Search Log
| Engine/Source | Query | Results |
|---|---|---|
| Semantic Scholar | malaria machine learning antimalarial activity prediction | 429-throttled |
| Semantic Scholar | Plasmodium falciparum deep learning drug discovery QSAR | 15 |
| Google Scholar / web | Pf antimalarial ML activity prediction model 2025 github | 7 |
| Google Scholar / web | antimalarial generative de novo molecular design DL 2024/2025 | 10 |
| Google Scholar / web | Pf open dataset bioactivity benchmark screening download | 9 |
| Google Scholar / web | artemisinin resistance Kelch13 mechanism review Africa | 8 |
| Google Scholar / web | H3D Africa antimalarial ML ZairaChem Ersilia | 10 |
| Google Scholar / web | bio-informed / transcriptomic QSAR antimalarial github | 7 |
| Google Scholar / web | molecular featurization foundation model ADMET github | 10 |
| Google Scholar / web | Neves deep learning tackling malaria LabMol | 6 |
| Crossref | DOI + author/date verification (7 DOIs) | verified |
| Availability checks | web server liveness + repo/accession resolution (7 items) | verified |
| Hub exclusion | ErsiliaModelsDOI.csv (143 DOIs) | 3 dropped |
| Pipeline exclusion | new-model issues (185 keys, 199/250 issues) | 1 dropped |

---

## Already covered — excluded from the review
*Candidates found during search but dropped in Step 5 because they are already in the Hub or the incorporation pipeline. Listed for transparency; not part of the novel-literature set above.*

| Item | DOI | Reason |
|---|---|---|
| [MAIP — blood-stage malaria inhibitor predictor](https://doi.org/10.1186/s13321-021-00487-2) | `10.1186/s13321-021-00487-2` | Hub |
| [ZairaChem / H3D virtual-screening cascade](https://doi.org/10.1038/s41467-023-41512-2) | `10.1038/s41467-023-41512-2` | Hub |
| [malaria-mam](https://doi.org/10.1021/acsomega.3c05664) | `10.1021/acsomega.3c05664` | Hub |
| [NPBERT — antimalarial natural-product BERT](https://doi.org/10.1021/acs.jcim.1c00584) | `10.1021/acs.jcim.1c00584` | Pipeline (repo already requested) |
