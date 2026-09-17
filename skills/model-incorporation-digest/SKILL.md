---
name: model-incorporation-digest
description: >
  Produce the monthly Ersilia model-incorporation digest — an internal summary of every
  model incorporated into the Ersilia Model Hub during a calendar month, with a table, a
  paragraph per model crediting its original authors, and the metadata defects worth
  fixing. Use this skill whenever the user asks for the monthly technology report, the
  model incorporation digest, or a summary of the month's model incorporations, and also
  when they ask to publish that digest to the Ersilia digests site. Triggers include:
  "technology report", "/model-incorporation-digest", "monthly report", "model
  incorporation digest", "what models did we incorporate last month", "summarise the
  month's models", "model incorporation summary", "what shipped to the Hub in August",
  "publish the digest", "put the monthly digest on the website". Always use this skill for
  monthly incorporation-digest requests even if the ask seems simple.
argument-hint: "[YYYY-MM] [--publish]"
allowed-tools: [Bash, Read, Write, WebFetch, WebSearch, AskUserQuestion]
---

# Ersilia Model Incorporation Digest

Your job is to produce the month's incorporation digest: **what went into the Ersilia
Model Hub, who made it, and what still needs fixing.**

The digest has two audiences and two renders from one context. The **internal** one is the
default and says whatever is useful to the team. The **public** one, `--public`, is the
same document minus the metadata-defects section, and it is published to the Ersilia
digests site alongside the literature and GitHub digests. What both must get right is
**credit**: a month's
incorporations are a month of other people's science that Ersilia packaged, and the
per-model paragraphs name the authors who did that science. `references/attribution-rules.md`
governs how — in particular the verb discipline, the honesty rules, the handling of a
`Replicated` or `Internal` model, and the rule that no Ersilia contributor is named.

## Parse arguments

- `[YYYY-MM]` (optional) — the month to report on. Defaults to the **last complete month**.
- `--publish` (optional) — after rendering, also publish the public copy to the digests
  site (Step 5). Without it the skill renders locally and stops.

## Read these first

- **`references/report-template.md`** — the digest's sections, what belongs in each, and
  how to write a per-model paragraph
- **`references/attribution-rules.md`** — the credit rules, the verb vocabularies, the
  honesty rules, and what changes for a `Replicated` or `Internal` model
- **`references/author-lookup.md`** — how the author list is resolved and how to get
  names right
- **`references/digest-website.md`** — how the digests site renders these files, how to
  preview it locally, and what adding the `models/` category takes (only needed when
  publishing)

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

A model with `n_authors == 0` cannot be credited automatically. It still goes in the
digest, with whatever names you could establish.

Try, in order: the DOI (arXiv `abs`/`pdf` URLs are converted automatically), then the
paper's own page, then a web search. `references/author-lookup.md` covers the traps.
Some venues genuinely have no machine-readable route — OpenReview sits behind a browser
check and answers its API with 403 — so ask the user for the author list rather than
guessing.

**Report the gap to the user in Step 6; do not write it into the model's paragraph.** How
a name was obtained is a fact about this skill's plumbing, not about the model, and the
paragraphs are read by people who want to know what the model does. The same goes for an
affiliation you had to correct off the paper because OpenAlex resolved it wrongly: fix it
in the context JSON so the byline is right, and say so when you present, not in the prose.

## Step 4 — Render

```bash
python scripts/render_report.py /tmp/2026-08-context.json \
    --out reports/2026-08-digest.md
```

`render_report.py` exits non-zero while any `summary` is missing. Fix the context and
re-render rather than hand-editing the output, which the next render would overwrite.

## Step 5 — Publish, if the user asked for it

Publishing is **not** automatic. The digest is useful internally on its own, and the
public copy is a separate act the user asks for. When they do:

**Check nothing recent is already published.** Re-running would clobber it.

```bash
python scripts/check_remote_digest.py
```

