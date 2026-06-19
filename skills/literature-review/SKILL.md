---
name: literature-review
description: >
  Conduct deep, structured literature research for Ersilia drug discovery work.
  Use this skill whenever a user asks to find, review, or summarise scientific papers
  about a disease, biological target, compound class, or AI/ML method in the context
  of drug discovery — especially for neglected tropical diseases (NTDs), antimicrobial
  resistance (AMR), or global health. Triggers include target names (e.g. Mtb, PfDHFR,
  TryR, InhA), disease names (e.g. malaria, leishmaniasis, tuberculosis, Chagas,
  schistosomiasis), model or method types (e.g. GNN, QSAR, ChemBERTa), and requests
  like "find papers on", "what does the literature say about", "summarise research on",
  "literature review for", or "what's been published about". Always use this skill for
  Ersilia-context literature work, even if the request is phrased casually.
---

# Literature Research for Ersilia

Rigorous literature research for Ersilia's mission — NTDs, AMR, and AI/ML drug discovery
for global health. The lens is **what's worth integrating**: new **models** (🤖) and
**datasets** (🗃️) the Hub could absorb, plus the biology that anchors them.

**Two engines do the heavy lifting: Semantic Scholar (API) and Google Scholar (web).**
Everything else is a supplement. Papers already in the Hub are **excluded** — the review
covers *novel* literature only.

Output: a concise, table-driven markdown report with **Reviews** and **Research papers**
sections, each entry carrying ribbon markers (⭐🌍🤖🗃️💻). Optionally posted to Slack.

---

## Inputs

- **Topic** (required): disease, target, compound class, or ML method.
- `--from / --to` (optional): date range. Default last 5 years. Seminal papers (target
  structure, field-defining method, key resistance mechanism) are **exempt** — include and
  mark as seminal.
- `--depth focused` (optional): cap at 8–15 papers (default: 20–40).
- `--slack` (optional, **experimental — off by default**): post a pointer to `#literature`
  after writing the file. Untested; do **not** post unless the user explicitly passes `--slack`
  in the current request.
- `--out <path>` (optional): override output location.

If the topic is ambiguous, ask **one** focused question. Never invent missing inputs.

---

## Reference files

Read before starting:

- `references/apis.md` — Semantic Scholar, Google Scholar, PubMed, Europe PMC, Crossref,
  preprint endpoints. **Read before any search.**
- `references/hub-incorporation-criteria.md` — rules for 🤖 / 🗃️ and venue priors. Read before tagging.
- `references/hub-exclusion.md` — how to fetch and apply the Hub-DOI exclusion set.
- `references/lmic-countries.md` — the 🌍 rule (LMIC authorship).

---

## Workflow

### Step 1 — Parse the query

| Dimension | What to extract |
|---|---|
| **Primary entity** | disease (*M. tuberculosis*, malaria), target (PfDHFR, InhA), compound class, or ML method (GNN, ChemBERTa) |
| **Angle** | biology/mechanism · drug discovery · AI/ML models · datasets · ADMET |
| **Scope signals** | LMIC-first? method comparison? target deep-dive? |

Map the entity to Ersilia priorities (see Ersilia context below).

---

### Step 2 — Build the Hub-DOI exclusion set

Before searching, pull the set of DOIs already in the Hub so they can be dropped later
(see `references/hub-exclusion.md` for the exact one-liner). The review focuses on **novel
literature** — anything already incorporated is out of scope.

Keep the normalised DOI set in memory. Track how many candidates it later removes.

---

### Step 3 — Search (Scholar-first)

**Primary engines** — run these first and hardest:

| Engine | How | Best for |
|---|---|---|
| **Semantic Scholar** | Graph API (`api.semanticscholar.org`) — see `apis.md` | structured hits: title, year, DOI, venue, citations, open-access PDF in one call |
| **Google Scholar** | `web_search site:scholar.google.com <query>` + citation snowballing | coverage, grey literature, cited-by chains |

**Supplements** — route by angle, don't let them crowd out the primary engines:

