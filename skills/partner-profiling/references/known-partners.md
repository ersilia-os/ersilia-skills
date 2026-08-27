# Known partners — the do-not-resurface list

`scripts/filter_and_sort.py --known references/known-partners.md` drops any candidate
matching an entry here, because **an existing relationship is not a new opportunity**.
Without this list a sweep re-proposes the same institutions every quarter and the report
loses its credibility on first read.

## Format

**Only bullet lines inside the `## Entries` section at the bottom are read.** Everything
else in this file — including this explanation — is ignored. That restriction exists
because an earlier parser read every non-heading line, turning this prose into 26 spurious
"organisation name" entries. Keep prose out of `## Entries` and entries out of the prose.

An entry is matched as either:

- a **domain** (a token containing a `.` and no spaces) — matched against the candidate's
  `org_url`, falling back to `url`; or
- an **organisation name** — matched case- and punctuation-insensitively against the
  candidate's `org`, falling back to `name`.

Fenced blocks, HTML comments and non-bullet lines inside the section are skipped, `**bold**`
is stripped, and text after an em dash (`—`) is a per-entry comment:

```
- example.org — MoU signed 2025, contact via their comms lead
- Example Institute
```

Matching is at **organisation** level, deliberately. A new journalist at an outlet Ersilia
already works with is usually still a new opportunity, but the outlet-level suppression is
the safer default: it produces a visible "already-known" count in the run output, and the
`--keep-known` flag surfaces those rows tagged instead of dropped when you want to look.

## How to populate it

**This list ships empty and must be populated before the first real sweep.**
`config/CLAUDE.md` forbids inventing partner names, so nothing is seeded — an unverified
guess at Ersilia's own partners would be worse than an empty file, because it would
silently suppress real candidates.

Two ways to fill it:

- **By hand**, from the team's own knowledge — fastest, and enough to start.
- **From Airtable**, the real registry: `config/CLAUDE.md` describes the *Ersilia Content*
  base as holding partner organisations and contacts. That is the right long-term source
  of truth. Its connector was **not authorised** when this skill was written, so the
  export is not implemented — see "Future work" in `SKILL.md`.

A good first pass is to run one sweep with this list empty and populate it from whatever
the report surfaces that Ersilia already works with. The first sweep is a census as much
as a discovery run.

## Entries

<!-- Add entries below this line, one `- ` bullet each. Nothing else in this section. -->
