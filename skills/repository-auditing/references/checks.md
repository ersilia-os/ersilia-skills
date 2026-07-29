# Check registry

Every finding the skill reports comes from one of the checks below. Each has a stable `id`,
a `tier`, a default `severity`, and the repository types it applies to. The checker scripts
own the `id` strings — keep this file and the scripts in sync.

## Report layout

The report is **not** organised by the tiers below. Tiers decide *severity*; the report is
grouped by **area**, because a reader asking "what is wrong with my docs?" needs one place to
look. The first version grouped by severity and scattered README problems across three
sections, which is what prompted the change.

Three parts, each with one job, plus two reference sections:

1. **Verdict** — LLM-written prose, a one-line delta on a repeat audit, an area status table,
   and the top three things to do.
2. **Findings by area** — one line per finding: severity marker, work tag, what is wrong,
   where, and up to two items of evidence. **No fix text.**
3. **Fix plan** — a fenced `bash` block of the mechanical fixes, then a `- [ ]` checklist
   tagged `AUTO` / `EDIT` / `ASK`: what to do about it.
4. **Evidence** — collapsed, keyed by check ID, up to 15 items per finding.
5. **Audit trail** — collapsed: hand-verified checks, accepted deviations, checks not run.

Each finding appears once in Findings and once in the Fix plan, carrying *different* content.
That split is what keeps the report short — the first version printed 25 of 35 findings twice,
wasting about a quarter of its length on restatement.

### Prose rules for the report itself

- **Never write `(s)` or `(ies)`.** Use `plural()` and `verb()` from `_common.py`:
  `f"{plural(n, 'dependency', 'dependencies')} {verb(n)} unpinned"`. `dependency(ies)` is the
  most visible sign a sentence was generated, and this skill asks other people's READMEs to
  read as human work.
- **Never truncate mid-string.** Cut evidence at an item boundary and prose at a word boundary.
  Two earlier versions shipped `docs/api.md, docs/cli.md, docs/conc…` and
  `mirroring \`ersilia\`'s \`tests_and_c…`.
- **Keep checker internals out of summaries.** No rule codes (`(ruff D1xx)`), no counts of
  counts (`(1 difference(s))`). Name the thing instead: `` `black` is configured alongside ruff``
  beats `1 non-ruff linter is configured`.
