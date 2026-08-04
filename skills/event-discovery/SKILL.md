---
name: event-discovery
description: >
  Discover events worth Ersilia's time and write a summarised, classified report.
  Use this skill whenever a user asks to find, surface, or round up upcoming
  conferences, symposia, workshops, summer schools, training / capacity-building
  events, hackathons, datathons, or fellowships relevant to Ersilia's mission
  (AI/ML for infectious- and neglected-disease drug discovery, Global-South capacity
  building, open science). Triggers include "find events", "upcoming conferences",
  "what events should Ersilia attend", "event digest", "discover workshops",
  "any hackathons or fellowships", "events on <topic/region>". Always use this skill
  for Ersilia event-discovery requests, even if the ask is phrased casually.
argument-hint: [focus] [--from <date>] [--to <date>] [--out <path>] [--force]
allowed-tools: [Read, Write, Bash, WebSearch, WebFetch, AskUserQuestion, slack_search_channels, slack_send_message]
---

# Event Discovery for Ersilia

Find the events worth Ersilia's time and turn them into a scannable, classified
report. The lens is **action**: for each event, is it one to **attend**, **apply**
to, **partner** on, **scout** (send someone to a high-fit but costly/far venue for
methods or partnership intel), or just **watch**? Coverage spans scientific conferences
and symposia, applied / industry ML drug-discovery meetings, workshops and training /
capacity-building schools, and hackathons, datathons and fellowships — screened against
Ersilia's four strategic priorities, with an explicit Global-South lens.

**Discovery is web-driven** (`WebSearch` + `WebFetch`). Claude does the uncertain
work — searching, verifying dates, judging relevance, classifying. Two stdlib-only
Python scripts do the deterministic work — validating, filtering the date window,
de-duplicating series, and rendering the report. Paths below are relative to this
skill folder.

---

## Inputs

- **`focus`** (optional): a topic or region lens, e.g. "AI drug discovery",
  "Africa training", "generative chemistry". Default: a broad sweep across all
  in-scope event types.
- **`--from` / `--to`** (optional): the event date window (ISO `YYYY-MM-DD`).
  Default: **today → +12 months**. Past events are always excluded. The
  12-month look-ahead (up from an earlier 9-month default) is deliberately
  generous: events need long planning lead time (bursaries, abstract
  deadlines, travel booking), and this window is what each twice-yearly
  scheduled run (see Scheduling) is expected to cover — the two runs then
  overlap by 6 months rather than leaving a gap.
- **`--out`** (optional): output path override for the report. Default:
  `reports/{YY}-{MM}-{DD}-event-discovery.md` (2-digit year, run date)
  relative to this skill folder — a working copy; the canonical home is the
  remote repo `ersilia-os/digests` at `events/YY-MM-DD-event-discovery.md`
  (Step 8).
- **`--force`** (optional): override the recent-report guards in Step 0.

If the focus is ambiguous, ask **one** focused question. **Never invent events,
dates, deadlines, or venues** — verify each against its official page or drop it.

---

## Reference files

Read all four before starting:

- `references/event-sources.md` — where to look per event type, how to query, **and
  the event JSON schema** you must produce. Read before any search.
- `references/classification.md` — the 5-axis taxonomy, marker ribbon, priority
  rubric. Read before classifying.
- `references/ersilia-priorities.md` — the four strategic priorities + relevance
  rubric. Read before screening.
- `references/lmic-countries.md` — the LMIC list behind the 🌍 / Global-South axis.

---

## Workflow

### Step 0 — Pre-flight check (no recent report)

The report is twice-yearly, not redundant. The canonical home is the remote
`ersilia-os/digests` repo, so check there directly — no dedicated script, just
one inline command:

```bash
gh api repos/ersilia-os/digests/contents/events --jq '.[].name' 2>/dev/null | sort -r | head -3
```

- If this errors for a reason other than the `events/` folder not existing yet
  (e.g. auth failure, network issue), **STOP** and surface it — don't silently
  proceed, since a run that can't see the remote could duplicate published work.
