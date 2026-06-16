# Literature Research: Malaria
*Generated: 2026-06-16 | Sources: Nature, Science, Cell, PubMed, Europe PMC, PLOS, bioRxiv, ChemRxiv, arXiv | Papers: 10 | Depth: focused*

---

## Overview

Malaria remains one of the most pressing infectious disease challenges globally, caused primarily by *Plasmodium falciparum* and *P. vivax* and transmitted by female *Anopheles* mosquitoes. The WHO World Malaria Report 2024 recorded approximately **263 million cases and 597,000 deaths in 2023** — an increase of 11 million cases from the prior year — with 94–95% of the burden concentrated in sub-Saharan Africa and disproportionately affecting children under five.

The central crisis driving the current literature is the **emergence and spread of artemisinin partial resistance (ART-R)** in Africa. Artemisinin-based combination therapies (ACTs) have anchored global malaria control since the early 2000s, reducing mortality substantially. However, mutations in the *P. falciparum* Kelch 13 protein (PfK13) — which first enabled ART-R in Southeast Asia — have now arisen independently in Rwanda, Uganda, the Horn of Africa, and are spreading across the Great Rift Valley. This has triggered urgent calls for new therapeutic scaffolds that bypass artemisinin entirely.

On the drug discovery front, two converging developments mark the current period. First, the **Phase 3 success of ganaplacide-lumefantrine (GanLum/KLU156)** announced at ASTMH 2025 — 97.4% PCR-corrected cure rate in 1,600+ participants across 12 sub-Saharan African countries — signals that a non-artemisinin first-line treatment may be imminent. Second, **AI/ML tools for antiplasmodial activity prediction** have matured substantially: from early graph neural networks (2019–2020) to multi-stage, multi-task deep learning platforms covering asexual blood stages, liver stages, and sexual/gametocyte stages simultaneously (2024).

For Ersilia, this literature is directly actionable: the ChEMBL-curated antiplasmodial bioactivity datasets powering QSAR and GNN models are Hub-compatible, several open-access activity-prediction tools (MalariaFlow, LabMol deep-QSAR models) represent prime Hub incorporation candidates, and the emergence of ART-R creates urgent demand for models trained on resistance phenotype data (IC50/clearance half-life endpoints).

---

## Disease / Target Biology

*P. falciparum* causes the most severe form of malaria by invading red blood cells through a tightly regulated sequence of egress, invasion, intra-erythrocytic replication, and gametocytogenesis. Key validated drug targets in the blood stage include dihydrofolate reductase (PfDHFR), dihydroorotate dehydrogenase (PfDHODH), phosphatidylinositol 4-kinase (PfPI4K), plasmepsins IX/X, and aminoacyl-tRNA synthetases. The liver stage — where sporozoites form hypnozoites in *P. vivax* — is harder to target but represents a single-passage vulnerability with potential for radical cure.

The **PfK13 protein** has become the defining resistance locus of the current era. Its propeller domain mutations (most critically C580Y, R539T, R561H, and A675V) confer ring-stage survival under artemisinin pressure. Rosenthal, Asua & Conrad (2024, *Nature Reviews Microbiology*; DOI: 10.1038/s41579-024-01008-2) provide the most comprehensive current synthesis of this landscape, documenting that K13-mutant parasites have now emerged independently in Rwanda, Uganda, Tanzania, Ethiopia, and Eritrea. Critically, high ACT failure rates occur when resistance to partner drugs (lumefantrine, piperaquine, amodiaquine) compounds the ART-R, exactly as occurred in Southeast Asia. This parallel trajectory makes the African ART-R epidemic a potential public health emergency of the first order.

Mechanistically, ART-R is multi-factorial. Zhu et al. (2022, *Communications Biology*; DOI: 10.1038/s42003-022-03215-0) analysed 577 clinical GMS isolates by transcriptomics and found that a specific ART-R transcriptional profile — encompassing proteotoxic stress, host cytoplasm remodelling, and REDOX metabolism — evolved from the initial stress-response profile of drug-sensitive parasites. More recently, a 2024 *Nature Microbiology* study (DOI: 10.1038/s41564-024-01664-3) revealed a novel **epitranscriptomic layer**: ART-R parasites differentially hypomodify mcm5s2U tRNA modifications post-drug, and a subset of proteins including PfK13 itself are regulated by Lys codon-biased translation. Conditional knockdown of the s2U thiouridylase PfMnmA in a drug-sensitive background was sufficient to increase artemisinin survival, identifying a new resistance determinant entirely upstream of K13 mutations.

