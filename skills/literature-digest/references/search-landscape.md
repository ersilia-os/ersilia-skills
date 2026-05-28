# Literature-digest — Search Landscape

Vocabulary, authors, venues, and task taxonomy used by this skill to construct literature-search
queries and to score candidate items. Blends three views of "what matters to Ersilia":

1. **Publication-record view** — what Miquel has co-authored and what the Ersilia Model Hub covers.
2. **Correspondence view** — what surfaces via Gmail Scholar alerts and ongoing collaborator
   threads (synthesised 2026-05-20).
3. **Grant view** — what the active grant portfolio commits Ersilia to keep up with (NIH R21
   antimalarial pyrazole, BBVA Prisms `glueAI`, Grand Challenges Gram-negative AMR / `E-AMR-CC`,
   CARB-X 2,4-diaminoquinazoline EOI, AI2050 compute fund, O'Shaughnessy Fellowship — sampled
   2026-05-20).

Where these views agree, weight is high. Where they disagree, the file flags the divergence so
ranking can prefer the source that best matches the question being asked.

---

## Topics of interest

Ranked by centrality. The score formula in `scripts/dedup_and_rank.py` uses topic-keyword hits as
one component; the higher the rank here, the heavier the weight should be.

> For the empirically-derived distribution of subtasks, journals and source types across
> the existing 189 Ready Hub models, see `hub-incorporation-criteria.md`. That file is the
> reference for assigning 🤖 and for placing items in the "Potential models" chapter.

### Recurring themes in the #literature channel (Slack history, 2026-Feb to 2026-May)

Themes the team explicitly engages with, derived from inspection of ~100 Slack
messages. These should weigh slightly higher than topic-keyword hits alone — they
reflect what is actually being read and discussed inside the org.

- **Agentic AI for science** — Sakana "AI Scientist", Jeff Clune's lineage,
  Google DeepMind Co-Scientist, FutureHouse multi-agent systems. Anything that
  positions an LLM agent against scientific discovery.
- **OpenADMET ecosystem** — the OpenADMET model collection, blind-challenge
  benchmarks, ADMET ensembles. Surface anything from `OpenADMET` GitHub.
- **Boltz-2 / cofolding** — Boltz performance evaluation, cofolding generalisation,
  alternatives to AlphaFold-Multimer.
- **Open generative chemistry tools** — CreM, ChemLint (Grisoni / van Tilborg),
  ETFlow, Synthonor, scaffold-aware transformers. The team triages new generative
  releases routinely.
- **Drug discovery in Africa** — the ACS *Drug Discovery Africa* collection
  (Dziwornu, Cheuka, Mayoka), H3D Foundation news, GC-ADDA outputs.
- **Open sharing of compounds and assays** — Matthew Todd's "Idler Compounds",
  Open Source Malaria, cross-screening protocols.
- **ChEMBL FAIRification and AI-driven annotation** — anything from the ChEMBL
  blog, especially AI-driven curation.
- **EBI BioAiRepo and open model registries** — peer registries to the Ersilia
  Model Hub; the team tracks how others structure model metadata.
- **AMR R&D funding / policy** — *Lancet Microbe* articles on investment trends,
  global health funding declines.
- **Chemical foundation models / representation learning** — MIST, ChemBERTa
  successors, GROVER, language-model embeddings for molecules.

These themes are not (yet) in the keyword-matrix scoring; treat them as editorial
priors when deciding what to surface.

### Tier A — pillars (always relevant)

1. **Bioactivity descriptors & chemical signatures** — Chemical Checker, learned compound
   descriptors connecting chemistry and biology. *(All three views.)*
2. **Open-source AI/ML for neglected & infectious diseases** — Ersilia Model Hub, antimalarial /
   antitubercular / antiviral virtual screening, AI for drug discovery in LMICs and Africa.
3. **Antimalarial drug discovery** — *Plasmodium falciparum*, MEP/DOXP / apicoplast biology,
   artemisinin resistance (kelch13, ring-stage tolerance, slow clearance kinetics), transmission
   blocking, liver-stage and hypnozoite biology.
4. **Antitubercular drug discovery** — *Mycobacterium tuberculosis*, MmpL3, PI4K, BacPROTACs,
   pharmacometrics-tailored TB treatment.
