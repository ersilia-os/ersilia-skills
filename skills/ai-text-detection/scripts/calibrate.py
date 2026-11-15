"""Fit the style-score thresholds on human text, measure how well they work, write them down.

A score means something only next to the rate at which human text gets the same score.
Inputs (references/calibration/): human.jsonl (pre-ChatGPT human windows, build_corpus.py),
ai.jsonl (AI-written windows on the same topics, several generators) and polished.jsonl
(human windows rewritten by an AI "to improve the English", reported separately). Also read:
~/.ai-text-detection/corpus/*.jsonl (labelled text kept only on this machine) and, with
``--with-local``, the user's own labelled cases (features only, see ledger.py). That is how
the skill keeps improving on the user's real documents.

Web detectors are not calibrated here (free limits and terms of use rule out running a
corpus through them); their weight comes from independent studies and, over time, from the
ledger's record of how they did on the user's cases.

Method:
* Split human and AI windows by source document (never by window) into a fit half and a
  held-out half, deterministically.
* Style score: a logistic regression on the stylometric features (fit half, human vs AI),
  each weight constrained to its published direction; thresholds at the 99th and 95th
  percentile of the human fit windows.
* Everything is then measured on the held-out half: false-positive rate overall, by text
  kind and for authors in non-English-speaking countries; detection rate on AI text, by
  generator; flag rate on AI-polished text; AUROC.

Writes references/calibration.json and references/validation.md.

Usage:
    python calibrate.py [--with-local] [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import math
import statistics
import sys
from datetime import date

from _common import LOCAL, REFS, read_jsonl, write_json
from stylometry import DIRECTION, FEATURES, MODEL_FEATURES, features

CAL = REFS / "calibration"


def half(doc_id: str) -> str:
    """'fit' or 'test', stable for a document id."""
    return (
        "fit" if int(hashlib.sha1(doc_id.encode()).hexdigest(), 16) % 2 == 0 else "test"
    )


def quantile(vals: list[float], q: float) -> float:
    """Linear-interpolated quantile, q in [0, 1]."""
    s = sorted(vals)
    if not s:
        return float("nan")
    pos = q * (len(s) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def auroc(pos: list[float], neg: list[float]) -> float | None:
    """Probability that a positive scores above a negative (ties count half)."""
    if not pos or not neg:
        return None
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rank_sum, i = 0.0, 0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        avg = (i + j + 1) / 2
        rank_sum += avg * sum(1 for k in range(i, j) if allv[k][1] == 1)
        i = j
    return (rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def fit_logistic(
    X: list[list[float]],
    y: list[int],
    l2: float = 1.0,
    iters: int = 3000,
    lr: float = 0.1,
    signs: list[int] | None = None,
) -> tuple[list[float], float]:
    """Gradient-descent logistic regression (features already standardised).

    ``signs`` constrains each weight to the published direction of its feature (+1: higher
    means more AI-like, -1: lower). A feature whose data disagree gets weight 0 rather than
    a flipped sign, so the score keeps meaning "more AI-typical", not "more like the
    particular generators in the corpus".
    """
    n, d = len(X), len(X[0])
    w, b = [0.0] * d, 0.0
    pos = sum(y)
    cw = {1: n / (2 * pos), 0: n / (2 * (n - pos))}  # balance the classes
    for _ in range(iters):
        gw, gb = [0.0] * d, 0.0
        for xi, yi in zip(X, y):
            z = b + sum(wj * xj for wj, xj in zip(w, xi))
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            g = (p - yi) * cw[yi]
            gb += g
            for j in range(d):
                gw[j] += g * xi[j]
        b -= lr * gb / n
        w = [wj - lr * (gj / n + l2 * wj / n) for wj, gj in zip(w, gw)]
        if signs:
            w = [max(0.0, wj * sj) * sj for wj, sj in zip(w, signs)]
    return w, b


def clean(v: float | None) -> float | None:
    """None for missing or NaN."""
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def pct(x: float | None) -> str:
    """Format a rate as a percentage."""
    return "n/a" if x is None else f"{100 * x:.1f}%"


def main(argv: list[str] | None = None) -> int:
    """Calibrate and validate."""
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=__import__("argparse").RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--with-local", action="store_true", help="add the user's labelled cases"
    )
    p.add_argument("--dry-run", action="store_true", help="print, don't write")
    args = p.parse_args(argv)

    human = read_jsonl(CAL / "human.jsonl")
    ai = read_jsonl(CAL / "ai.jsonl")
    polished = read_jsonl(CAL / "polished.jsonl")
    local = read_jsonl(LOCAL / "cases.jsonl") if args.with_local else []
    # Extra labelled text kept only on this machine (e.g. datasets whose licence does not
    # allow redistribution): ~/.ai-text-detection/corpus/*.jsonl, each row with "label".
    extra = [
        r for f in sorted((LOCAL / "corpus").glob("*.jsonl")) for r in read_jsonl(f)
    ]
    ai += [r for r in extra if r.get("label") == 1]
    human += [r for r in extra if r.get("label") == 0]
    if not human or not ai:
        print(
            "ERROR: need references/calibration/human*.jsonl and ai*.jsonl",
            file=sys.stderr,
        )
        return 1
    for r in human:
        r["label"] = 0
    for r in ai:
        r["label"] = 1
    for r in local:
        # Ledger rows carry stylometric features, never text.
        r["doc_id"] = f"local-{r['case']}"
        r["kind"] = r.get("kind") or "local"
    rows = human + ai + polished
    for r in rows:
        if "text" in r and "excess_rate" not in r:
            r.update(
                {k: v for k, v in features(r["text"]).items() if not k.startswith("_")}
            )
    rows_all = rows + [r for r in local if r.get("label") in (0, 1)]
    for r in rows_all:
        r["half"] = half(r["doc_id"])
    labelled = [r for r in rows_all if r.get("label") in (0, 1)]
    H = [r for r in labelled if r["label"] == 0]
    A = [r for r in labelled if r["label"] == 1]
    Hfit, Htest = (
        [r for r in H if r["half"] == "fit"],
        [r for r in H if r["half"] == "test"],
    )
    Afit, Atest = (
        [r for r in A if r["half"] == "fit"],
        [r for r in A if r["half"] == "test"],
    )

    cal: dict = {
        "version": date.today().isoformat(),
        "stylometry": {},
        "corpus": {},
    }
    val: dict = {"style": {}}

    # Stylometry: human quantiles and a logistic style score.
    cal["stylometry"]["human_quantiles"] = {
        k: [
            quantile([r[k] for r in Hfit if clean(r.get(k)) is not None], i / 100)
            for i in range(1, 100)
        ]
        for k in FEATURES
    }
    fit_rows = [r for r in Hfit + Afit]
    mean = [
        statistics.mean([r[k] for r in fit_rows if clean(r.get(k)) is not None])
        for k in MODEL_FEATURES
    ]
    sd = [
        statistics.pstdev([r[k] for r in fit_rows if clean(r.get(k)) is not None]) or 1
        for k in MODEL_FEATURES
    ]

    def z(r: dict) -> list[float]:
        return [
            ((clean(r.get(k)) if clean(r.get(k)) is not None else m) - m) / s
            for k, m, s in zip(MODEL_FEATURES, mean, sd)
        ]

    w, b = fit_logistic(
        [z(r) for r in fit_rows],
        [r["label"] for r in fit_rows],
        signs=[DIRECTION[k] for k in MODEL_FEATURES],
    )
    model = {
        "features": MODEL_FEATURES,
        "weights": w,
        "intercept": b,
        "mean": mean,
        "sd": sd,
    }

    def prob(r: dict) -> float:
        zz = b + sum(wi * xi for wi, xi in zip(w, z(r)))
        return 1 / (1 + math.exp(-zz))

    hs = [prob(r) for r in Hfit]
    sthr = {"1%": quantile(hs, 0.99), "5%": quantile(hs, 0.95)}
    cal["stylometry"].update({"model": model, "thresholds": sthr})
    sv = {}
    for name, subset in (
        ("human (held out)", Htest),
        (
            "human, non-English-speaking country",
            [r for r in Htest if r.get("native_english") is False],
        ),
        *[
            (f"human, {k}", [r for r in Htest if r.get("kind") == k])
            for k in sorted({r.get("kind") for r in Htest})
        ],
        ("AI (held out)", Atest),
        *[
            (f"AI, {g}", [r for r in Atest if r.get("generator") == g])
            for g in sorted({r.get("generator") for r in Atest if r.get("generator")})
        ],
        ("AI-polished human text", polished),
    ):
        ps = [prob(r) for r in subset]
        if ps:
            sv[name] = {
                "n": len(ps),
                "past_1pct": sum(x >= sthr["1%"] for x in ps) / len(ps),
                "past_5pct": sum(x >= sthr["5%"] for x in ps) / len(ps),
            }
    sv["auroc"] = auroc([prob(r) for r in Atest], [prob(r) for r in Htest])
    sv["weights"] = {k: round(x, 3) for k, x in zip(MODEL_FEATURES, w)}
    cal["stylometry"]["auroc"] = sv["auroc"]
    cal["stylometry"]["heldout"] = {
        k: v for k, v in sv.items() if isinstance(v, dict) and "n" in v
    }
    val["style"] = sv
    # Feature-by-feature separation, so the report can say which tells actually help.
    val["features_auroc"] = {
        k: auroc(
            [DIRECTION[k] * r[k] for r in Atest if clean(r.get(k)) is not None],
            [DIRECTION[k] * r[k] for r in Htest if clean(r.get(k)) is not None],
        )
        for k in FEATURES
    }
    cal["corpus"] = {
        "human_windows": len(H),
        "ai_windows": len(A),
        "polished_windows": len(polished),
        "human_docs": len({r["doc_id"] for r in H}),
        "ai_docs": len({r["doc_id"] for r in A}),
        "kinds": sorted({r.get("kind") for r in H if r.get("kind")}),
        "generators": sorted({r.get("generator") for r in A if r.get("generator")}),
        "local_cases": len({r["doc_id"] for r in local}),
        "local_corpus_windows": len(extra),
    }

    md = render_validation(cal, val)
    if args.dry_run:
        print(md)
        return 0
    write_json(REFS / "calibration.json", cal)
    (REFS / "validation.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


def render_validation(cal: dict, val: dict) -> str:
    """validation.md: what the thresholds achieve on held-out text."""
    c = cal["corpus"]
    lines = [
        "# Validation of the ai-text-detection thresholds",
        "",
        f"Generated by `calibrate.py` on {cal['version']}. Do not edit by hand.",
        "",
        (
            f"Corpus: {c['human_windows']} human windows from {c['human_docs']} documents written before ChatGPT "
            f"({', '.join(c['kinds'])}); {c['ai_windows']} AI windows from {c['ai_docs']} documents "
            f"(generators: {', '.join(c['generators']) or 'unspecified'}); {c['polished_windows']} AI-polished human windows; "
            f"{c['local_cases']} of the user's own labelled cases; {c.get('local_corpus_windows', 0)} windows from datasets kept only on this machine. Windows are ~300 words. Thresholds are set on half of "
            "the human documents; every rate below is measured on the other half (and on AI text never used to set them)."
        ),
        "",
        (
            "Read 'past 1%' as: share of windows the style score flags at its 1% false-positive operating point. For human text "
            "that share is the false-positive rate (should be near 1%); for AI text it is the detection rate."
        ),
        "",
    ]
    sv = val["style"]
    lines += [
        "## Style score (stylometry)",
        "",
        (
            f"Logistic regression on {', '.join(MODEL_FEATURES)}, each weight constrained to its published direction (a feature whose data disagree gets 0); weights {sv['weights']}. AUROC on held-out windows: "
            f"{sv.get('auroc') and round(sv['auroc'], 3)}."
        ),
        "",
        "| Text | Windows | Past 1% threshold | Past 5% threshold |",
        "|---|---|---|---|",
    ]
    for name, s in sv.items():
        if name in ("auroc", "weights"):
            continue
        lines.append(
            f"| {name} | {s['n']} | {pct(s['past_1pct'])} | {pct(s['past_5pct'])} |"
        )
    lines += [
        "",
        "AUROC of each stylometric feature alone (0.5 = useless): "
        + ", ".join(
            f"{k} {v:.2f}" for k, v in val["features_auroc"].items() if v is not None
        ),
        "",
        "## Limits",
        "",
        (
            "- The AI side is text from the generators listed above, prompted to write like a scientist. Other models, "
            "careful prompting, and human editing after generation lower detection rates; published evaluations (RAID, "
            "Dugan et al. 2024) show the same."
        ),
        (
            "- The human side is published, edited text from 2015-2021. Unedited drafts, very short texts, and formulaic "
            "sections (methods, boilerplate) can behave differently."
        ),
        (
            "- Every user-labelled case added with `ledger.py` and `--with-local` makes these numbers more representative "
            "of the documents the user actually receives."
        ),
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
