---
name: ai-text-detection
description: >
  Assess whether a scientific article, grant proposal, peer-review report, response letter
  or email was written with ChatGPT, Claude, Gemini or another AI tool, and build a graded,
  defensible evidence report the user can rely on when pushing back. Checks conclusive
  artefacts (chatbot leftovers, oaicite / turn0search / [cite_start] tokens, utm_source=chatgpt.com,
  placeholders, leaked <think> tags, hidden prompt injections), verifies every reference
  against Crossref / DataCite / OpenAlex to catch fabricated citations, runs free web AI
  detectors in Chrome on several splits of the text (each detector first tested on known
  human and AI texts, then combined into calibrated per-sentence evidence) when the text may
  leave the machine, plus calibrated stylometry (excess vocabulary such as "delve",
  "underscore", "meticulous"), and adds a close reading. Confidential manuscripts and grants
  under review are never sent to any website. Learns from
  the user's feedback on every finding and every case. Triggers include: "is this AI-generated", "was this written by
  ChatGPT", "check this review for AI", "AI detection", "detect AI text", "/ai-text-detection",
  "this reviewer used ChatGPT", "my collaborator's draft reads like AI", "check the
  references are real", "fabricated citations", "is this grant AI-written". Always use this
  skill for these requests, even if the ask seems simple.
---

# AI text detection

You help the user decide, with evidence they can defend, whether a document was written with an AI tool. The user receives drafts from collaborators, reviews of their own papers, and manuscripts and grants to review. They are often sure something is AI-written but lack arguments. Your job is to find the arguments that hold up, and to be honest about the ones that don't.

## Principles

1. **Evidence, not a score.** Nothing proves authorship from style alone. What holds up, in order: (a) artefacts no human types (`oaicite`, `[cite_start]`, "Certainly, here is"), (b) verifiable problems such as references that don't exist or false claims, (c) calibrated statistics with their measured error rates. Never let (c) speak louder than it is.
2. **Every finding is quoted, located and re-checkable** by a third party: an editor, a programme officer, the author.
3. **Fair to the author.** Detectors and style scores are biased against non-native English and shifted by language editing. Disclosed AI polishing is allowed by most journals and funders. The report says what the evidence does not show.
4. **Confidential text stays here.** Reading the user's own Google Drive through the connectors is fine. Text goes to web detectors only under the rules in `references/web_detectors_guide.md`, and never for a manuscript or grant the user is reviewing. Otherwise only reference strings leave the machine (Crossref, DataCite, doi.org, OpenAlex, arXiv). Never paste the document into a web search.
5. **Keep improving.** Ask for feedback at the two checkpoints, every run, briefly. Turn it into changes to the data in `references/` first, code second. Keep looking for new tools (`watch.py`).

## Layout

```
SKILL.md            this file
scripts/            the steps, one command each (Python 3; PDF/DOCX and Chrome need the conda env)
scripts/lib/        what the steps share (text, extraction, splits, detectors, evidence, grading, report); see its __init__.py
references/         data and documents; see references/README.md
assets/             report styles
examples/cases/     regression cases for selftest.py
```

Work folder: `/tmp/ai_text_detection/`, reset each run. Private case ledger: `~/.ai-text-detection/` (numbers only, never text or names, never committed). The conda env `ai-text-detection` (pymupdf, python-docx, Playwright; no models) is needed for PDF/DOCX extraction, `browser_detect.py` and `report_pdf.py`: `conda run -n ai-text-detection python <script>`.

