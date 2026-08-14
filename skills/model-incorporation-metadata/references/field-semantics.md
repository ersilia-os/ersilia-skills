# Field semantics — the judgement calls

The controlled vocabularies tell you which values are legal. They do not tell you which one
is *right*, and a value can be perfectly valid and still wrong. This document covers the
fields where a 2026 audit of all 218 Ready models found the choice was being made
inconsistently, with the concrete evidence behind each rule.

---

## `Output` — `Score` versus `Value`

The distinction is:

> A **score** is a number that relates to a label. A **value** is a number that has some
> direct interpretation.

So a classifier's probability is a `Score` — it exists only in relation to the class it
predicts. A measured or predicted physical quantity is a `Value`: logP, IC50, molecular
weight, a permeability coefficient, an embedding dimension.

**A column named `*_score` does not settle the question.** Three hub models emit computed
descriptors or plain counts under `Score`, and the name is doing all the misleading work:

| Model | Columns | Why it reads as `Value` |
|---|---|---|
| `eos12x7` | `sps_score`, `nsps_score` | a computed complexity descriptor, deterministic, with no label behind it |
| `eos4n4d` | `weighted_accumulation` | a predicted physical quantity — how much compound accumulates |
| `eos526j` | `top_score` plus three integer counts | step and precursor counts are directly interpretable numbers |

These were reviewed and deliberately kept as `Score`, but only after reading what the
columns contain. Do the same: look at the columns, not their names.

`Output` is a list, so a model returning both a probability and its associated measured
value is `[Score, Value]`.

---

## `Output Consistency` — read the code, not the subtask

This field records whether the same input always produces the same output. **It describes
the inference code, not the model category**, and it cannot be derived from `Subtask`. A
value that looks anomalous next to its subtask peers is not automatically wrong.

All three instructive cases exist in the hub:

| Model | Value | Why |
|---|---|---|
| `eos3e6s` | `Variable` | calls `random.sample()` with no seed — genuinely stochastic |
| `eos935d` | `Fixed` | a **generator** that is deterministic: it runs OpenNMT with `-beam_size 5`, and its `randomise_smile` helper is never called on the inference path |
| `eos2lm8` | `Variable` | a missing `.eval()` leaves dropout active at inference |

What to check in `main.py` and the inference module:

- unseeded `random`, `numpy.random` or `torch` sampling
- PyTorch models served without `.eval()` — dropout and BatchNorm stay in training mode
- beam search versus sampling in sequence models (beam search is deterministic)
- any API call to a third-party service whose backend can change

### A warning worth its own paragraph

`eos2lm8` is `Variable` **because of a bug**, not because of a design choice. The field is
recording a defect as though it were a property, and the correct value flips to `Fixed` the
moment the missing `.eval()` is added.

If you find yourself writing `Variable` because the code is wrong rather than because the
method is stochastic, say so explicitly to the user and to the reviewer. Metadata that
depends on a defect silently becomes false when the defect is fixed.

---

## `Output Dimension` — an invariant, not an estimate

**`Output Dimension` must equal the number of data rows in
`model/framework/columns/run_columns.csv`.** The two are written by different skills
(`/model-incorporation-code` Phase 4 creates the CSV) and they must agree.

Checked across all 218 models against freshly fetched `run_columns.csv` files, this came
back with zero mismatches — but only because someone checked. If the paper and the
repository disagree about the number of endpoints, the repository wins, because that is
what the served model actually returns.

If the dimension is a user-configurable parameter (`n_components` and similar), ask the
user rather than adopting a default from the documentation examples.

---

## `Task` and `Subtask` — where `Representation` runs out

`subtask.txt` offers only `Featurization` and `Projection` under `Representation`, and
`Featurization` is defined as producing a fixed-length embedding or descriptor vector.

Seven hub models produce neither a vector nor a projection: format conversions
(`eos2mrz` DeepSMILES, `eos6pbf` SELFIES, `eos7qga` InChIKey), a substructure tokeniser
(`eos1mxi`), alternative SMILES forms (`eos4k4f`), an IUPAC name (`eos4se9`) and a natural
language description (`eos2rd8`).

