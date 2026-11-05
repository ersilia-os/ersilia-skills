# Speed-up patterns

Patterns 1-5 covered every speed-up found in the first eight models. Check them in
this order: the first ones are the most common and usually the biggest wins. Pattern
8 is also about time; check it whenever featurization (building atom or bond
features for a graph model) shows up high in the profile. Patterns 6 and 7 are about
memory, not time: the model's peak memory grows with the input or with the number of
workers until the container kills it. Check them whenever Step 2 finds memory growth.
For each: how to spot it in the profile or code, the fix, and a real example.

## 1. Setup repeated for every molecule

**Signs.** Time grows linearly with molecules even for cheap models (metadata:
1 → 10 → 100 inputs costs ~5-10 s per molecule). In the profile: `pickle.load`,
`torch.load`, `joblib.load`, `json.load`, `load_model` called N times; or
`profile_model.py` shows one subprocess per molecule (`x10 bash`, `x10 python`).
In the code: a loop over SMILES that calls a function which loads a model, builds
a calculator, or runs a CLI.

**Fix.** Load once and reuse: `functools.lru_cache` on the loader, move the load
out of the loop, or call the CLI once with all molecules. Keep the per-molecule
error handling: if a batch call can fail on one bad molecule, filter invalid
inputs first and fall back to the old per-molecule loop if the batch still fails.

**Examples.**
- eos96f4: SCScore model reloaded from a 9 MB `.json.gz` per molecule → `lru_cache` on the loader. 14x.
- eos5gge: the `dilipred` library unpickled 13 random forests (54 MB) per molecule. A small module replaces `pickle` inside the library with a caching loader. 3.3x.
- eos4e40: two Python processes and 20 checkpoints (430 MB) per molecule → one chemprop run for all molecules. 29x.
- eos2b6f: two `python call_dimorphite_dl.py` processes per molecule → the same function called in-process (watch for `sys.argv` parsing, pitfalls.md). ~1 s per molecule saved.

## 2. Thread or process pools for a single item

**Signs.** Heavy `time.sleep`, `lock.acquire`, `multiprocessing/pool.py` or
`joblib/parallel.py` in the profile while work per call is tiny. Models with
`n_jobs=-1/30` predicting one row at a time; Mordred `calc.pandas(mols)` with one
molecule (it starts one process per CPU by default).

**Fix.** `n_jobs = 1` after loading the model; Mordred `nproc=1`.

**Watch out.** Thread count can change results (see pitfalls.md, "Thread count").
For scikit-learn forests, 30 threads add tree votes in random order, so the original
is not reproducible in the last digit anyway, and 1 thread makes it reproducible.

**Example.** eos5gge (together with pattern 1).

## 3. The same computation done twice

**Signs.** The same expensive function (descriptors, featurization, an external
program) appears with 2x the expected calls in the profile, or in
`profile_model.py`'s subprocess table. Often one call per output head or per
threshold.

**Fix.** Compute once, pass the result to both users. For an external program that
is deterministic, cache its output keyed on the exact input and options.

**Examples.**
- eos2lqb: Mordred descriptors computed once per cutoff (20%, 50%) → computed once and shared. 2.1x.
- eos3wzy: xtb ran on the same structure many times (~half the calls) → `lru_cache` keyed on the mol block and options. 1.5x.

## 4. Work whose result is never used

**Signs.** A loop that computes something for N items (conformers, folds, tautomers)
and only item 0 reaches the output. Typical for conformer code: N conformers
embedded, all force-field optimized and ranked by energy, but only the default
(first) conformer is written to an SDF or read by a descriptor (`GetUSRCAT`,
`SDWriter.write(mol)` and most 3D descriptors read `confId=-1`, the first conformer).

**Fix.** Do the expensive step only for the item that is used. Keep everything that
feeds it: with RDKit, **keep embedding all N conformers**, since conformer 0's
coordinates depend on how many are embedded; skip only per-conformer
optimization, alignment and ranking.

**Examples.**
- eos3mk2: MMFF on 10 conformers, 1 used. 1.4-1.55x.
- eos9ym3: UFF on 50-300 conformers, 1 used. 1.6x.

## 5. Slow checkpoint format

**Signs.** Most of a run is spent loading the checkpoint (`_pickle.load`, joblib)
even for one molecule: metadata shows a large constant time (e.g. ~50 s for 1 and
for 100 inputs).

**Fix.** Convert to a format that loads fast (numpy `.npz` arrays, safetensors), with
a small `convert_checkpoint.py` kept in `code/` so the conversion is reproducible,
and repeat the library's arithmetic on the arrays in the same order. Remember Git
LFS for the new file, and remove the old one.

**Example.** eos7pw8: 792 MB pickled dict of 26M fragments (~50 s to load) → 159 MB
`.npz` (0.1 s). 15x on 10,000 molecules, 190x on 100.

## 6. Whole input in one batch, with autograd on

