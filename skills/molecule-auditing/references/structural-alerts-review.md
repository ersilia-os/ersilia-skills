# Structural Alerts for Reactive / Undesirable Functional Groups — Tools & Literature Review

A focused review of curated SMARTS-based alert catalogs for flagging reactive, unstable, and otherwise undesirable functional groups in small molecules, plus a concrete plan to extend the `molecule-auditing` skill. Scope is deliberately limited to **rule-based substructure catalogs** (no ML predictors), and to the **reactive/undesirable-group** family of alerts (Brenk / Dundee / Lilly territory) rather than pure assay-interference (PAINS) or formal toxicity prediction.

---

## 1. Bottom line up front

Your collaborators' list — *hydrazine, 8-hydroxyquinoline, catechol, polyhalogenated, esters, phenols* — is **not a single named catalog**. It is a mix of three different things, and treating it as one list would be a mistake:

1. **Genuine reactive-group alerts** already covered by standard catalogs: `hydrazine`, `catechol`, `polyhalogenated`. These fire in RDKit's stock Brenk/NIH filters and in the ChEMBL Dundee/BMS sets (verified below).
2. **A metal-chelator alert that no stock catalog contains**: `8-hydroxyquinoline`. It needs a custom SMARTS. It's flagged not because it's reactive but because it chelates Fe/Zn/Cu and produces promiscuous, mechanism-confounded activity — a recurring artefact in anti-infective screens.
3. **Two groups that should *not* be blanket-flagged**: `esters` and `phenols`. These are among the most common functional groups in approved drugs. A naive "any phenol / any ester" SMARTS flags paracetamol, amoxicillin, aspirin and artemisinin (all verified below). The established catalogs never flag bare phenols/esters — they flag *specific reactive variants* (phenol esters, ≥3 esters, polyhalophenols, catechol/hydroquinone).

**Recommendation:** you do not need a new tool. RDKit's `FilterCatalog` (already wired into `drug_criteria.py`) plus the **ChEMBL alert sets via `rd_filters` / `datamol-medchem`** cover ~everything here. The right move is to (a) switch on the Brenk + ChEMBL Dundee/BMS catalogs you aren't yet using, (b) add a small custom-SMARTS catalog for chelators like 8-hydroxyquinoline, and (c) *not* implement blanket phenol/ester filters — instead report them as neutral "frequent functional groups" context, only flagging the reactive sub-patterns. See §6.

---

## 2. What "structural alert" means here

A structural alert (SA) is a substructure — encoded as SMARTS — empirically associated with a liability: chemical reactivity, metabolic instability, assay interference, promiscuity, or toxicity. Matching is a fast, fully interpretable substructure search. The catalogs differ in **what liability they target** and **how aggressive** they are:

- **Reactive / undesirable groups** (your case): groups likely to react covalently, decompose, chelate metals, or behave promiscuously — flagged for *library curation* and *hit triage*. Brenk, Glaxo, Dundee, BMS, Lilly.
- **Pan-assay interference (PAINS)**: substructures statistically enriched among frequent hitters in *specific* AlphaScreen panels. Narrower and more context-dependent than often assumed — a PAINS hit means "this readout may be artefactual", not "toxic".
- **Toxicophores**: groups tied to formal tox endpoints (Ames mutagenicity, skin sensitization, reactive-metabolite/DILI). ToxAlerts, DEREK-style rules. (Out of scope here, but noted for completeness.)

A critical caveat for Ersilia's context: **these are statistical envelopes derived largely from drug-like, often Western-pharma screening decks.** Natural products, anti-infectives, and neglected-disease chemotypes routinely carry "alerting" groups and still make legitimate drugs (nitrofurans, metronidazole's nitro group, artemisinin's peroxide). Alerts should *flag for review*, never auto-reject — exactly the philosophy already stated in your `drug-discovery-criteria.md`.

---

## 3. The catalogs (literature)

