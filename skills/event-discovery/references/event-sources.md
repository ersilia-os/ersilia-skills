# Event sources — the discovery map + event schema

Read before Step 2. This file lists **where to look** for each in-scope event type and
**how to query**, then defines the **event JSON schema** that Step 5 must produce and the
scripts consume.

Discovery is web-only: use `WebSearch` (site-scoped where a source has a stable domain)
and `WebFetch` on the event's own page to confirm dates and location. Always end at an
**official** event page — never a ticket reseller or an aggregator's stale mirror.

## In-scope event types (v1)

Scientific conferences & symposia · workshops & training / capacity-building ·
hackathons, datathons, challenges & fellowships · philanthropy / funder forums (donor and
foundation gatherings — the `Philanthropy` theme) · open-source / open-science community
gatherings (the `Community` theme).
**Out of scope in v1:** pure funding *calls* / grant deadlines (handled elsewhere) —
a funder's annual *forum or meeting* is an in-scope event; an open call for grant
applications is not.

**The test is participation** — a convening you attend on dates, or a cohort-based
fellowship, school or challenge you apply to. Not a paper, blog post, tool release,
job ad, organisation homepage or funding call. See
SKILL.md Step 3 for the full test and for how an organisation page is handled as a
*lead* rather than a candidate. This is load-bearing for the Slack sweep: `#general`
absorbed `#funding-opportunities` and `#media`, so grant calls and outreach articles
now arrive on the same feed as events.

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
| EMBO workshops & courses | meetings.embo.org | `EMBO workshop tuberculosis OR mycobacteria OR infection <year>`, `EMBO course drug discovery <year>` |
| AI4Sci / AI for Science Week | ai4sci.eu, ai4sciweek.org, discovery-science.org | `AI for Science conference <year> dates`, `AI4Sci <year>` |

### Global-health R&D partnerships & public funders

**The family that produced the sweep's worst documented miss.** The 2026-08-04 report
missed the EDCTP Forum 2027 (Madrid, 5–9 April 2027, abstract deadline 2 Sep 2026 with
travel/visa scholarships) because no row here covered EU public global-health R&D
partnerships. These are **scientific congresses** convened by funders — theme `Science`,
not `Philanthropy`, which is for donor/foundation gatherings.
| Source | Home | Query hint |
|---|---|---|
| Global Health EDCTP3 / EDCTP Forum | global-health-edctp3.europa.eu, edctpforum.eu | `EDCTP Forum <year> dates abstract deadline`, `Global Health EDCTP3 event <year>` |
| FESTMIH / ECTMIH (European tropical medicine congress) | festmih.eu, ectmih2027.eu | `ECTMIH <year> dates abstract`, `European Congress Tropical Medicine International Health <year>` |
| ISGlobal (Barcelona; ECTMIH 2027 organiser) | isglobal.org | `ISGlobal course OR symposium OR congress <year>` |
| RSTMH (Royal Society of Tropical Medicine & Hygiene) | rstmh.org | `RSTMH meeting OR call for papers <year>` |

### Priority-pathogen circuits

**Search by pathogen, not only by known venue.** `ersilia-priorities.md` lists the
priority organisms, but they were previously used only to *screen* at Step 4 and never
to *search* at Step 2 — so a pathogen's own congress circuit went unqueried. Run at
least one query per row (see Query discipline below).
| Pathogen | Home | Query hint |
|---|---|---|
| *M. tuberculosis* / *M. abscessus* | theunion.org, tbvaccinesforum.org, tbvi.eu, newtbvaccines.org, meetings.embo.org | `Union World Conference on Lung Health <year>`, `Global Forum on TB Vaccines <year>`, `tuberculosis conference OR congress <year>` |
| *P. falciparum* / *P. vivax* | mmv.org, who.int/teams/global-malaria-programme | `MIM Pan-African Malaria Conference <year>`, `malaria conference OR congress <year>` |
| *Leishmania* / *T. cruzi* / *T. brucei* | leishsymposium.org, worldleish8.org, dndi.org | `WorldLeish <year>`, `Chagas OR leishmaniasis congress <year>` |
| *S. mansoni* / schistosomiasis | — | `schistosomiasis conference OR symposium <year>`, `helminth OR NTD congress <year>` |
| AMR — ESKAPE / WHO GLASS | escmid.org, bsac.org.uk, gardp.org, acc-conference.com | `ESCMID Global <year> dates`, `antimicrobial resistance conference <year>`, `Antimicrobial Chemotherapy Conference <year>` |

