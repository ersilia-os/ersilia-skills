"""Stylistic measures of the document, compared with human scientific text.

Per window (see _common.chunks) it measures:

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
import csv
import math
import re
import statistics
import sys
from pathlib import Path

from _common import (
    REFS,
    WORK_DIR,
    chunks,
    load_text,
    read_json,
    sentences,
    words,
    write_json,
)

FEATURES = [
    "excess_rate",
    "marked_rate",
    "tells_rate",
    "em_dash_rate",
    "sent_cv",
    "mattr",
]
# Features in the style score. MATTR (lexical diversity) is reported but left out: its
# direction differs between model generations (older GPT text is less varied, recent
# models are often more varied than human scientific prose).
MODEL_FEATURES = ["excess_rate", "marked_rate", "tells_rate", "em_dash_rate", "sent_cv"]
# Direction in which a feature points towards LLM text (+1 higher, -1 lower).
DIRECTION = {
    "excess_rate": 1,
    "marked_rate": 1,
    "tells_rate": 1,
    "em_dash_rate": 1,
    "sent_cv": -1,
    "mattr": -1,
}


def load_lexicons() -> tuple[set[str], set[str], dict[str, re.Pattern]]:
    """(counted excess words, marked words, compiled tell groups)."""
    counted, marked = set(), set()
    with (REFS / "excess_words.csv").open(encoding="utf-8") as f:
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        for r in rows:
            if r["counted"] == "1":
                counted.add(r["word"])
            if r["marked"] == "1":
                marked.add(r["word"])
    groups = read_json(REFS / "markers.json")["style"]["tells"]["groups"]
    return counted, marked, {k: re.compile(v, re.IGNORECASE) for k, v in groups.items()}


LEX = None


def features(text: str) -> dict:
    """The stylometric features of one window of text."""
    global LEX
    if LEX is None:
        LEX = load_lexicons()
    counted, marked, tells = LEX
    ws = words(text)
    n = max(len(ws), 1)
    per_k = 1000 / n
    sl = [len(words(s)) for s in sentences(text)]
    cv = statistics.pstdev(sl) / statistics.mean(sl) if len(sl) >= 3 else float("nan")
    win = 100
    if len(ws) >= win:
        ttrs = [
            len(set(ws[i : i + win])) / win for i in range(0, len(ws) - win + 1, 10)
        ]
        mattr = sum(ttrs) / len(ttrs)
    else:
        mattr = len(set(ws)) / n
    tell_hits = {k: len(p.findall(text)) for k, p in tells.items()}
    return {
        "n_words": len(ws),
        "excess_rate": sum(w in counted for w in ws) * per_k,
        "marked_rate": sum(w in marked for w in ws) * per_k,
        "tells_rate": sum(tell_hits.values()) * per_k,
        "em_dash_rate": text.count("—") * per_k,
        "sent_cv": cv,
        "mattr": mattr,
        "_marked_words": sorted({w for w in ws if w in marked}),
        "_tells": {k: v for k, v in tell_hits.items() if v},
    }


def phrase_spans(text: str) -> list[dict]:
    """Character spans of marked AI words and stock phrasing, for highlighting."""
    global LEX
    if LEX is None:
        LEX = load_lexicons()
    _, marked, tells = LEX
    spans = []
    if marked:
        rx = re.compile(
            r"\b(?:"
            + "|".join(re.escape(w) for w in sorted(marked, key=len, reverse=True))
            + r")\b",
            re.IGNORECASE,
        )
        spans += [
            {
                "start": m.start(),
                "end": m.end(),
                "kind": "word",
                "label": f"AI-typical word: {m.group(0).lower()}",
            }
            for m in rx.finditer(text)
            # A capitalised word mid-sentence is a name ("Holistic Drug Discovery Centre").
            if not (
                m.group(0)[0].isupper()
                and not re.search(
                    r"(^|[.!?:]\s+|\n\s*)$", text[max(0, m.start() - 3) : m.start()]
                )
            )
        ]
    for name, rx in tells.items():
        spans += [
            {
                "start": m.start(),
                "end": m.end(),
                "kind": "phrase",
                "label": f"stock phrasing: {name}",
            }
            for m in rx.finditer(text)
        ]
    return spans


def percentile(value: float, quantiles: list[float]) -> float | None:
    """Percentile of ``value`` given human quantiles at 1, 2, ..., 99 %."""
    if (
        value is None
        or (isinstance(value, float) and math.isnan(value))
        or not quantiles
    ):
        return None
    if value <= quantiles[0]:
        return 1.0
    if value >= quantiles[-1]:
        return 99.0
    for i in range(1, len(quantiles)):
        if value <= quantiles[i]:
            lo, hi = quantiles[i - 1], quantiles[i]
            frac = 0 if hi == lo else (value - lo) / (hi - lo)
            return i + frac
    return 99.0


def style_score(f: dict, model: dict | None) -> float | None:
    """Probability-like score from the logistic model fitted by calibrate.py."""
    if not model:
        return None
    z = model["intercept"]
    for name, w, mu, sd in zip(
        model["features"], model["weights"], model["mean"], model["sd"]
    ):
        v = f.get(name)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            v = mu
        z += w * (v - mu) / (sd or 1)
    return 1 / (1 + math.exp(-z))


def main(argv: list[str] | None = None) -> int:
    """Measure the document and write stylometry.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    args = p.parse_args(argv)
    work = Path(args.work)
    doc = load_text(work)
    cal = (read_json(REFS / "calibration.json") or {}).get("stylometry", {})
    q = cal.get("human_quantiles", {})
    model = cal.get("model")
    thr = cal.get("thresholds", {})

    rows = []
    for c in chunks(doc):
        f = features(c["text"])
        f.update(
            {
                "id": c["id"],
                "section": c["section"],
                "start": c["start"],
                "end": c["end"],
            }
        )
        f["percentiles"] = {k: percentile(f[k], q.get(k, [])) for k in FEATURES}
        f["style_score"] = style_score(f, model)
        rows.append(f)
    whole = features(doc["text"])
    spans = phrase_spans(doc["text"])
    over = {
        k: sum(
            1
            for r in rows
            if r["style_score"] is not None and r["style_score"] >= thr[k]
        )
        for k in thr
    }
    summary = {
        "n_windows": len(rows),
        "document": {k: whole[k] for k in FEATURES},
        "marked_words": whole["_marked_words"],
        "tells": whole["_tells"],
        "median_percentiles": {
            k: statistics.median(
                [r["percentiles"][k] for r in rows if r["percentiles"][k] is not None]
            )
            if any(r["percentiles"][k] is not None for r in rows)
            else None
            for k in FEATURES
        },
        "style_score_median": statistics.median([r["style_score"] for r in rows])
        if rows and model
        else None,
        "windows_over": {
            k: {"count": v, "fraction": v / len(rows) if rows else 0, "fpr": k}
            for k, v in over.items()
        },
        "calibrated": bool(model),
    }
    write_json(
        work / "stylometry.json", {"summary": summary, "windows": rows, "spans": spans}
    )
    d = summary["document"]
    print(
        f"stylometry: {len(rows)} window(s); excess {d['excess_rate']:.1f}/1k, marked {d['marked_rate']:.1f}/1k, "
        f"tells {d['tells_rate']:.1f}/1k, em-dash {d['em_dash_rate']:.1f}/1k, sentence CV {d['sent_cv']:.2f}"
    )
    if summary["marked_words"]:
        print("  marked words: " + ", ".join(summary["marked_words"][:25]))
    if model:
        print(
            f"  style score median {summary['style_score_median']:.2f}; windows over threshold: "
            + ", ".join(
                f"{k} FPR {v['count']}/{len(rows)}"
                for k, v in summary["windows_over"].items()
            )
        )
    else:
        print(
            "  not calibrated yet: run calibrate.py for percentiles and a style score"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