- **Only runnable commands go in `AUTOFIX`.** An entry that is really prose ends up inside a
  ` ```bash ` block that fails when pasted. The ruff commands must pass
  `--config $SKILL/references/canonical-ruff.toml`, because the findings were measured against
  the canonical config and a bare `ruff check --fix .` would use the repo's drifted one.

### Report size

Measured across the seven calibration repos: the **readable** part (everything above the
Evidence appendix) is 76–118 lines. Totals run 76–364 because the appendix scales with finding
count; it is inside `<details>`, so it renders as a single toggle. `APPENDIX_ITEMS = 15` in
`render_report.py` bounds it — uncapped, `ersilia` produced a 504-line file, which is a lot to
leave in a repo root coming from a skill that flags verbose docs. Fifteen examples plus an
accurate `…and N more` is enough to start work and keeps the loss explicit.

### The repeat-audit delta

When an `AUDIT.md` already exists at the output path, the Verdict opens with one line on what
changed. **Three buckets, not two**, because "fixed" is easy to get wrong:

| Bucket | Meaning |
|---|---|
| **fixed** | The check ran again and no longer fires. Genuinely fixed. |
| **no longer checked** | Skipped or gated this run — its absence says nothing about the repo. |
| **new** | Not in the previous report. |

Two buckets would have lied. Tier 2 was gated *after* the first reports were written, so a
pre-gating report compared naively shows 8 Tier 2 items as "fixed" when nothing was fixed. The
report therefore carries `<!-- checks-version: YYYY-MM-DD -->` in its footer, taken from
`_state.json`'s `last_refresh_date`; when the previous report's stamp differs or is absent, the
delta drops the word "fixed" and says the comparison is indicative.

Tier 2 is excluded from the delta on both sides: its findings are rolled up into one line with
no recoverable IDs, so every T2 item would otherwise read as "new" on every run.

**Areas** are owned by `AREA_OF` in `scripts/render_report.py`, keyed on exact check ID
(prefix matching was tried and misfiled `PKG-DOCSTRING-*` under Documentation). An ID missing
from that table lands in `Other` and logs a warning, so a new check cannot silently vanish.
`AREA_TYPES` in the same file records which types each area is evaluated for.

**Status markers** are data, not decoration: 🔴 blocker · 🟡 should-fix · ⚪ nice-to-have ·
✅ ran and passed · — not evaluated. No other emoji anywhere; the skill flags
`T0-README-EMOJI` in other people's repos and has to obey its own rule.

**The ✅ / — distinction is load-bearing** and was the hardest thing here to get right. ✅
means checks in that area ran and found nothing; — means nothing was evaluated. It broke in
both directions during development: first marking a clean-but-partially-skipped area as "not
checked", then marking an App repo's `Tests & CI` as "✅ clean" when no test check had run at
all. The fix is `AREA_TYPES` — an area that does not apply to the repo's type is omitted
rather than marked either way, and an area with findings is always shown.

## Tiers

| Tier | Meaning | Applies to |
|---|---|---|
| **T0** | Baseline. Every ersilia-os repository, whatever its type, is expected to pass. | all types |
| **T1** | Type profile. What a good repository of *this* type looks like. | one type |
| **T2** | Flagship / aspirational. Only `ersilia` currently meets most of these. Always reported, always labelled aspirational so it cannot be mistaken for actionable debt. | all types |

## Severities

- **Blocker** — the repository is not fit to be shown to an outsider, or it leaks something.
  Missing core docs, template leftovers, secrets or datasets in git, code that will not lint
  or import, extra root-level folders in an Analysis repo.
- **Should-fix** — real debt, not urgent. Everything else in T0 and T1.
- **Nice-to-have** — all of T2, plus informational notes.

A checker may **raise** a severity when the evidence warrants it (e.g. `T0-SECRETS` is always
a Blocker), but never lowers one. Only the LLM judgement pass may downgrade, and it must
annotate why.

---

## Tier 0 — all types

| id | Severity | Check |
|---|---|---|
| `T0-README-MISSING` | Blocker | `README.md` exists at the repo root. |
| `T0-README-STUB` | Blocker | README has more than 10 non-blank lines. (`ersilia-app` has 3.) |
| `T0-LICENSE-MISSING` | Blocker | A `LICENSE` file exists. (`olinda` has none.) |
| `T0-LICENSE-NOT-GPL` | Nice-to-have | License is GPL-3.0. Informational — `isaura` is deliberately MIT. |
| `T0-FOOTER-MISSING` | Blocker | An About-Ersilia section exists. Heading variants `About Us` / `About us` count as present. |
| `T0-FOOTER-DRIFT` | Should-fix | The About paragraph differs from `references/canonical-footer.md`. |
| `T0-FOOTER-NOT-LAST` | Should-fix | Content other than the logo follows the About section. |
| `T0-LOGO-MISSING` | Blocker | The footer contains no logo image. |
| `T0-LOGO-UNRESOLVED` | Blocker | The footer logo path is relative and the file does not exist. |
| `T0-CLAUDEMD-MISSING` | Blocker | `CLAUDE.md` exists at the repo root. |
| `T0-CLAUDEMD-STALE` | Blocker | `CLAUDE.md` is an unedited template leftover — see the marker list below. Grants **no** overrides. |
| `T0-PLACEHOLDER` | Blocker | Template placeholder text survives anywhere in tracked files: `my_package`, `my-package`, `Your Name`, `you@ersilia.io`, `A short description of my package`, `My Ersilia Python Package`. |
| `T0-H1-IS-NAME` | Should-fix | The README H1 is the bare repo or package name. The rule is explicit in the template `CLAUDE.md`: *"a package named `lazy-qsar` should not have `# lazy-qsar` at the top"*. |
| `T0-H1-MISSING` | Should-fix | The README has no H1 at all. |
| `T0-HEADING-LEVELS` | Should-fix | Sections use H1 instead of H2 (`ersilia-maintenance`), or a heading level is skipped. |
| `T0-BROKEN-LINK` | Should-fix | A relative Markdown link or image target does not exist on disk. (`zaira-chem` → `CODE_OF_CONDUCT.md`; `lazy-qsar` → `docs/internals.md`.) |
| `T0-GITIGNORE-MISSING` | Blocker | `.gitignore` exists. (`ersilia-app` has none.) |
| `T0-JUNK-TRACKED` | Should-fix | git tracks `.DS_Store`, `__pycache__/`, `*.pyc`, `.ipynb_checkpoints/`, `tmp/`, `*.old.md`, `*.orig`, `*.rej`, `.vscode/`, `.idea/`. |
| `T0-DATA-TRACKED` | Blocker / Should-fix | git tracks a dataset: any `.csv .tsv .parquet .h5 .hdf5 .pkl .pickle .joblib .npy .npz .sqlite .db` under `data/` or `output(s)/`, or anywhere over 1 MB outside a fixture path. **Severity scales with size**: over 64 KB is a Blocker (real bloat in git history); under it a Should-fix (the `data/`-is-gitignored convention was bypassed, but nothing is bloated). `ersilia-app`'s 0 KB `data/example.csv` is the case this split exists for. |
| `T0-LARGE-FILE` | Blocker | git tracks any file over 5 MB that is not LFS-managed. |
| `T0-SECRETS` | Blocker | git tracks `.env`, `*.pem`, `*.key`, `id_rsa*`, `credentials.json`, `service-account*.json`, or a file containing a credential-shaped string (see the pattern list in `check_hygiene.py`). |
| `T0-GH-DESC-MISSING` | Should-fix | The GitHub repository description is set. |
| `T0-GH-TOPICS-FEW` | Should-fix | At least 3 GitHub topics are set. |
| `T0-DEFAULT-BRANCH` | Should-fix | The default branch is `main`. (`ersilia` uses `master` — long-standing, expect an override.) |
| `T0-REPO-NAME` | Should-fix | The repo name is lowercase alphanumeric with **hyphens only**. `_` is not permitted; neither is uppercase or `.`. Of 179 repos, zero use an underscore and only `ersilia.io` deviates — this is a rule the org already follows. |
| `T0-AIRTABLE-MISSING` | Should-fix | A row for this repo exists in the Airtable `Repositories` table. |
| `T0-AIRTABLE-INCOMPLETE` | Should-fix | That row has `Status`, `Type`, `Title` and a description filled in. |
| `T0-AIRTABLE-NO-PROJECT` | Should-fix | The row links to at least one `Projects` record, so the repo is traceable to the work that funded it. LLM-checked in Step 2 — no script can read Airtable. |
| `T0-AIRTABLE-TYPE-MISMATCH` | Should-fix | The Airtable `Type` matches what the repository actually looks like. A row saying `Package` on a repo with no `pyproject.toml`, or `Analysis` on a repo with no `data/` or `notebooks/`, means the registry is wrong or the repo drifted. LLM-checked in Step 2. |

