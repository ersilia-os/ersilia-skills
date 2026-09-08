# Post anatomy — the LinkedIn mechanics

Everything here is platform behaviour rather than taste. The credit rules live in
`attribution-rules.md`; this file is about what LinkedIn does to the text.

## The shape

```
[1]  Title — "New in the Ersilia Model Hub: <model name>"
[2]  Announcement — "We are very excited to announce the incorporation of <model>,
     <one line saying what kind of model it is>, into the Hub."
[3]  Credit — "Thanks to <authors> at <institutions>, <model> <what it produces>."
[4]  Method — 2–3 sentences. Every claim checked against the paper abstract.
[5]  Paper: <DOI>          (or "Preprint:" when Publication Type is Preprint)
     The authors' code: <Source Code>
[6]  What it enables — one sentence, then the command
     ersilia fetch <slug>
     https://github.com/ersilia-os/<eosXXXX>
[7]  Why it matters — one sentence with the LMIC / access lens, only if honest here
[8]  #Hashtags
```

Blocks 1–6 are mandatory. Block 7 is dropped rather than forced: a global-health framing
that does not actually fit the model reads as boilerplate, and readers notice. For a
domain-agnostic featurizer (`Biomedical Area: Any`) there is usually nothing honest to say,
so say nothing.

**Each block adds; none repeats.** This is the discipline the structure lives or dies by,
because blocks 2, 3, 4 and 6 are all circling the same model:

| Block | Its job | Not its job |
|---|---|---|
| 2 Announcement | that it is in the Hub, and what kind of model it is | how it works |
| 3 Credit | who made it, and what it **produces** | how it was trained |
| 4 Method | **how** it works and what it was trained on | restating the output |
| 6 Enables | what a reader can now **do** | restating the incorporation |

The failure mode is block 6 saying "their model is now packaged in the Ersilia Model Hub"
when block 1 and block 2 have already said exactly that. Block 6 starts from "It now
runs…" and goes straight to the capability. R11 fails a post that names the Ersilia Model
Hub more than once, which forces the fix.

There is no caveat block, no second explanation of Ersilia's role beyond the announcement
(R10), and no credit to the Ersilia contributor who did the incorporation — see
`attribution-rules.md`.

## Character budgets

| | |
|---|---|
| Hook, before "…see more" | **~210 chars** (varies by device; treat 210 as the ceiling) |
| House target, whole post | **900–1,500 chars** |
| LinkedIn hard limit | 3,000 chars |

Below 900 there is not room to credit twenty authors and say what the model does. Above
1,500 the post stops being read. `check_post.py` R5 warns outside the window.

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
