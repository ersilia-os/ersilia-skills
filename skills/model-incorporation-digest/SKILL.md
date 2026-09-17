---
name: model-incorporation-digest
description: >
  Produce the monthly Ersilia model-incorporation digest — an internal summary of every
  model incorporated into the Ersilia Model Hub during a calendar month, with a table, a
  paragraph per model crediting its original authors, and the metadata defects worth
  fixing. Use this skill whenever the user asks for the monthly technology report, the
  model incorporation digest, or a summary of the month's model incorporations. Triggers
  include: "technology report", "/model-incorporation-digest", "monthly report", "model
  incorporation digest", "what models did we incorporate last month", "summarise the
  month's models", "model incorporation summary", "what shipped to the Hub in August".
  Always use this skill for monthly incorporation-digest requests even if the ask seems
  simple.
argument-hint: [YYYY-MM]
allowed-tools: [Bash, Read, Write, WebFetch, WebSearch, AskUserQuestion]
---

# Ersilia Model Incorporation Digest

Your job is to produce the month's incorporation digest: **what went into the Ersilia
Model Hub, who made it, and what still needs fixing.**

The digest is internal, so it says whatever is useful to the team. It publishes nothing
and drafts nothing for publication. What it must still get right is **credit**: a month's
incorporations are a month of other people's science that Ersilia packaged, and the
per-model paragraphs name the authors who did that science. `references/attribution-rules.md`
governs how — in particular the verb discipline, the honesty rules, the handling of a
`Replicated` or `Internal` model, and the rule that no Ersilia contributor is named.

## Parse arguments

- `[YYYY-MM]` (optional) — the month to report on. Defaults to the **last complete month**.

## Read these first

- **`references/report-template.md`** — the digest's sections, what belongs in each, and
  how to write a per-model paragraph
- **`references/attribution-rules.md`** — the credit rules, the verb vocabularies, the
  honesty rules, and what changes for a `Replicated` or `Internal` model
- **`references/author-lookup.md`** — how the author list is resolved and how to get
  names right

---

## Step 1 — Sweep the month

```bash
python scripts/fetch_month_models.py 2026-08 --out /tmp/2026-08-context.json
```

This reads the Hub's own catalogue — one JSON on S3 with every model and its metadata —
keeps those whose `Incorporation Date` falls in the month, and resolves each publication
against Crossref and OpenAlex for the ordered author list and the abstract. It also flags
**metadata defects** per model.

Read the JSON and the stderr warnings. Note in particular:

- `n_models` — if zero, say so and stop; a month with no incorporations is a valid digest.
- `credit.n_authors == 0` for any model — its publication carries no resolvable DOI. See
  Step 3.
- `n_with_defects` — these go in the digest's own section, and they are often the most
  actionable thing in it.

## Step 2 — Write a paragraph per model

For each model, write two or three sentences into the `summary` field of its record in the
context JSON. `scripts/render_report.py` renders them; a model without one produces a
visible TODO and a non-zero exit, so none can be quietly skipped.

Say what the model does, what it was trained on, and what the authors showed. Draw on
`publication.abstract` and `model.description` — the Description was written against the
paper by `/model-incorporation-metadata`, so it is a sound starting point, but rewrite it
for a reader rather than pasting it.

**Check every claim against `publication.abstract`.** It is `null` for perhaps a third of
models — publishers deposit abstracts inconsistently — and absence is not permission to
skip the check: verify against the paper and say in the digest that the automated source
was unavailable.

**Watch for models Ersilia trained itself.** Where `Source Type` is `Replicated` or
`Internal`, the paper's authors produced the *data or the method*, not the served model.
The paragraph must say so plainly. August 2026 has a live example: `eos3f8h` credits Škuta
and colleagues for the EU OpenScreen screening database, while the classifiers were
trained by Ersilia with LazyQSAR.

**Watch for a model whose paper is not the paper it is served from.** July 2026 is the
live example: `eos5jv3` serves MycoPermeNet-v2, whose architecture is a different paper
from the one `Publication` cites. Where the two diverge, the paragraph names both and says
which did what.

## Step 3 — Handle models whose authors did not resolve

A model with `n_authors == 0` cannot be credited. It still goes in the digest, with the
gap stated plainly, so nobody mistakes an unresolved author list for an absent one.

Try, in order: the DOI (arXiv `abs`/`pdf` URLs are converted automatically), then the
paper's own page, then a web search. `references/author-lookup.md` covers the traps.
Some venues genuinely have no machine-readable route — OpenReview sits behind a browser
check and answers its API with 403 — so ask the user for the author list rather than
guessing, and record the gap in the defects section.

## Step 4 — Render

```bash
python scripts/render_report.py /tmp/2026-08-context.json \
    --out reports/2026-08-digest.md
```

`render_report.py` exits non-zero while any `summary` is missing. Fix the context and
re-render rather than hand-editing the output, which the next render would overwrite.

## Step 5 — Present

Show the user:

1. The month's headline numbers — how many models, by task, how many flagged
2. The digest path
3. The metadata defects, as a short list — these are the actionable items
4. Any model whose authors did not resolve, and what you need from them

## What not to do

- Do not publish, post or schedule anything. This skill produces an internal document.
- Do not credit the Ersilia contributor who did the incorporation. `Contributor` is in the
  metadata and is deliberately unused: internal credit is handled elsewhere.
- Do not invent an author name, an institution or a figure.
- Do not quote performance numbers the paper does not contain, and do not imply Ersilia
  reproduced results it did not.
- Do not use "we built", "we developed", "our model", or any phrase from the banned list in
  `references/attribution-rules.md`.
- Do not write around a metadata defect. Report it — and report it in the defects section,
  which carries what `fetch_month_models.py` flagged, not findings from elsewhere.
