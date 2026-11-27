# Airtable "Precalculations" table: schema and rules

Verified against the live base on 2026-11-26. Re-check with `list_tables_for_base` and
`get_table_schema` if a call fails or a status name looks unfamiliar. Field IDs survive
renames, names do not.

## Location

- Base: **Ersilia Model Hub**, `appR6ZwgLgG8RTdoU`
- Table: **Precalculations**, `tblfnOcphh8KX6TI0` (one row per snapshot, about 420 rows)
- Linked table: **Models**, `tblAfOWRbA7bI1VTB`

A **snapshot** is a model identifier plus its MAJOR version, e.g. `eos9x3z_v1`. MINOR and
PATCH releases reuse the same snapshot, so they never create new work.

## Fields

| Field | ID | Type | Notes |
|---|---|---|---|
| Snapshot | `fldizgVkFaYFtLiH2` | text | `eosXXXX_vN`, unique, fixed once written |
| Identifier | `fld5E51pR8doIytFe` | lookup | from Models |
| Slug | `fldIwlAFXzGZkwo1O` | lookup | from Models |
| Model (from Models) | `fldJYb7vMzwyVnF7V` | link | to Models |
| Current Snapshot | `fld1WFzxd2rQqcXne` | lookup | the model's current Snapshot Key, from Models |
| Version | `fldwZE0kglPtLcYE9` | formula | `Latest` if Snapshot = Current Snapshot, else `Superseded` |
| reference_library_1M_v0 | `fldF6jXSJpBgEQUVE` | single select | To do, Raw, Isaura, Not required, Deleted |
| eosframes | `fldSSgZLmzvbEZoCO` | single select | Blocked, To do, Done, Not required, Deleted |
| eosquality | `fldSnnMv8wmb1hijH` | single select | Blocked, To do, Done, Not required, Deleted |
| olinda | `fldR5bzI73bQe6F6J` | single select | To do, Done, Not required, Deleted |
| enamine_hll_460K_v0 | `fldLzrqyJtnsvXxnT` | single select | To do, Raw, Isaura, Not required, Ongoing, Deleted |
| enamine_lsc_2M_v0 | `fldCTEwVgjdPYlSOn` | single select | To do, Raw, Isaura, Not required, Deleted, Ongoing (multi-select until 2026-11-26) |
| enamine_real_sample_10M_v0 | `fldf7knxW8PIBUTL2` | single select | To do, Raw, Isaura, Not required, Ongoing, Deleted |
| enamine_real_sample_1B_v0 | `fldgSwDUnbt9junc9` | single select | To do, Raw, Isaura, Not required, Ongoing, Deleted |
| molport_5M_v0 | `fldxhZkn0N1OY8BQT` | single select | To do, Raw, Isaura, Not required, Ongoing, Deleted |
| coconut_715K_v0 | `fldRqYpDolF80CQjx` | single select | To do, Raw, Isaura, Not required, Ongoing, Deleted |

Every calculation column has a **Deleted** option (added 2026-11-26).

Choice IDs used by the automations:

| Field | Choice | ID |
|---|---|---|
| reference_library_1M_v0 | To do | `seluIP8G9ZaFeE1w2` |
| reference_library_1M_v0 | Raw | `seljNj6gmnF4zRjPi` |
| reference_library_1M_v0 | Isaura | `sell99os7RMPBLNgW` |
| reference_library_1M_v0 | Not required | `selDMCjBvLszHPQiz` |
| reference_library_1M_v0 | Deleted | `selaJUnT36MaaNhT4` |
| eosframes | Blocked | `selHn0Rya0lZOLe5M` |
| eosquality | Blocked | `selNZM5WzqHX92T7C` |
| eosframes, eosquality | To do | `sel7jh1huEsvR8aWS` |

## What the statuses mean

| Status | Meaning |
|---|---|
| To do | Required and ready to run (all dependencies met) |
| Blocked | Required, but waiting for a dependency (see below) |
| Ongoing | Someone is running it now |
| Raw | Computed, output stored locally, not yet pushed to isaura |
| Isaura | Computed and stored in isaura |
| Done | Computed (columns that are not stored in isaura) |
| Not required | Not needed for this snapshot |
| Deleted | Was computed and stored, then removed on purpose (typically an old version) |