| Catalog | Alerts | Target liability | Primary reference | Notes for you |
|---|---|---|---|---|
| **Brenk** | ~105 | Reactive, unstable, toxic, dye-like groups | Brenk et al., *ChemMedChem* 2008, 3, 435–444 | **Built explicitly for neglected-disease screening libraries** (DNDi-adjacent). The most directly relevant list to Ersilia's mission. Contains `hydrazine`, `catechol`, `halogenated_ring`. In stock RDKit. |
| **PAINS (A/B/C)** | ~480 | AlphaScreen frequent-hitter interference | Baell & Holloway, *J Med Chem* 2010, 53, 2719–2740 | Contains `catechol_A(92)`. Use only for triaging *biochemical HTS hits*; over-applied in the literature. In stock RDKit. |
| **NIH (MLSMR)** | ~180 | Experimentally problematic groups | Jadhav et al. / NIH MLSMR | Contains `hydrazine`, `ortho_hydroquinone`. In stock RDKit. |
| **ChEMBL "Dundee"** | ~105 | Reactive/undesirable functional groups | Brenk/Dundee set, curated into ChEMBL | Contains `hydrazine`, `catechol`, `halogenated ring`, `>2 ester groups`, `phenol ester`. **Not** in stock RDKit enum — get it via rd_filters/medchem. |
| **ChEMBL "Glaxo" (GSK hard filters)** | ~55 | Reactive + undesirable, with reasons | Hann et al. (GSK) | Reactive esters (sulphate/HOBt/p-nitrophenyl), peroxides, Michael acceptors. Via rd_filters/medchem. |
| **ChEMBL "BMS"** | ~180 | Reactive/promiscuous (very granular) | Pearce et al. (BMS) | Contains `hydrazine`, `perhalo_phenyl`, `polyhalo_phenol`, many activated esters. Via rd_filters/medchem. |
| **ChEMBL "Inpharmatica" / "LINT" / "SureChEMBL" / "MLSMR"** | varies | Mixed reactive/undesirable | curated into ChEMBL | Via rd_filters/medchem. |
| **Eli Lilly MedChem Rules** | 275 | Reactivity, interference, instability, promiscuity — **with a demerit-scoring system** | Bruns & Watson, *J Med Chem* 2012, 55, 9763–9772 | The most sophisticated: each match adds *demerits*; >100 → reject. 18 years of in-house curation. Open source (see §4). |
| **NIBR (Novartis) filters** | ~1000 | Screening-deck curation, with severity tiers | Schuffenhauer et al. (Novartis deck design) | Tiered (exclude / flag / annotate). Available in datamol-medchem. |
| **ToxAlerts (OCHEM)** | ~600 | Formal tox endpoints (mutagenicity, sensitization, reactive metabolites) | Sushko et al., *J Chem Inf Model* 2012, 52, 2310–2316 | Toxicophore-oriented; out of your immediate scope but the best open repository if you later want tox endpoints. Web/API + downloadable SMARTS. |

A useful, often-cited observation (TeachOpenCADD, SwissADME docs): **PAINS and Brenk hits are almost never the same molecule.** They are complementary lenses, not redundant.

---

## 4. The Python tools

| Tool | What it is | Catalogs | License | Recommendation |
|---|---|---|---|---|
| **RDKit `FilterCatalog`** | Built into RDKit; you already use it | PAINS, PAINS_A/B/C, BRENK, NIH, ZINC, CHEMBL* (newer RDKit also bundles a `ChEMBL` superset) | BSD | **Already in your stack.** Zero new dependency. Covers Brenk+NIH+PAINS. |
| **`rd_filters`** (P. Walters) | Thin script over RDKit applying the **ChEMBL `structural_alerts` table** + property filters | BRENK, Glaxo, Dundee, BMS, Inpharmatica, LINT, MLSMR, SureChEMBL, NIH, PAINS_A/B/C | MIT | **Best lightweight way to get the full ChEMBL sets.** The `alert_collection.csv` is a single file you can vendor directly into the skill. |
| **`datamol-medchem`** (`medchem`) | Modern, maintained med-chem filtering library | "Common Alerts" (= rd_filters/ChEMBL), **NIBR**, **Lilly demerits**, plus RDKit catalogs | Apache-2.0 | **Best if you want NIBR tiers and Lilly demerits in pure Python** without shelling out. Heavier dependency than rd_filters. |
| **`scikit-fingerprints`** | Sklearn-style cheminformatics; has molecular-filter transformers | PAINS, Brenk, NIH, ZINC, etc. as `sklearn` transformers | MIT | Nice if you want filters inside an sklearn pipeline; otherwise overkill here. |
| **Lilly-Medchem-Rules** (I. Watson) | Official C++/Ruby implementation of the 275 demerit rules | Lilly only | open (BSD-style) | Use if you specifically want the *demerit-scored* output. Not pure Python (needs build); the medchem package reimplements the rules in Python. |
| **FAF-Drugs4** | Web server (RPBS) for ADME-Tox + alert filtering | Lilly, Brenk, PAINS, custom | web service | Good for one-off interactive checks; not a library to embed. |
| **ToxAlerts / OCHEM** | Web server + downloadable SMARTS for tox endpoints | ~600 toxicophores | web/API | For tox endpoints later; downloadable SMARTS can be vendored. |

