"""Combine every detector, every split and the known-text calibration into one picture.

For each sentence of the prose, every unit that contains it (section S, passage P, window
W) and every tool that scored that unit gives a vote: AI (score >= 0.5) or human. A tool's
votes on a sentence are averaged across splits (v = share of its units that say AI), and
turned into evidence with the tool's likelihood ratios measured on known texts
(references/web_calibration.json, web_controls.py):

    tool evidence on a sentence = v * log(LR_flag) + (1 - v) * log(LR_clear)

A tool is used only if it was calibrated on at least 5 human and 5 AI texts and did
better than chance there (AUROC >= 0.6); otherwise it is shown but not counted. Tools
are combined conservatively, assuming they share part of their mistakes:

    combined = mean(tool evidence) * sqrt(number of tools used)

Positive means the text looks more like the AI texts the tools were tested on, negative
more like the human ones; exp(combined) reads as "N times more likely". Sentence values
are averaged (by words) into passage and document values.

Stability: for each tool, the share of sentences on which its verdict depends on the
split (some units containing the sentence say AI, others human).

Inputs (work folder): multi/plan.json and multi/plan.results.jsonl (segments.py and the
drivers in --plan mode), web_detectors.json (passage results; passages P1.. equal its
chunks 1..), the highlight files, and references/web_calibration.json.
Writes ``<work>/evidence.json``.

Usage:
    python evidence.py [--work /tmp/ai_text_detection]
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

from _common import REFS, WORK_DIR, read_json, read_jsonl, write_json

MIN_N = 5
MIN_AUROC = 0.6


def load_results(work: Path) -> dict[tuple[str, str], float]:
    """Latest score per (tool, unit id), from the multi-split log and the passage results."""
    out: dict[tuple[str, str], float] = {}
    for r in (read_json(work / "web_detectors.json") or {}).get("results", []):
        out[(r["tool"], f"P{r['chunk']}")] = float(r["score"])
    for r in read_jsonl(work / "multi" / "plan.results.jsonl"):
        if r.get("score") is not None:
            out[(r["tool"], str(r["chunk"]))] = float(r["score"])
    return out


def tool_weights(cal: dict, tools: set[str]) -> dict[str, dict]:
    """Which tools count, with their log likelihood ratios, and why the others do not."""
    out = {}
    for t in sorted(tools):
        c = (cal.get("tools") or {}).get(t)
        if not c:
            out[t] = {"used": False, "why": "not yet tested on known texts"}
        elif (c.get("n_human") or 0) < MIN_N or (c.get("n_ai") or 0) < MIN_N:
            out[t] = {
                "used": False,
                "why": f"tested on too few known texts ({c.get('n_human')} human, {c.get('n_ai')} AI)",
            }
        elif (c.get("auroc") or 0) < MIN_AUROC:
            out[t] = {
                "used": False,
                "why": f"no better than chance on known scientific texts (AUROC {c.get('auroc')})",
            }
        else:
            out[t] = {
                "used": True,
                "log_flag": math.log(c["lr_flag"]),
                "log_clear": math.log(c["lr_clear"]),
                "cal": c,
            }
        out[t].setdefault("cal", c)
    return out


def main(argv: list[str] | None = None) -> int:
    """Compute and write evidence.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    args = p.parse_args(argv)
    work = Path(args.work)
    plan = read_json(work / "multi" / "plan.json")
    if not plan:
        print("no multi-split plan (segments.py); nothing to combine")
        return 0
    units = {u["chunk"]: u for u in plan["units"]}
    sents = plan["sentences"]
    res = load_results(work)
    tools = {t for t, _ in res}
    weights = tool_weights(read_json(REFS / "web_calibration.json") or {}, tools)
    used = [t for t in tools if weights[t]["used"]]

    def contains(u: dict, s: dict) -> bool:
        return any(a <= s["start"] and s["end"] <= b for a, b in u["spans"])

    # Sentence -> units containing it (once, all scales).
    cover = {
        s["id"]: [uid for uid, u in units.items() if contains(u, s)] for s in sents
    }
    out_s, unstable = [], {t: [0, 0] for t in tools}
    for s in sents:
        per_tool, ev = {}, []
        for t in tools:
            votes = [res[(t, uid)] >= 0.5 for uid in cover[s["id"]] if (t, uid) in res]
            if not votes:
                continue
            v = sum(votes) / len(votes)
            per_tool[t] = {"v": round(v, 3), "n": len(votes)}
            unstable[t][1] += 1
            if 0 < v < 1:
                unstable[t][0] += 1
            if t in used:
                w = weights[t]
                ev.append(v * w["log_flag"] + (1 - v) * w["log_clear"])
        comb = (sum(ev) / len(ev)) * math.sqrt(len(ev)) if ev else None
        out_s.append(
            {
                **s,
                "tools": per_tool,
                "evidence": None if comb is None else round(comb, 3),
                "n_tools": len(ev),
            }
        )

    def wmean(rows: list[dict]) -> float | None:
        rows = [r for r in rows if r["evidence"] is not None]
        tot = sum(r["n_words"] for r in rows)
        return (
            round(sum(r["evidence"] * r["n_words"] for r in rows) / tot, 3)
            if tot
            else None
        )

    passages = []
    for uid, u in units.items():
        if u["scale"] != "P":
            continue
        rows = [r for r in out_s if contains(u, r)]
        passages.append(
            {"chunk": uid, "evidence": wmean(rows), "n_sentences": len(rows)}
        )
    doc_ev = wmean(out_s)
    stability = {t: (round(a / b, 3) if b else None) for t, (a, b) in unstable.items()}
    write_json(
        work / "evidence.json",
        {
            "tools": {
                t: {k: v for k, v in w.items() if k != "cal"} | {"cal": w.get("cal")}
                for t, w in weights.items()
            },
            "used": sorted(used),
            "document": {
                "evidence": doc_ev,
                "times": None if doc_ev is None else round(math.exp(doc_ev), 2),
            },
            "passages": passages,
            "sentences": out_s,
            "stability": stability,
            "units_scored": {
                t: sorted(uid for (tt, uid) in res if tt == t) for t in tools
            },
        },
    )
    print(
        f"tools used in the combination: {', '.join(sorted(used)) or 'none (none calibrated well enough yet)'}"
    )
    for t, w in weights.items():
        if not w["used"]:
            print(f"  not used: {t}: {w['why']}")
    if doc_ev is not None:
        print(
            f"document: combined evidence {doc_ev:+.2f} (about {math.exp(doc_ev):.2f} times as likely under AI as under human)"
        )
    for pa in passages:
        if pa["evidence"] is not None:
            print(f"  {pa['chunk']}: {pa['evidence']:+.2f}")
    print(
        "stability (share of sentences whose verdict depends on the split): "
        + ", ".join(f"{t} {v:.0%}" for t, v in stability.items() if v is not None)
    )
    _ = re
    return 0


if __name__ == "__main__":
    sys.exit(main())