### README quality — is it succinct, human, and clear?

| id | Severity | Check |
|---|---|---|
| `T0-H1-IS-NAME` | Should-fix | The H1 is the bare repo name. `# eosquality` is a poor title; `# Quality scoring for Ersilia model predictions` is not. |
| `T0-H1-NOT-DESCRIPTIVE` | Should-fix | The H1 is under 3 words (emoji stripped) — not the repo name, but still self-explanatory to nobody. |
| `T0-README-AI-TONE` | Should-fix | The README reads as LLM-generated. Fires on **accumulation**, never one word: ≥4 distinct LLM-favoured terms *plus* a second signal, or ≥7 distinct terms, or ≥8 `- **Bold lead-in:** …` bullets. Em-dash rate (≥4 and >4 per 1000 words) is one of the signals. Code fences and inline code are stripped first. Medium confidence — the judgement pass makes the real call. |
| `T0-README-EMOJI` | Nice-to-have | ≥6 emoji, or ≥3 headings carrying one. One in the title is fine (`ersilia` has 💊); a wall of them is not (`ersilia-maintenance`). |
| `T0-README-NO-PURPOSE` | Should-fix | Under 12 words between the H1 and the first H2. A reader should not have to infer the purpose from an Installation section. |
| `T0-README-NO-ECOSYSTEM` | Nice-to-have | Nothing outside the boilerplate footer connects the repo to the rest of Ersilia's work — no project named, no sibling repo or model linked. `mtb-targeted-protein-degradation` does this well with a "Related repositories" section. |
| `T0-BROKEN-EXTERNAL-LINK` | Should-fix | **Opt-in** (`--check-external`): HTTP-HEADs external links. Skips shields.io/badge endpoints, and treats 401/403/405/429 as bot-blocking rather than broken. Medium confidence — verify by hand. |

### Messiness and naming

| id | Severity | Check |
|---|---|---|
| `T0-ROOT-CLUTTER` | Should-fix | More than 18 non-dot files at the repository root. A crowded root is the first thing that makes a repo feel unmaintained. |
| `T0-NAMING-INCONSISTENT` | Nice-to-have | Python files that are not snake_case. A kebab-case module cannot even be imported. |

### `CLAUDE.md` staleness markers

Any of these, verbatim, means the file was inherited and never adapted:

- `This is an Ersilia Python package template`
- `This is the developer guide for a Python package built from the Ersilia Open Source Initiative's package template`
- `This is the by-default structure of the repository`  *(analysis template, when no repo-specific section was added)*
- a reference to `src/my_package/`
- `# Ersilia Python Package — Developer Guide` as the H1 in a repo that is not the template

`eosquality` trips the first of these: its Project Overview still says it is a template.

---

## Tier 1 — Package

