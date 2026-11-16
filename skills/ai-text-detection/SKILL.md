---
name: ai-text-detection
description: >
  Assess whether a scientific article, grant proposal, peer-review report, response letter
  or email was written with ChatGPT, Claude, Gemini or another AI tool, and build a graded,
  defensible evidence report the user can rely on when pushing back. Checks conclusive
  artefacts (chatbot leftovers, oaicite / turn0search / [cite_start] tokens, utm_source=chatgpt.com,
  placeholders, leaked <think> tags, hidden prompt injections), verifies every reference
  against Crossref / DataCite / OpenAlex to catch fabricated citations, runs a compendium of
  web AI detectors (Pangram, GPTZero and others) chunk by chunk in Chrome when the text may
  leave the machine, plus calibrated stylometry (excess vocabulary such as
  "delve", "underscore", "meticulous"), and adds a close reading. Confidential manuscripts
  and grants under review are never sent to any website. Learns from the user's feedback on every finding and every
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
4. **Confidential text stays here.** Reading it from the user's own Google Drive through the connectors is fine: it is the user's own storage. Text chunks go to web detectors only under the rules in step 2b, and never for a manuscript or grant the user is reviewing. Otherwise only reference strings go out (Crossref, DataCite, doi.org, OpenAlex, arXiv), plus a reference title when you search by hand. Never paste the document into a web search or any external service. Uploading a confidential manuscript or grant would itself breach review confidentiality.
5. **Keep improving.** The user's feedback is the most valuable input, and the field moves fast. Ask for it at the three checkpoints below, every run, briefly. Record it with `ledger.py`. Turn it into changes to `markers.json`, `grading.json` and the calibration. Keep scanning for new tools too (`watch.py`).

## Files

Scripts live in `scripts/`. They run with any `python3`, except PDF/DOCX extraction and `browser_detect.py`, which need the small conda env: `conda run -n ai-text-detection python <script>`. The work folder is `/tmp/ai_text_detection/` and is reset each run. The private case ledger is `~/.ai-text-detection/`: numbers only, never text or names, never committed.

| Script | Does |
|---|---|
| `setup_env.sh` | One-time, only after the user agrees: small conda env `ai-text-detection` (pymupdf, python-docx, Playwright; tens of MB; no models) |
| `record_feedback.py` | Lists the lessons (`list`) or logs one (`add`) |
| `ledger.py` | The case ledger: `record`, `finding`, `verdict`, `outcome`, `pending`, `stats` |
| `drive_intake.py` | Google Drive links: file ID, the local Drive mount for PDF/DOCX, and revision-history summary |
| `extract_text.py` | PDF / DOCX / TXT / stdin to `text.json`: sections, pages, reference list, hidden text, metadata |
| `scan_artifacts.py` | Graded regex markers from `references/markers.json`, each hit quoted and located |
| `check_references.py` | Each reference looked up; statuses are `ok`, `metadata-mismatch`, `doi-points-elsewhere`, `doi-not-registered`, `not-found`, `unverifiable` |
| `stylometry.py` | Excess vocabulary, stock phrasing, em dashes, sentence uniformity; percentiles against human text; style score |
| `segments.py`, `evidence.py` | Several splits of the text (sections, passages, sliding windows); one combined, calibrated score per sentence, passage and document |
| `web_controls.py` | Runs the detectors on known human and AI texts; writes each tool's measured rates to `references/web_calibration.json` |
| `api_detectors.py` | Detectors with an API key (Pangram, GPTZero, Sapling, hosted Binoculars): no CAPTCHA; per-service approval |
| `web_detectors.py`, `browser_detect.py` | Web detectors (Pangram, GPTZero, …): prepare chunks, drive Chrome to run them, record and summarise scores (`references/web_detectors.json`) |
| `baseline.py` | Optional: the same author's pre-2023 writing (OpenAlex abstracts or files the user gives), scored the same way, to show a change in their own style |
| `grade.py` | Rules in `references/grading.json` produce the tier plus defensible statements |
| `build_report.py`, `report_raw.py` | The report: raw HTML, scores first, then the text with AI-looking passages highlighted; published as a private Artifact |
| `build_corpus.py`, `calibrate.py` | Build the human calibration corpus; fit the style-score thresholds; write `references/validation.md` |
| `watch.py` | Monthly scan for new leak tokens, web detectors and their limits, vocabulary lists, datasets, policies and skills (`references/watchlist.json`) |
| `selftest.py` | Offline regression test over `examples/cases/` and every marker's examples |

