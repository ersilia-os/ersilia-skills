---
name: molecule-auditing
description: >
  Audit a set of candidate small molecules and turn them into an interactive,
  shareable visual report. Use this skill whenever the user has a table of compounds with
  computed features (activity, ADMET, drug-likeness, structural flags — from the Ersilia
  Model Hub or elsewhere) and wants to make sense of the columns, build a condensed
  curated deliverable (renaming, aggregating, filtering, dropping liabilities), and
  produce a self-contained HTML explorer with 2D structures, consensus badges, and
  optional per-compound SWOT one-liners. Trigger on "audit these molecules", "build a
  compound explorer", "make sense of this screening output", "prioritise these hits", or
  when the user provides a CSV with model-output columns and wants a report.
argument-hint: <molecules-csv> [--output <dir>]
allowed-tools: [Read, Bash, Write, WebFetch, AskUserQuestion]
---

# Molecule Auditing → Interactive Explorer

You help a researcher turn a raw table of candidate compounds into a curated, interactive
**HTML explorer** (plus the condensed CSV behind it). This is an **interactive, iterative
session**, not a one-shot batch job: you make sense of the data with the user, build a
condensed deliverable they shape, show them a visualizer, and only then — if they want it —
author the (expensive) SWOT one-liners. Never run the whole thing autonomously end-to-end.

**Make the interactive nature explicit to the user.** Tell them, early and again when you hand
over the explorer, that this is a live session: at any point they can ask you to rename, aggregate
or drop columns, change filters/cutoffs/badges/sliders, re-sort, restyle, or tweak the layout, and
you will regenerate the explorer for them. They are not stuck with the first version.

The heavy lifting is done by config-driven scripts in `scripts/`; your job is to interview
the user, assemble a `config.json`, run the scripts, show results, and iterate.

## Output location
Unless the user gives `--output`, create a folder **beside the input**: `<input_stem>_explorer/`.
All artifacts go there: `config.json`, `selection_table.csv` (the deliverable), `viz_meta.json`,
`selection_visualizer.html`, and (later) `swot_facts.csv` / `swot_lines.csv`.

## Step 0 — Environment
Verify RDKit and pandas import in the Python you'll use (probe `python`, then conda envs under
`~/miniconda3/envs/*`). Pick that interpreter for all script calls. If no RDKit env, stop and
tell the user to install it. (`sascorer` ships with RDKit's Contrib; the SA filter is skipped
gracefully if unavailable.)

## Step 1 — Make sense of the input columns
Read **only the header** and a few rows (never load the whole file into context).
- Identify the **SMILES** column (`input`/`smiles`) and any **key/id** column (catalog id,
  vendor code, hash). Set it as `key_col`: the explorer shows it on each card **next to** the
  CPD-XXX id (never replacing it), and only when it is present in the input.
- For every other column, decide what it means:
  - **Ersilia-derived columns** match `{feature}.{eosID}`. Collect the eos IDs and run
    `scripts/fetch_model_metadata.py eosAAAA eosBBBB ... --output <dir>/model_meta.json` to get
    each model's title, interpretation, task, target organism, and per-column direction.
    Use `references/ersilia-metadata-guide.md` for URL/field details.
  - **Non-Ersilia columns** (custom scores, vendor flags, assay readouts, etc.): **ask the user**
    what they mean and which direction is good — do not guess. Use AskUserQuestion.
- Present a concise column inventory back to the user (column → plain meaning → higher/lower is
  better) and confirm before proceeding.

## Step 2 — Build the condensed deliverable (iterative)
Work with the user to define the condensed table. This is flexible and usually takes a few
rounds — expect to re-run as they refine. Decide, via AskUserQuestion:
- **Which columns to keep**, their **display names** (rename freely), and **role**: `primary`
  (the main activity ranking), `secondary` (supporting activity), `liability` (safety/interference,
  lower is better), `physchem` (context), `ignore`.
- **Aggregates** where useful: collapse a block of related columns into one (`fraction_gt` /
  `count_gt` / `mean` of columns above a threshold) — e.g. "fraction of N assays predicting active".
- **Consensus badges** — the user defines **1–3 badge tiers**; each tier is a set of columns with
  a per-column cutoff, and the badge shows how many pass (e.g. a primary `activity` tier and an
  extended `profile` tier).
- **Per-cell highlighting**: which columns get rank-colouring (blue→red by within-set rank) and/or
  a pass outline, with their cutoffs.
- **Top sliders — keep them few and purposeful.** Do **not** add a min/max slider for every
  numeric column; that clutters the header and overwhelms the user. Reserve sliders for the
  handful of columns someone will actually filter on (typically the primary activity as a `min`
  and one or two key liabilities as `max`). When in doubt about whether a column deserves a
  slider, **ask the user** rather than adding it by default.
- **Cutoffs**: propose data-driven defaults (look at the distribution — a bimodal valley if the
  column is clearly bimodal, otherwise a sensible percentile/0.5) and let the user tune.