---

## Drug Discovery Approaches

Winzeler (2023, *Nature Reviews Drug Discovery*; DOI: 10.1038/s41573-023-00772-9) provides the definitive current overview of antimalarial drug discovery strategies: cell-based whole-organism phenotypic screening (the source of most modern scaffolds), target-based rational design, and chemogenomic/resistome profiling to reveal novel targets. The review documents a pipeline of roughly 15 compounds in clinical development, including candidates targeting PfPI4K, PfATP4, tRNA synthetases, and cytochrome bc1. The emergence of ART-R has sharpened the focus on **whole-lifecycle activity** — gametocytocidal, liver-stage, and transmission-blocking properties are now considered mandatory in modern target product profiles.

The most clinically consequential advance is **ganaplacide (KAF156)**, a novel imidazolopiperazine identified via high-throughput screening of 2.3 million compounds, with a mechanism of action entirely distinct from artemisinins and all licensed antimalarials. In combination with a new once-daily solid dispersion formulation of lumefantrine (GanLum/KLU156), the KALUMA Phase 3 trial (March 2024 – June 2025, 34 sites in 12 African countries, n > 1,600) achieved a PCR-corrected cure rate of 97.4% vs. 94.0% for Coartem, meeting the non-inferiority primary endpoint. In vitro data (Manaranche et al., *JAC*, 2024; DOI: 10.1093/jac/dkae300) confirm that ganaplacide retains full activity against ART-R K13-mutant parasites circulating in Africa. In addition, ganaplacide clears gametocytes faster than Coartem, offering a transmission-blocking bonus.

Winzeler and colleagues (2024, *Science*; DOI: 10.1126/science.adk9893) applied **systematic in vitro evolution** across a broad panel of antimalarial compound classes to map key resistance determinants genome-wide. This atlas of the P. falciparum resistome provides actionable guidance for both target prioritisation (genes where no resistance mutations exist are more druggable) and for designing drug combinations that resist sequential resistance evolution.

---

## AI/ML Methods

The computational landscape for antiplasmodial drug discovery has advanced rapidly from classical QSAR towards graph-based and multi-representation deep learning.

**Neves et al. (2020, *PLOS Computational Biology*; DOI: 10.1371/journal.pcbi.1007025)** is the foundational modern paper. The LabMol group (Brazil) built binary and continuous deep-QSAR models on a large antiplasmodial dataset and applied them to virtual screening; two hits (LabMol-149, LabMol-152) showed nanomolar activity (EC50 < 500 nM) with low cytotoxicity on experimental validation against multi-drug-resistant *P. falciparum* strains. The code and models were released openly, making it Hub-eligible.

**Lin et al. (2024, *European Journal of Medicinal Chemistry*)** introduced **MalariaFlow**, the first multi-stage deep learning platform covering liver-stage (LS), asexual blood-stage (ABS), and sexual/gametocyte-stage (SGS) simultaneously across 10 Plasmodium phenotypic endpoints. Benchmarking of nine architectures (RF, XGBoost, GCN, GAT, MPNN, AttentiveFP, FP-GNN, HiGNN, FG-BERT) showed the **FP-GNN co-representation model** outperformed all others (AUROC 0.900), while fingerprint-based ML outperformed pure GNNs on large datasets. A web server was released for virtual screening and similarity search. This is a strong Hub incorporation candidate: small-molecule SMILES input, multi-stage activity prediction endpoint, open web server.

**Ncube, Tukulula & Govender (2024, *Journal of Cheminformatics*; DOI: 10.1186/s13321-024-00842-z)** provide a structured comparative review of virtual screening, molecular docking, AI, and ML strategies for malaria therapeutics. The review benchmarks docking-based, ligand-based, and deep learning workflows against published hit rates and identifies the GSK/MMV open compound datasets as the highest-quality training resources for activity models.

Across these papers, there is broad **consensus** that graph-based co-representation models (combining molecular fingerprints with GNN featurisation) outperform either approach alone. There is **ongoing disagreement** about whether phenotypic whole-cell models (which capture all mechanisms simultaneously) are superior to target-based models for the primary screening task; the consensus is shifting toward multi-stage phenotypic models, but target-based models retain value for mechanism deconvolution and selectivity profiling.

---

## Research Gaps

