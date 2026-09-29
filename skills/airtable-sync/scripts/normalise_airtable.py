"""Flatten Airtable connector dumps into one clean JSON list per table.

The Airtable connector (`list_records_for_table`) returns
``{"records": [{"id", "createdTime", "cellValuesByFieldId": {...}}], ...}``. A large
table is paginated, and the harness may save a large response to a file, sometimes
wrapped as ``[{"type": "text", "text": "<json>"}]``. This script accepts any number of
such files for one table and writes

    [{"id": "rec...", "<key>": <value>, ...}, ...]

keyed by the field keys in `_common.TABLES`, with select values reduced to their names
and linked records to ``[{"id", "name"}]``.

Usage:
    python normalise_airtable.py --table publications --in page1.json page2.json \
        [--out /tmp/airtable_sync/publications.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import TABLES, WORK_DIR, die, write_json


def _load(path: str) -> list[dict]:
    """Return the ``records`` list from one connector dump, unwrapping text blocks."""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and "text" in data[0]
    ):
        data = json.loads("".join(block.get("text", "") for block in data))
    if isinstance(data, dict) and "records" in data:
        return data["records"]
    if isinstance(data, list):
        return data
    die(f"{path}: no 'records' list found")
    return []


def _flatten(value, kind: str):
    """Reduce a connector cell value to plain JSON for comparison."""
    if value is None:
        return [] if kind in ("multi", "links") else None
    if kind == "single":
        return value.get("name") if isinstance(value, dict) else value
    if kind == "multi":
        return [v.get("name") if isinstance(v, dict) else v for v in value]
    if kind == "links":
        return [{"id": v.get("id"), "name": v.get("name")} for v in value]
    return value


def normalise(table: str, records: list[dict]) -> list[dict]:
    """Map raw connector records to ``{"id", <key>: value}`` rows for ``table``."""
    fields = TABLES[table]["fields"]
    rows = []
    for rec in records:
        cells = rec.get("cellValuesByFieldId") or rec.get("fields") or {}
        row = {"id": rec.get("id")}
        for key, (fid, kind) in fields.items():
            row[key] = _flatten(cells.get(fid), kind)
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    """Normalise one table's dumps and write them to the work directory."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--table", required=True, choices=sorted(TABLES))
    p.add_argument("--in", dest="inputs", nargs="+", required=True)
    p.add_argument("--out")
    args = p.parse_args(argv)

    records: list[dict] = []
    for path in args.inputs:
        records.extend(_load(path))
    rows = normalise(args.table, records)
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        die("duplicate record ids across inputs: the same page was passed twice")
    out = args.out or f"{WORK_DIR}/{args.table}.json"
    write_json(out, rows)
    print(f"{args.table}: {len(rows)} records -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
