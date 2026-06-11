"""
swot_facts.py — compute a compact, deterministic 'facts' record per compound that the
skill agent reads to hand-author the SWOT one-liners. Config-driven (no hardcoded cols).

Usage:
    python swot_facts.py --config config.json

Reads <output_dir>/selection_table.csv + the config, and writes <output_dir>/swot_facts.csv:
one row per compound with the activity/consensus summary, liabilities (structural alerts from
drug_criteria.py + any liability-role columns over threshold), physchem, detected structural
motifs and a confident structural class. The agent never reads the full input CSV — only this.
"""
import os
import sys
import json
import argparse
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Crippen, rdMolDescriptors as rdMD

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from drug_criteria import structural_alerts  # noqa: E402

# ---- structural motif + confident class detection (reused from the Mtb build) ----
MOTIFS = {
    "nitro": ["[NX3+](=O)[O-]"], "aniline": ["[NX3;H2,H1][c]"],
    "sulfonamide": ["[SX4](=O)(=O)[NX3]"], "hydrazone": ["[NX3][NX2]=[CX3]"],
    "acylhydrazide": ["[CX3](=O)[NX3][NX3]"], "michael_acceptor": ["[CX3]=[CX3][CX3]=[OX1]"],
    "thiophene": ["c1ccsc1"], "furan": ["c1ccoc1"], "tetrazole": ["c1nnnn1"],
    "triazole": ["c1nncn1", "c1ncnn1", "c1cnnn1"], "oxadiazole": ["c1nnco1", "c1ncno1"],
    "pyrazole": ["c1ccnn1"], "long_alkyl": ["[CH2][CH2][CH2][CH2][CH2]"],
}
_COMPILED = [(n, [p for p in (Chem.MolFromSmarts(x) for x in sm) if p]) for n, sm in MOTIFS.items()]
_AROM_NITRO = Chem.MolFromSmarts("c[NX3+](=O)[O-]")
_ANILINE = Chem.MolFromSmarts("c[NX3;H1,H2;!$([NX3][CX3]=[OX1])]")
_SULFONAMIDE = Chem.MolFromSmarts("c[SX4](=O)(=O)[NX3]")
_BENZIMIDAZOLE = Chem.MolFromSmarts("c1ccc2[nH]cnc2c1")
_BENZOTRIAZOLE = Chem.MolFromSmarts("c1ccc2nnnc2c1")
_ACYLHYDRAZONE = Chem.MolFromSmarts("[CX3](=O)[NX3][NX2]=[CX3]")


def detect_motifs(mol):
    found = [n for n, pats in _COMPILED if any(mol.HasSubstructMatch(p) for p in pats)]
    if rdMD.CalcNumSpiroAtoms(mol) >= 1:
        found.append("spiro")
    if rdMD.CalcNumBridgeheadAtoms(mol) >= 2:
        found.append("bridged_cage")
    return found


def classify(mol):
    nitro = mol.HasSubstructMatch(_AROM_NITRO)
    if nitro and mol.HasSubstructMatch(_ANILINE):
        return "amino-nitroarene"
    if nitro:
        return "nitroaromatic"
    if mol.HasSubstructMatch(_BENZIMIDAZOLE):
        return "benzimidazole"
    if mol.HasSubstructMatch(_BENZOTRIAZOLE):
        return "benzotriazole"
    if mol.HasSubstructMatch(_ACYLHYDRAZONE):
        return "acylhydrazone"
    if mol.HasSubstructMatch(_SULFONAMIDE):
        return "aryl-sulfonamide"
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = json.load(open(args.config))
    out_dir = cfg["output_dir"]
    tab = pd.read_csv(os.path.join(out_dir, "selection_table.csv"))
    n = len(tab)

    pscore = cfg["primary_score"]
    asc = not cfg.get("primary_higher_better", True)
    prank = tab[pscore].rank(ascending=asc, method="min").astype(int)

    # role lookups
    roles = {c["name"]: c.get("role") for c in cfg["columns"]}
    higher = {c["name"]: c.get("higher_better", True) for c in cfg["columns"]}
    cell_cut = cfg.get("cell_cutoffs", {})
    liability_cols = [name for name, r in roles.items() if r == "liability"]
    badge_names = [t["name"] for t in cfg.get("badges", [])]
    badge_tot = {t["name"]: len(t["columns"]) for t in cfg.get("badges", [])}

    rows = []
    for i, r in tab.iterrows():
        mol = Chem.MolFromSmiles(r["smiles"])
        # which liability columns are 'on' (over cutoff, or for higher-worse > cutoff)
        flagged = []
        for c in liability_cols:
            cut = cell_cut.get(c, {}).get("cutoff", 0.5)
            v = r.get(c)
            if pd.notna(v) and ((v >= cut) if not higher.get(c, False) else (v >= cut)):
                flagged.append(c)
        alerts = []
        if mol is not None:
            ev = structural_alerts(r["smiles"], catalogs=("PAINS", "BRENK"))
            alerts = sorted({a.get("description", a.get("name", "alert")) for a in ev.get("alerts", [])})[:4]
        rec = {
            "cpd_id": r["cpd_id"], "smiles": r["smiles"],
            "primary": round(float(r[pscore]), 3), "primary_rank": int(prank[i]), "n_total": n,
            "struct_class": classify(mol) if mol else "",
            "motifs": "|".join(detect_motifs(mol)) if mol else "",
            "mw": round(rdMD.CalcExactMolWt(mol), 0) if mol else None,
            "logp": round(Crippen.MolLogP(mol), 2) if mol else None,
            "liability_cols": "|".join(flagged) or "none",
            "structural_alerts": "|".join(alerts) or "none",
        }
        for b in badge_names:
            rec[b] = f"{int(r[b])}/{badge_tot[b]}"
        rows.append(rec)

    facts = pd.DataFrame(rows)
    out_path = os.path.join(out_dir, "swot_facts.csv")
    facts.to_csv(out_path, index=False)
    print(f"Wrote {out_path}: {len(facts)} rows")
    print(f"  struct_class counts: {facts['struct_class'].replace('', '—').value_counts().to_dict()}")
    if n > 250:
        print(f"  NOTE: {n} compounds — authoring a bespoke SWOT line for each is a large task; "
              f"consider tightening filters/cutoffs first.")


if __name__ == "__main__":
    main()
