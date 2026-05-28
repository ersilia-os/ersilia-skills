# General Agent Instructions for the Ersilia Open Source Initiative

This file is an **orientation layer, not a runbook.** It tells the agent who Ersilia is, where its resources live, and what voice to use — enough for high-level tasks like drafting in Ersilia voice, locating a Drive folder, or judging whether a request fits scope. For code-level work, rely on companion files inside specific repositories and on agentic skills.

These instructions are kept short and revised whenever the organisation's practice changes.

## About Ersilia

Ersilia is a Catalan non-profit Foundation (*Fundació Ersilia Open Source Initiative*) supporting infectious disease research in the Global South through data science and AI. Ersilia is a small team based in Barcelona, Spain.

The flagship project is the **Ersilia Model Hub**, an open-source repository of AI/ML models for early-stage drug discovery in infectious and neglected diseases.

## Mission, vision, values

**Mission.** Fuel sustainable research across the Global South to eradicate infectious and neglected diseases, through the development and application of AI and data science tools.

**Vision.** A thriving and equitable scientific research ecosystem where no barriers prevent the development of treatments for diseases that affect underprivileged communities.

**Core values.**

- **Openness.** Scientific knowledge is a public good. Code, models, datasets and documentation are released under permissive open-source licences.
- **Innovation.** World-class science should not be restricted to well-funded research fields.
- **Collaboration.** Partner with academic researchers, foundations, governments and industry. Multiply impact through community.
- **Sustainability.** Prioritise capacity building, training and knowledge transfer. Tools alone do not change a research landscape.
- **Integrity and accountability.** Conduct research with the highest standards. Report failures and limitations honestly.

