# Drug Discovery Criteria

Catalogue of established property rules, composite scores, efficiency metrics, and structural-alert catalogs used to evaluate small molecules. Implementations live in `../scripts/drug_criteria.py`; this file is the rule catalogue, threshold reference, and citation index.

These rules are statistical envelopes derived from historical small-molecule drugs, not laws. A violation is a signal to look closer — macrocycles, PROTACs, antibiotics and natural products routinely sit outside Ro5 and still reach the clinic. Apply the rule that matches the dosing route and target context (see §6).

---

## 1. Property envelopes (hard filters)

Each rule below is a pass/fail filter over physicochemical descriptors. The summary table compares thresholds side-by-side; per-rule details follow.

| Rule | MW (Da) | LogP | HBD | HBA | TPSA (Å²) | RotB | Other | Use case |
|---|---|---|---|---|---|---|---|---|
| **Lipinski Ro5** | ≤500 | ≤5 | ≤5 | ≤10 | — | — | — | Oral small-molecule |
| **Rule of 3** | ≤300 | ≤3 | ≤3 | ≤3 | ≤60 | ≤3 | — | Fragment-based screening |
| **Ghose** | 160–480 | −0.4 to 5.6 | — | — | — | — | 40≤MR≤130, 20≤HAC≤70 | Drug-like library curation |
| **Veber** | — | — | — | — | ≤140 | ≤10 | — | Oral bioavailability (Lipinski complement) |
| **Egan** | — | ≤5.88 | — | — | ≤131.6 | — | — | Passive absorption |
| **Muegge** | 200–600 | −2 to 5 | ≤5 | ≤10 | ≤150 | ≤15 | rings≤7, C≥4, het≥1 | Conservative drug-likeness |
| **bRo5 (Doak)** | ≤1000 | −2 to 10 | ≤6 | ≤15 | ≤250 | ≤20 | — | Beyond-Ro5 oral space (macrocycles, etc.) |

### 1.1 Lipinski's Rule of Five
Lipinski et al., *Adv Drug Deliv Rev* 1997. Two or more violations → unlikely to be orally bioavailable. The most cited filter; designed for passive permeability and aqueous solubility of orally dosed small molecules. → `lipinski_violations(smiles)`

### 1.2 Rule of 3
Congreve et al., *Drug Discov Today* 2003. Tighter envelope for fragments (~150–300 Da) used in FBDD. Fragments are weak binders (IC50 typically mM–high µM) but enable efficient SAR exploration of larger chemical space. → `ro3_violations(smiles)`

### 1.3 Ghose filter
Ghose, Viswanadhan & Wendoloski, *J Comb Chem* 1999. Drug-likeness envelope derived from the CMC database; adds molar refractivity (MR) and heavy-atom count to the property panel. Often used as a library curation filter alongside Lipinski. → `ghose_violations(smiles)`

### 1.4 Veber's rules
Veber et al., *J Med Chem* 2002. Rotatable bonds (≤10) and TPSA (≤140 Å²) predict oral bioavailability independently of MW/LogP. Captures conformational flexibility and polarity penalties that Lipinski misses. → `veber_violations(smiles)`

### 1.5 Egan rule
Egan, Merz & Baldwin, *J Med Chem* 2000. Two-property filter (TPSA, LogP) predicting passive intestinal absorption. Underlies the white-region boundary of BOILED-Egg (§3.5). → `egan_violations(smiles)`

### 1.6 Muegge filter
Muegge, Heald & Brittelli, *J Med Chem* 2001. Bayer's conservative drug-likeness filter — adds ring count, carbon count and heteroatom count to Lipinski/Veber. Stricter than Lipinski on the low-MW end (excludes fragments). → `muegge_violations(smiles)`

