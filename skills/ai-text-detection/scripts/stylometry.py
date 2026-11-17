"""Stylistic measures of the document, compared with human scientific text.

Per window (see lib.text.style_windows) it measures:

    excess_rate     words from the Kobak et al. excess-vocabulary list, per 1,000 words
    marked_rate     the most LLM-typical of those words (delve, underscore, pivotal, ...)
    tells_rate      phrasing patterns from markers.json 'style.tells', per 1,000 words
    em_dash_rate    em dashes per 1,000 words
    sent_cv         coefficient of variation of sentence length ("burstiness"; LLM text
                    tends to be more uniform)
    mattr           moving-average type-token ratio (window 100)

Each value is placed as a percentile of the same measure on human pre-2023 windows from
references/calibration.json, and the logistic "style score" fitted by calibrate.py is
applied. All of this is *weak* evidence on its own: humans write like this too, more and
more since 2023. It is reported as context, and to point at the sections worth reading.

Writes ``<work>/stylometry.json``.

Usage:
    python stylometry.py [--work /tmp/ai_text_detection]
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

from lib.common import REFS, WORK_DIR, read_json, write_json
from lib.stats import missing
from lib.style import FEATURES, features, percentile, phrase_spans, style_score
from lib.text import load_text, style_windows


def measure(doc: dict) -> dict:
    """The contents of stylometry.json: the features of every window, where each sits
    among human text, the style score, and the stock phrases to highlight."""
    cal = (read_json(REFS / "calibration.json") or {}).get("stylometry", {})
    quantiles = cal.get("human_quantiles", {})
    model = cal.get("model")
    thresholds = cal.get("thresholds", {})

    rows = []
    for c in style_windows(doc):
        f = features(c["text"])
        f.update({k: c[k] for k in ("id", "section", "start", "end")})
        f["percentiles"] = {k: percentile(f[k], quantiles.get(k, [])) for k in FEATURES}
        f["style_score"] = style_score(f, model)
        rows.append(f)
    whole = features(doc["text"])
    over = {
        k: sum(
            1 for r in rows if not missing(r["style_score"]) and r["style_score"] >= t
        )
        for k, t in thresholds.items()
    }
    medians = {}
    for k in FEATURES:
        vals = [r["percentiles"][k] for r in rows if r["percentiles"][k] is not None]
        medians[k] = statistics.median(vals) if vals else None
    summary = {
        "n_windows": len(rows),
        "document": {k: whole[k] for k in FEATURES},
        "marked_words": whole["_marked_words"],
        "tells": whole["_tells"],
        "median_percentiles": medians,
        "style_score_median": statistics.median([r["style_score"] for r in rows])
        if rows and model
        else None,
        "windows_over": {
            k: {"count": v, "fraction": v / len(rows) if rows else 0, "fpr": k}
            for k, v in over.items()
        },
        "calibrated": bool(model),
    }
    return {"summary": summary, "windows": rows, "spans": phrase_spans(doc["text"])}


def main(argv: list[str] | None = None) -> int:
    """Measure the document and write stylometry.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    work = Path(p.parse_args(argv).work)
    out = measure(load_text(work))
    write_json(work / "stylometry.json", out)
    summary, n = out["summary"], out["summary"]["n_windows"]
    d = summary["document"]
    print(
        f"stylometry: {n} window(s); excess {d['excess_rate']:.1f}/1k, marked {d['marked_rate']:.1f}/1k, "
        f"tells {d['tells_rate']:.1f}/1k, em-dash {d['em_dash_rate']:.1f}/1k, sentence CV {d['sent_cv']:.2f}"
    )
    if summary["marked_words"]:
        print("  marked words: " + ", ".join(summary["marked_words"][:25]))
    if summary["calibrated"]:
        print(
            f"  style score median {summary['style_score_median']:.2f}; windows over threshold: "
            + ", ".join(
                f"{k} FPR {v['count']}/{n}" for k, v in summary["windows_over"].items()
            )
        )
    else:
        print(
            "  not calibrated yet: run calibrate.py for percentiles and a style score"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
