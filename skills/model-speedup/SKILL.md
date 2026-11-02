---
name: model-speedup
description: Makes a given Ersilia Model Hub model faster, and stops its memory from growing with the input, without changing its outputs. The user names the model (ID and local path). Measures the original on 10 and 100 molecules (twice, to check it is deterministic) and on 1000 when its memory grows with the input, profiles where the time goes including subprocesses, all on a container-sized budget of 2 CPUs, matches it against known patterns (setup repeated per molecule, thread/process pools for one item, duplicated computation, work whose result is never used, slow checkpoint formats, whole-input batches kept for autograd, worker pools that copy the model into each worker), applies changes one at a time with simple, commented code, and gates each on outputs identical to the original and on peak memory that does not grow with the input. Verifies the served model (ersilia fetch/serve/run against the original) and runs `ersilia test --shallow`. Writes a very brief optimizations.md in the model folder, stores original and optimized outputs for the user to re-test, and reports speed-ups and test commands. Does not commit or push. Triggers include "make eosXXXX faster", "speed up eosXXXX", "optimize the speed of this model", "this model is too slow", "why is eosXXXX slow", "eosXXXX uses too much memory", "eosXXXX runs out of memory / gets OOM-killed", "/model-speedup".
argument-hint: <model_id> <model_path>
---

# Ersilia Model Speed-up

Many slow models are not slow because of their science. They reload a checkpoint for
every molecule, start 30 threads to predict one row, compute the same descriptors
twice, or optimize 300 conformers to use one. Others are not slow but hungry: their
memory grows with the number of molecules (eos9o72: 1.6 GB at 100 molecules, 11 GB at
1000) or with the number of workers (eos8aa5: the model copied into 16 workers), until
the container kills them. Your job is to find that waste, remove it **without changing
a single output value**, and hand back code a reviewer can read in a minute.

## What you receive

- The **model ID** (`eos` + 4 characters, e.g. `eos4e40`), picked by the user.
- The **local path** to the cloned model repository.

If the path is missing, clone `https://github.com/ersilia-os/<model_id>` next to the
other optimized models (ask where if that is unclear). That is the only question
you may ask before the final report.

## Principles

1. **Identical outputs, or it isn't done.** Every change is gated on `compare.py`
   reporting the output identical to the original's, cell by cell. "Probably the same
   science" is not a pass. The only exception is an original that is not reproducible
   itself (see Step 2); then the bar is "no bigger than the original's own run-to-run
   difference", and you report both numbers.
2. **Measure before you change.** The profile decides what to fix, not a hunch from
   reading code. Subprocesses hide time from cProfile; `profile_model.py` shows them.
3. **One change at a time.** Gate each change on its own, so a failure points at its
   cause and the final report can give each change's gain.
4. **Simple code, explained.** Prefer the smallest edit that removes the waste. Mark
   each change with a comment starting `# OPTIMIZATION:` that says what was slow and
   why the change keeps the results the same. Match the surrounding code's style.
5. **Know the traps.** Most failed gates in practice came from random state, thread
   count and batch size, not from logic errors. Read `references/pitfalls.md` before
   concluding why a gate failed.
