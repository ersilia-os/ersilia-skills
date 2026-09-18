# Slack alert template — published digest notification

Sent **once** after a successful publish to `ersilia-os/digests` — never on a failure, never
when the digest was rendered but not uploaded. The skill sends this only when
`scripts/upload_digest.py` exits 0.

## Channel

Workspace `ersilia-workspace`. **Channel: `#technology` — ID `C0100L3DRCM`.** Same channel as
the GitHub digest: this is model-hub work and the engineering team watches it there. (For
reference, the literature digest posts to `#literature` = `C010067BP2Q`.)

## Template

```markdown
📦 *New model incorporation digest — {Month YYYY}*

{n} models incorporated: {n} {Task} · {n} {Task} · {n} {Task}. All {n} {Status}.
{defects line}

Read it: {pages_url}
```

`{pages_url}` is the rendered GitHub **Pages** URL — the **first** line printed by
`upload_digest.py` (`https://ersilia-os.github.io/digests/models/{YY-MM-DD}-models-digest.html`).
Use it, not the github.com blob URL, which is the raw markdown.

## Field rules

- **Month** is the month reported on, not the month it was published.
- Counts come straight from the context JSON: `n_models`, `by_task`, `by_status`,
  `n_with_defects`. Never recount them by hand.
- **The defects line is the one thing the public page does not carry.** The digest published
  to the site has no defects section; this channel is internal, and the count is the part a
  reader can act on. Write `"{n} flagged for metadata repair."`, or `"Nothing flagged."` when
  the scan came back clean.
- Where a status is anything other than `Ready`, say so plainly rather than writing "All
  Ready" — a model that is not fetchable is the most important thing in the alert.
- Keep it to the three lines above. It is a pointer, not a summary. People click through.

## Worked example

```text
📦 *New model incorporation digest — August 2026*

10 models incorporated: 4 Representation · 4 Sampling · 2 Annotation. All 10 Ready.
3 flagged for metadata repair.

Read it: https://ersilia-os.github.io/digests/models/26-08-31-models-digest.html
```

## Rules of decorum

- The 📦 prefix is the only allowed emoji in the alert. It is the one the other digests have
  not taken — the GitHub digest uses 🛠️.
- **Do not name authors in the alert.** The digest credits them properly, with institution
  and venue; a Slack pointer that names two of ten authors and drops the rest credits nobody.
- **Do not name the Ersilia contributor** who did the incorporations, the same rule the
  digest itself follows.
- Do not post if the upload failed. Post exactly once per publish, including a `--force`
  re-publish, since the team should know the page changed.
