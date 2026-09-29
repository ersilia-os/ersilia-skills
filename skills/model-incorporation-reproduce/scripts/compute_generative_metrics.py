"""
Compute generative model evaluation metrics.

Usage:
    python compute_generative_metrics.py \
        --generated <generated.csv> --smiles-col <col> \
        [--training <training.csv> --training-smiles-col <col>]

Outputs a JSON object with:
  n_generated, n_valid, validity, n_unique, uniqueness, novelty (if training set given),
  sa_score_available, and a "properties" dict (qed, sa_score, mw, logp, hbd, hba, tpsa)
  — each as {mean, std, median, min, max} computed over unique valid generated molecules.

Exit codes: 0 = success, 1 = error.
"""

import argparse
import importlib.util
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

try:
    from rdkit import Chem, RDConfig
    from rdkit.Chem import Descriptors, QED, rdMolDescriptors
except ImportError:
    print(
        "ERROR: RDKit is required. Install via: conda install -c conda-forge rdkit",
        file=sys.stderr,
    )
    sys.exit(1)

# Locate sascorer via RDConfig (the canonical RDKit way) or common fallback paths.
_SA_AVAILABLE = False
_sascorer = None
_candidate_paths = [
    os.path.join(RDConfig.RDContribDir, "SA_Score", "sascorer.py"),
    "/opt/conda/share/RDKit/Contrib/SA_Score/sascorer.py",
]
for _p in _candidate_paths:
    if os.path.exists(_p):
        try:
            spec = importlib.util.spec_from_file_location("sascorer", _p)
            _sascorer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_sascorer)
            _SA_AVAILABLE = True
            break
        except Exception:
            pass


def mol_from_smiles(s: str):
    try:
        return Chem.MolFromSmiles(str(s))
    except Exception:
        return None


def compute_properties(mols: list) -> dict:
    qed_vals, mw_vals, logp_vals, hbd_vals, hba_vals, tpsa_vals, sa_vals = (
        [], [], [], [], [], [], []
    )
    for mol in mols:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                qed_vals.append(QED.qed(mol))
            except Exception:
                pass
            try:
                mw_vals.append(Descriptors.MolWt(mol))
            except Exception:
                pass
            try:
                logp_vals.append(Descriptors.MolLogP(mol))
            except Exception:
                pass
            try:
                hbd_vals.append(rdMolDescriptors.CalcNumHBD(mol))
            except Exception:
                pass
            try:
                hba_vals.append(rdMolDescriptors.CalcNumHBA(mol))
            except Exception:
                pass
            try:
                tpsa_vals.append(Descriptors.TPSA(mol))
            except Exception:
                pass
            if _SA_AVAILABLE:
                try:
                    sa_vals.append(_sascorer.calculateScore(mol))
                except Exception:
                    pass

    def stats(vals):
        if not vals:
            return None
        arr = np.array(vals, dtype=float)
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "median": float(np.median(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
        }

    return {
        "qed": stats(qed_vals),
        "mw": stats(mw_vals),
        "logp": stats(logp_vals),
        "hbd": stats(hbd_vals),
        "hba": stats(hba_vals),
        "tpsa": stats(tpsa_vals),
        "sa_score": stats(sa_vals) if _SA_AVAILABLE else None,
    }


def canonical(mol) -> str | None:
    try:
        return Chem.MolToSmiles(mol)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Compute generative model metrics.")
    parser.add_argument("--generated", required=True, help="CSV with generated SMILES")
    parser.add_argument(
        "--smiles-col", default="smiles", help="SMILES column in generated CSV"
    )
    parser.add_argument(
        "--training", help="CSV with training set SMILES (enables novelty computation)"
    )
    parser.add_argument(
        "--training-smiles-col",
        default="smiles",
        help="SMILES column in training CSV",
    )
    args = parser.parse_args()

    gen_df = pd.read_csv(args.generated)
    if args.smiles_col not in gen_df.columns:
        print(
            f"ERROR: column '{args.smiles_col}' not found in {args.generated}. "
            f"Available: {list(gen_df.columns)}",
            file=sys.stderr,
        )
        sys.exit(1)

    raw_smiles = gen_df[args.smiles_col].tolist()
    n_generated = len(raw_smiles)

    # Validity
    mols = [mol_from_smiles(s) for s in raw_smiles]
    valid_pairs = [(s, m) for s, m in zip(raw_smiles, mols) if m is not None]
    n_valid = len(valid_pairs)
    validity = n_valid / n_generated if n_generated > 0 else 0.0

    # Uniqueness (over valid molecules)
    seen: set[str] = set()
    unique_mols = []
    for _, m in valid_pairs:
        c = canonical(m)
        if c and c not in seen:
            seen.add(c)
            unique_mols.append(m)
    n_unique = len(unique_mols)
    uniqueness = n_unique / n_valid if n_valid > 0 else 0.0

    # Novelty
    novelty = None
    if args.training:
        train_df = pd.read_csv(args.training)
        if args.training_smiles_col not in train_df.columns:
            print(
                f"WARNING: training SMILES column '{args.training_smiles_col}' not found — "
                "skipping novelty.",
                file=sys.stderr,
            )
        else:
            train_canonical: set[str] = set()
            for s in train_df[args.training_smiles_col].tolist():
                m = mol_from_smiles(s)
                if m:
                    c = canonical(m)
                    if c:
                        train_canonical.add(c)
            novel = sum(1 for m in unique_mols if canonical(m) not in train_canonical)
            novelty = novel / n_unique if n_unique > 0 else 0.0

    properties = compute_properties(unique_mols)

    result = {
        "n_generated": n_generated,
        "n_valid": n_valid,
        "validity": round(validity, 4),
        "n_unique": n_unique,
        "uniqueness": round(uniqueness, 4),
        "novelty": round(novelty, 4) if novelty is not None else None,
        "sa_score_available": _SA_AVAILABLE,
        "properties": properties,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
