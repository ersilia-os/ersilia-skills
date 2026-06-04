"""describe_compound.py — deterministic one-line description of a compound.

Given a SMILES, produces a single human-readable sentence combining a
scaffold/ring descriptor and the salient functional groups. Everything is
derived from RDKit (ring perception + Chem.Fragments) — no LLM, no network,
fully reproducible. See `describe()`.

An optional LLM phrasing layer can sit on top of `features()` (which returns
the structured, deterministic signals) — see `to_prompt()`. That keeps the
*content* grounded in RDKit while letting an LLM handle only the wording.
"""
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski, Fragments

# Named ring systems exposed as RDKit fr_ flags -> readable name
RING_FLAGS = {
    "fr_benzene": "benzene", "fr_pyridine": "pyridine", "fr_imidazole": "imidazole",
    "fr_furan": "furan", "fr_thiophene": "thiophene", "fr_thiazole": "thiazole",
    "fr_oxazole": "oxazole", "fr_tetrazole": "tetrazole", "fr_piperdine": "piperidine",
    "fr_piperzine": "piperazine", "fr_morpholine": "morpholine",
    "fr_dihydropyridine": "dihydropyridine",
}
# Functional groups, ordered most-characteristic first so truncation keeps the
# defining group. Readable names carry no trailing "group" word.
FG_FLAGS = [
    ("fr_sulfonamd", "sulfonamide"), ("fr_lactam", "lactam"), ("fr_nitro", "nitro"),
    ("fr_phos_acid", "phosphate"), ("fr_guanido", "guanidine"), ("fr_amidine", "amidine"),
    ("fr_nitrile", "nitrile"), ("fr_hdrzine", "hydrazine"), ("fr_azo", "azo"),
    ("fr_oxime", "oxime"), ("fr_epoxide", "epoxide"), ("fr_COO", "carboxylic acid"),
    ("fr_ester", "ester"), ("fr_lactone", "lactone"), ("fr_amide", "amide"),
    ("fr_urea", "urea"), ("fr_aldehyde", "aldehyde"), ("fr_ketone", "ketone"),
    ("fr_aniline", "aniline"), ("fr_SH", "thiol"), ("fr_sulfone", "sulfone"),
    ("fr_sulfide", "thioether"), ("fr_phenol", "phenol"), ("fr_NH2", "primary amine"),
    ("fr_NH1", "secondary amine"), ("fr_NH0", "tertiary amine"), ("fr_ether", "ether"),
    ("fr_Al_OH", "hydroxyl"), ("fr_halogen", "halogen"),
]
SIZE = {0: "acyclic", 1: "monocyclic", 2: "bicyclic", 3: "tricyclic"}


def _join(items):
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def features(smiles):
    """Return the deterministic structured signals (no prose)."""
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    rings = Descriptors.RingCount(m)
    arom = Lipinski.NumAromaticRings(m)
    return {
        "rings": rings,
        "aromatic_rings": arom,
        "aliphatic_rings": rings - arom,
        "named_rings": [n for f, n in RING_FLAGS.items() if getattr(Fragments, f)(m) > 0],
        "functional_groups": [n for f, n in FG_FLAGS if getattr(Fragments, f)(m) > 0],
    }


def describe(smiles, max_fgs=4):
    """Deterministic one-line description."""
    fe = features(smiles)
    if fe is None:
        return "Invalid SMILES."
    rings, arom, aliph = fe["rings"], fe["aromatic_rings"], fe["aliphatic_rings"]
    size = SIZE.get(rings, "polycyclic")
    if rings == 0:
        arom_word = ""
    elif arom and not aliph:
        arom_word = "aromatic "
    elif aliph and not arom:
        arom_word = "saturated "
    else:
        arom_word = "mixed aromatic/aliphatic "

    core = f"a {size} {arom_word}compound"
    if size == "acyclic":
        core = "an acyclic compound"
    if fe["named_rings"]:
        core += f" containing {_join(fe['named_rings'])}"
    fgs = fe["functional_groups"][:max_fgs]
    if fgs:
        if len(fgs) == 1:
            core += f", bearing a {fgs[0]} group"
        else:
            core += f", bearing {_join(fgs)} groups"
    else:
        core += " with no notable functional groups"
    return core[0].upper() + core[1:] + "."


def to_prompt(smiles):
    """Build an LLM prompt from the deterministic features (optional phrasing layer)."""
    fe = features(smiles)
    if fe is None:
        return None
    return (
        "Write a single concise sentence describing this compound. "
        "Use ONLY these facts; do not add or infer anything else:\n"
        f"- rings: {fe['rings']} (aromatic: {fe['aromatic_rings']}, aliphatic: {fe['aliphatic_rings']})\n"
        f"- named ring systems: {', '.join(fe['named_rings']) or 'none'}\n"
        f"- functional groups: {', '.join(fe['functional_groups']) or 'none'}"
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(describe(sys.argv[1]))
    else:
        tests = {
            "ciprofloxacin": "OC(=O)c1cn(C2CC2)c2cc(N3CCNCC3)c(F)cc2c1=O",
            "amoxicillin": "CC1(C)SC2C(NC(=O)C(N)c3ccc(O)cc3)C(=O)N2C1C(=O)O",
            "aspirin": "CC(=O)Oc1ccccc1C(=O)O",
            "caffeine": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
            "ibuprofen": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
            "metronidazole": "Cc1ncc([N+]([O-])=O)n1CCO",
            "ethanol": "CCO",
            "sulfamethoxazole": "Cc1cc(NS(=O)(=O)c2ccc(N)cc2)no1",
        }
        for name, smi in tests.items():
            print(f"{name:18s}: {describe(smi)}")
