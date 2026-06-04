# Chelator Alert Catalog — Grounding & Methodology

This document explains exactly where the chelator alert catalog (`../assets/chelator_alerts.yaml`) comes from and how it was derived, so every family is traceable to published data rather than to hand-authored guesses.

## Single source

All SMARTS are taken **verbatim** from one peer-reviewed, openly-deposited dataset:

> Schuck B, Brenk R. *On the hunt for metalloenzyme inhibitors: Investigating the presence of metal-coordinating compounds in screening libraries and chemical spaces.* Arch Pharm. 2024;357:e2300648. https://doi.org/10.1002/ardp.202300648
> Code/data: https://github.com/ruthbrenk/Metal-chelating-groups (v1.1) · Zenodo https://doi.org/10.5281/zenodo.10079154

This is the same Brenk as the widely-used Brenk structural-alert filter, which is why it sits naturally alongside the other catalogs in this skill.

## How the groups were originally produced (by the authors)

The authors searched the PDB for proteins containing Mg²⁺, Mn²⁺, or Zn²⁺, found ligands with a heteroatom within 2.6 Å of the metal, and applied a rule-based pipeline to extract the coordinating atom plus its local chemical environment as a SMARTS. This yielded **1,223 unique metal-coordinating groups** (Supporting Information S3), each tagged with the metal(s) it bound, with PDB frequencies in S4, library prevalence in S6, and a substructure hierarchy in S5. Crucially, these are **empirical** — every group is something that actually coordinated a metal in a crystal structure, not a proposed motif.

## How we reduced 1,223 → 16 (reproducible)

1. **Start: 1,223** unique SMARTS (S3), forms converted to searchable patterns by the authors (S6: `[OD1]`/`[ND1]`/`[ND2]` mark unsubstituted coordinating atoms).
2. **Drop phosphorus groups (−521 → 703).** The authors themselves note phosphates are non-drug-like (high charge, poor permeability) and dominate the set because of ATP/ADP-type Mg ligands.
3. **Drop the over-general parents.** The S5 hierarchy's root nodes are deliberately the *most general* motifs — bare carbonyl `C=O` (root of 347 groups), alcohol `[OD1]C` (395), ether, phenol, amide. These flag almost any molecule (the same trap as blanket "phenol/ester" filters) and carry no specific signal.
4. **Keep the chemically specific, recurring motifs** that are recognised metal-binding groups in the medicinal-chemistry literature, prioritising by PDB frequency (S4) and presence in drug-like chelator libraries (S6).
5. **Result: 16 families** — 10 high-specificity ("keep") and 6 more promiscuous but legitimate donors ("borderline").

Note: the genuinely useful motifs (catechol, hydroxamic acid, hydroxypyrimidinone) are *leaf/intermediate* nodes in the S5 tree, **not** roots — so the "57 roots" are a map of the data, not the catalog itself. Selection was driven by frequency + recognised-ZBG status, with the hierarchy used only to understand structure and to surface the boron/benzoxaborole/tropolone/pyranone families.

## The 16 families

Every `smarts`, `metals`, `pdb_ligands`, and `lib_*` value below is from the paper's S3/S4/S6. The `rationale` (ZBG class + drug exemplar) is added context for interpretability, clearly separated from the published data.

