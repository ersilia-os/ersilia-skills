# Antihelminthic Criteria

> Audit guidance for compounds targeting parasitic worms: schistosomes (*Schistosoma mansoni*, *S. haematobium*, *S. japonicum*), soil-transmitted helminths (STHs — *Ascaris lumbricoides*, hookworms *Necator*/*Ancylostoma*, *Trichuris trichiura*), filariae (*Onchocerca volvulus* — river blindness, *Wuchereria bancrofti* / *Brugia* — lymphatic filariasis), and intestinal tapeworms. Cross-link: [shared anti-infective concepts](./shared-anti-infective-criteria.md).

## Quick rules (Claude reads these first)

- **Helminths are multicellular eukaryotes** — drug discovery here borrows heavily from veterinary pharmacology and inherits a long agrochemical history. Several "antihelminthic" leads have origins in livestock anthelmintic programmes.
- **Single-dose, oral, mass-administration-friendly is the implicit product profile.** STH and filarial control rely on mass drug administration (MDA); a candidate that needs multi-day dosing or refrigeration is at a strong disadvantage.
- **MW 250–400 and LogP 2–4** is the empirical window for clinical antihelminthics. Outliers exist (ivermectin MW 875) but are veterinary in origin.
- **Activity against adult worms ≠ activity against juveniles / eggs.** For schistosomiasis, praziquantel is excellent against adults but weak against young migrating schistosomula — a known gap. Filter for activity stage when columns disambiguate.
- **Praziquantel resistance is a real and growing concern.** Hits that resemble praziquantel face the same risk; novel-scaffold preference is scientifically meaningful here.
- **Avoid mammalian neurotoxicity scaffolds.** Helminth and mammalian neuromuscular pharmacology overlap (GABAA, nAChR, glutamate-gated chloride channels); GluCl (helminth-specific) is the avermectin sweet spot.
- **G6PD-related and pregnancy precautions** apply to several antihelminthics (DEC-induced filarial death reactions, albendazole teratogenicity in animals). Flag accordingly.

## Pathogen biology essentials

Helminths span two phyla — Platyhelminthes (flatworms: schistosomes, tapeworms, flukes) and Nematoda (roundworms: STHs, filariae, *Strongyloides*). They are multicellular, sometimes very large (adult *Ascaris* > 20 cm; adult *Onchocerca* > 30 cm), and have differentiated tissues — muscle, nervous system, gut, reproductive system. Drug targets are correspondingly different from those in microbes:

- **Neuromuscular pharmacology**: parasitic worm muscle uses nAChR (levamisole target), GluCl (ivermectin target), GABA (piperazine target), and TRPM (praziquantel-related Ca²⁺-permeable channels) — paralysis or spastic contraction expels worms from gut / vasculature.
- **β-tubulin polymerisation**: benzimidazoles selectively bind worm β-tubulin; mammalian β-tubulin is much less sensitive.
- **Energy metabolism**: anaerobic glycolysis, fumarate reductase — distinct from mammalian aerobic respiration.
- **Cuticle / tegument biology**: schistosome tegument is a syncytial covering with unique transport proteins.

The host context varies dramatically: intestinal lumen (STHs) vs gut wall + portal venous system (schistosomes) vs subcutaneous nodules (*Onchocerca*) vs lymphatics (*W. bancrofti*). Tissue distribution requirements differ accordingly.

## Property windows (empirically derived)

### Property windows for `antihelminthic` (n = 11 compounds)

| Property | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| MW | 199.3 | 235.8 | 307.3 | 326.2 | 797.0 |
| LogP | 0.70 | 2.32 | 2.83 | 3.55 | 5.38 |
| TPSA | 15.6 | 32.4 | 67.0 | 102.0 | 170.1 |
| HBD | 0 | 0 | 1 | 2 | 3 |
| HBA | 2 | 3 | 4 | 6 | 14 |
| RotBonds | 1 | 2 | 3 | 4 | 8 |
| AromaticRings | 0 | 1 | 2 | 2 | 3 |
| Fsp3 | 0.00 | 0.08 | 0.36 | 0.55 | 0.90 |
| HeavyAtoms | 14 | 16 | 21 | 22 | 56 |

**Outlier compounds** (any property outside the p5–p95 band):
- **Ivermectin** — MW=797, RotBonds=8, HBA=14. Macrocyclic lactone; semi-synthetic from a *Streptomyces* fermentation product. Veterinary origin.
- **Triclabendazole** — LogP=5.38. Lipophilic chlorinated benzimidazole; very effective for fascioliasis.
- **Niclosamide** — Fsp3=0.00. Salicylanilide; rigid planar scaffold.
- **Diethylcarbamazine** — MW=199, LogP=0.70, Fsp3=0.90. Small piperazine carboxamide; lymphatic filariasis MDA standard.

**Target window for novel leads: MW 250–400, LogP 2–4, HBD ≤ 2.** Lipinski-compliant scaffolds dominate; macrolactones like ivermectin are a separate strategy with different optimisation rules.

## Structural traits that favour activity

- **Benzimidazole-2-carbamate** (albendazole, mebendazole, fenbendazole, triclabendazole) — selective worm β-tubulin binding. Mature, mass-deployable scaffold ([Lacey 1990](https://doi.org/10.1016/0020-7519(90)90034-J)).
- **Pyrazino-isoquinoline** (praziquantel) — Ca²⁺ influx → spastic paralysis. Schistosomiasis gold standard ([Caffrey 2007](https://doi.org/10.1016/j.cbpa.2007.07.014)).
- **Macrocyclic lactone with disaccharide** (ivermectin, moxidectin, eprinomectin) — GluCl agonism (worm-specific) → paralysis. Onchocerciasis + LF + STH dual use ([Crump & Omura 2011](https://doi.org/10.2183/pjab.87.13)).
- **Imidazo[1,2-a]thiazole** (levamisole) — nAChR agonist → spastic paralysis. STH.
- **Tetrahydropyrimidine** (pyrantel) — nAChR agonist; STH.
- **Salicylanilide** (niclosamide, oxyclozanide, rafoxanide) — mitochondrial uncoupler; tapeworms + flukes.
- **Diethylcarbamazine piperazine** — kills *W. bancrofti* microfilariae via host-mediated and direct mechanisms.
- **Cyclic depsipeptide** (emodepside) — calcium-activated potassium channel SLO-1 agonist; recently approved for veterinary use, in development for human onchocerciasis ([Krücken 2021](https://doi.org/10.1016/j.actatropica.2020.105776)).

## Structural traits that lower activity or signal liabilities

- **Pure mammalian neuromuscular agents** (e.g. broad nAChR antagonists, GABA agonists without GluCl selectivity) — risk human toxicity.
- **Lipinski-violating scaffolds without veterinary precedent** — for mass drug administration use, oral simplicity is mandatory.
- **Compounds requiring CYP-mediated activation in livestock-PK contexts** — translate poorly to humans.
- **Pure prokaryote inhibitors** (e.g. classical antibacterial scaffolds) — worms are eukaryotic; mechanism likely not relevant.

## Permeability / accumulation peculiarities

Worms inhabit very different host compartments, each with its own delivery profile:

- **Intestinal STHs** — drug needs to reach the gut lumen; oral compounds with poor systemic absorption can be ideal (niclosamide is poorly absorbed and that's why it works for tapeworms).
- **Schistosomes** — live in mesenteric / vesical / hepatic-portal veins. Drug must reach systemic circulation; tegument is the target tissue.
- **Onchocerca** — subcutaneous nodules of adult worms + skin microfilariae. Lipophilic, well-distributed compounds preferred (ivermectin).
- **Wuchereria** — lymphatic vessels. Need adequate lymphatic distribution.
- **Filarial microfilariae rapid kill** can cause severe inflammatory reactions (Mazzotti reaction in onchocerciasis, encephalopathy with *Loa loa* co-infection during DEC) — a slow-kill compound profile is actually preferred clinically for some scenarios.

There is no efflux equivalent to AcrAB-TolC; worm pharmacology has its own P-glycoprotein-like transporters that drive benzimidazole / ivermectin resistance in livestock, with growing concern in humans.

## Safety liabilities specific to this bucket

- **Mazzotti reaction / inflammatory die-off** — rapid microfilarial kill releases parasite antigens; can cause severe symptoms in onchocerciasis or *Loa loa* co-infection. A slow-kill or macrofilaricidal profile may be safer.
- **Benzimidazole teratogenicity** — albendazole + mebendazole carry pregnancy warnings (animal teratogenic data); a known class watch-out.
- **Ivermectin / *Loa loa* encephalopathy** — in patients heavily infected with *L. loa*, ivermectin can cause fatal encephalopathy. Pre-screening for *L. loa* is standard in endemic Central Africa.
- **Praziquantel cardiac at high doses** — some literature on QT signal at supratherapeutic exposure. Apply standard hERG threshold.
- **Triclabendazole hepatotoxicity** — rare but reported; long-treatment caveat for fascioliasis.
- **Levamisole agranulocytosis** — clinically known; withdrawn for non-helminth indications partly for this.
- **Diethylcarbamazine ocular toxicity in onchocerciasis** — DEC is contraindicated for onchocerciasis specifically because rapid microfilarial death in the eye causes severe damage.

## Mechanism-of-action shortcuts

| Target | Drug class / archetype | Recognisable feature |
|---|---|---|
| β-tubulin (worm-selective) | Benzimidazole-2-carbamates (albendazole, mebendazole) | Benzimidazole + methyl carbamate |
| TRPM Ca²⁺ channel | Praziquantel | Pyrazino-isoquinoline |
| GluCl (glutamate-gated Cl⁻) | Macrocyclic lactones (ivermectin, moxidectin) | 16-membered macrolactone + disaccharide |
| nAChR agonist (worm) | Imidazo-thiazoles (levamisole), tetrahydropyrimidines (pyrantel) | Small bicyclic with sulfur or pyrimidine |
| Mitochondrial uncoupling | Salicylanilides (niclosamide) | 5-chloro-2'-NO₂-salicylanilide |
| Microfilarial kill (mech still debated) | Piperazine carboxamides (DEC) | Diethylcarbamoyl-piperazine |
| SLO-1 K⁺ channel | Cyclic depsipeptides (emodepside) | Cyclo-octadepsipeptide |
| Anaerobic metabolism / DNA | Nitroaryls (nitazoxanide) | Nitrothiazolyl-salicylamide |

## How to interpret Ersilia model outputs in this context

- **`schistosoma_*` / `s_mansoni_*` columns** → primary `efficacy` for schistosomiasis hits.
- **`sth_*` / *Trichuris* / *Ascaris* / hookworm columns** → primary `efficacy` for STH; cross-reference all three when available — *Trichuris* is the hardest to kill.
- **`onchocerca_*` / `filaria_*` columns** → primary `efficacy` for onchocerciasis / lymphatic filariasis.
- **`adult_vs_larval_*` activity columns** — when available, weight the adult-worm column more, since adult clearance drives cure.
- **`pgp_*` / efflux columns** — relevant; veterinary helminth resistance is P-gp-mediated.
- **`hERG` columns** — apply standard threshold; praziquantel cardiac data justifies attention.
- **`teratogenicity` columns** — escalate for benzimidazole-class scaffolds.
- **`oral_bioavailability_*`** — escalate; oral MDA is intrinsic to the product profile.
- **`gut_distribution` / `oral_non-absorbed` (if present)** — for tapeworm / STH indications, *low* systemic absorption can be a feature.

## References

| # | Author, Year | Title | Source | Link |
|---|---|---|---|---|
| 1 | Keiser & Utzinger, 2010 | The drugs we have and the drugs we need against major helminth infections | Adv Parasitol | https://doi.org/10.1016/S0065-308X(10)73008-6 |
| 2 | Crump & Omura, 2011 | Ivermectin, "wonder drug" from Japan: the human use perspective | Proc Jpn Acad Ser B | https://doi.org/10.2183/pjab.87.13 |
| 3 | Caffrey, 2007 | Chemotherapy of schistosomiasis: present and future | Curr Opin Chem Biol | https://doi.org/10.1016/j.cbpa.2007.07.014 |
| 4 | Geary et al., 2015 | Anthelmintic drug discovery: into the future | J Parasitol | https://doi.org/10.1645/14-703.1 |
| 5 | Lacey, 1990 | Mode of action of benzimidazoles | Int J Parasitol | https://doi.org/10.1016/0020-7519(90)90034-J |
| 6 | Krücken et al., 2021 | Reagents for emodepside resistance research and new drug development | Acta Trop | https://doi.org/10.1016/j.actatropica.2020.105776 |
| 7 | Hotez et al., 2014 | Helminth infections: the great neglected tropical diseases | J Clin Invest | https://doi.org/10.1172/JCI34261 |
| 8 | WHO | Soil-transmitted helminthiases / Schistosomiasis / Onchocerciasis / Lymphatic filariasis programmes | — | https://www.who.int/teams/control-of-neglected-tropical-diseases |

_Last reviewed: 2026-05_