**Verdict for the skill:** stay in RDKit. Add the ChEMBL sets by vendoring `rd_filters`' `alert_collection.csv` (a `FilterCatalog` can be built from arbitrary SMARTS), or add `datamol-medchem` if you want NIBR severity tiers and Lilly demerits without writing scoring logic yourself.

---

## 5. Where each of the six alerts actually lives (verified)

Verified with RDKit 2026.03 against the stock `FilterCatalog` enums **and** the ChEMBL/`rd_filters` SMARTS. Representative molecule in parentheses.

| Collaborator's term | Fires in stock RDKit? | Also in ChEMBL sets? | Verdict |
|---|---|---|---|
| **hydrazine** (phenylhydrazine) | ✅ BRENK, NIH | ✅ Dundee, BMS, Glaxo (acylhydrazide) | Real reactive alert. Keep. |
| **catechol** (catechol) | ✅ PAINS_B, BRENK, NIH (`ortho_hydroquinone`) | ✅ Dundee | Real alert (redox-cycling / metal chelation). Keep. |
| **polyhalogenated** (1,2,4-trichlorobenzene) | ✅ BRENK (`halogenated_ring_1`) | ✅ Dundee (`halogenated ring`), BMS (`perhalo_phenyl`, `polyhalo_phenol`) | Real alert. Keep. |
| **8-hydroxyquinoline** (8-HQ) | ❌ no hit | ❌ not present | **Gap.** Needs custom SMARTS — it's a *chelator* alert, not a reactive-group alert. |
| **esters** (ethyl benzoate) | ❌ no hit (correctly) | only *reactive* variants: `>2 esters`, `phenol ester`, activated esters | **Do not blanket-flag.** Flag only reactive ester sub-patterns. |
| **phenols** (phenol) | ❌ no hit (correctly) | only *reactive* variants: catechol, polyhalophenol, `gte_5_phenolic_OH` | **Do not blanket-flag.** Report as context; flag only reactive variants. |

**Why blanket phenol/ester filtering is wrong — concrete check.** A generic `c1ccccc1[OX2H]` (any phenol) and `[CX3](=O)[OX2H0][#6]` (any ester) match:

| Drug | Generic phenol? | Generic ester? |
|---|---|---|
| Paracetamol | ✅ | — |
| Amoxicillin | ✅ | — |
| Aspirin | ✅ (as phenol ester) | ✅ |
| Artemisinin | — | ✅ |

All four are legitimate, widely-used drugs (several central to global health). Blanket phenol/ester rules would flag them. This is exactly why the curated catalogs encode *reactive variants* instead. If your collaborators are seeing "phenol" and "ester" on an alert list, it almost certainly came from a frequency-of-occurrence analysis or an over-eager in-house filter — worth asking them for the source.

---

## 6. Integration plan for `molecule-auditing`

Your `scripts/drug_criteria.py` already exposes `structural_alerts(smiles, catalogs=...)` over `FilterCatalog`, currently mapping PAINS/PAINS_A-C/BRENK/NIH/ZINC, and `process_molecules.py` enforces only Lipinski + PAINS. Minimal, well-scoped changes:

**(1) Turn on Brenk + ChEMBL reactive sets for reactive-group auditing.**
Brenk is the single most relevant catalog (built for neglected-disease libraries). For an audit framed as "reactive/undesirable groups", default to `("BRENK", "NIH")` rather than PAINS — PAINS answers a different question (assay interference).

