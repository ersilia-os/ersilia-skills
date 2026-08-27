---
name: partner-profiling
description: >
  Discover and profile potential partners who expand Ersilia's visibility and network —
  science journalists and outlets, open-source / open-science organisations, and research
  institutions in Barcelona, Catalonia and Spain, plus institutional comms teams,
  community amplifiers and creatives such as photographers. Runs in three modes: a `sweep`
  that finds new candidates against a focus lens, a `dossier` that deep-profiles one named
  target, and a `campaign` that finds who helps a specific occasion land and when each of
  them must be contacted. Use this skill whenever a user asks to find, research or profile
  potential partners, journalists, media contacts, photographers, outlets, collaborators or
  institutions for outreach, visibility, networking, or to publicise an event or
  announcement. Triggers include "find partners", "who should we pitch", "science
  journalists covering X", "partner sweep", "profile <name>", "prepare a dossier on", "who
  covers AMR", "local institutions in Barcelona", "media contacts for Ersilia", "expand our
  visibility", "who can help spread the word", "we have an anniversary/launch/report
  coming", "find a photographer", "who should we invite to cover this". Always use this
  skill for Ersilia partner-profiling requests, even if the ask is phrased casually.
argument-hint: [sweep|dossier|campaign] [focus, target or occasion] [--occasion-date <date>] [--out <path>] [--force]
allowed-tools: [Read, Write, Bash, WebSearch, WebFetch, AskUserQuestion]
---

# Partner Profiling for Ersilia

Find the people and organisations who can widen Ersilia's reach, and turn them into a
work queue rather than a contact list. Three modes:

- **`sweep`** — discover *new* candidates against a focus lens, ranked by strategic fit.
  The standing landscape: "who should Ersilia know?"
- **`dossier`** — deep-profile *one* named target: who they are, what they cover, our way
  in, the pitch, the ask, and the risks.
- **`campaign`** — we have a thing happening on a date (an anniversary, a launch, a report)
  and need to know **who helps it land and who must be contacted first**. Ranked by
  contact-by deadline, not by priority.

The lens is **action**: for each candidate, is this someone to **pitch**, **introduce**
ourselves to, **invite** into something of ours, **commission**, **nurture** an existing
thread with, or just **watch**?

**Sweep and campaign answer different questions and rank on different axes.** A sweep
asks who is worth knowing; a campaign asks who to email this week. Do not run a sweep and
call it a campaign plan — the ordering will bury the rows that need action now.

**All paths below are relative to this skill folder** (`skills/partner-profiling/`).

**v1 output is local only.** Reports are written to `reports/`, which is gitignored.
Nothing is published to `ersilia-os/digests` (a public repo) and nothing is posted to
Slack. That is a deliberate consequence of recording named individuals — see
`references/data-handling.md`.

---

## Inputs

- **`mode`** (optional): `sweep` (default) or `dossier`.
- **`focus`** (sweep) — a lens, e.g. "science journalists covering AMR in Africa",
  "Barcelona institutions", "open-science fellowship programmes". Default: a broad sweep
  across all three classes. **A focus makes the sweep much better** — the axis-driven
  pass in `references/partner-sources.md` needs something to vary.
- **`target`** (dossier) — the person or organisation to profile. Required in this mode.
- **`occasion`** (campaign) — what is being amplified, e.g. "Ersilia 5th anniversary",
  "Model Hub 1,000th model". Required in this mode.
- **`--occasion-date`** (campaign) — the occasion's ISO date. Required in practice:
  without it no `contact_by` can be sanity-checked and the schedule is unanchored.
- **`--out`** (optional): output path override. Defaults:
  - sweep: `reports/{YY}-{MM}-{DD}-partner-sweep.md`
  - dossier: `reports/{YY}-{MM}-{DD}-dossier-{slug}.md`
  - campaign: `reports/{YY}-{MM}-{DD}-campaign-{slug}.md`
- **`--force`** (optional): override the recent-sweep guard in Step 0.

If the focus is ambiguous, ask **one** focused question. **Never invent a person, a role,
a beat, an article or a contact address** — verify each against a live first-party page or
drop it. Misattributing a beat to a real journalist is the worst failure this skill can
produce, and it is worse than missing them entirely.

---

## Reference files

Read all five before starting:

- `references/partner-sources.md` — where to look per class, the two-pass query method,
  **and the partner JSON schema** you must produce. Read before any search.
- `references/classification.md` — the 5-axis taxonomy, marker ribbon, action verbs.
  Read before classifying.
- `references/partner-priorities.md` — the relevance gate and the scoring rubric. Read
  before screening.
- `references/data-handling.md` — what may and may not be recorded about a person. Read
  before recording any contact detail.
- `references/known-partners.md` — existing relationships, suppressed from sweeps.

---

## Not in scope

**Read this before Step 2, not after someone asks why a row is in the report.** The
description above is the binding definition: **media and science communication**,
**open-source / open-science organisations**, and **institutions in Barcelona, Catalonia
and Spain** (plus Global-South researchers reached through an academic tie). A candidate
must belong to one of those.

Out of scope, however relevant they may feel:

- **Funders, foundations, grantmakers and philanthropy.** Real organisational need,
  different audience, different rubric — it gets **its own skill**. Do not let a
  foundation in because it also runs a communications programme.
- **Global research institutions and networks as a family** — universities outside Spain,
  product-development partnerships (DNDi, MMV, GARDP, H3D), consortia. Deliberately
  excluded from v1 scope. A Global-South *researcher* reached through a citation or
  workshop tie is in scope as an `Institution` row; their institution as an
  institutional-partnership target is not.
- **Global-health policy bodies** — WHO, Africa CDC, ministries.
- **Events and conferences** — `event-discovery` covers these. If a sweep turns up a
  convening rather than a partner, hand it to that skill. The overlap runs the other way
  too: event digests are a *source* for this skill (see `partner-sources.md`).
- **Recruitment.** Candidates, interns and job adverts are not partners.
- **Commercial partnerships and business development.** There is no `Company` class. A
  private company enters only if it would plausibly **amplify** — and a same-field
  competitor almost never would. The relevance gate settles this without needing a new
  class: ask what they would actually do for the message, not whether they are adjacent.
  A Barcelona deeptech in Ersilia's own field is a field-neighbour, not an amplifier.
- **Anyone whose only qualification is a large audience.** See the reach note in
  `classification.md`.

**The relevance gate replaces event-discovery's priority-4 test.** Partner work *is*
priority-4 work, so that test would reject everything here. The discipline instead is
actionability: if you cannot write the `hook` and the `next_step`, the candidate is not
ready. `filter_and_sort.py` enforces this by dropping any row missing either — see
`references/partner-priorities.md`.

---

## Workflow — `sweep` mode

### Step 0 — Pre-flight check (no recent sweep)

Sweeps are quarterly, not redundant. The reports are local, so just look:

```bash
ls -1 reports/*-partner-sweep.md 2>/dev/null | sort -r | head -3
```

The glob matches **sweeps only**. A dossier written yesterday says nothing about whether
the landscape needs re-sweeping, and an unfiltered `reports/*.md` made every dossier trip
the guard.

- If it prints filenames, read the newest one's embedded date. If it is within the last
  **45 days**, stop and ask whether to proceed (`--force` skips this). 45 days is tuned to a quarterly cadence: it catches an accidental re-run
  while always clearing the next scheduled sweep ~90 days out.
- If nothing prints, this is a first run — continue. Unlike event-discovery's Step 0,
  there is no auth or network call here, so an empty result is unambiguous and needs no
  error handling.

### Step 1 — Parse the request

Resolve mode, focus and output path. Decide which of the three classes the focus implies;
a broad sweep covers all three.

### Step 2 — Sweep sources — two passes, both required

Follow `references/partner-sources.md`. **Pass A** walks the source tables; **Pass B**
queries by attribute (beat, geography, format, role, mechanism) and is never scoped to a
source the map already names. Pass B is what stops coverage freezing at whatever was
written down on day one — it is not optional, and it is where the mechanism-axis queries
(fellowship cohorts, grantee lists, citing authors) pay off.

Record which pass found each candidate in `source`.

### Step 3 — Verify each candidate

For every candidate, reach a **first-party page** and confirm: the person exists in that
role, the beat or remit is as claimed, and at least one dated piece of recent relevant
work. Three outcomes:

0. **Check the link points at the current edition, before anything else.** A recurring
   series keeps a generic landing page that renders whichever edition is current *today*
   and year-specific pages that never move — always cite the year-specific one. A generic
   page sends the reader to last year's event while looking verified. The script enforces
   this (see `references/partner-sources.md`), but the script can only compare years it can
   see: a generic URL with no year in it is invisible to it unless you record
   `edition_year`.
1. **Confirmed** — `verified: true`.
2. **Partly confirmed** — the organisation is real but the individual's remit could not be
   established. Keep with `verified: false`, and make `next_step` the verification itself.
3. **Not a partner** — an event, a paper, a job advert, a funder. Drop it, and mention it
   in the Step 8 summary so the work is visible.

**Do not record a contact address at this step without checking `data-handling.md` first.**
The test is whether the organisation publishes it *to be contacted on*.

### Step 4 — Screen against the relevance gate

Apply `references/partner-priorities.md`: can you write, in one sentence each, the specific
audience or capability gained, and a concrete next step? If not, drop the candidate. Then
ask the reciprocity question — what do *they* get — and if there is no answer, score `Low`
and set the action to `watch` rather than inventing an ask.

### Step 5 — Classify and assemble the pool

Assign all five axes from `references/classification.md` plus an action verb, and write the
JSON array defined in `references/partner-sources.md` to a temporary file. Do **not**
hand-set markers; the script derives them.

### Step 6 — Screen, dedup and rank (script)

```bash
python3 scripts/filter_and_sort.py --in /tmp/pool.json --out /tmp/partners_clean.json \
  --known references/known-partners.md \
  --ledger ~/.ersilia/partners_seen.json --hide-seen
```

The script drops rows missing a required field, rejects out-of-vocabulary axis values,
enforces the contact policy, suppresses known partners, merges duplicates, applies the
ledger, derives the marker ribbon and ranks the result. **Read its warnings** — they are
the audit trail for everything that did not make the report.

- `--hide-seen` gives a "what's new since the last sweep" report. Drop it to include
  previously-seen partners tagged `(seen)`.
- `--keep-known` tags known partners instead of dropping them, for when you want to look
  at the existing relationships too.
- To re-surface everything once (e.g. "show me the full landscape again"), omit
  `--ledger`/`--hide-seen` for that one invocation rather than deleting the ledger file.

### Step 7 — Render the report (script)

```bash
python3 scripts/render_sweep.py --in /tmp/partners_clean.json \
  --out reports/26-08-20-partner-sweep.md \
  --date 2026-08-20 --focus "science journalists, AMR; Barcelona institutions" --sources 14
```

`--layout` picks the shape:

- **`table`** (default) — **one table per class**, with columns chosen for that class
  (a `Creative` table carries event experience and portfolio; a `Media` table carries
  reach), plus a shared **Cost** column on every table. Warm rows also get a strip at the top, because splitting by class
  scatters them. See "Report columns differ by class" in `classification.md`.
- **`detail`** — a heading and labelled bullets per partner, plus the warm-paths and
  per-class sections. Wordier, and the **only** layout safe for a Google Drive Doc, whose
  markdown conversion mangles pipe tables. Pair it with `--markers text`.

Then summarise in chat: the counts strip, the warm paths, and anything flagged `†`.

### Step 8 — Review gate (STOP here)

**Present the report and stop.** Three things are the user's call, not the skill's:

- **Every `†` unverified row** — verify, drop, or accept the flag.
- **Every candidate dropped in Step 3 as "not a partner"** — list them in chat with one
  clause each saying why. This keeps a judgement call visible and overrulable.
- **Every contact the script stripped** — the warnings name them. If one was stripped
  wrongly, the fix is a reviewed edit to `ALLOWED_CONTACT_KINDS`, never a workaround.

Nothing is published anywhere in v1, so the gate is about accuracy rather than
irreversibility — but a report naming real journalists is a document that will be shared
by hand, and a wrong beat is embarrassing in exactly the way that closes a door.

---

## Workflow — `dossier` mode

### Step D1 — Confirm the target and check for prior work

```bash
ls -1 reports/*dossier* 2>/dev/null | sort -r | head -5
```

If a dossier on this target already exists, read it and update rather than restart.

### Step D2 — Research the target

