# Quarterly references-refresh procedure

The skill's reference files (`search-landscape.md`, `hub-incorporation-criteria.md`,
`lmic-countries.md`) drive every weekly digest's ranking and curation. If they
fall behind reality — new Hub models, new grants, new themes in `#literature` —
the digest's signal degrades silently.

This procedure refreshes them. It is **not** a weekly task. The state file
`_state.json` controls the cadence (default 90 days). When
`scripts/check_references_freshness.py` prints `DUE`, the skill should pause the
normal digest run, prompt the user to refresh, and only proceed once the
refresh is complete (or the user explicitly defers).

## Inputs to consult during a refresh

Every refresh re-derives the references from these four sources in this order.

### 1. The Hub catalogue (canonical source for what gets incorporated)

- **Where**: `https://github.com/ersilia-os/ersilia-maintenance/files/repo_info.json`
  and `ErsiliaModelsDOI.csv` in the same folder.
- **How**: pull via `gh api repos/ersilia-os/ersilia-maintenance/contents/files/repo_info.json`
  (base64-decode the `content` field). Same for the CSV.
- **What to extract**:
  - Subtask distribution across `Ready` models — refresh the table in
    `hub-incorporation-criteria.md`.
  - Top venues for incorporated publications — refresh Tier 1 in
    `search-landscape.md`.
  - New Internal / Replicated models — note what Ersilia built itself; these
    indicate where the team is investing effort.
  - Authors that appear repeatedly as Contributor or first-author on
    incorporated papers — add to the author tiers in `search-landscape.md`.

### 2. The Slack `#literature` channel (the team's reading list, last 90 days)

- **Where**: workspace `ersilia-workspace`, channel `C010067BP2Q`.
- **How**: use the Slack MCP (`slack_read_channel`) with `oldest` set to
  `today − 90 days`. Page through with `cursor`.
- **What to extract**:
  - URLs shared — group by host (Nature / Science / J Cheminform / arXiv /
    GitHub / Hugging Face / etc.). Recurring hosts inform the journal tiers.
  - Authors mentioned by name in messages. Recurring authors get promoted in
    `search-landscape.md`.
  - Topical themes (e.g. agentic AI, OpenADMET, cofolding, generative
    chemistry). Refresh the "Recurring themes" subsection.
  - GitHub repos under `ersilia-os/*` or external repos linked — these are
    candidate Hub incorporations that may not have published yet.

### 3. Google Drive grants and proposals (forward-looking commitments)

- **Where**: the user's Google Drive. Search recent grant documents
  (NIH R21, BBVA Prisms, CARB-X, AI2050, etc.) — anything modified in the last
  6 months.
- **How**: use the Google Drive MCP (`search_files` with
  `modifiedTime > today-180d` and `title contains 'proposal'` / `contains 'grant'`).
- **What to extract**:
  - Active collaborator institutions and PIs — add to author tiers (especially
    the "grant co-PIs" group, which carries the highest author bonus).
  - Methods the grants commit Ersilia to (e.g. Boltz-2, TabPFN, deep docking,
    explicit AI agents). Add to keyword matrix and modality list.
  - Diseases / pathogens in scope per grant. Add to the diseases keyword list.

### 4. The user's Gmail (Scholar alerts + collaborator threads, last 90 days)

- **Where**: the user's inbox via the Gmail MCP.
- **How**: search `from:scholaralerts-noreply newer_than:90d` and
  `(from:fulbrightmail OR from:uct.ac.za OR …) newer_than:90d`.
- **What to extract**:
  - Authors of Scholar-alerted papers — these are the people the user is
    *already* following; reinforce their author tier.
  - Recurring topics in Scholar alerts.

## Edits to make per file

### `search-landscape.md`

- Topics: re-order Tier A/B/C if anything has clearly moved up or down.
- Recurring themes (Slack-derived): rewrite the bullets from this refresh
  window's Slack inspection.
- Authors: promote/demote based on Hub-author frequency (input 1) and Slack
  mention frequency (input 2).
- Journals: re-rank Tier 1 / 2 / 3 based on Hub-publication frequency. Move any
  venue that has gained ≥3 incorporated models into Tier 1 if not there already.
- Task / Subtask taxonomy: update the "Hub share" column with the current
  numbers.

### `hub-incorporation-criteria.md`

- Update the snapshot date.
- Refresh the Subtask, Source type, and Publication-type tables with new
  numbers.
- Refresh the "Where Hub publications actually live" table.
- If any single venue has changed rank by ≥3 places, note the move in prose.

### `lmic-countries.md`

- Re-pull the World Bank classification (FY rolls in July). Diff against the
  prior version and note any reclassifications in the file's "Notes" section.

### Anywhere else

- `slack-alert-template.md`: only edit if the chapter list in
  `output-template.md` has changed.
- `output-template.md`: only edit if the curation framework itself changes —
  this is not normally part of a refresh.

## Completing the refresh

When the edits are done, update `references/_state.json`:

```json
{
  "last_refresh_date": "YYYY-MM-DD",
  "refresh_interval_days": 90,
  "next_refresh_due": "YYYY-MM-DD",
  "refreshed_files": [
    "search-landscape.md",
    "hub-incorporation-criteria.md",
    "lmic-countries.md"
  ],
  "refresh_log": [
    { "date": "YYYY-MM-DD", "notes": "one-sentence summary of what changed" },
    ...prior entries...
  ]
}
```

Commit the reference-file changes (locally — references are part of the skill
and *are* committed, unlike digests). Then the normal weekly digest run can
proceed.

## When to refresh outside the cadence

Skip the timer when:

- A grant proposal lands or fails — the author tiers and topics may need to
  shift quickly.
- A major Slack discussion changes priorities (e.g. a new disease focus).
- The Hub picks up >10 new models in a short period — the priors are stale.

In any of those cases, run the refresh manually, then update `_state.json`.