- **LMIC-led computational work is essentially absent.** No computational drug discovery papers with LMIC first or senior authorship appeared across the comprehensive search. The groups producing antiplasmodial AI models are predominantly in Brazil, China, South Korea, and South Africa (upper-middle income), and the US/EU. This is a critical gap for a disease whose burden falls almost exclusively on low-income African countries.
- **ART-R modelling for Africa.** Existing ML models are trained predominantly on *P. falciparum* 3D7 (drug-sensitive) bioactivity data. Very few models predict activity against the K13-mutant resistant strains now prevalent in eastern Africa. Training data capturing resistance phenotype (IC50 or RSA values in K13-mutant backgrounds) from African clinical isolates remains scarce in public databases.
- **Liver-stage and gametocyte endpoint data.** MalariaFlow is the first platform to cover multiple lifecycle stages, but the underlying datasets for liver-stage and gametocyte activity prediction are roughly 10× smaller than blood-stage datasets, constraining model quality.
- **Bioactivity dataset integration.** ChEMBL, MMV's open datasets, and the GSK Tres Cantos Open set contain substantial antiplasmodial data but with inconsistent assay standardisation. A harmonised, stage-annotated, resistance-stratified benchmark dataset would unlock substantially better model performance.
- **Open-access tools for partnership with African research institutions.** The Ersilia Model Hub is well-positioned to fill the gap in open, deployable, low-resource-compatible antiplasmodial prediction tools that African partners can run without cloud compute.

---

## Curated Entry List

### Tier 1 — Core papers

