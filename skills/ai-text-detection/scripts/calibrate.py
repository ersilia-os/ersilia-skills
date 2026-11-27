"""Fit the style-score thresholds on human text, measure how well they work, write them down.

A score means something only next to the rate at which human text gets the same score.
Inputs (references/calibration/): human.jsonl (pre-ChatGPT human windows, build_corpus.py),
ai.jsonl (AI-written windows on the same topics, several generators) and polished.jsonl
(human windows rewritten by an AI "to improve the English", reported separately). Also read:
~/.ai-text-detection/corpus/*.jsonl (labelled text kept only on this machine) and, with
``--with-local``, the user's own labelled cases (features only, see ledger.py). That is how
the skill keeps improving on the user's real documents.

Web detectors are not calibrated here: web_controls.py tests them on known texts.

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

from lib.common import LOCAL, REFS, die, read_jsonl, today, write_json
from lib.stats import auroc, missing, quantile
from lib.style import DIRECTION, FEATURES, MODEL_FEATURES, features

CAL = REFS / "calibration"


def half(doc_id: str) -> str:
    """'fit' or 'test', stable for a document id."""
    return (
        "fit" if int(hashlib.sha1(doc_id.encode()).hexdigest(), 16) % 2 == 0 else "test"
    )


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


def pct(x: float | None) -> str:
    """Format a rate as a percentage."""
    return "n/a" if x is None else f"{100 * x:.1f}%"


def present(rows: list[dict], key: str) -> list[float]:
    """The values of one feature over the rows that have it."""
    return [r[key] for r in rows if not missing(r.get(key))]


def load_corpus(with_local: bool) -> dict[str, list[dict]]:
    """The labelled windows, each with its style features and its half (fit or test).

    ``human`` and ``ai`` include the datasets kept only on this machine
    (~/.ai-text-detection/corpus/*.jsonl, each row with "label"; e.g. datasets whose
    licence does not allow redistribution) and, with ``with_local``, the user's own
    labelled cases from the ledger, which carry features and never text.
    """
    human = read_jsonl(CAL / "human.jsonl")
    ai = read_jsonl(CAL / "ai.jsonl")
    polished = read_jsonl(CAL / "polished.jsonl")
    local = read_jsonl(LOCAL / "cases.jsonl") if with_local else []
    extra = [
        r for f in sorted((LOCAL / "corpus").glob("*.jsonl")) for r in read_jsonl(f)
    ]
    ai += [r for r in extra if r.get("label") == 1]
    human += [r for r in extra if r.get("label") == 0]
    for r in human:
        r["label"] = 0
    for r in ai:
        r["label"] = 1
    for r in local:
        r["doc_id"] = f"local-{r['case']}"
        r["kind"] = r.get("kind") or "local"
    for r in human + ai + polished:
        if "text" in r and "excess_rate" not in r:
            r.update(
                {k: v for k, v in features(r["text"]).items() if not k.startswith("_")}
            )
    labelled_local = [r for r in local if r.get("label") in (0, 1)]
    for r in human + ai + polished + labelled_local:
        r["half"] = half(r["doc_id"])
    return {
        "human": human + [r for r in labelled_local if r["label"] == 0],
        "ai": ai + [r for r in labelled_local if r["label"] == 1],
        "polished": polished,
        "local": local,
        "extra": extra,
    }


def fit_style(h_fit: list[dict], a_fit: list[dict]) -> dict:
    """The style model: a logistic regression on standardised features, human vs AI,
    each weight constrained to its published direction."""
    fit_rows = h_fit + a_fit
    mean = [statistics.mean(present(fit_rows, k)) for k in MODEL_FEATURES]
    sd = [statistics.pstdev(present(fit_rows, k)) or 1 for k in MODEL_FEATURES]
    model = {"features": MODEL_FEATURES, "mean": mean, "sd": sd}
    w, b = fit_logistic(
        [standardise(r, model) for r in fit_rows],
        [r["label"] for r in fit_rows],
        signs=[DIRECTION[k] for k in MODEL_FEATURES],
    )
    return {
        "features": MODEL_FEATURES,
        "weights": w,
        "intercept": b,
        "mean": mean,
        "sd": sd,
    }


def standardise(r: dict, model: dict) -> list[float]:
    """A row's model features as z-scores; a missing feature counts as the mean."""
    return [
        ((m if missing(r.get(k)) else r[k]) - m) / s
        for k, m, s in zip(model["features"], model["mean"], model["sd"])
    ]


def score(r: dict, model: dict) -> float:
    """The style score of a row under the model."""
    z = model["intercept"] + sum(
        wi * xi for wi, xi in zip(model["weights"], standardise(r, model))
    )
    return 1 / (1 + math.exp(-z))


def heldout_rates(
    model: dict, thresholds: dict, h_test: list, a_test: list, polished: list
) -> dict:
    """Share of held-out windows past each threshold: overall, by kind, by generator."""
    subsets = [
        ("human (held out)", h_test),
        (
            "human, non-English-speaking country",
            [r for r in h_test if r.get("native_english") is False],
        ),
        *[
            (f"human, {k}", [r for r in h_test if r.get("kind") == k])
            for k in sorted({r.get("kind") for r in h_test})
        ],
        ("AI (held out)", a_test),
        *[
            (f"AI, {g}", [r for r in a_test if r.get("generator") == g])
            for g in sorted({r.get("generator") for r in a_test if r.get("generator")})
        ],
        ("AI-polished human text", polished),
    ]
    out = {}
    for name, subset in subsets:
        ps = [score(r, model) for r in subset]
        if ps:
            out[name] = {
                "n": len(ps),
                "past_1pct": sum(x >= thresholds["1%"] for x in ps) / len(ps),
                "past_5pct": sum(x >= thresholds["5%"] for x in ps) / len(ps),
            }
    return out


def calibrate(corpus: dict[str, list[dict]]) -> tuple[dict, dict]:
    """(calibration.json contents, the validation figures for validation.md)."""
    human, ai, polished = corpus["human"], corpus["ai"], corpus["polished"]
    h_fit = [r for r in human if r["half"] == "fit"]
    h_test = [r for r in human if r["half"] == "test"]
    a_fit = [r for r in ai if r["half"] == "fit"]
    a_test = [r for r in ai if r["half"] == "test"]

    model = fit_style(h_fit, a_fit)
    human_scores = [score(r, model) for r in h_fit]
    thresholds = {
        "1%": quantile(human_scores, 0.99),
        "5%": quantile(human_scores, 0.95),
    }
    heldout = heldout_rates(model, thresholds, h_test, a_test, polished)
    area = auroc([score(r, model) for r in a_test], [score(r, model) for r in h_test])
    cal = {
        "version": today(),
        "stylometry": {
            "human_quantiles": {
                k: [quantile(present(h_fit, k), i / 100) for i in range(1, 100)]
                for k in FEATURES
            },
            "model": model,
            "thresholds": thresholds,
            "auroc": area,
            "heldout": heldout,
        },
        "corpus": {
            "human_windows": len(human),
            "ai_windows": len(ai),
            "polished_windows": len(polished),
            "human_docs": len({r["doc_id"] for r in human}),
            "ai_docs": len({r["doc_id"] for r in ai}),
            "kinds": sorted({r.get("kind") for r in human if r.get("kind")}),
            "generators": sorted(
                {r.get("generator") for r in ai if r.get("generator")}
            ),
            "local_cases": len({r["doc_id"] for r in corpus["local"]}),
            "local_corpus_windows": len(corpus["extra"]),
        },
    }
    val = {
        "style": {
            **heldout,
            "auroc": area,
            "weights": {
                k: round(x, 3) for k, x in zip(MODEL_FEATURES, model["weights"])
            },
        },
        # Feature-by-feature separation, so the report can say which tells actually help.
        "features_auroc": {
            k: auroc(
                [DIRECTION[k] * x for x in present(a_test, k)],
                [DIRECTION[k] * x for x in present(h_test, k)],
            )
            for k in FEATURES
        },
    }
    return cal, val


def main(argv: list[str] | None = None) -> int:
    """Calibrate and validate."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--with-local", action="store_true", help="add the user's labelled cases"
    )
    p.add_argument("--dry-run", action="store_true", help="print, don't write")
    args = p.parse_args(argv)
    corpus = load_corpus(args.with_local)
    if not corpus["human"] or not corpus["ai"]:
        die("need references/calibration/human.jsonl and ai.jsonl")
    cal, val = calibrate(corpus)
    md = render_validation(cal, val)
    if not args.dry_run:
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