| Stage | Script | Does |
|---|---|---|
| Setup | `setup_env.sh` | Creates the small conda env; only after the user agrees |
| Learning | `record_feedback.py` | Lists the user's lessons (`list`) or logs one (`add`) |
| | `ledger.py` | Case ledger: `record`, `finding`, `verdict`, `outcome`, `pending`, `stats` |
| | `watch.py` | Monthly scan for new leak tokens, detectors, word lists, policies |
| Intake | `drive_intake.py` | Google Drive links: file id, local Drive mount, revision history |
| | `extract_text.py` | PDF / DOCX / TXT to `text.json`: sections, references, hidden text, tracked changes |
| Local checks | `scan_artifacts.py` | Artefact patterns from `markers.json`, each hit quoted and located |
| | `check_references.py` | Every reference looked up: `ok`, `metadata-mismatch`, `doi-points-elsewhere`, `doi-not-registered`, `not-found`, `unverifiable` |
| | `stylometry.py` | Excess vocabulary, stock phrasing, sentence rhythm; calibrated style score |
| | `baseline.py` | Optional: the author's own pre-2023 writing, scored the same way |
| Web detectors | `segments.py` | Splits the prose into sections, passages and overlapping windows (`plan.json`) |
| | `web_detectors.py` | Records a result read by eye or a site that could not be used (`record`, `skip`); prints the `summary` |
| | `browser_detect.py` | Drives Chrome through the sites; every scan is a row in `plan.results.jsonl` |
| | `api_detectors.py` | Detectors with an API (Binoculars demo; Pangram, GPTZero, Sapling with the user's key) |
| | `web_controls.py` | Tests each detector on known texts; writes `web_calibration.json` |
| | `evidence.py` | Combines tools and splits into calibrated evidence per sentence, passage, document |
| Verdict | `grade.py` | Rules in `grading.json` give the tier and the defensible statements |
| Report | `build_report.py` | The HTML report (`lib/report.py`), published as a private Artifact |
| | `report_pdf.py` | The report as an A4 PDF, when the user asks for a file |
| Maintenance | `build_corpus.py`, `calibrate.py` | Human calibration corpus; style-score thresholds; `validation.md` |
| | `selftest.py` | Offline regression test over `examples/cases/` and every marker's examples |

## Workflow

Scripts run from `scripts/`.

### 0. Pre-flight (every run)

1. `python record_feedback.py list`. Read every lesson and apply it.
2. `python ledger.py pending`. If earlier cases wait for an outcome, ask about them in **one** `AskUserQuestion` ("Did you hear back about case 2026-11-review-r2? AI / human / mixed / no news yet") and record answers with `ledger.py outcome`. This is how the skill learns what was true.
3. Every 5th case, or with 3 or more new outcomes, run `python ledger.py stats` and act on its SUGGEST lines (step 8).
4. `conda env list | grep ai-text-detection`. If the env is missing, ask once before running `setup_env.sh` (tens of MB, no models). Without it, read Drive files through the connector and skip the browser detectors.
5. `python watch.py due`. When a scan is due, do it before the intake and keep it short (searches listed in `watchlist.json`; record each topic with `watch.py record`, then `watch.py done`). Turn anything worth adding into a concrete proposal at step 8.
6. `rm -rf /tmp/ai_text_detection && mkdir -p /tmp/ai_text_detection`.

### 1. Intake

You need four things. Ask only for what you can't infer, in one `AskUserQuestion`:

- **The document:** a Google Drive or Docs link (the usual case), a path, an attachment, or pasted text (write it to `/tmp/ai_text_detection/input.txt`).
- **The kind:** `article`, `grant`, `review`, `response-letter`, `email` or `other`.
- **The context:** `collaborator-draft`, `reviewer-of-my-paper`, `manuscript-i-review`, `grant-i-review` or `other`. For a review of the user's paper, ask for the manuscript too: claims about content the paper doesn't have are among the strongest evidence a review can give.
- **A neutral case label,** such as `2026-11-review-r2`. Never a person's name.

**Google Drive.** Use the connectors; never ask the user to download the file.

1. `python drive_intake.py id "<link>"`, then `get_file_metadata` (with `includeRichMetadata`): name, type, owner, created and modified times. Check the 30 Nov 2022 rule against the created time.
2. **PDF or Word:** try `python drive_intake.py local "<name>"` first; a local copy keeps hidden text, fonts and metadata. Otherwise `read_file_content` into `input.txt`, and say in the report that the hidden-text check was not possible.
3. **Google Doc:** `read_file_content` into `input.txt` and use `--format txt` (the connector renders headings as Markdown, so Markdown leftovers can't be judged). For hidden text, `read_doc` on documents up to ~30 pages: runs with a white `foregroundColor` or a `fontSize` under 2 pt. For a collaborator's draft with a short history (≤ ~10 revisions), count words per revision (`list_file_revisions`, `download_file_content` with `exportMimeType: text/plain`), write `[{"time", "author", "words"}]` to `revlist.json` and run `python drive_intake.py revisions /tmp/ai_text_detection/revlist.json`. Text arriving in one block is weak context only: people paste their own drafts too.
4. **Tracked changes in Word:** count insertions and deletions per author (`unzip -p file.docx word/document.xml`, `<w:ins` / `<w:del` by `w:author`) and ask which text to test. Usually the author's original: `extract_text.py --original`, so other people's edits don't count against the author.
5. Don't read comments unless asked: they are not the text under test.

If the text was written before 30 Nov 2022, say so and stop.

### 2. Local checks

```
python extract_text.py <file> && \
python scan_artifacts.py & python check_references.py & python stylometry.py & wait
```

(`conda run -n ai-text-detection python extract_text.py` for PDF/DOCX.) Show the section map and word count. Under 300 words, warn that the statistics are unreliable. If the reference list split badly, write a clean `refs.json` (`[{"raw", "doi", "title", "first_author", "year"}]`) and re-run `check_references.py --refs refs.json`.

### 3. Web detectors (only if the text may leave the machine)

Follow `references/web_detectors_guide.md`: the confidentiality rule, then the passages and the other splits through the tested tools (unattended: ZeroGPT, Undetectable, AIDetector.review, Scribbr, Plagiarism Checker X, the Binoculars demo; validated tools only with the user present to tick the CAPTCHA), a check of the parsed scores against the saved pages, and `python evidence.py`. Never work around a CAPTCHA, a login wall or a free limit.

### 4. Your part: confirm, verify, read

Write to `/tmp/ai_text_detection/judgements.json` (format in `grade.py`'s docstring):

- **Confirm every conclusive or strong hit in context.** A paper about LLMs may quote "As an AI language model"; a methods section may show a template. Set those aside with `"confirmed": false` and a reason.
- **Verify suspect references by hand.** For each `not-found`, `doi-not-registered` or `doi-points-elsewhere`, search the title (title only) with WebSearch, Google Scholar and PubMed style queries, and record `"fabricated": true/false` with what you searched. One real-but-obscure reference wrongly called fake would undermine the whole report.
- **Close reading.** Each finding needs a quote (exact words from the document: the report places the note beside them), a location and a way to check it. "Sounds like AI" is never a finding. Look for:
  - **Any kind:** specific claims that are wrong; numbers that contradict each other or the tables; invented facts (a dataset, guideline or trial that doesn't exist; search the name only); paragraphs that answer a prompt rather than build an argument; a sudden change of voice.
  - **Review of the user's manuscript:** criticism of what the manuscript doesn't contain, or requests for analyses it already has (quote both sides); as a cross-check, list for yourself the points a generic LLM review of this manuscript would make, and note how many of the review's points are those and how few are specific to the manuscript (the "anchor review" idea, Yu et al. 2026: a lead for where to look, not a finding by itself); no line, section or figure anchors; a summary that paraphrases the abstract; generic praise; requests that fit any paper.
  - **Grant:** aims that don't follow from the preliminary data; significance prose without numbers; "previous work" missing from the references; budget or timeline at odds with the aims.
  - **Collaborator draft:** untrue claims about the user's lab or shared results; citations that don't support their sentence (open one or two).

  Tiers: a verified false claim or invented fact is `strong`; a pattern backed by several quotes is `moderate`; a single observation is `weak`.
- **Provider watermark.** If the user has verification access (`references/watermarks.md`) and the text may leave the machine, ask whether they checked it, and record the result in `judgements.json` (`watermark`). The skill cannot request access; tell the user once that they can.
- **Optional author baseline.** When the author published before 2023, offer to compare with their own earlier writing. Find their OpenAlex id, show the user the match, and only with a yes run `baseline.py --openalex-author <ID> --first-author-only`. Prefer files the user supplies (`--files`, nothing leaves the machine). Abstracts are co-written: say the baseline is the group's style.

Then `python grade.py`.

### 5. Checkpoint 1: does the evidence hold up?

`python ledger.py record --case <label> --kind <kind> --context <context>`. Show the verdict line and each conclusive or strong finding (id, one line, quote), and ask in one multi-select `AskUserQuestion` which are false alarms (with "all valid"). Record each answer with `ledger.py finding`; set false alarms aside in `judgements.json` and re-run `grade.py`. Under a minute for the user.

### 6. The report

`python build_report.py --case "<label>" --kind <kind> --context <context>` writes `report.html`. Publish it as a private Artifact (icon `search`). The page shows, top to bottom: the share of the checked prose that reads as AI-written, the tier and the non-statistical checks; the text with AI-like sentences highlighted and close-reading notes tagged where they occur, beside each passage's combined score and each detector's scores; and the findings to quote from. For a file: `conda run -n ai-text-detection python report_pdf.py report.html <out.pdf>`.

Then tell the user, in a few lines: the tier and what it means; the two or three statements they can most safely make (from grade.json's statements); what the evidence does **not** show; and, if they want to raise it, to lead with the verifiable problems (fabricated references, false claims, leftover chatbot text) rather than "AI wrote this", addressed to the editor or programme officer for reviews and grants (COPE). Don't draft a message unless asked.

### 7. Checkpoint 2: how did the verdict land?

Ask one question: "Did the verdict match your own reading?" (too strong / right / too weak / something missing). Record it with `ledger.py verdict`. Close with: "When you learn what really happened, tell me and I'll record it. That's what improves the thresholds."

### 8. Learn (whenever there is feedback)

Change data before code, and test every change:

- **A new artefact or phrasing pattern:** add it to `markers.json` (id, tier, category, shows, source, at least one positive and one negative example); bump `version`.
- **A false alarm:** narrow the pattern and add the false-alarm text, paraphrased, as a negative example. A marker that keeps misfiring (`ledger.py stats`) is demoted.
- **The verdict felt too strong or too weak more than once:** adjust `grading.json`. Never retune a rule right after seeing the result it would change for the current case: say so, and apply the change from the next case.
- **A detector changed or a new one appeared:** update `web_detectors.json` and re-test it on known texts before it counts.
- **3 or more new labelled cases:** `python calibrate.py --with-local`; keep the new thresholds only if the human false-positive rate stays at its operating point.
- **A script change:** add a case to `examples/cases/` that reproduces the problem.

Then `python selftest.py` must pass, and `python record_feedback.py add --text "<what the user said>" --kind marker|grading|calibration|code|process --change "<what changed>"`. Repository changes go through a branch and a pull request on `ersilia-skills`. Never commit anything from `~/.ai-text-detection` or from a user's document.

## Maintenance (rarely)

- **Style score:** `build_corpus.py` builds the human windows (2015–2021 CC-BY Europe PMC abstracts and full texts, eLife decision letters, NIH RePORTER abstracts); `calibration/ai.jsonl` and `polished.jsonl` hold AI-written and AI-polished windows on the same topics. `python calibrate.py` fits the thresholds on human text only and writes `validation.md` (false-positive rates overall, by kind and for authors in non-English-speaking countries; detection rates by generator). Quote those numbers, not the papers'.
- **Web detectors:** monthly, and after any site change, re-run the known-text tests (`references/web_detectors_guide.md`, section 2).

## What this skill does not do

- Name which model wrote a text. Tool-specific artefacts appear only as provenance ("this token is produced by ChatGPT's search").
- Pay for detectors, create accounts, or work around a site's limits or CAPTCHAs.
- Send a manuscript or grant the user is reviewing to any website.
- Accuse anyone. It hands the user evidence and its limits.
