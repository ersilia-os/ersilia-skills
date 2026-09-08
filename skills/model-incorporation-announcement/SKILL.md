---
name: model-incorporation-announcement
description: >
  Draft the LinkedIn post announcing that a model has been incorporated into the Ersilia
  Model Hub, giving the model's original authors more prominence than Ersilia. Resolves
  the ordered author list and affiliations from the model's publication DOI, drafts the
  post, and lints it against the attribution rules before anything is published. Use this
  skill whenever a user wants to announce, publicise or post about a newly incorporated
  model. Trigger on phrases like "announce this model", "write the LinkedIn post for
  eosXXXX", "post about the new model", "draft the announcement", "we incorporated a
  model, let's tell people", or any request to publicise a Hub incorporation. Always use
  this skill for incorporation announcements, even if the request seems simple.
argument-hint: <eosXXXX> [--reproduce PASS|PARTIAL|FAIL]
allowed-tools: [Bash, Read, Write, WebFetch, WebSearch, AskUserQuestion]
---

# Model Incorporation Announcement

Your job is to draft the LinkedIn post that announces a newly incorporated model — and to
draft it so that the **original authors carry the post and Ersilia carries one clause of
it**. This is the last step of the incorporation pipeline, after
`/model-incorporation-reproduce` and after the pull request is merged.

The governing principle: Ersilia did the packaging, somebody else did the science. A post
that blurs the two costs Ersilia the trust that makes open publication worth it for
researchers. `references/attribution-rules.md` turns that principle into twelve rules,
all of which `scripts/check_post.py` checks.

The post follows a **fixed block structure** — announcement, credit, method, links,
capability — set out in `references/post-anatomy.md`. Do not invent a shape for each model.
Two rules catch the drift a well-meaning draft falls into: **R10**, Ersilia gets two blocks
at the top and none after the credit; and **R11**, the Ersilia Model Hub is named once.

**Scope: the post text, and nothing else.** No image, no cross-posting, no outreach to the
authors, and no publishing — this skill hands over a draft that a human posts.

## Parse arguments

- `<eosXXXX>` (required) — the model identifier, e.g. `eos4e40`
- `--reproduce PASS|PARTIAL|FAIL` (optional) — the verdict from
  `/model-incorporation-reproduce`. Governs whether the post may quote figures. Absent
  means **no figures**.

If the identifier is missing, ask for it. Do not accept a slug — the scripts key on the
identifier.

## Read these first

Read all three before drafting. They carry the reasoning and the edge cases that do not
fit here:

- **`references/attribution-rules.md`** — the credit hierarchy, the verb vocabularies, the
  honesty rules, the tagging policy, and what changes when `Source Type` is `Replicated`
  or `Internal`
- **`references/post-anatomy.md`** — the block structure, character budgets, LinkedIn's
  lack of markdown, links, emoji, hashtags
- **`references/author-lookup.md`** — the Crossref/OpenAlex procedure, how to get names
  right, and the conservative profile-verification protocol

---

## Step 1 — Check the model is actually live

An announcement that leads to a failing `ersilia fetch` costs more than a week's delay.

```bash
curl -s https://raw.githubusercontent.com/ersilia-os/<eosXXXX>/main/metadata.json | head -40
```

Require `"Status": "Ready"`. Confirm the `DockerHub` URL resolves. If either fails, stop
and tell the user the model is not ready to announce, naming what is missing.

## Step 2 — Build the context

```bash
python scripts/fetch_model_context.py <eosXXXX> --out /tmp/<eosXXXX>-context.json
```

This reads the model's metadata from GitHub, then resolves the publication DOI against
Crossref and OpenAlex. Read the resulting JSON and the warnings on stderr.

The fields that decide how you write:

| Field | What it decides |
|---|---|
| `credit.first_author`, `credit.last_author`, `credit.n_authors` | who is named, and how (R1) |
| `credit.lead_institutions` | the institutions named in the hook |
| `credit.has_global_south_author` | whether the post names LMIC institutions |
| `model.source_type` | `External` / `Replicated` / `Internal` — changes the whole frame |
| `model.license` | whether a licence constraint must be stated |
| `publication.title`, `.journal`, `.year` | the paper's own identity |
| `publication.abstract` | what the method paragraph is fact-checked against (Step 4) |

