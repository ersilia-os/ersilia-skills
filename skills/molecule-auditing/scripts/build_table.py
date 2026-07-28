"""
build_table.py — turn an Ersilia screening CSV into a condensed, filtered scoring
table, driven entirely by a config JSON (no hardcoded column names).

Usage:
    python build_table.py --config config.json

The config (written by the skill agent from the interactive interview) declares which
columns to keep, their roles/directions, the consensus badge tiers and per-column
cutoffs, the structure-quality filters to apply, optional aggregate columns, and the
primary score used to rank CPD-XXX ids. Outputs, into config["output_dir"]:
  - selection_table.csv   (the condensed table; merges swot_lines.csv if present)
  - viz_meta.json         (everything make_visualizer.py needs: column order, badge
                           definitions, per-cell cutoffs, rank-color columns, sliders,
                           legend metadata)

See SKILL.md for the config schema. All keys are optional except input_csv, smiles_col,
columns, and output_dir.
"""
import os
import sys
import json
import argparse
import pandas as pd
from rdkit import Chem
from rdkit.Chem import RDConfig, rdMolDescriptors as rdMD

sys.path.append(os.path.join(RDConfig.RDContribDir, "SA_Score"))
try:
    import sascorer  # noqa: E402
    _HAVE_SA = True
except Exception:
    _HAVE_SA = False

_HAL = {9, 17, 35, 53}


def num(series):
    return pd.to_numeric(series, errors="coerce")


def n_halogens(mol):
    return sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() in _HAL)


def n_ring_atoms(mol):
    return sum(1 for a in mol.GetAtoms() if a.IsInRing())