5. **Gram-negative AMR** — *Klebsiella pneumoniae* (esp. blaNDM-1, ST147), *Acinetobacter
   baumannii*, *E. coli*, ESKAPE pathogens; permeability and efflux; cell-wall penetration;
   accumulation.
6. **Generative and predictive AI for drug discovery** — de novo molecular generation
   (Reinvent, CREM, Stoned, ShEPhERD, Fasmifra, diffusion, GFlowNets), property and activity
   prediction (ADMET, bioactivity, MoA, uncertainty), foundation models for chemistry
   (SMILES, graph, 3D, multimodal).
7. **Knowledge graphs & embeddings for drug discovery** — Bioteque-style pre-calculated
   embeddings, biomedical KG fusion, similarity across chemical-biological spaces.

### Tier B — strong adjacents (frequently relevant)

8. **Targeted protein degradation & chemoproteomics** — molecular glue degraders, PROTACs,
   BacPROTACs, E3 ligase recruitment, ternary-complex modelling, large-scale chemoproteomics
   ligand discovery.
9. **Antivirals (broad-spectrum and pandemic preparedness)** — SARS-CoV-2 follow-on work,
   umifenovir analogues, host-directed antivirals (SPHK1, GS).
10. **Other parasitic/neglected diseases** — schistosomiasis, kinetoplastids (leishmaniasis,
    Chagas, HAT), Entamoeba, Toxoplasma, soil-transmitted helminths; mycetoma, Buruli ulcer,
    leprosy, dengue, chikungunya, rabies, snakebite envenoming.
11. **Protein structure prediction & design** — AlphaFold ecosystem, Boltz-1/Boltz-2, Chai-1,
    RoseTTAFold-AllAtom, ESMFold; de novo binders and enzymes.
12. **Ultra-large virtual screening** — Enamine REAL, ZINC22, deep docking, AI-accelerated
    docking surrogates, billion-scale campaigns.
13. **Drug repurposing & side-effect mining** — recycling side-effects into clinical markers,
    chemo-centric views of disease, COVID-19 drug repertoire expansion.
14. **Pharmacometrics / PBPK / human-dose prediction** — MMV Sola, allometric scaling, AI
    coupled to pharmacometric modelling.
15. **Systems pharmacology & polypharmacology** — binding-pocket similarity (PocketVec),
    structural systems pharmacology, target-network analyses.

### Tier C — opportunistic / discipline-specific

16. **LLMs for chemistry and biomedical data curation** — text mining of assay annotations,
    chemistry copilots, MCP servers (e.g. ChemLint).
17. **Cancer pharmacogenomics & drug response** — drug sensitivity across cell lines,
    pancancer drug MoA inference, personalised cancer therapy prioritisation. Pediatric cancer
    fusion targets (ZFTA-RELA, SS18-SSX) via `glueAI`.
18. **Foundation models for tabular bioactivity** — TabPFN and successors.
19. **Open science, capacity building, equitable AI for health** — decolonisation of research,
    Digital Public Goods, training programs in Africa / LMICs, GC-ADDA, H3D Foundation, EDCTP3.
20. **Protein interactome & alternative conformations** — human binary interactome, alternative
    splicing of interactions, residue-coevolution-guided conformation discovery.
21. **Global-health epidemiology (Zambia, CHAMPS)** — cervical cancer screening, ART
    initiation, causes of childhood mortality. (Personal-record relevance; rarely a digest
    item but flag when LMIC-led.)

### Hub-coverage gaps the user does not personally publish on but the skill should still surface

Generic ADMET / physicochemical models, broad generative-chemistry methods (VAE / diffusion on
molecules), molecular fingerprints and pretrained encoders at large, ADMET-AI / OpenADMET-style
ensembles, hERG and CYP450 prediction families.

---

## Search keywords

Compose a query by combining one term from **methods** with one from **endpoints** or
**diseases/pathogens**. Alone, the disease group is too broad.

### Methods (how the model works)

