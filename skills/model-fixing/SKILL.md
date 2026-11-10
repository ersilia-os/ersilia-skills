---
name: model-fixing
description: Applies fixes to an Ersilia Model Hub model after `ersilia-model-test` has diagnosed what is failing. Takes the failing checks and proposed fixes from a preceding test run, confirms a concrete edit plan with the user, applies the changes to the model's editable files (main.py, metadata.yml, install.yml, run_columns.csv), then re-runs the shallow test once and compares the example output with the stored run_output.csv to verify the fixes worked without changing the model's outputs. Also handles bugs in Hub models reported in a GitHub issue (for example, outputs that drifted from a previous release). Use this skill whenever a user wants to apply, implement, or carry out the fixes suggested by an Ersilia test, says "apply the fixes", "fix the model", "go ahead and fix it", "make those changes", or wants to act on a failing `ersilia test` result. This is the natural next step after `ersilia-model-test`; trigger it whenever the user asks to fix a tested Ersilia model.
---

# Ersilia Model Fixer

Your job is to **apply** the fixes that `ersilia-model-test` has already diagnosed, then confirm they worked. `ersilia-model-test` is the read-only half (it runs the test and proposes fixes); you are the write half (you make the edits and verify). The two skills are meant to run back-to-back in the same conversation.

## What you receive

You work from a **diagnosis already in the conversation**: usually the one `ersilia-model-test` produced (the list of failing checks, each with a root cause and a proposed fix), or a bug in a model already in the Hub, reported in a GitHub issue that names the root cause (for example, outputs that drifted from a previous release). For an issue-reported bug, Step 0 (baseline) is mandatory, because the shallow test can pass while the outputs are wrong. You also need:

- The **model ID** (`eos` + 4 alphanumeric chars, e.g. `eos4ywv`)
- The **local path** to the cloned model repository

Both are usually already established in the conversation. If either is missing, ask.

**If there is no diagnosis in the conversation** (the user jumped straight here, with neither a test result nor an issue), don't guess at fixes. Ask them to run `ersilia-model-test` first so the failures are diagnosed against the actual test output — applying fixes without a real diagnosis is how models get broken in new ways.

## Safe-editing rules (read before touching anything)

These mirror the constraints `ersilia-model-test` operates under. Respect them exactly — they protect the reference outputs and the run harness the test depends on.

**Never touch:**
- `model/framework/run.sh` — the run harness
- `model/framework/examples/run_output.csv` — the reference output. `ersilia test` only checks its column names, never its values: its consistency checks compare the current code with itself (two runs, or Ersilia vs bash), so a fix that changes every output still passes. This skill compares the values itself (Steps 0 and 4b)
- `model/checkpoints/` — the trained model weights
- Any directory structure — never delete, move, or rename folders

**You may edit only these files:**

| File | Typical fixes |
|------|---------------|
| `model/framework/code/main.py` | run failures, import paths, input parsing, random seeds, NaN handling, output columns |
| `metadata.yml` | description length, field formats, list-vs-string, missing required fields |
| `model/framework/columns/run_columns.csv` | column keys/types/directions, matching main.py output |
| `install.yml` | missing packages, pinned versions, python version, conda-vs-pip |
| `model/framework/examples/run_input.csv` | only if the 3 example SMILES themselves are the problem — rare |

If a proposed fix would require touching a forbidden file, stop and flag it to the user rather than working around the rule.

## Workflow

### Step 0: Record the baseline output (before any edit)

Check that the folder holding the model is named exactly `<model_id>` (Ersilia takes the model ID from the folder name; see Step 4). Then run the **unedited** model on the example input and compare it with the stored example output. This shows up front whether `run_output.csv` still matches the current code, or has already gone stale.

The model needs a working environment. If `ersilia fetch <model_id> --from_dir <model_path>` (or a previous shallow test) has created the `<model_id>` conda env, use it; otherwise build a scratch env from the exact pins in `install.yml`. If the model cannot run at all (the usual `simple_model_run: false` case), note that there is no baseline and skip to Step 1.

```bash
cd <model_path>/model/framework
conda run -n <model_id> bash run.sh . examples/run_input.csv <scratch_dir>/baseline_output.csv
```

Compare with the script in Step 4b. Write down the result (number of values that differ, maximum absolute difference). You report it in Step 5.

### Step 1: Build the concrete edit plan

Turn the diagnosis into specific edits. For each failing check, decide the exact file, the exact change, and re-**read the current contents of that file** before planning the edit — the diagnosis tells you *what* is wrong, but you apply against the real current bytes, not your memory of them.

Order matters: **fix the run failure first** (`simple_model_run: false`). When the model can't execute, every downstream check fails as a side effect, so a single run fix often clears most of the board. See `references/fix-patterns.md` for the correct, idiomatic way to write each fix type — use it so your edits match how working Ersilia models are actually written, instead of a plausible-looking guess.

### Step 2: Confirm with the user

Before writing anything, show the plan concretely:

---

**Fix plan for `<model_id>` — N changes**

For each change:
- **File**: path
- **Fixes**: which failing check(s) this addresses
- **Change**: the specific edit — show the before → after, or the diff, so the user sees exactly what will change

---

Then ask: *"Shall I apply these changes?"* Apply only on a yes. If the user wants to adjust the plan, revise it and re-confirm.

