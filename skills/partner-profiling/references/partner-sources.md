# Partner sources — the discovery map and the partner schema

Read before the sweep. This file lists **where to look** for each of the three v1 classes,
**how to query**, and defines the **partner JSON schema** the scripts consume.

Discovery is web-only: `WebSearch` (site-scoped where a source has a stable domain) and
`WebFetch` on the organisation's own page to confirm every detail. Always end at a
**first-party** page — an outlet's own masthead or byline archive, an institution's own
staff or outreach page, a foundation's own programme page. Never a directory scrape, a
data broker, a "media contacts" aggregator or a CV mirror.

## Two passes, both required

The sweep runs **source-driven** and then **axis-driven**. Both, every time.

This is a lesson inherited from event-discovery, whose recall gap was diagnosed as
structural: a sweep that only refreshes the sources already named in its own map can
never find a source the map does not list, so its coverage silently freezes at whatever
was written down on day one. A partner map is *more* prone to this than an event map,
because outlets and programmes are far more numerous than conference series and no list
of them is ever close to complete.

### Pass A — source-driven

Walk the tables below. For each source, check what is currently there: who is on the
masthead, which programmes are open, who is on the seminar committee.

### Pass B — axis-driven (never scoped to a source named above)

Query by **attribute**, not by organisation, so a partner nobody has listed can surface.
Run at least one query on each axis:

- **By beat** — `antimicrobial resistance journalist`, `neglected tropical disease
  reporter`, `open science reporter`, `AI in global health correspondent`.
- **By geography** — `science journalist Africa health`, `periodista ciencia Barcelona`,
  `divulgació científica Catalunya`.
- **By format** — `global health newsletter author`, `drug discovery podcast host`,
  `open science seminar series Barcelona`.
- **By role** — `science editor <outlet>`, `press office <institution>`, `outreach lead`,
  `community manager open source science`.
- **By mechanism** — the highest-yield axis, because these produce *lists*:
  journalism-fellowship cohorts covering global health, open-science grantee lists
  (e.g. CZI EOSS), speaker lists from meetings, and the citing-author lists below.

**Record which pass found each partner in `source`.** If Pass B keeps producing candidates
that Pass A missed, the tables below are out of date — add the new source and note it in
`ROADMAP.md`.

## Where to look

### Media and science communication

| Source family | Examples of where to look | Query hint |
|---|---|---|
| Global-health and development desks | scidev.net, devex.com, healthpolicy-watch.news, theconversation.com (Africa edition) | `site:scidev.net antimicrobial resistance`, `<outlet> masthead health editor` |
| Science outlets with a chemistry / biomedicine beat | nature.com (Nature Africa), chemistryworld.com, cen.acs.org, undark.org, statnews.com | `<outlet> staff page`, `<outlet> author drug discovery` |
| Spanish and Catalan science media | elpais.com (Planeta Futuro), agenciasinc.es, ara.cat, lavanguardia.com | `periodista salud global`, `divulgació científica` |
| Pitch and contributor pages | The Conversation, SciDev.Net and similar publish explicit pitch guidance | `<outlet> pitch guidelines`, `<outlet> write for us` |
| Journalism fellowships and grant cohorts | Pulitzer Center grantees, European Journalism Centre, One World Media | `global health journalism fellowship <year> grantees` |
| Newsletters and podcasts | Substack and podcast directories in the global-health and drug-discovery niches | `global health newsletter antimicrobial resistance` |

**The mechanism axis matters most here.** A fellowship cohort or grantee list is a
pre-filtered set of journalists who *chose* this beat, which is a far stronger signal than
a masthead listing, and it comes with a dated piece of work you can cite in the hook.

### Open-source and open-science organisations

| Source family | Examples of where to look | Query hint |
|---|---|---|
| Open-science community organisations | we-are-ols.org (Open Life Science), numfocus.org, codeforscience.org, society-rse.org, pyopensci.org | `open science fellowship programme <year>` |
| Funder-run open-source programmes | Chan Zuckerberg Initiative EOSS, Wellcome, Sloan | `CZI EOSS grantees <year>` (a list, not a page) |
| Research-software bodies | Software Sustainability Institute, Research Software Alliance, The Turing Way | `research software community call` |
| Scientific-software publishing | Journal of Open Source Software editors and reviewers in cheminformatics | `JOSS cheminformatics reviewer` |
| Domain-adjacent open source | Open Bioinformatics Foundation, RDKit / cheminformatics community, Open Force Field | `open source cheminformatics community governance` |
| **Our own dependency graph** | Who contributes to, forks, stars or depends on `ersilia-os` repositories | `gh api` on the org's repos; check dependents of our published packages |

The dependency-graph row is the most Ersilia-specific source in this file: someone already
using the Hub is the warmest possible open-source partner, and they are invisible to every
query above.

### Institutions — Barcelona, Catalonia and Spain

