---
name: paper-summary
description: >
  Summarise a scientific paper PDF and assess its relevance to the Ersilia Model Hub.
  Reads the PDF, extracts title/authors/key contributions, searches the Hub for similar
  existing models, and produces a structured report in one of two modes: short (3–5
  sentence summary + bullet-point relevance verdict) or extended (abstract-like summary
  + deep relevance analysis including added value over existing Hub models). Use whenever
  a user provides a PDF and asks "is this relevant for Ersilia?", "summarise this paper",
  "should we incorporate this model?", "what is this paper about?", or any equivalent
  phrasing in an Ersilia context.
---

# Paper Summary & Ersilia Hub Relevance Assessor

Read a PDF and produce a structured report — factual summary plus a reasoned verdict on
whether the paper's model (or dataset) is a candidate for Ersilia Model Hub incorporation.

Two output modes are available:
- **`--short`** (default): 3–5 sentence summary + bullet-point relevance verdict. Fast triage read.
- **`--extended`**: abstract-like summary (longer, written in your own words — not the verbatim abstract) + in-depth relevance analysis including what the model adds over existing Hub models.

If the user does not specify a mode, use `--short`.

---

## What you receive

- **PDF** (required): either a local file path to the paper, or a PDF attached directly to the conversation.
- **Mode** (optional): `--short` (default) or `--extended`.

Determine the PDF source in this order:
1. **Attached PDF** — if the user attached a file to the conversation message, use it directly. The content is already available in context; no Read tool call is needed.
2. **File path** — if the user provided a local path (e.g. `/home/user/paper.pdf`), use the Read tool on that path.

If neither is present, ask the user to either attach the PDF or provide its path. Do not invent a path.

---

## Step 1 — Read the paper

Use the Read tool on the PDF. Extract:

| Field | What to look for |
|---|---|
| **Title** | Exact paper title |
| **Authors** | First author + "et al." if more than two |
| **Year / Venue** | Publication year and journal or preprint server |
| **Primary contribution** | What the paper actually releases: a model, a dataset, both, or neither |
| **Input modality** | What the model takes as input (SMILES, protein sequence, image, etc.) |
| **Task** | What the model does (activity prediction, featurization, ADMET, generation, etc.) |
| **Biological / disease endpoint** | Which disease, target, or property is addressed |
| **Availability** | Is code/weights/web server openly available? Where? |
| **Links** | All explicit URLs or package names in the paper: code repo, web server, data download, PyPI/conda package, Zenodo DOI. Copy them verbatim; do not invent or expand. |
| **Key results** | One or two headline performance numbers (AUC, RMSE, accuracy, R²) |

---

## Step 2 — Search the Hub for similar models

First, ensure `ersilia_search` is installed:

```bash
pip install -q git+https://github.com/ersilia-os/search-engine.git
```

If installation fails, note the error in the report and skip to Step 3.

Then run `ersilia_search` to find existing Hub models that overlap with this paper's
contribution. Always use `--limit 20` to avoid missing closely related models. **Always
run two searches, and always add `--all-statuses` to both:**

1. **Task/endpoint query** — generic terms for what the model does:
   ```bash
   ersilia_search --text "<task> <endpoint>" --limit 20 --all-statuses
   ```
   Examples:
   - `ersilia_search --text "antimalarial activity prediction" --limit 20 --all-statuses`
   - `ersilia_search --text "molecular featurization ADMET" --limit 20 --all-statuses`
   - `ersilia_search --text "tuberculosis MIC prediction" --limit 20 --all-statuses`

2. **Method-name query** — the paper's own tool/model name, which may be the exact
   string used when it was incorporated:
   ```bash
   ersilia_search --text "<tool or model name from paper>" --limit 20 --all-statuses
   ```
   Example: if the paper introduces "ChemBERTa", run `ersilia_search --text "ChemBERTa" --limit 20 --all-statuses`.

**Why `--all-statuses` is mandatory, not optional.** Without it, the tool silently
restricts results to `Ready` models only. A paper's model can already be sitting in the
Hub's incorporation pipeline as `In progress` or `In maintenance`, or have been previously
incorporated and later `Archived` — and none of those show up in a default search. Missing
this makes the assessment actively wrong: it presents a paper as a fresh, unclaimed
candidate when the team is already working on it (or already decided to drop it). Always
pull all four statuses (`Ready`, `In progress`, `In maintenance`, `Archived`) and report
the status of every match.

