---
name: model-optimization
description: Makes an Ersilia Model Hub model smaller without changing its outputs. Traces the model at runtime on a cheap gate set (examples, 10 molecules, edge cases) to learn which packages are really loaded and called, summarises that per package and per install line, and decides the removals from it: CPU-only builds, unused or transitive packages, --no-deps trees, imports code/ never uses for inference. Gates each change on exact output equality (or a distribution check for Variable models), edge-case behaviour and a runtime-behaviour diff, diagnosing failures before bisecting and re-summarising after each kept change. Edits install.yml or a legacy Dockerfile, verifies on 100 molecules when the model's speed allows it (45-minute cap, otherwise 10) with a served-model run and `ersilia test --shallow`, and opens a PR with a size report. Runs unattended, once per model, thorough over fast. Triggers include "optimize eosXXXX", "make the model lighter", "reduce the image size", "the environment is too big", "remove unused packages", "use CPU-only torch", "/model-optimization".
argument-hint: <model_id> <model_path>
---

# Ersilia Model Optimizer (size)

Images are much bigger than the models inside them. The trained weights are usually a small part of the footprint. The rest is Python and its libraries, including packages the model never imports, packages it imports but never uses for inference, dependencies dragged in by other packages, and GPU support installed into models that only run on CPU. Your job is to remove that weight **without changing a single output value**, prove the model still works as it should, and hand it over as a pull request a reviewer can merge.

This skill runs **once per model**, so it is built to be thorough rather than fast. Spend runs where they buy certainty: trace before you guess, test the inputs that exercise the code, and verify the served model at the end. Don't spend runs on changes that can't pay off.

**Size only.** This skill does not attempt speed optimizations (batching, `no_grad`, loading checkpoints once, vectorizing loops, etc.), even if you notice obvious ones. Note them in `$WORK/log.md` for a future pass, but don't apply them. Computational performance is already recorded in the model's metadata and isn't re-measured here.

**You run unattended.** Don't ask for confirmation between steps. The only times you stop early are the stop conditions listed below. When you stop, say why in the final report.

## What you receive

- The **model ID** (`eos` + 4 alphanumeric chars, e.g. `eos4cxk`)
- The **local path** to the cloned model repository

If either is missing and can't be inferred from the working directory, ask. That is the only question you may ask.

## How to think about this job

These principles decide the many small calls the steps below leave to you:

1. **Evidence before edits.** What the model loads, calls and opens at runtime (the tracer) beats what `install.yml` declares or what `grep` finds. Never remove a package because it "looks unused"; remove it because the trace shows it isn't needed and the gate agrees.
2. **A pass only means as much as the inputs behind it.** Three example molecules exercise one code path. The gate set, the full set and the edge cases exist to reach the others (invalid SMILES, salts, charges, metals, very large molecules). If the plan shows imports in `code/` on lines that never ran, find an input that reaches them before you drop their package, or keep the package.
3. **Equal outputs are necessary, not sufficient.** A removed package can make a library quietly take a fallback path that gives the same numbers on 3 inputs and different ones elsewhere. The behaviour diff (`deps.py diff`) catches this: same packages loaded, same versions, no new failed imports.
4. **Be cost-aware with gates.** Every gate rebuilds an environment and runs the model several times. Group candidates that are safe together, isolate the risky ones, and skip changes that save less than ~10 MB: they add review noise for no real gain. Gates run on the 10-molecule gate set; the 100-molecule full set is for proving the model works, at baseline and in the final verification, and only when the model is fast enough to afford it.
5. **Diagnose, then bisect.** When a group fails, the error usually names the culprit (`ModuleNotFoundError: No module named 'x'`, a pip resolver conflict, a mismatch in one column). Revert that candidate only and re-gate. Bisect only when the failure doesn't point anywhere.
6. **Re-summarise after every kept change.** Removing one package can make others removable (and a CPU build changes the whole dependency tree). Summarise the candidate environment again until nothing worth gating is left.

## Scope and safety rules

This skill works only inside a model repository. It needs no changes to ersilia, ersilia-pack or eos-template, and must not make any.

**You may edit only:**

| File | What for |
|---|---|
| `install.yml` | CPU-only builds, removing unused packages, `--no-deps`, pins of needed dependencies |
| `Dockerfile` (legacy models only) | same as install.yml, but only the `RUN pip install …` / `RUN conda install …` lines |
| `model/framework/code/main.py` and auxiliary code under `model/framework/code/` | **only** to delete dead imports: import statements whose package never runs after it is imported and whose imported names are used on no line that ran (see `code_imports` in the summary), so that package can be dropped. Delete the whole statement (all its lines). No other code changes: don't rewrite annotations, don't make imports lazy, don't touch logic. |

**Never touch:** `model/framework/run.sh`, `model/checkpoints/`, `model/framework/examples/run_output.csv`, `metadata.yml` / `metadata.json`, or the directory structure. Never delete, move or rename folders. On legacy models, also never touch `src/service.py`, `pack.py`, or the Dockerfile's `FROM`, `MAINTAINER`, `WORKDIR /repo` and `COPY . /repo` lines. The `FROM` tag fixes the Python version and the base image, and the test requires the other two lines as they are.