If it prints a path, **stop** and tell the user. Only `--force` past it on their say-so.
If it exits 1, the check itself failed: treat that as a hard block, because a run that
skips the check can overwrite published work.

**Render the public copy** under the canonical name, which `--public` prints for you:

```bash
python scripts/render_report.py /tmp/2026-08-context.json \
    --out /tmp/26-08-31-models-digest.md --public
```

The name is `YY-MM-DD-models-digest.md` dated the **last day of the month reported**,
matching the window-end convention the sibling digests use. `upload_digest.py` refuses
any other name.

**Upload it:**

```bash
python scripts/upload_digest.py --digest /tmp/26-08-31-models-digest.md
```

This goes to `ersilia-os/digests` at `models/`, and updates that repo's `README.md` under
`## Model incorporation digests`. It refuses to overwrite without `--force`; on exit code
2 the file already exists, so surface that and ask rather than forcing. On success it
prints the canonical **GitHub Pages URL** on line 1 — that is the link to hand the user,
not the local path.

**Upload the `--public` render, never the internal one.** The two differ only in the
defects section, the filename does not record which is which, and the script cannot tell
them apart. Publishing the internal copy puts a list of unrepaired defects in live models
on a public page.

**To check the publish path without publishing** — it needs no network, credentials or
`gh`, standing up a fake `gh` over a temporary directory instead:

```bash
python scripts/selftest_publish.py
```

It drives the whole sequence: both renders, the staleness guard, a first upload, the
refusal to overwrite, `--force`, the README index and its ordering, and the refusal of a
non-canonical filename. Run it after touching either script.

**One-time setup (first models digest only).** The `models/` category does not exist on
the digests site yet, and adding one touches five files in `ersilia-os/digests`, not the
one an earlier version of this note claimed. Everything below was worked out by building
that site locally with an August digest in it; `references/digest-website.md` has the
detail and the tested patch.

1. `.github/workflows/pages.yml` — stage the folder. The workflow copies each category by
   name, so a `models/` directory is **not** picked up automatically.
2. `website/_config.yml` — a `- scope: {path: "models"}` block mapping to the `digest`
   layout, with `wide: true`. This family opens with a summary table, which is exactly the
   case that flag exists for.
3. `website/_layouts/base.html` — a sidebar nav group and its colour dot.
4. `website/index.md` — the year calendar: gather the family, add its date/URL lookup, add
   a branch to the per-day cell logic, a legend swatch, and a "Recent" list.
5. `website/assets/style.css` — `--digest-models` and its hover, plus `.has-mod`,
   `.swatch.mod` and `.nav-dot.is-models`.

Until this lands the file still uploads, but nothing links to it and it renders without the
site layout. Make it a PR to the digests repo.

## Step 6 — Present

Show the user:

1. The month's headline numbers — how many models, by task, how many flagged
2. The digest path
3. The metadata defects, as a short list — these are the actionable items
4. Any model whose authors did not resolve, and what you need from them
5. If published, the Pages URL — the remote is canonical, not the local file

## What not to do

- Do not publish unless the user asked. Rendering the digest is the job; putting it on a
  public page is a separate decision that is theirs.
- Do not publish the internal render. The public copy comes from `--public`, and the
  defects section never goes on a public page.
- Do not credit the Ersilia contributor who did the incorporation. `Contributor` is in the
  metadata and is deliberately unused: internal credit is handled elsewhere.
- Do not invent an author name, an institution or a figure.
- Do not quote performance numbers the paper does not contain, and do not imply Ersilia
  reproduced results it did not.
- Do not use "we built", "we developed", "our model", or any phrase from the banned list in
  `references/attribution-rules.md`.
- Do not write around a metadata defect. Report it — and report it in the defects section,
  which carries what `fetch_month_models.py` flagged, not findings from elsewhere.
- Do not write commentary into a model's paragraph. It describes the model: what it does,
  what it was trained on, what the authors showed. Not where a name or an affiliation came
  from, not what the metadata says, and not where anything sits in this document.
