# partner-profiling — decisions and planned improvements

Kept for the same reason event-discovery keeps one: a discovery skill without a written
record of its scope decisions grows by whichever URL arrived most recently, and the same
"should this be in?" question gets answered differently each time it is asked.

## v1 scope decisions (2026-08-20, at skill creation)

### In scope

Three classes, chosen by the user at design time:

1. **Media and science communication** — journalists, editors, desks, podcasters,
   newsletter authors, science-comms platforms.
2. **Open-source / open-science organisations** — foundations, fellows programmes,
   maintainer communities.
3. **Institutions in Barcelona, Catalonia and Spain** — plus Global-South researchers
   reached through an academic tie (citation, coauthorship, workshop alumni).

### Out, and why

- **Funders, foundations and philanthropy — OUT, to its own skill.** The user stated a
  separate funder-profiling skill is planned. The rubric genuinely differs: a funder is
  assessed on fit to a call and a deadline, not on audience reach and a story hook. Do not
  admit a foundation because it also runs a communications programme.
- **Global research institutions and networks as a family — OUT of v1.** Offered at design
  time and explicitly not selected. This is the one that will be asked about most, because
  the original request said "globally and locally" and v1's global half is media plus
  open-source only. It is a deliberate narrowing, not an oversight. Revisit as v2.
- **Global-health policy bodies — OUT of v1.** Offered and not selected.
- **Events — OUT, owned by `event-discovery`.** The relationship is one-directional in
  code and bidirectional in practice: event digests are a *source* for this skill.

### Open questions carried forward

- **"Founder" vs "funder".** The user wrote "a separate skill for founder profiling". Read
  as **funder**, and the design proceeded on that reading. If startup founders were
  actually meant, the excluded class is different and this file is wrong.
- **The Norrsken building.** `partner-sources.md` deliberately neither admits nor excludes
  co-located organisations. event-discovery excluded startup/VC *events* there; an
  organisation is a different question. First time one is judged, record the outcome here.

## Design decisions worth not re-deriving

- **Local-only output.** Chosen by the user. It is also the only option consistent with
  recording named individuals and publicly listed contacts, given that both
  `ersilia-skills` and `ersilia-os/digests` are **public** repos. Any future publishing
  step must reckon with that, not just with convenience.
- **The relevance gate replaces the priority-4 drift test.** event-discovery treats a
  priority-4-only event as a drift candidate. Partner outreach *is* priority-4 work, so
  that test would reject the whole sweep. The substitute discipline is mechanical: a row
  without a `hook` and a `next_step` is dropped by the script. See
  `references/partner-priorities.md`.
- **The ledger key carries no date.** event-discovery's key appends the event year because
  a conference has editions. A journalist does not. Do not copy that pattern here.
- **No pipe tables in either renderer.** Not a style choice — the Google Drive
  markdown-to-Doc conversion mangles them. Verified 2026-08-20. See `SKILL.md` Gotchas.

## Planned improvements

1. **Populate `references/known-partners.md`.** It ships empty because `config/CLAUDE.md`
   forbids inventing partner names. Until it is filled, every sweep will re-propose
   organisations Ersilia already works with. **This is the first thing to do before a real
   run**, and the highest-value single edit in the skill.
2. **Airtable as the source of truth for known partners.** The *Ersilia Content* base is
   the real registry. Its connector was unauthorised at build time, so nothing was tested
   against it. Needs authorisation in the claude.ai connector settings first.
3. **Google Drive delivery.** Verified technically possible and format-compatible; blocked
   only on the local-only decision above. Would need `--markers text` and a
   restricted-access target folder.
4. **Automate mining the event digests.** `partner-sources.md` names
   `../event-discovery/reports/` as a source but reading it is manual. Organiser and
   speaker extraction would be near-free recall.
5. **Mine Ersilia's own dependency graph.** Contributors to and dependents of `ersilia-os`
   repositories are the warmest possible open-source partners and no web query in the
   source map will ever find them.
6. **Recall review after the first three real sweeps.** event-discovery's recall gap was
   only diagnosed after several live runs. Expect the same here, and expect Pass B to be
   where the fix lands.

## Reframe — campaign mode (2026-08-21, one day after creation)

The skill was built as a **standing landscape tracker**: "who should Ersilia know", swept
quarterly, ranked by strategic priority. On the first review the user reframed the purpose:

> "As an example, lets say we are celebrating Ersilia anniversary and we want possible
> partners that might be interested in collaborating with us to spread the message/event,
> journalist, photographer. This skill is more towards finding this type of partnerships
> and not funding."

That is **occasion-driven amplification**, which differs from a standing sweep in three
ways that all needed code, not just prose:

1. **The useful ordering is contact-by date, not priority.** A monthly print title closes
   copy weeks ahead; a photographer books months ahead. `filter_and_sort.py --order
   deadline` was added, along with the ⏱️ marker and warnings for a `contact_by` that has
   passed or falls after the occasion.
2. **A photographer breaks the axes.** `reach` is meaningless — you buy a skill, you do not
   borrow an audience — so `REACHLESS_CLASSES` was added and the renderer omits the field.
   No existing action verb fit either, hence `commission`.
3. **The suppression logic inverts.** A sweep hides known partners and already-seen rows; a
   campaign wants them, because an existing relationship is the best amplifier. Campaign
   mode therefore uses `--keep-known` and no ledger.

Added: `campaign` mode, `render_campaign.py`, classes `Comms-team` / `Community` /
`Creative`, action `commission`, and the campaign fields `contact_by`, `lead_time_note`,
`amplification`, `portfolio_url`, `does_events`, `rate_note`.

**What survived the reframe unchanged:** the relevance gate. It was written as "a specific
audience *or capability* they give access to", and the capability half already covered a
photographer. That was luck rather than foresight, but it is the reason the reframe cost
one new mode instead of a rewrite.

### The companies question, resolved without a new class

`Company` was considered and rejected. Under an amplification lens a private company enters
only if it would spread the message, and a same-field deeptech is a field-neighbour rather
than an amplifier. **DevsHealth** (Barcelona, AI for anti-infective drug discovery) was the
concrete case that prompted this and stays out. The relevance gate settles it, so the
vocabulary does not grow. If a local company ever *would* amplify — a venue sponsor, say —
it can enter as `Community`.

### Institutions stay local

Re-confirmed 2026-08-21 when the user asked "why only barcelona?". The answer has two
halves worth keeping distinct: the first sweep was Barcelona because the *run* chose that
focus, while the `Institution` **class** is local by design. Media, open-source
organisations and Global-South researchers reached by citation are all already global, so a
global sweep needs no code change — only institutions-as-partners are scoped to
Barcelona/Catalonia/Spain.

## Bugs found by running it (2026-08-21)

1. **`load_known` parsed the reference file's prose as entries.** 26 sentence fragments
   became "organisation names". Nothing collided by luck, but a short prose bullet would
   have silently suppressed a real candidate. Entries are now restricted to bullet lines
   inside `## Entries`, and the file was restructured to match.
2. **Character-level marker dedup stripped a variation selector.** `dict.fromkeys` over a
   ribbon containing both `⏱️` and `✉️` (each ending U+FE0F) dropped the envelope's
   selector, rendering a bare `✉`. Only reachable once campaign mode existed.
3. **`MARKER_TEXT` had no entry for `⏱️`**, so `--markers text` silently dropped the
   urgency label — the one marker a Drive reader would most need.
