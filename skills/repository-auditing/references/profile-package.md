# Profile — Package

Applies to Airtable `Type = Package`. 71 of 179 repos, the largest group. The written spec is
`ersilia-os/eos-python-package/CLAUDE.md`; the working reference implementation is
`ersilia-os/ersilia`.

## Expected layout

```
├── src/<package>/          # or a flat top-level package — both exist in the org
│   ├── __init__.py
│   ├── utils/logging.py    # the logger singleton
│   └── cli/                # one module per command, if there is a CLI
├── tests/                  # `test/` also in use (ersilia); either is accepted
├── docs/                   # long-form content offloaded from the README
├── assets/Ersilia_Brand.png
├── pyproject.toml
├── ruff.toml
├── .pre-commit-config.yaml
├── .github/workflows/
├── CLAUDE.md
├── LICENSE
└── README.md
```

`src/` layout and a flat top-level package are both in circulation (`ersilia-pack` and
`compound-embedding` use `src/`; `ersilia`, `lazy-qsar`, `stylia`, `isaura`, `olinda`,
`xai4chem` are flat). **Do not report layout choice as a finding** — only report a mismatch
between the layout on disk and what `pyproject.toml` declares.

## Normative rules, quoted from the template `CLAUDE.md`

**Layout**
- *"Rename the package folder … Never leave `my_package` in place once the template is being used."*
- *"Remove `core.py` if untouched."*
- *"Favour submodules (`io/`, `utils/`, `cli/`, ...) instead of a single flat file. Avoid a flat namespace."*
- *"Keep public APIs small. Ersilia packages are thought of as simple APIs and CLIs. Avoid over-parametrising function signatures."*

**Code style**
- *"Run ruff before every commit. `ruff check` and `ruff format` must both pass."*
- *"Docstrings: NumPy convention. Write succinct NumPy-style docstrings for every public class, function, and method. For private helpers, only add a docstring when the intent isn't obvious from the name and signature."*
- *"Keep code, docstrings, and docs aligned."*

**Logging**
- A module-level singleton on stdlib `logging` + Rich's `RichHandler`, exposing the usual
  levels plus `success()`. Reference: `ersilia/utils/logging.py`. A `loguru`-based
  alternative (`lazy-qsar`) is acceptable.
- *"Import the singleton everywhere — do not call `logging.getLogger(...)` directly in feature code."*

**CLI**
- *"Use Click … organised as `src/<package>/cli/commands/` with one file per command and a small `create_cli.py`."*
- *"Document commands as a table."* Two columns, command → one-line description. Not prose,
  not reproduced `--help` output.

**Tests**
- *"Smoke-test the user-facing API/CLI … Skip exhaustive unit-test coverage of internals."*
- *"Keep `tests/` lean … delete them once the code they exercised has stabilised."*
  Because of this, **a small test suite is not a finding** — an absent one is.

**Dependencies**
- *"Pin exact versions. Use `==X.Y.Z` for every entry in `pyproject.toml` … No floors (`>=`), no ranges."*
- *"Evaluate every new dependency … Prefer the standard library or an existing transitive dependency."*
- *"Keep `pyproject.toml` in sync with the package."*

**README**
- *"Be brutally brief … Aim for a screen or two. Long-form content belongs in `docs/`."*
- *"Never use the package name as the H1 title."* e.g. `lazy-qsar` → `# Lazy QSAR modelling for small molecules`.
- *"No AI-style filler. Skip generic Installation / Contributing / License / Acknowledgements boilerplate unless the project actually has something to say about it."*

**Releases**
- *"Semantic versioning only. Versions are `vMAJOR.MINOR.PATCH`."*
- *"PyPI releases via GitHub Actions … triggers on release (not on every push). The git tag,
  GitHub release name, and `[project].version` … must all match."*

**Data**
- *"`data/` is gitignored on purpose. Do not commit datasets, model artefacts, or large binaries to git."*
- Use `eosvc` with an `access.json` when reproducible data is needed.

## Reality check — what the audit will actually find

Of the nine Package repos surveyed, only `ersilia` uses NumPy docstrings, and only
`ersilia`, `ersilia-pack`, `isaura` and `olinda` have a `ruff.toml` or tests. Expect
`PKG-DOCSTRING-*` to dominate most reports. That is the real state of the codebase, not a
bug in the checker — report it plainly and let the maintainer decide the order of work.

Two ruff dialects exist. The audit enforces the `ersilia` one (`references/canonical-ruff.toml`)
because it is the only one that enforces the NumPy docstring rule the template mandates. The
tinygrad-derived dialect in `ersilia-pack`, `isaura` and `olinda` (2-space indent,
`preview = true`, no `D` rules, and leftover `tinygrad/runtime/autogen` excludes) is reported
as `PKG-RUFF-CONFIG-DRIFT`.

`olinda` is the cautionary example: its `CLAUDE.md` is the fullest statement of the package
standard in the whole org, and the repo violates it on three counts (295-line README,
`# Olinda` as H1, no `LICENSE` at all). A `CLAUDE.md` is not compliance.