Descriptor · Embedding · Fingerprint · Chemical graph model · Chemical language model · Compound
generation · de novo design · Diffusion · GFlowNet · Reinforcement learning · Scaffold hopping ·
Foundation model · TabPFN · Similarity · Bioactivity profile · Natural product · Synthetic
accessibility · Drug-likeness · Quantum properties · Target identification · Therapeutic
indication · Co-folding · Deep docking · Active learning · Bayesian optimization · Multi-task
learning · Transfer learning · Knowledge graph · Graph neural network.

### Endpoints (what the model predicts)

ADME · ADMET · Toxicity · Cardiotoxicity · hERG · CYP450 · Metabolism · Permeability ·
Solubility · LogP · LogS · pKa · Lipophilicity · Half-life · Microsomal stability · Plasma-protein
binding · Tox21 · IC50 · BACE · Cytotoxicity · MIC · MoA · Frequency of resistance · PRR · MIR.

### Diseases / pathogens (where the model applies)

Antimicrobial activity · Antimicrobial resistance · Antiviral activity · Antiparasitic activity ·
Antifungal activity · ESKAPE pathogens · Gram-negative bacteria · Malaria / *Plasmodium
falciparum* · Tuberculosis / *Mycobacterium tuberculosis* · COVID-19 / SARS-CoV-2 · *Escherichia
coli* · *Staphylococcus aureus* · *Acinetobacter baumannii* · *Klebsiella pneumoniae* ·
*Pseudomonas aeruginosa* · *Candida albicans* · *Neisseria gonorrhoeae* · *Cryptococcus
neoformans* · Schistosomiasis · Leishmaniasis · Chagas disease · Human African trypanosomiasis ·
*Toxoplasma gondii* · *Entamoeba histolytica* · Diarrheal diseases · Cancer · AIDS / HIV ·
Alzheimer · Mycetoma · Buruli ulcer · Leprosy · Dengue · Chikungunya · Rabies · Snakebite
envenoming.

### Modality / mechanism (load-bearing in 2026)

Molecular glue · PROTAC · BacPROTAC · Targeted protein degradation · E3 ligase · Ubiquitin
proteasome · Apicoplast · MEP / DOXP pathway · Kelch13 · Ring-stage · Hemozoin · Phosphatidyl-
inositol kinase · Chymotrypsin-like protease.

### Dataset / benchmark anchors (useful standalone terms)

ChEMBL · MoleculeNet · DrugBank · Co-ADD · Spark · MMV (box / Pathogen / Pandemic Response) ·
Enamine REAL · ZINC22 · Therapeutics Data Commons · Polaris · PDBbind.

### Open-science anchors

Digital Public Goods · Open-source AI · Decolonisation · GC-ADDA · H3D Foundation · EDCTP3 ·
Schmidt Sciences · AI2050 · MMV · GHIT · GARDP · DNDi · CARB-X.

---

## Authors to follow

Boost in the ranking score: any item with a first OR senior author on this list gets +3.

### Core IRB / Ersilia network (closest collaborators)

- **Patrick Aloy** — IRB Barcelona. Chemical Checker, Bioteque, pocket descriptors. Long-running
  co-author across foundational papers.
- **Martino Bertoni** — IRB Barcelona. Chemical Checker / bioactivity descriptors.
- **Adrià Fernández-Torras** — AstraZeneca (formerly IRB Barcelona). Bioteque, descriptor reviews.
- **Adrià Comajuncosa-Creus** — IRB Barcelona. Chemical Checker continuation, PocketVec.
- **Pau Badia-i-Mompel** — Stanford. Bioactivity / signalling-network methods.
- **Lidia Mateo** — IRB Barcelona. Cancer pharmacogenomics.
- **Modesto Orozco** — IRB Barcelona / UB. Biomolecular simulation, structural biology.
- **Gemma Turon** — Ersilia. Current Ersilia-side first author.

### Active grant co-PIs and partner institutions

Boost +5 (above the standard +3) on the grant-track work — these are deliverables, not interest.