**Non-Ready entries are often metadata-thin.** Models still `In progress` frequently have
an empty Description/Task/Subtask (only a Title and GitHub link exist yet), so a
keyword/description-based text query can miss them even with `--all-statuses` set. If the
paper's method name is distinctive, cross-check it directly with a status filter, e.g.:
```bash
ersilia_search --status "In progress" --status "In maintenance" --status "Archived" --limit 200 --csv
```
and grep the output for the method/tool name or close variants. Do this whenever the
task/method-name queries come back thin or ambiguous — don't rely on text relevance
ranking alone to surface sparse in-progress rows.

**Important — truncated titles.** The `ersilia_search` table truncates long titles with
`…`. Never expand a truncated title or infer what it says — use only the visible characters
plus the model ID. If a title is truncated and looks potentially relevant, treat it as
tentative until you have verified the full name (e.g. by noting in the report that the
full title could not be confirmed from the search output). Do not fabricate a plausible-
sounding expansion. Use `--csv` when you need the untruncated Title/Description/Status
columns instead of the rendered table.

Read all result sets. Note any models that overlap in task + endpoint, **regardless of
status**. Record their `Identifier` (e.g. `eos4ywv`), the visible (possibly truncated)
title, and their `Status`.

---

## Step 3 — Apply the Hub relevance criteria

Use the criteria in `references/hub-incorporation-criteria.md` to assess the paper.
Work through these questions in order — stop as soon as you hit a hard exclusion:

1. **Does the paper release a model or dataset?**
   If no (pure biology, review, analysis only) → verdict is **Not eligible**: no model to incorporate.

2. **Does the model take small molecules as primary input?**
   Eligible input: SMILES, InChI, molfile, or a compound–protein interaction model
   where the small molecule is the user-facing input.
   Hard exclusions: protein sequence, RNA/peptide sequence, gene/genome, transcriptomics,
   cell images, pocket tensors. If excluded → verdict is **Out of scope**: input modality
   not currently supported by the Hub.

3. **Does it perform one of the six Hub subtasks?**
   Activity prediction · Featurization · Property prediction · Similarity search · Generation · Projection
   If none applies → verdict is **Low fit**.

4. **Is the endpoint Hub-relevant?**
   High-priority: AMR, malaria / Plasmodium, TB / M. tuberculosis, Chagas / T. cruzi,
   leishmaniasis, ADMET, toxicity, hERG, CYP, drug-likeness, solubility.
   Lower priority: cardiology-only, plant-only, or highly disease-specific endpoints
   with no generalisation to the Hub's NTD/AMR/ADMET focus.

5. **Is code / weights / web server openly available?**
   If proprietary → flag as **Online-mode only** (lower priority, but still eligible).

6. **Is a similar model already in the Hub, in any status?**
   If the `ersilia_search` results (across all statuses) contain a model doing the same
   task on the same endpoint, flag it — but the wording depends on status:
   - **Ready** → flag as **Potential overlap**; name the existing model(s).
   - **In progress** or **In maintenance** → flag as **Already in the Hub pipeline**. This
     is a stronger signal than a plain overlap: the team already knows about this method
     and is actively working on it (or maintaining it). Do not present the paper as an
     unclaimed candidate — say explicitly that a matching model is already underway/live,
     name it, and let the user decide whether the paper adds anything beyond what's
     already being built.
   - **Archived** → flag as **Previously incorporated, now archived**; name the model. Do
     not speculate about why it was archived unless the paper or Hub description states
     it — just surface the fact so the user can decide whether it's worth reviving or
     whether the new paper's version supersedes it.
   Do NOT decide on deduplication in any case — surface the overlap and status, and let
   the user decide.

**Verdict override.** Steps 1–5 above set a *base* verdict from eligibility alone. If step
6 finds a matching model that is `In progress` or `In maintenance`, override the final
verdict to **Already in Hub pipeline** regardless of what the base verdict would have
been — calling a paper a "Strong candidate" is misleading if the team is already building
it. An `Archived` match does NOT override the verdict; keep the base verdict and add the
archived-model context as a reasoning bullet instead, since an archived model may need
reviving or may be legitimately superseded by the new paper.

---

## Step 4 — Write the report

Branch on mode.

---

### Mode: `--short` (default)

Keep it tight — this is a fast triage read, not a summary. Target roughly **half
the length** of `--extended`. The summary is 3–5 sentences max; the reasoning
bullets are one short clause each. If it feels like it could be trimmed, trim it.

---

#### Paper Summary

**Title:** [exact title]
**Authors:** [First Author et al., Year — Venue]

[3–5 sentences: problem, what is released, approach in one clause, headline result.
No background context — jump straight to the contribution.]

**Links:** [list each URL or package name verbatim from the paper, comma-separated. Omit this line entirely if the paper states no explicit links.]

---

#### Ersilia Model Hub Relevance

