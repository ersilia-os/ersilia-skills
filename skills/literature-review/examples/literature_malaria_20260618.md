# Literature Research: Malaria (AI/ML drug discovery focus)
*Generated: 2026-06-18 | Engines: Semantic Scholar, Google Scholar (+ PubMed, Europe PMC, PLOS, Crossref, preprints) | Papers: 16 | Hub DOIs excluded: 3 (MAIP `s13321-021-00487-2`, ZairaChem `s41467-023-41512-2`, malaria-mam `acsomega.3c05664`)*

## Overview
*P. falciparum* drug discovery has a deep phenotypic-screening data layer (ChEMBL, GSK Tres Cantos, MMV) that ML increasingly mines, but the novel-literature pool is modest because the Hub already holds the obvious anchors (MAIP, ZairaChem, malaria-mam). The most incorporable new work is multistage phenotypic activity models and experimentally-validated ChEMBL classifiers ([Lin et al., 2024](https://doi.org/10.1016/j.ejmech.2024.116776); [Kore et al., 2025](https://doi.org/10.1186/s13065-025-01395-4)).

## Biology / Target
Artemisinin partial resistance is driven by *Pfkelch13* propeller mutations (C580Y, R539T) that slow ring-stage drug activation and boost antioxidant defence; the field's worry is now African spread ([Ward et al., 2022](https://doi.org/10.1016/j.mib.2022.102193); [Azmi et al., 2023](https://doi.org/10.1016/j.meegid.2023.105460)). Validated chemical-biology targets (PfATP4, PfDHODH, PfDHFR, PfCRT) and the lead-discovery pipeline are surveyed in [Siqueira-Neto et al., 2023](https://doi.org/10.1038/s41573-023-00772-9).

## Drug Discovery
Antiplasmodial discovery runs largely on whole-cell phenotypic screens across blood/liver/gametocyte stages, with hits triaged to targets post hoc; this gives ML abundant labelled actives but stage- and strain-specific noise ([Dorjsuren et al., 2021](https://doi.org/10.1038/s41598-021-81486-z)). Generative chemistry has produced synthesised, experimentally-profiled antimalarial leads ([Godinez et al., 2022](https://doi.org/10.1038/s42256-022-00448-w)).

## Models & Datasets worth integrating
**Models (🤖) — most-incorporable first:**
1. **MalariaFlow** ([Lin et al., *Eur J Med Chem*, 2024](https://doi.org/10.1016/j.ejmech.2024.116776)) — FP-GNN/GCN/AttentiveFP ensemble over 15 multistage *P. falciparum* phenotypic sets; open web server. Direct activity-prediction incorporation.
2. **RF antiplasmodial classifier** ([Kore et al., *BMC Chem*, 2025](https://doi.org/10.1186/s13065-025-01395-4)) — RF on ~15k ChEMBL blood-stage molecules, Avalon fingerprints, experimentally validated; trivially reproducible QSAR.
3. **Pretrained BERT for natural products** ([Nguyen-Vo et al., *JCIM*, 2021](https://doi.org/10.1021/acs.jcim.1c00584)) — chemical-language featurizer + antimalarial activity head.
4. **PfPK6 inhibitor ensemble** ([Gholami et al., *Mol Divers*, 2025](https://doi.org/10.1007/s11030-025-11203-9)) — target-specific kinase QSAR (R²≈0.94).
5. **PLASMOpred** ([Lamptey et al., *Pharmaceuticals*, 2025](https://doi.org/10.3390/ph18060776)) — web app for AMA1–RON2 invasion-blocker activity (⚠ low-tier venue; kept as the only Ghana-led antimalarial ML model).

General-purpose featurizers worth a separate look: [Feng et al., *NMI*, 2024](https://doi.org/10.1038/s42256-024-00876-w) (bioactivity foundation model, few-shot) and [Godinez et al., *NMI*, 2022](https://doi.org/10.1038/s42256-022-00448-w) (generative).

**Datasets (🗃️):**
1. **MalariaFlow 15-set corpus** — 410,673 unique molecules, 16,585 actives, multistage ([Lin et al., 2024](https://doi.org/10.1016/j.ejmech.2024.116776)).
2. **qHTS blood + liver-stage screen** — chemoprotective antimalarials, dose-response across stages ([Dorjsuren et al., 2021](https://doi.org/10.1038/s41598-021-81486-z)).
3. **ChEMBL ~15k blood-stage actives** — clean, dose-validated training set ([Kore et al., 2025](https://doi.org/10.1186/s13065-025-01395-4)).

*Hub already covers:* MAIP (antimalarial enrichment), ZairaChem cascade (H3D), malaria-mam. *Still lacks:* a stage-resolved (liver/gametocyte/transmission-blocking) open model and a maintained generative antimalarial.

## Research Gaps
- **Stage coverage is lopsided** — almost all open models predict asexual blood-stage activity; liver-stage, gametocyte and transmission-blocking models are scarce despite available data.
- **Venue thinness for novel ML** — beyond MalariaFlow and the two NMI papers, much antimalarial-ML sits in mid/low-tier venues (BMC Chem, Mol Divers, MDPI *Pharmaceuticals*); a strong preprint would often beat them.
- **LMIC authorship is real but small** — Nigeria ([Oguike et al.](https://doi.org/10.1007/s11030-022-10380-1), [Isewon et al.](https://doi.org/10.1371/journal.pone.0315530)), Ghana ([Lamptey et al.](https://doi.org/10.3390/ph18060776)); most large screens/models remain led from HICs/China.
- **Unverified repo links** — MalariaFlow ships a web server but no public code repo was confirmed (no 💻); reproducibility rests on the server staying up.
- **No clean novel-resistance ML** — *Pfkelch13*/PfATP4 resistance prediction from sequence is out of the small-molecule Hub surface; surfaced as biology context only.

---

## Reviews
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
| [Siqueira-Neto et al., *Nat Rev Drug Discov*, 2023](https://doi.org/10.1038/s41573-023-00772-9) | ⭐ | **Antimalarial drug discovery: progress and approaches.** Definitive survey of validated targets (PfATP4, PfDHODH, PfDHFR, PfCRT), clinical candidates and screening strategy. The framing map for which malaria endpoints are worth modelling. |
| [Oguike et al., *Mol Divers*, 2022](https://doi.org/10.1007/s11030-022-10380-1) | 🌍 | **Systematic review of ML QSAR against *P. falciparum*.** Nigeria-led (Univ. of Nigeria, Nsukka) synthesis of descriptors, algorithms and datasets used for antiplasmodial QSAR. A ready-made benchmark/feature checklist for a Hub antimalarial model. |
| [Ward et al., *Curr Opin Microbiol*, 2022](https://doi.org/10.1016/j.mib.2022.102193) | | **Pf resistance to artemisinin-based combination therapies.** Mechanistic account of K13-driven ring-stage survival and partner-drug failure. Defines the resistance endpoints any deployed model must stay ahead of. |
| [Azmi et al., *Infect Genet Evol*, 2023](https://doi.org/10.1016/j.meegid.2023.105460) | | **Molecular insights into artemisinin resistance (updated).** Consolidates K13 propeller markers (C580Y, R539T, I543T) and the redox/proteostasis model of resistance. Background for resistance-aware compound prioritisation. |
| [Turon et al., *Commun Med*, 2025](https://doi.org/10.1038/s43856-025-01211-z) | | **Accelerating African infectious-disease drug discovery through data science.** Ersilia-authored perspective on open AI/ML for LMIC drug discovery, malaria included. Directly states the mission and the Hub's role. |

## Research papers

### Targets & biology
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
| [Isewon et al., *PLOS ONE*, 2024](https://doi.org/10.1371/journal.pone.0315530) | 🌍 | **ML prediction of essential metabolic genes in the *P. falciparum* metabolic network.** Nigeria-led (Covenant University) target-ID using network + ML features. Gene-level input, so out of the small-molecule Hub surface — useful for choosing *which* targets to build compound models against. |

### Activity prediction
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
| [Lin et al., *Eur J Med Chem*, 2024](https://doi.org/10.1016/j.ejmech.2024.116776) | 🤖🗃️ | **MalariaFlow.** Benchmarks fingerprint-ML, GNNs and co-representation models across 15 multistage phenotypic sets (FP-GNN best, AUROC 0.90); open web server + datasets. The single strongest incorporation candidate — a multistage antimalarial activity model. |
| [Feng et al., *Nat Mach Intell*, 2024](https://doi.org/10.1038/s42256-024-00876-w) | ⭐🤖 | **Bioactivity foundation model via pairwise meta-learning.** General few-shot bioactivity predictor that transfers to low-data assays. Matches Ersilia's low-data/few-shot framing; usable for sparse antimalarial endpoints. |
| [Kore et al., *BMC Chem*, 2025](https://doi.org/10.1186/s13065-025-01395-4) | 🌍🤖🗃️ | **Experimentally validated RF antiplasmodial model.** RF on ~15k ChEMBL blood-stage molecules with Avalon fingerprints; predictions confirmed in vitro. India-led (BITS Pilani); a clean, reproducible QSAR drop-in. |
| [Hlozek et al., *ACS Med Chem Lett*, 2024](https://doi.org/10.1021/acsmedchemlett.4c00243) | | **Prospective validation of AI/ML tools at an African drug discovery centre.** Reports the H3D virtual-screening cascade (built with Ersilia/ZairaChem) in production for malaria & TB. Real-world deployment evidence for Hub-style models. |
| [Gholami et al., *Mol Divers*, 2025](https://doi.org/10.1007/s11030-025-11203-9) | 🌍🤖 | **Ensemble ML for PfPK6 inhibitors.** Target-specific kinase QSAR (R²≈0.94). Iran-led (Babol Noshirvani); incorporable as a focused target model. |
| [Lamptey et al., *Pharmaceuticals*, 2025](https://doi.org/10.3390/ph18060776) | 🌍🤖 | **PLASMOpred (⚠ low-tier venue).** Web app predicting small-molecule blockers of the AMA1–RON2 invasion complex. Ghana-led (WACCBIP, Univ. of Ghana) — kept as the only LMIC-authored antimalarial ML web tool; small-molecule input, so Hub-eligible. |

### Featurization
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
| [Nguyen-Vo et al., *JCIM*, 2021](https://doi.org/10.1021/acs.jcim.1c00584) | 🤖 | **Pretrained bidirectional transformer for antimalarial natural products.** Chemical-language embeddings feeding an activity head; targets the under-modelled natural-product chemical space. Featurizer + activity model in one — a recurring Hub pattern. |

### Generation
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
| [Godinez et al., *Nat Mach Intell*, 2022](https://doi.org/10.1038/s42256-022-00448-w) | ⭐🤖 | **Generative chemistry for potent antimalarials (JAEGER, JT-VAE).** Designs, then synthesises and experimentally profiles novel antimalarial scaffolds via pQSAR prioritisation. Landmark proof that generation→synthesis closes for malaria; reference for a Hub generative model. |

### Datasets & benchmarks
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
| [Dorjsuren et al., *Sci Rep*, 2021](https://doi.org/10.1038/s41598-021-81486-z) | 🗃️ | **qHTS of blood- and liver-stage *Plasmodium*.** Dose-response chemoprotective screen across stages — a stage-resolved training/benchmark set the Hub lacks. |

---

## Search Log
| Engine/Source | Query | Results |
|---|---|---|
| Semantic Scholar | malaria machine learning antimalarial activity prediction | 15 (rest 429-throttled) |
| Google Scholar / web | Pf antimalarial ML activity prediction model 2024 | 8 |
| Google Scholar / web | malaria drug discovery deep learning dataset open source | 10 |
| Google Scholar / web | artemisinin resistance Kelch13 mechanism review | 8 |
| Google Scholar / web | generative de novo antimalarial GNN 2024/2025 | 9 |
| Google Scholar / web | Pf HTS dataset ChEMBL phenotypic 2024 | 7 |
| Google Scholar / web | Africa/LMIC ML antimalarial QSAR (H3D, Nigeria) | 6 |
| Google Scholar / web | foundation model featurization antimalarial transfer learning | 8 |
| Google Scholar / web | PfATP4/PfDHODH target structure review | 8 |
| Google Scholar / web | MalariaFlow github/web server | 7 |
| Crossref | DOI + author/date verification (12 DOIs) | verified |
| Europe PMC (core) | author affiliations for 🌍 (6 papers) | verified |
| Hub exclusion | ErsiliaModelsDOI.csv (143 DOIs) | 3 candidates dropped |