All seven sit under `Featurization`, which is being used as a catch-all for "produces a
non-numeric representation". **This is a convention, not a description** — follow it so the
catalogue stays consistent, but know that it is a compromise rather than a fit.

A useful signal: `Output` already separates these correctly as `Compound` or `Text` rather
than `Value`, so a `Featurization` model whose `Output` is not `Value` is one of these
cases.

---

## Publication fields

### `Publication Year` is the cited paper's year

Never the incorporation year. The two are unrelated, and conflating them was the single
largest error source in the audit: **26 wrong years, of which 18 exactly equalled the
model's own incorporation year.**

For **internally built** models the rule still holds. Ersilia may train a model on data
published elsewhere; `Publication` and `Publication Year` then describe that source paper,
while `Incorporation Date` doubles as the model training date.

Where a journal reports both an **online** date and an **issue** date, use the **issue
year** — that is the citation year of the version of record. Five hub models legitimately
differ from Crossref's default `issued` field for exactly this reason.

### Check whether the preprint has already been published

Before writing `Preprint`, look. Of 29 preprint-citing models audited, **nine of the 17
distinct sources had been published since incorporation, affecting 21 models** — one
preprint alone (arXiv 2007.02835, GROVER) is cited by 12 of them, so a single stale record
propagates across a whole family.

At incorporation time this is one lookup:

| Source | Where to check |
|---|---|
| bioRxiv / medRxiv | `https://api.biorxiv.org/details/biorxiv/<doi>` — exposes a `published` field |
| ML conference papers | DBLP (`https://dblp.org/search/publ/api?q=<title>&format=json`) is the reliable index for NeurIPS, ICLR, ICML |
| Journals | Crossref (`https://api.crossref.org/works/<doi>`) or OpenAlex |

Do **not** rely on arXiv's own `journal_ref` field — it is only populated when the authors
remember to update it, which is often never.

### `Publication Type` has no value for DOI-less proceedings

`publication_type.txt` offers `Peer reviewed | Preprint | Other`. NeurIPS, ICLR, ICML and
KDD papers are peer reviewed but **mint no DOI**, so `Publication` has nowhere better to
point than the arXiv entry.

**Convention:** use `Peer reviewed` only where the published version carries a DOI, so
`Publication` and `Publication Type` describe the same artefact. Six sources in the hub sit
in this hole — GROVER (NeurIPS 2020), MoLeR (ICLR 2022), CLAMP (ICML 2023), SQUID (ICLR
2023), GenMol (ICML 2025) and Uni-Mol (ICLR 2023) — and all remain `Preprint`.

**Consequence to expect:** `Publication Year` still tracks the published version, so it can
legitimately disagree with the year of the DOI being cited. Three hub models do exactly
this. That is not an error, and an automated year check will flag it every time.

### URL hygiene

- Prefer a DOI (`https://doi.org/...`) over a publisher landing page or a PubMed record.
  DOIs survive site migrations; publisher paths do not.
- Verify the URL resolves before writing it.
- **HTTP 403 from ACS, RSC, Oxford, Wiley and MDPI on `doi.org` redirects is bot-blocking,
  not a dead link.** Those pages open normally in a browser. In a sweep of 436 hub URLs, 73
  of the 80 non-200 responses were exactly this; only 7 were genuinely broken. Treating
  publisher 403s as rot wastes a reviewer's day.

---

## Controlled vocabularies — there are fifteen

The workflow fetches eleven, which is correct: those are the fields it writes. But
`ersilia/hub/content/metadata/` holds **fifteen**, and the other four constrain fields this
skill must not modify:

| File | Field |
|---|---|
| `license.txt` | `License` — set at model-request time, **not free text** |
| `status.txt` | `Status` |
| `input.txt` | `Input` |
| `docker_architecture.txt` | `Docker Architecture` |

If one of those looks wrong, raise it with the user rather than editing it here.
