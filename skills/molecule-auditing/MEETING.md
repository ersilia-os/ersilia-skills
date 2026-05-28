# Meeting with Iakovos — molecule-auditing skill

## Quick context

- Anti-infective audit skill, 7 pathogen buckets (gram-neg, gram-pos, mycobacterial, malaria, kinetoplastid, helminthic, fungal)
- Per-bucket: reference compounds, MedChem criteria, property windows
- Want your feedback on the **chemistry**, **references**, and **SMARTS**

---

## Files to browse

- **Skill workflow**: [SKILL.md](SKILL.md)
- **Shared anti-infective criteria**: [shared-anti-infective-criteria.md](references/shared-anti-infective-criteria.md)
- **Per-bucket criteria docs**:
  - [gram-negative](references/gram-negative-criteria.md)
  - [gram-positive](references/gram-positive-criteria.md)
  - [antimycobacterial](references/antimycobacterial-criteria.md)
  - [antimalarial](references/antimalarial-criteria.md)
  - [antikinetoplastid](references/antikinetoplastid-criteria.md)
  - [antihelminthic](references/antihelminthic-criteria.md)
  - [antifungal](references/antifungal-criteria.md)
- **Generic drug-discovery rules**: [drug-discovery-criteria.md](references/drug-discovery-criteria.md)
- **Reference SMILES per bucket**: [assets/](assets/)

---

## MedChem feedback

- Do the 7 buckets make sense? Anything missing / wrongly grouped?
- For each bucket, look at the reference compound list — obvious omissions or wrong inclusions?
- Property windows (MW / LogP / TPSA / HBD / etc.) — do they match your intuition?
- Structural traits favouring / lowering activity — anything I have wrong?
- Most common mistake a non-MedChem person makes when triaging anti-infective hits?
- How do you separate **MoA-legitimate** scaffolds (nitroaromatics, β-lactams, Michael acceptors) from **artefact-prone** ones?

---

## References & resources

- Anchor reviews per bucket you'd recommend
- Public datasets beyond ChEMBL / PubChem (MMV Pathogen Box, CO-ADD, DNDi compounds, ChEMBL-NTD)
- Public TPPs / TCPs we should cross-link (MMV, DNDi, WHO, Stop TB)
- Internal Ersilia documents / wiki we should mine
- Communities / mailing lists where new resources surface

---

## ★ SMARTS lists — the priority ask

- **Do you have a personal / lab SMARTS list you can share?** Any format — we'll convert.
- For each SMARTS we want:
  - Pattern
  - Short label (display name)
  - Severity: hard-reject / flag / informational
  - One-line reason or citation
  - Optional: bucket scope
- Specific lists worth probing:
  - Your own curated lab list
  - Anti-infective phenotypic-screen alerts (better than generic PAINS)
  - Aggregator patterns you've seen fail counter-screens
  - Frequent-hitter scaffolds in **kinetoplastid** + **antimycobacterial** screens
  - Niche published lists you use (Pat Walters `rd_filters`, ChEMBL alerts, Eli Lilly MedChem rules)
- Catalogs already in RDKit (PAINS / Brenk / NIH / ZINC) — do you trust them? Which subsets?
- For primary anti-infective screening, top alert classes to monitor:
  - Redox cyclers / quinones
  - Aggregators
  - Fluorescence interferers
  - Metal chelators (catechols, hydroxyquinolines)
  - Membrane disruptors (cationic amphiphiles)
- Your one-line **"throw it out on sight"** scaffolds?
- Even 10–20 high-priority SMARTS today would be a meaningful upgrade.
