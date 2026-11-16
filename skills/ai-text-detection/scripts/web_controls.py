"""Learn what each web detector is worth: run it on texts whose origin is known.

A detector's "100% AI" means nothing until we know how often it says that about human
scientific prose. This script builds control sets, then turns the detectors' answers on
them into measured rates in references/web_calibration.json (about the tools only; no user
text), which evidence.py and the report use to weight each tool.

The control texts are public (CC BY human writing from 2015-2021) or were written for this
repository (AI and AI-polished windows), so sending them to a website exposes nothing.

    build      <dir>/controls.json: human, AI-written and AI-polished windows, chosen
               deterministically across kinds, native and non-native English, generators
    shuffle    <dir>/shuffled.json: the human controls with their sentences in random
               order. Detectors may have been trained on published papers; shuffling
               defeats memorisation and keeps the style
    domain     <dir>/domain.json: human texts from the document's own field (Europe PMC
               query), because formulaic technical prose is where false alarms happen
    analyze    read the *.results.jsonl next to those plans and write, per tool: false
               alarms (overall, same field, shuffled), detection rate, AI-polished rate,
               AUROC and likelihood ratios (add-one smoothed)

Usage:
    python web_controls.py build [--dir /tmp/ai_text_detection_controls]
    python web_controls.py shuffle
    python web_controls.py domain --query "PBPK linezolid" --query "population pharmacokinetics"
    conda run -n ai-text-detection python browser_detect.py --plan /tmp/ai_text_detection_controls/controls.json --tools zerogpt
    python web_controls.py analyze
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

from _common import REFS, read_json, read_jsonl, write_json

CAL = REFS / "calibration"
OUT = REFS / "web_calibration.json"
READABLE = REFS / "web_validation.md"
MIN_N = 5  # as in evidence.py: fewer known texts than this, and a tool is not counted


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


def domain(d: Path, queries: list[str], n: int) -> dict:
    """Human controls matched to the document's field (open-access CC BY, 2015-2021).

    A detector may treat formulaic technical prose (models, doses, statistics) as machine-
    like. These controls test that on the document's own kind of text. Each query is a
    Europe PMC query; one Introduction or Discussion window per matching paper is used.
    """
    import random

    from build_corpus import fulltext_windows, search

    units, seen = [], set()
    for q in queries:
        full = f'({q}) AND OPEN_ACCESS:y AND LICENSE:"cc by" AND PUB_YEAR:[2015 TO 2021] AND HAS_FT:y'
        res = [r for r in search(full, 1) if r.get("pmcid") and r["pmcid"] not in seen]
        random.Random(q).shuffle(res)
        for r in res:
            if sum(1 for u in units if u["query"] == q) >= n:
                break
            seen.add(r["pmcid"])
            wins = [
                w for w in fulltext_windows(r, "article") if 250 <= w["n_words"] <= 450
            ]
            if not wins:
                continue
            w = wins[0]
            cid = f"d{len(units) + 1:02d}"
            f = d / f"{cid}.txt"
            f.write_text(w["text"], encoding="utf-8")
            units.append(
                {
                    "chunk": cid,
                    "file": str(f),
                    "label": "human_domain",
                    "source_id": w["id"],
                    "kind": "article",
                    "native_english": w.get("native_english"),
                    "country": w.get("country"),
                    "year": w.get("year"),
                    "source_url": w.get("source_url"),
                    "query": q,
                    "n_words": w["n_words"],
                }
            )
    out = {"built": date.today().isoformat(), "queries": queries, "units": units}
    write_json(d / "domain.json", out)
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
            for extra in ("shuffled", "domain")
            for u in (read_json(d / f"{extra}.json") or {"units": []})["units"]
        }
    )
    res = [
        r
        for r in read_jsonl(d / "controls.results.jsonl")
        + read_jsonl(d / "shuffled.results.jsonl")
        + read_jsonl(d / "domain.results.jsonl")
        if r.get("score") is not None
    ]
    latest: dict[tuple[str, str], float] = {}
    for r in res:
        latest[(r["tool"], str(r["chunk"]))] = float(r["score"])
    cal = read_json(OUT) or {"_about": "", "tools": {}}
    cal["_about"] = (
        "Measured on known texts by web_controls.py: human = published scientific prose from 2015-2021 "
        "(CC BY / public domain), ai = written by Claude or GPT models, polished = human text rewritten by an AI. "
        "human_domain = human prose from the document's own field. fpr, lr_* and auroc pool all human texts (general and "
        "domain); fpr_generic and fpr_domain show them apart. fpr = share of human texts scored >= 0.5; tpr = share of "
        "AI texts scored >= 0.5. Small samples: "
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
        hd = [
            v
            for (t, c), v in latest.items()
            if t == tool and label_of.get(c) == "human_domain"
        ]
        fpr_generic = round(sum(v >= 0.5 for v in h) / len(h), 3) if h else None
        h = h + hd  # rates and likelihood ratios use every independent human text
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
            "fpr_generic": fpr_generic,
            "n_domain": len(hd),
            "fpr_domain": round(sum(v >= 0.5 for v in hd) / len(hd), 3) if hd else None,
            "domain_scores": sorted(round(v, 2) for v in hd),
        }
    write_json(OUT, cal)
    write_readable(cal)
    return cal


def write_readable(cal: dict) -> None:
    """references/web_validation.md: the same rates as a table people can read."""

    def pc(x: float | None) -> str:
        return "—" if x is None else f"{round(100 * x)}%"

    def count(rate: float | None, n: int | None) -> str:
        return "—" if rate is None or not n else f"{round(rate * n)}/{n}"

    rows, thin = [], []
    for tool, c in sorted(
        cal["tools"].items(), key=lambda kv: -(kv[1].get("auroc") or 0)
    ):
        if (c.get("n_human") or 0) < MIN_N or (c.get("n_ai") or 0) < MIN_N:
            thin.append(f"{tool} ({c.get('n_human')} human, {c.get('n_ai')} AI)")
            continue
        rows.append(
            f"| {tool} | {count(c['fpr'], c['n_human'])} | "
            f"{count(c.get('fpr_domain'), c.get('n_domain'))} | "
            f"{count(c.get('fpr_shuffled'), c.get('n_shuffled'))} | "
            f"{count(c['tpr'], c['n_ai'])} | {pc(c.get('polished_flagged'))} | "
            f"{c['auroc']:.2f} | {c['lr_flag']} | {c['lr_clear']} | {c['date']} |"
        )
    READABLE.write_text(
        "# Web detectors on known texts\n\n"
        "Generated by `web_controls.py analyze`. Do not edit by hand.\n\n"
        "Each detector was run on published human scientific prose from before ChatGPT (some from the "
        "field of the document that prompted the run), on AI-written texts (Claude and GPT), on human "
        "texts rewritten by an AI, and on the human texts with their sentences shuffled (a check that "
        "the detector is not just recognising papers it was trained on). A text counts as flagged when "
        "the tool scores it 0.5 or more.\n\n"
        "| Detector | False alarms | Same field | Shuffled | Caught AI | Flags AI-polished | AUROC | LR if flagged | LR if clear | Tested |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n\n"
        "LR = likelihood ratio, with add-one smoothing so a small sample never gives infinity: how much "
        "more likely the tool's verdict is if the text is AI-written than if it is human. evidence.py "
        f"counts a tool only with at least {MIN_N} human and {MIN_N} AI texts and an AUROC of 0.6 or more.\n"
        + (f"\nNot enough known texts yet: {', '.join(thin)}.\n" if thin else "")
        + "\n## Limits\n\n"
        "- The samples are small: one more miss among 10 AI texts moves a detection rate by 10 points.\n"
        "- The AI texts come from a few models prompted to write like scientists. Other models, careful "
        "prompting and human editing after generation are harder to catch.\n"
        "- Sites change their models without notice. Re-run monthly (`watch.py`) and after any visible change.\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    """Dispatch."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("cmd", choices=["build", "shuffle", "domain", "analyze"])
    p.add_argument(
        "--query",
        action="append",
        help="Europe PMC query for domain controls (repeatable)",
    )
    p.add_argument("--dir", default="/tmp/ai_text_detection_controls")
    p.add_argument("--n", type=int, default=8)
    args = p.parse_args(argv)
    d = Path(args.dir)
    if args.cmd == "domain":
        out = domain(d, args.query or [], args.n)
        for u in out["units"]:
            print(
                f"{u['chunk']}: {u['n_words']} words, {u.get('year')}, {u.get('country')}, {u['source_url']}"
            )
        return 0
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
