# Digest output template

Exact structure for `digests/YY-MM-DD-literature-digest.md` (local working copy) and
`ersilia-os/digests/literature/YY-MM-DD-literature-digest.md` (canonical remote path).
The local file is a staging area; `scripts/upload_digest.py` publishes it to the remote
repo. Match this verbatim. The skill's "Render" step composes the file by filling these
blocks.

## File header

```markdown
# Ersilia Literature Digest — Week of {YYYY-MM-DD}
```

That's it for the header. **Do not** add a "Covers the 7 days ending..." line, a
"Sources scanned..." line, methodology callouts about how 🤖 is applied, or
any other intro paragraph. The file proceeds directly to the connector
semaphore and legend below. The date in the H1 is the **end** of the date
range. Don't restate marker rules in-document — the legend line says enough
and the reference files carry the detail.

## Connector status (semaphore)

Immediately after the H1, render a single one-line connector semaphore. Use 🟢 for
"fetched data successfully", 🔴 for "failed or skipped", ⚪ for "not triggered"
(only the web-hunt slot uses ⚪). Format — connector name followed by its emoji,
separated by ` · `, with **community-curated sources first**, then literature
APIs, then the supplementary web hunt:

```markdown
**Connectors:** Alerts and Newsletters 🟢 · Slack 🟢 · Europe PMC 🟢 · bioRxiv 🟢 · Web hunt ⚪
```

- Always render all five connector slots in this exact order:
  **Alerts and Newsletters → Slack → Europe PMC → bioRxiv → Web hunt**.
- The four MVP connectors are 🟢 / 🔴 (success / failed-or-skipped); the
  **Web hunt** slot is 🟢 (ran and added items), 🔴 (ran and failed), or ⚪ (not
  triggered — the pool already met the 🤖/🗃️ minima in Step 4.5).
- Use these exact short names. Do not name the Slack workspace/channel, do not name
  the user's email address. The Gmail connector is always labelled
  **"Alerts and Newsletters"**.

## Emoji legend (rendered on every digest)

Three stacked lines, no blank line between them. Each line ends with **two
trailing spaces** so Markdown renders a hard line break and the three lines sit
visually adjacent (no extra vertical gap).

```markdown
**Connectors:** Alerts and Newsletters 🟢 · Slack 🟢 · Europe PMC 🟢 · bioRxiv 🟢 · Web hunt ⚪
**Markers:** ⭐ High impact · 🌍 LMIC · 🤖 Candidate model · 🗃️ Interesting dataset · 💻 Code available
**Tasks:** 🧪 Property · 🎯 Activity · 🧩 Featurization · 🗺️ Projection · 🔍 Similarity · 🎨 Generative
```

Label rules:

- Each label starts with a capital letter.
- Keep labels short: one or two words.
- Marker mapping (`Markers:` line): ⭐ = **High impact** · 🌍 = **LMIC** · 🤖 =
  **Candidate model** · 🗃️ = **Interesting dataset** · 💻 = **Code available**.
- Task mapping (`Tasks:` line and inline trailing labels): 🧪 = **Property**
  (Property prediction or calculation) · 🎯 = **Activity** (Activity prediction)
  · 🧩 = **Featurization** · 🗺️ = **Projection** · 🔍 = **Similarity**
  (Similarity search) · 🎨 = **Generative**.
- The legend uses the short form "Tasks" even though the canonical Hub vocabulary
  calls these *subtasks* — the digest is for fast reading, not metadata
  fidelity.
- Use these exact strings. Do not introduce new emojis without updating this
  legend and the per-entry trailing labels.

## Section structure

The digest opens with **two dedicated Hub chapters** (Models, Datasets) followed
by **four theme chapters** for context items. Six chapters total, fixed order:

1. `## 🤖 Models that could join the Hub` ← **always first**
2. `## 🗃️ Datasets that could join the Hub` ← **always second**
3. `## AI/ML methods for drug discovery`
4. `## Antibiotic and antimicrobial discovery`
5. `## AI agents and foundation models for science`
6. `## Global health and open science`

Go straight from each `##` heading to its bulleted entries — no framing
sentence under the heading, no "intro paragraph". The exception is the
empty-chapter rule for chapters 1 and 2 (see below).

### De-duplication rule (important)

