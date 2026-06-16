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

Conduct rigorous, comprehensive literature research for Ersilia's drug discovery mission
— focused on neglected tropical diseases (NTDs), antimicrobial resistance (AMR), and
AI/ML-driven drug discovery for global health.

The research question may be a disease, a protein target, a compound class, an ML method,
or a combination. The output is a well-cited synthesis with 20–40 curated papers, a
curation marker on each entry (🤖, 🌍, 🗃️, 💻, ⭐), and a written markdown report.

---

## Inputs

The user will invoke this skill with:

- A research topic (required): disease, target, method, or compound class.
- (optional) A date range, e.g. `--from 2020-01-01 --to 2025-12-31`. Default: last 5 years.
  Foundational / landmark papers (original target structure, seminal resistance mechanism,
  field-defining method) are **exempt** from this window — include them regardless of age and
  mark them as seminal.
- (optional) `--depth focused` to cap at 8–15 papers and run faster (default is comprehensive: 20–40 papers).
- (optional) `--out <path>` to override the default output file location.

If the topic is ambiguous, ask one focused question before searching. Never invent missing inputs.

---

## Reference files

Read these before starting any search:

- `references/hub-incorporation-criteria.md` — empirical priors for 🤖 (small-molecule-input gate, subtask taxonomy, venue priors). Read before triage.
- `references/lmic-countries.md` — World Bank low/lower-middle income countries (the 🌍 rule).
- `references/apis.md` — PubMed, Europe PMC, bioRxiv/ChemRxiv endpoint formats. Read before any API call.

---

## Workflow

### Step 1 — Parse the query

Identify:

- **Primary entity**: disease (*M. tuberculosis*, malaria), target protein (PfDHFR, TryR, InhA),
  compound class (AMPs, antimalarials, nitroaromatics), or ML method (GNN, ChemBERTa, REINVENT).
- **Research angle**: biology/mechanism, drug discovery assays, AI/ML models, clinical findings,
  open datasets, ADMET.
- **Scope signals**: LMIC-first framing? A comparison of methods? A target-specific deep dive?
  A biology/mechanism focus vs. a computational-methods focus?

Map the entity to Ersilia disease priorities (see reference files); note Hub subtasks where
relevant, but treat them as a tag, not the organising principle of the review.

---

### Step 2 — Multi-source search

Run searches across all four sources. Use `web_search` as the primary tool; supplement with
API calls (bash subprocess) where the domains are accessible — see `references/apis.md` for
exact endpoint formats.

| Source | web_search prefix | Best for |
|---|---|---|
| **Nature / Nature family** | `site:nature.com` | High-impact biology, chemistry, AI — search first |
| **Science / Science family** | `site:science.org` | High-impact biology, chemistry, AI — search first |
| **Cell / Cell Press** | `site:cell.com` | High-impact biology, disease mechanisms — search first |
| **PubMed / MEDLINE** | `site:pubmed.ncbi.nlm.nih.gov` | Peer-reviewed biology, pharmacology, clinical |
| **Europe PMC** | `site:europepmc.org` | Open-access full text, preprints + journals |
| **PLOS** | `site:journals.plos.org` | NTDs (PLOS Negl. Trop. Dis.), pathogens, global-health medicine |
| **bioRxiv** | `site:biorxiv.org` | AI/ML preprints, computational biology |
| **ChemRxiv** | `site:chemrxiv.org` | Chemistry and ADMET preprints |
| **arXiv** | `site:arxiv.org` | ML-method preprints (cs.LG) — new architectures not on bioRxiv |

Search **Nature, Science, and Cell first** — landmark papers here set the framing for the rest of the review.

**Minimum search coverage:**

Run at least **4 query variants across the sources** (~30 searches total). Mix — and keep the
balance, do not let the computational variants crowd out the biology/clinical layer that
anchors a literature review:

1. **Biology / mechanism**: `<disease/target> mechanism resistance pathogenesis review`
2. **Narrow**: `<target/disease> <specific subtask> drug discovery`
3. **Broad**: `<disease family> AI machine learning compound`
4. **Method-facing**: `<method type> ADMET activity prediction <disease>`

Run every variant against the general sources (Nature, Science, Cell, PubMed, Europe PMC). Route
the specialized sources to where they pay off: **PLOS** for variants 1–2 (NTD biology / drug
discovery), **arXiv** for variants 3–4 (ML methods), **bioRxiv/ChemRxiv** for the computational
and chemistry variants.

**Example queries for PfDHFR:**
```
site:pubmed.ncbi.nlm.nih.gov PfDHFR inhibitor malaria drug discovery
site:europepmc.org PfDHFR antifolate resistance Plasmodium falciparum
site:biorxiv.org DHFR malaria machine learning activity prediction
site:chemrxiv.org dihydrofolate reductase antimalarial QSAR 2023
site:pubmed.ncbi.nlm.nih.gov antifolate Plasmodium drug resistance mechanism
site:europepmc.org malaria drug discovery AI deep learning SMILES
...
```

After `web_search`, use `web_fetch` on individual paper pages to retrieve full abstracts
when snippets are too short. Also use `web_fetch` on Europe PMC / PubMed landing pages
to get complete metadata (authors, journal, year, DOI).

**Target raw pool**: 40–80 raw results before screening.

**Citation snowballing.** Database keyword search alone misses foundational work. After the
initial searches, take the 2–3 strongest reviews or landmark papers in the pool and scan their
reference lists for works that are repeatedly cited but not yet in your pool — fetch the review
page (or its references via Crossref `is-referenced-by-count` / the reference list) and add the
recurring citations. This backward search is the main way seminal older papers enter the review.

---

### Step 3 — Verify metadata via Crossref

Before composing any entry, verify the first-author surname and publication date via
Crossref:

```bash
curl -s "https://api.crossref.org/works/<doi>"
```

Use `message.author[0].family` and `message.published["date-parts"][0]` as canonical
values. When only the title is known:

```bash
curl -s "https://api.crossref.org/works?query.title=<title>&filter=container-title:<journal>"
```

If lookup fails, omit the author rather than guessing. Never fabricate author names or dates.

**Canonical URL** — once the DOI is confirmed via Crossref, set the entry URL to
`https://doi.org/<doi>`. This resolves to the publisher's landing page and is the only
reliable permanent link. For preprints without a DOI, use the direct biorxiv/chemrxiv
paper page URL (e.g. `https://www.biorxiv.org/content/<id>`). Never use search-result
pages, PubMed search URLs, or any URL that does not resolve directly to the paper itself.

---

### Step 4 — Screen and tier

**Deduplicate first.** The same work often appears multiple times in the raw pool — most
commonly a preprint (bioRxiv/ChemRxiv) and its later journal version. Collapse these to a
single entry, preferring the peer-reviewed published version (and its DOI); keep the preprint
only if no published version exists. Also merge near-identical titles from different sources.

Then apply filters in order:

**Filter A — scope.** An item must fit at least one of three buckets:
1. **Antibiotic / antimicrobial / AMR drug discovery** — TB, NTD antibacterials, AMP / peptide
   antibiotic work, AMR surveillance with an ML hook.
2. **Global health / LMIC drug discovery / open-science capacity-building** — NTDs (malaria,
   leishmaniasis, HAT, schistosomiasis, Chagas), Africa/LMIC-led work, public datasets or open
   infrastructure releases.
3. **General-purpose AI methods for drug discovery** — featurizers, ADMET and toxicity
   predictors, generative chemistry, CPI/docking surrogates, synthesis planning, multi-task
   chemistry foundation models, open chemistry datasets, methodology reviews.
