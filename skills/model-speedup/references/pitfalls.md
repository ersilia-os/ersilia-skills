# Pitfalls: when a speed-up changes the outputs

Every one of these happened on a real model. Read this before deciding why a gate
failed, and before claiming a change "can't affect" the results.

## Random state that carries over between molecules

RDKit embedding without `randomSeed` (`EmbedMolecule`, `EmbedMultipleConfs` with the
default `-1`) is reproducible run to run, but each molecule's coordinates depend on
how many random numbers were drawn before it in the same process. So these all
change outputs:
- adding a seed (eos3wzy: 3 of 10 molecules changed),
- running molecules in a different order, in a worker pool, or in separate processes,
- embedding fewer conformers (eos3mk2, eos9ym3: conformer 0 changes),
- multithreaded embedding (`numThreads=0`, eos9ym3; on eos3mk2 identical on 100
  molecules but 4 of 1,000 rows differed). The skill doesn't add parallelism anyway
  (SKILL.md, principle 6).

Also beware: a pipeline may embed all molecules in a first pass and process them in
a second (QupKake), so a molecule's result depends on the *whole batch*. A subset of
the input does not reproduce it; test with the full file.

## Thread count

Floating-point sums in a different order give different last digits, and iterative
methods can amplify them.
- xtb `-P 1/4/16` gives three different final energies for the same molecule; on 100
  molecules this flipped one predicted pKa site (eos3wzy). Keep the original `-P` and
  `OMP_NUM_THREADS`.
- scikit-learn forests with `n_jobs > 1` add tree votes in random order: the original
  differs by ~1e-16 between its own runs (eos5gge).
- The CPU count sets the default thread count of OpenMP, MKL, OpenBLAS and joblib, so
  the same code on 2 and on 16 CPUs can differ in the last digits. That is why every
  local run uses the same `--cpus`, and the served model (not restricted) is compared
  only with the served original.

## Batch size

Running molecules through a neural network together changes float32 results in the
7th-8th digit (eos4e40, chemprop). Load once but keep the original batch size, e.g.
chemprop `--batch_size 1` when the original predicted one molecule per call.

The reverse happens when the original ran the *whole input* as one batch and memory
grew with it (patterns.md, pattern 6): splitting it into chunks changes the last
float32 digit too (eos9o72: max diff 6e-8 to 1e-7). Here the original batch size is
the problem, since it equals the input size, so the change is kept when the
differences stay at that level, and reported with the number (SKILL.md, Step 4).
`torch.inference_mode()` alone does not change outputs; apply and gate it first, so
the report can tell the two apart.

## Measuring memory of worker processes

`peak_rss_mb` adds up the RSS of every process, so weights a forked worker shares with
its parent are counted once per worker: a 400 MB array shared by 4 workers shows as
~2 GB RSS and ~400 MB PSS. Use `peak_pss_mb` for any model with worker processes, or
a load-once-and-fork fix (pattern 7) looks like no gain. Also, `--cpus` restricts the
CPUs but not `os.cpu_count()`, so a pool sized from it starts as many workers as on
the whole machine, which is what happens in Docker too.

## Fallback paths and timeouts

- Code that catches errors and falls back (per-molecule retries, `except: NaN`) can
  hide a change: the same output for most rows, a blank row for one. Compare blank
  cells (`compare.py` reports `blank_mismatches`).
- Per-molecule timeouts make results speed-dependent: a faster version may finish a
  molecule the original dropped. If outputs differ by one blank row, check for a
  timeout before blaming your change.

## Originals that are not reproducible

Run the original twice on the same input before optimizing. If the two runs differ,
the bar is: differences no larger than the original's own run-to-run differences
(report both numbers), never "close enough". If the optimized version becomes
deterministic, say so: it is an improvement.

## Fixing bugs is a different change

A crash fix changes outputs on purpose (eos3wzy: a single molecule with exactly one
pKa site crashed, `squeeze()` on a 1-element tensor). Keep it separate from the
speed-ups, state it explicitly in optimizations.md, and show the input that triggers it.

## Environment

- Code that calls a bare `python` in a subprocess runs whatever `python` is first on
  PATH (eos2lqb). Always put the env's bin/ first on PATH (`run_model.py` does it);
  replacing `python` with `sys.executable` is a safe fix.
- Conda installs can upgrade pinned packages (eos7pw8: `conda install syba` upgraded
  rdkit and numpy). Check versions after building the env and pin back.
- Use the versions the Dockerfile / install.yml pin; numpy dtype rules and RDKit
  behaviour differ between versions.

## Licences

Some vendored files forbid modification (eos9ym3's `rdkonf6.py`: "You may not modify
the program"). Read the header before editing third-party code; put the faster
version in Ersilia's own file instead.

## numpy details

`np.searchsorted(uint32_array, python_ints)` promotes and copies the whole array on
every call. Cast the query to the array's dtype (eos7pw8).
