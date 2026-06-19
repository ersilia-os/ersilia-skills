---
name: literature-digest
description: >
  Produce the weekly Ersilia literature digest covering AI/ML for drug discovery,
  antibiotic and antimicrobial discovery, NTDs and AMR, and open science for global
  health — through an explicit LMIC and decolonisation lens. Use this skill whenever
  the user asks to prepare, run, or refresh the literature digest. Triggers include:
  "weekly literature digest", "literature digest for Ersilia", "/literature-digest",
  "lit digest this week", "what did we miss last week", "digest the literature".
  Always use this skill for digest requests even if the ask seems simple.
---

# Ersilia Literature Digest

You produce the weekly literature digest for **Ersilia Open Source Initiative** — a curated
markdown file covering AI/ML for drug discovery, antibiotic and antimicrobial discovery, NTDs
and AMR, and open science for global health.

The digest is read by the whole Ersilia team. Assume shared internal context (Hub, H3D,
GC-ADDA, Chemical Checker, Boltz-2, etc.) but write so a new team scientist can follow.

The relevance bar is **three-pillar**: an item qualifies if it touches *either* an AI/ML
method plausibly applicable to drug discovery, *or* an Ersilia-relevant disease, *or* an
open-science / capacity-building / LMIC-policy story. Apply the equity lens throughout —
LMIC-led work (per `references/lmic-countries.md`) gets the 🌍 marker and a ranking bonus.

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
  --in /tmp/bx.json --in /tmp/epmc.json --in /tmp/slack.json \
  --seen /tmp/seen.txt \
  --landscape references/search-landscape.md \
  --lmic references/lmic-countries.md \
  --out /tmp/pool.json
```

This produces a top-~50 pool with score breakdowns. The pool is what you triage in Step 5
— do not fall back to the raw fetched data.

### Step 5 — LLM triage to the final 25–35

Read `/tmp/pool.json`. For each item:

- **Filter to scope first.** An item must fit one of three buckets to belong
  in the digest:
  1. **Antibiotic / antimicrobial / AMR drug discovery** — including TB, NTD
     antibacterials, AMP / peptide-antibiotic work, AMR surveillance with an
     ML hook.
  2. **Global health / LMIC drug discovery / open-science capacity-building**
     — NTDs (malaria, leishmaniasis, HAT, schistosomiasis, etc.), Africa /
     LMIC-led work, public datasets / open infrastructure releases.
  3. **General-purpose AI methods for drug discovery** — featurizers, ADMET
     and toxicity predictors, generative chemistry, CPI / docking surrogates,
     synthesis planning, retrosynthesis, multi-task chemistry foundation
     models, open chemistry datasets, methodology reviews that map the field.
  Disease-specific cancer / cardiology / diabetes / RNA-only / protein-only
  papers do **not** qualify unless they are *highly* relevant (e.g. an open
  general-purpose dataset that happens to be exemplified on oncology). Default
  to omitting borderline items rather than padding the digest.
- **Apply Hub-incorporability as the primary lens within scope.** Re-read
  `references/hub-incorporation-criteria.md` before triaging. The single most
  important question for in-scope items is: "could this become an Ersilia
  Model Hub entry?" Activity prediction, featurization, and property
  prediction together account for 86 % of Ready Hub models — weight items in
  those subtasks heavier than everything else.
- **Small-molecule input is the gate for 🤖.** The Hub's current incorporation
  surface only accepts small-molecule input (SMILES / InChI / molfile). A
  model with protein-sequence, RNA, peptide, gene, transcriptomic, image, or
  pocket-tensor input is **not** 🤖-eligible no matter how impressive — surface
  it as a context item without 🤖 and call out the input modality so the team
  knows why. Same for generators that require non-molecule conditioning
  (pocket-conditioned, RNA-target-conditioned). Reciprocally, compound-protein
  interaction models *are* 🤖-eligible because the primary user-facing input
  is the small molecule.
- **Be conservative with 💻.** Only apply 💻 when the abstract or paper page
  explicitly names a public repo URL. Crossref/EuropePMC abstracts often omit
  code mentions; do not infer code presence from "this work is open" or "code
  available upon request". Default-off when uncertain.
- **🗃️ is for big, highly-published corpora.** Prefer datasets of tens of
  thousands of compounds upwards with clear open release and a venue that
  generates citations (e.g. COMPASS in *npj AMR*, QuantumPioneer from
  Coley/Kraft groups). Small per-paper training sets do not warrant 🗃️.
- Discard if you cannot write a credible "Why it matters for Ersilia" one-liner. If you
  cannot, the item does not belong in the digest — say so to yourself and skip.
- Assign each survivor to one of the four chapters in
  `references/output-template.md`. The 🤖 marker and trailing task emoji do the
  Hub-flagging work inline; there is no dedicated chapter.
- **Within each chapter, order entries 🤖-first.** A reader scanning the digest
  for incorporable models should see them before reviews, perspectives, or
  context items. Inside the 🤖 block, sort by venue tier (NMI/JCIM/JCheminform/
  NAR/Nat Comms before bioRxiv/chemRxiv), then by recency.
- Apply target item count from `references/output-template.md` (aim 25–35).
  Adjust to what the week actually delivered — do not pad.
- Apply the equity lens last: check that LMIC-led work is surfaced where it exists; if a
  paper about LMIC pathogens has no LMIC authorship, note it under "Known gaps" rather
  than promoting it.

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

### Step 9 — Post the Slack alert (only on successful push)

After (and **only** after) `upload_digest.py` exits 0, post a single notification
to `#literature` so the team sees the new digest. Use the Slack MCP directly:

```text
slack_send_message(
    channel_id = "C010067BP2Q",  # #literature on ersilia-workspace
    message = <rendered template from references/slack-alert-template.md>
)
```

- Render the template per `references/slack-alert-template.md`. Use the chapter
  short-forms. Compose the chapter list from chapters that actually appeared in
  the digest (skip empty ones).
- **Do not** post if the upload failed (any non-zero exit from `upload_digest.py`),
  if `--dry-run` was set, or if the digest was generated but not actually pushed.
- **Do not** mention team members by name in the Slack post (the template forbids
  it). The post is a pointer to the digest, not a summary.
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
