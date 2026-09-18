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

{n} models incorporated. The Hub now holds {catalog_size}.

*{Task}* ({n})
• {Title} — {First Author}, {Institution}{ (Ersilia note) }
• …

{one block per task category, in the digest's own order}

{status line}

Read it: {pages_url}
```

`{pages_url}` is the rendered GitHub **Pages** URL — the **first** line printed by
`upload_digest.py` (`https://ersilia-os.github.io/digests/models/{YY-MM-DD}-models-digest.html`).
Use it, not the github.com blob URL, which is the raw markdown.

## Field rules

- **Month** is the month reported on, not the month it was published.
- Counts come straight from the context JSON: `n_models`, `catalog_size`, `by_status`,
  and the per-task counts from `task_groups()`. Never recount them by hand.
- **List every model**, grouped by task in the same order the digest uses, so the alert and
  the page agree. A reader should be able to tell what shipped without clicking.
- **Name every model's first author and their institution**, using the same trimmed form
  the digest's Author column uses. All of them or none: an alert naming two of ten authors
  and dropping the rest credits nobody.
- **Say when Ersilia trained it.** Where `Source Type` is `Internal` or `Replicated`, the
  line carries a short parenthetical — "trained by Ersilia on their data",
  "re-implemented by Ersilia" — for the same reason the digest's paragraph does. Without it
  the alert reads as though the named authors built the served model.
- **Never mention metadata defects.** Not the count, not the identifiers, not a hint that
  any exist. They are repairs owed on somebody's model, they belong to
  `/model-incorporation-metadata` and not to this skill, and a channel post naming models as
  defective is the wrong place for them however internal the channel is. The alert points at
  a digest; it does not file work against other people.
- Where a status is anything other than `Ready`, say so plainly rather than writing "All
  Ready" — a model that is not fetchable is the most important thing in the alert. That is a
  fact about whether the models work, which is not the same as a metadata defect.
- It is longer than the other digests' alerts on purpose. A month of incorporations is ten
  or so items, and the first version of this alert said only how many there were, which told
  a reader nothing they could act on. Around 1,100 characters for a ten-model month is the
  right order.

## Worked example

```text
📦 *New model incorporation digest — August 2026*

10 models incorporated. The Hub now holds 254.

*Annotation* (2)
• Antimicrobial activity prediction from EU OpenScreen data — Ctibor Škuta, Czech Academy of Sciences (trained by Ersilia on their data)
• HADES Oral Drug-Likeness — Narek Petrosyan, Denovo Sciences

*Representation* (4)
• GLACIER Molecular Embeddings — Emily Nguyen, University of Southern California
• SAND Shape-Aware Descriptor — Robin Winter, Pfizer
• NaFM Natural Product Embeddings — Yuheng Ding, Peking University
• MolCompass Chemical Space Projection — Sergey Sosnin, University of Vienna

*Sampling* (4)
• CoCoGraph Formula-Preserving Generation — Manuel Ruiz-Botella, Universitat Rovira i Virgili
• CoCoGraph Small-Fragment Inpainting — Manuel Ruiz-Botella, Universitat Rovira i Virgili
• GenMol Scaffold Decoration — Seul Lee, KAIST
• PyMolGen Drug-Like Molecule Generation — Bruno N. Falcone, University of Nottingham

All 10 Ready.

Read it: https://ersilia-os.github.io/digests/models/26-08-31-models-digest.html
```

## Rules of decorum

- The 📦 prefix is the only allowed emoji in the alert. It is the one the other digests have
  not taken — the GitHub digest uses 🛠️.
- **Name every model's first author, or name none.** Crediting a subset is worse than
  crediting nobody. The alert names them all.
- **Do not name the Ersilia contributor** who did the incorporations, the same rule the
  digest itself follows.
- Do not post if the upload failed. Post exactly once per publish, including a `--force`
  re-publish, since the team should know the page changed.