| id | Severity | Check |
|---|---|---|
| `PKG-NO-PYPROJECT` | Should-fix | `pyproject.toml` exists. |
| `PKG-SETUP-PY` | Should-fix | `setup.py` is used instead of `pyproject.toml`. (`zaira-chem`.) |
| `PKG-DEP-UNPINNED` | Should-fix | A runtime dependency uses `>=`, `~=`, `<`, `*` or no specifier. The template rule is *"Pin exact versions. Use `==X.Y.Z` … No floors (`>=`), no ranges."* |
| `PKG-DEV-DEP-UNPINNED` | Should-fix | An optional/dev dependency is unpinned. (`eosquality`: bare `black`, `ruff`.) |
| `PKG-NO-REQUIRES-PYTHON` | Should-fix | `requires-python` is declared. |
| `PKG-PLACEHOLDER-PKG` | Blocker | `src/my_package/` was never renamed. |
| `PKG-UNTOUCHED-CORE` | Should-fix | The templated `core.py` is still byte-identical to the template's. |
| `PKG-NO-RUFF-CONFIG` | Should-fix | A `ruff.toml` (or `[tool.ruff]` in `pyproject.toml`) exists. |
| `PKG-RUFF-CONFIG-DRIFT` | Should-fix | The ruff config differs from `references/canonical-ruff.toml` on `line-length`, `indent-width`, `target-version`, `lint.select`, or `lint.pydocstyle.convention`. |
| `PKG-COMPETING-LINTERS` | Should-fix | `black`, `flake8`, `isort` or `pylint` is configured alongside ruff. The canonical toolchain is ruff-only. (`eosquality` configures both black and ruff, and its `CLAUDE.md` tells you to run `flake8`, which is not a declared dependency.) |
| `PKG-NO-PRECOMMIT` | Should-fix | `.pre-commit-config.yaml` exists with `ruff` and `ruff-format` hooks at a pinned `rev`. |
| `PKG-RUFF-CHECK-FAILS` | Should-fix | Residual `ruff check` violations against the canonical config — import ordering, whitespace, line length. Deliberately **not** a Blocker: the Blocker-worthy failures below (syntax errors, unused imports and variables, undefined names) are reported individually, and calling an unsorted import block a Blocker would drown them. |
| `PKG-RUFF-FORMAT-DIRTY` | Should-fix | `ruff format --check` reports files needing reformatting. |
| `PKG-SYNTAX-ERROR` | Blocker | A tracked `.py` file fails to parse. |
| `PKG-UNUSED-IMPORT` | Blocker | Unused imports (ruff `F401`). Rolled up per file. |
| `PKG-UNUSED-VAR` | Blocker | Assigned-but-never-read local variables (ruff `F841`) — the "stale variables" check. |
| `PKG-UNDEFINED-NAME` | Blocker | ruff `F821`. |
| `PKG-DEAD-MODULE-NAME` | Should-fix | A module-level function, class or constant that is never referenced anywhere in the repo and is not exported via `__all__` or a `[project.scripts]` entry point. Stdlib-AST based; reported with lower confidence than ruff findings. |
| `PKG-DOCSTRING-MISSING` | Should-fix | A public module, class, function or method has no docstring. Private (`_`-prefixed) helpers are exempt, per the template rule. |
| `PKG-DOCSTRING-NOT-NUMPY` | Should-fix | A docstring for a callable with arguments has no `Parameters` section, or one that returns a value has no `Returns` section, or the section underline is not a run of `-` matching the header length. |
| `PKG-NO-TESTS` | Should-fix | `tests/` or `test/` exists and contains at least one `test_*.py` with at least one `test_*` function. |
| `PKG-NO-PYTEST-CONFIG` | Should-fix | `[tool.pytest.ini_options]` with `testpaths` is declared. |
| `PKG-CI-NO-QUALITY` | Should-fix | At least one workflow runs both ruff and pytest. A publish-only workflow does not count (`lazy-qsar`, `stylia`). |
| `PKG-NO-CI` | Should-fix | `.github/workflows/` exists and is non-empty. |
| `PKG-VERSION-MISMATCH` | Should-fix | The latest semver git tag, the latest GitHub release name, and `[project].version` all agree. |
| `PKG-TAG-NOT-SEMVER` | Should-fix | Tags follow `vMAJOR.MINOR.PATCH`. No date-based or build-number schemes. |
| `PKG-NO-RELEASE` | Nice-to-have | A repo whose Airtable Status is `Completed` has at least one GitHub release. |
| `PKG-BARE-LOGGER` | Should-fix | `logging.getLogger(` appears in feature code instead of importing the module-level singleton. |
| `PKG-NO-LOGGER-SINGLETON` | Nice-to-have | A package that logs at all exposes `utils/logging.py` with a `logger` singleton and a `success()` method. |
| `PKG-CLI-NOT-CLICK` | Should-fix | A package exposing a CLI uses `argparse` rather than Click. (`eosquality` does, against its own guide.) |
| `PKG-CLI-NOT-TABLED` | Should-fix | A package with a CLI documents its commands as a two-column README table. |
| `PKG-CLI-OPT-SEPARATOR` | Should-fix | A multiword option uses `_` instead of `-`. kebab-case is canonical — see `canonical-cli.md`. Click maps `--batch-size` to `batch_size` itself, so only the flag string changes. |
| `PKG-CLI-INCONSISTENT` | Should-fix | One CLI mixes `_` and `-` in its option names. Worse than either convention. `ersilia` currently does this: 10 snake, 8 kebab. |
| `PKG-CLI-VERB-DIVERGENT` | Should-fix | A command is a near-synonym of one of `ersilia`'s eleven canonical verbs — `download`→`fetch`, `predict`→`run`, `list`→`catalog`, and so on. Domain verbs with no canonical equivalent (`fit`, `build`, `train`) pass untouched. |
| `PKG-CLI-IO-NAMING` | Should-fix | A file argument is named `--infile`, `--out`, `--dest`, `--source`, `--output-file`, … instead of `--input` / `--output`. |
| `PKG-CLI-NO-SHORT-IO` | Nice-to-have | `--input`/`--output` declared without the `-i`/`-o` short form that `ersilia run` exposes. |
| `PKG-README-VERBOSE` | Should-fix | README exceeds 250 non-blank lines. (`olinda` 295, `stylia` 290, `isaura` 259.) The rule is *"Aim for a screen or two."* |
| `PKG-README-FILLER` | Should-fix | README carries boilerplate the template forbids — empty Installation/Contributing/License/Acknowledgements sections, or AI-style restatements. Flagged by the LLM pass, not by a script. |
| `PKG-README-TODO` | Should-fix | The README contains a TODO/backlog section. Backlogs belong in issues. (`eosquality` has a `# TODO` H1.) |
| `PKG-FLAT-NAMESPACE` | Nice-to-have | A package over ~800 lines lives in a single flat module rather than submodules. |
| `PKG-NO-ACCESS-JSON` | Should-fix | A repo that gitignores `data/` declares an `access.json`. (`eos-python-package` itself misses this.) |
| `PKG-DOCS-PROMISED-MISSING` | Should-fix | A file the repo's own `CLAUDE.md` or README requires does not exist. (`eosquality` requires five `docs/` files; none exist.) |