| Source family | Examples of where to look | Query hint |
|---|---|---|
| Barcelona research centres | bsc.es, isglobal.org, irbbarcelona.org, irsicaixa.es, crg.eu, ibecbarcelona.eu, prbb.org | `<centre> seminar series external speaker` |
| Catalan universities | ub.edu, uab.cat, upf.edu, iqs.edu | `<university> open science office`, `<university> outreach programme` |
| Catalan public bodies and clusters | Generalitat de Catalunya, Biocat, Barcelona Science Plan | `Biocat programa`, `pla de ciència Barcelona` |
| Seminar and colloquium programmes | The concrete `invite` mechanism — most centres publish who programmes them | `<centre> colloquium organiser contact` |

**Note on the Norrsken building.** event-discovery rules general startup / VC /
impact-investing *events* out of scope, including those in Ersilia's own building. That
decision was about events. A co-located organisation is a different question, and this
skill does not auto-include or auto-exclude it: judge it on the relevance gate in
`partner-priorities.md` like anything else, and if you admit one, record why in
`ROADMAP.md` so the next sweep answers the same way.

### Global-South academic ties (within the `Institution` class)

| Source family | Where to look | Query hint |
|---|---|---|
| Who cites us | OpenAlex / Semantic Scholar citing-author lists for Ersilia publications | OpenAlex API on the Ersilia works; take citing authors and their affiliations |
| Who co-authored with us | Coauthor lists on ersilia.io/publications | — |
| Workshop alumni | Ersilia's own workshop cohorts (`ersilia-workshops`) | — |
| Speakers at events we already track | `../event-discovery/reports/` and the published digests | Read the digests; take organiser and speaker names |

The last row is free recall: the event digests already name the venues and the people who
convene them. Mining them costs one file read and needs no new search.

### Institutional comms teams (`Comms-team`)

| Source family | Where to look | Query hint |
|---|---|---|
| Press offices of institutions we already work with | The institution's own press/news page | `<institution> press office contact` |
| Catalan university news channels | The comms page of UB, UAB, UPF, UPC | `<university> sala de premsa`, `<university> news channel` |
| Research-centre comms | CERCA-centre press contacts | `<centre> premsa comunicació contacte` |

The strongest `Comms-team` rows come from institutions Ersilia **already** has a tie to —
a joint student, a shared project. A press office will carry a note about a collaborator
far more readily than about a stranger, so check the existing relationships first.

### Community amplifiers (`Community`)

| Source family | Where to look | Query hint |
|---|---|---|
| Local meetups and user groups | Meetup and community directories, university society pages | `open science meetup Barcelona`, `python barcelona grup` |
| Other non-profits and NGOs in adjacent fields | Their own sites | `associació ciència oberta Catalunya` |
| Mailing lists and newsletters with a local list | Newsletter archives | `butlletí recerca Barcelona` |

### Creatives (`Creative`)

| Source family | Where to look | Query hint |
|---|---|---|
| Event and conference photographers | Their own portfolio sites | `event photographer Barcelona conference portfolio` |
| Science photographers and videographers | Portfolio sites, science-comms directories | `science photographer Barcelona`, `videògraf esdeveniments Barcelona` |
| Illustrators and designers | Portfolio sites | `scientific illustrator Barcelona` |

**Verify a creative differently.** There is no "beat" to confirm; confirm instead that the
portfolio shows **work of the kind we need** (indoor evening events, not only weddings or
product shots), that they publish rates or a quote route, and that they are actually local
enough to attend. Record `portfolio_url`, `does_events` and `rate_note`. Their contact
route is usually a `public_form`.

**Licensing is part of the ask, not an afterthought.** Ersilia publishes openly, so a
photographer whose standard contract restricts reuse is a poor fit however good the
portfolio. Put the licence question in `next_step`.

## Links must point at the current edition

**A recurring series has two kinds of page, and only one is safe to cite.**

- A **generic landing page** — `canodrom.barcelona/en/opentechweek` — renders whichever
  edition the site currently shows. Today that may be last year's; next month it may be
  this year's. It is not a stable citation.
- A **year-specific page** — a dated news item, `…-open-tech-week-2026-1614276` — never
  moves.

**Always cite the year-specific page as the row's `url`.** A generic page produces a link
the reader clicks and lands on *last year's event*, which is worse than no link at all
because it looks checked. This was flagged by a reader of a real report, which is exactly
the wrong way to find it.

When only a generic page exists, record **`edition_year`** — the edition the page actually
documented when you read it. `filter_and_sort.py` compares both the years embedded in
`url`/`org_url` and `edition_year` against the target year (the occasion's year in campaign
mode, else the run year) and, on a mismatch, warns *and forces* `verified: false`. That is
not a punishment: a row citing last year's edition genuinely is not verified for this one,
and the `†` flag routes it to the review gate where someone has to decide.

Two deliberate non-flags:

- **A later year is fine.** Linking next year's edition is forward planning, not staleness.
- **`recent_work` is never checked.** Old items there are the *evidence* — a 2019 byline is
  the point, not a defect. Only the primary link a reader clicks is judged.

