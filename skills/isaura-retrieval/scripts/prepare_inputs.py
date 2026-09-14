"""Input plumbing for isaura retrieval.

Isaura's CLI is picky about input CSVs in ways that are easy to get wrong by hand:
``inspect`` only reads a column literally named ``input``, while ``read`` and ``pull``
accept ``input`` or ``smiles``; and ``inspect`` writes a completely empty file (no
header at all) when it finds nothing, which naive CSV parsing treats as an error.

This script does the three set operations the retrieval workflow needs, so the
sequence stays about isaura commands rather than about CSV wrangling.

Subcommands
-----------
normalize
    Turn a file path or a literal SMILES into a clean, deduplicated CSV with a
    single ``input`` column.
diff
    Subtract an ``inspect`` result from an input set to get what is still missing.
merge
    Union several molecule CSVs into one read set, preserving order.

Every subcommand prints the resulting molecule count to stdout so the caller can
report it without re-reading the file.
"""

import argparse
import csv
import os
import sys

#: Column names that may hold the molecule, in order of preference. Isaura itself
#: looks for "input" then "smiles"; the capitalised variants show up often enough in
#: user-supplied files to be worth accepting here.
MOLECULE_COLUMNS = ("input", "smiles", "SMILES", "Smiles")

#: Characters that never appear in a SMILES string but are common in file paths.
#: Used to tell "this argument is a path that does not exist" from "this argument
#: is a literal molecule", so a typo'd path is reported rather than silently
#: treated as a molecule.
PATH_HINTS = ("/", "\\")


def read_molecules(path):
    """Read molecules from a CSV or plain-text file.

    Parameters
    ----------
    path : str
        Path to a CSV with a molecule column, or a text file with one molecule
        per line. An empty file yields an empty list rather than raising, because
        ``isaura inspect`` writes a zero-byte file when it finds no matches.

    Returns
    -------
    list of str
        Molecules in file order, stripped of surrounding whitespace. Blank
        entries are dropped.
    """
    if os.path.getsize(path) == 0:
        return []

    with open(path, newline="", encoding="utf-8") as handle:
        sample = handle.readline()
        handle.seek(0)

        if "," in sample or any(c in sample for c in MOLECULE_COLUMNS):
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            column = next((c for c in MOLECULE_COLUMNS if c in fieldnames), None)
            if column is not None:
                return [
                    (row.get(column) or "").strip()
                    for row in reader
                    if (row.get(column) or "").strip()
                ]
            handle.seek(0)

        # No recognisable header: treat every line as a molecule, but skip a lone
        # header-looking first line so a headerless-looking CSV does not smuggle
        # the word "smiles" in as a molecule.
        lines = [line.strip() for line in handle if line.strip()]

    if lines and lines[0] in MOLECULE_COLUMNS:
        lines = lines[1:]
    return lines


def resolve_molecules(value):
    """Interpret a CLI argument as either a file of molecules or a literal SMILES.

    Parameters
    ----------
    value : str
        A path, or a SMILES string typed directly by the user.

    Returns
    -------
    list of str
        The molecules the argument refers to.
    """
    if os.path.isfile(value):
        return read_molecules(value)

    # A missing path is far more likely to be a typo than a molecule, and silently
    # treating it as a SMILES would produce a confident "not in isaura" answer for
    # a molecule that was never real. Fail loudly instead.
    if any(hint in value for hint in PATH_HINTS) or value.lower().endswith((".csv", ".txt", ".tsv")):
        sys.exit(f"No such file: {value}")

    return [part.strip() for part in value.split() if part.strip()]


def dedupe(molecules):
    """Drop duplicates while preserving first-seen order.

    Order matters because the user recognises their own input ordering in the
    results, and duplicates matter because they inflate the counts reported back
    without adding any information.
    """
    seen = set()
    unique = []
    for molecule in molecules:
        if molecule not in seen:
            seen.add(molecule)
            unique.append(molecule)
    return unique


def write_molecules(path, molecules):
    """Write molecules as a CSV with a single ``input`` column.

    The header is always written, even for an empty set, so downstream isaura
    commands get a well-formed file.
    """
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["input"])
        for molecule in molecules:
            writer.writerow([molecule])


def cmd_normalize(args):
    """Turn a file or literal SMILES into a deduplicated ``input``-column CSV."""
    molecules = dedupe(resolve_molecules(args.input))
    write_molecules(args.output, molecules)
    print(f"{len(molecules)} molecules → {args.output}")


def cmd_diff(args):
    """Write the molecules in ``--input`` that are absent from ``--found``."""
    wanted = dedupe(read_molecules(args.input))
    found = set(read_molecules(args.found))
    missing = [molecule for molecule in wanted if molecule not in found]
    write_molecules(args.output, missing)
    print(f"{len(missing)} of {len(wanted)} molecules missing → {args.output}")


def cmd_merge(args):
    """Union several molecule CSVs into one, preserving first-seen order."""
    molecules = []
    for path in args.inputs:
        if os.path.isfile(path):
            molecules.extend(read_molecules(path))
    molecules = dedupe(molecules)
    write_molecules(args.output, molecules)
    print(f"{len(molecules)} molecules → {args.output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    normalize = subparsers.add_parser(
        "normalize", help="Build a clean input CSV from a file or a literal SMILES"
    )
    normalize.add_argument("--input", required=True, help="Path to a file, or a SMILES string")
    normalize.add_argument("--output", required=True, help="Path for the normalised CSV")
    normalize.set_defaults(func=cmd_normalize)

    diff = subparsers.add_parser(
        "diff", help="Subtract an inspect result from an input set"
    )
    diff.add_argument("--input", required=True, help="The full input CSV")
    diff.add_argument("--found", required=True, help="The CSV written by isaura inspect")
    diff.add_argument("--output", required=True, help="Path for the missing-molecule CSV")
    diff.set_defaults(func=cmd_diff)

    merge = subparsers.add_parser("merge", help="Union several molecule CSVs")
    merge.add_argument("--inputs", required=True, nargs="+", help="CSVs to merge")
    merge.add_argument("--output", required=True, help="Path for the merged CSV")
    merge.set_defaults(func=cmd_merge)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