| Source | web_search prefix | Best for |
|---|---|---|
| PubMed | `site:pubmed.ncbi.nlm.nih.gov` | peer-reviewed biology, pharmacology, clinical |
| Europe PMC | `site:europepmc.org` | open-access full text |
| PLOS | `site:journals.plos.org` | NTD biology & drug discovery |
| bioRxiv / ChemRxiv | `site:biorxiv.org` / `site:chemrxiv.org` | ML & chemistry preprints |
| arXiv | `site:arxiv.org` | new ML architectures (cs.LG) |
| Nature / Science / Cell | `site:nature.com` etc. | landmark biology/chemistry/AI — for framing |

**Coverage:** run ≥4 query variants across engines (~30 searches), balanced across layers:

1. **Biology / mechanism** — `<entity> mechanism resistance pathogenesis review`
2. **Narrow** — `<target/disease> <subtask> drug discovery`
3. **Broad** — `<disease family> AI machine learning compound`
4. **Method-facing** — `<method type> ADMET activity prediction <disease>`

Use `web_fetch` on individual paper pages for full abstracts / metadata.

**Citation snowballing:** take the 2–3 strongest reviews/landmarks and mine their
references (Semantic Scholar `references`/`citations` fields, or the review's reference list)
for recurring works not yet in the pool. This is how seminal older papers enter.

**Target raw pool:** 40–80 results before screening.

---

### Step 4 — Verify metadata

Verify first-author surname + year before composing an entry. Prefer Semantic Scholar's
returned fields; fall back to Crossref by DOI (`api.crossref.org/works/<doi>`). If lookup
fails, **omit the author** — never guess.

- **DOI:** every entry needs a verified DOI — it is both the citation link and the
  Hub-exclusion key. No DOI, no exclusion check.
- **Affiliations (for 🌍):** Crossref usually omits them. Use the Europe PMC *core* endpoint
  (`.../search?query=...&resultType=core`) — it returns author affiliation strings reliably.
  Don't try to fetch publisher landing pages for this; they routinely 403. See `apis.md`.
- **URL:** `https://doi.org/<doi>` for published work; direct preprint page otherwise.
  Never link to search-result or PubMed-search pages.

---

### Step 5 — Screen, exclude, tag

In order:

1. **Dedup.** Collapse preprint + journal versions to one (keep the published DOI). Merge near-identical titles.
2. **Exclude Hub DOIs.** Drop any candidate whose normalised DOI is in the Step-2 set. Record the count dropped.
3. **Scope filter** — keep only items in one of:
   - Antibiotic / antimicrobial / AMR drug discovery (TB, NTD antibacterials, AMPs, AMR+ML)
   - Global health / LMIC drug discovery / open-science (NTDs, Africa/LMIC-led, public datasets/infra)
   - General-purpose AI methods for drug discovery (featurizers, ADMET, generative chemistry, CPI, foundation models, open chem datasets)
   - Foundational biology / mechanism / epidemiology of a **priority** pathogen or target
4. **Venue quality — strong-prefer high-tier.** Bias hard toward high-tier venues: Nature /
   Science / Cell family, NMI, Nat. Commun., PNAS, NEJM, Lancet, JACS, Angew. Chem., J. Med.
   Chem., eLife, **plus** the Hub's own high-prior venues (J. Cheminform., JCIM, Bioinformatics,
   Briefings in Bioinformatics, Nucleic Acids Research). **Drop MDPI and other low-tier /
   pay-to-publish venues** (Antibiotics, Diagnostics, Diseases, Pharmaceuticals, Biomolecules,
   IJMS, Molecules, Applied Sciences, Microorganisms, Cureus, …) **unless the paper is uniquely
   load-bearing** — the only open model/dataset for that endpoint and nothing higher-tier
   covers it. When you keep one, flag it inline in the TL;DR: `(⚠ low-tier venue)`. Prefer a
   strong preprint (bioRxiv/ChemRxiv/arXiv) over a weak journal.
5. **Tag for integration** (the headline lens — re-read `hub-incorporation-criteria.md`):
   - 🤖 — Hub-incorporable model (small-molecule input, one of six subtasks, openly available)
   - 🗃️ — open dataset the Hub could train on (bioactivity / ADMET / phenotypic on priority targets)
6. **Equity** — apply 🌍 (first/last author at LMIC institution); ranking bonus on tie-breaks.
   LMIC-pathogen papers with no LMIC authorship → note under "Research Gaps", don't promote.

