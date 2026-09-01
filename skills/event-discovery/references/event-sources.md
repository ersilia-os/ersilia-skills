# Event sources — the discovery map + event schema

Read before Step 2. This file lists **where to look** for each in-scope event type and
**how to query**, then defines the **event JSON schema** that Step 5 must produce and the
scripts consume.

Discovery is web-only: use `WebSearch` (site-scoped where a source has a stable domain)
and `WebFetch` on the event's own page to confirm dates and location. Always end at an
**official** event page — never a ticket reseller or an aggregator's stale mirror.

## In-scope event types (v1)

Scientific conferences & symposia · workshops & training / capacity-building ·
hackathons, datathons & fellowships · philanthropy / funder forums (donor and
foundation gatherings — the `Philanthropy` theme).
**Out of scope in v1:** pure funding *calls* / grant deadlines (handled elsewhere) —
a funder's annual *forum or meeting* is an in-scope event; an open call for grant
applications is not.

## Where to look

### Scientific conferences & symposia
| Source | Home | Query hint |
|---|---|---|
| Gordon Research Conferences | grc.org | `site:grc.org medicinal chemistry OR chemical biology OR drug discovery <year>` |
| ISMB / ECCB (comp. bio) | iscb.org | `ISMB ECCB <year> dates registration` |
| NeurIPS / ICML / ICLR (ML4Science, AI4Science tracks) | neurips.cc, icml.cc, iclr.cc | `NeurIPS <year> AI for science workshop drug discovery` |
| ASTMH (tropical medicine) | astmh.org | `ASTMH annual meeting <year>` |
| ACS / EFMC / RSC med-chem & cheminformatics | acs.org, efmc.info, rsc.org | `EFMC ISMC <year>`, `RSC cheminformatics <year>` |
| Dedicated cheminformatics / QSAR meetings | gdch.de (GCC), euroqsar.org, iccs-nl.org (ICCS), acscinf.org (ACS CINF), rsc.org (RSC-CICAG), qsar.org | `German Conference on Cheminformatics <year>`, `EuroQSAR <year>`, `ICCS chemical structures <year>`, `ACS CINF <year>` |
| Keystone Symposia | keystonesymposia.org | `Keystone Symposia infectious disease <year>` |
| ELRIG (drug discovery) | elrig.org | `ELRIG Drug Discovery <year>` |
| NTD / AMR bodies | dndi.org, mmv.org, who.int/tdr, gardp.org | `DNDi OR MMV OR GARDP conference OR symposium <year>` |

### Applied / industry ML drug discovery
These are method-heavy, often vendor- or CRO-hosted meetings where applied AI-for-drug-discovery
tooling, chemical-space design, and industry partnerships live. They are usually `International`,
in-person and costly — but a strong fit to priority 1/2 earns them a place on strategic fit alone
(action `scout` / `watch`; see `ersilia-priorities.md`). Don't let cost/distance alone drop them.
| Source | Home | Query hint |
|---|---|---|
| Enamine Drug Discovery Conference | enamine.net | `Enamine Drug Discovery Conference <year> dates` |
| CHI Drug Discovery Chemistry / Discovery on Target | drugdiscoverychemistry.com, discoveryontarget.com | `Drug Discovery Chemistry <year> San Diego`, `Discovery on Target <year> Boston` |
| AI in Drug Discovery summits | oxfordglobal.com, hansonwade.com | `AI in Drug Discovery summit <year> dates`, `AI-driven drug discovery conference <year>` |
| RSC "AI in Chemistry" (CICAG) | rsc.org | `RSC Artificial Intelligence in Chemistry <year>` |
| ML-for-molecules workshops (LMRL, MoML, M2D2, AI4Science) | — | `Learning Meaningful Representations of Life <year>`, `Molecular ML MoML <year>`, `Molecular Machine Learning M2D2 <year>`, `AI for Science workshop <year>` |
| ELLIS ML programmes / workshops | ellis.eu | `ELLIS machine learning molecules OR chemistry workshop <year>` |
| SLAS / Bio-IT World / BioTechX (screening & informatics) | slas.org, bio-itworldexpo.com, biotechx.com | `SLAS <year> dates`, `Bio-IT World <year>`, `BioTechX <year>` |

### Workshops & training / capacity-building
| Source | Home | Query hint |
|---|---|---|
| EMBL-EBI training | ebi.ac.uk/training | `EMBL-EBI course cheminformatics OR machine learning <year>` |
| Wellcome Connecting Science | wellcomeconnectingscience.org | `Wellcome Connecting Science course <year> Africa` |
| H3D / H3ABioNet | h3d.uct.ac.za, h3abionet.org | `H3D symposium OR training <year>` |
| ICTP (Trieste) | ictp.it | `ICTP school quantitative biology OR machine learning <year>` |
| Deep Learning Indaba | deeplearningindaba.com | `Deep Learning Indaba <year>` |
| Data Science Africa | datascienceafrica.org | `Data Science Africa summer school <year>` |
| AIMS network | nexteinstein.org | `AIMS AI OR data science school <year>` |

