"""Learn what each web detector is worth: run it on texts whose origin is known.

A detector's "100% AI" means nothing until we know how often it says that about human
scientific prose. This script builds a control set from the calibration corpus and turns
the detectors' answers into measured rates, stored in references/web_calibration.json
(about the tools only; no user text). grade.py and the report weight each tool by it.

The control texts are public (CC BY / public domain human windows from 2015-2021) or were
written for this repository (AI windows), so sending them to a website exposes nothing.

    build      write <dir>/controls.json: human, AI-written and AI-polished windows, chosen
               deterministically (mix of kinds, of native and non-native English, of
               generators), 250-450 words each
    analyze    read <dir>/controls.results.jsonl (from browser_detect.py / api_detectors.py
               --plan) and write per-tool rates to references/web_calibration.json

Usage:
    python web_controls.py build [--dir /tmp/ai_text_detection_controls] [--n 8]
    conda run -n ai-text-detection python browser_detect.py --plan /tmp/ai_text_detection_controls/controls.json --tools zerogpt
    python api_detectors.py --plan /tmp/ai_text_detection_controls/controls.json --tools binoculars
    python web_controls.py analyze
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

from _common import REFS, read_json, read_jsonl, write_json

CAL = REFS / "calibration"
OUT = REFS / "web_calibration.json"


def pick(rows: list[dict], n: int, key) -> list[dict]:
    """n rows spread over the groups given by key, in a stable pseudo-random order."""
    rows = sorted(rows, key=lambda r: hashlib.sha1(r["id"].encode()).hexdigest())
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(str(key(r)), []).append(r)
    out, i = [], 0
    while len(out) < n and any(groups.values()):
        g = sorted(groups)[i % len(groups)]
        if groups[g]:
            out.append(groups[g].pop(0))
        i += 1
    return out


def build(d: Path, n: int) -> dict:
    """Write the control plan."""
    from _common import words

    human = [
        r
        for r in read_jsonl(CAL / "human.jsonl")
        if 250 <= len(words(r["text"])) <= 450
    ]
    ai = [
        r for r in read_jsonl(CAL / "ai.jsonl") if 150 <= len(words(r["text"])) <= 450
    ]
    pol = [
        r
        for r in read_jsonl(CAL / "polished.jsonl")
        if 200 <= len(words(r["text"])) <= 450
    ]
    chosen = (
        [
            ("human", r)
            for r in pick(human, n, lambda r: (r.get("kind"), r.get("native_english")))
        ]
        + [("ai", r) for r in pick(ai, n, lambda r: r.get("generator"))]
        + [("polished", r) for r in pick(pol, max(2, n // 3), lambda r: r.get("kind"))]
    )
    d.mkdir(parents=True, exist_ok=True)
    units = []
    for i, (label, r) in enumerate(chosen, 1):
        cid = f"{label[0]}{i:02d}"
        f = d / f"{cid}.txt"
        f.write_text(r["text"], encoding="utf-8")
        units.append(
            {
                "chunk": cid,
                "file": str(f),
                "label": label,
                "source_id": r["id"],
                "kind": r.get("kind"),
                "generator": r.get("generator"),
                "native_english": r.get("native_english"),
                "n_words": len(words(r["text"])),
            }
        )
    plan = {"built": date.today().isoformat(), "units": units}
    write_json(d / "controls.json", plan)
    return plan


def shuffle(d: Path) -> dict:
    """Sentence-shuffled copies of the human controls (a memorisation check).

    The human controls are published papers that detectors were probably trained on, so a
    detector could recognise them instead of judging their style. Shuffling the sentence
    order keeps the vocabulary and style but breaks any memorised sequence. If a tool also
    calls the shuffled texts human, its low false-positive rate is not just memory.
    """
    import random

    from _common import sentences

    plan = read_json(d / "controls.json")
    units = []
    for u in plan["units"]:
        if u["label"] != "human":
            continue
        sents = sentences(Path(u["file"]).read_text(encoding="utf-8"))
        rng = random.Random(u["chunk"])
        order = list(range(len(sents)))
        while order == sorted(order) and len(order) > 1:
            rng.shuffle(order)
        cid = "s" + u["chunk"][1:]
        f = d / f"{cid}.txt"
        f.write_text(" ".join(sents[i] for i in order), encoding="utf-8")
        units.append({**u, "chunk": cid, "file": str(f), "label": "human_shuffled"})
    out = {"built": date.today().isoformat(), "units": units}
    write_json(d / "shuffled.json", out)
    return out


def auroc(pos: list[float], neg: list[float]) -> float | None:
    """P(random AI text scores above random human text); ties count half."""
    if not pos or not neg:
        return None
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def analyze(d: Path) -> dict:
    """Per-tool rates on the controls, merged into references/web_calibration.json."""
    plan = read_json(d / "controls.json")
    label_of = {u["chunk"]: u["label"] for u in plan["units"]}
    label_of.update(
        {
            u["chunk"]: u["label"]
            for u in (read_json(d / "shuffled.json") or {"units": []})["units"]
        }
    )
    res = [
        r
        for r in read_jsonl(d / "controls.results.jsonl")
        + read_jsonl(d / "shuffled.results.jsonl")
        if r.get("score") is not None
    ]
    latest: dict[tuple[str, str], float] = {}
    for r in res:
        latest[(r["tool"], str(r["chunk"]))] = float(r["score"])
    cal = read_json(OUT) or {"_about": "", "tools": {}}
    cal["_about"] = (
        "Measured on known texts by web_controls.py: human = published scientific prose from 2015-2021 "
        "(CC BY / public domain), ai = written by Claude or GPT models, polished = human text rewritten by an AI. "
        "fpr = share of human texts scored >= 0.5; tpr = share of AI texts scored >= 0.5. Small samples: "
        "the intervals in 'n' matter. Re-run monthly (watch.py) and after any site change."
    )
    for tool in sorted({t for t, _ in latest}):
        h = [
            v
            for (t, c), v in latest.items()
            if t == tool and label_of.get(c) == "human"
        ]
        a = [v for (t, c), v in latest.items() if t == tool and label_of.get(c) == "ai"]
        p = [
            v
            for (t, c), v in latest.items()
            if t == tool and label_of.get(c) == "polished"
        ]
        hs = [
            v
            for (t, c), v in latest.items()
            if t == tool and label_of.get(c) == "human_shuffled"
        ]
        fp, tp = sum(v >= 0.5 for v in h), sum(v >= 0.5 for v in a)
        cal["tools"][tool] = {
            "date": date.today().isoformat(),
            "n_human": len(h),
            "n_ai": len(a),
            "n_polished": len(p),
            "fpr": round(fp / len(h), 3) if h else None,
            "tpr": round(tp / len(a), 3) if a else None,
            "polished_flagged": round(sum(v >= 0.5 for v in p) / len(p), 3)
            if p
            else None,
            "auroc": round(auroc(a, h), 3) if a and h else None,
            # Likelihood ratios with add-one smoothing, so a small sample never gives infinity.
            "lr_flag": round(((tp + 1) / (len(a) + 2)) / ((fp + 1) / (len(h) + 2)), 2)
            if a and h
            else None,
            "lr_clear": round(
                ((len(a) - tp + 1) / (len(a) + 2)) / ((len(h) - fp + 1) / (len(h) + 2)),
                2,
            )
            if a and h
            else None,
            "mean_human": round(sum(h) / len(h), 3) if h else None,
            "mean_ai": round(sum(a) / len(a), 3) if a else None,
            "n_shuffled": len(hs),
            "fpr_shuffled": round(sum(v >= 0.5 for v in hs) / len(hs), 3)
            if hs
            else None,
        }
    write_json(OUT, cal)
    return cal


def main(argv: list[str] | None = None) -> int:
    """Dispatch."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("cmd", choices=["build", "shuffle", "analyze"])
    p.add_argument("--dir", default="/tmp/ai_text_detection_controls")
    p.add_argument("--n", type=int, default=8)
    args = p.parse_args(argv)
    d = Path(args.dir)
    if args.cmd == "shuffle":
        out = shuffle(d)
        print(
            f"{len(out['units'])} sentence-shuffled human controls -> {d / 'shuffled.json'}"
        )
        return 0
    if args.cmd == "build":
        plan = build(d, args.n)
        for u in plan["units"]:
            print(
                f"{u['chunk']}: {u['label']:<8} {u['n_words']:>4} words  {u.get('kind') or ''} {u.get('generator') or ''} "
                f"{'non-native' if u.get('native_english') is False else ''}"
            )
        return 0
    cal = analyze(d)
    print(
        f"{'tool':<18} {'FPR (human)':>12} {'TPR (AI)':>9} {'polished':>9} {'AUROC':>6} {'LR flag':>8} {'LR clear':>9} {'FPR shuffled':>13}"
    )
    for t, v in cal["tools"].items():
        print(
            f"{t:<18} {v['fpr']!s:>6} of {v['n_human']:<3} {v['tpr']!s:>5}/{v['n_ai']:<3} {v['polished_flagged']!s:>9} "
            f"{v['auroc']!s:>6} {v['lr_flag']!s:>8} {v['lr_clear']!s:>9} {v.get('fpr_shuffled')!s:>6} of {v.get('n_shuffled', 0)}"
        )
    _ = json
    return 0


if __name__ == "__main__":
    sys.exit(main())
