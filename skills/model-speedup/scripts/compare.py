"""Compare two model output CSVs cell by cell.

Identical means: same header, same number of rows, and every cell string-identical
(columns `key` and `input`, added by Ersilia, are ignored). When they differ, the
report says how much, to help judge the cause:

- rows_differing: rows with at least one different cell
- blank_mismatches: cells empty in one file and filled in the other
  (a molecule that failed in one run only)
- max_abs_diff / max_rel_diff: largest difference between numeric cells
  (~1e-16 is last-digit float noise; ~1e-7 is float32 noise; larger is a real change)
- first: the first few differing cells

Usage
-----
    python compare.py <reference.csv> <candidate.csv>

Prints a JSON report. Exit code 0 if identical, 1 otherwise.
"""

import csv
import json
import math
import sys

IGNORED_COLUMNS = {"key", "input"}


def _read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], []
    header = rows[0]
    keep = [i for i, name in enumerate(header) if name.strip().lower() not in IGNORED_COLUMNS]
    return [header[i] for i in keep], [[r[i] if i < len(r) else "" for i in keep] for r in rows[1:]]


def _number(text):
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def compare_files(reference, candidate, max_listed=10):
    ref_header, ref_rows = _read(reference)
    cand_header, cand_rows = _read(candidate)
    report = {"identical": False}
    if ref_header != cand_header:
        report["header"] = {"reference": ref_header, "candidate": cand_header}
        return report
    if len(ref_rows) != len(cand_rows):
        report["row_count"] = {"reference": len(ref_rows), "candidate": len(cand_rows)}
        return report

    rows_differing, blank_mismatches, max_abs, max_rel, first = 0, 0, 0.0, 0.0, []
    for row_idx, (ref_row, cand_row) in enumerate(zip(ref_rows, cand_rows), start=1):
        row_differs = False
        for col, ref_cell, cand_cell in zip(ref_header, ref_row, cand_row):
            if ref_cell == cand_cell:
                continue
            row_differs = True
            if (ref_cell.strip() == "") != (cand_cell.strip() == ""):
                blank_mismatches += 1
            a, b = _number(ref_cell), _number(cand_cell)
            if a is not None and b is not None:
                diff = abs(a - b)
                max_abs = max(max_abs, diff)
                if a != 0:
                    max_rel = max(max_rel, diff / abs(a))
            if len(first) < max_listed:
                first.append({"row": row_idx, "column": col, "reference": ref_cell, "candidate": cand_cell})
        rows_differing += row_differs

    if rows_differing == 0:
        return {"identical": True}
    report.update({
        "rows_differing": rows_differing,
        "rows_total": len(ref_rows),
        "blank_mismatches": blank_mismatches,
        "max_abs_diff": max_abs,
        "max_rel_diff": max_rel,
        "first": first,
    })
    return report


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    result = compare_files(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["identical"] else 1)
