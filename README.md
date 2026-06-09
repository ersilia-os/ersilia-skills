# Claude Code Skills for Ersilia

A curated collection of Claude Code skills to help the Ersilia team work more effectively across programmes, science, visibility, platform, and day-to-day operations.

> **Early-stage repository (v0)**
>
> This is Ersilia's first attempt to build a systematic library of Claude Code skills. The structure and categories are intentional, but most skills are currently **scaffolded** — they define the workflow and accept the right arguments, but have not yet been fully developed, tested, or validated for production use.
>
> Skills are being built incrementally. Each skill will be reviewed and promoted through the maturity stages (`scaffold → draft → ready`) before it is relied upon. Please check the status column in the catalogue below before using a skill in critical workflows.

---

## What are Claude Code skills?

Claude Code skills are reusable workflow definitions stored as `SKILL.md` files. When this repository is installed as a Claude Code plugin, each skill becomes a slash command available in any Claude Code session. Skills encode step-by-step instructions, argument handling, and references to supporting knowledge-base documents — teaching Claude how to perform a specific Ersilia workflow reliably and consistently.

## Why Ersilia is building skills

Ersilia's work spans science, technology, communications, and operations. Much of the team's expertise lives in people's heads or in scattered documents. Skills are a way to encode that institutional knowledge into reusable AI workflows — making expert-level processes accessible to every contributor, reducing onboarding friction, and ensuring consistent quality across the organisation.

---

## Skill Catalogue

At Ersilia, we have divided the skills we are developing and using into several categories, according to what we use them for. 
They are still being developed and tested by the Ersilia team, and once they are ready they will be listed and available

**Status definitions**:
- `scaffold` — structure and arguments defined; workflow written but not tested or validated
- `draft` — skill has been used and iterated on; mostly reliable but still evolving
- `ready` — skill has been reviewed, tested, and is considered reliable for regular use

---

## Repository Structure

```
claude-ersilia-skills/
├── .claude-plugin/
│   └── plugin.json                     # Plugin manifest
├── skills/
│   ├── slack-summaries/
│   │   ├── SKILL.md                    # Skill definition
│   │   └── references/                 # Supporting knowledge-base files
│   ├── grant-tracking/
│   ├── model-incorporation/
│   └── ... (25 skills total)
└── README.md
```

Each skill follows the same layout: a `SKILL.md` file containing the workflow definition, and a `references/` folder for any supporting documents the skill reads at runtime (e.g., brand guidelines, metadata vocabularies, knowledge bases).

---

## How Skills Are Structured

Every `SKILL.md` file has two parts:

**Frontmatter** — machine-readable metadata:
```markdown
---
description: One-line description of what the skill does
argument-hint: <required-arg> [--optional <value>]
allowed-tools: [Read, Write, WebFetch, Bash, ...]
---
```

**Body** — the workflow Claude follows: argument parsing, step-by-step instructions, output format, and any important rules or constraints.

The `references/` folder holds supporting files that the skill reads using the `Read` tool at runtime — for example, a brand guidelines document for the `branding` skill, or a metadata vocabulary for `model-incorporation`.

---

## Installation

### Local setup (recommended for contributors)

After cloning the repo, run once:

```bash
bash setup.sh
```

This creates a symlink in `~/.claude/skills/` for each skill folder, so skills are immediately available as slash commands in Claude Code. Any personal skills you already have there are left untouched. A `post-merge` git hook is also installed, so whenever you `git pull` and new skills are added, they are linked automatically — no manual re-run needed.

### Remote plugin (read-only access)

If you only need to use the skills without a local clone, add this to your Claude Code configuration (`~/.claude/settings.json`):

```json
{
  "plugins": ["https://github.com/ersilia-os/ersilia-skills"]
}
```

### Using skills

Once installed, skills are available as slash commands in any Claude Code session. For example:

```
/model-incorporation https://github.com/org/model-repo --paper https://doi.org/...
/literature-review "graph neural networks for antimicrobial resistance" --since 2022
/email-drafting "pitch to a potential funder" --to "Gates Foundation"
```

---

## Contributing a Skill

Skills are added and improved through pull requests. To contribute:

1. Create a folder at `skills/<category>/<skill-name>/`
2. Add a `SKILL.md` with valid frontmatter (`description`, `argument-hint`, `allowed-tools`) and a step-by-step workflow body
3. Add a `references/` subfolder (can be empty initially, with a placeholder `README.md`)
4. Open a pull request — new skills start at `scaffold` status
5. Skills are promoted to `draft` once they have been used and iterated on, and to `ready` once reviewed and validated

Please keep skills focused on a single, well-defined task. If a workflow is too broad, consider splitting it into multiple skills.

---

## About Ersilia

The [Ersilia Open Source Initiative](https://ersilia.io) is a tech non-profit with the mission to equip laboratories, universities, and clinics in the Global South with AI/ML tools for infectious disease research. Ersilia operates according to the principles of open science, decolonized research, and egalitarian access to knowledge.

The [Ersilia Model Hub](https://github.com/ersilia-os/ersilia) is Ersilia's flagship project — a unified platform of pre-trained AI/ML models for infectious and neglected disease research, covering areas such as antibiotic activity prediction, ADMET prediction, molecular representation, and generative chemistry.

---

## License

GPL-3.0. See [LICENSE](LICENSE) for details.