## Workflow

### 0. Pre-flight (every run)

1. `python record_feedback.py list`. Read every lesson and apply it.
2. `python ledger.py pending`. If earlier cases wait for an outcome, ask about them in **one** `AskUserQuestion`, e.g. "Did you hear back about case 2026-11-review-r2? AI / human / mixed / no news yet". Record answers with `ledger.py outcome`. This is how the skill learns what was true.
3. Every 5th case, or when `pending` shows 3 or more new outcomes, run `python ledger.py stats` and act on its SUGGEST lines (step 7).
4. **The small env.** `conda env list | grep ai-text-detection`. It is needed only for PDF/DOCX files and for driving Chrome. If it is missing, ask once before running `scripts/setup_env.sh` (tens of MB, no models). Without it, read Drive files through the connector, and skip the web detectors or use Claude in Chrome if it is connected.
5. **Watch for new tools.** `python watch.py due`. When a scan is due (monthly), do it before the intake and keep it short: run the listed searches, compare the results with what `markers.json`, `web_detectors.json`, `policies.json` and the corpus already have, and record each topic with `watch.py record` ("nothing new" counts). Then `watch.py done`. Turn anything worth adding into a concrete proposal for the user at step 7, e.g. a new leak token with its source, a web detector with new independent evidence or a changed free limit, or a new policy. Also do this between scans whenever you meet a tool or artefact the skill doesn't know.
6. `rm -rf /tmp/ai_text_detection && mkdir -p /tmp/ai_text_detection`.

### 1. Intake

You need four things. Ask only for what you can't infer, in one `AskUserQuestion`:

- **The document**: a Google Drive or Docs link (the usual case, see below), a path, an attachment, or pasted text. For pasted text, write it to `/tmp/ai_text_detection/input.txt`.
- **The kind**: `article`, `grant`, `review`, `response-letter`, `email` or `other`.
- **The context**: `collaborator-draft`, `reviewer-of-my-paper`, `manuscript-i-review`, `grant-i-review` or `other`. For a review of their paper, ask for their manuscript too: a reviewer's claims about it are then checkable. Claims about content the paper doesn't have are among the strongest evidence for reviews.
- **A neutral case label**, such as `2026-11-review-r2`. Never use a person's name.

**Google Drive links.** Use the Google Drive and Google Docs connectors; never ask the user to download the file.

1. `python drive_intake.py id "<link>"` gives the file ID. Then `get_file_metadata` (with `includeRichMetadata`) gives the name, type, owner, created and modified times. Keep these for the report's context, and check the 30 Nov 2022 rule against the created time.
2. **PDF or Word file:** first try `python drive_intake.py local "<name>"`. Google Drive for desktop is mounted on this machine, and a local copy keeps hidden text, fonts and metadata. If it isn't in the mount (files shared with the user often aren't), call `read_file_content` and write the text to `input.txt`. Say in the report that the hidden-text check was not possible from the connector text.
3. **Google Doc:**
   - Call `read_file_content` and write its text to `input.txt`. Use `--format txt` with `extract_text.py`: the connector renders headings and bold as Markdown, so Markdown leftovers can't be judged from it.
   - For the hidden-text check, call `read_doc` on documents up to about 30 pages and look for text runs with a white or near-white `foregroundColor` or a `fontSize` under 2 pt. Quote any you find in `judgements.json` `reading` as a `strong` finding, or as manipulation if it addresses an AI.
   - **Revision history:** call `list_file_revisions`. For a collaborator's draft, when the history is short (up to ~10 revisions), fetch the plain text of each revision (`download_file_content` with `revisionId` and `exportMimeType: text/plain`) and count its words. Write `[{"time", "author", "words"}]` to `/tmp/ai_text_detection/revlist.json`, then run `python drive_intake.py revisions /tmp/ai_text_detection/revlist.json`. Text that arrived in one block was written elsewhere. That is weak context only, because people also paste their own drafts.
