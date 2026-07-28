# Structural Liability & Metal-Chelation Alerts — Shareable Summary

A consolidated summary of our research into tools for flagging "liable" chemical structures, functional groups, and chemotypes — and a concrete plan for packaging them as Ersilia Model Hub models. Written to be shared with collaborators.

## 1. The starting question, and what we learned

The original ask: find a (Python) tool to detect *liable structural alerts* — reactive functional groups and chemotypes — with a collaborator-supplied example list: **hydrazine, 8-hydroxyquinoline, catechol, polyhalogenated, esters, phenols**.

The single most important finding is that **that list is not one thing**, and treating it as one would cause real errors:

- **hydrazine, catechol, polyhalogenated** are genuine *reactive/undesirable-group* alerts — well covered by existing catalogs.
- **8-hydroxyquinoline** is a *metal chelator*, a different liability (promiscuity / assay interference via metal binding), not a reactive group — and it is absent from the standard reactive-group catalogs.
- **esters and phenols** should **not** be blanket-flagged. They are among the most common groups in approved drugs; a naive "any phenol / any ester" filter flags paracetamol, amoxicillin, aspirin, and artemisinin (verified). The established catalogs deliberately flag only *reactive variants* (phenol esters, ≥3 esters, polyhalophenols, catechol), never the bare group.

The practical consequence: liabilities split into **distinct lenses**, each answered by a different, purpose-built resource — plus a neutral **functional-group census** that *reports* common groups (like phenol/ester) as context instead of flagging them.

## 2. The four alert catalogs

Each answers a different question. They are complementary, not redundant — notably, Brenk and PAINS almost never flag the same atoms.

| Catalog | What it flags | Question it answers | Alerts | Source |
|---|---|---|---|---|
| **Brenk** | Reactive, unstable, undesirable functional groups | "Is this group chemically problematic?" | 105 | Brenk et al., *ChemMedChem* 2008 — built for **neglected-disease** screening libraries |
| **PAINS** | Pan-assay interference substructures (frequent hitters) | "Will this give false readouts in biochemical/HTS assays?" | 480 (A 16 / B 55 / C 409) | Baell & Holloway, *J Med Chem* 2010 |
| **Lilly demerits** | Reactivity / promiscuity / instability, **scored** | "What is this compound's overall liability burden?" | 275 rules | Bruns & Watson, *J Med Chem* 2012 |
| **Metalloenzyme chelators** | Mg/Mn/Zn metal-coordinating groups | "Could this chelate a metalloenzyme cofactor (promiscuity/interference)?" | 16 families / 19 SMARTS | Schuck & Brenk, *Arch Pharm* 2024 |

Key distinctions:
- **Brenk** is knowledge-based and tuned to anti-infective / neglected-disease chemistry — the best conceptual fit for Ersilia's work.
- **Lilly** is the only *graded* catalog: each match adds demerits, and a molecule is rejected past ~100. It outputs a score and a verdict, not per-alert hits.
- **Metalloenzyme chelators** is derived entirely from the published, openly-deposited Schuck & Brenk dataset (PDB-mined Mg/Mn/Zn coordinating groups; Zenodo 10.5281/zenodo.10079154). See `chelator-alerts-grounding.md` for full provenance.

## 3. Closing the loop: where the collaborators' six alerts land

| Original term | Lens | Covered by | Note |
|---|---|---|---|
| hydrazine | reactive group | **Brenk** (+ NIH) | ✅ direct |
| catechol | reactive + interference + chelation | **Brenk**, **PAINS**, **chelators** | ✅ appears in three lenses |
| polyhalogenated | reactive group | **Brenk** (`halogenated_ring`) | ✅ direct |
| 8-hydroxyquinoline | metal chelation / frequent hitter | partially — **chelators** has a hydroxy**quinazoline** cousin | ⚠️ Verified: NOT in PAINS or any RDKit catalog. True 8-HQ is an Fe/Cu chelator, absent from the Mg/Mn/Zn set. Best published source = Schorpp frequent-hitter filters (see §6). |
| esters | (not a liability) | **census** | ❌ do not flag; report neutrally. Only reactive ester variants are Brenk alerts. |
| phenols | (not a liability) | **census** | ❌ do not flag; report neutrally. Only catechol/polyhalophenol etc. are alerts. |

This is the clean answer to the initial prompt: four of the six are real alerts handled by Brenk/PAINS/chelators; one (8-HQ) is a partially-covered chelation case with a documented gap; and two (esters, phenols) belong in the census, not the alert path.

## 4. Proposed Ersilia Model Hub models

| # | Model | Contains | Endpoints (output columns) | Output type | Source |
|---|---|---|---|---|---|
| 1 | `brenk-filters` | 105 reactive/undesirable alerts | 105 (+1 count) | per-alert flags | Brenk 2008 |
| 2 | `lilly-demerits` | 275 demerit rules | 2 (demerit score + reject flag) | score + verdict | Bruns & Watson 2012 |
| 3 | `pains-alerts` | 480 interference substructures | 480 (+1 count) | per-alert flags | Baell & Holloway 2010 |
| 4 | `metalloenzyme-chelators` | 16 Mg/Mn/Zn chelator families | 16 (+ metal tags) | per-alert flags + metal | Schuck & Brenk 2024 |
| 5 | `functional-group-census` *(proposed)* | ~85 functional groups | ~85 counts | neutral counts | RDKit `Chem.Fragments` |
| 6 | `frequent-hitter-chelators` *(proposed)* | chelating assay frequent hitters incl. 8-HQ | ~178 (or curated subset) | per-alert flags | Schorpp 2014 / Ghosh 2022 (ToxAlerts) |

