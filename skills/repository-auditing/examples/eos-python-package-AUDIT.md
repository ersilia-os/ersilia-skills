# Audit — `eos-python-package`

Package · 2026-07-28 · `main@0b314dc` · local-clone · type from airtable (Template → Package profile)

> [!IMPORTANT]
> **Template repository** — placeholder text is its purpose, so those checks are suppressed.

## Verdict

Since the 2026-07-28 audit: **1 fixed**, 11 unchanged.

The package template, and close to the standard it defines — no blockers, nothing leaking.
The gap worth closing is that it does not practise what it prescribes: its own `CLAUDE.md`
mandates ruff and NumPy docstrings, yet the template ships with no `ruff.toml`, no pre-commit
config and no CI, so every repo generated from it starts without them. It also gitignores
`data/` without the `access.json` that eosvc needs.

| Area                     | State |
|--------------------------|-------|
| Hygiene & security       | 🟡 1 issue |
| Documentation            | ✅ clean |
| Tests & CI               | 🟡 1 issue |
| Code quality             | 🟡 5 issues |
| Dependencies & packaging | ⚪ 1 issue |
| API & CLI                | ✅ clean |
| Modularity & structure   | ✅ clean |
| Releases                 | ⚪ 1 issue |
| Metadata & registry      | 🟡 2 issues |
| Airtable registry        | ✅ verified |
| External links           | — not checked |

**Start here:** 1. add `ruff.toml` from the canonical config · 2. add a CI workflow running ruff + pytest · 3. add `access.json` for the gitignored `data/`

## Findings

### Code quality (5)
- 🟡 EDIT `PKG-DOCSTRING-MISSING` 2 public functions have no docstring — src/my_package/core.py:1 `hello`; tests/test_core.py:3 `test_hello`
- 🟡 EDIT `PKG-NO-PRECOMMIT` There is no pre-commit config
- 🟡 AUTO `PKG-NO-RUFF-CONFIG` There is no ruff configuration
- 🟡 AUTO `PKG-RUFF-CHECK-FAILS` `ruff check` reports 2 style violations against the canonical config — I001×1, W292×1
- 🟡 AUTO `PKG-RUFF-FORMAT-DIRTY` 1 file not `ruff format` clean — `tests/test_core.py`

### Metadata & registry (2)
- 🟡 EDIT `T0-AIRTABLE-NO-PROJECT` The Airtable record links to no Projects entry
- 🟡 EDIT `T0-GH-TOPICS-FEW` The repository has 0 GitHub topics; at least 3 are expected

### Hygiene & security (1)
- 🟡 EDIT `PKG-NO-ACCESS-JSON` `data` is gitignored but there is no access.json

### Tests & CI (1)
- 🟡 EDIT `PKG-NO-CI` There are no GitHub Actions workflows

### Dependencies & packaging (1)
- ⚪ ASK `PKG-DEP-UNUSED` 1 declared dependency is never imported — `numpy` (medium)

### Releases (1)
- ⚪ EDIT `PKG-NO-RELEASE` Airtable marks this repo Completed but it has no GitHub release

⚪ **Tier 2**, if you want the flagship bar: add a banner or badge row, a `docs/` directory.

## Fix plan

Mechanical first — safe, reviewable in one diff, and it shrinks the rest:

```bash
SKILL="/Users/mduranfrigola/Documents/GitHub/ersilia-skills/skills/repository-auditing"

cp $SKILL/references/canonical-ruff.toml ruff.toml
ruff check --fix --config $SKILL/references/canonical-ruff.toml .
ruff format --config $SKILL/references/canonical-ruff.toml .
```

Then, in order:

- [ ] AUTO `PKG-NO-RUFF-CONFIG` — Copy `references/canonical-ruff.toml` to `ruff.toml`.
- [ ] AUTO `PKG-RUFF-CHECK-FAILS` — Run `ruff check --fix` — most are auto-fixable — then fix what remains by hand.
- [ ] AUTO `PKG-RUFF-FORMAT-DIRTY` — Run `ruff format`.
- [ ] EDIT `PKG-DOCSTRING-MISSING` — Add succinct NumPy-style docstrings.
- [ ] EDIT `PKG-NO-ACCESS-JSON` — Add `access.json` declaring each eosvc-backed directory, e.g. `{"data": "public"}`, so the bucket…
- [ ] EDIT `PKG-NO-CI` — Add one that runs `ruff check` and `pytest` on push and pull request, mirroring `ersilia`'s…
- [ ] EDIT `PKG-NO-PRECOMMIT` — Add `.pre-commit-config.yaml` with the `ruff` and `ruff-format` hooks at a pinned `rev`, matching…
- [ ] EDIT `T0-AIRTABLE-NO-PROJECT` — Link the row to the project that owns the templates, so the repo is traceable to the work that funds it.
- [ ] EDIT `T0-GH-TOPICS-FEW` — Add topics so the repo is discoverable — e.g. `drug-discovery`, `machine-learning`, `global-health`…
- [ ] EDIT `PKG-NO-RELEASE` — Cut a release so consumers have something citable to pin to.
- [ ] ASK `PKG-DEP-UNUSED` — Remove them, or confirm they are needed at runtime rather than at import time (a CLI plugin or a backend…
- [ ] OPT `Tier 2` only if you want the flagship bar — add a banner or badge row, a `docs/` directory

## Audit trail

<details><summary>5 verified by hand · 0 accepted deviations · 23 checks not run</summary>

**Verified by hand** — checks with no script behind them, confirmed passing.

- `T0-AIRTABLE-MISSING` — row `rec03nSrwiAeLb5v2` exists in Repositories
- `T0-AIRTABLE-INCOMPLETE` — Title "Ersilia Python Package Template", Status Completed, Type Template, description all present
- `T0-AIRTABLE-TYPE-MISMATCH` — Airtable says Template and it is the template; audited with the Package profile since it ships a pyproject.toml
- `T0-README-AI-TONE` — 40-line README, no LLM vocabulary, no em-dashes
- `T0-H1-IS-NAME` — `# My Ersilia Python Package` is a placeholder title, correct for a template

**Not run** — listed so an absent finding is never mistaken for a pass.

- `T2-NO-COC`, `T2-NO-CONTRIBUTING`, `T2-NO-DEPENDABOT`, `T2-NO-ISSUE-TEMPLATE`, `T2-NO-PR-TEMPLATE` — early-stage repo (1 contributor, 0 releases, 0 stars); community files are not a fair expectation yet
- `ANA-DATA-NOT-IGNORED`, `ANA-EMPTY-DOC-DIR`, `ANA-EXTRA-ROOT-DIR`, `ANA-REPORT-AT-ROOT` — not an Analysis repo (type=Package)
- `PKG-CLI-NOT-CLICK`, `PKG-CLI-NOT-TABLED` — no CLI detected
- `AUT-SCHEDULE-UNDOCUMENTED`, `AUT-WORKFLOW-UNDOCUMENTED` — not an Automation repo (type=Package)
- `PKG-PLACEHOLDER-PKG`, `PKG-UNTOUCHED-CORE` — target is a template repository — the placeholder package is its purpose
- `EOSVC-NOT-USED` — access.json absence is reported by check_hygiene
- `T2-NO-CITATION` — no linked publication and no DOI or arXiv id in the README
- `PKG-RUFF-CONFIG-DRIFT` — no ruff config to compare
- `APP-NO-ENTRYPOINT` — not an App repo (type=Package)
- `T0-BROKEN-EXTERNAL-LINK` — not requested — pass --check-external to HTTP-check external links
- `T2-NO-CHANGELOG` — only 0 releases; a changelog earns its keep once there are versions to compare
- `T0-CLAUDEMD-STALE` — target is a template repository — its CLAUDE.md legitimately describes the template. It grants no overrides regardless.
- `T0-PLACEHOLDER` — target is a template repository — placeholder text is its purpose

</details>

Nothing in `eos-python-package` was changed. Findings say what is wrong; the fix plan says what to do. The standard is versioned in `skills/repository-auditing/references/`.

<!-- checks-version: 2026-07-28 -->