### Dependencies — are they actually declared?

| id | Severity | Check |
|---|---|---|
| `PKG-DEP-UNDECLARED` | Should-fix | Every third-party import appears in `pyproject.toml`, `requirements.txt`, `environment.yml` or `install.yml`. An undeclared import means a fresh `pip install` produces something that crashes on first use. `IMPORT_TO_DIST` in `check_code.py` maps the non-obvious names (`sklearn` → `scikit-learn`, `rdkit` → `rdkit-pypi`, `yaml` → `pyyaml`); stdlib comes from `sys.stdlib_module_names`. Medium confidence — an optional or conditional import may be deliberate. |
| `PKG-DEP-UNUSED` | Nice-to-have | Declared dependencies that nothing imports. Tooling (`ruff`, `pytest`, `build`, …) is exempt via `TOOLING_DISTS`. Every dependency is a long-term cost. |

### Bad practices

| id | Severity | Check |
|---|---|---|
| `PKG-ABSOLUTE-PATH` | Blocker | A hardcoded `/Users/…`, `/home/…`, `/Volumes/…` or `C:\Users\…` path. The one path issue that is always wrong: it cannot work on anyone else's machine or in CI. |
| `PKG-BARE-EXCEPT` | Should-fix | A bare `except:` (which also swallows `KeyboardInterrupt`) or `except Exception: pass`. |
| `PKG-PRINT-IN-LIB` | Should-fix | `print()` in library code — not in `tests/`, `scripts/` or `notebooks/`, where it is fine. Use the logger singleton so output can be silenced and levelled. |
| `PKG-SHELL-INJECTION` | Should-fix | `os.system` or `shell=True`. Any filename with a space or a semicolon becomes a command. |
| `PKG-WILDCARD-IMPORT` | Should-fix | `from x import *`. Defeats ruff's unused-import detection and hides a name's origin. |
| `PKG-MUTABLE-DEFAULT` | Should-fix | A list, dict or set as a default argument — created once and shared across every call. |
| `PKG-COMMENTED-CODE` | Nice-to-have | 4+ consecutive comment lines that parse as Python. `looks_like_code` filters prose out. Git remembers; commented code goes stale silently. Medium confidence. |
| `PKG-TODO-DENSITY` | Nice-to-have | More than 4 TODO/FIXME/HACK/XXX per 1000 lines. In-code TODOs are invisible to everyone not reading that file. |

### Modularity

| id | Severity | Check |
|---|---|---|
| `PKG-GOD-MODULE` | Should-fix | A module over 600 lines. Calibrated against `ersilia`, whose well-factored modules sit under 400. Medium confidence. |
| `PKG-LONG-FUNCTION` | Should-fix | A function over 80 lines — it does not fit on a screen, so it cannot be reviewed properly. Medium confidence. |
| `PKG-DEEP-NESTING` | Nice-to-have | Control flow nested 5+ levels. Use early returns. Medium confidence. |
| `PKG-FLAT-NAMESPACE` | Should-fix | Over 800 lines with **no** submodules at all. *"Avoid a flat namespace."* Suppressed for Workshop repos, where linear teaching code is correct. |

### eosvc

| id | Severity | Check |
|---|---|---|
| `EOSVC-STALE-DECL` | Should-fix | `access.json` exists but the repo has no data or output directory — it describes storage that is not there. The complementary cases (`data/` present but undeclared, keys not matching) are `ANA-NO-ACCESS-JSON` / `PKG-NO-ACCESS-JSON` / `ANA-ACCESS-JSON-MISMATCH`. |

---

## Tier 1 — Analysis