**Verdict:** [one of: Strong candidate · Candidate · Already in Hub pipeline · Low fit · Out of scope · Not eligible]

**Reasoning:**
[4–5 bullets, each a short clause (not a full sentence). State the fact + implication only.]
- Input: SMILES → within Hub surface.
- Task: activity prediction → aligns with Hub's largest subtask bucket.
- Endpoint: P. falciparum IC50 → high-priority (antimalarial focus).
- Availability: GitHub (MIT) → straightforward path.
- Overlap: eosXXXX (Ready) covers same endpoint — review before incorporating.
- Pipeline: eosYYYY (In progress) is this same method — already being incorporated, not a fresh candidate.

**Hub search results:** [list all closely matching Hub models as `eosXXXX — Title (Status)`, or "No close matches found."]

---

### Mode: `--extended`

Write a longer, richer report. The summary must be written in your own words — do not
copy the abstract verbatim. The relevance section must go beyond a checklist and reason
about the model's specific contribution relative to what already exists in the Hub.

---

#### Paper Summary

**Title:** [exact title]
**Authors:** [First Author et al., Year — Venue]

[6–10 sentences structured as follows:
1. **Context** (1–2 sentences): What biological or chemical problem does the paper address, and why does it matter?
2. **Contribution** (2–3 sentences): What model or dataset does the paper introduce? What architecture or approach does it use? What training data?
3. **Results** (2–3 sentences): What are the headline performance numbers? How does the model compare to prior work on the same benchmarks?
4. **Limitations / caveats** (1–2 sentences): Any notable limitations acknowledged by the authors (dataset size, generalisability, benchmark choices)?
Write for a computational biologist. Do not reproduce the abstract — synthesise the paper in your own words.]

**Links:** [list each URL or package name verbatim from the paper, comma-separated. Omit this line entirely if the paper states no explicit links.]

---

#### Ersilia Model Hub Relevance

**Verdict:** [one of: Strong candidate · Candidate · Already in Hub pipeline · Low fit · Out of scope · Not eligible]

**Eligibility assessment:**
[Work through the same checklist as in `--short`, but write each point as a full sentence
rather than a bullet fragment. Cover input modality, task, endpoint priority, and availability.]

**Added value over existing Hub models:**
[This is the core of the extended mode. For each Hub model returned by `ersilia_search`
that overlaps in task or endpoint — at ANY status — explain specifically what the new
paper adds or differs, and always name the status explicitly:
- Does it cover a broader or different set of targets?
- Does it use a more recent or more accurate architecture?
- Does it train on more / different / higher-quality data?
- Does it address a biological endpoint not currently covered?
- Is performance meaningfully better on shared benchmarks?
- If the match is `In progress`/`In maintenance`: say so plainly up front — this section's
  job shifts from "would this be a good addition" to "does this paper contain anything the
  in-flight incorporation is missing" (e.g. a better benchmark, an architectural detail,
  training data the current effort may not be using).
- If the match is `Archived`: note it was previously in the Hub and is no longer active;
  say whether the new paper's version looks like a straightforward revival candidate or
  a meaningfully different approach.
If no overlapping Hub models were found (at any status), state that clearly and note which
gap the paper would fill. If the paper is out of scope or not eligible, write "N/A — model
not eligible for incorporation."]

**Hub search results:** [list all closely matching Hub models as `eosXXXX — Title (Status)`, or "No close matches found."]

---

## Verdict definitions

| Verdict | Meaning |
|---|---|
| **Strong candidate** | Small-molecule input, Hub-relevant task + endpoint, open code, no identical model in the Hub (at any status) |
| **Candidate** | Eligible but with one flag: low-priority endpoint, online-mode only, or a potential overlap with a `Ready` model |
| **Already in Hub pipeline** | A matching model already exists as `In progress` or `In maintenance` — the team is already on it; overrides whatever the base eligibility verdict would have been |
| **Low fit** | Eligible input modality, but task or endpoint sits outside Ersilia priorities |
| **Out of scope** | Hard exclusion on input modality (protein, RNA, image, etc.) |
| **Not eligible** | Paper does not release a model or dataset |

Note: a match against an `Archived` model does not get its own verdict — it stays at
whatever the base eligibility verdict is (Strong candidate/Candidate/etc.), with the
archived overlap surfaced as a reasoning bullet, since an archived entry means "no longer
active in the Hub," not "already being handled."

---

## Reference

Before applying criteria, re-read `references/hub-incorporation-criteria.md` — it
contains the empirical subtask distribution, venue priors, and the exact 🤖 eligibility
rules. The criteria here are a summary; the reference file is authoritative.