Models 1, 3, 4, 6 share a per-alert design; model 2 is aggregate by nature; model 5 is neutral context (below).

## 5. The functional-group census — what it is and how to build it

**What it is.** A census answers *"what functional groups are in this molecule?"* — a neutral inventory — rather than *"what's wrong with it?"*. It exists precisely so that ubiquitous groups like **phenol and ester** can be *surfaced as context* without being mislabelled as liabilities. It complements the alert catalogs: alerts say "look closer here," the census says "here's what the molecule is made of."

**Why it matters here.** It is the correct home for the two over-flagged items from the original list. A reviewer sees "contains: phenol, ester, aryl halide" as information, and only the alert models raise actual flags (and only for the genuinely reactive sub-patterns).

**How to develop it — grounded, no hand-authoring.** Three published, open options, in order of effort:

1. **RDKit `Chem.Fragments` (recommended start).** RDKit ships **85** built-in functional-group counters (`fr_*`), already including `fr_phenol`, `fr_ester`, `fr_halogen`, `fr_alkyl_halide`, `fr_aniline`, `fr_nitro`, `fr_sulfonamd`, etc. Zero SMARTS authoring; each returns a count. This is directly an ~85-endpoint Ersilia model.
2. **Ertl IFG algorithm** (Ertl, *J Cheminform* 2017). Automatically *identifies* functional groups with no predefined list — useful if you want emergent groups rather than a fixed vocabulary.
3. **checkmol/matchmol** (Haider) — ~200 curated functional-group definitions, open source, if you want a richer fixed vocabulary than RDKit's.

**Recommended design.** Start with RDKit `Chem.Fragments` (85 counts) as `functional-group-census`. Keep it a *separate* model with its own neutral output — never merged into the alert flags — so the "report vs. flag" distinction stays clean. If you later want broader coverage, layer in checkmol's set.

## 6. Update — 8-HQ and chelating frequent hitters

Follow-up finding (verified empirically in RDKit): **8-hydroxyquinoline is not flagged by PAINS — nor by any RDKit-bundled catalog** (Brenk / PAINS / NIH / ZINC / the full ChEMBL vendor sets). Hits on related molecules are incidental (clioquinol→iodine, nitroxoline→nitro), never the metal-binding motif. 8-HQ's real liability is **assay frequent-hitter / promiscuity via metal chelation**, not reactivity.

The matching published source is **Schorpp et al. 2014** — AlphaScreen frequent-hitter mining that found chelators (esp. 8-HQ) dominate frequent hitters, encoded as **178 promiscuity SMARTS filters** hosted on **ToxAlerts** (`ochem.eu/alerts`). This is a set *distinct* from the 480 PAINS (ToxAlerts holds both). An updated, higher-accuracy version with mechanism labels is **Ghosh et al. 2022**.

Status / how to obtain: ToxAlerts has no open bulk file (unlike Schuck's Zenodo) — export needs an OCHEM login, or use the paper supplementary files. Once obtained, extract + RDKit-verify the same way as the chelator model. Candidate model: **`frequent-hitter-chelators`** (row 6 above), or fold into a broader `promiscuity-alerts`. This is the proper home for the 8-HQ gap — *not* a hand-authored SMARTS.

## 7. References

- Brenk et al. *Lessons Learnt from Assembling Screening Libraries for Drug Discovery for Neglected Diseases.* ChemMedChem 2008. — Brenk filters.
- Baell & Holloway. *New Substructure Filters for Removal of PAINS.* J Med Chem 2010. — PAINS.
- Bruns & Watson. *Rules for Identifying Potentially Reactive or Promiscuous Compounds.* J Med Chem 2012. — Lilly demerits. https://doi.org/10.1021/jm301008n
- Schuck & Brenk. *On the hunt for metalloenzyme inhibitors…* Arch Pharm 2024. https://doi.org/10.1002/ardp.202300648 · data: https://doi.org/10.5281/zenodo.10079154
- Ertl. *An algorithm to identify functional groups in organic molecules.* J Cheminform 2017.
- Schorpp et al. *Identification of Small-Molecule Frequent Hitters from AlphaScreen High-Throughput Screens.* J Biomol Screen 2014. — 178 promiscuity filters (8-HQ chelators). https://journals.sagepub.com/doi/10.1177/1087057113516861
- Ghosh et al. *Highly Accurate Filters to Flag Frequent Hitters in AlphaScreen Assays by Suggesting their Mechanism.* Mol Inform 2022. https://onlinelibrary.wiley.com/doi/10.1002/minf.202100151
- ToxAlerts (frequent-hitter + PAINS SMARTS): http://ochem.eu/alerts
- RDKit `Chem.Fragments` (fr_* descriptors); RDKit `FilterCatalog` (Brenk/PAINS/NIH/ChEMBL).
- MeDBA (Fe/Cu extension, currently not downloadable): https://doi.org/10.1093/nar/gkac860

*Companion files in this skill: `chelator-alerts-grounding.md` (full provenance of model 4), `assets/chelator_alerts.yaml` (the catalog), `structural-alerts-review.md` (broader tools/literature review).*
