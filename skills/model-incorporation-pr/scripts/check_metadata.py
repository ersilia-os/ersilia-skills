"""Check the metadata limits that CI enforces, before an incorporation is submitted.

Usage: python check_metadata.py <model_path>

Prints one line per check and exits 1 if any fails.
"""

import csv
import sys
from pathlib import Path

import yaml


def main(model_path):
    root = Path(model_path)
    meta = yaml.safe_load((root / "metadata.yml").read_text())
    desc, interp = meta["Description"], meta["Interpretation"]
    with open(root / "model/framework/columns/run_columns.csv") as f:
        n_cols = sum(1 for _ in csv.DictReader(f))

    checks = [
        (
            f"Description: {len(desc)} chars",
            200 <= len(desc) <= 600,
            "must be 200-600 characters",
        ),
        (
            f"Interpretation: {len(interp)} chars, {len(interp.split())} words",
            10 <= len(interp) <= 300 and len(interp.split()) <= 20 and ":" not in interp,
            "must be 10-300 characters, at most 20 words, no colon",
        ),
        (
            f"Output Dimension: {meta['Output Dimension']} vs {n_cols} rows in run_columns.csv",
            meta["Output Dimension"] == n_cols,
            "must equal the number of rows in run_columns.csv",
        ),
    ]
    failed = 0
    for label, ok, rule in checks:
        print(("OK    " if ok else "FAIL  ") + label + ("" if ok else f"  ({rule})"))
        failed += not ok
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
