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
"fetched data successfully", 🔴 for "failed or skipped". Format — connector name
followed by its emoji, separated by ` · `, with **community-curated sources first**:

```markdown
**Connectors:** Alerts and Newsletters 🟢 · Slack 🟢 · Europe PMC 🟢 · bioRxiv 🟢
```

- Always render all four MVP connectors, even if one was 🔴. Order is fixed:
  **Alerts and Newsletters → Slack → Europe PMC → bioRxiv** (community-curated
  signal first, then the literature APIs).
- Use these exact short names. Do not name the Slack workspace/channel, do not name
  the user's email address. The Gmail connector is always labelled
  **"Alerts and Newsletters"**.

## Emoji legend (rendered on every digest)

Three stacked lines, no blank line between them. Each line ends with **two
trailing spaces** so Markdown renders a hard line break and the three lines sit
visually adjacent (no extra vertical gap).

```markdown
**Connectors:** Alerts and Newsletters 🟢 · Slack 🟢 · Europe PMC 🟢 · bioRxiv 🟢
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

Group items into a small number of **theme chapters**, one `##` heading each.
Use the chapter list below verbatim, in this fixed display order. Skip empty
chapters — **do not** write a placeholder ("nothing this week") and **do not**
write a framing sentence under the heading. Go straight from `##` to the
bulleted entry list.

1. `## AI agents and foundation models for science`
2. `## AI/ML methods for drug discovery`
3. `## Antibiotic and antimicrobial discovery`
4. `## Global health and open science`

### Placement rules

Items are placed **only by theme**. The 🤖 marker and the inline task label do
the work of flagging Hub-relevance; there is **no dedicated chapter** for
candidate models or datasets — they are distributed across the four theme
chapters wherever they topically fit.

- Agentic AI, AI-for-science, scientific co-pilots, foundation models for
  science → **chapter 1**.
- Method advances in drug discovery — cofolding benchmarks, generative chemistry,
  ADMET prediction, virtual-screening tools, featurizers, foundation models for
  small molecules. **🤖 items most often land here** when the model is a generic
  drug-discovery method. → **chapter 2**.
- Antibacterial / antimicrobial chemistry, AMR target biology, structural biology
  of pathogen proteins, ESKAPE / *Klebsiella* / *Acinetobacter* etc. →
  **chapter 3**.
- LMIC-led work, NTDs, capacity-building, AMR policy, open-science
  infrastructure, decolonisation, equity. 🌍 items most often land here. →
  **chapter 4**.

A 🤖 paper on an antimalarial activity model goes in chapter 2 (method) or
chapter 4 (global health) depending on whether the contribution is the
method or the disease focus — pick whichever the body sentence emphasises. When
in doubt, prefer the chapter that gives the reader the most context.

### Ordering within a chapter

Entries inside a chapter are sorted **🤖 candidate models first**, then the
rest. A reader scanning the digest for Hub-incorporable work should see those
items before reviews, perspectives, and context pieces.

Inside the 🤖 block, sort by venue tier (NMI / JCIM / J Cheminform / Nat
Comms / NAR before bioRxiv / chemRxiv / arXiv preprints), then by recency. The
hub-incorporation prior in `hub-incorporation-criteria.md` is the reference for
which venues count as "Hub-feeder" — apply that list, not personal taste.

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

Total items per digest: aim for **25–40** across all chapters, with at least a
third carrying 🤖 in a healthy week. Density is the goal; the format below is
one line per item. If 🤖 candidates fall well below a third, that is a signal
to widen the Gmail / Slack net rather than to pad the digest.

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

```markdown
- [Gottweis et al., *Nature*, 2026](https://www.nature.com/articles/s41586-026-10644-y) ⭐ — **Accelerating scientific discovery with Co-Scientist.** Multi-agent research assistant validated on drug repurposing and AMR case studies that overlap the Ersilia AMR pipelines directly; the workflow is worth dissecting for an open-source reimplementation.

- [Wadell et al., *arXiv*, 2025](https://arxiv.org/abs/2510.18900) 🤖💻 — **Foundation Models for Discovery and Exploration in Chemical Space (MIST).** Open molecular foundation model benchmarked on 400+ tasks — a credible drop-in featurizer for the Ersilia Model Hub. · [code](https://github.com/example/mist)

- [Mottin et al., *ACS Med Chem Lett*, 2026](https://doi.org/example) 🌍🤖 — **Antimalarial pyrazole optimization with AI-aided SAR.** LMIC-led work on a scaffold adjacent to MMV1794; the released surrogate model is small enough to import into the Hub as a Plasmodium-prioritisation classifier.
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