- **Structure-quality filters** — walk through each and ask whether/where to apply: max MW, max
  halogen count, min ring atoms, max synthetic-accessibility (SA), and dropping PAINS/Brenk alerts
  (via `drug_criteria.py`). **Ad-hoc molecule removal is fine** — if the user wants to drop
  specific compounds or apply an on-the-fly threshold, add it to the filters and re-run.
- **CPD-XXX ids**: assigned by rank on the primary score. The input's own identifier (`key_col`)
  is preserved and shown on each card alongside (not instead of) the CPD id.
- **Legend**: invest a little time here — it's part of the deliverable. Populate `config.legend`
  with a concise, informative one-line meaning for **every** kept column; for Ersilia-derived
  columns set `model` to the eos id (the explorer auto-links it to the model's Ersilia Model Hub
  page). For non-Ersilia columns, write the meaning from the user's explanation.

Write `config.json` (schema below) and run:
```
python scripts/build_table.py --config <dir>/config.json
```
Report the row counts, what each filter dropped, and the badge distributions. **Iterate** with the
user until the deliverable (`selection_table.csv`) is what they want.

## Step 3 — First visualizer, WITHOUT SWOT
The SWOT analysis is expensive, so **always build a first visualizer without it** and get the
user's sign-off on the layout/columns/filters first:
```
python scripts/make_visualizer.py --output-dir <dir>
```
Open `<dir>/selection_visualizer.html` (use the chrome-devtools MCP if available, or tell the user
to open it) and confirm structures render, badges/filters/sort work, and the columns shown are
right. **Explicitly invite changes** — remind the user they can ask you to adjust columns, names,
filters, cutoffs, badges, sliders, sort or styling and you'll rebuild it. Loop back to Step 2 for
any change. **Do not proceed to SWOT until the user is happy.**

## Step 4 — SWOT one-liners (only when the user asks)
A SWOT one-liner is a single sentence per compound: what makes it interesting and what's wrong
with it. Style: qualitative (no raw numbers), no model names, lead with a confident structural
class when sure, "strength — but weakness" with one em-dash. Procedure:
1. Run `python scripts/swot_facts.py --config <dir>/config.json` → `swot_facts.csv` (per-compound
   facts: primary score/rank, badge counts, detected structural class & motifs, MW/logP, flagged
   liability columns, and PAINS/Brenk structural alerts). It prints a **size warning** for large
   sets — relay it; large sets mean many lines to author, so consider tightening filters first.
2. **Author a few examples first** (read `swot_facts.csv` for ~5 diverse compounds, read their
   SMILES, write bespoke one-liners) and show them to the user. Refine the style with them. **Do
   not auto-author the whole set.**
3. Once the style is approved, author a one-liner for **every** compound by reading its SMILES +
   facts, drawing on your own medicinal-chemistry knowledge and the domain notes in `references/`
   (pathogen criteria, frequent-hitter/alert context). Write them to **`<dir>/swot_lines.tsv`**
   (tab-separated, header `cpd_id<TAB>swot`) — tabs avoid the comma-quoting issues that one-liner
   text would cause in a CSV. For large sets, write in batches (e.g. `swot_part01.tsv`, …) and
   concatenate, or append to the one TSV.
4. Re-run `build_table.py` (merges the `swot` column) then `make_visualizer.py` (renders the
   one-liner at the bottom of each card). Verify and confirm with the user.

## Step 5 — Deliver
When the user is satisfied, share the deliverables: the `selection_visualizer.html` (self-contained,
opens in any browser) and `selection_table.csv`. Upload/move them wherever the user wants them.

## Step 6 — Feeding learnings back into the skill (optional, guarded)
Occasionally a session surfaces a **generalizable** improvement to the skill itself — most often
in the SWOT phrasing (a rule the user kept correcting), but also a new structural-class/motif
detector worth adding to `swot_facts.py`, a sensible default cutoff/filter, a column-role
heuristic, or a visualizer behaviour. When that happens, you may offer to improve the skill — but
**default to NOT touching it**, and only proceed when **all** of these hold:
1. **It generalizes** beyond this dataset/session (it would help future, unrelated audits) — not a
   one-off preference specific to these compounds or this project.
2. **It adds significant value** — a real quality or correctness gain, not cosmetics.
3. **The user explicitly agrees** to update the skill, after you describe the change precisely.

How to do it safely:
- Don't hand-hack the scripts in place mid-session. Invoke the **skill-creator** skill to make the
  edit properly, or make a deliberate change on a **git branch** in the `ersilia-skills` repo and
  open a PR for review. Keep the change minimal; re-run on `assets/drugbank_head_example.csv` and
  the existing `evals/`, and add an eval if the learning is testable.
- Only the **general rule** may flow back — never a session's bespoke content (specific compounds,
  a project-specific config, or hand-authored one-liners). Those stay in the session output.
- If it's borderline or you're unsure it generalizes, **don't edit** — capture it as a short note
  for the maintainers instead.