**If `credit.n_authors` is 0**, the DOI did not resolve. Ask the user for the author list
rather than proceeding — a post with no names is not publishable under these rules.

**If `credit.lead_institutions` is empty**, the paper is very likely an arXiv preprint;
arXiv deposits no affiliations. Read them off the paper's title page and record in the
draft that they were transcribed by hand.

**If `model.source_type` is `Internal` or `Replicated`**, read that section of
`references/attribution-rules.md` now; R1 and R2 do not apply as written.

**Report metadata defects rather than writing around them.** A placeholder
`Interpretation`, a `Publication` field that is not a DOI URL, a missing `Description` —
these are `/model-incorporation-metadata` bugs. Use the paper directly for this post, and
raise the defect **with the user in conversation**, not in the draft file: it is something
someone needs to go and fix in the model repository, and in an announcement draft it just
reads as part of the post.

## Step 3 — Draft the post

Follow the block structure in `references/post-anatomy.md` exactly. Write plain text,
900–1,500 characters, no markdown, at most one emoji.

The structure exists because blocks 2, 3, 4 and 6 all circle the same model and it is very
easy to say the same thing four times. Each block has one job:

| Block | Its job |
|---|---|
| 1 Title | `New in the Ersilia Model Hub: <model name>` |
| 2 Announcement | that it is in the Hub, and what kind of model it is |
| 3 Credit | `Thanks to <authors> at <institutions>, <model> <what it produces>.` |
| 4 Method | how it works and what it was trained on |
| 6 Enables | what a reader can now do — never restating the incorporation |

Block 3 is the one that carries the skill's whole purpose. Name every author for a paper
with five or fewer; first, last and a count beyond that (R1).

Draw the science from `publication.abstract` and `model.description`. Quote a figure only
if `--reproduce PASS` was passed **and** the figure is the paper's own.

## Step 4 — Fact-check the method paragraph against the abstract

**Always do this, and record it in the draft.** The method paragraph is where a plausible
sentence that the paper does not support is most likely to appear, and it is the part a
scientific audience will check.

Take block 4 claim by claim and match each against `publication.abstract`. Build the table
that goes into the draft:

| Claim in the post | Abstract |
|---|---|
| masks entire modalities and predicts their latent representations | "masks entire modalities and predicts the corresponding latent representations" ✓ |
| … | … |

Rules for the table:

- A claim with no support in the abstract is **cut or rewritten**, not softened.
- Where the abstract and `Description` give different figures (say "nearly 5 million" vs
  "4.69 M"), use the precise one and note both.
- **`publication.abstract` is often `null`.** Publishers deposit abstracts inconsistently
  and OpenAlex has none for many journal articles — for eos4e40's *Cell* paper it comes
  back empty. That is not permission to skip the check: verify against the paper itself,
  and record in the draft that the automated source was unavailable.

## Step 5 — Look up the authors' profiles

**Always do this, and always report the result in the draft.** A draft with placeholder
rows is not finished — `check_post.py` R12 fails one.

Look up **only the authors the post names** (all of them for a paper with ≤5, the first and
the last beyond that). **Do not look up institutions**: Ersilia names them in the post but
does not tag them. `references/author-lookup.md` explains why.

Use `WebSearch`, including a pass restricted to `linkedin.com` via `allowed_domains` — it
surfaces profiles the open search misses. Then follow the protocol in
`references/author-lookup.md`, which exists because **a LinkedIn profile cannot be
opened**: `WebFetch` on a `/in/` URL returns HTTP 999. Verification is therefore built from
the search-result title (LinkedIn renders them as `Name - Employer | LinkedIn`) plus at
least one independent source — Google Scholar, ORCID, a lab page, an institutional
directory.

Record every author as a row with the URL, the evidence, and one of four statuses:

| Status | Means | Taggable |
|---|---|---|
| `confirmed` | a human opened the profile and it matches | yes |
| `corroborated` | title affiliation matches **and** ≥1 independent source ties the person to this paper or lab | yes — human confirms in the composer |
| `ambiguous` | several candidate profiles, or a common name with nothing distinguishing | **no** |
| `unverified` | nothing found | **no** |

