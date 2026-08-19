---
name: model-monitoring
description: >
  Produce the Ersilia model-monitoring report — a self-contained HTML page covering
  (1) isaura precalculation coverage, showing which Ready models have the full set of
  1,355,109 stored predictions, which are incomplete and which have none; (2) Singularity
  `.sif` image availability from the `models-sif` S3 bucket; and (3) this week's model
  maintenance activity from the `ersilia-os/ersilia-maintenance` repository. Use this skill
  whenever the user asks to monitor models or stored data, check precalculation, isaura or
  Singularity coverage, or wants the state of the Model Hub as a report. Triggers include:
  "model monitoring", "/model-monitoring", "monitoring report", "which models have
  precalculations", "isaura coverage", "which models are missing calculations", "do we have
  predictions for all models", "which models have a sif", "singularity images", "sif
  coverage", "check the maintenance repo this week", "state of the model hub", "how much
  data do we have stored". Always use this skill for model-monitoring requests even if the
  ask seems simple.
argument-hint: "[--plots] [--out <path>] [--reuse-stats <path>]"
allowed-tools: [Read, Bash, Write, Edit, WebFetch, AskUserQuestion, Skill]
---

# Ersilia Model Monitoring

You produce the model-monitoring report for **Ersilia Open Source Initiative**: one
self-contained HTML file that answers three questions the team asks every week.

1. **Where are the precalculations?** For which models do we hold the full set of stored
   predictions in isaura, for which are they incomplete, and for which do we have nothing?
2. **Where are the Singularity images?** For which models has a `.sif` been built and
   uploaded, and for which is one missing?
3. **What happened in maintenance?** Which models were tested, which passed, which failed,
   and how the hub's health is trending month over month.

The first two are what no other skill answers, and they are usually why someone runs this.
Both are about whether a model can actually be *served*: precalculations are what make the
Hub fast (with them a request is a lookup, without them every request is computed from
scratch), and a `.sif` is what lets a model run on HPC or on any host without Docker. So a
`Ready` model missing either one is a real, actionable gap rather than a cosmetic one.

**The population is `Ready` models.** Coverage is measured against models users can actually
run, because that is what makes a gap meaningful — an Archived model was never going to be
served, and including it would only pad the denominator. Data or images belonging to
non-`Ready` models are still reported, but separately, since that is a question about
reclaiming storage rather than about coverage.

The report is a **local file**, not published anywhere. It is written for the Ersilia
engineering and science team.

This skill is the sibling of `github-digest` and `literature-digest` and follows the same
shape: deterministic scripts do the fetching and arithmetic, the reference files carry the
domain knowledge and report format, and you do the triage, interpretation and composition.
Both halves of the report always run — the maintenance picture and the coverage picture
are read together, and a report with only one of them has repeatedly proven to be the
wrong deliverable.

---

## Inputs

All optional. Ask only if something is genuinely ambiguous; never invent a value.

- `--plots` — also embed the three monthly trend PNGs published by the maintenance repo.
  Off by default because they roughly triple the file size (250 KB → 600 KB). Turn them on
  when the user asks for plots, monthly trends, or "the graphs".
- `--out <path>` — where to write the HTML. Default:
  `reports/YY-MM-DD-model-monitoring.html` relative to this skill folder, using today's
  date with a two-digit year, matching the other Ersilia report skills.
- `--reuse-stats <path>` — reuse an existing `isaura_stats_*.json` instead of re-running the
  remote inventory. The inventory is the slowest step, so this is the flag to reach for when
  you are iterating on presentation and the underlying data has not changed.
- `--title` — report headline. Default: `Model Hub monitoring — <D Mon YYYY>`.

---

## Workflow

Run in order. The two fetch steps are independent, so start them together.

### Step 0 — Pre-flight

The data sources live in **different conda environments** and **none is on the default
PATH**. The scripts resolve them for you, but confirm they exist before committing to a long
run, because failing at step 3 wastes the inventory:

```bash
ls ~/anaconda3/envs/ersilia/bin/isaura ~/anaconda3/envs/ersilia-search/bin/ersilia_search
aws --version && aws s3 ls s3://models-sif/ --profile ersilia | head -2
```

If either is missing, stop and tell the user which environment needs attention. Do not
substitute a different environment or fall back to a partial report — a coverage number
computed from half the sources is worse than no number, because it looks authoritative.

Note there is **no GitHub CLI** on this machine. The `gh` binary inside the
`ersilia-search` environment is an unrelated tool that happens to share the name. The
maintenance data is public and is fetched over plain HTTPS, so this costs nothing — just
don't reach for `gh`.

### Step 1 — Load context

Read `references/data-sources.md` before running anything. It records the exact commands,
the shape of every payload, and the traps that have already caught this skill once (the
500-result ceiling, the CSV that lies to `wc -l`, the bucket name, the schema rename).
Quote it rather than re-deriving it — the traps are not guessable from the tool help.

Read `references/report-template.md` when you need to change what the report contains or
how it is ordered.

### Step 2 — Fetch the maintenance reports

```bash
cd scripts
python3 fetch_maintenance.py --out /tmp/maintenance.json          # add --plots if asked
```

Fast (a few seconds). Pulls the weekly testing report, the failing-models report, the
updated-source report, the monthly health report and the monthly history, and parses the
markdown tables into structured rows.

A missing source is reported in `missing_sources` rather than crashing the run, because the
maintenance automation renames files from time to time. If anything is listed there, say so
to the user — the report will render, but a section will be thin.

### Step 3 — Compute isaura coverage

```bash
python3 fetch_coverage.py --out /tmp/coverage.json
```

The slowest step, though only about **30 seconds** — it walks the whole remote bucket. It
joins two sources:

- `isaura stats -pn isaura-public -r` — a JSON inventory of what is actually stored,
  one record per model *version*.
- `ersilia_search --status Ready --limit 500 --csv` — the authoritative list of models
  users can run. Pass `--status all` to widen the population to every status, which is
  occasionally useful but is not the default for the reason given above.

Coverage is the set difference, and every model lands in exactly one class:

| Class | Meaning |
|---|---|
| `complete` | Every one of the 1,355,109 reference molecules has a stored prediction |
| `partial` | Some predictions stored, but fewer than the full set |
| `missing` | The hub lists the model; isaura holds nothing for it |
| `orphan` | isaura holds data for a model outside the measured population |

`orphan` is a storage question, not a coverage gap, so it is counted separately and never
folded into the coverage percentage. A model can also be stored several times (`eos1lb5/v1`
and `/v2`); the script keeps the **best** version's count, since the question is whether the
predictions exist at all.

If this step exits complaining about the 500-result ceiling, do not work around it by
raising the limit — the API rejects anything above 500. Tell the user the search API needs
pagination before coverage numbers can be trusted at the hub's new size. A truncated
inventory would silently under-report coverage, which is the one failure mode that would
make this report actively harmful.

### Step 3b — Inventory the Singularity images

```bash
python3 fetch_sif.py --coverage /tmp/coverage.json --out /tmp/sif.json
```

Fast (seconds). Lists `s3://models-sif` via the AWS CLI under the `ersilia` profile and joins
it against the hub population.

Note the bucket is **`models-sif`** with a hyphen — S3 bucket names cannot contain
underscores, so `models_sif` does not resolve. Keys are flat, one per model version:
`<model_id>_<version>.sif`.

This step reads the hub population out of `coverage.json` rather than calling
`ersilia_search` again, which is why it runs after step 3. That is deliberate: both sections
then measure against exactly the same set of models, so their percentages are directly
comparable. A key that does not match the expected naming is reported in
`unexpected_keys` rather than dropped, because an unmatched key means the convention changed
and images are about to be under-counted.

### Step 4 — Build the report

```bash
python3 build_report.py \
  --coverage /tmp/coverage.json \
  --maintenance /tmp/maintenance.json \
  --sif /tmp/sif.json \
  --out ../reports/YY-MM-DD-model-monitoring.html \
  --title "Model Hub monitoring — 19 Aug 2026"
```

