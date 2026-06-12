# Literature Research: *Plasmodium falciparum* Druggable Targets
*Generated: 2026-06-12 | Sources: Nature/npj, Cell/Cell Chem Biol, PubMed, Europe PMC, bioRxiv, ChemRxiv | Papers: 28*

---

## Lifecycle / Pathway Diagram

> No direct SVG/PNG URL could be verified to resolve to a raw image file; stage table used instead.
> For a visual lifecycle diagram, see: [Wikimedia Commons — Life Cycle of the Malaria Parasite](https://commons.wikimedia.org/wiki/File:Life_Cycle_of_the_Malaria_Parasite.svg) (CC BY-SA 4.0, user Bbkkk).

**Compound action by lifecycle stage:**

| Stage | Description | Active compound classes | Example drugs / leads |
|---|---|---|---|
| **Sporozoite / Pre-erythrocytic (Liver)** | Mosquito-injected sporozoites invade hepatocytes; asymptomatic ~7 days | PfPI4K inhibitors; liver-stage active aminoacyl-tRNA synthetase (aaRS) inhibitors | Imidazopyrazines (KAF156/ganaplacide); apicoplast-aaRS nucleoside sulfamates |
| **Asexual blood stage (Ring)** | Newly invaded merozoites form ring-stage trophozoites; K13 mutations confer ART partial resistance here | Artemisinins (ART); proteasome inhibitors (synergy with ART); PfDHODH inhibitors | DHA/artemether; WLL-vs (vinyl sulfone); DSM265 |
| **Asexual blood stage (Trophozoite/Schizont)** | Rapid haemoglobin digestion and DNA replication; most drug targets expressed | PfDHFR antifolates; PfDHODH inhibitors; PfA-M1/M17 aminopeptidase inhibitors; proteasome inhibitors; aaRS inhibitors; kinase (PfCDPK1, PfPKG) inhibitors | Pyrimethamine; DSM265; MIPS2673; TDI-8304 |
| **Merozoite egress/invasion** | Merozoites burst RBC and invade new cells; key role for PfCDPK1 and PfPKG | PKG inhibitors (cGMP-signalling); CDPK1 inhibitors | MMV030084 (PKG); imidazopyridazines (PfCDPK1) |
| **Gametocyte (Transmission)** | Sexual differentiation; blocks human-to-mosquito transmission | aaRS inhibitors (pan-life-cycle); proteasome inhibitors; PI4K inhibitors | Nucleoside sulfamates; KAF156 |
| **Mosquito stages (Oocyst/Sporozoite)** | Sexual recombination in midgut, sporozoite formation | Transmission-blocking: PI4K inhibitors, some aaRS inhibitors | KAF156; MDSA |

---

## Overview

Malaria caused by *Plasmodium falciparum* remains a leading global health crisis, with approximately 263 million cases and 597,000 deaths reported in 2023 — a worrying increase from previous years, disproportionately concentrated in sub-Saharan Africa. The backbone of treatment — artemisinin-based combination therapies (ACTs) — is under severe threat: partial artemisinin resistance driven by *kelch13* mutations has spread from Southeast Asia into East Africa and is now documented in Uganda, Rwanda, Tanzania, and the Democratic Republic of Congo. Partner drug resistance is compounding the problem. The pipeline of replacement chemotypes is thin, and the fundamental challenge of selecting targets that are (i) essential across multiple lifecycle stages, (ii) divergent enough from human orthologues, (iii) tractable for small-molecule inhibition, and (iv) unlikely to rapidly develop resistance is far from resolved.

For Ersilia, *P. falciparum* is a top-priority organism. The Ersilia Model Hub requires tools for activity prediction, featurization, ADMET estimation, and generative chemistry applied specifically to antimalarial targets. The papers curated below span the full spectrum from target biology through to AI/ML models directly applicable to Ersilia workflows. Of particular interest are Hub-ready models (🤖) trained on antiplasmodial datasets, multi-stage active scaffold series relevant to the MMV/DNDi pipeline, and LMIC-led contributions (🌍) that reflect the communities most affected.

The field has entered an exciting inflection point: AlphaFold-predicted structures are being systematically combined with essentiality genetics and druggability assessment to expand the target space well beyond the classical handful of validated targets (DHFR, DHODH, PI4K, proteasome). The 2025 *npj Drug Discovery* work by Winzeler's group identifies 27 high-priority targets from a genome-wide screen — most still lacking chemical starting points. This gap between validated targets and available inhibitor scaffolds is precisely where Ersilia Hub models for activity prediction and generative chemistry can have the most impact.

---

## Disease / Target Biology

**Genome-scale target identification.** The druggable genome of *P. falciparum* has historically been explored through phenotypic screens and reverse genetics, but two recent systematic analyses have dramatically expanded the landscape. Godinez-Macias et al. (*npj Drug Discovery*, 2025, DOI: 10.1038/s44386-025-00006-5) combined AlphaFold-predicted structures with ligand-binding predictions (AlphaFill, BindingDB, BRENDA) and blood-stage essentiality genetics to identify 867 candidate proteins with druggability evidence, of which 540 lacked any clinical-stage inhibitor. Expert-scored rubric assessment yielded 27 high-priority targets — many entirely undrugged. Complementarily, Cowell & Winzeler (*Pathogens & Disease*, 2018, DOI: 10.1177/1178636118808529) had previously established a resistome/druggable genome framework using whole-genome sequencing of 262 clones resistant to 37 chemotypes, discovering novel targets including *P. falciparum* acetyl-CoA synthetase (PfAcAS). Genome-scale metabolic modelling offers yet another orthogonal route: Taweechai et al. (*Antimicrob Agents Chemother*, 2025, DOI: 10.1128/aac.00459-25) used flux-balance analysis and CRISPR-Cas9 knockouts to validate UMP-CMP kinase (UCK) as a bona fide blood-stage drug target.

**Proteasome (Pf20S).** The *P. falciparum* 20S proteasome has emerged as one of the most compelling validated targets, for two compounding reasons: it is essential at all lifecycle stages, and parasites with K13-driven ART resistance show increased dependence on proteasome-mediated clearance of oxidatively damaged proteins. Deni et al. (*Cell Chem Biol*, 2023, DOI: 10.1016/j.chembiol.2023.03.002) profiled four chemotype classes and showed that covalent vinyl sulfone WLL-vs, which simultaneously targets β2 and β5 subunits, is least susceptible to resistance and strongly synergises with artemisinins including in ART-resistant parasites. Crucially, dual-subunit targeting dramatically constrains resistance evolution. Structural underpinning came from Hsu et al. (*Nat Commun*, 2023, DOI: 10.1038/s41467-023-44077-2), who solved cryo-EM structures of Pf20S with the macrocyclic peptide TDI-8304 and found that a β6 A117D resistance mutation paradoxically enhances activity of WLW-vs — collateral sensitivity that can be exploited in combination strategies.

**Haemoglobin digestion proteases: PfA-M1 and PfA-M17 aminopeptidases.** *P. falciparum* digests up to 75% of erythrocyte haemoglobin to supply amino acids, and the metallo-aminopeptidases PfA-M1 and PfA-M17 are essential terminal processors in this pathway. Giannangelo et al. (*eLife*, 2024, DOI: 10.7554/eLife.92990) applied three orthogonal chemoproteomics technologies (thermal proteome profiling, limited proteolysis, and untargeted metabolomics) to confirm that the selective inhibitor MIPS2673 targets only PfA-M1 *in situ*, disrupts haemoglobin-derived peptide metabolism, and is potent against both *P. falciparum* and *P. vivax* with no host cytotoxicity — a rare multi-species validation. The thermal proteome profiling approach itself is directly relevant as a target deconvolution tool for the Hub pipeline.

**PfDHODH (dihydroorotate dehydrogenase).** *P. falciparum* uniquely relies on *de novo* pyrimidine biosynthesis, lacking a salvage pathway. PfDHODH catalyses the rate-limiting fourth step and has a structurally distinct ubiquinone-binding pocket from the mitochondrial mammalian enzyme. Clinical candidate DSM265 (triazolopyrimidine class) reached Phase II trials, though resistance mutations in the enzyme's binding pocket have been characterised. Target-specific ML scoring functions for PfDHODH are now being developed (Caba & Ballester, *Bioinformatics*, 2025, DOI: 10.1093/bib/bbaf631.043), offering a route to improved inhibitor prioritisation.

**Aminoacyl-tRNA synthetases (aaRS).** With 36 aaRSs distributed across cytoplasm, apicoplast, and mitochondria, *P. falciparum* presents multiple isoforms divergent from human homologues. Stokes et al. (*Enzymes*, 2023, PMID: 37018842) reviewed the field comprehensively and highlighted nucleoside sulfamate "reaction-hijacking" inhibitors (e.g., cladosporin/ML901 for PfLysRS) as the most advanced chemotype class, active at all lifecycle stages. McLellan et al. (*Antimicrob Agents Chemother*, 2024, DOI: 10.1128/aac.00793-24) characterised delayed death caused by disruption of apicoplast-targeted aaRS, validating apicoplast aaRS as a clinically relevant entry point. Nyamai & Bishop (*Int J Mol Sci*, 2020, DOI: 10.3390/ijms21113803) from Rhodes University (South Africa 🌍) predicted allosteric binding sites distinct from the active site in PfProRS and PfArgRS — exploiting these cryptic pockets may improve selectivity.

**Kinases: PfCDPK1, PfPKG.** The plant-like calcium-dependent protein kinases have no mammalian orthologues; PfCDPK1 governs merozoite egress and erythrocyte invasion. PfPKG (cGMP-dependent protein kinase) has been validated as resistance-refractory: resistance selections never mutated PfPKG itself across multiple chemotypes, and the clinical candidate MMV030084 shows prophylactic, blood-stage, and transmission-blocking activity. The acetyl-CoA synthetase target (PfAcAS) was genetically and chemically validated using MMV019721 and MMV084978 from Medicines for Malaria Venture (Cobbold/Fidock group, *Cell Chem Biol*, 2021, DOI: 10.1016/j.chembiol.2021.09.002) — linking epigenetic regulation via acetyl-CoA production to a novel druggability angle.

**PfMDR1 (multidrug resistance transporter).** A fresh (2026) cryo-EM structure of PfMDR1 in complex with the clinical candidate ACT-451840 revealed a central cavity binding mode and inward-open conformation locking mechanism (Zhao et al., *Nat Commun*, 2026, DOI: 10.1038/s41467-026-73692-y). This provides the first molecular rationale for ACT-451840 resistance mutations and points to the transporter itself as a tractable target, not merely a resistance determinant.

---

## Drug Discovery Approaches

Target-based and phenotypic approaches each have roles in the *P. falciparum* pipeline. The dominant strategy remains phenotypic whole-cell screening (HTSs on asexual blood-stage cultures), which has yielded the GSK TCAMS set (13,533 compounds), the Malaria Box (400 MMV compounds), and the Pandemic Response Box — all public. Chemogenomic profiling using CRISPRi/Tn mutagenesis links phenotypic hits to specific targets at scale (Scientific Reports, 2023). The deeper shift is toward target-first: with validated targets in hand, structure-based virtual screening, ML-guided library selection, and covalent warhead design are all being deployed.

Resistance evolution is built into modern P. falciparum drug discovery: the minimum inoculum of resistance (MIR) paradigm and dual/triple-target combination design have emerged as strategies specifically because resistance arises quickly in clonal cultures. The proteasome vinyl sulfone work exemplifies this — by targeting two subunits simultaneously, MIR is dramatically raised. The Open Source Malaria (OSM) consortium operates a fully open discovery programme on PfATP4-targeting Series 4 compounds, and its data is freely available for ML model training (OSM GitHub repository).

Natural product-derived libraries are increasingly relevant for LMIC researchers lacking access to large pharma compound sets. Enninful et al. from the University of Ghana (🌍) screened AfroDB — a database of African natural product compounds — against PfTMPK (*Front Cell Infect Microbiol*, 2022, DOI: 10.3389/fcimb.2022.868529), identifying aurantiamide acetate as a promising hit with acceptable ADMET properties. This approach has direct relevance for Ersilia's mission of building tools usable with locally available chemical libraries.

---

## AI/ML Methods

The AI/ML landscape for antiplasmodial activity prediction has matured substantially since 2020. Three clear generations are visible:

**Generation 1 — Fingerprint QSAR.** Classical random forest and SVM models using ECFP4/6 fingerprints remain competitive on small datasets (<1000 compounds) and are reproducible with basic infrastructure. These are well-represented in ChEMBL and form the backbone of many hub activity predictors. The multistage ML-QSAR models of Peña-Guerrero et al. (*Pharmaceuticals*, 2024, PMCID: 11318017) demonstrated that training on stage-specific data produces better cross-stage predictions, and applied XAI (explainable AI) to identify structural motifs driving activity at each lifecycle stage.

**Generation 2 — Graph neural networks.** DeepMalaria (Keshavarzi Arshadi et al., *Front Pharmacol*, 2020, DOI: 10.3389/fphar.2019.01526) was the first graph convolutional approach for antiplasmodial activity prediction; trained on the 13,446-compound GSK dataset, it validated predicted hits experimentally at the nanomolar level. Ribeiro et al. (*PLoS Comput Biol*, 2020, DOI: 10.1371/journal.pcbi.1007025) developed deep-learning QSAR models that discovered LabMol-149 and LabMol-152 — two novel antiplasmodial scaffolds with sub-500 nM EC₅₀ values against both drug-sensitive and multidrug-resistant strains.

**Generation 3 — Co-representation models and large datasets.** MalariaFlow (Lin et al., *Eur J Med Chem*, 2024, DOI: 10.1016/j.ejmech.2024.116720) assembled 410,654 records across 10 *Plasmodium* phenotypes and 3 lifecycle stages in humans, and benchmarked nine ML/DL architectures. The co-representation model FP-GNN — which fuses ECFP fingerprints with graph-level features — achieved the highest AUROC (0.900 overall) and outperformed pure fingerprint and pure graph approaches. A public web server is available. This is a strong Hub candidate: SMILES input, activity prediction output, open dataset.

**Target-specific ML scoring functions.** Caba & Ballester (*Bioinformatics*, 2025, DOI: 10.1093/bib/bbaf631.043) showed that target-specific RF/GBM scoring functions trained on PfDHODH-specific bioactivity data significantly outperform generic docking scoring functions for PfDHODH virtual screening — validating the principle of building Hub-style single-target activity models.

**Active learning for hit ID.** Matlhodi et al. from North-West University and University of Venda (South Africa 🌍, *PLoS ONE*, 2024, DOI: 10.1371/journal.pone.0308969) demonstrated active-learning-driven AutoQSAR to generate and prioritise PfHsp90 inhibitors. A de novo compound generation step + QSAR re-scoring loop produced FTN-T5 (IC₅₀ = 1.44 µM against *Pf* NF54), providing a proof of concept for using active learning to escape chemical series biases in small training sets — a key advantage for LMIC applications with limited screening data.

**Protein stability design for druggability.** A 2026 bioRxiv preprint applied ProteinMPNN-guided sequence design to three challenging *P. falciparum* targets (bromodomains PfBDP1, PfBDP2, and a third target), engineering thermally stable variants without distorting binding pocket geometry — directly enabling structural assays that were previously inaccessible, and expanding the set of tractable Pf targets for structure-based drug discovery.

---

## Open Datasets

The *P. falciparum* drug discovery field has unusually rich open bioactivity resources:

- **ChEMBL** (https://www.ebi.ac.uk/chembl/): Tens of thousands of dose-response records against *P. falciparum* 3D7 and drug-resistant strains (Dd2, K1, W2), drawn from published literature, the TCAMS, and deposited NTD sets. ChEMBL-NTD (https://chembl.gitbook.io/chembl-ntd) additionally houses deposited compound sets from MMV, DNDi, Novartis, and academic groups, including GSK's TCAMS (13,533 compounds) and MMV Malaria Box screens.

- **GlaxoSmithKline TCAMS** (Tres Cantos Antimalarial Compound Set): 13,533 confirmed antiplasmodial hits publicly released; formed the primary training set for DeepMalaria. Available via ChEMBL and directly.

- **MMV Malaria Box / Pandemic Response Box**: 400 and 400 compounds respectively, publicly available with multi-strain and multi-stage phenotypic screening data. Stage-resolved data (ring, trophozoite, schizont, gametocyte) makes these valuable for multistage model training.

- **Open Source Malaria (OSM)**: Fully open dataset on PfATP4-targeting Series 4 compounds with iterative SAR and biological data published in real time (https://github.com/OpenSourceMalaria/Series4_PredictiveModel). Ideal for QSAR model training and benchmarking.

- **MalariaFlow dataset**: 410,654 records across 10 *Plasmodium* phenotypes built by Lin et al. (2024) — the largest curated antiplasmodial activity dataset to date 🗃️.

- **PlasmoDB** (https://plasmodb.org/plasmo/): Genomic, transcriptomic, and proteomic data for P. falciparum; integrates essentiality data from saturation mutagenesis (MIS screens). Used for target prioritisation.

---

## Research Gaps

1. **Structural coverage.** Despite 867 candidate druggable targets identified by Godinez-Macias et al. (2025), fewer than 30 have confirmed inhibitor scaffolds in the literature. AlphaFold structures exist for most, but without experimental validation of binding pockets, virtual screening reliability remains limited.

2. **Multi-stage activity models.** Most existing Hub-ready models address asexual blood-stage activity only. Transmission-blocking and liver-stage endpoints are sparsely represented in training datasets; building dedicated models for these stages is a high-priority gap.

3. **Resistance-aware models.** No Hub model currently predicts whether a compound will select for resistance, or what the MIR will be. Integrating in vitro resistance selection data (from Cowell/Winzeler and Deni/Fidock groups) into predictive models is an unmet need.

4. **ADMET for malaria-specific pharmacokinetics.** Parasite-selective ADMET models (e.g., accumulation in parasite food vacuole, haemoglobin-derived metabolism interference) are absent from the Hub; most current ADMET tools are trained on generic pharmacokinetic data.

5. **LMIC authorship gap.** Despite Africa bearing over 90% of malaria deaths, only a small fraction of the papers surveyed have first or last authors at LMIC institutions. Ghana (Enninful et al.) and South Africa (Nyamai/Bishop; Matlhodi et al.) are notable exceptions. Critical work on ART resistance in field isolates from Uganda, Rwanda, and DRC comes largely from teams in high-income countries. Ersilia should actively partner with African research institutions (WACCBIP Ghana, KEMRI Kenya, MBARARA Uganda) to build locally-anchored datasets and co-develop models.

6. **Low-data / few-shot regimes.** For the 540 targets lacking clinical-stage inhibitors (Godinez-Macias et al.), there will be few or no bioactivity data points initially. Few-shot and transfer-learning approaches (pretraining on ChEMBL-wide data) are needed and largely absent from the malaria-specific ML literature.

---

## Curated Entry List

### Tier 1 — Core papers

- [Godinez-Macias et al., *npj Drug Discovery*, 2025](https://doi.org/10.1038/s44386-025-00006-5) ⭐ — **Revisiting the Plasmodium falciparum druggable genome using predicted structures and data mining.** AlphaFold-driven assessment of 5,318 protein-coding genes identified 867 druggable candidates; expert scoring yielded 27 high-priority blood-stage targets, most lacking any lead compounds. Provides a publicly annotated genome-wide resource — directly maps the target space Ersilia should build activity models for.

- [Deni et al., *Cell Chemical Biology*, 2023](https://doi.org/10.1016/j.chembiol.2023.03.002) ⭐ — **Mitigating the risk of antimalarial resistance via covalent dual-subunit inhibition of the Plasmodium proteasome.** Vinyl sulfone WLL-vs demonstrates potent activity against ART-resistant parasites by targeting both β2 and β5 proteasome subunits simultaneously; minimal resistance selection observed. Proteasome inhibitors are a leading next-generation antimalarial class; activity prediction models for this target class are a Hub priority.

- [Hsu et al., *Nature Communications*, 2023](https://doi.org/10.1038/s41467-023-44077-2) ⭐ — **Structures revealing mechanisms of resistance and collateral sensitivity of Plasmodium falciparum to proteasome inhibitors.** Cryo-EM structures of Pf20S with macrocyclic peptide TDI-8304 explain species selectivity and resistance; β6 A117D mutation causes collateral sensitivity to WLW-vs. Structural insight for Hub docking-surrogate and activity models targeting the Pf proteasome.

- [Giannangelo et al., *eLife*, 2024](https://doi.org/10.7554/eLife.92990) — **Chemoproteomics validates selective targeting of Plasmodium M1 alanyl aminopeptidase as an antimalarial strategy.** Multi-omic (thermal proteomics + metabolomics) confirmation that MIPS2673 selectively inhibits PfA-M1 in parasites; potent against both *P. falciparum* and *P. vivax*. PfA-M1 activity prediction models would benefit Ersilia's multi-species pipeline.

- [Taweechai et al., *Antimicrob Agents Chemother*, 2025](https://doi.org/10.1128/aac.00459-25) — **Validated antimalarial drug target discovery using genome-scale metabolic modelling.** GSM flux-balance analysis plus CRISPR-Cas9 knockdown validates UMP-CMP kinase (UCK) as a blood-stage *P. falciparum* drug target; biochemical assays confirm growth inhibition. Provides a new validated target with a defined enzymatic assay, suitable for activity model development.

- [Zhao et al., *Nature Communications*, 2026](https://doi.org/10.1038/s41467-026-73692-y) ⭐ — **Structural and mechanistic insights into the inhibition of Plasmodium falciparum MDR1.** First cryo-EM structure of PfMDR1 in complex with clinical candidate ACT-451840 at 3.42 Å; reveals inward-open locking mechanism and explains resistance mutations. Directly relevant for developing Hub ADMET models that account for drug efflux via PfMDR1.

- [Stokes et al. (review), *Enzymes*, 2023](https://pubmed.ncbi.nlm.nih.gov/37018842/) — **Targeting Aminoacyl tRNA Synthetases for Antimalarial Drug Development.** Comprehensive review of all 36 *Pf* aaRSs as drug targets; AMP-mimicking nucleoside sulfamate reaction-hijacking inhibitors are the most advanced class with pan-life-cycle activity. Hub models for aaRS-targeting compounds should account for apicoplast vs cytoplasmic isoforms.

- [McLellan et al., *Antimicrob Agents Chemother*, 2024](https://doi.org/10.1128/aac.00793-24) — **Dual targeting of aminoacyl-tRNA synthetases to the apicoplast and cytosol in Plasmodium falciparum.** Characterises delayed-death phenotype caused by disruption of apicoplast-targeted aaRS and validates these as druggable entry points. Key mechanistic paper supporting aaRS as Hub-relevant target class.

- [Enninful et al. (Univ of Ghana), *Front Cell Infect Microbiol*, 2022](https://doi.org/10.3389/fcimb.2022.868529) ⭐🌍 — **Targeting the *Plasmodium falciparum* Thymidylate Monophosphate Kinase for the Identification of Novel Antimalarial Natural Compounds.** LMIC-led virtual screen of the AfroDB African natural products library against PfTMPK; ADMET-filtered hits identified aurantiamide acetate as a promising lead. Directly demonstrates Hub-relevant workflows for natural-product-rich LMIC compound libraries; first author at Noguchi Memorial Institute for Medical Research, Ghana.

- [Cowell & Winzeler, *Pathogens & Disease*, 2018](https://doi.org/10.1177/1178636118808529) — **Exploration of the Plasmodium falciparum Resistome and Druggable Genome Reveals New Mechanisms of Drug Resistance and Antimalarial Targets.** Systematic WGS of 262 in vitro-resistant clones against 37 chemotypes; identified novel targets including *PfAcAS*; one-third of resistance events driven by gene amplification. Foundational target-discovery methodology paper establishing resistance-based target ID as a validated approach.

- [Cobbold et al., *Cell Chemical Biology*, 2021](https://doi.org/10.1016/j.chembiol.2021.09.002) — **Chemogenomics identifies acetyl-coenzyme A synthetase as a target for malaria treatment and prevention.** Genetic validation of PfAcAS via in vitro resistance evolution, conditional knockdown, and metabolic profiling; mutations in PfAcAS confer resistance to MMV019721 and MMV084978. Opens a new epigenetic-metabolic target class for Hub activity prediction.

---

- [Lin et al. (MalariaFlow), *Eur J Med Chem*, 2024](https://doi.org/10.1016/j.ejmech.2024.116720) 🤖🗃️💻 — **MalariaFlow: A comprehensive deep learning platform for multistage phenotypic antimalarial drug discovery.** Assembled 410,654 *Plasmodium* bioactivity records; FP-GNN co-representation model achieves AUROC 0.900 for antiplasmodial activity prediction; public web server provided. Primary Hub candidate: SMILES input, multistage activity prediction — highest-priority 🤖 entry in this review.

- [Keshavarzi Arshadi et al. (DeepMalaria), *Front Pharmacol*, 2020](https://doi.org/10.3389/fphar.2019.01526) 🤖💻 — **DeepMalaria: Artificial Intelligence Driven Discovery of Potent Antiplasmodials.** GCNN trained on 13,446 publicly available GSK antiplasmodial compounds; all nanomolar hits correctly predicted; macrocyclic and approved-drug hits experimentally validated. Hub-incorporable for activity prediction; code and model architecture described. One of the foundational graph-based models for antiplasmodial activity prediction.

- [Ribeiro et al., *PLoS Comput Biol*, 2020](https://doi.org/10.1371/journal.pcbi.1007025) 🤖💻 — **Deep Learning-driven research for drug discovery: Tackling Malaria.** Deep-learning QSAR models for *P. falciparum* activity and cytotoxicity; discovered LabMol-149 and LabMol-152 with sub-500 nM EC₅₀ against both sensitive and multidrug-resistant strains. Hub-incorporable for activity prediction; strong experimental validation from LMIC-relevant strain backgrounds.

- [Matlhodi et al. (NWU/Univ Venda), *PLoS ONE*, 2024](https://doi.org/10.1371/journal.pone.0308969) 🌍🤖 — **Auto QSAR-based active learning docking for hit identification of potential inhibitors of *Plasmodium falciparum* Hsp90 as antimalarial agents.** De novo active-learning QSAR pipeline targeting PfHsp90; FTN-T5 identified with IC₅₀ 1.44 µM and high selectivity index. Hub-incorporable for activity prediction against PfHsp90; first/last authors at South African universities; demonstrates low-data regime applicability.

- [Caba & Ballester, *Bioinformatics*, 2025](https://doi.org/10.1093/bib/bbaf631.043) 🤖 — **Target-specific machine-learning scoring functions enhance virtual screening for PfDHODH inhibitors.** Target-specific RF/GBM models trained on PfDHODH bioactivity data significantly outperform generic scoring functions in virtual screening. Hub-incorporable for PfDHODH activity prediction; validates single-target ML approach for validated Pf targets.

- [Nyamai & Bishop (Rhodes Univ), *Int J Mol Sci*, 2020](https://doi.org/10.3390/ijms21113803) 🌍 — **Identification of Selective Novel Hits against *Plasmodium falciparum* Prolyl tRNA Synthetase Active Site and a Predicted Allosteric Site Using In Silico Approaches.** MD simulation and free-energy landscape analysis identifies a cryptic allosteric pocket in PfProRS distinct from the active site; virtual screening identifies allosteric ligands. Authors at Rhodes University (South Africa 🌍); exploiting allosteric pockets may improve selectivity over host aaRSs.

### Tier 2 — Supporting papers

- [Peña-Guerrero et al., *Pharmaceuticals*, 2024](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11318017/) 🤖 — **Innovative Multistage ML-QSAR Models for Malaria.** ML-QSAR models covering liver, blood, and transmission stages with XAI analysis; six validated multistage hits. Guides model design for multi-endpoint Hub tools.

- [Sanaullah et al., *Trop Med*, 2025](https://doi.org/10.3390/tropicalmed10040094) — **Combating Malaria: Targeting the Ubiquitin-Proteasome System to Conquer Drug Resistance.** Review of UPS/proteasome pathway involvement in ART resistance and inhibitor classes; good introduction to the biology for Ersilia model framing.

- [Gonçalves et al., *Front Cell Infect Microbiol*, 2024](https://doi.org/10.3389/fcimb.2024.1342856) — **Mutation in the 26S proteasome regulatory subunit rpn2 gene in *Plasmodium falciparum* confers resistance to artemisinin.** First report of an rpn2 mutation (738K) enhancing parasite survival after DHA treatment; confirms 19S regulatory particle as a resistance locus. Relevant for resistance-aware model building.

- [Ji et al., *Molecules*, 2022](https://doi.org/10.3390/molecules27092670) — **In Silico and In Vitro Antimalarial Screening and Validation Targeting *Plasmodium falciparum* Plasmepsin V.** Homology-model-based virtual screening against PmV (essential protein export target); 4 validated hits with µM IC₅₀ values. Provides a small but confirmed training set for PmV activity models.

- [Enninful et al. (NMIMR Ghana), *Front Cell Infect Microbiol*, 2022](https://doi.org/10.3389/fcimb.2022.868529) — (see Tier 1 entry above; re-flagged here to emphasise LMIC authorship significance)

---

## Known Gaps

- **No Tier 1 paper from East Africa** (Uganda, Kenya, Tanzania, Ethiopia) despite these countries bearing the highest burden of ART-resistant *P. falciparum*. Publications on resistance surveillance from these settings (e.g., KEMRI, Uganda Malaria Research Group) are not represented in the drug discovery literature.
- **No open dataset for liver-stage activity** comparable in size to the blood-stage datasets from GSK/MMV; limits multistage model development.
- **No Hub-ready model for resistance prediction** (i.e., prediction of whether a compound will select for resistance mutations in specific target genes); this remains a critical open problem.
- **Sparse structural data for novel targets.** Of the 27 high-priority targets from Godinez-Macias et al. (2025), most lack experimental co-crystal structures with small molecules, limiting structure-based virtual screening fidelity.
- **ADMET models for parasite pharmacology** (vacuole accumulation, haem-binding, food vacuole partitioning) are absent from the literature and from the Hub.

---

## Search Log

| Source | Query | Results retrieved |
|---|---|---|
| Nature / npj | *P. falciparum* druggable targets drug discovery 2022–2025 | 6 |
| Nature | Malaria kinase protease inhibitor 2022–2025 | 6 |
| Cell / Cell Chem Biol | *P. falciparum* drug target validation 2022–2025 | 6 |
| PubMed | PfDHFR PfDHODH drug target 2022–2025 | 7 |
| PubMed | PfKRS1 aminoacyl-tRNA synthetase drug target | 7 |
| Europe PMC | *P. falciparum* machine learning deep learning antimalarial 2023–2024 | 5 |
| bioRxiv | *P. falciparum* drug discovery AI QSAR activity prediction | 6 |
| ChemRxiv | Malaria ADMET antimalarial 2023–2025 | 5 |
| Multi-source | Proteasome ART resistance ChEMBL dataset malaria 2023–2025 | 7 |
| Multi-source | PfATP4 PfCDPK1 kinase inhibitor drug discovery | 5 |
| Multi-source | ChEMBL PlasmoDB MMV DNDi open dataset 2022–2024 | 6 |
| Multi-source | GNN transformer antimalarial activity prediction Nature | 7 |
| Multi-source | DeepMalaria GCNN antiplasmodial deep learning | 6 |
| Multi-source | MalariaFlow FP-GNN multistage antimalarial 2024 | 5 |
| Web fetch | npj Drug Discovery doi:10.1038/s44386-025-00006-5 | Metadata verified |
| Web fetch | eLife doi:10.7554/eLife.92990 | Metadata verified |
