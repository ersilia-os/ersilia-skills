---
name: model-fixing
description: Applies fixes to an Ersilia Model Hub model after `ersilia-model-test` has diagnosed what is failing. Takes the failing checks and proposed fixes from a preceding test run, confirms a concrete edit plan with the user, applies the changes to the model's editable files (main.py, metadata.yml, install.yml, run_columns.csv), then re-runs the shallow test once to verify the fixes worked. Use this skill whenever a user wants to apply, implement, or carry out the fixes suggested by an Ersilia test, says "apply the fixes", "fix the model", "go ahead and fix it", "make those changes", or wants to act on a failing `ersilia test` result. This is the natural next step after `ersilia-model-test`; trigger it whenever the user asks to fix a tested Ersilia model.
---

# Ersilia Model Fixer

Your job is to **apply** the fixes that `ersilia-model-test` has already diagnosed, then confirm they worked. `ersilia-model-test` is the read-only half (it runs the test and proposes fixes); you are the write half (you make the edits and verify). The two skills are meant to run back-to-back in the same conversation.

## What you receive

You work from the **diagnosis produced earlier in the conversation by `ersilia-model-test`** — the list of failing checks, each with a root cause and a proposed fix. You also need:

- The **model ID** (`eos` + 4 alphanumeric chars, e.g. `eos4ywv`)
- The **local path** to the cloned model repository

Both are usually already established in the conversation. If either is missing, ask.

**If there is no diagnosis in the conversation** (the user jumped straight here), don't guess at fixes. Ask them to run `ersilia-model-test` first so the failures are diagnosed against the actual test output — applying fixes without a real diagnosis is how models get broken in new ways.

## Safe-editing rules (read before touching anything)

These mirror the constraints `ersilia-model-test` operates under. Respect them exactly — they protect the reference outputs and the run harness the test depends on.

**Never touch:**
- `model/framework/run.sh` — the run harness
- `model/framework/examples/run_output.csv` — the reference output the consistency check compares against
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
conda run -n ersilia ersilia test <model_id> --shallow --from_dir <model_path>
```

Read the new `<model_id>-test.json` and the terminal output. Compare against the failures you set out to fix. Run the test **once** — this is a verification pass, not a fix-until-perfect loop. If checks are still failing, report that honestly with the new diagnosis rather than silently editing again; the user decides whether to do another round.

### Step 5: Report

Give the user a clear before/after:

---

**Applied N fixes to `<model_id>`**

- ✅ **`<check>`** — now passing (was failing). Changed `<file>`: one-line summary.
- ⚠️ **`<check>`** — still failing. What the new test output shows and your best read on why.

Files changed: list them.

---

Be straight about what's still broken. A half-fixed model reported as fixed causes more trouble downstream than an honest "3 of 4 resolved, here's the remaining one."

## Cleanup

After the verification run, delete the JSON report so it doesn't get committed:

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

Once the test passes:

> 1. Run `/model-incorporation-reproduce` to verify the model reproduces the metrics reported in its paper
> 2. Commit the fixes, push, and open a pull request from your fork to `ersilia-os/<model_id>`