- **Kelly Chibale** — UCT / H3D. AI2050 co-PI; African DDI lead.
- **John G. Woodland** — UCT / H3D. Drug-discovery ecosystem perspectives.
- **Vinayak Singh** — UCT / H3D. TB drug discovery; ADDA4TB BacPROTAC work.
- **Godwin (Godfrey) Dziwornu** — UCT / H3D. Antimalarial medchem (PI4K, MmpL3 series).
- **Mwila Mulubwa** — UCT / H3D. Pharmacometrics, dose-prediction.
- **Jason Hlozek** — UCT / H3D. Gates TB AI program lead; Gr-ADI working group.
- **Sandeep Ghorpade · Dirk Lamprecht · Rosemary Swanson** — UCT / H3D. Gates TB AI.
- **Susan Winks · Godfrey Mayoka** — H3D Foundation. EDCTP3 exchange.
- **Fabrice Boyom** — Univ. of Yaoundé 1 (ARHIH). NIH R21 antimalarial pyrazole PI.
- **Collen Masimirembwa** — AiBST (Harare). DMPK collaborator on NIH R21.
- **Rajshekhar Karpoormath** — UKZN. CARB-X 2,4-diaminoquinazoline EOI PI.
- **Cristina Mayor-Ruiz** — IRB Barcelona. BBVA Prisms `glueAI` co-PI; molecular glues.
- **Fidele Ntie-Kang** — Univ. of Buea. Natural products; GC-ADDA convening co-author.
- **José L. Medina-Franco** — UNAM. Chemoinformatics; GC-ADDA contributor.
- **Peter Mubanga Cheuka** — Univ. of Zambia. Antimicrobial medchem.

### External topical anchors (boost +3)

- **Francesca Grisoni** — TU Eindhoven. Generative & interpretable ML for molecules.
- **Jure Leskovec** — Stanford. Graph ML, relational foundation models.
- **John Jumper** — Google DeepMind. AlphaFold ecosystem.
- **David Baker** — Univ. of Washington. De novo protein design (RFdiffusion, RoseTTAFold).
- **Regina Barzilay** — MIT. Boltz / Boltz-2 co-folding; ML for antibiotics.
- **Connor Coley** — MIT. Retrosynthesis, generative design, lab automation.
- **Marwin Segler** — Microsoft Research. Generative chemistry, retrosynthesis.
- **Andreas Bender** — Univ. of Cambridge. Cheminformatics, ADMET, polypharmacology.
- **Pat Walters** — Relay Therapeutics. Practical cheminformatics commentary.
- **Cesar de la Fuente** — UPenn. AI-driven antimicrobial peptides & small molecules.
- **Eugene Muratov** — UNC. QSAR, antimicrobial & antimalarial modeling.
- **Bharath Ramsundar** — Deep Forest Sciences / DeepChem. Open-source ML chemistry.
- **Dong-Sheng Cao** — Central South Univ. Cheminformatics, ADMET prediction.
- **Sean Ekins** — Collaborations Pharmaceuticals. AI for NTDs, Bayesian QSAR.
- **Grace Mugumbate** — Africa University. TB target ID, African DDI capacity.
- **Elizabeth Winzeler** — UCSD. *Plasmodium* druggable genome (cited foundation).
- **Francesco Gentile** — Univ. of Victoria. Deep docking protocols.
- **Frank Hutter** — Univ. of Freiburg / ELLIS. TabPFN.
- **Brian Shoichet** — UCSF. Ultra-large docking, ZINC22.
- **John Chodera** — MSKCC. OpenADMET, open-source physical chemistry.
- **Eytan Ruppin** — Cedars-Sinai / NCI. Systems pharmacology, polypharmacology.
- **Georg Winter & Marko Cigler** — CeMM, Vienna. Targeted protein degradation.
- **Fabian Offensperger** — CeMM. Chemoproteomics.
- **Michael Todd** — Open Source Malaria.
- **Quique Bassat** — ISGlobal. CHAMPS, child mortality, global health.
- **Gemma Moncunill** — ISGlobal. Malaria immunology biomarkers.
- **Jürgen Bajorath** — University of Bonn. Chemoinformatics / AI colloquium.
- **Ian Tietjen** — Wistar Institute. Natural-product antivirals; HIV.

Set Scholar alerts for the first two groups; use the third group to catch topic-specific work.

---

## Journals to prioritise

### Starred journals (⭐) — very-high-impact venues

