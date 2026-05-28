#!/usr/bin/env python3
"""
Compute physicochemical property windows for each bucket's reference SMILES set.

Reads `assets/reference_<bucket>.csv` files and emits a markdown table per
bucket with min / p25 / median / p75 / max for each 2D RDKit descriptor, plus
a list of compounds that fall outside the p5-p95 band for any property. The
output is intended to be copy-pasted into `references/<bucket>-criteria.md`.

Design constraints:
- Minimal dependencies: RDKit + Python stdlib only.
- 2D descriptors only — no conformer generation, no 3D / shape descriptors.
- Re-runnable: if the reference compound set changes, regenerate the tables.

Usage:
    python compute_reference_properties.py
        [--bucket <name>]
        [--assets-dir <path>]
        [--output-mode markdown|csv|both]

Defaults:
- Scans every `reference_*.csv` in the skill's assets/ directory.
- Emits one markdown section per bucket to stdout.
"""

import argparse
import csv
import statistics
import sys
from pathlib import Path

try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
except ImportError:
    sys.stderr.write(
        "ERROR: RDKit is required. Install with `pip install rdkit` "
        "or `conda install -c conda-forge rdkit`.\n"
    )
    sys.exit(1)


# --- Descriptor definitions --------------------------------------------------

DESCRIPTORS = [
    ("MW",            lambda m: Descriptors.MolWt(m),            1),
    ("LogP",          lambda m: Descriptors.MolLogP(m),          2),
    ("TPSA",          lambda m: Descriptors.TPSA(m),             1),
    ("HBD",           lambda m: Descriptors.NumHDonors(m),       0),
    ("HBA",           lambda m: Descriptors.NumHAcceptors(m),    0),
    ("RotBonds",      lambda m: Descriptors.NumRotatableBonds(m),0),
    ("AromaticRings", lambda m: Descriptors.NumAromaticRings(m), 0),
    ("Fsp3",          lambda m: Descriptors.FractionCSP3(m),     2),
    ("HeavyAtoms",    lambda m: Descriptors.HeavyAtomCount(m),   0),
]


def percentile(sorted_vals, p):
    """Linear-interpolation percentile (p in [0, 1])."""
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def fmt(v, decimals):
    if v is None:
        return "—"
    if decimals == 0:
        return f"{int(round(v))}"
    return f"{v:.{decimals}f}"


# --- Per-compound descriptor computation -------------------------------------

def compute_for_smiles(smiles):
    """Return {descriptor_name: value} or None if SMILES is unparseable."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    out = {}
    for name, fn, _ in DESCRIPTORS:
        try:
            out[name] = float(fn(mol))
        except Exception:
            out[name] = None
    return out


def load_bucket(csv_path):
    """Load a reference CSV. Returns list of {name, class, smiles, descriptors}."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            smiles = (row.get("smiles") or "").strip()
            name = (row.get("name") or "").strip()
            klass = (row.get("class") or "").strip()
            if not smiles:
                continue
            descs = compute_for_smiles(smiles)
            if descs is None:
                sys.stderr.write(
                    f"  warning: could not parse SMILES for "
                    f"{name or smiles!r} in {csv_path.name}; skipping\n"
                )
                continue
            rows.append({
                "name": name,
                "class": klass,
                "smiles": smiles,
                "descriptors": descs,
            })
    return rows


# --- Per-bucket summarisation ------------------------------------------------

def summarise_bucket(bucket_name, rows):
    """Compute summary stats + identify outliers."""
    n = len(rows)
    summary = {"bucket": bucket_name, "n": n, "stats": {}, "outliers": []}

    if n == 0:
        return summary

    # Stats per descriptor
    for name, _fn, _dec in DESCRIPTORS:
        vals = [r["descriptors"][name] for r in rows
                if r["descriptors"].get(name) is not None]
        vals.sort()
        if not vals:
            summary["stats"][name] = None
            continue
        summary["stats"][name] = {
            "min":    vals[0],
            "p5":     percentile(vals, 0.05),
            "p25":    percentile(vals, 0.25),
            "median": percentile(vals, 0.50),
            "p75":    percentile(vals, 0.75),
            "p95":    percentile(vals, 0.95),
            "max":    vals[-1],
        }

    # Outliers: any compound with any property outside its [p5, p95] band
    for r in rows:
        flags = []
        for name, _fn, dec in DESCRIPTORS:
            s = summary["stats"].get(name)
            if s is None:
                continue
            v = r["descriptors"].get(name)
            if v is None:
                continue
            if v < s["p5"] or v > s["p95"]:
                direction = "<" if v < s["p5"] else ">"
                bound = s["p5"] if v < s["p5"] else s["p95"]
                flags.append(f"{name}={fmt(v, dec)} ({direction}{fmt(bound, dec)})")
        if flags:
            summary["outliers"].append({
                "name": r["name"] or r["smiles"][:30],
                "flags": flags,
            })

    return summary


