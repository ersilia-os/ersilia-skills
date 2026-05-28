#!/usr/bin/env python3
"""
Ersilia molecule auditor — processes a screening CSV and produces a summary
that Claude can use to write an audit report without reading the full dataset.

Usage:
    python process_molecules.py <csv_path> \
        --metadata <metadata_json_path> \
        [--top-n 30] \
        [--context "malaria"] \
        [--mode similar|novel] \
        [--skill-dir <path>] \
        [--output-dir <dir>]

Arguments:
    csv_path            Path to the eosframes-format CSV file
    --metadata          Path to a JSON file mapping column names to metadata.
                        Each entry must include:
                          want_high: true/false/null
                          scoring_role: "efficacy"|"safety_flag"|"beneficial_admet"|
                                        "physicochemical"|"info"
                          flag_threshold: float or null (for safety_flag columns)
                          description: str
    --top-n             Number of top candidates to include in detail (default: 30)
    --context           Therapeutic context string (optional, framed in report)
    --mode              Structural novelty mode: "similar" (prefer known-antibiotic-like
                        compounds) or "novel" (prefer structurally distinct compounds).
                        Requires RDKit. Loads reference SMILES from
                        <skill-dir>/assets/antibiotic_reference.csv.
    --skill-dir         Path to the skill directory (needed for --mode)
    --output-dir        Directory for output files (default: same dir as csv_path)

Outputs (written to output_dir):
    audit_summary.json  Stats + top N candidates — the only file Claude reads

Key design note on scoring:
    Only columns with scoring_role == "efficacy" contribute to the aggregate activity
    score. Safety/toxicity columns (scoring_role == "safety_flag") are used for flags,
    not for scoring. Physicochemical columns are handled via Lipinski/Veber rules.
    The want_high field (not direction) determines normalisation direction — want_high
    reflects whether a higher value is *desirable*, which must be reasoned from the
    concept, not assumed from the encoding convention.
"""

import sys
import json
import csv
import re
import argparse
import os
from pathlib import Path

# RDKit is a hard requirement. The molecule-auditing skill's Step 0 enforces
# this before invoking the script; if you're invoking it directly, make sure
# your Python interpreter has RDKit installed.
from rdkit import Chem
from rdkit.Chem import Descriptors, DataStructs, AllChem
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams

_PAINS_PARAMS = FilterCatalogParams()
_PAINS_PARAMS.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
PAINS_CATALOG = FilterCatalog(_PAINS_PARAMS)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("csv_path")
    p.add_argument("--metadata", required=True,
                   help="JSON file: {col_name: {want_high, scoring_role, flag_threshold, "
                        "description, model_title, model_interpretation}}")
    p.add_argument("--top-n", type=int, default=30)
    p.add_argument("--context", default="")
    p.add_argument("--mode", default=None, choices=["similar", "novel"],
                   help="Structural mode: 'similar' or 'novel' vs known antibiotics")
    p.add_argument("--skill-dir", default=None,
                   help="Skill directory (for loading antibiotic_reference.csv)")
    p.add_argument("--output-dir", default=None)
    return p.parse_args()


# ---------------------------------------------------------------------------
# CSV loading helpers
# ---------------------------------------------------------------------------

def detect_smiles_column(headers):
    for h in headers:
        if h.lower() in ("smiles", "input"):
            return h
    return None

def detect_key_column(headers):
    for h in headers:
        if h.lower() == "key":
            return h
    return None

MODEL_ID_RE = re.compile(r'^(.+)\.(eos[0-9a-z]{4})$')

def parse_score_columns(headers):
    """Return list of (col_name, feature_name, model_id) for columns with eos suffix."""
    result = []
    for h in headers:
        m = MODEL_ID_RE.match(h)
        if m:
            result.append((h, m.group(1), m.group(2)))
    return result

def parse_unknown_columns(headers, smiles_col, key_col, score_cols):
    known = {smiles_col, key_col} | {c[0] for c in score_cols}
    return [h for h in headers if h and h not in known]


# ---------------------------------------------------------------------------
# RDKit-based helpers
# ---------------------------------------------------------------------------

