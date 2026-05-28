# Gram-Negative Criteria

> Audit guidance for compounds targeting gram-negative pathogens — Enterobacteriaceae (*E. coli*, *Klebsiella pneumoniae*), *Pseudomonas aeruginosa*, *Acinetobacter baumannii*, *Salmonella*, *Shigella*, *N. gonorrhoeae*. Penetration of the outer membrane is the dominant challenge. Cross-link: [shared anti-infective concepts](./shared-anti-infective-criteria.md).

## Quick rules (Claude reads these first)

- **Permeability > potency** at the hit-triage stage. A compound with weak biochemical activity that enters the cell often beats a potent one that doesn't.
- **Small + polar + amine-bearing + rigid** is the eNTRy-rule shorthand ([Richter 2017](https://doi.org/10.1038/nature22308)) — see Permeability section. This audit does *not* compute eNTRy programmatically (globularity requires 3D conformers); apply it qualitatively when interpreting hits.
- **Target MW ≤ 600** for novel leads; clinical drugs reach 800–1100 (cephalosporins, polymyxins) but expanding from a hit-stage 800 Da compound is rarely productive.
- **logD7.4 < 1** is the empirical sweet spot for gram-neg accumulation ([Brown 2014](https://doi.org/10.1021/jm501552x)). Highly lipophilic compounds (LogP > 3) usually fail penetration despite favourable host PK.
- **Primary amine + carboxylate is a known good combination** (fluoroquinolones, β-lactams, carbapenems) — promotes both porin uptake and aqueous solubility.
- **Efflux is everywhere.** Assume AcrAB-TolC (Enterobacteriaceae) / MexAB-OprM (*P. aeruginosa*) will challenge any non-zwitterionic hit; co-administered efflux pump inhibitors are an active research direction.
- **ESKAPE pathogens (*K. pneumoniae*, *A. baumannii*, *P. aeruginosa*, *Enterobacter*) carry distinct resistance landscapes** — a hit working on *E. coli* may fail against the clinically prioritised pathogens. Treat *E. coli*-only activity columns as a starting point, not a definitive answer.

## Pathogen biology essentials

Gram-negative bacteria have a **double membrane**: a cytoplasmic (inner) membrane and an asymmetric **outer membrane** with lipopolysaccharide (LPS) on the outer leaflet and phospholipid on the inner. The outer membrane is low-fluidity, negatively charged, and excludes most small molecules. The few entry routes:

- **Porins** (OmpF, OmpC, OmpD in Enterobacteriaceae; OprD in *P. aeruginosa*) — water-filled channels with size cutoffs ~600 Da; favour small, polar, weakly-charged molecules.
- **Self-promoted uptake** by polycationic compounds (polymyxins) that disrupt LPS organisation.
- **Active transport** via specific permeases / siderophore mimicry.
- **Diffusion through the lipid bilayer** — slow and limited to small, lipophilic, neutral compounds.

The periplasmic space hosts β-lactamases that degrade β-lactam compounds en route to PBP targets. Drugs that reach the cytoplasm then encounter the cytoplasmic membrane, multiple efflux pumps, and intracellular targets.

The ESKAPE pathogens (*Enterococcus faecium*, *Staphylococcus aureus*, *Klebsiella pneumoniae*, *Acinetobacter baumannii*, *Pseudomonas aeruginosa*, *Enterobacter*) are the WHO-prioritised AMR concerns; the gram-negatives in this list (KPAE) drive most current antibiotic R&D. *E. coli* is the standard screening organism but is a relatively easy gram-negative; *P. aeruginosa* and *A. baumannii* are far harder due to lower porin permeability and more aggressive efflux.

## Property windows (empirically derived)

### Property windows for `gram_negative` (n = 12 compounds)

| Property | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| MW | 240.1 | 353.9 | 441.5 | 554.6 | 1116.4 |
| LogP | -7.82 | -1.72 | -0.93 | 0.95 | 1.58 |
| TPSA | 74.6 | 114.7 | 182.5 | 204.8 | 441.3 |
| HBD | 1 | 3 | 4 | 6 | 16 |
| HBA | 4 | 6 | 10 | 12 | 16 |
| RotBonds | 2 | 4 | 6 | 8 | 24 |
| AromaticRings | 0 | 0 | 1 | 2 | 2 |
| Fsp3 | 0.14 | 0.36 | 0.49 | 0.69 | 1.00 |
| HeavyAtoms | 17 | 25 | 30 | 37 | 79 |

**Outlier compounds** (any property outside the p5–p95 band):
- **Colistin** — MW=1116, TPSA=441, HBD=16, RotBonds=24. Cyclic lipopeptide; works via membrane disruption, not classical permeability.
- **Amikacin** — LogP=−7.82. Aminoglycoside; uses self-promoted uptake via LPS-binding amines.
- **Gentamicin** — Fsp3=1.00. Aminoglycoside, all-aliphatic scaffold.
- **Nitrofurantoin** — MW=240. Old-generation small-molecule UTI drug; reductive activation MoA.
- **Ciprofloxacin / Levofloxacin** — narrow rotatable-bond / TPSA outliers but classic gram-neg leads.

The median LogP of −0.93 reflects the polarity bias of clinically successful gram-neg agents: this is *not* an artefact, it's the design principle. **Target window for novel leads: MW 300–500, LogP −2 to +1, TPSA 100–200, HBD 2–6, at least one ionisable amine.**

## Structural traits that favour activity

- **Primary or secondary amine** (eNTRy rule criterion 1) — strongly correlates with intracellular accumulation in *E. coli* ([Richter 2017](https://doi.org/10.1038/nature22308)). Amphoteric / zwitterionic compounds (β-lactams, fluoroquinolones) reliably penetrate.
- **Rigid scaffolds with low rotatable-bond count** (eNTRy criterion 3) — fewer than ~5 rotatable bonds correlates with accumulation. Flexibility allows compounds to fold and avoid porin uptake.
- **Globularity ≤ 0.25** (eNTRy criterion 2) — flat, planar scaffolds enter porins more readily than spherical molecules. Globularity is a 3D shape descriptor; this audit does *not* compute it but the conceptual rule (flatter = better) applies to hit triage.
- **Zwitterion at physiological pH** — favours porin uptake, reduces efflux.
- **Catechol / hydroxamic acid + siderophore mimicry** (cefiderocol) — hijacks iron-uptake systems for active transport.
- **Polycationic peptidic scaffolds** (polymyxins, daptomycin analogs) — disrupt LPS organisation; effective but with nephrotox cost.

## Structural traits that lower activity or signal liabilities

- **High lipophilicity (LogP > 3)** — even with good biochemical activity, lipophilic compounds rarely accumulate in gram-negatives because they preferentially partition into membranes and become substrates for efflux ([Brown 2014](https://doi.org/10.1021/jm501552x)).
- **MW > 600** — exceeds porin size cutoff for diffusion-based entry; requires a specific active-transport hook.
- **No ionisable groups** — neutral, lipophilic compounds are efflux-prone and porin-blind.
- **High globularity scaffolds** (spirocycles, bridged bicyclics) — eNTRy-rule violators; expect poor accumulation regardless of biochemical potency.
- **Hits resembling clinical antibiotics** of the same class — class-level resistance (β-lactamases, aminoglycoside-modifying enzymes, ribosomal protection) limits the value of close analogs.

## Permeability / accumulation peculiarities — the eNTRy rules

[Richter 2017](https://doi.org/10.1038/nature22308) profiled 100+ compounds for *E. coli* accumulation by LC-MS and identified three predictive features. Compounds satisfying all three accumulated > 0.1 nmol / 10⁸ CFU:

1. **Primary amine** — at least one ionisable primary amine (or rarely a strong basic group). Positively-charged at physiological pH.
2. **Low globularity (≤ 0.25)** — flat, anisotropic shape. Requires a 3D conformer; **this audit does not compute globularity**, but flat aromatic / heteroaromatic cores are a 2D proxy.
3. **Rigidity (RotBonds ≤ 5)** — fewer flexible bonds. Easily checked from the SMILES.

Applying eNTRy to a novel chemotype turned a gram-positive deoxynybomycin into a broad-spectrum gram-negative active in the original paper. The rules are not perfect — *P. aeruginosa* and *A. baumannii* have additional barriers, and active transport routes can bypass eNTRy — but they are the best-validated framework for early-stage gram-negative hit triage.

**Efflux pumps** to be aware of:
- **AcrAB-TolC** in Enterobacteriaceae — broad-substrate; effluxes most antibiotics. Major resistance contributor.
- **MexAB-OprM**, **MexCD-OprJ**, **MexXY-OprM** in *P. aeruginosa* — overlapping substrate scopes; can be upregulated in clinical isolates.
- **AdeABC** in *A. baumannii*.
- **P-gp** (host) is not the relevant efflux here, but its substrates often overlap.

## Safety liabilities specific to this bucket

- **Nephrotoxicity** — aminoglycosides (gentamicin, amikacin) and polymyxins (colistin) are nephrotoxic; cumulative dose limits clinical use. Watch for similar charge-density patterns in hits.
- **Ototoxicity** — aminoglycoside-specific; not predictable from physchem alone, but flag aminoglycoside-class analogs.
- **QT prolongation** — fluoroquinolones (moxifloxacin > levofloxacin > ciprofloxacin) and azoles. Apply hERG threshold.
- **C. difficile risk** — broad-spectrum gram-negative agents perturb gut microbiota; not predictable from a CSV, but a known class-level liability.
- **β-lactam allergy** — patient-level concern, not predictable from compound structure.
- **Tendinopathy** — fluoroquinolone class effect, not chemistry-predictable.

## Mechanism-of-action shortcuts

| Target | Drug class / archetype | Recognisable feature |
|---|---|---|
| PBPs (cell wall) | β-lactams (penicillins, cephalosporins, carbapenems, monobactams) | β-lactam ring + side chain |
| DNA gyrase / topo IV | Fluoroquinolones | Quinolone-3-carboxylic acid + C-6 fluorine |
| 30S ribosome | Aminoglycosides | Polycationic aminosugar scaffold |
| 30S ribosome (different site) | Tetracyclines | Naphthacene-diol core |
| 23S / 50S ribosome | Macrolides (limited gram-neg) | Macrolactone with desosamine |
| LPS / outer membrane | Polymyxins | Cyclic lipopeptide, polycationic |
| Folate (DHPS) | Sulfonamides | p-amino-benzene sulfonamide |
| Folate (DHFR) | Diaminopyrimidines (trimethoprim) | 2,4-diaminopyrimidine |
| Reductive activation | Nitrofurans (nitrofurantoin) | Nitrofuran + side chain |

## How to interpret Ersilia model outputs in this context

- **`e_coli_*` / `ecoli_*` / `gram_negative_*` columns** → primary `efficacy` for this bucket. *E. coli* is the standard but easiest gram-negative; cross-reference any *Pseudomonas*-specific or *Acinetobacter*-specific column when available.
- **`pseudomonas_*` / `paeruginosa_*` columns** — escalate weight: *P. aeruginosa* activity is harder to find and clinically more valuable.
- **`klebsiella_*` columns** — similar reasoning to *Pseudomonas*.
- **`permeability_*` / `pampa_*` / `caco2_*`** — these predict host PK, not bacterial penetration. Do not treat host permeability as a gram-negative penetration proxy.
- **`pgp_*` columns** — host efflux; not the same as AcrAB-TolC, but the structural features that flag P-gp substrates often correlate with bacterial efflux substrates.
- **`hERG` columns** — apply standard threshold; relevant for fluoroquinolone-like hits.

## References

| # | Author, Year | Title | Source | Link |
|---|---|---|---|---|
| 1 | Richter et al., 2017 | Predictive compound accumulation rules yield a broad-spectrum antibiotic | Nature | https://doi.org/10.1038/nature22308 |
| 2 | Brown et al., 2014 | Trends and exceptions of physical properties on antibacterial activity for gram-positive and gram-negative pathogens | J Med Chem | https://doi.org/10.1021/jm501552x |
| 3 | Silver, 2011 | Challenges of antibacterial discovery | Clin Microbiol Rev | https://doi.org/10.1128/CMR.00030-10 |
| 4 | Tommasi et al., 2015 | ESKAPEing the labyrinth of antibacterial discovery | Nat Rev Drug Discov | https://doi.org/10.1038/nrd4572 |
| 5 | Lewis, 2020 | The science of antibiotic discovery | Cell | https://doi.org/10.1016/j.cell.2020.02.056 |
| 6 | Zgurskaya et al., 2015 | Permeability barrier of gram-negative cell envelopes and approaches to bypass it | ACS Infect Dis | https://doi.org/10.1021/acsinfecdis.5b00097 |
| 7 | Boucher et al., 2009 | Bad bugs, no drugs: no ESKAPE! An update from the Infectious Diseases Society of America | Clin Infect Dis | https://doi.org/10.1086/595011 |
| 8 | WHO | WHO bacterial priority pathogens list | — | https://www.who.int/publications/i/item/9789240093461 |

_Last reviewed: 2026-05_
