"""Gate a candidate model output against a reference output.

Two modes:

exact
    For models with Output Consistency: Fixed. Header and every cell must be
    string-identical. Line endings and a trailing newline are the only
    differences tolerated.

        python compare_outputs.py exact <reference.csv> <candidate.csv>

distribution
    For models with Output Consistency: Variable. Several reference runs and
    several candidate runs are pooled per column. Numeric columns pass a
    two-sample Kolmogorov-Smirnov test at alpha=0.01; text columns must keep
    the fraction of empty and of unique values within 0.10 of the reference.

    Columns that hold SMILES (generative models) are checked together instead,
    because a per-column check would pass even for garbage molecules. This
    needs RDKit, so run the script with a Python that has it (e.g. the model's
    scratch env). Over all SMILES cells: the fraction of empty cells, the
    fraction of non-empty cells that RDKit parses, and the mean per-row
    fraction of unique molecules must stay within 0.10 of the reference; and
    the distributions of molecular weight, heavy atoms, rings, logP and TPSA
    must not differ from the reference by more than the reference runs differ
    among themselves (KS distance, with 1.5x margin, never stricter than the
    alpha=0.01 critical value). Needs at least 2 reference runs.

        python compare_outputs.py distribution --ref r1.csv r2.csv r3.csv \
            --cand c1.csv c2.csv c3.csv

sanity
    Checks that one output is a real prediction and not a silently broken
    model, before it is used as the reference: as many rows as inputs, not all
    cells empty, and (with at least 3 distinct inputs) not every column
    constant. Columns that are entirely empty or constant are listed.

        python compare_outputs.py sanity <input.csv> <output.csv>

Exits 0 on PASS and 1 on FAIL, and prints a JSON verdict.
"""

import argparse
import csv
import json
import math
import random
import sys

KS_C_ALPHA_001 = 1.628
TEXT_TOLERANCE = 0.10
NOISE_MARGIN = 1.5
MAX_MOLS_PER_RUN = 5000

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors

    RDLogger.DisableLog("rdApp.*")
    DESCRIPTORS = {
        "mol_weight": Descriptors.MolWt,
        "heavy_atoms": lambda m: m.GetNumHeavyAtoms(),
        "rings": rdMolDescriptors.CalcNumRings,
        "logp": Crippen.MolLogP,
        "tpsa": rdMolDescriptors.CalcTPSA,
    }
except ImportError:
    Chem = None


