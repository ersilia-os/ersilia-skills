# Antifungal Criteria

> Audit guidance for compounds targeting pathogenic fungi: *Candida* spp. (including *C. auris*), *Cryptococcus neoformans*, *Aspergillus fumigatus*, *Pneumocystis jirovecii*, dermatophytes, and endemic mycoses (*Histoplasma*, *Coccidioides*, *Blastomyces*). Cross-link: [shared anti-infective concepts](./shared-anti-infective-criteria.md).

## Quick rules (Claude reads these first)

- **Host-vs-pathogen selectivity is the dominant challenge.** Fungi are eukaryotes; many of their essential biology overlaps with human cells (ergosterol vs cholesterol, fungal CYP51 vs human CYPs). Therapeutic windows are tighter than for antibacterials.
- **Five validated MoA classes** — azoles (CYP51 / sterol synthesis), polyenes (ergosterol binding), echinocandins (β-1,3-glucan synthase), pyrimidine analogs (flucytosine), allylamines (squalene epoxidase). Recognising scaffold = recognising target.
- **Drug-drug interactions via CYP3A4** — azoles are CYP3A4 inhibitors; this is critical in transplant, HIV, and TB co-treatment. Flag any azole-like scaffold for DDI review.
- **Candida auris is the strategic priority.** Multi-drug-resistant, healthcare-associated, mortality 30–60%. Activity columns against *C. auris* specifically deserve top weighting.
- **MW window is bimodal**: small synthetic compounds (~250–500, azoles, allylamines, flucytosine) vs large natural-product-derived (amphotericin B ~924, echinocandins > 1000). Treat these as two strategic camps, not one continuum.
- **Oral bioavailability is highly valued** — voriconazole and posaconazole grew the market partly because oral azoles displaced IV amphotericin B for many indications. Flag candidates with poor predicted oral PK.
- **CNS penetration matters for cryptococcal meningitis.** Fluconazole crosses the BBB well; voriconazole does adequately; echinocandins do not. `bbb_*` columns are relevant for cryptococcal indications.

## Pathogen biology essentials

Pathogenic fungi share core eukaryotic biology with humans — nuclei, organelles, microtubules, cytoplasmic translation. The exploitable differences are narrow:

- **Ergosterol** replaces cholesterol in fungal membranes — the basis for polyene (direct binding) and azole (biosynthesis inhibition) MoAs.
- **β-1,3-glucan + chitin** cell wall — entirely fungal; echinocandins inhibit β-1,3-glucan synthase. Mammalian cells have no cell wall.
- **GPI-anchor biosynthesis** — fungal Gwt1 has no mammalian equivalent; fosmanogepix exploits this ([Hoenigl 2021](https://doi.org/10.1007/s40265-021-01611-0)).
- **Pyrimidine salvage** — fungi take up 5-fluorocytosine via cytosine permease (absent in mammals) and deaminate it to 5-FU intracellularly.

Pathogen niches differ dramatically: superficial skin/mucous (dermatophytes, *Candida albicans* mucocutaneous), deep tissue (*Cryptococcus* in CNS, *Aspergillus* in lungs), bloodstream (invasive candidiasis), opportunistic on immunocompromised (*Pneumocystis*). The host context shapes which property profile wins.

## Property windows (empirically derived)

### Property windows for `antifungal` (n = 12 compounds)

| Property | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| MW | 129.1 | 338.6 | 544.1 | 955.9 | 1096.1 |
| LogP | -2.44 | 0.42 | 2.61 | 3.57 | 5.58 |
| TPSA | 3.2 | 71.6 | 87.7 | 310.4 | 397.5 |
| HBD | 0 | 0 | 1 | 12 | 14 |
| HBA | 1 | 5 | 8 | 16 | 19 |
| RotBonds | 0 | 4 | 5 | 10 | 20 |
| AromaticRings | 0 | 1 | 2 | 3 | 5 |
| Fsp3 | 0.00 | 0.31 | 0.39 | 0.52 | 0.74 |
| HeavyAtoms | 9 | 24 | 38 | 67 | 77 |

**Outlier compounds** (any property outside the p5–p95 band):
- **Caspofungin / Micafungin** — MW 967 / 1096, HBD 14, RotBonds 20. Echinocandins; semi-synthetic cyclic lipohexapeptides; IV-only.
- **Flucytosine** — MW=129, HeavyAtoms=9. Smallest in the set; fluorinated cytosine analog; oral but used mostly in combination.
- **Terbinafine** — TPSA=3.2, HBA=1. Highly lipophilic allylamine; ideal for dermatophyte skin/nail accumulation.
- **Itraconazole** — LogP=5.58, AromaticRings=5. Lipophilic triazole; bioavailability variability is its main clinical pain point.

The bimodal distribution is clear: small lipophilic synthetics cluster around MW 300–400 / LogP 2–4, while the natural-product class clusters near MW 900–1100 / LogP +/-2.

**Target window for novel small-molecule leads: MW 280–450, LogP 1–4, TPSA 40–100, HBD ≤ 3.** Echinocandin-style large-scaffold leads need a different optimisation playbook (semi-synthetic modification of a natural-product core).

## Structural traits that favour activity

- **Triazole / imidazole** binding fungal CYP51 (sterol 14α-demethylase) via Fe-coordination of N3/N4. Fluconazole, voriconazole, posaconazole, itraconazole, isavuconazole, the newer tetrazoles (oteseconazole) all share the azole-Fe pharmacophore ([Lass-Flörl 2011](https://doi.org/10.2165/11585870-000000000-00000)).
- **Heptaene macrolactone + amino sugar** (amphotericin B, nystatin, natamycin) — direct ergosterol binding → membrane pore. Most reliable broad-spectrum fungicidal MoA.
- **Cyclic lipohexapeptide** (caspofungin, micafungin, anidulafungin, rezafungin) — β-1,3-glucan synthase (FKS1/FKS2) inhibition. Fungicidal against *Candida*, fungistatic against *Aspergillus*. Long-half-life rezafungin enables once-weekly dosing ([Hoenigl 2021](https://doi.org/10.1007/s40265-021-01611-0)).
- **Fluorinated pyrimidine** (flucytosine, 5-FC) — Cytosine permease uptake + cytosine deaminase conversion to 5-fluorouracil → fungal-selective. Combination use only (rapid resistance as monotherapy).
- **Allylamine / arylallylamine** (terbinafine, naftifine) — squalene epoxidase inhibition → ergosterol shortage + squalene accumulation. Highly lipophilic; accumulates in skin / nail.
- **Glycerol-tyrosine / Gwt1-inhibitor** (fosmanogepix / manogepix) — GPI anchor synthesis; novel MoA in late development.
- **Triterpenoid glucan synthase inhibitor** (ibrexafungerp) — oral echinocandin-class alternative; same target as caspofungin but different scaffold.
- **Pyrimidine pyrimidinone / orotomide** (olorofim) — fungal dihydroorotate dehydrogenase inhibitor; pyrimidine salvage; novel; especially for *Aspergillus* / *Scedosporium*.

## Structural traits that lower activity or signal liabilities

- **Pure mammalian CYP inhibitors** without fungal CYP51 selectivity — risk severe DDIs and adrenal toxicity (CYP11B inhibition).
- **Compounds resembling clinical azoles** in the *C. auris* context — face pre-existing azole resistance (often via Erg11 mutations, efflux pump upregulation).
- **Pure tubulin-binding scaffolds without fungal selectivity** — griseofulvin is the historical example; works for dermatophytes only.
- **Highly polar / charged compounds** rarely cross the fungal cell wall + membrane efficiently.
- **Cytochrome P450 inducers** with overlap into mammalian P450s — long-treatment patients accumulate metabolic perturbation.

## Permeability / accumulation peculiarities

- **Fungal cell wall (β-glucan + chitin + mannoproteins)** — porous to small molecules but obstructive to large peptides / oligomers. Echinocandins exploit the wall as the target, not a barrier.
- **Drug efflux pumps**: Cdr1 / Cdr2 (ABC transporters) and Mdr1 (MFS transporter) in *Candida* — overexpression is a major azole-resistance mechanism.
- **Lipid raft localisation**: ergosterol-rich membrane microdomains affect membrane-targeting drug accumulation.
- **Biofilm penetration**: *Candida* biofilms on indwelling devices dramatically reduce echinocandin / azole efficacy; this is a chronic indication concern.

## Safety liabilities specific to this bucket

- **Hepatotoxicity** — all clinical azoles carry DILI risk; voriconazole and ketoconazole are the highest-risk. A new azole-like scaffold should be flagged for hepatotox columns.
- **QT prolongation** — most azoles (fluconazole, voriconazole, posaconazole) prolong QT; isavuconazole notably *shortens* it.
- **Nephrotoxicity** — amphotericin B (conventional) is severely nephrotoxic; liposomal formulations dramatically improved this. Flucytosine itself accumulates with renal impairment → bone marrow toxicity.
- **Visual disturbances** — voriconazole class effect (~30% of patients); not fully understood mechanistically.
- **CYP3A4 inhibition / DDIs** — azoles are potent CYP3A4 inhibitors; transplant immunosuppressants (tacrolimus, sirolimus), HIV protease inhibitors, TB rifampicin, statins are all at risk.
- **Adrenal insufficiency** — ketoconazole at high dose inhibits CYP11B1; class watch-out for closely related azoles.
- **Photosensitivity / skin cancer** — long-term voriconazole; observed but mechanism still investigated.
- **Hyperphosphatemia / pseudoaldosteronism** — itraconazole solution; class watch-out.

## Mechanism-of-action shortcuts

| Target | Drug class / archetype | Recognisable feature |
|---|---|---|
| Sterol 14α-demethylase (CYP51) | Azoles (fluconazole, voriconazole, posaconazole, itraconazole, isavuconazole) | Triazole or imidazole + aryl + linker |
| Ergosterol (direct membrane binding) | Polyenes (amphotericin B, nystatin) | Heptaene + macrolactone + mycosamine |
| β-1,3-glucan synthase (FKS1) | Echinocandins (caspofungin, micafungin, anidulafungin, rezafungin) | Cyclic lipohexapeptide |
| β-1,3-glucan synthase (different scaffold) | Triterpenoids (ibrexafungerp) | Oral; non-peptidic glucan synthase inhibitor |
| Pyrimidine salvage → 5-FU | Flucytosine | 5-fluoro-cytosine |
| Squalene epoxidase | Allylamines (terbinafine, naftifine) | Aryl-allylamine |
| Dihydroorotate dehydrogenase | Orotomides (olorofim) | Pyrimidinone scaffold |
| GPI-anchor biosynthesis (Gwt1) | Fosmanogepix (manogepix prodrug) | Pyridine-based, novel |
| Microtubule (dermatophytes) | Griseofulvin | Spiro-benzofuran |
| Sec14 / phosphatidylinositol transfer | Turbinmicin (preclinical) | Bicyclic natural product |

## How to interpret Ersilia model outputs in this context

- **`candida_*` / `c_albicans_*` / `c_auris_*` columns** → primary `efficacy` for this bucket. *C. auris* activity is the strategic priority.
- **`aspergillus_*` / `a_fumigatus_*` columns** → primary `efficacy` for invasive aspergillosis; treat as distinct from *Candida* — echinocandins are fungistatic vs *Aspergillus*, fungicidal vs *Candida*.
- **`cryptococcus_*` columns** → primary `efficacy` for cryptococcal meningitis; combine with `bbb_*` evaluation.
- **`bbb_*` columns** — escalate weight when context names cryptococcal disease.
- **`cyp3a4_*` / DDI columns** — escalate; azole DDIs are the dominant clinical pain point.
- **`hERG` columns** — apply standard threshold; QT history across the azole class warrants attention.
- **`dili` / hepatotox columns** — escalate; azole-class DILI is well-documented.
- **`renal_tox` / nephrotox columns** — escalate; AmB and flucytosine baseline.
- **`bioavailability_*` / `hia_*`** — escalate; oral antifungals have a strong market preference.

## References

| # | Author, Year | Title | Source | Link |
|---|---|---|---|---|
| 1 | Roemer & Krysan, 2014 | Antifungal drug development: challenges, unmet clinical needs, and new approaches | Cold Spring Harb Perspect Med | https://doi.org/10.1101/cshperspect.a019703 |
| 2 | Perfect, 2017 | The antifungal pipeline: a reality check | Nat Rev Drug Discov | https://doi.org/10.1038/nrd.2017.46 |
| 3 | Hoenigl et al., 2021 | The antifungal pipeline: fosmanogepix, ibrexafungerp, olorofim, opelconazole, and rezafungin | Drugs | https://doi.org/10.1007/s40265-021-01611-0 |
| 4 | Lass-Flörl, 2011 | Triazole antifungal agents in invasive fungal infections: a comparative review | Drugs | https://doi.org/10.2165/11585870-000000000-00000 |
| 5 | Berkow & Lockhart, 2017 | Fluconazole resistance in *Candida* species: a current perspective | Infect Drug Resist | https://doi.org/10.2147/IDR.S118892 |
| 6 | Denning, 2003 | Echinocandin antifungal drugs | Lancet | https://doi.org/10.1016/S0140-6736(03)14472-8 |
| 7 | Pappas et al., 2018 | Invasive candidiasis | Nat Rev Dis Primers | https://doi.org/10.1038/nrdp.2018.26 |
| 8 | CDC | Candida auris (clinical information, treatment, AR Threats) | — | https://www.cdc.gov/fungal/candida-auris/ |

_Last reviewed: 2026-05_
