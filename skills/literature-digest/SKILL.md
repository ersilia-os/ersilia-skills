---
name: literature-digest
description: >
  Produce the weekly Ersilia literature digest. Primary mission: surface every model
  and dataset that could plausibly join the Ersilia Model Hub — across all six Hub
  task families (Property prediction, Activity prediction, Featurization, Projection,
  Similarity search, Generation), with antimicrobial / antipathogen drug discovery as
  the most-prioritised disease lens. Secondary mission: keep the team current on
  agentic AI for science, automation in chemistry, open-source drug discovery, and
  global health. Apply an explicit LMIC and decolonisation lens throughout. Use this
  skill whenever the user asks to prepare, run, or refresh the literature digest.
  Triggers include: "weekly literature digest", "literature digest for Ersilia",
  "/literature-digest", "lit digest this week", "what did we miss last week", "digest
  the literature". Always use this skill for digest requests even if the ask seems
  simple.
---

# Ersilia Literature Digest

You produce the weekly literature digest for **Ersilia Open Source Initiative** — a
curated markdown file whose primary job is to **hunt for models and datasets the
Ersilia Model Hub could incorporate**, and whose secondary job is to give the team
contextual reading on antimicrobial / antipathogen drug discovery, agentic AI for
science, automation in chemistry, open-source drug discovery, and global health.

The digest is read by the whole Ersilia team. Assume shared internal context (Hub,
H3D, GC-ADDA, Chemical Checker, Boltz-2, etc.) but write so a new team scientist can
follow.

The relevance bar has **two missions**, both required reading every week:

- **Mission A — Hub candidates.** Find every paper, preprint, repo, or release in the
  window that could become an Ersilia Model Hub entry: an open small-molecule-input
  model (Property / Activity / Featurization / Projection / Similarity / Generation),
  or an openly-released large dataset that the Hub could train or benchmark on.
  Antimicrobial / antipathogen / AMR / NTD work earns an editorial bump but is *not*
  required — generic chemistry foundation models, ADMET predictors, generative
  systems, and chemical-space tools belong here too.
- **Mission B — Context.** Cover the week's signal on antimicrobial / antipathogen
  drug discovery (disease biology, AMR policy, target work), agentic AI for science
  (multi-agent research systems, scientific copilots, AI Scientist lineage),
  automation in chemistry (self-driving labs, autonomous synthesis, robotic
  chemistry), open-source drug discovery (DNDi, MMV, OSM, GC-ADDA, H3D outputs), and
  global health.

Apply an equity lens cross-cutting both missions — LMIC-led work (per
`references/lmic-countries.md`) gets the 🌍 marker and a ranking bonus.

---

## Inputs

The user will invoke this skill with:

- (optional) a date range, e.g. `--from 2026-05-13 --to 2026-05-20`. Default: the last 7
  days ending today.
- (optional) `--out <path>` to override the local staging path. Default:
  `digests/YY-MM-DD-literature-digest.md` (end date of the window, 2-digit year)
  relative to this skill folder. For 2026-05-21 the file is
  `26-05-21-literature-digest.md`. The local file is a working copy; the canonical
  home is the remote repo `ersilia-os/digests` at
  `literature/YY-MM-DD-literature-digest.md` (Step 8).
- (optional) `--force` to override the recent-digest guards in Step 0.
- (optional) `--dry-run` to fetch and rank but not write the digest file (used for testing).

If anything is unclear, ask one focused question before proceeding. Never invent missing
inputs.

---

## Workflow

Run the steps in order. Track progress with `TaskCreate` / `TaskUpdate` if the run is
non-trivial.

### Step 0 — Pre-flight checks (two hard gates)

**Gate A — required MCPs.** The Slack MCP (workspace `ersilia-workspace`) and the
Gmail MCP must both be available in this session. These are the two highest-signal
sources for the digest, and the spec explicitly forbids generating a digest without
them. To verify, attempt one cheap read against each:

- Slack: `slack_search_channels` with `query="literature"`. If it errors with
  "MCP not available" / "tool not found" / similar, treat it as missing.
- Gmail: `search_threads` with `query="newer_than:1d"` (any small query). Same
  failure modes.

If **either** check fails, **STOP**. Tell the user which MCP is unavailable and
refuse to proceed. Do not fetch from any other source either — a digest without
Slack and Gmail is not a digest we ship. The user can re-invoke once the MCPs are
connected.

