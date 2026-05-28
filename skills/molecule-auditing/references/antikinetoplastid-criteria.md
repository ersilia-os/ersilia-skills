# Antikinetoplastid Criteria

> Audit guidance for compounds targeting trypanosomatid parasites: *Trypanosoma brucei* (Human African Trypanosomiasis, HAT / "sleeping sickness"), *T. cruzi* (Chagas disease), and *Leishmania* spp. (visceral / cutaneous / mucocutaneous leishmaniasis). The three diseases share enough biology to group, but each has distinct host context and TPPs. Cross-link: [shared anti-infective concepts](./shared-anti-infective-criteria.md).

## Quick rules (Claude reads these first)

- **Identify the disease before judging the property profile.** HAT (T1 oral, T2 CNS-penetrant), Chagas (chronic phase needs sustained tissue exposure), visceral leishmaniasis (intramacrophage in liver/spleen/bone marrow) — each has a distinct PK target.
- **Nitroaromatic + reductive activation is a clinically validated MoA.** Nifurtimox, benznidazole, fexinidazole, delamanid-like nitroimidazoles. AMES positives are *expected*; flag but contextualise via [shared rules](./shared-anti-infective-criteria.md).
- **CNS penetration is non-negotiable for late-stage HAT (T2).** Fexinidazole replaced melarsoprol partly because it crosses the BBB; flag any candidate's `bbb_*` column accordingly.
- **Intramacrophage activity matters for *L. donovani* and *T. cruzi*.** Cell-free trypomastigote/promastigote activity is a starting point; intracellular amastigote activity is the predictive assay.
- **Chronic Chagas needs months of dosing** → strict tolerability + low DDI burden. Benznidazole's known hepatotox and skin reactions set the bar a new entity must clear.
- **DNDi Target Product Profiles** ([DNDi TPPs](https://dndi.org/research-development/target-product-profile/)) codify the property windows per indication. Cross-reference when `--context` names HAT, Chagas, or leishmaniasis.
- **Avoid amphotericin-class polyenes for novel-lead positioning.** Liposomal amphotericin B is the leishmaniasis gold standard but is IV-only, expensive, and chemically saturated as a class.

## Pathogen biology essentials

Trypanosomatids are protozoan eukaryotes of the order Kinetoplastida, characterised by:

- **The kinetoplast**: a unique, catenated mitochondrial DNA network. Key drug target for some classes (pentamidine, anti-mitochondrial agents).
- **Glycosomes**: peroxisome-like organelles housing the bulk of glycolysis. Distinct trypanosomatid biology — distinct druggable targets (e.g. glycosomal kinases).
- **Polyamine / trypanothione redox metabolism**: replaces the mammalian glutathione system; ornithine decarboxylase (eflornithine target) is essential.
- **Surface coat antigenic variation** (*T. brucei*) — explains why vaccines have failed and chemotherapy dominates.

Life-cycle and host-tissue tropism vary by species:

- ***T. brucei***: extracellular in blood + lymph (stage 1) → CNS (stage 2). Insect vector: tsetse fly. HAT.
- ***T. cruzi***: intracellular amastigotes in cardiomyocytes, smooth muscle, neurons → chronic Chagas cardiomyopathy / megaviscera. Insect vector: triatomine bug. The Americas.
- ***Leishmania* spp.**: intracellular amastigotes in macrophages → cutaneous (CL), mucocutaneous (MCL), or visceral (VL / kala-azar). Insect vector: sandfly. Indian subcontinent, East Africa, South America, Mediterranean.

For an audit, the most consequential biology is **intracellular amastigote residence** (Chagas + VL): a hit must cross the host cell membrane, the parasitophorous vacuole, and the parasite plasma membrane. Predicted host permeability matters, but intracellular accumulation is the real test.

## Property windows (empirically derived)

### Property windows for `antikinetoplastid` (n = 12 compounds)

| Property | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| MW | 182.2 | 285.1 | 369.4 | 580.2 | 1192.2 |
| LogP | -6.00 | 0.91 | 2.89 | 3.55 | 5.80 |
| TPSA | 37.4 | 84.6 | 93.8 | 164.0 | 454.6 |
| HBD | 0 | 0 | 2 | 5 | 12 |
| HBA | 3 | 4 | 6 | 10 | 16 |
| RotBonds | 3 | 5 | 7 | 9 | 20 |
| AromaticRings | 0 | 0 | 2 | 2 | 7 |
| Fsp3 | 0.07 | 0.23 | 0.35 | 0.62 | 1.00 |
| HeavyAtoms | 12 | 20 | 24 | 32 | 78 |

**Outlier compounds** (any property outside the p5–p95 band):
- **Suramin** — MW=1192, AromaticRings=7, TPSA=455. Symmetric polysulfonated urea; only effective for early-stage HAT; IV, very old.
- **Sodium stibogluconate** — LogP=−6. Pentavalent antimony; complex carbohydrate-Sb compound; the SMILES is a coordination approximation. IV/IM use only.
- **Miltefosine** — RotBonds=20, Fsp3=1.0. Alkylphosphocholine; long aliphatic chain explains the outliers.
- **Amphotericin B** — HBD=12. Polyene macrolactone; the gold standard for VL but a class apart chemically.
- **Eflornithine** — MW=182. Small α-difluoromethylornithine; suicide ODC inhibitor; T2 HAT.
- **Sitamaquine** — TPSA=37.4. 8-aminoquinoline VL candidate; abandoned for nephrotox.

**Target window for novel leads: MW 280–500, LogP 1–4, TPSA 60–120, HBD ≤ 4.** Aim for oral bioavailability + tissue distribution; CNS penetration is a bonus for HAT, mandatory for late-stage.

## Structural traits that favour activity

- **Nitroimidazole / nitrofuran + suitable side chain**: bioactivated by parasite type-I nitroreductases (NTR) that mammals lack. Fexinidazole, benznidazole, nifurtimox, and the delamanid-class compounds all exploit this differential ([Patterson & Wyllie 2014](https://doi.org/10.1016/j.pt.2014.04.001)).
- **Aminoalkyl-alkylphosphocholine / lipid-like polar-head + alkyl-tail** (miltefosine) — disrupts parasite phospholipid metabolism / membranes; only oral drug currently approved for VL.
- **Aromatic diamidines** (pentamidine, related): bind AT-rich DNA + kinetoplast; activity against early-stage HAT and *L. donovani*. Tolerability limits broader use.
- **Difluoromethyl-amine / suicide-substrate warheads** (eflornithine) — irreversible ODC inhibition; T2 HAT.
- **Triazole / sterol-pathway inhibitors** (posaconazole-like) — repurposed antifungal scaffolds; some activity in Chagas (mixed clinical results).
- **Proteasome inhibitor scaffolds** (GNF6702, LXE408) — parasite proteasome differs from human; promising new MoA across kinetoplastids ([Khare 2016](https://doi.org/10.1038/nature19339)).

## Structural traits that lower activity or signal liabilities

- **Pentavalent antimony scaffolds** (sodium stibogluconate, meglumine antimoniate) — clinical standard but cardiotoxic, nephrotoxic, and old. Not a useful structural target for new leads.
- **Arsenic-containing scaffolds** (melarsoprol) — toxic; "I beat death" survival rate cliché. Avoid.
- **Pure 8-aminoquinolines** — face G6PD-deficiency hemolysis like antimalarial primaquine analogs.
- **Compounds with high host CYP3A4 inhibition** — Chagas patients often co-medicate for cardiac comorbidities; DDIs are common failure modes.
- **PgP substrates** — efflux from macrophages limits intracellular amastigote exposure.

## Permeability / accumulation peculiarities

The intracellular amastigote stages of *T. cruzi* and *Leishmania* sit inside acidic parasitophorous vacuoles within macrophages. Reaching them requires:

1. Crossing the macrophage plasma membrane (or being phagocytosed if formulated for it — liposomal amphotericin B).
2. Crossing the parasitophorous vacuole membrane.
3. Crossing the parasite plasma membrane.

Lipophilic compounds tend to partition into membranes rather than cross them; very polar compounds may struggle to enter the macrophage at all. The empirical sweet spot is moderately lipophilic with a weakly basic ionisable group — basic compounds accumulate in the acidic parasitophorous vacuole by ion trapping.

For HAT T2, **BBB penetration is required**. Fexinidazole crosses the BBB; melarsoprol does aggressively (with cost — reactive encephalopathy in ~5%). Pre-T2 oral candidates have failed historically because the parasite escapes into the CNS before therapy completes.

## Safety liabilities specific to this bucket

- **Nifurtimox neurotoxicity** — peripheral neuropathy, restlessness, psychosis. Class-level reductive-activation watch-out.
- **Benznidazole hepatotoxicity + skin reactions** — Stevens-Johnson rare but reported. Sets the bar for chronic Chagas tolerability.
- **Melarsoprol encephalopathy** — ~5% reactive arsenical encephalopathy, ~50% fatal when it occurs. Historical; replaced by fexinidazole.
- **Antimony cardiotoxicity** — meglumine antimoniate / sodium stibogluconate; QT prolongation, arrhythmias.
- **Amphotericin nephrotoxicity** — non-liposomal form; liposomal formulations dramatically improved.
- **Miltefosine teratogenicity** — contraindicated in pregnancy; long half-life means contraception needed for months post-treatment.
- **Pentamidine pancreatic islet toxicity** — hypoglycaemia → late hyperglycaemia; QT prolongation.
- **CNS reactive intermediates** — any compound generating CNS-active reactive metabolites flags for fexinidazole-style safety review.

## Mechanism-of-action shortcuts

| Target | Drug class / archetype | Recognisable feature |
|---|---|---|
| Type-I nitroreductase activation → DNA damage / radicals | Nitroimidazoles (benznidazole, fexinidazole) | 5-nitroimidazole + side chain |
| Type-I nitroreductase (different scaffold) | Nitrofurans (nifurtimox) | 5-nitrofuran + side chain |
| Phospholipid metabolism / membrane | Alkylphosphocholines (miltefosine) | Lipid tail + phosphocholine head |
| Ornithine decarboxylase (ODC) | α-DFMO (eflornithine) | α-difluoromethyl + α-amino acid |
| Ergosterol biosynthesis | Amphotericin B (polyene) | Macrolide + amino sugar |
| Kinetoplast DNA / AT-rich groove | Diamidines (pentamidine) | Aromatic bis-amidine |
| ODC / polyamine + arsenical | Melarsoprol | Melamine + arsenoxide |
| Trypanothione synthesis | (preclinical) trypanothione reductase inhibitors | Disulfide-engaging warheads |
| 26S parasite proteasome | GNF6702, LXE408 | Heterocyclic peptidomimetics |
| Sterol 14α-demethylase (CYP51) | Azoles (posaconazole — repurposed) | Triazole + biphenyl-piperazine |

## How to interpret Ersilia model outputs in this context

- **`tcruzi_*` / `t_cruzi_*` columns** → primary `efficacy` for Chagas. Prefer intracellular amastigote columns over trypomastigote columns when both present.
- **`tbrucei_*` columns** → primary `efficacy` for HAT.
- **`leishmania_*` / `l_donovani_*` / `l_infantum_*` columns** → primary `efficacy` for VL; *L. amazonensis* / *L. major* for cutaneous.
- **`bbb_*` columns** — escalate for HAT (T2 requires CNS penetration); irrelevant for Chagas / VL.
- **`pgp_*` / efflux columns** — escalate for intramacrophage Chagas / VL hits.
- **`ames_*` / mutagenicity columns** — flag but contextualise; nitroaromatic clinical drugs are AMES positives by mechanism.
- **`hERG` / cardiac columns** — apply standard threshold; QT history in antimony / pentamidine sets a precedent.
- **`teratogenicity` columns** — escalate; miltefosine's long half-life makes pregnancy contraindication a class watch-out.
- **`dili` / hepatotox columns** — escalate; benznidazole's known hepatotox is the implicit baseline.

## References

| # | Author, Year | Title | Source | Link |
|---|---|---|---|---|
| 1 | Field et al., 2017 | Anti-trypanosomatid drug discovery: an ongoing challenge and a continuing need | Nat Rev Microbiol | https://doi.org/10.1038/nrmicro.2016.193 |
| 2 | Khare et al., 2016 | Proteasome inhibition for treatment of leishmaniasis, Chagas disease and sleeping sickness | Nature | https://doi.org/10.1038/nature19339 |
| 3 | Patterson & Wyllie, 2014 | Nitro drugs for the treatment of trypanosomatid diseases: past, present, and future prospects | Trends Parasitol | https://doi.org/10.1016/j.pt.2014.04.001 |
| 4 | Deeks, 2019 | Fexinidazole: first global approval | Drugs | https://doi.org/10.1007/s40265-019-1051-6 |
| 5 | Burza et al., 2018 | Leishmaniasis | Lancet | https://doi.org/10.1016/S0140-6736(18)31204-2 |
| 6 | Pérez-Molina & Molina, 2018 | Chagas disease | Lancet | https://doi.org/10.1016/S0140-6736(17)31612-4 |
| 7 | Büscher et al., 2017 | Human African trypanosomiasis | Lancet | https://doi.org/10.1016/S0140-6736(17)31510-6 |
| 8 | Wyatt et al., 2011 | Target validation: linking target and chemical properties to desired product profile | Curr Top Med Chem | https://doi.org/10.2174/156802611795429185 |
| 9 | DNDi | Target product profiles (HAT, Chagas, leishmaniasis, mycetoma) | — | https://dndi.org/research-development/target-product-profile/ |
| 10 | Wyllie et al., 2018 | Preclinical candidate for the treatment of visceral leishmaniasis that acts through proteasome inhibition | PNAS | https://doi.org/10.1073/pnas.1815780116 |

_Last reviewed: 2026-05_
