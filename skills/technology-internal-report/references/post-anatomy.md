# Post anatomy — the LinkedIn mechanics

Everything here is platform behaviour rather than taste. The credit rules live in
`attribution-rules.md`; this file is about what LinkedIn does to the text.

## The shape

```
[1]  Title — "New in the Ersilia Model Hub: <n> models from <Month>"
[2]  Announcement — "We are very excited to announce <n> new models incorporated last
     month — <the span, e.g. featurizers, generative models and an activity predictor>."
[3]  "With thanks to the authors of each:"
[4]  One line per model, blank line between:
     <Model name> — <First Author> and colleagues at <Institution> — <one clause on what
     it does>: <paper DOI>
[5]  One sentence on what they now enable
[6]  Full catalogue: <link>
[7]  #Hashtags
```

Blocks 1–4 are mandatory. Block 5 is one sentence, not a paragraph — the models have
already spoken for themselves.

**Each block adds; none repeats.** Blocks 1, 2 and 5 all circle the same fact:

| Block | Its job | Not its job |
|---|---|---|
| 1 Title | the month, the count, and that it is the Hub | what any model does |
| 2 Announcement | the *span* of the month — which kinds of model | naming models |
| 4 Model lines | who made each one and what it does | Ersilia |
| 5 Enables | what a reader can now do | restating the incorporation |

R11 fails a post that names the Ersilia Model Hub more than once, which forces block 5 to
start from the capability rather than from where the models live.

There is no caveat block, no second explanation of Ersilia's role beyond the announcement
(R10), and no credit to the Ersilia contributors who did the incorporations — see
`attribution-rules.md`.

## Character budgets

| | |
|---|---|
| Hook, before "…see more" | **~210 chars** (varies by device; treat 210 as the ceiling) |
| House target, a monthly round-up | **900–2,500 chars** |
| LinkedIn hard limit | 3,000 chars |

Below 900 there is not room to credit a month of authors. Above 2,500 the post stops
being read, and LinkedIn's own ceiling is 3,000. The window is wider than a single-model
post's because nine or ten models of credit will not fit in 1,500. `check_post.py` R5
warns outside it.

## No formatting

LinkedIn renders **no markdown**. `**bold**`, `[text](url)` and backticks all post as
literal characters. R8 fails on each.

The unicode "math alphanumeric" trick (𝗯𝗼𝗹𝗱 𝘁𝗲𝘅𝘁) does render — and is **banned here**.
Screen readers announce those codepoints individually or skip them, so a post styled that
way is unreadable to blind readers. R8 fails on it. Structure with line breaks instead;
a blank line between blocks is the only typography the platform gives you, and it is enough.

## Links

Put them **in the post body**, in the order `attribution-rules.md` R4 requires.

LinkedIn's feed algorithm de-prioritises posts carrying external links, and the common
workaround is to move links to the first comment. Ersilia does not do that here: a post
that credits authors in prose while hiding their paper in a comment is credit theatre.
Reach is worth less than the paper being one click away. If reach matters for a particular
launch, add the links *again* in the first comment — never move them out of the post.

Bare URLs are fine and preferred; LinkedIn does not shorten them in the body, and a
visible `doi.org` link reads as a citation.

## Emoji

At most one, and only if it carries information. Ersilia's voice is "clear, plain and
grounded" and the audience includes grantmakers and senior academics; a rocket emoji reads
as a product launch, which this is not. Never use emoji as bullet characters — screen
readers read every one aloud.

## Hashtags

Three to five, grouped on the final line. R6 warns otherwise. Draw from:

`#DrugDiscovery` `#AntimicrobialResistance` `#AMR` `#OpenScience` `#OpenSource`
`#NeglectedTropicalDiseases` `#GlobalHealth` `#MachineLearning` `#AI` `#Cheminformatics`

Pick by what the model actually is — the `Biomedical Area` and `Tag` metadata fields are
the honest source. Do not add `#Innovation`-class filler.

## Timing

Post after the model is genuinely fetchable — the PR merged, the Docker image built and
`Status: Ready` in the metadata. A post that leads to a failing `ersilia fetch` costs more
than a week's delay. Step 1 of `SKILL.md` checks this.
