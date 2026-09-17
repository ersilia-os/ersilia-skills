# Digest template — what goes in each section

`scripts/render_report.py` builds every section from the month context, so the shape is
fixed and only one thing is written by hand: the per-model `summary` paragraphs. This file
is about those.

## The sections

```
# Ersilia model incorporation digest — <Month Year>
  headline counts: models, tasks, statuses, Global-South-led, catalogue size

## Summary
  one `### <Task>` group per task category, each a table: identifier, title, subtask, authors

## The models
  one section each: byline, paragraph, then facts (paper, authors' code, fetch, licence)

## Metadata to fix
  the defects fetch_month_models.py found, per model
```

Models are ordered by task category — Annotation, Representation, Sampling, then anything
unrecognised — and the summary is grouped under one heading per category, the way the event
report groups by continent. "Four featurizers and four generative models" is the shape of a
month; a single flat list makes the reader count it themselves. **The models** repeats that
same order, so moving between the two sections is not a search.

The summary carries no paper column: every model's own section below gives its DOI, and a
second copy crowded the four columns that answer "what shipped". Links there are written as
explicit markdown links, never bare URLs — the digests site renders with kramdown, which
does not autolink, so a bare address publishes as unclickable text.

The order is deliberate. The **table** answers "what shipped" for someone skimming before
a meeting. **The models** answers "what is each of these". **Metadata to fix** is the
action list, and it closes the digest because it is the only section anyone has to act on.

The digest carries no announcement draft and no tagging worksheet.

There are two renders of this one document. The default is **internal**. `--public` emits
the same file without `## Metadata to fix`, and that copy is published to the digests site
at `ersilia-os/digests` under `models/`. The defects section is the only difference: it
lists repairs owed on models that are already live, addressed to whoever can make them, so
it is written for the team and does not belong on a public page.

Everything above it is the same in both, which is deliberate. The per-model paragraphs
credit each model's original authors by name and institution, and that is precisely what a
public page should carry.

## Writing a per-model paragraph

Two or three sentences. Answer, in order:

1. **What it does** — the input, the output, and what the output means.
2. **What it was trained on** — dataset and scale, because that is what a reader needs to
   judge whether it applies to their compounds.
3. **What the authors showed** — a validation, a benchmark, a limitation they stated.

Then stop. This is a report, not a paper. Two sentences that say something specific beat
five that restate the title.

Do:

> Projects a SMILES string onto a 2D map of chemical space with a pretrained parametric
> t-SNE network, deterministically — structurally similar compounds land together every
> run. Built on 2048-bit ECFP fingerprints and trained on 1.56 million ChEMBL v23
> structures. The authors intend it for checking a QSAR model's applicability domain and
> spotting activity cliffs.

Don't:

> This model is a useful new tool for chemical space visualisation that leverages
> state-of-the-art machine learning to help researchers explore their data.

The second says nothing a reader could act on, and "leverages state-of-the-art" is the
tell. Name the method, the scale and the intended use.

### Models Ersilia trained itself

Where `Source Type` is `Replicated` or `Internal`, the paper's authors produced the data or
the method — not the model being served. Say which. `eos3f8h` in August 2026 is the worked
case: the credit belongs to Škuta and colleagues for the EU OpenScreen screening database,
and the classifiers on top were trained by Ersilia with LazyQSAR. A paragraph that let a
reader think the authors built the model would be wrong.

### Length and honesty

- Do not quote a metric the paper does not contain.
- Where the model's `Description` and the paper's abstract disagree, prefer the abstract
  and say so.
- State a licence only when it constrains reuse — non-commercial or research-only. MIT and
  Apache need no mention.

## Metadata defects

`fetch_month_models.py` flags these mechanically, each mapping to a rule in
`/model-incorporation-metadata`:

| Flag | Why it matters |
|---|---|
| `Status` not `Ready` | the model is in the month's count but not actually usable |
| `Interpretation` empty or placeholder | the field users read first says nothing |
| `Interpretation` contains a colon | breaks `metadata.yml` parsing unless quoted |
| `Description` empty, placeholder, or outside 200–600 chars | `ersilia test` enforces the range |
| `Publication` is not a DOI URL | the author list cannot be resolved automatically |
| `Output Dimension` missing | must equal the row count of `run_columns.csv` |

Do not fix these from inside this skill and do not write around them. List them, so
whoever reads the digest can go and repair the model.

This section carries what `fetch_month_models.py` flagged, and only that. A problem you
found by reading the paper is not a scanner defect: if it changes who the model credits,
it belongs in that model's paragraph; if it is a repair for someone else to make, it
belongs in an issue against the model, not here.