### 1.7 Beyond-Ro5 (bRo5)
Doak, Over, Giordanetto & Kihlberg, *Chem Biol* 2014. Empirical envelope for oral drugs that violate Ro5 — covers macrocycles, peptidomimetics, and many natural products. Use this as the filter when working in the bRo5 space rather than discarding compounds for Lipinski violations. → `bro5_violations(smiles)`

---

## 2. Single-rule risk flags

Binary flags that pair two descriptors to predict downstream liability. Treat as warnings, not disqualifications.

| Flag | Condition | Risk highlighted | Source |
|---|---|---|---|
| **Pfizer 3/75** | LogP > 3 **AND** TPSA < 75 | ~2.5× higher *in vivo* toxicity risk | Hughes et al., *Bioorg Med Chem Lett* 2008 |
| **GSK 4/400** | MW > 400 **AND** LogP > 4 | Higher promiscuity / ADMET liabilities | Gleeson, *J Med Chem* 2008 |

→ `pfizer_3_75_flag(smiles)`, `gsk_4_400_flag(smiles)`

---

## 3. Composite drug-likeness scores

Continuous scores that collapse several descriptors into a single value. Useful for ranking; always inspect the underlying descriptors before acting on the composite alone.

### 3.1 QED — Quantitative Estimate of Drug-likeness
Bickerton, Paolini, Besnard, Muresan & Hopkins, *Nat Chem* 2012. Weighted geometric mean of desirability functions over MW, LogP, HBD, HBA, TPSA, RotB, aromatic ring count, and structural-alert count. Output in [0, 1]; ≥ 0.5 commonly used as a drug-like cut-off. → `qed_score(smiles)`

### 3.2 Fsp³ — Fraction of sp³ carbons
Lovering, Bikker & Humblet, *J Med Chem* 2009 ("Escape from flatland"). Fsp³ ≥ 0.42 correlates with higher clinical success rates. Captures 3D-character / stereochemical complexity. → `fsp3(smiles)`

### 3.3 Aromatic ring count
Ritchie & Macdonald, *Drug Discov Today* 2009. > 3 aromatic rings worsens solubility, hERG, CYP and overall developability. Aim for ≤ 3. → `n_aromatic_rings(smiles)`

### 3.4 BOILED-Egg
Daina & Zoete, *ChemMedChem* 2016. Two-region classifier on the TPSA × WLogP plane: the white region predicts human intestinal absorption (HIA+). The inner yolk region is sometimes used to predict BBB penetration; ignore that aspect outside CNS contexts. Returns `"HIA"`, `"BBB"` (inside yolk) or `"outside"`. The implementation uses a bounding-box approximation of the original ellipses. → `boiled_egg(smiles)`

### 3.5 Synthetic accessibility
**SAscore** — Ertl & Schuffenhauer, *J Cheminform* 2009. Score 1 (easy) to 10 (hard); ≤ 4 broadly considered tractable. Ships in RDKit's `Contrib/SA_Score` directory. Useful as a sanity check on hits from generative or large virtual libraries.

Alternatives in the literature, not implemented here: **SCScore** (Coley et al., *J Chem Inf Model* 2018; learned from reaction corpora), **RAscore** (Thakkar et al., *Chem Sci* 2021; deep-learning retrosynthesis classifier), **SYBA** (Voráč et al., *J Cheminform* 2020).

---

## 4. Efficiency metrics

Normalise potency by size or lipophilicity to detect optimisation drift. All require measured or predicted activity (pIC50 / pKi).

| Metric | Formula | Target | Use | Source |
|---|---|---|---|---|
| **LE** — Ligand Efficiency | 1.4 × pIC50 / heavy atoms | ≥ 0.3 kcal/mol/atom | Catch MW creep; fragment-to-lead tracking | Hopkins, Groom & Alex 2004 |
| **LipE / LLE** | pIC50 − LogP | ≥ 5 | Catch lipophilicity-driven potency | Leeson & Springthorpe 2007 |
| **BEI** — Binding Efficiency Index | pIC50 / MW (kDa) | ≥ 20 | Binding per unit mass | Abad-Zapatero & Metz 2005 |
| **SEI** — Surface Efficiency Index | pIC50 / (TPSA/100) | ≥ 15 | Binding per unit polar surface | Abad-Zapatero & Metz 2005 |
| **PFI** — Property Forecast Index | LogD₇.₄ + #aromatic rings | ≤ 7 | Developability proxy (solubility, hERG) | Young et al. 2011 |