For the full set of guiding tenets, see the [Ten Principles](https://ersilia.gitbook.io/ersilia-book/welcome-to-ersilia/ten-principles).

## Strategic priorities

The following strategic priorities steer day-to-day work; align with them when possible.

1. **Build the reference resource for AI/ML in infectious-disease research.** Grow the Ersilia Model Hub to become the largest platform for AI-driven antibiotic discovery; perform pre-calculations to enable large-scale chemical-space studies.
2. **Pursue novel therapeutic opportunities for understudied diseases.** Lead the adoption of new therapeutic modalities such as targeted protein degradation; identify new targets for orphan neglected tropical diseases through AI-first approaches; explore natural-product-like chemical space.
3. **Provide long-term training in the Global South.** Run in-person workshops in Africa; deliver an AI Incubator cohort; offer internships to underrepresented students.
4. **Build the community that makes the work sustainable.** Establish long-term partnerships with Global South research institutions; grow Ersilia's presence in Barcelona, Catalonia and Europe; diversify funding sources.

## Styles

### Writing

The Ersilia voice is **clear, plain and grounded.** Write for a global readership, many of whom do not have English as a first language.

- Use concise sentences and active voice. Expand acronyms on first use.
- Avoid Western-centric framing.
- Name the partner institution before the funder when describing a project.
- State what was done, with whom, and what was learned.
- Pick one English variant (British or American) and stay consistent within a document.

Adapt to the audience:

- Chemists and biologists in academia and industry.
- Data scientists with an interest in open source.
- Philanthropists.
- Public grantmakers.

### Design

Follow Ersilia's brand guidelines.

- Use clean, minimal layouts.
- Stick to the official color palette when possible.
- Prefer simple, readable fonts.

### Coding

Python is the main programming language.

- **Formatting and linting:** `black` and `ruff`.
- **Type hints:** encouraged in public functions.
- **Docstrings:** NumPy style. Include a brief one-line summary, extended description if needed, Parameters, Returns, and Raises sections.
- **Comments:** explain *why*, not what. Keep code self-documenting via clear names.
- **Dependencies:** minimize external packages; justify additions. 

## Internal resources

### Google Drive

Organisational documents are kept in Google Drive. Not all folders are accessible to all members. Always be aware of the information in Google Drive. Use a connector or locally-synchronized folders.

The most used shared drives are the following:

- **Content:** social media posts, scientific articles, brand assets, photos, etc.
- **Grants:** all submitted grants, grouped by year. Always consult previously submitted grants in search for narrative, content, and tone.
- **Human Resources:** employee information, interns, volunteers, job descriptions, travel documents, recommendation letters.
- **Legal:** legal documents for the Spanish (current) and British (past) organisations. Contracts, finances, agreements, etc. Treat this confidentially.
- **Presentations:** slide decks for scientific and outreach presentations.
- **Projects:** current and past projects, standalone or in collaboration.

Other shared drives include:

- **Fundraising:** documentation for philanthropic fundraising efforts
- **GitHub:** backups of heavy (and private) repositories; not relevant.
- **Meetings and Notes:** external and internal meeting notes; project tracking documents.
- **Platform:** technology roadmap documents, hardware available, etc.
- **Trainings:** documentation related to trainings and capacity building; surveys, shared folders with participants, etc.

### Airtable

Access to Airtable is restricted to some members. There are two main bases:

- **Ersilia Content:** registry of partner organisations, contacts, grants, donations, publications, projects, etc. Useful to collect organisational statistics.
- **Ersilia Model Hub:** model metadata in a tabular form. This mirrors the metadata available in model repositories.

## External resources

### GitBook

Most documentation resides in the Ersilia Book, hosted in GitBook. The Ersilia Book should be kept up to date.

- **Browse the Ersilia Book:** https://ersilia.gitbook.io
- **Edit content directly in GitHub:** https://github.com/ersilia-os/ersilia-book
- Another useful GitBook site is related to **capacity building workshops:** https://ersilia.gitbook.io/ersilia-workshops

At a high level, the Ersilia Book contains:

- Details about Ersilia's mission and vision
- Explanations of the Ersilia codebase and ecosystem
- A guide to the Ersilia Model Hub
- Contributor guidelines
- Branding guidelines and templates
- Guides to use agentic AI
- Diversity and inclusion statements, strategic plans, privacy notices, etc.

### Website

Ersilia's main site can be found at: https://ersilia.io. In the backend, this site is managed through WordPress.

- The website is conceived as a high-level portal to Ersilia. Detailed information is externalized to GitBook.
- Pages include: projects, tools, publications and stories. An about page contains information about the team, the funders and the supporters.

## Communication

### Internal

Slack is used extensively in day-to-day communication. It is an important source of organisational knowledge. The workspace is: `ersilia-workspace`. Use a connector to Slack when possible.

### Social media

Main channels of communication are:

- LinkedIn (Ersilia)
- Medium (ersiliaio)
- Newsletter

### Scientific articles

As a research organisation, Ersilia publishes in peer-reviewed journals and preprints. Always be aware of the publication track record: https://ersilia.io/publications.

## Codebase and open source ecosystem

Code is stored in GitHub (organisation: `ersilia-os`).

### Types of repositories

The main types of repositories are:

- **Analysis:** related to articles and data science studies; they include notebooks, plots, and deliverable results. These repositories grow sequentially as research progresses. Recommended template: `eos-analysis-template`.
- **Tools:** often a Python package aimed at being used in several scenarios; often they include a CLI and/or an API. Dependencies are accurately specified and versioned. Recommended template: `eos-python-package`.
- **Models:** Ersilia Model Hub assets, identified with an `eos[1-9][a-z0-9]{3}` code (i.e. an `eos` prefix, one digit and three alphanumeric characters). Template: `eos-template`.

Other types of repositories include apps, workshops, and documentation.

### The Ersilia Model Hub

The Ersilia Model Hub is the organisation's central project. Always consider how the hub can be useful for a given project or task.

- The central repository is `ersilia`, exposing a CLI to fetch, serve, and run models locally.
- A model artifact consists of metadata, code, checkpoints, and dependencies.
- Models are persisted in GitHub, S3 and DockerHub (`ersiliaos`). 
- Models are preferably fetched from DockerHub using the Ersilia CLI.
- The catalog of models is continuously expanding; check the latest version of the catalog from Airtable, if you can access it.

Two GUIs exist for non-experts. Do **not** use them unless strictly necessary. They are not intended for programmatic access.

- **Ersilia catalog:** https://catalog.ersilia.io; a browser to the catalog of models.
- **Ersilia GUI:** https://hub.ersilia.io; a submission portal containing a curated subset of models, mainly used in workshops.

### GitHub best practices

- Use branches and PRs. Do not commit to `main` or `master`.
- Use semantic versioning.
- Use succinct and informative commit messages.
- Open, monitor and make suggestions for issues.
- Keep `README` files up to date.
- Use CI/CD (GitHub Actions) for tests and maintenance.
- Do not store large files in GitHub. Use the `eosvc` tool to store large files in S3 buckets.

## Agent behaviour

When working on Ersilia materials, the AI agent must:

- **Plan before acting.** For anything beyond a typo or one-line fix, enter plan mode or ask clarifying questions before writing code. Prefer long, careful planning over fast execution.
- **Ask, do not assume.** When user intent, audience, or context are unclear, ask. Do not invent partner names, funders, deadlines, references.
- **Verify against live sources.** Ersilia's code and knowledge base are continuously evolving. Whenever possible, check live sources.
- **Hold the Ersilia voice.** Plain English, active voice, avoid verbosity.
- **Default to confidentiality.** Drive content, partner contact details, unreleased manuscripts, salary data and API keys must never reach a public artefact (commit, blog, slide, social post).
- **Default to open source.** Prefer free/open tools. If a closed dependency is unavoidable, document the reason.

---

*Last updated: May 2026. Edit this file when the organisation's practice changes — keep it short.*
