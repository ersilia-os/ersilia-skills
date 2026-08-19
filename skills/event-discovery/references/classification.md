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
(strategic fit × Global-South relevance × reachability, with strategic fit weighted
equally to Global-South relevance — a strong priority-1/2 methods or industry venue can
score Medium/High on fit alone even if costly and far). Every event also gets a
recommended **action**: *attend / apply / partner / scout / watch* (`scout` = a high-fit
but costly/far event worth sending someone to for methods or partnership intel).

## Marker ribbon (fixed display order `⭐🌍🎓💻💬💰🗓️`)

Stored in the `markers` field as a string in this exact order; render as-is. Apply a
marker **only when load-bearing — absent beats wrong.**

| Marker | Apply when |
|---|---|
| ⭐ | `priority` is `High` — a top pick worth the team's active effort |
| 🌍 | the event is Global-South **by focus** — see the rule below |
| 🎓 | training / capacity-building event (`type` ∈ {Workshop, Summer school} or `theme` = Training) |
| 💻 | open-source or AI-methods focus — the event centres on code, models, or ML methods |
| 💬 | surfaced from the `#networking` Slack sweep rather than the automated web sweep (pairs with `shared_by`) |
| 💰 | the event offers a **bursary / financial aid / travel support** (from the `bursary` field) |
| 🗓️ | **any** typed deadline (abstract / early-bird / registration / bursary) falls within the report window |

**The 🌍 rule — focus, not venue.** Apply 🌍 when **any** of these holds:

1. `focus_region` is set and names an LMIC country or a Global-South region — an
   "AMR in Africa" symposium held in London (`focus_region: "Africa"`) earns 🌍;
2. no `focus_region` is set and the **`country`** is on the LMIC list; **or**
3. the event **explicitly serves or prioritises Global-South participants** —
   a regional LMIC focus, travel bursaries, scholarships, or fee waivers stated on
   the official page.

Decide LMIC status with `lmic-countries.md`, whose tagging rule this mirrors.

**Clause 3 is load-bearing — do not drop it.** Most Global-South-serving events in
this digest are *held in the North*: a TB Keystone in London with a Global Health
Award, a tropical-medicine meeting in the US with travel awards, an Asia-Pacific
conference with a fellowship programme. Several host countries (South Africa,
Malaysia, Brazil) are upper-middle-income and so are **not** on the LMIC list at
all, meaning clause 2 never fires for them. A geography-only reading of this rule
silently strips 🌍 from exactly the events the Global-South lens exists to surface —
it did, in testing, cutting the marker from 4 to 1 on a real report.

A generic European conference that merely happens to host one LMIC speaker still
does not qualify. Where `scope` and 🌍 diverge, **🌍 follows who the event serves** —
`scope` describes where it sits.

Claude sets `⭐🌍🎓💻💬`. The last two in the ribbon are script-derived:
`filter_and_sort.py` appends 💰 when the `bursary` field names real support, and 🗓️
when any `deadlines` entry lands in-window. Claude still records the raw `bursary`
and `deadlines` values — the script decides the markers.

## Worked examples

- **Deep Learning Indaba (Africa, annual)** — `scope: Global-South`, `theme: Training`,
  `format: In-person`, `type: Conference`, `priority: High`; markers `⭐🌍🎓💻`; maps to
  priorities 3 & 4; action *attend*.
- **Gordon Research Conference on Medicinal Chemistry (US)** — `scope: International`,
  `theme: Science`, `format: In-person`, `type: Conference`, `priority: Medium`; no ⭐
  unless High; maps to priority 2; action *scout* — costly and far, but a strong
  priority-2 fit, so kept and flagged as intel-worthy rather than dropped.
- **Enamine Drug Discovery Conference (Europe, industry)** — `scope: International`,
  `theme: Science`, `format: In-person`, `type: Conference`, `priority: Medium`; markers
  `💻`; maps to priority 1 (applied ML / chemical-space design); action *scout* — carried
  on strategic fit alone despite cost/distance; 🌍 reachability would only lift it to *attend*.
- **A virtual RSC cheminformatics workshop with an abstract deadline next month** —
  `scope: International`, `theme: Science`, `format: Virtual`, `type: Workshop`,
  `priority: High`; markers `⭐🎓💻🗓️`; maps to priority 1; action *apply*.