### Two template formats

| | Current template | Legacy template (BentoML) |
|---|---|---|
| Dependencies | `install.yml` | `Dockerfile` (`RUN` lines) |
| Python version | `python:` key | `pyXY` tag on the `FROM` line (e.g. `bentoml/model-server:0.11.0-py38` → 3.8) |
| Metadata | `metadata.yml` | `metadata.json` |
| Extra files | none | `src/service.py`, `pack.py` (never touch) |

`run.sh`, `model/framework/code/`, the examples and the checkpoints look the same in both, so the gates, `run_model` and `build_env.py` work unchanged: `build_env.py` reads the Dockerfile when there is no `install.yml`, the same way `ersilia test` does. If a repo has both files, `install.yml` wins, both for `ersilia test` and here. Edit only `install.yml` then, and leave the Dockerfile alone.

**Dockerfile pin rules.** `ersilia test` validates every `RUN pip install` token against `^[A-Za-z0-9_\-\.\[\]]+(==|>=|<=|>|<)[A-Za-z0-9_\-\.]+$`. That means:
- A local version tag such as `torch==1.13.1+cpu` **fails** the check, because of the `+`. Keep the plain pin (`torch==1.13.1`) and select the CPU build through the index instead (see `references/optimization-patterns.md`, *Legacy Dockerfile models*). Then confirm with `pip freeze` in the candidate env that the `+cpu` build was really installed.
- The only flags the check skips are `--index-url`, `--extra-index-url`, `-f`, `--no-deps`, `--upgrade`, `--no-cache-dir` and `-r`. Use `-f`, not `--find-links`, which the check would read as an unpinned package.
- Keep one `pip install` per `RUN` line. Don't chain commands with `&&` or split them with `\`: each line is parsed and run on its own.

**Git writes only in Step 7.** Until then, keep the optimizations as uncommitted changes in the working tree. In Step 7, and only after the final verification has passed, create one branch, one commit containing only the edited files, push it and open one PR. Never push to the default branch, force-push, rewrite history or merge.

All scratch material (test reports, logs, backups, traces, scratch outputs) goes in a work directory **outside** the repository:

```bash
MODEL_ID=<model_id>
REPO=<model_path>
WORK=$(dirname "$REPO")/${MODEL_ID}-optimization
SKILL=<this skill's directory>          # contains scripts/, assets/ and references/
PY_ERS=$(conda run -n ersilia python -c "import sys; print(sys.executable)")
mkdir -p "$WORK"/{backup,out,traces,served}
```

### Bundled scripts

| Script | Run with | What it does |
|---|---|---|
| `scripts/build_env.py` | `$PY_ERS` | Builds a scratch conda env from install.yml / Dockerfile exactly as ersilia-pack would, and reports its size and GPU payload |
| `scripts/tracer/sitecustomize.py` | (loaded via `PYTHONPATH`) | When `OPT_TRACE_DIR` is set, records per process: modules loaded, env files opened or mapped, executables started, failed imports, and with `OPT_TRACE_COVER` / `OPT_TRACE_CALLS` the lines run in `code/` and the packages whose code ran after import |
| `scripts/env_inventory.py` | the **env's** Python | Every installed distribution with files, size and requirements, plus conda packages |
| `scripts/deps.py summary` | `$PY_ERS` | What the model really used: every package's runtime status and size, the dependencies each declared line alone installs, the GPU payload and the imports in `code/`. Facts only; you decide the changes |
| `scripts/deps.py diff` | `$PY_ERS` | Behaviour gate: baseline vs candidate traces and inventories |
| `scripts/compare_outputs.py` | `$PY_ERS` | `exact` / `distribution` output gates, and `sanity` for a reference output |
| `scripts/compare_reports.py` | `$PY_ERS` | Compares the before/after `ersilia test` JSON reports |
| `assets/edge_input.csv` | — | Edge-case molecules (single atom, salt, charged, stereo, isotope, boron, silicon, metal complex, long chain, peptide, invalid SMILES) |

## Stop conditions

Stop, leave the repository exactly as you found it, and report the reason if:

1. There is neither an `install.yml` nor a `Dockerfile`, or the Dockerfile has no `pyXY` tag on its `FROM` line, so the Python version can't be determined.
2. The baseline shallow test has any boolean check that is `false`. A model that doesn't pass isn't ready for optimization. Point the user to `/ersilia-model-test` and then `/model-fixing`.
3. The baseline scratch environment doesn't reproduce `run_output.csv` exactly (Fixed models), or doesn't give the same output twice in a row on the gate and edge inputs. The exact gate is meaningless if the baseline itself doesn't reproduce.
4. The working tree already has uncommitted changes to editable files. You couldn't separate your changes from the user's.
5. The baseline output fails `compare_outputs.py sanity` on the gate (or full) input (wrong row count, every cell empty, or every column constant across distinct molecules). Parity with a broken model proves nothing; report what you saw so someone can fix the model first.

## Workflow

### Step 0: Preflight