4. **Foundational biology / mechanism / epidemiology of a priority pathogen or target** —
   target structure and druggability, resistance mechanisms, host–pathogen biology, disease
   burden and epidemiology. These anchor the review even without a drug-discovery or ML hook,
   provided the pathogen or target is an Ersilia priority.

Borderline cancer / cardiology / diabetes papers do **not** qualify unless they introduce a
general-purpose tool with clear applicability to Ersilia targets, or concern a priority
pathogen/target under bucket 4.

**Filter B — Hub-incorporability tag.** Re-read `references/hub-incorporation-criteria.md`.
Apply the 🤖 marker using its exact rules (small-molecule-input gate, six subtask taxonomy,
open code/weights requirement). This is a useful relevance signal for items that pass scope,
not a curation gate — a paper does not need to be Hub-incorporable to belong in the review.

**Tier each survivor:**

| Tier | Criteria | Include? |
|---|---|---|
| **1** | Directly addresses the query entity with experimental or model validation data (an open model/dataset release is one such case, not a privileged one) | Always |
| **2** | Reviews, methodology papers, or datasets with strong relevance to Ersilia's work | Include if space (after Tier 1) |
| **3** | Tangential, low quality, or duplicate | Skip |

**Target final set**: 20–40 papers (or 8–15 in `--depth focused` mode).

**Equity check.** Apply the LMIC lens last:
- Apply 🌍 per the rule in `references/lmic-countries.md` (first or last author at an LMIC
  institution).
- Give 🌍 items a ranking bonus when near tie-breaks.
- If a paper addresses LMIC pathogens but has no LMIC authorship, note it under
  "Known gaps" rather than promoting it.

**Coverage self-check.** Before writing, verify the final set isn't lopsided. Ask:
- Are both layers represented — foundational biology/mechanism *and* drug-discovery/methods?
- Are the major sub-areas of the topic covered, or is one angle over-represented?
- Are the main research groups / labs working on this target or disease present?
- Is anything obviously missing (a known landmark paper, a key method, a recent breakthrough)?

If a gap shows up, run targeted follow-up searches to fill it before proceeding. Note any gap
you cannot fill under "Known gaps" rather than papering over it.

---

### Step 4.5 — Find a lifecycle or pathway diagram

Before writing the synthesis, search for an open-access image that shows the disease
lifecycle, infection pathway, or target mechanism — and annotate which stages active
compound classes act on.

**Search strategy (in order of preference):**

1. **Wikimedia Commons** — `site:commons.wikimedia.org <disease> lifecycle` or
   `site:commons.wikimedia.org <disease> pathway`. Prefer SVG or high-res PNG files
   with a CC or public-domain licence.
2. **CDC / WHO public image libraries** — `site:cdc.gov <disease> life cycle`,
   `site:who.int <disease> diagram`.
3. **KEGG / WikiPathways** — for target-level pathway diagrams when the query is a
   specific protein or metabolic pathway.

**URL validation** — use `web_fetch` on the candidate image URL to confirm it resolves
to an actual image file (ends in `.png`, `.svg`, `.jpg`, or `.gif`). Never link to a
page that displays an image; link only to the raw image file URL. If no verified direct
image URL is found, fall back to a text-based stage table (see below) rather than
using an unverified link.

**Compound-stage annotation** — regardless of whether an image is found, produce a
markdown table mapping each lifecycle or pathway stage to the compound classes known
to act there. Derive this from the curated papers and established pharmacology:

| Stage | Description | Active compound classes | Example drugs / leads |
|---|---|---|---|
| ... | ... | ... | ... |

Include this table below the image (or in place of it if no image is available).

---

### Step 5 — Synthesise the report

Structure the synthesis around these sections (adapt to the specific query):

1. **Lifecycle / Pathway Diagram** — embed the verified image (or stage table) from
   Step 4.5. Include the source attribution on the line below the image.
2. **Overview** — High-level picture, key open questions, why this topic matters for
   global health and Ersilia specifically.
