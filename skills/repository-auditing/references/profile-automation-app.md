# Profile — Automation and App

Two small types sharing one profile because they overlap heavily and neither has a template.
`Type = Automation` is 14 of 179 repos, `Type = App` is 8. There is **no `eos-*` template for
either**, so the standard here is derived from the best existing examples rather than quoted
from a `CLAUDE.md`. Treat these checks as softer than the Package and Analysis ones, and lean
on the LLM judgement pass.

## Automation

Reference examples: `ersilia-maintenance` (16 workflows, 805 commits — the busiest automation
repo in the org), `ersilia-model-workflows` (10 workflows, the reusable-workflow library that
every model repo calls into), `ersilia-self-service`, `digests`.

### What good looks like

- A short README that lists **what each workflow does and when it runs**. `ersilia-maintenance`
  does this well with a "Workflows Overview" plus a "Workflow Schedule" table;
  `ersilia-model-workflows` keeps it to 32 lines. Either length is fine — the test is whether a
  newcomer can tell which workflow to look at without opening `.github/workflows/`.
- Reusable workflows factored out and called with `uses:`, rather than copy-pasted YAML. This is
  the established house pattern: all five workflows in `eos-template` are thin wrappers around
  `ersilia-os/ersilia-model-workflows@main`.
- Third-party actions pinned to a tag or SHA. **First-party `ersilia-os/*` reusable workflows at
  `@main` are deliberate** — that is how model repos pick up workflow fixes without a fleet-wide
  bump. Report those as informational, never as a finding.
- Guards so a template or fork does not fire the automation. `eos-template` uses
  `if: github.repository != 'ersilia-os/eos-template'` on three of its five workflows.
- Secrets referenced as `${{ secrets.NAME }}`. The skill lists the names it finds for human
  review — it cannot verify a secret exists, and says so rather than implying a pass.

### Known smells to catch

- `ersilia-maintenance` commits a `.DS_Store` and uses H1 for every README section
  (`T0-JUNK-TRACKED`, `T0-HEADING-LEVELS`).
- A workflow with a `schedule:` trigger whose cadence appears nowhere in the README — the most
  common real defect in this type. Someone has to know a cron exists before they can debug it.
- Credential-shaped literals in YAML. Always a Blocker.

## App

Reference examples: `h3d-screening-cascade-app`, `pharmacogx-app`, `ersilia-app`.

### What good looks like

- A documented way to run it: a `Dockerfile`, a `docker-compose.yml`, a `Procfile`, or an
  explicit start command in the README. Whichever it is, the README has to name it.
- A deployment note — where this is hosted and how it gets there.
- A `.gitignore`, which for a web app means `node_modules/`, build output, and `.env`.
- The same T0 baseline as everything else: real README, LICENSE, footer, `CLAUDE.md`.

### Known smells to catch

`ersilia-app` is the negative test case for this profile and should light up: a **3-line
README**, no `.gitignore` at all, and no About-Ersilia footer. It has a `Dockerfile`, so
`APP-NO-ENTRYPOINT` should pass while `APP-NO-RUN-DOCS`, `T0-README-STUB`,
`T0-GITIGNORE-MISSING` and `T0-FOOTER-MISSING` all fire. If a change to this profile makes
`ersilia-app` look clean, the change is wrong.

## Language caveat

Apps are frequently not Python. Skip the Python-specific machinery — ruff, docstrings, pytest,
`pyproject.toml` — unless tracked `.py` files actually exist, and record the skip in the report's
Skipped checks section so the gap is visible rather than silently absent. The same applies to an
Automation repo that is nothing but YAML: most of the code checks legitimately have nothing to
run against, and saying so is more useful than reporting a clean pass.