A narrow set: when an item is published in one of these, mark the entry with ⭐ in the
digest. This is *editorial flair*, not a ranking bonus — the ranking still uses the
Tier 1/2/3 bonuses below. The criterion is "this is the kind of paper the team would
want to read regardless of topic".

- *Nature*
- *Science*
- *Cell*
- *Nature Biotechnology*
- *Nature Methods*
- *Nature Machine Intelligence*
- *Nature Chemical Biology*
- *Nature Chemistry*
- *Nature Medicine*
- *Nature Reviews Drug Discovery*
- *Science Advances*
- *Science Translational Medicine*
- *PNAS* — use sparingly; not every PNAS paper warrants ⭐.

Preprint servers never warrant ⭐ on their own, even when the work would clearly land
in one of the above after peer review — wait for the published version. The exception
is a preprint where a starred journal acceptance has been publicly announced; in that
case mark ⭐ and note the venue in the entry.

### Tier 1 — set alerts (+3 in ranking)

Venues that dominate either Miquel's record, the Hub's catalogue, or the active grant portfolio.

**The Hub catalogue (189 Ready models) is dominated by six venues** — these are
the highest-prior places to find incorporable papers:

1. *Journal of Cheminformatics* — 29 Hub models. The single most-incorporated
   venue. Always scan.
2. *arXiv* — 25 Hub models. Preprints are first-class.
3. *Journal of Chemical Information and Modeling (JCIM)* — 13 Hub models.
4. *Nature Machine Intelligence* — 11 Hub models.
5. *Nature Communications* — 9 Hub models.
6. *Nucleic Acids Research* — 6 Hub models. Especially the web-server issue.

The rest of Tier 1, in no particular order:

- *Nature Biotechnology* — Chemical Checker landmark; rare but high-signal.
- *Nature* — including *Nature Africa*.
- *Nature Chemical Biology* · *Nature Chemistry* · *Nature Reviews Drug Discovery*.
- *Nature Protocols* — deep docking (Gentile 2022).
- *Science* — when collaborators publish there (CeMM chemoproteomics, Boltz, etc.).
- *Cell Chemical Biology* — TPD / MGD mechanism papers.
- *Communications Medicine* — Africa data-science DDI (Turon et al. 2025).
- *Journal of Cheminformatics* — most over-represented hub venue; also a user venue.
- *Journal of Chemical Information and Modeling (JCIM)* — both.
- *Journal of Medicinal Chemistry (JMC)* · *ACS Medicinal Chemistry Letters*.
- *ACS Infectious Diseases* · *ACS Omega* — frequent venues for the H3D portfolio.
- *PLOS Computational Biology* · *PLOS Neglected Tropical Diseases*.
- *Artificial Intelligence in the Life Sciences* — Ersilia adoption paper (Turon &
  Duran-Frigola 2025).
- *npj Drug Discovery* — *Plasmodium* druggable genome and similar work.

### Tier 2 — scan tables of contents (+2 in ranking)

- *Cell* · *Cell Reports Medicine* · *Cell Systems* · *Cell Host & Microbe*.
- *PNAS* · *eLife*.
- *Science Advances* · *Science Translational Medicine*.
- *Nature Methods* · *Nature Computational Science* · *Communications Chemistry*.
- *Current Opinion in Chemical Biology* · *Current Opinion in Systems Biology*.
- *Nucleic Acids Research* — database / resource papers.
- *Bioinformatics* · *Briefings in Bioinformatics*.
- *Molecular Informatics* · *RSC Medicinal Chemistry* · *ChemMedChem*.
- *JACS* — for the TPD thread.
- *Chemical Science* and other RSC titles (incl. *Digital Discovery*).
- *Drug Discovery Today* · *Frontiers in Drug Discovery* · *Frontiers in Chemistry*.
- *Structure* — for structural-pharmacology threads.
- *Antimicrobial Agents and Chemotherapy (AAC)* · *mBio* · *Malaria Journal*.
- *Drug Metabolism and Disposition* · *Bioorganic & Medicinal Chemistry* · *SLAS Discovery* ·
  *Computational and Structural Biotechnology Journal*.
