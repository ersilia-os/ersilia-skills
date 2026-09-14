---
name: isaura-retrieval
description: >
  Retrieve precalculated Ersilia model predictions for one or more molecules from isaura,
  Ersilia's precalculation store. Given a SMILES string or a file of SMILES plus an Ersilia
  model ID (eosxxxx), this checks the local isaura store first, pulls anything missing from
  the remote store, and writes the results to a CSV — reporting clearly which molecules were
  found and which are not in isaura at all. Use this skill whenever the user wants stored,
  cached or precalculated predictions instead of running inference. Triggers include:
  "get the precalculations for", "does isaura have", "is this molecule in isaura",
  "retrieve predictions for eos1234", "pull from isaura", "check the precalculation store",
  "do we already have results for these smiles", "/isaura-retrieval", "look up these
  molecules in isaura", "fetch stored outputs for this model". Always use this skill for
  isaura retrieval requests even if the ask looks like a one-liner — the CLI has failure
  modes that are easy to trip and this encodes the working sequence.
---

# Isaura retrieval

Isaura is Ersilia's precalculation store. It holds model outputs that were computed once so
nobody has to recompute them. There are two stores: a **local** one (MinIO in Docker, on this
machine) and a **remote** one (Ersilia's cloud). The local store is fast; the remote store is
the source of truth. The job of this skill is to get a user their predictions from whichever
store has them, and to be honest when neither does.

## The one rule that matters

**Only use the `isaura` CLI.** Never reach into MinIO with `boto3`, `mc`, the MinIO console,
or DuckDB against the Parquet files directly, and never import `isaura.manage` to do the work
by hand. The store's layout (hive prefixes, bloom indices, chunked Parquet, catalog files) is
an internal detail that changes between versions — code that bypasses the CLI silently returns
wrong or partial answers, and can corrupt the local store on write. If a CLI command seems not
to do what you need, say so rather than working around it.

## Prerequisites

Isaura is normally installed in the `ersilia` conda environment, so `isaura` is usually not on
the default PATH. Each `Bash` call starts a fresh shell, so the environment has to be activated
in the same command as the `isaura` call:

```bash
source "$(conda info --base)/etc/profile.d/conda.sh" && conda activate ersilia && isaura --help
```

If that fails, check whether `isaura` is already on PATH (`which isaura`) before concluding it
is missing — some setups install it globally or in a different environment. If you genuinely
cannot find it, say so and stop; do not try to install it.

The CLI renders rich progress spinners that carriage-return over themselves. To read the
output, pipe it through `tr '\r' '\n'`, then filter — otherwise a single line of spinner frames
buries the result you care about.

Paths written as `scripts/...` below are relative to this skill's folder, not to the working
directory. The helper is plain Python with no third-party dependencies, so it runs under any
interpreter — it does not need the `ersilia` environment.

## Step 1 — Understand the request

You need two things: **the molecules** and **the model ID**.

- Molecules can arrive as a single SMILES in the prompt, a list in the prompt, or a path to a
  CSV/TXT file. All three are fine.
- The model ID is the `eosxxxx` identifier. If the user gives a model *name* instead
  ("the antimicrobial activity one"), ask which `eos` ID they mean rather than guessing — a
  wrong ID silently returns "not in isaura", which is a misleading answer.
- Version is optional. Omit `--version` and isaura resolves the latest stored version itself;
  this is almost always what you want, because different models sit at v1, v2 or v3. Always
  report back which version was actually used — isaura prints it as
  `No version specified — using latest: v2`.
- Project bucket defaults to `isaura-public`. Only use a different one if the user names it.

## Step 2 — Preflight the local engine

The local store is a MinIO container. If it is down, every local command fails in a confusing
way, so check first:

```bash
isaura engine --status
```

If Docker or minio is not running, **stop and tell the user** — say that the local isaura
engine is down and that `isaura engine --start` will bring it up. Do not start it yourself;
starting containers on someone's machine is their call, not yours.

## Step 3 — Normalise the inputs

Isaura's commands disagree about input columns: `read` and `pull` accept a column named
`input` *or* `smiles`, but `inspect` only ever looks at `input`. Since the sequence below
relies on `inspect`, normalise everything to a CSV with a single `input` column up front.
Duplicates are also worth collapsing — they inflate the counts you report without adding
information.

Use the bundled helper rather than writing this again each time:

```bash
python scripts/prepare_inputs.py normalize --input <file-or-SMILES> --output inputs.csv
```

It accepts a file path (CSV with any of `input`/`smiles`/`SMILES`, or a plain one-per-line
text file) or a literal SMILES string, deduplicates while preserving order, and writes a
clean `input`-column CSV. It prints the molecule count, which you will need for the report.

Work in the current working directory unless the user says otherwise. Name outputs
`<model_id>_isaura_results.csv` and `<model_id>_isaura_missing.csv`. Keep the intermediate
files (`inputs.csv`, the inspect outputs) in a scratch location — they are plumbing, not
deliverables.

> Filename trap: `read` refuses to run if the output filename contains an `eosxxxx` that
> differs from `--model-id`, and exits 1. Naming outputs after the model keeps you safe;
> never name an output file after a *different* model.

## Step 4 — Is the model in the local store at all?

```bash
isaura catalog -pn isaura-public 2>&1 | tr '\r' '\n' | grep -v "Fetching catalog" | grep <model_id>
```

A hit shows `model/version`, row count and size. A miss means the model has no local data, and
you can skip straight to the remote path in Step 6 — no point inspecting molecules for a model
that isn't there.

## Step 5 — Which molecules are in the local store?

This is the step that makes the whole thing work, and it is the one that is tempting to skip.

`isaura read` is **all-or-nothing**: it checks every requested input against a bloom index and,
if even one is absent, it aborts with `inputs not indexed: [...] total_missing=N` and returns
nothing at all — not even the molecules it *does* have. So never point `read` at a set you
have not already confirmed is fully present. The same applies to `pull`, which uses the same
reader internally.

`isaura inspect` is the safe probe: it takes your input CSV and writes out only the molecules
that are present, without failing on the ones that aren't.

```bash
isaura inspect -m <model_id> -pn isaura-public -i inputs.csv -o local_found.csv
```

Then split your inputs against that result:

```bash
python scripts/prepare_inputs.py diff --input inputs.csv --found local_found.csv --output local_missing.csv
```

> If nothing is found, `inspect` writes an **empty file with no header** — not a CSV with zero
> rows. Treat "file is empty" as "nothing found"; the helper handles this.

Three outcomes:

- **All molecules found locally** → go to Step 7 and read them. Nothing needs pulling.
- **Some found** → read what is there later, but first try the remote for the rest (Step 6).
- **None found** → go to Step 6.

## Step 6 — Try the remote store for whatever is missing

Inspect the remote for *only the missing molecules*, not the whole original set:

```bash
isaura inspect -m <model_id> -pn isaura-public -i local_missing.csv -o remote_found.csv -r
```

This is fast (seconds), because it only reads the remote index.

If `remote_found.csv` has molecules, pull them into the local store. Pull the **inspect
output**, never the raw missing list — pulling a set containing molecules the remote lacks
trips the same all-or-nothing abort:

```bash
isaura pull -m <model_id> -pn isaura-public -i remote_found.csv
```

Pull is the slow step (tens of seconds for a handful of molecules, longer for large sets and
wide models) because it fetches from the cloud and writes into local MinIO. Let it finish; it
prints `✓ <model>/<version> pulled N rows`. After it completes, those molecules are in the
local store and behave exactly like anything else that was already there.

If `remote_found.csv` is empty, the molecules genuinely are not in isaura. Before reporting
that, distinguish the two reasons — they mean very different things to the user:

```bash
isaura catalog -pn isaura-public -r 2>&1 | tr '\r' '\n' | grep -v "Fetching catalog" | grep <model_id>
```

- Model absent from the remote catalog → **the model has no precalculations at all**. The user
  needs to run inference, or ask for the model to be precalculated.
- Model present but molecules absent → **the model is precalculated, but not for these
  molecules**. Isaura stores a fixed reference library, so arbitrary SMILES frequently miss.
  This is the common case and is not an error.

The remote catalog is large and takes up to a minute, so only run it to explain an empty
result — not as a routine check.

## Step 7 — Read the results

Build the final read set: everything confirmed present locally in Step 5, plus everything
successfully pulled in Step 6.

```bash
python scripts/prepare_inputs.py merge --inputs local_found.csv remote_found.csv --output readable.csv
isaura read -m <model_id> -pn isaura-public -i readable.csv -o <model_id>_isaura_results.csv
```

If `readable.csv` is empty, skip the read entirely — there is nothing to retrieve, and running
`read` on an empty set just produces noise.

The results CSV has a `key` column (an internal hash), an `input` column (the SMILES) and one
column per model output. Confirm the row count isaura reports (`✓ <model>/<version>: N rows`)
matches what you expected; a mismatch is worth investigating rather than glossing over.

Finally, write the molecules that were never found anywhere to
`<model_id>_isaura_missing.csv`, so the user can feed that file straight into an inference run.
Skip the file if nothing was missing.

## Step 8 — Report

Report in the terminal, concisely. The user wants to know: did I get my data, where is it, and
what didn't I get. Use this shape:

```
## isaura retrieval — <model_id> (<version>)

<N> molecules requested

- Found in local store: <N>
- Pulled from remote store: <N>
- Not in isaura: <N>

Results: <path to results CSV>  (<N> rows, columns: <output column names>)
Missing: <path to missing CSV>   (omit this line if nothing is missing)
```

Then add one or two sentences of interpretation, if there is anything to interpret — for
example that the model has no precalculations at all, or that the missing molecules are
outside isaura's reference library and would need a fresh `ersilia run`. Do not pad the
report with the commands you ran; the user can ask.

If everything was already local, say so plainly — that is the fastest, happiest path and worth
a single sentence, not a ceremony.

## When things go wrong

**`inputs not indexed: [...] total_missing=N`** — a `read` or `pull` was given molecules the
target store doesn't have. This is the all-or-nothing abort from Step 5. Go back and inspect
first; don't retry the same command.

**`Filename and --model-id do not match`** — the output path contains a different `eosxxxx`.
Rename the output.

**`Could not connect to local MinIO` / `Is Docker running?`** — the engine is down. Report it
and point at `isaura engine --start` (Step 2).

**`No remote credentials configured`** — the remote store has never been set up here. Report
it and point at `isaura configure --remote`. Local results, if any, are still valid; say what
you got before saying what you couldn't.

**`No molecule column found in <file>`** — the input CSV lacks an `input`/`smiles` column.
Normalising with the helper in Step 3 prevents this; if it still happens, look at the file.

## Reference

For anything this skill doesn't cover, the authoritative source is the isaura repository
(`github.com/ersilia-os/isaura`): its `README.md` and `docs/API_AND_CLI_USAGE.md` document
every command, and `docs/TROUBLESHOOTING.md` covers recovery from a damaged local store. If
the repository happens to be cloned locally, read it there. Prefer reading the docs over
experimenting against the store.
