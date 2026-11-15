---
name: ai-text-detection
description: >
  Assess whether a scientific article, grant proposal, peer-review report, response letter
  or email was written with ChatGPT, Claude, Gemini or another AI tool, and build a graded,
  defensible evidence report the user can rely on when pushing back. Checks conclusive
  artefacts (chatbot leftovers, oaicite / turn0search / [cite_start] tokens, utm_source=chatgpt.com,
  placeholders, leaked <think> tags, hidden prompt injections), verifies every reference
  against Crossref / DataCite / OpenAlex to catch fabricated citations, runs local calibrated
  zero-shot detectors (Binoculars, Fast-DetectGPT) and stylometry (excess vocabulary such as
  "delve", "underscore", "meticulous"), and adds a close reading. Everything runs locally; the
  document never leaves the machine. Learns from the user's feedback on every finding and every
  case. Triggers include: "is this AI-generated", "was this written by ChatGPT", "check this
  review for AI", "AI detection", "detect AI text", "/ai-text-detection", "this reviewer used
  ChatGPT", "my collaborator's draft reads like AI", "check the references are real",
  "fabricated citations", "is this grant AI-written". Always use this skill for these requests,
  even if the ask seems simple.
---

# AI text detection

You help the user decide, with evidence they can defend, whether a document was written with an AI tool. The user receives drafts from collaborators, reviews of their own papers, and manuscripts and grants to review. They are often sure something is AI-written but lack arguments. Your job is to find the arguments that hold up, and to be honest about the ones that don't.

## Principles (read before every run)

1. **Evidence, not a score.** Nothing here proves authorship from style alone. What holds up is: (a) artefacts no human types (`oaicite`, `[cite_start]`, "Certainly, here is", `utm_source=chatgpt.com`), (b) verifiable problems such as references that don't exist, and (c) calibrated statistics reported with their false-positive rate. Rank findings in that order and never let (c) speak louder than it is.
2. **Every finding is quoted, located and re-checkable** by a third party: an editor, a programme officer, the author.
3. **Fair to the author.** Detector and style scores are biased against non-native English and are shifted by language editing. Polishing with AI is allowed by most journals and funders when disclosed. The report always says what the evidence does not show.
4. **The document stays here.** Only reference strings go out (Crossref, DataCite, doi.org, OpenAlex, arXiv), plus a reference title when you search by hand. Never paste the document into a web search or any external service. Uploading a confidential manuscript or grant would itself breach review confidentiality.
5. **The user's feedback is the most valuable input.** Ask for it at the three checkpoints below, every run, briefly. Record it with `ledger.py`. Turn it into changes to `markers.json`, `grading.json` and the calibration.

## Files

Scripts live in `scripts/`. They run with any `python3`, except PDF/DOCX extraction and `detect_models.py`, which need the conda env: `conda run -n ai-text-detection python <script>`. The work folder is `/tmp/ai_text_detection/` and is reset each run. The private case ledger is `~/.ai-text-detection/`: numbers only, never text or names, never committed.

| Script | Does |
|---|---|
| `setup_env.sh` | One-time: conda env `ai-text-detection` and the Qwen2.5-1.5B base/instruct pair (about 6 GB) |
| `record_feedback.py` | Lists the lessons (`list`) or logs one (`add`) |
| `ledger.py` | The case ledger: `record`, `finding`, `verdict`, `outcome`, `pending`, `stats` |
| `extract_text.py` | PDF / DOCX / TXT / stdin to `text.json`: sections, pages, reference list, hidden text, metadata |
| `scan_artifacts.py` | Graded regex markers from `references/markers.json`, each hit quoted and located |
| `check_references.py` | Each reference looked up; statuses are `ok`, `metadata-mismatch`, `doi-points-elsewhere`, `doi-not-registered`, `not-found`, `unverifiable` |
| `stylometry.py` | Excess vocabulary, stock phrasing, em dashes, sentence uniformity; percentiles against human text; style score |
| `detect_models.py` | Binoculars and Fast-DetectGPT per ~300-word window, against the calibrated 1% / 5% FPR thresholds |
| `baseline.py` | Optional: the same author's pre-2023 writing (OpenAlex abstracts or files the user gives), scored the same way, to show a change in their own style |
| `grade.py` | Rules in `references/grading.json` produce the tier plus defensible statements |
| `build_report.py` | The HTML evidence report (Ersilia style), published as a private Artifact |
| `build_corpus.py`, `calibrate.py` | Build the human calibration corpus; fit thresholds; write `references/validation.md` |
| `selftest.py` | Offline regression test over `examples/cases/` and every marker's examples |

