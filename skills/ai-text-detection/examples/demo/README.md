# Demonstration case: a published paper with known contamination

A public example of the ai-text-detection report, on a text whose origin is known.

**This is not the published article.** It is a copy of Turon G, Hlozek J, Woodland JG,
Kumar A, Chibale K, Duran-Frigola M. *First fully-automated AI/ML virtual screening cascade
implemented at a drug discovery centre in Africa.* Nat Commun 14, 5736 (2023),
<https://doi.org/10.1038/s41467-023-41512-2>, licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), **deliberately altered** to test
whether the skill finds text written or reworded by an AI. The original was written by its
authors without AI tools. The paper's results and numbers are unchanged.

| File | What |
|---|---|
| `turon2023_contaminated.docx` | The altered copy (Abstract to Methods, and the references) |
| `contamination.json` | Every change, and so the answer key |
| `report.html` | The skill's report on the altered copy, self-contained |

Rebuild the altered copy with `conda run -n ai-text-detection python scripts/build_demo.py`
(it fetches the paper from Europe PMC and applies `contamination.json`).

## What was changed

Nine paragraphs, 1,182 of 6,155 words of prose (19%). No replacement is longer than the
paragraph it replaces; the copy is 46 words shorter than the original. The AI text was
written by Claude on 17 November 2026, in two manners: its usual one ("default") and one
that avoids the usual AI vocabulary and rhythm ("careful").

| Where | Change |
|---|---|
| Abstract | Reworded by AI (same content) |
| Introduction, paragraph 1 | Replaced by AI text, default manner; a ChatGPT citation token left in place of citation [6,7] |
| Introduction, paragraph 2 | Reworded by AI |
| Introduction, last paragraph | Replaced by AI text, careful manner |
| Results, one short paragraph (CYP models) | Reworded by AI |
| Discussion, paragraph 1 | Reworded by AI |
| Discussion, paragraph 2 | Replaced by AI text, default manner; opens with a chatbot's "Certainly! Here is a revised version of the paragraph:" |
| Discussion, paragraph 3 | Replaced by AI text, default manner |
| Discussion, last paragraph | Replaced by AI text, careful manner |
| References 19 and 40 | Swapped for invented papers: one with an unregistered DOI, one with the DOI of another paper |
| End of the abstract | A hidden instruction to AI reviewers (white text, 1 pt) |

Everything else, including all of the Methods and nearly all of the Results, is the
authors' text.

## What the skill found

Verdict: **conclusive**, from the two leftover chatbot fragments.

| Planted | Found? |
|---|---|
| ChatGPT citation token | Yes (conclusive) |
| Chatbot opening line | Yes (conclusive) |
| Hidden instruction | Yes (reported separately, as manipulation) |
| Two invented references | Yes, both, and no real reference was called invented. Two real references without an identifier were not found automatically and were confirmed by hand |

The detectors (five free web detectors and the Binoculars demo, each first tested on known
texts, combined across three ways of splitting the text; run on 17 November 2026):

| Paragraph | Truth | Combined detectors |
|---|---|---|
| Introduction 1 | AI-written, default | 15× AI |
| Introduction 2 | AI-reworded | 7× AI |
| Discussion 1 | AI-reworded | 27× AI |
| Discussion 2 | AI-written, default | 31× AI |
| Discussion 3 | AI-written, default | 17× AI |
| Abstract | AI-reworded | 2.9× human: **missed** |
| Results (CYP paragraph) | AI-reworded | 12× human: **missed** |
| Introduction, last | AI-written, careful | 3.4× human: **missed** |
| Discussion, last | AI-written, careful | 4.5× human: **missed** |
| Untouched Results (1,862 words) | Human | 12× human; no sentence flagged |
| Untouched Methods (2,103 words) | Human | 11× human; no sentence flagged |
| Untouched Discussion (299 words) | Human | 2× human; no sentence flagged |
| Untouched Introduction (270 words) | Human | Even; 2 of 8 sentences flagged |

What this shows:

- **Default AI text is caught**, written or reworded: five of five paragraphs of 80 words
  or more in the Introduction and Discussion.
- **AI text written with care is not caught by detectors.** Both such paragraphs score as
  human. The close reading, done by a reader who was not shown the answer key, picked out
  exactly these two paragraphs for their change of register.
- **Short or isolated reworded text is missed**: the abstract (one passage on its own) and a
  69-word paragraph inside human Results.
- **Almost no false alarms on 4,500 words of human text.** The two flagged human sentences
  sit between AI paragraphs and share scan windows with them.
- **The whole-document figure says "human" (4.5×)**, because four fifths of the text is. The
  localised result is what matters, and the report words it that way.
- **Close reading also finds human slips.** Two of its three notes are about the authors'
  own text (four descriptors in the Discussion against five elsewhere; a mean cited as a
  median). They are graded weak, and they say nothing about who wrote the text.

Limits of this example: one paper, one AI model, one day's detector versions. Binoculars
answered for 3 of 16 passages only. The contamination and the report's confirmation steps
were made by the same assistant; only the close reading was blind.
