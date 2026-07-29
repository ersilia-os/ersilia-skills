# Claude Code Skills for Ersilia

A curated collection of Claude Code skills to help the Ersilia team work more effectively at three levels: technically, scientifically and operationally.

At a technical level we are using Claude to have a better maintenance of the Ersilia Model Hub, incorporating new models, fixing them, and tracking issues. At a scientific level it allows us to improve scientific literacy, helping us find relevant papers and summarizing them. At an organizational level it helps us improve our visibility and measure our impact on social media and also it is a support for finding new collaboration opportunities, and better tracking our partner collaborators and funders

---

Skill Catalogue

At Ersilia, we have divided the skills we are developing according to three goals we want to achieve:

Better public reach
Ersilia Model Hub Growth
Improve scientific literacy

Each set of skills is designed to help us achieve one of these three goals. Some skills are still being developed and tested internally by the Ersilia team; once they are ready, their code will be made public in this repository. Each skill follows the same layout: a SKILL.md file containing the workflow definition, and a references/ folder for any supporting documents the skill reads at runtime (e.g., brand guidelines, metadata vocabularies, knowledge bases).

1. Better public reach
Name	Skill
event-discovery	Discovers interesting events for Ersilia and writes a summarised report, classified by category (local/global, science/philanthropy, etc.).
stylia-plotting	Documents how to create Python plots using the stylia package — Ersilia's matplotlib wrapper for publication-ready figures.
2. Ersilia Model Hub Growth

Several of these skills are designed to be chained together as part of a larger workflow rather than run in isolation:
Model incorporation pipeline — model-incorporation-request, model-incorporation-metadata, model-incorporation-code, and model-incorporation-reproduce cover the full lifecycle of bringing a new model into the Hub, from opening the initial request to verifying it reproduces the original paper's results. They are meant to be run in sequence.

---

## How Skills Are Structured

Every `SKILL.md` file has two parts:

**Frontmatter** — machine-readable metadata. `name` must match the skill's folder name, and is
what you type as the slash command:
```markdown
---
name: skill-name
description: >
  What the skill does and when to use it. Write it in the third person and end with an
  explicit list of trigger phrases — this text is what Claude matches against a request.
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

1. Create a folder at `skills/<skill-name>/` — skills sit directly under `skills/`, with no category level
2. Add a `SKILL.md` with valid frontmatter (`name`, `description`, and optionally `argument-hint` and `allowed-tools`) and a step-by-step workflow body
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