`--sif` is optional; without it the report renders with a placeholder in place of the
Singularity section.

Output is one file with no external dependencies: CSS inlined, plots embedded as data URIs,
GitHub links navigational only. That self-containment is deliberate — these reports get
archived and forwarded, and one that loses its charts a month later is worse than none.

### Step 5 — Read the numbers before showing anyone

The scripts print a summary line each. Read it and sanity-check against what the report
says, because a plausible-looking report built on a broken join is the main risk here:

- Do `complete + partial + missing` add up to the hub total? (`orphan` sits outside it.)
  The same applies to `available + missing` against the hub total for images.
- Is the no-data count non-zero but small? Every hub model suddenly showing as `missing`
  means the join key broke, not that the bucket emptied.
- Are the two coverage percentages plausibly different? They measure different artefacts, so
  they should not match exactly — identical figures usually mean one JSON was reused.
- Does the monthly history show real values for the most recent months? All-zero recent
  months means the schema drifted again — see `references/data-sources.md`.

### Step 6 — Present it

Open the file and summarise. Lead with what needs attention, not with the totals:

```bash
xdg-open <path-to-report.html>
```

Then give the user a short written summary: how many models failed maintenance tests, how
many `Ready` models lack precalculations, and the headline coverage percentage. Name the
specific models in the actionable set if there are only a handful — a number they have to
click to unpack is less useful than three model ids they can act on.

If the report flags unavailable sources in a note box, say so, so they do not have to spot
it themselves.

### Step 7 — Iterate

Treat this as a live session. Common follow-ups:

- **Restyling.** The design is deliberate — the coverage plate is the signature element and
  everything around it is kept quiet so it carries the page. If the user wants a different
  look, load the `frontend-design` skill and work from `build_report.py`'s design notes,
  which explain what each choice is doing so you can change it coherently rather than
  layering CSS on top. The data JSONs are stable, so re-rendering is cheap: keep them and
  pass `--reuse-stats` on any re-fetch.
- **Deeper on a failing model.** Hand off to `failing-models-check` for the per-check
  breakdown, then `model-fixing` to act on it. Don't re-implement that analysis here.
- **A different completeness threshold.** `--full-count` on `fetch_coverage.py`, if the
  reference collection ever changes size.
- **The private bucket.** `--bucket isaura-private`. Out of scope by default, and worth
  confirming with the user before reporting on it, since it is not public data.

---

## What the report contains

Full detail in `references/report-template.md`. In order:

1. **Headline figures** — Ready models, both coverage percentages, failed tests, the gap
   counts, total GB stored.
2. **Needs attention** — models failing their last maintenance test, and Ready models
   missing precalculations. First because it is the only section that asks the reader to do
   something.
3. **Coverage plate** — one well per model, coloured by class, problems first. A dense grid
   is the only device that makes ~220 models legible at a glance, and a plate is native
   vernacular for the audience.
4. **Precalculation coverage** — the full table, searchable and sortable, filterable by
   class.
5. **Singularity images** — its own figure grid plus a matching searchable table. Kept
   structurally parallel to the isaura section, since both answer the same shape of question
   about a different artefact.
6. **This week in maintenance** — weekly test results, plus models whose upstream source
   moved on since packaging.
7. **Monthly health** — the current snapshot and the month-by-month series.
8. **Monthly trends** — the three published plots, only with `--plots`.

---

## Reference files

- `references/data-sources.md` — the tools, their environments, exact commands, payload
  shapes, and the known traps. Read before running.
- `references/report-template.md` — report structure, section order, and the reasoning
  behind the design so changes stay coherent.

---

## Related skills

- `failing-models-check` — per-check breakdown for models that failed. This skill tells you
  *which* models are failing; that one tells you *what* failed inside them.
- `model-fixing` — applies fixes once a failure is diagnosed.
- `github-digest` — issue and PR activity across the org, the operational sibling of this
  report.
