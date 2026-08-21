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
allowed-tools: [Read, Write, Bash, WebSearch, WebFetch, AskUserQuestion, slack_search_channels, slack_read_channel, slack_read_user_profile, slack_send_message]
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
  12-month look-ahead is deliberately generous, for **two** reasons — events
  need long planning lead time (bursaries, abstract deadlines, travel
  booking), *and* a wide window is the **recovery net for events that missed
  an earlier digest**. An event never captured has no ledger entry, so only a
  later sweep can catch it. Under the monthly cadence (see Scheduling) that
  means re-sweeping the same 12 months every run for a handful of new hits:
  accepted cost, paid deliberately, because the alternative is that anything
  missed once is missed permanently.
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

The report is monthly, not redundant. The canonical home is the remote
`ersilia-os/digests` repo, so check there directly — no dedicated script, just
one inline command:

```bash
if LISTING=$(gh api repos/ersilia-os/digests/contents/events --jq '.[].name' 2>&1); then
  printf '%s\n' "$LISTING" | sort -r | head -3
elif printf '%s' "$LISTING" | grep -q 'Not Found'; then
  echo "events/ folder does not exist yet — first run, continue to Step 1."
else
  echo "STOP — cannot read the remote digests repo:" >&2
  printf '%s\n' "$LISTING" >&2
  exit 1
fi
```

**Do not discard stderr here.** A 404 (`events/` not created yet) and an auth or
network failure both produce *no filenames*, so a suppressed error is
indistinguishable from a clean first run — the skill would sail past the guard
and republish over existing work. That is the precise failure this step exists
to prevent, so "Not Found" is the **only** soft case; everything else stops the
run and surfaces the message.
- If it prints filenames, read the newest one's embedded date
  (`YY-MM-DD-event-discovery.md`). If that date is within the last **20 days**,
  **stop and ask** the user whether they want to proceed anyway (`--force`
  skips this check). 20 days is tuned to the monthly cadence: it catches a
  same-day or same-week accidental re-run while always clearing the next
  scheduled run, which is ~28–31 days out. **Do not raise this back toward a
  full cycle length** — at 150 days (the old twice-yearly value) it would
  reject every monthly run.
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

### Step 2a — Sweep Slack (`#networking`)

Teammates post events in `#networking` that no web sweep will surface. Read them
as a **first-class source**, not a bonus.

```text
slack_search_channels(query="networking")   # resolve the id, never hardcode it
slack_read_channel(channel_id=<id>, ...)    # messages since the previous digest
```

Collect the messages to `/tmp/slack_raw.json` (each needs at least `text`, `ts`,
`user`; add `user_real_name` via `slack_read_user_profile` and `permalink` when
available), then:

```bash
python scripts/fetch_slack.py --raw /tmp/slack_raw.json \
  --out /tmp/slack_candidates.json --channel "#networking" \
  --exclude-user <the id that posts the Step 9 alert>
```

**Window: since the previous digest.** Take the date from the newest remote
report Step 0 already listed. No fixed lookback — that would either re-read
months of history or miss a delayed run.

**The feedback loop is the trap here.** Step 9 posts this skill's own alert
*into* `#networking`, so a naive read re-ingests it as a fresh batch of
candidates every month, compounding. `fetch_slack.py` guards this two ways —
dropping messages whose text starts with the alert signature, and dropping
`--exclude-user` ids. Pass the flag; the text match alone is a fallback, not the
plan.

**Candidates are not events.** A Slack message yields a URL and a sharer, never
the `name` / `start_date` / `location` the schema requires. Each candidate goes
through Step 3 exactly like a web hit — the difference is only how it entered.

**If the Slack MCP is unavailable**, skip this step, continue on web sources
alone, and record `slack:down` in `--connectors` (Step 7) so the header shows 🔴.
Do not fail the run.

### Step 3 — Verify each event

`WebFetch` the event's **official page** and confirm **name, exact dates, location,
official URL**. If the page confirms them, set `verified: true`. If the official page
**can't be fetched** (site down, cert error) but independent reputable sources agree on
name/dates/URL, keep the event with `verified: false` — it will be flagged with `†` in
the report rather than silently dropped. If you can't establish a date or an official
URL at all, drop it (omit, never guess a date).

**Exception for team-shared candidates (Step 2a).** Verify-or-drop applies to
machine-discovered events. A candidate a colleague posted is **kept even when it
cannot be verified at all** — set `verified: false` so it renders with `†`, and
keep `shared_by`. A human vouched for it; silently discarding that is worse than
carrying a flagged row the reader can judge at Step 7a.

**If the official page states no dates**, set `start_date: null` — never guess.
`validate_event` waives the required `start_date` when `shared_by` is set, and the
event renders under **"Shared by the team — dates not yet announced"** rather than
being dropped. This waiver is narrow by design: a *machine-discovered* event with
no date is still dropped, because there "no date" means the sweep failed, while for
a shared event a colleague has already vouched for the thing existing.