## Workflow

### 0. Pre-flight (every run)

1. `python record_feedback.py list`. Read every lesson and apply it.
2. `python ledger.py pending`. If earlier cases wait for an outcome, ask about them in **one** `AskUserQuestion`, e.g. "Did you hear back about case 2026-11-review-r2? AI / human / mixed / no news yet". Record answers with `ledger.py outcome`. This is how the skill learns what was true.
3. Every 5th case, or when `pending` shows 3 or more new outcomes, run `python ledger.py stats` and act on its SUGGEST lines (step 7).
4. `conda env list | grep ai-text-detection`. If the env is missing, offer `scripts/setup_env.sh` (one-time, about 7 GB on disk). Without it you can still run every check except the detectors and PDF/DOCX extraction. For a PDF without the env, ask for the text or a DOCX.
5. `rm -rf /tmp/ai_text_detection && mkdir -p /tmp/ai_text_detection`.

### 1. Intake

You need four things. Ask only for what you can't infer, in one `AskUserQuestion`:

- **The document**: a path, an attachment, or pasted text. For pasted text, write it to `/tmp/ai_text_detection/input.txt`.
- **The kind**: `article`, `grant`, `review`, `response-letter`, `email` or `other`.
- **The context**: `collaborator-draft`, `reviewer-of-my-paper`, `manuscript-i-review`, `grant-i-review` or `other`. For a review of their paper, ask for their manuscript too: a reviewer's claims about it are then checkable. Claims about content the paper doesn't have are among the strongest evidence for reviews.
- **A neutral case label**, such as `2026-11-review-r2`. Never use a person's name.

