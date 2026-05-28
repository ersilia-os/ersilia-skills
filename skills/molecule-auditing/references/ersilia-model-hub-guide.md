# Ersilia Model Hub Guide (for molecule auditing)

This guide complements `ersilia-metadata-guide.md`. That file documents the per-model **mechanics** (URLs, JSON/CSV schemas, the `direction` vs `want_high` distinction, the `scoring_role` taxonomy). This file documents the **judgment** layered on top of those mechanics, organised as a strict three-tier hierarchy:

- **Tier 1 — In-dataset models.** eos IDs whose output columns are present in the CSV. *Considered* — they drive scoring and filtering, and every one of them must be accounted for in the audit report.
- **Tier 2 — Curated relevant set.** Hand-maintained list of Ersilia models known to be useful for typical molecule-auditing scenarios (ADMET, antimicrobial activity, safety). *Suggested first* whenever a category gap is found. Source of truth: `curated_models.yaml`.
- **Tier 3 — Full Ersilia Model Hub (last resort).** The live Airtable catalogue (~170 Ready models). *Suggested only* when the curated set has no model matching **this dataset's specific context** — pathogen, target, or property — even if the category is abstractly covered by tier 2.

Apply the tiers in order: classify tier 1 first, then identify gaps and fill them from tier 2, escalating to tier 3 only on context-fit failure. All tiers depend on knowing each model's metadata — always start by fetching it via `scripts/fetch_model_metadata.py` (see `ersilia-metadata-guide.md`).

---

## What Ersilia is (in one paragraph)

