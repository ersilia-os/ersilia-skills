# Digest template — what goes in each section

`scripts/render_report.py` builds every section from the month context, so the shape is
fixed and only one thing is written by hand: the per-model `summary` paragraphs. This file
is about those.

## The sections

```
# Ersilia model incorporation digest — <Month Year>
  headline counts: models, tasks, statuses, Global-South-led, catalogue size

(no separate summary — the entries below carry it)

## The models
  one `### <Task>` group per task category, each a table:
  Model (identifier + title) · Tag (task emoji + subtask) · Author (first author,
  institution, journal and year) · What it does · Links (paper, code)

## Metadata to fix
  the defects fetch_month_models.py found, per model
```

Models are ordered by task category — Annotation, Representation, Sampling, then anything
unrecognised — and grouped under one heading per category, the way the event report groups
by continent. "Four featurizers and four generative models" is the shape of a month; a flat
list makes the reader count it themselves.

Each model is **one row**. What goes in the cells is as much about what is left out:

- **Author names one person** — the first author. The full list is in the paper, one click
  away, and a cell carrying eleven names is a cell nobody reads.
- **The institution is trimmed, never abbreviated.** Sub-units after a comma, legal
  suffixes and parenthetical cities come off, so "Denovo Sciences Inc (Yerevan)" reads
  "Denovo Sciences". Nothing is shortened into an acronym: an institution's name is part
  of the credit.
- **The venue is the journal and the year, nothing else.** A record with no journal is
  labelled a preprint, keyed on the record rather than on `Publication Type`, which the
  scan itself flags as unreliable.
- **No fetch command and no licence.** Both were on every row, and neither is what the
  table is for. The licence only ever mattered when it constrained reuse, and by the time
  it does the reader is on the model's own page.
- **Write every link explicitly.** The digests site renders with kramdown, which does not
  autolink, so a bare URL publishes as unclickable text while the DOI beside it works.

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

### The paragraph is about the model, and only the model

Everything in it should be a fact a reader could use to decide whether to run the model.
Not how the digest was assembled. These all appeared in a real draft and are all wrong
here:

> ✗ The institutions in the byline were taken from the paper: OpenAlex mis-resolves them
>   to a Slovak institute and to Denso.
> ✗ Its Publication field is an OpenReview URL, which mints no DOI, so the author list
>   could not be resolved automatically.
> ✗ …which is the paper the table above cites.
> ✗ The credit here is for the screening data, not the model.

The first two are about this skill's plumbing. The third points at the document, and
breaks the moment the ordering changes. The fourth narrates the crediting instead of
crediting: state who did what and let the reader draw the conclusion.

For the same reason, never locate a model by position — "the model above" — because the
entries are grouped by task and the ordering is not stable. Name the sibling model.

Where a name or an affiliation had to be established by hand, fix it in the context JSON
so the byline is right, and tell the user when you present. That belongs in the
conversation, not in the digest.

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