3. **Disease / Target Biology** — Mechanism of action, druggability, known resistance
   issues. Cite landmark papers.
4. **Drug Discovery Approaches** — Assays, screening campaigns, known scaffolds / lead
   series.
5. **AI/ML Methods** — Models applied to this target or disease, key datasets, benchmark
   results. Cover the methods landscape broadly; note where a tool is Hub-relevant (🤖) but
   don't restrict the section to Hub candidates. Mention any notable open dataset (🗃️) inline
   here rather than in a dedicated section.
6. **Research Gaps** — What is missing, understudied, or contradicted in the literature.
   Call out LMIC authorship gaps explicitly.

Write in clear scientific prose. Every factual claim carries an inline citation:
`(Author et al., Year, PMID/DOI)`.

**Surface consensus vs. disagreement.** A good review does not just list findings — it states
where the literature *agrees* and where it *conflicts*. Where you find contested mechanisms,
inconsistent activity/potency data, or failed replications, say so explicitly and cite the
competing papers side by side, rather than presenting one side as settled.

---

### Step 6 — Compose each curated entry

For every paper in the final set, compose a one-line entry in this format:

```
[Author et al., *Venue*, YYYY](url) {ribbon} — **Title.** TL;DR + why it matters for Ersilia.
```

**Curation markers** (ribbon, fixed display order `⭐🌍🤖🗃️💻`):

| Marker | When to apply |
|---|---|
| ⭐ | Very-high-impact venue: Nature, Science, Cell, PNAS, NMI, NEJM, Lancet, JACS, Angewandte Chemie, Nature/Science/Cell family |
| 🌍 | First or last author at an LMIC institution (see `references/lmic-countries.md`) |
| 🤖 | Hub-incorporable model — small-molecule input, one of six subtasks, openly available (see `references/hub-incorporation-criteria.md`) |
| 🗃️ | Releases a notable open dataset relevant to Ersilia targets (bioactivity/ADMET). Secondary signal — apply when clear, don't hunt for it |
| 💻 | Abstract or paper page explicitly names a public repo URL — do not infer |

**Entry rules:**

- `TL;DR` — 1–2 sentences, plain language, written fresh. Never paste the abstract verbatim.
- `Why it matters for Ersilia` — required, one sentence, specific. Name the Hub subtask,
  NTD pipeline, partner institution, or open-science release.
- `Author` — verified via Crossref (see Step 3). Omit if lookup fails.
- Venue — journal or preprint server, verified.
- `url` — must be `https://doi.org/<doi>` for published papers, or the direct preprint page
  for preprints. Never link to a search result page, a PubMed search URL, or any intermediary
  that is not the paper itself. If no verified URL exists, omit the hyperlink entirely rather
  than linking to the wrong page.
- Within each section, sort by relevance to the query, then by venue tier, then by recency.
- Only apply a marker when the criterion is load-bearing. Absent is better than wrong.

---

### Step 7 — Write and surface output