- [Winzeler, *Nat Rev Drug Discov*, 2023](https://doi.org/10.1038/s41573-023-00772-9) ⭐ — **Antimalarial drug discovery: progress and approaches.** Comprehensive 2023 review of cell-based screening, target-based approaches, and the current clinical pipeline (~15 candidates); covers whole-lifecycle target product profiles and the impact of ART-R on drug development strategy. Essential entry-point for Ersilia's antimalarial pipeline orientation.

- [Okombo & Fidock, *Nat Rev Microbiol*, 2025](https://doi.org/10.1038/s41579-024-01099-x) ⭐ — **Towards next-generation treatment options to combat Plasmodium falciparum malaria.** 2025 synthesis of the new treatment landscape post-ART-R: vaccines (RTS,S, R21), ganaplacide and other pipeline candidates, and strategies to preserve ACT utility. Directly frames the translational urgency for Ersilia's drug-discovery models.

- [Rosenthal, Asua & Conrad, *Nat Rev Microbiol*, 2024](https://doi.org/10.1038/s41579-024-01008-2) ⭐ — **Emergence, transmission dynamics and mechanisms of artemisinin partial resistance in Africa.** Definitive 2024 review documenting the independent emergence of K13 mutations across multiple African countries, the epidemiology of their spread, and the molecular mechanisms of ring-stage survival. Establishes the biological context for why new antimalarials must be active against ART-R strains — directly relevant to activity model training priorities.

- [Authors et al., *Nat Microbiol*, 2024](https://doi.org/10.1038/s41564-024-01664-3) ⭐ — **tRNA modification reprogramming contributes to artemisinin resistance in Plasmodium falciparum.** Reveals a novel epitranscriptomic mechanism: ART-R parasites differentially hypomodify mcm5s2U tRNA post-drug, regulating translation of PfK13 and other resistance proteins via codon bias. Identifies PfMnmA as a new potential drug target upstream of K13, expanding the target landscape for Ersilia.

- [Datoo et al., *Lancet*, 2024](https://doi.org/10.1016/S0140-6736(23)02511-4) ⭐ — **Safety and efficacy of malaria vaccine candidate R21/Matrix-M in African children: a multicentre, double-blind, randomised, phase 3 trial.** Phase 3 trial across four African countries (n = 4,800 children aged 5–36 months) showing 75% efficacy with seasonal dosing and 68% with age-based dosing. The highest-efficacy malaria vaccine result on record; WHO prequalified R21 in 2023. Positions vaccine-chemotherapy combinations as the new standard-of-care framework that Ersilia's pipeline models will operate within.

- [Winzeler et al., *Science*, 2024](https://doi.org/10.1126/science.adk9893) ⭐ — **Systematic in vitro evolution in Plasmodium falciparum reveals key determinants of drug resistance.** Genome-wide map of resistance mutations arising in vitro across multiple compound classes, providing an atlas of the *P. falciparum* resistome. Identifies loci where no resistance mutations arise (highly druggable targets) and informs rational combination design. Directly useful for training resistance-aware ML models and prioritising Hub model endpoints.

### Tier 2 — Supporting papers

- [Zhu et al., *Commun Biol*, 2022](https://doi.org/10.1038/s42003-022-03215-0) — **Artemisinin resistance in the malaria parasite originates from its initial transcriptional response.** Transcriptome analysis of 577 clinical isolates from the Greater Mekong Subregion identifies the ART-R transcriptional signature — proteotoxic stress, REDOX, cytoplasm remodelling — as an evolved form of the natural stress response of susceptible parasites. Provides the transcriptomic dataset context for signature-based drug-target prioritisation tools.

- [Neves et al., *PLOS Comput Biol*, 2020](https://doi.org/10.1371/journal.pcbi.1007025) 🤖 — **Deep Learning-driven research for drug discovery: Tackling Malaria.** *Seminal.* LabMol group built binary and continuous deep-QSAR models for antiplasmodial activity and cytotoxicity; virtual screening identified two nanomolar hits (LabMol-149/152) validated experimentally. Open models trained on drug-sensitive and multi-drug-resistant *P. falciparum* strains. Strong Hub activity-prediction candidate; training dataset (ChEMBL-curated ~15,000 compounds) is a direct resource for Ersilia.

- Lin et al., *Eur J Med Chem*, 2024 🤖 — **MalariaFlow: A comprehensive deep learning platform for multistage phenotypic antimalarial drug discovery.** First platform covering liver-stage, blood-stage, and gametocyte-stage endpoints simultaneously (10 phenotypic classes). Benchmarks nine architectures; FP-GNN (AUROC 0.900) outperforms standalone GNNs and fingerprint models. Releases a public web server for virtual screening and similarity search. Highest-priority Hub incorporation candidate in this review (small-molecule input, activity prediction, open web access). *Note: DOI not confirmed at time of writing; access via the MalariaFlow web server directly.*

- [Ncube, Tukulula & Govender, *J Cheminform*, 2024](https://doi.org/10.1186/s13321-024-00842-z) — **Leveraging computational tools to combat malaria: assessment and development of new therapeutics.** Comparative review of virtual screening, docking, AI, and ML strategies for antimalarial discovery from the University of KwaZulu-Natal. Benchmarks docking-based vs. ligand-based vs. deep learning workflows, identifies the GSK/MMV open compound libraries as optimal training resources. Useful methodological reference for Ersilia's model selection and validation pipelines.

---

## Known Gaps

- **LMIC authorship:** No Tier 1 or Tier 2 paper in this review has a first or senior author at a low- or lower-middle-income institution. This is a structural gap in the current computational malaria literature, not a reflection of African scientific activity (which is primarily in epidemiology and clinical research). Ersilia can address this directly by partnering with African institutions on model development.
- **Resistance-stratified bioactivity data:** No open, curated, K13-mutant-background activity dataset exists for training ML models on ART-R parasites. This is the single highest-value dataset gap identified in this review.
- **P. vivax computational models:** Almost all ML activity models target *P. falciparum*. P. vivax (up to 48% of cases in Southeast Asia) has a different biology (hypnozoites, different metabolic pathways) and essentially no dedicated Hub-compatible activity-prediction models.
- **Ganaplacide Phase 3 publication:** Results of the KALUMA trial were announced at ASTMH November 2025 but had not appeared in a peer-reviewed journal at the time of this review. Ersilia should monitor for the primary paper (likely Lancet or NEJM) as it will contain the most complete efficacy and safety dataset for a non-artemisinin first-line drug.

---

## Search Log

| Source | Query | Results retrieved |
|---|---|---|
| Nature (nature.com) | malaria Plasmodium falciparum drug discovery 2023–2025 | 6 |
| Nature (nature.com) | malaria artemisinin resistance mechanism 2023–2025 | 5 |
| Nature (nature.com) | malaria artemisinin partial resistance Africa 2024–2025 | 6 |
| Science (science.org) | malaria Plasmodium drug target 2023–2025 | 7 |
| PubMed | malaria machine learning deep learning drug discovery 2024–2025 | 7 |
| PLOS | malaria drug discovery antimalarial 2024–2025 | 6 |
| bioRxiv | malaria Plasmodium AI machine learning activity prediction 2024–2025 | 6 |
| Europe PMC | malaria antiplasmodial QSAR GNN 2024–2025 | 5 |
| Web (general) | KAF156 ganaplacide clinical trial phase 3 2024–2025 | 7 |
| Web (general) | R21 Matrix-M malaria vaccine efficacy 2024 Lancet Nature | 6 |
| Web (general) | MalariaFlow deep learning multistage antiplasmodial 2024 | 7 |
| Web (general) | malaria AI drug discovery transformer GNN antiplasmodial ChEMBL 2024–2025 | 7 |
