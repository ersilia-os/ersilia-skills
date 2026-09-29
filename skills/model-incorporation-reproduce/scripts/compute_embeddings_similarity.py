"""
Compute per-molecule cosine similarity between reference and Ersilia embedding vectors.

Usage:
    python compute_embeddings_similarity.py \
        --reference <reference_embeddings.csv> \
        --ersilia <ersilia_embeddings.csv> \
        [--smiles-col smiles]

Both CSVs must have:
  - A SMILES column (--smiles-col, default: "smiles") used to align rows.
  - All remaining numeric columns treated as embedding dimensions.

Output (stdout): key=value lines with summary stats and verdict.
Per-molecule details go to stderr.

Exit codes:
  0 = EQUIVALENT   (mean cosine similarity >= 0.999)
  1 = APPROXIMATE  (0.990 <= mean < 0.999)
  2 = DIVERGENT    (mean < 0.990)
"""

import argparse
import sys

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


def load_embeddings(path: str, smiles_col: str):
    df = pd.read_csv(path)
    if smiles_col not in df.columns:
        raise ValueError(
            f"SMILES column '{smiles_col}' not found in {path}. "
            f"Available: {list(df.columns)}"
        )
    smiles = df[smiles_col].tolist()
    feat_cols = [c for c in df.columns if c != smiles_col]
    matrix = df[feat_cols].apply(pd.to_numeric, errors="coerce").values
    return smiles, matrix


def main():
    parser = argparse.ArgumentParser(
        description="Compare embedding cosine similarity between reference and Ersilia outputs."
    )
    parser.add_argument("--reference", required=True, help="CSV with reference embeddings")
    parser.add_argument("--ersilia", required=True, help="CSV with Ersilia wrapper embeddings")
    parser.add_argument(
        "--smiles-col", default="smiles", help="Column name for SMILES (default: smiles)"
    )
    args = parser.parse_args()

    smiles_ref, mat_ref = load_embeddings(args.reference, args.smiles_col)
    smiles_ers, mat_ers = load_embeddings(args.ersilia, args.smiles_col)

    ref_index = {s: i for i, s in enumerate(smiles_ref)}
    common = [s for s in smiles_ers if s in ref_index]

    if not common:
        print("ERROR: no common SMILES between reference and Ersilia files.", file=sys.stderr)
        sys.exit(2)

    skipped = len(smiles_ers) - len(common)
    if skipped:
        print(
            f"WARNING: {skipped} SMILES in Ersilia file not found in reference — skipped.",
            file=sys.stderr,
        )

    ers_order = {s: i for i, s in enumerate(smiles_ers)}
    idx_ref = [ref_index[s] for s in common]
    idx_ers = [ers_order[s] for s in common]

    A = mat_ref[idx_ref]
    B = mat_ers[idx_ers]

    if A.shape[1] != B.shape[1]:
        print(
            f"ERROR: embedding dimensions differ — reference has {A.shape[1]}, "
            f"Ersilia has {B.shape[1]}.",
            file=sys.stderr,
        )
        sys.exit(2)

    valid_mask = ~(np.isnan(A).any(axis=1) | np.isnan(B).any(axis=1))
    n_dropped = int((~valid_mask).sum())
    if n_dropped:
        print(
            f"WARNING: {n_dropped} molecules had NaN in embeddings and were skipped.",
            file=sys.stderr,
        )

    A = A[valid_mask]
    B = B[valid_mask]
    valid_smiles = [common[i] for i, ok in enumerate(valid_mask) if ok]

    if len(A) == 0:
        print("ERROR: no valid molecule pairs after NaN filtering.", file=sys.stderr)
        sys.exit(2)

    sims = np.array(
        [cosine_similarity(A[i : i + 1], B[i : i + 1])[0, 0] for i in range(len(A))]
    )

    print("Per-molecule cosine similarity:", file=sys.stderr)
    for s, sim in zip(valid_smiles, sims):
        marker = "  ← LOW" if sim < 0.990 else ""
        print(f"  {sim:.6f}  {s}{marker}", file=sys.stderr)

    mean_sim = float(np.mean(sims))
    min_sim = float(np.min(sims))
    max_sim = float(np.max(sims))
    std_sim = float(np.std(sims))
    n_below = int((sims < 0.999).sum())

    if mean_sim >= 0.999:
        verdict = "EQUIVALENT"
        code = 0
    elif mean_sim >= 0.990:
        verdict = "APPROXIMATE"
        code = 1
    else:
        verdict = "DIVERGENT"
        code = 2

    print(f"molecules_compared: {len(A)}")
    print(f"mean_cosine_similarity: {mean_sim:.6f}")
    print(f"min_cosine_similarity: {min_sim:.6f}")
    print(f"max_cosine_similarity: {max_sim:.6f}")
    print(f"std_cosine_similarity: {std_sim:.6f}")
    print(f"count_below_0.999: {n_below}")
    print(f"verdict: {verdict}")

    sys.exit(code)


if __name__ == "__main__":
    main()
