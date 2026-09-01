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

Read all four before starting (`recall-fixture.md` is a fifth, consumed at Step 6a):

- `references/event-sources.md` — where to look per event type, how to query, **and
  the event JSON schema** you must produce. Read before any search.
- `references/classification.md` — the 5-axis taxonomy, marker ribbon, priority
  rubric. Read before classifying.
- `references/ersilia-priorities.md` — the four strategic priorities + relevance
  rubric. Read before screening.
- `references/lmic-countries.md` — the LMIC list behind the 🌍 / Global-South axis.
- `references/recall-fixture.md` — events the sweep must keep finding, graded at Step 6a.
  **Do not read this before sweeping**: knowing the answers would bias the sweep toward
  them, and the fixture would then only ever confirm itself.

---

## Not in scope

**Read this before Step 2, not after someone asks why an event was included.** The
description at the top of this file is the binding definition: events relevant to
**AI/ML for infectious- and neglected-disease drug discovery, Global-South capacity
building, or open science**. An event must serve at least one of those three. "Worth
Ersilia's time" is the *lens*, not the scope — an organisation has many interests wider
than its mission, and this digest covers the mission.

**Out of scope, however relevant they may feel:**

- **Fundraising and corporate-partnership conferences.** Diversified funding is a real
  organisational need and priority 4 names it — but a fundraising-venue tracker is a
  *different digest with a different audience*, not a few rows inside the science one.
- **Grant calls** (unchanged from v1) and fundraising-skills courses — staff training, not
  mission capacity building.
- **General startup / VC / impact-investing events**, including those held in our own
  building. See the Norrsken note in `event-sources.md`.
- **Nonprofit operations** — HR, CRM, comms, governance — and **award ceremonies**,
  **vendor trade shows**, and **job adverts**.
- **General tech conferences** with no drug-discovery, scientific or open-source substance.

**The priority-4 test.** Priorities 1–3 name concrete things; priority 4 (community,
partnerships, sustainability) can absorb almost anything if read loosely, so **an event
mapping to priority 4 alone is a drift candidate**. It needs a second, independent reason:
a named community tie, or Spanish reachability. Priority 4 plus general relevance is
not enough.

### When someone asks "did we catch this event?"

**That question is not automatically a recall bug.** Answer in this order:

1. **Is it in scope?** Apply the mission lens above *before* diagnosing the sweep. If it
   fails, the honest answer is "correctly out of scope" — say so, and do not add a source
   row. Record the decision in `ROADMAP.md` so the same question resolves the same way
   next time.
2. **If it is in scope, why was it missed?** Then it is a recall question, and the answer
   is usually a missing query axis rather than a missing row — see Step 2 Pass B.

**This ordering exists because it was got wrong.** Over three days in August 2026, three
consecutive "did we catch this?" questions each produced a new source class; the third
(a corporate-charity fundraising conference) was admitted, then reverted a day later for
contradicting the description above. Nothing in this file pushed back, because it only
ever said what to collect. A digest that grows by whichever URL arrived most recently
stops being the thing the team subscribed to.

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

### Step 2 — Sweep sources (web) — two passes, both required

**Pass A alone is what caused the sweep's worst miss.** A source-scoped query can only
refresh a series the map already names, so an unlisted series is invisible however
relevant it is — that is how the 2026-08-04 report missed the EDCTP Forum 2027 despite
its abstract deadline being open. Pass B exists to find what the map does not know.

#### Pass A — source-driven

Work through `references/event-sources.md`. For each in-scope event type run **≥4
query variants** (source-scoped `WebSearch` plus a couple of open searches for the
`focus`), anchored to the window's year(s). Events 6–12 months out are often announced
under the *following* year — query both. Aim for a **raw pool of 30–60 candidates**.

#### Pass B — axis-driven (never scoped to a known venue name)

Query the **mission**, not the map. Every axis below runs **every time**, regardless of
`focus` — these are floors, not suggestions. Record which ones you ran and pass them to
`--axes-searched` in Step 7.

