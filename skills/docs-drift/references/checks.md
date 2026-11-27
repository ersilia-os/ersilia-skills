# Checks

Every deterministic check in `scripts/check_drift.py`, what it compares and why it has its
severity. **High**: a reader who follows the text fails. **Medium**: the text is wrong or
unreachable, but nothing breaks for a reader. **Low**: still works, worth fixing with other
changes on the same page.

| Check | Severity | Compares | Notes |
|---|---|---|---|
| `cli-command` | high | `ersilia <cmd>` in code spans and blocks | Against the commands registered with `@ersilia_cli.command` in `ersilia/cli/commands/`. Placeholders (`<MODEL>`, `[OPTIONS]`, `COMMAND`) are skipped. |
| `cli-flag` | high | Options after a command, and global options | Against that command's click options. `-` and `_` are equivalent, as in the CLI. Hidden options count as valid. |
| `repo-missing` | high | `github.com/ersilia-os/<repo>` links | The repo neither exists nor redirects (deleted, or private). Template names (`eosXabc`, `my-…`, `your-…`, `example…`) are skipped. |
| `repo-file-missing` | high | `/blob/` and `/tree/` links | The branch exists but the file is gone. |
| `summary-missing` | high | `book/SUMMARY.md` entries | The listed file does not exist. |
| `broken-placeholder` | high | `/broken/pages/…` links | GitBook leaves these when a link's target page is deleted. |
| `relative-link` | high | Relative links between Book pages and to assets | Code spans and blocks are ignored, so SMILES such as `[N+](=O)` are not read as links. |
| `repo-branch-missing` | medium | `/blob/<ref>/…` links | The branch or commit no longer exists. |
| `python-version` | medium | `conda create -n <env> python=X.Y` | Against `requires-python` in the package's `pyproject.toml`. Only when the env is the package's own (same name as the repo or package); other envs have their own needs. |
| `orphan-page` | medium | Book pages not in `SUMMARY.md` | Unless `hidden: true`. Other findings on an orphan page are folded into it, since nobody can reach the page. |
| `hidden-in-summary` | medium | Sidebar entries for `hidden: true` pages | The Book's own convention (its `CLAUDE.md`). |
| `external-link` | medium | Other URLs, opt-in | Only 404, 410 or a domain that does not resolve; 403, 429 and timeouts are not proof a page is gone. |
| `repo-renamed` | low | Org repo links | GitHub redirects, until a new repo takes the old name. |
| `repo-archived` | low | Org repo links | Often fine (history), but the text may present an archived tool as current. |

## Not covered (on purpose)

- Model repo READMEs: generated from metadata.
- Relative links inside one repo's README: `repository-auditing` checks those.
- Prose accuracy: the agent's judgement pass (SKILL.md, Step 4), capped per run.
- The workshops GitBook (`ersilia.gitbook.io/ersilia-workshops`): its source repo is not
  confirmed yet. Add it as a second Book once it is.
