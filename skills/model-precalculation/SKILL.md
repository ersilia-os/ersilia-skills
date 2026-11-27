---
name: model-precalculation
description: >
  Track and drive the precalculations every Ersilia Model Hub model needs after a new model
  or a new MAJOR version: reference_library_1M_v0, eosframes, eosquality, olinda and the
  Enamine / MolPort / COCONUT libraries. Reads the Airtable "Precalculations" table (Ersilia
  Model Hub base), shows what is ready to run, what is blocked and why, checks that this
  computer can run it, marks jobs Ongoing, and after a run checks the result (isaura for the
  reference library, S3 for eosframes and eosquality) before marking it Isaura or Done.
  Every Airtable write is shown to the user and confirmed first. It does not run the
  calculations itself. Use this skill whenever the user asks what
  precalculations are pending, wants to start or finish a precalculation, or asks whether
  the Precalculations table is up to date. Triggers include: "precalculation queue",
  "/model-precalculation", "what needs to be calculated", "which models need the reference
  library", "pending eosframes", "pending eosquality", "start a precalculation", "I finished
  calculating eosXXXX", "mark eosXXXX as done", "is the precalculations table up to date".
argument-hint: "[queue | start <snapshot> <calculation> | finish <snapshot> <calculation> | reconcile]"
allowed-tools: [Read, Bash, Write, AskUserQuestion]
---

# Ersilia model precalculation

Every new model, and every new MAJOR version of a model, needs a set of precalculations.
They run on team members' own computers, not in the cloud, so the Airtable
**Precalculations** table is the only shared view of what is done and what is pending. This
skill keeps that table honest and easy to act on.

Each piece of the system does one job:

- **Airtable** holds the state and the dependency rules. Its automations create a row on
  each MAJOR release and unblock dependent calculations.
- **This skill** is the operator's view. It shows the queue, checks this computer, and
  updates statuses after the user confirms.
- **The runner** does the actual computing. It is developed separately and is not part of
  this skill.
- **model-monitoring** compares the table with isaura in its weekly report.

## Hard rules

- **Confirm every write.** Before any Airtable update, show the exact rows and the
  before → after values, then ask. Write only what the user approves.
- **Never mark a stored result without checking isaura.** `reference_library_1M_v0` (and any
  other column) moves to **Isaura** only when `reconcile_isaura.py` shows the full count for
  that snapshot. A row marked Isaura while the data is missing is worse than a row marked
  To do.
- **Never mark Done without checking S3.** eosframes and eosquality move to **Done** only
  when `check_s3.py` finds every expected file for that exact snapshot.
- **Gone means Deleted.** A row marked **Isaura** or **Done** whose output is no longer
  found (nothing at all in isaura or S3) was removed on purpose. Propose **Deleted**. A
  *partial* result is not a deletion: report it and let a person decide.
- **Never change "Not required" or "Deleted" back.** Those are decisions, not results. If
  output shows up again for a Deleted row, report it only. Pending work (To do or Blocked)
  on a superseded version becomes **Not required**; propose it, the user confirms.
- **Latest versions first.** Pending work on a superseded major version is not queued by
  default; it usually needs Not required or Deleted, not a run.
- **Never skip a dependency.** Do not offer eosframes or eosquality for a snapshot whose
  reference library is not in isaura, even if the user asks for "everything that is To do".
  Explain why instead.
- **Do not reset Ongoing rows on your own.** Someone may be running them. Report them and
  let the user decide.

## Inputs

All optional. The first word of the arguments picks the mode; with no arguments, run
**queue**.

- `queue`: show what is ready, blocked and ongoing.
- `start <snapshot> <calculation>`: check this computer and mark the job Ongoing.
- `finish <snapshot> <calculation>`: verify the result and mark it Isaura or Done.
- `reconcile`: compare the whole table with isaura and propose fixes.

## Workflow

Scripts live in `scripts/`. Run them with the Python that has no extra dependencies (only
the standard library is used). Write scratch files to the session scratchpad.

### Step 0: Load the schema

Read `references/airtable-schema.md`. It has the base, table, field and choice IDs, the
meaning of every status and the dependency map. Use field IDs, not names, in every
connector call.

### Step 1: Read the table

If `AIRTABLE_TOKEN` is set, pass `--from-api` to the scripts and skip this step.

Otherwise read the table with the Airtable connector, following "Reading the table with the
connector" in the schema reference, and save the result to a JSON file. Read all rows: the
queue is wrong if pages are missing. If the read fails, stop and say so. Do not report a
partial queue.

### Step 2: Show the queue (`queue` mode, and the start of every other mode)

```bash
python scripts/build_queue.py --airtable <saved.json> [--calc eosframes] [--json queue.json]
```

Report, in this order:

1. A table of ready / blocked / ongoing / old-version counts per calculation. The queue only
   includes rows whose Version is **Latest**. "Old version" counts pending work on superseded
   rows. The "Close pending work on superseded versions" automation normally sets that work
   to Not required, so a non-zero count means the automation is off or failed: say so, check
   it in Airtable, and offer to set the rows to Not required. Pass `--include-superseded` only
   if the user really wants to compute an old version.