def lipinski_violations(mol, Descriptors):
    mw   = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    hbd  = Descriptors.NumHDonors(mol)
    hba  = Descriptors.NumHAcceptors(mol)
    viols = []
    if mw   > 500: viols.append(f"MW={mw:.0f}")
    if logp > 5:   viols.append(f"LogP={logp:.1f}")
    if hbd  > 5:   viols.append(f"HBD={hbd}")
    if hba  > 10:  viols.append(f"HBA={hba}")
    return viols

# ---------------------------------------------------------------------------
# Antibiotic reference loading and Tanimoto similarity
# ---------------------------------------------------------------------------

def load_antibiotic_reference(skill_dir, Chem, AllChem):
    """Load reference antibiotic SMILES and compute Morgan fingerprints."""
    if skill_dir is None:
        return None, None
    ref_path = Path(skill_dir) / "assets" / "antibiotic_reference.csv"
    if not ref_path.exists():
        return None, None

    refs = []
    fps = []
    with open(ref_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            smi = row.get("smiles", "").strip()
            if not smi:
                continue
            mol = Chem.MolFromSmiles(smi)
            if mol is None:
                continue
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
            refs.append({"class": row.get("class", ""), "name": row.get("name", ""),
                         "smiles": smi})
            fps.append(fp)
    return refs, fps if fps else None


def max_tanimoto(query_fp, ref_fps, DataStructs):
    """Return max Tanimoto similarity of query_fp against all ref_fps."""
    if not ref_fps:
        return None
    sims = DataStructs.BulkTanimotoSimilarity(query_fp, ref_fps)
    return max(sims) if sims else None


NOVELTY_THRESHOLD = 0.3   # below this → structurally novel


# ---------------------------------------------------------------------------
# Per-column statistics (for Dataset Overview section)
# ---------------------------------------------------------------------------

def compute_column_stats(col_values, col_meta, score_cols):
    """
    Compute summary statistics for every recognized score column.

    Returns a dict keyed by col_name with:
        n, n_missing, min, max, mean, p25, p50, p75, p95,
        n_above_threshold, pct_above_threshold (for safety_flag columns),
        scoring_role, description, model_title
    """
    stats = {}
    for col_name, feature, model_id in score_cols:
        values = col_values.get(col_name, [])
        meta = col_meta.get(col_name) or col_meta.get(feature) or {}
        role = meta.get("scoring_role", "info")
        threshold = meta.get("flag_threshold")

        entry = {
            "scoring_role":  role,
            "description":   meta.get("description", ""),
            "model_title":   meta.get("model_title", ""),
            "want_high":     meta.get("want_high"),
            "model_id":      model_id,
            "n":             len(values),
            "n_missing":     0,   # filled below
        }

        if values:
            sv = sorted(values)
            n = len(sv)
            entry["min"]  = round(sv[0], 4)
            entry["max"]  = round(sv[-1], 4)
            entry["mean"] = round(sum(sv) / n, 4)
            entry["p25"]  = round(sv[max(0, int(n * 0.25) - 1)], 4)
            entry["p50"]  = round(sv[max(0, int(n * 0.50) - 1)], 4)
            entry["p75"]  = round(sv[max(0, int(n * 0.75) - 1)], 4)
            entry["p95"]  = round(sv[max(0, int(n * 0.95) - 1)], 4)
            if threshold is not None:
                n_above = sum(1 for v in sv if v > threshold)
                entry["n_above_threshold"]   = n_above
                entry["pct_above_threshold"] = round(100.0 * n_above / n, 1)
            else:
                entry["n_above_threshold"]   = None
                entry["pct_above_threshold"] = None
        else:
            for k in ("min", "max", "mean", "p25", "p50", "p75", "p95"):
                entry[k] = None
            entry["n_above_threshold"]   = None
            entry["pct_above_threshold"] = None

        stats[col_name] = entry
    return stats


# ---------------------------------------------------------------------------
# Normalised score (want_high-aware — NOT direction-based)
# ---------------------------------------------------------------------------

def normalised_score(raw_value, want_high):
    """
    Return a 0–1 score where higher is always "better" (for efficacy columns only).

    want_high=True  → higher raw value is better (e.g. inhibition probability)
    want_high=False → lower raw value is better (e.g. IC50; flip so score is still 0–1)
    want_high=None  → column is not used for scoring (physicochemical, info, etc.)

    Note: this uses want_high, NOT direction. direction encodes the value-concept
    relationship (encoding convention); want_high encodes desirability (drug discovery
    objective). They are related but not the same — always reason about want_high
    from the concept description, not from direction alone.
    """
    try:
        v = float(raw_value)
    except (ValueError, TypeError):
        return None
    if want_high is True:
        return v
    elif want_high is False:
        return 1.0 - v
    return None  # None → excluded from aggregate


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process(args):
    csv_path = Path(args.csv_path)
    output_dir = Path(args.output_dir) if args.output_dir else csv_path.parent

    # Load column metadata (must contain want_high, scoring_role, flag_threshold)
    with open(args.metadata) as f:
        col_meta = json.load(f)

    # Load antibiotic reference for novelty/similarity mode
    ref_mols, ref_fps = None, None
    if args.mode:
        ref_mols, ref_fps = load_antibiotic_reference(args.skill_dir, Chem, AllChem)
        if ref_fps is None:
            print(f"Warning: --mode {args.mode} requested but no reference SMILES loaded "
                  f"(check antibiotic_reference.csv in skill assets). "
                  f"Continuing without novelty scoring.", file=sys.stderr)

    # --- First pass: stream rows ---
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        smiles_col   = detect_smiles_column(headers)
        key_col      = detect_key_column(headers)
        score_cols   = parse_score_columns(headers)
        unknown_cols = parse_unknown_columns(headers, smiles_col, key_col, score_cols)

        # Identify column roles from metadata
        efficacy_cols   = []  # contribute to aggregate score
        safety_flag_cols = []  # flagged when value > threshold
        # (beneficial_admet and physicochemical are informational in the summary)

        for col_name, feature, model_id in score_cols:
            meta = col_meta.get(col_name) or col_meta.get(feature) or {}
            role = meta.get("scoring_role", "")
            want_high = meta.get("want_high")   # True / False / None
            threshold = meta.get("flag_threshold")

            if role == "efficacy" and want_high is not None:
                efficacy_cols.append((col_name, feature, model_id, want_high))
            elif role == "safety_flag":
                th = threshold if threshold is not None else 0.5
                safety_flag_cols.append((col_name, feature, model_id, th))

        # Fallback: if no safety_flag columns defined in metadata, use hERG pattern
        HERG_PATTERN = re.compile(r'(herg|cardiotox)', re.IGNORECASE)
        herg_fallback_cols = []
        if not safety_flag_cols:
            for col_name, feature, model_id in score_cols:
                if HERG_PATTERN.search(col_name):
                    herg_fallback_cols.append(col_name)

        # Accumulate raw values for ALL score columns (for per-column statistics)
        all_score_col_names = [c[0] for c in score_cols]
        col_values = {c: [] for c in all_score_col_names}

        rows = []
        n_total = 0
        n_invalid_smiles = 0

        for row in reader:
            n_total += 1
            mol_key    = row.get(key_col, str(n_total)) if key_col else str(n_total)
            smiles_val = row.get(smiles_col, "") if smiles_col else ""

            # Collect raw values for ALL score columns (for statistics)
            for col_name in all_score_col_names:
                raw = row.get(col_name)
                try:
                    rv = float(raw)
                    col_values[col_name].append(rv)
                except (ValueError, TypeError):
                    pass

            # Aggregate activity score — efficacy columns ONLY
            scores = []
            raw_scores = {}
            safety_flags = []  # list of (col_name, value, threshold) tuples

            for col_name, feature, model_id, want_high in efficacy_cols:
                raw = row.get(col_name)
                try:
                    rv = float(raw)
                except (ValueError, TypeError):
                    rv = None
                raw_scores[col_name] = rv
                ns = normalised_score(rv, want_high)
                if ns is not None:
                    scores.append(ns)

            # Safety flags (separate from scoring)
            for col_name, feature, model_id, threshold in safety_flag_cols:
                raw = row.get(col_name)
                try:
                    rv = float(raw)
                except (ValueError, TypeError):
                    rv = None
                raw_scores.setdefault(col_name, rv)
                if rv is not None and rv > threshold:
                    safety_flags.append((col_name, rv, threshold))

            # hERG fallback (only when no safety_flag columns defined)
            herg_flag = False
            if herg_fallback_cols:
                for col_name in herg_fallback_cols:
                    raw = row.get(col_name)
                    try:
                        rv = float(raw)
                    except (ValueError, TypeError):
                        rv = None
                    if rv is not None and rv > 0.5:
                        herg_flag = True

            activity_score = sum(scores) / len(scores) if scores else None

            # Lipinski / PAINS
            lip_viols = []
            pains_flag = False
            mol_valid = True
            max_sim = None

            if smiles_val:
                mol = Chem.MolFromSmiles(smiles_val)
                if mol is None:
                    mol_valid = False
                    n_invalid_smiles += 1
                else:
                    lip_viols = lipinski_violations(mol, Descriptors)
                    entry = PAINS_CATALOG.GetFirstMatch(mol)
                    if entry:
                        pains_flag = True

                    # Tanimoto similarity to antibiotic reference set
                    if ref_fps:
                        try:
                            qfp = AllChem.GetMorganFingerprintAsBitVect(
                                mol, radius=2, nBits=2048)
                            max_sim = max_tanimoto(qfp, ref_fps, DataStructs)
                        except Exception:
                            pass

            # Novelty flag: True if max_sim < NOVELTY_THRESHOLD (structurally distinct)
            novelty_flag = None
            if max_sim is not None:
                novelty_flag = max_sim < NOVELTY_THRESHOLD

            rows.append({
                "key":            mol_key,
                "smiles":         smiles_val,
                "activity_score": activity_score,
                "raw_scores":     raw_scores,
                "lip_viols":      lip_viols,
                "safety_flags":   safety_flags,
                "herg_flag":      herg_flag,   # only used when safety_flag metadata absent
                "pains_flag":     pains_flag,
                "mol_valid":      mol_valid,
                "max_tanimoto":   max_sim,
                "novelty_flag":   novelty_flag,
            })

    # --- Sort ---
    valid_rows   = [r for r in rows if r["activity_score"] is not None]
    invalid_rows = [r for r in rows if r["activity_score"] is None]
    valid_rows.sort(key=lambda r: r["activity_score"], reverse=True)
    n_scored = len(valid_rows)

    # --- Classify ---
    top25_threshold = (valid_rows[max(0, int(n_scored * 0.25) - 1)]["activity_score"]
                       if n_scored > 0 else 0)
    top50_threshold = (valid_rows[max(0, int(n_scored * 0.50) - 1)]["activity_score"]
                       if n_scored > 0 else 0)

    def has_safety_concern(r):
        """True if any safety flag triggered, or hERG fallback triggered, or PAINS."""
        return bool(r["safety_flags"]) or r["herg_flag"] or r["pains_flag"]

    def classify(r):
        if not r["mol_valid"]:
            return "Exclude"
        s = r["activity_score"]
        if s is None:
            return "Unscored"
        n_lip = len(r["lip_viols"])
        safety = has_safety_concern(r)

        # In "novel" mode, structurally similar compounds are mildly penalised
        # (downgraded from Promising to Borderline if similarity is high)
        similarity_penalty = (
            args.mode == "novel"
            and r["max_tanimoto"] is not None
            and r["max_tanimoto"] >= 0.5
        )

        if (s >= top25_threshold
                and n_lip <= 1
                and not safety
                and not similarity_penalty):
            return "Promising"
        if s >= top50_threshold or (s >= top25_threshold and n_lip <= 2):
            return "Borderline"
        return "Deprioritise"

    for r in valid_rows + invalid_rows:
        r["classification"] = classify(r)

    all_rows = valid_rows + invalid_rows

    from collections import Counter
    counts = Counter(r["classification"] for r in all_rows)

    # --- Top N candidates ---
    top_candidates = []
    for r in valid_rows[:args.top_n]:
        top_candidates.append({
            "key":            r["key"],
            "smiles":         r["smiles"],
            "activity_score": round(r["activity_score"], 4) if r["activity_score"] is not None else None,
            "raw_scores":     {k: round(v, 4) if v is not None else None
                               for k, v in r["raw_scores"].items()},
            "lip_violations": r["lip_viols"],
            "safety_flags":   [(c, round(v, 4), t) for c, v, t in r["safety_flags"]],
            "herg_flag":      r["herg_flag"],
            "pains_flag":     r["pains_flag"],
            "classification": r["classification"],
            "max_tanimoto":   round(r["max_tanimoto"], 4) if r["max_tanimoto"] is not None else None,
            "novelty_flag":   r["novelty_flag"],
        })

    # --- Score distribution ---
    def percentile_buckets(sorted_scores, n_buckets=10):
        if not sorted_scores:
            return []
        bucket_size = max(1, len(sorted_scores) // n_buckets)
        return [round(sorted_scores[min(i * bucket_size, len(sorted_scores) - 1)], 4)
                for i in range(n_buckets)]

    activity_scores = [r["activity_score"] for r in valid_rows]
    score_distribution = percentile_buckets(list(reversed(activity_scores)))

    # --- Novelty stats (when mode is set) ---
    novelty_stats = None
    if args.mode:
        n_with_sim = sum(1 for r in all_rows if r["max_tanimoto"] is not None)
        n_novel    = sum(1 for r in all_rows
                         if r["max_tanimoto"] is not None
                         and r["max_tanimoto"] < NOVELTY_THRESHOLD)
        n_similar  = n_with_sim - n_novel
        novelty_stats = {
            "mode":      args.mode,
            "threshold": NOVELTY_THRESHOLD,
            "n_with_similarity_computed": n_with_sim,
            "n_novel":   n_novel,
            "n_similar": n_similar,
            "reference_compounds": len(ref_fps) if ref_fps else 0,
        }

    # --- Models summary ---
    model_ids = list({model_id for _, _, model_id, _ in efficacy_cols})

    # --- Per-column statistics (for Dataset Overview preamble) ---
    column_stats = compute_column_stats(col_values, col_meta, score_cols)

    # --- Build summary ---
    summary = {
        "input_file":          str(csv_path),
        "context":             args.context,
        "mode":                args.mode,
        "n_total":             n_total,
        "n_scored":            n_scored,
        "n_invalid_smiles":    n_invalid_smiles,
        "models_detected":     model_ids,
        "efficacy_columns":    [{"col": c, "feature": f, "model": m, "want_high": wh}
                                for c, f, m, wh in efficacy_cols],
        "safety_flag_columns": [{"col": c, "feature": f, "model": m, "threshold": th}
                                for c, f, m, th in safety_flag_cols],
        "unknown_columns":     unknown_cols,
        "classification_counts": dict(counts),
        "score_distribution_top_to_bottom": score_distribution,
        "top_candidates":      top_candidates,
        "thresholds": {
            "top25": round(top25_threshold, 4),
            "top50": round(top50_threshold, 4),
        },
        "novelty_stats":       novelty_stats,
        "column_stats":        column_stats,
        "caveats": {
            "unknown_cols":            len(unknown_cols) > 0,
            "no_efficacy_cols":        len(efficacy_cols) == 0,
            "no_safety_flag_metadata": not safety_flag_cols,
        }
    }

    output_path = output_dir / "audit_summary.json"
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"audit_summary.json written to {output_path}")
    print(f"Total molecules: {n_total} | Scored: {n_scored} | "
          f"Promising: {counts.get('Promising', 0)} | "
          f"Borderline: {counts.get('Borderline', 0)} | "
          f"Deprioritise: {counts.get('Deprioritise', 0)}")
    if novelty_stats:
        print(f"Novelty ({args.mode} mode): "
              f"{novelty_stats['n_novel']} novel / {novelty_stats['n_similar']} similar "
              f"(threshold={NOVELTY_THRESHOLD})")
    return str(output_path)


if __name__ == "__main__":
    args = parse_args()
    process(args)
