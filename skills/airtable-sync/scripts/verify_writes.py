"""Check that what was written to Airtable is what was approved.

After the writes, the skill re-reads each touched table through the connector and runs
`normalise_airtable.py --out /tmp/airtable_sync/<table>.after.json`. This script
compares every record in ``writes.json`` with that re-read: updates by record id,
creates by their identifying value (Name, Title or URL), deletes by the record being
absent. GitHub calls are checked by `apply_github.py`. Prints one line per mismatch
and exits 1 if there is any.

Usage:
    python verify_writes.py [--writes /tmp/airtable_sync/writes.json] [--work /tmp/airtable_sync]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import TABLES, WORK_DIR, die, read_json

# How a newly created row is found again in the re-read.
CREATE_KEY = {"repositories": "name", "publications": "title", "blogposts": "url"}


def _norm(value):
    if isinstance(value, list):
        return sorted(v["id"] if isinstance(v, dict) else v for v in value)
    return value


def main(argv: list[str] | None = None) -> int:
    """Compare approved writes with the re-read tables."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--writes", default=f"{WORK_DIR}/writes.json")
    p.add_argument("--work", default=WORK_DIR)
    args = p.parse_args(argv)

    writes = read_json(args.writes) or die(f"missing {args.writes}")
    table_by_id = {t["id"]: name for name, t in TABLES.items()}
    problems, checked = [], 0
    for call in writes["calls"]:
        if call["tool"] == "gh":
            continue  # checked by apply_github.py, which runs them
        table = table_by_id[call["tableId"]]
        after = read_json(Path(args.work) / f"{table}.after.json")
        if after is None:
            problems.append(f"{table}: no re-read found ({table}.after.json)")
            continue
        key_by_fid = {fid: key for key, (fid, _) in TABLES[table]["fields"].items()}
        by_id = {r["id"]: r for r in after}
        ck = CREATE_KEY[table]
        by_key = {r.get(ck): r for r in after if r.get(ck)}
        if call["tool"] == "delete_records_for_table":
            for n, rid in zip(call["items"], call["recordIds"]):
                checked += 1
                if rid in by_id:
                    problems.append(
                        f"[{n}] {table}: record {rid} still exists after delete"
                    )
            continue
        for n, rec in zip(call["items"], call["records"]):
            checked += 1
            fields = {key_by_fid[f]: v for f, v in rec["fields"].items()}
            row = by_id.get(rec["id"]) if "id" in rec else by_key.get(fields.get(ck))
            if row is None:
                problems.append(f"[{n}] {table}: record not found after write")
                continue
            for key, want in fields.items():
                if _norm(row.get(key)) != _norm(want):
                    problems.append(
                        f"[{n}] {table}.{key}: expected {want!r}, found {row.get(key)!r}"
                    )
    for line in problems:
        print(line)
    print(
        f"verified {checked} record(s): {'OK' if not problems else f'{len(problems)} problem(s)'}"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
