---
name: ersilia-model-test
description: Tests an Ersilia Model Hub model before hub incorporation. Runs `ersilia test --shallow` on a locally cloned model repository, reads the results, identifies failing checks, and proposes a debugging strategy to the user — but does not apply fixes automatically. Use this skill whenever a user wants to test, validate, or debug an Ersilia model before submitting it to the hub, mentions test failures, says "the test is failing", or is preparing a model for hub incorporation. Trigger even if the user just says "test the model" or "run ersilia test" in any Ersilia context.
---

# Ersilia Model Tester

Your job is to run the Ersilia shallow test on a locally cloned model, read the results, and tell the user what is failing and how to fix it. You propose fixes — you do not apply them unless the user explicitly asks you to.

## What you receive

- The **model ID** (format: `eos` + 4 alphanumeric characters, e.g. `eos4ywv`)
- The **local path** to the cloned GitHub repository (e.g. `/home/user/eos4ywv`)

If either is missing, ask the user before proceeding.

## Step 1: Run the shallow test (once)

Always run inside the `ersilia` conda environment, from the model directory:

```bash
cd <model_path>
conda run -n ersilia ersilia test <model_id> --shallow --from_dir <model_path>
```

This produces a JSON report `<model_id>-test.json` in the current directory. Capture the terminal output too — it often contains error tracebacks that explain why a check failed.

**Important:** Never delete, remove, or modify any directories or folders. Never touch `run.sh`. Never touch `run_output.csv`.

## Step 2: Read and triage the results

Read `<model_id>-test.json`. It contains boolean results for each check.

**Ignore — these are auto-populated after hub merge and not your concern:**
- Any check with value `"not present"` (S3 URL, DockerHub, model size, incorporation date, computational performance, release version, etc.)

**Focus on everything that is `false`.** Group them:

1. **Run failure** (`simple_model_run: false`) — the model crashes on execution. This is the most critical. All other checks below it will also be false as a side effect — focus on fixing the run first.
2. **Metadata failures** — fields like `model_description`, `model_task`, etc.
3. **File structure failures** — columns format, install.yml syntax, etc.
4. **Consistency failures** — output varies between runs, or differs between Ersilia CLI and direct bash execution.

## Step 3: Diagnose each failure

For each failing check, **read the relevant files** to understand the root cause. Do not guess — look at the actual code and config. Relevant files to read:

| Failing check | Files to read |
|---------------|--------------|
| `simple_model_run` | `model/framework/code/main.py`, terminal error output |
| `model_description` | `metadata.yml` (check Description field length — max 600 characters) |
| `metadata_*` | `metadata.yml` |
| `columns` / `metadata_dim_and_run_column_file_dim_check` | `model/framework/columns/run_columns.csv`, `metadata.yml` |
| `install_yaml_check` | `install.yml` |
| `check_consistency_of_model_output` / `rmse_mean` | `model/framework/code/main.py` (look for random seeds, stochastic operations) |

See `references/troubleshooting.md` for specific causes and fixes for each check type.

## Step 4: Present findings and proposed fixes to the user

After diagnosing, give the user a clear summary structured like this:

---

**Test result: X checks failing** (ignoring "not present" fields)

For each failing check:
- **What failed**: name of the check
- **Why**: one-sentence root cause based on what you read in the code
- **Proposed fix**: exactly what to change and in which file

Then ask: *"Would you like me to apply these fixes?"*

---

Only apply fixes if the user says yes. If the user asks you to apply, make the changes and then re-run the test to confirm.

## Model template structure (for reference)

```
<model_id>/
├── model/
│   ├── framework/
│   │   ├── run.sh              ← NEVER modify
│   │   ├── code/
│   │   │   └── main.py
│   │   ├── examples/
│   │   │   ├── run_input.csv
│   │   │   └── run_output.csv  ← NEVER modify
│   │   └── columns/
│   │       └── run_columns.csv
│   └── checkpoints/            ← do not modify
├── metadata.yml
└── install.yml
```

---

## Next steps

> **Remaining steps:**
> 1. Run `/model-incorporation-reproduce` to verify the model performs as reported in the paper
> 2. Push and open a pull request from your fork to `ersilia-os/eosXXXX`
