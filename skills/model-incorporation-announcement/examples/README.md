# Examples

Two worked announcement drafts, kept so the next one can be written against them. Both
pass `scripts/check_post.py` with 0 fail across all twelve rules.

What each is here to demonstrate — this lives here rather than inside the drafts, which
carry only what the person posting needs:

| Example | Shows |
|---|---|
| `eos4e40-announcement.md` | A 20-author *Cell* paper: the **>5 rule** — first author, last author, "and 18 colleagues". A closing "why it matters" block, which is honest here because the model is an antimicrobial one. And the **abstract fact-check failing over**: OpenAlex and Crossref both hold no abstract for this paper, so the check was done against the paper and recorded as such. |
| `eos9q2i-announcement.md` | A 5-author arXiv preprint: the **≤5 rule** — all five named inline in the thanks sentence. **Affiliations taken from the paper**, because arXiv deposits none and OpenAlex returns an empty institution list. The DOI **derived** from an `arxiv.org/abs` URL. A link labelled `Preprint:` carrying the preprint status, with no caveat paragraph. And **no** closing block: `Biomedical Area` is `Any`, so there is no honest access angle to claim. |

Between them they cover both credit shapes and both states of the abstract check, which is
why there are two and not one.

Both carry a **real completed profile lookup**, authors only — institutions are named in
the post but never tagged. Between them they show all three outcomes the protocol
actually produces:

- **`corroborated`** — four of Mol-JEPA's five authors.
- **`ambiguous`** — Balestriero has two live-looking profiles after a Meta → Brown move;
  Stokes likewise after Broad → McMaster, and in his case the profile whose title matches
  the paper is the *stale* one.
- **`unverified`** — eos4e40's last author has no personal profile at all, and the nearest
  name match is a different person. Senior academics often are not on the platform.

No profile page was opened in either: LinkedIn answers non-browser clients with HTTP 999,
which is why the protocol is built from search-result titles plus independent sources.

## What is not in a draft

Drafting inputs and internal findings stay out of the file. The reproduce verdict and the
licence check govern *what the post may say* — they are not notes for the person pasting it
in. Metadata defects found along the way (a `Publication` field holding an arXiv URL
instead of a DOI, an `Interpretation` still carrying template placeholder text — both real
in `eos9q2i`) are reported to the user in conversation, where someone can act on them, and
never parked in an announcement draft where they would be read as part of the post.

The one exception: **when the post quotes a figure**, the draft carries a
`**Reproduce verdict:** PASS` line, because then the provenance is load-bearing. No figure,
no line.