This keeps the skill improving over time without letting any single session corrupt it.

---

## config.json schema
Written by you from the interview; consumed by `build_table.py` (and `swot_facts.py`). All keys
optional except `input_csv`, `output_dir`, `smiles_col`, `columns`, `primary_score`.

```json
{
  "input_csv": "path/to/input.csv",
  "output_dir": "path/to/<stem>_explorer",
  "smiles_col": "input",
  "key_col": "key",
  "title": "Project — context",
  "category_col": null,
  "primary_score": "<display name of the primary column>",
  "primary_higher_better": true,
  "sort_by": "<display name>",
  "columns": [
    {"src": "inhibition_50um.eos4e40", "name": "abx_activity", "role": "primary", "higher_better": true},
    {"src": "ames.eos7m30", "name": "ames", "role": "liability", "higher_better": false}
  ],
  "aggregates": [
    {"name": "assay_consensus", "type": "fraction_gt", "cols": ["a.eosX","b.eosX"], "threshold": 0.7}
  ],
  "badges": [
    {"name": "activity", "label": "activity", "columns": [{"col": "abx_activity", "cutoff": 0.5, "op": ">="}]},
    {"name": "profile",  "label": "profile",  "columns": [
      {"col": "abx_activity", "cutoff": 0.5, "op": ">="},
      {"col": "qed", "cutoff": 0.5, "op": ">="}]}
  ],
  "rank_color_cols": ["abx_activity"],
  "cell_cutoffs": {
    "abx_activity": {"cutoff": 0.5, "op": ">=", "style": "fill"},
    "qed": {"cutoff": 0.5, "op": ">=", "style": "box"}
  },
  "filters": {"max_mw": 500, "max_halogens": 4, "min_ring_atoms": 7, "max_sa": 4.5,
              "drop_pains": true, "drop_brenk": false},
  "sliders": {"min": ["abx_activity"], "max": ["ames", "herg"]},
  "legend": {"abx_activity": {"model": "eos4e40", "meaning": "P(E. coli inhibition at 50 uM)", "higher_better": true}}
}
```
Notes: `op` is `">="` (default) or `"<="`. `cell_cutoffs` style `"fill"` paints the cell (rank
colour if the column is in `rank_color_cols`); `"box"` outlines it when the value passes. `legend`
(populated from fetched metadata + the user's explanations of non-Ersilia columns) drives the
Legend tab.

## Scripts
- `scripts/fetch_model_metadata.py` — fetch Ersilia model metadata + run_columns from GitHub.
- `scripts/build_table.py` — config → `selection_table.csv` + `viz_meta.json` (filters, badges,
  CPD ids, aggregates; merges `swot_lines.csv` when present).
- `scripts/swot_facts.py` — config → `swot_facts.csv` (per-compound facts for SWOT authoring).
- `scripts/make_visualizer.py` — `selection_table.csv` + `viz_meta.json` → `selection_visualizer.html`.
- `scripts/drug_criteria.py` — RDKit MedChem rules/alerts (used by filters + SWOT facts).
- `references/` — domain knowledge: `ersilia-metadata-guide.md` (Step 1 metadata fetch),
  `drug-discovery-criteria.md` + the pathogen `*-criteria.md` + `shared-anti-infective-criteria.md`
  (scaffold recognition, frequent-hitter/alert context, pathogen physchem) — read these when
  interpreting columns and writing SWOT one-liners.

## Handling change requests without corrupting the skill
Users will often ask for tweaks to the explorer — that's expected. Keep the skill's `scripts/`
**pristine**; never edit them to satisfy a single session. Route changes by type:
- **Config-level (the common case):** which columns, display names, roles, aggregates, badge
  tiers, cutoffs, rank-colouring, per-cell shading, filters, ad-hoc compound drops, sort, sliders,
  title — all live in `config.json`. Edit it and re-run `build_table.py` / `make_visualizer.py`.
  No code change, nothing to corrupt.
- **One-off visual/layout tweaks the config can't express** (e.g. card width, an extra note, a
  colour): edit the **generated** `selection_visualizer.html` **in the session output folder** — a
  copy, never the skill script. The skill is unaffected.
- **Genuinely reusable improvements:** don't fold them in mid-session; note them and make a
  deliberate, reviewed update to the skill afterwards (skill-creator / a PR).
The skill repo is under git, so any accidental edit to `scripts/` is recoverable with `git restore`.

The built-in explorer already supports compound **selection** (a checkbox per card), **Export
selected (CSV)**, **Import selection** (re-check a previously exported set to resume a session),
and **Clear** — all client-side, no server.

## Edge cases
- **No clear primary activity column**: ask the user which column should rank the compounds.
- **No Ersilia columns at all**: skip metadata fetch; rely entirely on the user's column explanations.
- **Very large input**: warn that structures + SWOT scale poorly; encourage filtering in Step 2.
- **SMILES that fail to parse**: dropped with a count reported; never crash the run.
