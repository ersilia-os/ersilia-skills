# Running the web detectors

The statistical layer of the skill: free web AI detectors, run by the skill itself (the
user used to paste chunks by hand), tested on known texts, and combined across several
splits of the document. SKILL.md step 3 points here.

## 1. May the text leave the machine?

Pasting into a website uploads it.

| Context | Rule |
|---|---|
| `collaborator-draft`, public text | Yes |
| `reviewer-of-my-paper` | Ask first: the review is confidential to the journal |
| `manuscript-i-review`, `grant-i-review` | **Never.** Reviewer confidentiality forbids it (NIH, ERC, UKRI, Wellcome, ICMJE, Springer Nature). Say so in one line and skip this whole step |

The first time any service would receive text, ask the user, and record the yes
(`api_detectors.py --approved <id>`). Never create accounts or API keys.

## 2. Know the tools before trusting them

A tool counts only after it has been run on known texts (`web_controls.py`; results in
`web_calibration.json` and `web_validation.md`). Always try a new or changed site on the
control texts before the user's document. Re-run monthly (`watch.py`) and after any
visible site change:

```
python web_controls.py build                         # human, AI and AI-polished controls
python web_controls.py shuffle                       # memorisation check
python web_controls.py domain --query "<Europe PMC query for the document's field>"
conda run -n ai-text-detection python browser_detect.py --plan /tmp/ai_text_detection_controls/controls.json --tools <ids>
#   ... the same for shuffled.json and domain.json
python web_controls.py analyze
```

Formulaic technical prose is where false alarms happen, so a tool's rate on the document's
own field is the one that matters: add domain controls whenever the field is new.

## 3. Split the document several ways

```
python web_detectors.py prepare      # passages P1.. (the unit the report shows)
python segments.py                   # sections S1.., passages, overlapping windows W1..
python segments.py --for-tool <id>   # the unit ids within that tool's size limits
```

A verdict that holds across splits is worth more than one that flips with the cut.

## 4. Run them

**API first** when the user has set a key (`python api_detectors.py --status` sends
nothing). The Binoculars demo needs no key.

```
python api_detectors.py --tools binoculars
python api_detectors.py --tools binoculars --plan /tmp/ai_text_detection/multi/plan.json --chunks <ids>
```

**Then the browser,** for the passages and then for the other splits:

```
conda run -n ai-text-detection python browser_detect.py --tools zerogpt,undetectable,aidetector_review,scribbr,plagiarismcheckerx
conda run -n ai-text-detection python browser_detect.py --plan /tmp/ai_text_detection/multi/plan.json --tools <id> --chunks <ids from segments.py --for-tool>
```

It opens the user's Chrome with the skill's own profile. If Claude in Chrome is connected
in the session (`mcp__claude-in-chrome__*`), it can be used instead, following the same rules.

The validated tools (Pangram, GPTZero, Originality) show a CAPTCHA to automated use. Run
them only while the user is at the computer, with `--human-wait 120`, so the user ticks
the box in the open window. Never tick it for them.

## 5. Read the results

Sites with a parser (`"parse"` in `web_detectors.json`) are recorded automatically. After
every run, open a sample of the saved result pages and screenshots (`<work>/web/`,
`<work>/plan/`) and check them against the recorded scores; check every page when a site
is new or changed. For a site without a parser, read the page and record it:
`python web_detectors.py record --tool <id> --chunk <k> --score <0-1> --label "<what it says>"`.

Then combine: `python evidence.py`. It prints which tools were counted, the document's and
each passage's combined value, and how often each tool's verdict depends on the split.

## 6. Site rules

- **Never work around** a CAPTCHA, a login wall or a free-use limit. Record it with
  `web_detectors.py skip --tool <id> --why "..."`, update the tool's `automation` status in
  `web_detectors.json`, and move on.
- **Terms:** a site marked `"terms": "no-automation"` (Clever AI Detector) is never driven by
  script. Offer to open it so the user can paste a passage by hand.
- **Cookies:** the script declines non-essential cookies. It accepts them only on sites where
  the user approved it (`"cookies": "accept"`).
- **Pace:** a human pace (`--pace`, several seconds between scans), one document at a time.

## 7. Keep looking

New detectors appear and free tiers change every month. When the monthly scan (`watch.py`)
or a run turns up a site the registry lacks, add it to `web_detectors.json` with what is
known about its evidence, probe it on one control text, and calibrate it before it counts.