Transition rules (decided 2026-11-26):

- **Isaura / Done → Deleted** when the output is no longer found: nothing in isaura for the
  reference library, nothing in S3 for eosframes / eosquality. `reconcile_isaura.py`
  (`isaura_missing`) and `check_s3.py` (`done_but_missing`) propose it. A partial result is
  reported, not marked Deleted.
- **To do / Blocked → Not required** on Superseded rows. Old major versions are not
  computed. Applied to all 166 such rows on 2026-11-26; from then on the "Close pending
  work on superseded versions" automation does it when a new major version arrives.
- **Not required and Deleted are final.** The scripts never propose changing them, even if
  output shows up again.

## Versions

Each model keeps one row per MAJOR version. The **Version** formula marks the model's
current major version as `Latest` and older ones as `Superseded`. The Grid view groups by
Version, so Latest rows come first and the Superseded group can be collapsed.

`build_queue.py` leaves pending work on Superseded rows out of the queue (column
"old version"). Those cells become **Not required**. When a model moves to a new major
version, its previous row shows up there.

## Dependencies

| Calculation | Waits for | Unblocked when |
|---|---|---|
| eosframes | reference_library_1M_v0 | reference_library_1M_v0 = Isaura |
| eosquality | reference_library_1M_v0 | reference_library_1M_v0 = Isaura |

All models need eosframes and eosquality (decision of 2026-11-26). Snapshots whose
reference library is "Not required" (old, superseded versions) keep both as Not required.

The same map lives in `scripts/_precalc.py` (`DEPENDENCIES`). Change both together.

## Automations

| Name | ID | What it does |
|---|---|---|
| New release update | `wflH743m9pMzBN9Sn` | On a new MAJOR release, creates a row with reference_library = To do and eosframes / eosquality = Blocked |
| Unblock dependent calculations | `wfl92JjUYX8YpHw6B` | When reference_library_1M_v0 changes to Isaura, moves eosframes / eosquality from Blocked to To do |
| Close pending work on superseded versions | `wflo6c5G0wW4QLlTx` | When a row's Version becomes Superseded (the model got a new major version), sets every To do / Blocked cell on it to Not required. A script step first checks that Current Snapshot is a newer major version of the same model, so a row that only lost its Models link is left alone |

Automations only fire on changes made *after* they are turned on. Anything that slipped
through shows up in `build_queue.py` as "Blocked but dependency is met".

## Where outputs live

| Calculation | Location | Checked by |
|---|---|---|
| reference_library_1M_v0 | isaura, bucket `isaura-public` | `reconcile_isaura.py` |
| eosframes | `s3://eosvc-public/eosframes/output/ersilia_reference_library_v0/<snapshot>_transformer.json` | `check_s3.py` |
| eosquality | `s3://eosvc-public/eosquality/output/scores_<set>_1000_<snapshot>.csv` (5 sets: drugs, inert, molecules, np_large, synthetic) and `artifacts_<model_id>/` | `check_s3.py` |

The eosquality artifacts folder has no version in its name, so a new major version
overwrites the previous one. `check_s3.py` reads the version from
`artifacts_<model_id>/shared/metadata.json` and only counts a snapshot as complete when it
matches.

## Reading the table with the connector

The connector cannot be called from Python. Read the table yourself and save the JSON:

1. `list_records_for_table` with `baseId=appR6ZwgLgG8RTdoU`, `tableId=tblfnOcphh8KX6TI0`,
   `pageSize=500` and `fieldIds` = Snapshot, Version and the calculation fields you need.
2. When the result is large it is saved to a file automatically; pass that file path to the
   scripts with `--airtable`. Otherwise write the response to a JSON file in the scratchpad.
3. If `nextCursor` is set, fetch the next page and save the pages as a JSON list.

With a personal access token in `AIRTABLE_TOKEN`, the scripts read the table themselves
with `--from-api`.
