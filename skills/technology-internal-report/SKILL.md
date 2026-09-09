---
name: technology-internal-report
description: >
  Produce the monthly Ersilia technology internal report — a summary of every model
  incorporated into the Ersilia Model Hub during a calendar month, with a table, a
  paragraph per model crediting its original authors, the metadata defects worth fixing,
  and a draft LinkedIn round-up post for the team to review before publishing. Use this
  skill whenever the user asks for the monthly technology report, a summary of the
  month's model incorporations, or the round-up of what shipped to the Hub. Triggers
  include: "technology report", "/technology-internal-report", "monthly report", "what
  models did we incorporate last month", "summarise the month's models", "model
  incorporation summary", "monthly round-up", "what shipped to the Hub in August".
  Always use this skill for monthly technology-report requests even if the ask seems
  simple.
argument-hint: [YYYY-MM] [--no-roundup]
allowed-tools: [Bash, Read, Write, WebFetch, WebSearch, AskUserQuestion]
---

# Ersilia Technology Internal Report

Your job is to produce the month's technology report: **what went into the Ersilia Model
Hub, who made it, and what still needs fixing** — plus a draft LinkedIn round-up that the
team reviews in the same document before anyone posts it.

The report is internal. The round-up inside it is not. So the report says whatever is
useful to the team, while the round-up obeys the credit rules in
`references/attribution-rules.md`: the models' **original authors** carry the post and
Ersilia carries the announcement. A month's incorporations are a month of other people's
science that Ersilia packaged.

## Parse arguments

- `[YYYY-MM]` (optional) — the month to report on. Defaults to the **last complete month**.
- `--no-roundup` (optional) — skip the LinkedIn draft and produce the internal sections
  only. Use when the user only wants the meeting document.

## Read these first

- **`references/report-template.md`** — the report's sections, what belongs in each, and
  how to write a per-model paragraph
- **`references/attribution-rules.md`** — the credit rules that govern the round-up, the
  verb vocabularies, the honesty rules, and what changes for a `Replicated` or `Internal`
  model
- **`references/post-anatomy.md`** — the round-up's block structure and LinkedIn's
  mechanics
- **`references/author-lookup.md`** — how the author list is resolved, how to get names
  right, and the profile-verification protocol

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

- `n_models` — if zero, say so and stop; a month with no incorporations is a valid report.
- `credit.n_authors == 0` for any model — its publication carries no resolvable DOI. See
  Step 3.
- `n_with_defects` — these go in the report's own section, and they are often the most
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
skip the check: verify against the paper and say in the report that the automated source
was unavailable.

**Watch for models Ersilia trained itself.** Where `Source Type` is `Replicated` or
`Internal`, the paper's authors produced the *data or the method*, not the served model.
The paragraph must say so plainly. August 2026 has a live example: `eos3f8h` credits Škuta
and colleagues for the EU OpenScreen screening database, while the classifiers were
trained by Ersilia with LazyQSAR.

## Step 3 — Handle models whose authors did not resolve

A model with `n_authors == 0` cannot be credited, and **an uncreditable model must not go
into the round-up** — publicising work you cannot attribute is the one thing this skill
exists to prevent. It still goes in the internal report, with the gap stated.

Try, in order: the DOI (arXiv `abs`/`pdf` URLs are converted automatically), then the
paper's own page, then a web search. `references/author-lookup.md` covers the traps.
Some venues genuinely have no machine-readable route — OpenReview sits behind a browser
check and answers its API with 403 — so ask the user for the author list rather than
guessing, and record the gap in the defects section.

## Step 4 — Draft the round-up

Skip if `--no-roundup`. Write it into the context JSON's top-level `roundup` field,
following the block structure in `references/post-anatomy.md`.

A round-up names many models, so the per-model credit is one line each: the model's name,
its **first author** and institution, one clause on what it does, and its paper link.
Every model you name must carry its first author — R1 enforces exactly that.

Length runs 900–2,500 characters, wider than a single-model post, because nine or ten
models of credit do not fit in 1,500.

## Step 5 — Look up the authors' profiles

**Always do this, and always report it in the report.** Look up the **first author of
every model the round-up names**, and no institutions — Ersilia names institutions in the
post but does not tag them. Write the rows into the context JSON's `profiles` list.

A LinkedIn profile cannot be opened (`WebFetch` on a `/in/` URL returns HTTP 999), so
verification comes from the search-result title plus an independent source. Use a
`linkedin.com`-restricted `WebSearch` pass as well as an open one. Statuses:
`confirmed` (a human opened it), `corroborated` (title plus one independent source),
`ambiguous`, `unverified`. You can only ever write `corroborated`.
`references/author-lookup.md` has the protocol and the traps.

## Step 6 — Render and lint

```bash
python scripts/render_report.py /tmp/2026-08-context.json \
    --out reports/2026-08-technology.md
python scripts/check_post.py reports/2026-08-technology.md \
    --context /tmp/2026-08-context.json
```

`render_report.py` exits non-zero while any `summary`, the `roundup` or the `profiles` list
is missing. `check_post.py` checks the round-up against the twelve rules; **every rule must
be FAIL-free before you show the report to the user.** Fix the post and re-render rather
than explaining a failure away.

R12 checks that a profile row *exists* for each named author. It cannot check that you
actually looked — that part is on you.

## Step 7 — Present

Show the user:

1. The month's headline numbers — how many models, by task, how many flagged
2. The report path
3. The linter output
4. The metadata defects, as a short list — these are the actionable items
5. Any model whose authors did not resolve, and what you need from them

Then ask whether the round-up wording should change, apply edits, re-render, re-lint.

Do not post anything. Ersilia's LinkedIn is published by a human; this skill stops at a
reviewed draft.

## What not to do

- Do not post, schedule or publish anything.
- Do not name a model in the round-up whose authors you could not resolve.
- Do not credit the Ersilia contributor who did the incorporation. `Contributor` is in the
  metadata and is deliberately unused: internal credit is handled elsewhere.
- Do not tag institutions.
- Do not invent an author name, an institution, a LinkedIn handle or a figure.
- Do not quote performance numbers the paper does not contain, and do not imply Ersilia
  reproduced results it did not.
- Do not use "we built", "we developed", "our model", or any phrase from the banned list in
  `references/attribution-rules.md`.
- Do not write around a metadata defect. Report it.
