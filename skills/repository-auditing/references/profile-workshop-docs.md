# Profile — Workshop and Documentation

Two small types sharing one profile. `Type = Workshop` is 11 of 179 repos, `Type = Documentation`
is 3. Neither has an `eos-*` template. These are the types where a rigid checklist does the most
damage: a workshop repo has no package to lint, and holding it to the Package bar produces
nothing but noise. Keep the audit to T0 plus the handful of checks below, and let the LLM
judgement pass carry most of the weight.

## Workshop

Reference examples: `event-fund-ai-drug-discovery` (10 stars, the most-starred workshop repo),
`ai2050-dd-workshop`, `python-101`, `ersilia-intro-workshop`, `outreachy-contributions`.

### What good looks like

- The README says **who this is for and how to use it**. A workshop repo is read by someone who
  was not in the room — often years later. This is the single most valuable thing on the page,
  and it is what `WSH-NO-AUDIENCE` looks for.
- The date or edition is discoverable, in the README or in a directory name. Workshop material
  ages, and a reader needs to know whether they are looking at the 2024 or the 2026 run.
- Sessions or modules in a predictable order, so the material can be followed unattended.
- A reuse statement. Most of these repos are meant to be picked up and taught by others, which
  the `LICENSE` file alone does not communicate — hence `WSH-NO-LICENSE-STATEMENT`, kept at
  Nice-to-have.

### What not to report

No tests, no CI, no `pyproject.toml`, no ruff config, no docstrings. Notebooks with committed
outputs are **fine here** — for teaching material, saved outputs are usually the point, so
`ANA-NOTEBOOK-OUTPUTS` does not apply to this type. Do not flag a short README either: brevity
is correct, and `T0-README-STUB` (fewer than 10 lines) is the only floor.

## Documentation

Reference examples: `ersilia-book` (the GitBook source, 52 commits, and one of only three repos
org-wide with a `CLAUDE.md`), `eos-demo`, `illness-metaphors`.

### What good looks like

- Navigation and content agree. For a GitBook repo, `SUMMARY.md` is the source of truth: every
  entry resolves to a real file, and every content file is reachable from it. `ersilia-book`'s
  own `CLAUDE.md` ships this as a copy-paste grep check, which is where `DOC-BROKEN-NAV` and
  `DOC-ORPHAN-PAGE` come from. A broken nav entry is a Blocker because it renders as a
  `/broken/pages/` link on the published site — a visible, public defect.
- Every relative link resolves. This is `T0-BROKEN-LINK`, and it matters more here than
  anywhere else.
- Consistent, kebab-case filenames.
- A short root README that points at the published site rather than duplicating it.
  `ersilia-book`'s is 34 lines and does exactly this.

### What not to report

Python tooling of any kind, unless tracked `.py` files exist. Record the skip so the absence is
visible in the report rather than reading as a pass.

## A note on both types

These repos are frequently the **first** Ersilia artefact an outside collaborator or a workshop
participant sees, and several are the most-starred repos in their type. The T0 baseline —
a real README, a LICENSE, the About-Ersilia footer with a resolving logo, working links — is
therefore worth more here than the deep code checks are anywhere else. Weight the report
accordingly: a workshop repo with four T0 findings and nothing else is in worse shape than a
package with forty docstring findings.