**Gate B — references not stale.** Check whether the skill's reference files are
overdue for their quarterly refresh:

```bash
python scripts/check_references_freshness.py
```

- If the script prints `OK`, continue.
- If the script prints `DUE`, the references are past their 90-day refresh
  cadence. **Pause** the run and tell the user. Offer two choices: (a) run the
  refresh procedure documented in `references/refresh-procedure.md` now (it
  re-derives the topic / author / journal / Hub priors from the Hub catalogue,
  Slack `#literature`, Google Drive grants, and Gmail Scholar alerts), or
  (b) explicitly defer and proceed with stale references — record the deferral
  in `references/_state.json`'s `refresh_log` with an explanatory note. Never
  refresh silently; the changes are editorial.
- The freshness check is non-fatal (exit 0 in both `OK` and `DUE`) so an
  emergency digest can still ship if the user defers. Exit 1 means the state
  file itself is broken — STOP and fix that before continuing.

**Gate C — no recent digest (remote first, then local).** The digest is weekly, not
redundant — and the canonical home is the remote `ersilia-os/digests` repo, so the
remote is the authoritative check. Run both, **remote first**:

```bash
python scripts/check_remote_digest.py --days 7
python scripts/check_recent_digest.py --days 7
```

- If `check_remote_digest.py` exits non-zero, the remote was unreachable. **STOP** —
  do not silently fall through to the local check, because a successful local run
  could clobber published work on retry. Surface the error to the user.
- If `check_remote_digest.py` prints a path on stdout, **STOP**. A digest already
  exists in the remote repo for this window. The default is **never** to run again
  — tell the user the remote path (and the html URL from stderr) and explicitly ask
  whether they want to override with `--force`. Do not assume yes.
- If `check_recent_digest.py` prints a path, **STOP** the same way (a local working
  copy exists; offer to upload the existing one instead of regenerating).
- Only if **both** checks come back empty, continue to Step 1.

The cutoff is the date encoded in the filename (`YY-MM-DD-literature-digest.md`,
or the legacy `YY-MM-DD-digest.md`), not the filesystem mtime. A digest dated within
the last 7 days blocks a new run.

### Step 1 — Load context

Read these reference files into context before fetching anything:

- `references/search-landscape.md` — topics, keywords, authors, journals, task taxonomy,
  and the ranking weights.
- `references/lmic-countries.md` — World Bank low/lower-middle income countries (the 🌍
  rule).
- `references/source-catalogue.md` — which sources are in v1 vs. deferred, and the schema
  for normalised items.
- `references/output-template.md` — exact structure of the digest file.

Do not paraphrase these — quote them when relevant.

### Step 2 — Build the seen-items set (from the remote repo)

```bash
python scripts/parse_prior_digests.py --last 8 --out /tmp/seen.txt
```

This pulls the last 8 published digests from `ersilia-os/digests/literature/` via
`gh`, downloads their bodies, and emits a flat list of DOIs, arXiv IDs, and URLs
to exclude. The **remote** repo is the source of truth — local `digests/` files
are just working copies and may be stale.

- If the remote `literature/` directory does not exist yet (first-ever run), the
  script emits an empty file and exits 0 — fine.
- On any other remote error the script exits 1. Treat that as a hard failure
  (same posture as Step 0 Gate B): without a valid seen-set, the digest could
  duplicate items already published.
- The `--also-local` flag is available for development; production runs do not
  use it.

### Step 3 — Fetch from sources (v1)

Four MVP connectors, two patterns. Run the API-based ones (bioRxiv, Europe PMC) in
parallel; the MCP-based ones (Slack, Gmail) need a two-step collection because the
MCP is not callable from Python subprocesses.

Track per-connector status (success / failure + reason) as you go — it feeds the
digest's connector semaphore (Step 7). Per-connector item counts and failure
reasons are NOT included in the digest itself; the semaphore is the only
connector signal that ships.

**API-based** — straight subprocess calls:

```bash
python scripts/fetch_biorxiv.py    --from {start} --to {end} --out /tmp/bx.json
python scripts/fetch_europepmc.py  --from {start} --to {end} --out /tmp/epmc.json
```

**Slack** — workspace handle is `ersilia-workspace`:

1. Use the Slack MCP yourself:
   - `slack_search_channels` to locate `#literature` (or the closest match — log
     the channel name).
   - `slack_read_channel` to read messages in the date range.
   - For each unique message author, optionally call `slack_read_user_profile` for
     a real name to use as attribution.
2. Save the collected messages as a JSON list to `/tmp/slack_raw.json`. Each
   message needs `text` and `ts`; include `user_real_name` (or `user_name`),
   `permalink`, and `channel_name` whenever available.

```bash
python scripts/fetch_slack.py --raw /tmp/slack_raw.json --out /tmp/slack.json
```

**Gmail** — high-signal source: Google Scholar alerts, curated newsletters,
publisher table-of-contents emails, and collaborator threads sharing links.
**Do not include the user's email address anywhere in the digest** — label the
connector by what it covers, never by the inbox it reads.

1. Use the Gmail MCP yourself, scoped to the user's inbox (the harness already knows
   which account). **The single highest-recall query is the user-maintained
   `Research-Updates` Gmail label** — they tag everything literature-relevant under
   it. Pull from it exhaustively first, then top up with the per-sender buckets if
   anything looks missing:
   - **Whole `Research-Updates` label**:
     `label:Research-Updates after:YYYY/MM/DD` (use the window start date). This
     subsumes the Scholar alerts, journal ToC ealerts (Nature/NMI/Nat Comms/Comm
     Chem/Comm Med/Comm Bio, Cell Press, eLife, Wiley/ChemMedChem, ACS journal
     alerts for JCIM/J Med Chem/ACS Med Chem Lett/ACS Infect Dis/ACS Omega,
     Lancet, BMJ, npj Digital Medicine), and the curated weekly digests
     (Semantic Scholar, The Academic Digest, *Nature Briefing*).
   - **Scholar alert fallback**: `from:scholaralerts-noreply@google.com
     newer_than:7d` (also `scholarcitations-noreply@google.com`) — use only if
     the label query returns nothing or is unavailable.
   - **Collaborator mentions**: any other thread in the window where a paper or
     code link was shared. Be conservative — only include threads whose body
     contains a DOI, arXiv ID, bioRxiv/chemRxiv URL, GitHub repo URL, or
     Hugging Face URL.

   **ToC alerts are dense.** A single NMI/JCIM/Nat Comms email contains 10–30
   paper links and may bust the MCP's per-thread output limit. When that happens
   the `get_thread` tool error message gives you the path to the on-disk dump —
   parse it with `python3` + a regex on the HTML, then verify the resulting
   DOIs/first-authors via Crossref (see step 6 below).
2. For each thread, call `get_thread` to get the body text. Assemble a JSON list
   `/tmp/gmail_raw.json` with one object per thread:
   ```json
   {"id": "...", "subject": "...", "sender": "scholaralerts-noreply@google.com",
    "sender_name": "Google Scholar Alerts", "date": "YYYY-MM-DD",
    "body_text": "...", "snippet": "...", "thread_url": "https://mail.google.com/..."}
   ```
3. Then normalise:

```bash
python scripts/fetch_gmail.py --raw /tmp/gmail_raw.json --out /tmp/gmail.json
```

The normaliser deliberately drops the raw `sender` (email address) from output so
that downstream digests cannot leak it; only the human-friendly display name
survives.

**Graceful degradation for API sources only.** The two MCP sources (Slack and Gmail)
are *required* (Step 0 already gated on this); if either becomes unreachable
mid-run, that is a hard failure — abort with the same message as Gate A. The two
API sources (bioRxiv, Europe PMC) can degrade: if one errors, mark it 🔴 in the
connector semaphore and continue with the remaining three.

**Phase B / C sources** (arXiv, chemRxiv, Semantic Scholar, journal RSS, GitHub,
Hugging Face): not in MVP. If you see scripts for these in `scripts/`, run them
too; otherwise skip silently. They do not get a row in the connector semaphore
unless they actually exist as MVP connectors.

### Step 4 — Deduplicate and rank

```bash
python scripts/dedup_and_rank.py \
  --in /tmp/bx.json --in /tmp/epmc.json --in /tmp/slack.json --in /tmp/gmail.json \
  --seen /tmp/seen.txt \
  --landscape references/search-landscape.md \
  --lmic references/lmic-countries.md \
  --out /tmp/pool.json
```

This produces a top-~80 pool with score breakdowns. The pool is what you triage in Step 5
— do not fall back to the raw fetched data.