→ `ligand_efficiency`, `lip_e`, `bei`, `sei`, `pfi` in `drug_criteria.py`. PFI is approximated with LogP since LogD₇.₄ requires pKa.

---

## 5. Structural alerts

RDKit's `FilterCatalog` ships several substructure catalogs, each flagging a different category of liability. Use them selectively — a PAINS hit means "the assay readout may be artefactual", not "the compound is toxic".

| Catalog enum | Flags | When to use | Source |
|---|---|---|---|
| **PAINS** (full) | Pan-assay interference substructures (aggregators, redox-cyclers, fluorophores, chelators) | Triaging hits from biochemical / HTS screens | Baell & Holloway, *J Med Chem* 2010 |
| **PAINS_A / _B / _C** | PAINS subsets by frequency (A = most common offenders, C = least) | Use a subset for stricter or looser PAINS gating | Baell & Holloway 2010 |
| **BRENK** | Reactive, unstable, or undesirable functional groups | General library curation; medicinal-chemistry filter | Brenk et al., *ChemMedChem* 2008 |
| **NIH** | Substructures known to cause experimental headaches in the NIH MLSMR | Curation for high-throughput screening | NIH MLSMR |
| **ZINC** | Drug-like sanity (large fused systems, reactives) | First-pass virtual library curation | Irwin & Shoichet, ZINC |

These are the catalogs exposed by `FilterCatalogParams.FilterCatalogs` in stock RDKit. Other curated alert sets in the literature (require custom SMARTS, not in the RDKit enum): **Eli Lilly MedChem Rules** (Bruns & Watson, *J Med Chem* 2012; 275 alerts), **Glaxo hard filters** (Hann et al.), **Inpharmatica**, **Dundee**, **BMS**, **SureChEMBL**, **MLSMR**, **ChEMBL** composite (Sushko et al., *Mol Inform* 2012).

→ `structural_alerts(smiles, catalogs=("PAINS","BRENK",...))`

---

## 6. Context → ruleset mapping

Trigger keywords from the `--context` argument switch which ruleset(s) apply. Match case-insensitively as substrings.

| Keyword class | Examples | Apply | Comment |
|---|---|---|---|
| Anti-infective | `antibiotic`, `antimicrobial`, `antibacterial`, `antifungal`, `antimalarial`, `antiparasitic`, `anti-infective` | See [`shared-anti-infective-criteria.md`](./shared-anti-infective-criteria.md) and the matching per-bucket file (`gram-negative-criteria.md`, `antimycobacterial-criteria.md`, etc.) | Many classes break Ro5 — don't auto-reject |
| Oral | `oral`, `oral bioavailability` | Lipinski + Veber | Default |
| Parenteral / topical / inhaled | `IV`, `intravenous`, `topical`, `inhaled` | bRo5 envelope (§1.7) | Loosen size & lipophilicity |
| Beyond-Ro5 chemotypes | `PROTAC`, `degrader`, `macrocycle`, `natural product` | bRo5 envelope (§1.7) | Ro5 violations expected |
| Fragment screen | `fragment`, `FBDD` | Rule of 3 (§1.2) | Tighter envelope |
| (no match) | — | Lipinski + Veber | Default to oral small-molecule |

When multiple keywords match, apply the most restrictive ruleset consistent with the dosing route and note the trade-off in the report.

---

## 7. Implementation

All rules and scores in this document are implemented in `../scripts/drug_criteria.py` with consistent return types:

