# Attribution rules — why the authors come before us

An incorporation announcement has two subjects: a piece of science somebody else did, and
a packaging job we did. The second is smaller. A post that inverts them costs Ersilia the
thing it most needs from researchers — the confidence that publishing openly leads to
their work being credited, not absorbed.

So the ordering is not politeness. It is the *claim* the post makes, and it is checkable.
`scripts/check_post.py` enforces the four rules below that can be decided from the text.

## The credit hierarchy

The round-up opens as an announcement — Ersilia says how many models went into the Hub —
and then hands the rest over. The announcement is the frame; the month's authors are the
content.

1. **The announcement.** A title with the month and the count, and one sentence saying
   what was incorporated. Two short blocks: that is all the room Ersilia gets.
2. **The authors.** One line per model, each naming its own first author and institution.
3. **What each model does.** One clause per model, and its paper link.
4. **What they enable.** One sentence, plus where the catalogue lives.

If a reader skims and comes away thinking Ersilia built ten models last month, the post
failed regardless of what it technically said. Announcing an incorporation is not claiming
authorship — but the difference has to survive a skim, which is why every model carries a
name.

## R1 — every model you name carries its own first author

A round-up covers a whole month, so credit cannot be concentrated in one opening block the
way a single-model announcement's could. The rule is per model: **name a model, name its
first author.** `check_post.py` resolves each named model's first author from OpenAlex and
fails on any model named without one.

A model counts as named if its name, slug or identifier appears in the post. So:

- **One line per model** — the model's name, its first author and institution, one clause
  on what it does, and the paper link.
- **≤5 authors on the paper?** The one-line form still names only the first author; the
  full list belongs in the report's per-model section, where there is room.
- **Author list never resolved?** Then **do not name the model in the post.** Publicising
  work you cannot attribute is the single thing this skill exists to prevent. It still
  appears in the internal report, with the gap stated — `SKILL.md` Step 3.
- Institutions are **named** in the post and **never tagged**.

Where the paper marks a corresponding author, they are usually the easiest to find on
LinkedIn, but the round-up names the first author for consistency across models.

## R2 — the credit comes before the packaging detail

The announcement may open the post. What Ersilia *did* — the packaging, the command, the
repository — may not appear until after the authors are named. `check_post.py` compares
the position of the `ersilia fetch` command against the first author mention.

So "we are very excited to announce" at the top is fine; "we packaged their model so it
runs anywhere" at the top is not. The first is an announcement, the second is a claim
about our own work placed above the people whose work it is.

## R3 — verb discipline

Verbs assign credit more strongly than any adjective. Keep the two vocabularies apart.

**Announcement language is not an authorship claim.** "We are very excited to announce the
incorporation of X" is the house opener: the object of the verb is the *incorporation*,
which is genuinely ours. "We are excited to launch X" or "we present X" makes the model
the object, and those stay banned.

| The authors | Ersilia |
|---|---|
| developed, trained, designed, built | packaged, wrapped, made available |
| screened, validated, showed, found | added to the Hub, standardised, integrated |
| published, released | ported, hosted, serve, distribute |

Banned outright — every one of these has appeared in a real draft somewhere:

> we built · we developed · we trained · we created · we present · we introduce ·
> introducing our · our new model · our latest model · we're excited to launch ·
> proud to present our

"Our" is only correct about things that are genuinely ours: our Hub, our packaging.
Never "our model".

## R4 — the paper is linked before the Hub

Link order is the machine-readable version of the credit hierarchy, and it is the part
readers act on. Order:

1. The publication DOI (`https://doi.org/…`).
2. The authors' own code repository (`Source Code` in the metadata).
3. Only then the Ersilia model repository or `ersilia fetch` command.

If the paper is open access, `fetch_model_context.py` returns `open_access_url` — prefer
the DOI anyway, since it is the citable, permanent form.

## R10 — Ersilia appears in two blocks, not four

**At most two paragraphs may mention Ersilia's role**: the title and the announcement.
That budget is spent at the top, deliberately. Nothing below the credit block gets to talk
about us again.

The sentences this rule exists to delete are the ones that *sound* generous:

> ✗ That packaging is the whole of our contribution — the assay, the model and the
>   validation are the authors'.
> ✗ The architecture, the dataset and the pretraining are theirs. We wrapped the released
>   weights and changed nothing.
> ✗ The science is theirs. Our part is the plumbing.

Every one of these is a paragraph about us wearing the costume of a paragraph about them.
Enumerating what belongs to the authors keeps the reader's attention on the division of
credit — which is our preoccupation, not theirs. The "Thanks to …" block already did the
crediting; a reader who reaches the end of the post knows who did what.