### Hackathons, datathons & fellowships
| Source | Home | Query hint |
|---|---|---|
| Open-source / global-health hackathons | — | `global health OR drug discovery hackathon OR datathon <year>` |
| Fellowships & awards | — | `AI for science fellowship <year> deadline`, `EMBO OR Schmidt OR foundation fellowship global health <year>` |

### Philanthropy & funder forums (the `Philanthropy` theme)
| Source | Home | Query hint |
|---|---|---|
| Gates Foundation Grand Challenges | grandchallenges.org | `Grand Challenges Annual Meeting <year> dates` |
| Skoll World Forum | skoll.org | `Skoll World Forum <year> dates Oxford` |
| World Health Summit | worldhealthsummit.org | `World Health Summit <year> Berlin dates` |
| Wellcome / global-health funders | wellcome.org | `Wellcome global health meeting OR forum <year>` |

These are funder/foundation **gatherings** (in scope), not grant *calls* (out of scope).

### Global-South regional — Asia & Latin America (don't let the sweep skew to EU/US/Africa)
| Source | Home | Query hint |
|---|---|---|
| InCoB / ISCB-APAC (Asia-Pacific comp bio) | incob.apbionet.org | `InCoB ISCB-APAC <year> dates` |
| India drug discovery / cheminformatics | csir.res.in, instem.res.in, bioclues.org | `India drug discovery OR cheminformatics conference <year>` |
| X-Meeting / AB3C (Brazil bioinformatics) | x-meeting.com | `X-meeting AB3C <year> Brazil dates` |
| LASBio / Latin-American med-chem | — | `Latin American Symposium Medicinal Chemistry <year>` |
| WorldLeish / LeishSymposium (Leishmania, T. cruzi) | leishsymposium.org | `WorldLeish <year> dates`, `Chagas OR leishmaniasis congress <year>` |
| DNDi / regional NTD bodies | dndi.org/events | `DNDi Latin America OR Asia meeting <year>` |

Latin-American and South/SE-Asian events are often less web-visible and announced in
Portuguese/Spanish; if a sweep returns nothing there, **say so** rather than implying the
region is empty — the absence is usually a search gap, not a real one.

### Virtual / online (no physical location — collected in the report's Virtual section)
| Source | Home | Query hint |
|---|---|---|
| EMBL-EBI live virtual courses | ebi.ac.uk/training | `EMBL-EBI virtual course machine learning OR cheminformatics OR structural <year>` |
| GARDP / BSAC Antimicrobial Chemotherapy Conf. | acc-conference.com | `Antimicrobial Chemotherapy Conference online <year>` |
| LeishSymposium (virtual, Leishmania/T. cruzi) | leishsymposium.org | `LeishSymposium <year> virtual dates` |
| ML-for-chemistry seminar series | — | `virtual OR online symposium AI machine learning chemistry OR drug discovery <year> dates` |

Add sources as the team learns them — keep entries factual (home URL + how to query),
never invent an event from a source name.

## Query discipline

- Run **≥4 query variants per in-scope type** (source-scoped + a couple of open web
  searches for the current `focus`).
- Anchor every query to the date window (`<year>` and, where useful, the next year too,
  since events 6–9 months out are often announced under the following year).
- `WebFetch` the official page to confirm **name, exact dates, location, URL** before
  keeping an event. If the page does not confirm a date, drop it — do not guess.
- Target a raw pool of **30–60 candidates** before screening.

## Event JSON schema (Step 5 writes this; the scripts read it)

Write the classified pool to `/tmp/events_pool.json` as a JSON array of objects. Fields:

| Field | Type | Notes |
|---|---|---|
| `name` | string | **required** — official event name |
| `start_date` | string | **required** — ISO `YYYY-MM-DD` (first day). **Waived only when `shared_by` is set:** a colleague may share a real event whose page has not announced dates yet. Set it to `null` in that case — never guess — and the event renders under "Shared by the team — dates not yet announced" instead of being dropped. A machine-discovered event with no date is still dropped. |
| `end_date` | string \| null | ISO `YYYY-MM-DD`; null for single-day events |
| `location` | string | **required** — "City, Country" or "Virtual" |
| `country` | string \| null | country name; drives which **continent section** the event is filed under — i.e. where you would physically travel |
| `focus_region` | string \| null | **optional** — the region the event is *about*, when it differs from `country`. A country (`"Kenya"`) or a continent (`"Africa"`). An "AMR in Africa" symposium held in London gets `"Africa"`. Drives the 🌍 decision and the "Coverage by region focus" footer; falls back to `country` when omitted. Never causes an event to appear twice — sections stay location-based. |
| `url` | string | **required** — official event page |
| `source` | string | **required** — which source it came from (e.g. "GRC", "Indaba") |
| `cost` | string | attendance cost as stated on the official page — `Free`, a figure with currency (e.g. `~€450`, `$150 student / $350 industry`), or `Unknown` if the page gives none. Never invent a number. |
| `bursary` | string | financial-aid / travel-support offered, as stated on the official page — a short description (e.g. `Bursaries up to £700 (PhD/postdoc)`, `Fee waivers & fellowships`), `None` if the page says there is none, or `Unknown`. The script adds the 💰 marker when this names real support. Don't invent — quote or paraphrase the page. |
| `format` | string | one of `In-person` / `Virtual` / `Hybrid` (see classification.md) |
| `type` | string | one of the Type values in classification.md |
| `theme` | string | one of `Science` / `Philanthropy` / `Community` / `Training` |
| `scope` | string | one of `Local` / `Regional` / `Global-South` / `International` |
| `priority` | string | `High` / `Medium` / `Low` |
| `markers` | string | emoji ribbon you set in fixed order `⭐🌍🎓💻💬`; the script appends 💰 (from `bursary`) and 🗓️ (from `deadlines`). 🌍 follows `focus_region` when set, else `country`. |
| `shared_by` | string \| null | **optional** — for candidates from the Slack sweep (Step 2a), the name of the teammate who posted it. Renders as a `💬 Shared by the team` footnote, not a table column, and pairs with the 💬 marker. |
| `deadlines` | object | typed deadlines, each an ISO `YYYY-MM-DD` string (omit or `null` if unknown). Recognised keys: `abstract` (call for papers / posters), `early_bird` (early-bird registration), `registration` (standard/final registration or an application/interest deadline), `bursary` (financial-aid / scholarship application). Record every date the page states — **including past ones**; the script decides which land in-window (adds 🗓️), and a **past `registration` date on a still-upcoming event** moves it to the report's "registration closed" section. Use `registration` as the catch-all when the type is unclear. |
| `priorities` | array[int] | which Ersilia strategic priorities (1–4) it maps to |
| `action` | string | `attend` / `apply` / `partner` / `scout` / `watch` (`scout` = a high-fit event worth sending someone to for methods/partner intel even though it's far/costly) |
| `engagement` | string | the participation angle — a short phrase (≤6 words) for *what to do there* and, if clear, *who should go*: e.g. `Present Model Hub work`, `Recruit trainees; send a student`, `Meet African partners`, `Scout AI4Science talks`. `—` if there's no distinct angle beyond attending. |
| `why_ersilia` | string | one line: why it matters (name the priority + action) |
| `verified` | bool | `true` when you confirmed name/dates/URL on the **official page** via `WebFetch`; `false` for a strong candidate you could not page-verify (e.g. the site failed to load) but whose details agree across independent reputable sources. Defaults to `true` if omitted. Unverified events are kept but flagged with `†` in the report. **Team-shared candidates (`shared_by` set) are kept at `false` even with no corroborating sources** — a colleague vouched for it, so it is flagged for the reader rather than dropped. |

Example object:

```json
{
  "name": "Deep Learning Indaba 2026",
  "start_date": "2026-08-23",
  "end_date": "2026-08-29",
  "location": "Kigali, Rwanda",
  "country": "Rwanda",
  "url": "https://deeplearningindaba.com/2026/",
  "source": "Deep Learning Indaba",
  "cost": "$150 student / $200 faculty / $350 industry (financial aid = free)",
  "bursary": "Financial aid route = free registration",
  "format": "In-person",
  "type": "Conference",
  "theme": "Training",
  "scope": "Global-South",
  "priority": "High",
  "markers": "⭐🌍🎓💻",
  "deadlines": { "abstract": "2026-05-15", "registration": "2026-07-31", "bursary": "2026-04-30" },
  "priorities": [3, 4],
  "action": "attend",
  "engagement": "Recruit trainees; send a student",
  "why_ersilia": "Priority 3/4: pan-African ML community — attend to recruit trainees and partners.",
  "verified": true
}
```

Here the `abstract` and `bursary` dates fall before a mid-2026 window and earn no 🗓️,
while `registration` (2026-07-31) would. Record every real date regardless of type —
`filter_and_sort.py` decides which land in-window, adds 🗓️ if any do, and lists each
in-window deadline (with its type) in the report's Deadlines section.
