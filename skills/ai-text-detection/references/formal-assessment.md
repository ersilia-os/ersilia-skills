# The formal assessment

For when the user will show the result to someone else (an editor, a programme officer, an
integrity committee, the author) and must be able to demonstrate that it was done properly.
`formal_report.py` writes it from the same work folder as the normal report.

## What it can and cannot claim

There is **no official EU guideline on detecting AI-written text in research**, and no rule,
EU or otherwise, approves an AI detector as evidence. A search of the primary sources
(17 November 2026) found:

- **Binding law on side issues.** The AI Act (Art. 50) obliges *providers* of generative AI to
  mark their output; it does not oblige a researcher to label a paper, and does not regulate
  detectors. GDPR Art. 22 gives people the right not to be subject to a decision based solely
  on automated processing.
- **Soft law on disclosure and responsibility.** The ERA Forum *Living guidelines on the
  responsible use of generative AI in research* (fourth version, October 2026): disclose
  substantial use; polishing is not substantial; never send unpublished work to non-secured
  AI tools. The word "detect" does not appear in it.
- **Due-process codes.** The ALLEA *European Code of Conduct for Research Integrity* (2023)
  names "hiding the use of AI or automated tools" as an unacceptable practice, and equally
  "accusing a researcher of misconduct … in a malicious way"; it requires presumption of
  innocence, confidentiality, full details to the person concerned, a fair chance to respond,
  and proportionate action. COPE advises editors to start with a neutral question and not to
  reject on suspected AI use they cannot prove.
- **A reporting standard.** The ENFSI guideline for evaluative reporting (the European
  forensic-science standard): weigh the findings under two stated propositions, report how
  strongly they support one over the other, never the probability that a proposition is true.

So the formal assessment says it is **aligned with** these sources, step by step, and never
that it is certified, "AI Act compliant" or legally conclusive. It is not legal advice.

## The nine steps, and what backs each

| Step | What the document records | Basis |
|---|---|---|
| 1. Question and rule | What is being asked, and the journal / funder / institution rule that applies (`--policy`) | Living guidelines; ALLEA 3.1; Horizon Europe application form |
| 2. Confidentiality | Whether any text left the machine and to which services; nothing for work under review | Living guidelines (reviewers); ERC guidelines; ALLEA 3.2; GDPR Art. 5 |
| 3. Two propositions | Undisclosed substantial AI generation vs. the author's own text, possibly AI-polished | ENFSI (balance) |
| 4. Findings | Every line of evidence, run or not: finding, how to re-check it, known error rate and limits | ENFSI (robustness, transparency) |
| 5. Evaluation | The tier and the statements, worded as support for a proposition | ENFSI (logic) |
| 6. Limits | What the evidence does not show; non-native English; polishing | OIA casework; Turnitin; COPE Forum |
| 7. Human review | Who read the findings in context and takes responsibility; signature line | GDPR Art. 22; COPE Forum |
| 8. Next steps | A neutral question to the right person; who decides; rights of the person concerned | COPE case 26-11; ALLEA 3.2; funder rules |
| 9. Record | Tool and rule versions, dates, a hash of the text assessed | ENFSI (transparency) |

Annex A prints every source with its legal status, the exact words relied on, and how the
quote was checked. Annex B lists policy summaries for the kind of document.

## Rules for Claude when preparing one

1. Run the normal workflow first (SKILL.md steps 0-6). The formal assessment adds no new
   evidence; it records the same evidence to a stricter standard.
2. Ask the user for the **rule that applies** (journal instructions, call text, institutional
   policy) and pass it with `--policy`. If they have none, the document says so. Do not guess a
   policy, and do not quote one from memory: open it.
3. Ask who signs (`--assessor`). The user reviews the findings; the tool does not sign.
4. Wording: support for a proposition, never "the author used AI" or a probability of it. The
   detectors' line is capped at "moderate support" however large the number, because their
   likelihood ratios come from small test sets.
5. Never present the assessment as certified, official or legally binding, and never as a
   finding of misconduct. The competent body decides.
6. Sources go stale. `frameworks.json` records when each was reviewed; the monthly scan
   (`watch.py`, topic "policies") re-checks them. Before a formal assessment that will be used
   in a dispute, re-open the two or three sources it leans on most and update `reviewed`.
7. Quotes in `frameworks.json` are verbatim and were checked against the documents. Change one
   only after reading the source again; never paraphrase inside quotation marks.

## Where the wider EU picture matters

- Since 2 August 2026 providers must mark generated text (AI Act Art. 50(2)); systems already
  on the market have until 2 December 2026. Claude and ChatGPT (in the EU) now watermark their
  text, and both restrict verification to approved organisations: see `watermarks.md`.
- The Commission's own instructions to Horizon Europe evaluators say that AI use in drafting
  a proposal "may not be considered … as a reason to penalise a proposal". A concern about a
  grant must therefore rest on what is verifiably wrong in it, not on AI use as such.