- If it prints filenames, read the newest one's embedded date
  (`YY-MM-DD-event-discovery.md`). If that date is within the last ~150 days
  (roughly the 6-month cadence, so this only catches an accidental re-run
  within the same cycle, never the next scheduled one), **stop and ask** the
  user whether they want to proceed anyway (`--force` skips this check).
- If the folder doesn't exist yet or the newest report is older than that,
  continue to Step 1.

### Step 1 — Parse the request

Extract the `focus`, resolve the date window (default today → +12 months; today is
whatever the current date is), and note any explicit type or region signal. Keep the
resolved `--from`/`--to` — every later step and both scripts use them.

### Step 2 — Sweep sources (web)

Work through `references/event-sources.md`. For each in-scope event type run **≥4
query variants** (source-scoped `WebSearch` plus a couple of open searches for the
`focus`), anchored to the window's year(s). Events 6–12 months out are often announced
under the *following* year — query both. Aim for a **raw pool of 30–60 candidates**.

Also keep events **beyond** the window whose **deadline is already open** — a conference
in mid-2027 whose abstract or bursary deadline falls inside the window is actionable
*now*. The script routes these into a separate section; don't discard them just because
the event date is past `--to`.

**Cover every continent.** Run at least one query aimed at each of Africa, Europe, Asia,
South America, North America, and Oceania — don't let the default sources skew the sweep
to Europe / North America / Africa. For Asia and Latin America especially, query regional
bodies (see the "Global-South regional" sources) and in **Spanish / Portuguese** too.
Track which continents you actually queried and pass them to `--continents-searched` in
Step 7. If a continent genuinely returns nothing verifiable, that's fine — the report
will mark it "searched, none verified" so the gap is visible, never silently empty.

### Step 3 — Verify each event

`WebFetch` the event's **official page** and confirm **name, exact dates, location,
official URL**. If the page confirms them, set `verified: true`. If the official page
**can't be fetched** (site down, cert error) but independent reputable sources agree on
name/dates/URL, keep the event with `verified: false` — it will be flagged with `†` in
the report rather than silently dropped. If you can't establish a date or an official
URL at all, drop it (omit, never guess a date). Also capture, when stated: the **typed
deadlines** (`abstract` / `early_bird` / `registration` / `bursary`); the attendance
**cost** (`Free`, a figure with currency, or `Unknown`); and any **bursary** / financial
aid / travel support (short description, `None`, or `Unknown`). Never invent a number, a
date, or a bursary. Never keep a ticket-reseller or aggregator link as the official URL.

### Step 4 — Screen for relevance

Keep only events that map to **≥1 Ersilia strategic priority**
(`references/ersilia-priorities.md`). Drop the rest. Record which priorities (1–4)
each surviving event maps to.

### Step 5 — Classify and assemble the pool

For every surviving event, assign all five axes and the marker ribbon per
`references/classification.md`, set a `priority` and an `action`, note the `engagement`
angle (what to do there / who should go, or `—`), and write a one-line `why_ersilia`.
Use `references/lmic-countries.md` for the `Global-South` / 🌍 decision.

Write the pool to `/tmp/events_pool.json` as a JSON array conforming to the schema in
`references/event-sources.md`. Set the `⭐🌍🎓💻` markers yourself; do **not** add the
💰 or 🗓️ markers — the script derives those from the `bursary` and `deadlines` fields.

### Step 6 — Normalise and order (script)

```bash
python scripts/filter_and_sort.py --in /tmp/events_pool.json --from <from> --to <to> \
  --ledger ~/.ersilia/events_seen.json --hide-seen --out /tmp/events_clean.json
```

Validates required fields, de-duplicates recurring series, sorts by date, and flags
in-window deadlines (adds 🗓️). Drops events outside the window **unless** a typed
deadline lands inside it — those are kept and routed to a "beyond the window" section.
**Read the WARNINGs it
prints** — note any dropped events in the in-chat summary so nothing disappears silently.