Every 🤖 item lives **only** in chapter 1. Every 🗃️ item lives **only** in
chapter 2. Do **not** duplicate them into chapters 3–6. The reader's mental
model is: *chapters 1–2 = Hub candidates; chapters 3–6 = context.*

A Hub-incorporable model that is *also* a major antimalarial work still goes
**only** in chapter 1 — the body sentence in chapter 1 names the antimalarial
context, but the entry does not appear in chapter 4.

### Empty-chapter rule for chapters 1 and 2

If chapter 1 has zero 🤖 entries after both Step 5 triage and Step 4.5 web hunt,
render the heading anyway with a single-line italic placeholder so the reader
knows the absence is intentional:

```markdown
## 🤖 Models that could join the Hub

_Nothing this week — the pool and the supplementary web hunt did not surface a Hub-incorporable model. Treat as a signal to widen the Gmail / Slack net._
```

Same for chapter 2:

```markdown
## 🗃️ Datasets that could join the Hub

_Nothing this week — no openly-released ≥10k-row datasets cleared the dataset checklist._
```

This is the **only** place in the digest where an empty section is rendered.
Theme chapters 3–6 still follow the "skip if empty" rule — no heading, nothing.

### Chapter 1 internal structure — group 🤖 by Hub task

Group entries under chapter 1 by Hub task family using `###` subheadings, in the
fixed order **Activity → Property → Featurization → Generation → Similarity →
Projection** (descending Hub share). Skip empty subheadings. Within each
subheading, sort by venue tier (NMI / JCIM / J Cheminform / Nat Comms / NAR
before bioRxiv / chemRxiv / arXiv preprints), then by recency.

```markdown
## 🤖 Models that could join the Hub

### 🎯 Activity prediction

- [Bullet …]
- [Bullet …]

### 🧪 Property prediction

- [Bullet …]

### 🧩 Featurization

- [Bullet …]

### 🎨 Generative

- [Bullet …]
```

Use the **task emoji + name** as the `###` subheading so the reader sees both
the icon and the word, matching the legend at the top.

Each 🤖 entry must use the structured body-sentence pattern from `SKILL.md`
Step 5a: **Open-source {task} model taking {input} → {output}; released with
{weights/code} under {license}. Plausible Hub addition because {hook}.** Add
`(weights: pending)` or `(infra: heavy)` qualifiers when applicable.

### Chapter 2 internal structure — group 🗃️ by endpoint family

Group entries under chapter 2 by endpoint family using `###` subheadings:

```markdown
## 🗃️ Datasets that could join the Hub

### Bioactivity datasets

- [Bullet …]

### ADMET / property datasets

- [Bullet …]

### Generative training corpora

- [Bullet …]

### Featurization / multi-task benchmarks

- [Bullet …]

### Other Hub-relevant datasets

- [Bullet …]
```

Each 🗃️ entry must use the structured body-sentence pattern from `SKILL.md`
Step 5b: **{N} compounds / rows · {endpoint} · {license} · {download host}.
Plausible Hub input because {hook}.**

### Theme-chapter placement rules (chapters 3–6)

Items that did **not** earn 🤖 or 🗃️ are placed in chapters 3–6 by theme. No
subheadings inside these chapters — single bullet list per chapter.

- **Chapter 3 (AI/ML methods for drug discovery)** — methodology papers,
  benchmarks, reviews, perspectives, **gated-out models** (protein-conditioned
  generators, structure-only models, non-permissive-license releases,
  image-input models), AI-for-chemistry surveys, retrosynthesis advances,
  virtual-screening protocol papers. The body sentence on a gated-out model
  should name the gating dimension explicitly
  (`(input: protein sequence)`, `(license: CC-BY-NC)`, etc.).
- **Chapter 4 (Antibiotic and antimicrobial discovery)** — disease biology of
  bacterial / mycobacterial / fungal / parasitic / viral pathogens, AMR
  surveillance, AMR policy, pathogen target-structure papers, medicinal-
  chemistry SAR campaigns. Antimicrobial / antipathogen items get an editorial
  bump: rank them above same-tier non-antimicrobial items inside any context
  chapter.