**A shared event the web sweep also found keeps its credit.** When the same event
arrives twice, `filter_and_sort.py` merges `shared_by` and 💬 onto whichever copy it
kept, so the colleague is credited even though the web copy is the one that
survived dedup.

Also capture, when stated: the **typed
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
Write the pool to `/tmp/events_pool.json` as a JSON array conforming to the schema in
`references/event-sources.md`. Set the `⭐🌍🎓💻💬` markers yourself; do **not** add the
💰 or 🗓️ markers — the script derives those from the `bursary` and `deadlines` fields.

**`focus_region` (optional).** Set it when an event is *about* a region other than
the one it is held in — an "AMR in Africa" symposium in London gets
`focus_region: "Africa"`. Accepts a country or a continent. Leave it out for the
common case where the event is simply about where it happens; the scripts fall
back to `country` wherever focus is needed. One row per event either way — the
report never cross-lists an event under two continents.

**🌍 follows *focus*, not location.** Use `references/lmic-countries.md`, but apply
it to what the event is *about*: an Africa-focused event held in Berlin earns 🌍;
a generic European conference that happens to host one LMIC speaker does not.
Where no `focus_region` is set, this collapses to the old location-based reading,
so most events are unaffected.

**For candidates from Step 2a**, additionally set `shared_by` to the sharer's
name and add the 💬 marker. The renderer credits them in a footnote rather than a
table column.

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
The ledger is updated with every kept event at the end of the run, so next month's run
won't re-surface the same edition this one already showed. **This is what makes the
monthly cadence readable** — without it, every run would repeat the same standing list.
The
file lives outside this repo (`~/.ersilia/events_seen.json`, in the user's home
directory) so it persists across runs regardless of cadence and is never committed. If
the user explicitly asks for a full, unfiltered sweep (e.g. "show me everything
again"), omit `--ledger`/`--hide-seen` for that one invocation rather than editing or
deleting the ledger file.

**Known limitation — accepted deliberately.** The ledger key is
name+location+year, so it does **not** change when an event's *details* change.
An event first surfaced with `deadline: Unknown` will never resurface when its
deadline is later announced, because it is already recorded for that edition.
Under the monthly cadence that blind window is up to eleven months wide. The
mitigation is Step 3: when verifying an event, capture deadlines properly the
*first* time, since there is no second chance within the edition. If this proves
too costly in practice, the fix is a fingerprint over the
deadline/bursary/registration fields added to the ledger record — recorded here
so the tradeoff stays visible instead of being rediscovered as a bug.

### Step 7 — Render the report (script) + summarise

```bash
python scripts/render_report.py --in /tmp/events_clean.json --focus "<focus>" --from <from> --to <to> --today <today> --swept <N> --continents-searched "Africa,Europe,Asia,South America,North America,Oceania" --connectors "web:ok,slack:ok" --out <report path>
```

`--connectors "web:ok,slack:ok"` renders the `**Connectors:**` header line, 🟢 for
`ok` and 🔴 for anything else. Pass `slack:down` when Step 2a was skipped. Omit the
flag entirely and the line is left out rather than implying every connector was
healthy.

`--today` (the current date) drives the **Act now** countdown; it defaults to `--from`
if omitted. Pass the real today when `--from` isn't today.

`--group-by continent` (the **default**) sections the report by continent (Africa →
Europe → Asia → South America → North America → Oceania), and **within each continent
sub-groups by theme** (Science → Training → Community → Philanthropy) — useful for
travel/reachability decisions, which is what this report is mainly read
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

### Step 7a — Review gate (STOP here)

**Nothing is published until the user approves this run.** Present the rendered
report and the in-chat summary, then **stop and wait**. Steps 8 and 9 do not run
on the same turn as Step 7 unless the user has already said, in this session, to
publish without reviewing.

State plainly what will happen on approval — the remote path it will be written
to, and that a Slack alert will follow — so "yes" is informed consent for both,
not just the push.

This gate exists because publishing is a two-channel, effectively irreversible
action: Step 8 writes to a public repo that auto-rebuilds a public site, and
Step 9 posts to a team channel. Neither can be cleanly retracted — the Slack MCP
available here has **no edit-message tool**, so a wrong number in the alert
cannot be corrected in place, only superseded by a later report.

Two things are the user's call at this gate, not the skill's:

- **A run with zero new events.** Publish an empty report as a "nothing new this
  month" signal, or skip this cycle. There is no automatic rule — ask.
- **Anything the report flags as uncertain**: `†` unverified events (including
  human-sourced ones kept under Step 2a's exception) and any WARNINGs from
  Step 6.

If the user declines, keep the local file and stop. Do not partially publish —
never run Step 8 without Step 9, or the report goes live silently.

### Step 8 — Submit to the canonical remote and hand off

**Precondition: the user approved this run at Step 7a.** Do not run this step
speculatively or "to save a round trip".

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
# Suppressing stderr is safe *here* (unlike Step 0): see the note below.
SHA=$(gh api "repos/ersilia-os/digests/contents/$REMOTE_PATH" --jq .sha 2>/dev/null)

gh api -X PUT "repos/ersilia-os/digests/contents/$REMOTE_PATH" \
  -f message="Add $(basename "$REPORT") (event discovery report)" \
  -f content="$(base64 < "$REPORT" | tr -d '\n')" \
  -f branch="main" \
  ${SHA:+-f sha="$SHA"}
```

- `gh` must be authenticated (`gh auth status` checks this).
- **Why `2>/dev/null` is acceptable on the SHA lookup but not in Step 0.** Here a
  swallowed error can only ever leave `$SHA` empty, and an empty `$SHA` makes the
  `PUT` fail *loudly* — 422 `sha wasn't supplied` if the file exists, or an auth
  error if that was the real cause. There is no silent-wrong-outcome path. In
  Step 0 the same suppression is genuinely dangerous, because an empty result is
  a valid "nothing published yet" answer that lets the run proceed.
- `base64` has no portable no-wrap flag — `-w0` is GNU-only and errors on
  macOS/BSD. `base64 < "$REPORT" | tr -d '\n'` works on both; keep it that way.
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
# Ersilia Event Digest — <YYYY-MM-DD>

**Scope:** N new events · window <from> → <to> · M sources swept · focus: <focus>
**Connectors:** Web hunt 🟢 · Slack 🟢
**Markers:** ⭐ High-priority fit · 🌍 Global-South · 🎓 Training · 💻 Open-source / AI methods · 💰 Bursary / travel support · 🗓️ Deadline in window · 💬 Shared by the team

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

## Shared by the team — dates not yet announced
| … |

## Virtual / online
| … |

## Deadlines (within the window)
- **<YYYY-MM-DD>** — [Name](url) · abstract / CFP

## Coverage by region focus
_Counted by what each event is **about**, not where it is held …_
- **Africa**: 3 events

---
† Not confirmed on the official page …

💬 Shared by the team rather than found by the automated sweep:
- Name — @sharer
```

**The header block must never use pipes.** It reads as three bold lines with `·`
separators because an earlier single line of `*Generated: … | Window: … | Events: …*`
was parsed by kramdown as a one-row **table** on the published page, with the italic
asterisks leaking through as literal `*Generated:` and `37*`. A lone pipe-delimited
line is a table waiting to happen — keep separators as `·`.

**The count is a delta.** `N new events` is what Step 6 kept after dropping
already-seen editions, not a standing total. A low number is the expected steady state
under the monthly cadence, not a failed sweep.

**The coverage footer counts region *focus*, so it will not match the continent
section counts** — an Africa-focused event held in Berlin sits under Europe but counts
toward Africa in the footer. That divergence is intentional; the heading and the
italic note carry it.

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

## Cadence

**Monthly, on the first Friday, invoked manually.** There is deliberately no
cron job: the user runs the skill from a standing calendar reminder, because
every report is reviewed before it is published (Step 7a) and an unattended run
would have nothing to gate on.

Do **not** offer to automate this with `/schedule`. Beyond the review gate,
"first Friday" is not expressible in cron: in Vixie cron, when both
day-of-month and day-of-week are restricted they combine as **OR**, not AND, so
`0 8 1-7 * 5` fires on the 1st–7th *and* on every Friday. Automating it
correctly would need a Friday-only schedule plus a
`[ "$(date +%-d)" -le 7 ] || exit 0` guard in the command — complexity with no
payoff while a human is reviewing each run anyway.

Because the cadence is monthly and Step 6 drops already-seen events, a typical
run surfaces **few** events — often a handful, sometimes none. That is the
intended steady state, not a failed sweep; see Step 7's delta framing.

Posting to Slack (Step 9) needs the Slack MCP live in the session. Unlike
`literature-digest`, that is a **soft** dependency for the alert but a **hard**
one for the Slack *connector* in Step 2a — without the MCP the run proceeds on
web sources alone and both the alert and the Slack sweep are skipped, which the
`**Connectors:**` header line records as 🔴.

---

## Future work (documented, not implemented)

- **References freshness.** `literature-digest` has a quarterly refresh procedure for
  its reference files, gated by a `check_references_freshness.py` script. This skill's
  references (`event-sources.md`, `classification.md`, `ersilia-priorities.md`,
  `lmic-countries.md`) have no equivalent refresh cadence or check yet — noting this
  explicitly rather than silently omitting it. Worth adding if the source landscape
  (new conference series, shifting Ersilia priorities) drifts noticeably between runs.