### Spain — Barcelona, Catalonia & national

**Priority 4 names "presence in Barcelona, Catalonia and Europe", and the sweep had no
way to act on it.** Geography was tracked only at continent granularity, so "Europe:
swept" hid the fact that nothing ever queried Ersilia's own city. The evidence is
uncomfortable: all three congresses the 2026-08-04 report missed were **in Spain**, and
the backfill then turned up MozFest 2026 in Barcelona and the MAINFRAME symposium at the
Ateneu Barcelonès — 180+ researchers on AI-driven small-molecule discovery, a 20-minute
walk from the office, found only because a colleague posted it.

A local event is also the cheapest possible attendance: no flights, no visa, no
accommodation. A Barcelona event at `Medium` fit beats a San Diego event at `High`.
| Source | Home | Query hint |
|---|---|---|
| Biocat / BioRegion of Catalonia agenda | biocat.cat/en/news/agenda | `Biocat agenda <year>`, `BioRegion Catalonia life sciences event <year>` |
| SEQT (Spanish medicinal chemistry society) | seqt.org/en/events/meetings, seqt.org/es/eventos/congresos | `SEQT congreso <year>`, `Sociedad Española de Química Terapéutica congreso <year>` |
| ISCIII / Fundación CSAI (EDCTP Forum 2027 host) | isciii.es | `ISCIII jornada OR congreso OR curso <year>` |
| Barcelona research institutes | irbbarcelona.org, prbb.org, irsicaixa.es, bsc.es | `IRB Barcelona OR PRBB OR BSC symposium OR jornada <year>` |
| SDDN — Spanish drug discovery network | sddn.es | `SDDN reunión OR jornada <year>`, `Spanish drug discovery network meeting <year>` |
| BIOSPAIN (Spanish biotech convention) | — | `BIOSPAIN <year> dates` |
| **Norrsken House Barcelona — our own building** | norrsken.org | `Norrsken House Barcelona event <year>`, `Norrsken Impact Week <year>` |

**Check Norrsken every run — but proximity is a reason to *look*, never a reason to
*include*.** Ersilia's headquarters is Norrsken House Barcelona (per the team's own
announcement in Slack), so its programme is worth sweeping every time: an event in the
building we work in costs a lift, not a flight. Norrsken's own programme, however, is
startup/impact-investing rather than science — Impact/Week 2026 (14–15 Oct 2026, in our
venue) is themed on climate, energy and geopolitics for founders and investors.

**So every Norrsken event still has to pass the mission lens in SKILL.md's "Not in scope"
section**, and priority-4-only events need the second reason set out in
`ersilia-priorities.md`. A venue we occupy generates a high volume of near-misses; treat
the row as a funnel, not a whitelist. The same holds for any other
community/venue source added here later.

Note the query shape: Norrsken's events are English-named impact/startup convenings
(`Impact/Week`), so the Spanish- and Catalan-language terms above will **not** find them
and neither will `simposio`/`jornada`. Query the venue by name.

**Biocat's agenda is a discovery source, not a citation.** It curates Catalan, Spanish and
international life-science events and negotiates discounts for BioRegion organisations —
so it is an excellent place to *find* an event, but always follow through to the event's
own official page before recording a `url`, per the no-aggregators rule at the top of
this file.

**Query in Spanish and Catalan, not only English.** This is not optional politeness —
it is the difference between finding an event and not. The archived `#networking` channel
held `platformdali.org/es/encuentros`, which an English-only sweep cannot reach. Useful
terms: Spanish `congreso`, `jornada`, `simposio`, `curso`, `encuentro`, `reunión`,
`convocatoria`; Catalan `congrés`, `jornada`, `simposi`, `curs`, `trobada`. The existing
Spanish/Portuguese instruction in SKILL.md Step 2 applied only to Latin America — Spain
itself was never covered by it.