**Coverage self-check** before writing — is the set lopsided?
- Both layers present (biology *and* methods/models)?
- Major sub-areas and main labs covered?
- Any known landmark / recent breakthrough missing?

Fill gaps with targeted searches; record anything unfillable under "Research Gaps".

**Target final set:** 20–40 papers (8–15 in `--depth focused`).

---

### Step 6 — Synthesise the report

**Tight, scannable prose.** Lean on the curated tables instead of re-explaining each paper —
the prose frames the landscape, the tables carry the detail. Hold the framing sections to a
hard line budget:

| Section | Content | Length budget |
|---|---|---|
| **Overview** | the picture + why it matters for Ersilia | **≤ 2 lines** |
| **Biology / Target** | mechanism, druggability, resistance — landmarks only | **≤ 2 lines** |
| **Drug Discovery** | assays, screens, scaffolds, lead series | **≤ 2 lines** |
| **Models & Datasets worth integrating** | the core section — see below | most detail here |
| **Research Gaps** | field gaps **and** review limitations, merged — see below | bullets |

**Models & Datasets worth integrating — aim for 5 + 5.** List up to **5 models (🤖)** and up to
**5 datasets (🗃️)**, one embedded-DOI line each, ordered by how incorporable they are. If the
topic genuinely yields fewer high-quality ones, list what exists and say so — never pad with
weak/low-tier entries. Close with one line on what the Hub already covers / still lacks.

**Research Gaps — one merged section.** A single bulleted list covering both (a) gaps in the
science (understudied biology, contested results, missing methods) and (b) this review's own
limitations (sparse areas, unverified items, LMIC-authorship gaps, venue caveats). There is
**no** separate "Known Gaps" section.

**Citations — DOI always embedded, never bare.** Every in-text citation is a hyperlink with
the DOI embedded on the author–year text: `([Author et al., Year](https://doi.org/<doi>))`.
**Never** print a raw `10.xxxx/...` or PMID string in the prose. No verified DOI → link the
direct preprint page; no link at all → drop the claim or fold it into "Research Gaps".

**State consensus vs. disagreement** — where the literature conflicts (contested mechanisms,
inconsistent potency, failed replications), cite the competing papers side by side.

---

### Step 7 — Compose curated entries

One line each, ordered by relevance → venue tier → recency:

```
[Author et al., *Venue*, YYYY](url) {ribbon} — **Title.** TL;DR + why it matters for Ersilia.
```

- **TL;DR** — 1–2 fresh sentences, plain language. Never paste the abstract.
- **Why it matters for Ersilia** — required, one specific sentence (name the subtask, dataset, NTD, partner, or release).
- Apply a marker only when load-bearing. Absent beats wrong.

Group into **Reviews** (one undivided section) and **Research papers** (split into themed
sub-sections by Hub subtask). Render only the sub-sections that have entries, in this order:

1. **Targets & biology** — non-model science: mechanism, targets, resistance, epidemiology.
2. **Activity prediction** — bioactivity / potency models.
3. **Featurization** — descriptors, embeddings, foundation-model representations.
4. **Generation** — generative / de-novo design.
5. **Property / ADMET** — physchem, ADMET, toxicity predictors.
6. **Datasets & benchmarks** — open dataset / benchmark releases (🗃️).

Collapse the rare subtasks (similarity, projection) into an "Other models" bucket only if
populated. Reviews are **not** sub-divided.

**Markers** (fixed display order `⭐🌍🤖🗃️💻`):

| Marker | When |
|---|---|
| ⭐ | very-high-impact venue (Nature, Science, Cell, PNAS, NMI, NEJM, Lancet, JACS, Angew. Chem., family) |
| 🌍 | first/last author at LMIC institution (`lmic-countries.md`) |
| 🤖 | Hub-incorporable model (`hub-incorporation-criteria.md`) |
| 🗃️ | open dataset the Hub could train on |
| 💻 | paper explicitly names a public repo URL — do not infer |

---

### Step 8 — Write output (+ optional Slack)

Write the markdown file, then surface it:
- **Claude.ai / Cowork:** write to `/mnt/user-data/outputs/literature_<topic>_<YYYYMMDD>.md`
  and call `present_files`.