You can only ever write `corroborated` at best; `confirmed` belongs to whoever opens the
profile. **Never invent a handle**, and leave `@` out of the post body entirely — LinkedIn
only binds mentions typed into the composer.

Two outcomes are normal and must be reported plainly rather than smoothed over:

- **Two profiles for one person.** A move between the paper and the incorporation leaves
  both live-looking, and sometimes the one whose title matches the paper is the stale one
  (eos4e40's first author moved from the Broad to McMaster). Mark `ambiguous`.
- **No profile at all.** Senior academics frequently are not on LinkedIn; eos4e40's last
  author has no personal profile, and the nearest name match is a different person
  entirely. Mark `unverified` and say what you searched.

## Step 6 — Write the draft file and lint it

Write to `drafts/YY-MM-DD-<eosXXXX>.md` with exactly these sections, in this order —
`check_post.py` parses them:

````markdown
# Announcement — <eosXXXX> · <slug>

**Paper:** <title> — <journal>, <year> · <doi url>
**Authors:** <first> (first) → <last> (last), <n> total · <institutions>

**Method paragraph checked against the abstract:** <the table from Step 4, or a note
saying the abstract was unavailable and what was used instead>

## Post

```text
<the post body, exactly as it will be pasted>
```

## Profiles to tag

| Author | Position | Profile | Status |
|---|---|---|---|
| <name> | first | `linkedin.com/in/<handle>` | **corroborated** — <the evidence> |
| <name> | last | none found | **unverified** — <what was searched> |
````

**Keep the file to those sections.** It is read by the person about to post, so it holds
the post, the two lines identifying the paper and its authors, the fact-check record, and
the tagging worksheet. Nothing else:

- **No drafting inputs.** The reproduce verdict and the licence check govern what the post
  may *say*; they are not notes for whoever pastes it in. The one exception: if the post
  quotes a figure, add a `**Reproduce verdict:** PASS` line, because then the provenance is
  load-bearing.
- **No metadata defects.** Report those to the user in conversation (Step 2, Step 7), where
  someone can act on them. In the draft they read as part of the post.
- **No notes about the draft itself.** What an example demonstrates belongs in
  `examples/README.md`, not in its header.

Then lint:

```bash
python scripts/check_post.py drafts/YY-MM-DD-<eosXXXX>.md --context /tmp/<eosXXXX>-context.json
```

**Every rule must be FAIL-free before you show the draft to the user.** If a rule fails,
fix the post and re-run — do not explain the failure away. The rules exist because this is
exactly the kind of writing where good intentions drift. Warnings are judgement calls:
address them or say why you left them.

## Step 7 — Present and confirm

Show the user:

1. The **hook** on its own, as it will appear before "…see more"
2. The full post body
3. The linter output
4. The fact-check table from Step 4
5. The profile table, with unverified rows clearly marked
6. Any metadata defects found in Step 2, as a short list — these are for the user to fix
   in the model repository, and they are deliberately not in the draft file

Then ask:

> "This is the draft. The authors named in the hook are <names>; Ersilia appears from
> character <n>. Any wording you want changed?"

Apply any edits, re-run the linter, and show the result again. Do not post anything
yourself — Ersilia's LinkedIn is published by a human, and this skill stops at the draft.

## Step 8 — Hand off

Print the posting checklist:

> **To publish:**
> 1. Paste the post body into LinkedIn. Do not add formatting — LinkedIn renders none.
> 2. Tag the confirmed profiles by **typing** each name and picking it from the dropdown.
>    Skip every row marked unverified.
> 3. Check the DOI link appears above the Ersilia link in the preview.

## What not to do

- Do not post, schedule or publish anything. This skill produces a draft.
- Do not produce an image, a Medium version, a newsletter block or a note to the authors.
  The deliverable is one LinkedIn post.
- Do not credit the Ersilia contributor who did the incorporation. Internal credit is
  handled elsewhere; this post is about the authors.
- Do not invent an author name, an institution, a LinkedIn handle or a figure.
- Do not quote performance numbers without `--reproduce PASS`.
- Do not use "we built", "we developed", "our model", or any phrase from the banned list in
  `references/attribution-rules.md`.
- Do not describe packaging a public model as a collaboration or partnership.
- Do not bury the paper link in a first comment to chase reach.
