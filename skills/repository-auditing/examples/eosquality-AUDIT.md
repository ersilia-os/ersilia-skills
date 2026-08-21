# Audit — `eosquality`

Package · 2026-07-28 · `main@7d1266d` · local-clone · type from airtable

> [!IMPORTANT]
> Working tree has **uncommitted changes** — findings describe the tree on disk, not the default branch.
> `CLAUDE.md` is an inherited template, so it **grants no overrides**.

## Verdict

A carefully written package with no test or CI scaffolding at all. The single blocker is
misleading rather than broken: `CLAUDE.md` still declares itself a template, so it grants no
overrides and anyone reading it learns about the template instead of this repo. Nothing is
leaking, hygiene is clean and the registry entry is in order — this is scaffolding work, not
repair.

| Area                     | State |
|--------------------------|-------|
| Template leftovers       | ✅ clean |
| Hygiene & security       | ✅ clean |
| Documentation            | 🔴 1 blocker, 4 others |
| Tests & CI               | 🟡 3 issues |
| Code quality             | 🟡 9 issues |
| Dependencies & packaging | 🟡 3 issues |
| API & CLI                | 🟡 3 issues |
| Modularity & structure   | 🟡 2 issues |
| Releases                 | 🟡 1 issue |
| Metadata & registry      | 🟡 1 issue |
| Airtable registry        | ✅ verified |
| External links           | — not checked |

**Start here:** 1. rewrite `CLAUDE.md` to describe this repo · 2. run the mechanical block, then re-audit · 3. add `tests/` and a CI workflow

## Findings

### Documentation (5)
- 🔴 EDIT `T0-CLAUDEMD-STALE` CLAUDE.md is an unadapted template leftover — `CLAUDE.md` — markers found: "This is an Ersilia Python package template"
- 🟡 EDIT `PKG-DOCS-PROMISED-MISSING` 5 documentation files are required by the repo's own docs but do not exist — `docs/api.md`; `docs/cli.md` (+3 more, see Evidence)
- 🟡 EDIT `PKG-README-TODO` The README carries a TODO/backlog section — `README.md`
- 🟡 EDIT `T0-FOOTER-DRIFT` The About-Ersilia paragraph differs from the canonical wording — `README.md:89`
- 🟡 EDIT `T0-HEADING-LEVELS` The README has 2 H1 headings; sections should be H2 — `README.md` — line 81: `# TODO`

### Code quality (9)
- 🟡 EDIT `PKG-BARE-EXCEPT` 1 bare or silently-swallowing `except` clause — `src/eosquality/utils/logging.py:43`
- 🟡 EDIT `PKG-COMPETING-LINTERS` `black` is configured alongside ruff — `[tool.black]` in pyproject.toml
- 🟡 ASK `PKG-DEAD-MODULE-NAME` 7 module-level names are defined but never referenced — full list in Evidence (medium)
- 🟡 EDIT `PKG-DOCSTRING-MISSING` 56 public classes and methods have no docstring — full list in Evidence
- 🟡 EDIT `PKG-DOCSTRING-NOT-NUMPY` 108 public functions have a docstring with no `Parameters`/`Returns` section — full list in Evidence
- 🟡 EDIT `PKG-NO-PRECOMMIT` There is no pre-commit config
- 🟡 EDIT `PKG-PRINT-IN-LIB` 19 `print()` calls in library code across 4 modules — full list in Evidence
- 🟡 AUTO `PKG-RUFF-CHECK-FAILS` `ruff check` reports 17 style violations against the canonical config — I001×17
- 🟡 AUTO `PKG-RUFF-CONFIG-DRIFT` The ruff config in pyproject.toml [tool.ruff] diverges from the org standard — `pyproject.toml [tool.ruff]`

### Dependencies & packaging (3)
- 🟡 EDIT `PKG-DEP-UNPINNED` 13 runtime dependencies are not pinned to an exact version — `pyproject.toml` — `numpy>=1.21`; `pandas>=1.5` (+11 more, see Evidence)
- 🟡 EDIT `PKG-DEV-DEP-UNPINNED` 3 optional/dev dependencies are unpinned — `pyproject.toml` — `[dev] black`; `[dev] ruff` (+1 more, see Evidence)
- ⚪ ASK `PKG-DEP-UNUSED` 3 declared dependencies are never imported — `joblib`; `matplotlib` (+1 more, see Evidence) (medium)

### Tests & CI (3)
- 🟡 EDIT `PKG-NO-CI` There are no GitHub Actions workflows
- 🟡 EDIT `PKG-NO-PYTEST-CONFIG` No `[tool.pytest.ini_options]` with `testpaths` — `pyproject.toml`
- 🟡 EDIT `PKG-NO-TESTS` There is no test suite