**This is enforced, not trusted.** `render_report.py` **refuses to render** unless every
axis in `AXIS_ORDER` and every continent is claimed, exiting non-zero and naming what is
missing. That gate exists because this instruction was already written here, in bold, and a
run skipped ML methods, Asia and Oceania anyway. The footers reported the gap honestly,
which only helps a reader who checks. Refusing to render is what stops a partial sweep
shipping as a complete report.

**"Swept" means queried, never found.** An axis that returns nothing is still swept — say
so and pass it. Completeness therefore costs one more query and can never cost a fabricated
event. If a sweep genuinely cannot be completed, `--allow-incomplete-sweep` renders it with
a ⚠️ warning stamped in the report header; tell the user why you used it.

| Axis | Run at least | Shape of query |
|---|---|---|
| **Pathogens** — TB, malaria, *Leishmania*/Chagas, schistosomiasis, AMR | one per pathogen (5) | `tuberculosis conference OR congress <year>`, `antimicrobial resistance conference <year>` — see "Priority-pathogen circuits" in `event-sources.md` |
| **ML methods** | one or two | `machine learning drug discovery workshop <year> call for papers`, `NeurIPS OR ICML OR ICLR <year> AI for science workshop`. **Do not query method names alone** — `QSAR OR graph neural network OR molecular representation conference <year>` returns arXiv papers, not events (verified 2026-08-19). Method venues are mostly *workshops attached to* the big ML conferences, so pair this axis with Pass A's LMRL / MoML / M2D2 rows. |
| **Spain** — Barcelona, Catalonia & national | one or two, **in Spanish or Catalan** | `congreso OR jornada OR simposio <year> Barcelona`, `Biocat agenda <year>` — see "Spain" in `event-sources.md` |
| **Open deadlines** | one or two | `call for abstracts <year> global health OR drug discovery`, `abstract deadline <month> <year> tropical medicine` |

The **deadline axis inverts the usual search**: it hunts for a *deadline* rather than an
event, because the highest-value hit is an event 6–12 months out whose abstract or
bursary deadline closes in weeks. Those are invisible to a "conference `<year>`" query
that ranks on event date, and the report's "Act now" block can only ever render what the
sweep already caught — it never goes looking.

The pathogens and method areas are listed in `ersilia-priorities.md` and were, before
this pass existed, used only to **screen** at Step 4 and never to **search** here. That
asymmetry is the recall bug: it left one TB event and no AMR-specific venue in a report
whose mission is antimicrobial drug discovery.

Also keep events **beyond** the window whose **deadline is already open** — a conference
in mid-2027 whose abstract or bursary deadline falls inside the window is actionable
*now*. The script routes these into a separate section; don't discard them just because
the event date is past `--to`.

**Cover every continent.** Run at least one query aimed at each of Africa, Europe, Asia,
South America, North America, and Oceania — don't let the default sources skew the sweep
to Europe / North America / Africa. For Asia and Latin America especially, query regional
bodies (see the "Global-South regional" sources) and in **Spanish / Portuguese** too.
Spain is **not** covered by that instruction — it has its own axis in Pass B, queried in
Spanish and Catalan, because "Europe: swept" at continent granularity hid the fact that
nothing ever queried Ersilia's own city.
Track which continents you actually queried and pass them to `--continents-searched` in
Step 7. If a continent genuinely returns nothing verifiable, that's fine — the report
will mark it "searched, none verified" so the gap is visible, never silently empty. Asia and
Oceania in particular return mostly aggregators and vanity `International Conference on
<topic>` series; "searched, none in report" is the correct honest outcome there, and far
better than admitting a predatory conference to fill the column.

**All six are enforced by `render_report.py`** — see Pass B above. An event turning up *from*
a continent does not count as having searched it: the flag means you aimed a query there.
That distinction was got wrong once already, with four continents claimed on the strength of
events that arrived incidentally through pathogen queries.

### Step 2a — Sweep Slack (`#general`)

Teammates post events in `#general` that no web sweep will surface. Read them
as a **first-class source**, not a bonus.

```text
slack_search_channels(query="general")      # resolve the id, never hardcode it
slack_read_channel(channel_id=<id>, ...)    # messages since the previous digest
```

