# Antimalarial Criteria

> Audit guidance for compounds targeting *Plasmodium* species — primarily *P. falciparum* and *P. vivax*, with attention to life-cycle stage. Cross-link: [shared anti-infective concepts](./shared-anti-infective-criteria.md).

## Quick rules (Claude reads these first)

- **Identify the life-cycle stage the hit targets** before judging the property profile. Liver-stage prophylaxis (TCP-3) needs different PK from blood-stage cure (TCP-1) or transmission-blocking (TCP-4).
- **Lipophilicity is well-tolerated** — antimalarials cluster around LogP 3–5, higher than general drugs. Polar compounds rarely accumulate in the parasite digestive vacuole.
- **MW 300–450 is typical** for blood-stage actives; clinical drugs reach 530 (lumefantrine). Lead-stage hits should aim lower (≤ 400) to leave optimisation headroom.
- **Single-dose oral cure is the gold standard.** Half-life and absorption matter more than for chronic indications; flag any candidate with predicted poor `bioavailability` or `hia` against this goal.
- **PfCRT / Kelch13 awareness.** A new chloroquine-like (4-aminoquinoline) or artemisinin-like (endoperoxide) chemotype will face pre-existing resistance markers; novel scaffolds against PfATP4, PI4K, or DHODH are scientifically preferred.
- **Embryotoxicity / teratogenicity** matters because malaria affects pregnant women — flag any compound with a teratogen signal, and note that primaquine and tafenoquine are contraindicated in G6PD deficiency.
- **MMV TCPs (Target Candidate Profiles)** codify the property windows for each indication ([Burrows 2017](https://doi.org/10.1186/s12936-017-1733-z)) — when a `--context` value names malaria or a parasite, cross-reference the TCPs in the report.

## Pathogen biology essentials

*Plasmodium* parasites are apicomplexan eukaryotes with a complex life cycle:

1. **Sporozoites** are injected by the mosquito and infect hepatocytes (liver stage).
2. **Hepatocyte schizogony** produces merozoites that emerge into blood. *P. vivax* and *P. ovale* leave dormant **hypnozoites** in the liver — the cause of relapsing malaria.
3. **Asexual blood stage** (rings → trophozoites → schizonts) drives clinical symptoms; the parasite digests host hemoglobin in an acidic digestive vacuole, generating **hemozoin** (Heme polymer).
4. **Gametocytes** are taken up by mosquitoes; transmission-blocking targets this stage.

Different drug classes hit different stages — chloroquine targets hemozoin formation (asexual blood), primaquine kills hypnozoites (liver), atovaquone hits mitochondrial cytochrome bc1 (multiple stages). A compound's life-cycle activity profile is as important as its potency.

The host context matters: malaria is endemic across the global South, including in children and pregnant women; oral, single-dose, heat-stable, cheap, and well-tolerated is the implicit product profile.

## Property windows (empirically derived)

### Property windows for `antimalarial` (n = 13 compounds)

| Property | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| MW | 248.7 | 284.4 | 335.9 | 366.8 | 531.0 |
| LogP | 2.19 | 2.60 | 3.78 | 4.81 | 9.12 |
| TPSA | 23.5 | 41.1 | 48.4 | 57.2 | 100.5 |
| HBD | 0 | 1 | 1 | 2 | 2 |
| HBA | 2 | 3 | 4 | 5 | 7 |
| RotBonds | 0 | 1 | 3 | 6 | 12 |
| AromaticRings | 0 | 0 | 2 | 2 | 3 |
| Fsp3 | 0.17 | 0.28 | 0.50 | 0.89 | 1.00 |
| HeavyAtoms | 17 | 20 | 23 | 26 | 35 |

**Outlier compounds** (any property outside the p5–p95 band):
- **Lumefantrine** — MW=531, LogP=9.12, RotBonds=12. Long-half-life ACT partner; bile-excreted, highly lipophilic. Not a model for novel leads.
- **Artesunate** — TPSA=100.5, HBA=7. Hemisuccinate prodrug of dihydroartemisinin; the polar tail is hydrolysed in vivo.
- **Pyrimethamine** — MW=249, Fsp3=0.17. Small antifolate; the low Fsp3 reflects the diaminopyrimidine + chlorophenyl architecture.

Target window for new leads: **MW 280–400, LogP 2.5–4.5, TPSA 40–70, HBD ≤ 2**. Anti-malarial chemical space is unusually well-defined by clinical history; deviations should be justified by mechanism.

## Structural traits that favour activity

- **Endoperoxide / 1,2,4-trioxane motif** (artemisinin family): iron-activated; the resulting carbon radicals alkylate parasite proteins, including PfATP6 and others. Bioactivation is the mechanism — preserving the endoperoxide is essential ([Tu 2011](https://doi.org/10.1038/nm.2471)).
- **4-aminoquinoline scaffold** (chloroquine, amodiaquine, piperaquine): concentrates in the digestive vacuole via acid trapping; blocks hemozoin formation. Strong but compromised by PfCRT-mediated resistance.
- **8-aminoquinoline scaffold** (primaquine, tafenoquine): the only class with strong hypnozoite activity; mechanism via active metabolite generation.
- **Aryl-amino-alcohol** (mefloquine, lumefantrine, halofantrine): blood-stage actives with long half-lives.
- **Lipophilic naphthoquinone** (atovaquone): cytochrome bc1 inhibitor; the ubiquinone-mimetic motif is the pharmacophore.
- **PfATP4 inhibitor scaffolds** — spiroindolones (cipargamin), pyrazoleamides ([Rottmann 2010](https://doi.org/10.1126/science.1193225)).
- **PI4K inhibitor scaffolds** — aminopyridines (MMV390048) ([McNamara 2013](https://doi.org/10.1038/nature12782)).
- **DHODH inhibitor scaffolds** — triazolopyrimidines (DSM265) ([Phillips 2015](https://doi.org/10.1126/scitranslmed.aaa6645)).

## Structural traits that lower activity or signal liabilities

- **Pure 4-aminoquinolines closely resembling chloroquine** (Tanimoto ≥ 0.5) will inherit PfCRT-mediated resistance; novel scaffolds preferred.
- **Pure artemisinin-like endoperoxides** are now compromised in Southeast Asia by Kelch13 mutations ([Witkowski 2013](https://doi.org/10.1016/S1473-3099(13)70252-4)). Combination therapy is mandatory; monotherapy in screening is the wrong frame.
- **Highly polar / charged compounds** rarely accumulate in the digestive vacuole or cross multiple membranes (parasite, parasitophorous vacuole, erythrocyte).
- **Pure antifolate scaffolds** (diaminopyrimidine + sulfonamide partner) face widespread DHFR/DHPS mutations.
- **Compounds requiring host CYP-mediated activation** can fail in paediatric populations with developmentally low CYP expression.

## Permeability / accumulation peculiarities

The parasite lives inside an erythrocyte, inside a parasitophorous vacuole, with a digestive vacuole as its primary target compartment. A blood-stage drug must cross: (1) the erythrocyte membrane, (2) the parasitophorous vacuole membrane, (3) the parasite plasma membrane, and often (4) the digestive vacuole membrane.

- **Weak-base accumulation**: 4-aminoquinolines pK_a ≈ 8–10 and accumulate 100–1000× in the acidic (~pH 5) digestive vacuole via ion trapping. This is a *feature*: design weak-base centres deliberately.
- **Liver stage** needs hepatocyte access — typical Lipinski-like oral PK applies; 8-aminoquinolines reach liver schizonts after CYP-mediated bioactivation.
- **PfCRT** (chloroquine resistance transporter) effluxes positively-charged 4-aminoquinolines from the digestive vacuole; this is the dominant mechanism of clinical chloroquine resistance.

## Safety liabilities specific to this bucket

- **Embryotoxicity / teratogenicity** — flag aggressively. Malaria affects pregnant women; artemisinin embryotoxicity in animal models was a brief concern (clinical experience reassuring but still cautioned in first trimester).
- **G6PD-deficiency hemolysis** — primaquine and tafenoquine cause hemolysis in G6PD-deficient patients. Any 8-aminoquinoline analog should trigger G6PD-related caveats in the report.
- **QT prolongation** — halofantrine was withdrawn for QT; lumefantrine has a milder signal; piperaquine carries QT warnings. Apply hERG threshold strictly.
- **CYP inhibition / drug-drug interactions** — relevant when malaria patients are co-infected with HIV / TB and on multi-drug regimens.
- **Methemoglobinemia** — primaquine class; 8-aminoquinoline-specific.
- **Resistance pre-existence** — flag scaffolds resembling chloroquine, sulfadoxine, pyrimethamine for class-level resistance risk.

## MMV Target Candidate Profiles (TCPs)

[Burrows 2017](https://doi.org/10.1186/s12936-017-1733-z) defines five TCPs. Map the audit context to the right one:

- **TCP-1** — clears acute, uncomplicated *P. falciparum* asexual blood-stage infection. Fast onset; single-encounter cure or short course.
- **TCP-2** — anti-relapse: kills *P. vivax* / *P. ovale* hypnozoites. Hard target chemically.
- **TCP-3** — chemoprotection (causal prophylaxis): kills liver-stage schizonts before blood-stage emergence.
- **TCP-4** — transmission-blocking: kills gametocytes or interrupts mosquito-stage development.
- **TCP-5** — *P. vivax* radical cure (blood + liver). Effectively TCP-1 + TCP-2.

Each TCP has its own property and PK criteria. For an audit, the relevant TCP comes from `--context` ("blood-stage", "liver-stage", "transmission", etc.) or model-metadata target organism.

## Mechanism-of-action shortcuts

| Target | Drug class / archetype | Recognisable feature |
|---|---|---|
| Hemozoin formation (digestive vacuole) | 4-aminoquinolines (chloroquine, amodiaquine, piperaquine) | 7-Cl-quinoline + basic-amine tail |
| Heme alkylation via Fe-activated peroxide | Artemisinins | 1,2,4-trioxane endoperoxide |
| Hypnozoite kill | 8-aminoquinolines (primaquine, tafenoquine) | 8-amino-6-methoxyquinoline |
| Cytochrome bc1 | Atovaquone | Hydroxynaphthoquinone with cyclohexyl-aryl tail |
| DHFR (antifolate) | Pyrimethamine, proguanil | Diaminopyrimidine |
| PfATP4 (Na+ ATPase) | Cipargamin (spiroindolones) | Spiroindolone-tetrahydroisoquinoline |
| PfPI4K | MMV390048 | 2-amino-pyridine with sulfonyl-piperazine |
| DHODH | DSM265 | Triazolopyrimidine |
| Multi-stage / aryl-amino-alcohol | Mefloquine, lumefantrine | Aryl + amino alcohol |

## How to interpret Ersilia model outputs in this context

- **`plasmodium_*` / `pf_*` / `pv_*` columns** → primary `efficacy` for this bucket. Treat *P. falciparum* and *P. vivax* columns separately if both present.
- **Blood-stage vs liver-stage activity columns** — if both exist, report the life-cycle profile explicitly.
- **`hERG` / cardiac columns** — apply standard threshold; QT history in halofantrine / lumefantrine makes this non-negotiable.
- **`teratogenicity` / `developmental_toxicity` columns** — escalate; pregnancy use is intrinsic to malaria treatment.
- **`g6pd_hemolysis` (if present) or related red-cell tox columns** — escalate, especially for 8-aminoquinoline-like scaffolds.
- **`bbb_*` columns** — irrelevant unless targeting cerebral malaria specifically.
- **`bioavailability_*` / `hia_*`** — escalate for blood-stage TCP-1 (oral, single-dose).

## References

| # | Author, Year | Title | Source | Link |
|---|---|---|---|---|
| 1 | Burrows et al., 2017 | New developments in anti-malarial target candidate and product profiles | Malar J | https://doi.org/10.1186/s12936-017-1733-z |
| 2 | Wells et al., 2015 | Malaria medicines: a glass half full? | Nat Rev Drug Discov | https://doi.org/10.1038/nrd4573 |
| 3 | Phillips et al., 2017 | Malaria | Nat Rev Dis Primers | https://doi.org/10.1038/nrdp.2017.50 |
| 4 | Tu, 2011 | The discovery of artemisinin (qinghaosu) and gifts from Chinese medicine | Nat Med | https://doi.org/10.1038/nm.2471 |
| 5 | Witkowski et al., 2013 | Novel phenotypic assays for the detection of artemisinin-resistant *Plasmodium falciparum* malaria in Cambodia | Lancet Infect Dis | https://doi.org/10.1016/S1473-3099(13)70252-4 |
| 6 | Rottmann et al., 2010 | Spiroindolones, a potent compound class for the treatment of malaria | Science | https://doi.org/10.1126/science.1193225 |
| 7 | McNamara et al., 2013 | Targeting *Plasmodium* PI(4)K to eliminate malaria | Nature | https://doi.org/10.1038/nature12782 |
| 8 | Phillips et al., 2015 | A long-duration dihydroorotate dehydrogenase inhibitor (DSM265) for prevention and treatment of malaria | Sci Transl Med | https://doi.org/10.1126/scitranslmed.aaa6645 |
| 9 | Medicines for Malaria Venture | Target Candidate Profiles, R&D pipeline | — | https://www.mmv.org/research-development |
| 10 | WHO | Guidelines for the treatment of malaria | — | https://www.who.int/teams/global-malaria-programme |

_Last reviewed: 2026-05_
