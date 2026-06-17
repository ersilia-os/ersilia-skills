# molecule-auditing — TODO

## SMARTS / structural-alert expansion

Background research (sources cited at the bottom) found we're under-using RDKit's bundled catalogs and that several high-value external sets are easy to adopt.

### What we already have

- RDKit `FilterCatalogParams.FilterCatalogs` currently used in `scripts/drug_criteria.py`: `PAINS`, `PAINS_A`, `PAINS_B`, `PAINS_C`, `BRENK`, `NIH`, `ZINC`.

### Available but not yet wired up

1. **Other RDKit `CHEMBL_*` enums** — `CHEMBL`, `CHEMBL_Glaxo`, `CHEMBL_Dundee`, `CHEMBL_BMS`, `CHEMBL_SureChEMBL`, `CHEMBL_MLSMR`, `CHEMBL_Inpharmatica`, `CHEMBL_LINT`. The earlier "CHEMBL not in enum" finding was specific to one RDKit build; re-verify against the build the skill targets, then add to `_get_catalog_map` in `drug_criteria.py`. Watch for double-counting: `BRENK` ≈ `CHEMBL_Dundee`, `NIH` ≈ `CHEMBL_MLSMR`.

2. **NIBR Substructure Filters** (Schuffenhauer 2020, *J Med Chem*) — **already in `rdkit/Contrib/NIBRSubstructureFilters/`**, just not exposed via the enum. 444 SMARTS with `severity` (1=flag, 2=exclude), `covalent` flag, PubChem hit counts. Most modern, empirically tuned set. **Highest-value next add.** Load CSV programmatically; preserve severity/covalent metadata as `FilterCatalogEntry` props.

3. **Lilly MedChem Rules** (Bruns & Watson 2012) — 275 rules with graded *demerit* scoring rather than binary flags. Apache-2.0. Queries are in LillyMol native format; pure-Python use requires Datamol's `medchem` wrapper. Add only if we want graded warnings ("amber" vs "red") instead of pass/fail.

4. **Datamol medchem's `common_alerts_collection.csv`** — 2,458 consolidated rows. Add *selectively* for categories not covered above: Alarm-NMR, Chelator, DNABinder, Skin sensitisation, Frequent-Hitter, GST/HIS-Hitters, LD50-Oral, Genotoxic-Carcinogenicity, Toxicophore. Skip Glaxo/BMS/Dundee/MLSMR/SureChEMBL/Inpharmatica/LINT/PAINS rows to avoid duplication with RDKit.

5. **OCHEM ToxAlerts** — endpoint-specific toxicophore SMARTS (mutagenicity, skin sensitisation, reactive metabolism), ~600+. Each alert carries its own citation. Bulk export ergonomics not confirmed; may require login.

### Desirable-trait SMARTS — gap

- No public SMARTS catalogue of privileged scaffolds. Bioisosteres are transformations (SMIRKS), not substructures. Drug-likeness rules are property-based, not SMARTS.
- **Recommendation for the Ersilia context**: hand-curate ~20 anti-infective privileged-scaffold SMARTS (4-aminoquinoline, 8-aminoquinoline, nitroimidazole, β-lactam core, oxazolidinone, fluoroquinolone core, benzimidazole anthelmintic core, artemisinin endoperoxide, sulfonamide-DHPS, diaminopyrimidine-DHFR, etc.) with one-line rationale + literature citation per scaffold. Live alongside `assets/` reference SMILES or as a new `references/anti-infective-scaffolds.smarts`.

### Pitfalls to document wherever we adopt these

- **PAINS SLN→SMARTS translation drift**: RDKit ships 480 patterns, FAFDrugs has 515, medchem has 405. All translations of Baell's original SLN. Pick one set and document which.
- **Inpharmatica and LINT** in ChEMBL/RDKit have no traceable primary citation — flag as lower-confidence than Glaxo/BMS/Dundee/PAINS/MLSMR.
- **DataWarrior toxicity flags are not SMARTS** — they're Actelion idcode fragments. Don't try to extract; integrate as a separate predictor if wanted.

### Concrete next actions (in suggested order)

- [ ] Verify `CHEMBL_*` enum availability against the RDKit version the skill targets; add to `_get_catalog_map` if present.
- [ ] Add NIBR filters: load `Contrib/NIBRSubstructureFilters/SubstructureFilter_HitTriaging_wPubChemExamples.csv`, build a `FilterCatalog` programmatically, expose via `drug_criteria.structural_alerts(..., catalogs=("NIBR",))`. Preserve `severity` and `covalent` columns as entry properties so the audit report can rank warnings.
- [ ] Decide whether to add Lilly MedChem Rules (graded demerits) — depends on whether the audit report wants tiered warnings or stays binary.
- [ ] Hand-curate anti-infective privileged-scaffold SMARTS list (~20 entries with citations). New file under `references/` or `assets/`.
- [ ] Update `references/drug-discovery-criteria.md` §5 once any of the above land — refresh the catalog table and the implementation pointer.

### Sources

- RDKit FilterCatalog dir: https://github.com/rdkit/rdkit/tree/master/Code/GraphMol/FilterCatalog
- RDKit NIBR contrib: https://github.com/rdkit/rdkit/tree/master/Contrib/NIBRSubstructureFilters
- Schuffenhauer 2020 (NIBR): https://pubs.acs.org/doi/abs/10.1021/acs.jmedchem.0c01332
- Lilly MedChem Rules: https://github.com/IanAWatson/Lilly-Medchem-Rules — Bruns & Watson 2012, https://pubs.acs.org/doi/10.1021/jm301008n
- Datamol medchem CSV: https://raw.githubusercontent.com/datamol-io/medchem/main/medchem/data/common_alerts_collection.csv
- OCHEM ToxAlerts: http://ochem.eu/alerts — Sushko 2012, https://pubs.acs.org/doi/10.1021/ci300245q
- PAINS translation drift writeup: https://www.nextmovesoftware.com/talks/Mayfield_PainsInTheButt_201902.pdf
