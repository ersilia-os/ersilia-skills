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
argument-hint: [focus] [--from <date>] [--to <date>] [--out <path>]
allowed-tools: [Read, Write, Bash, WebSearch, WebFetch, AskUserQuestion]
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
  Default: **today → +9 months**. Past events are always excluded.
- **`--out`** (optional): output path override for the report.

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

### Step 1 — Parse the request

Extract the `focus`, resolve the date window (default today → +9 months; today is
whatever the current date is), and note any explicit type or region signal. Keep the
resolved `--from`/`--to` — every later step and both scripts use them.

### Step 2 — Sweep sources (web)

Work through `references/event-sources.md`. For each in-scope event type run **≥4
query variants** (source-scoped `WebSearch` plus a couple of open searches for the
`focus`), anchored to the window's year(s). Events 6–9 months out are often announced
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
python scripts/filter_and_sort.py --in /tmp/events_pool.json --from <from> --to <to> --out /tmp/events_clean.json
```

Validates required fields, de-duplicates recurring series, sorts by date, and flags
in-window deadlines (adds 🗓️). Drops events outside the window **unless** a typed
deadline lands inside it — those are kept and routed to a "beyond the window" section.
**Read the WARNINGs it
prints** — note any dropped events in the in-chat summary so nothing disappears silently.

**Recurring runs (optional).** Add `--ledger <path>` to remember events across runs:
events already in the ledger are tagged `(seen)`, and the ledger is updated with this
run. Add `--hide-seen` as well to *drop* seen events for a "what's new since last time"
report. Omit `--ledger` entirely for a normal one-off run (the default). Keep the ledger
file outside version control (a stable path like `~/.ersilia/events_seen.json`).

### Step 7 — Render the report (script) + summarise

```bash
python scripts/render_report.py --in /tmp/events_clean.json --focus "<focus>" --from <from> --to <to> --today <today> --swept <N> --continents-searched "Africa,Europe,Asia,South America,North America,Oceania" --out <report path>
```

`--today` (the current date) drives the **Act now** countdown; it defaults to `--from`
if omitted. Pass the real today when `--from` isn't today.

`--group-by continent` sections the report by continent (Africa → Europe → Asia →
South America → North America → Oceania), and **within each continent sub-groups by
theme** (Science → Training → Community → Philanthropy) — useful for travel/reachability
decisions. Default is `theme` (single level). Continent is derived from each event's
`country`. **Virtual / online events** (no physical location) are never a continent —
in either mode they collect into a single **Virtual / online** section at the end.

`--continents-searched "Africa,Europe,Asia,South America,North America,Oceania"` (the
continents you queried in Step 2) adds a **Coverage by continent** footer. Continents you
searched that found nothing show "searched, none verified"; any you skipped show "not
searched" — so coverage is always explicit. Pass this on every run.

Output location (mirrors the literature skills):
- **Claude.ai / Cowork:** write to `/mnt/user-data/outputs/events_<focus>_<YYYYMMDD>.md`
  and call `present_files`.
- **Claude Code / local:** that path won't exist — write to `--out` if given, else
  `./events_<focus>_<YYYYMMDD>.md`, and hand the user the file path.

`<N>` is the number of distinct sources you actually swept. Then surface the file and
write the **in-chat summary**: the top 3 events (one line each), the single most
time-sensitive deadline, and a note of anything the script dropped.

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