| id | Severity | Check |
|---|---|---|
| `ANA-EXTRA-ROOT-DIR` | Blocker | A root-level directory outside the template set. The template `CLAUDE.md` is unambiguous: *"Do **not** create new folders at the root level outside the ones listed above."* Allowed: `data/`, `scripts/`, `notebooks/`, `assets/`, `output/`, `src/`, `tools/`, `docs/`, `tmp/`, plus dotdirs and `.github/`. |
| `ANA-DATA-NOT-IGNORED` | Blocker | `data/` and `output/` are gitignored. |
| `ANA-NO-ACCESS-JSON` | Should-fix | `access.json` exists. |
| `ANA-ACCESS-JSON-MISMATCH` | Should-fix | `access.json` keys match the gitignored data dirs, and values are `public` or `private`. (`eosquality` uses `outputs` where the template uses `output`.) |
| `ANA-STALE-GITKEEP` | Should-fix | A `.gitkeep` survives in a directory that now has real content. The rule: *"As soon as a folder contains data or files, remove the `.gitkeep`."* |
| `ANA-EMPTY-DOC-DIR` | Should-fix | A directory the README or `CLAUDE.md` documents does not exist. (`eos-analysis-template` documents `src/`, `tools/` and `output/` but ships none of them.) |
| `ANA-SCRIPT-NOT-NUMBERED` | Should-fix | A file in `scripts/` does not start with `NN_`. |
| `ANA-SCRIPT-NUMBER-GAP` | Should-fix | The `scripts/` numbering has a gap or a duplicate. |
| `ANA-OUTPUT-NUMBER-MISMATCH` | Nice-to-have | `output/` numbering does not mirror `scripts/`. |
| `ANA-BADGE-MISSING` | Should-fix | The status badge is present under the README H1. |
| `ANA-BADGE-PENDING` | Should-fix | The badge still says `pending` while the Airtable Status is past `Todo`. States: `pending` (red) → `in progress` (orange) → `ready` (green). |
| `ANA-README-VERBOSE` | Should-fix | README exceeds 60 non-blank lines. *"Aim for ~50 lines for the root README."* |
| `ANA-README-FOLDER-TREE` | Should-fix | The README reproduces the folder tree instead of linking to `CLAUDE.md`. |
| `ANA-REQS-MISSING` | Should-fix | `requirements.txt` exists. |
| `ANA-REQS-EMPTY` | Blocker | `requirements.txt` is zero bytes. (`eos-analysis-template` ships it empty, against its own rule *"Pin versions in `requirements.txt`"*.) |
| `ANA-REQS-UNPINNED` | Should-fix | A `requirements.txt` entry has no `==`. |
| `ANA-NO-DEFAULT-PY` | Should-fix | `src/default.py` exists once there is code in `scripts/` or `src/`. |
| `ANA-CONST-NOT-CAPS` | Nice-to-have | A project-wide constant in `src/default.py` is not `ALL_CAPS`. |
| `ANA-NO-RANDOM-SEED` | Should-fix | Stochastic code (`train_test_split`, `random.`, `np.random`, `sample(`, `shuffle`) exists but no `RANDOM_SEED` is defined in `src/default.py`. |
| `ANA-NO-SEED-SET` | Should-fix | A script using stochastic methods never sets a seed. |
| `ANA-NO-SYSPATH-PREAMBLE` | Should-fix | A script importing from `src/` lacks the mandated `sys.path.append(os.path.join(root, "..", "src"))` preamble. |
| `ANA-DIRS-IN-FUNCTION` | Nice-to-have | `os.makedirs` is called inside a function rather than at module level. |
| `ANA-NO-MAKEDIRS` | Nice-to-have | A script writes to an output dir it never ensures exists. |
| `ANA-MATPLOTLIB-NOT-STYLIA` | Should-fix | `matplotlib.pyplot` is imported without `stylia`. *"All Python plotting should strictly use the stylia library."* |
| `ANA-NOTEBOOK-OUTPUTS` | Should-fix | A committed `.ipynb` has non-empty cell outputs or a non-null `execution_count`. |
| `ANA-NO-PROVENANCE` | Should-fix | A script downloads from ChEMBL/PubChem/TDC/ZINC/DrugBank/UniProt without a recorded version or snapshot date. *"Datasets without a recorded version are not reproducible."* |
| `ANA-DOC-NAMING` | Nice-to-have | A file in `docs/` is not named `YYYY-MM-DD_topic.md` or `NN_topic.md`. |
| `ANA-REPORT-AT-ROOT` | Should-fix | A long-form Markdown file sits at the repo root instead of `docs/`. Excludes `README.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`. |

---

## Tier 1 — Automation and App

| id | Severity | Check |
|---|---|---|
| `AUT-NO-WORKFLOWS` | Should-fix | An Automation repo has at least one file in `.github/workflows/`. |
| `AUT-WORKFLOW-UNDOCUMENTED` | Should-fix | Every workflow file is mentioned by name or by its `name:` in the README. |
| `AUT-ACTION-UNPINNED` | Should-fix | A third-party action is referenced at `@main`/`@master` rather than a tag or SHA. First-party `ersilia-os/*` reusable workflows at `@main` are the house pattern — report as informational only. |
| `AUT-SCHEDULE-UNDOCUMENTED` | Should-fix | A workflow with a `schedule:` trigger has its cadence documented in the README. |
| `AUT-HARDCODED-TOKEN` | Blocker | A credential-shaped literal appears in a workflow instead of `${{ secrets.* }}`. |
| `AUT-SECRETS-USED` | Nice-to-have | Informational: the list of `secrets.*` names a workflow consumes, for human review. Never a failure — the skill cannot read secret values. |
| `APP-NO-ENTRYPOINT` | Should-fix | An App repo has a `Dockerfile`, a `docker-compose.yml`, a `Procfile`, or a documented start command in the README. |
| `APP-NO-RUN-DOCS` | Should-fix | The README says how to run the app locally. |

---

## Tier 1 — Workshop and Documentation

| id | Severity | Check |
|---|---|---|
| `WSH-NO-AUDIENCE` | Should-fix | The README states who the material is for and how to use it. LLM-judged. |
| `WSH-NO-DATE` | Should-fix | The README or a directory name carries the date or edition of the workshop. |
| `WSH-NO-LICENSE-STATEMENT` | Nice-to-have | Teaching materials carry an explicit reuse/license statement beyond the `LICENSE` file. |
| `DOC-BROKEN-NAV` | Blocker | For GitBook-style repos: an entry in `SUMMARY.md` points at a file that does not exist. Pattern borrowed from `ersilia-book/CLAUDE.md`, which ships exactly this check as a copy-paste grep. |
| `DOC-ORPHAN-PAGE` | Should-fix | A content file is not reachable from `SUMMARY.md`. |

