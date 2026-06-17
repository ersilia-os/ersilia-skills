# Claude Code Skills for Ersilia

A curated collection of Claude Code skills to help the Ersilia team work more effectively at three levels: technically, scientifically and operationally.

At a technical level we are using Claude to have a better maintenance of the Ersilia Model Hub, incorporating new models, fixing them, and tracking issues. At a scientific level it allows us to improve scientific literacy, helping us find relevant papers and summarizing them. At an organizational level it helps us improve our visibility and measure our impact on social media and also it is a support for finding new collaboration opportunities, and better tracking our partner collaborators and funders

---

## Skill Catalogue

At Ersilia, we have divided the skills we are developing according to four goals we want to achieve:
1. New connection with funders
2. Better public reach
3. Ersilia Model Hub Growth
4. Improve scientific literacy

Each set of skills is designed to help us achieve one of these four goals. Some skills are still being developed and tested by the Ersilia team, and once they are ready they will be listed and made available.

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
