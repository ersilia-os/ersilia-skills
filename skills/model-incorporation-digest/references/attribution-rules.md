# Attribution rules — why the authors come before us

An incorporation has two subjects: a piece of science somebody else did, and a packaging
job we did. The second is smaller. A digest that inverts them costs Ersilia the thing it
most needs from researchers — the confidence that publishing openly leads to their work
being credited, not absorbed.

The digest is internal, which lowers the stakes but not the standard. It is the document
the team reasons from, and a paragraph that reads as though Ersilia built the model is how
that mistake enters everything written later.

## The credit hierarchy

Each model's paragraph is about the model and the people who made it. Ersilia appears only
where its own work is the fact being reported — that it packaged the model, and anything
it changed.

1. **Who made it.** The byline names the authors and their institutions, in the paper's
   order.
2. **What it does and what it was trained on.**
3. **What the authors showed** — a validation, a benchmark, a limitation they stated.
4. **What Ersilia did**, only where it is not simply packaging: a re-training, a slice, a
   defaulted parameter.

If a reader skims the digest and comes away thinking Ersilia built ten models last month,
it failed regardless of what it technically said.

## Verb discipline

Verbs assign credit more strongly than any adjective. Keep the two vocabularies apart.

| The authors | Ersilia |
|---|---|
| developed, trained, designed, built | packaged, wrapped, made available |
| screened, validated, showed, found | added to the Hub, standardised, integrated |
| published, released | ported, hosted, serve, distribute |

Banned outright — every one of these has appeared in a real draft somewhere:

> we built · we developed · we trained · we created · we present · we introduce ·
> introducing our · our new model · our latest model · proud to present our

"Our" is only correct about things that are genuinely ours: our Hub, our packaging.
Never "our model".

## Honesty rules

These are not mechanically checkable, so they are on you.

- **Attribute every figure to its source.** A number is the paper's claim unless
  `/model-incorporation-reproduce` returned **PASS**, in which case it is also ours. Say
  which. Never let the digest imply a reproduction we did not achieve.
- **Do not imply a collaboration that does not exist.** Packaging a public model is not a
  partnership.
- **Do not imply clinical validity.** These are early-discovery models.
- **The digest carries no licence.** It was on every row, which buried the one that
  mattered, and every row links to the model, whose own page states its terms. The cost is
  real: a copyleft or non-commercial licence now has no signal in the digest. So when a
  month contains one, **say so when you present** — that is the moment somebody can decide
  whether it belongs back on the page.
- **Say what we changed — and only if we changed something.** If Ersilia re-trained,
  sliced, or defaulted a parameter, one clause says so. Silent modification presented as
  the authors' model is the worst outcome available. When nothing changed, say nothing.
- **State a limitation once, in the model's own paragraph.** An applicability domain or a
  narrow training set is a fact the team needs. Repeating it as a disclaimer elsewhere is
  hedging.

## No internal credit

The digest does not name the Ersilia contributor who did the incorporation. `Contributor`
is in the metadata and is deliberately unused. Internal credit is real and belongs
somewhere, but not in the document that records whose science this was.

## Edge cases the metadata decides

Read `Source Type` before writing anything.

- **`External`** (the large majority) — everything above applies as written.
- **`Replicated`** — Ersilia re-trained a model following someone else's published method.
  Credit the *method's* authors exactly as usual, then state plainly that this is Ersilia's
  re-implementation and not the authors' own weights. Readers must not think they are
  running the published model.
- **`Internal`** — the model is Ersilia's. Credit whoever produced the **training data**,
  which is usually somebody else's paper or a public database, and say plainly that Ersilia
  trained the model. The self-reference rules relax; the honesty rules do not.
- **No DOI in `Publication`** — the author list cannot be resolved automatically. Ask the
  user for it rather than proceeding, and state the gap in the model's paragraph rather
  than letting an unresolved list read as an absent one.
- **Preprint since published** — cite the published version. `/model-incorporation-metadata`
  should already have caught this; if `Publication Type` still says `Preprint` and Crossref
  shows a journal version, fix the metadata rather than papering over it in the post.