---

## Tier 2 — aspirational, and gated

**Nothing in Tier 2 is unconditional.** `ersilia` is a very evolved package and is not the bar
every repo should be held to; firing ten findings at a 7-commit analysis script is noise, not
information. Each item fires only when it is a fair expectation of *that* repository, and a
gated-out check is recorded in *Checks not run* with the numbers that closed it.

| id | Severity | Fires when |
|---|---|---|
| `T2-NO-CHANGELOG` | Nice-to-have | **≥2 GitHub releases.** A changelog earns its keep once there are versions to compare. |
| `T2-NO-CITATION` | Nice-to-have | The repo **backs a publication** — linked to a Publications record in Airtable (supplied by the LLM via `--backs-paper`), or a DOI / arXiv id in the README. |
| `T2-NO-CONTRIBUTING` | Nice-to-have | The **community gate** is open (below). |
| `T2-NO-COC` | Nice-to-have | Community gate. No org-level defaults exist — `ersilia-os/.github` holds only a LICENSE and profile README, so nothing is inherited. |
| `T2-NO-ISSUE-TEMPLATE` | Nice-to-have | Community gate. |
| `T2-NO-PR-TEMPLATE` | Nice-to-have | Community gate. |
| `T2-NO-DEPENDABOT` | Nice-to-have | Community gate. |
| `T2-NO-BANNER` | Nice-to-have | Always — cheap, and independent of maturity. |
| `T2-NO-TOC` | Nice-to-have | Always, once the README passes 120 lines. |
| `T2-NO-DOCS-DIR` | Nice-to-have | Always. |

### The community gate

Open when the repo looks externally consumed: **≥3 contributors, or ≥5 stars, or ≥2
releases.** Implemented in `community_gate()` in `check_repo_meta.py`.

The `≥2 releases` term is deliberate. An earlier draft used `≥1`, which let a single `v0.0.1`
tag on a 7-commit repo open the gate — the opposite of the intent. Verified against live
GitHub data: the threshold closes for `eosquality` (1 contributor, 1 release, 1 star) and
opens for every other surveyed package (`isaura` 3/8/7, `stylia` 5/3/5, `olinda` 5/1/5,
`compound-embedding` 6/0/3, `ersilia-pack` 6/0/11, `lazy-qsar` 7/30/5, `ersilia` 306/30/92).

---

## Calibration — measured, 2026-07-28

These are the **actual** results of running the skill, not predictions. They are the
regression baseline: a change that moves these numbers materially needs justifying.

### After the report restructure, Tier 2 gating and CLI checks

| Repo | Type | Lines | Blk | Should | Nice |
|---|---|--:|--:|--:|--:|
| `eos-python-package` | Package | 120 | 0 | 8 | 4 |
| `eos-analysis-template` | Analysis | 93 | 1 | 4 | 5 |
| `eosquality` | Package | 132 | 1 | 25 | 2 |
| `ersilia` | Package | 132 | 2 | 25 | 3 |
| `ersilia-app` | App | 96 | 4 | 8 | 8 |
| `ersilia-maintenance` | Automation | 113 | 3 | 14 | 9 |
| `stylia` | Package | 114 | 2 | 19 | 7 |

Report length is now 93–132 lines against 206 before, and **zero sentences are duplicated**
between Findings and the Fix plan (verified programmatically — the same 26 check IDs appear in
both sections of the `eosquality` report carrying entirely different text).

Blocker counts are unchanged from the pre-restructure baseline, which is the point: the
restructure is presentation only. Should-fix rose where the new CLI checks fire (`eosquality`
24→25, `ersilia` 22→25) and Nice-to-have fell sharply from Tier 2 gating (`eosquality` 9→2,
`eos-python-package` 11→4).

**CLI assertions.** `eosquality` must produce exactly one new CLI finding —
`PKG-CLI-VERB-DIVERGENT` for `download` → `fetch`. Its options were inspected directly and are
already compliant: all seven multiword options are kebab-case and both `-i/--input` and
`-o/--output` short pairs exist. If `PKG-CLI-OPT-SEPARATOR` or `PKG-CLI-NO-SHORT-IO` fires
here, that is a false positive. `ersilia` must produce `PKG-CLI-OPT-SEPARATOR` (10 options),
`PKG-CLI-INCONSISTENT` and `PKG-CLI-IO-NAMING` (`--output_file`); if it comes back clean the
check is broken. (An earlier note said 14 snake_case options — that came from a regex over all
option strings including duplicates; the AST pass over `ersilia/cli/commands/` finds 10, which
is the accurate figure.)

### False positive fixed 2026-07-28

`PKG-DEAD-MODULE-NAME` flagged `test_hello` in `eos-python-package/tests/test_core.py`. pytest
discovers test functions **by name**, so a `test_*` function is never referenced from anywhere
and would always look dead. `check_dead_names` now skips test modules, which is the only reason
`eos-python-package` moved from 9 should-fix to 8. Every other calibration repo is unchanged.