### API & CLI (3)
- 🟡 ASK `PKG-CLI-NOT-CLICK` The CLI is built with argparse rather than Click
- 🟡 EDIT `PKG-CLI-NOT-TABLED` The package ships a CLI but the README has no command table — `README.md`
- 🟡 EDIT `PKG-CLI-VERB-DIVERGENT` 1 command is a near-synonym of a canonical verb — `download` → `fetch` (src/eosquality/cli/download.py:59)

### Modularity & structure (2)
- 🟡 ASK `PKG-GOD-MODULE` 3 modules exceed 600 lines — `src/eosquality/quality.py (938 lines)`; `src/eosquality/scores/consistency.py (615 lines)` (+1 more, see Evidence) (medium)
- 🟡 EDIT `PKG-LONG-FUNCTION` 13 functions exceed 80 lines — full list in Evidence (medium)

### Metadata & registry (1)
- 🟡 EDIT `T0-GH-TOPICS-FEW` The repository has 0 GitHub topics; at least 3 are expected

### Releases (1)
- 🟡 EDIT `PKG-VERSION-MISMATCH` The tag, the GitHub release and the declared version do not agree — latest tag: `0.0.1`; GitHub release: `0.0.1` (+1 more, see Evidence)

⚪ **Tier 2**, if you want the flagship bar: add a `docs/` directory.

## Fix plan

Mechanical first — safe, reviewable in one diff, and it shrinks the rest:

```bash
SKILL="/Users/mduranfrigola/Documents/GitHub/ersilia-skills/skills/repository-auditing"

ruff check --fix --config $SKILL/references/canonical-ruff.toml .
cp $SKILL/references/canonical-ruff.toml ruff.toml
```

Then, in order:

- [ ] EDIT `T0-CLAUDEMD-STALE` `CLAUDE.md` **blocker** — Rewrite the Project Overview and any layout section to describe this repository.
- [ ] AUTO `PKG-RUFF-CHECK-FAILS` — Run `ruff check --fix` — most are auto-fixable — then fix what remains by hand.
- [ ] AUTO `PKG-RUFF-CONFIG-DRIFT` `pyproject.toml [tool.ruff]` — Replace it with `references/canonical-ruff.toml`.
- [ ] EDIT `PKG-BARE-EXCEPT` — Catch the specific exception.
- [ ] EDIT `PKG-CLI-NOT-TABLED` `README.md` — Add a compact two-column table (command → one-line description).
- [ ] EDIT `PKG-CLI-VERB-DIVERGENT` — Rename to the canonical verb so the vocabulary matches every other Ersilia CLI.
- [ ] EDIT `PKG-COMPETING-LINTERS` — The canonical toolchain is ruff-only — `ruff check` plus `ruff format` replace black, flake8 and isort.
- [ ] EDIT `PKG-DEP-UNPINNED` `pyproject.toml` — Use `==X.Y.Z` for every entry.
- [ ] EDIT `PKG-DEV-DEP-UNPINNED` `pyproject.toml` — Pin these too — an unpinned `ruff` or `black` means the lint result depends on when you installed.
- [ ] EDIT `PKG-DOCS-PROMISED-MISSING` — Write them, or drop the requirement from `CLAUDE.md`/README so the docs match reality.
- [ ] EDIT `PKG-DOCSTRING-MISSING` — Add succinct NumPy-style docstrings.
- [ ] EDIT `PKG-DOCSTRING-NOT-NUMPY` — Add the sections. NumPy style: the header, then a rule of `-` the same length, then one entry per…
- [ ] EDIT `PKG-LONG-FUNCTION` — Extract the steps into named helpers.
- [ ] EDIT `PKG-NO-CI` — Add one that runs `ruff check` and `pytest` on push and pull request, mirroring `ersilia`'s…
- [ ] EDIT `PKG-NO-PRECOMMIT` — Add `.pre-commit-config.yaml` with the `ruff` and `ruff-format` hooks at a pinned `rev`, matching…
- [ ] EDIT `PKG-NO-PYTEST-CONFIG` `pyproject.toml` — Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, as in `eos-python-package`.
- [ ] EDIT `PKG-NO-TESTS` — Add smoke tests for the user-facing API and CLI in `tests/`.
- [ ] EDIT `PKG-PRINT-IN-LIB` — Use the logger singleton so output can be silenced, redirected and levelled…
- [ ] EDIT `PKG-README-TODO` `README.md` — Move the open items to GitHub issues.
- [ ] EDIT `PKG-VERSION-MISMATCH` — Bring all three into line.
- [ ] EDIT `T0-FOOTER-DRIFT` `README.md:89` — Replace it with the block in `references/canonical-footer.md`.
- [ ] EDIT `T0-GH-TOPICS-FEW` — Add topics so the repo is discoverable — e.g. `drug-discovery`, `machine-learning`, `global-health`…
- [ ] EDIT `T0-HEADING-LEVELS` `README.md` — Demote every section heading below the title to `##`.
- [ ] ASK `PKG-CLI-NOT-CLICK` — Port to Click, organised as `src/<package>/cli/commands/` with one file per command and a small…
- [ ] ASK `PKG-DEAD-MODULE-NAME` — Delete them, or export them via `__all__` if they are public API.
- [ ] ASK `PKG-GOD-MODULE` — Split them into submodules.
- [ ] ASK `PKG-DEP-UNUSED` — Remove them, or confirm they are needed at runtime rather than at import time (a CLI plugin or a backend…
- [ ] OPT `Tier 2` only if you want the flagship bar — add a `docs/` directory

## Evidence

<details><summary>evidence for 11 findings</summary>

**PKG-DEAD-MODULE-NAME** — 7 module-level names are defined but never referenced

- src/eosquality/library/maccs.py:172 `fit_and_save_maccs`
- src/eosquality/library/physchem.py:254 `fit_and_save_physchem`
- src/eosquality/utils/arrays.py:6 `safe_nanmean`
- src/eosquality/utils/arrays.py:16 `bounded_clip`
- src/eosquality/utils/arrays.py:21 `exclude_self_neighbors`
- src/eosquality/utils/stats.py:13 `robust_spread`
- src/eosquality/utils/stats.py:23 `decay_score`

**PKG-DEP-UNPINNED** — 13 runtime dependencies are not pinned to an exact version

- `numpy>=1.21`
- `pandas>=1.5`
- `scipy>=1.9`
- `scikit-learn>=1.1`
- `joblib>=1.2`
- `loguru>=0.7`
- `rich>=13.0`
- `FPSim2>=0.4`
- `rdkit>=2022.03`
- `packaging>=21.0`
- `eosframes>=1.0`
- `xgboost>=3.0`
- `tables>=3.8`

**PKG-DEV-DEP-UNPINNED** — 3 optional/dev dependencies are unpinned

- `[dev] black`
- `[dev] ruff`
- `[viz] matplotlib>=3.7`

**PKG-DOCS-PROMISED-MISSING** — 5 documentation files are required by the repo's own docs but do not exist

- `docs/api.md`
- `docs/cli.md`
- `docs/concepts.md`
- `docs/diagram.md`
- `docs/reference-library.md`

**PKG-DOCSTRING-MISSING** — 56 public classes and methods have no docstring

- `src/eosquality/basic_descriptors.py:210`
- `src/eosquality/basic_descriptors.py:216`
- `src/eosquality/config.py:60`
- `src/eosquality/schema/models.py:24`
- `src/eosquality/schema/models.py:28`
- `src/eosquality/scores/consistency.py:441`
- `src/eosquality/scores/consistency.py:451`
- `src/eosquality/scores/consistency.py:457`
- `src/eosquality/scores/consistency.py:463`
- `src/eosquality/scores/consistency.py:469`
- `src/eosquality/scores/consistency.py:475`
- `src/eosquality/scores/consistency.py:481`
- `src/eosquality/scores/consistency.py:485`
- `src/eosquality/scores/extremity.py:293`
- `src/eosquality/scores/extremity.py:301`
- …and 25 more — re-run the checker for the full list

**PKG-DOCSTRING-NOT-NUMPY** — 108 public functions have a docstring with no `Parameters`/`Returns` section

- src/eosquality/__init__.py:47 `set_verbosity` — no Parameters (1 args)
- src/eosquality/basic_descriptors.py:70 `build_physchem` — no Parameters (5 args), Returns
- src/eosquality/basic_descriptors.py:135 `build_maccs` — no Parameters (5 args), Returns
- src/eosquality/basic_descriptors.py:195 `load` — no Parameters (1 args), Returns
- src/eosquality/cli/__init__.py:51 `build_parser` — no Returns
- src/eosquality/cli/build.py:20 `cmd_build` — no Parameters (1 args), Returns
- src/eosquality/cli/build.py:77 `register_subparsers` — no Parameters (1 args)
- src/eosquality/cli/download.py:32 `cmd_download` — no Parameters (1 args), Returns
- src/eosquality/cli/download.py:57 `register_subparsers` — no Parameters (1 args)
- src/eosquality/cli/fit.py:29 `cmd_fit` — no Parameters (1 args), Returns
- src/eosquality/cli/fit.py:125 `register_subparsers` — no Parameters (1 args)
- src/eosquality/cli/run.py:27 `cmd_run` — no Parameters (1 args), Returns
- src/eosquality/cli/run.py:120 `register_subparsers` — no Parameters (1 args)
- src/eosquality/knn/fit.py:15 `fit_knn` — no Returns
- src/eosquality/knn/load.py:16 `load_knn` — no Parameters (1 args), Returns
- …and 25 more — re-run the checker for the full list

**PKG-GOD-MODULE** — 3 modules exceed 600 lines

- `src/eosquality/quality.py (938 lines)`
- `src/eosquality/scores/consistency.py (615 lines)`
- `src/eosquality/scores/signal.py (1083 lines)`

**PKG-LONG-FUNCTION** — 13 functions exceed 80 lines

- `src/eosquality/cli/fit.py:29 `cmd_fit` (93 lines)`
- `src/eosquality/cli/fit.py:125 `register_subparsers` (111 lines)`
- `src/eosquality/cli/run.py:27 `cmd_run` (90 lines)`
- `src/eosquality/library/download.py:75 `ensure_library_downloaded` (81 lines)`
- `src/eosquality/quality.py:120 `fit` (195 lines)`
- `src/eosquality/quality.py:317 `run` (234 lines)`
- `src/eosquality/scores/consistency.py:121 `fit` (105 lines)`
- `src/eosquality/scores/consistency.py:232 `run` (94 lines)`
- `src/eosquality/scores/signal.py:296 `fit_from_arrays` (156 lines)`
- `src/eosquality/scores/signal.py:653 `fit` (154 lines)`
- `src/eosquality/shared/fit.py:22 `fit_shared` (88 lines)`
- `src/eosquality/shared/metadata.py:78 `compute_metadata` (81 lines)`
- `src/eosquality/vectorindex.py:95 `build` (222 lines)`

**PKG-PRINT-IN-LIB** — 19 `print()` calls in library code across 4 modules

- `src/eosquality/cli/run.py (6)`
- `src/eosquality/cli/build.py (5)`
- `src/eosquality/cli/fit.py (5)`
- `src/eosquality/cli/download.py (3)`

**PKG-VERSION-MISMATCH** — The tag, the GitHub release and the declared version do not agree

- latest tag: `0.0.1`
- GitHub release: `0.0.1`
- pyproject version: `0.1.0`

**PKG-DEP-UNUSED** — 3 declared dependencies are never imported

- `joblib`
- `matplotlib`
- `tables`

</details>

## Audit trail

<details><summary>7 verified by hand · 0 accepted deviations · 15 checks not run</summary>

**Verified by hand** — checks with no script behind them, confirmed passing.

- `T0-AIRTABLE-MISSING` — row `receLElWZZ4FZQqji` exists in Repositories
- `T0-AIRTABLE-INCOMPLETE` — Title, Status, Type and description all present
- `T0-AIRTABLE-NO-PROJECT` — linked to "Plan Generación Conocimiento"
- `T0-AIRTABLE-TYPE-MISMATCH` — Airtable says Package; pyproject.toml and src/ layout agree
- `T0-README-AI-TONE` — read in full — precise and human; 1 em-dash in 95 lines
- `T0-H1-IS-NAME` — `# Quality of Ersilia predictions` is descriptive
- `T0-README-NO-PURPOSE` — lead states what it does and explicitly what it does not

**Not run** — listed so an absent finding is never mistaken for a pass.

- `T2-NO-COC`, `T2-NO-CONTRIBUTING`, `T2-NO-DEPENDABOT`, `T2-NO-ISSUE-TEMPLATE`, `T2-NO-PR-TEMPLATE` — early-stage repo (1 contributor, 1 release, 1 star); community files are not a fair expectation yet
- `ANA-DATA-NOT-IGNORED`, `ANA-EMPTY-DOC-DIR`, `ANA-EXTRA-ROOT-DIR`, `ANA-REPORT-AT-ROOT` — not an Analysis repo (type=Package)
- `AUT-SCHEDULE-UNDOCUMENTED`, `AUT-WORKFLOW-UNDOCUMENTED` — not an Automation repo (type=Package)
- `T2-NO-CITATION` — no linked publication and no DOI or arXiv id in the README
- `APP-NO-ENTRYPOINT` — not an App repo (type=Package)
- `T0-BROKEN-EXTERNAL-LINK` — not requested — pass --check-external to HTTP-check external links
- `T2-NO-CHANGELOG` — only 1 release; a changelog earns its keep once there are versions to compare

</details>

Nothing in `eosquality` was changed. Findings say what is wrong; the fix plan says what to do. The standard is versioned in `skills/repository-auditing/references/`.

<!-- checks-version: 2026-07-28 -->