def sa_score(mol):
    return sascorer.calculateScore(mol) if _HAVE_SA else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = json.load(open(args.config))

    out_dir = cfg["output_dir"]
    os.makedirs(out_dir, exist_ok=True)
    df = pd.read_csv(cfg["input_csv"])
    smi_col = cfg["smiles_col"]
    key_col = cfg.get("key_col")

    n_in = len(df)
    # ---- structure-quality filters (only those present in cfg["filters"]) ----
    filt = cfg.get("filters", {}) or {}
    mols = [Chem.MolFromSmiles(s) for s in df[smi_col]]
    keep = pd.Series([m is not None for m in mols], index=df.index)
    drops = {"invalid_smiles": int((~keep).sum())}

    def mol_metric(fn):
        return pd.Series([fn(m) if m is not None else None for m in mols], index=df.index)

    if "max_mw" in filt:
        mw = mol_metric(lambda m: rdMD.CalcExactMolWt(m))
        k = mw <= filt["max_mw"]; drops["mw>%.0f" % filt["max_mw"]] = int((keep & ~k).sum()); keep &= k
    if "max_halogens" in filt:
        h = mol_metric(n_halogens)
        k = h <= filt["max_halogens"]; drops[">%d halogens" % filt["max_halogens"]] = int((keep & ~k).sum()); keep &= k
    if "min_ring_atoms" in filt:
        r = mol_metric(n_ring_atoms)
        k = r >= filt["min_ring_atoms"]; drops["<%d ring atoms" % filt["min_ring_atoms"]] = int((keep & ~k).sum()); keep &= k
    if "max_sa" in filt and _HAVE_SA:
        sa = mol_metric(sa_score)
        k = sa < filt["max_sa"]; drops["SA>=%.1f" % filt["max_sa"]] = int((keep & ~k).sum()); keep &= k
    if filt.get("drop_pains") or filt.get("drop_brenk"):
        from drug_criteria import structural_alerts
        cats = tuple(c for c, on in (("PAINS", filt.get("drop_pains")), ("BRENK", filt.get("drop_brenk"))) if on)
        has_alert = pd.Series(
            [bool(structural_alerts(s, catalogs=cats).get("alerts")) if m is not None else False
             for s, m in zip(df[smi_col], mols)], index=df.index)
        k = ~has_alert; drops["%s alert" % "/".join(cats)] = int((keep & ~k).sum()); keep &= k

    df = df[keep].reset_index(drop=True)
    mols = [m for m, k in zip(mols, keep) if k]

    # ---- assemble output columns ----
    out = pd.DataFrame()
    out["smiles"] = df[smi_col].values
    if key_col and key_col in df.columns:
        out["source_key"] = df[key_col].values

    col_specs = cfg["columns"]  # list of {src, name, role, higher_better}
    for c in col_specs:
        out[c["name"]] = num(df[c["src"]]) if c.get("numeric", True) else df[c["src"]].values

    # ---- aggregate columns (e.g. fraction of a block passing a threshold) ----
    for agg in cfg.get("aggregates", []):
        block = df[agg["cols"]].apply(pd.to_numeric, errors="coerce")
        if agg["type"] == "fraction_gt":
            out[agg["name"]] = (block > agg["threshold"]).mean(axis=1)
        elif agg["type"] == "count_gt":
            out[agg["name"]] = (block > agg["threshold"]).sum(axis=1).astype(int)
        elif agg["type"] == "mean":
            out[agg["name"]] = block.mean(axis=1)

    # ---- consensus badges (per tier: count of columns passing their cutoff) ----
    badge_meta = []
    for tier in cfg.get("badges", []):
        passes = None
        for cc in tier["columns"]:
            col, cut, op = cc["col"], cc["cutoff"], cc.get("op", ">=")
            v = out[col]
            p = (v >= cut) if op == ">=" else (v <= cut)
            passes = p.astype(int) if passes is None else passes + p.astype(int)
        out[tier["name"]] = passes.astype(int)
        badge_meta.append({"name": tier["name"], "total": len(tier["columns"]),
                           "label": tier.get("label", tier["name"])})

    # ---- CPD-XXX ids ranked by the primary score ----
    pscore = cfg["primary_score"]
    asc = not cfg.get("primary_higher_better", True)
    rank = out[pscore].rank(ascending=asc, method="first").astype(int)
    out.insert(0, "cpd_id", "CPD-" + rank.astype(str).str.zfill(3))

    # round floats
    float_cols = [c["name"] for c in col_specs if c.get("numeric", True)] + \
                 [a["name"] for a in cfg.get("aggregates", []) if a["type"] != "count_gt"]
    for c in float_cols:
        if c in out.columns:
            out[c] = out[c].round(3)

    # sort
    sort_by = cfg.get("sort_by", pscore)
    out = out.sort_values([t["name"] for t in cfg.get("badges", [])][:1] + [sort_by],
                          ascending=[False] * min(1, len(cfg.get("badges", []))) + [asc]) \
             .reset_index(drop=True)

    # merge swot if authored (tab-separated preferred — one-liners contain commas)
    for fn, sep in (("swot_lines.tsv", "\t"), ("swot_lines.csv", ",")):
        p = os.path.join(out_dir, fn)
        if os.path.exists(p):
            try:
                sw = pd.read_csv(p, sep=sep)
                out = out.merge(sw[["cpd_id", "swot"]], on="cpd_id", how="left")
            except Exception as e:
                print(f"  WARN: could not merge {fn} ({e}); skipping swot")
            break

    out_path = os.path.join(out_dir, "selection_table.csv")
    out.to_csv(out_path, index=False)

    # ---- viz_meta.json for make_visualizer + legend ----
    viz_meta = {
        "badges": badge_meta,
        "badge_defs": cfg.get("badges", []),
        "rank_color_cols": cfg.get("rank_color_cols", []),
        "cell_cutoffs": cfg.get("cell_cutoffs", {}),
        "slider_min": cfg.get("sliders", {}).get("min", []),
        "slider_max": cfg.get("sliders", {}).get("max", []),
        "category_col": cfg.get("category_col"),
        "display_cols": [c["name"] for c in col_specs] + [a["name"] for a in cfg.get("aggregates", [])],
        "primary_score": pscore,
        "sort_default": sort_by,
        "legend": cfg.get("legend", {}),   # {col_name: {meaning, model, higher_better}}
        "title": cfg.get("title", "Molecule explorer"),
    }
    json.dump(viz_meta, open(os.path.join(out_dir, "viz_meta.json"), "w"), indent=1)

    # ---- report ----
    print(f"Wrote {out_path}: {len(out)} rows x {out.shape[1]} cols (from {n_in} input)")
    print("  filters dropped:", {k: v for k, v in drops.items() if v})
    for b in badge_meta:
        print(f"  badge {b['name']} (/{b['total']}): {out[b['name']].value_counts().sort_index().to_dict()}")
    print(f"  wrote viz_meta.json; swot merged: {'swot' in out.columns}")


if __name__ == "__main__":
    main()