- *International Journal for Parasitology — Drugs and Drug Resistance*.
- *PLOS Pathogens*.
- *The Lancet Microbe*.
- **Preprint servers**: arXiv (`q-bio.BM`, `q-bio.QM`, `cs.LG`, `cs.AI`), ChemRxiv, bioRxiv,
  medRxiv. Preprints are mandatory in this field; do not deprioritise.

### Tier 3 — opportunistic / global-health adjuncts (+1 in ranking)

- *The Lancet Global Health* — HIV co-morbidity work (CIDRZ collaboration).
- *JAMA Network Open* · *JCI Insight*.
- *Journal of the International AIDS Society* · *Scientific Reports*.
- *npj Antimicrobials and Resistance* · *npj Digital Medicine*.
- *NEJM* — only when content is squarely on Ersilia-relevant clinical work; otherwise low
  signal-to-noise. Default-low.

---

## LMIC tagging

LMIC affiliation (🌍 marker) is decided strictly via the World Bank low- and lower-middle-income
country list — see `lmic-countries.md`. The rule:

- 🌍 if **first author** OR **senior (last) author** is at an institution in a WB low- or
  lower-middle-income country.
- Use the *first listed affiliation* per author for v1. Multi-affiliation senior authors get
  parsed more carefully in v2.
- Score bonus: +2 to the item's rank.
- The marker is editorial, not just a flag — only apply it when the LMIC author is meaningfully
  load-bearing (first or senior), not when they appear mid-list on a 30-author paper.

The current WB list excludes upper-middle-income countries (notably South Africa, Brazil, China,
Mexico). Ersilia engages heavily with H3D (Cape Town) and Brazilian / Mexican collaborators —
they will *not* receive the 🌍 marker but their work still scores via the author list. This is by
design: the marker reflects World Bank classification, not Ersilia's relationship.

---

## Task / Subtask taxonomy

Canonical vocabulary from `skills/ersilia-metadata/SKILL.md`, validated against the
189 Ready models in the Hub (see `hub-incorporation-criteria.md` for the empirical
distribution). The "Hub share" column shows what fraction of the Hub each subtask
accounts for — use it as a prior when triaging.

| Task | Subtask | Hub share | What a search should look for |
|---|---|---:|---|
| Annotation | **Activity prediction** | 41 % | Bioassay datasets, QSAR, IC50/MIC/Ki prediction, multi-task activity profiling against Hub-priority pathogens (*Plasmodium*, *Mycobacterium*, *Klebsiella*, etc.) and ESKAPE. |
| Representation | **Featurization** | 25 % | Pretrained chemical encoders (graph, transformer, language-model), molecular fingerprints, descriptor vectors, chemical foundation models. |
| Annotation | **Property calculation or prediction** | 20 % | ADMET endpoints, solubility, permeability, metabolic stability, toxicity panels (Tox21, hERG, DILI), CYP-mediated metabolism. |
| Sampling | **Similarity search** | 6 % | Ligand-based virtual screening, k-NN over fingerprints/embeddings, retrieval methods, docking surrogates. |
| Sampling | **Generation** | 5 % | De novo molecular design, SMILES VAE/transformer/diffusion, scaffold hopping, RL generators, scaffold-aware transformers. |
| Representation | **Projection** | 3 % | 2D/3D embeddings of chemical space, UMAP/t-SNE-based methods, manifold learning over compounds. |

Activity prediction + featurization + property prediction together account for
**86 %** of all Ready Hub models. Weight papers in those three subtasks heavier
than the other three when triaging.

When chapter 5 of the digest groups items by subtask, use these exact subtask
names as `###` subheadings, in the order above.

---

## Ranking summary (for `scripts/dedup_and_rank.py`)

| Signal | Weight |
|---|---|
| Author match (Tier B: external anchors) | +3 |
| Author match (Tier A: IRB / Ersilia network) | +4 |
| Author match (active grant co-PI) | +5 |
| Journal Tier 1 | +3 |
| Journal Tier 2 | +2 |
| Journal Tier 3 | +1 |
| Topic-keyword hit (per match, cap at +4) | +1 each |
| LMIC affiliation (WB low/lower-middle) on first or senior author | +2 |
| Recency (linear from old to new across window) | +1 max |
| Already in a prior digest | −999 (exclude) |

Take the top ~50 by score into the LLM-triage step.
