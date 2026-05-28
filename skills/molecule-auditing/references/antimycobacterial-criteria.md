# Antimycobacterial Criteria

> Audit guidance for compounds targeting *Mycobacterium tuberculosis*, NTM (*M. abscessus*, *M. avium* complex), and *M. leprae*. Cross-link: [shared anti-infective concepts](./shared-anti-infective-criteria.md).

## Quick rules (Claude reads these first)

- **Favour lipophilic over polar.** TB hits cluster at higher LogP than most antibacterials — the mycolic acid layer rewards membrane-permeable compounds. Penalise extreme polarity unless the compound targets a periplasmic enzyme.
- **MW 300–550 is the sweet spot** for new chemical entities; clinically-used drugs span much wider (isoniazid MW 137 to rifampicin MW 823) because parenteral / hepatic-clearance routes tolerate extremes that screening hits cannot.
- **Hepatotox is a hard gate.** TB treatment runs 4–6 months; any DILI / ALT-elevation signal in screening (e.g. high `dili` probability) is a major liability. Weight hepatotox more heavily than for short-course indications.
- **Intracellular activity matters.** Hits with strong cell-free MIC but weak intracellular (macrophage) activity are routine. If the Ersilia CSV has both a biochemical and a macrophage column, weight the macrophage column more.
- **Cleared TB targets attract**: DprE1, MmpL3, InhA, KasA, QcrB, ATP synthase — recognising scaffolds known to hit these is a fast first-pass classification.
- **Nitroimidazole AMES positives are clinical-grade**: delamanid and pretomanid are AMES+ and approved. Apply the [shared rule](./shared-anti-infective-criteria.md): note but contextualise.
- **Avoid pure mammalian targets**: kinase-rich pharmacophores frequently produce mammalian off-targets without TB activity; phenotypic hit confirmation against axenic *M. tuberculosis* is essential.

## Pathogen biology essentials

*Mycobacterium tuberculosis* has a unique cell envelope: a peptidoglycan layer, an arabinogalactan polymer, and an outer **mycomembrane** built of long-chain (C60–C90) mycolic acids and free lipids. The mycomembrane is a fluidity-low, hydrophobic barrier that excludes polar compounds and slows diffusion of even lipophilic ones. Hits favoured by this envelope share two traits: enough lipophilicity to partition into the lipid bilayer and enough rigidity to traverse it without rotating into unproductive conformations.