Same verification standard as Step 3, but deeper. Assemble: `background`, `remit`,
`audience`, `recent_work` (at least two dated items — a dossier without recent work has no
hook), `warm_paths`, `pitch`, `ask`, `risks`, and `sources` for every claim.

**`risks` is the section that makes a dossier honest.** Name the mismatches: wrong
audience for a methods story, no prior contact, a closing time window. A dossier with an
empty `risks` list has not been thought about.

### Step D3 — Render (script)

Write the target as a single JSON object, then:

```bash
python3 scripts/render_dossier.py --in /tmp/target.json \
  --out reports/26-08-20-dossier-a-placeholder.md --date 2026-08-20
```

The script warns if `background`, `pitch` or `ask` is empty — those three carry the
document. To apply the contact policy to a dossier target, pass it through
`filter_and_sort.py` first (it accepts a one-element array).

### Step D4 — Review gate

Same as Step 8. Present it and stop.

---

## Workflow — `campaign` mode

Use this when there is a **date**. The output is a contact schedule, not a landscape.

### Step C1 — Pin down the occasion and what is on offer

Before searching, write down three things. If you cannot, ask the user rather than guess:

1. **What is happening, and on what date.**
2. **What we are actually offering** — an event to attend and photograph, an announcement,
   a milestone, a report. This is the campaign's shared hook, and it is what every row's
   own `hook` specialises.
3. **What we want back** — coverage, a listing, photographs, a co-promoted post. This
   becomes each row's `amplification`.

```bash
ls -1 reports/*-campaign-*.md 2>/dev/null | sort -r | head -5
```

If a plan for this occasion already exists, update it rather than starting over.

### Step C2 — Sweep for amplifiers

Same two passes as Step 2, but the classes in play are usually `Media`, `Comms-team`,
`Community` and `Creative`, and the question is narrower: **would they plausibly amplify
this specific thing?** An organisation that is a fine long-term partner but has no reason
to care about this occasion belongs in a sweep, not here.

Existing relationships are the best amplifiers, so **do not pass `--hide-seen` or rely on
the known-partners suppression** in campaign mode — a partner Ersilia already works with is
exactly who should carry the announcement. See Step C4.

### Step C3 — Verify, and set a `contact_by` for every row

Verification is as in Step 3. Then add the campaign fields from
`references/partner-sources.md`: `contact_by`, `lead_time_note`, `amplification`.

**Deriving `contact_by` is the judgement that makes this mode useful.** A monthly print
title closes copy weeks ahead of the issue; a daily wants days; a photographer books out
months. Record the reasoning in `lead_time_note` so the date can be argued with. Where the
publication cycle is genuinely unknown, say so there rather than inventing a lead time.

### Step C4 — Screen, order by deadline (script)

```bash
python3 scripts/filter_and_sort.py --in /tmp/pool.json --out /tmp/partners_clean.json \
  --known references/known-partners.md --keep-known \
  --order deadline --today 2026-08-21 --occasion-date 2026-11-15
```

- `--order deadline` sorts by `contact_by` and enables the ⏱️ marker.
- `--keep-known` **matters here**: known partners are tagged rather than dropped, because
  an existing relationship is an asset for a campaign even though it is not a discovery.
- `--today` is optional; it defaults to the system date and exists so a run is reproducible.
- Read the warnings. Three are specific to this mode: a `contact_by` already passed, a
  `contact_by` falling **after** the occasion (the easy mistake — it looks complete and is
  useless), and a row with no `contact_by` at all.
- No `--ledger` is used in campaign mode. The ledger answers "have we seen this before",
  which is a discovery question; re-contacting a known amplifier for a new occasion is the
  intended behaviour, not a duplicate.

### Step C5 — Render the plan (script)

```bash
python3 scripts/render_campaign.py --in /tmp/partners_clean.json \
  --out reports/26-08-21-campaign-anniversary.md \
  --date 2026-08-21 --occasion "Ersilia anniversary" --occasion-date 2026-11-15
```

`--layout table` (the default) emits **one table per class**, each led by a contact-by
column, above them an **⏱️ Act first** strip listing everything due within 21 days
regardless of class. That strip is not decoration: splitting into per-class tables
scatters the deadline ordering, which is the entire reason campaign mode exists, so the
strip is the one place the report still answers "who do I contact this week". `--layout detail` instead leads with a bucketed schedule (Overdue
/ this week / this month / later / no date) followed by per-partner blocks, and is the
layout to use for a Drive Doc, with `--markers text`.