| Category | Return type |
|---|---|
| Hard filters (§1) | `(n_violations: int, violations: list[str])` |
| Risk flags (§2) | `bool` |
| Composite scores (§3) | `float` (or `str` for BOILED-Egg) |
| Efficiency metrics (§4) | `float` (require `pIC50`) |
| Structural alerts (§5) | `dict[str, str]` (catalog → first match) |

One-shot evaluation:

```python
from drug_criteria import evaluate
report = evaluate("CCN(CC)CCNC(=O)c1cc(Cl)c(N)cc1OC", pIC50=7.2,
                  alert_catalogs=("PAINS", "BRENK"))
# report["filters"]["lipinski"] = {"n_violations": 0, "violations": []}
# report["scores"]["qed"]       = 0.78
# report["alerts"]              = {}  # nothing fired
```

The molecule-auditing script (`process_molecules.py`) currently enforces Lipinski and PAINS directly; the other rules in this module are available for reports that need broader coverage (bRo5, fragments, structural-alert panels beyond PAINS) without re-implementing.

---

## 8. References

**Property envelopes**
- Lipinski, Lombardo, Dominy, Feeney. *Adv Drug Deliv Rev* 1997, 23, 3–25. — Rule of Five.
- Congreve, Carr, Murray, Jhoti. *Drug Discov Today* 2003, 8, 876–877. — Rule of 3.
- Ghose, Viswanadhan, Wendoloski. *J Comb Chem* 1999, 1, 55–68. — Ghose filter.
- Veber, Johnson, Cheng, Smith, Ward, Kopple. *J Med Chem* 2002, 45, 2615–2623. — RotB, TPSA.
- Egan, Merz, Baldwin. *J Med Chem* 2000, 43, 3867–3877. — Passive absorption.
- Muegge, Heald, Brittelli. *J Med Chem* 2001, 44, 1841–1846. — Bayer drug-likeness.
- Doak, Over, Giordanetto, Kihlberg. *Chem Biol* 2014, 21, 1115–1142. — bRo5.

**Risk flags**
- Hughes, Blagg, Price, et al. *Bioorg Med Chem Lett* 2008, 18, 4872–4875. — Pfizer 3/75.
- Gleeson. *J Med Chem* 2008, 51, 817–834. — GSK 4/400.

**Composite scores**
- Bickerton, Paolini, Besnard, Muresan, Hopkins. *Nat Chem* 2012, 4, 90–98. — QED.
- Lovering, Bikker, Humblet. *J Med Chem* 2009, 52, 6752–6756. — Fsp³.
- Ritchie, Macdonald. *Drug Discov Today* 2009, 14, 1011–1020. — Aromatic rings.
- Daina, Zoete. *ChemMedChem* 2016, 11, 1117–1121. — BOILED-Egg.
- Ertl, Schuffenhauer. *J Cheminform* 2009, 1, 8. — SAscore.

**Efficiency metrics**
- Hopkins, Groom, Alex. *Drug Discov Today* 2004, 9, 430–431. — Ligand efficiency.
- Leeson, Springthorpe. *Nat Rev Drug Discov* 2007, 6, 881–890. — LipE / LLE.
- Abad-Zapatero, Metz. *Drug Discov Today* 2005, 10, 464–469. — BEI / SEI.
- Young, Green, Leeson, Marchese Robinson, Price. *Drug Discov Today* 2011, 16, 822–830. — PFI.

**Structural alerts**
- Baell, Holloway. *J Med Chem* 2010, 53, 2719–2740. — PAINS.
- Brenk, Schipani, James, Krasowski, Gilbert, Frearson, Wyatt. *ChemMedChem* 2008, 3, 435–444. — Brenk filters.
- Bruns, Watson. *J Med Chem* 2012, 55, 9763–9772. — Eli Lilly MedChem Rules.
- Sushko, Salmina, Potemkin, Poda, Tetko. *Mol Inform* 2012, 31, 711–720. — ChEMBL alerts.
