# Provider watermarks in AI-generated text

The one line of evidence that does not depend on style. Since the EU AI Act's Article 50(2)
began to apply (2 August 2026), the main providers embed a statistical watermark in the text
their models generate. Checked 17 November 2026.

| Provider | What is marked | Who can verify | How to ask |
|---|---|---|---|
| Anthropic (Claude) | Text from Claude models launched on or after 2 August 2026, and older models as they are added; less reliable with non-default sampling settings | Private preview: regulators, law enforcement, media, fact-checkers, independent researchers, educational organisations, EU civil society, some enterprises | Access request form linked from https://support.claude.com/en/articles/16266773 |
| OpenAI (ChatGPT, Codex: "textGrain") | Announced 5 October 2026 for ChatGPT and Codex users in the EU, rolling out; opt-in on the API | Approved research and academic organisations | Through OpenAI (no public form found) |
| Google (SynthID) | Gemini text | The public detector covers images, audio and video, not text | — |

## How the skill uses it

- **The skill cannot request access; the user can,** as an independent researcher. It is worth
  doing once: for recent Claude or ChatGPT text it is far stronger than any detector.
- When the user has access and checks a text, record the result in `judgements.json`:
  `"watermark": [{"provider": "Anthropic", "result": "detected in 3 of 4 passages", "date": "2026-12-01"}]`.
  Also enter a detection as a `reading` finding of tier
  `moderate` (one independent line: the text passed through that model, which may have been
  for translation or proofreading), and say exactly that.
- Confidentiality still applies: a manuscript or grant under review is not sent to a
  verification service either, unless the journal or funder does it.

## What a result shows

- **Detected:** the text was processed by that provider's model. Anthropic: "a signal that
  content was processed by Claude, but is not fully conclusive"; it also appears when the model
  only translated, proofread or summarised a human text. It says nothing about disclosure.
- **Not detected:** nothing. The text may be from an older or other model, or heavily edited,
  paraphrased, translated, very short, or generated with non-default settings. OpenAI's own
  figures: replacing a quarter of the words drops detection to about 17%.
