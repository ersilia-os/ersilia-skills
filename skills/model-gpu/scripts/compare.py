"""Compare two model output CSVs.

Checks same header, same number of rows, same empty cells, and numeric cells equal
within --atol (default 0: exact). Non-numeric cells must be string-identical.
Columns `key` and `input`, added by Ersilia, are ignored.

Usage
-----
    python compare.py <reference.csv> <candidate.csv> [--atol 1e-4]

Prints a JSON report. Exit code 0 if the files match, 1 otherwise.
"""

import argparse
import csv
import json
import math
import sys

IGNORED_COLUMNS = {"key", "input"}


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], []
    keep = [i for i, c in enumerate(rows[0]) if c.strip().lower() not in IGNORED_COLUMNS]
    header = [rows[0][i] for i in keep]
    return header, [[r[i] if i < len(r) else "" for i in keep] for r in rows[1:]]


def number(text):
    try:
        x = float(text)
    except ValueError:
        return None
    return None if math.isnan(x) else x


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("candidate")
    parser.add_argument("--atol", type=float, default=0.0)
    args = parser.parse_args()

    ref_header, ref = read(args.reference)
    new_header, new = read(args.candidate)
    report = {"header_equal": ref_header == new_header, "rows": [len(ref), len(new)]}

    blank_mismatches = text_mismatches = over_tolerance = 0
    max_abs_diff = 0.0
    first = []
    for r, (a_row, b_row) in enumerate(zip(ref, new)):
        for c, (a, b) in enumerate(zip(a_row, b_row)):
            if a == b:
                continue
            a_num, b_num = number(a), number(b)
            if (a.strip() == "") != (b.strip() == ""):
                blank_mismatches += 1
                bad = True
            elif a_num is None or b_num is None:
                text_mismatches += 1
                bad = True
            else:
                diff = abs(a_num - b_num)
                max_abs_diff = max(max_abs_diff, diff)
                bad = diff > args.atol
                over_tolerance += bad
            if bad and len(first) < 5:
                first.append({"row": r, "column": ref_header[c], "reference": a, "candidate": b})

    report.update(
        max_abs_diff=max_abs_diff,
        atol=args.atol,
        cells_over_tolerance=over_tolerance,
        blank_mismatches=blank_mismatches,
        text_mismatches=text_mismatches,
        first=first,
    )
    report["match"] = (
        report["header_equal"]
        and len(ref) == len(new)
        and over_tolerance == blank_mismatches == text_mismatches == 0
    )
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["match"] else 1)


if __name__ == "__main__":
    main()