6. **No added parallelism, and time on a container budget.** Models run in Docker
   containers, often with few CPUs or several containers on one machine, so speed must
   come from removing work, not from more threads or processes. Never add
   multiprocessing, worker pools, `n_jobs` > 1, `numThreads=0`, `nproc` > 1 or higher
   `OMP_NUM_THREADS` / `-P` values. Removing parallelism the original uses for tiny work
   (pattern 2) is allowed, and so is making a pool the original already has fit its
   container (pattern 7: model loaded once before forking, worker count bounded by CPUs
   and memory, never above the original's). Don't test parallel variants as candidates
   either; at most mention them in the report. For the same reason, every local run (baseline, profile,
   gates, final timing) uses `--cpus $CPUS` (2 CPUs): a speed-up measured on all the
   cores of a workstation can vanish in a container.
7. **Faster, not hungrier.** Loading once or running all molecules in one call trades
   time for memory, and a model that runs out of memory in its container is broken,
   not fast. `run_model.py` reports the peak memory of every run; a kept change must
   not make memory grow with the number of molecules (see Step 4). If the *original's*
   memory already grows with the input (patterns 6 and 7), fixing that is a goal in its
   own right, worth doing even when it gains no time.
8. **Report honestly.** Say what was not applied and why (e.g. "~9x faster but changes
   3 of 1,000 molecules"). The user decides about trade-offs; you don't apply them.

## Scope

You may edit files under `model/framework/code/` (including vendored libraries, unless
their licence forbids it; then put the faster version in Ersilia's own file) and, only
for pattern 5, `model/checkpoints/` (new checkpoint file, `.gitattributes` LFS entry).

Never touch `run.sh`, `metadata.*`, `install.yml` / `Dockerfile` (dependencies are the
`model-optimization` skill's job), `src/service.py`, `pack.py`, or
`examples/run_output.csv` (it must still match, since outputs are identical).
**Never commit or push**; the user does that after testing.

## Bundled files

| File | Use |
|---|---|
| `scripts/run_model.py` | Run `main.py` with an env's Python (env bin/ first on PATH), optionally on the first N CPUs (`--cpus`); report time and peak memory of the whole process tree (`peak_rss_mb`, and `peak_pss_mb`, which counts memory shared between worker processes once); compare with a reference. |
| `scripts/compare.py` | Cell-by-cell comparison; when different, reports rows, blank mismatches and max abs/rel difference. |
| `scripts/profile_model.py` | cProfile of `main.py` plus a table of every subprocess with its time. Run with the env's Python. |
| `assets/input_10.csv`, `assets/input_100.csv` | Standard test molecules. |
| `assets/edge_input.csv` | Edge cases: invalid SMILES, salts, charges, metals, very large molecules. |
| `references/patterns.md` | The seven patterns (five slow, two memory): signs, fix, real examples. |
| `references/pitfalls.md` | Why "harmless" changes alter outputs, from real cases. |

`SKILL_DIR` below is this skill's folder.

## Stop conditions

Stop and report (no changes kept) when:
- the model calls a remote API for its predictions (the time is the network);
- the environment cannot be built, or the original fails on `input_10.csv`;
- the original takes more than ~30 min on 10 molecules (too slow to gate reliably;
  report the profile and candidate fixes instead);
- no candidate gives at least ~1.2x after gating, and the original's memory does not
  grow with the input (if it does, a change that bounds it is enough to keep).

## Workflow

### Step 0: Preflight

```bash
MODEL=<model_id>; REPO=<model_path>
WORK=$(dirname $REPO)/$MODEL-optimization        # results folder the user keeps
CPUS=2                                            # CPU budget for every local run (Principle 6)
mkdir -p $WORK/served $WORK/pristine
git -C $REPO status --short                       # must be clean; if not, ask
git -C $REPO status --porcelain > $WORK/git-status-before.txt
cp -r $REPO $WORK/pristine/$MODEL                 # pristine copy to run the original
```
The pristine folder is named exactly like the model, because `ersilia fetch
--from_dir` takes the model ID from the folder name (Step 5). Record `nproc` and the
CPU model (`lscpu | grep 'Model name'`) in `$WORK/log.md`: timings are only
comparable on the same machine.

Note the template (install.yml or legacy Dockerfile), `Output Consistency` in the
metadata, and the timings in the metadata (`Computational Performance 1..5`, seconds
for 1/10/100/1000/10000 inputs): a large constant time points to pattern 5, linear
growth of several s per molecule to pattern 1.

### Step 1: Environment

Build the env from the repo's install.yml or Dockerfile (e.g. with
`../model-optimization/scripts/build_env.py --repo $REPO --name speed_$MODEL`, or
`conda create` + the pinned installs). Never start the env name with the model ID:
`ersilia delete $MODEL` (Step 5) removes every conda env whose name starts with it.
Afterwards check that pinned packages kept their versions (conda can upgrade them).
`PY=<env>/bin/python`.

### Step 2: Baseline

```bash
R="$SKILL_DIR/scripts/run_model.py --cpus $CPUS"; O=$WORK/pristine/$MODEL
python $R --python $PY --repo $O --input $SKILL_DIR/assets/input_10.csv  --output $WORK/original_10.csv
python $R --python $PY --repo $O --input $SKILL_DIR/assets/input_10.csv  --output $WORK/original_10_run2.csv \
          --reference $WORK/original_10.csv            # determinism check
python $R --python $PY --repo $O --input $SKILL_DIR/assets/edge_input.csv --output $WORK/original_edge.csv
python $R --python $PY --repo $O --input $SKILL_DIR/assets/input_100.csv --output $WORK/original_100.csv
```
Record `seconds`, `peak_rss_mb` and `peak_pss_mb` of each run in `$WORK/log.md`.

**Memory scaling.** Compare the original's peak from 10 to 100 molecules (use
`peak_pss_mb` if it runs worker processes; `peak_rss_mb` then counts shared weights
once per worker). If it rises by more than ~1 MB per extra molecule, or the original
runs a pool sized with a fixed number or `os.cpu_count()`, also run it on 1000
molecules and keep that as a reference:
```bash
(head -1 $SKILL_DIR/assets/input_100.csv; for i in $(seq 10); do tail -n +2 $SKILL_DIR/assets/input_100.csv; done) > $WORK/input_1000.csv
python $R --python $PY --repo $O --input $WORK/input_1000.csv --output $WORK/original_1000.csv
```
Repeated molecules are fine for memory. Growth that is still linear at 1000 (eos9o72:
1.6 GB at 100, 4.7 GB at 380, 11 GB at 1000) points to pattern 6; a large peak that
scales with the number of workers rather than molecules, to pattern 7. Watch the
machine's free memory: stop the run if it would exhaust it, and report the
growth rate instead.
- References and candidates must always use the same `--cpus`: the CPU count can change
  the thread count of OpenMP/BLAS and with it the last digits (pitfalls.md).
- If the 10-molecule run takes over ~3 min, skip 100 or run it in the background.
- If run 2 differs from run 1, the original is not reproducible. Find out why (threads?
  unseeded randomness?) and use run-to-run difference as the bar (Principle 1).
- Keep `original_10_run2.csv` only in that case.
- If the original crashes on the whole edge file, gate on "the optimized model fails
  the same way" and note it; don't fix it as part of the speed-up.

### Step 3: Profile and plan

```bash
taskset -c 0-$((CPUS-1)) $PY $SKILL_DIR/scripts/profile_model.py --repo $O \
    --input $SKILL_DIR/assets/input_10.csv --top 30
```
Read `references/patterns.md` and match the profile to it. If most time is in one
subprocess, rerun that command under `python -m cProfile -s cumtime` to look inside.
Then read the code on the hot path. Write a short plan in `$WORK/log.md`: each
candidate, the evidence, the expected gain and the risk to outputs (with
`references/pitfalls.md` in mind). Order by gain/risk.

### Step 4: Apply and gate, one change at a time

For each candidate:
1. Make the smallest edit in `$REPO`, with an `# OPTIMIZATION:` comment.
2. Gate on the edge cases and 10 molecules (fast), then on 100:
   ```bash
   for t in edge 10 100; do
     python $R --python $PY --repo $REPO --input <input for $t> --output $WORK/optimized_$t.csv \
               --reference $WORK/original_$t.csv
   done
   ```
3. Check memory: compare `peak_rss_mb` (`peak_pss_mb` for worker pools) with the
   original's on the same input, and on 1000 molecules too if Step 2 found growth.
   - A constant increase is expected when something is now loaded once and kept (the
     original loaded the same thing per molecule). Note it.
   - Growth with the input is not: if the optimized model's peak rises much more from 10
     to 100 molecules than the original's, the change holds every molecule at once (a
     batched call over the whole file, a cache keyed per molecule). It will not survive
     10,000 inputs in a container. Process in chunks (keeping the original batch size
     for the numerics), bound or clear the cache between molecules, and re-gate; if
     that loses the gain, record it under "Not applied".
   - For a memory fix (patterns 6 and 7), the peak at 1000 molecules should be about
     the same as at 100.
   - Chunking an original that ran the whole input as one batch can change float32
     results in the last digit (pitfalls.md, "Batch size"). Keep the change if the only
     differences are at float32 rounding level (max abs diff ≲ 1e-6, no blank or NaN
     changes), and report the number. Larger differences go under "Not applied".
4. Identical → keep it, note the time and memory. Different → read `compare.py`'s report
   (blank mismatches? 1e-16 noise? 1e-7 float32? real change?), check
   `references/pitfalls.md`, and either adjust the change (e.g. keep the original
   batch size, thread count or embedding count) and re-gate, or revert it and record
   it under "Not applied" with the measured gain and the difference it causes.

A crash or bug you find on the way is a separate change: fix it only if it is small
and certain, mark it `# FIX:`, keep an input that triggers it in `$WORK`, and report
it as an intended output change.

### Step 5: Final measurement

**Local timing.** With all kept changes, rerun original and optimized on 10 and 100
(with `--cpus $CPUS`) one after the other (not in parallel: they compete for CPU),
compare, and record times and peak memory. If timings are noisy, alternate runs and
take the median.

**Served model.** Local runs call `main.py` in a scratch env; users get the model
through `ersilia fetch`, which adds the serving layer and runs `run.sh`. Run the
original and the optimized model that way, one after the other, on the 100 molecules
(on the 10 if the original took over ~15 min on 100) and the edge cases. `fetch`,
`serve`, `run` and `close` must run in **one shell** (a model served in one
`conda run` is invisible to the next), and the run is polled instead of wrapped in
`timeout` (under `timeout`, ersilia does not find the served model):

```bash
VERIFY=$SKILL_DIR/assets/input_100.csv            # or input_10.csv, see above
# Positional parameters ($ followed by a digit) are avoided on purpose: Claude Code
# replaces them with the skill's arguments when it loads this file.
served() {  # usage: LABEL=original SRC=<folder named exactly $MODEL> served
  conda run -n ersilia bash -c "
    ersilia fetch $MODEL --from_dir '$SRC' > '$WORK/served/fetch_$LABEL.log' 2>&1 &&
    ersilia serve $MODEL --disable-cache > '$WORK/served/serve_$LABEL.log' 2>&1 || exit 1
    s=\$SECONDS
    ersilia run -i '$VERIFY' -o '$WORK/served/${LABEL}_verify.csv' & pid=\$!
    for i in \$(seq 2700); do kill -0 \$pid 2>/dev/null || break; sleep 1; done   # 45-min limit
    kill \$pid 2>/dev/null; wait \$pid
    echo \"$LABEL: \$((SECONDS - s)) s\" >> '$WORK/served/times.txt'
    ersilia run -i '$SKILL_DIR/assets/edge_input.csv' -o '$WORK/served/${LABEL}_edge.csv'
    ersilia close; ersilia delete $MODEL"
}
cd $WORK
LABEL=original SRC=$WORK/pristine/$MODEL served
LABEL=optimized SRC=$REPO served
for t in verify edge; do
  python $SKILL_DIR/scripts/compare.py $WORK/served/original_$t.csv $WORK/served/optimized_$t.csv
done
```
- If every `ersilia` command dies at startup with `ValueError` in
  `determine_orphaned_session`, `~/eos/sessions/` holds a folder with a non-numeric
  name (`session_<name>`), from someone serving a model under a custom session. It is
  in use: don't delete it; ask the user, and meanwhile finish everything local.
- `--disable-cache` matters: otherwise the second run can get the first one's results
  back from the cache and the comparison proves nothing.
- If `$REPO`'s folder is not named `$MODEL`, copy it to `$WORK/candidate/$MODEL` first.
- Compare served original with served optimized only, never with the local outputs:
  the served model is not CPU-restricted, so a thread-sensitive model can differ from
  the `--cpus $CPUS` runs in the last digits.
- Served outputs must be identical (or within the original's own run-to-run
  difference, Principle 1). A fetch or run that fails only for the optimized model is
  a regression: find the change that causes it and revert or fix it. If the original
  fails to fetch too, log it and rely on the shallow test.

**Shallow test.**

```bash
cd $WORK && conda run -n ersilia ersilia test $MODEL --shallow --from_dir $REPO > $WORK/served/test.log 2>&1
```
Read `$MODEL-test.json` (in `$WORK`, else in `$REPO`; move it to `$WORK/served/`) and
ignore `"not present"` values. If a boolean check is `false`, run the same test on
`$WORK/pristine/$MODEL`: a check that fails there too predates the speed-up (report it
and point to `/ersilia-model-test`); a check that fails only for the optimized model is
a regression to fix before you finish.

**Cleanup.** `fetch` and `test` can leave files in the repository (a generated
`install.sh`, line-ending changes to example files). Compare `git status --porcelain`
with `$WORK/git-status-before.txt` and undo every change that is not yours.

### Step 6: Write up

Leave in `$WORK`: `original_*.csv`, `optimized_*.csv`, `served/`, any special inputs
(`input_*.csv`), and `log.md`. Delete the pristine copy. Write
`$REPO/optimizations.md`, **very brief**:

```markdown
# Optimizations

1. **<what>** (`<file>`): <what was slow, one sentence>. <what now>. ~<N>x faster (100 mols: <a> s → <b> s).

Timed on <CPUS> CPUs. Peak memory (100 mols): <a> MB → <b> MB (1000 mols, if measured: <a> MB → <b> MB). Served model: <a> s → <b> s, outputs identical; `ersilia test --shallow` passes.

Outputs identical to the original on `10.csv`, `100.csv` and edge cases (`compare.py`). Results in `../<model>-optimization/`.

Not applied: <faster variant> (~<N>x) changes outputs (<how many> molecules).
```

Final report to the user: a table (molecules, original time, optimized time, original
and optimized peak memory, output; include 1000 molecules when memory was measured there), the served-model times and comparison, the
shallow-test result, what was not applied and why, any bug fix, and the commands to
re-test:

```bash
python $SKILL_DIR/scripts/run_model.py --cpus 2 --python <env>/bin/python --repo <REPO> \
    --input <input> --output /tmp/out.csv --reference <WORK>/original_100.csv
```

Remind the user that nothing is committed, and list files changed (`git status`).
