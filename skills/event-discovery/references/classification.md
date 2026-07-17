# Event classification — the 5-axis taxonomy

Single source of truth for how every event is labelled. Each event carries a value on
**all five axes** plus a compact emoji marker ribbon. The values here are the only
allowed values — `filter_and_sort.py` and `render_report.py` expect them verbatim.
Do not invent new axis values.

## The five axes

| Axis | Field | Allowed values |
|---|---|---|
| **Scope** | `scope` | `Local` · `Regional` · `Global-South` · `International` |
| **Theme** | `theme` | `Science` · `Philanthropy` · `Community` · `Training` |
| **Format** | `format` | `In-person` · `Virtual` · `Hybrid` |
| **Type** | `type` | `Conference` · `Symposium` · `Workshop` · `Summer school` · `Hackathon` · `Datathon` · `Fellowship` |
| **Priority** | `priority` | `High` · `Medium` · `Low` |

### Scope — where it sits geographically

- `Local` — Barcelona, Catalonia, or elsewhere in Spain.
- `Regional` — elsewhere in Europe.
- `Global-South` — hosted in a low- or lower-middle-income country, **or** explicitly
  serving / prioritising Global-South participants (bursaries, regional focus). Decide
  LMIC status with `lmic-countries.md`. This axis value also earns the 🌍 marker.
- `International` — global or hosted outside Europe in a high-income country (e.g. US,
  Japan), not LMIC-focused.

Pick the single most informative value. A summer school in Kenya is `Global-South`, not
`International`, even though attendees are global.

### Theme — what the event is fundamentally about

- `Science` — AI/ML, cheminformatics, drug discovery, infectious / neglected-disease
  research. The default for most technical conferences.
- `Philanthropy` — funders, foundations, donors, grant-maker forums, donor-community
  gatherings.
- `Community` — open-source / open-science community events, networking, partnerships.
- `Training` — capacity-building, education, hands-on skill transfer.

An event can touch several themes; record the primary one. (A training school with a
strong AI-methods syllabus is `Training` if skill transfer is the point, `Science` if
it is really a research meeting with a tutorial attached.)

### Format, Type — literal descriptors

Use the event's own description. If a conference has a co-located hackathon, classify the
**event you are recommending** — split into two rows if both are worth attending.

### Priority — the action signal

`High` / `Medium` / `Low`, scored with the rubric in `ersilia-priorities.md`
(strategic fit × Global-South relevance × reachability). Every event also gets a
recommended **action**: *attend / apply / partner / watch*.

## Marker ribbon (fixed display order `⭐🌍🎓💻💰🗓️`)

Stored in the `markers` field as a string in this exact order; render as-is. Apply a
marker **only when load-bearing — absent beats wrong.**

| Marker | Apply when |
|---|---|
| ⭐ | `priority` is `High` — a top pick worth the team's active effort |
| 🌍 | `scope` is `Global-South` (LMIC-hosted or LMIC-serving, per `lmic-countries.md`) |
| 🎓 | training / capacity-building event (`type` ∈ {Workshop, Summer school} or `theme` = Training) |
| 💻 | open-source or AI-methods focus — the event centres on code, models, or ML methods |
| 💰 | the event offers a **bursary / financial aid / travel support** (from the `bursary` field) |
| 🗓️ | **any** typed deadline (abstract / early-bird / registration / bursary) falls within the report window |

Claude sets `⭐🌍🎓💻`. The last two are script-derived: `filter_and_sort.py` appends 💰
when the `bursary` field names real support, and 🗓️ when any `deadlines` entry lands
in-window. Claude still records the raw `bursary` and `deadlines` values — the script
decides the markers.

## Worked examples

- **Deep Learning Indaba (Africa, annual)** — `scope: Global-South`, `theme: Training`,
  `format: In-person`, `type: Conference`, `priority: High`; markers `⭐🌍🎓💻`; maps to
  priorities 3 & 4; action *attend*.
- **Gordon Research Conference on Medicinal Chemistry (US)** — `scope: International`,
  `theme: Science`, `format: In-person`, `type: Conference`, `priority: Medium`; markers
  `⭐`? only if High else none; maps to priority 2; action *watch* (costly, far).
- **A virtual RSC cheminformatics workshop with an abstract deadline next month** —
  `scope: International`, `theme: Science`, `format: Virtual`, `type: Workshop`,
  `priority: High`; markers `⭐🎓💻🗓️`; maps to priority 1; action *apply*.