### Open-source / open-science community (the `Community` theme)

`classification.md` has a `Community` theme but this file had no sources for it, so
priority-4 venues depended entirely on a teammate posting them.
| Source | Home | Query hint |
|---|---|---|
| Mozilla Festival (MozFest) | mozillafestival.org | `MozFest <year> dates location`, `Mozilla Festival <year> call for proposals` |
| BOSC / Open Bioinformatics Foundation | open-bio.org | `BOSC <year> dates`, `Bioinformatics Open Source Conference <year>` |
| Conscience (open-science drug discovery; runs MAINFRAME) | conscience.ca | `MAINFRAME symposium <year>`, `Conscience symposium <year> dates` |
| ChEMBL / EMBL-EBI user-group meetings | ebi.ac.uk, chembl.blogspot.com | `ChEMBL User Group Meeting <year>` |

### News & announcement feeds (where events surface *first*)

**Every other source in this file is an event or organiser page — which is where an
event lands last, not first.** A congress is announced in a funder's news post 6–18
months before its microsite exists or ranks. The EDCTP Forum 2027 was announced on
**2 March 2026**; the 2026-08-04 sweep, five months later, still missed it, because
nothing here pointed at a news feed. Sweep these for *announcements*, then follow them
to whatever page exists — see SKILL.md Step 3 for how to verify an event that has an
announcement but no site yet.
| Source | Home | Query hint |
|---|---|---|
| Global Health EDCTP3 news | global-health-edctp3.europa.eu/news-and-events | `EDCTP3 news event OR forum OR congress <year>` |
| DNDi news (distinct from `dndi.org/events`) | dndi.org/news | `DNDi news symposium OR meeting OR conference <year>` |
| WHO/TDR news | who.int/tdr/news | `TDR news meeting OR training <year>` |
| GARDP news | gardp.org/news | `GARDP news conference OR webinar <year>` |
| Wellcome news & reports | wellcome.org/news | `Wellcome news meeting OR summit <year>` |
| ISGlobal news (Barcelona) | isglobal.org/en/news | `ISGlobal news congress OR course <year>` |
| FESTMIH events & announcements | festmih.eu/events | `FESTMIH ECTMIH announcement <year>` |

Query these with **announcement verbs**, not venue names — `announced`, `will host`,
`save the date`, `call for abstracts` — since the event's own name is exactly what you
do not yet know.

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
| BioStruct-Africa (structure-based design training, Africa) | biostructafrica.org | `BioStruct-Africa workshop <year>`, `structural biology training Africa <year>` |

BioStruct-Africa is worth querying every run: it covers participants' travel,
accommodation, registration **and visa** fees, which is rare enough to be 💰 on its own
and squarely priority 3.

### Hackathons, datathons & fellowships
| Source | Home | Query hint |
|---|---|---|
| Open-source / global-health hackathons | — | `global health OR drug discovery hackathon OR datathon <year>` |
| Fellowships & awards | — | `AI for science fellowship <year> deadline`, `EMBO OR Schmidt OR foundation fellowship global health <year>` |
| Prediction / benchmark challenges | — | `blind challenge ADMET OR bioactivity prediction <year>`, `OpenADMET challenge <year>` |

A **challenge** is in scope under the participation test — a cohort applies and takes
part on a deadline — even though nobody travels to it.

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
- Run **≥1 query per row in "Priority-pathogen circuits"** — all five, every run, even
  when the `focus` is a method rather than a disease. This is a floor, not a suggestion:
  the pathogens are the mission, and querying them only via named venues is what left
  the 2026-08-04 report with a single TB event and no AMR-specific venue at all.
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
| `priorities` | array[int] | which Ersilia strategic priorities (1–4) it maps to. **May be empty** for a human-sourced event: `shared_by` events skip the Step 4 relevance screen, so there may be no priority to record. Not validated. |
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