**Check `Is Archived` on the resolved channel before reading.** On 2026-08-07 the
workspace collapsed to three public channels, and `#networking` — this step's
original target — was archived into `#general`. Reading an archived channel is the
nastiest failure mode available here: it returns **no new messages and no error**,
so the run looks like a quiet month rather than a broken connector. If the resolved
channel is archived, stop and tell the user which channel superseded it; do not
silently continue.

Collect the messages to `/tmp/slack_raw.json` (each needs at least `text`, `ts`,
`user`; add `user_real_name` via `slack_read_user_profile` and `permalink` when
available), then:

```bash
python scripts/fetch_slack.py --raw /tmp/slack_raw.json \
  --out /tmp/slack_candidates.json --channel "#general"
```

**Window: since the previous digest.** Take the date from the newest remote
report Step 0 already listed. No fixed lookback — that would either re-read
months of history or miss a delayed run.

**The feedback loop is the trap here.** Step 9 posts this skill's own alert
*into* `#general`, so a naive read re-ingests it as a fresh batch of candidates
every month, compounding. `fetch_slack.py` guards this with a prefix match on the
alert signature over *normalised* text — `normalise_for_match` strips the emoji
shortcodes and rewritten emphasis that Slack applies on read-back, which is what
defeated the earlier literal match. Verified against the real 2026-08-04 alert as
Slack stored it.

**Do not pass `--exclude-user` for a human teammate's ID.** The alert is posted
under whichever account runs the skill, so excluding that ID would also discard
that person's own genuine event shares — a real loss now that the channel is
`#general`, where they post as a normal participant. The signature guard plus the
`SELF_URL_MARKERS` filter already cover the loop. Reserve `--exclude-user` for a
dedicated bot identity, if one is ever introduced.

**Candidates are not events.** A Slack message yields a URL and a sharer, never
the `name` / `start_date` / `location` the schema requires. Each candidate goes
through Step 3 exactly like a web hit — the difference is only how it entered.

**`#general` is a mixed feed, so most of its links are not events.** The old
`#networking` was topically curated — nearly every link in it was an event or an
organisation worth knowing. `#general` also carries papers, blog posts, tool
releases, job ads, funding calls, publication announcements and congratulations.
`fetch_slack.py` cannot tell these apart and does not try: it is a normaliser, and
it emits one candidate per URL. **Step 3 is where a link is judged to be an event**
— see the participation test there. Expect a majority of `#general` candidates to fall
out at that step; that is the step working, not a bug.

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

**Announced but not yet built (from the news-feed sources).** An event found via Pass A's
news feeds often has no microsite yet — only an announcement naming the city and dates.
Keep it, with `verified: false` and the **announcement URL** as `url`, and swap in the
official site on a later run once it exists. Dropping these would defeat the point of
sweeping announcements at all: they are precisely the 6–18-month-out events the sweep
used to miss entirely.

Two hard conditions, because this lowers the verification bar:

- **The page you cite must itself state the year or edition.** Never cite a series'
  generic landing page — `worldleish.org`, `edctpforum.eu` with no year — as
  confirmation of a specific edition. Those pages outlive every edition and will read as
  verified for a year that has not been announced. Cite the dated announcement.
- **Dates must be stated, not inferred** from "next spring" or a previous edition's
  timing. If the announcement gives a month but no days, treat the date as unknown
  rather than guessing the first of the month.

**First, the participation test — is this an event at all?** An event is something
**a person takes part in, bounded in time**. Two shapes qualify:

- A **convening** — conference, congress, symposium, workshop, summer school,
  hackathon, datathon, webinar, funder forum. You attend it, on dates.
- A **structured participation opportunity** — fellowship, training programme,
  prediction challenge or competition, with a cohort and an application deadline.
  `event-sources.md` puts these in scope for v1 deliberately, so the test cannot be
  "does it have dates you attend" alone.

These are **not** events, however relevant they are: a paper or preprint, a blog
post, a tool / library / model release, a **job advert**, an organisation's homepage,
a network-membership page, a newsletter, or a social-media post *about* something.