Summarise in chat by reading out the overdue and this-week rows; those are the only ones
that need a decision today.

Campaign reports also carry a **Budget** section: the partners that cost money, and
separately the ones nobody has priced. There is no arithmetic — costs are free text and
cannot be summed — and the unpriced list is the more useful half.

**Context fields are trimmed in table layout; `next_step` never is.** A truncated
instruction is worse than a long cell — a trimmed conditional ("only if a result ships,
otherwise drop this row") reads as an unconditional one. Do not add a trim there.

### Step C6 — Review gate

Same as Step 8, plus one campaign-specific item: **every row whose `contact_by` has already
passed or falls after the occasion.** Those are either a wrong date or a genuinely missed
window, and only the user can say which.

---

## Gotchas

Each of these cost a debugging cycle when the skill was built (2026-08-20).

- **The default layout is `table`; the Drive-safe layout is `detail`.** These are two
  destinations, not two styles. The table layout exists because the local report is far
  more scannable as one row per partner; the detail layout exists because Drive cannot
  render pipe tables. Do not collapse them into one.
- **Escape pipes in every table cell.** `cell()` does this. An unescaped `|` in a hook or
  a URL silently splits the row into the wrong number of columns and corrupts every cell
  after it. When testing this, note that `line.split("|")` counts an *escaped* `\|` as a
  separator too — count with a negative lookbehind or you will diagnose a working escape
  as broken.
- **Markdown pipe tables do not survive conversion to a Google Doc.** The header row comes
  back empty and its cells are demoted into a body row with escaped literal asterisks. This
  is why both renderers use headings and labelled bullets, and why the report format looks
  nothing like event-discovery's tables. Do not "improve" it back into a table.
- **Emoji above U+1FFFF corrupt in the same conversion.** `🏠🌍💻📣🤝` become mojibake;
  `⭐` (U+2B50) and `✉️` (U+2709) survive because they are BMP characters. Hence
  `render_sweep.py --markers text`, which swaps the ribbon for bracketed labels. The
  default emoji mode is correct for the local report.
- **`known-partners.md` documents its own format with a fenced example, and the parser
  used to read it as data** — the shipped, entry-free file silently suppressed a real
  candidate. `load_known` now skips fenced blocks. If you add a format example to that
  file, keep it inside a fence.
- **Duplicate merging picks the *more complete* copy as the base, not the first one.** The
  same outlet arrives from a byline page and a tag page in either order, and an earlier-
  but-thinner row used to overwrite a researched `hook`. Completeness weights `hook` and
  `next_step` heavily, for that reason.
- **Markers are derived after the dedup loop, not when a row is appended.** A later
  duplicate can upgrade a kept row's priority or add a contact; markers computed at append
  time went stale and silently dropped the `⭐`/`🤝`/`✉️` the upgrade had just earned.
- **A generic series URL is a stale link waiting to happen.** `…/opentechweek` renders
  whichever edition the site currently shows; cite the dated page instead. This shipped
  wrong once — a report linked the 2025 edition of Barcelona Open Tech Week while its own
  note said the 2026 dates were unconfirmed, and a reader found it. `filter_and_sort.py`
  now warns and forces `verified: false` on any year mismatch, but it cannot see a year
  that isn't in the URL — record `edition_year` for generic pages.
- **An absent `cost` means "not established", never "free".** The renderers print `—`
  and the campaign Budget section names the unpriced partners outright, because an
  unknown cost is a risk and a blank cell reads as a zero. On the anniversary run the two
  unpriced rows were Norrsken venue hire and Open Tech Week participation — plausibly the
  only two line items that would actually cost anything.
- **The contact policy fails closed.** An unrecognised `kind` is stripped, not kept. This
  is deliberate: the default for an unreviewed channel type is to discard it. Adding one is
  an edit to `ALLOWED_CONTACT_KINDS` in `scripts/_common.py` after a human decision.
- **A `scientific_correspondence` address does not earn the `✉️` marker.** It is a real
  address but not a channel we may pitch on, so the row is not "contactable" for this
  skill's purpose. That asymmetry is intentional, not a bug.
- **Never de-duplicate the marker ribbon by character.** `⏱️` and `✉️` are both
  two-codepoint sequences ending in U+FE0F, so a `dict.fromkeys` dedup stripped the
  envelope's variation selector and it rendered as a bare `✉`. Only surfaced once campaign
  mode put both markers in one ribbon. `order_markers` already emits each marker once.
- **`reach` is empty for `Creative` rows on purpose.** You buy a photographer's skill, you
  do not borrow their audience. `REACHLESS_CLASSES` records this so an empty value is not
  mistaken for missing data, and the campaign renderer omits the field entirely.
- **Campaign mode deliberately does not use the ledger, and uses `--keep-known`.** The
  suppression logic that makes a sweep useful makes a campaign wrong: the partners Ersilia
  already has are precisely the ones who should carry an announcement.
- **The ledger key has no date component**, deliberately unlike event-discovery's, whose
  key appends the event year. A conference has editions; a journalist does not. Do not
  copy that pattern over.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `dropping '<name>': missing required field(s): hook` | The relevance gate did its job. Either write a real hook or accept the drop — do not paraphrase the organisation's tagline into the field. |
| `dropping '<name>': class='Journalist' not in ['Media', ...]` | Out-of-vocabulary axis value. Use the exact strings in `classification.md`; the script rejects rather than coerces so a typo cannot become a silent mis-grouping. |
| `stripped an unrecognised contact kind 'linkedin_dm'` | The policy failing closed, as designed. If the channel is legitimately a published contact route, review it and add it to `ALLOWED_CONTACT_KINDS`. |
| `ERROR: dossier input must be one target; got an array of 2` | `render_dossier.py` was handed a sweep pool. Extract the single target object. |
| Everything is suppressed as already-known | An over-broad entry in `known-partners.md` — a bare organisation name matches loosely. Run with `--keep-known` to see which rows are being hit. |
| Every partner re-appears in a new sweep | `--ledger` was omitted, or the ledger path differs between runs. It defaults to `~/.ersilia/partners_seen.json`; the script creates that directory. |
| Report is empty but the sweep found candidates | Check the warnings. With `--hide-seen`, a re-run over the same pool correctly keeps nothing. |
| `'<name>' contact_by ... falls AFTER the occasion` | The row looks complete but is useless — contacting them then cannot help the occasion land. Either the lead time was misjudged or the row should be dropped. |
| `'<name>' has no contact_by date — sorted last` | Campaign mode cannot schedule it. Derive a lead time from the publication or booking cycle, or move the row to a plain sweep. |
| A campaign plan is missing the partners we already work with | `--keep-known` was omitted, so the known-partners suppression dropped them. In campaign mode that suppression is wrong — existing partners are the best amplifiers. |
| Marker ribbon shows a bare `✉` instead of `✉️` | The variation-selector bug is back — something is de-duplicating markers by character. See Gotchas. |

---

## Future work (documented, not implemented)

- **Google Drive delivery.** Verified working: `create_file` with
  `contentMimeType: text/markdown` produces a Doc, and this report format converts
  cleanly. Blocked on a decision, not a capability — the user chose local-only for v1. If
  built, use `--markers text`, and the target must be a restricted-access folder because
  the reports contain contact details.
- **Airtable as the known-partners source of truth.** `config/CLAUDE.md` describes the
  *Ersilia Content* base as the registry of partner organisations and contacts. That is
  the right home for `known-partners.md`. **Its connector was not authorised** when this
  skill was written, so nothing was built or tested against it.
- **Slack alert.** Deliberately absent: the reports contain contact details, and v1 keeps
  everything local. A campaign plan is the one output where a Slack post would genuinely
  help — the contact schedule is time-sensitive and the team needs to see it — so this is
  the first thing to revisit if the local-only decision is relaxed.
- **Campaign follow-up tracking.** The plan says who to contact by when; nothing records
  whether it happened or what came back. That is a tracker, not a discovery skill, and it
  probably belongs in Airtable rather than here.
- **Mining the event digests automatically.** `partner-sources.md` names
  `../event-discovery/reports/` as a source, but reading it is manual. A script that
  extracted organiser and speaker names would be near-free recall.
- **Ersilia's own dependency graph.** Contributors to and dependents of `ersilia-os`
  repositories are the warmest possible open-source partners and are invisible to every
  web query in the source map.