| Family | Verbatim SMARTS (S6) | Metals | PDB lig. | Lib (LC) | Tier | Recognised as |
|---|---|---|---|---|---|---|
| sulfonamide | `[ND1]S(=O)(=O)c1ccccc1`, `[ND1]S(=O)=O` | Zn | 339 | 13 | keep | Carbonic-anhydrase ZBG (acetazolamide) |
| hydroxamic acid | `[OD1]NC=O` | Mg/Mn/Zn | 62 | 10 | keep | HDAC/MMP ZBG (vorinostat) |
| catechol | `[OD1]c1ccccc1[OD1]` | Mg/Mn/Zn | 49 | 3 | keep | Fe siderophore; also Brenk/PAINS |
| thiol | `[SD1]C` | Zn | 42 | 0 | keep | Soft-metal ZBG (captopril) |
| hydroxypyrimidinone | `[OD1]c1cncnc1=O`, `[ND2]C(=O)c1cncnc1[OD1]` | Mg/Mn/Zn | 30 | 23 | keep | Integrase/endonuclease two-metal chelator (raltegravir, baloxavir) |
| hydroxyquinazoline | `[OD1]c1cccc2cncnc12` | Mg | 12 | 0 | keep | Fused N,O chelator (8-HQ cousin — see caveat) |
| boronic acid | `[OD1]B(O)O`, `[OD1]B(O)c1ccccc1` | Zn/Mg | 25 | 0 | keep | Zn/serine warhead (bortezomib, vaborbactam) |
| benzoxaborole | `[OD1]B1ccCO1` | Mg/Zn | — | 0 | keep | Boron scaffold (tavaborole — anti-infective) |
| tropolone | `[OD1]c1cccccc1=O` | Mn/Zn | — | 1 | keep | Fe/Cu/Zn O,O chelator (hinokitiol) |
| 4-pyranone | `O=c1ccocc1` | Zn | — | 113 | keep | Fe/Cu chelator (maltol, kojic acid) |
| imidazole | `c1cncn1` | Zn | 22 | — | borderline | Histidine-mimic N-donor |
| pyridine | `c1ccncc1` | Mn/Zn | 29 | — | borderline | Monodentate N-donor (very common) |
| tetrazole | `c1nnnn1` | Zn | — | — | borderline | Carboxylate bioisostere |
| oxime | `[OD1]N=C` | Mg/Mn | 3 | — | borderline | N,O donor (pralidoxime) |
| α-hydroxy acid | `[OD1]CC(=O)[OD1]` | Mg | 38 | — | borderline | Ca/Mg/Fe O,O chelator (citrate) |
| amino-carboxylate | `[OD1]C(=O)CN` | Mg/Mn/Zn | 54 | — | borderline | Aminopolycarboxylate (EDTA) |

## Verification (RDKit 2026.03)

- **All 19 patterns parse.**
- **Positive controls hit their family:** acetazolamide→sulfonamide, vorinostat→hydroxamate, catechol→catechol, captopril→thiol, raltegravir→hydroxypyrimidinone, tavaborole→benzoxaborole, maltol→pyranone, tropolone→tropolone.
- **Promiscuity (flags among 8 ordinary drugs — paracetamol, amoxicillin, aspirin, ibuprofen, caffeine, diazepam, metronidazole, propranolol):** every "keep" family = **0/8**. Borderline: imidazole 2/8 (caffeine, metronidazole), amino-carboxylate 1/8 (amoxicillin). This is the evidence behind the keep/borderline split.

## Scope caveats (important, honest)

1. **Mg/Mn/Zn only — not an Fe/Cu set.** The source covers enzyme-cofactor metals. It is *not* an iron-sequestration / Fe-Cu chelation set.
2. **True 8-hydroxyquinoline is NOT matched.** The closest published motif is a hydroxy**quinazoline** (two ring N). Clioquinol (true 8-HQ) is only caught by the generic `pyridine` pattern. Closing the original 8-HQ/Fe-chelator gap properly requires a different source such as MeDBA (844 metal-binding pharmacophores across more metals) — and should *not* be patched with a hand-written SMARTS.
3. **Cyclic boronate esters can evade** the free-boronic-acid pattern (e.g. vaborbactam); free boronic acids and benzoxaboroles are covered.
4. **A hit is a flag for review, not a toxicity verdict.** Many legitimate, marketed drugs chelate metals as their mechanism (ACE inhibitors, HDAC inhibitors, integrase inhibitors). Use this to surface possible metalloenzyme promiscuity / assay interference, then judge in context.