`check_post.py` counts paragraphs containing *Ersilia, we, our, us* after stripping URLs
and the `ersilia fetch` command, and fails on more than two.

## R11 — name the Ersilia Model Hub once

The title, the announcement and the enablement block all want to say "the Ersilia Model
Hub". Let exactly one of them — the title. The announcement can say "into the Hub", and
the enablement block starts from the capability instead:

> ✗ Their model is now packaged in the Ersilia Model Hub, so it runs as a featurizer in
>   any pipeline.
> ✓ It now runs as a featurizer in any pipeline, with no need to rebuild the original
>   environment.

`check_post.py` fails a post containing the phrase more than once. The rule is narrow on
purpose: it catches the one repetition that actually happens, without policing how often
the model's own name appears.

## Honesty rules

These are not mechanically checkable, so they are on you.

- **Quote no figure we have not reproduced.** Numbers may be cited only if they are the
  paper's own *and* `/model-incorporation-reproduce` returned **PASS**. On PARTIAL or FAIL,
  stay qualitative — and if the divergence is material, say so or say nothing. Never let a
  post imply a reproduction we did not achieve. `check_post.py` R9 warns whenever a
  percentage or metric name appears, precisely because it cannot tell.
- **Do not imply a collaboration that does not exist.** Packaging a public model is not a
  partnership. Write "their model is now in the Hub", never "in partnership with".
- **Do not imply clinical validity.** These are early-discovery models.
- **Name the licence when it constrains reuse.** MIT or Apache needs no mention; anything
  non-commercial or research-only does, in one clause, so nobody builds on a wrong
  assumption.
- **Say what we changed — and only if we changed something.** If Ersilia re-trained,
  sliced, or defaulted a parameter, one clause says so, inside the single Hub paragraph.
  Silent modification presented as the authors' model is the worst outcome available. But
  when nothing changed, **say nothing**: "we changed nothing" is a sentence about us, and
  R10 will fail it.
- **Do not add disclaimers.** Not quoting a figure is how the post stays honest about
  results we have not reproduced; a sentence saying we have not benchmarked the model is
  hedging, and in a post about someone else's work it reads as doubt cast on them. The
  same goes for preprint status: label the link `Preprint:` and let that carry it, rather
  than writing a caveat paragraph. Readers of a preprint link know what a preprint is.

## Tagging

**Never invent a LinkedIn handle.** A wrong tag notifies a stranger and misattributes a
paper in public. `check_post.py` R7 fails on any `@mention` that is not backed by a
`confirmed` row in the draft's *Profiles to tag* table.

The recommended pattern is **no `@` in the post body at all**. LinkedIn only binds a
mention when the name is typed into the composer and picked from the dropdown — a pasted
handle posts as dead text. So the draft carries plain names in the body and a separate
worksheet of verified profile URLs for whoever publishes.

Confidence in a profile row means: the profile's own page states an affiliation or
publication list matching this paper. A name match alone is **unverified** — common names
are common. Leave it unverified and let the human decide; an untagged author is a small
loss, a mis-tagged one is a public error.

Telling the authors before posting is good practice, and Ersilia may well do it — but it
is **not part of this skill**. Do not draft outreach, and do not hold the post waiting for
a reply. If the user reports that the authors have asked for something to change, that is
an instruction about the wording and you follow it.

## No internal credit

The post does not name the Ersilia contributor who did the incorporation, and does not
name Ersilia staff at all. Internal credit is real and belongs somewhere — but every line
spent on it is a line the authors do not get, and the closing lines of a post are the ones
people remember.

## Edge cases the metadata decides

Read `Source Type` before writing anything.

- **`External`** (the large majority) — everything above applies as written.
- **`Replicated`** — Ersilia re-trained a model following someone else's published method.
  Credit the *method's* authors in the hook exactly as usual, then state plainly that this
  is Ersilia's re-implementation and not the authors' own weights. Readers must not think
  they are running the published model.
- **`Internal`** — the model is Ersilia's. R1/R2 cannot apply; instead credit the
  Ersilia team members by name and credit whoever produced the **training data**, which is
  usually somebody else's paper or a public database. The self-reference rules relax; the
  honesty rules do not.
- **No DOI in `Publication`** — the author list cannot be resolved automatically. Ask the
  user for it rather than proceeding; a post with no names is not publishable under these
  rules.
- **Preprint since published** — cite the published version. `/model-incorporation-metadata`
  should already have caught this; if `Publication Type` still says `Preprint` and Crossref
  shows a journal version, fix the metadata rather than papering over it in the post.