**Cross-run memory (default, not optional).** `--ledger ~/.ersilia/events_seen.json`
is passed on every run: an event already recorded there — matched by name-without-year
+ location **plus the event's own start-date year** — is tagged `(seen)`, and
`--hide-seen` drops it from this report instead of repeating it. That year component
matters: the ledger exists to stop the *same edition* from being re-shown in a later
report, not to hide next year's edition just because an earlier year's was already
reported — "GCC 2026" being seen never suppresses "GCC 2027" once it rolls around,
even at the same venue. A new calendar-year edition of a recurring series always shows.
The ledger is updated with every kept event at the end of the run, so the *next* run
(whatever the cadence) won't re-surface the same edition this one already showed. The
file lives outside this repo (`~/.ersilia/events_seen.json`, in the user's home
directory) so it persists across runs regardless of cadence and is never committed. If
the user explicitly asks for a full, unfiltered sweep (e.g. "show me everything
again"), omit `--ledger`/`--hide-seen` for that one invocation rather than editing or
deleting the ledger file.

### Step 7 — Render the report (script) + summarise

```bash
python scripts/render_report.py --in /tmp/events_clean.json --focus "<focus>" --from <from> --to <to> --today <today> --swept <N> --continents-searched "Africa,Europe,Asia,South America,North America,Oceania" --out <report path>
```

`--today` (the current date) drives the **Act now** countdown; it defaults to `--from`
if omitted. Pass the real today when `--from` isn't today.

`--group-by continent` (the **default**) sections the report by continent (Africa →
Europe → Asia → South America → North America → Oceania), and **within each continent
sub-groups by theme** (Science → Training → Community → Philanthropy) — useful for
travel/reachability decisions, which is what this twice-yearly report is mainly read
for. Pass `--group-by theme` to fall back to the single-level theme grouping for a
one-off ask. Continent is derived from each event's `country`. **Virtual / online
events** (no physical location) are never a continent — in either mode they collect
into a single **Virtual / online** section at the end.

`--continents-searched "Africa,Europe,Asia,South America,North America,Oceania"` (the
continents you queried in Step 2) adds a **Coverage by continent** footer. Continents you
searched that found nothing show "searched, none verified"; any you skipped show "not
searched" — so coverage is always explicit. Pass this on every run.

Output location:
- **Claude.ai / Cowork:** write to `/mnt/user-data/outputs/events_<focus>_<YYYYMMDD>.md`
  and call `present_files`.
- **Claude Code / local:** write to `--out` if given, else the default staging path
  `reports/{YY}-{MM}-{DD}-event-discovery.md` (2-digit year, run date) relative to this
  skill folder. This is the working copy; the canonical home is the remote repo
  published in Step 8.

`<N>` is the number of distinct sources you actually swept. Then surface the file and
write the **in-chat summary**: the top 3 events (one line each), the single most
time-sensitive deadline, and a note of anything the script dropped.

The `reports/` folder is `.gitignored` — the file lives locally but is not committed by
default.

### Step 8 — Submit to the canonical remote and hand off

The local file in `reports/` is a working copy. The canonical home is
`github.com/ersilia-os/digests` at `events/{YY}-{MM}-{DD}-event-discovery.md`.
Submitting it there is what "publishes" the report — the repo's own GitHub
Actions workflow (triggered on push to `main`) rebuilds the Jekyll site and
generates the report's page automatically, so there is nothing else to run.
No dedicated script — just `gh api`:

```bash
REPORT="reports/{YY}-{MM}-{DD}-event-discovery.md"
REMOTE_PATH="events/$(basename "$REPORT")"

# If a file already exists at that path, its blob sha is required to overwrite it.
SHA=$(gh api "repos/ersilia-os/digests/contents/$REMOTE_PATH" --jq .sha 2>/dev/null)

gh api -X PUT "repos/ersilia-os/digests/contents/$REMOTE_PATH" \
  -f message="Add $(basename "$REPORT") (event discovery report)" \
  -f content="$(base64 -w0 "$REPORT")" \
  -f branch="main" \
  ${SHA:+-f sha="$SHA"}
```

- `gh` must be authenticated (`gh auth status` checks this).
- If `$SHA` came back non-empty, you're overwriting an existing remote report —
  this should only happen after Step 0 already flagged it and the user agreed
  (`--force`). Don't silently overwrite otherwise.
- The command's JSON response includes `content.html_url` (the github.com blob)
  and `content.download_url`. Derive the reader-facing **Pages URL** yourself —
  `https://ersilia-os.github.io/digests/events/{YY-MM-DD}-event-discovery.html`
  — and hand that to the user and use it in the Slack alert; don't present the
  local path or the raw github.com blob as the primary artefact.
- No README index update — the website's navigation is generated directly from
  the files under `events/` (once the site templates support that folder), not
  from a hand-maintained README list.

If the submission fails for a recoverable reason (network blip, `gh` auth
lapsed), keep the local file intact and tell the user how to re-run just this
step. Never delete the local file before a successful submission.

### Step 9 — Post the Slack alert (only after a successful submission)

After (and **only** after) the Step 8 `gh api` call succeeds, post a rich
notification to `#networking` so the team sees what is in the report without
clicking through.

Resolve the channel by name via the Slack MCP — its ID is not hardcoded here
(unlike `literature-digest`'s `#literature`):

```text
slack_search_channels(query="networking")
```

- If no matching channel is found, **do not** post elsewhere. Tell the user
  `#networking` doesn't exist (or isn't visible to this session) and skip the
  post; the report is still generated and submitted, so nothing is lost — only
  the Slack post is skipped.
- If the Slack MCP isn't available in this session at all, treat this the same
  way — a **soft** skip, not a hard stop. Unlike `literature-digest`,
  event-discovery's core work (`WebSearch`/`WebFetch`) never depended on Slack,
  so a missing MCP here only costs the alert, not the whole run. Tell the user
  to re-run just the Slack post once the MCP is connected.

Otherwise, render `references/slack-alert-template.md` (top picks per continent/theme,
the Act-now deadlines, the counts strip, a link to the Pages URL) and post:

```text
slack_send_message(
    channel_id = "<resolved channel id>",
    message = <rendered template from references/slack-alert-template.md>
)
```

**Posting rules**:
- **Do not** post if the Step 8 submission failed.
- **Do not** mention team members by name. **Do not** name internal channels beyond
  what Slack itself routes.
- Post once per push. If it was a `--force` overwrite, still post once — the
  team should know the report has been updated.

---

## Output report format

`render_report.py` produces this deterministically — do not hand-format it:

```markdown
# Event Discovery for Ersilia — <focus>
*Generated: <YYYY-MM-DD> | Window: <from> → <to> | Events: N | Sources swept: M*

**Markers:** ⭐ High-priority fit · 🌍 Global-South · 🎓 Training · 💻 Open-source / AI methods · 💰 Bursary / travel support · 🗓️ Deadline in window

## ⏱️ Act now
**Deadlines in the next 30 days**
- **in 9 days** (2026-07-20) — [Name](url) · registration

**Top picks**
- ⭐ [Name](url) — 2026-10-05, City, Country · attend

## Science
| Event | Markers | Dates | Location | Format · Type | Cost | Bursary | Priority | Engagement | Why it matters (priority · action) |
|---|---|---|---|---|---|---|---|---|---|
| [Name](url) | ⭐🎓💻💰🗓️ | 2026-10-05 | Virtual | Virtual · Workshop | Free | Fee waivers | High | Present Model Hub work | Priority 1: … — apply. |

## Training
| … |

## Beyond the window — event is later, but a deadline is open now
| … |

## Registration closed — event still upcoming, but you can no longer register
| … |

## Virtual / online
| … |

## Deadlines (within the window)
- **<YYYY-MM-DD>** — [Name](url) · abstract / CFP
```

The "Beyond the window" and "Registration closed" sections appear only when such events
exist. A past `registration` deadline on a still-upcoming event moves it into the
"Registration closed" section (and out of the theme/continent tables, Act-now and
Deadlines callout), so you don't plan around something you can no longer join.
Use `--group-by continent` to section the tables geographically instead of by theme.

Themes render in fixed order (Science → Training → Community → Philanthropy), only
non-empty groups appear, and an empty result set is reported honestly rather than padded.

---

## Ersilia context

**Four strategic priorities** (full text in `references/ersilia-priorities.md`):
(1) grow the Model Hub as the reference AI/ML resource for infectious-disease research;
(2) pursue novel therapeutics for understudied diseases; (3) long-term training in the
Global South; (4) build the community that makes the work sustainable.

**Priority organisms** — *M. tuberculosis* / *M. abscessus*, *P. falciparum* /
*P. vivax*, *Leishmania* spp., *T. cruzi* / *T. brucei*, *S. mansoni*, ESKAPE & GLASS
AMR pathogens.

**Framing** — Ersilia is Barcelona-based; Europe is easy reach, the Global South is the
mission. Prefer open, low-cost, and capacity-building events; weigh travel cost and
bursary availability into priority. **But strategic fit stands on its own:** a strong
priority-1/2 methods or industry venue (applied AI/ML for drug discovery — e.g. Enamine,
CHI, RSC "AI in Chemistry", the LMRL/MoML circuit) is kept and surfaced on fit alone even
when costly and far — set its action to `scout`, don't drop it. The Global-South lens is
the tie-breaker between *attend* and *scout*, not a filter that removes top method venues.

---

## Things to avoid

- No invented events, dates, venues, or deadlines — never guess. Confirm on the official
  page (`verified: true`); if the page won't load but reputable sources agree, keep it as
  `verified: false` (flagged `†`) rather than dropping a real event. No date / no official
  URL at all → drop it.
- No past events. Events dated beyond the window are dropped **unless** a typed deadline
  falls inside it (then they're kept for that deadline); the Step-6 script enforces this.
- No event without its official URL; never dress up a ticket-reseller or aggregator
  page as official.
- Don't pad a thin window — a short, honest list beats a padded one.
- Don't hand-format the report or add the 🗓️ marker yourself — the scripts own both.
- Grant **calls / application deadlines** are **out of scope** in v1 — leave them to the
  Grants workflow. A funder's annual **forum or meeting** (e.g. Grand Challenges, Skoll,
  World Health Summit) *is* in scope — classify it under the `Philanthropy` theme.
- Do not commit the report to git unless the user explicitly asks. `reports/` is
  gitignored by default for a reason.

---

## Scheduling

This skill is invoked manually by default. To run it twice a year:

```text
/schedule create event-discovery --cron "0 8 1 1,7 *" --command "/event-discovery"
```

(Jan 1 and Jul 1, 08:00 local time.) The `schedule` skill handles the cron wiring; see
its SKILL.md for options. Posting to Slack (Step 9) requires the Slack MCP to be live
in that session — unlike `literature-digest`, this is a soft dependency here (the
report still generates and submits without it; only the alert is skipped), so it's less
critical to guarantee for a scheduled run than for `literature-digest`'s hard MCP gates.

---

## Future work (documented, not implemented)

- **References freshness.** `literature-digest` has a quarterly refresh procedure for
  its reference files, gated by a `check_references_freshness.py` script. This skill's
  references (`event-sources.md`, `classification.md`, `ersilia-priorities.md`,
  `lmic-countries.md`) have no equivalent refresh cadence or check yet — noting this
  explicitly rather than silently omitting it. Worth adding if the source landscape
  (new conference series, shifting Ersilia priorities) drifts noticeably between runs.
