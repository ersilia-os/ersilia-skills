# Gram-Positive Criteria

> Audit guidance for compounds targeting gram-positive pathogens — *Staphylococcus aureus* (including MRSA), *Streptococcus pneumoniae*, *S. pyogenes*, *Enterococcus faecalis* and *E. faecium* (including VRE), *Clostridioides difficile*. Cross-link: [shared anti-infective concepts](./shared-anti-infective-criteria.md).

## Quick rules (Claude reads these first)

- **Permeability is not the gate** for gram-positives the way it is for gram-negatives. A single peptidoglycan-thick cell wall is far more permeable than an outer membrane; hits failing on activity are usually mechanism failures, not entry failures.
- **Cell wall + ribosome dominate the validated target list.** β-lactams (PBPs), glycopeptides (lipid II), oxazolidinones, macrolides, lincosamides, streptogramins. Recognising scaffolds here = recognising the validated target.
- **Lipinski-tolerant.** Many clinical drugs (vancomycin, teicoplanin, daptomycin) violate every rule — they work because the target sits on the outside of the cell.
- **Resistance is the main strategic concern.** MRSA, VRE, MDR *S. pneumoniae* — a hit's value depends heavily on whether it overcomes a clinically relevant resistance mechanism.
- **MW window is wide** (350–1900 in clinical use); novel leads should still aim ≤ 500 to keep optimisation headroom, but accept that the bucket's clinical reality spans much wider.
- **Bacterial selectivity over the mitochondrial ribosome** matters for oxazolidinones (linezolid) — extended use causes haematological / mitochondrial toxicity. Flag persistent off-target tox patterns.
- **Anaerobic *C. difficile*** has its own structural preferences (fidaxomicin, metronidazole, vancomycin) — when the context specifies *C. difficile*, narrow-spectrum gut-acting compounds are preferred.

## Pathogen biology essentials

Gram-positive bacteria have a single cytoplasmic membrane surrounded by a thick (20–80 nm) **peptidoglycan** cell wall, often decorated with **teichoic acids** and surface proteins. The cell wall is mechanically demanding but chemically permeable — small molecules diffuse through readily. Key implications:

- **External targets are accessible.** Lipid II (peptidoglycan precursor), PBPs, and the membrane itself are all on the outside; this is why huge molecules like vancomycin (MW 1450) and daptomycin (MW 1620) work.
- **The cytoplasmic membrane** is the main barrier for intracellular targets; oxazolidinones and fluoroquinolones cross it readily.
- **No outer-membrane efflux** of the gram-negative variety; resistance comes from target modification (mecA in MRSA → modified PBP2a; vanA/B in VRE → D-Ala-D-Lac peptidoglycan precursors), efflux pumps (NorA, mefA), and enzymatic destruction (β-lactamases).