- **Chapter 5 (AI agents and foundation models for science)** — multi-agent
  research systems (Sakana AI Scientist, Co-Scientist, FutureHouse, ChemCrow,
  PaperQA, BioPlanner), scientific copilots, self-driving labs, autonomous
  synthesis, robotic chemistry, closed-loop optimisation, autonomous drug
  discovery. Surface even when not antimicrobial-specific.
- **Chapter 6 (Global health and open science)** — LMIC-led work that doesn't
  belong in chapter 1 or 2, NTDs, capacity-building, AMR/NTD funding/policy,
  open-science infrastructure releases, decolonisation pieces, DNDi / MMV /
  GHIT / GARDP / CARB-X / Schmidt / AI2050 / EDCTP3 outputs.

### Ordering within chapters 3–6

Sort by venue tier (NMI / JCIM / J Cheminform / Nat Comms / NAR / *Nature*
family before bioRxiv / chemRxiv / arXiv preprints), then by recency. Within a
tier, rank antimicrobial / antipathogen items above non-antimicrobial items.

### Trailing task emoji on 🤖 and 🗃️ entries

Every entry that carries 🤖 (candidate model) **must** end its body sentence
with a `·`-separated **task emoji**. Same for 🗃️ (interesting dataset). The
emoji alone is enough — the legend at the top of the file already explains
each one, and the leading 🤖 or 🗃️ marker tells the reader whether the entry
is a model or a dataset. Do **not** repeat the task name in italics — that is
redundant.

```markdown
- [Zhou et al., *Nucleic Acids Res*, 2026-05-19](https://doi.org/10.1093/nar/gkag478) 🤖💻 — **DeepCYP …** body sentence. · 🧪
- [Molaei et al., *Sci Rep*, 2026-05-18](https://doi.org/10.1038/s41598-026-53762-3) 🌍🗃️ — **Synthesis and anti-leishmanial…** body sentence. · 🎯
```

Pick exactly **one** task emoji per entry (the closest fit). When a paper
spans more than one task, prefer the most-specific one and lean on the body
sentence to capture nuance.

| Task emoji | Use for (model in 🤖 entries) | Use for (dataset in 🗃️ entries) |
|---|---|---|
| 🧪 | Property prediction or calculation — ADMET, solubility, permeability, CYP, hERG. | ADMET / toxicity / physicochemical datasets. |
| 🎯 | Activity prediction — QSAR, IC50/MIC/Ki, phenotypic activity. | Bioactivity / phenotypic-screen datasets. |
| 🧩 | Featurization — encoders, foundation models, fingerprints. | Multi-task / mixed-endpoint collections suitable for featurisers. |
| 🗺️ | Projection — 2D/3D embeddings, UMAP/t-SNE, manifold learning. | Structural / pocket / cofolding datasets. |
| 🔍 | Similarity search — ligand-based VS, k-NN, docking surrogates. | Reference libraries for retrieval. |
| 🎨 | Generative — de novo design, scaffold hopping, VAE / diffusion. | Curated chemistry corpora that drive generative training. |

Total items per digest: aim for **25–40** across all chapters, with **≥8 🤖**
in chapter 1 and **≥2 🗃️** in chapter 2 as the minimum healthy week. Density is
the goal; the format below is one line per item. If 🤖 candidates fall below 8
even after the Step 4.5 web hunt, render the empty-chapter placeholder rather
than padding chapter 1 with weak candidates.

## Per-item template (one line per article)

Each item is a single bulleted line. The line has four parts, in fixed order:

```markdown
- [{First Author} et al., *{Venue}*, {YYYY-MM-DD}]({paper_url}) {inline emoji ribbon} — **{Title}.** {Combined "why it matters for Ersilia" + TL;DR in 1–2 short sentences.} {trailing extras}
```

Components:

1. **Citation as link** — `[Author et al., Venue, YYYY-MM-DD](paper_url)`. Markdown
   link text uses the canonical short citation, **with the exact ISO date** when
   known (publication date for journal items; posting date for preprints). If
   the day is genuinely unknown — Crossref only reports the month — fall back to
   `YYYY-MM`. Never invent a day. Single-author papers drop "et al.". The `Venue`
   is italicised inside the link text.
2. **Emoji ribbon** — zero or more curation markers, concatenated with no separator,
   placed right after the link and before the em-dash. Use the fixed display order
   (see below).