### Worked examples

`examples/` holds two committed reports — `eosquality` (busy: a blocker, every area, the Evidence
appendix) and `eos-python-package` (quiet: no blockers, no appendix, template suppressions). Real
output, so a format defect is visible there. `examples/README.md` says what to distrust first.

### Per-repo detail

| Repo | Type | Blk | Should | Nice | Result |
|---|---|--:|--:|--:|---|
| `eos-python-package` | Package | 0 | 9 | 10 | Near-clean, as it should be. Genuine findings: `PKG-NO-ACCESS-JSON` (gitignores `data/` with no `access.json`), `PKG-DOCSTRING-MISSING` on `core.py`'s `hello`, `PKG-NO-RUFF-CONFIG` (mandates ruff, ships no config), `PKG-NO-CI`, `PKG-NO-PRECOMMIT`. A flood here means the profile is miscalibrated. |
| `eosquality` | Package | 1 | 19 | 8 | `T0-CLAUDEMD-STALE` is the single Blocker. Then `PKG-NO-TESTS`, `PKG-NO-PYTEST-CONFIG`, `PKG-DOCS-PROMISED-MISSING` (5 files), `PKG-DEP-UNPINNED` (13), `PKG-DEV-DEP-UNPINNED`, `PKG-COMPETING-LINTERS` (black + ruff), `PKG-CLI-NOT-CLICK`, `PKG-CLI-NOT-TABLED`, `PKG-README-TODO`, `T0-HEADING-LEVELS`, `T0-FOOTER-DRIFT`, `PKG-NO-CI`, `PKG-NO-PRECOMMIT`, `PKG-RUFF-CONFIG-DRIFT`, `PKG-VERSION-MISMATCH`, `T0-GH-TOPICS-FEW`. `T0-FOOTER-NOT-LAST` correctly does **not** fire — the `# TODO` H1 sits above the footer. |
| `eos-analysis-template` | Analysis | 1 | 4 | 7 | `ANA-REQS-EMPTY` is the Blocker. Plus `ANA-EMPTY-DOC-DIR` (`output/`, `src/`, `tools/` — documented, never shipped), `ANA-ACCESS-JSON-MISMATCH`, `ANA-NO-DEFAULT-PY`. |
| `ersilia` | Package | 3 | 15 | 0 | The bar is reachable: T0/T1 broadly pass. `T0-CLAUDEMD-MISSING` and a **real** `T0-SECRETS` (see below) are the Blockers. `T0-DEFAULT-BRANCH` fires on `master` — expect an override. Every T2 check passes, the only repo in the org for which that is true. |
| `eos-template` / any `eosNxxx` | Model | — | — | — | `resolve_target.py` exits 3 before any check runs. |

### The `ersilia` secret is real

`T0-SECRETS` fires on `ersilia/utils/exceptions_utils/issue_reporting.py:100`, a commented-out
Gmail app password with the inline note *"insecure: the password will be visible from the
code"*. Commenting a credential out does not unpublish it — it is in the public history. This
is the check working, not a false positive. Do not add an exemption for commented lines.

### False positives fixed during calibration

Kept here so they are not reintroduced:

- **Package example data.** `ersilia/io/types/examples/protein.tsv` (2.5 MB) is a reference
  input the package loads at runtime, not a committed dataset. `FIXTURE_DIRS` in
  `check_hygiene.py` exempts `examples/`, `fixtures/`, `tests/`, `assets/` and `templates/`
  from the size-based half of `T0-DATA-TRACKED`; anything under `data/` is still flagged at
  any size, and the 5 MB `T0-LARGE-FILE` ceiling still applies everywhere.
- **HTML README titles.** `ersilia` sets its title with `<h2 align="center">` so it can sit
  under a centred banner. That is a title, so `T0-H1-MISSING` is skipped with a reason rather
  than reported.
- **`.gitkeep` in `tmp/`.** The templates use a tracked `.gitkeep` to preserve empty
  directories, including gitignored ones. `check_junk` exempts `.gitkeep` entirely;
  `ANA-STALE-GITKEEP` judges staleness separately, and `has_real_content` does not count a
  subdirectory that itself holds only `.gitkeep` files.
- **`git check-ignore` on a bare directory.** It returns "not ignored" for `data` even when
  `.gitignore` contains `data/`. `is_ignored_dir` probes a path *inside* the directory
  instead, which is the question that actually matters.
- **Template repos.** `is_template_repo` in `_common.py` suppresses `T0-PLACEHOLDER`,
  `T0-CLAUDEMD-STALE`, `PKG-PLACEHOLDER-PKG`, `PKG-UNTOUCHED-CORE` and `ANA-BADGE-PENDING` —
  all five describe the template's purpose. Every other check still applies, and the
  suppressions appear in the report's Checks-not-run section.

### Checks that apply beyond their prefix

`ANA-NOTEBOOK-OUTPUTS` and `ANA-STALE-GITKEEP` are named for the Analysis profile but run on
every type except Workshop (where saved notebook outputs are the point). A committed notebook
carrying outputs is worth flagging wherever it appears — it fires on `ersilia`.