**The line between a fellowship (in) and a grant call (out)** is who takes part: a
fellowship or school trains *people* on a cohort basis, while a grant call funds an
*institution's* project. v1 keeps the first and excludes the second, while keeping a
funder's own *forum* in. This matters more since `#funding-opportunities` folded into
`#general`: grant calls now arrive on the same feed as events. A deadline alone never
makes something an event — a job advert has one too.

A human-sourced URL therefore has three outcomes, not two:

1. **A specific convening** → a candidate. Continue below.
2. **An organisation or programme page** → treat it as a **lead, not a candidate**.
   Look for a specific upcoming convening on that site; if there is one in the
   window, *that* becomes the candidate and the sharer keeps the credit. If there
   isn't, carry it to Step 7a as a lead rather than inventing an event from a
   homepage.
3. **Neither** → drop it, and list it at Step 7a as dropped-not-an-event. The drop
   must be **visible**: a colleague posted it, so the user overrules the call, not
   the skill silently.

**Exception for team-shared candidates (Step 2a).** Verify-or-drop applies to
machine-discovered events. A candidate a colleague posted is **kept even when it
cannot be verified at all** — set `verified: false` so it renders with `†`, and
keep `shared_by`. A human vouched for it; silently discarding that is worse than
carrying a flagged row the reader can judge at Step 7a.

**This exception covers verification, never the participation test.** "The official page
is down" and "this is not an event" are different failures. The first is what a
colleague's vouching can stand in for; the second it cannot — a blog post does not
become a convening because someone shared it.

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

**Human-sourced events skip this screen.** A colleague posting a link is relevance
signal the rubric cannot see — they know what Ersilia is chasing this quarter. So a
`shared_by` event is kept even when you cannot map it to a priority; record
`priorities: []` and let the reader judge.

**The screen is skipped, not the participation test.** The bypass is about *relevance*
only. Anything that failed Step 3's participation test never reaches this step, so
"shared by a colleague" cannot carry a blog post or a funding call into the report.
Keeping these two gates distinct is what makes the bypass safe on a mixed channel
like `#general`: the scorer is overruled about **what matters**, never about **what
an event is**.

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
**The ledger is READ-ONLY at this step.** It is written only after Step 8's push
succeeds, by `scripts/update_ledger.py`. The ledger's job is to stop an event that has
*already been reported* from being reported again — so writing it here, before the Step 7a
approval gate, marks events seen even when the report is never published, and they then
never resurface. That is the exact opposite of what the ledger is for, and it is silent.
It bit twice on 2026-09-01, once while preparing that day's own digest. `filter_and_sort.py`
has an `--update-ledger` escape hatch for backfills; do not use it in the normal flow. **This is what makes the
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

### Step 6a — Grade the sweep against the recall fixture

```bash
python scripts/check_recall.py --fixture references/recall-fixture.md \
  --pool /tmp/events_pool.json --clean /tmp/events_clean.json --today <today>
```

**Why this exists.** Every improvement to `event-sources.md` and to Step 2's axis pass is
otherwise unverifiable. A sweep that quietly degrades produces a thin report, and a thin
report is indistinguishable from a quiet month — so recall can rot for a year without
anyone noticing. `references/recall-fixture.md` pins events the sweep is known to be able
to find, each tagged with the axis or source that should catch it, so a miss names its own
cause.

**It warns; it never blocks — and that is deliberate**, the opposite of the completeness
gate in Step 7. A missing query is always the operator's fault and always fixable by
running it. A fixture miss may just mean the event moved, was renamed, or stopped
existing. A check that fails on legitimate misses is one people learn to bypass.

- Graded against the **pool**, not the report: the pool is what the sweep *found*, before
  the window filter and before the ledger hides already-seen editions. Grading the report
  would make every entry start failing the month after it first appeared.
- `--clean` additionally grades the "must exclude" rows, which test rules that run after
  the pool is written.
- **Carry the result into the Step 7a summary** — found/missed counts, and any missed
  entry with the lever that should have caught it.
- **Expired rows are not misses.** When the script says *needs replacing*, replace the
  entry with the next edition of that series or another event exercising the same lever.
  Left alone, the fixture becomes a list of false alarms.

### Step 7 — Render the report (script) + summarise