3. **Title** in bold, ending with a period.
4. **One-or-two-sentence body** combining *why it matters for Ersilia* with a tiny
   TL;DR. Required. Be specific (name the Hub model, NTD pipeline, partner
   institution). If you cannot write a credible one-liner, drop the item.
   - **🤖 entries** use the structured Step 5a pattern: *Open-source {task}
     model taking {input} → {output}; released with {weights/code} under
     {license}. Plausible Hub addition because {hook}.*
   - **🗃️ entries** use the structured Step 5b pattern: *{N} compounds / rows ·
     {endpoint} · {license} · {download host}. Plausible Hub input because
     {hook}.*
   - **Context entries** (chapters 3–6) keep a free-form one-or-two-sentence
     body. For gated-out models, name the gating dimension in parentheses
     (e.g. `(input: protein sequence)`, `(license: CC-BY-NC)`).
5. **Trailing extras** (optional, appended after the body sentence, separated by `·`):
   - `[code]({code_url})` when an open-source repo is linked from the paper.
   - `[preprint]({preprint_url})` when the entry is the published version and a
     preprint URL is also useful.
   - **No sharer attribution.** Do not surface that an item was shared internally
     via Slack, by whom, or via which Gmail alert / newsletter sender. The digest
     is read on a public repo; it must not out internal team members or expose
     internal channel names. The fact that an item is in the digest is enough.

### Per-item curation markers

Up to **five** optional markers may appear inline in the emoji ribbon. Fixed display
order: **⭐ 🌍 🤖 🗃️ 💻** (impact → equity → model → dataset → code).

| Marker | Meaning | When to apply |
|---|---|---|
| ⭐ | Very-high-impact journal | Venue is in the "Starred journals" list in `search-landscape.md`. Preprints never warrant ⭐ on their own. |
| 🌍 | LMIC-led work | First OR senior author at a World Bank low/lower-middle-income institution (see `lmic-countries.md`). |
| 🤖 | Model/tool potentially incorporable into the Ersilia Model Hub | Open-source or openly distributable model with a clear inference interface; task fits the Hub taxonomy. Skip if closed, irreproducible, or commercial-only. |
| 🗃️ | Dataset useful for training or evaluating Hub models | Openly downloadable; covers a Hub-relevant endpoint; large/labelled enough to train or benchmark. **Prefer big, well-established corpora** (tens of thousands of compounds upwards; clear public release; venue with citation traction). Examples this week: COMPASS (75k AMPs, *npj AMR*), QuantumPioneer (Coley/Kraft reaction QM corpus). Small, single-target or single-paper datasets rarely warrant 🗃️ on their own. Skip purely descriptive (non-ML-trainable) datasets. |
| 💻 | Open code linked from the paper | The paper links to a public, runnable code repository (GitHub, GitLab, Codeberg, etc.). 💻 is applied **only when code existence is verified** — i.e. the abstract or paper text explicitly mentions a repo URL, or Crossref/OpenAlex metadata flags an open code object. Crossref abstracts often omit code mentions, so when the abstract is silent, fetch the paper page (or `data availability` block) before applying 💻. **Default-off**: if you cannot point at a specific URL, do not apply 💻 — false positives are worse than omission. When a URL *is* surfaced, also append `[code](...)` to the trailing extras. |

Markers are editorial — apply them only when they're load-bearing. Do not sprinkle.
A *Nature Methods* paper that releases an open Plasmodium ADMET model trained on a new
Hub-ready dataset, led by a Cameroonian lab, with code on GitHub, would carry
**⭐🌍🤖🗃️💻**.

## Worked examples

**A 🤖 entry in chapter 1 → Featurization subheading:**

```markdown
## 🤖 Models that could join the Hub

### 🧩 Featurization

- [Wadell et al., *arXiv*, 2025-10-23](https://arxiv.org/abs/2510.18900) 🤖💻 — **Foundation Models for Discovery and Exploration in Chemical Space (MIST).** Open-source featurization model taking SMILES → 512-d embedding; released with weights on HuggingFace and inference code on GitHub under Apache-2.0. Plausible Hub addition because it benchmarks above ChemBERTa-2 on 400+ tasks, including MIC against ESKAPE pathogens. · [code](https://github.com/example/mist) · 🧩
```