def read(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def exact(ref_path, cand_path):
    ref_h, ref_rows = read(ref_path)
    cand_h, cand_rows = read(cand_path)
    mismatches = []
    if ref_h != cand_h:
        mismatches.append({"where": "header", "reference": ref_h, "candidate": cand_h})
    if len(ref_rows) != len(cand_rows):
        mismatches.append(
            {"where": "row_count", "reference": len(ref_rows), "candidate": len(cand_rows)}
        )
    for i, (r, c) in enumerate(zip(ref_rows, cand_rows)):
        for j, (a, b) in enumerate(zip(r, c)):
            if a != b:
                col = ref_h[j] if j < len(ref_h) else j
                mismatches.append({"row": i + 1, "column": col, "reference": a, "candidate": b})
        if len(r) != len(c):
            mismatches.append({"row": i + 1, "where": "cell_count"})
    with open(ref_path, "rb") as f1, open(cand_path, "rb") as f2:
        byte_identical = f1.read() == f2.read()
    return {
        "mode": "exact",
        "verdict": "PASS" if not mismatches else "FAIL",
        "byte_identical": byte_identical,
        "n_mismatches": len(mismatches),
        "first_mismatches": mismatches[:10],
    }


def to_float(v):
    try:
        x = float(v)
    except ValueError:
        return None
    return None if math.isnan(x) else x


def ks_statistic(a, b):
    a, b = sorted(a), sorted(b)
    i = j = 0
    d = 0.0
    while i < len(a) and j < len(b):
        x = min(a[i], b[j])
        while i < len(a) and a[i] <= x:
            i += 1
        while j < len(b) and b[j] <= x:
            j += 1
        d = max(d, abs(i / len(a) - j / len(b)))
    return d


def pool(paths):
    header = None
    columns = {}
    for p in paths:
        h, rows = read(p)
        if header is None:
            header = h
            columns = {k: [] for k in h}
        elif h != header:
            return h, None
        for r in rows:
            for k, v in zip(h, r):
                columns[k].append(v)
    return header, columns


def ks_critical(n, m):
    return KS_C_ALPHA_001 * math.sqrt((n + m) / (n * m))


def is_smiles_column(values):
    vals = [v for v in values if v][:50]
    return bool(vals) and sum(Chem.MolFromSmiles(v) is not None for v in vals) >= 0.5 * len(vals)


def smiles_run_stats(path, columns):
    """Summary statistics and a descriptor sample over the SMILES cells of one run."""
    header, rows = read(path)
    idx = [header.index(c) for c in columns]
    n_cells = n_empty = n_valid = 0
    row_unique, mols = [], []
    for r in rows:
        canon = []
        for j in idx:
            v = r[j] if j < len(r) else ""
            n_cells += 1
            if not v:
                n_empty += 1
                continue
            m = Chem.MolFromSmiles(v)
            if m is None:
                continue
            n_valid += 1
            canon.append(Chem.MolToSmiles(m))
            mols.append(m)
        if canon:
            row_unique.append(len(set(canon)) / len(canon))
    n_filled = n_cells - n_empty
    rng = random.Random(0)
    if len(mols) > MAX_MOLS_PER_RUN:
        mols = rng.sample(mols, MAX_MOLS_PER_RUN)
    return {
        "empty": n_empty / max(n_cells, 1),
        "valid": n_valid / max(n_filled, 1),
        "row_unique": sum(row_unique) / max(len(row_unique), 1),
        "descriptors": {k: [f(m) for m in mols] for k, f in DESCRIPTORS.items()},
    }


def smiles_checks(ref_paths, cand_paths, columns):
    ref = [smiles_run_stats(p, columns) for p in ref_paths]
    cand = [smiles_run_stats(p, columns) for p in cand_paths]
    results = []
    for k in ("empty", "valid", "row_unique"):
        r = sum(x[k] for x in ref) / len(ref)
        c = sum(x[k] for x in cand) / len(cand)
        results.append({"check": k, "reference": round(r, 3), "candidate": round(c, 3),
                        "pass": abs(r - c) <= TEXT_TOLERANCE})
    for k in DESCRIPTORS:
        a = [v for x in ref for v in x["descriptors"][k]]
        b = [v for x in cand for v in x["descriptors"][k]]
        if not a or not b:
            results.append({"check": k, "pass": not a and not b})
            continue
        # noise floor: how far each reference run is from the other reference runs
        noise = 0.0
        for i, x in enumerate(ref):
            rest = [v for j, y in enumerate(ref) if j != i for v in y["descriptors"][k]]
            if x["descriptors"][k] and rest:
                noise = max(noise, ks_statistic(x["descriptors"][k], rest))
        d = ks_statistic(a, b)
        limit = max(ks_critical(len(a), len(b)), NOISE_MARGIN * noise)
        results.append({"check": k, "ks_d": round(d, 4), "ref_noise_d": round(noise, 4),
                        "limit": round(limit, 4), "pass": d <= limit})
    return results


def distribution(ref_paths, cand_paths):
    ref_h, ref_cols = pool(ref_paths)
    cand_h, cand_cols = pool(cand_paths)
    if ref_cols is None or cand_cols is None or ref_h != cand_h:
        return {"mode": "distribution", "verdict": "FAIL", "reason": "headers differ"}
    results, failed = [], False
    smiles_cols = []
    if Chem is not None:
        smiles_cols = [k for k in ref_h
                       if sum(to_float(v) is not None for v in ref_cols[k]) < 0.9 * len(ref_cols[k])
                       and is_smiles_column(ref_cols[k])]
    smiles_results = []
    if smiles_cols:
        if len(ref_paths) < 2:
            return {"mode": "distribution", "verdict": "FAIL",
                    "reason": "SMILES outputs need at least 2 reference runs"}
        smiles_results = smiles_checks(ref_paths, cand_paths, smiles_cols)
        failed = not all(r["pass"] for r in smiles_results)
    for k in ref_h:
        if k in smiles_cols:
            continue
        ref_num = [to_float(v) for v in ref_cols[k]]
        cand_num = [to_float(v) for v in cand_cols[k]]
        numeric = sum(x is not None for x in ref_num) >= 0.9 * len(ref_num) > 0
        if numeric:
            a = [x for x in ref_num if x is not None]
            b = [x for x in cand_num if x is not None]
            if not b:
                results.append({"column": k, "type": "numeric", "pass": False})
                failed = True
                continue
            d = ks_statistic(a, b)
            crit = ks_critical(len(a), len(b))
            ok = d <= crit
            results.append(
                {"column": k, "type": "numeric", "ks_d": round(d, 4),
                 "critical": round(crit, 4), "pass": ok}
            )
        else:
            def fractions(vals):
                n = max(len(vals), 1)
                return sum(v == "" for v in vals) / n, len(set(vals)) / n

            re_, ru = fractions(ref_cols[k])
            ce, cu = fractions(cand_cols[k])
            ok = abs(re_ - ce) <= TEXT_TOLERANCE and abs(ru - cu) <= TEXT_TOLERANCE
            results.append(
                {"column": k, "type": "text", "empty_ref": round(re_, 3),
                 "empty_cand": round(ce, 3), "unique_ref": round(ru, 3),
                 "unique_cand": round(cu, 3), "pass": ok}
            )
        failed = failed or not ok
    out = {
        "mode": "distribution",
        "verdict": "FAIL" if failed else "PASS",
        "n_columns": len(results) + len(smiles_cols),
        "failing_columns": [r for r in results if not r["pass"]][:20],
    }
    if smiles_cols:
        out["smiles_columns"] = len(smiles_cols)
        out["smiles_checks"] = smiles_results
    elif Chem is None:
        out["warning"] = "RDKit not available: SMILES columns were checked as plain text"
    return out


def sanity(input_path, output_path):
    _, inputs = read(input_path)
    header, rows = read(output_path)
    problems = []
    if len(rows) != len(inputs):
        problems.append(f"{len(rows)} output rows for {len(inputs)} inputs")
    cols = {k: [r[j] if j < len(r) else "" for r in rows] for j, k in enumerate(header)}
    empty = [k for k, v in cols.items() if all(x.strip() == "" for x in v)]
    constant = [k for k, v in cols.items() if k not in empty and len(set(v)) == 1]
    if cols and len(empty) == len(cols):
        problems.append("every output cell is empty")
    distinct_inputs = len({tuple(r) for r in inputs})
    if distinct_inputs >= 3 and cols and len(empty) + len(constant) == len(cols):
        problems.append("every output column is empty or constant across distinct inputs")
    filled = sum(x.strip() != "" for v in cols.values() for x in v)
    return {
        "mode": "sanity",
        "verdict": "FAIL" if problems else "PASS",
        "problems": problems,
        "rows": len(rows), "inputs": len(inputs), "columns": len(cols),
        "filled_fraction": round(filled / max(len(rows) * len(cols), 1), 3),
        "empty_columns": empty[:20], "constant_columns": constant[:20],
    }


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    e = sub.add_parser("exact")
    e.add_argument("reference")
    e.add_argument("candidate")
    d = sub.add_parser("distribution")
    d.add_argument("--ref", nargs="+", required=True)
    d.add_argument("--cand", nargs="+", required=True)
    s = sub.add_parser("sanity")
    s.add_argument("input")
    s.add_argument("output")
    args = ap.parse_args()
    if args.mode == "exact":
        out = exact(args.reference, args.candidate)
    elif args.mode == "sanity":
        out = sanity(args.input, args.output)
    else:
        out = distribution(args.ref, args.cand)
    print(json.dumps(out, indent=2))
    sys.exit(0 if out["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