```bash
python scripts/render_report.py --in /tmp/events_clean.json --focus "<focus>" --from <from> --to <to> --today <today> --swept <N> --continents-searched "Africa,Europe,Asia,South America,North America,Oceania" --axes-searched "TB,Malaria,Leishmania/Chagas,Schistosomiasis,AMR,ML methods,Spain,Open deadlines" --connectors "web:ok,slack:ok" --out <report path>
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

`--axes-searched` does the same job for Step 2's **Pass B** axes and adds a **Sweep axes**
section. Known axes are `TB, Malaria, Leishmania/Chagas, Schistosomiasis, AMR, ML methods,
Spain, Open deadlines`; matching is case-insensitive and tolerant (`chagas` matches
`Leishmania/Chagas`), and a value matching nothing raises a WARNING rather than passing
silently.

**Both flags are required and completeness is enforced.** Missing either flag, or omitting
any axis or continent from it, makes the script **exit non-zero without writing a report**,
listing exactly what was not queried. Do not work around this by padding the flag: claiming
an axis you skipped is the one outcome worse than the gap itself, because nothing downstream
can detect it. Go and run the query — an axis that returns nothing still counts as swept.
`--allow-incomplete-sweep` is the deliberate escape hatch and stamps a ⚠️ line into the
report header; if you use it, say why in the Step 7a summary.

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

Three things are the user's call at this gate, not the skill's:

- **A run with zero new events.** Publish an empty report as a "nothing new this
  month" signal, or skip this cycle. There is no automatic rule — ask.
- **Anything the report flags as uncertain**: `†` unverified events (including
  human-sourced ones kept under Step 2a's exception) and any WARNINGs from
  Step 6.
- **The recall-fixture result** (Step 6a): the found/missed count, each missed entry with
  the lever that should have caught it, and any row flagged as expired. A miss is not a
  reason to withhold the report — it is a reason to look at that axis before the next run.
- **Every human-sourced link that did not become an event.** List them in the
  in-chat summary — never in the published report — in two groups:
  - **Leads** — organisation or programme pages with no specific convening found
    (Step 3, outcome 2).
  - **Dropped, not an event** — papers, blog posts, tool releases, job ads,
    funding calls (Step 3, outcome 3), each with one clause saying which.

  Name the sharer to the user here; the published report and the Slack alert still
  credit sharers only for events that made it in. This list is the price of the
  participation test: it keeps a teammate's contribution from vanishing silently, and
  it is the user — not the skill — who overrules a judgement call. Say `none` when
  there were none, so its absence never reads as an omission.

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
- **Record the published events in the ledger — only now, after the push succeeded:**

  ```bash
  python scripts/update_ledger.py --in /tmp/events_clean.json \
    --ledger ~/.ersilia/events_seen.json --first-seen <YY-MM-DD of the report>
  ```

  This is what stops next month's digest repeating this month's list. It is idempotent, so
  re-running after a retry is safe. If the push failed, **do not run it** — the events were
  not published, so they must stay eligible for the next run.
- No README index update — the website's navigation is generated directly from
  the files under `events/` (once the site templates support that folder), not
  from a hand-maintained README list.

If the submission fails for a recoverable reason (network blip, `gh` auth
lapsed), keep the local file intact and tell the user how to re-run just this
step. Never delete the local file before a successful submission.

### Step 9 — Post the Slack alert (only after a successful submission)

After (and **only** after) the Step 8 `gh api` call succeeds, post a rich
notification to `#general` so the team sees what is in the report without
clicking through.

Resolve the channel by name via the Slack MCP — its ID is not hardcoded here
(unlike `literature-digest`'s `#literature`):

```text
slack_search_channels(query="general")
```

- If no matching channel is found, **do not** post elsewhere. Tell the user
  `#general` doesn't exist (or isn't visible to this session) and skip the
  post; the report is still generated and submitted, so nothing is lost — only
  the Slack post is skipped.
- **If the resolved channel is archived, skip the post the same way.** Unlike the
  silent read in Step 2a, posting to an archived channel fails outright — but check
  `Is Archived` first anyway, so the user gets "the target channel was archived"
  rather than a raw API error.
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

## Sweep axes
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
