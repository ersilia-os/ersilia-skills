# Target venue guidance (self-review mode)

Used in Step 7 of `SKILL.md`, self-review mode only, to suggest 2–4 ranked journals for a
paper Ersilia is preparing to submit. This is a broader question than "is this paper
Hub-incorporation-worthy" — it's "where does this specific paper, with its specific rigor
level and contribution type, actually fit."

The venue-frequency data below reflects where Ersilia's own incorporated models have
historically been published (derived from the same empirical snapshot referenced by
`paper-to-model-assessment`'s Hub-relevance criteria) — a strong prior for "a paper that
looks like this is the kind of paper these venues publish," but not a guarantee, and rigor
level should still gate the suggestion (see the heuristic at the bottom).

## Top venues (by frequency among Ersilia-relevant publications)

| Venue | Frequency | Best fit for |
|---|---:|---|
| **Journal of Cheminformatics** | Dominant | Methods papers: new models, descriptors, featurizers, benchmarking studies. Open access, cheminformatics-specific audience, values reproducibility and methodological rigor over breadth of impact. The default strong fit for most Ersilia-style contributions. |
| **arXiv** (preprint) | Very high | Any contribution type, as a preprint — fast, no barrier, doesn't preclude later journal submission. Good first step when the paper is solid but not yet polished enough for a peer-reviewed venue, or when priority/timestamping matters. |
| **Journal of Chemical Information and Modeling (JCIM)** | High | Methods and application papers with strong methodological/statistical rigor; slightly more traditional cheminformatics/QSAR audience than J Cheminform. Good fit when the paper leans heavily on structure-activity or structure-property modeling. |
| **Nature Machine Intelligence** | High-impact | Foundational methods with broad ML significance beyond just cheminformatics — a paper needs a genuinely novel *ML* contribution, not just a strong application of existing methods to chemistry, to be competitive here. |
| **Nature Communications** | High-impact | Broad significance, cross-disciplinary appeal, strong real-world validation. Best for papers with a compelling "why this matters beyond the immediate field" story and enough data/breadth to justify it. |
| **Nucleic Acids Research** (Web Server issue) | Domain-specific | Papers whose primary contribution is a usable, working web server/tool — the bar here is a functioning, accessible service, not just a method described in the abstract. |
| **chemRxiv** (preprint) | Preprint | Chemistry-flavored preprint venue; similar role to arXiv but chemistry-specific audience. |
| **Cell family / Bioinformatics / J Med Chem / ACS Omega** | Longer tail | Cell-family: high-impact biology-forward framing. Bioinformatics: strong computational-methods bar, less chemistry-specific. J Med Chem: medicinal-chemistry-forward framing, best when the paper's story centers on drug candidates rather than the ML method itself. ACS Omega: solid, broadly-scoped venue, a reasonable landing spot for competent work that doesn't need top-tier framing. |

## Matching heuristic

1. **Contribution type first.**
   - New model/method/descriptor → J Cheminform or JCIM.
   - Dataset release without a model → J Cheminform, or a data-focused venue (Scientific
     Data) if the dataset itself is the headline contribution.
   - Working tool/web server → NAR Web Server issue.
   - Broadly significant methodological advance (not just a chemistry application of an
     existing ML idea) → Nature Machine Intelligence.
   - Strong real-world impact story with breadth beyond one endpoint → Nature Communications.

2. **Then gate by rigor level (from Step 7's verdict).** Don't suggest a high-impact venue
   for a paper that Step 6 flagged as needing major revision — be honest that the paper
   should clear those concerns first, and suggest venues proportionate to its current state.
   A paper needing only minor polish can reasonably target its "best fit" venue; a paper
   needing major revision should be told so explicitly, with the suggested venue framed as
   "once the [specific major concern] is addressed."

3. **Preprint first, when uncertain.** If the paper is solid but its eventual best-fit venue
   is genuinely unclear (e.g. borderline between J Cheminform and JCIM), suggesting arXiv or
   chemRxiv as an immediate first step is always a safe, low-risk recommendation alongside
   the ranked journal suggestions.

4. **Always give a one-line rationale tied to the paper's actual content** — not a generic
   "this journal publishes similar work." Reference the paper's specific contribution type,
   endpoint, or rigor characteristics.