TB is also slow-growing (~24 h doubling time), intracellular (replicates inside macrophages, including caseous granulomas), and metabolically heterogeneous within a single host. The clinical implication: a compound must remain bioavailable for weeks, penetrate caseum ([Sarathy 2018](https://doi.org/10.1128/CMR.00060-17)), and act on bacteria across replicating, non-replicating, and persister states. Standard MIC against log-phase axenic culture is a starting point, not a clinical predictor.

## Property windows (empirically derived)

### Property windows for `antimycobacterial` (n = 12 compounds)

| Property | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| MW | 102.1 | 159.0 | 380.9 | 468.7 | 781.0 |
| LogP | -7.17 | -0.34 | 1.47 | 3.97 | 7.01 |
| TPSA | 29.3 | 59.7 | 68.4 | 88.4 | 266.0 |
| HBD | 0 | 1 | 1 | 2 | 11 |
| HBA | 2 | 3 | 4 | 7 | 13 |
| RotBonds | 0 | 2 | 4 | 7 | 9 |
| AromaticRings | 0 | 1 | 1 | 2 | 5 |
| Fsp3 | 0.00 | 0.18 | 0.39 | 0.60 | 1.00 |
| HeavyAtoms | 7 | 11 | 27 | 32 | 56 |

**Outlier compounds** (any property outside the p5–p95 band):
- **Rifampicin** — MW=781, HeavyAtoms=56. Ansamycin macrocycle; large but clinically essential — RNA polymerase target rewards bulk.
- **Streptomycin** — LogP=−7.17, TPSA=266, HBD=11. Aminoglycoside; IV-only; not a model for novel TB leads.
- **Ethambutol** — RotBonds=9, Fsp3=1.0. Flexible aliphatic diamine; arabinosyl transferase inhibitor — small and polar; works because the target is in the cell wall periplasm.
- **Bedaquiline** — LogP=7.01, AromaticRings=5. The lipophilicity that drives ATP synthase activity also drives phospholipidosis and a QT signal.
- **Delamanid** — HBD=0. Tight nitroimidazo-oxazole; HBD count alone is misleading for an activated pro-drug.
- **Cycloserine** — MW=102, HeavyAtoms=7. Smallest compound in the set; D-alanine mimetic — uses an active transport route.

Hit triage should aim for the **p25–p75 window (MW 159–469, LogP −0.3 to 3.97)** with strong tolerance for the rifampicin-style "large macrocycle / unusual scaffold" outlier when it engages a validated target.

## Structural traits that favour activity

- **Lipophilic aromatic cores with one basic / ionisable centre**: bedaquiline, the QcrB inhibitors (Q203, telacebec), the imidazopyridines all share this. The basic amine traps the molecule via lysosomal accumulation in macrophages, which concentrates exposure near intracellular bacteria ([Andries 2005](https://doi.org/10.1126/science.1106753), [Pethe 2013](https://doi.org/10.1038/nm.3262)).
- **Nitroimidazo[2,1-b]oxazine / nitroimidazo[2,1-b]oxazole scaffolds** (pretomanid, delamanid): activated by Ddn (deazaflavin-dependent nitroreductase) and selectively kill *M. tuberculosis* via NO release. Recognising this scaffold = recognising a validated, advanced TB candidate.
- **Benzothiazinones / DprE1 inhibitors** (BTZ-043, macozinone): nitro-substituted benzothiazinones suicide-inhibit DprE1 ([Makarov 2009](https://doi.org/10.1126/science.1171583)). One of the most validated novel TB target classes.
- **Diarylquinolines, diarylpyridines** — ATP synthase / QcrB inhibitors with the lipophilic-aromatic-basic profile.
- **Adamantane / lipophilic cage scaffolds with diamine tails** (SQ109): MmpL3 inhibitors blocking mycolic acid transport ([Tahlan 2012](https://doi.org/10.1128/AAC.05708-11)).

## Structural traits that lower activity or signal liabilities

- **Highly polar compounds (TPSA > 140, LogP < 0)** without an active-transport hook rarely cross the mycomembrane. Hits in this region are often artefacts or work via non-bacterial mechanisms.
- **Multiple ionisable centres or zwitterions** typically have poor accumulation despite acceptable predicted permeability.
- **Quinolone-like cores with C-7 piperazine** (ciprofloxacin family) show only modest activity against *M. tuberculosis* compared with later FQs (moxifloxacin, levofloxacin); plain ciprofloxacin is not used in TB regimens.
- **Pure β-lactams** without a β-lactamase inhibitor — *M. tuberculosis* expresses BlaC; meropenem + clavulanate works because of co-administration, not because β-lactams alone are effective.
- **High-fluorine / heavy-halogen scaffolds without a clear TB pharmacophore**: often signal a kinase or GPCR origin with no mycobacterial relevance.

## Permeability / accumulation peculiarities

The mycomembrane is the dominant barrier. There is no published equivalent of the gram-negative "eNTRy rules" for TB, but [Lakshminarayana 2015](https://doi.org/10.1093/jac/dku457) profiled 40+ clinical and preclinical anti-TB agents and noted:

- **Median MW ≈ 350–450** for whole-cell-active leads; clinical drugs trend higher due to development-stage MW creep.
- **LogP shifted up** (median ~3) relative to general drugs; the "TB-friendly" profile is more lipophilic than general drug-likeness suggests.
- **HBD ≤ 3** is a strong predictor of mycomembrane penetration.
- Compounds active against axenic culture but inactive in macrophages typically fail intracellular accumulation (lysosomal acidification, sequestration).

Efflux: MmpS5-MmpL5 and Rv1258c are documented TB efflux pumps. P-gp substrate prediction in the host is also relevant — TB drugs that engage host P-gp can be poorly retained in macrophages.

## Safety liabilities specific to this bucket

- **Hepatotoxicity** — isoniazid + rifampicin + pyrazinamide all carry DILI risk; a new TB candidate cannot exceed first-line drug hepatotox without strong efficacy compensation. Flag any compound with high `dili` probability.
- **QT prolongation** — bedaquiline and delamanid both carry a QT signal that gated their approval. Apply hERG flag threshold strictly.
- **Phospholipidosis** — lipophilic amines that accumulate in lysosomes (bedaquiline, clofazimine) cause phospholipid storage; long-treatment-amplified.
- **Optic neuritis** — ethambutol-class; not predictable from physchem, but a known watch-out for TB drug development.
- **Bone marrow suppression** — linezolid in TB use is dose-limited by haematological tox.
- **Nitro group AMES positives** — clinical-grade for nitroimidazoles; flag but contextualise per [shared rules](./shared-anti-infective-criteria.md).

## Mechanism-of-action shortcuts

| Target | Drug class / archetype | Recognisable feature |
|---|---|---|
| RNA polymerase β-subunit | Rifamycins (rifampicin, rifabutin) | Ansamycin macrocycle |
| InhA (enoyl-ACP reductase) | Isoniazid + KatG activation | Hydrazide warhead |
| ATP synthase F1 | Diarylquinolines (bedaquiline) | Lipophilic quinoline-naphthalene-amine triad |
| DprE1 (decaprenyl-phospho-ribose epimerase) | Benzothiazinones (BTZ-043) | Nitrobenzothiazinone |
| Cytochrome bc1 (QcrB) | Imidazopyridines (Q203/telacebec) | Imidazo[1,2-a]pyridine carboxamide |
| MmpL3 (mycolic acid transport) | Adamantane diamines (SQ109) | Lipophilic cage + diamine tail |
| Mycobacterial F420/Ddn → NO | Nitroimidazo-oxazines (pretomanid, delamanid) | Bicyclic nitroimidazole |
| 30S ribosomal subunit | Aminoglycosides (streptomycin, amikacin) | Aminoglycoside scaffold; IV use only |
| 50S ribosomal subunit | Oxazolidinones (linezolid, sutezolid) | Oxazolidinone with acetamidomethyl tail |

## How to interpret Ersilia model outputs in this context

- **`mtb_inhibition_*` or `tb_*` columns** → primary `efficacy` for this bucket. Treat as the dominant ranking signal.
- **`e_coli_inhibition_*` or general antibacterial columns** → only weakly predictive of TB activity; do *not* use as a proxy.
- **`bbb_*` columns** — not strongly relevant unless targeting CNS-TB / tuberculous meningitis; in those rare cases promote `beneficial_admet` weighting.
- **`pampa_*` / `caco2_*` permeability** — useful as oral bioavailability proxies but not as mycomembrane permeability proxies.
- **`dili` / `hepatotox` columns** — escalate to top-of-report safety concern given long-treatment context.
- **`herg` / cardiac columns** — escalate; bedaquiline/delamanid have set a precedent that QT signals must be addressed early.

## References

| # | Author, Year | Title | Source | Link |
|---|---|---|---|---|
| 1 | Koul et al., 2011 | The challenge of new drug discovery for tuberculosis | Nature | https://doi.org/10.1038/nature09657 |
| 2 | Lakshminarayana et al., 2015 | Comprehensive physicochemical, pharmacokinetic and activity profiling of anti-TB agents | J Antimicrob Chemother | https://doi.org/10.1093/jac/dku457 |
| 3 | Andries et al., 2005 | A diarylquinoline drug active on the ATP synthase of *Mycobacterium tuberculosis* | Science | https://doi.org/10.1126/science.1106753 |
| 4 | Pethe et al., 2013 | Discovery of Q203, a potent clinical candidate for the treatment of tuberculosis | Nat Med | https://doi.org/10.1038/nm.3262 |
| 5 | Makarov et al., 2009 | Benzothiazinones kill *Mycobacterium tuberculosis* by blocking arabinan synthesis | Science | https://doi.org/10.1126/science.1171583 |
| 6 | Tahlan et al., 2012 | SQ109 targets MmpL3, a membrane transporter of trehalose monomycolate involved in mycolic acid donation to the cell wall core of *Mycobacterium tuberculosis* | Antimicrob Agents Chemother | https://doi.org/10.1128/AAC.05708-11 |
| 7 | Sarathy et al., 2018 | Caseum: a niche for *Mycobacterium tuberculosis* drug-tolerant persisters | Clin Microbiol Rev | https://doi.org/10.1128/CMR.00060-17 |
| 8 | Mdluli et al., 2015 | The tuberculosis drug discovery and development pipeline and emerging drug targets | Cold Spring Harb Perspect Med | https://doi.org/10.1101/cshperspect.a021154 |
| 9 | Working Group for New TB Drugs | Public TB drug pipeline tracker | — | https://www.newtbdrugs.org/pipeline |
| 10 | Stop TB Partnership | Global TB drug development landscape | — | https://www.stoptb.org/our-work/research-development |

_Last reviewed: 2026-05_
