# Partner relevance — the screening and scoring rubric

Read before screening. A candidate stays in the sweep only if it passes the **relevance
gate** below; survivors are then scored `High` / `Medium` / `Low`.

Ersilia's four strategic priorities are in `config/CLAUDE.md`. They are quoted in full in
`../event-discovery/references/ersilia-priorities.md` — read that file for the canonical
wording rather than duplicating it here, and keep both in sync if `config/CLAUDE.md`
changes.

## Why this rubric is not event-discovery's

event-discovery treats **priority 4** (community, partnerships, sustainability) as a drift
warning: an event mapping to priority 4 *alone* needs a second independent reason, because
priority 4 read loosely absorbs anything.

**That test cannot be transplanted here.** Partner outreach *is* priority-4 work almost by
definition — applying event-discovery's rule would reject the entire sweep. So the
discipline has to come from somewhere else, and it comes from **actionability**:

> **The relevance gate.** A candidate is in scope only if you can state, in one sentence
> each, (a) a specific audience or capability they give Ersilia access to, and (b) a
> concrete next step someone could take this month. Those are the `hook` and `next_step`
> fields, and `filter_and_sort.py` **drops any row missing either**.

That is the load-bearing rule of this skill. "Plausibly aligned with our mission" is not a
reason to include an organisation — it is the description of every organisation in global
health. The gate is deliberately mechanical so it cannot be softened case-by-case: if the
hook cannot be written, the candidate is not ready, and a row that says "explore possible
synergies" is a row that should have been dropped.

**A second, softer test — reciprocity.** Ask what *they* get. An approach with nothing to
offer is a request for a favour, and it will not land. If you cannot name what Ersilia
brings to this specific partner (a story with named institutions, an open dataset, a
speaker, a case study, a workshop cohort), score it `Low` and set the action to `watch`
rather than inventing an ask.

## Scoring rubric

Assign `High` / `Medium` / `Low` by combining four signals. Do not over-think it — pick
the label the majority of signals support.

| Signal | Points toward higher priority |
|---|---|
| **Strategic fit** | Serves a named priority through a concrete mechanism (their audience *is* our target audience; their programme *is* something we can join). Vague thematic overlap → lower. |
| **Relevant reach** | A `Broad` or `Field` audience that includes the people we need to reach — researchers in the Global South, funders, the open-science community. Large but irrelevant audiences do not count. |
| **Warmth** | A named introduction or existing correspondence → higher; a genuinely cold approach to a busy stranger → lower, because the realistic probability of a reply is part of the priority. |
| **Reciprocity** | We can name a specific thing they gain → higher. Nothing to offer yet → `Low` / `watch`. |

Two standing thumbs on the scale, both from priority 4 and priority 3:

- **Barcelona / Catalonia is the ceiling of reachability.** No flight, no visa, and
  someone can attend for a single afternoon. A local institution clears the effort bar on
  that alone, so its action should be `introduce` or `invite`, not `watch`.
- **The 🌍 Global-South lens is the tie-breaker.** Between two otherwise equal candidates,
  the one that reaches or is based in the Global South ranks higher. It is a tie-breaker
  rather than a gate, because a European science desk that reaches African policy readers
  serves priority 3 better than a Global-South outlet nobody in the field reads.

### The labels

- **High** — a concrete mechanism plus relevant reach, and either a warm path or local
  reachability. Something to do this month.
- **Medium** — a real opportunity with a caveat: cold, or a narrower audience, or the
  reciprocal offer is not ready yet.
- **Low** — worth recording so the next sweep does not rediscover it, but no approach now.
  Almost always paired with the `watch` action.

State the mapped priority numbers in `priorities` and put the reasoning in `hook`.

## Ranking is not scoring

`filter_and_sort.py` orders the report by **priority, then warmth, then reach**. That
ordering is deliberate and separate from the score: among equally-scored candidates the
warm ones come first, because they are the cheapest to act on and the most likely to be
abandoned if a reader stops halfway down the page. The report's "Start here — warm paths"
section exists for the same reason.