### Step 3: Apply the fixes

Make the edits exactly as confirmed. Keep changes minimal and surgical — change what the fix requires and nothing else, so the diff stays reviewable and you don't introduce new failures. Match the surrounding code's style, imports, and conventions.

### Step 4: Re-run the test once to verify

Run the same shallow test `ersilia-model-test` uses, from the model directory in the `ersilia` conda environment:

```bash
cd <model_path>
conda run -n ersilia ersilia -v test <model_id> --shallow --from_dir <model_path>
```

- The folder must be named exactly `<model_id>` (a clone into `eos3l5f_main` fails at "Fetch Status" for reasons unrelated to the model). Clone into a scratch parent folder if needed: `<scratch>/<model_id>`.
- `-v` makes fetch errors print their traceback. Without it, a failed fetch only shows "Model not fetched successfully".

Read the new `<model_id>-test.json` and the terminal output. Compare against the failures you set out to fix. Run the test **once** — this is a verification pass, not a fix-until-perfect loop. If checks are still failing, report that honestly with the new diagnosis rather than silently editing again; the user decides whether to do another round.

### Step 4b: Compare the outputs with the stored example

A green shallow test does not mean the outputs are unchanged (see the safe-editing rules). Run the edited model on the example input and compare it element-wise with `run_output.csv`:

```bash
cd <model_path>/model/framework
conda run -n <model_id> bash run.sh . examples/run_input.csv <scratch_dir>/fixed_output.csv
```

```python
import csv
import numpy as np

def load(path):
    rows = list(csv.reader(open(path)))
    return rows[0], rows[1:]

h_ref, ref = load("<model_path>/model/framework/examples/run_output.csv")
h_new, new = load("<scratch_dir>/fixed_output.csv")
assert h_ref == h_new, "header differs"
ref, new = np.array(ref, dtype=float), np.array(new, dtype=float)
diff = np.abs(ref - new)
print(f"values differing > 1e-4: {(diff > 1e-4).sum()} / {diff.size}; max abs diff: {np.nanmax(diff):.2e}")
```

(Adapt the loading for non-numeric outputs such as SMILES, which should match exactly.)

Read `Output Consistency` in `metadata.yml`:

- **`Fixed`**: the check passes only if every value is within `1e-4` (enough for float32 or ONNX rounding; real drift is much larger).
- **`Variable`**: skip the element-wise comparison, and say so in the report.

**On a mismatch, stop and report. Never edit `run_output.csv` to make it pass.** Compare with the Step 0 baseline to tell which case it is, and let the user decide:

| Baseline vs stored | Fixed vs stored | Most likely meaning |
|---|---|---|
| matches | differs | The fix changed the outputs: a regression. Revisit the fix. |
| differs | matches | The stored example was stale and the fix restores it. Confirm against an independent reference (the last good release image, or the authors' original code) before calling it fixed. |
| differs | differs | Both are off. Find a reference before going further. |

### Step 5: Report

Give the user a clear before/after:

---

**Applied N fixes to `<model_id>`**

- ✅ **`<check>`** — now passing (was failing). Changed `<file>`: one-line summary.
- ⚠️ **`<check>`** — still failing. What the new test output shows and your best read on why.

**Example output vs stored `run_output.csv`** (or "skipped: Variable model" / "no baseline: model did not run"):

| Code | Values differing > 1e-4 | Max abs diff |
|---|---|---|
| Before the fix (Step 0) | x / N | … |
| After the fix (Step 4b) | y / N | … |

Files changed: list them.

---

Be straight about what's still broken. A half-fixed model reported as fixed causes more trouble downstream than an honest "3 of 4 resolved, here's the remaining one."

## Cleanup

After the verification run, delete the JSON report so it doesn't get committed. Keep the baseline and fixed outputs in the scratch folder, never in the model repo:

```bash
rm -f <model_path>/<model_id>-test.json
```

## Model template structure (for reference)

```
<model_id>/
├── model/
│   ├── framework/
│   │   ├── run.sh              ← NEVER modify
│   │   ├── code/
│   │   │   └── main.py         ← editable
│   │   ├── examples/
│   │   │   ├── run_input.csv   ← editable (rarely)
│   │   │   └── run_output.csv  ← NEVER modify
│   │   └── columns/
│   │       └── run_columns.csv ← editable
│   └── checkpoints/            ← NEVER modify
├── metadata.yml                ← editable
└── install.yml                 ← editable
```

## Next steps

Once the test passes and the example output matches (or the user has accepted an explained mismatch):

> 1. Optional: run `/model-incorporation-reproduce` to verify the model reproduces the metrics reported in its paper
> 2. For a model that is not yet in the Hub, run `/model-incorporation-pr` to commit the fixes, push, open the pull request and, with your approval, merge it once every check is green. For a model already in the Hub, commit the fixes and open a pull request from your fork to `ersilia-os/<model_id>` by hand

**Always open the PR from the user's fork, never from a branch pushed to `ersilia-os/<model_id>`.** The shared PR workflow clones `https://github.com/<pr_user>/<model_id>`. A PR from a branch on the organisation repo fails at "Clone repo", and the model is never tested. Pushing, opening the PR and re-running upload workflows are the user's decisions: ask before each one.
> 3. Run `/model-incorporation-release` to confirm CI is green, check the release, deposit the paper and close the request