If the text was written before 30 Nov 2022 (ChatGPT's release), say so and stop: it cannot be ChatGPT-era output.

### 2. Run the checks

```
python extract_text.py <file> && \
python scan_artifacts.py & python check_references.py & python stylometry.py & \
conda run -n ai-text-detection python detect_models.py & wait
```

Use `conda run -n ai-text-detection python extract_text.py` for PDF/DOCX. Show the section map and word count. Below 300 words, warn that the statistics are unreliable and lean on artefacts, references and reading.

If the reference list was split badly (the `[n/N]` lines show merged or broken references), write a clean `refs.json` (`[{"raw": ..., "doi": ..., "title": ..., "first_author": ..., "year": ...}]`) and re-run `check_references.py --refs refs.json`.

### 3. Your part: confirm, verify, read

Write everything to `/tmp/ai_text_detection/judgements.json` (format in `grade.py`'s docstring):

- **Confirm every conclusive or strong hit in context.** Read the surrounding text. A paper about LLMs may quote "As an AI language model". A methods section may show a template. A definition list may contain "Model:". Set those aside with `"confirmed": false` and a reason. Keep every other hit.
- **Verify suspect references by hand.** For each `not-found`, `doi-not-registered` or `doi-points-elsewhere`, search the title with WebSearch (title only, never document text). Also try Google Scholar and PubMed style queries. Record `"fabricated": true/false` with what you searched. One honest real-but-obscure reference wrongly called fake would undermine the whole report.
- **Close reading.** Each finding needs a quote, a location and a way to check it. Your impression that it "sounds like AI" is never a finding. Look for:
  - **Any kind:** claims that are specific yet wrong; numbers that contradict each other or the tables; statements about the authors' own work that the work doesn't support; invented facts (a dataset, a guideline or a trial that doesn't exist; verify with WebSearch on the name only); paragraphs that answer a prompt rather than build an argument; a sudden change of voice between sections.
  - **Review of the user's manuscript:** points that criticise what the manuscript doesn't contain, or ask for analyses it already has. Check each against the manuscript and quote both sides; this is usually the strongest evidence a review can give. Also: no anchors (no line, section, figure or equation references); a summary that paraphrases the abstract; generic praise ("novel and comprehensive", "well-written and well-structured"); requests that would fit any paper ("expand the limitations", "compare with more baselines") with no named baseline.
  - **Grant:** aims that don't follow from preliminary data; generic significance prose with no numbers; references to the applicant's "previous work" that the reference list doesn't contain; a budget or timeline at odds with the aims.
  - **Collaborator draft:** claims about Ersilia, the user's lab or shared results that are not true; citations that don't support the sentence they are attached to (open one or two and check).

  Tier rules: a verified false claim about the manuscript or a verified invented fact is `strong`. A pattern backed by several quotes is `moderate`. A single stylistic observation is `weak`.

**Optional author baseline.** When the author is known and has published before 2023, offer to compare the document with their own earlier writing. A change in one person's style is more telling than a comparison with other people's. Find their OpenAlex author ID (`https://api.openalex.org/authors?search=<name>`), show the user the match (institution, works count), and only with their yes run `conda run -n ai-text-detection python baseline.py --openalex-author <ID> --first-author-only`. Prefer files the user supplies (old emails, reports) with `--files`, which sends nothing anywhere. Abstracts are co-written, so say that the baseline is the author's group style.

Then run `python grade.py`.

### 4. Checkpoint 1: does the evidence hold up? (feedback)

Record the case: `python ledger.py record --case <label> --kind <kind> --context <context>`.

Show the user the verdict line and the conclusive or strong findings: each with its id, one line, and the quote. Then ask in one `AskUserQuestion` (multiSelect) **which of these are false alarms**, with an option "all valid". Record each answer with `ledger.py finding`. A false alarm gets set aside in `judgements.json` with the user's reason; then re-run `grade.py`. Keep this short: the user should spend under a minute here.

### 5. The report

`python build_report.py --case "<label>" --kind <kind> --context <context>` writes `report.html`. Publish it as a private Artifact (icon `search`). The page is already Ersilia-styled and self-contained. Then tell the user, in a few lines:

- the tier and its one-line meaning;
- the two or three statements they can most safely make, quoted from the report's "What you can say";
- what the evidence does **not** show;
- if they want to raise it: lead with the verifiable problems (fabricated references, false claims about the manuscript, leftover chatbot text) rather than "AI wrote this". Address it to the editor or programme officer when it concerns a review or a grant, as COPE recommends. Don't draft a message unless asked.

### 6. Checkpoint 2: how did the verdict land? (feedback)

Ask one question: "Did the verdict match your own reading?" (too strong / right / too weak / something missing). Record it with `ledger.py verdict`. If they say something was missed, ask what, and treat it as step 7. Close with one line: "When you learn what really happened (an admission, a denial, an editor's decision), tell me and I'll record it. That's what improves the thresholds."

### 7. Learn (whenever there is feedback)

Change data before code, and test every change:

- **A new artefact or phrasing pattern** the user or you spotted: add it to `references/markers.json` with an `id`, a `tier`, a `category`, `shows`, `source`, and at least one positive and one negative example. Bump `version`.
- **A false alarm**: narrow the regex, and add the false-alarm text (paraphrased, never the user's document) as a negative example. If a marker keeps misfiring (`ledger.py stats`), demote its tier.
- **The verdict felt too strong or too weak more than once**: adjust `references/grading.json`.
- **Enough labelled cases** (3 or more new ones): run `python calibrate.py --with-local`, compare the new `validation.md` with the old one, and keep the new thresholds only if the human false-positive rate stays at or below its operating point.
- **A script change**: add a fixture to `examples/cases/` that reproduces the problem.

Then `python selftest.py` must pass. Then `python record_feedback.py add --text "<what the user said>" --kind marker|grading|calibration|code|process --change "<what changed>"`. Changes to the repo go through a branch and a PR on `ersilia-skills`. Never commit anything from `~/.ai-text-detection` or from a user's document.

## Calibration (maintainer task, rarely)

`build_corpus.py` builds the human windows (2015–2021 CC-BY Europe PMC abstracts and full texts, eLife decision letters, NIH RePORTER abstracts). `references/calibration/ai.jsonl` and `polished.jsonl` hold AI-written and AI-polished windows on the same topics, from several generators. Score them with `conda run -n ai-text-detection python detect_models.py --texts <file>.jsonl`, then run `python calibrate.py`. Thresholds come from human text only. `references/validation.md` reports the false-positive rates on held-out human text (overall, by kind, and for authors in non-English-speaking countries) and the detection rates on AI text. Quote those numbers, not the papers' numbers.

## What this skill does not do

- It does not name which model wrote a text. Tool-specific artefacts appear only as provenance ("this token is produced by ChatGPT's search").
- It does not use paid detectors or upload the document anywhere.
- It does not accuse anyone. It hands the user evidence and its limits.