The [Ersilia Model Hub](https://github.com/ersilia-os/ersilia) is an open-source library of pre-trained AI/ML models for infectious-disease and neglected-disease drug discovery (antimicrobial activity, ADMET, toxicity, generative chemistry, molecular representations). Each model lives in its own GitHub repository under the `ersilia-os` organisation with a stable `eos[0-9a-z]{4}` identifier, and the full hub catalogue is maintained in an Airtable base (see §Live lookup below). Models are designed to consume SMILES strings and emit either a score, a value, or a richer object — the column conventions are documented in `ersilia-metadata-guide.md`.

---

## Tier 1 — Interpreting Ersilia columns already in the dataset

The classification rules — what a column is *for*, whether it is `efficacy` / `safety_flag` / `beneficial_admet` / `physicochemical` / `info`, and whether `want_high` is `true` / `false` / `null` — are already specified in `ersilia-metadata-guide.md` (see its §"Scoring Role and Desirability" and §"Common Ersilia ADMET column patterns"). Do not duplicate that reasoning here; do it once per column following the existing guide.

What this skill adds is a **reporting contract**: every Ersilia column in the dataset must be visibly accounted for in the audit report so the reader can see which columns drove decisions and which were ignored. Group columns into four **filtering-utility buckets**:

| Bucket | Maps to `scoring_role` | What the audit does with it |
|---|---|---|
| `filterable_quantitative` | `efficacy`, `beneficial_admet` (when `want_high` is set) | Use as a ranking or soft-threshold filter. Show in the Top Candidates table. |
| `filterable_flag` | `safety_flag` | Apply a hard or soft cutoff (default `flag_threshold = 0.5`). Flag offenders in the report. |
| `range_constrained` | `physicochemical` | Apply Lipinski/Veber-style range rules from `drug-discovery-criteria.md`. Do not score directionally. |
| `informational` | `info` (featurisers, embeddings, fingerprints, projections, raw similarities) | **Do not filter on these.** Surface only as context, novelty/clustering input, or in the Column Guide. |
| `ambiguous` | any column where `metadata.json` / `run_columns.csv` could not be fetched, or where `Interpretation` is missing and `want_high` cannot be assigned with confidence | List in the report's Caveats section. Do **not** silently use it as a filter. |

**Hard rule** — A column may only enter the aggregate score or a filtering decision if it falls in `filterable_quantitative`, `filterable_flag`, or `range_constrained`. `informational` and `ambiguous` columns are reportable but never filterable.

---

## Tier 2 — Curated relevant set

After classifying tier-1 columns, ask: **what is structurally missing from this dataset that an Ersilia model could supply?** Cover three categories, in order:

1. **ADMET / physicochemical properties** — absorption, solubility, permeability, plasma protein binding, metabolic stability, BBB penetration. A screen without any ADMET coverage cannot meaningfully prioritise for downstream development.
2. **Antibiotic / antimicrobial activity** — pathogen-specific activity. Match against `--context`, `Target Organism` metadata, or the dataset's apparent disease focus.
3. **Safety / toxicity flags** — hERG, cardiotoxicity, DILI, Tox21, clinical-trial toxicity, adverse drug reactions. A hit list without safety triage is incomplete.

For each uncovered category, **recommend 1–3 models from `curated_models.yaml`** (sibling file in this directory). The YAML is the source of truth — Read it directly and pick by `id`, `pathogen`, `want_high`, and `fit`. Do not maintain a parallel list in this doc.

**A few illustrative entries** (full list in the YAML):

- **ADMET** — `eos7m30` (multi-endpoint ADMET, one-stop coverage), `eos2lqb` (oral bioavailability), `eos1amr` (BBB penetration — context-dependent).
- **Antimicrobial** — `eos4e40` (*E. coli*), `eos9ivc` (*M. tuberculosis*), `eos4rta` (*P. falciparum* / antimalarial), `eos3lyd` (gram-negative efflux evader — useful as a secondary filter).
- **Safety** — `eos4tcc` (BayeshERG / hERG blockade), `eos5gge` (DILI), `eos69p9` (Tox21 panel).

**When tier 2 doesn't fit** — if no curated model matches *this dataset's* pathogen, target, or property (not merely the category), escalate to tier 3. See the trigger rules in the next section.

---

## Tier 3 — Full Ersilia Model Hub lookup (last resort)

Escalate to tier 3 **only** when the curated set in `curated_models.yaml` has no model that fits the dataset's specific context. The trigger is **context-fit, not category coverage**:

- ✅ Escalate: dataset targets *Neisseria gonorrhoeae*. Tier 2 has *S. aureus*, *A. baumannii*, *B. cenocepacia*, etc. — antimicrobial is "covered" abstractly but no *N. gonorrhoeae* model is present.
- ✅ Escalate: dataset is a *Schistosoma mansoni* screen. Tier 2 has no antiparasitic helminth model.
- ✅ Escalate: dataset needs a CYP2C9-specific inhibition predictor. Tier 2 has ADMET but no CYP2C9 model.
- ❌ Do **not** escalate just to fish for more options: if `eos4tcc` (hERG) is already a fine fit for a cardiac-safety gap, don't query the hub for alternatives.

**Source**: Airtable base `appR6ZwgLgG8RTdoU`, table `Models` (`tblAfOWRbA7bI1VTB`). Public shared view: <https://airtable.com/appR6ZwgLgG8RTdoU/shr7scXQV3UYqnM6Q/tblAfOWRbA7bI1VTB>.

**Preferred path — Airtable MCP** (only if the user's session has the Airtable MCP available):

1. `mcp__claude_ai_Airtable__list_tables_for_base` with `baseId = "appR6ZwgLgG8RTdoU"` to confirm the `Models` table schema.
2. `mcp__claude_ai_Airtable__list_records_for_table` with:
   - `baseId = "appR6ZwgLgG8RTdoU"`, `tableId = "tblAfOWRbA7bI1VTB"`,
   - `fieldIds = ["Identifier", "Title", "Interpretation", "Subtask", "Biomedical Area", "Target Organism", "Tag", "Status"]`,
   - filter on `Status = "Ready"` (singleSelect — use `get_table_schema` first to resolve the choice ID),
   - and a `contains` filter on `Title`, `Tag`, `Biomedical Area`, or `Target Organism` matching the gap (e.g. `"Neisseria"`, `"Schistosoma"`, `"CYP2C9"`).
3. The table has ~170 Ready models — page through with `cursor` if needed.

**Fallback — WebFetch**: GET the shared view URL above and parse the rendered HTML. Less reliable than the MCP path; only use when the MCP is unavailable.

For any model found via tier-3 lookup, immediately fetch its per-model metadata with `scripts/fetch_model_metadata.py <eos_id>` (or, as a fallback, the raw URLs in `ersilia-metadata-guide.md`) to confirm `Title`, `Interpretation`, `Task`/`Subtask`, and the `run_columns.csv` schema before recommending it.

---

## Recommendation format (applies to tier 2 and tier 3)

Recommendations from tier 2 and tier 3 use the **same format** in the audit report — the reader does not need to know which tier a suggestion came from. For each recommended model, the report must state, in this order:

1. **eos ID** as a code span, linked to `https://github.com/ersilia-os/{model_id}`.
2. **What it predicts** — one sentence, drawn from the model's `Interpretation` (preferred) or `Title`.
3. **Why it fits this dataset** — one sentence tying it to a specific gap (e.g. "the dataset has no safety columns and the top candidates include known hERG-prone scaffolds", or "the screen targets *M. tuberculosis* but no TB-specific activity column is present").
4. **Caveats** — one short clause if relevant (e.g. organism trained only on *E. coli*; output is inverted; CNS-only relevance).

Limit recommendations to **1–3 per category** to keep the report actionable. Prefer breadth (one ADMET + one antimicrobial + one safety) over depth in a single area.

---

## Output contract — new audit report sections

The `molecule-auditing` SKILL.md report template adds two sections that draw on this guide. They live alongside the existing report structure; they do not replace anything.

### `## Ersilia columns used`

A table covering every Ersilia output column detected in the dataset, in this order:

| Column | eos ID | Bucket | Role in this audit |
|---|---|---|---|
| `inhibition_50um.eos4e40` | `eos4e40` | `filterable_quantitative` | Primary efficacy — drives ranking |
| `ames.eos7m30` | `eos7m30` | `filterable_flag` | Safety flag — drops molecules with prob > 0.5 |
| `embedding_*.eos…` | `eos…` | `informational` | Not used for filtering; available for clustering |
| `logp.eos7m30` | `eos7m30` | `range_constrained` | Lipinski filter (≤ 5) |
| `…` (unfetchable) | `eos…` | `ambiguous` | Listed in Caveats; not used for filtering |

This section sits **before** the existing "Audit Results" → "Top Candidates" section so the reader sees what drove the ranking before seeing the ranking.

### `## Recommended additional Ersilia models`

A flat bulleted list, grouped by the three categories. Skip any category fully covered by columns already in the dataset. If a category is fully covered, say so explicitly in a one-line note rather than omitting the heading silently.

```markdown
### ADMET / physicochemical
- [`eos2lqb`](https://github.com/ersilia-os/eos2lqb) — Probability of high human oral bioavailability. The dataset has activity and safety coverage but no absorption signal; this would help prioritise orally-deliverable hits.

### Antimicrobial activity
- _Already covered_ — `eos9ivc` (antituberculosis activity) is present.

### Safety / toxicity
- [`eos4tcc`](https://github.com/ersilia-os/eos4tcc) — Probability of hERG channel blockade. None of the existing columns flag cardiac liability; recommended as a hard safety gate before progressing any hit.
- [`eos5gge`](https://github.com/ersilia-os/eos5gge) — Drug-Induced Liver Injury prediction. Complements hERG for a minimum safety triage.
```

This section sits **at the end** of the Audit Results, just before Caveats — it points forward, not at the current screen.