4. **Comments:** don't read comments unless the user asks; they are not part of the text under test.
5. **Word files with tracked changes** (common for drafts that the user or colleagues have already edited): count the insertions and deletions per author (`unzip -p file.docx word/document.xml`, then count `<w:ins` and `<w:del` by `w:author`), and the document creator (`docProps/core.xml`). Ask which text to test. The usual answer is the author's original: `extract_text.py --original`, which removes tracked insertions and restores deletions, so the reviewers' own edits don't count against the author. Don't run `extract_text.py` on the plain file in that case: python-docx silently drops inserted text and keeps deletions out, which gives neither version.

If the text was written before 30 Nov 2022 (ChatGPT's release), say so and stop: it cannot be ChatGPT-era output.

### 2. Run the checks

```
python extract_text.py <file> && \
python scan_artifacts.py & python check_references.py & python stylometry.py & wait
```

Use `conda run -n ai-text-detection python extract_text.py` for PDF/DOCX. Show the section map and word count. Below 300 words, warn that the statistics are unreliable and lean on artefacts, references and reading.

If the reference list was split badly (the `[n/N]` lines show merged or broken references), write a clean `refs.json` (`[{"raw": ..., "doi": ..., "title": ..., "first_author": ..., "year": ...}]`) and re-run `check_references.py --refs refs.json`.

### 2b. Web detectors in Chrome: the statistical layer (you do it; the user shouldn't have to)

The user used to paste chunks into GPTZero, Pangram and others by hand. Do it for them, without asking them to open anything.

1. **Can the text leave the machine?** Pasting into a website uploads it.
   - **Yes:** the user's own or co-authored drafts (`collaborator-draft`), and public text.
   - **No, never:** `manuscript-i-review` and `grant-i-review`. Reviewer confidentiality forbids it (NIH, ERC, UKRI, Wellcome, ICMJE, Springer Nature). Say so in one line and skip this step.
   - **Ask first:** `reviewer-of-my-paper`, because the review is confidential to the journal.
2. `python web_detectors.py prepare` cuts the scored windows into 250–600-word chunks (`/tmp/ai_text_detection/web/chunk_k.txt`).
3. **Know the tools before trusting them** (`web_controls.py`). Each detector's weight comes from its results on known texts: published human scientific prose from before ChatGPT, AI-written texts (Claude and GPT), and AI-polished human text. These come from the calibration corpus and are public or written for this repository, so they can be sent anywhere. `references/web_calibration.json` keeps the rates: how often a tool cries wolf on human science, how often it catches AI, and its AUROC. Re-run it monthly and whenever a site changes: `python web_controls.py build`, the drivers with `--plan <controls.json>`, then `python web_controls.py analyze`. Always try a new site on control texts before the user's document.
4. **Split the text several ways** (`segments.py`): sections, passages, and sliding ~350-word windows that move forward half a window at a time. Each tool gets only the splits within its size range (`segments.py --for-tool <id>`). Run the drivers with `--plan /tmp/ai_text_detection/multi/plan.json --chunks <ids>`. A verdict that holds across splits is worth more than one that flips. Then `python evidence.py` combines every tool, weighted by its known-text results, and every split into one value per sentence, per passage and for the document. The report shows it as a heatmap, and `grade.py` uses it (`grading.json` "combined").
5. **APIs first, when a key is set** (`python api_detectors.py --status` sends nothing). An API avoids CAPTCHAs entirely. Pangram (validated) gives free research credits on application, GPTZero (validated) is paid, Sapling (context) has a free key, and the Binoculars authors host a free demo (context). The user creates keys; you never do. The first time any service would receive text, ask the user and record their yes with `--approved <service>`. Then run `python api_detectors.py --tools <ids>`.
6. **Drive the browser yourself** for the sites without an API key.
   - If Claude in Chrome tools are available in the session (`mcp__claude-in-chrome__*`), use them: open each site in `references/web_detectors.json` (`default_order`: Pangram, GPTZero first), paste each chunk, run it, read the result.
   - Otherwise run `conda run -n ai-text-detection python browser_detect.py --tools pangram,gptzero`. It opens the user's Google Chrome with a dedicated profile, pastes each chunk, presses the scan button, and saves each result page as text plus a screenshot. If Playwright is missing, ask once before `conda run -n ai-text-detection pip install playwright` (tens of MB; it uses the installed Chrome).
   - If a site shows a login wall the first time, run `browser_detect.py --login` once and tell the user which site wants them to sign in. The profile remembers it.
7. **Read every result yourself.** Sites with a parser in `web_detectors.json` ("parse") are read automatically, but check a sample of result pages against the parsed scores after any run, and every page when a site is new or changed. For the others, open the saved page text or screenshot, find the AI likelihood, and record it with `python web_detectors.py record --tool <id> --chunk <k> --score <0-1> --label "<what the site says>"`. The `guess` the script prints is only a hint. Then run `python web_detectors.py summary`.
8. **Respect each site's terms.** Sites marked `"terms": "no-automation"` (Clever AI Detector) are never driven by the script; offer to open the page so the user can paste a chunk by hand, and record what they read out. Many sites also mark the sentences they consider AI: `browser_detect.py` saves them, and the report shades those sentences in the text, naming the tool on hover.
9. **Never work around a CAPTCHA, a login wall or a free-use limit.** Record it with `web_detectors.py skip --tool <id> --why "..."` and move on to the next site. Keep a human pace, one document at a time.

`grade.py` reads the results:
- **Validated tools** (Pangram, GPTZero, Originality) that flag at least half of the words they scanned count as one moderate line of evidence. A tool counts only if it scanned at least half the text.
- **Two validated tools plus a non-statistical finding** (artefacts, references, close reading) make it strong.
- **Unvalidated tools** (Copyleaks, QuillBot, ZeroGPT) are weak context at most.
- **A validated tool that scores the text human** is reported as counter-evidence.

The report adds one row per tool and one column per tool in the passages table. The ledger keeps each tool's scores per case (`ledger.py record`), so its agreement with real outcomes builds up. That is how the tools are calibrated on the user's documents: running a corpus through them is ruled out by free limits and terms of use. Run the validated tools first; then context tools until at least two have run, so the consensus row means something.

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

`python build_report.py --case "<label>" --kind <kind> --context <context>` writes `report.html`: a deliberately raw page.
- **Scores first:** every number, with the threshold and the held-out error rate it is compared with.
- **A per-passage table:** each ~300-word window with its style score, each web detector's score for its chunk, and a flag.
- **The document's own text,** with only the AI-looking parts highlighted: shaded windows past the 5% or 1% thresholds, and marked artefacts, AI-typical words and stock phrasing. Everything else stays plain.
- **The findings,** then the limits.

Publish it as a private Artifact (icon `search`). `--style ersilia` gives the older designed page, only if asked. Then tell the user, in a few lines:

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

`build_corpus.py` builds the human windows: 2015–2021 CC-BY Europe PMC abstracts and full texts, eLife decision letters, and NIH RePORTER abstracts. `references/calibration/ai.jsonl` and `polished.jsonl` hold AI-written and AI-polished windows on the same topics, from several generators. `python calibrate.py` fits the style-score thresholds on human text only. `references/validation.md` reports:
- the false-positive rates on held-out human text: overall, by kind, and for authors in non-English-speaking countries;
- the detection rates on AI text, by generator.

Quote those numbers, not the papers' numbers. Web detectors are weighted by independent published evidence (`web_detectors.json`) and, over time, by the ledger.

## What this skill does not do

- It does not name which model wrote a text. Tool-specific artefacts appear only as provenance ("this token is produced by ChatGPT's search").
- It does not pay for detectors, create accounts, or work around a site's limits or CAPTCHAs.
- It never sends a manuscript or grant the user is reviewing to any website.
- It does not accuse anyone. It hands the user evidence and its limits.
