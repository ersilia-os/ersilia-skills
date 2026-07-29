# Canonical CLI vocabulary

Ersilia packages are thought of as simple APIs and CLIs, and a user who has learned one
should be able to guess the next. `ersilia-os/ersilia` is the reference implementation, so
its vocabulary is the canon — with one correction, below.

## Command verbs

`ersilia` exposes eleven, all in `ersilia/cli/commands/`:

```
catalog  close  delete  example  fetch  info  publish  run  serve  test  uninstall
```

When a new CLI needs a command that means the same thing as one of these, **use the
canonical verb**. The synonyms worth catching:

| Instead of | Use | Because |
|---|---|---|
| `download`, `get`, `pull` | `fetch` | `ersilia fetch <model>` is the verb every user already knows |
| `execute`, `predict`, `infer`, `apply` | `run` | `run` is the canonical execution verb |
| `start`, `up`, `host` | `serve` | matches `ersilia serve` |
| `remove`, `rm`, `del`, `uninstall`* | `delete` | *`uninstall` is canonical for removing the tool itself, `delete` for removing a model |
| `list`, `ls`, `index`, `browse` | `catalog` | matches `ersilia catalog` |
| `describe`, `show`, `about`, `card` | `info` | matches `ersilia info` |
| `check`, `validate`, `verify` | `test` | matches `ersilia test` |
| `sample`, `demo` | `example` | matches `ersilia example` |

Domain verbs with no canonical equivalent are fine and should not be flagged — `fit`,
`build`, `train`, `embed`, `score`, `annotate` all pass untouched. The rule is about not
inventing a second word for a thing that already has one.

## Input and output

```
-i, --input     the input file
-o, --output    the output file
```

Both the short and the long form. `ersilia`'s `run` uses exactly this pair. Names to avoid
for file arguments, because they fragment the vocabulary: `--infile`, `--in`, `--source`,
`--from`, `--outfile`, `--out`, `--dest`, `--destination`, `--target`, `--result`,
`--output-file`.

## Multiword options: kebab-case

```
--batch-size      not  --batch_size
--from-github     not  --from_github
--output-file     not  --output_file
```

**This is a ruling, not an observation.** `ersilia`'s own CLI is split — 14 snake_case
options against 5 kebab-case — so "match ersilia" was not an answer. kebab-case wins for
three reasons:

1. It is the Click and POSIX convention. Click maps `--batch-size` to a `batch_size`
   parameter automatically, so **nothing in the Python changes** — this is a rename of the
   flag string only.
2. It is what `ersilia`'s more recently added options already use (`--write-store`,
   `--read-store`, `--tracking-use-case`, `--max-cache-memory-frac`), so the org is drifting
   this way regardless.
3. Mixing the two inside one CLI — which `ersilia` currently does — is worse than either.

### Consequence for `ersilia` itself

Under this rule `ersilia` is non-compliant on 14 options: `--batch_size`, `--from_dir`,
`--from_dockerhub`, `--from_github`, `--from_hosted`, `--from_s3`, `--file_name`,
`--n_samples`, `--output_file`, `--report_path`, and a few more. That is the honest result
and should be reported rather than special-cased — the same way the ruff-dialect ruling makes
`ersilia-pack`, `isaura` and `olinda` non-compliant. It is a mechanical rename, and Click
accepts both spellings simultaneously if a deprecation window is wanted.

Separately, and worth fixing on its own terms: `ersilia` has a typo in a public flag,
`--nearest-neigbors` (missing the `h`).

## Framework

Click, not argparse. From the package template's `CLAUDE.md`:

> **Use Click.** If the package exposes a CLI, build it with Click, organised as
> `src/<package>/cli/commands/` with one file per command and a small `create_cli.py` that
> registers them.

`eosquality` uses argparse with a `register_subparsers` function per command — a reasonable
shape, but against the rule and against `ersilia`.

## Documentation

CLI commands go in the README as a **compact two-column table** (command → one-line
description). Not prose per flag, and not a paste of `--help`.

## What the checks do and do not cover

Covered: separator style, near-synonym verbs, the `-i`/`-o` pair, I/O naming, and mixing
separators within one CLI.

Not covered, deliberately: help-text presence and phrasing. `ersilia`'s own option help is
inconsistent enough that there is no canon to check against, and a missing help string is a
weaker defect than a divergent name.