**A 🤖 entry in chapter 1 → Activity subheading (LMIC-led):**

```markdown
### 🎯 Activity prediction

- [Mottin et al., *ACS Med Chem Lett*, 2026-04-18](https://doi.org/example) 🌍🤖 — **Antimalarial pyrazole optimisation with AI-aided SAR.** Open-source activity-prediction model taking SMILES → *Plasmodium falciparum* 3D7 EC50; released with weights and training code under MIT. Plausible Hub addition because it covers an MMV1794-adjacent scaffold and complements existing antimalarial Hub coverage. · [code](https://github.com/example/pf-pyrazole) · 🎯
```

**A 🗃️ entry in chapter 2 → Bioactivity datasets subheading:**

```markdown
## 🗃️ Datasets that could join the Hub

### Bioactivity datasets

- [Augustine et al., *npj AMR*, 2026-03-12](https://doi.org/example) 🗃️💻 — **COMPASS: a curated antimicrobial-peptide bioactivity corpus.** 75,000 rows · MIC against ESKAPE panel · CC-BY-4.0 · Zenodo. Plausible Hub input because AMP-MIC datasets at this scale are rare and the panel matches the active Ersilia AMR pipeline. · [code](https://github.com/example/compass) · 🎯
```

**A context entry in chapter 5 (no 🤖):**

```markdown
## AI agents and foundation models for science

- [Gottweis et al., *Nature*, 2026-02-19](https://www.nature.com/articles/s41586-026-10644-y) ⭐ — **Accelerating scientific discovery with Co-Scientist.** Multi-agent research assistant validated on drug-repurposing and AMR case studies that overlap the Ersilia AMR pipelines directly; the workflow is worth dissecting for an open-source reimplementation.
```

**A gated-out model in chapter 3 (chapter 3, not chapter 1):**

```markdown
## AI/ML methods for drug discovery

- [Liu et al., *Nature Methods*, 2026-04-02](https://doi.org/example) ⭐💻 — **TargetDiff-2: pocket-conditioned diffusion for ligand design.** State-of-the-art structure-based generator producing competitive *in silico* hit rates against *Mtb* InhA; weights under Apache-2.0. (Input: pocket point-cloud — Hub-eligible once protein-input support lands.) · [code](https://github.com/example/targetdiff-2)
```

## Field rules

- **Author line**: name the **first** author + "et al." Add the **senior** (last) author
  in parentheses only if their name carries notable signal for the team (e.g. Chibale,
  Aloy, Baker, Leskovec). Otherwise omit to keep the line compact.
- **Body sentence**: 1–2 short sentences. Combine "why it matters for Ersilia" with a
  micro-TL;DR. Write fresh — never paste the abstract verbatim. If you cannot write a
  credible one-liner, the item does not belong in the digest.
- **Body language rules** — non-negotiable, the digest is on a public repo:
  - **Never name a team member.** Not Miquel, not Gemma, not any other internal
    name. Refer to the organisation impersonally ("Ersilia", "the Ersilia Model
    Hub", "an Ersilia pipeline").
  - **Never name an internal Slack channel** or any other internal forum. Don't
    write `#literature`, `#research`, or similar.
  - **No first-person plural.** Replace "our pipeline", "we should", "the team
    is reading" with impersonal phrasing ("the Ersilia Model Hub", "this
    informs", "worth reading").
  - Grant identifiers used externally (e.g. *E-AMR-CC*, *AI2050*) are fine —
    they appear in publicly-available proposals.
- **Emojis**: only the five per-item markers (⭐🌍🤖🗃️💻), in fixed display order,
  inline in the ribbon. Plus 🟢/🔴 in the connector-status block. No others.
- **Code presence detection**: 💻 is allowed when (a) the paper text or abstract
  explicitly mentions a public repo URL, OR (b) Crossref / OpenAlex metadata flags an
  open code object. When in doubt, leave it off — false positives are worse than
  omission.

## Footer

There is no footer. The file ends after the last chapter's last bullet. **Do not**
write a "Methodology notes" block, a "Suggested follow-ups" block, a horizontal
rule, or any other closing material. The connector semaphore at the top already
tells the reader which sources ran; the entries themselves are the deliverable.
