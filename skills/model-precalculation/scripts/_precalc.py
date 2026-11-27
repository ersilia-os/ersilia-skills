"""Shared constants and loaders for the model-precalculation scripts.

The Precalculations table in Airtable is the single source of truth for which
calculations each model snapshot (``eosXXXX_vN``) still needs. These helpers turn
the table into plain Python dicts, so the queue and reconciliation scripts can be
tested without Airtable access.

Two input routes are supported, because the Airtable connector used by Claude
cannot be called from a subprocess:

* ``--airtable PATH``: a JSON file saved from the Airtable connector
  (``list_records_for_table`` output, or a list of several such pages).
* ``--from-api``: read the table directly over the Airtable REST API, using a
  personal access token in ``AIRTABLE_TOKEN`` (read-only scope is enough).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE_ID = "appR6ZwgLgG8RTdoU"  # Ersilia Model Hub
TABLE_ID = "tblfnOcphh8KX6TI0"  # Precalculations

SNAPSHOT_FIELD = "fldizgVkFaYFtLiH2"
# Formula: "Latest" when the row is the model's current major version,
# "Superseded" for older major versions.
VERSION_FIELD = "fldwZE0kglPtLcYE9"

# Calculation columns, in the order they are shown to the user.
CALCULATIONS = {
    "reference_library_1M_v0": "fldF6jXSJpBgEQUVE",
    "eosframes": "fldSSgZLmzvbEZoCO",
    "eosquality": "fldSnnMv8wmb1hijH",
    "olinda": "fldR5bzI73bQe6F6J",
    "enamine_hll_460K_v0": "fldLzrqyJtnsvXxnT",
    "enamine_lsc_2M_v0": "fldCTEwVgjdPYlSOn",
    "enamine_real_sample_10M_v0": "fldf7knxW8PIBUTL2",
    "enamine_real_sample_1B_v0": "fldgSwDUnbt9junc9",
    "molport_5M_v0": "fldxhZkn0N1OY8BQT",
    "coconut_715K_v0": "fldRqYpDolF80CQjx",
}

# Calculation -> the calculation it waits for, and the status that unblocks it.
# The Airtable automation "Unblock dependent calculations" applies the same rule.
DEPENDENCIES = {
    "eosframes": ("reference_library_1M_v0", "Isaura"),
    "eosquality": ("reference_library_1M_v0", "Isaura"),
}

# Statuses meaning "finished" for each kind of column.
FINISHED = {"Isaura", "Done"}

# Statuses a person sets on purpose; the scripts never propose changing them.
HUMAN_DECISIONS = {"Not required", "Deleted"}

# Number of molecules in reference_library_1M_v0, as stored in isaura.
REFERENCE_LIBRARY_SIZE = 1_355_109


def _select_name(value):
    """Return the option name(s) of a select cell, whatever shape it arrives in."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("name")
    if isinstance(value, list):
        names = [_select_name(v) for v in value]
        names = [n for n in names if n]
        if not names:
            return None
        # Multi-select cells should not occur (enamine_lsc_2M_v0 was fixed on
        # 2026-11-26); join them so build_queue.py flags any that reappear.
        return names[0] if len(names) == 1 else " + ".join(names)
    return str(value)


def normalise_record(record: dict) -> dict:
    """Flatten one Airtable record into {record_id, snapshot, <calc>: status}.

    Accepts both the connector shape (``cellValuesByFieldId``) and the REST
    API shape (``fields`` keyed by field ID when ``returnFieldsByFieldId`` is
    set).
    """
    cells = record.get("cellValuesByFieldId") or record.get("fields") or {}
    out = {
        "record_id": record.get("id"),
        "snapshot": cells.get(SNAPSHOT_FIELD),
        # Missing when the saved JSON predates the Version field; treat as Latest
        # so nothing is silently dropped from the queue.
        "version": cells.get(VERSION_FIELD) or "Latest",
    }
    for name, fid in CALCULATIONS.items():
        out[name] = _select_name(cells.get(fid))
    return out


def load_from_file(path: str) -> list[dict]:
    """Load records from a saved connector response (one page or a list of pages)."""
    data = json.loads(Path(path).read_text())
    pages = data if isinstance(data, list) else [data]
    records = []
    for page in pages:
        if isinstance(page, dict) and "records" in page:
            records.extend(page["records"])
        elif isinstance(page, dict) and (
            "cellValuesByFieldId" in page or "fields" in page
        ):
            records.append(page)
        else:
            sys.exit(f"ERROR: {path} does not look like Airtable records.")
    return [normalise_record(r) for r in records]


def load_from_api(token: str | None = None) -> list[dict]:
    """Read every Precalculations record over the Airtable REST API."""
    token = token or os.environ.get("AIRTABLE_TOKEN")
    if not token:
        sys.exit(
            "ERROR: --from-api needs a personal access token in AIRTABLE_TOKEN.\n"
            "Without one, read the table with the Airtable connector and pass "
            "the saved JSON with --airtable."
        )
    fields = [SNAPSHOT_FIELD, VERSION_FIELD, *CALCULATIONS.values()]
    records, offset = [], None
    while True:
        params = [("returnFieldsByFieldId", "true"), ("pageSize", "100")]
        params += [("fields[]", f) for f in fields]
        if offset:
            params.append(("offset", offset))
        url = (
            f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}?"
            + urllib.parse.urlencode(params)
        )
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            page = json.load(resp)
        records.extend(page.get("records", []))
        offset = page.get("offset")
        if not offset:
            break
    return [normalise_record(r) for r in records]


def load_records(args) -> list[dict]:
    """Load and validate records from whichever source the CLI arguments name."""
    if getattr(args, "from_api", False):
        records = load_from_api()
    elif getattr(args, "airtable", None):
        records = load_from_file(args.airtable)
    else:
        sys.exit("ERROR: pass --airtable <saved connector JSON> or --from-api.")
    missing = [r["record_id"] for r in records if not r["snapshot"]]
    if missing:
        print(
            f"[warn] {len(missing)} record(s) have no Snapshot and are ignored: "
            + ", ".join(missing[:10]),
            file=sys.stderr,
        )
    return [r for r in records if r["snapshot"]]


def split_snapshot(snapshot: str) -> tuple[str, str]:
    """Split ``eos9x3z_v1`` into (``eos9x3z``, ``v1``)."""
    model_id, _, version = snapshot.partition("_")
    return model_id, version


def add_source_args(parser) -> None:
    """Add the --airtable / --from-api pair shared by every script."""
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--airtable", help="Saved Airtable connector JSON (one page or a list)"
    )
    src.add_argument(
        "--from-api",
        action="store_true",
        help="Read the table over the REST API (needs AIRTABLE_TOKEN)",
    )
