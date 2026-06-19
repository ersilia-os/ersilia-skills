# Slack alert template — published digest notification

Sent to `#literature` (workspace `ersilia-workspace`, channel ID `C010067BP2Q`)
after a successful push to `ersilia-os/digests`. The skill only sends this when
`scripts/upload_digest.py` exits 0 — never on dry-run, never on failure, never on
the `--no-readme` path mid-step.

## Template

```markdown
📚 *New literature digest — week of {YYYY-MM-DD}*

{N} items across {N_chapters} chapters: {chapter_names_short_list}.

Read it: {pages_url}
```

`{pages_url}` is the rendered GitHub **Pages** URL — the **first** line printed by
`upload_digest.py` (`https://ersilia-os.github.io/digests/literature/{YY-MM-DD}-literature-digest.html`).
Use it, not the github.com blob URL — it's the reader-friendly page.

## Field rules

- **Date** is the ISO-format end date of the digest window.
- **N items** is the total number of bullets across all chapters in the digest.
- **N_chapters** counts non-empty chapters only. Skip the empty ones.
- **chapter_names_short_list** is a comma-separated list of the chapter
  headings the digest actually rendered, in display order. Drop the long
  prefix; use the short forms below.

### Chapter short forms

Use these inside the chapter-name list so the message stays compact:

| Full heading | Short form for Slack |
|---|---|
| AI agents and foundation models for science | AI agents & foundation models |
| AI/ML methods for drug discovery | AI/ML methods |
| Antibiotic and antimicrobial discovery | Antibiotics & AMR |
| Global health and open science | Global health & open science |

## Worked example

```text
📚 *New literature digest — week of 2026-05-21*

17 items across 4 chapters: AI agents & foundation models, AI/ML methods, Antibiotics & AMR, Global health & open science.

Read it: https://ersilia-os.github.io/digests/literature/26-05-21-literature-digest.html
```

## Rules of decorum

- The 📚 prefix is the only allowed emoji. Do not add others.
- Do not name team members, do not mention internal channels other than what
  Slack will surface itself by routing the post.
- Do not include the digest summary or any cherry-picked highlights — the
  message is a pointer, not a substitute for the digest. People click through.
- Do not post if the upload failed or was a dry-run; **only** on a confirmed
  successful push.
