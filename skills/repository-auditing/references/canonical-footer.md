# Canonical README footer

Every ersilia-os repository must close with the **About the Ersilia Open Source Initiative**
section below. This is the byte-identical footer shipped by `eos-python-package` and
`eos-analysis-template` — the two templates new repositories are generated from — and is
therefore the standard the audit enforces.

It is **pure Markdown**. There is no `<img>` tag, no `<div>`, and no License line inside the
footer (license belongs in the `LICENSE` file, and — for repos that have something to say —
in its own section above the footer).

## The block

```markdown
## About the Ersilia Open Source Initiative

The [Ersilia Open Source Initiative](https://ersilia.io) is a tech-nonprofit organization fueling sustainable research in the Global South. Ersilia's main asset is the [Ersilia Model Hub](https://github.com/ersilia-os/ersilia), an open-source repository of AI/ML models for antimicrobial drug discovery.

![Ersilia Logo](assets/Ersilia_Brand.png)
```

## Rules

1. **Heading.** `## About the Ersilia Open Source Initiative`. `## About Us` and
   `## About us` are tolerated legacy variants (`ersilia`, `stylia`, `zaira-chem`,
   `ersilia-model-workflows` use them) — report as drift, not as a missing footer.
2. **Position.** It must be the **last** section of the README. Nothing but the logo line
   follows it. A `# TODO` backlog after the footer (as in `eosquality`) is a finding.
3. **Logo.** A logo image must be present and must resolve. With the relative path above,
   `assets/Ersilia_Brand.png` has to exist in the repo. A `raw.githubusercontent.com` URL
   is an accepted alternative (it renders on PyPI and in forks) — reported as drift only.
4. **Wording.** Diff the paragraph against the canonical text. Any change is drift. The
   known drifted phrasings in circulation, all of which should be reported:
   - `tech-nonprofit` without `organization` (`eosquality`)
   - `for drug discovery` instead of `for antimicrobial drug discovery` (`eosquality`)
   - the charity-number / LMIC paragraph (`pharmacogx-embeddings`, `compound-embedding`,
     `ersilia-model-workflows`)
   - the GitBook-and-GitHub one-liner (`chembl-antimicrobial-tasks`,
     `mtb-targeted-protein-degradation`)
   - the decolonised-research paragraph plus a Funding subsection (`ersilia`)

## Why the templates win

Four different About-Ersilia paragraphs are in circulation across the org and no single one
was ever declared canonical. The template wording is the one every newly generated repository
starts with, so standardising on it means the audit pushes the org toward convergence rather
than away from it. Repos with the funder-logo footer (`ersilia`, which carries MICIU/AEI
attribution required by its grant) legitimately need extra content — that belongs in a
`### Funding` subsection **inside** the About section, and is not a finding.