2. What is ongoing, so nobody starts it twice.
3. What is ready, newest snapshots first if the user asks for a short list.
4. Rows that break the dependency rules, with the proposed fix. For "Blocked but dependency
   is met", the fix is To do. For "To do but dependency not met", the fix is Blocked. Offer to
   apply the fixes (Step 5).

Keep it short. The user wants to know what to run next, not every snapshot name.

### Step 3: Start a job (`start` mode)

1. Confirm the snapshot and calculation are **ready** in the queue. If they are blocked or
   ongoing, stop and say why.
2. Check this computer:

   ```bash
   python scripts/check_machine.py --path <output dir> --min-free-gb <size>
   ```

   Any FAIL stops here. Tell the user how to fix it (start Docker, free disk, install
   isaura). Do not mark anything Ongoing on a computer that cannot run the job.
3. Show the change (`<snapshot>  <calculation>: To do → Ongoing`) and ask. On yes, write
   it with `update_records_for_table`, using the record ID from the saved JSON.
4. Tell the user how to run the calculation. The runner is being developed separately; until
   it exists, the user runs the calculation with their usual commands. Remind them to come
   back with `finish` when it ends.

### Step 4: Finish a job (`finish` mode)

1. For **reference_library_1M_v0**, check isaura for this snapshot:

   ```bash
   python scripts/reconcile_isaura.py --airtable <saved.json> --snapshot <snapshot>
   ```

   - Full count (1,355,109): propose **Isaura**.
   - Partial count: do not mark Isaura. Report the count and propose **Raw** only if the
     user confirms that the full output exists locally.
   - Zero: report that nothing reached isaura and leave the status unchanged. (If the row
     was already Isaura, `reconcile` mode proposes Deleted instead.)
2. For **eosframes and eosquality**, check S3:

   ```bash
   python scripts/check_s3.py --airtable <saved.json> --snapshot <snapshot> [--profile <aws profile>]
   ```

   - "complete in S3": propose **Done**. For eosquality this needs all 5 score sets and
     artifacts whose recorded version matches the snapshot.
   - "INCOMPLETE in S3": report what is missing (a score set, or artifacts from another
     version, which means a newer run overwrote them) and leave the status unchanged.
   - Nothing in S3: report it and leave the status unchanged.
3. For **olinda**, no automatic check exists yet. Ask the user where the output is, check
   that it exists and is not empty, then propose **Done**.
4. For the other libraries, isaura counts are not in the public inventory. Ask the user to
   confirm the push, then propose **Isaura** (or **Raw** if it is only local).
5. Show the change and ask. On yes, write it. Tell the user that setting the reference
   library to Isaura will make Airtable move eosframes and eosquality from Blocked to
   To do, once the "Unblock dependent calculations" automation is on.

### Step 5: Reconcile the whole table (`reconcile` mode)

```bash
python scripts/reconcile_isaura.py --airtable <saved.json> [--reuse-stats isaura_stats.json] --json reconcile.json
python scripts/check_s3.py --airtable <saved.json> [--profile <aws profile>] --json s3.json
python scripts/build_queue.py --airtable <saved.json> --json queue.json
```

`isaura stats` takes about 30 seconds. Reuse a stats file from model-monitoring when one
from today exists. Present:

- `untracked_complete`: complete in isaura but not marked. Propose Isaura.
- `isaura_missing`: marked Isaura, nothing stored any more. Propose **Deleted**.
- `isaura_incomplete`: marked Isaura but only part of the data is there. Report only. A
  person must decide whether to recompute.
- `partial_in_progress`: possibly a run that stopped halfway. Report only.
- `isaura_without_row`: data for a version with no Airtable row. Report only.
- From `check_s3.py`: `untracked_complete` (propose Done), `done_but_missing` (propose
  **Deleted**), `incomplete` (report only; a person decides whether to recompute), and
  `s3_without_row` (report only).
- From `build_queue.py`: the "old version" column. Propose **Not required** for each of
  those cells.
- Dependency issues from `build_queue.py`, with their fixes.

Apply the approved changes in batches of up to 50 records with `update_records_for_table`.
Re-run both scripts afterwards and report the new counts.

## Output

Answer in the terminal. Lead with the one or two things to act on, then the counts. Name
snapshots as `eosXXXX_vN`. Do not paste the full lists unless the user asks.

## When something goes wrong

- A status name the scripts do not know means the table changed. Re-read the schema with
  `get_table_schema`, update `references/airtable-schema.md` and `_precalc.py`, and tell the
  user.
- If either script stops with "inventory is empty" or "listing came back empty", do not
  propose anything. An empty listing means a failed read (wrong bucket, profile or
  network), and treating it as real would mark every row Deleted.
- If the AWS CLI reports a missing profile, list them with `aws configure list-profiles` and
  pass the right one with `--profile`. Do not guess between profiles that point to
  different accounts.
- If `isaura` is in several conda environments, the scripts stop and ask. Pass the chosen
  one with `--isaura-bin`.
- If the automations seem not to fire, check in Airtable that they are turned on. Edits made
  through the connector stay as drafts until someone publishes them.