### Step 4.5 — Supplementary web hunt (only if the pool is thin on Hub candidates)

This step is the safety net for Mission A. After `dedup_and_rank.py` writes
`/tmp/pool.json`, scan the pool and count items that look like 🤖 candidates (open
small-molecule model with code or weights, fits a Hub task) and 🗃️ candidates
(openly-released dataset, ≥10k rows, Hub-relevant endpoint). Use the
model-release-verb and dataset-release-verb signals already added by
`dedup_and_rank.py` as the cheap proxy.

If the pool has **fewer than 8 🤖 candidates** OR **fewer than 2 🗃️ candidates**,
run a bounded supplementary search using the `WebSearch` and `WebFetch` tools the
harness provides. Targets, in priority order:

1. **HuggingFace recent uploads** — `WebSearch` queries scoped to
   `site:huggingface.co/models` with tags `molecule`, `cheminformatics`,
   `chemistry`, `drug-discovery`, `protein-language-model`,
   `molecular-property-prediction`. Look for upload dates inside the digest window.
2. **GitHub trending in the last 7 days** — `WebSearch` for
   `site:github.com` + `trending` + (`cheminformatics` OR `drug-discovery` OR
   `qsar` OR `molecular-property-prediction` OR `de-novo-design` OR
   `antimicrobial`). Confirm the repo's most-recent commit is inside the window.
3. **arXiv recent submissions** — `WebSearch` for `arxiv.org` recent in
   `cs.LG` / `q-bio.BM` / `q-bio.QM` / `cs.AI` with chemistry / drug-discovery
   keywords from `search-landscape.md`'s Methods × Diseases axes.
4. **Targeted DOI / arXiv ID lookups** — if a Slack or Gmail message in the window
   mentioned a paper but the connector dropped the metadata, search the
   title/snippet via WebSearch to recover the DOI or arXiv ID, then `WebFetch` the
   abstract.

Hard caps:

- **At most 10 supplementary items** added to the pool. The web hunt is a top-up,
  not a primary source.
- **At most 6 minutes** of wall time across all web hunt queries. Budget aggressively.
- Each supplementary item must carry a verifiable URL (paper, preprint, model card,
  or repo) before being added.

For each kept item, normalise into the standard schema (`title`, `authors`, `venue`,
`date`, `doi` or `arxiv_id` or `url`, `abstract`, `source: "web_hunt"`,
`source_subtype: "huggingface" | "github" | "arxiv" | "doi_lookup"`) and append to
the pool. Then re-run the ranking pass:

```bash
python scripts/dedup_and_rank.py \
  --in /tmp/pool.json --in /tmp/web_hunt.json \
  --seen /tmp/seen.txt \
  --landscape references/search-landscape.md \
  --lmic references/lmic-countries.md \
  --out /tmp/pool.json
```

Record the outcome for the connector semaphore (Step 7):

- `Web hunt ⚪` — not triggered (pool already had ≥8 🤖 and ≥2 🗃️).
- `Web hunt 🟢` — triggered and added at least one new item.
- `Web hunt 🔴` — triggered, all sub-searches failed or returned nothing usable.

If the web hunt fails entirely, that is **not a hard failure** — proceed to Step 5
with whatever the pool contains. The empty-chapter rule in
`references/output-template.md` handles thin weeks gracefully.

### Step 5 — LLM triage to the final 25–40

Read `/tmp/pool.json`. **Your default posture is "find more models and datasets",
not fewer.** Aim for **≥8 🤖 candidates and ≥2 🗃️ datasets in the final digest**.
If the pool yields fewer, do not pad with off-mission items — instead loop back to
Step 4.5 (web hunt) once more, then accept the lower count and render the
empty-chapter placeholder rather than promoting weak candidates.

Triage in three passes: (5a) Mission A — Hub candidates, (5b) Mission B — context,
(5c) chapter assignment + ordering.

#### Step 5a — Mission A: identify Hub candidates

For every item in the pool, evaluate against the **Hub-incorporability checklist
for models** below. Take notes (mental or scratch) on each row — the body sentence
in Step 6 must speak to these answers.

**Hub-incorporability checklist (🤖)**:

| # | Question | Pass criterion | If fail |
|---|---|---|---|
| 1 | **Input modality** | Accepts SMILES / InChI / molfile / SDF as the primary input. CPI (compound–protein interaction) models pass — the molecule is the primary input. | No 🤖. Surface as context with `(input: {modality})` annotation, in chapter 3 (methods) or wherever topical. |
| 2 | **Output** | Produces a numeric score, vector, label, or molecule(s) — i.e. something the Hub `predict` / `featurize` / `generate` interface can return. | No 🤖. |
| 3 | **Task fit** | Slots into one of: Property prediction, Activity prediction, Featurization, Projection, Similarity search, Generation. | No 🤖; mention task mismatch. |
| 4 | **Code availability** | A public repo URL (GitHub / GitLab / Codeberg / HuggingFace Space) is named in the paper or in the model/dataset release page. | No 🤖. (Independent of 💻 — see below.) |
| 5 | **Weights availability** | Trained weights are released (HuggingFace, Zenodo, repo release, or supplementary). | 🤖 with `(weights: pending)` qualifier; flag for follow-up. |
| 6 | **License** | Permissive enough for Ersilia redistribution — MIT, Apache-2.0, BSD-2/3-Clause, CC-BY, CC-BY-SA, MPL-2.0. CC-NC, GPL/AGPL-only, "research-only" or "non-commercial" all fail. | No 🤖. Note the license blocker in the body sentence and surface as context. |
| 7 | **Inference reproducibility** | Dependencies are tractable — no proprietary library, no hardware lock-in beyond a single GPU, no cloud-API call required for inference — i.e. plausibly runnable inside an Ersilia model container. | 🤖 with `(infra: heavy)` qualifier; flag for follow-up. |

Decision:

- **Before running the checklist:** ask the seven conditional-route trigger
  questions (C1–C7) from `references/hub-incorporation-criteria.md` for any
  item that looks gated out by criteria 1–3. If a trigger fires, assign 🤖❓
  and write the conditional body sentence (template in that reference file)
  rather than the standard one below — then skip the checklist for that item.
- Items passing **1–4 and 6** unconditionally get 🤖.
- Items passing **1–4 + 6** but failing 5 or 7 still get 🤖 (still a candidate),
  and the body sentence must say so concretely
  (e.g. "weights not yet released" or "requires a 4×A100 inference budget").
- Items failing any of 1–3 or 6 and not matching any C1–C7 trigger do **not**
  get 🤖 or 🤖❓. They may still appear as context in chapter 3 (methods) with
  the failing dimension named.
- A paper carries **either** 🤖 or 🤖❓, never both. Within a chapter, 🤖
  entries sort first, then 🤖❓, then unannotated.
- 💻 is **independent** of 🤖 / 🤖❓. 💻 applies only when the abstract or paper
  page explicitly names a public repo URL — Crossref/EuropePMC abstracts often
  omit code mentions; do not infer code presence from "this work is open" or
  "code available upon request". Default-off when uncertain. An item can carry
  🤖 without 💻 (e.g. weights on HuggingFace, no repo) and vice versa.

**Body-sentence pattern for 🤖 entries.** Replace generic "could be a drop-in
featurizer" with a structured one-liner naming **(input → output / task / license /
hook)**:

```
Open-source {task} model taking {input modality} → {output type};
released with {weights/code} under {license}. Plausible Hub addition because {hook}.
```

Worked example:

> Open-source activity-prediction model taking SMILES → IC50 (regression);
> released with weights and inference code on GitHub under Apache-2.0.
> Plausible Hub addition because it covers *M. tuberculosis* H37Rv whole-cell,
> a Hub gap.

**Dataset-incorporability checklist (🗃️)**:

| # | Question | Pass criterion |
|---|---|---|
| 1 | **Scale** | ≥10,000 compounds (or rows in a Hub-relevant table). Smaller per-paper training sets do **not** warrant 🗃️. |
| 2 | **Endpoint** | Bioactivity (IC50/MIC/Ki/EC50), ADMET property, toxicity, generative target distribution, or embedding/representation benchmark. |
| 3 | **Public download** | A direct download URL is named in the paper (Zenodo / HF / repo / journal supplementary). |
| 4 | **License** | CC-BY, CC-BY-SA, CC0, ODC-By, ODbL, MIT / Apache-2.0 (for code-shipped datasets), or equivalent. CC-NC / academic-only fail. |
| 5 | **Format** | SMILES (or convertible from InChI / SDF / molfile / 2D structure file) is in the file. Images-only or figures-only datasets fail. |