```bash
cd "$REPO"
git status --porcelain > "$WORK/git-status-before.txt"
git fetch origin && DEFAULT=$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's@^origin/@@')
git rev-list --count "origin/$DEFAULT..HEAD"   # must be 0, or the PR would carry unrelated local commits
git rev-list --count "HEAD..origin/$DEFAULT"   # if > 0 and the tree is clean: git switch "$DEFAULT" && git pull --ff-only
gh auth status                                  # needed for Step 7
if test -f install.yml; then DEPS=install.yml; elif test -f Dockerfile; then DEPS=Dockerfile; else echo "STOP: no install.yml or Dockerfile"; fi
grep -E "^(Output Consistency|Input):" metadata.yml 2>/dev/null || grep -E '"(Output Consistency|Input)"' -A1 metadata.json
```

Always optimize from the tip of `origin/$DEFAULT`. If HEAD is behind it (an old checkout, or a detached HEAD), fast-forward first, and only then record `git-status-before.txt` again. Otherwise the baseline measures a model that isn't the one the PR changes. If HEAD has local commits that aren't on `origin/$DEFAULT`, or `gh` isn't authenticated, still run the optimization, but record that Step 7 will be skipped and say why in the final report. Don't try to log in to `gh` yourself.

**Checkpoints stored in S3.** Many models keep `model/checkpoints/` out of git (it's in `.gitignore`, and `access.json` says `"checkpoints": "public"`). A fresh clone then has an empty `model/checkpoints/`, and the baseline test fails at "Model Fetching Check" with every run check `false`. That's a missing download, not a broken model, so don't apply stop condition 2 for it. Download the weights first, from the repo root, with an env that has `eosvc`:

```bash
eosvc download --path model/checkpoints    # e.g. conda run -n <env with eosvc> eosvc download --path model/checkpoints
rm -rf .eosvc                              # lock file eosvc leaves behind; not part of the repo
```

This only fills gitignored files, so it doesn't count as touching `model/checkpoints/`. Never upload with `eosvc`.

`$DEPS` is the dependency file you'll edit. Wherever this skill says `install.yml` below, it means `$DEPS`. Record `Output Consistency`: `Fixed` uses the **exact gate**, `Variable` uses the **distribution gate**. Record the `Input` type: the edge-case set applies only to `Compound` inputs. Read `$DEPS`, `model/framework/code/main.py` and everything under `code/` now. You'll need them to judge the plan.

### Step 1: Baseline measurement

Run the shallow test. It runs every check the gates rely on and reports the environment and directory size, which are the "before" numbers. No deep test is run: computational performance is already in the model's metadata, and this skill doesn't change speed.

```bash
cd "$WORK"
conda run -n ersilia ersilia test $MODEL_ID --shallow --from_dir "$REPO" 2>&1 | tee "$WORK/baseline-test.log"
mv "$WORK/${MODEL_ID}-test.json" "$WORK/baseline-test.json"   # also check $REPO if it's not in $WORK
```

Read `baseline-test.json`. Ignore values of `"not present"`. Apply stop condition 2 to the boolean checks. Record the environment size and directory size it reports. The test fetches and then deletes its own copy of the model, but it can leave files in the repository (a generated `install.sh`, CRLF/LF changes to example files). Compare against `git-status-before.txt` and undo anything the test run changed (see Cleanup).

### Step 2: Baseline environment, test inputs and traced reference runs

Build the environment that `install.yml` describes, as a scratch env you control. Name scratch envs `opt_<model_id>_*`, never `<model_id>_*`: when `ersilia test` (or `ersilia delete`) removes its copy of the model, it also removes every conda env whose name starts with the model ID.

```bash
$PY_ERS $SKILL/scripts/build_env.py --repo "$REPO" --name opt_${MODEL_ID}_base --recreate > "$WORK/env-before.json"
BASE=$(conda run -n opt_${MODEL_ID}_base python -c "import sys,os; print(os.path.dirname(sys.executable))")
$BASE/python $SKILL/scripts/env_inventory.py > "$WORK/inv-base.json"
```

Every model run goes through `run_model`, which puts the env's Python first on `PATH` and loads the tracer. `run.sh` calls `python <framework dir>/code/main.py <input> <output>`, so the tracer reaches main.py and every Python process it starts. Tracing doesn't change numerics (the exact gate against `run_output.csv` confirms it), and it records each run into its own trace directory:

```bash
EX="$REPO/model/framework/examples"
run_model () {  # args: env bin dir, input, output [, time limit in seconds] (trace goes to $WORK/traces/<output name>)
  # positional args are read through an array: "$" + digit in this file gets replaced by the skill's arguments
  local args=("$@"); local bindir="${args[0]}" input="${args[1]}" output="${args[2]}" limit="${args[3]:-0}"
  local tr="$WORK/traces/$(basename "$output" .csv)"; rm -rf "$tr"
  local start=$(date +%s)
  # with a limit, a run that doesn't finish in time is killed and its .exit is 124
  (cd "$REPO/model/framework" && PATH="$bindir:$PATH" PYTHONPATH="$SKILL/scripts/tracer" \
     OPT_TRACE_DIR="$tr" OPT_TRACE_COVER="$REPO/model/framework/code" OPT_TRACE_CALLS=1 \
     timeout --kill-after=30 "$limit" bash run.sh "$REPO/model/framework" "$input" "$output" > "$output.stdout" 2> "$output.log"; echo $? > "$output.exit")
  echo $(( $(date +%s) - start )) > "$output.time"
}
```

**Two test sets, for two different jobs.**

| Set | File | Molecules | Used for |
|---|---|---|---|
| **Gate set** | `gate_input.csv` | 10 | Every run while you change packages: baseline determinism, each group gate (Step 4), the traces behind the plan |
| **Full set** | `full_input.csv` | 100 | Only where you need to be sure the whole model works: the reference runs in Step 2 and the final verification in Step 5. Never inside a group gate |

A group gate runs again for every candidate, so it has to be cheap; 10 molecules plus the examples and the edge cases are enough to see a removed package break the model. The 100 molecules are what proves, once at the start and once at the end, that the optimized model gives the same answers on a realistic sample. Build both with the same deterministic generator, so that the gate set is the first 10 molecules of the full set:

```bash
conda run -n ersilia ersilia example $MODEL_ID -n 100 -m deterministic -o "$WORK/full_input.csv"
sed -i '1s/.*/smiles/' "$WORK/full_input.csv"     # run.sh expects a "smiles" header
head -11 "$WORK/full_input.csv" > "$WORK/gate_input.csv"
```

Copy the edge cases too (Compound inputs only): `cp $SKILL/assets/edge_input.csv "$WORK/edge_input.csv"`. Edge cases run as their own file because a model that crashes on one invalid molecule would otherwise lose the whole batch: what the gate compares is the **behaviour** (exit code plus output), whatever it is. If the model crashes on the whole edge file because of one molecule (typically the invalid SMILES), also keep `edge_valid.csv` with only the molecules it can process, so the other edge cases are really exercised. For other input types use `run_input.csv` and the gate/full sets only, and note in the log that no edge set was used.

Run the gate-set baseline:

```bash
run_model $BASE "$EX/run_input.csv"      "$WORK/out/base_example.csv"
run_model $BASE "$WORK/gate_input.csv"   "$WORK/out/base_gate_1.csv"
run_model $BASE "$WORK/gate_input.csv"   "$WORK/out/base_gate_2.csv"
run_model $BASE "$WORK/edge_input.csv"   "$WORK/out/base_edge_1.csv"
run_model $BASE "$WORK/edge_input.csv"   "$WORK/out/base_edge_2.csv"
```

- **Fixed:** `compare_outputs.py exact "$EX/run_output.csv" base_example.csv`, `exact base_gate_1.csv base_gate_2.csv` and `exact base_edge_1.csv base_edge_2.csv` (or, if the edge run produced no output, the same `.exit` code both times) must all PASS, otherwise stop condition 3 applies.
- **Variable:** run 3 times per input (`base_gate_1..3`, `base_example_1..3`, `base_edge_1..3`). As a self-check, `compare_outputs.py distribution --ref base_gate_1.csv --cand base_gate_2.csv` should PASS. If it doesn't, the distribution gate is too noisy for this model. Say so in the report and rely on the final checks (Step 5) alone.
- **Sanity:** `compare_outputs.py sanity "$WORK/gate_input.csv" base_gate_1.csv` must PASS (stop condition 5). Also read `base_edge_1.csv` and its log once: note how the model treats invalid molecules (empty row, NaN, crash). That is the behaviour candidates have to keep.

**Decide whether the full set runs, and where.** This is a judgement call, not a formula: 100 molecules buy confidence, but some models need hours for them, and every full run you start at baseline commits you to the same run in Step 5. Estimate the cost from the runs you already have. `base_example` (3 molecules) is mostly start-up, so the per-molecule cost is roughly `(t(base_gate_1) − t(base_example)) / 7`, and a 100-molecule run takes about `t(base_gate_1) + 90 × per-molecule`. Then:

| Estimated 100-molecule run | What to do |
|---|---|
| up to ~15 min | Run the full set in the scratch env (`base_full`, traced: the extra molecules feed the plan) and in the served baseline below. Repeat both in Step 5. |
| ~15–45 min | Run the full set **only in the served baseline and the served final run** (the environment users get), in the background with a **45-minute limit**. Keep the scratch env on the gate set. |
| clearly over 45 min (the 10 molecules alone took several minutes) | Don't start it. Use the gate set as the verification set in Step 5 and say so in the log and the report. |

Adjust with what you know of the model. Lean towards the full set when the code has branches that depend on the molecule (featurizers per atom type, conformer generation, size cut-offs) or when the plan shows `unexercised_imports`; a model with one code path for every molecule gains little from it. Variable models need the samples, so prefer the full set if they can afford it. A deterministic model that takes a second per molecule always runs it.

A full run that hits the limit (`.exit` is 124 with `run_model`, or no output file from the served run after 45 minutes; kill the served model then) isn't a failure of the model: drop the full set for the rest of the job, log the time it ran, and fall back to the gate set. Whatever you decide, the same set must be used before and after: never compare a full-set final run against a gate-set baseline. Record the decision and its reason in `$WORK/log.md` (`VERIFY_SET=full` or `VERIFY_SET=gate`, and where the full set runs).

If you run the full set in the scratch env:

```bash
run_model $BASE "$WORK/full_input.csv" "$WORK/out/base_full.csv" 2700
```

and apply sanity to it as well (`compare_outputs.py sanity "$WORK/full_input.csv" base_full.csv`). There is no need to run it twice: determinism is already checked on the gate set.

**Served baseline.** The scratch env lacks the serving layer that `ersilia fetch` adds (ersilia-pack and the packages it pins). Run the verification set (`full_input.csv` or `gate_input.csv`, as decided above) and the edge inputs through the real served model once now, so Step 5 can compare like with like:

`serve`, `run` and `close` must run in **one shell**: each `conda run` is a new process, and a model served in one is invisible to `ersilia run` in the next ("No model seems to be served"). Fetch from a **pristine copy** of the repository, in a folder named exactly like the model (`ersilia fetch --from_dir` takes the model ID from the folder name), so that the served baseline can run in the background while you edit the working tree in Steps 3–4 (a fetch reads the files while it runs):

```bash
rm -rf "$WORK/pristine" && mkdir -p "$WORK/pristine" && cp -r "$REPO" "$WORK/pristine/$MODEL_ID"
cd "$WORK" && conda run -n ersilia bash -c "
  ersilia fetch $MODEL_ID --from_dir '$WORK/pristine/$MODEL_ID' > '$WORK/served/fetch-base.log' 2>&1
  ersilia serve $MODEL_ID --disable-cache > '$WORK/served/serve-base.log' 2>&1   # no cache: Step 5 must not get these results back
  ersilia run -i '$WORK/<verification set>.csv' -o '$WORK/served/base_verify.csv' & pid=\$!
  for i in \$(seq 2700); do kill -0 \$pid 2>/dev/null || break; sleep 1; done   # 45-min limit
  kill \$pid 2>/dev/null; wait \$pid
  ersilia run -i '$WORK/edge_input.csv' -o '$WORK/served/base_edge.csv'
  ersilia close; ersilia delete $MODEL_ID"
```

Don't write `timeout 2700 ersilia run …`: ersilia finds the served model through the session of the parent shell, and under `timeout` the parent is `timeout` itself, so the run fails with "No model seems to be served". Running it in the background and polling it from the same shell keeps the shell as parent. Don't use a `(sleep 2700; kill …) &` watcher either: killing that subshell leaves its `sleep` alive holding the output pipe, and `conda run` then waits the full 45 minutes. The 45-minute limit only matters for the full set; with the gate set it never triggers. If it does trigger, apply the fallback above: switch `VERIFY_SET` to `gate` and run the served baseline again on `gate_input.csv`.

Check that the output files exist before you move on. If the fetch fails here although the shallow test passed, log it and skip the served comparison in Step 5; don't stop. Run Cleanup for the repository afterwards (fetch can leave files behind, just like the test).

### Step 3: Plan

Summarise what the baseline really used, then decide the changes yourself:

```bash
$PY_ERS $SKILL/scripts/deps.py summary --repo "$REPO" --inventory "$WORK/inv-base.json" \
  --traces "$WORK"/traces/base_* --json "$WORK/summary-1.json"
```

The summary states facts and proposes nothing. It has:

- `dists`: every installed package with its size, whether a line declares it, who requires it, and its runtime **status**:

| status | Meaning | Needed? |
|---|---|---|
| `called` | its code ran after the import | yes |
| `imported` | imported, but none of its code ran afterwards | yes, unless it is a dead import (below) |
| `files` | not imported, but a file of it was opened, mapped (`.so`) or executed | yes |
| `metadata` | only its `*.dist-info` was read (an entry-point or version scan) | no |
| `unused` | nothing of it was touched | no |

- `declared_lines`: for each pip line, the dependencies **only that line installs**, split into the used ones (with versions) and the unused ones (with sizes). This is what removing the line or adding `--no-deps` to it would drop.
- `gpu_payload`: GPU wheels (`nvidia-*`, `triton`, …) and the CUDA libraries bundled inside the torch wheel itself.
- `code_imports`: every import in `code/` that maps to an installed package, whether it ran, and whether the name it binds is used on any line that ran.
- `missing_imports`: imports that failed at baseline (optional dependencies the model already runs without).

**Turn the facts into changes.** Packages marked `ersilia-pack-utils`, `pip`, `setuptools` and `wheel` always stay. Then, in this order:

| Change | When the summary shows | Risk |
|---|---|---|
| **CPU build** (Tier 1) | `gpu_payload` above ~10 MB | low |
| **Remove a line** | a declared package that is `metadata` or `unused`, and whose deps listed under its line are unused too | low (medium if `code/` imports it) |
| **Remove a line, pin what it provided** | a declared package that isn't needed itself, but some deps only it installs are used: pin those, plain | medium |
| **`--no-deps`** | a needed declared package whose `unused` deps add up to ≥ 10 MB: install it with `--no-deps` and pin, with `--no-deps`, **only** the deps listed as used under its line | medium, high if ≥ 20 pins |
| **Dead import** | a `code_imports` entry that ran, whose name is used on no line that ran, and whose package is only `imported` (no code ran): delete the import statement (its full line span) and the package line | medium |
| **Remove a conda package** | a conda line whose package wasn't touched | medium |

Rules that keep the decisions safe:
- Never pin a `metadata` or `unused` package: it isn't needed, and pinning one with `--no-deps` can leave it half-installed (e.g. `pydantic` without `pydantic_core`) or clash with what the serving layer installs.
- An import in `code/` that never **ran** keeps its package. Read the code around it: if an input could reach that branch (an error path, a special molecule type, an optional featurizer), add such an input to `edge_input.csv`, re-run the baseline on it and summarise again. If no input can reach it (training-only code, a CLI branch `run.sh` never takes), leave it and note it in the log.
- A dead import whose module does registration or monkey-patching at import time (plugins, `torch` ops, RDKit `IPythonConsole`, `warnings` filters) is not dead.
- A package used only through a subprocess or a data file shows up as `files`; double-check models that shell out to tools (`obabel`, `java`, `xtb`).
- When there is a GPU payload, decide the rest after Tier 1: the CPU build changes the whole dependency tree, so summarise again from the candidate env.
- Skip changes that save less than ~10 MB: they add review noise for no real gain.

Write the chosen changes to `$WORK/log.md`, each with its group, its evidence from the summary (status, sizes) and the expected saving. Read `references/optimization-patterns.md` before you write any change: it has the correct idioms and the list of things that are never allowed.

### Step 4: Apply candidates in groups, gating each group

Group by risk, so that gates are spent where failure is plausible:

1. **Tier 1** (CPU build) alone. Then summarise again from the candidate env (below) before anything else.
2. All **low-risk** changes together.
3. Each **medium-risk** change on its own, largest expected saving first. Dead imports that protect each other (each keeps the other's package needed) go together as one change.
4. **High-risk** changes only if they save at least 100 MB, each on its own.

For each group:

1. **Back up** every file you're about to edit: `cp <file> "$WORK/backup/<file>.<n>"`, where `<n>` counts gates (the `.1` copy is the original).
2. **Apply** all candidates of the group at once, on top of what earlier groups kept. Keep each edit minimal, and match the file's existing style. `--no-deps` lines and the pins they need go after every other line (see the patterns reference for why). For a dead import, delete the whole statement, using the line span `code_imports` gives.
3. **Pin check.** Every pip entry in `install.yml` must stay version-pinned (`["pip", "<pkg>", "<version>", ...flags]`). In a Dockerfile, every package token must match the pin rules above. Check this by reading the file: the shallow test runs only at the end.
4. **Build** the candidate env and inventory it:
   ```bash
   $PY_ERS $SKILL/scripts/build_env.py --repo "$REPO" --name opt_${MODEL_ID}_cand --recreate > "$WORK/env-cand-<n>.json" 2> "$WORK/env-cand-<n>.log"
   CAND=$(conda run -n opt_${MODEL_ID}_cand python -c "import sys,os; print(os.path.dirname(sys.executable))")
   $CAND/python $SKILL/scripts/env_inventory.py > "$WORK/inv-cand-<n>.json"
   ```
   A failed install is a failed gate. For a torch change, confirm with `$CAND/pip freeze | grep -i torch` that the `+cpu` build was really installed.
5. **Smoke check** (seconds, before the slow runs): import every top-level module the baseline loaded that belongs to a package still installed, e.g. `$CAND/python -c "import rdkit, numpy, …"`. An `ImportError` here fails the gate without running the model.
6. **Run** the model on `run_input.csv`, `gate_input.csv` and `edge_input.csv` (plus `edge_valid.csv` if you made one) with `run_model $CAND …`, into `$WORK/out/cand<n>_*.csv` (3 runs each for Variable). Never the full set here: it belongs to Steps 2 and 5 only.
7. **Output gate:**
   - Fixed: `compare_outputs.py exact` of `run_output.csv` vs `cand<n>_example.csv`, `base_gate_1.csv` vs `cand<n>_gate.csv`, and `base_edge_1.csv` vs `cand<n>_edge.csv` (or the same `.exit` code if the baseline produced no output). All must PASS. There is no tolerance: a difference in the last decimal is a FAIL.
   - Variable: `compare_outputs.py distribution --ref base_gate_* --cand cand<n>_gate_*` must PASS, and so must the same check on the example and edge inputs.
8. **Behaviour gate:**
   ```bash
   $PY_ERS $SKILL/scripts/deps.py diff --base-traces "$WORK"/traces/base_gate_1 \
     --cand-traces "$WORK"/traces/cand<n>_gate --base-inv "$WORK/inv-base.json" \
     --cand-inv "$WORK/inv-cand-<n>.json" --removed <dists the group removes on purpose>
   ```
   It must PASS. Read its `warn` lines too: a package that is loaded now but wasn't at baseline, or an optional import that now fails, means the model took a different path. Accept that only when you can see in the code or the logs that the difference is cosmetic (a progress bar, a logging backend).
9. **Logs.** Compare `cand<n>_gate.csv.log` with `base_gate_1.csv.log` for new warnings or errors (`grep -iE "warn|error|fallback|not (installed|found|available)"`, ignoring timestamps and paths). A new message that mentions a removed package is a FAIL even if every check above passed.
10. **Keep, or diagnose and narrow.**
    - PASS: keep the whole group, and log the env size from `env-cand-<n>.json` and what was removed. Snapshot the state it leaves: `mkdir -p "$WORK/kept/<k>" && cp <each editable file> "$WORK/kept/<k>/"`, where `<k>` counts kept groups from 1 (`kept/0` is a copy of the original files, made before the first gate). Step 5 rolls back through these snapshots if the final verification fails.
    - FAIL with one candidate: restore its backup, and log the reason (the first mismatches, the diff verdict, or the error).
    - FAIL with several: first read the error. If it names a package or module (`No module named`, a resolver conflict, a `diff` line), restore just the candidate that owns it and re-gate the rest. If nothing points to a culprit, restore the backup, split the group in two halves and gate the first half; keep it if it passes, then gate the second half on top. Recurse until every candidate is kept or isolated.
11. **Summarise again** after every kept group, from the candidate env and its traces:
    ```bash
    $PY_ERS $SKILL/scripts/deps.py summary --repo "$REPO" --inventory "$WORK/inv-cand-<n>.json" \
      --traces "$WORK"/traces/cand<n>_* --json "$WORK/summary-<n+1>.json"
    ```
    Look for new changes worth a gate (Tier 1 typically exposes `--no-deps` and removal candidates in the torch dependency tree). Stop when nothing above ~10 MB is left.

Always gate against the **original** baseline references, never a previous group's output. Never "fix up" a failing group by touching forbidden files or loosening a gate.

### Step 5: Final verification

If no candidate was kept, skip to Step 6, report that nothing could be optimized safely, and don't open a PR.

Otherwise, check the final state in three independent ways.

1. **Scratch env, full gate.** Rebuild from the final files and repeat steps 4.4–4.9 once more (`env-after.json`, `inv-after.json`, outputs `final_*`). Compare against the original baseline. This catches an interaction between groups. If Step 2 ran the full set in the scratch env, also run `final_full` (same 2700 s limit) and compare it with `base_full.csv`; if the full set runs only in the served model, the scratch env stays on the gate set.
2. **Served model.** Run the verification set chosen in Step 2 (with the same 45-minute polling loop, not `timeout`) and the edge inputs through `ersilia fetch --from_dir "$REPO"` / `serve --disable-cache` / `run` in one shell, as in Step 2, into `$WORK/served/after_verify.csv` and `after_edge.csv`, then `ersilia close` and `ersilia delete $MODEL_ID`. Compare with `served/base_verify.csv` and `served/base_edge.csv`: `exact` for Fixed, `distribution` for Variable. This is the environment users get, with the serving layer installed on top of your changes. A fetch that hangs or fails here is a FAIL (see the `--no-deps` notes in the patterns reference).
3. **Shallow test.** Its size values are the "after" numbers:
   ```bash
   cd "$WORK"
   conda run -n ersilia ersilia test $MODEL_ID --shallow --from_dir "$REPO" 2>&1 | tee "$WORK/after-test.log"
   mv "$WORK/${MODEL_ID}-test.json" "$WORK/after-test.json"
   $PY_ERS $SKILL/scripts/compare_reports.py "$WORK/baseline-test.json" "$WORK/after-test.json" --checks-only
   ```

The optimization succeeds only if all of these hold:
- The final scratch-env output and behaviour gates pass.
- The served-model outputs match the served baseline (unless the served baseline was skipped in Step 2, which the report must say).
- `compare_reports.py` exits 0: no check that passed at baseline fails now.
- The environment size reported by the shallow test went down.

**If any of these fails, don't throw everything away.** A failure that only shows up here almost always comes from the serving layer, which the scratch env doesn't have, and usually belongs to one kept group. Find it and keep the rest:

1. **Diagnose first.** Read the failing check and its log, and match it to a kept group:

   | Symptom | Usual cause |
   |---|---|
   | `ersilia fetch` hangs at 0% CPU | `--no-deps` lines not last, or so many that pip's "which is not installed" stderr fills the pipe (patterns reference) |
   | `dockerfile_check` / install-file check `false` | a pin that breaks the format rules (`+cpu` in a Dockerfile, an unpinned token, `--find-links`) |
   | Import error or different output only in the served model | a `--no-deps` pin that clashes with a package the serving layer installs (`pydantic`, `packaging`, `numpy`, `psutil`, …): compare `pip freeze` of the served env with the scratch env |
   | Different output in the scratch env as well | an interaction between groups that no single gate saw |

   If the cause points to one group, restore the snapshot from **before** that group (`kept/<k-1>`) and re-apply every later kept group on top of it, then repeat the whole of Step 5 once.
2. **Otherwise, roll back one group at a time.** Restore the previous snapshot (`kept/<k-1>`, then `kept/<k-2>`, …) and repeat the whole of Step 5 on it. Keep the most advanced state that passes. Groups were applied from safest to riskiest (Tier 1 first), so the rollback normally drops the risky change and keeps the big, safe one.
3. **Bound the cost.** Each attempt is a rebuild, a served run and a shallow test. Stop once a state passes. If even `kept/1` fails, restore `kept/0` (the original), check with `git diff` that the repo is back to its starting state, report the failure and don't open a PR.

Log every attempt: which state, which check failed, why. In the report, list each group dropped at this stage with the reason, like the candidates reverted in Step 4. The sizes in the report are those of the state that passed. Don't try new changes at this point: only drop kept groups.

### Step 6: Report

Run the Cleanup section first, so that `git status` shows only your edits to editable files.

Write `$WORK/optimization-report.md`. It's the PR body. Keep it brief:

```markdown
## Optimization of <model_id>

| | Before | After | Change |
|---|---|---|---|
| Environment size | <X> MB | <Y> MB | −<Z> MB (−<P>%) |
| Directory size | <X> MB | <Y> MB | −<Z> MB |

**Changes:** <one line per kept change, e.g. "torch 2.2.2 → CPU wheel (−4.7 GB)", "removed unused `seaborn`", "removed import of `hyperopt` (training only) and the package">

**Verification:** outputs identical to `run_output.csv` and to the original environment on <N> molecules (100, or 10 if the model was too slow for the full set: say which) and <M> edge-case inputs (or: distribution check), in a scratch env and through `ersilia fetch`/`run`; same packages loaded at runtime with the same versions; `ersilia test --shallow` passes before and after.
```

Take the sizes from `baseline-test.json` and `after-test.json`. Add one line listing reverted candidates only if there were any, and one line for any package you kept only because its import could not be exercised.

### Step 7: Open the PR

Do this only if Step 5 succeeded, HEAD had no local-only commits, and `gh` is authenticated (all recorded in Step 0). Otherwise skip it and say which condition failed.

```bash
cd "$REPO"
BRANCH=optimization/${MODEL_ID}-$(date +%Y%m%d)
git switch -c "$BRANCH"
git add -- <each file you edited>          # never `git add -A` or `git add .`
git diff --cached --name-only              # must list only install.yml / Dockerfile / files under model/framework/code/
git commit -m "Optimize ${MODEL_ID}: <headline, e.g. CPU-only torch, drop unused deps (-6.7 GB env)>"
git push -u origin "$BRANCH"
gh pr create --repo ersilia-os/${MODEL_ID} --base "$DEFAULT" --head "$BRANCH" \
  --title "Optimize ${MODEL_ID}: <same headline>" --body-file "$WORK/optimization-report.md"
```

- If the staged file list includes anything outside the editable set, unstage it and find out where it came from before you commit.
- If the push is rejected for lack of permission, push to a fork instead: `gh repo fork --remote --remote-name fork`, then `git push -u fork "$BRANCH"`, and pass `--head <fork-owner>:$BRANCH` to `gh pr create`.
- If a branch with that name already exists on the remote, add a suffix (`-2`). Never overwrite a remote branch.
- Write the PR URL into `$WORK/log.md`.

Then give the user a short summary in the terminal: size before/after, the files changed, how it was verified (number of inputs, served run), the path to the report, and the PR URL. If you skipped Step 7, say why, and say that the changes are still uncommitted in the working tree.

## Cleanup

Run this after every `ersilia test` or `ersilia fetch` for the repository part, and in full before Step 6.

- After every `ersilia test` or served run, kill the model processes left behind: `ps -eo pid,args | grep "eos/repository/${MODEL_ID}/" | grep -v grep`. Idle model servers keep their memory. Only kill processes under `eos/repository/${MODEL_ID}/` that were started after your baseline test, never other models' processes. Don't use `pkill -f` with a pattern that also appears in your own command line, because it kills your shell.
- Remove the scratch envs: `conda env remove -n opt_${MODEL_ID}_base -y` and `conda env remove -n opt_${MODEL_ID}_cand -y`.
- In the repository, compare `git status --porcelain` with `$WORK/git-status-before.txt`. Delete any **untracked** file that the test or fetch runs created (e.g. `install.sh`, `<model_id>-test.json`). For any **tracked** file outside the editable set that they modified (e.g. line endings in `run_input.csv`), run `git checkout -- <file>`, but only if it was clean in `git-status-before.txt`.
- Delete `__pycache__` directories the traced runs created under `model/framework/code/` if they were not there before (check `git-status-before.txt`; they are normally gitignored).
- Keep `$WORK`. It holds the evidence behind the report: plans, traces, outputs and logs.

## Model template structure (for reference)

```
<model_id>/
├── model/
│   ├── framework/
│   │   ├── run.sh              ← NEVER modify
│   │   ├── code/
│   │   │   ├── main.py         ← editable (dead-import removal only)
│   │   │   └── ...             ← editable (dead-import removal only)
│   │   ├── examples/
│   │   │   ├── run_input.csv   ← do not modify
│   │   │   └── run_output.csv  ← NEVER modify (the reference for the exact gate)
│   │   └── columns/
│   │       └── run_columns.csv ← do not modify
│   └── checkpoints/            ← NEVER modify
├── metadata.yml                ← do not modify
└── install.yml                 ← editable
```

Legacy (BentoML) template, where the tree under `model/` is the same:

```
<model_id>/
├── model/                      ← as above
├── src/service.py              ← NEVER modify
├── pack.py                     ← NEVER modify
├── metadata.json               ← do not modify
└── Dockerfile                  ← editable: RUN pip/conda install lines only
```