# --- Output formatting --------------------------------------------------------

def render_markdown(summary):
    lines = []
    bucket = summary["bucket"]
    n = summary["n"]
    lines.append(f"### Property windows for `{bucket}` (n = {n} compounds)")
    lines.append("")
    if n == 0:
        lines.append("_No reference compounds loaded._")
        lines.append("")
        return "\n".join(lines)

    lines.append("| Property | min | p25 | median | p75 | max |")
    lines.append("|---|---|---|---|---|---|")
    for name, _fn, dec in DESCRIPTORS:
        s = summary["stats"].get(name)
        if s is None:
            lines.append(f"| {name} | — | — | — | — | — |")
            continue
        lines.append(
            f"| {name} | {fmt(s['min'], dec)} | {fmt(s['p25'], dec)} | "
            f"{fmt(s['median'], dec)} | {fmt(s['p75'], dec)} | {fmt(s['max'], dec)} |"
        )
    lines.append("")

    if summary["outliers"]:
        lines.append("**Outlier compounds** (any property outside the p5–p95 band):")
        for o in summary["outliers"]:
            flags = "; ".join(o["flags"])
            lines.append(f"- **{o['name']}** — {flags}")
        lines.append("")
    else:
        lines.append("_No compounds fall outside the p5–p95 band on any property._")
        lines.append("")

    return "\n".join(lines)


def render_csv(summary, writer):
    bucket = summary["bucket"]
    for name, _fn, _dec in DESCRIPTORS:
        s = summary["stats"].get(name)
        if s is None:
            writer.writerow([bucket, name, "", "", "", "", "", "", ""])
            continue
        writer.writerow([
            bucket, name,
            s["min"], s["p5"], s["p25"], s["median"], s["p75"], s["p95"], s["max"],
        ])


# --- Main ---------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bucket", default=None,
                   help="Restrict to one bucket (e.g. 'antimalarial'). "
                        "Default: process all reference_*.csv files.")
    p.add_argument("--assets-dir", default=None,
                   help="Path to assets/ directory. Default: ../assets relative "
                        "to this script.")
    p.add_argument("--output-mode", default="markdown",
                   choices=["markdown", "csv", "both"],
                   help="Output format (default: markdown).")
    return p.parse_args()


def discover_bucket_files(assets_dir, bucket_filter):
    files = sorted(assets_dir.glob("reference_*.csv"))
    if bucket_filter:
        # Match either reference_<bucket>.csv exactly, or substring on bucket name
        wanted = [f for f in files if f.stem == f"reference_{bucket_filter}"
                  or bucket_filter in f.stem]
        if not wanted:
            sys.stderr.write(
                f"ERROR: no reference file matches bucket '{bucket_filter}' "
                f"in {assets_dir}\n"
            )
            sys.exit(2)
        return wanted
    return files


def bucket_name_from_path(path):
    stem = path.stem  # reference_<bucket>
    return stem[len("reference_"):] if stem.startswith("reference_") else stem


def main():
    args = parse_args()

    if args.assets_dir:
        assets_dir = Path(args.assets_dir).resolve()
    else:
        assets_dir = (Path(__file__).resolve().parent.parent / "assets").resolve()

    if not assets_dir.is_dir():
        sys.stderr.write(f"ERROR: assets directory not found: {assets_dir}\n")
        sys.exit(2)

    bucket_files = discover_bucket_files(assets_dir, args.bucket)
    if not bucket_files:
        sys.stderr.write(f"WARNING: no reference_*.csv files in {assets_dir}\n")
        return

    summaries = []
    for path in bucket_files:
        bucket = bucket_name_from_path(path)
        sys.stderr.write(f"Processing {path.name} (bucket: {bucket})...\n")
        rows = load_bucket(path)
        summaries.append(summarise_bucket(bucket, rows))

    if args.output_mode in ("markdown", "both"):
        for s in summaries:
            print(render_markdown(s))

    if args.output_mode in ("csv", "both"):
        if args.output_mode == "both":
            print()  # blank line separator
        writer = csv.writer(sys.stdout)
        writer.writerow(
            ["bucket", "property", "min", "p5", "p25", "median",
             "p75", "p95", "max"]
        )
        for s in summaries:
            render_csv(s, writer)


if __name__ == "__main__":
    main()