Items passing all five rows get 🗃️. Borderline cases (e.g. 5,000 compounds but on
a Hub-priority endpoint with no equivalent existing) may be promoted at editorial
discretion — note the size in the body sentence.

**Body-sentence pattern for 🗃️ entries**:

```
{N} compounds / rows · {endpoint} · {license} · {download host}.
Plausible Hub input because {hook}.
```

**Gated-out but interesting (no 🤖, surface as context).** Some models are too
interesting to drop but fail the small-molecule input gate or the license gate.
Surface them in **chapter 3** (AI/ML methods) without 🤖, with the gating
dimension named:

- Protein-conditioned / pocket-conditioned generators (DiffDock-Pocket,
  Pocket2Mol, TargetDiff, RFdiffusion-AA, ShEPhERD-pocket).
- Protein-sequence-only / structure-only models (Boltz-2, Chai-1, ESM-style).
- Multi-omics or transcriptomics-input models.
- Image-input phenotypic models.
- Commercial-license-only releases (note the license in the body).

These do not block the 🤖 quota — they are *additive* context.

#### Step 5b — Mission B: context items

For items that are *not* Hub candidates, decide whether they belong in chapters
3–6 (the context chapters). Acceptance criteria:

- **Chapter 3 (AI/ML methods for drug discovery)** — methodology papers,
  benchmarks, reviews, perspectives, gated-out models from 5a, AI-for-chemistry
  surveys, retrosynthesis advances, virtual-screening protocol papers. Lean
  inclusive on representation / projection / similarity papers — these task
  families are under-represented in the Hub (3–6 % each) and the user explicitly
  wants them surfaced even when modest.
- **Chapter 4 (Antibiotic and antimicrobial discovery)** — disease biology of
  bacterial / mycobacterial / fungal / parasitic / viral pathogens, AMR
  surveillance, AMR policy, target-structure papers on pathogen proteins,
  medicinal-chemistry SAR campaigns. Antimicrobial / antipathogen items get an
  editorial bump: rank them above same-tier non-antimicrobial items inside any
  context chapter.
- **Chapter 5 (AI agents and foundation models for science)** — multi-agent
  research systems (Sakana AI Scientist, Co-Scientist, FutureHouse, ChemCrow,
  PaperQA, BioPlanner), scientific copilots, self-driving labs, autonomous
  synthesis, robotic chemistry, closed-loop optimisation, autonomous drug
  discovery papers. Surface even when not antimicrobial-specific — the user
  explicitly wants these.
- **Chapter 6 (Global health and open science)** — LMIC-led work, NTDs,
  capacity-building, AMR/NTD funding/policy, open-science infrastructure
  releases, decolonisation pieces, DNDi / MMV / GHIT / GARDP / CARB-X /
  Schmidt / AI2050 / EDCTP3 outputs.

Discard items you cannot link to a primary source, items where you cannot write
a credible "why it matters for Ersilia" one-liner, and disease-specific cancer /
cardiology / diabetes / RNA-only papers unless they are *highly* relevant (e.g.
a generic chemistry-foundation model exemplified on oncology). Default to
omitting borderline items rather than padding the digest.

#### Step 5c — Chapter assignment and ordering

**De-duplication rule (important):** every 🤖 item lives **only** in chapter 1
("Models that could join the Hub"). Every 🗃️ item lives **only** in chapter 2
("Datasets that could join the Hub"). Do **not** also place them in chapters 3–6.
This guarantees the reader sees Hub candidates in one place, and context items in
one place.

Within chapter 1, group by task family using `###` subheadings (Activity →
Property → Featurization → Generation → Similarity → Projection — descending Hub
share). Within each subheading, sort by venue tier (NMI / JCIM / J Cheminform /
Nat Comms / NAR before bioRxiv / chemRxiv / arXiv), then by recency.

Within chapter 2, group by endpoint family using `###` subheadings (Bioactivity →
ADMET / Property → Generative training corpora → Featurization / multi-task
benchmarks → Other).

Within chapters 3–6, no subheadings. Sort by venue tier then recency; rank
antimicrobial / antipathogen items above same-tier non-antimicrobial items.

Apply the equity lens last: check that LMIC-led work is surfaced where it exists
(🌍 marker per `references/lmic-countries.md`). If a paper about LMIC pathogens
has no LMIC authorship, note the gap rather than promoting it.