**(2) Add the ChEMBL Dundee/Glaxo/BMS sets via vendored SMARTS.**
Stock RDKit doesn't expose the ChEMBL vendor sets by enum. Vendor `rd_filters`' `alert_collection.csv` (MIT) into `assets/`, and build a custom `FilterCatalog` from those SMARTS at load time — same return shape as the existing function. This gives Dundee (`>2 esters`, `phenol ester`, `halogenated ring`), Glaxo (reactive esters), and BMS (`perhalo_phenyl`, `polyhalo_phenol`) without a new runtime dependency. (If you'd rather not vendor, `datamol-medchem`'s `CommonAlertsFilters` exposes the same set plus NIBR tiers and Lilly demerits.)

**(3) Add a small custom "chelator / metal-binder" catalog.**
8-hydroxyquinoline and close analogues aren't in any standard set. A handful of SMARTS (8-HQ, bidentate catechol-as-chelator, hydroxypyridinones, kojic-acid-like) gives you the chelator lens, which matters in anti-infective work where iron/zinc chelation is a common confounder. Keep it as a separate named catalog so it's clearly *chelation*, not *reactivity*.

**(4) Do NOT add blanket phenol/ester filters.**
Instead, surface them as neutral "functional-group census" context in the report (e.g. "contains: phenol, ester"), and only *flag* the reactive sub-patterns the catalogs already encode. This avoids flagging a large fraction of legitimate anti-infectives.

**(5) Optional: adopt Lilly-style demerit scoring.**
If you want a single tunable "reactivity burden" number rather than binary hits, the Lilly demerit model (sum of per-match demerits, reject >100) is the most validated scheme. Available in `datamol-medchem`. Useful for *ranking* a library rather than gating it.

Suggested default for a reactive-group audit context:
```
catalogs = ("BRENK", "NIH", "ChEMBL_Dundee", "ChEMBL_Glaxo", "ChEMBL_BMS", "Chelators")
# PAINS reserved for an explicit "assay interference" audit mode
```

---

## 7. References

**Catalogs / primary literature**
- Brenk, Schipani, James, Krasowski, Gilbert, Frearson, Wyatt. *Lessons Learnt from Assembling Screening Libraries for Drug Discovery for Neglected Diseases.* ChemMedChem 2008, 3, 435–444. https://chemistry-europe.onlinelibrary.wiley.com/doi/full/10.1002/cmdc.200700139
- Baell, Holloway. *New Substructure Filters for Removal of Pan Assay Interference Compounds (PAINS).* J Med Chem 2010, 53, 2719–2740.
- Bruns, Watson. *Rules for Identifying Potentially Reactive or Promiscuous Compounds.* J Med Chem 2012, 55, 9763–9772. https://pubs.acs.org/doi/10.1021/jm301008n
- Sushko, Salmina, Potemkin, Poda, Tetko. *ToxAlerts: A Web Server of Structural Alerts for Toxic Chemicals and Compounds with Potential Adverse Reactions.* J Chem Inf Model 2012, 52, 2310–2316. https://pubs.acs.org/doi/10.1021/ci300245q

**Tools**
- RDKit `FilterCatalog`: https://www.rdkit.org/docs/source/rdkit.Chem.rdfiltercatalog.html  (origin PR: https://github.com/rdkit/rdkit/pull/536)
- `rd_filters` (P. Walters): https://github.com/PatWalters/rd_filters  — alert data: `rd_filters/data/alert_collection.csv`
- `datamol-medchem` (Common Alerts / NIBR / Lilly): https://medchem-docs.datamol.io/stable/tutorials/Structural_Filters.html
- Lilly-Medchem-Rules (I. Watson): https://github.com/IanAWatson/Lilly-Medchem-Rules
- ToxAlerts / OCHEM: https://docs.ochem.eu/display/MAN/ToxAlerts:+Database+of+structural+alerts.html
- TeachOpenCADD T003 (unwanted substructures tutorial): https://projects.volkamerlab.org/teachopencadd/talktorials/T003_compound_unwanted_substructures.html
- Practical Cheminformatics — "Filtering Chemical Libraries": http://practicalcheminformatics.blogspot.com/2018/08/filtering-chemical-libraries.html

*All substructure-match claims in §5 verified with RDKit 2026.03.2 against the stock FilterCatalog enums and the ChEMBL/rd_filters SMARTS.*