**Markdown file** — write to:
```
/mnt/user-data/outputs/literature_<topic>_<YYYYMMDD>.md
```
(Use the topic slug and today's date.)

Use the output template:

```markdown
# Literature Research: [Topic]
*Generated: [Date] | Sources: Nature, Science, Cell, PubMed, Europe PMC, PLOS, bioRxiv, ChemRxiv, arXiv | Papers: N*

---

## Lifecycle / Pathway Diagram

![Disease lifecycle](image_url)
*Source: [Title / licence](source_url)*

**Compound action by stage:**

| Stage | Description | Active compound classes | Example drugs / leads |
|---|---|---|---|
| ... | ... | ... | ... |

> If no verified direct image URL was found, omit the `![]()` line and keep only the table.

## Overview
[2–3 paragraphs]

## Disease / Target Biology
[With citations]

## Drug Discovery Approaches
[With citations]

## AI/ML Methods
[With citations — broad methods coverage; tag Hub-relevant tools 🤖; mention 🗃️ datasets inline]

## Research Gaps
[Including LMIC authorship gaps]

---

## Curated Entry List

### Tier 1 — Core papers
- [Author et al., *Venue*, YYYY](url) ⭐🌍🤖 — **Title.** TL;DR. Why it matters for Ersilia.

### Tier 2 — Supporting papers
- [Author et al., *Venue*, YYYY](url) — **Title.** TL;DR. Why it matters for Ersilia.

---

## Known Gaps
- [LMIC authorship gaps, missing experimental data, understudied angles]

## Search Log
| Source | Query | Results retrieved |
|---|---|---|
| Nature | ... | N |
| Science | ... | N |
| Cell | ... | N |
| PubMed | ... | N |
| Europe PMC | ... | N |
| PLOS | ... | N |
| bioRxiv | ... | N |
| ChemRxiv | ... | N |
| arXiv | ... | N |
```

Call `present_files` immediately after writing to surface the download link.

**In-chat summary** — after presenting the file, write a concise in-chat block with:

1. A one-paragraph synthesis (the "so what" for Ersilia) — the key findings of the review.
2. The 2–3 most important papers (any tier) with one line each on why.
3. The most important gap, in one sentence.
4. Secondary callouts, only if present: Hub candidates (🤖) and LMIC-led papers (🌍), each as
   a short bulleted list.

---

## Ersilia context

**Priority diseases / organisms**
- *Mycobacterium tuberculosis*, *M. abscessus* (TB, AMR)
- *Plasmodium falciparum*, *P. vivax* (malaria)
- *Leishmania* spp. (leishmaniasis)
- *Trypanosoma cruzi* (Chagas), *T. brucei* (sleeping sickness / HAT)
- *Schistosoma mansoni* (schistosomiasis)
- ESKAPE pathogens, GLASS AMR priority list

**Hub subtask taxonomy** (from `references/hub-incorporation-criteria.md`)
- Activity prediction (41 % of Ready models — highest prior)
- Featurization (25 %)
- Property calculation / prediction (20 %)
- Similarity search (6 %)
- Generation (5 %)
- Projection (3 %)

**Relevant AI/ML model types**
- QSAR (RF, XGBoost, SVM)
- Graph neural networks (GNN, MPNN, AttentiveFP)
- Transformers (ChemBERTa, MolBERT, Uni-Mol)
- Generative models (VAE, diffusion, REINVENT)
- ADMET predictors, bioactivity classifiers, docking surrogates

**Key databases to mention where relevant**
ChEMBL · BindingDB · ZINC · PubChem · Open Targets · MMV/DNDi compound sets

**Framing priorities**
- Open-source tools and reproducible workflows
- Low-data / few-shot regimes
- Resource-limited setting applicability
- Models available in or compatible with the Ersilia Model Hub

---

## Things to avoid

- Do not include items you cannot link to a primary source.
- Do not paste abstracts verbatim — write fresh TL;DRs.
- Do not invent or guess DOIs, authors, or dates. If uncertain, omit and note why.
- Do not promote work *about* LMICs without LMIC authorship into the equity section.
- Do not apply 🤖 to models with non-small-molecule primary inputs (protein, RNA, peptide,
  image, pocket-tensor). Surface them as context items instead.
- Do not apply 💻 without an explicit public repo URL from the paper.
- Do not pad to hit the 20–40 target — if the week or topic is sparse, say so.
- Do not embed a diagram image URL that has not been verified to resolve to a raw image file
  (`.png`, `.svg`, `.jpg`, `.gif`). If the URL resolves to an HTML page, use the stage table
  instead.
- Do not link to search-result pages, PubMed search URLs, or any URL that is not the paper
  itself. Every link must resolve directly to the paper's landing page — use `https://doi.org/<doi>`
  for published work, or the direct preprint URL for preprints. If no verified direct URL is
  available, omit the link rather than using a proxy or search page.