**State what is still unconfirmed.** For the 2026 Open Tech Week the year-specific page
confirmed the edition and MozFest's dates but *not* the full week's dates — so the row says
so, rather than repeating a date range that only press coverage carried.

## The partner JSON schema

Produce a JSON **array** of objects with these fields, and pass it to
`scripts/filter_and_sort.py`.

### Required — a row missing any of these is dropped

| Field | Type | Notes |
|---|---|---|
| `name` | string | Display name. For a person, `"Person — Organisation"`; for an organisation, its name. |
| `class` | string | `Media` · `Open-source` · `Institution` · `Comms-team` · `Community` · `Creative` — the full list lives in `classification.md` |
| `url` | string | The first-party page that backs this row. |
| `source` | string | Where you found it, and which pass (`"Pass B — beat query"`). |
| `hook` | string | The specific audience or capability they give access to, citing their recent work. |
| `next_step` | string | A concrete action someone could take this month. |

### Classification — validated against `classification.md`

`scope` · `reach` · `warmth` · `priority` · `action`. An out-of-vocabulary value **drops
the row**, so use the exact strings.

### Optional but strongly wanted

| Field | Type | Notes |
|---|---|---|
| `person` | string | Named individual, if the row is about a person. |
| `role` | string | Their role or title. |
| `org` / `org_url` | string | Organisation and its home page. `org_url` is the dedup key — set it. |
| `priorities` | array of int | Which of the four strategic priorities this serves. |
| `recent_work` | array | `{"title", "url", "date", "note"}`. The evidence behind the hook. |
| `warm_paths` | array of string | Required in practice whenever `warmth` is above `Cold`. |
| `contacts` | array | `{"kind", "value"}` — **`kind` must be from the vocabulary in `data-handling.md`**; anything else is stripped. |
| `cost` | string | What engaging them costs: `"Free — editorial"`, `"€800–1,500 full day"`, `"Quote on request"`. Free text, any class. **Omit it when nobody has established a price** — an absent cost renders as "not established" and is listed as a budget risk, whereas guessing "Free" hides one. |
| `edition_year` | int | For a recurring series: the edition the cited page actually documents. Checked against the target year; a mismatch forces `verified: false`. See "Links must point at the current edition". |
| `verified` | bool | `false` if no live page confirmed the details. Renders with `†`. |

### Campaign-mode fields

Required in practice for `campaign` mode — a row without `contact_by` cannot be scheduled
and renders in a trailing bucket.

| Field | Type | Notes |
|---|---|---|
| `contact_by` | string | ISO date by which they must be contacted for the occasion to be helped. **This is the field campaign mode sorts on.** |
| `lead_time_note` | string | Why that date — the publication cycle, the booking window. Makes the date auditable instead of asserted. |
| `amplification` | string | What we are hoping they actually do: a news item, a listing in a mail-out, event photography. |
| `portfolio_url` | string | `Creative` only. |
| `does_events` | bool | `Creative` only — does the portfolio show event work. |
| `rate_note` | string | **Legacy alias for `cost`**, accepted for older pools. Prefer `cost`, which applies to every class. |

**Deriving `contact_by` is a judgement, so record the reasoning.** A monthly print title
closes copy weeks ahead; a daily wants days; a photographer books out months. The script
warns when a `contact_by` has already passed, or falls *after* the occasion date — the
second is the easy mistake, and it makes the row useless while looking complete.

### Dossier-only fields

`background` · `remit` · `audience` · `pitch` · `ask` · `risks` · `sources`. Read by
`render_dossier.py`; `background`, `pitch` and `ask` carry the document, and the script
warns when any is empty. A dossier target does **not** need the six required fields above —
it is rendered directly, and `render_dossier.py` applies the contact policy itself.

### A worked row

```json
{
  "name": "A. Example — Example Global Health",
  "person": "A. Example",
  "role": "Health and science correspondent",
  "org": "Example Global Health",
  "org_url": "https://example.test/global-health",
  "url": "https://example.test/authors/a-example",
  "class": "Media", "scope": "International", "reach": "Broad",
  "warmth": "Warm intro", "priority": "High", "action": "pitch",
  "priorities": [1, 3],
  "hook": "Ran a three-part series on AMR surveillance gaps in West Africa; part two named the absence of open tooling and identified nobody filling it.",
  "next_step": "Ask B. Colleague for the introduction, then pitch the Hub's AMR models as the follow-up.",
  "recent_work": [{"title": "Who counts the resistant infections?", "url": "https://example.test/2026/amr", "date": "2026-03-11"}],
  "warm_paths": ["B. Colleague shares a source with them at a Lagos lab"],
  "contacts": [{"kind": "outlet_pitch", "value": "globalhealth@example.test"}],
  "source": "Pass A — outlet masthead, confirmed on byline page",
  "verified": true
}
```