**Signs.** Peak memory grows linearly with the number of molecules, MBs per molecule,
in a PyTorch model that only predicts (from 10 to 100 to 1000 molecules). In the code,
every molecule is built into one batch (a single `BatchMolGraph`, `torch.stack` of all
inputs, one `model(all_x)` call), and the forward pass is not inside
`torch.no_grad()` / `torch.inference_mode()`. `.numpy(force=True)` or `.detach()` at the
end is a hint: it works around the gradient instead of turning it off.

**Fix.** Two changes, gated separately:
1. Wrap the forward pass in `torch.inference_mode()` (or `no_grad()`). Autograd stops
   keeping every intermediate activation. Outputs are identical; this alone cut
   memory to a third on eos9o72.
2. Run the molecules in chunks (e.g. 64) and concatenate. Memory becomes constant.
   This can change float32 results in the last digit (pitfalls.md, "Batch size").

**Example.** eos9o72 (CheMeleon fingerprints, chemprop): peak at 1000 molecules
11.4 GB → 3.4 GB with `inference_mode` (identical) → 0.8 GB with chunks of 64 (max
diff 1e-7, the same as at 100 and 2000 molecules). Same time.

## 7. Worker pools that copy the model into every worker

**Signs.** The original already runs a `ProcessPoolExecutor` / `multiprocessing.Pool`
with a fixed size (`N_WORKERS = 16`) or `os.cpu_count()`, and each worker loads the
model in its initializer. Memory is roughly workers × model size, whatever the input
size, and in a container with less memory than that, workers are OOM-killed
(`BrokenProcessPool`), or the run slows to a crawl as the pool restarts. `--cpus 2`
does not reveal it: `os.cpu_count()` still sees every core, as in Docker.

**Fix.** Keep the parallelism the original has, but make it fit (Principle 6):
- Load the model once in the parent, then start workers with the `fork` context, so
  they share the weights copy-on-write. Per-worker setup that is small stays in the
  initializer.
- Size the pool from `len(os.sched_getaffinity(0))` and available memory (the
  cgroup limit if there is one, else `MemAvailable`), never above the original's.
- If the original submits every molecule at once, process in batches with a fresh
  pool per batch, so worker memory cannot keep growing.
Measure with `peak_pss_mb`: `peak_rss_mb` counts the shared weights once per worker
and hides the gain.

**Example.** eos8aa5: a 358 MB TorchScript model loaded in each of 16 fixed workers.
Load once + fork, workers from CPUs and memory, batches of 1000 with a retry at half
the workers on `BrokenProcessPool`. In an 8 GB Docker VM, 100 molecules went from
~60 s with OOM kills to ~14 s; outputs bit-identical.

## 8. A per-molecule result recomputed for every atom or bond

**Signs.** A featurizer (often for a GNN) asks, for each atom or bond, "is this
atom part of a match of pattern X?", and answers by searching the *whole molecule*
and then checking whether the atom is in the matches. The search depends only on
the molecule and the pattern, so it is repeated atoms × patterns times for the same
answer, and again for every molecule variant (protonation states, tautomers). In
the profile: `GetSubstructMatches` / `MolFromSmarts` (or ring info, descriptors) with
ncalls in the hundreds of thousands for a few molecules, high `tottime` in a small
helper like `atom_smarts_query(atom, smarts)`, and `atom.GetOwningMol()` in the code.

**Fix.** Compute the matches once per molecule and pattern, parse each pattern once
(`lru_cache`), and look the atom up in a set. Keep the exact same call
(`GetSubstructMatches` with the same arguments, including the default
`maxMatches=1000`), so the result is identical. If the featurizer only sees one atom
at a time (feature lambdas), activate a small cache for the duration of the
per-molecule loop with a context manager, and leave it off elsewhere so other callers
keep the original behaviour.

**Example.** eos2b6f (pkasolver, microstate pKa): ~50 SMARTS × every atom × every
protonation state, each a full-molecule substructure search: 477,400 calls and 12 of
45 s on 10 molecules. Cached per molecule in `make_nodes`. Together with pattern 1
(dimorphite-dl in-process): 550 s → 179 s on 100 molecules (3.1x), outputs identical.

## Not worth it / out of scope

- The model calls a remote API (eos3kcw, eos1d7r...): the time is the network.
- Genuine work is the bottleneck (e.g. eos7ike averages properties over all conformers).
- `torch.inference_mode()` when each call predicts one small item (eos2b6f: one molecule pair per call, 25 models): outputs identical but no time gained. It pays off for memory with big batches (pattern 6).
- Size optimizations (unused packages, CPU-only torch): that is the `model-optimization` skill.
- Adding parallelism (worker pools, multiprocessing, `n_jobs` > 1, `numThreads=0`,
  more xtb `-P` threads): models run in Docker containers with few CPUs, so speed
  must come from less work. Making a pool the original already has fit its container
  is pattern 7, not this. It also changed outputs every time it was tried
  (eos3mk2, eos9ym3, eos3wzy; see pitfalls.md).