Target total item count: **25–40 across all chapters**, with at least 8 🤖 and 2
🗃️ as the minimum healthy week. Density is the goal; the format is one bullet per
item.

### Step 6 — Compose each entry

For every chosen item, write the entry following `references/output-template.md` exactly.
Specifically:

- **Verify the first-author surname and the publication date via Crossref before
  composing.** Gmail Scholar alerts and publisher ToC HTML often truncate or
  reorder author lists, and inferring "First et al." from a snippet is how the
  v1/v2 of this digest leaked fabricated names like "Smith et al." into entries
  that should have read "Augustine et al." Run a quick
  `https://api.crossref.org/works/<doi>` lookup (or
  `https://api.crossref.org/works?query.title=...&filter=container-title:<journal>`
  when only the title is known) and use `message.author[0].family` and
  `message.published.date-parts[0]`. Same rule for arXiv IDs (resolve via
  Crossref or arXiv's own API). If lookup fails, omit the author rather than
  guessing.
- Entries are **one bullet line each** in the format defined by
  `references/output-template.md`: `[Author et al., *Venue*, YYYY](url) {ribbon}
  — **Title.** Combined why-matters + TL;DR.`
- Inline curation markers (`⭐ 🌍 🤖 🗃️ 💻`) in fixed display order, only when
  load-bearing. See `output-template.md` for criteria.
- **Body language**: impersonal. Never name a team member, never name an internal
  Slack channel, never use first-person plural. The digest is publicly hosted on
  `ersilia-os/digests`.
- `Authors` line — name the lead institution.
- `Venue` line — preprint server or journal, plus the publication date.
- `TL;DR` — 1–2 sentences. Plain language. Write fresh. Never paste the abstract verbatim.
- `Why it matters for Ersilia` — required, one sentence, specific. Name the Hub model, NTD
  pipeline, partner institution, or open-source release that ties it to Ersilia.
- `Links` — paper URL, DOI, code, model/dataset if present.
- For Slack items, include `**Shared by**: @{sharer}` above the `Links` line.

### Step 7 — Render the digest file

Write to the default local staging path unless `--out` was provided:

`skills/literature-digest/digests/{YY}-{MM}-{DD}-literature-digest.md`

(2-digit year, end date of the window — e.g. `26-05-21-literature-digest.md`).
This is the working copy; the canonical home is the remote repo published in Step 8.
Include:

- The minimal header (just the H1 title line from `references/output-template.md`).
- The connector semaphore line.
- Chapter headings, in order, each followed *directly* by its bulleted entries.
  No framing sentences under chapter headings — go straight to the bullets.
- The file ends with the last bullet of the last chapter. **No** methodology
  notes, **no** suggested follow-ups, **no** trailing horizontal rule, **no**
  per-item sharer attribution. The digest sits in a public repo; internal
  channels and team-member names never appear.

The `digests/` folder is `.gitignored` — the file lives locally but is not committed by
default.

### Step 8 — Upload to the canonical remote and hand off

The local file in `digests/` is a working copy. The canonical home is
`github.com/ersilia-os/digests` at `literature/{YY}-{MM}-{DD}-literature-digest.md`.
Upload via:

```bash
python scripts/upload_digest.py --digest digests/{YY}-{MM}-{DD}-literature-digest.md
```

- The script uses `gh` (which must be authenticated; `gh auth status` checks this).
- It **refuses to overwrite** an existing remote file unless `--force` is passed.
  This is belt-and-braces with Step 0 Gate B — if you somehow got past the
  pre-flight, the upload still won't clobber.
- After uploading the digest file, the script also updates the repo's
  `README.md` under the `## Literature digests` heading with a line like
  `- [YYYY-MM-DD](literature/YY-MM-DD-literature-digest.md)`. Entries are kept
  in date-descending order; the operation is idempotent. Pass `--no-readme` to
  skip this step (rarely useful in production).
- On success it prints URLs on stdout, one per line: **line 1 is the canonical GitHub
  Pages URL** (`https://ersilia-os.github.io/digests/literature/{YY-MM-DD}-literature-digest.html`),
  line 2 the github.com source blob, then download/README URLs. Hand the **Pages URL** to
  the user and use it in the Slack alert. Do **not** present the local path as the primary
  artefact — the remote is canonical.
- On exit code 2 (remote file already exists), surface the message to the user and
  ask whether to re-run with `--force`. Do not retry silently.

If the upload fails for a recoverable reason (network blip, gh auth lapsed), keep
the local file intact and tell the user how to re-run just the upload step. Never
delete the local file before a successful upload.

### Step 9 — Post the rich Slack alert (only on successful push)

After (and **only** after) `upload_digest.py` exits 0, post a single rich,
multi-section notification to `#literature` so the team sees what is in the digest
without having to click through. The Slack alert is **not** a pointer — it is the
preview that earns the click.

Use the Slack MCP directly:

```text
slack_send_message(
    channel_id = "C010067BP2Q",  # #literature on ersilia-workspace
    message = <rendered template from references/slack-alert-template.md>
)
```

**Composition.** Re-read the digest you just uploaded. Render the template at
`references/slack-alert-template.md` by extracting:

- Top ~5 entries from **chapter 1** (🤖 models) in venue-tier + recency order.
  Preserve each entry's structured "input → output / task / license + code" body
  framing — condense to one Slack line each but do not lose the key facts.
- Top ~3 entries from **chapter 2** (🗃️ datasets) using the structured `N ·
  endpoint · license · host` framing.
- Top ~3 ⭐-marked entries from anywhere in the digest (big-picture / must-reads,
  typically agentic AI or major reviews).
- Top ~3 🌍-marked entries (LMIC-led) from anywhere in the digest.
- Total counts strip (N items / 🤖 / 🗃️ / 🌍 / ⭐).

See `references/slack-alert-template.md` for the exact section order, field rules,
and Slack-markdown conventions. The template requires the *bold title* of each
selected bullet to match the digest verbatim — no fresh paraphrase — so a clicking
reader sees the same headline twice.

**Posting rules**:

- **Do not** post if the upload failed (any non-zero exit from `upload_digest.py`),
  if `--dry-run` was set, or if the digest was generated but not actually pushed.
- **Do not** mention team members by name. **Do not** name internal channels
  beyond what Slack itself routes.
- The 📚 prefix on the header is the only allowed extra emoji beyond the digest's
  curation markers (⭐ 🌍 🤖 🗃️ 💻 + the six task emojis).
- Post once per push. If the upload was a `--force` overwrite, still post once —
  the team should know the digest has been updated.

---

## Things to avoid

- Do not include items you cannot link to a primary source.
- Do not summarise abstracts verbatim — write a fresh TL;DR.
- Do not include items just because they are popular if they are off-scope.
- Do not invent or guess DOIs, authors, or dates. If a field is uncertain, omit it.
- Do not use emojis other than the six allowed markers: ⭐ (very-high-impact venue),
  🌍 (LMIC-led work), 🤖 (Hub-incorporable model/tool), 🗃️ (dataset for training or
  evaluation), 💻 (open code linked from the paper), and 🟢 / 🔴 in the connector
  semaphore. They appear inline in the entry's emoji ribbon, in fixed order
  ⭐🌍🤖🗃️💻. See `references/output-template.md` for when to apply each.
- Do not promote work *about* LMICs without LMIC authorship into the equity section. Note
  the gap instead.
- Do not commit the digest to git unless the user explicitly asks. `digests/` is gitignored
  by default for a reason.

---

## Scheduling

This skill is invoked manually by default. To run it weekly:

```text
/schedule create literature-digest --cron "0 8 * * 1" --command "/literature-digest"
```

(Monday 08:00 local time.) The `schedule` skill handles the cron wiring; see its SKILL.md
for options. Self-scheduling is intentionally not built in — running this requires the
Slack and Gmail MCPs to be live in the session, which is easier to guarantee for a manual
run than a cron.

---

## Future work (documented, not implemented)

- **Phase B sources**: arXiv, Gmail Scholar alerts.
- **Phase C sources**: chemRxiv, Semantic Scholar (citation-aware ranking), named-journal
  RSS, Gmail-delivered newsletters (Decoding Bio, Asimov Press, Pat Walters, Owl Posting),
  GitHub topic search, Hugging Face Hub.
- **LinkedIn**: deferred until Claude in Chrome is wired up.
- **Handoff to `newsletter-drafting`**: a future flag could re-package the digest's high-
  impact items as a newsletter block. Today this is manual.
- **Affiliation parsing**: v1 takes the first listed affiliation per author. v2 should
  handle multi-affiliation senior authors and use ROR / Crossref for country resolution.
