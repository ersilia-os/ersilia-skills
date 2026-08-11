---
name: peer-reviewing
description: >
  Emulate a peer review of a scientific manuscript PDF and produce a structured report with
  a prioritized action list and a formal recommendation verdict. Two modes: self-review (for
  Ersilia's own drafts before submission — coaching tone, includes suggested target journals)
  and referee (for a paper the user has been asked to formally review for a journal —
  editor-facing tone, calibrated to the target venue). Applies general peer-review standards
  (novelty, significance, methodology, clarity, whether the evidence actually supports the
  claims) plus a cheminformatics/AI4science-specific rigor checklist (data leakage, splits,
  baselines, applicability domain, reproducibility, generative-model evaluation). Always use
  this skill whenever a user wants a paper peer-reviewed, wants critical feedback on a draft
  before submitting, has been asked to referee or review a paper for a journal, asks "is this
  ready to submit", "review this paper", "give me reviewer comments", "what would a reviewer
  say about this", or shares a manuscript PDF and asks for a critical read — even if they
  never use the words "peer review" explicitly.
allowed-tools: [Read, Write, Bash, WebFetch, WebSearch, AskUserQuestion]
---

# Peer Reviewing

Read a manuscript PDF and produce a structured peer-review report: a summary, a set of
comments classified by severity, a domain rigor checklist, a reproducibility check, and a
formal recommendation verdict. The goal is to give the author (or the person asked to
referee) the same kind of critical, specific read a good human reviewer would give — not a
generic "looks good" pass, and not a vague list of platitudes.

Two modes shape the whole report, because a paper the user is writing themselves needs
coaching toward a strong submission, while a paper someone else asked them to referee needs
comments they can hand to an editor. Getting the mode right matters more than any individual
comment, so nail it down before doing anything else.

---

## What you receive

- **PDF** (required): either a local file path, or a PDF attached directly to the conversation.
- **`--mode <self-review|referee>`**: determines tone and report structure (see Step 0).
- **`--venue <name>`** (optional, situationally required — see Step 0).
- **`--short` / `--extended`** (optional, default `--extended`): report depth.
- **`--verify-novelty`** (optional flag, default off): enables a web-search-based novelty check.
- **`--verify-reproducibility`** (optional flag, default off): enables a full clone-and-run
  check against the paper's own code (see Step 5).

Determine the PDF source in this order:
1. **Attached PDF** — if the user attached a file to the conversation message, use it
   directly. The content is already available in context; no Read tool call is needed.
2. **File path** — if the user provided a local path (e.g. `/home/user/paper.pdf`), use the
   Read tool on that path.

If neither is present, ask the user to either attach the PDF or provide its path. Do not
invent a path.

---

## Step 0 — Determine mode and venue

The self-review and referee reports differ in tone, framing, and even which sections exist
(only self-review gets journal suggestions). Guessing wrong here doesn't just cost a few
lines of text — it produces a report that reads completely wrong for the situation, so it's
worth pausing to get right before reading a single page of the PDF.

**Mode:**
- If `--mode` is given, use it.
- If omitted, infer it from how the request is phrased. High-confidence signals for
  `self-review`: "review my draft", "is this ready to submit", "feedback on our manuscript
  before we send it out". High-confidence signals for `referee`: "I've been asked to review
  this for [journal]", "I'm refereeing this paper", "here are the reviewer guidelines,
  can you help me write comments".
- If the phrasing is genuinely ambiguous (e.g. the user just says "review this paper" with
  no other context and it's unclear whether they wrote it), ask once via AskUserQuestion
  rather than guessing.

**Venue:**
- `referee` mode: if `--venue` isn't given, ask for it. Venue norms genuinely change what
  counts as a strong paper — a Nature-family reviewer weighs broad significance and framing
  heavily, a J Cheminform or JCIM reviewer weighs methodological rigor and reproducibility
  more heavily, and a Nucleic Acids Research web-server paper is expected to ship a working,
  usable server rather than just an idea. Skipping this means calibrating against nothing.
- `self-review` mode: venue is optional context. If given, use it to calibrate expectations
  the same way; if not, Step 8 will propose venues based on the paper's own content.

---

## Step 1 — Read the manuscript

Use the Read tool on the PDF. Extract:

| Field | What to look for |
|---|---|
| **Title / Authors** | Exact title; first author + "et al." if more than two |
| **Contribution type** | Methods paper, dataset paper, application/benchmark study, review, or perspective — this determines which rigor-checklist items in Step 3 even apply |
| **Claimed contribution** | What the authors say is new, in their own words (usually from the abstract/intro) |
| **Methods summary** | What was actually done — architecture, training data, experimental protocol |
| **Results summary** | Headline numbers and how they were validated (held-out test set? cross-validation? prospective/external validation?) |
| **Stated limitations** | What the authors already admit as caveats — useful context, don't re-raise these as if you discovered them |
| **Data / code availability** | The exact statement made, plus every URL mentioned anywhere in the paper (repo, data download, supplementary, web server, Zenodo/DOI) |
| **Related work as cited** | What prior work the paper positions itself against |

---

## Step 2 — General peer-review assessment

Work through the dimensions a competent reviewer always checks, regardless of field:

- **Novelty & significance** — is the contribution genuinely new relative to what it cites?
  Is the significance claim proportionate to the evidence shown (a 2% AUC improvement is not
  "state-of-the-art" unless the paper shows why 2% matters here)?
- **Methodological soundness** — are the methods actually appropriate for the stated goal?
  Any obvious confound in how the experiment was designed?
- **Clarity & structure** — could a competent reader follow and reproduce the logic without
  needing to read the code?
- **Evidence-to-claims fit** — this is the one reviewers miss least often and authors miss
  most often: do the results shown actually support the conclusions drawn, or is there a gap
  (e.g. concluding "generalizes well" from one endpoint, or "outperforms baselines" from a
  comparison against weak baselines)?
- **Figures & tables** — self-explanatory, correctly labeled, statistically honest (watch for
  truncated axes, cherry-picked examples presented as representative, missing error bars)?
- **Related work completeness** — based only on what's cited in the paper itself at this
  stage (Step 6 covers an optional search-based check); note anything the authors' own
  framing suggests they should have engaged with but didn't.

---

## Step 3 — Domain rigor checklist (cheminformatics / AI4science)

Read `references/rigor-checklist.md`. It's organized by category (data splits, baselines,
metrics, reproducibility, applicability domain, chemistry-specific data handling, generative
models, docking/virtual screening, ablations) with a short note on which contribution types
each category applies to.

Go through every item that applies to this paper's contribution type. Skip categories that
don't apply (e.g. skip the generative-model section entirely for a QSAR paper) rather than
forcing a verdict on something irrelevant — padding the report with "N/A" clutter is worse
than a shorter, sharper report, and it also dilutes the items that actually matter.

For each applicable item, record: **Pass** / **Concern** / **Not applicable**, with a
one-line note explaining the verdict.

---

## Step 4 — Reproducibility & link check

1. Collect every URL identified in Step 1 (code repo, data download, supplementary
   materials, web server, DOI).
2. WebFetch each one. Record whether it resolves cleanly, redirects, 404s, or times out.
3. Cross-check against the paper's own availability statement — "code available at [URL]"
   with a dead link is a concrete, easily-fixed, and genuinely common reviewer complaint;
   flag it plainly.
4. This is a reachability check, not a deep audit: don't clone repos or attempt to run
   anything here. The question at this step is only "does the promised artifact exist and is
   it reachable" — actually running the authors' code to check the paper's claims hold up is
   Step 5, and is opt-in because it's a much heavier undertaking.

---

## Step 5 — Deep reproducibility verification (`--verify-reproducibility` only)

Skip entirely if the flag isn't set — Step 9's templates show a one-line "not run" note
instead. This step is expensive and can fail for many ordinary reasons (broken environments,
missing data, long training times), which is why it's opt-in rather than run by default. But
when a user does ask for it, it's usually because reproducibility is exactly what they're
worried about, so it's worth doing properly rather than half-heartedly.

This only proceeds if Step 4 found a working code repository — there's nothing to clone
without one. If the repo link 404'd or no code link exists at all, report "Cannot verify:
no working code repository found" and stop here. That's already a Major-tier finding coming
out of Step 4; don't invent a second, redundant one.

1. **Clone and install.**
   ```bash
   git clone <repo_url> /tmp/<slug>_reproduce
   cd /tmp/<slug>_reproduce
   pip install -r requirements.txt   # try `conda env create -f environment.yml` if pip fails
   ```
   On install failure: report the exact error and mark reproducibility **Not verified —
   install failed**. Don't force it or guess at fixes — a paper whose own environment
   doesn't install cleanly from its stated instructions is itself worth noting as a
   reproducibility concern, not something to route around.

2. **Reproduce specific reported values first, if any exist.** If Step 1 turned up
   "reproducibility anchors" — specific named-compound scores, worked examples, or a small
   case study reported directly in the paper's text — run those exact inputs through the
   cloned code and compare against the reported value. This is the cheapest and most
   concrete check available: one number the paper reports vs. one number the authors' own
   code produces, no dataset acquisition required.

3. **Reproduce aggregate metrics, if feasible.** If the paper reports a headline metric
   (AUC, RMSE, accuracy, etc.) on a named, publicly available benchmark:
   - Look for the dataset in the repo's own `data/` folder first, then in the paper's data
     availability statement.
   - Run the code's own evaluation path, as documented in the repo's README, on that
     dataset.
   - Compare the reproduced metric to the paper's reported value using the same tolerance
     bands used elsewhere in Ersilia's reproduction tooling, so a "Divergent" here means the
     same thing it means everywhere else in the team's work:

     | Metric type | Tolerance | 2× tolerance |
     |---|---|---|
     | AUC-ROC, AUC-PRC, Accuracy, MCC, F1 | ±0.03 absolute | ±0.06 |
     | RMSE, MAE | ±10% relative | ±20% relative |
     | R² | ±0.05 absolute | ±0.10 |

   If the dataset can't be acquired, or the evaluation path isn't documented clearly enough
   to run with confidence, say so plainly rather than guessing at a substitute — a paper
   with no discoverable path to reproduction is itself the finding worth reporting.

4. **Assign a status** to each item checked: **REPRODUCED** (within tolerance) /
   **APPROXIMATE** (within 2× tolerance) / **DIVERGENT** (beyond 2× tolerance — flag loudly,
   this is a strong signal something is wrong either with the paper's claims or with how it
   was run) / **NOT VERIFIED** (couldn't install, couldn't acquire data, or the evaluation
   path wasn't documented — always state the specific blocker rather than leaving it vague).

Anything **DIVERGENT** here is among the strongest Major comments a reviewer can make —
concrete, falsifiable, and hard to argue with. Feed it into Step 7 accordingly and let it
weigh heavily on the recommendation verdict.

---

## Step 6 — Optional novelty verification (`--verify-novelty` only)

If the flag is set:
1. WebSearch using the paper's own claimed-novelty language plus its key method/task terms.
2. Look for closely related prior work that the paper doesn't already cite.
3. Always include an explicit caveat in the report: this is a best-effort, non-exhaustive
   automated check — a subject-matter expert should still verify novelty claims directly.
   Search results can miss recent preprints, non-English work, or work under different
   terminology, and can also surface superficially-similar but substantively-different work.

If the flag is not set, still include a one-line note in the report ("Novelty verification:
not run — pass `--verify-novelty` to enable") so the user knows the option exists, rather
than silently omitting the section.

---

## Step 7 — Compile findings and verdict

Classify every concern raised in Steps 2–5:
- **Major** — would materially affect whether a reader trusts the paper's conclusions:
  a methodological flaw, an unsupported claim, a missing critical baseline, a broken
  reproducibility promise.
- **Minor** — clarity, presentation, or small gaps that don't undermine the core claims.

Build the prioritized action list from these, tagging each item **Critical / High / Medium /
Low** based on how much it threatens the paper's validity or its acceptance chances — not
just how easy or hard the fix is.

Then determine the verdict using the mode-appropriate scale. Justify it the way a real
reviewer would — reasoning through the major factors, not just picking a label:

**Referee mode:**
- **Accept** — no major concerns; only very minor points remain.
- **Minor Revision** — solid contribution, a handful of small-to-moderate fixes needed.
- **Major Revision** — fundamentally sound, but substantial new work is needed (an extra
  baseline, a missing ablation, a genuinely unclear method) before it's ready.
- **Reject** — a fundamental flaw undermines the core claims, or the paper fits so poorly
  it belongs in a different venue or field entirely.

**Self-review mode:**
- **Ready to submit** — no major concerns.
- **Needs minor polish** — only Minor-tier items outstanding.
- **Needs major revision** — one or more Major-tier items must be fixed before submitting
  anywhere.
- **Not ready** — a fundamental issue with the study design or evidence needs rethinking,
  not just polishing prose.

---

## Step 8 — Journal suggestions (self-review mode only)

Skip this step entirely in `referee` mode — the venue is already fixed by definition.

Read `references/target-venues.md`. Match the paper's contribution type, rigor level, and
domain to 2–4 ranked venues, each with a one-line rationale grounded in that venue's actual
scope — not generic "this seems good enough for a high-impact journal" hand-waving. If the
paper has real weaknesses (per Step 7), let that honestly shape the suggestions (e.g. a paper
needing major revision probably isn't ready to target Nature Communications yet, even if the
topic would otherwise fit).

---

## Step 9 — Write the report

Save the full report as a markdown file with the Write tool, and also present it in the chat
response — the saved file is what makes the report shareable/attachable (e.g. to an actual
submission, or to a colleague), while the chat response is what the user reads right now.

Default filename: `<slug-of-title>_peer_review.md`, saved in the same directory as the
source PDF (or the current working directory, if the PDF was only attached rather than given
as a path).

Always include the disclaimer near the top of both the file and the chat response — this is
an AI-emulated review, useful as a rigorous starting point or coaching aid, but not a
substitute for actual human reviewers or editorial judgment.

Branch on `--short` / `--extended` below.

---

### Mode: `--short`

```
# Peer Review — [Title]
*AI-emulated review — a rigorous starting point, not a substitute for actual reviewers or editorial judgment.*

**Mode:** [Self-review | Referee — target venue: [venue]]

## Summary
[2–3 sentences: what the paper claims to contribute]

## Recommendation
**Verdict:** [verdict]
**Why:** [2–3 sentence justification]

## Top concerns
[3–5 bullets, Major-tier only, each a short clause + why it matters]

## Prioritized action list
1. [Critical/High/Medium/Low] ...
2. ...
```

Append this section only in `self-review` mode:

```
## Suggested target journals
1. **[Venue]** — [one-line rationale]
2. ...
```

---

### Mode: `--extended`

```
# Peer Review — [Title]
*AI-emulated review — a rigorous starting point, not a substitute for actual reviewers or editorial judgment.*

**Mode:** [Self-review | Referee — target venue: [venue]]
**Authors:** [First Author et al., Year]

## Summary
[4–6 sentences: contribution, approach, headline result, what's actually being claimed]

## Recommendation
**Verdict:** [verdict]
**Justification:** [full paragraph reasoning through the major factors behind the verdict]

## Major Comments
1. **[short label]** — [what's wrong, why it matters, what in the paper supports the concern]
2. ...

## Minor Comments
- ...

## Domain Rigor Checklist
| Item | Status | Note |
|---|---|---|
| [item] | Pass / Concern / N/A | [one-line note] |

## Reproducibility & Link Check
| Link | Status |
|---|---|
| [url] | Resolves / Redirects / 404 / Timeout |

## Deep Reproducibility Verification
[If `--verify-reproducibility` was used: status (REPRODUCED / APPROXIMATE / DIVERGENT / NOT
VERIFIED) for each item checked — reproducibility anchors and/or aggregate metrics — with
reported vs. reproduced values, or the specific blocker if not verified.]
[If not: "Not run — pass `--verify-reproducibility` to enable a full clone-and-run check
against the paper's own code."]

## Novelty Verification
[If `--verify-novelty` was used: findings + the caveat from Step 6.]
[If not: "Not run — pass `--verify-novelty` to enable an automated literature check."]

## Prioritized Action List
1. [Critical] ...
2. [High] ...
3. [Medium] ...
4. [Low] ...
```

Append this section only in `self-review` mode:

```
## Suggested Target Journals
1. **[Venue name]** — [one-line rationale tied to the paper's contribution type and rigor level]
2. ...
```

---

## Reference Files

- `references/rigor-checklist.md` — the cheminformatics/AI4science-specific pitfall checklist used in Step 3.
- `references/target-venues.md` — venue scope/fit guidance used in Step 8 (self-review mode only).