- **Claude Code / local:** that path won't exist — write to `--out` if given, else
  `./literature_<topic>_<YYYYMMDD>.md`, and hand the user the file path (there is no
  `present_files`).

Template (every citation embeds its DOI as a link — no bare DOI/PMID strings anywhere):

```markdown
# Literature Research: [Topic]
*Generated: [Date] | Engines: Semantic Scholar, Google Scholar (+ PubMed, Europe PMC, PLOS, preprints) | Papers: N | Hub DOIs excluded: M*

## Overview
[≤ 2 lines — citations as embedded DOI links]

## Biology / Target
[≤ 2 lines]

## Drug Discovery
[≤ 2 lines]

## Models & Datasets worth integrating
**Models (🤖) — up to 5**, most-incorporable first: one embedded-DOI line each.
**Datasets (🗃️) — up to 5**: one embedded-DOI line each.
[one line on what the Hub already covers / still lacks]

## Research Gaps
- [field gaps + review limitations + LMIC-authorship gaps, merged]

---

## Reviews
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
| [Author et al., *Venue*, YYYY](url) | ⭐🌍 | … |

## Research papers

### Targets & biology
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|

### Activity prediction
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|

### Generation
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|

### Property / ADMET
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|

### Datasets & benchmarks
| Paper | Markers | TL;DR + why for Ersilia |
|---|---|---|
*(render only non-empty sub-sections; flag any sub-tier venue inline as `⚠ low-tier venue`)*

---

## Search Log
| Engine/Source | Query | Results |
|---|---|---|
```

**In-chat summary** after presenting:
1. One-paragraph synthesis (the "so what" for Ersilia).
2. The 2–3 most important papers, one line each.
3. The single most important gap.
4. If present: 🤖 Hub candidates and 🌍 LMIC-led papers, as short bullets.

**Slack — experimental, disabled by default.** Do **nothing** Slack-related unless the user
passes `--slack` in this request. When (and only when) they do: post a single pointer to
`#literature` (workspace `ersilia-workspace`, channel `C010067BP2Q`) via the Slack MCP — one
📚 message, link only, no highlights (mirror the digest skill's `slack-alert-template.md`).
Never post on failure or before the file is written. Until the user has tested this path,
the default behaviour is to skip Slack entirely and just surface the file in chat.

---

## Ersilia context

**Priority organisms** — *M. tuberculosis* / *M. abscessus*, *P. falciparum* / *P. vivax*,
*Leishmania* spp., *T. cruzi* / *T. brucei*, *S. mansoni*, ESKAPE & GLASS AMR priority pathogens.

**Hub subtasks** (prior share) — Activity prediction (41%) · Featurization (25%) ·
Property prediction (20%) · Similarity (6%) · Generation (5%) · Projection (3%).

**Model types** — QSAR (RF/XGB/SVM) · GNN/MPNN/AttentiveFP · transformers (ChemBERTa, Uni-Mol)
· generative (VAE, diffusion, REINVENT) · ADMET / bioactivity / docking surrogates.

**Databases** — ChEMBL · BindingDB · ZINC · PubChem · Open Targets · MMV/DNDi sets.

**Framing** — open-source & reproducible · low-data/few-shot · resource-limited settings ·
Hub-compatible models.

---

## Things to avoid

- No item without a primary-source link (`https://doi.org/<doi>` or direct preprint page).
- No bare DOI or PMID strings in the prose — every citation is a hyperlink with the DOI
  embedded: `[Author et al., Year](https://doi.org/<doi>)`.
- No verbatim abstracts — write fresh TL;DRs.
- No invented DOIs, authors, or dates — omit and note why.
- No paper already in the Hub (the Step-2 exclusion is mandatory).
- No 🤖 on non-small-molecule inputs (protein/RNA/peptide/image/pocket) — surface as context instead.
- No 💻 without an explicit repo URL from the paper.
- No 🌍 promotion of work *about* LMICs without LMIC authorship.
- Don't pad to hit 20–40 — if the topic is sparse, say so.
- No MDPI or other low-tier / pay-to-publish venues unless uniquely load-bearing (the only
  open model/dataset for an endpoint) — and flag those inline as `(⚠ low-tier venue)`. A
  strong preprint beats a weak journal.