MRSA and VRE epidemiology drive most current gram-positive R&D ([Murray 2022](https://doi.org/10.1016/S0140-6736(21)02724-0)). *C. difficile* sits in a special category — gut-acting, spore-forming, recurrence-prone.

## Property windows (empirically derived)

### Property windows for `gram_positive` (n = 12 compounds)

| Property | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| MW | 334.4 | 348.9 | 453.7 | 693.6 | 1868.2 |
| LogP | -4.08 | 0.37 | 0.99 | 1.90 | 11.76 |
| TPSA | 71.1 | 110.1 | 139.5 | 165.4 | 657.3 |
| HBD | 1 | 3 | 4 | 4 | 22 |
| HBA | 4 | 5 | 9 | 13 | 26 |
| RotBonds | 4 | 4 | 6 | 7 | 30 |
| AromaticRings | 0 | 0 | 1 | 2 | 10 |
| Fsp3 | 0.20 | 0.41 | 0.47 | 0.94 | 0.97 |
| HeavyAtoms | 23 | 24 | 31 | 48 | 132 |

**Outlier compounds** (any property outside the p5–p95 band):
- **Teicoplanin** — MW=1868, RDKit LogP≈11.8 (unreliable for large glycopeptides), HeavyAtoms=132. Multi-glycosylated lipoglycopeptide; the LogP estimate is noise — log-D7.4 measured is near zero.
- **Daptomycin** — MW=1620, LogP=−4.1, RotBonds=30, HBD=22. Cyclic lipopeptide; membrane-disruption MoA via Ca²⁺-dependent insertion. Calculated LogP underestimates because the lipid tail balances the polar core.
- **Penicillin G** — small outlier; MW=334, HeavyAtoms=23. The minimal β-lactam scaffold.
- **Linezolid / Tedizolid** — TPSA / Fsp3 outliers; small lean compounds illustrating the oxazolidinone class.
- **Azithromycin** — Fsp3=0.97. Macrolide; nearly fully saturated lactone scaffold.

Note: RDKit's `MolLogP` is unreliable for very large, heavily-glycosylated, or zwitterionic compounds — vancomycin (excluded) and teicoplanin (included) both have estimated values far from measured log-D. Use these for trend-spotting, not as quantitative descriptors.

**Target window for novel leads: MW 300–550, LogP 0–3, TPSA 80–150, HBD ≤ 5.** Macromolecules (glycopeptides, lipopeptides) are a separate strategy with different optimisation rules.

## Structural traits that favour activity

- **β-lactam ring + acyl side chain** — covalent inhibition of PBPs; entire mature pharmacopoeia. Side-chain identity drives spectrum and β-lactamase stability ([Llarrull 2010](https://doi.org/10.1016/j.cbpa.2010.06.180)).
- **Glycopeptide aglycone (peptidic + biphenyl macrocycle)** binding D-Ala-D-Ala in lipid II. Vancomycin / teicoplanin scaffold; lipo- and bis-glycosylated extensions (oritavancin, dalbavancin, telavancin) restore activity against VRE.
- **Oxazolidinone + 5-acetamidomethyl + aryl-fluorophenyl + morpholino** — the linezolid pharmacophore; binds 23S rRNA at the peptidyl-transferase centre ([Barbachyn & Ford 2003](https://doi.org/10.1002/anie.200200528)).
- **14-, 15-, 16-membered macrolactones with desosamine** — macrolide ribosomal binding; ketolides (telithromycin, solithromycin) overcome erm/mef resistance.
- **Lipopeptide with cyclic peptide + acyl tail** (daptomycin, surotomycin) — membrane disruption MoA; Ca²⁺-dependent ([Robbel & Marahiel 2010](https://doi.org/10.1074/jbc.R110.119008)).
- **Cyclic lipoglycopeptides** (oritavancin, dalbavancin) — long half-life (single-dose use cases), retain glycopeptide MoA.

## Structural traits that lower activity or signal liabilities

- **Pure β-lactam without β-lactamase stability** features (e.g. acyl side chain prone to ring opening) — destroyed by staphylococcal β-lactamases.
- **Cationic compounds resembling polymyxins** are nephrotoxic and typically lack gram-positive selectivity advantage over established options.
- **Aminoglycoside-like polycations** retain some gram-positive activity (synergy with cell-wall agents) but rarely useful as monotherapy.
- **PBP2a (MRSA) blindness** — many older β-lactams lack the chemistry to engage PBP2a; ceftaroline-like 5th-generation cephalosporins were specifically designed to bind it.
- **Vancomycin-like glycopeptide analogs** that hit only D-Ala-D-Ala — face VRE pre-existing resistance (D-Ala-D-Lac substitution).

## Permeability / accumulation peculiarities

The gram-positive cell wall is permeable; the relevant "barrier" considerations are:

- **External vs internal targets** — external targets (PBPs, lipid II, membrane) bypass permeability entirely. Internal targets (ribosome, gyrase, DHFR) require cytoplasmic membrane crossing.
- **Efflux pumps** — NorA (*S. aureus*), MefA / MefE (*S. pneumoniae*), MsrA — primarily affect ribosomal target drugs.
- **Cell wall thickness in VISA/hVISA** — thickened cell wall sequesters vancomycin before it reaches lipid II; clinical mechanism for reduced glycopeptide susceptibility.
- **Anaerobic / intracellular distribution** — *C. difficile* lives in colon; oral non-absorbed compounds (fidaxomicin, oral vancomycin) preferred for that indication.

## Safety liabilities specific to this bucket

- **Mitochondrial / haematological toxicity** — oxazolidinones bind eukaryotic mitochondrial ribosomes at high exposure; long-course linezolid causes thrombocytopenia / lactic acidosis / optic neuropathy. Tedizolid has a wider window.
- **Nephrotoxicity** — vancomycin (cumulative dose / trough-driven); rare with newer glycopeptides.
- **Red-man syndrome** — vancomycin infusion-rate dependent; chemistry-related (histamine release).
- **QT prolongation** — macrolides (clarithromycin > azithromycin > erythromycin); apply hERG threshold.
- **β-lactam allergy** — patient-specific.
- **Eosinophilic pneumonia** — daptomycin-class; long-treatment watch-out.
- **MAOI activity** — linezolid is a weak MAO inhibitor; drug-drug interaction risk with serotonergic agents.

## Mechanism-of-action shortcuts

| Target | Drug class / archetype | Recognisable feature |
|---|---|---|
| PBPs / cell-wall transpeptidation | β-lactams (penicillins, cephalosporins, carbapenems) | β-lactam ring + acyl side chain |
| Lipid II (D-Ala-D-Ala) | Glycopeptides (vancomycin, teicoplanin) | Peptidic + biphenyl macrocycle |
| Lipid II (different epitope) | Lipoglycopeptides (oritavancin, dalbavancin) | Glycopeptide + lipophilic tail |
| Membrane (Ca²⁺-dependent) | Lipopeptides (daptomycin) | Cyclic peptide + decanoyl tail |
| 23S rRNA peptidyl transferase | Oxazolidinones (linezolid, tedizolid) | 5-acetamidomethyl-oxazolidinone + aryl-F-morpholino |
| 50S ribosome | Macrolides (azithromycin, clarithromycin) | Macrolactone + desosamine |
| 50S ribosome | Lincosamides (clindamycin) | Sugar + thiomethyl + amide |
| 50S ribosome | Streptogramins (quinupristin/dalfopristin) | Two-component synergistic pair |
| Topo IV / gyrase | Fluoroquinolones | Quinolone-3-carboxylic acid + C-6 F |
| RNA polymerase σ factor | Fidaxomicin (*C. difficile*) | Macrocyclic ansamycin |
| Reductive activation (anaerobes) | Metronidazole | 5-nitroimidazole |

## How to interpret Ersilia model outputs in this context

- **`saureus_*` / `staph_*` / `mrsa_*` columns** → primary `efficacy` for this bucket; if both MSSA and MRSA columns present, MRSA activity is more valuable.
- **`spneumoniae_*` columns** — community-acquired pneumonia relevance; secondary efficacy weight.
- **`enterococcus_*` / `vre_*` columns** — VRE activity is a strategic priority; escalate weight when present.
- **`cdiff_*` / `c_difficile_*` columns** — narrow-spectrum gut-acting; consider whether oral bioavailability should be *avoided* (gut-restricted is preferred).
- **`mit_tox_*` / mitochondrial toxicity columns** — escalate for oxazolidinone-like scaffolds.
- **`hERG` columns** — apply standard threshold; macrolides + fluoroquinolones are the relevant scaffolds.

## References

| # | Author, Year | Title | Source | Link |
|---|---|---|---|---|
| 1 | Murray et al., 2022 | Global burden of bacterial antimicrobial resistance in 2019: a systematic analysis | Lancet | https://doi.org/10.1016/S0140-6736(21)02724-0 |
| 2 | Barbachyn & Ford, 2003 | Oxazolidinone structure-activity relationships leading to linezolid | Angew Chem Int Ed | https://doi.org/10.1002/anie.200200528 |
| 3 | Robbel & Marahiel, 2010 | Daptomycin, a bacterial lipopeptide synthesized by a nonribosomal machinery | J Biol Chem | https://doi.org/10.1074/jbc.R110.119008 |
| 4 | Llarrull et al., 2010 | The future of the β-lactams | Curr Opin Chem Biol | https://doi.org/10.1016/j.cbpa.2010.06.180 |
| 5 | Howden et al., 2010 | Reduced vancomycin susceptibility in *Staphylococcus aureus*, including vancomycin-intermediate and heterogeneous vancomycin-intermediate strains | Clin Microbiol Rev | https://doi.org/10.1128/CMR.00042-09 |
| 6 | Arias & Murray, 2009 | Antibiotic-resistant bugs in the 21st century — a clinical super-challenge | N Engl J Med | https://doi.org/10.1056/NEJMp0804651 |
| 7 | Brown & Wright, 2016 | Antibacterial drug discovery in the resistance era | Nature | https://doi.org/10.1038/nature17042 |
| 8 | WHO | WHO bacterial priority pathogens list | — | https://www.who.int/publications/i/item/9789240093461 |

_Last reviewed: 2026-05_
